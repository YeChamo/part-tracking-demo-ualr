"""Prepare a selected YOLOX checkpoint for the portable ONNX runtime.

Checkpoints are read with PyTorch's restricted weights-only loader. Explicitly
selected Python experiment files are user code; checkpoint metadata never
chooses or imports such a file. Cache publication follows complete weight
admission, CPU export, and Torch/ONNX Runtime numerical comparison.
"""
from __future__ import annotations

import ast
from collections.abc import Mapping
from contextlib import contextmanager
import hashlib
import importlib
import importlib.abc
import importlib.machinery
import importlib.util
import json
import math
from numbers import Real
import os
from pathlib import Path
import shutil
import sys
import tempfile
import threading
import types
import uuid

import numpy as np

from .model_classes import parse_class_names


EXPORTER_VERSION = "ualr-yolox-onnx-v1"
_EXPORT_LOCK = threading.RLock()
_VARIANTS = {
    "nano": (0.33, 0.25, True), "tiny": (0.33, 0.375, False),
    "s": (0.33, 0.50, False), "m": (0.67, 0.75, False),
    "l": (1.0, 1.0, False), "x": (1.33, 1.25, False),
}
_STEMS = {(int(64 * width), depthwise): name
          for name, (_, width, depthwise) in _VARIANTS.items()}


class ExportCancelled(RuntimeError):
    pass


def _check_cancelled(cancelled) -> None:
    if cancelled is None:
        return
    stopped = cancelled() if callable(cancelled) else cancelled.is_set()
    if stopped:
        raise ExportCancelled("YOLOX model preparation cancelled.")


def _progress(callback, message: str, cancelled=None) -> None:
    _check_cancelled(cancelled)
    if callback is not None:
        callback(message)
    _check_cancelled(cancelled)


def _digest(path: Path, cancelled=None) -> str:
    value = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(1024 * 1024):
            _check_cancelled(cancelled)
            value.update(chunk)
    return value.hexdigest()


def _json(value) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _numeric_numpy_scalar(dtype, data):
    """Admit old numeric metric scalars without admitting NumPy object arrays."""
    dtype = np.dtype(dtype)
    if (dtype.kind not in "buifc" or dtype.fields or dtype.subdtype
            or not 0 < dtype.itemsize <= 32 or not isinstance(data, (bytes, bytearray))
            or len(data) != dtype.itemsize):
        raise ValueError("Only bounded numeric NumPy checkpoint scalars are supported.")
    return np.frombuffer(data, dtype=dtype, count=1)[0].item()


def _safe_load(path: Path):
    try:
        import torch
    except ImportError as exc:
        raise ValueError("PyTorch is required to convert .pth/.pt YOLOX models; choose an ONNX export or install the conversion runtime.") from exc
    # Explicit, numeric-only compatibility for old RV metric values. Never
    # add checkpoint-specified classes or retry with weights_only=False.
    dtypes = {type(np.dtype(code)) for code in ("?", "i1", "u1", "i2", "u2", "i4", "u4", "i8", "u8", "f2", "f4", "f8", "c8", "c16")}
    allowed = [np.dtype, *dtypes,
               (_numeric_numpy_scalar, "numpy._core.multiarray.scalar"),
               (_numeric_numpy_scalar, "numpy.core.multiarray.scalar")]
    try:
        with torch.serialization.safe_globals(allowed):
            try:
                return torch.load(path, map_location="cpu", weights_only=True, mmap=True)
            except RuntimeError as exc:
                if "mmap can only be used" not in str(exc).lower():
                    raise
                return torch.load(path, map_location="cpu", weights_only=True)
    except Exception as exc:
        raise ValueError("Cannot safely read this YOLOX checkpoint. Use a tensor/state-dict checkpoint with primitive metadata or select its ONNX export. Arbitrary serialized Python objects are not loaded.") from exc


def _state_dict(checkpoint):
    import torch

    if not isinstance(checkpoint, Mapping):
        raise ValueError("YOLOX checkpoint must contain a state dictionary.")
    state = checkpoint
    for key in ("state_dict", "model", "model_state_dict"):
        if isinstance(checkpoint.get(key), Mapping):
            state = checkpoint[key]
            break
    if not state or any(not isinstance(key, str) or not torch.is_tensor(value) for key, value in state.items()):
        raise ValueError("YOLOX model state must be a non-empty mapping of tensor names to tensors.")
    state = dict(state)
    while state:
        prefix = next((value for value in ("module.", "_orig_mod.", "model.")
                       if all(key.startswith(value) for key in state)), None)
        if prefix is None:
            break
        state = {key[len(prefix):]: value for key, value in state.items()}
    return state


def _head_count(state, *, required: bool) -> int | None:
    import torch

    weights = [state.get(f"head.cls_preds.{index}.weight") for index in range(3)]
    if not any(value is not None for value in weights) and not required:
        return None
    if any(not torch.is_tensor(value) or value.ndim != 4 or value.shape[0] <= 0 for value in weights):
        raise ValueError("A native YOLOX checkpoint needs all three trained classification heads; select its Python experiment for a different architecture.")
    counts = {int(value.shape[0]) for value in weights}
    if len(counts) != 1:
        raise ValueError("YOLOX classification heads disagree on class count.")
    return counts.pop()


def _positive(value, label: str, *, maximum: float = 4.0) -> float:
    if (isinstance(value, bool) or not isinstance(value, Real)
            or not math.isfinite(value) or not 0 < value <= maximum):
        raise ValueError(f"Invalid recorded YOLOX {label}.")
    return float(value)


def _variant(value: str) -> str:
    value = str(value).strip().lower().replace("-", "_")
    if value in ("", "auto"):
        return "auto"
    for prefix in ("yolox_", "yolox"):
        if value.startswith(prefix):
            value = value[len(prefix):]
            break
    if value not in _VARIANTS:
        raise ValueError("Choose a native YOLOX Nano/Tiny/S/M/L/X architecture or select its Python experiment.")
    return value


def _native_config(checkpoint, state, architecture: str) -> dict:
    import torch

    if (any(checkpoint.get(key) is not None for key in ("rv_arch", "rv_variant", "rv_model_config"))
            or any(key.startswith("backbone.asff_blocks.") for key in state)):
        raise ValueError("This industrial/ASFF YOLOX graph needs its original Python experiment selected. Its graph cannot be inferred safely from weights alone.")
    selected = _variant(architecture)
    recorded = checkpoint.get("yolox_inference_config")
    if recorded is not None:
        if (not isinstance(recorded, Mapping) or type(recorded.get("schema_version")) is not int
                or recorded.get("schema_version") != 1 or recorded.get("architecture") != "yolox_pafpn"):
            raise ValueError("Unsupported recorded YOLOX graph; select its original Python experiment.")
        depth = _positive(recorded.get("depth"), "depth", maximum=2.0)
        width = _positive(recorded.get("width"), "width", maximum=2.0)
        depthwise = recorded.get("depthwise")
        if type(depthwise) is not bool or recorded.get("act") not in ("silu", "relu", "lrelu"):
            raise ValueError("Unsupported YOLOX activation/depthwise metadata; select its Python experiment.")
        normalization = recorded.get("normalization")
        if not isinstance(normalization, Mapping) or normalization.get("type") != "batchnorm2d":
            raise ValueError("Recorded YOLOX graph must specify BatchNorm normalization.")
        eps = _positive(normalization.get("eps"), "BatchNorm epsilon", maximum=1.0)
        momentum = normalization.get("momentum")
        if momentum is not None and (isinstance(momentum, bool) or not isinstance(momentum, Real)
                                     or not math.isfinite(momentum) or not 0 <= momentum <= 1):
            raise ValueError("Invalid recorded YOLOX BatchNorm momentum.")
        config = {"depth": depth, "width": width, "depthwise": depthwise,
                  "act": recorded["act"], "bn_eps": eps, "bn_momentum": momentum}
        if selected != "auto" and (depth, width, depthwise) != _VARIANTS[selected]:
            raise ValueError("Selected YOLOX architecture conflicts with the checkpoint's recorded graph.")
        return config
    stem = state.get("backbone.backbone.stem.conv.conv.weight")
    if not torch.is_tensor(stem) or stem.ndim != 4:
        raise ValueError("Cannot identify this YOLOX architecture; select its original Python experiment.")
    depthwise = any(key.startswith(("backbone.backbone.dark2.0.dconv.", "backbone.backbone.dark2.0.pconv.")) for key in state)
    inferred = _STEMS.get((int(stem.shape[0]), depthwise))
    if inferred is None:
        raise ValueError("Unrecognized YOLOX width/depthwise graph; select its original Python experiment.")
    if selected != "auto" and selected != inferred:
        raise ValueError("Selected YOLOX architecture conflicts with the trained tensor dimensions.")
    depth, width, depthwise = _VARIANTS[inferred]
    return {"depth": depth, "width": width, "depthwise": depthwise,
            "act": "silu", "bn_eps": .001, "bn_momentum": .03}


def _metadata_size(metadata) -> tuple[int, int] | None:
    if not isinstance(metadata, Mapping):
        return None
    containers = [metadata, *(metadata[key] for key in ("metadata", "meta", "train_args", "args", "hyperparameters", "config")
                              if isinstance(metadata.get(key), Mapping))]
    for container in containers:
        for key in ("test_size", "image_size", "input_size", "img_size", "imgsz"):
            value = container.get(key)
            if value is None:
                continue
            try:
                return _size(value)
            except ValueError:
                raise ValueError(f"Invalid checkpoint {key}; choose a manual input size or correct its experiment.") from None
    return None


def _size(value) -> tuple[int, int]:
    if isinstance(value, str):
        try:
            value = ast.literal_eval(value)
        except (ValueError, SyntaxError):
            raise ValueError("YOLOX input size must be a positive integer or [height, width].") from None
    if isinstance(value, Mapping):
        value = (value.get("height"), value.get("width"))
    if isinstance(value, Real) and not isinstance(value, bool):
        value = (value, value)
    if not isinstance(value, (tuple, list)) or len(value) != 2:
        raise ValueError("YOLOX input size must be an integer or [height, width].")
    if any(isinstance(part, bool) or not isinstance(part, Real) or not math.isfinite(part)
           or part != int(part) or not 16 <= part <= 4096 for part in value):
        raise ValueError("YOLOX input dimensions must be whole numbers from 16 to 4096.")
    return int(value[0]), int(value[1])


def _names(checkpoint, explicit, custom_metadata=None) -> list[str]:
    if explicit is not None and (not isinstance(explicit, str) or explicit.strip()):
        return parse_class_names(explicit)
    for container in (checkpoint, custom_metadata or {}):
        for key in ("names", "class_names"):
            if container.get(key) is not None:
                names = parse_class_names(container[key])
                if names:
                    return names
    return []


def _validate_count(count: int, checkpoint, names) -> None:
    if not 1 <= count <= 4096:
        raise ValueError("YOLOX output must have 1 to 4096 class channels.")
    for key in ("nc", "num_classes"):
        value = checkpoint.get(key)
        if value is not None and (isinstance(value, bool) or value != count):
            raise ValueError("Checkpoint class-count metadata disagrees with its trained output.")
    if names and len(names) != count:
        raise ValueError(f"The YOLOX model has {count} classes, but {len(names)} class names were supplied.")


def _admit_weights(model, state) -> None:
    import torch

    target = model.state_dict()
    missing = [key for key in target if key not in state and not key.endswith(".num_batches_tracked")]
    unexpected = sorted(set(state) - set(target))
    invalid = []
    for key in set(target) & set(state):
        source, destination = state[key], target[key]
        if (source.shape != destination.shape or source.is_complex()
                or (destination.is_floating_point() and not source.is_floating_point())
                or (source.is_floating_point() and not bool(torch.isfinite(source).all()))):
            invalid.append(key)
    if missing or unexpected or invalid:
        raise ValueError("YOLOX checkpoint does not completely match this graph. Select its original Python experiment. "
                         f"Missing={missing[:5]}, unexpected={unexpected[:5]}, invalid={sorted(invalid)[:5]}.")
    model.load_state_dict(state, strict=False)


def _experiment_identity(path: Path, cancelled=None) -> tuple[dict, set[Path]]:
    sources, source_paths, total = {}, set(), 0
    for directory, folders, files in os.walk(path.parent, followlinks=False):
        folders[:] = sorted(folder for folder in folders if folder not in
                            {".git", ".venv", "venv", "node_modules", "__pycache__", "_runtime", "data", ".package", ".build"}
                            and not (Path(directory) / folder).is_symlink())
        for name in sorted(files):
            source = Path(directory) / name
            if source.suffix.lower() != ".py" or source.is_symlink():
                continue
            total += source.stat().st_size
            if len(sources) >= 1024 or total > 16 * 1024 * 1024:
                # A large shared source tree is safe to use but does not get
                # cross-load cache reuse with an incomplete dependency digest.
                return {"file_sha256": _digest(path, cancelled), "uncached": uuid.uuid4().hex}, source_paths
            sources[source.relative_to(path.parent).as_posix()] = _digest(source, cancelled)
            source_paths.add(source.resolve())
    return {"file_sha256": _digest(path, cancelled), "local_python_sources": sources}, source_paths


@contextmanager
def _portable_yolox_namespace():
    """Offer inference-only official-style imports when YOLOX is absent.

    An explicitly available real model-source package takes precedence. This
    compatibility namespace provides no training, dataset, or custom-layer API.
    """
    if "yolox" in sys.modules or importlib.machinery.PathFinder.find_spec("yolox", sys.path) is not None:
        yield
        return
    from .vendor import yolox_models
    from .vendor.yolox_models.experiment import ExportExp

    package = types.ModuleType("yolox")
    package.__path__ = []
    package.__spec__ = importlib.machinery.ModuleSpec("yolox", loader=None, is_package=True)
    experiments = types.ModuleType("yolox.exp")
    experiments.__path__ = []
    experiments.__spec__ = importlib.machinery.ModuleSpec("yolox.exp", loader=None, is_package=True)
    experiments.Exp = ExportExp
    package.exp, package.models = experiments, yolox_models
    aliases = {"yolox": package, "yolox.exp": experiments, "yolox.models": yolox_models}
    for name in ("network_blocks", "darknet", "yolo_pafpn", "yolo_head", "yolox"):
        aliases["yolox.models." + name] = importlib.import_module("app.vendor.yolox_models." + name)
    prior = {name: sys.modules.get(name) for name in aliases}
    try:
        sys.modules.update(aliases)
        yield
    finally:
        for name, module in aliases.items():
            if prior[name] is not None:
                sys.modules[name] = prior[name]
            elif sys.modules.get(name) is module:
                sys.modules.pop(name, None)


@contextmanager
def _experiment(path: Path, source_paths: set[Path]):
    """Import only the explicitly selected file with its local dependencies."""
    old_path = list(sys.path)
    previous = {}
    for name, module in list(sys.modules.items()):
        filename = getattr(module, "__file__", None)
        if filename and not (name == "app" or name.startswith("app.")):
            try:
                local = Path(filename).resolve() in source_paths
            except (OSError, ValueError):
                local = False
            if local:
                previous[name] = sys.modules.pop(name)
    module_name = "_ualr_yolox_experiment_" + uuid.uuid4().hex
    class FreshSourceLoader(importlib.machinery.SourceFileLoader):
        def get_code(self, fullname):
            return compile(self.get_data(self.path), self.path, "exec", dont_inherit=True)

    class FreshSourceFinder(importlib.abc.MetaPathFinder):
        def find_spec(self, fullname, search_path=None, target=None):
            spec = importlib.machinery.PathFinder.find_spec(fullname, search_path)
            if spec is not None and spec.origin:
                try:
                    local = Path(spec.origin).resolve() in source_paths
                except (OSError, ValueError):
                    local = False
                if local:
                    spec.loader = FreshSourceLoader(fullname, spec.origin)
                    return spec
            return None

    finder = FreshSourceFinder()
    try:
        sys.path.insert(0, str(path.parent))
        sys.meta_path.insert(0, finder)
        importlib.invalidate_caches()
        spec = importlib.util.spec_from_file_location(module_name, path)
        if spec is None:
            raise ValueError("Cannot import the selected YOLOX Python experiment.")
        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module
        with _portable_yolox_namespace():
            exec(compile(path.read_bytes(), str(path), "exec"), module.__dict__)
            yield module
    finally:
        sys.path[:] = old_path
        sys.meta_path.remove(finder)
        sys.modules.pop(module_name, None)
        for name, module in list(sys.modules.items()):
            filename = getattr(module, "__file__", None)
            if filename and name not in previous and not (name == "app" or name.startswith("app.")):
                try:
                    if Path(filename).resolve() in source_paths:
                        sys.modules.pop(name, None)
                except (OSError, ValueError):
                    pass
        sys.modules.update(previous)


def _custom_model(module):
    import torch

    metadata = {}
    for key in ("metadata", "MODEL_METADATA"):
        value = getattr(module, key, None)
        if isinstance(value, Mapping):
            metadata.update(value)
    if callable(getattr(module, "build_model", None)):
        result = module.build_model()
        experiment = None
    elif callable(getattr(module, "Exp", None)):
        experiment = module.Exp()
        result = experiment.get_model()
    else:
        raise ValueError("The selected Python file must define build_model() or Exp().get_model().")
    for owner in (module, experiment):
        if owner is not None:
            for key in ("names", "class_names", "input_size", "test_size", "yolox_strides", "num_classes"):
                value = getattr(owner, key, None)
                if value is not None:
                    metadata[key] = value
    if isinstance(result, tuple) and len(result) == 2:
        model, extra = result
        if isinstance(extra, Mapping) and any(key in extra for key in ("names", "class_names", "input_size", "test_size", "num_classes", "yolox_strides")):
            metadata.update(extra)
        else:
            metadata["names"] = extra
    else:
        model = result
    if not isinstance(model, torch.nn.Module):
        raise ValueError("The selected YOLOX experiment must return a torch.nn.Module.")
    return model, metadata


def _strides(model, metadata=None) -> list[int]:
    import torch

    metadata = metadata or {}
    candidates = (getattr(model, "yolox_strides", None), metadata.get("yolox_strides"),
                  getattr(getattr(model, "head", None), "strides", None))
    values = next((candidate for candidate in candidates if candidate is not None), [8, 16, 32])
    if torch.is_tensor(values):
        values = values.detach().cpu().tolist()
    elif isinstance(values, np.ndarray):
        values = values.tolist()
    if isinstance(values, str):
        try:
            values = json.loads(values)
        except ValueError:
            raise ValueError("YOLOX strides must be a JSON integer list.") from None
    if (not isinstance(values, (list, tuple)) or not 1 <= len(values) <= 8
            or any(isinstance(value, bool) or not isinstance(value, Real)
                   or not math.isfinite(value) or value != int(value)
                   or not 1 <= value <= 256 for value in values)):
        raise ValueError("YOLOX strides must contain distinct positive integers up to 256.")
    strides = [int(value) for value in values]
    if len(set(strides)) != len(strides):
        raise ValueError("YOLOX strides must contain distinct positive integers up to 256.")
    return strides


def _input(size: tuple[int, int]) -> np.ndarray:
    # Fixed BGR-like 0..255 input, without global RNG changes or a blank image.
    values = (np.arange(3 * size[0] * size[1], dtype=np.uint32) * 37 + 17) % 256
    return values.astype(np.float32).reshape(1, 3, *size)


def _output(value, size, strides, count=None):
    anchors = sum((size[0] // stride) * (size[1] // stride) for stride in strides)
    if (value.ndim != 3 or value.shape[0] != 1 or value.shape[1] != anchors or value.shape[2] <= 5
            or value.dtype != np.float32 or not np.isfinite(value).all()):
        raise ValueError("Experiment must produce finite FP32 raw YOLOX [1,N,5+C] output matching its input and strides. Set its head.decode_in_inference=False and yolox_strides correctly.")
    actual = int(value.shape[2] - 5)
    if count is not None and actual != count:
        raise ValueError("YOLOX exported output class count disagrees with its trained heads.")
    probabilities = value[..., 4:]
    if probabilities.min() < -1e-6 or probabilities.max() > 1 + 1e-6:
        raise ValueError("YOLOX output must contain sigmoid objectness/class probabilities and raw box channels.")
    return actual


def _validate_onnx(path: Path, identity: dict, data: np.ndarray, expected=None):
    import onnxruntime as ort

    options = ort.SessionOptions()
    options.intra_op_num_threads = 2
    options.inter_op_num_threads = 1
    session = ort.InferenceSession(str(path), sess_options=options, providers=["CPUExecutionProvider"])
    try:
        inputs, outputs = session.get_inputs(), session.get_outputs()
        if len(inputs) != 1 or len(outputs) != 1 or inputs[0].shape != list(data.shape):
            raise ValueError("Converted ONNX input/output signature is incompatible with the selected model.")
        metadata = session.get_modelmeta().custom_metadata_map
        if any(metadata.get(key) != value for key, value in _onnx_metadata(identity).items()):
            raise ValueError("Converted ONNX metadata does not match this checkpoint/configuration.")
        actual = session.run([outputs[0].name], {inputs[0].name: data})[0]
        _output(actual, identity["input_size"], identity["strides"], identity["class_count"])
        if expected is not None and not np.allclose(actual, expected, rtol=3e-3, atol=1e-3):
            difference = float(np.max(np.abs(actual - expected)))
            raise ValueError(f"Converted ONNX does not match Torch predictions (maximum difference {difference:.6g}); conversion was not cached.")
        return actual
    finally:
        del session


def _onnx_metadata(identity: dict) -> dict[str, str]:
    return {"names": _json(identity["names"]), "nc": str(identity["class_count"]),
            "input_size": _json(identity["input_size"]), "test_size": _json(identity["input_size"]),
            "checkpoint_sha256": identity["checkpoint_sha256"],
            "source_checkpoint_sha256": identity["checkpoint_sha256"],
            "ualr_exporter_version": EXPORTER_VERSION, "yolox_decode": "raw",
            "yolox_strides": _json(identity["strides"]), "letterbox": "top_left",
            "yolox_letterbox": "top_left"}


def _cached(directory: Path, identity: dict, data, cancelled=None) -> Path | None:
    model, manifest = directory / "model.onnx", directory / "manifest.json"
    try:
        saved = json.loads(manifest.read_text(encoding="utf-8"))
        if saved.get("identity") != identity or saved.get("onnx_sha256") != _digest(model, cancelled):
            return None
        _check_cancelled(cancelled)
        _validate_onnx(model, identity, data)
        return model
    except ExportCancelled:
        raise
    except Exception:
        return None


def _remove_generated(directory: Path, cache: Path) -> None:
    resolved, boundary = directory.resolve(), cache.resolve()
    if resolved == boundary or not resolved.is_relative_to(boundary):
        raise RuntimeError("Cache cleanup target is outside the model cache.")
    if directory.is_symlink():
        directory.unlink()
    elif directory.exists():
        shutil.rmtree(directory)


def _convert(path, checkpoint, state, model, config, custom_metadata, experiment_identity,
             root, source_hash, image_size, class_names, progress, cancelled):
    import torch
    import onnx

    _progress(progress, "Validating YOLOX weights and class labels…", cancelled)
    model = model.cpu().float().eval()
    model.requires_grad_(False)
    _admit_weights(model, state)
    for layer in model.modules():
        if hasattr(layer, "decode_in_inference"):
            layer.decode_in_inference = False
    size = (_size(image_size) if image_size is not None else
            _metadata_size(checkpoint) or _metadata_size(custom_metadata) or (640, 640))
    strides = _strides(model, custom_metadata)
    if any(dimension % max(strides) for dimension in size):
        raise ValueError("YOLOX input height and width must be divisible by its largest stride.")
    names = _names(checkpoint, class_names, custom_metadata)
    # A selected custom graph may have one/four pyramid heads or different
    # parameter names. Strict weight admission already checked its complete
    # graph; measure its class count from the resulting detection tensor.
    heads = _head_count(state, required=True) if experiment_identity is None else None
    if heads is not None:
        _validate_count(heads, checkpoint, names)
    data = _input(size)
    _progress(progress, "Checking the selected YOLOX graph…", cancelled)
    with torch.inference_mode():
        predicted = model(torch.from_numpy(data))
    if not torch.is_tensor(predicted):
        raise ValueError("YOLOX experiment must return one raw detection tensor, not training losses or a list of outputs.")
    expected = predicted.detach().cpu().numpy()
    count = _output(expected, size, strides, heads)
    _validate_count(count, checkpoint, names)
    if custom_metadata.get("num_classes") is not None and custom_metadata["num_classes"] != count:
        raise ValueError("Python experiment class-count metadata disagrees with its output.")
    identity = {"exporter": EXPORTER_VERSION, "checkpoint_sha256": source_hash,
                "input_size": list(size), "class_count": count, "names": names,
                "strides": strides, "configuration": config, "experiment": experiment_identity,
                "torch_version": torch.__version__, "onnx_version": onnx.__version__}
    cache = (root / "data" / "model_cache").resolve()
    cache.mkdir(parents=True, exist_ok=True)
    key = hashlib.sha256(_json(identity).encode("utf-8")).hexdigest()
    destination = cache / key
    cached = _cached(destination, identity, data, cancelled)
    if cached is not None:
        if _digest(path, cancelled) != source_hash:
            raise ValueError("YOLOX checkpoint changed while loading; wait until saving finishes and retry.")
        _progress(progress, "Using the verified cached YOLOX ONNX model.", cancelled)
        return cached
    _progress(progress, "Converting YOLOX checkpoint to ONNX (first use)…", cancelled)
    with tempfile.TemporaryDirectory(prefix=".export-", dir=cache) as temporary:
        staging = Path(temporary)
        converted = staging / "model.onnx"
        with torch.no_grad():
            torch.onnx.export(model, torch.from_numpy(data), str(converted),
                              input_names=["images"], output_names=["output"],
                              opset_version=17, dynamo=False, external_data=False,
                              do_constant_folding=True)
        _check_cancelled(cancelled)
        graph = onnx.load(str(converted), load_external_data=False)
        if any(tensor.data_location == onnx.TensorProto.EXTERNAL for tensor in graph.graph.initializer):
            raise ValueError("YOLOX conversion produced unexpected external tensor files.")
        onnx.helper.set_model_props(graph, _onnx_metadata(identity))
        onnx.checker.check_model(graph)
        onnx.save(graph, str(converted))
        del graph
        _progress(progress, "Comparing ONNX predictions against the loaded Torch model…", cancelled)
        _validate_onnx(converted, identity, data, expected)
        if _digest(path, cancelled) != source_hash:
            raise ValueError("YOLOX checkpoint changed during conversion; wait until saving finishes and retry.")
        if experiment_identity is not None:
            current, _ = _experiment_identity(Path(experiment_identity["path"]), cancelled)
            if (current["file_sha256"] != experiment_identity["file_sha256"]
                    or ("uncached" not in experiment_identity and current != {key: value for key, value in experiment_identity.items() if key != "path"})):
                raise ValueError("YOLOX Python experiment/dependencies changed during conversion; retry after saving.")
        manifest = {"identity": identity, "onnx_sha256": _digest(converted, cancelled), "validated": "torch_ort_cpu_nonblank_v1"}
        (staging / "manifest.json").write_text(_json(manifest), encoding="utf-8")
        _check_cancelled(cancelled)
        backup = None
        if destination.exists():
            if destination.is_symlink() or not destination.resolve().is_relative_to(cache):
                raise ValueError("The generated model-cache entry must remain inside the cache directory.")
            backup = cache / (".old-" + key + "-" + uuid.uuid4().hex)
            os.replace(destination, backup)
        try:
            os.replace(staging, destination)
        except Exception:
            if backup is not None:
                os.replace(backup, destination)
                backup = None
            raise
        finally:
            if backup is not None:
                _remove_generated(backup, cache)
    _progress(progress, "YOLOX ONNX model verified and ready.", cancelled)
    return destination / "model.onnx"


def prepare_model(path: Path, root: Path, image_size: int | None = 640, *,
                  class_names="", architecture="auto", experiment_path="",
                  progress=None, cancelled=None) -> Path:
    """Return an ONNX path; convert selected .pth/.pt files before camera use.

    ``None`` uses checkpoint/experiment H,W metadata, then 640. An integer is
    a manual square-size override. Custom Python executes only when supplied
    explicitly as ``experiment_path``; no executable path in a checkpoint is
    followed. Progress receives strings; cancellation accepts a callable/Event.
    """
    root = Path(root).expanduser().resolve()
    path = Path(path).expanduser()
    path = (path if path.is_absolute() else root / path).resolve()
    _check_cancelled(cancelled)
    if not path.is_file():
        raise ValueError(f"Selected YOLOX model was not found: {path}")
    if path.suffix.lower() == ".onnx":
        return path
    if path.suffix.lower() not in {".pth", ".pt"}:
        raise ValueError("Choose a YOLOX .pth, .pt, or .onnx model.")
    with _EXPORT_LOCK:
        _progress(progress, "Reading the selected YOLOX checkpoint…", cancelled)
        source_hash = _digest(path, cancelled)
        checkpoint = _safe_load(path)
        state = _state_dict(checkpoint)
        policy = checkpoint.get("multi_label_config", {})
        if not isinstance(policy, Mapping) or policy.get("multi_label", False):
            raise ValueError("This shared-box multi-label checkpoint needs a compatible multi-label runtime; this demo exports single-label bottle/color YOLOX models.")
        import torch
        threads = torch.get_num_threads()
        try:
            torch.set_num_threads(min(4, threads))
            if experiment_path:
                experiment = Path(experiment_path).expanduser()
                experiment = (experiment if experiment.is_absolute() else root / experiment).resolve()
                if not experiment.is_file() or experiment.suffix.lower() != ".py":
                    raise ValueError("Select the original YOLOX Python experiment (.py).")
                fingerprint, source_paths = _experiment_identity(experiment, cancelled)
                fingerprint["path"] = str(experiment)
                _progress(progress, f"Loading the selected experiment: {experiment.name}", cancelled)
                try:
                    with _experiment(experiment, source_paths) as module:
                        model, custom_metadata = _custom_model(module)
                        return _convert(path, checkpoint, state, model, {"kind": "explicit_python_experiment"},
                                        custom_metadata, fingerprint, root, source_hash, image_size,
                                        class_names, progress, cancelled)
                except ImportError as exc:
                    raise ValueError(f"The selected YOLOX experiment needs an unavailable dependency: {exc}. Supply its layers/dependencies or use app.vendor.yolox_models.experiment.ExportExp.") from exc
            config = _native_config(checkpoint, state, architecture)
            count = _head_count(state, required=True)
            _validate_count(count, checkpoint, _names(checkpoint, class_names))
            from .vendor.yolox_models import build_model

            model = build_model(count, **config)
            return _convert(path, checkpoint, state, model, config, {}, None, root,
                            source_hash, image_size, class_names, progress, cancelled)
        finally:
            torch.set_num_threads(threads)
