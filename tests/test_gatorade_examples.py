"""Optional real-photo regression when the supplied examples folder is present."""
from __future__ import annotations

import unittest
from pathlib import Path

import cv2
import numpy as np

from app.gatorade_pipeline import GatoradePipeline
from app.settings import DEFAULTS


ROOT = Path(__file__).resolve().parents[1]
EXAMPLES = ROOT.parent / "examples"
EXPECTED = {
    "WIN_20261022_11_04_03_Pro.jpg": "blue",
    "WIN_20261022_11_04_07_Pro.jpg": "blue",
    "WIN_20261022_11_04_09_Pro.jpg": "blue",
    "WIN_20261022_11_04_11_Pro.jpg": "blue",
    "WIN_20261022_11_04_14_Pro.jpg": "blue",
    "WIN_20261022_11_04_16_Pro.jpg": "blue",
    "WIN_20261022_11_04_20_Pro.jpg": "yellow",
    "WIN_20261022_11_04_25_Pro.jpg": "yellow",
    "WIN_20261022_11_04_27_Pro.jpg": "yellow",
    "WIN_20261022_11_04_29_Pro.jpg": "yellow",
    "WIN_20261022_11_04_35_Pro.jpg": "white",
    "WIN_20261022_11_04_38_Pro.jpg": "white",
    "WIN_20261022_11_04_40_Pro.jpg": "white",
}


def _cast(image: np.ndarray, blue_shift: int, red_shift: int) -> np.ndarray:
    channels = cv2.split(image)
    return cv2.merge((cv2.add(channels[0], blue_shift), channels[1],
                      cv2.add(channels[2], red_shift)))


@unittest.skipUnless(all((EXAMPLES / name).is_file() for name in EXPECTED),
                     "supplied example photos are outside this source checkout")
class ExamplePhotoTests(unittest.TestCase):
    def test_detector_and_color_under_camera_variation(self):
        pipeline = GatoradePipeline({**DEFAULTS, "gatorade_label_check": False}, ROOT).open()
        try:
            for filename, expected in EXPECTED.items():
                image = cv2.imread(str(EXAMPLES / filename))
                self.assertIsNotNone(image, filename)
                variants = {
                    "original": image,
                    "dim": cv2.convertScaleAbs(image, alpha=.65),
                    "bright": cv2.convertScaleAbs(image, alpha=1.3),
                    "warm": _cast(image, -22, 22),
                    "cool": _cast(image, 22, -22),
                    "blur": cv2.GaussianBlur(image, (5, 5), 0),
                    "small": cv2.resize(image, (640, round(image.shape[0] * 640 / image.shape[1]))),
                }
                for variant, frame in variants.items():
                    with self.subTest(photo=filename, variant=variant):
                        result = pipeline.infer(frame)
                        self.assertIn(expected, result["colors"])
                        self.assertTrue(result["boxes"])
        finally:
            pipeline.close()
