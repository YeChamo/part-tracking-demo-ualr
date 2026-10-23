"""Operational color groups, separate from the neural network's trained labels."""


def canonical_sort_color(value: str) -> str:
    """Map the demo's requested aliases while preserving other trained categories."""
    color = str(value).strip().casefold()
    return {'yellow': 'red', 'gray': 'white', 'grey': 'white'}.get(color, color)
