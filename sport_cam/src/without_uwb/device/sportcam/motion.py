"""How the head changes speed, for everything that turns it.

Tracking eases toward a goal angle (`ease_to`), the app's joystick toward a
speed (`Ptz.jog`); both change speed no faster than an acceleration limit
(`accelerate`), so every move starts and ends gently whichever is driving.
Below this, ptz.py turns the angles into servo writes the same way for both.
"""
from __future__ import annotations

import math

from . import config


def accelerate(vel: float, want: float, max_accel: float, dt: float) -> float:
    """`vel` moved toward `want` by at most `max_accel`·dt: one tick's change."""
    step = max_accel * dt
    return want if abs(want - vel) <= step else vel + math.copysign(step, want - vel)


def ease_to(pos: float, vel: float, goal: float, dt: float,
            max_dps: float, max_accel: float) -> tuple[float, float]:
    """One tick of easing toward `goal` → (new position, new velocity).

    The wanted speed is the distance left over TRACK_EASE_S, capped at
    `max_dps` and at the speed from which `max_accel` can still stop at the
    goal. The velocity moves toward it by at most `max_accel`·dt per tick.
    """
    err = goal - pos
    want = math.copysign(min(abs(err) / config.TRACK_EASE_S,
                             math.sqrt(2.0 * max_accel * abs(err)), max_dps), err)
    vel = accelerate(vel, want, max_accel, dt)
    step = vel * dt
    if err * step > 0 and abs(step) >= abs(err):
        return goal, 0.0                       # arriving: land on it, not past it
    return pos + step, vel


def tilt_error_px(y: float, h: float) -> float:
    """How far below where it should be a person's box sits, in pixels of a
    PREVIEW_SIZE frame (positive: aim lower; negative: aim higher).

    Normally the box's centre from the frame's. But a person too tall for the
    frame runs off its edges, and the box stops at them: its centre then sits
    mid-frame however the head is cut off, so the centre alone says nothing is
    wrong. So when the top of the body is within TRACK_HEADROOM_FRACTION of
    the frame's top, or the bottom has run off the frame, aim the top of the
    body at that headroom instead: the head stays in, and the rest falls
    where it may.
    """
    ph = config.PREVIEW_SIZE[1]
    cy = y + h / 2
    body = h * config.PERSON_IN_BOX_H
    top, bottom = cy - body / 2, cy + body / 2
    headroom = config.TRACK_HEADROOM_FRACTION * ph
    if top < headroom or bottom >= ph * (1 - config.ZOOM_GUARD_EDGE):
        return top - headroom
    return cy - ph / 2
