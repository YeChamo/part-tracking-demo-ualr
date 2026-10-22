"""Class labels for a YOLOX model trained to detect bottles by color.

This module only interprets model configuration. It never derives a bottle's
color from camera pixels and never assigns colors to generic COCO classes.
"""
from __future__ import annotations

import ast
import csv
import json
import re
from collections.abc import Mapping, Sequence
from typing import Any


COLORS = ("orange", "yellow", "green", "blue", "red", "purple", "clear")


def _structured(value: str) -> Any:
    """Read JSON or the literal dictionaries used in some ONNX metadata."""
    try:
        return json.loads(value)
    except (ValueError, TypeError):
        try:
            return ast.literal_eval(value)
        except (ValueError, SyntaxError):
            raise ValueError("Use a JSON list/object or comma-separated class names.") from None


def _class_id(value: Any) -> int:
    if isinstance(value, bool) or not re.fullmatch(r"\d+", str(value).strip()):
        raise ValueError("Model class IDs must be non-negative whole numbers.")
    return int(value)


def parse_class_names(value: Any) -> list[str]:
    """Return class names in exact model-output order.

    Supported values are a list, a numeric-key dictionary, a JSON/Python
    literal string of either, or comma/newline-separated names. Dictionary IDs
    must start at zero and have no gaps, so labels cannot shift silently.
    """
    if value is None or (isinstance(value, str) and not value.strip()):
        return []
    if isinstance(value, str):
        value = value.strip()
        if value.startswith(("[", "{", "(")):
            value = _structured(value)
        else:
            value = next(csv.reader([value.replace("\r\n", ",").replace("\n", ",")]))
    if isinstance(value, Mapping):
        indexed = {_class_id(key): name for key, name in value.items()}
        if len(indexed) != len(value) or sorted(indexed) != list(range(len(indexed))):
            raise ValueError("Class names must use consecutive IDs starting at 0.")
        value = [indexed[index] for index in range(len(indexed))]
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        raise ValueError("Use a list or numeric-key object for model class names.")
    names = []
    for name in value:
        if not isinstance(name, str) or not name.strip():
            raise ValueError("Every model class needs a non-empty name.")
        names.append(name.strip())
    return names


def class_names_from_metadata(metadata: Mapping[str, Any] | None) -> list[str]:
    """Read recognized class-label metadata; absent labels return an empty list."""
    if not metadata:
        return []
    for key in ("names", "class_names", "classes"):
        if metadata.get(key):
            return parse_class_names(metadata[key])
    return []


def color_from_class_name(name: str) -> str | None:
    """Resolve an unambiguous color token, e.g. ``bottle_orange``.

    Only the supported exact color tokens count. Labels such as ``bottle``,
    ``red_blue`` and ``redish`` are deliberately not assigned a color.
    """
    tokens = set(re.findall(r"[a-z]+", str(name).lower()))
    matches = tokens.intersection(COLORS)
    return next(iter(matches)) if len(matches) == 1 else None


def parse_color_map(value: Any) -> dict[int, str]:
    """Read explicit model class IDs to colors, without assuming output order.

    Accept a mapping, a JSON/Python literal mapping, or ``0:orange,1:blue``.
    Color names must be one of ``COLORS``. Duplicate numeric IDs are rejected.
    """
    if value is None or (isinstance(value, str) and not value.strip()):
        return {}
    if isinstance(value, str):
        value = value.strip()
        if value.startswith("{"):
            value = _structured(value)
        else:
            pairs = []
            for part in re.split(r"[,;\n]", value):
                if not part.strip():
                    continue
                pair = re.split(r"[:=]", part, maxsplit=1)
                if len(pair) != 2:
                    raise ValueError("Map color classes as 0:orange,1:blue or a JSON object.")
                pairs.append((pair[0].strip(), pair[1].strip()))
            # Preserve pairs until duplicate IDs have been checked.
            value = pairs
    if isinstance(value, Mapping):
        pairs = value.items()
    elif isinstance(value, list) and all(isinstance(p, tuple) and len(p) == 2 for p in value):
        pairs = value
    else:
        raise ValueError("Color mapping must be an object of class ID to color.")
    result = {}
    for key, name in pairs:
        index = _class_id(key)
        if index in result:
            raise ValueError(f"Color mapping repeats class ID {index}.")
        color = str(name).strip().lower()
        if color not in COLORS:
            raise ValueError(f"Class {index} needs a supported color: {', '.join(COLORS)}.")
        result[index] = color
    return result


def build_color_map(class_names: Any = None, explicit_map: Any = None,
                    class_count: int | None = None) -> dict[int, str]:
    """Validate a model's trained bottle-color class configuration.

    Explicit mappings override names for that class. At least two distinct
    colors are required for sorting. An actual class count, when supplied,
    verifies that class labels and IDs fit the model instead of guessed IDs.
    """
    names = parse_class_names(class_names)
    if class_count is not None:
        class_count = _class_id(class_count)
        if class_count < 1:
            raise ValueError("YOLOX model has no class channels.")
        if names and len(names) != class_count:
            raise ValueError(f"The model has {class_count} classes, but {len(names)} class names were supplied.")
    result = {index: color for index, name in enumerate(names)
              if (color := color_from_class_name(name)) is not None}
    result.update(parse_color_map(explicit_map))
    if class_count is not None and any(index >= class_count for index in result):
        raise ValueError(f"Color class IDs must be below the model's {class_count} classes.")
    if len(set(result.values())) < 2:
        raise ValueError("Select a YOLOX model trained for at least two bottle colors and configure its color class IDs. The bundled COCO model only detects generic bottles.")
    return result


def color_map_error(class_names: Any = None, explicit_map: Any = None,
                    class_count: int | None = None, pass_color: str | None = None) -> str:
    """Return a user-visible setup error, or an empty string when valid."""
    try:
        colors = build_color_map(class_names, explicit_map, class_count)
        if pass_color is not None and str(pass_color).lower() not in colors.values():
            return "The pass color must be one of the YOLOX model's configured bottle colors."
    except (ValueError, TypeError) as exc:
        return str(exc)
    return ""
