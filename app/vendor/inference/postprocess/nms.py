from __future__ import annotations

import numpy as np


def nms_numpy(boxes: np.ndarray, scores: np.ndarray, iou_thresh: float) -> np.ndarray:
    """Class-agnostic NMS. Pure numpy — no torch/torchvision.

    boxes: (N, 4) xyxy float
    scores: (N,) float
    Returns: indices of kept boxes, sorted by descending score.
    """
    if boxes.size == 0:
        return np.empty((0,), dtype=np.int64)

    x1 = boxes[:, 0]
    y1 = boxes[:, 1]
    x2 = boxes[:, 2]
    y2 = boxes[:, 3]
    areas = np.clip(x2 - x1, 0, None) * np.clip(y2 - y1, 0, None)

    order = scores.argsort()[::-1]
    keep: list[int] = []
    while order.size > 0:
        i = int(order[0])
        keep.append(i)
        if order.size == 1:
            break
        rest = order[1:]

        xx1 = np.maximum(x1[i], x1[rest])
        yy1 = np.maximum(y1[i], y1[rest])
        xx2 = np.minimum(x2[i], x2[rest])
        yy2 = np.minimum(y2[i], y2[rest])

        w = np.clip(xx2 - xx1, 0, None)
        h = np.clip(yy2 - yy1, 0, None)
        inter = w * h
        union = areas[i] + areas[rest] - inter
        iou = np.where(union > 0, inter / union, 0.0)

        order = rest[iou <= iou_thresh]

    return np.asarray(keep, dtype=np.int64)


def nms_per_class(
    boxes: np.ndarray,
    scores: np.ndarray,
    classes: np.ndarray,
    iou_thresh: float,
) -> np.ndarray:
    """Run NMS separately per class. Returns indices into the input arrays."""
    if boxes.size == 0:
        return np.empty((0,), dtype=np.int64)
    keep_all: list[int] = []
    for cls in np.unique(classes):
        mask = classes == cls
        if not mask.any():
            continue
        idxs = np.where(mask)[0]
        kept_local = nms_numpy(boxes[idxs], scores[idxs], iou_thresh)
        keep_all.extend(idxs[kept_local].tolist())
    # Sort by score descending at the end
    keep_all.sort(key=lambda i: -scores[i])
    return np.asarray(keep_all, dtype=np.int64)
