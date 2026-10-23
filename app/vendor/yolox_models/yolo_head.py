# Copyright (c) Megvii Inc. All rights reserved.
# Licensed under Apache-2.0; see LICENSE in this directory.
# Modified for Part Tracking Demo UALR (2026): inference-only head; removed
# training losses, assignment, visualization, and optional training imports.
"""Stock YOLOX detection head with checkpoint-compatible parameter names."""
from __future__ import annotations

import torch
from torch import nn

from .network_blocks import BaseConv, DWConv


class YOLOXHead(nn.Module):
    def __init__(self, num_classes, width=1.0, in_channels=(256, 512, 1024),
                 act="silu", depthwise=False):
        super().__init__()
        self.num_classes = num_classes
        self.strides = (8, 16, 32)
        self.decode_in_inference = False
        self.cls_convs = nn.ModuleList()
        self.reg_convs = nn.ModuleList()
        self.cls_preds = nn.ModuleList()
        self.reg_preds = nn.ModuleList()
        self.obj_preds = nn.ModuleList()
        self.stems = nn.ModuleList()
        conv = DWConv if depthwise else BaseConv
        channels = int(256 * width)
        for source_channels in in_channels:
            self.stems.append(BaseConv(int(source_channels * width), channels, 1, 1, act=act))
            self.cls_convs.append(nn.Sequential(
                conv(channels, channels, 3, 1, act=act),
                conv(channels, channels, 3, 1, act=act),
            ))
            self.reg_convs.append(nn.Sequential(
                conv(channels, channels, 3, 1, act=act),
                conv(channels, channels, 3, 1, act=act),
            ))
            self.cls_preds.append(nn.Conv2d(channels, num_classes, 1, 1, 0))
            self.reg_preds.append(nn.Conv2d(channels, 4, 1, 1, 0))
            self.obj_preds.append(nn.Conv2d(channels, 1, 1, 1, 0))

    def forward(self, features):
        if self.training:
            raise RuntimeError("This vendored YOLOX graph supports inference only; call eval().")
        if self.decode_in_inference:
            raise RuntimeError("This YOLOX export must keep decode_in_inference=False.")
        outputs = []
        for index, feature in enumerate(features):
            feature = self.stems[index](feature)
            cls_feature = self.cls_convs[index](feature)
            reg_feature = self.reg_convs[index](feature)
            # Coordinates remain grid offsets / log-size. Only the objectness
            # and class channels are probabilities, exactly as an upstream
            # YOLOX export with decode_in_inference=False.
            output = torch.cat((self.reg_preds[index](reg_feature),
                                self.obj_preds[index](reg_feature).sigmoid(),
                                self.cls_preds[index](cls_feature).sigmoid()), dim=1)
            outputs.append(output.flatten(start_dim=2))
        return torch.cat(outputs, dim=2).permute(0, 2, 1)
