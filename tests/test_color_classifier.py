import unittest
from pathlib import Path

import numpy as np

from app.color_classifier import COLOR_NAMES, ColorClassifier, prepare_input


ROOT = Path(__file__).resolve().parents[1]


class ColorClassifierTests(unittest.TestCase):
    def test_preprocessing_bgr_conversion_and_normalization(self):
        crop = np.full((30, 50, 3), (255, 0, 0), dtype=np.uint8)
        batch = prepare_input(crop)
        self.assertEqual(batch.shape, (1, 3, 224, 224))
        np.testing.assert_allclose(batch[0, :, 100, 100], [-.485/.229, -.456/.224, (1-.406)/.225], rtol=1e-6)
        self.assertTrue(batch.flags.c_contiguous)

    def test_invalid_crops_rejected(self):
        for crop in (None, np.zeros((0, 2, 3), np.uint8), np.zeros((8, 8), np.uint8), np.zeros((8, 8, 3), np.float32)):
            with self.subTest(crop_type=type(crop)):
                with self.assertRaises(ValueError):
                    prepare_input(crop)

    def test_logits_validation_and_stable_softmax(self):
        logits = np.full((1, 13), -10000, np.float32)
        logits[0, 4] = 10000
        probabilities = ColorClassifier._probabilities(logits)
        self.assertEqual(COLOR_NAMES[int(probabilities.argmax())], "blue")
        self.assertAlmostEqual(float(probabilities.sum()), 1)
        for bad in (np.zeros((13,)), np.full((1, 13), np.nan), np.zeros((1, 12))):
            with self.assertRaises(ValueError):
                ColorClassifier._probabilities(bad)

    def test_real_bundled_trained_model_executes(self):
        model = ROOT / "models/color/distilV4_student.onnx"
        if not model.is_file():
            self.skipTest("Bundled optional color network unavailable")
        classifier = ColorClassifier(model).open()
        try:
            # Runtime checks only. These swatches are not a bottle accuracy benchmark.
            for bgr in ((255, 0, 0), (0, 255, 255), (255, 255, 255)):
                actual, confidence = classifier.infer(np.full((70, 90, 3), bgr, np.uint8))
                self.assertIn(actual, COLOR_NAMES)
                self.assertGreater(confidence, 0)
                self.assertLessEqual(confidence, 1)
        finally:
            classifier.close()
        with self.assertRaises(RuntimeError):
            classifier.infer(np.zeros((8, 8, 3), np.uint8))

    def test_optional_real_product_crop_calibration(self):
        """Calibrated examples, deliberately not claimed as held-out accuracy."""
        import cv2
        folder = ROOT / ".build/color-model-research"
        examples = [(folder / f"real-{color}-gatorade.png", color)
                    for color in ("blue", "yellow", "white")]
        if not all(path.is_file() for path, _ in examples):
            self.skipTest("Optional official product calibration images unavailable")
        classifier = ColorClassifier(ROOT / "models/color/distilV4_student.onnx").open()
        try:
            for path, expected in examples:
                image = cv2.imread(str(path), cv2.IMREAD_UNCHANGED)
                # Author-supplied PNG alpha supplies the product box for this
                # classifier-only check; it does not assert detector recall.
                ys, xs = np.nonzero(image[:, :, 3] > 127)
                bottle = image[ys.min():ys.max()+1, xs.min():xs.max()+1, :3]
                height, width = bottle.shape[:2]
                x1, y1, x2, y2 = classifier.bottle_crop
                crop = bottle[int(height*y1):int(height*y2), int(width*x1):int(width*x2)]
                actual, confidence = classifier.infer(crop)
                self.assertEqual(actual, expected)
                self.assertGreaterEqual(confidence, .5)
        finally:
            classifier.close()


if __name__ == "__main__":
    unittest.main()
