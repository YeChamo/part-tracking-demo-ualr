"""YOLOX bottle localization and trained neural-network color predictions.

Color decisions use trained detector/classifier outputs exclusively. This module
has no hand-coded pixel-color rules and does not touch camera, barcode, or motion devices.
"""
from __future__ import annotations

import math
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np

from .model_classes import (build_color_map, class_names_from_metadata,
                            parse_class_names)
from .vendor.inference import DetectorConfig, InferenceError
from .accelerated_backend import AcceleratedONNXBackend
from .checkpoint_export import prepare_model
from .model_runtime import ModelDetector as Detector
from .sorting_colors import canonical_sort_color


class _ModelBackend(AcceleratedONNXBackend):
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
            automatic = bool(getattr(self, 'auto_model_config', False))
            _validate_input_shape(details['input_shape'], self._cfg.img_size, automatic=automatic)
            # Use the same shape resolver as CPU/TensorRT warmup. Symbolic
            # spatial axes may have rectangular input_size/test_size metadata;
            # substituting img_size twice here would violate a warmed engine's
            # fixed profile even though its first warmup used the right shape.
            input_shape = (self._shape(self._session, self._cfg) if automatic
                           else (1, 3, self._cfg.img_size, self._cfg.img_size))
            tensor = np.zeros(input_shape, dtype=np.float32)
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


def _validate_input_shape(shape: list, image_size: int, *, automatic=False) -> None:
    if len(shape) != 4 or _fixed_dimension(shape[1]) != 3:
        raise ValueError("YOLOX input must have shape [1, 3, height, width].")
    if _fixed_dimension(shape[0]) not in (None, 1):
        raise ValueError("Use a YOLOX model exported with batch size 1.")
    for dimension in shape[2:]:
        if automatic:
            if _fixed_dimension(dimension) is not None and dimension <= 0:
                raise ValueError('YOLOX image dimensions must be positive.')
        elif _fixed_dimension(dimension) not in (None, image_size):
            raise ValueError(f"YOLOX model input is {shape[2:]}; set its image size to match the square export.")


def _class_count(details: dict, image_size: int, *, automatic=False) -> int:
    _validate_input_shape(details["input_shape"], image_size,automatic=automatic)
    output = details["output_shape"]
    channels = _fixed_dimension(output[-1]) if output else None
    if (len(output) != 3 or _fixed_dimension(output[0]) not in (None, 1)
            or channels is None or channels <= 5):
        hint = (" This is a class-score output, not bottle detections."
                " For distilV4_student.onnx choose 'Bundled color neural network' under Color model type;"
                " the Bottle model should be yolox_nano.onnx."
                if len(output) == 2 else " Export the detection head without NMS.")
        raise ValueError(f"YOLOX output must be [1, N, 5+C] with a fixed class count; got {output}.{hint}")
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
    """Use YOLOX bottles with a combined or separate trained color network.

    ``infer`` returns parallel ``boxes``, ``colors``, ``color_confidences``,
    ``reasons``, and ``model_labels`` lists, plus total ``inference_ms``.
    Sorting mode gives unknown color a rejection reason. Visual mode reports
    model colors without emitting sorting decisions.
    """

    def __init__(self, settings: dict, root: Path):
        self.settings = dict(settings)
        self.root = Path(root)
        self._parts: _Model | None = None
        self._color: _Model | None = None
        self._classifier = None
        self._classifier_path: Path | None = None
        self._color_backend = str(settings.get("color_backend", "yolox")).strip().casefold()
        self._mode = str(settings.get("yolox_mode", "tracking"))
        self._visual_only = bool(settings.get("visual_only", self._mode == "tracking")) or self._mode == "tracking"
        if self._visual_only and self._mode != "combined":
            # Visual tracking can optionally add a trained color detector.
            # The default bottle locator remains useful without color weights.
            self._mode = "two_models" if str(settings.get("color_model_path", "") or "").strip() else "tracking"
        self.settings.update(visual_only=self._visual_only, yolox_mode=self._mode)
        self._pass_color = canonical_sort_color(settings.get("pass_color", "orange"))
        self._color_confidence = 0.50
        self.progress = None
        self.cancelled = None

    def _path(self, setting: str, default: str = "") -> Path:
        value = str(self.settings.get(setting, "") or default).strip()
        if not value:
            raise ValueError("Select a trained YOLOX color model (.pth, .pt or .onnx) for two-model mode.")
        path = Path(value).expanduser()
        return (path if path.is_absolute() else self.root / path).resolve()

    def _open_model(self, path: Path, *, color: bool, second: bool = False) -> _Model:
        if not path.is_file():
            raise ValueError(f"YOLOX model was not found: {path}")
        if path.suffix.lower() not in ('.onnx','.pth','.pt'):
            raise ValueError("Select a YOLOX checkpoint (.pth/.pt) or ONNX model (.onnx).")
        bundled_locators = {(self.root / "models" / name).resolve()
                            for name in ("yolox_nano.onnx", "yolox_s.onnx")}
        if color and path in bundled_locators:
            raise ValueError("The bundled COCO YOLOX model only locates generic bottles. Select your trained bottle-color YOLOX model; generic class IDs cannot be relabeled as colors.")
        size_key = "color_image_size" if second else "image_size"
        image_size = int(self.settings.get(size_key, self.settings.get("image_size", 640)))
        automatic=bool(self.settings.get('auto_model_config',False))
        names_key = "color_class_names" if second else "model_class_names"
        original_path=path
        path=prepare_model(path,self.root,None if automatic else image_size,
                           class_names=self.settings.get(names_key,''),
                           architecture=self.settings.get('color_architecture' if second else 'model_architecture','auto'),
                           experiment_path=self.settings.get('color_experiment_path' if second else 'model_experiment_path',''),
                           progress=self.progress,cancelled=self.cancelled)
        if image_size < 1 or (not automatic and (image_size < 32 or image_size % 32)):
            raise ValueError("YOLOX image size must be positive; manual square sizes must be multiples of 32.")
        confidence_key = "color_confidence" if second else "confidence"
        confidence = float(self.settings.get(confidence_key, 0.50 if second else 0.25))
        if not math.isfinite(confidence) or not 0 < confidence <= 1:
            raise ValueError("YOLOX confidence must be greater than 0 and at most 1.")
        cfg = DetectorConfig(model_path=str(path), img_size=image_size, conf=confidence,
                             max_det=100, device="cpu", intra_op_threads=int(self.settings.get("inference_threads", 2)),
                             inter_op_threads=1)
        backend = _ModelBackend(cache_root=self.root/'data'/'engine_cache',
                                mode=self.settings.get('inference_backend','auto'),
                                progress=self.progress,cancelled=self.cancelled)
        backend.auto_model_config=automatic
        detector = Detector(cfg, backend=backend)
        try:
            detector.open()
            details = backend.model_details()
            count = _class_count(details, image_size,automatic=automatic)
            if automatic and all(_fixed_dimension(v) for v in details['input_shape'][2:]):
                cfg.img_size=max(details['input_shape'][2:])
            if hasattr(detector,'configure_model'):
                detector.configure_model(details.get('metadata',{}),details['input_shape'])
            metadata_names = class_names_from_metadata(details.get("metadata"))
            names = parse_class_names(self.settings.get(names_key)) or metadata_names
            if count == 80 and original_path in bundled_locators:
                if not names:
                    names = [f"class_{index}" for index in range(count)]
                if len(names) == count and names[39].casefold() in {"39", "class_39"}:
                    names[39] = "bottle"
            if names and len(names) != count:
                raise ValueError(f"The YOLOX model has {count} classes, but {len(names)} class names were supplied.")
            # A stock COCO export sometimes carries labels even when renamed.
            if color and len(metadata_names) == 80 and "bottle" in [name.lower() for name in metadata_names]:
                raise ValueError("This COCO YOLOX export predicts generic objects, not trained bottle colors.")
            colors = build_color_map(names, self.settings.get("color_class_map"), count,
                                     allow_class_labels=True) if color else {}
            colors = {index: canonical_sort_color(value) for index, value in colors.items()}
            if color and not self._visual_only and self._pass_color not in colors.values() and not self.settings.get('_inspect_models'):
                raise ValueError("Choose a pass color/class from this model: "+', '.join(dict.fromkeys(colors.values()))+'.')
            cfg.class_names = names or [f"class_{index}" for index in range(count)]
            return _Model(detector, cfg.class_names, count, colors, original_path, confidence)
        except Exception as exc:
            detector.close()
            slot = 'YOLOX color model' if second else 'Combined bottle/color YOLOX model' if color else 'Bottle YOLOX model'
            hint = (" Put distilV4_student.onnx in Color model with Color model type set to"
                    " 'Bundled color neural network', and yolox_nano.onnx in Bottle model."
                    if original_path.name.casefold() == 'distilv4_student.onnx' else '')
            error_type = type(exc) if isinstance(exc, (ValueError, InferenceError)) else RuntimeError
            raise error_type(f"{slot} '{original_path}': {exc}{hint}") from exc

    def open(self) -> "YoloXPipeline":
        self.close()
        self.set_confidence(self.settings.get("confidence", 0.25),
                            self.settings.get("color_confidence", 0.50))
        if self._mode not in {"tracking", "combined", "two_models"}:
            raise ValueError("Choose tracking, combined, or two_models for the YOLOX pipeline.")
        if not self._visual_only and str(self.settings.get("rule", "color")) != "color":
            raise ValueError("Live YOLOX bottle sorting requires the color rule.")
        if self._color_backend not in {"yolox", "classifier"}:
            raise ValueError("Choose yolox or classifier for the color backend.")
        try:
            if self._mode in {"tracking", "two_models"}:
                if self._mode == "two_models":
                    color_path = self._path("color_model_path")
                    if self._color_backend == "classifier":
                        if not color_path.is_file():
                            raise ValueError(f"Color model was not found: {color_path}")
                        from .color_classifier import ColorClassifier
                        self._classifier_path = color_path
                        self._classifier = ColorClassifier(color_path)
                        try:
                            self._classifier.open()
                        except Exception as exc:
                            raise ValueError(f"Color neural network '{color_path}': {exc}"
                                             " Use the bundled distilV4_student.onnx with this model type;"
                                             " for a YOLOX color detector change Color model type to 'YOLOX color detector'.") from exc
                        available = list(dict.fromkeys(canonical_sort_color(name) for name in self._classifier.names))
                        if (not self._visual_only and self._pass_color not in available
                                and not self.settings.get('_inspect_models')):
                            raise ValueError("Choose a pass color/class from this model: "
                                             + ', '.join(available) + '.')
                    else:
                        self._color = self._open_model(color_path, color=True, second=True)
                self._parts = self._open_model(self._path("model_path", "models/yolox_nano.onnx"), color=False)
                locator_class = int(self.settings.get("model_class_id", 39))
                if self.settings.get('auto_model_config') and locator_class==39 and self._parts.class_count<=39:
                    choices=[index for index,name in enumerate(self._parts.names) if name.casefold() in ('bottle','bottles')]
                    locator_class=choices[0] if len(choices)==1 else 0 if self._parts.class_count==1 else -1
                    self.settings['model_class_id']=locator_class
                if locator_class < -1 or locator_class >= self._parts.class_count:
                    raise ValueError(f"Bottle locator class ID must be -1 (all classes), or 0 to {self._parts.class_count - 1}.")
            else:
                self._parts = self._open_model(self._path("model_path", "models/yolox_nano.onnx"), color=True)
        except Exception:
            self.close()
            raise
        return self

    def information(self) -> dict:
        color=self._color or self._parts
        models=[{'path':str(model.path),'class_names':model.names,
                 'input_shape':list(getattr(model.detector._cfg,'input_hw',(model.detector._cfg.img_size,)*2))}
                for model in (self._parts,self._color) if model is not None]
        if self._classifier is not None:
            models.append({'path':str(self._classifier_path),'class_names':list(self._classifier.names),
                           'input_shape':list(getattr(self._classifier,'input_shape',()))})
        return {'colors':list(dict.fromkeys(canonical_sort_color(name) for name in self._classifier.names)) if self._classifier is not None else
                         list(dict.fromkeys(color.colors.values())) if color else [],
                'visual_only':self._visual_only,
                'models':models,
                'description':self.describe()}

    def close(self) -> None:
        for model in (self._parts, self._color):
            if model is not None:
                model.detector.close()
        self._parts = self._color = None
        if self._classifier is not None:
            self._classifier.close()
        self._classifier = self._classifier_path = None

    def set_confidence(self, bottle: float, color: float) -> None:
        """Update thresholds without reloading models.

        The video worker calls this at a frame boundary. Validate both values
        before changing either, so an invalid request cannot partially apply.
        A combined model retains boxes at the bottle threshold and makes their
        color unknown when no class prediction reaches the color threshold.
        """
        try:
            bottle = float(bottle)
            color = self._color_confidence if self._visual_only and self._mode == "tracking" else float(color)
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
        if self._visual_only:
            base=f"YOLOX bottle tracking: {self._parts.path.name}"
            if self._color is not None:
                base += f"; YOLOX colors: {self._color.path.name}"
            elif self._classifier is not None:
                base += f"; color NN: {self._classifier_path.name}"
            elif self._mode == "combined":
                base += " (bottle/color model)"
        elif self._color is not None:
            base=f"YOLOX bottles: {self._parts.path.name}; YOLOX colors: {self._color.path.name}"
        elif self._classifier is not None:
            base=f"YOLOX bottles: {self._parts.path.name}; color NN: {self._classifier_path.name}"
        else:
            base=f"YOLOX bottle/color: {self._parts.path.name} ({self._parts.class_count} classes)"
        backend=getattr(self._parts.detector,'_backend',None)
        runtime=getattr(backend,'actual_mode','cpu')
        return base+' • '+('ONNX CPU' if runtime=='cpu' else runtime)

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
        if self._mode in {"tracking", "two_models"}:
            locator_class = int(self.settings.get("model_class_id", 39))
            parts = [item for item in parts if locator_class == -1 or item.class_id == locator_class]
        groups = _groups(parts)
        boxes = [tuple(float(value) for value in group[0].xyxy) for group in groups]
        if self._classifier is not None:
            started = time.perf_counter()
            predictions = [self._classify_bottle(frame, box) for box in boxes]
            inference_ms += (time.perf_counter() - started) * 1000
        elif self._color is None:
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
        if self._visual_only:
            return {"boxes": boxes, "colors": list(colors),
                    "color_confidences": list(confidences),
                    "confidences": [float(group[0].score) for group in groups],
                    "reasons": [[] for _ in boxes], "inference_ms": inference_ms,
                    "model_labels": [group[0].label for group in groups], "visual_only": True}
        source = "Color NN" if self._classifier is not None else "YOLOX color"
        reasons = [[] if color == self._pass_color else ["Unknown color"] if color == "unknown"
                   else [f"{source} {color} (divert)"] for color in colors]
        return {"boxes": boxes, "colors": list(colors), "color_confidences": list(confidences),
                "reasons": reasons, "inference_ms": inference_ms, "model_labels": list(labels)}

    def _classify_bottle(self, frame, box) -> tuple[str, float, str]:
        """Apply the trained classifier's own bottle ROI once, with no pixel rule."""
        height, width = frame.shape[:2]
        left, top, right, bottom = box
        roi = getattr(self._classifier, "bottle_crop", (0.0, 0.0, 1.0, 1.0))
        x1 = max(0, min(width, math.floor(left + (right - left) * roi[0])))
        y1 = max(0, min(height, math.floor(top + (bottom - top) * roi[1])))
        x2 = max(0, min(width, math.ceil(left + (right - left) * roi[2])))
        y2 = max(0, min(height, math.ceil(top + (bottom - top) * roi[3])))
        if x2-x1 < 2 or y2-y1 < 2:
            return "unknown", 0.0, ""
        color, confidence = self._classifier.infer(frame[y1:y2, x1:x2])
        confidence = float(confidence)
        if not math.isfinite(confidence) or not 0 <= confidence <= 1:
            raise ValueError("Color classifier returned an invalid confidence.")
        if color not in self._classifier.names or confidence < self._color_confidence:
            return "unknown", 0.0, ""
        return canonical_sort_color(color), confidence, color
