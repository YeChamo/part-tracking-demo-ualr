"""YOLOX inference graph compatibility without export or external services."""
import importlib.util
import os
import unittest
from pathlib import Path


TORCH_AVAILABLE = importlib.util.find_spec("torch") is not None


@unittest.skipUnless(TORCH_AVAILABLE, "Native checkpoint preparation requires optional Torch")
class YoloXExportGraphTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import torch
        cls.torch = torch
        cls.original_threads = torch.get_num_threads()
        torch.set_num_threads(1)

    @classmethod
    def tearDownClass(cls):
        cls.torch.set_num_threads(cls.original_threads)

    def test_nano_and_standard_models_emit_raw_three_level_predictions(self):
        from app.vendor.yolox_models import build_model
        for width, depthwise in ((.25, True), (.5, False)):
            with self.subTest(width=width, depthwise=depthwise):
                model = build_model(3, .33, width, depthwise=depthwise)
                self.assertFalse(model.training)
                self.assertFalse(model.head.decode_in_inference)
                self.assertEqual(next(model.parameters()).device.type, "cpu")
                self.assertEqual(next(model.parameters()).dtype, self.torch.float32)
                # Zero the heads, then set regression biases to distinguish
                # raw offsets/log-sizes from decoded pixel-space boxes.
                with self.torch.no_grad():
                    for index in range(3):
                        for prediction in (model.head.reg_preds[index], model.head.obj_preds[index],
                                           model.head.cls_preds[index]):
                            prediction.weight.zero_()
                            prediction.bias.zero_()
                        model.head.reg_preds[index].bias.copy_(self.torch.tensor([1., 2., 3., 4.]))
                with self.torch.inference_mode():
                    output = model(self.torch.zeros(1, 3, 160, 160))
                self.assertEqual(tuple(output.shape), (1, 20 * 20 + 10 * 10 + 5 * 5, 8))
                self.assertTrue(bool(self.torch.isfinite(output).all()))
                self.torch.testing.assert_close(output[..., :4], self.torch.tensor([1., 2., 3., 4.]).expand(1, 525, 4))
                self.torch.testing.assert_close(output[..., 4:], self.torch.full((1, 525, 4), .5))

    def test_custom_width_depth_activation_and_normalization_are_preserved(self):
        from app.vendor.yolox_models import build_model
        model = build_model(2, .5, .125, act="relu", bn_eps=.002, bn_momentum=.07)
        self.assertEqual(model.backbone.backbone.stem.conv.conv.out_channels, 8)
        self.assertEqual(len(model.backbone.C3_p3.m), round(3 * .5))
        for module in model.modules():
            if isinstance(module, self.torch.nn.BatchNorm2d):
                self.assertEqual(module.eps, .002)
                self.assertEqual(module.momentum, .07)
        with self.torch.inference_mode():
            output = model(self.torch.zeros(1, 3, 160, 160))
        self.assertEqual(tuple(output.shape), (1, 525, 7))

    def test_export_experiment_describes_a_custom_graph_without_training_imports(self):
        from app.vendor.yolox_models.experiment import ExportExp
        experiment = ExportExp()
        experiment.num_classes = 2
        experiment.depth = .33
        experiment.width = .125
        experiment.act = "lrelu"
        experiment.test_size = (160, 160)
        model = experiment.get_model()
        self.assertIs(model, experiment.get_model())
        self.assertIsInstance(model.backbone.backbone.stem.conv.act, self.torch.nn.LeakyReLU)
        self.assertEqual(model.head.num_classes, 2)
        self.assertEqual(experiment.test_size, (160, 160))

    def test_invalid_graph_parameters_are_explicit(self):
        from app.vendor.yolox_models import build_model
        for extra in ({"num_classes": 0}, {"num_classes": True}, {"depth": float("nan")},
                      {"width": 0}, {"act": "unknown"}, {"depthwise": 1},
                      {"bn_eps": 0}, {"bn_momentum": 2}):
            with self.subTest(extra=extra):
                values = {"num_classes": 2, "depth": .33, "width": .25}
                values.update(extra)
                with self.assertRaises(ValueError):
                    build_model(**values)

    def test_real_nano_checkpoint_has_exact_state_keys_and_shapes_when_provided(self):
        from app.vendor.yolox_models import build_model
        value = os.environ.get("UALR_REFERENCE_YOLOX_CHECKPOINT")
        if not value:
            self.skipTest("Set UALR_REFERENCE_YOLOX_CHECKPOINT to a local stock nano checkpoint")
        path = Path(value)
        self.assertTrue(path.is_file())
        checkpoint = self.torch.load(path, map_location="cpu", weights_only=True)
        state = checkpoint.get("model", checkpoint)
        model = build_model(80, .33, .25, depthwise=True)
        self.assertEqual(set(state), set(model.state_dict()))
        self.assertEqual({key: tuple(value.shape) for key, value in state.items()},
                         {key: tuple(value.shape) for key, value in model.state_dict().items()})
        model.load_state_dict(state, strict=True)
        with self.torch.inference_mode():
            output = model(self.torch.zeros(1, 3, 160, 160))
        self.assertEqual(tuple(output.shape), (1, 525, 85))
        self.assertTrue(bool(self.torch.isfinite(output).all()))


if __name__ == "__main__":
    unittest.main()
