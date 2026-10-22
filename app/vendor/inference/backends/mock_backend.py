from __future__ import annotations

from typing import List, Optional

import numpy as np

from ..config import DetectorConfig
from ..types import InferenceError
from .base import InferenceBackend


class MockBackend(InferenceBackend):
    """Returns caller-supplied raw output tensors.

    Use for testing — lets you drive the Detector's pre/post-process pipeline
    without an actual ONNX model.
    """

    def __init__(
        self,
        raw_outputs: Optional[List[np.ndarray]] = None,
        *,
        fail_open: bool = False,
    ) -> None:
        self._raw = [a.copy() for a in (raw_outputs or [])]
        self._open = False
        self._fail_open = fail_open

    def open(self, cfg: DetectorConfig) -> None:
        if self._fail_open:
            raise InferenceError("mock: open failed (fail_open=True)")
        self._open = True

    def close(self) -> None:
        self._open = False

    def is_open(self) -> bool:
        return self._open

    def input_name(self) -> str:
        return "mock_input"

    def infer_raw(self, input_tensor: np.ndarray) -> List[np.ndarray]:
        if not self._open:
            raise InferenceError("backend not open")
        return [a.copy() for a in self._raw]

    def set_outputs(self, raw_outputs: List[np.ndarray]) -> None:
        self._raw = [a.copy() for a in raw_outputs]

    def describe(self) -> str:
        state = "open" if self._open else "closed"
        return f"mock backend [{state}] outputs={len(self._raw)}"
