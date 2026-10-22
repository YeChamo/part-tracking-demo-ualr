from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Literal, Optional


Device = Literal["auto", "cuda", "cpu", "tensorrt"]
PostProcessKind = Literal["yolox", "passthrough"]


@dataclass
class DetectorConfig:
    # ---- model ----
    model_path: str = ""                        # path to an .onnx file
    class_names: List[str] = field(default_factory=list)
    img_size: int = 640                         # square input side

    # ---- thresholds ----
    conf: float = 0.25                          # score floor applied post-decode
    nms_iou: float = 0.50                       # IoU threshold for NMS
    max_det: int = 300                          # cap final detections

    # ---- runtime ----
    device: Device = "auto"
    # Ordered list of ONNX Runtime execution providers to try.
    # None = auto (TensorRT → CUDA → CPU, whichever is present).
    providers: Optional[List[str]] = None

    # ---- preprocessing ----
    # YOLOX was trained with BGR input and no normalization — leave these alone
    # for YOLOX. Flip to True/values when running models that expect RGB or
    # mean/std-normalized inputs.
    input_is_rgb: bool = False
    mean: Optional[tuple[float, float, float]] = None   # per-channel mean (applied after /255 if normalize=True)
    std: Optional[tuple[float, float, float]] = None
    normalize: bool = False                     # divide by 255 before mean/std

    # ---- post-processing ----
    postprocess: PostProcessKind = "yolox"
    # YOLOX strides used during training / export. Leave as default for
    # stock YOLOX; override if you retrained with a custom FPN.
    yolox_strides: tuple[int, ...] = (8, 16, 32)

    # ---- threading ----
    intra_op_threads: int = 0                   # 0 = let ORT decide
    inter_op_threads: int = 0
