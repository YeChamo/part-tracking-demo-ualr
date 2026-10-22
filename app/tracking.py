"""Small, dependency-free tracker for a single conveyor lane.

Coordinates are image pixels. ``line`` and ``entry`` are fractions measured
from the incoming side, so the same recipe works in either direction. Sorting
tracks first appear in the entry zone and decide only on a fresh line crossing.
Visual-only tracks can begin anywhere and never produce sorting decisions.
Extrapolation is used solely for association.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import math
from typing import Sequence


BBox = tuple[float, float, float, float]


@dataclass(frozen=True)
class TrackingConfig:
    direction: str = "ltr"
    line: float = 0.80
    entry: float = 0.30
    confirm_frames: int = 3
    max_miss: float = 0.40
    visual_only: bool = False

    def __post_init__(self) -> None:
        if type(self.visual_only) is not bool:
            raise ValueError("visual_only must be a boolean")
        if self.direction not in {"ltr", "rtl"}:
            raise ValueError("direction must be ltr or rtl")
        for name in ("line", "entry", "max_miss"):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
                raise ValueError(f"{name} must be finite")
        if not 0 < self.entry < self.line < 1:
            raise ValueError("entry and line must satisfy 0 < entry < line < 1")
        if isinstance(self.confirm_frames, bool) or not isinstance(self.confirm_frames, int) or not 1 <= self.confirm_frames <= 120:
            raise ValueError("confirm_frames must be an integer between 1 and 120")
        if not 0.02 <= self.max_miss <= 5:
            raise ValueError("max_miss must be between 0.02 and 5 seconds")


@dataclass
class Track:
    id: int
    bbox: BBox
    bad: bool = False
    reasons: list[str] = field(default_factory=list)
    hits: int = 1
    decided: bool = False
    last_seen: float = 0.0
    missed: bool = False
    _vx: float = field(default=0.0, repr=False)
    _vy: float = field(default=0.0, repr=False)
    _streak: int = field(default=0, repr=False)
    _pending: list[str] = field(default_factory=list, repr=False)


@dataclass(frozen=True)
class Decision:
    id: int
    bad: bool
    reasons: list[str]
    captured: float
    bbox: BBox


def _center(box: BBox) -> tuple[float, float]:
    return ((box[0] + box[2]) / 2, (box[1] + box[3]) / 2)


def _iou(a: BBox, b: BBox) -> float:
    area = max(0.0, min(a[2], b[2]) - max(a[0], b[0])) * max(0.0, min(a[3], b[3]) - max(a[1], b[1]))
    if not area:
        return 0.0
    union = (a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - area
    return area / union


class BottleTracker:
    def __init__(self, config: TrackingConfig | None = None):
        self.config = config or TrackingConfig()
        self._tracks: dict[int, Track] = {}
        self._next_id = 1
        self._last_capture: float | None = None
        self._paused_at: float | None = None
        self._shape: tuple[int, int] | None = None

    @property
    def tracks(self) -> list[Track]:
        return sorted(self._tracks.values(), key=lambda track: track.id)

    def reset(self) -> None:
        """Forget live bottles, retaining the monotonically increasing ID counter."""
        self._tracks.clear()
        self._last_capture = None
        self._paused_at = None
        self._shape = None

    def _leading(self, box: BBox, width: int) -> float:
        return box[2] / width if self.config.direction == "ltr" else 1 - box[0] / width

    def _at_entry(self, box: BBox, width: int) -> bool:
        cx, _ = _center(box)
        progress = cx / width if self.config.direction == "ltr" else 1 - cx / width
        return progress <= self.config.entry and self._leading(box, width) < self.config.line

    def _inspect(self, track: Track, reasons: list[str]) -> None:
        if self.config.visual_only:
            track.bad = False
            track.reasons.clear()
            track._streak = 0
            track._pending.clear()
            return
        # Unavailable inspection is a fail-closed state, never a good bottle.
        unavailable = any(reason.casefold().startswith(("inspection unavailable", "unknown inspection", "unknown color", "not inspected", "vision unavailable")) for reason in reasons)
        if reasons:
            track._streak += 1
            track._pending = list(dict.fromkeys(track._pending + reasons))
            if unavailable or track._streak >= self.config.confirm_frames:
                track.bad = True
                track.reasons = list(dict.fromkeys(track.reasons + track._pending))
            elif track.bad:
                track.reasons = list(dict.fromkeys(track.reasons + reasons))
        else:
            track._streak = 0
            track._pending.clear()

    def _cost(self, track: Track, box: BBox, captured: float, width: int, height: int) -> float | None:
        old = track.bbox
        cx, cy = _center(old)
        nx, ny = _center(box)
        old_w, old_h = old[2] - old[0], old[3] - old[1]
        new_w, new_h = box[2] - box[0], box[3] - box[1]
        dt = captured - track.last_seen
        forward = nx - cx if self.config.direction == "ltr" else cx - nx
        # Sorting follows a one-way belt; a visual demonstration may reverse.
        if not self.config.visual_only and forward < -max(3.0, min(old_w, new_w) * 0.22):
            return None
        if max(old_w, new_w) / min(old_w, new_w) > 2.0 or max(old_h, new_h) / min(old_h, new_h) > 1.8:
            return None
        predicted_x, predicted_y = cx + track._vx * dt, cy + track._vy * dt
        x_gate = max(8.0, width * 0.065, max(old_w, new_w) * 1.15)
        # A wider gate after a dropout is tied to an already measured velocity.
        x_gate += min(abs(track._vx) * dt * 0.45, width * 0.10)
        y_gate = max(6.0, height * 0.045, max(old_h, new_h) * 0.45)
        dx, dy = abs(nx - predicted_x), abs(ny - predicted_y)
        if dx > x_gate or dy > y_gate:
            return None
        predicted = (old[0] + track._vx * dt, old[1] + track._vy * dt, old[2] + track._vx * dt, old[3] + track._vy * dt)
        return dx / x_gate + dy / y_gate + 0.2 * abs(math.log(new_w / old_w)) + 0.2 * abs(math.log(new_h / old_h)) - 0.6 * _iou(predicted, box)

    def _associate(self, boxes: list[BBox], captured: float, width: int, height: int) -> list[tuple[Track, int]]:
        # Conveyor order cannot change in one lane. Ordered sequence alignment
        # enforces one-to-one matches without ever swapping adjacent identities.
        tracks = sorted(self._tracks.values(), key=lambda track: _center(track.bbox)[0])
        detections = sorted(range(len(boxes)), key=lambda index: _center(boxes[index])[0])
        n, m = len(tracks), len(detections)
        scores = [[math.inf] * (m + 1) for _ in range(n + 1)]
        previous: dict[tuple[int, int], tuple[int, int, bool]] = {}
        scores[0][0] = 0.0
        for i in range(n + 1):
            for j in range(m + 1):
                score = scores[i][j]
                if i < n and score + 1.1 < scores[i + 1][j]:
                    scores[i + 1][j] = score + 1.1
                    previous[i + 1, j] = (i, j, False)
                if j < m and score + 1.1 < scores[i][j + 1]:
                    scores[i][j + 1] = score + 1.1
                    previous[i, j + 1] = (i, j, False)
                if i < n and j < m:
                    cost = self._cost(tracks[i], boxes[detections[j]], captured, width, height)
                    if cost is not None and score + cost < scores[i + 1][j + 1]:
                        scores[i + 1][j + 1] = score + cost
                        previous[i + 1, j + 1] = (i, j, True)
        matches: list[tuple[Track, int]] = []
        i, j = n, m
        while i or j:
            pi, pj, matched = previous[i, j]
            if matched:
                matches.append((tracks[pi], detections[pj]))
            i, j = pi, pj
        return matches

    @staticmethod
    def _validated(boxes: Sequence[Sequence[float]], reasons: Sequence[Sequence[str]], captured: float, width: int, height: int) -> tuple[list[BBox], list[list[str]]]:
        if isinstance(captured, bool) or not isinstance(captured, (int, float)) or not math.isfinite(captured) or captured < 0:
            raise ValueError("captured must be a finite, nonnegative monotonic timestamp")
        if any(isinstance(value, bool) or not isinstance(value, int) or value < 2 for value in (width, height)):
            raise ValueError("image width and height must be integers of at least 2")
        if len(boxes) != len(reasons):
            raise ValueError("each detection must have its own reasons list")
        cleaned_boxes: list[BBox] = []
        cleaned_reasons: list[list[str]] = []
        for box, flags in zip(boxes, reasons):
            if len(box) != 4 or any(isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) for value in box):
                raise ValueError("each box must contain four finite coordinates")
            x1, y1, x2, y2 = (float(value) for value in box)
            if not 0 <= x1 < x2 <= width or not 0 <= y1 < y2 <= height:
                raise ValueError("boxes must have positive area and stay inside the image")
            if isinstance(flags, (str, bytes)) or any(not isinstance(reason, str) for reason in flags):
                raise ValueError("reasons must be lists of strings")
            cleaned_boxes.append((x1, y1, x2, y2))
            cleaned_reasons.append(list(dict.fromkeys(reason.strip() for reason in flags if reason.strip())))
        return cleaned_boxes, cleaned_reasons

    def update(self, boxes: list[Sequence[float]], reasons: list[list[str]], captured: float, width: int, height: int, moving: bool = True) -> tuple[list[Track], list[Decision]]:
        boxes, reasons = self._validated(boxes, reasons, captured, width, height)
        if self._last_capture is not None and captured <= self._last_capture:
            # Reused or out-of-order camera frames cannot advance identities.
            return self.tracks, []
        self._last_capture = captured
        if self._shape is not None and self._shape != (width, height):
            self._tracks.clear()
            self._paused_at = None
        self._shape = (width, height)
        if not moving and not self.config.visual_only:
            if self._paused_at is None:
                self._paused_at = captured
            return self.tracks, []
        if self._paused_at is not None:
            paused_for = captured - self._paused_at
            for track in self._tracks.values():
                track.last_seen += paused_for
                track._vx = track._vy = 0.0
            self._paused_at = None
        # Expire before association: a later bottle must not inherit an old ID.
        self._tracks = {key: track for key, track in self._tracks.items() if captured - track.last_seen <= self.config.max_miss}
        matches = self._associate(boxes, captured, width, height)
        used: set[int] = set()
        seen: set[int] = set()
        decisions: list[Decision] = []
        for track, index in matches:
            used.add(index)
            seen.add(track.id)
            box = boxes[index]
            previous_edge = self._leading(track.bbox, width)
            previous_center = _center(track.bbox)
            next_center = _center(box)
            dt = captured - track.last_seen
            if dt > 0:
                vx, vy = (next_center[0] - previous_center[0]) / dt, (next_center[1] - previous_center[1]) / dt
                track._vx = vx if track.hits == 1 else 0.65 * vx + 0.35 * track._vx
                track._vy = vy if track.hits == 1 else 0.65 * vy + 0.35 * track._vy
            track.bbox = box
            track.hits += 1
            track.last_seen = captured
            track.missed = False
            self._inspect(track, reasons[index])
            if (not self.config.visual_only and not track.decided
                    and previous_edge < self.config.line <= self._leading(box, width)):
                # Confirmation filters transient upstream noise, but evidence
                # still unresolved at the deadline cannot become a PASS merely
                # because too few camera frames remain for confirmation.
                if not track.bad and track._streak > 0 and track._pending:
                    track.bad = True
                    track.reasons = [
                        f"Unconfirmed {'color' if 'color' in reason.casefold() else 'inspection'}: {reason}"
                        for reason in track._pending
                    ]
                track.decided = True
                decisions.append(Decision(track.id, track.bad, list(track.reasons), captured, box))
        for track in self._tracks.values():
            if track.id not in seen:
                track.missed = True
                track._streak = 0
                track._pending.clear()
        for index, box in enumerate(boxes):
            if index in used or (not self.config.visual_only and not self._at_entry(box, width)):
                continue
            # An unassociated duplicate around an existing bottle must not
            # create a second identity (including detector duplicate boxes).
            if any(_iou(box, track.bbox) > 0.20 for track in self._tracks.values()):
                continue
            track = Track(self._next_id, box, last_seen=captured)
            self._next_id += 1
            self._inspect(track, reasons[index])
            self._tracks[track.id] = track
        return self.tracks, sorted(decisions, key=lambda decision: decision.id)
