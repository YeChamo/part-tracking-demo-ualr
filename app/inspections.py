"""Visible cap and label inspections for the pictured orange-cap bottles.

Absence of evidence is kept separate from a missing-cap verdict when the top
of a bottle is clipped. OCR text is evidence, not an invented product class.
"""
from __future__ import annotations

import re
from typing import Sequence

import cv2
import numpy as np


def inspect_orange_cap(frame: np.ndarray, bbox: Sequence[float]) -> dict:
    """Check the orange closure in the upper 18% of a visible bottle box."""
    height, width = frame.shape[:2]
    x1, y1, x2, y2 = (int(round(float(v))) for v in bbox)
    x1, y1, x2, y2 = max(0, x1), max(0, y1), min(width, x2), min(height, y2)
    bw, bh = x2-x1, y2-y1
    roi = (x1+int(.15*bw), y1, x2-int(.15*bw), y1+int(.18*bh))
    result = {'status':'unknown', 'confidence':0.0, 'roi':roi}
    if bw < 35 or bh < 80 or y1 <= .015*height:
        return result
    patch = frame[roi[1]:roi[3],roi[0]:roi[2]]
    if patch.size == 0 or min(patch.shape[:2]) < 12:
        return result
    hue, saturation, value = cv2.split(cv2.cvtColor(patch, cv2.COLOR_BGR2HSV))
    # Keep amber room light and yellow drink behind a clear neck from being
    # counted as the orange plastic closure.
    orange = (hue >= 3) & (hue <= 17) & (saturation >= 90) & (value >= 70)
    coverage = float(orange.mean())
    row_coverage = orange.mean(axis=1)
    widest_row = float(row_coverage.max())
    active = row_coverage >= .35
    edges = np.flatnonzero(np.diff(np.r_[False,active,False]))
    runs = [(int(start),int(end-start)) for start,end in zip(edges[::2],edges[1::2])]
    start, span = max(runs,key=lambda item:item[1]) if runs else (0,0)
    # An uncapped bottle can retain a thin orange tamper band. Require the
    # taller closure near the detected bottle top before reporting PRESENT.
    min_cap_span = max(8,.045*bh)
    if coverage >= .08 and span >= min_cap_span and start <= .045*bh:
        result.update(status='present',confidence=min(1.0,span/min_cap_span-0.2))
    elif coverage <= .025 and widest_row < .15:
        result.update(status='missing',confidence=min(1.0,1.0-coverage/.05))
    elif span >= 3 and span < min_cap_span and start >= .04*bh:
        result.update(status='missing',confidence=.75)
    return result


def has_gatorade_text(lines: list[dict]) -> bool:
    words = [re.sub(r'[^A-Z]','',item['text'].upper())
             for item in lines if item['confidence'] >= .75]
    if any('GATORADE' in word for word in words):
        return True
    return (any(re.fullmatch(r'GATO[RB]AD[EC]',word) for word in words)
            and any('THIRST' in word for word in words))


class LabelReader:
    """RapidOCR model used in Remington Vision's public Gatorade demo."""

    def __init__(self):
        from rapidocr_onnxruntime import RapidOCR
        self.engine = RapidOCR(intra_op_num_threads=2, inter_op_num_threads=1,
                               det_limit_side_len=320, use_cls=False)

    def read(self, crop: np.ndarray) -> list[dict]:
        if not crop.size or min(crop.shape[:2]) < 40:
            return []
        scale = min(2.0,max(1.0,500/max(crop.shape[:2])))
        image = cv2.resize(crop,None,fx=scale,fy=scale) if scale>1 else crop
        result,_ = self.engine(image)
        return [{'text':str(text).strip(),'confidence':float(confidence)}
                for _box,text,confidence in (result or [])
                if confidence >= .75 and len(re.sub(r'[^A-Za-z0-9]','',str(text))) >= 3]


def label_summary(lines: list[dict], limit: int = 90) -> str:
    text = ' · '.join(item['text'] for item in lines[:5])
    return text[:limit]
