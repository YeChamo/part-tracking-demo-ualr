from __future__ import annotations

from typing import Any

from .base import PostProcessor
from .passthrough import PassthroughPostProcessor
from .yolox import YOLOXPostProcessor


def make_postprocessor(kind: str, **kwargs: Any) -> PostProcessor:
    k = str(kind).strip().lower()
    if k == "yolox":
        return YOLOXPostProcessor(**kwargs)
    if k == "passthrough":
        return PassthroughPostProcessor(**kwargs)
    raise ValueError(f"unknown post-processor: {kind!r} (expected 'yolox' or 'passthrough')")


__all__ = [
    "PostProcessor",
    "YOLOXPostProcessor",
    "PassthroughPostProcessor",
    "make_postprocessor",
]
