from __future__ import annotations

from abc import ABC, abstractmethod
from typing import List

import numpy as np

from ..config import DetectorConfig


class InferenceBackend(ABC):
    """Single-model inference transport. Synchronous, single-threaded by contract.

    The Detector handles pre/post-processing and threading. Backends only:
      - load the model
      - accept a preprocessed input tensor
      - return raw output tensors
    """

    @abstractmethod
    def open(self, cfg: DetectorConfig) -> None: ...

    @abstractmethod
    def close(self) -> None: ...

    @abstractmethod
    def is_open(self) -> bool: ...

    @abstractmethod
    def infer_raw(self, input_tensor: np.ndarray) -> List[np.ndarray]:
        """Run one forward pass.

        input_tensor shape: (N, C, H, W) float32
        Returns: list of output tensors as raw numpy arrays (one per ONNX output).
        """

    @abstractmethod
    def input_name(self) -> str: ...

    @abstractmethod
    def describe(self) -> str: ...
