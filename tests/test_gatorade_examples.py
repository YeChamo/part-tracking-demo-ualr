"""Optional real-photo localization/tracking checks; no pixel-color classifier.

Private camera photos may live in the sibling examples/ folder (or the
UALR_EXAMPLE_PHOTOS directory). The public COCO fixture is downloaded only by
an explicit verification task into ignored .build/, never by these tests.
"""
from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path
import unittest

import cv2

from app.settings import DEFAULTS
from app.tracking import BottleTracker, TrackingConfig


ROOT = Path(__file__).resolve().parents[1]
EXAMPLES = Path(os.environ.get("UALR_EXAMPLE_PHOTOS", ROOT.parent / "examples"))
PHOTO_NAMES = tuple(f"WIN_20261022_11_04_{second:02d}_Pro.jpg"
                    for second in (3, 7, 9, 11, 14, 16, 20, 25, 27, 29, 35, 38, 40))
PUBLIC = ROOT / ".build" / "bottle-positive-20261022"
PUBLIC_IMAGE = PUBLIC / "photos" / "000000000283.jpg"
RUNTIME = importlib.util.find_spec("onnxruntime") is not None


def _iou(a, b):
    intersection = max(0, min(a[2], b[2]) - max(a[0], b[0])) * max(0, min(a[3], b[3]) - max(a[1], b[1]))
    union = (a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - intersection
    return intersection / union if union > 0 else 0.0


def _pipeline(model):
    from app.yolox_pipeline import YoloXPipeline
    return YoloXPipeline(dict(DEFAULTS, visual_only=True, yolox_mode="tracking", rule="tracking",
                              model_path=str(ROOT / "models" / model), model_class_id=39,
                              color_model_path="", confidence=.25, auto_model_config=True,
                              inference_backend="cpu"), ROOT).open()


def _ground_truth(image_path, frame):
    height, width = frame.shape[:2]
    boxes = []
    for line in image_path.with_suffix(".txt").read_text(encoding="utf-8").splitlines():
        category, x, y, bw, bh = map(float, line.split())
        if category == 39:
            boxes.append(((x - bw / 2) * width, (y - bh / 2) * height,
                          (x + bw / 2) * width, (y + bh / 2) * height))
    return boxes


def _record_production_check(value):
    evidence = PUBLIC / "evidence.json"
    record = json.loads(evidence.read_text(encoding="utf-8")) if evidence.is_file() else {}
    record["production_tracking_check"] = value
    record["scope"] = "Real COCO train images; smoke test only, not held-out or Gatorade/color accuracy."
    evidence.write_text(json.dumps(record, indent=2), encoding="utf-8")


@unittest.skipUnless(RUNTIME and all((EXAMPLES / name).is_file() for name in PHOTO_NAMES),
                     "private supplied camera photos are outside this source checkout")
class PrivateCameraPhotoTests(unittest.TestCase):
    def test_yolox_localizes_real_bottles_without_a_color_model(self):
        pipeline = _pipeline("yolox_s.onnx")
        self.addCleanup(pipeline.close)
        for filename in PHOTO_NAMES:
            with self.subTest(photo=filename):
                frame = cv2.imread(str(EXAMPLES / filename))
                self.assertIsNotNone(frame)
                result = pipeline.infer(frame)
                self.assertTrue(result["boxes"], filename)
                self.assertTrue(result["visual_only"])
                self.assertTrue(all(name == "bottle" for name in result["model_labels"]))


@unittest.skipUnless(RUNTIME and PUBLIC_IMAGE.is_file() and PUBLIC_IMAGE.with_suffix(".txt").is_file(),
                     "optional public real-bottle fixture is not downloaded in ignored .build/")
class PublicBottlePhotoTests(unittest.TestCase):
    def test_both_real_bundled_models_match_an_annotated_bottle(self):
        frame = cv2.imread(str(PUBLIC_IMAGE))
        self.assertIsNotNone(frame)
        targets = _ground_truth(PUBLIC_IMAGE, frame)
        self.assertTrue(targets)
        for model in ("yolox_nano.onnx", "yolox_s.onnx"):
            with self.subTest(model=model):
                pipeline = _pipeline(model)
                try:
                    result = pipeline.infer(frame)
                    matches = [score for box, score in zip(result["boxes"], result["confidences"])
                               if max(_iou(box, target) for target in targets) >= .5]
                    self.assertTrue(matches, f"{model} must match a real annotated bottle")
                    self.assertGreater(max(matches), .25)
                finally:
                    pipeline.close()

    def test_real_detections_reach_tracker_with_stable_ids_and_no_routes(self):
        frame = cv2.imread(str(PUBLIC_IMAGE))
        targets = _ground_truth(PUBLIC_IMAGE, frame)
        pipeline = _pipeline("yolox_nano.onnx")
        self.addCleanup(pipeline.close)
        tracker = BottleTracker(TrackingConfig(visual_only=True))
        bottle_ids = []
        score = 0.0
        overlap = 0.0
        height, width = frame.shape[:2]
        for index in range(4):
            result = pipeline.infer(frame)
            self.assertTrue(result["visual_only"])
            tracks, decisions = tracker.update(result["boxes"], result["reasons"],
                                               1 + index * .1, width, height, moving=False)
            self.assertEqual(decisions, [])
            matching = [track for track in tracks if max(_iou(track.bbox, target) for target in targets) >= .5]
            self.assertTrue(matching)
            bottle_ids.append(matching[0].id)
            for box, confidence in zip(result["boxes"], result["confidences"]):
                current = max(_iou(box, target) for target in targets)
                if current > overlap:
                    score, overlap = confidence, current
        self.assertEqual(len(set(bottle_ids)), 1)
        _record_production_check({"image": PUBLIC_IMAGE.name, "model": "yolox_nano.onnx",
                                  "real_bottle_confidence": score, "ground_truth_iou": overlap,
                                  "frames": 4, "stable_bottle_ids": bottle_ids,
                                  "routing_decisions": 0, "camera_opened": False,
                                  "motion_requested": False, "synthetic_weights": False})


if __name__ == "__main__":
    unittest.main()
