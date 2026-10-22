"""Acceleration orchestration with fake ORT/GPU; no NVIDIA hardware required."""
from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

import numpy as np

from app.accelerated_backend import (AcceleratedONNXBackend, _external_model_files,
                                     _model_fingerprint, probe_nvidia_gpu)
from app.vendor.inference import DetectorConfig
from app.vendor.inference.types import InferenceError


TRT = "TensorrtExecutionProvider"
CPU = "CPUExecutionProvider"


class _Session:
    def __init__(self, owner, providers):
        self.owner = owner
        self.providers = [value[0] if isinstance(value, tuple) else value for value in providers]
        self.is_tensor = TRT in self.providers
        self.disabled_fallback = False
        self.inputs_seen = []
        self.run_error = None
        self.run_hook = None
        if self.is_tensor and owner.tensor_creation_error:
            raise RuntimeError(owner.tensor_creation_error)
        if self.is_tensor and owner.tensor_activates is False:
            self.providers = [CPU]
        if self.is_tensor and owner.write_engine:
            options = providers[0][1]
            target = Path(options["trt_engine_cache_path"])
            (target / "sample.engine").write_bytes(b"real-engine-placeholder-for-test")

    def get_inputs(self):
        return [SimpleNamespace(name="camera_tensor", shape=self.owner.input_shape, type="tensor(float)")]

    def get_outputs(self):
        return [SimpleNamespace(name="detections", shape=[1, "anchors", "channels"])]

    def get_modelmeta(self):
        return SimpleNamespace(custom_metadata_map=self.owner.metadata)

    def get_providers(self):
        return list(self.providers)

    def disable_fallback(self):
        self.disabled_fallback = True

    def run(self, outputs, inputs):
        self.inputs_seen.append(inputs["camera_tensor"])
        if self.run_hook:
            self.run_hook()
        if self.run_error:
            raise RuntimeError(self.run_error)
        if self.is_tensor and self.owner.tensor_warmup_error:
            raise RuntimeError(self.owner.tensor_warmup_error)
        return self.owner.results


class _ORT:
    __version__ = "test-ort-1"
    SessionOptions = SimpleNamespace

    def __init__(self):
        self.available = [TRT, CPU]
        self.input_shape = [1, 3, 32, 32]
        self.metadata = {}
        self.results = [np.zeros((1, 21, 7), dtype=np.float32)]
        self.calls = []
        self.sessions = []
        self.tensor_creation_error = None
        self.tensor_warmup_error = None
        self.tensor_activates = True
        self.write_engine = True
        self.session_hook = None

    def get_available_providers(self):
        return self.available

    def InferenceSession(self, path, *, sess_options, providers):
        self.calls.append((path, sess_options, providers))
        session = _Session(self, providers)
        if self.session_hook:
            self.session_hook(session)
        self.sessions.append(session)
        return session


class AcceleratedBackendTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="ualr-acceleration-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.model = self.root / "custom.onnx"
        self.model.write_bytes(b"unit-test-model-content")
        self.cfg = DetectorConfig(model_path=str(self.model), img_size=32, intra_op_threads=2, inter_op_threads=1)
        self.ort = _ORT()
        self.gpu = {"device_id": 0, "uuid": "GPU-unit-test", "name": "Test NVIDIA", "driver_version": "999.1",
                    "compute_capability": "8.9"}
        self.progress = []
        self.ort_patch = patch.dict(sys.modules, {"onnxruntime": self.ort})
        self.gpu_patch = patch("app.accelerated_backend.probe_nvidia_gpu", side_effect=lambda: dict(self.gpu))
        # File hashing stays real. External-data parsing and runtime probing are
        # isolated so these orchestration tests do not need ONNX or TensorRT.
        self.external_patch = patch("app.accelerated_backend._external_model_files", return_value=[])
        self.runtime_patch = patch("app.accelerated_backend._runtime_fingerprint",
                                   side_effect=lambda ort, gpu: {"gpu": dict(gpu), "ort": ort.__version__, "trt": "10.test"})
        for active in (self.ort_patch, self.gpu_patch, self.external_patch, self.runtime_patch):
            active.start()
            self.addCleanup(active.stop)

    def backend(self, mode="auto", **kwargs):
        backend = AcceleratedONNXBackend(cache_root=self.root / "cache", mode=mode, progress=self.progress.append, **kwargs)
        self.addCleanup(backend.close)
        return backend

    def test_cpu_mode_never_probes_gpu_and_warms_before_publishing_session(self):
        backend = self.backend("cpu")
        with patch("app.accelerated_backend.probe_nvidia_gpu") as probe:
            backend.open(self.cfg)
        probe.assert_not_called()
        self.assertEqual(backend.actual_mode, "cpu")
        self.assertEqual(self.ort.calls[0][2], [CPU])
        self.assertEqual(len(self.ort.sessions[0].inputs_seen), 1)
        self.assertEqual(self.ort.sessions[0].inputs_seen[0].shape, (1, 3, 32, 32))
        self.assertEqual(self.ort.sessions[0].inputs_seen[0].dtype, np.float32)
        self.assertEqual(backend.input_name(), "camera_tensor")
        self.assertIn("CPU", backend.describe())
        self.assertEqual(self.ort.calls[0][1].intra_op_num_threads, 2)

    def test_advertised_tensor_provider_without_real_gpu_uses_cpu_and_reports_reason(self):
        backend = self.backend()
        with patch("app.accelerated_backend.probe_nvidia_gpu", return_value=None):
            backend.open(self.cfg)
        self.assertEqual(backend.actual_mode, "cpu")
        self.assertIn("NVIDIA GPU", backend.describe())
        self.assertTrue(any("using CPU" in message for message in self.progress))
        self.assertEqual(len(self.ort.calls), 1)
        self.assertEqual(self.ort.calls[0][2], [CPU])

    def test_explicit_tensor_request_falls_back_when_portable_runtime_has_no_provider(self):
        self.ort.available = [CPU]
        backend = self.backend("tensorrt_fp16")
        backend.open(self.cfg)
        self.assertEqual(backend.actual_mode, "cpu")
        self.assertIn("no TensorRT provider", backend.notice)

    def test_tensor_session_failure_uses_cpu_before_open_returns(self):
        self.ort.tensor_creation_error = "TensorRT DLL missing"
        backend = self.backend()
        backend.open(self.cfg)
        self.assertEqual(backend.actual_mode, "cpu")
        self.assertIn("TensorRT DLL missing", backend.describe())
        self.assertFalse(list((self.root / "cache").glob("*/selected.json")))

    def test_tensor_warmup_failure_uses_cpu_and_does_not_publish_failed_cache(self):
        self.ort.tensor_warmup_error = "GPU engine failed during warmup"
        backend = self.backend()
        backend.open(self.cfg)
        self.assertEqual(backend.actual_mode, "cpu")
        self.assertIn("warmup", backend.notice)
        self.assertFalse(list((self.root / "cache").glob("*/selected.json")))

    def test_tensor_provider_silently_disappearing_is_reported_as_cpu_fallback(self):
        self.ort.tensor_activates = False
        backend = self.backend()
        backend.open(self.cfg)
        self.assertEqual(backend.actual_mode, "cpu")
        self.assertIn("activate", backend.notice)

    def test_engine_artifact_required_before_claiming_acceleration(self):
        self.ort.write_engine = False
        backend = self.backend()
        backend.open(self.cfg)
        self.assertEqual(backend.actual_mode, "cpu")
        self.assertIn("no cached engine", backend.notice)

    def test_tensor_cache_options_use_exact_graph_name_shape_and_precision(self):
        self.ort.input_shape = [1, 3, 32, 64]
        backend = self.backend("tensorrt_fp16")
        backend.open(self.cfg)
        options = next(call[2][0][1] for call in self.ort.calls if isinstance(call[2][0], tuple))
        self.assertTrue(options["trt_engine_cache_enable"])
        self.assertTrue(options["trt_fp16_enable"])
        self.assertFalse(options["trt_int8_enable"])
        self.assertEqual(options["trt_profile_min_shapes"], "camera_tensor:1x3x32x64")
        self.assertEqual(options["trt_profile_min_shapes"], options["trt_profile_max_shapes"])
        self.assertEqual(backend.actual_mode, "tensorrt_fp16")
        self.assertEqual(backend._session.inputs_seen[0].shape, (1, 3, 32, 64))
        self.assertTrue(backend._session.disabled_fallback)
        self.assertIn("TensorRT FP16", backend.describe())
        self.assertTrue((backend.cache_directory / "sample.engine").is_file())

    def test_cache_reuse_verifies_artifacts_and_builds_new_generation_after_corruption(self):
        first = self.backend()
        first.open(self.cfg)
        original = first.cache_directory
        first.close()
        second = self.backend()
        second.open(self.cfg)
        self.assertEqual(second.cache_directory, original)
        self.assertTrue(any("cached TensorRT" in message for message in self.progress))
        second.close()
        (original / "sample.engine").write_bytes(b"corrupted")
        third = self.backend()
        third.open(self.cfg)
        self.assertNotEqual(third.cache_directory, original)
        self.assertEqual(third.cache_directory.parent, original.parent)
        manifest = json.loads((third.cache_directory.parent / "selected.json").read_text())
        self.assertEqual(manifest["generation"], third.cache_directory.name)

    def test_cache_identity_changes_with_source_device_driver_runtime_precision_and_shape(self):
        first = self.backend()
        first.open(self.cfg)
        first_path = first.cache_directory.parent
        first.close()
        for field, value in (("uuid", "GPU-other"), ("driver_version", "1000.0"), ("compute_capability", "9.0")):
            old = self.gpu[field]
            self.gpu[field] = value
            backend = self.backend()
            backend.open(self.cfg)
            self.assertNotEqual(backend.cache_directory.parent, first_path)
            backend.close()
            self.gpu[field] = old
        self.ort.__version__ = "test-ort-2"
        runtime = self.backend()
        runtime.open(self.cfg)
        self.assertNotEqual(runtime.cache_directory.parent, first_path)
        self.ort.__version__ = "test-ort-1"
        fp16 = self.backend("tensorrt_fp16")
        fp16.open(self.cfg)
        self.assertNotEqual(fp16.cache_directory.parent, first_path)
        self.ort.input_shape = [1, 3, 32, 64]
        rectangular = self.backend()
        rectangular.open(self.cfg)
        self.assertNotEqual(rectangular.cache_directory.parent, first_path)
        self.ort.input_shape = [1, 3, 32, 32]
        self.model.write_bytes(b"different-model-weights")
        changed = self.backend()
        changed.open(self.cfg)
        self.assertNotEqual(changed.cache_directory.parent, first_path)

    def test_confidence_changes_do_not_change_engine_identity(self):
        backend = self.backend()
        backend.open(self.cfg)
        original = backend.cache_directory
        backend.close()
        self.cfg.conf = .85
        backend.open(self.cfg)
        self.assertEqual(backend.cache_directory, original)

    def test_live_tensor_failure_raises_without_cpu_session_or_empty_result(self):
        backend = self.backend()
        backend.open(self.cfg)
        count = len(self.ort.calls)
        backend._session.run_error = "device lost during frame"
        with self.assertRaisesRegex(InferenceError, "device lost"):
            backend.infer_raw(np.zeros((1, 3, 32, 32), dtype=np.float32))
        self.assertEqual(len(self.ort.calls), count)
        self.assertEqual(backend.actual_mode, "tensorrt_fp32")

    def test_bad_warmup_shape_or_nonfinite_result_never_opens(self):
        for bad in (np.zeros((1, 21, 5)), np.zeros((1, 0, 7)), np.zeros((21, 7)), np.full((1, 21, 7), np.nan)):
            with self.subTest(shape=bad.shape):
                self.ort.results = [bad]
                backend = self.backend("cpu")
                with self.assertRaises(InferenceError):
                    backend.open(self.cfg)
                self.assertFalse(backend.is_open())

    def test_nonfinite_live_result_is_an_error(self):
        backend = self.backend("cpu")
        backend.open(self.cfg)
        self.ort.results = [np.full((1, 21, 7), np.inf)]
        with self.assertRaisesRegex(InferenceError, "non-finite"):
            backend.infer_raw(np.zeros((1, 3, 32, 32), dtype=np.float32))

    def test_source_changed_during_warmup_cannot_be_published_or_silently_reloaded(self):
        self.ort.session_hook = lambda session: setattr(session, "run_hook", lambda: self.model.write_bytes(b"weights-being-replaced"))
        backend = self.backend()
        with self.assertRaisesRegex(InferenceError, "changed while loading"):
            backend.open(self.cfg)
        self.assertFalse(backend.is_open())
        self.assertFalse(list((self.root / "cache").glob("*/selected.json")))

    def test_cancellation_before_loading_creates_no_sessions(self):
        backend = self.backend(cancelled=lambda: True)
        with self.assertRaisesRegex(InferenceError, "cancelled"):
            backend.open(self.cfg)
        self.assertEqual(self.ort.calls, [])

    def test_cancellation_after_warmup_never_falls_back_or_publishes(self):
        cancel = [False]
        self.ort.session_hook = lambda session: setattr(session, "run_hook", lambda: cancel.__setitem__(0, True))
        backend = self.backend(cancelled=lambda: cancel[0])
        with self.assertRaisesRegex(InferenceError, "cancelled"):
            backend.open(self.cfg)
        self.assertFalse(backend.is_open())
        self.assertFalse(list((self.root / "cache").glob("*/selected.json")))

    def test_static_rectangular_and_metadata_dynamic_shapes_warm_exact_size(self):
        self.ort.input_shape = [1, 3, "height", "width"]
        self.ort.metadata = {"input_size": "[32,64]"}
        backend = self.backend("cpu")
        backend.open(self.cfg)
        self.assertEqual(backend._session.inputs_seen[0].shape, (1, 3, 32, 64))
        backend.close()
        self.ort.metadata = {}
        self.cfg.input_hw = (64, 96)
        backend.open(self.cfg)
        self.assertEqual(backend._session.inputs_seen[0].shape, (1, 3, 64, 96))

    def test_wrong_batch_or_channel_axis_never_opens(self):
        for shape in ([2, 3, 32, 32], [1, 4, 32, 32], [1, 3, 32], [1, 3, -1, 32]):
            self.ort.input_shape = shape
            backend = self.backend("cpu")
            with self.subTest(shape=shape), self.assertRaises(InferenceError):
                backend.open(self.cfg)
            self.assertFalse(backend.is_open())

    def test_closed_backend_discards_session_config_and_description(self):
        backend = self.backend("cpu")
        backend.open(self.cfg)
        backend.close()
        self.assertFalse(backend.is_open())
        self.assertIsNone(backend._cfg)
        self.assertIn("closed", backend.describe())
        with self.assertRaises(InferenceError):
            backend.infer_raw(np.zeros((1, 3, 32, 32), dtype=np.float32))


class NvidiaProbeTests(unittest.TestCase):
    def test_probe_reads_real_gpu_identity_with_bounded_cli(self):
        completed = SimpleNamespace(stdout="GPU-abc, NVIDIA Test, 555.11, 8.9\n")
        with patch("app.accelerated_backend.shutil.which", return_value="nvidia-smi"), patch(
                "app.accelerated_backend.subprocess.run", return_value=completed) as command:
            result = probe_nvidia_gpu()
        self.assertEqual(result["uuid"], "GPU-abc")
        self.assertEqual(result["compute_capability"], "8.9")
        self.assertEqual(command.call_args.kwargs["timeout"], 4)
        self.assertNotIn("shell", command.call_args.kwargs)

    def test_probe_failure_or_incomplete_identity_is_not_a_gpu(self):
        with patch("app.accelerated_backend.shutil.which", return_value="nvidia-smi"):
            for output in ("", "GPU-abc, Test, 555, N/A", "unknown, Test, 555, 8.9"):
                with self.subTest(output=output), patch("app.accelerated_backend.subprocess.run", return_value=SimpleNamespace(stdout=output)):
                    self.assertIsNone(probe_nvidia_gpu())
            with patch("app.accelerated_backend.subprocess.run", side_effect=subprocess.TimeoutExpired("nvidia-smi", 4)):
                self.assertIsNone(probe_nvidia_gpu())


class ExternalModelDataTests(unittest.TestCase):
    def test_protobuf_seven_descriptor_without_label_hashes_nested_external_tensors(self):
        class Tensor:
            EXTERNAL = 1

            def __init__(self, location):
                self.data_location = self.EXTERNAL
                self.external_data = [SimpleNamespace(key="location", value=location)]

        class Message:
            def __init__(self, fields):
                self.fields = fields

            def ListFields(self):
                return self.fields

        # Protobuf 7 exposes is_repeated and removes FieldDescriptor.label.
        # Exercise both repeated tensors and singular nested graph messages.
        repeated = SimpleNamespace(type=11, TYPE_MESSAGE=11, is_repeated=True)
        singular = SimpleNamespace(type=11, TYPE_MESSAGE=11, is_repeated=False)
        nested = Message([(repeated, [Tensor("weights.bin")])])
        graph = Message([(singular, nested), (repeated, [Tensor("weights.bin")])])
        onnx = SimpleNamespace(TensorProto=Tensor,
                               load=Mock(return_value=SimpleNamespace(graph=graph)))
        with tempfile.TemporaryDirectory(prefix="ualr-external-data-") as folder:
            root = Path(folder)
            model = root / "graph.onnx"
            weights = root / "weights.bin"
            model.write_bytes(b"graph-with-external-tensors")
            weights.write_bytes(b"original-weights")
            with patch.dict(sys.modules, {"onnx": onnx}):
                self.assertEqual(_external_model_files(model, required=True), [weights.resolve()])
                original = _model_fingerprint(model, required=True)
                weights.write_bytes(b"changed-weights")
                changed = _model_fingerprint(model, required=True)
            self.assertEqual(original["onnx_sha256"], changed["onnx_sha256"])
            self.assertNotEqual(original["external_data"], changed["external_data"])


if __name__ == "__main__":
    unittest.main()
