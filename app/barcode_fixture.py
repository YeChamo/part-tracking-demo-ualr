"""Generate clearly synthetic EAN-13 fixtures without an image-generator API.

These are invented demo values, not product identities read from a camera.
Display callers should label them "SYNTHETIC DEMO BARCODE".  The renderer uses
only NumPy and fixed EAN-13 bit patterns, so fixtures work offline and can be
tested by the application's real barcode decoder.
"""
from __future__ import annotations

import re

import numpy as np


_LEFT = (
    "0001101", "0011001", "0010011", "0111101", "0100011",
    "0110001", "0101111", "0111011", "0110111", "0001011",
)
_PARITY = (
    "LLLLLL", "LLGLGG", "LLGGLG", "LLGGGL", "LGLLGG",
    "LGGLLG", "LGGGLL", "LGLGLG", "LGLGGL", "LGGLGL",
)


def make_ean13(payload12: str) -> str:
    """Append the EAN-13 check digit to exactly 12 ASCII digits."""
    if not isinstance(payload12, str) or re.fullmatch(r"[0-9]{12}", payload12) is None:
        raise ValueError("EAN-13 payload must contain exactly 12 ASCII digits.")
    weighted = sum(int(digit) * (1 if index % 2 == 0 else 3) for index, digit in enumerate(payload12))
    return payload12 + str((-weighted) % 10)


def normalize_ean13(value: str) -> str:
    """Accept 12 payload digits or verify a complete 13-digit code."""
    if not isinstance(value, str) or re.fullmatch(r"[0-9]{12,13}", value) is None:
        raise ValueError("EAN-13 requires 12 payload digits or 13 digits including its checksum.")
    normalized = make_ean13(value[:12])
    if len(value) == 13 and value != normalized:
        raise ValueError("EAN-13 checksum is invalid.")
    return normalized


def demo_barcode(sequence: int) -> str:
    """Assign a deterministic invented code to a virtual bottle, up to 1e9."""
    if isinstance(sequence, bool) or not isinstance(sequence, int) or not 0 <= sequence <= 999_999_999:
        raise ValueError("Synthetic bottle sequence must be an integer from 0 to 999999999.")
    return make_ean13(f"200{sequence:09d}")


DEFAULT_EAN13 = demo_barcode(1)


def ean13_modules(value: str = DEFAULT_EAN13) -> str:
    """Return the 95 data/guard modules; 1 means a black bar."""
    code = normalize_ean13(value)
    left = []
    for digit, parity in zip(code[1:7], _PARITY[int(code[0])]):
        pattern = _LEFT[int(digit)]
        # G is the reversed complement of L; right-side R is its complement.
        if parity == "G":
            pattern = "".join("1" if bit == "0" else "0" for bit in pattern[::-1])
        left.append(pattern)
    right = ["".join("1" if bit == "0" else "0" for bit in _LEFT[int(digit)]) for digit in code[7:]]
    return "101" + "".join(left) + "01010" + "".join(right) + "101"


def ean13_bgr(value: str = DEFAULT_EAN13, *, module_width: int = 4,
              height: int = 140, quiet_zone: int = 12) -> np.ndarray:
    """Render a high-contrast uint8 BGR fixture, with white margins.

    The default image is 476 by 140 pixels.  Preserve its aspect ratio and use
    nearest-neighbor scaling when displaying it as a scan target.  ``quiet_zone``
    is measured in modules on each side, not pixels.
    """
    for name, number, low, high in (
        ("module_width", module_width, 1, 32),
        ("height", height, 32, 2048),
        ("quiet_zone", quiet_zone, 11, 100),
    ):
        if isinstance(number, bool) or not isinstance(number, int) or not low <= number <= high:
            raise ValueError(f"{name} must be an integer from {low} to {high}.")
    modules = ean13_modules(value)
    width = (len(modules) + 2 * quiet_zone) * module_width
    image = np.full((height, width, 3), 255, dtype=np.uint8)
    vertical_margin = min(max(4, module_width * 2), height // 4)
    x = quiet_zone * module_width
    for index, bit in enumerate(modules):
        if bit == "1":
            start = x + index * module_width
            image[vertical_margin:height - vertical_margin, start:start + module_width] = 0
    return image
