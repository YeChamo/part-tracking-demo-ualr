from __future__ import annotations

from typing import List

import numpy as np

from ..config import DetectorConfig
from ..types import Detection, InferenceError
from .base import PostProcessor
from .nms import nms_per_class


class YOLOXPostProcessor(PostProcessor):
    """Decodes YOLOX-style outputs and returns Detection objects.

    Accepts both common YOLOX ONNX export shapes:

    A) Raw logits (decode NOT baked into graph):
         output shape: (1, num_anchors, 5 + num_classes)
         where num_anchors = sum(grid_h_s * grid_w_s for stride s in cfg.yolox_strides)
         values per anchor: [cx_s, cy_s, log_w, log_h, obj, *cls_scores]
         (cx_s, cy_s in stride-grid units; log_w, log_h are log-box-size)

    B) Decoded boxes (decode baked in):
         output shape: (1, num_anchors, 5 + num_classes)
         values per anchor: [cx_px, cy_px, w_px, h_px, obj, *cls_scores]
         We detect this by checking the range of cx/cy against img_size.
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
        if not raw_outputs:
            return []
        out = raw_outputs[0]
        if out.ndim != 3:
            raise InferenceError(
                f"expected YOLOX output shape (1, N, 5+C); got {out.shape}"
            )
        out = out[0]  # (N, 5+C)
        num_classes = out.shape[1] - 5
        if num_classes <= 0:
            raise InferenceError(f"YOLOX output has no class channels: {out.shape}")

        img_size = int(cfg.img_size)
        need_decode = self._should_decode(out, img_size)
        if need_decode:
            decoded = self._decode_strided(out, img_size, tuple(cfg.yolox_strides))
        else:
            decoded = out.copy()
            # already in pixel coords — just copy

        # decoded columns: [cx, cy, w, h, obj, *cls]
        cxcy = decoded[:, 0:2]
        wh = decoded[:, 2:4]
        obj = decoded[:, 4:5]
        cls_scores = decoded[:, 5:]

        # per-anchor best class + combined score
        class_ids = cls_scores.argmax(axis=1)
        top_cls = cls_scores[np.arange(cls_scores.shape[0]), class_ids]
        scores = (obj.squeeze(-1) * top_cls).astype(np.float32)

        conf_mask = scores >= float(cfg.conf)
        if not conf_mask.any():
            return []

        cxcy = cxcy[conf_mask]
        wh = wh[conf_mask]
        scores = scores[conf_mask]
        class_ids = class_ids[conf_mask]

        # cxcywh (pixels in letterboxed space) -> xyxy
        boxes = np.empty((cxcy.shape[0], 4), dtype=np.float32)
        boxes[:, 0] = cxcy[:, 0] - wh[:, 0] / 2.0
        boxes[:, 1] = cxcy[:, 1] - wh[:, 1] / 2.0
        boxes[:, 2] = cxcy[:, 0] + wh[:, 0] / 2.0
        boxes[:, 3] = cxcy[:, 1] + wh[:, 1] / 2.0

        # Undo letterbox: subtract pad, divide by scale
        pad_x, pad_y = letterbox_pad
        boxes[:, [0, 2]] -= pad_x
        boxes[:, [1, 3]] -= pad_y
        boxes /= max(1e-6, float(letterbox_scale))

        # Clip to source image
        h, w = src_hw
        boxes[:, 0::2] = np.clip(boxes[:, 0::2], 0, w - 1)
        boxes[:, 1::2] = np.clip(boxes[:, 1::2], 0, h - 1)

        keep = nms_per_class(boxes, scores, class_ids, float(cfg.nms_iou))
        if keep.size == 0:
            return []

        if keep.size > int(cfg.max_det):
            # Already sorted by score in nms_per_class; truncate
            keep = keep[: int(cfg.max_det)]

        out_detections: List[Detection] = []
        for i in keep:
            cid = int(class_ids[i])
            label = cfg.class_names[cid] if 0 <= cid < len(cfg.class_names) else f"class_{cid}"
            out_detections.append(
                Detection(
                    xyxy=(float(boxes[i, 0]), float(boxes[i, 1]), float(boxes[i, 2]), float(boxes[i, 3])),
                    score=float(scores[i]),
                    class_id=cid,
                    label=label,
                )
            )
        return out_detections

    # ------------------------------------------------------------------ decode

    @staticmethod
    def _should_decode(out: np.ndarray, img_size: int) -> bool:
        """Heuristic: if cx/cy values look like grid coords (small integers) the
        model didn't decode; if they look like pixel coords (spread 0..img_size)
        the model did."""
        cx = out[:, 0]
        cy = out[:, 1]
        max_cx = float(cx.max()) if cx.size else 0.0
        max_cy = float(cy.max()) if cy.size else 0.0
        # Decoded pixel coords reach close to img_size. Raw grid coords for the
        # coarsest stride (32) on a 640 input reach at most ~20.
        grid_ceiling = img_size / 16.0
        return max_cx < grid_ceiling and max_cy < grid_ceiling

    @staticmethod
    def _decode_strided(
        out: np.ndarray,
        img_size: int,
        strides: tuple[int, ...],
    ) -> np.ndarray:
        """Apply YOLOX grid-cell decoding. Modifies a copy of `out`.

        For each stride s:
          grid_h, grid_w = img_size // s
          num_anchors_at_s = grid_h * grid_w
          cx_px = (cx_grid + grid_x) * s
          cy_px = (cy_grid + grid_y) * s
          w_px = exp(log_w) * s
          h_px = exp(log_h) * s
        """
        decoded = out.copy()
        idx = 0
        for s in strides:
            gh = img_size // s
            gw = img_size // s
            n = gh * gw
            if idx + n > decoded.shape[0]:
                # Output doesn't match expected anchor count — stop early;
                # leaves remaining rows untouched (they'll likely fail the conf
                # threshold). This is safer than raising on retrained models.
                break
            chunk = decoded[idx : idx + n]
            ys, xs = np.meshgrid(np.arange(gh), np.arange(gw), indexing="ij")
            grid = np.stack([xs.reshape(-1), ys.reshape(-1)], axis=1).astype(np.float32)
            chunk[:, 0:2] = (chunk[:, 0:2] + grid) * float(s)
            chunk[:, 2:4] = np.exp(chunk[:, 2:4]) * float(s)
            decoded[idx : idx + n] = chunk
            idx += n
        return decoded
