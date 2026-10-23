"""Rectangular preprocessing and explicit YOLOX decoding without devices."""
import unittest

import numpy as np

from app.model_runtime import ModelDetector, ModelPostProcessor
from app.vendor.inference import DetectorConfig, InferenceError


class ModelGeometryTests(unittest.TestCase):
    def detector(self, metadata=None, shape=(1, 3, 32, 64)):
        cfg = DetectorConfig(img_size=640)
        detector = ModelDetector(cfg)
        detector.configure_model(metadata or {}, list(shape))
        return detector, cfg

    def test_rectangular_top_left_geometry_uses_raw_bgr_pixels(self):
        detector, cfg = self.detector({"letterbox": "top_left", "yolox_decode": "raw",
                                       "yolox_strides": "[8, 16, 32]", "input_size": "[32,64]"})
        frame = np.full((20, 20, 3), (10, 20, 30), np.uint8)
        tensor, scale, pad = detector._preprocess(frame)
        self.assertEqual(cfg.input_hw, (32, 64))
        self.assertEqual(cfg.img_size, 64)
        self.assertEqual(cfg.yolox_strides, (8, 16, 32))
        self.assertEqual(tensor.shape, (1, 3, 32, 64))
        self.assertEqual(tensor.dtype, np.float32)
        self.assertTrue(tensor.flags.c_contiguous)
        self.assertEqual(scale, 1.6)
        self.assertEqual(pad, (0, 0))
        np.testing.assert_array_equal(tensor[0, :, 0, 0], [10, 20, 30])
        np.testing.assert_array_equal(tensor[0, :, 0, 32], [114, 114, 114])

    def test_metadata_absent_preserves_legacy_centered_letterbox(self):
        detector, cfg = self.detector(shape=(1, 3, 32, 32))
        tensor, scale, pad = detector._preprocess(np.full((10, 20, 3), 50, np.uint8))
        self.assertEqual(cfg.yolox_decode, "auto")
        self.assertEqual(cfg.letterbox, "center")
        self.assertEqual(scale, 1.6)
        self.assertEqual(pad, (0, 8))
        self.assertEqual(tensor[0, 0, 0, 0], 114)
        self.assertEqual(tensor[0, 0, 8, 0], 50)

    def test_symbolic_geometry_uses_recorded_rectangular_size(self):
        detector, cfg = self.detector({"test_size": "[48,96]", "yolox_letterbox": "top_left"},
                                      (1, 3, "height", "width"))
        self.assertEqual(cfg.input_hw, (48, 96))
        self.assertEqual(detector._preprocess(np.zeros((24, 48, 3), np.uint8))[0].shape, (1, 3, 48, 96))

    def test_invalid_or_conflicting_metadata_never_changes_geometry_silently(self):
        for metadata, shape in (({"input_size": "[64,32]"}, (1, 3, 32, 64)),
                                ({"yolox_strides": "[8,0,32]"}, (1, 3, 32, 64)),
                                ({"yolox_strides": "[]"}, (1, 3, 32, 64)),
                                ({"yolox_decode": "logits"}, (1, 3, 32, 64)),
                                ({"letterbox": "stretch"}, (1, 3, 32, 64)),
                                ({}, (1, 1, 32, 64)), ({}, (2, 3, 32, 64))):
            with self.subTest(metadata=metadata, shape=shape), self.assertRaises(InferenceError):
                self.detector(metadata, shape)

    def test_detector_infer_connects_rectangular_preprocessing_and_declared_decode(self):
        class FakeBackend:
            tensor = None
            def is_open(self): return True
            def infer_raw(self, tensor):
                self.tensor = tensor
                output = np.zeros((1, 8, 6), np.float32)
                output[0, 7] = (.5, .5, 0, 0, 1, .9)
                return [output]
        backend = FakeBackend()
        detector = ModelDetector(DetectorConfig(class_names=["blue"]), backend=backend)
        detector.configure_model({"yolox_decode": "raw", "letterbox": "top_left", "yolox_strides": "[16]"},
                                 [1, 3, 32, 64])
        result = detector.infer(np.zeros((32, 64, 3), np.uint8))
        self.assertEqual(backend.tensor.shape, (1, 3, 32, 64))
        self.assertEqual(len(result.detections), 1)
        np.testing.assert_allclose(result.detections[0].xyxy, (48, 16, 63, 31))
        self.assertEqual(result.detections[0].label, "blue")


class ModelOutputTests(unittest.TestCase):
    def process(self, output, *, mode="raw", shape=(64, 64), strides=(8, 16, 32)):
        cfg = DetectorConfig(img_size=max(shape), conf=.25, class_names=["blue"])
        cfg.input_hw, cfg.yolox_decode, cfg.yolox_strides = shape, mode, strides
        return ModelPostProcessor().process([output], cfg, src_hw=shape,
                                             letterbox_scale=1.0, letterbox_pad=(0, 0))

    def test_explicit_raw_decode_overrides_the_legacy_coordinate_heuristic(self):
        output = np.zeros((1, 84, 6), np.float32)
        output[0, 0] = (4, 3, np.log(2), np.log(2), 1, .9)
        detections = self.process(output)
        self.assertEqual(len(detections), 1)
        np.testing.assert_allclose(detections[0].xyxy, (24, 16, 40, 32), atol=.0001)
        self.assertEqual(detections[0].label, "blue")

    def test_explicit_decoded_small_boxes_are_never_decoded_twice(self):
        detections = self.process(np.array([[[1, 1, 2, 2, 1, .9]]], np.float32), mode="decoded")
        self.assertEqual(len(detections), 1)
        np.testing.assert_allclose(detections[0].xyxy, (0, 0, 2, 2))

    def test_rectangular_custom_stride_grid_matches_source_coordinates(self):
        # 32x64 / stride16 gives 2 rows of 4 cells. Last cell is (3,1).
        output = np.zeros((1, 8, 6), np.float32)
        output[0, 7] = (.5, .5, 0, 0, 1, .8)
        detections = self.process(output, shape=(32, 64), strides=(16,))
        np.testing.assert_allclose(detections[0].xyxy, (48, 16, 63, 31))

    def test_raw_anchor_count_mismatch_is_an_error_instead_of_partial_decode(self):
        for count in (1, 83, 85):
            with self.subTest(anchors=count), self.assertRaisesRegex(InferenceError, "anchors"):
                self.process(np.zeros((1, count, 6), np.float32))

    def test_non_finite_outputs_and_decode_overflow_are_faults(self):
        for value in (float("nan"), float("inf"), -float("inf")):
            output = np.zeros((1, 84, 6), np.float32)
            output[0, 0, 0] = value
            with self.subTest(value=value), self.assertRaisesRegex(InferenceError, "finite"):
                self.process(output)
        output = np.zeros((1, 84, 6), np.float32)
        output[0, 0, 2] = 1000
        with self.assertRaisesRegex(InferenceError, "finite"):
            self.process(output)

    def test_legacy_auto_format_still_recognizes_decoded_outputs(self):
        output = np.array([[[32, 32, 16, 16, 1, .9]]], np.float32)
        detections = self.process(output, mode="auto")
        np.testing.assert_allclose(detections[0].xyxy, (24, 24, 40, 40))


if __name__ == "__main__":
    unittest.main()
