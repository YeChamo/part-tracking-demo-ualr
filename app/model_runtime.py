"""Metadata-aware YOLOX preprocessing and decoding, independent of devices.

Converted checkpoints declare their geometry and raw/decoded output format.
Older ONNX files retain the existing centered letterbox and decode heuristic.
The vendored inference package remains unchanged.
"""
from __future__ import annotations

import json
from collections.abc import Mapping
from numbers import Integral

import cv2
import numpy as np

from .vendor.inference import Detector, InferenceError
from .vendor.inference.postprocess.yolox import YOLOXPostProcessor


def _json_list(value, name):
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except ValueError:
            raise InferenceError(f"{name} metadata must be a JSON list.") from None
    if not isinstance(value, (tuple, list)):
        raise InferenceError(f"{name} metadata must be a list.")
    return value


def _positive_int(value, name):
    if isinstance(value, bool) or not isinstance(value, Integral) or value < 1:
        raise InferenceError(f"{name} must be a positive whole number.")
    return int(value)


def _dimension(value, name):
    if value is None or isinstance(value, str) and value.strip():
        return None
    return _positive_int(value, name)


class ModelPostProcessor(YOLOXPostProcessor):
    """Decode declared raw heads exactly once and verify their complete grid."""

    @staticmethod
    def _should_decode(out, img_size):
        # process() resolves explicit format / legacy heuristic before handing
        # decoded boxes to the unchanged vendored NMS/coordinate conversion.
        return False

    @staticmethod
    def _decode_raw(out, input_hw, strides):
        height, width = input_hw
        expected = sum((height // stride) * (width // stride) for stride in strides)
        if out.shape[0] != expected:
            raise InferenceError(f"YOLOX raw output has {out.shape[0]} anchors; input {height}x{width} and strides {strides} require {expected}.")
        decoded = out.copy()
        offset = 0
        try:
            with np.errstate(over="raise", invalid="raise"):
                for stride in strides:
                    grid_h, grid_w = height // stride, width // stride
                    count = grid_h * grid_w
                    ys, xs = np.meshgrid(np.arange(grid_h), np.arange(grid_w), indexing="ij")
                    grid = np.stack((xs.reshape(-1), ys.reshape(-1)), axis=1).astype(np.float32)
                    chunk = decoded[offset:offset + count]
                    chunk[:, :2] = (chunk[:, :2] + grid) * stride
                    chunk[:, 2:4] = np.exp(chunk[:, 2:4]) * stride
                    offset += count
        except FloatingPointError:
            raise InferenceError("YOLOX raw box decoding produced non-finite coordinates.") from None
        if not np.isfinite(decoded).all():
            raise InferenceError("YOLOX raw box decoding produced non-finite coordinates.")
        return decoded

    def process(self, raw_outputs, cfg, *, src_hw, letterbox_scale, letterbox_pad):
        if not raw_outputs:
            raise InferenceError("YOLOX model returned no detection output.")
        output = np.asarray(raw_outputs[0])
        if output.ndim != 3 or output.shape[0] != 1 or output.shape[2] <= 5:
            raise InferenceError(f"Expected YOLOX output [1, N, 5+C]; got {output.shape}.")
        if not np.issubdtype(output.dtype, np.floating) or not np.isfinite(output).all():
            raise InferenceError("YOLOX output must contain finite floating-point values.")
        try:
            with np.errstate(over="raise", invalid="raise"):
                output = output.astype(np.float32, copy=False)
        except FloatingPointError:
            raise InferenceError("YOLOX output cannot be represented as finite FP32 values.") from None
        mode = getattr(cfg, "yolox_decode", "auto")
        if mode not in ("auto", "raw", "decoded"):
            raise InferenceError("YOLOX decode format must be raw, decoded, or auto.")
        raw = mode == "raw" or (mode == "auto" and YOLOXPostProcessor._should_decode(output[0], int(cfg.img_size)))
        if raw:
            input_hw = tuple(getattr(cfg, "input_hw", (int(cfg.img_size), int(cfg.img_size))))
            output = self._decode_raw(output[0], input_hw, tuple(cfg.yolox_strides))[None]
        return super().process([output], cfg, src_hw=src_hw,
                               letterbox_scale=letterbox_scale, letterbox_pad=letterbox_pad)


class ModelDetector(Detector):
    """Detector with explicit model metadata and rectangular input support."""

    def __init__(self, cfg, *, backend=None, postprocessor=None):
        super().__init__(cfg, backend=backend,
                         postprocessor=ModelPostProcessor() if postprocessor is None else postprocessor)

    def configure_model(self, metadata, input_shape):
        if metadata is None:
            metadata = {}
        if not isinstance(metadata, Mapping):
            raise InferenceError("YOLOX metadata must be an object.")
        if not isinstance(input_shape, (tuple, list)) or len(input_shape) != 4:
            raise InferenceError("YOLOX input must have shape [1, 3, height, width].")
        batch = _dimension(input_shape[0], "YOLOX input batch")
        if batch not in (None, 1) or _dimension(input_shape[1], "YOLOX input channels") != 3:
            raise InferenceError("YOLOX input must have batch size 1 and three channels.")
        graph_hw = [_dimension(value, "YOLOX input size") for value in input_shape[2:]]
        configured = getattr(self._cfg, "input_hw", (int(self._cfg.img_size), int(self._cfg.img_size)))
        declared = metadata.get("input_size", metadata.get("test_size"))
        if declared is not None:
            declared = _json_list(declared, "YOLOX input_size")
            if len(declared) != 2:
                raise InferenceError("YOLOX input_size must contain height and width.")
            configured = tuple(_positive_int(value, "YOLOX input size") for value in declared)
            if any(actual is not None and actual != expected for actual, expected in zip(graph_hw, configured)):
                raise InferenceError("YOLOX input_size metadata disagrees with the model input shape.")
        if not isinstance(configured, (tuple, list)) or len(configured) != 2:
            raise InferenceError("YOLOX input size must contain height and width.")
        configured = tuple(_positive_int(value, "YOLOX input size") for value in configured)
        input_hw = tuple(actual if actual is not None else fallback for actual, fallback in zip(graph_hw, configured))
        strides = metadata.get("yolox_strides", self._cfg.yolox_strides)
        strides = tuple(_positive_int(value, "YOLOX stride") for value in _json_list(strides, "YOLOX strides"))
        if not strides:
            raise InferenceError("YOLOX strides must not be empty.")
        decode = str(metadata.get("yolox_decode", "auto")).strip().lower()
        if decode not in ("raw", "decoded", "auto"):
            raise InferenceError("YOLOX yolox_decode metadata must be raw or decoded.")
        letterbox = str(metadata.get("letterbox", metadata.get("yolox_letterbox", "center"))).strip().lower()
        if letterbox not in ("top_left", "center"):
            raise InferenceError("YOLOX letterbox metadata must be top_left or center.")
        self._cfg.input_hw = input_hw
        self._cfg.img_size = max(input_hw)
        self._cfg.yolox_strides = strides
        self._cfg.yolox_decode = decode
        self._cfg.letterbox = letterbox

    def _preprocess(self, bgr):
        cfg = self._cfg
        target_h, target_w = getattr(cfg, "input_hw", (int(cfg.img_size), int(cfg.img_size)))
        height, width = bgr.shape[:2]
        scale = min(target_w / width, target_h / height)
        top_left = getattr(cfg, "letterbox", "center") == "top_left"
        if top_left:
            resized_w, resized_h = max(1, int(width * scale)), max(1, int(height * scale))
            pad_x = pad_y = 0
        else:
            resized_w, resized_h = max(1, int(round(width * scale))), max(1, int(round(height * scale)))
            pad_x, pad_y = (target_w - resized_w) // 2, (target_h - resized_h) // 2
        canvas = np.full((target_h, target_w, 3), 114, dtype=np.uint8)
        canvas[pad_y:pad_y + resized_h, pad_x:pad_x + resized_w] = cv2.resize(
            bgr, (resized_w, resized_h), interpolation=cv2.INTER_LINEAR)
        if cfg.input_is_rgb:
            canvas = cv2.cvtColor(canvas, cv2.COLOR_BGR2RGB)
        tensor = canvas.astype(np.float32)
        if cfg.normalize:
            tensor /= 255.0
        if cfg.mean is not None:
            tensor -= np.asarray(cfg.mean, dtype=np.float32)
        if cfg.std is not None:
            tensor /= np.asarray(cfg.std, dtype=np.float32)
        return np.ascontiguousarray(tensor.transpose(2, 0, 1)[None]), float(scale), (pad_x, pad_y)
