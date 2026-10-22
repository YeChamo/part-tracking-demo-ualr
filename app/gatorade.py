"""Gatorade demo observations layered on the generic YOLOX-S bottle boxes.

Color and label evidence are separate from the detector so future inspections
can consume the same localized bottle without changing tracking or motion code.
"""
from __future__ import annotations

from pathlib import Path
from typing import Sequence

import cv2
import numpy as np


COLOR_NAMES = ("red", "orange", "yellow", "green", "blue", "purple", "white")


def neutralize_color_cast(frame: np.ndarray) -> np.ndarray:
    """Estimate camera channel bias from the least colorful visible pixels.

    The correction is deliberately bounded. A scene without a credible neutral
    reference is left alone rather than having its drink colors shifted.
    """
    if frame.ndim != 3 or frame.shape[2] != 3:
        raise ValueError("Expected an HxWx3 BGR camera frame.")
    small = cv2.resize(frame, (160, 90), interpolation=cv2.INTER_AREA).astype(np.float32)
    pixels = small.reshape(-1, 3)
    spread = pixels.max(axis=1) - pixels.min(axis=1)
    value = pixels.max(axis=1)
    valid = (value > 75) & (value < 245)
    if int(valid.sum()) < 500:
        return frame
    neutral_limit = np.quantile(spread[valid], .45)
    anchor = np.median(pixels[valid & (spread <= neutral_limit)], axis=0)
    if float(anchor.max() - anchor.min()) > 70:
        return frame
    offset = np.clip(anchor.mean() - anchor, -35, 35)
    if float(np.max(np.abs(offset))) < 1:
        return frame
    transform = np.float32([[1, 0, 0, offset[0]],
                            [0, 1, 0, offset[1]],
                            [0, 0, 1, offset[2]]])
    return cv2.transform(frame, transform)


def _sample(frame: np.ndarray, bbox: Sequence[float], top: float, bottom: float) -> tuple[np.ndarray, tuple[int, int, int, int]]:
    height, width = frame.shape[:2]
    x1, y1, x2, y2 = (int(round(float(value))) for value in bbox)
    x1, y1 = max(0, x1), max(0, y1)
    x2, y2 = min(width, x2), min(height, y2)
    bw, bh = x2 - x1, y2 - y1
    roi = (int(x1 + .30 * bw), int(y1 + top * bh),
           int(x1 + .70 * bw), int(y1 + bottom * bh))
    return frame[roi[1]:roi[3], roi[0]:roi[2]], roi


def _classify_patch(crop: np.ndarray, roi: tuple[int, int, int, int]) -> dict:
    reading = {"name": "unknown", "confidence": 0.0, "roi": roi}
    if not crop.size or min(crop.shape[:2]) < 8:
        return reading
    hue, saturation, value = cv2.split(cv2.cvtColor(crop, cv2.COLOR_BGR2HSV))
    chromatic = (saturation >= 65) & (value >= 45)
    pale = (saturation < 55) & (value >= 90)
    if float(chromatic.mean()) < .25:
        fraction = float(pale.mean())
        if fraction >= .70:
            reading.update(name="white", confidence=fraction)
        return reading
    hues = hue[chromatic]
    votes = (
        ((hues < 9) | (hues >= 170)).mean(),
        ((hues >= 9) & (hues < 23)).mean(),
        ((hues >= 23) & (hues < 38)).mean(),
        ((hues >= 38) & (hues < 88)).mean(),
        ((hues >= 88) & (hues < 133)).mean(),
        ((hues >= 133) & (hues < 170)).mean(),
    )
    winner = int(np.argmax(votes))
    confidence = float(votes[winner])
    reading.update(name=COLOR_NAMES[winner] if confidence >= .65 else "unknown",
                   confidence=confidence)
    return reading


def measure_drink_color(frame: np.ndarray, bbox: Sequence[float]) -> dict:
    """Sample exposed liquid on the shoulder, with a fallback for cropped views."""
    if not isinstance(frame, np.ndarray) or frame.ndim != 3 or frame.shape[2] != 3:
        raise ValueError("Expected an HxWx3 BGR camera frame.")
    if len(bbox) != 4 or not all(np.isfinite(float(value)) for value in bbox):
        raise ValueError("Bottle box must contain four finite coordinates.")
    x1, y1, x2, y2 = (float(value) for value in bbox)
    if x2 - x1 < 20 or y2 - y1 < 40:
        return {"name": "unknown", "confidence": 0.0, "roi": (0, 0, 0, 0)}
    crop, roi = _sample(frame, bbox, .22, .35)
    reading = _classify_patch(crop, roi)
    if reading["name"] == "unknown" and y1 <= .02 * frame.shape[0]:
        crop, roi = _sample(frame, bbox, .10, .22)
        reading = _classify_patch(crop, roi)
    # A clipped bottle can expose a pale highlight where its shoulder would
    # normally be. Strong liquid color lower down wins over that highlight.
    if (reading["name"] == "unknown" or
            (reading["name"] == "white" and y1 <= .02 * frame.shape[0])):
        crop, roi = _sample(frame, bbox, .82, .93)
        lower = _classify_patch(crop, roi)
        if lower["name"] not in ("unknown", "white"):
            reading = lower
        elif reading["name"] == "unknown" and y2 < .98 * frame.shape[0]:
            reading = lower
    return reading


class GatoradeLabelMatcher:
    """Geometric Gatorade label evidence; a failed match is not a brand verdict."""

    def __init__(self, model_dir: Path):
        self.sift = cv2.SIFT_create(nfeatures=800, contrastThreshold=.02)
        self.references = []
        for name in ("logo", "blue", "yellow", "white"):
            path = Path(model_dir) / f"gatorade_{name}_reference.png"
            reference = cv2.imread(str(path), cv2.IMREAD_GRAYSCALE)
            if reference is None:
                continue
            keypoints, descriptors = self.sift.detectAndCompute(reference, None)
            if descriptors is not None and len(descriptors) >= 12:
                self.references.append((reference, keypoints, descriptors))
        if not self.references:
            raise FileNotFoundError(f"No usable Gatorade label references in {model_dir}")

    def match(self, crop: np.ndarray) -> bool:
        if not crop.size or min(crop.shape[:2]) < 40:
            return False
        scale = min(1.0, 800 / max(crop.shape[:2]))
        gray = cv2.cvtColor(cv2.resize(crop, None, fx=scale, fy=scale), cv2.COLOR_BGR2GRAY)
        if self._match_gray(gray):
            return True
        return self._match_gray(cv2.flip(gray, 1))

    def _match_gray(self, gray: np.ndarray) -> bool:
        keypoints, descriptors = self.sift.detectAndCompute(gray, None)
        if descriptors is None or len(descriptors) < 12:
            return False
        for reference, ref_points, ref_descriptors in self.references:
            pairs = cv2.BFMatcher().knnMatch(ref_descriptors, descriptors, k=2)
            candidates = [m for pair in pairs if len(pair) == 2
                          for m, n in [pair] if m.distance < .6 * n.distance]
            unique = {m.trainIdx: m for m in sorted(candidates, key=lambda m: m.distance, reverse=True)}
            matches = list(unique.values())
            if len(matches) < 12:
                continue
            src = np.float32([ref_points[m.queryIdx].pt for m in matches])
            dst = np.float32([keypoints[m.trainIdx].pt for m in matches])
            transform, mask = cv2.findHomography(src, dst, cv2.RANSAC, 3)
            if transform is None or mask is None or mask.sum() < 12 or mask.mean() < .6:
                continue
            h, w = reference.shape
            corners = cv2.perspectiveTransform(np.float32([[[0, 0], [w, 0], [w, h], [0, h]]]), transform)[0]
            if not np.isfinite(corners).all() or not cv2.isContourConvex(corners):
                continue
            area = abs(cv2.contourArea(corners)) / (gray.shape[0] * gray.shape[1])
            inside = ((corners[:, 0] >= -5) & (corners[:, 0] <= gray.shape[1] + 5)
                      & (corners[:, 1] >= -5) & (corners[:, 1] <= gray.shape[0] + 5)).all()
            if inside and .015 < area < .7:
                return True
        return False
