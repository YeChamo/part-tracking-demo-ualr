"""Gatorade color routing checks without a camera or motion connection."""
from __future__ import annotations

import unittest
from pathlib import Path

import cv2
import numpy as np

from app.gatorade import GatoradeLabelMatcher, measure_drink_color
from app.settings import DEFAULTS
from app.vision import classify, classify_color


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
        settings = {**DEFAULTS, "pass_color": "blue"}
        observed = classify_color(frame, box, settings)
        self.assertEqual(observed[0], "blue")
        self.assertEqual(classify(frame, box, settings, None, observed), [])
        settings["pass_color"] = "yellow"
        self.assertEqual(classify(frame, box, settings, None, observed),
                         ["Color: blue (divert)"])

    def test_white_is_distinct_from_legacy_clear(self):
        frame, box = bottle_image((180, 180, 180))
        self.assertEqual(classify_color(frame, box, DEFAULTS)[0], "white")
        self.assertEqual(classify(frame, box, {**DEFAULTS, "pass_color": "white"}, None), [])

    def test_reference_matcher_rejects_plain_g(self):
        matcher = GatoradeLabelMatcher(ROOT / "models")
        self.assertEqual(len(matcher.references), 4)
        frame = np.full((400, 250, 3), 255, np.uint8)
        cv2.putText(frame, "G", (20, 250), cv2.FONT_HERSHEY_SIMPLEX, 5, (0, 0, 0), 8)
        self.assertFalse(matcher.match(frame))


if __name__ == "__main__":
    unittest.main()
