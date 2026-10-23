"""Visual-only IDs and real model startup, without camera or motion control."""
import importlib.util
from pathlib import Path
import unittest

import numpy as np

from app.settings import DEFAULTS
from app.tracking import BottleTracker, TrackingConfig


class VisualTrackingTests(unittest.TestCase):
    def test_default_recipe_is_ready_for_one_bundled_bottle_model(self):
        self.assertTrue(DEFAULTS["visual_only"])
        self.assertEqual(DEFAULTS["yolox_mode"], "tracking")
        self.assertEqual(DEFAULTS["rule"], "tracking")
        self.assertEqual(DEFAULTS["model_path"], "models/yolox_nano.onnx")
        self.assertEqual(DEFAULTS["model_class_id"], 39)
        self.assertEqual(DEFAULTS["inference_backend"], "cpu")
        self.assertEqual(DEFAULTS["color_model_path"], "")

    def test_centered_stationary_bottle_gets_a_stable_id_without_entry_zone(self):
        tracker = BottleTracker(TrackingConfig(visual_only=True))
        box = (450, 100, 550, 300)
        ids = []
        for index in range(5):
            tracks, decisions = tracker.update([box], [["Unknown color"]], 1 + index * .1,
                                               1000, 400, moving=False)
            self.assertEqual(len(tracks), 1)
            self.assertFalse(tracks[0].bad)
            self.assertEqual(tracks[0].reasons, [])
            self.assertEqual(decisions, [])
            ids.append(tracks[0].id)
        self.assertEqual(len(set(ids)), 1)
        self.assertEqual(tracks[0].hits, 5)

    def test_bottles_can_first_appear_beyond_the_old_decision_line(self):
        tracker = BottleTracker(TrackingConfig(visual_only=True))
        tracks, decisions = tracker.update([(850, 100, 950, 300)], [[]], 1, 1000, 400)
        self.assertEqual(len(tracks), 1)
        self.assertEqual(decisions, [])

    def test_crossing_the_entire_view_never_emits_a_pass_or_reject_decision(self):
        tracker = BottleTracker(TrackingConfig(visual_only=True))
        ids = []
        for index, x in enumerate(range(450, 851, 40)):
            tracks, decisions = tracker.update([(x, 100, x + 60, 280)], [["Color: blue (divert)"]],
                                               1 + index * .1, 1000, 400)
            self.assertEqual(decisions, [])
            self.assertEqual(len(tracks), 1)
            self.assertFalse(tracks[0].bad)
            self.assertFalse(tracks[0].decided)
            ids.append(tracks[0].id)
        self.assertEqual(len(set(ids)), 1)

    def test_sorting_mode_retains_its_entry_zone_requirement(self):
        tracker = BottleTracker(TrackingConfig(visual_only=False))
        self.assertEqual(tracker.update([(450, 100, 550, 300)], [[]], 1, 1000, 400), ([], []))

    def test_visual_hand_demo_can_reverse_and_turn_around_without_changing_id(self):
        tracker = BottleTracker(TrackingConfig(visual_only=True))
        ids = []
        for index, x in enumerate((400, 440, 480, 440, 400, 360, 400, 440)):
            tracks, decisions = tracker.update([(x, 100, x + 60, 280)], [[]],
                                               1 + index * .1, 1000, 400)
            self.assertEqual(len(tracks), 1)
            self.assertEqual(decisions, [])
            ids.append(tracks[0].id)
        self.assertEqual(len(set(ids)), 1)


@unittest.skipUnless(importlib.util.find_spec("onnxruntime"), "Real model startup requires ONNX Runtime")
class RealBottleTrackingTests(unittest.TestCase):
    def test_real_stock_nano_opens_and_tracks_without_any_color_model(self):
        from app.yolox_pipeline import YoloXPipeline
        root = Path(__file__).resolve().parents[1]
        if not (root / DEFAULTS["model_path"]).is_file():
            self.skipTest("Bundled Nano is not present in this source checkout")
        settings = dict(DEFAULTS, color_model_path="", pass_color="not-a-trained-color")
        pipeline = YoloXPipeline(settings, root)
        self.addCleanup(pipeline.close)
        pipeline.open()
        self.assertIsNone(pipeline._color)
        self.assertEqual(pipeline._parts.names[39], "bottle")
        self.assertEqual(pipeline.information()["colors"], [])
        self.assertTrue(pipeline.information()["visual_only"])
        result = pipeline.infer(np.full((320, 480, 3), 127, np.uint8))
        self.assertTrue(result["visual_only"])
        self.assertEqual(len(result["boxes"]), len(result["confidences"]))
        self.assertTrue(all(reason == [] for reason in result["reasons"]))
        self.assertTrue(all(color == "unknown" for color in result["colors"]))


if __name__ == "__main__":
    unittest.main()
