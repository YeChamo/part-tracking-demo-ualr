from __future__ import annotations

import time
from typing import List, Optional, Tuple

import numpy as np

from .backends import InferenceBackend, make_backend
from .config import DetectorConfig
from .postprocess import PostProcessor, make_postprocessor
from .types import Detection, InferenceError, InferenceResult


class Detector:
    """One ONNX detection model, wrapped in pre/post-process pipeline.

    Usage:
        cfg = DetectorConfig(model_path="yolox.onnx",
                             class_names=["a", "b"],
                             img_size=640, conf=0.25, nms_iou=0.5)
        with Detector(cfg) as det:
            result = det.infer(bgr_frame)
            for d in result.detections:
                print(d.label, d.score, d.xyxy)
            annotated = det.draw(bgr_frame, result)
    """

    def __init__(
        self,
        cfg: DetectorConfig,
        *,
        backend: Optional[InferenceBackend] = None,
        postprocessor: Optional[PostProcessor] = None,
    ) -> None:
        self._cfg = cfg
        self._backend = backend if backend is not None else make_backend("onnx")
        self._post = postprocessor if postprocessor is not None else make_postprocessor(cfg.postprocess)

    # ------------------------------------------------------------------ lifecycle

    def open(self) -> None:
        if not self._backend.is_open():
            self._backend.open(self._cfg)

    def close(self) -> None:
        if self._backend.is_open():
            self._backend.close()

    def is_open(self) -> bool:
        return self._backend.is_open()

    def describe(self) -> str:
        return self._backend.describe()

    def __enter__(self) -> "Detector":
        self.open()
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()

    # ------------------------------------------------------------------ main API

    def infer(self, bgr: np.ndarray) -> InferenceResult:
        if bgr is None or bgr.size == 0:
            raise InferenceError("empty input frame")
        if bgr.ndim != 3 or bgr.shape[2] != 3:
            raise InferenceError(f"expected HxWx3 BGR frame; got shape {bgr.shape}")
        if not self._backend.is_open():
            self.open()

        src_hw = (int(bgr.shape[0]), int(bgr.shape[1]))

        t0 = time.perf_counter()
        tensor, scale, pad = self._preprocess(bgr)
        t1 = time.perf_counter()
        raw_outputs = self._backend.infer_raw(tensor)
        t2 = time.perf_counter()
        detections = self._post.process(
            raw_outputs,
            self._cfg,
            src_hw=src_hw,
            letterbox_scale=scale,
            letterbox_pad=pad,
        )
        t3 = time.perf_counter()

        return InferenceResult(
            detections=detections,
            input_shape=src_hw,
            preprocess_ms=(t1 - t0) * 1000.0,
            inference_ms=(t2 - t1) * 1000.0,
            postprocess_ms=(t3 - t2) * 1000.0,
        )

    # ------------------------------------------------------------------ helpers

    def _preprocess(self, bgr: np.ndarray) -> Tuple[np.ndarray, float, Tuple[int, int]]:
        """Letterbox to a square cfg.img_size, normalize per cfg, return NCHW
        float32 tensor plus the scale factor and padding (for post-process)."""
        import cv2

        cfg = self._cfg
        target = int(cfg.img_size)
        h, w = bgr.shape[:2]
        scale = min(target / w, target / h)
        nw, nh = int(round(w * scale)), int(round(h * scale))
        resized = cv2.resize(bgr, (nw, nh), interpolation=cv2.INTER_LINEAR)

        canvas = np.full((target, target, 3), 114, dtype=np.uint8)
        pad_x = (target - nw) // 2
        pad_y = (target - nh) // 2
        canvas[pad_y : pad_y + nh, pad_x : pad_x + nw] = resized

        if cfg.input_is_rgb:
            canvas = cv2.cvtColor(canvas, cv2.COLOR_BGR2RGB)

        tensor = canvas.astype(np.float32)
        if cfg.normalize:
            tensor /= 255.0
        if cfg.mean is not None:
            tensor -= np.array(cfg.mean, dtype=np.float32)
        if cfg.std is not None:
            tensor /= np.array(cfg.std, dtype=np.float32)

        tensor = np.transpose(tensor, (2, 0, 1))          # HWC -> CHW
        tensor = np.expand_dims(tensor, 0)                # add batch dim
        tensor = np.ascontiguousarray(tensor)
        return tensor, float(scale), (int(pad_x), int(pad_y))

    # ------------------------------------------------------------------ drawing

    @staticmethod
    def draw(
        bgr: np.ndarray,
        result: InferenceResult,
        *,
        thickness: int = 2,
        show_label: bool = True,
    ) -> np.ndarray:
        """Draw detections onto a copy of the frame. BGR in, BGR out."""
        import cv2

        canvas = bgr.copy()
        for d in result.detections:
            color = _color_for_class(d.class_id)
            x1, y1, x2, y2 = [int(round(v)) for v in d.xyxy]
            cv2.rectangle(canvas, (x1, y1), (x2, y2), color, thickness)
            if show_label and d.label:
                text = f"{d.label} {d.score:.2f}"
                (tw, th), _ = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)
                ty = max(th + 4, y1 - 4)
                cv2.rectangle(canvas, (x1, ty - th - 4), (x1 + tw + 4, ty), color, -1)
                cv2.putText(canvas, text, (x1 + 2, ty - 2),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1, cv2.LINE_AA)
        return canvas


# Deterministic per-class color palette (BGR).
_PALETTE = [
    (60, 200, 60), (60, 60, 220), (0, 165, 255), (230, 110, 30),
    (180, 30, 200), (60, 200, 200), (200, 200, 60), (120, 80, 30),
    (30, 120, 200), (200, 60, 120),
]


def _color_for_class(class_id: int) -> Tuple[int, int, int]:
    return _PALETTE[int(class_id) % len(_PALETTE)]
