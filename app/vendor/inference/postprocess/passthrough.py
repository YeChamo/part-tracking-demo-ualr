from __future__ import annotations

from typing import List

import numpy as np

from ..config import DetectorConfig
from ..types import Detection, InferenceError
from .base import PostProcessor
from .nms import nms_per_class


class PassthroughPostProcessor(PostProcessor):
    """For ONNX models that already emit final detections.

    Expects three output tensors in this order:
      boxes  : (N, 4) xyxy in model-input-image pixel coords
      scores : (N,)   float
      classes: (N,)   int  (0-based)

    This matches common torchvision detection ONNX exports (Mask R-CNN / Faster
    R-CNN) and YOLOX exports where decode + NMS were baked into the graph.
    NMS is re-applied in case the model skipped it.
    """

    def process(
        self,
        raw_outputs: List[np.ndarray],
        cfg: DetectorConfig,
        *,
        src_hw: tuple[int, int],
        letterbox_scale: float,
        letterbox_pad: tuple[int, int],
    ) -> List[Detection]:
        if len(raw_outputs) < 3:
            raise InferenceError(
                "passthrough expects [boxes, scores, classes]; "
                f"got {len(raw_outputs)} output tensor(s)"
            )
        boxes = np.asarray(raw_outputs[0], dtype=np.float32).reshape(-1, 4)
        scores = np.asarray(raw_outputs[1], dtype=np.float32).reshape(-1)
        classes = np.asarray(raw_outputs[2], dtype=np.int64).reshape(-1)
        if not (boxes.shape[0] == scores.shape[0] == classes.shape[0]):
            raise InferenceError(
                f"passthrough shape mismatch: boxes={boxes.shape}, "
                f"scores={scores.shape}, classes={classes.shape}"
            )
        if boxes.shape[0] == 0:
            return []

        mask = scores >= float(cfg.conf)
        if not mask.any():
            return []
        boxes = boxes[mask]
        scores = scores[mask]
        classes = classes[mask]

        # Undo letterbox
        pad_x, pad_y = letterbox_pad
        boxes[:, [0, 2]] -= pad_x
        boxes[:, [1, 3]] -= pad_y
        boxes /= max(1e-6, float(letterbox_scale))

        h, w = src_hw
        boxes[:, 0::2] = np.clip(boxes[:, 0::2], 0, w - 1)
        boxes[:, 1::2] = np.clip(boxes[:, 1::2], 0, h - 1)

        keep = nms_per_class(boxes, scores, classes, float(cfg.nms_iou))
        if keep.size == 0:
            return []
        if keep.size > int(cfg.max_det):
            keep = keep[: int(cfg.max_det)]

        out: List[Detection] = []
        for i in keep:
            cid = int(classes[i])
            label = cfg.class_names[cid] if 0 <= cid < len(cfg.class_names) else f"class_{cid}"
            out.append(
                Detection(
                    xyxy=(float(boxes[i, 0]), float(boxes[i, 1]), float(boxes[i, 2]), float(boxes[i, 3])),
                    score=float(scores[i]),
                    class_id=cid,
                    label=label,
                )
            )
        return out
