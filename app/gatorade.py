"""Optional offline matching of Gatorade reference artwork.

This utility is for examining reference images only. Live bottle locations and
colors come exclusively from the selected YOLOX model class predictions; label
artwork matching does not supply color, pass/fail, tracking, or motion decisions.
"""
from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np


class GatoradeLabelMatcher:
    """Offline geometric reference matching, separate from the live YOLOX route.

    A match is reference-image evidence only. A failed match is not a brand
    verdict, and neither result is a bottle-color prediction.
    """

    def __init__(self, model_dir: Path):
        self.sift = cv2.SIFT_create(nfeatures=800, contrastThreshold=.02)
        self.references = []
        for name in ("logo", "blue", "yellow", "white"):
            path = Path(model_dir) / f"gatorade_{name}_reference.png"
            if not path.is_file():
                continue
            reference = cv2.imread(str(path), cv2.IMREAD_GRAYSCALE)
            if reference is None:
                continue
            keypoints, descriptors = self.sift.detectAndCompute(reference, None)
            if descriptors is not None and len(descriptors) >= 12:
                self.references.append((reference, keypoints, descriptors))
        if not self.references:
            raise FileNotFoundError(f"No usable Gatorade label references in {model_dir}")

    def match(self, crop: np.ndarray) -> bool:
        if (not isinstance(crop, np.ndarray) or crop.ndim != 3
                or crop.shape[2] != 3 or crop.dtype != np.uint8
                or not crop.size or min(crop.shape[:2]) < 40):
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
