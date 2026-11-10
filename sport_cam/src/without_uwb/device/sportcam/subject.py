"""Which detection is the person being followed.

One job, with no camera or servos behind it: remember where the person was
last seen and what they look like, and from a detection's boxes choose the
one that is them.

**Where** is a direction in the room — pan and tilt, in degrees — not a place
in the picture. The picture moves: the head turns and the lens zooms between
two detections, and measured in pixels the camera's own motion would count as
the person's. The tracker turns each box into a direction with the pose the
head had when its frame was taken.

**What they look like** is the colours of their torso (detector.look_of),
kept only TRACK_LOOK_FRESH_S: the light changes, and a stale memory would
shut the real person out.
"""
from __future__ import annotations

import math

from . import config
from .detector import look_distance, score_of

Direction = tuple[float, float]      # pan, tilt of something seen, degrees


class Subject:
    def __init__(self) -> None:
        self.look = None                         # their colours, recent
        self.look_at = 0.0                       # …and when last refreshed
        self.direction: Direction | None = None  # where they were last seen

    def forget(self) -> None:
        """A new session: nobody is being followed."""
        self.look = None
        self.direction = None

    def looks_like(self, box, now: float) -> bool | None:
        """Is this box's colouring the person being followed? None when that
        can't be said: no look, or the memory is too old to trust."""
        look = getattr(box, "look", None)        # a plain tuple carries none
        if look is None or self.look is None or now - self.look_at > config.TRACK_LOOK_FRESH_S:
            return None
        return look_distance(self.look, look) <= config.TRACK_LOOK_MAX_DISTANCE

    def pick(self, boxes: list, now: float):
        """Someone to start following: confident enough, not known to be
        someone else, and of those the largest. None if nobody qualifies."""
        sure = [b for b in boxes if score_of(b) >= config.PERSON_LOCK_CONFIDENCE
                and self.looks_like(b, now) is not False]
        return max(sure, key=lambda b: b[2] * b[3], default=None)

    def choose(self, boxes: list, directions: list[Direction], now: float,
               gone_s: float, hfov_deg: float):
        """The detection that is 'our' person, or None.

        `directions[i]` is where `boxes[i]` is; `gone_s` how long since they
        were last seen; `hfov_deg` the width of the picture, which sizes the
        gate. With no previous direction (first sighting), `pick`. After that
        the nearest to where they were last seen, within a gate
        (TRACK_GATE_FRACTION of the picture's width), that doesn't look like
        someone else; back after TRACK_RESEEN_S unseen the gate is wider
        (TRACK_GATE_LOST_FRACTION) and the box must also be confident, as for
        a first sighting. If that finds nobody, or only a doubtful box,
        someone confident anywhere who does look like them takes over: the
        gate must not hold the person out.
        """
        if self.direction is None:
            return self.pick(boxes, now)
        pan, tilt = self.direction
        away = {id(b): math.hypot(d[0] - pan, d[1] - tilt) for b, d in zip(boxes, directions)}

        def far(b) -> float:
            return away[id(b)]

        reseen = gone_s > config.TRACK_RESEEN_S
        gate = hfov_deg * (config.TRACK_GATE_LOST_FRACTION if reseen
                           else config.TRACK_GATE_FRACTION)
        near = [b for b in boxes if far(b) <= gate and self.looks_like(b, now) is not False
                and (not reseen or score_of(b) >= config.PERSON_LOCK_CONFIDENCE)]
        best = min(near, key=far, default=None)
        if best is None or score_of(best) < config.PERSON_LOCK_CONFIDENCE:
            them = [b for b in boxes if score_of(b) >= config.PERSON_LOCK_CONFIDENCE
                    and self.looks_like(b, now)]
            best = min(them, key=far, default=best)
        return best

    def saw(self, now: float, box, direction: Direction) -> None:
        """They were seen: where, and their colours blended into the memory
        (a fresh memory moves TRACK_LOOK_BLEND of the way; a stale one is
        replaced)."""
        self.direction = direction
        look = getattr(box, "look", None)
        if look is not None:
            fresh = self.look is not None and now - self.look_at <= config.TRACK_LOOK_FRESH_S
            k = config.TRACK_LOOK_BLEND
            self.look = (1 - k) * self.look + k * look if fresh else look
            self.look_at = now
