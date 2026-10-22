from __future__ import annotations

import os
from typing import List, Optional

import numpy as np

from ..config import DetectorConfig
from ..types import InferenceError
from .base import InferenceBackend


# Provider preference when device="auto". TensorRT gives the fastest
# inference when the model has been warmed; CUDA is fallback; CPU always.
_AUTO_PREF = ("TensorrtExecutionProvider", "CUDAExecutionProvider", "CPUExecutionProvider")


def _resolve_providers(cfg: DetectorConfig, available: List[str]) -> List[str]:
    if cfg.providers:
        # Honor explicit caller choice, but filter to what's actually available.
        return [p for p in cfg.providers if p in available]
    if cfg.device == "cpu":
        if "CPUExecutionProvider" not in available:
            raise InferenceError(f"CPU provider was requested but is unavailable. ORT sees: {available}")
        return ["CPUExecutionProvider"]
    if cfg.device == "cuda":
        if "CUDAExecutionProvider" not in available:
            raise InferenceError(f"CUDA was requested but its provider is unavailable. ORT sees: {available}")
        return [p for p in ("CUDAExecutionProvider", "CPUExecutionProvider") if p in available]
    if cfg.device == "tensorrt":
        if "TensorrtExecutionProvider" not in available:
            raise InferenceError(f"TensorRT was requested but its provider is unavailable. ORT sees: {available}")
        return [p for p in ("TensorrtExecutionProvider", "CUDAExecutionProvider", "CPUExecutionProvider")
                if p in available]
    # auto
    return [p for p in _AUTO_PREF if p in available]


class ONNXBackend(InferenceBackend):
    def __init__(self) -> None:
        self._session = None
        self._input_name: Optional[str] = None
        self._output_names: Optional[List[str]] = None
        self._used_providers: List[str] = []
        self._cfg: Optional[DetectorConfig] = None

    def open(self, cfg: DetectorConfig) -> None:
        if not cfg.model_path:
            raise InferenceError("DetectorConfig.model_path is empty")
        if not os.path.isfile(cfg.model_path):
            raise InferenceError(f"model file not found: {cfg.model_path}")

        try:
            import onnxruntime as ort  # lazy import — optional dep
        except Exception as e:
            raise InferenceError(
                "onnxruntime is not installed. Run: pip install onnxruntime "
                "(or onnxruntime-gpu for CUDA/TensorRT)"
            ) from e

        available = list(ort.get_available_providers())
        providers = _resolve_providers(cfg, available)
        if not providers:
            raise InferenceError(
                f"no execution providers available. ORT sees: {available}"
            )

        so = ort.SessionOptions()
        if cfg.intra_op_threads > 0:
            so.intra_op_num_threads = int(cfg.intra_op_threads)
        if cfg.inter_op_threads > 0:
            so.inter_op_num_threads = int(cfg.inter_op_threads)

        try:
            sess = ort.InferenceSession(cfg.model_path, sess_options=so, providers=providers)
        except Exception as e:
            raise InferenceError(f"failed to create ORT session: {e}") from e

        inputs = sess.get_inputs()
        outputs = sess.get_outputs()
        if not inputs or not outputs:
            raise InferenceError("ONNX model has no inputs or outputs")

        self._session = sess
        self._input_name = inputs[0].name
        self._output_names = [o.name for o in outputs]
        self._used_providers = list(sess.get_providers())
        self._cfg = cfg

    def close(self) -> None:
        self._session = None
        self._input_name = None
        self._output_names = None

    def is_open(self) -> bool:
        return self._session is not None

    def input_name(self) -> str:
        if self._input_name is None:
            raise InferenceError("backend not open")
        return self._input_name

    def infer_raw(self, input_tensor: np.ndarray) -> List[np.ndarray]:
        if self._session is None:
            raise InferenceError("backend not open")
        try:
            outs = self._session.run(self._output_names, {self._input_name: input_tensor})
        except Exception as e:
            raise InferenceError(f"ORT run failed: {e}") from e
        return list(outs)

    def describe(self) -> str:
        if self._session is None:
            return "onnx backend [closed]"
        return f"onnx backend [open] providers={self._used_providers}"
