"""Optional ORT TensorRT acceleration with a warmed, hardware-specific cache.

The portable CPU runtime remains usable on computers without NVIDIA hardware.
Acceleration is selected only after a real GPU probe and successful warmup.
Fallback happens while opening a model, before the camera starts; an inference
failure after opening raises an error instead of changing runtimes mid-frame.
"""
from __future__ import annotations

from contextlib import contextmanager
import csv
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import threading

import numpy as np

from .vendor.inference.backends.onnx_backend import ONNXBackend
from .vendor.inference.types import InferenceError


_TRT = "TensorrtExecutionProvider"
_CPU = "CPUExecutionProvider"
_MODES = {"auto", "cpu", "tensorrt_fp32", "tensorrt_fp16"}
_BUILD_LOCK = threading.Lock()


class _Cancelled(InferenceError):
    pass


class _SourceChanged(InferenceError):
    pass


def probe_nvidia_gpu() -> dict | None:
    """Return a real first-device identity, never infer a GPU from ORT packages."""
    executable = shutil.which("nvidia-smi")
    if not executable and os.name == "nt":
        for path in (Path(os.environ.get("SystemRoot", r"C:\Windows")) / "System32" / "nvidia-smi.exe",
                     Path(os.environ.get("ProgramFiles", r"C:\Program Files")) / "NVIDIA Corporation" / "NVSMI" / "nvidia-smi.exe"):
            if path.is_file():
                executable = str(path)
                break
    if not executable:
        return None
    options = {"creationflags": subprocess.CREATE_NO_WINDOW} if os.name == "nt" else {}
    try:
        result = subprocess.run(
            [executable, "--query-gpu=uuid,name,driver_version,compute_cap", "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=4, check=True, **options)
        rows = list(csv.reader(result.stdout.splitlines(), skipinitialspace=True))
        if not rows or len(rows[0]) != 4:
            return None
        uuid, name, driver, capability = (value.strip() for value in rows[0])
        if (not uuid.startswith("GPU-") or not name or not driver
                or not re.fullmatch(r"\d+\.\d+", capability)):
            return None
        return {"device_id": 0, "uuid": uuid, "name": name, "driver_version": driver,
                "compute_capability": capability}
    except (OSError, ValueError, subprocess.SubprocessError):
        return None


def _runtime_fingerprint(ort, gpu: dict) -> dict:
    # Bind caches to the installed TensorRT SDK, not just ORT's advertised EP.
    # CUDA/runtime library loading is then exercised by session creation/warmup.
    try:
        import tensorrt
        version = str(tensorrt.__version__)
    except (ImportError, AttributeError) as exc:
        raise InferenceError("TensorRT runtime is not installed; install the optional GPU dependencies.") from exc
    if not version:
        raise InferenceError("TensorRT runtime version could not be identified.")
    build_info = str(ort.get_build_info()) if hasattr(ort, "get_build_info") else ""
    return {"gpu": dict(gpu), "onnxruntime": str(ort.__version__),
            "tensorrt": version, "ort_build": build_info}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _external_model_files(path: Path, *, required: bool) -> list[Path]:
    try:
        import onnx
    except ImportError:
        if required:
            raise InferenceError("ONNX is required to verify the TensorRT model cache; install optional GPU dependencies.") from None
        return []
    model = onnx.load(str(path), load_external_data=False)
    locations = set()

    def tensors(message):
        if isinstance(message, onnx.TensorProto):
            if message.data_location == onnx.TensorProto.EXTERNAL:
                location = next((item.value for item in message.external_data if item.key == "location"), "")
                if not location:
                    raise InferenceError("ONNX external tensor data has no location.")
                locations.add((path.parent / location).resolve())
            return
        for field, value in message.ListFields():
            if field.type != field.TYPE_MESSAGE:
                continue
            repeated = field.is_repeated if hasattr(field,'is_repeated') else field.label == field.LABEL_REPEATED
            if repeated:
                for child in value:
                    tensors(child)
            else:
                tensors(value)

    tensors(model.graph)
    return sorted(locations)


def _model_fingerprint(path: Path, *, required: bool = False) -> dict:
    return {"onnx_sha256": _sha256(path),
            "external_data": {str(item): _sha256(item) for item in _external_model_files(path, required=required)}}


@contextmanager
def _cache_lock(directory: Path):
    """Serialize a cache build within this process and across desktop instances."""
    with _BUILD_LOCK:
        directory.mkdir(parents=True, exist_ok=True)
        with (directory / "build.lock").open("a+b") as handle:
            handle.seek(0)
            if not handle.read(1):
                handle.write(b"0")
                handle.flush()
            handle.seek(0)
            try:
                if os.name == "nt":
                    import msvcrt
                    msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
                else:
                    import fcntl
                    fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            except OSError as exc:
                raise InferenceError("Another instance is building this TensorRT cache; using CPU for this load.") from exc
            try:
                yield
            finally:
                handle.seek(0)
                if os.name == "nt":
                    msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
                else:
                    fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


class AcceleratedONNXBackend(ONNXBackend):
    def __init__(self, cache_root=None, mode="auto", progress=None, cancelled=None):
        super().__init__()
        if mode not in _MODES:
            raise ValueError("Choose auto, cpu, tensorrt_fp32, or tensorrt_fp16.")
        self.mode = mode
        self.cache_root = Path(cache_root) if cache_root is not None else Path.home() / ".cache" / "part-tracking-demo-ualr" / "tensorrt"
        self.progress = progress
        self.cancelled = cancelled
        self.notice = ""
        self.actual_mode = "closed"
        self.cache_directory = None
        self._gpu_name = ""

    def _check_cancelled(self):
        if self.cancelled is not None and self.cancelled():
            raise _Cancelled("Model loading was cancelled.")

    def _notify(self, message):
        if self.progress is not None:
            try:
                self.progress(message)
            except Exception:
                pass

    @staticmethod
    def _shape(session, cfg):
        inputs = session.get_inputs()
        outputs = session.get_outputs()
        if len(inputs) != 1 or not outputs:
            raise InferenceError("YOLOX requires one image input and a detection output.")
        shape = list(inputs[0].shape)
        if (len(shape) != 4 or any(isinstance(dim, bool) for dim in shape)
                or any(isinstance(dim, int) and dim != target for dim, target in zip(shape[:2], (1, 3)))):
            raise InferenceError(f"YOLOX image input must have shape [1,3,H,W]; model declares {shape}.")
        fallback = getattr(cfg, "input_hw", None) or (int(cfg.img_size), int(cfg.img_size))
        dynamic_spatial = any(not isinstance(dim, int) for dim in shape[2:])
        if dynamic_spatial and hasattr(session, "get_modelmeta"):
            metadata = session.get_modelmeta().custom_metadata_map or {}
            recorded = metadata.get("input_size") or metadata.get("test_size")
            if recorded:
                try:
                    fallback = json.loads(recorded) if isinstance(recorded, str) else recorded
                except (TypeError, ValueError) as exc:
                    raise InferenceError("YOLOX input_size metadata must contain [height,width].") from exc
        if dynamic_spatial and (not isinstance(fallback, (tuple, list)) or len(fallback) != 2
                or any(type(value) is not int or value <= 0 for value in fallback)):
            raise InferenceError("YOLOX input dimensions must be positive integers.")
        spatial = tuple(dim if isinstance(dim, int) else default for dim, default in zip(shape[2:], fallback))
        if any(dim <= 0 for dim in spatial):
            raise InferenceError("YOLOX input dimensions must be positive integers.")
        expected = (1, 3, *spatial)
        if getattr(inputs[0], "type", "tensor(float)") != "tensor(float)":
            raise InferenceError("Use a YOLOX ONNX export with FP32 image input.")
        return expected

    @staticmethod
    def _validate_outputs(outputs):
        if not outputs:
            raise InferenceError("YOLOX produced no output tensors.")
        first = outputs[0]
        if (not isinstance(first, np.ndarray) or first.ndim != 3 or first.shape[0] != 1
                or first.shape[1] < 1 or first.shape[2] <= 5):
            raise InferenceError("YOLOX output must have shape [1, N, 5+C].")
        for output in outputs:
            if not isinstance(output, np.ndarray) or not np.issubdtype(output.dtype, np.number) or not np.isfinite(output).all():
                raise InferenceError("YOLOX output contains invalid or non-finite values.")
        return list(outputs)

    def _new_session(self, ort, cfg, providers):
        options = ort.SessionOptions()
        if cfg.intra_op_threads > 0:
            options.intra_op_num_threads = int(cfg.intra_op_threads)
        if cfg.inter_op_threads > 0:
            options.inter_op_num_threads = int(cfg.inter_op_threads)
        return ort.InferenceSession(cfg.model_path, sess_options=options, providers=providers)

    def _warmup(self, session, cfg, source, expected_source, *, strict):
        self._check_cancelled()
        shape = self._shape(session, cfg)
        outputs = [item.name for item in session.get_outputs()]
        self._validate_outputs(session.run(outputs, {session.get_inputs()[0].name: np.zeros(shape, dtype=np.float32)}))
        self._check_cancelled()
        if _model_fingerprint(source, required=strict) != expected_source:
            raise _SourceChanged("The ONNX model or its tensor data changed while loading; wait for saving to finish and reload.")
        return shape

    @staticmethod
    def _cached_generation(directory, identity):
        try:
            manifest = json.loads((directory / "selected.json").read_text(encoding="utf-8"))
            generation = manifest["generation"]
            if (manifest["identity"] != identity or not isinstance(generation, str)
                    or Path(generation).name != generation or not generation.startswith("build-")):
                return None
            target = directory / generation
            artifacts = manifest["artifacts"]
            if not isinstance(artifacts, dict) or not artifacts or not any(name.endswith(".engine") for name in artifacts):
                return None
            for name, expected in artifacts.items():
                if Path(name).name != name or _sha256(target / name) != expected:
                    return None
            actual = {item.name for item in target.iterdir() if item.is_file()}
            if actual != set(artifacts):
                return None
            return target
        except (OSError, ValueError, KeyError, TypeError):
            return None

    def _open_tensor(self, ort, cfg, source, gpu):
        fingerprint = _model_fingerprint(source, required=True)
        precision = "tensorrt_fp16" if self.mode == "tensorrt_fp16" else "tensorrt_fp32"
        metadata_session = self._new_session(ort, cfg, [_CPU])
        shape = list(self._shape(metadata_session, cfg))
        input_name = metadata_session.get_inputs()[0].name
        del metadata_session
        identity = {"schema": 1, "policy": "ort-trt-fixed-shape-v1", "source": fingerprint,
                    "runtime": _runtime_fingerprint(ort, gpu), "precision": precision, "input_shape": shape}
        key = hashlib.sha256(json.dumps(identity, sort_keys=True).encode("utf-8")).hexdigest()
        directory = self.cache_root.expanduser().resolve() / key
        with _cache_lock(directory):
            self._check_cancelled()
            target = self._cached_generation(directory, identity)
            reused = target is not None
            if target is None:
                target = Path(tempfile.mkdtemp(prefix="build-", dir=directory))
            self._notify("Loading cached TensorRT engine…" if reused else "Building TensorRT engine; first load can take several minutes…")
            provider_options = {"device_id": int(gpu["device_id"]), "trt_engine_cache_enable": True,
                                "trt_engine_cache_path": str(target), "trt_fp16_enable": precision == "tensorrt_fp16",
                                "trt_int8_enable": False, "trt_max_workspace_size": 1024 * 1024 * 1024,
                                "trt_profile_min_shapes": f"{input_name}:{'x'.join(map(str, shape))}",
                                "trt_profile_opt_shapes": f"{input_name}:{'x'.join(map(str, shape))}",
                                "trt_profile_max_shapes": f"{input_name}:{'x'.join(map(str, shape))}"}
            session = self._new_session(ort, cfg, [(_TRT, provider_options), _CPU])
            if _TRT not in session.get_providers():
                raise InferenceError("ONNX Runtime could not activate its TensorRT provider.")
            session.disable_fallback()
            self._warmup(session, cfg, source, fingerprint, strict=True)
            artifacts = {item.name: _sha256(item) for item in target.iterdir() if item.is_file()}
            if not any(name.endswith(".engine") for name in artifacts):
                raise InferenceError("TensorRT produced no cached engine; acceleration could not be confirmed.")
            manifest = {"identity": identity, "generation": target.name, "artifacts": artifacts}
            temporary = directory / (target.name + ".json.tmp")
            temporary.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
            temporary.replace(directory / "selected.json")
            self.actual_mode = precision
            self._gpu_name = str(gpu["name"])
            self.cache_directory = target
            return session

    def open(self, cfg):
        self.close()
        self.notice = ""
        self._check_cancelled()
        source = Path(cfg.model_path).expanduser().resolve()
        if not cfg.model_path or not source.is_file():
            raise InferenceError(f"ONNX model was not found: {cfg.model_path}")
        try:
            import onnxruntime as ort
        except ImportError as exc:
            raise InferenceError("ONNX Runtime is not installed.") from exc
        available = list(ort.get_available_providers())
        try:
            initial_source = _model_fingerprint(source)
        except Exception as exc:
            raise InferenceError(f"Could not inspect the ONNX model: {exc}") from exc
        session = None
        if self.mode != "cpu":
            try:
                gpu = probe_nvidia_gpu()
                if gpu is None:
                    raise InferenceError("No usable NVIDIA GPU was found.")
                if _TRT not in available:
                    raise InferenceError("This ONNX Runtime build has no TensorRT provider; install optional GPU dependencies.")
                session = self._open_tensor(ort, cfg, source, gpu)
            except (_Cancelled, _SourceChanged):
                raise
            except Exception as exc:
                if _model_fingerprint(source) != initial_source:
                    raise _SourceChanged("The ONNX model changed while loading; finish saving and reload.") from exc
                self.notice = "TensorRT unavailable; using CPU. " + str(exc)
                self._notify(self.notice)
        if session is None:
            if _CPU not in available:
                raise InferenceError("The ONNX Runtime CPU provider is unavailable.")
            self._notify("Loading and warming ONNX Runtime CPU…")
            try:
                session = self._new_session(ort, cfg, [_CPU])
                self._warmup(session, cfg, source, initial_source, strict=False)
            except (_Cancelled, _SourceChanged):
                raise
            except Exception as exc:
                raise InferenceError(f"Could not load and warm the YOLOX CPU model: {exc}") from exc
            self.actual_mode = "cpu"
        self._check_cancelled()
        self._session = session
        self._cfg = cfg
        self._input_name = session.get_inputs()[0].name
        self._output_names = [item.name for item in session.get_outputs()]
        self._used_providers = list(session.get_providers())

    def infer_raw(self, input_tensor):
        return self._validate_outputs(super().infer_raw(input_tensor))

    def close(self):
        super().close()
        self._cfg = None
        self._used_providers = []
        self.actual_mode = "closed"
        self.cache_directory = None
        self._gpu_name = ""

    def describe(self):
        if not self.is_open():
            return "ONNX backend [closed]"
        if self.actual_mode.startswith("tensorrt"):
            label = "TensorRT FP16" if self.actual_mode == "tensorrt_fp16" else "TensorRT FP32"
            return f"{label} [open] • {self._gpu_name} • warmed engine cache"
        return "ONNX Runtime CPU [open]" + (" • " + self.notice if self.notice else "")
