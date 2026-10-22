from __future__ import annotations

from abc import ABC, abstractmethod
from typing import List

import numpy as np

from ..config import DetectorConfig
from ..types import Detection


class PostProcessor(ABC):
    """Turns raw model outputs into Detection objects in source-image coords.

    Implementations must honor:
      - the confidence floor (cfg.conf)
      - NMS (cfg.nms_iou) if the model doesn't do its own
      - max-detection cap (cfg.max_det)
      - letterbox scale factor passed at call time
    """

    @abstractmethod
    def process(
        self,
        raw_outputs: List[np.ndarray],
        cfg: DetectorConfig,
        *,
        src_hw: tuple[int, int],                # (H, W) of the original source image
        letterbox_scale: float,                 # factor used in preprocessing
        letterbox_pad: tuple[int, int],         # (pad_left, pad_top)
    ) -> List[Detection]: ...
