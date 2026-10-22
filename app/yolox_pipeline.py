"""YOLOX bottle localization and model-predicted bottle colors.

Color decisions use detector class channels exclusively. This module has no
pixel-color classifier and does not touch camera, barcode, or motion devices.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np

from .model_classes import (build_color_map, class_names_from_metadata,
                            parse_class_names)
from .vendor.inference import Detector, DetectorConfig
from .vendor.inference.backends.onnx_backend import ONNXBackend


class _ModelBackend(ONNXBackend):
    """Expose the open session's model description without changing vendor code."""

    def model_details(self) -> dict[str, Any]:
        if self._session is None:
            raise RuntimeError("Open the YOLOX model before reading its metadata.")
        details = {
            "metadata": dict(self._session.get_modelmeta().custom_metadata_map),
            "input_shape": list(self._session.get_inputs()[0].shape),
            "output_shape": list(self._session.get_outputs()[0].shape),
        }
        # Some valid YOLOX exports mark even the class axis as symbolic. Measure
        # that axis once with a blank tensor so labels are checked against the
        # actual graph rather than trusting a configured/metadata class count.
        output = details["output_shape"]
        if len(output) == 3 and _fixed_dimension(output[-1]) is None:
            if self._cfg is None:
                raise RuntimeError("YOLOX backend has no input configuration.")
            _validate_input_shape(details["input_shape"], self._cfg.img_size)
            tensor = np.zeros((1, 3, self._cfg.img_size, self._cfg.img_size), dtype=np.float32)
            outputs = self.infer_raw(tensor)
            if not outputs:
                raise ValueError("YOLOX model produced no detection output.")
            details["output_shape"] = list(outputs[0].shape)
        return details


@dataclass
class _Model:
    detector: Detector
    names: list[str]
    class_count: int
    colors: dict[int, str]
    path: Path
    confidence: float


def _fixed_dimension(value: Any) -> int | None:
    return value if isinstance(value, int) and not isinstance(value, bool) else None


def _validate_input_shape(shape: list, image_size: int) -> None:
    if len(shape) != 4 or _fixed_dimension(shape[1]) != 3:
        raise ValueError("YOLOX input must have shape [1, 3, height, width].")
    if _fixed_dimension(shape[0]) not in (None, 1):
        raise ValueError("Use a YOLOX model exported with batch size 1.")
    for dimension in shape[2:]:
        if _fixed_dimension(dimension) not in (None, image_size):
            raise ValueError(f"YOLOX model input is {shape[2:]}; set its image size to match the square export.")


def _class_count(details: dict, image_size: int) -> int:
    _validate_input_shape(details["input_shape"], image_size)
    output = details["output_shape"]
    channels = _fixed_dimension(output[-1]) if output else None
    if (len(output) != 3 or _fixed_dimension(output[0]) not in (None, 1)
            or channels is None or channels <= 5):
        raise ValueError("YOLOX output must be [1, N, 5+C] with a fixed class count. Export the detection head without NMS.")
    return channels - 5


def _iou(first, second) -> float:
    ax, ay, bx, by = first
    cx, cy, dx, dy = second
    intersection = max(0.0, min(bx, dx) - max(ax, cx)) * max(0.0, min(by, dy) - max(ay, cy))
    union = (bx - ax) * (by - ay) + (dx - cx) * (dy - cy) - intersection
    return intersection / union if union > 0 else 0.0


def _groups(detections: list, threshold: float = 0.50) -> list[list]:
    """Class-agnostic NMS groups retain conflicts for the color decision."""
    remaining = sorted(detections, key=lambda item: item.score, reverse=True)
    groups = []
    while remaining:
        best, remaining = remaining[0], remaining[1:]
        duplicates = [item for item in remaining if _iou(best.xyxy, item.xyxy) >= threshold]
        groups.append([best, *duplicates])
        remaining = [item for item in remaining if _iou(best.xyxy, item.xyxy) < threshold]
    return groups


class YoloXPipeline:
    """Use either a combined bottle-color YOLOX model or two YOLOX detectors.

    ``infer`` returns parallel ``boxes``, ``colors``, ``color_confidences``,
    ``reasons``, and ``model_labels`` lists, plus total ``inference_ms``.
    Unknown color always carries a rejection reason.
    """

    def __init__(self, settings: dict, root: Path):
        self.settings = dict(settings)
        self.root = Path(root)
        self._parts: _Model | None = None
        self._color: _Model | None = None
        self._mode = str(settings.get("yolox_mode", "two_models"))
        self._pass_color = str(settings.get("pass_color", "orange")).strip().lower()
        self._color_confidence = 0.50

    def _path(self, setting: str, default: str = "") -> Path:
        value = str(self.settings.get(setting, "") or default).strip()
        if not value:
            raise ValueError("Select a trained YOLOX color model (.onnx) for two-model mode.")
        path = Path(value).expanduser()
        return (path if path.is_absolute() else self.root / path).resolve()

    def _open_model(self, path: Path, *, color: bool, second: bool = False) -> _Model:
        if not path.is_file():
            raise ValueError(f"YOLOX model was not found: {path}")
        if path.suffix.lower() != ".onnx":
            raise ValueError("Select a YOLOX ONNX export (.onnx), with its external data file if present.")
        if color and path == (self.root / "models" / "yolox_nano.onnx").resolve():
            raise ValueError("The bundled COCO YOLOX model only locates generic bottles. Select your trained bottle-color YOLOX model; generic class IDs cannot be relabeled as colors.")
        size_key = "color_image_size" if second else "image_size"
        image_size = int(self.settings.get(size_key, self.settings.get("image_size", 640)))
        if image_size < 32 or image_size % 32:
            raise ValueError("YOLOX image size must be a positive multiple of 32.")
        confidence_key = "color_confidence" if second else "confidence"
        confidence = float(self.settings.get(confidence_key, 0.50 if second else 0.25))
        if not math.isfinite(confidence) or not 0 < confidence <= 1:
            raise ValueError("YOLOX confidence must be greater than 0 and at most 1.")
        cfg = DetectorConfig(model_path=str(path), img_size=image_size, conf=confidence,
                             max_det=100, device="cpu", intra_op_threads=int(self.settings.get("inference_threads", 2)),
                             inter_op_threads=1)
        backend = _ModelBackend()
        detector = Detector(cfg, backend=backend)
        try:
            detector.open()
            details = backend.model_details()
            count = _class_count(details, image_size)
            metadata_names = class_names_from_metadata(details.get("metadata"))
            names_key = "color_class_names" if second else "model_class_names"
            names = parse_class_names(self.settings.get(names_key)) or metadata_names
            if names and len(names) != count:
                raise ValueError(f"The YOLOX model has {count} classes, but {len(names)} class names were supplied.")
            # A stock COCO export sometimes carries labels even when renamed.
            if color and len(metadata_names) == 80 and "bottle" in [name.lower() for name in metadata_names]:
                raise ValueError("This COCO YOLOX export predicts generic objects, not trained bottle colors.")
            colors = build_color_map(names, self.settings.get("color_class_map"), count) if color else {}
            if color and self._pass_color not in colors.values():
                raise ValueError("The pass color must be one of the YOLOX model's configured bottle colors.")
            cfg.class_names = names or [f"class_{index}" for index in range(count)]
            return _Model(detector, cfg.class_names, count, colors, path, confidence)
        except Exception:
            detector.close()
            raise

    def open(self) -> "YoloXPipeline":
        self.close()
        self.set_confidence(self.settings.get("confidence", 0.25),
                            self.settings.get("color_confidence", 0.50))
        if self._mode not in {"combined", "two_models"}:
            raise ValueError("Choose combined or two_models for the YOLOX pipeline.")
        if str(self.settings.get("rule", "color")) != "color":
            raise ValueError("Live YOLOX bottle sorting requires the color rule.")
        try:
            if self._mode == "two_models":
                color_path = self._path("color_model_path")
                self._color = self._open_model(color_path, color=True, second=True)
                self._parts = self._open_model(self._path("model_path", "models/yolox_nano.onnx"), color=False)
                locator_class = int(self.settings.get("model_class_id", 39))
                if locator_class < -1 or locator_class >= self._parts.class_count:
                    raise ValueError(f"Bottle locator class ID must be -1 (all classes), or 0 to {self._parts.class_count - 1}.")
            else:
                self._parts = self._open_model(self._path("model_path", "models/yolox_nano.onnx"), color=True)
        except Exception:
            self.close()
            raise
        return self

    def close(self) -> None:
        for model in (self._parts, self._color):
            if model is not None:
                model.detector.close()
        self._parts = self._color = None

    def set_confidence(self, bottle: float, color: float) -> None:
        """Update thresholds without reloading models.

        The video worker calls this at a frame boundary. Validate both values
        before changing either, so an invalid request cannot partially apply.
        A combined model retains boxes at the bottle threshold and makes their
        color unknown when no class prediction reaches the color threshold.
        """
        try:
            bottle, color = float(bottle), float(color)
        except (TypeError, ValueError):
            raise ValueError("YOLOX confidence must be greater than 0 and at most 1.") from None
        if any(not math.isfinite(value) or not 0 < value <= 1 for value in (bottle, color)):
            raise ValueError("YOLOX confidence must be greater than 0 and at most 1.")
        self.settings.update(confidence=bottle, color_confidence=color)
        self._color_confidence = color
        for model, threshold in ((self._parts, bottle), (self._color, color)):
            if model is not None:
                model.confidence = threshold
                model.detector._cfg.conf = threshold

    def describe(self) -> str:
        if self._parts is None:
            return "YOLOX bottle/color pipeline [closed]"
        if self._color is not None:
            return f"YOLOX bottles: {self._parts.path.name}; YOLOX colors: {self._color.path.name}"
        return f"YOLOX bottle/color: {self._parts.path.name} ({self._parts.class_count} classes)"

    @staticmethod
    def _detections(result, model: _Model) -> list:
        valid = []
        for item in result.detections:
            box = item.xyxy
            if (len(box) == 4 and all(math.isfinite(float(value)) for value in box)
                    and box[2] > box[0] and box[3] > box[1]
                    and math.isfinite(item.score) and model.confidence <= item.score <= 1):
                valid.append(item)
        return valid

    @staticmethod
    def _prediction(candidates: list, colors: dict[int, str], *, strict: bool) -> tuple[str, float, str]:
        if not candidates:
            return "unknown", 0.0, ""
        ordered = sorted(candidates, key=lambda item: item.score, reverse=True)
        best = ordered[0]
        color = colors.get(best.class_id, "unknown")
        relevant = ordered if strict else [item for item in ordered if best.score - item.score <= 0.10]
        choices = {colors.get(item.class_id, "unknown") for item in relevant}
        if len(choices) != 1:
            color = "unknown"
        label = " / ".join(dict.fromkeys(item.label for item in relevant if item.label))
        return color, float(best.score) if color != "unknown" else 0.0, label

    def infer(self, frame) -> dict:
        if self._parts is None:
            raise RuntimeError("Open and configure the YOLOX pipeline before inference.")
        parts_result = self._parts.detector.infer(frame)
        parts = self._detections(parts_result, self._parts)
        inference_ms = float(parts_result.inference_ms)
        if self._mode == "two_models":
            locator_class = int(self.settings.get("model_class_id", 39))
            parts = [item for item in parts if locator_class == -1 or item.class_id == locator_class]
        groups = _groups(parts)
        boxes = [tuple(float(value) for value in group[0].xyxy) for group in groups]
        if self._color is None:
            predictions = [self._prediction([item for item in group if item.score >= self._color_confidence],
                                            self._parts.colors, strict=False) for group in groups]
        else:
            color_result = self._color.detector.infer(frame)
            inference_ms += float(color_result.inference_ms)
            assigned = [[] for _ in boxes]
            ambiguous = set()
            for item in self._detections(color_result, self._color):
                x, y = (item.xyxy[0] + item.xyxy[2]) / 2, (item.xyxy[1] + item.xyxy[3]) / 2
                owners = [index for index, box in enumerate(boxes) if box[0] <= x <= box[2] and box[1] <= y <= box[3]]
                if len(owners) == 1:
                    assigned[owners[0]].append(item)
                elif len(owners) > 1:
                    ambiguous.update(owners)
            predictions = [("unknown", 0.0, "Ambiguous color association") if index in ambiguous
                           else self._prediction(items, self._color.colors, strict=True)
                           for index, items in enumerate(assigned)]
        colors, confidences, labels = zip(*predictions) if predictions else ((), (), ())
        reasons = [[] if color == self._pass_color else ["Unknown color"] if color == "unknown"
                   else [f"YOLOX color {color} (divert)"] for color in colors]
        return {"boxes": boxes, "colors": list(colors), "color_confidences": list(confidences),
                "reasons": reasons, "inference_ms": inference_ms, "model_labels": list(labels)}
