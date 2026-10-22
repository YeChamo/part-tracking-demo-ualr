"""YOLOX-S bottle localization with a separate Gatorade demo inspection.

The trained-color YOLOX pipeline remains available for future inspection
models. This mode supplies useful sorting from the current example photos.
"""
from __future__ import annotations

import math
import logging
import time
from concurrent.futures import Future, ThreadPoolExecutor
from pathlib import Path

from .gatorade import GatoradeLabelMatcher, measure_drink_color, neutralize_color_cast
from .inspections import LabelReader, has_gatorade_text, inspect_orange_cap, label_summary
from .vendor.inference import Detector, DetectorConfig


class GatoradePipeline:
    def __init__(self, settings: dict, root: Path):
        self.settings = dict(settings)
        self.root = Path(root)
        self.detector: Detector | None = None
        self.matcher: GatoradeLabelMatcher | None = None
        self.reader: LabelReader | None = None
        self.ocr_pool: ThreadPoolExecutor | None = None
        self.ocr_future: Future | None = None
        self.ocr_box: tuple[float, float, float, float] | None = None
        self.last_ocr_at = 0.0
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
            if self.settings.get("label_ocr", True):
                self.reader = LabelReader()
                self.ocr_pool = ThreadPoolExecutor(max_workers=1,thread_name_prefix='gatorade-ocr')
        except Exception:
            self.close()
            raise
        return self

    def close(self) -> None:
        if self.ocr_pool is not None:
            self.ocr_pool.shutdown(wait=False,cancel_futures=True)
        self.ocr_pool = self.ocr_future = self.ocr_box = None
        if self.detector is not None:
            self.detector.close()
        self.detector = None
        self.matcher = None
        self.reader = None

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
        return "YOLOX-S bottle + color + cap + label"

    @staticmethod
    def _match_ocr_box(old, boxes) -> int | None:
        if old is None or not boxes:
            return None
        ox,oy = (old[0]+old[2])/2,(old[1]+old[3])/2
        ow,oh = old[2]-old[0],old[3]-old[1]
        candidates = []
        for index,box in enumerate(boxes):
            x,y = (box[0]+box[2])/2,(box[1]+box[3])/2
            width,height = box[2]-box[0],box[3]-box[1]
            if (abs(x-ox)<=.4*max(ow,width) and abs(y-oy)<=.35*max(oh,height)
                    and .5<=width/max(ow,1)<=2 and .5<=height/max(oh,1)<=2):
                candidates.append(index)
        return candidates[0] if len(candidates)==1 else None

    def infer(self, frame) -> dict:
        if self.detector is None:
            raise RuntimeError("Open the Gatorade pipeline before inference.")
        result = self.detector.infer(frame)
        class_id = int(self.settings.get("model_class_id", 39))
        detections = [item for item in result.detections
                      if class_id == -1 or item.class_id == class_id]
        boxes = [tuple(item.xyxy) for item in detections]
        started = time.perf_counter()
        color_frame = neutralize_color_cast(frame) if boxes else frame
        colors, confidences, reasons, matches, caps, label_texts = [], [], [], [], [], []
        height, width = frame.shape[:2]
        pass_color = str(self.settings.get("pass_color", "blue")).lower()
        now = time.monotonic()
        completed_ocr = None
        if self.ocr_future is not None and self.ocr_future.done():
            index = self._match_ocr_box(self.ocr_box,boxes)
            if index is not None:
                try:
                    completed_ocr = (index,self.ocr_future.result())
                except Exception:
                    logging.warning('Label OCR failed; color and cap inspection continue.',exc_info=True)
            self.ocr_future = self.ocr_box = None
        if self.reader and self.ocr_pool and boxes and self.ocr_future is None and now-self.last_ocr_at >= .8:
            index = max(range(len(boxes)), key=lambda i:
                        (boxes[i][2]-boxes[i][0])*(boxes[i][3]-boxes[i][1]))
            x1,y1,x2,y2 = (int(round(value)) for value in boxes[index])
            crop = frame[max(0,y1):min(height,y2),max(0,x1):min(width,x2)]
            self.ocr_box = boxes[index]
            self.ocr_future = self.ocr_pool.submit(self.reader.read,crop.copy())
            self.last_ocr_at = now
        for index, box in enumerate(boxes):
            reading = measure_drink_color(color_frame, box)
            color = reading["name"] if reading["confidence"] >= self.color_confidence else "unknown"
            colors.append(color)
            confidences.append(float(reading["confidence"]) if color != "unknown" else 0.0)
            why = ([] if color == pass_color else ["Unknown color"] if color == "unknown"
                   else [f"Gatorade color {color} (divert)"])
            cap = inspect_orange_cap(frame, box)
            caps.append(cap)
            reasons.append(why)
            x1, y1, x2, y2 = (int(round(value)) for value in box)
            x1, y1, x2, y2 = max(0, x1), max(0, y1), min(width, x2), min(height, y2)
            crop = frame[y1:y2, x1:x2]
            label_lines = completed_ocr[1] if completed_ocr and index==completed_ocr[0] else []
            label_texts.append(label_summary(label_lines))
            matches.append(has_gatorade_text(label_lines) or bool(self.matcher and self.matcher.match(crop)))
        return {"boxes": boxes, "colors": colors, "color_confidences": confidences,
                "reasons": reasons, "inference_ms": float(result.inference_ms),
                "inspection_ms": (time.perf_counter() - started) * 1000.0,
                "model_labels": [item.label for item in detections],
                "brand_matches": matches, "caps": caps, "label_texts": label_texts}
