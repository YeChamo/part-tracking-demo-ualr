"""Gatorade color routing checks without a camera or motion connection."""
from __future__ import annotations

import unittest
from pathlib import Path
from types import SimpleNamespace

import cv2
import numpy as np

from app.gatorade import GatoradeLabelMatcher, measure_drink_color, neutralize_color_cast
from app.gatorade_pipeline import GatoradePipeline
from app.settings import DEFAULTS


ROOT = Path(__file__).resolve().parents[1]


def bottle_image(color: tuple[int, int, int], *, cropped_top: bool = False) -> tuple[np.ndarray, tuple[int, int, int, int]]:
    frame = np.full((320, 200, 3), 185, np.uint8)
    frame[20:300, 40:160] = color
    frame[20:50, 40:160] = (25, 135, 240)  # orange cap
    frame[145:265, 40:160] = (105, 105, 105)  # opaque label
    if cropped_top:
        frame = frame[90:]
        return frame, (40, 0, 160, 210)
    return frame, (40, 20, 160, 300)


class GatoradeColorTests(unittest.TestCase):
    def test_shoulder_color_ignores_cap_and_label(self):
        for name, bgr in (("blue", (235, 155, 65)),
                          ("yellow", (55, 215, 235)),
                          ("white", (180, 180, 180))):
            with self.subTest(name=name):
                frame, box = bottle_image(bgr)
                reading = measure_drink_color(frame, box)
                self.assertEqual(reading["name"], name)
                self.assertGreaterEqual(reading["confidence"], .65)

    def test_cropped_blue_and_two_way_routing(self):
        frame, box = bottle_image((235, 155, 65), cropped_top=True)
        self.assertEqual(measure_drink_color(frame, box)["name"], "blue")
        detection = SimpleNamespace(xyxy=box, class_id=39, label="bottle", score=.9)
        result = SimpleNamespace(detections=[detection], inference_ms=1.0)
        pipeline = GatoradePipeline({**DEFAULTS, "pass_color": "blue"}, ROOT)
        pipeline.detector = SimpleNamespace(infer=lambda _frame: result)
        self.assertEqual(pipeline.infer(frame)["reasons"], [[]])
        pipeline.settings["pass_color"] = "yellow"
        self.assertEqual(pipeline.infer(frame)["reasons"], [["Gatorade color blue (divert)"]])

    def test_white_is_distinct_from_legacy_clear(self):
        frame, box = bottle_image((180, 180, 180))
        self.assertEqual(measure_drink_color(frame, box)["name"], "white")
        self.assertNotEqual(measure_drink_color(frame, box)["name"], "clear")

    def test_camera_white_balance_does_not_change_drink_color(self):
        for name, bgr, shift in (("blue", (160, 144, 68), (-22, 0, 22)),
                                 ("yellow", (86, 163, 159), (22, 0, -22)),
                                 ("white", (162, 161, 157), (22, 0, -22))):
            with self.subTest(name=name):
                frame, box = bottle_image(bgr)
                cast = np.uint8(np.clip(frame.astype(np.int16) + shift, 0, 255))
                corrected = neutralize_color_cast(cast)
                self.assertEqual(measure_drink_color(corrected, box)["name"], name)

    def test_clipped_blue_bottle_uses_lower_liquid_over_pale_highlight(self):
        frame = np.full((320, 200, 3), 180, np.uint8)
        frame[0:300, 40:160] = (160, 144, 68)
        frame[66:105, 40:160] = (225, 225, 225)
        self.assertEqual(measure_drink_color(frame, (40, 0, 160, 300))["name"], "blue")

    def test_colored_scene_without_neutral_reference_is_not_forced_gray(self):
        frame = np.full((320, 200, 3), (30, 110, 190), np.uint8)
        self.assertTrue(np.array_equal(neutralize_color_cast(frame), frame))

    def test_reference_matcher_rejects_plain_g(self):
        matcher = GatoradeLabelMatcher(ROOT / "models")
        self.assertEqual(len(matcher.references), 4)
        frame = np.full((400, 250, 3), 255, np.uint8)
        cv2.putText(frame, "G", (20, 250), cv2.FONT_HERSHEY_SIMPLEX, 5, (0, 0, 0), 8)
        self.assertFalse(matcher.match(frame))


if __name__ == "__main__":
    unittest.main()
