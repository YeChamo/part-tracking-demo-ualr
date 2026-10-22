from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional

import numpy as np


class InferenceError(Exception):
    pass


@dataclass(frozen=True)
class Detection:
    xyxy: tuple[float, float, float, float]     # (x1, y1, x2, y2) in source-image pixel coords
    score: float                                 # confidence in [0, 1]
    class_id: int                                # 0-based class index
    label: str = ""                              # resolved class name (or "class_<id>")
    mask: Optional[np.ndarray] = None            # HxW uint8 binary mask, source-image sized (segmentation only)


@dataclass
class InferenceResult:
    detections: List[Detection] = field(default_factory=list)
    input_shape: Optional[tuple[int, int]] = None       # (H, W) of the source frame
    inference_ms: float = 0.0                           # backend-reported inference time
    preprocess_ms: float = 0.0
    postprocess_ms: float = 0.0

    @property
    def total_ms(self) -> float:
        return self.inference_ms + self.preprocess_ms + self.postprocess_ms
