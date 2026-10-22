# Copyright (c) Megvii Inc. All rights reserved.
# Licensed under Apache-2.0; see LICENSE in this directory.
# Modified for Part Tracking Demo UALR (2026): inference-only model wrapper;
# removed training and assignment visualization entry points.
"""Stock YOLOX backbone/head composition for inference and ONNX export."""
from torch import nn


class YOLOX(nn.Module):
    def __init__(self, backbone, head):
        super().__init__()
        self.backbone = backbone
        self.head = head

    def forward(self, images):
        return self.head(self.backbone(images))
