"""YOLOX-S bottle localization with a separate Gatorade demo inspection.

The trained-color YOLOX pipeline remains available for future inspection
models. This mode supplies useful sorting from the current example photos.
"""
from __future__ import annotations

import math
import time
from pathlib import Path

from .gatorade import GatoradeLabelMatcher, measure_drink_color
from .vendor.inference import Detector, DetectorConfig


class GatoradePipeline:
    def __init__(self, settings: dict, root: Path):
        self.settings = dict(settings)
        self.root = Path(root)
        self.detector: Detector | None = None
        self.matcher: GatoradeLabelMatcher | None = None
        self.bottle_confidence = 0.25
        self.color_confidence = 0.50

    def open(self) -> "GatoradePipeline":
        if self.settings.get("rule", "color") != "color":
            raise ValueError("Live Gatorade sorting requires the color rule.")
        self.set_confidence(self.settings.get("confidence", .25),
                            self.settings.get("color_confidence", .50))
        path = Path(self.settings.get("model_path") or "models/yolox_s.onnx").expanduser()
        path = (path if path.is_absolute() else self.root / path).resolve()
        if not path.is_file() or path.suffix.lower() != ".onnx":
            raise ValueError(f"YOLOX-S bottle model was not found: {path}")
        size = int(self.settings.get("image_size", 640))
        if size < 32 or size % 32:
            raise ValueError("YOLOX image size must be a positive multiple of 32.")
        class_id = int(self.settings.get("model_class_id", 39))
        if class_id < -1 or class_id >= 80:
            raise ValueError("COCO bottle class ID must be -1 or 0 to 79.")
        cfg = DetectorConfig(model_path=str(path), img_size=size,
                             conf=self.bottle_confidence, max_det=50,
                             device="cpu", intra_op_threads=int(self.settings.get("inference_threads", 2)),
                             inter_op_threads=1)
        self.detector = Detector(cfg)
        try:
            self.detector.open()
            if self.settings.get("gatorade_label_check", True):
                self.matcher = GatoradeLabelMatcher(self.root / "models")
        except Exception:
            self.close()
            raise
        return self

    def close(self) -> None:
        if self.detector is not None:
            self.detector.close()
        self.detector = None
        self.matcher = None

    def set_confidence(self, bottle: float, color: float) -> None:
        try:
            bottle, color = float(bottle), float(color)
        except (TypeError, ValueError):
            raise ValueError("Confidence must be greater than zero and at most one.") from None
        if any(not math.isfinite(value) or not 0 < value <= 1 for value in (bottle, color)):
            raise ValueError("Confidence must be greater than zero and at most one.")
        self.bottle_confidence, self.color_confidence = bottle, color
        if self.detector is not None:
            self.detector._cfg.conf = bottle

    def describe(self) -> str:
        return "YOLOX-S bottle + Gatorade drink color"

    def infer(self, frame) -> dict:
        if self.detector is None:
            raise RuntimeError("Open the Gatorade pipeline before inference.")
        result = self.detector.infer(frame)
        class_id = int(self.settings.get("model_class_id", 39))
        detections = [item for item in result.detections
                      if class_id == -1 or item.class_id == class_id]
        boxes = [tuple(item.xyxy) for item in detections]
        started = time.perf_counter()
        colors, confidences, reasons, matches = [], [], [], []
        height, width = frame.shape[:2]
        pass_color = str(self.settings.get("pass_color", "blue")).lower()
        for box in boxes:
            reading = measure_drink_color(frame, box)
            color = reading["name"] if reading["confidence"] >= self.color_confidence else "unknown"
            colors.append(color)
            confidences.append(float(reading["confidence"]) if color != "unknown" else 0.0)
            reasons.append([] if color == pass_color else
                           ["Unknown color"] if color == "unknown" else
                           [f"Gatorade color {color} (divert)"])
            x1, y1, x2, y2 = (int(round(value)) for value in box)
            x1, y1, x2, y2 = max(0, x1), max(0, y1), min(width, x2), min(height, y2)
            crop = frame[y1:y2, x1:x2]
            matches.append(bool(self.matcher and self.matcher.match(crop)))
        return {"boxes": boxes, "colors": colors, "color_confidences": confidences,
                "reasons": reasons, "inference_ms": float(result.inference_ms),
                "inspection_ms": (time.perf_counter() - started) * 1000.0,
                "model_labels": [item.label for item in detections],
                "brand_matches": matches}
