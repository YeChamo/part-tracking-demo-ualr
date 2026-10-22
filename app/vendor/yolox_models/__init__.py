"""Self-contained stock YOLOX inference graphs, adapted from Megvii YOLOX.

Import this optional package only when preparing a native Torch checkpoint.
Camera inference uses the resulting ONNX model and needs no training modules.
See LICENSE and NOTICE for the upstream license and modification details.
"""
from __future__ import annotations

import math
from numbers import Integral, Real

import torch
from torch import nn

from .yolo_head import YOLOXHead
from .yolo_pafpn import YOLOPAFPN
from .yolox import YOLOX


def build_model(num_classes, depth, width, depthwise=False, act="silu",
                bn_eps=.001, bn_momentum=.03):
    """Build a CPU/FP32 inference-only YOLOX with standard state-dict names.

    The caller must admit complete trained weights before using/exporting it.
    Outputs are RAW ``[batch, anchors, 5 + classes]``: grid-relative x/y,
    log-width/height, then sigmoid objectness and class probabilities.
    """
    if isinstance(num_classes, bool) or not isinstance(num_classes, Integral) or num_classes < 1:
        raise ValueError("YOLOX num_classes must be a positive integer.")
    for name, value in (("depth", depth), ("width", width), ("bn_eps", bn_eps)):
        if isinstance(value, bool) or not isinstance(value, Real) or not math.isfinite(value) or value <= 0:
            raise ValueError(f"YOLOX {name} must be finite and positive.")
    if int(64 * width) < 1:
        raise ValueError("YOLOX width must create positive channel counts.")
    if type(depthwise) is not bool:
        raise ValueError("YOLOX depthwise must be a boolean.")
    if act not in ("silu", "relu", "lrelu"):
        raise ValueError("YOLOX activation must be silu, relu, or lrelu.")
    if bn_momentum is not None and (isinstance(bn_momentum, bool)
            or not isinstance(bn_momentum, Real) or not math.isfinite(bn_momentum)
            or not 0 <= bn_momentum <= 1):
        raise ValueError("YOLOX BatchNorm momentum must be None or between 0 and 1.")
    with torch.device("cpu"):
        model = YOLOX(
            YOLOPAFPN(float(depth), float(width), depthwise=depthwise, act=act),
            YOLOXHead(int(num_classes), float(width), depthwise=depthwise, act=act),
        )
    for module in model.modules():
        if isinstance(module, nn.BatchNorm2d):
            module.eps = float(bn_eps)
            module.momentum = bn_momentum
    return model.float().cpu().eval()


__all__ = ["build_model"]
