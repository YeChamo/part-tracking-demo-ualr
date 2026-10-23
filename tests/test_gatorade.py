"""Offline Gatorade reference checks, with no live camera or motion output."""
from __future__ import annotations

import ast
import tempfile
import unittest
from pathlib import Path

import cv2
import numpy as np

from app import gatorade
from app.gatorade import GatoradeLabelMatcher


ROOT = Path(__file__).resolve().parents[1]
REFERENCE_NAMES = ("logo", "blue", "yellow", "white")


def reference_canvas(name):
    reference = cv2.imread(str(ROOT / "models" / f"gatorade_{name}_reference.png"))
    if reference is None:
        raise AssertionError(f"Missing reference image: {name}")
    scale = min(1.0, 400 / max(reference.shape[:2]))
    image = cv2.resize(reference, None, fx=scale, fy=scale)
    height, width = image.shape[:2]
    canvas = np.full((height * 2, width * 2, 3), 255, np.uint8)
    canvas[height // 2:height // 2 + height, width // 2:width // 2 + width] = image
    return canvas


class GatoradeReferenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.matcher = GatoradeLabelMatcher(ROOT / "models")

    def test_reference_files_are_valid_png_images(self):
        for name in REFERENCE_NAMES:
            with self.subTest(reference=name):
                path = ROOT / "models" / f"gatorade_{name}_reference.png"
                self.assertEqual(path.read_bytes()[:8], b"\x89PNG\r\n\x1a\n")
                image = cv2.imread(str(path), cv2.IMREAD_COLOR)
                self.assertIsNotNone(image)
                self.assertEqual(image.dtype, np.uint8)
                self.assertEqual(image.shape[2], 3)
                self.assertGreaterEqual(min(image.shape[:2]), 200)

    def test_reference_matcher_loads_all_four_reference_images(self):
        self.assertEqual(len(self.matcher.references), len(REFERENCE_NAMES))

    def test_reference_artwork_matches_when_embedded_in_a_larger_crop(self):
        # A translated/scaled copy provides a known correspondence for the
        # optional geometric matcher. This is not a claim of brand accuracy
        # against real bottles, nor a trained color-class prediction.
        for name in REFERENCE_NAMES:
            with self.subTest(reference=name):
                self.assertTrue(self.matcher.match(reference_canvas(name)))

    def test_reference_matcher_rejects_plain_g(self):
        frame = np.full((400, 250, 3), 255, np.uint8)
        cv2.putText(frame, "G", (20, 250), cv2.FONT_HERSHEY_SIMPLEX, 5, (0, 0, 0), 8)
        self.assertFalse(self.matcher.match(frame))

    def test_reference_matcher_rejects_blank_and_invalid_crops(self):
        for crop in (None, [], np.empty((0, 0, 3), np.uint8),
                     np.zeros((20, 20, 3), np.uint8),
                     np.zeros((100, 100), np.uint8),
                     np.zeros((100, 100, 4), np.uint8),
                     np.zeros((100, 100, 3), np.float32),
                     np.full((400, 250, 3), 255, np.uint8)):
            with self.subTest(shape=getattr(crop, "shape", None)):
                self.assertFalse(self.matcher.match(crop))

    def test_missing_references_are_explicit(self):
        with tempfile.TemporaryDirectory() as folder:
            with self.assertRaises(FileNotFoundError):
                GatoradeLabelMatcher(Path(folder))

    def test_optional_reference_module_cannot_supply_pixel_color_predictions(self):
        for obsolete_api in ("measure_drink_color", "_sample", "_classify_patch", "COLOR_NAMES"):
            self.assertFalse(hasattr(gatorade, obsolete_api), obsolete_api)

    def test_live_vision_does_not_import_the_offline_matcher(self):
        for filename in ("app/vision.py", "app/yolox_pipeline.py", "app/ui.py"):
            tree = ast.parse((ROOT / filename).read_text(encoding="utf-8"))
            imports = []
            for node in ast.walk(tree):
                if isinstance(node, ast.ImportFrom):
                    imports.append(node.module or "")
                    imports.extend(alias.name for alias in node.names)
                elif isinstance(node, ast.Import):
                    imports.extend(alias.name for alias in node.names)
            with self.subTest(module=filename):
                self.assertFalse(any(name == "gatorade" or name.endswith(".gatorade")
                                     or name == "GatoradeLabelMatcher" for name in imports))


if __name__ == "__main__":
    unittest.main()
