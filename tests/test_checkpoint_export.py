"""Restricted checkpoint loading and real CPU ONNX conversion; no hardware."""
import importlib.util
import json
from pathlib import Path
import tempfile
import threading
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import numpy as np

from app.checkpoint_export import (ExportCancelled, _native_config,
                                   _numeric_numpy_scalar, _safe_load,
                                   _state_dict, _strides, prepare_model)


_DEPS = all(importlib.util.find_spec(name) is not None for name in ("torch", "onnx", "onnxruntime"))
if _DEPS:
    import torch


def _write_marker(path):
    Path(path).write_text("unsafe", encoding="utf-8")


class _UnsafePayload:
    def __init__(self, path):
        self.path = path

    def __reduce__(self):
        return _write_marker, (self.path,)


CUSTOM_SOURCE = '''
import torch
from torch import nn
class Detector(nn.Module):
    yolox_strides = [8]
    def __init__(self):
        super().__init__()
        self.proj = nn.Conv2d(3, 7, 1, stride=8)
    def forward(self, x):
        y = self.proj(x).flatten(2).transpose(1, 2)
        return torch.cat((y[..., :4], y[..., 4:].sigmoid()), 2)
def build_model():
    return Detector(), ['custom_orange', 'custom_blue']
'''


@unittest.skipUnless(_DEPS, "Torch/ONNX/ORT conversion dependencies are optional in source tests")
class CheckpointExportTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name).resolve()
        self.experiment = self.root / "experiment.py"
        self.experiment.write_text(CUSTOM_SOURCE, encoding="utf-8")
        self.checkpoint = self.root / "custom.pth"
        # Parameter names/shapes match the explicitly selected experiment.
        self.state = {"proj.weight": torch.linspace(-.01, .01, 21).reshape(7, 3, 1, 1),
                      "proj.bias": torch.linspace(-.2, .2, 7)}
        self.payload = {"model": self.state, "names": ["orange", "blue"], "nc": 2,
                        "input_size": [32, 64], "test_size": [32, 64]}
        self.save()

    def save(self):
        torch.save(self.payload, self.checkpoint)

    def prepare(self, **kwargs):
        return prepare_model(self.checkpoint, self.root, kwargs.pop("image_size", None),
                             experiment_path=kwargs.pop("experiment_path", self.experiment), **kwargs)

    def metadata(self, output):
        import onnx
        graph = onnx.load(str(output), load_external_data=False)
        return {item.key: item.value for item in graph.metadata_props}

    def test_real_custom_conversion_honors_rectangular_size_and_metadata(self):
        messages = []
        output = self.prepare(progress=messages.append)
        self.assertTrue(output.is_file())
        self.assertTrue(output.is_relative_to(self.root / "data" / "model_cache"))
        metadata = self.metadata(output)
        self.assertEqual(json.loads(metadata["names"]), ["orange", "blue"])
        self.assertEqual(json.loads(metadata["input_size"]), [32, 64])
        self.assertEqual(json.loads(metadata["yolox_strides"]), [8])
        self.assertEqual(metadata["yolox_decode"], "raw")
        self.assertEqual(metadata["letterbox"], "top_left")
        self.assertEqual(metadata["nc"], "2")
        self.assertTrue(any("Comparing" in item for item in messages))
        manifest = json.loads(output.with_name("manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest["validated"], "torch_ort_cpu_nonblank_v1")

    def test_manual_square_size_and_explicit_class_order_override(self):
        output = self.prepare(image_size=32, class_names="blue,orange")
        metadata = self.metadata(output)
        self.assertEqual(json.loads(metadata["names"]), ["blue", "orange"])
        self.assertEqual(json.loads(metadata["input_size"]), [32, 32])

    def test_explicit_experiment_class_names_fallback_when_checkpoint_unnamed(self):
        del self.payload["names"]
        self.save()
        self.assertEqual(json.loads(self.metadata(self.prepare())["names"]), ["custom_orange", "custom_blue"])

    def test_empty_checkpoint_names_fall_back_to_selected_experiment(self):
        self.payload["names"] = []
        self.save()
        self.assertEqual(json.loads(self.metadata(self.prepare())["names"]), ["custom_orange", "custom_blue"])

    def test_custom_single_head_does_not_require_three_stock_class_heads(self):
        source = CUSTOM_SOURCE.replace("self.proj = nn.Conv2d(3, 7, 1, stride=8)",
            "self.head = nn.Module()\n        self.head.cls_preds = nn.ModuleList([nn.Conv2d(3, 7, 1, stride=8)])")
        self.experiment.write_text(source.replace("self.proj(x)", "self.head.cls_preds[0](x)"), encoding="utf-8")
        self.payload["model"] = {key.replace("proj.", "head.cls_preds.0."): value for key, value in self.state.items()}
        self.save()
        output = self.prepare()
        self.assertEqual(self.metadata(output)["nc"], "2")
        self.assertEqual(json.loads(self.metadata(output)["yolox_strides"]), [8])

    def test_verified_cache_reuses_without_exporting_again(self):
        first = self.prepare()
        with patch("torch.onnx.export", side_effect=AssertionError("cache should skip export")):
            second = self.prepare()
        self.assertEqual(first, second)

    def test_corrupt_graph_is_rebuilt_before_returning_cache(self):
        output = self.prepare()
        output.write_bytes(b"corrupted model")
        with patch("torch.onnx.export", wraps=torch.onnx.export) as export:
            rebuilt = self.prepare()
        self.assertEqual(output, rebuilt)
        self.assertEqual(export.call_count, 1)
        self.assertEqual(self.metadata(rebuilt)["nc"], "2")
        self.assertFalse(list(output.parent.parent.glob(".old-*")))

    def test_corrupt_manifest_is_rebuilt(self):
        output = self.prepare()
        output.with_name("manifest.json").write_text("not JSON", encoding="utf-8")
        with patch("torch.onnx.export", wraps=torch.onnx.export) as export:
            self.prepare()
        self.assertEqual(export.call_count, 1)

    def test_name_override_changes_cache_identity(self):
        first = self.prepare()
        second = self.prepare(class_names="blue,orange")
        self.assertNotEqual(first.parent, second.parent)

    def test_custom_dependency_change_invalidates_cache_and_reloads_fresh_source(self):
        helper = self.root / "layers.py"
        helper.write_text(CUSTOM_SOURCE.replace("def build_model():", "SCALE = 1\ndef build_model():").replace(
            "self.proj(x).flatten", "(self.proj(x) * SCALE).flatten"), encoding="utf-8")
        self.experiment.write_text("from layers import build_model\n", encoding="utf-8")
        first = self.prepare()
        # Same file length and near-identical timestamp tests stale .pyc imports.
        helper.write_text(helper.read_text(encoding="utf-8").replace("SCALE = 1", "SCALE = 2"), encoding="utf-8")
        second = self.prepare()
        self.assertNotEqual(first.parent, second.parent)
        import onnxruntime as ort
        from app.checkpoint_export import _input
        data = _input((32, 64))
        options = ort.SessionOptions()
        options.intra_op_num_threads, options.inter_op_num_threads = 2, 1
        before = ort.InferenceSession(str(first), sess_options=options, providers=["CPUExecutionProvider"]).run(None, {"images": data})[0]
        after = ort.InferenceSession(str(second), sess_options=options, providers=["CPUExecutionProvider"]).run(None, {"images": data})[0]
        self.assertTrue(np.allclose(after[..., :4], before[..., :4] * 2, rtol=1e-4, atol=1e-4))

    def test_checkpoint_metadata_never_executes_an_experiment_path(self):
        marker = self.root / "executed.txt"
        self.experiment.write_text(f"open({str(marker)!r},'w').write('executed')\n", encoding="utf-8")
        self.payload["experiment_path"] = str(self.experiment)
        self.save()
        with self.assertRaisesRegex(ValueError, "experiment"):
            prepare_model(self.checkpoint, self.root, 32)
        self.assertFalse(marker.exists())

    def test_unsafe_serialized_objects_are_never_executed(self):
        marker = self.root / "unsafe.txt"
        self.payload["extra"] = _UnsafePayload(str(marker))
        self.save()
        with self.assertRaisesRegex(ValueError, "safely read"):
            self.prepare()
        self.assertFalse(marker.exists())

    def test_legacy_numeric_numpy_metric_scalars_load_safely(self):
        self.payload["best_ap"] = np.float64(.7)
        self.payload["last_epoch"] = np.int64(3)
        self.save()
        checkpoint = _safe_load(self.checkpoint)
        self.assertEqual(checkpoint["best_ap"], .7)
        self.assertEqual(checkpoint["last_epoch"], 3)
        self.assertIsInstance(checkpoint["best_ap"], float)

    def test_numpy_object_scalars_are_not_allowed(self):
        with self.assertRaises(ValueError):
            _numeric_numpy_scalar(np.dtype("O"), b"x" * np.dtype("O").itemsize)

    def test_custom_numpy_and_tensor_strides_are_normalized_without_truthiness(self):
        for values in (np.asarray([8, 16, 32]), torch.tensor([8, 16, 32]), torch.tensor([8., 16., 32.])):
            with self.subTest(values=values):
                self.assertEqual(_strides(SimpleNamespace(yolox_strides=values)), [8, 16, 32])
                self.assertEqual(_strides(SimpleNamespace(head=SimpleNamespace(strides=values))), [8, 16, 32])
                self.assertEqual(_strides(SimpleNamespace(), {"yolox_strides": values}), [8, 16, 32])
        for values in (np.asarray([]), np.asarray([[8, 16]]), torch.tensor([8., float("nan")]),
                       torch.tensor([8., 8.5]), np.asarray([8, 8]), torch.tensor([8, 512]), [True, 16]):
            with self.subTest(values=values), self.assertRaisesRegex(ValueError, "strides"):
                _strides(SimpleNamespace(yolox_strides=values))

    def test_load_mmap_compatibility_still_uses_weights_only(self):
        with patch("torch.load", side_effect=[RuntimeError("mmap can only be used with files saved with zip serialization"), self.payload]) as load:
            self.assertIs(_safe_load(self.checkpoint), self.payload)
        self.assertEqual(load.call_count, 2)
        self.assertTrue(all(call.kwargs["weights_only"] is True for call in load.call_args_list))

    def test_uniform_state_wrappers_and_container_variants(self):
        for container in ("model", "state_dict", "model_state_dict"):
            with self.subTest(container=container):
                wrapped = {"module._orig_mod.model." + key: value for key, value in self.state.items()}
                normalized = _state_dict({container: wrapped})
                self.assertEqual(set(normalized), set(self.state))
        self.assertEqual(set(_state_dict(self.state)), set(self.state))

    def test_missing_extra_or_nonfinite_trained_weights_fail_admission(self):
        cases = [dict(self.state), dict(self.state), dict(self.state)]
        del cases[0]["proj.bias"]
        cases[1]["unexpected"] = torch.ones(1)
        cases[2]["proj.bias"] = torch.full((7,), float("nan"))
        for state in cases:
            self.payload["model"] = state
            self.save()
            with self.subTest(keys=list(state)), self.assertRaisesRegex(ValueError, "completely match"):
                self.prepare()

    def test_class_names_and_count_must_match_actual_output(self):
        with self.assertRaisesRegex(ValueError, "has 2 classes"):
            self.prepare(class_names="orange,blue,white")
        self.payload["nc"] = 3
        self.save()
        with self.assertRaisesRegex(ValueError, "class-count"):
            self.prepare()

    def test_multilabel_checkpoint_is_not_silently_downgraded(self):
        self.payload["multi_label_config"] = {"multi_label": True}
        self.save()
        with self.assertRaisesRegex(ValueError, "multi-label"):
            self.prepare()

    def test_cancellation_before_work_does_not_create_cache(self):
        event = threading.Event()
        event.set()
        with self.assertRaises(ExportCancelled):
            self.prepare(cancelled=event)
        self.assertFalse((self.root / "data" / "model_cache").exists())

    def test_cancellation_during_conversion_never_publishes_model(self):
        event = threading.Event()
        def progress(message):
            if "Comparing" in message:
                event.set()
        with self.assertRaises(ExportCancelled):
            self.prepare(progress=progress, cancelled=event.is_set)
        self.assertFalse(list((self.root / "data" / "model_cache").glob("*/manifest.json")))

    def test_checkpoint_change_during_conversion_is_not_published(self):
        def progress(message):
            if "Converting" in message:
                with self.checkpoint.open("ab") as file:
                    file.write(b"changed while saving")
        with self.assertRaisesRegex(ValueError, "changed during conversion"):
            self.prepare(progress=progress)
        self.assertFalse(list((self.root / "data" / "model_cache").glob("*/manifest.json")))

    def test_onnx_parity_failure_does_not_publish(self):
        with patch("app.checkpoint_export._validate_onnx", side_effect=ValueError("prediction parity mismatch")):
            with self.assertRaisesRegex(ValueError, "parity mismatch"):
                self.prepare()
        self.assertFalse(list((self.root / "data" / "model_cache").glob("*/manifest.json")))

    def test_exp_get_model_and_tuple_metadata_are_supported(self):
        self.experiment.write_text(CUSTOM_SOURCE.replace("def build_model():\n    return Detector(), ['custom_orange', 'custom_blue']",
            "class Exp:\n    test_size = (32, 64)\n    def get_model(self):\n        return Detector(), {'names':['one','two'], 'yolox_strides':[8]}"), encoding="utf-8")
        del self.payload["names"]
        self.save()
        self.assertEqual(json.loads(self.metadata(self.prepare())["names"]), ["one", "two"])

    def test_industrial_checkpoint_requires_explicit_configuration(self):
        self.payload["rv_arch"] = "industrial_yolox"
        self.payload["rv_variant"] = "simam"
        self.save()
        with self.assertRaisesRegex(ValueError, "industrial/ASFF"):
            prepare_model(self.checkpoint, self.root, 32)
        self.assertTrue(self.prepare().is_file())

    def test_missing_experiment_dependencies_explain_configuration_requirement(self):
        self.experiment.write_text("import definitely_missing_ualr_layer\n", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "unavailable dependency"):
            self.prepare()

    def test_auto_architecture_uses_tensor_dimensions_and_recorded_metadata(self):
        state = {"backbone.backbone.stem.conv.conv.weight": torch.zeros(16, 12, 3, 3),
                 "backbone.backbone.dark2.0.dconv.conv.weight": torch.zeros(16, 1, 3, 3)}
        config = _native_config({}, state, "auto")
        self.assertEqual((config["depth"], config["width"], config["depthwise"]), (.33, .25, True))
        recorded = {"schema_version": 1, "architecture": "yolox_pafpn", "depth": .5, "width": .25,
                    "depthwise": True, "act": "relu", "normalization": {"type": "batchnorm2d", "eps": .002, "momentum": .1}}
        config = _native_config({"yolox_inference_config": recorded}, state, "auto")
        self.assertEqual((config["depth"], config["act"], config["bn_eps"]), (.5, "relu", .002))
        with self.assertRaisesRegex(ValueError, "conflicts"):
            _native_config({"yolox_inference_config": recorded}, state, "nano")

    def test_native_nano_real_export_and_strict_state_validation(self):
        from app.vendor.yolox_models import build_model
        model = build_model(2, .33, .25, True)
        self.payload = {"model": model.state_dict(), "names": ["orange", "blue"], "nc": 2,
                        "input_size": [32, 64], "test_size": [32, 64]}
        self.save()
        output = prepare_model(self.checkpoint, self.root, None)
        self.assertEqual(json.loads(self.metadata(output)["input_size"]), [32, 64])
        self.assertEqual(json.loads(self.metadata(output)["yolox_strides"]), [8, 16, 32])

    def test_portable_official_style_exp_import_and_subclass(self):
        from app.vendor.yolox_models import build_model
        model = build_model(2, .33, .25, True)
        self.payload = {"model": model.state_dict(), "names": ["orange", "blue"], "nc": 2,
                        "input_size": [32, 64], "test_size": [32, 64]}
        self.save()
        self.experiment.write_text('''
from yolox.exp import Exp as MyExp
from yolox.models import YOLOX, YOLOPAFPN, YOLOXHead
class Exp(MyExp):
    def __init__(self):
        super().__init__()
        self.num_classes = 2
        self.depth = .33
        self.width = .25
        self.depthwise = True
        self.input_size = self.test_size = (32, 64)
''', encoding="utf-8")
        before = {name: module for name, module in sys.modules.items() if name == "yolox" or name.startswith("yolox.")}
        # Force the portable compatibility branch even if the test host has
        # a separate training-package installation. No original repo imports.
        original_find = importlib.machinery.PathFinder.find_spec
        def find(fullname, *args, **kwargs):
            return None if fullname == "yolox" else original_find(fullname, *args, **kwargs)
        with patch.dict(sys.modules, {name: None for name in before}, clear=False):
            for name in before:
                sys.modules.pop(name, None)
            with patch("app.checkpoint_export.importlib.machinery.PathFinder.find_spec", side_effect=find):
                output = self.prepare()
            self.assertFalse(any(name == "yolox" or name.startswith("yolox.") for name in sys.modules))
        self.assertTrue(output.is_file())

    def test_onnx_passthrough_does_not_import_or_load_checkpoint(self):
        output = self.root / "existing.onnx"
        output.write_bytes(b"validation belongs to the runtime")
        with patch("app.checkpoint_export._safe_load", side_effect=AssertionError("no checkpoint load")):
            self.assertEqual(prepare_model(output, self.root), output)


if __name__ == "__main__":
    unittest.main()
