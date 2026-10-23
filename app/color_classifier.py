"""Small, trained color neural network; see models/color/MODEL_CARD.md.

This general color model was trained on procedural garments, not bottles.
Preprocessing adapts the author's MIT-licensed compose_input implementation.
No pixel thresholds or hand-written color classifier are used.
"""
from pathlib import Path

import cv2
import numpy as np


COLOR_NAMES = ("red", "orange", "yellow", "green", "blue", "violet", "purple",
               "white", "gray", "black", "pink", "brown", "olive")
_MEAN = np.array([.485, .456, .406], dtype=np.float32).reshape(3, 1, 1)
_STD = np.array([.229, .224, .225], dtype=np.float32).reshape(3, 1, 1)


def _square(cx, cy, half, width, height):
    x1, y1 = max(0, cx-half), max(0, cy-half)
    x2, y2 = min(width, cx+half), min(height, cy+half)
    side = min(x2-x1, y2-y1)
    x1 = max(0, min(x1, width-side))
    y1 = max(0, min(y1, height-side))
    return int(x1), int(y1), int(x1+side), int(y1+side)


def prepare_input(crop):
    """Reproduce the trained 112-in-224 composite for an already selected ROI."""
    if (not isinstance(crop, np.ndarray) or crop.dtype != np.uint8
            or crop.ndim != 3 or crop.shape[2] != 3 or min(crop.shape[:2]) < 2):
        raise ValueError("Color model needs a nonempty BGR uint8 image crop.")
    height, width = crop.shape[:2]
    inner_side = max(min(width, height), 10)
    x1, y1, x2, y2 = _square(width//2, height//2, inner_side//2, width, height)
    inner = cv2.resize(crop[y1:y2, x1:x2], (112, 112), interpolation=cv2.INTER_AREA)
    outer_side = max(int(max(width, height)*2), inner_side+20)
    x1, y1, x2, y2 = _square(width//2, height//2, outer_side//2, width, height)
    composite = cv2.resize(crop[y1:y2, x1:x2], (224, 224), interpolation=cv2.INTER_AREA)
    composite[56:168, 56:168] = inner
    rgb = cv2.cvtColor(composite, cv2.COLOR_BGR2RGB).astype(np.float32)/255.0
    return np.ascontiguousarray(((rgb.transpose(2, 0, 1)-_MEAN)/_STD)[None])


class ColorClassifier:
    """ONNX CPU adapter; caller applies confidence and routing policy."""
    names = COLOR_NAMES
    input_shape = (1, 3, 224, 224)
    # The pipeline applies this inner-body selection exactly once per bottle.
    bottle_crop = (.20, .18, .80, .35)

    def __init__(self, path):
        self.path = Path(path)
        self._session = None
        self._input_name = None

    def open(self):
        import onnxruntime as ort
        if not self.path.is_file():
            raise ValueError(f"Color neural network was not found: {self.path}")
        options = ort.SessionOptions()
        options.intra_op_num_threads = 2
        options.inter_op_num_threads = 1
        session = ort.InferenceSession(str(self.path), sess_options=options,
                                       providers=["CPUExecutionProvider"])
        inputs, outputs = session.get_inputs(), session.get_outputs()
        if (len(inputs) != 1 or len(outputs) != 1 or inputs[0].type != "tensor(float)"
                or list(inputs[0].shape)[1:] != [3, 224, 224]
                or len(outputs[0].shape) != 2 or outputs[0].shape[-1] != len(self.names)):
            raise ValueError("Choose the bundled 13-color MobileNet ONNX model (224 x 224 input).")
        logits = session.run(None, {inputs[0].name: prepare_input(np.full((16, 16, 3), 127, np.uint8))})[0]
        self._probabilities(logits)
        self._session, self._input_name = session, inputs[0].name
        return self

    @staticmethod
    def _probabilities(logits):
        logits = np.asarray(logits, dtype=np.float32)
        if logits.shape != (1, len(COLOR_NAMES)) or not np.isfinite(logits).all():
            raise ValueError("Color model returned invalid color logits.")
        exponent = np.exp(logits[0]-float(logits.max()))
        return exponent/exponent.sum()

    def infer(self, crop):
        if self._session is None:
            raise RuntimeError("Open the color neural network before inference.")
        logits = self._session.run(None, {self._input_name: prepare_input(crop)})[0]
        probabilities = self._probabilities(logits)
        index = int(probabilities.argmax())
        return self.names[index], float(probabilities[index])

    def close(self):
        self._session = None
        self._input_name = None
