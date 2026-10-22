from __future__ import annotations

from typing import Any

from .base import InferenceBackend
from .mock_backend import MockBackend


def make_backend(kind: str, **kwargs: Any) -> InferenceBackend:
    """Build an inference backend by name. Lazy-imports optional libraries."""
    k = str(kind).strip().lower()
    if k == "onnx":
        from .onnx_backend import ONNXBackend
        return ONNXBackend(**kwargs)
    if k == "mock":
        return MockBackend(**kwargs)
    raise ValueError(f"unknown inference backend: {kind!r} (expected 'onnx' or 'mock')")


__all__ = ["InferenceBackend", "MockBackend", "make_backend"]
