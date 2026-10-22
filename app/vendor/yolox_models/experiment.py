"""A small inference-only base for explicitly selected custom experiments.

Self-contained experiment files can import ``ExportExp`` instead of the YOLOX
training package. Override the graph fields or ``get_model`` to describe the
actual checkpoint. Dataset/trainer/augmentation APIs are intentionally absent.
"""
from __future__ import annotations

from . import build_model


class ExportExp:
    def __init__(self):
        self.num_classes = 80
        self.depth = 1.0
        self.width = 1.0
        self.depthwise = False
        self.act = "silu"
        self.bn_eps = .001
        self.bn_momentum = .03
        self.input_size = (640, 640)
        self.test_size = (640, 640)
        self.model = None

    def get_model(self, sublinear=False):
        if self.model is None:
            self.model = build_model(self.num_classes, self.depth, self.width,
                                     depthwise=self.depthwise, act=self.act,
                                     bn_eps=self.bn_eps, bn_momentum=self.bn_momentum)
        return self.model


Exp = ExportExp
