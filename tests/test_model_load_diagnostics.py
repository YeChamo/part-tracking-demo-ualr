"""Wrong model selections fail with the actual shape, slot, and corrective action."""
import importlib.util
from pathlib import Path
import unittest

import numpy as np

from app.accelerated_backend import AcceleratedONNXBackend
from app.vendor.inference import InferenceError
from app.yolox_pipeline import YoloXPipeline, _class_count


ROOT = Path(__file__).resolve().parents[1]
CLASSIFIER = ROOT / 'models/color/distilV4_student.onnx'


class ModelLoadDiagnosticsTests(unittest.TestCase):
    def test_runtime_output_error_includes_actual_shape_and_model_type_action(self):
        with self.assertRaises(InferenceError) as caught:
            AcceleratedONNXBackend._validate_outputs([np.zeros((1, 13), np.float32)])
        message = str(caught.exception)
        self.assertIn('[1, 13]', message)
        self.assertIn('Bundled color neural network', message)
        self.assertIn('Bottle model', message)

    def test_metadata_output_error_keeps_detection_contract_and_shows_shape(self):
        with self.assertRaises(ValueError) as caught:
            _class_count({'input_shape': [1, 3, 224, 224], 'output_shape': [1, 13]}, 224)
        message = str(caught.exception)
        self.assertIn('[1, N, 5+C]', message)
        self.assertIn('[1, 13]', message)
        self.assertIn('Color model type', message)

    @unittest.skipUnless(CLASSIFIER.is_file() and importlib.util.find_spec('onnxruntime'), 'Bundled model and ONNX Runtime required')
    def test_actual_classifier_in_bottle_slot_names_file_and_does_not_change_selection(self):
        settings = dict(visual_only=True, yolox_mode='tracking', model_path=str(CLASSIFIER),
                        color_model_path='', color_backend='classifier', auto_model_config=True,
                        inference_backend='cpu', confidence=.2)
        pipe = YoloXPipeline(settings, ROOT)
        try:
            with self.assertRaises(InferenceError) as caught:
                pipe.open()
            message = str(caught.exception)
            self.assertIn('Bottle YOLOX model', message)
            self.assertIn(str(CLASSIFIER), message)
            self.assertIn('[1, 13]', message)
            self.assertIn('Bundled color neural network', message)
            self.assertEqual(settings['model_path'], str(CLASSIFIER))
            self.assertEqual(pipe.settings['model_path'], str(CLASSIFIER))
            self.assertIsNone(pipe._parts)
        finally:
            pipe.close()

    @unittest.skipUnless(CLASSIFIER.is_file() and importlib.util.find_spec('onnxruntime'), 'Bundled model and ONNX Runtime required')
    def test_actual_classifier_in_yolox_color_slot_names_slot_and_closes_models(self):
        settings = dict(visual_only=False, yolox_mode='two_models', rule='color', pass_color='blue',
                        model_path='models/yolox_nano.onnx', color_model_path=str(CLASSIFIER),
                        color_backend='yolox', auto_model_config=True, inference_backend='cpu')
        pipe = YoloXPipeline(settings, ROOT)
        try:
            with self.assertRaises(InferenceError) as caught:
                pipe.open()
            message = str(caught.exception)
            self.assertIn('YOLOX color model', message)
            self.assertIn(str(CLASSIFIER), message)
            self.assertIn('[1, 13]', message)
            self.assertIn('Bundled color neural network', message)
            self.assertEqual(pipe.settings['color_backend'], 'yolox')
            self.assertIsNone(pipe._parts)
            self.assertIsNone(pipe._color)
        finally:
            pipe.close()


if __name__ == '__main__':
    unittest.main()
