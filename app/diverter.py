"""Pure timing and saved-program plans for the bottle conveyor.

No function in this module connects to or commands EtherMotion. The runtime
executes a primary saved cycle, then optionally a separate return cycle after
both the bottle-clear deadline and the primary-completion hold have elapsed.
Without a separate return program, the primary saved cycle owns its complete
move, hold, and return sequence.
"""
from __future__ import annotations

import math
import re
from dataclasses import dataclass
from typing import Any


_PROGRAM_ID = re.compile(r"[A-Za-z0-9_-]{1,64}\Z")


def _number(value: Any, name: str, *, positive: bool = False) -> float:
    if isinstance(value, bool):
        raise ValueError(f"{name} must be a finite number.")
    try:
        result = float(value)
    except (ValueError, TypeError, OverflowError):
        raise ValueError(f"{name} must be a finite number.") from None
    if not math.isfinite(result) or (result <= 0 if positive else result < 0):
        limit = "greater than 0" if positive else "0 or greater"
        raise ValueError(f"{name} must be finite and {limit}.")
    return result


def _cycles(value: Any, name: str) -> int:
    number = _number(value, name, positive=True)
    if number != int(number) or not 1 <= number <= 10:
        raise ValueError(f"{name} must be a whole number from 1 to 10.")
    return int(number)


def _program(value: Any, name: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{name} must be a saved EtherMotion program ID or blank.")
    value = value.strip()
    if value and not _PROGRAM_ID.fullmatch(value):
        raise ValueError(f"{name} must contain 1–64 letters, numbers, underscores, or dashes.")
    return value


@dataclass(frozen=True)
class _Timing:
    travel: float
    lead: float
    move: float
    clearance: float
    hold: float
    reject: str
    reject_cycles: int
    accept: str
    accept_cycles: int
    return_program: str


def _settings(settings: dict) -> _Timing:
    speed = _number(settings.get("belt_speed", 200.0), "Belt speed", positive=True)
    distance = _number(settings.get("distance_mm", 0.0), "Camera-to-diverter distance")
    extra = _number(settings.get("delay_ms", 0.0), "Extra arrival delay") / 1000
    lead = _number(settings.get("lead_ms", 0.0), "Diverter lead") / 1000
    move = _number(settings.get("move_ms", 150.0), "Diverter move time") / 1000
    length = _number(settings.get("bottle_length_mm", 80.0), "Bottle length along the belt", positive=True)
    margin = _number(settings.get("clearance_ms", 100.0), "Bottle clearance margin") / 1000
    hold = _number(settings.get("hold_ms", 500.0), "Hold after primary completion") / 1000
    travel = distance / speed + extra
    clearance = length / speed + margin
    if not math.isfinite(travel) or not math.isfinite(clearance):
        raise ValueError("Calculated conveyor timing must be finite; check distance, length, and speed.")
    return _Timing(travel, lead, move, clearance, hold,
                   _program(settings.get("program_id", ""), "Reject program"),
                   _cycles(settings.get("reject_cycles", 1), "Reject cycle count"),
                   _program(settings.get("pass_program_id", ""), "Pass program"),
                   _cycles(settings.get("pass_cycles", 1), "Pass cycle count"),
                   _program(settings.get("return_program_id", ""), "Return program"))


def validate_timing(settings: dict) -> None:
    """Raise when configured timing cannot be armed for conveyor output.

    A preview/plan may describe earlier trigger times, but armed output cannot
    clamp an impossible deadline to the present. Lead must cover the move time
    and must fit within camera-to-diverter travel plus the extra arrival delay.
    Program existence, driver readiness, and available inter-bottle spacing
    are checked by the runtime that owns the hardware connection.
    """
    timing = _settings(settings)
    if timing.lead < timing.move:
        raise ValueError("Diverter lead must be at least the diverter move time before arming.")
    if timing.travel < timing.lead:
        raise ValueError("Bottle travel time must be at least the diverter lead before arming; increase distance or arrival delay, or reduce belt speed.")


def plan(settings: dict, bad: bool, captured: float) -> dict:
    """Return one bottle's absolute monotonic deadlines and selected cycles.

    ``captured`` is the bottle's timestamp at the configured tracking line.
    Travel includes the configured extra delay. A blank primary program means
    no action for this outcome; an optional return is suppressed in that case.
    Call ``validate_timing`` before arming output; this planner preserves exact
    deadlines, including a due time earlier than capture for an invalid setup.
    """
    timing = _settings(settings)
    captured = _number(captured, "Bottle capture timestamp")
    arrival = captured + timing.travel
    due = arrival - timing.lead
    clearance = arrival + timing.clearance
    if not all(math.isfinite(value) for value in (arrival, due, clearance)):
        raise ValueError("Calculated bottle deadlines must be finite.")
    program = timing.reject if bad else timing.accept
    return {
        "program_id": program,
        "repeats": timing.reject_cycles if bad else timing.accept_cycles,
        "return_program_id": timing.return_program if program else "",
        "hold_seconds": timing.hold,
        "arrival_at": arrival,
        "due_at": due,
        "clearance_at": clearance,
    }


def preview(settings: dict) -> str:
    """Describe the same timing used by ``plan``, without commanding hardware."""
    timing = _settings(settings)
    text = (f"Trigger delay: {(timing.travel - timing.lead) * 1000:.0f} ms. "
            f"Bottle arrival: {timing.travel * 1000:.0f} ms. "
            f"Minimum clearance: {timing.clearance * 1000:.0f} ms after arrival "
            f"({(timing.travel + timing.clearance) * 1000:.0f} ms after detection). ")
    if timing.return_program:
        text += (f"Separate return waits until the bottle is clear AND at least {timing.hold * 1000:.0f} ms "
                 "after each primary cycle completes.")
    else:
        text += "The primary saved cycle must contain its own hold and return."
    try:
        validate_timing(settings)
    except ValueError as exc:
        text += f" Cannot arm: {exc}"
    return text
