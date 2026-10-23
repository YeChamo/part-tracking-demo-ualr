"""Real checkpoint -> ONNX -> YOLOX pipeline tests, without camera or motion.

Controlled synthetic weights make predictions independent of the input pixels.
These checks establish conversion/runtime behavior, not bottle-model accuracy.
"""
from __future__ import annotations

import importlib.util
import json
import math
from pathlib import Path
import tempfile
import unittest

import numpy as np


DEPENDENCIES_AVAILABLE = all(importlib.util.find_spec(name) is not None
                             for name in ("torch", "onnx", "onnxruntime", "cv2"))


@unittest.skipUnless(DEPENDENCIES_AVAILABLE, "PTH pipeline integration requires Torch, ONNX and ONNX Runtime")
class PthPipelineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import torch
        cls.torch = torch
        cls.previous_threads = torch.get_num_threads()
        torch.set_num_threads(1)
        cls.folder = tempfile.TemporaryDirectory(prefix="ualr-pth-pipeline-")
        cls.root = Path(cls.folder.name).resolve()
        cls.custom_colors = cls.write_checkpoint("custom_colors", ["plum", "lemon"], predicted=1)
        cls.one_color = cls.write_checkpoint("one_color", ["blue"], predicted=0)
        cls.locator = cls.write_checkpoint("locator", ["bottle"], predicted=0)
        cls.two_colors = cls.write_checkpoint("two_colors", ["blue", "yellow"], predicted=0)

    @classmethod
    def tearDownClass(cls):
        cls.folder.cleanup()
        cls.torch.set_num_threads(cls.previous_threads)

    @classmethod
    def write_checkpoint(cls, name, names, predicted):
        from app.vendor.yolox_models import build_model
        torch = cls.torch
        with torch.random.fork_rng(devices=[]):
            torch.manual_seed(123)
            model = build_model(len(names), .33, .125)
        with torch.no_grad():
            for index in range(3):
                model.head.reg_preds[index].weight.zero_()
                model.head.reg_preds[index].bias.copy_(torch.tensor([.5, .5, math.log(.25), math.log(.25)]))
                model.head.obj_preds[index].weight.zero_()
                model.head.obj_preds[index].bias.fill_(10 if index == 0 else -12)
                model.head.cls_preds[index].weight.zero_()
                model.head.cls_preds[index].bias.fill_(-10)
                model.head.cls_preds[index].bias[predicted] = 10
        path = cls.root / f"{name}.pth"
        torch.save({"model": model.state_dict(), "names": names, "nc": len(names),
                    "test_size": [160, 192], "input_size": [160, 192],
                    "yolox_inference_config": {
                        "schema_version": 1, "architecture": "yolox_pafpn",
                        "depth": .33, "width": .125, "depthwise": False, "act": "silu",
                        "normalization": {"type": "batchnorm2d", "eps": .001, "momentum": .03},
                    }}, path)
        return path

    def settings(self, **values):
        from app.settings import DEFAULTS
        return {**DEFAULTS, "visual_only": False, "rule": "color", "yolox_mode": "combined",
                "auto_model_config": True, "inference_backend": "cpu",
                "confidence": .5, "color_confidence": .5, **values}

    def open_pipeline(self, settings):
        from app.yolox_pipeline import YoloXPipeline
        pipeline = YoloXPipeline(settings, self.root)
        self.addCleanup(pipeline.close)
        pipeline.open()
        return pipeline

    @staticmethod
    def orange_frame():
        return np.full((160, 192, 3), (0, 128, 255), np.uint8)

    def assert_model_geometry(self, model, shape=(160, 192), strides=(8, 16, 32)):
        cfg = model.detector._cfg
        self.assertEqual(cfg.input_hw, shape)
        self.assertEqual(cfg.yolox_strides, strides)
        self.assertEqual(cfg.yolox_decode, "raw")
        self.assertEqual(cfg.letterbox, "top_left")
        converted = Path(cfg.model_path)
        self.assertEqual(converted.suffix, ".onnx")
        self.assertTrue(converted.is_file())
        self.assertTrue(converted.is_relative_to(self.root / "data" / "model_cache"))
        metadata = model.detector._backend.model_details()["metadata"]
        self.assertEqual(json.loads(metadata["yolox_strides"]), list(strides))
        self.assertEqual(json.loads(metadata["input_size"]), list(shape))

    def test_recorded_nonbase_rectangular_model_routes_its_literal_class_predictions(self):
        pipeline = self.open_pipeline(self.settings(model_path=str(self.custom_colors), pass_color="plum"))
        self.assertEqual(pipeline.information()["colors"], ["plum", "lemon"])
        self.assertEqual(pipeline._parts.names, ["plum", "lemon"])
        self.assert_model_geometry(pipeline._parts)
        result = pipeline.infer(self.orange_frame())
        self.assertTrue(result["boxes"])
        self.assertEqual(set(result["colors"]), {"lemon"})
        self.assertTrue(all(reason == ["YOLOX color lemon (divert)"] for reason in result["reasons"]))
        self.assertTrue(all(value > .99 for value in result["color_confidences"]))
        # The chosen stride-8 heads produce two-pixel boxes on the half-grid.
        # This checks actual native coordinate decoding, not just label text.
        boxes = np.asarray(result["boxes"])
        np.testing.assert_allclose(boxes[:, 2:] - boxes[:, :2], 2, atol=.0001)
        np.testing.assert_allclose(((boxes[:, 2:] + boxes[:, :2]) / 2) % 8, 4, atol=.0001)

    def test_one_class_color_checkpoint_can_pass_using_its_model_prediction(self):
        pipeline = self.open_pipeline(self.settings(model_path=str(self.one_color), pass_color="blue"))
        self.assertEqual(pipeline.information()["colors"], ["blue"])
        self.assert_model_geometry(pipeline._parts)
        result = pipeline.infer(self.orange_frame())
        self.assertTrue(result["boxes"])
        self.assertEqual(set(result["colors"]), {"blue"})
        self.assertTrue(all(reason == [] for reason in result["reasons"]))

    def test_two_models_auto_select_the_only_locator_class_and_read_color_model(self):
        pipeline = self.open_pipeline(self.settings(yolox_mode="two_models", color_backend="yolox",
                        model_path=str(self.locator), color_model_path=str(self.two_colors),
                        model_class_id=39, pass_color="blue"))
        self.assertEqual(pipeline.settings["model_class_id"], 0)
        self.assertEqual(pipeline._parts.names, ["bottle"])
        self.assertEqual(pipeline._color.names, ["blue", "yellow"])
        self.assert_model_geometry(pipeline._parts)
        self.assert_model_geometry(pipeline._color)
        result = pipeline.infer(self.orange_frame())
        self.assertTrue(result["boxes"])
        self.assertEqual(set(result["colors"]), {"blue"})
        self.assertTrue(all(reason == [] for reason in result["reasons"]))

    def test_manual_square_override_and_automatic_rectangular_size_are_distinct(self):
        automatic = self.open_pipeline(self.settings(model_path=str(self.custom_colors), pass_color="lemon"))
        manual = self.open_pipeline(self.settings(model_path=str(self.custom_colors), pass_color="blue",
                        auto_model_config=False, image_size=160, color_class_map="0:orange,1:blue"))
        self.assert_model_geometry(automatic._parts, (160, 192))
        self.assert_model_geometry(manual._parts, (160, 160))
        self.assertNotEqual(automatic._parts.detector._cfg.model_path, manual._parts.detector._cfg.model_path)
        result = manual.infer(self.orange_frame())
        self.assertTrue(result["boxes"])
        self.assertEqual(set(result["colors"]), {"blue"})
        self.assertTrue(all(reason == [] for reason in result["reasons"]))

    def test_selected_experiment_strides_survive_export_and_native_pipeline_decode(self):
        # A P3-only graph genuinely supports a width divisible by 8 rather
        # than 32. Its checkpoint/experiment own the rectangular input size.
        custom_checkpoint = self.root / "custom_stride.pth"
        checkpoint = self.torch.load(self.custom_colors, map_location="cpu", weights_only=True)
        checkpoint.update(test_size=[160, 200], input_size=[160, 200])
        self.torch.save(checkpoint, custom_checkpoint)
        experiment = self.root / "first_level_experiment.py"
        experiment.write_text('''import torch
from app.vendor.yolox_models import build_model as _build

class FirstLevel(torch.nn.Module):
    def __init__(self):
        super().__init__()
        base = _build(2, .33, .125)
        self.backbone = base.backbone
        self.head = base.head
        self.yolox_strides = [8]

    def forward(self, images):
        features = self.backbone.backbone(images)
        return self.head([features["dark3"]])

def build_model():
    return FirstLevel(), {"names": ["plum", "lemon"], "test_size": [160, 200], "yolox_strides": [8]}
''', encoding="utf-8")
        pipeline = self.open_pipeline(self.settings(model_path=str(custom_checkpoint), pass_color="lemon", image_size=200,
                        model_experiment_path=str(experiment)))
        self.assert_model_geometry(pipeline._parts, shape=(160, 200), strides=(8,))
        output_shape = pipeline._parts.detector._backend.model_details()["output_shape"]
        self.assertEqual(output_shape[1], 20 * 25)
        result = pipeline.infer(np.full((160, 200, 3), (0, 128, 255), np.uint8))
        self.assertTrue(result["boxes"])
        self.assertEqual(set(result["colors"]), {"lemon"})
        self.assertTrue(all(reason == [] for reason in result["reasons"]))


if __name__ == "__main__":
    unittest.main()
