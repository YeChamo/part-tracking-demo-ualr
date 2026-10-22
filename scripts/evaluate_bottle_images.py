"""Run the live Gatorade inspection pipeline on local still images.

Usage: python scripts/evaluate_bottle_images.py data/external_eval
Images are intentionally kept outside Git; obtain permission before reuse.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

import cv2

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.gatorade_pipeline import GatoradePipeline  # noqa: E402
from app.settings import DEFAULTS  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("images", type=Path, help="Image file or directory of images")
    args = parser.parse_args()
    paths = sorted(args.images.iterdir()) if args.images.is_dir() else [args.images]
    paths = [path for path in paths if path.suffix.lower() in {".jpg", ".jpeg", ".png", ".webp"}]
    if not paths:
        parser.error("No supported images found")
    pipeline = GatoradePipeline({**DEFAULTS, "label_ocr": False}, ROOT).open()
    try:
        for path in paths:
            frame = cv2.imread(str(path))
            if frame is None:
                print(json.dumps({"image": path.name, "error": "Could not read image"}))
                continue
            result = pipeline.infer(frame)
            print(json.dumps({
                "image": path.name,
                "detections": len(result["boxes"]),
                "colors": result["colors"],
                "caps": [cap["status"] for cap in result["caps"]],
                "boxes": [[round(float(value), 1) for value in box] for box in result["boxes"]],
            }))
    finally:
        pipeline.close()


if __name__ == "__main__":
    main()
