"""Zoom framing: how big the followed person should be in the picture.

One job, with no camera or lens behind it: given the person's box, when it
was seen and whether the lens was moving, say by how much the focal length
should change, if at all. Both trackers use it; each applies the step to its
own zoom and says when the lens took it (`moved`).

Boxes are padded (detector.py: the body is PERSON_IN_BOX_H of the box's
height and PERSON_IN_BOX_W of its width); the fill is measured on the body.

* **guard** — the body is near an edge of the frame, or fills more than
  ZOOM_GUARD_FILL: zoom out a step (ZOOM_GUARD_STEP), as soon as the lens
  may move again (ZOOM_RATE_LIMIT_S after the last framing move). The
  detector's boxes stop at the frame's edge, so a body running off it shows
  as a box against the edge; this acts on the approach, and it wins.
* **fill loop** — otherwise, the fill off ZOOM_FILL_TARGET by more than
  ZOOM_FILL_DEADBAND for ZOOM_FILL_HOLD_S (a step back and forward doesn't
  count): move part of the way to the target (ZOOM_VISION_GAIN, in log space
  so in and out behave alike), then wait ZOOM_TRACK_DWELL_S, which leaves
  autofocus its turn between moves.

A correction is worked out once per lens move, from a picture of the lens at
rest: adding one up per detection, while the lens hasn't moved yet, overshoots
by several times.
"""
from __future__ import annotations

from . import config


class Framing:
    def __init__(self) -> None:
        self.reset()

    def reset(self) -> None:
        """A new search: no move to wait out, nothing off target yet."""
        self._moved_at = float("-inf")           # the last framing move the lens took
        self._off_since: float | None = None     # off target since, for the fill loop

    def moved(self, now: float) -> None:
        """The lens took a framing move at `now`: the next waits its turn."""
        self._moved_at = now
        self._off_since = None

    def step(self, now: float, box, lens_moving: bool) -> float | None:
        """What to multiply the focal length by for this sighting of the
        person, or None to leave the zoom alone. Call `moved` if the lens
        takes it; if it doesn't, the next sighting asks again."""
        if lens_moving:
            # a picture taken while the lens moves says nothing about the next move
            self._off_since = None
            return None
        x, y, w, h = box
        pw, ph = config.PREVIEW_SIZE
        bw, bh = w * config.PERSON_IN_BOX_W, h * config.PERSON_IN_BOX_H
        cx, cy = x + w / 2, y + h / 2
        left, right, top, bottom = cx - bw / 2, cx + bw / 2, cy - bh / 2, cy + bh / 2
        fill = max(bh / ph, bw / pw, 1e-3)
        ex, ey = config.ZOOM_GUARD_EDGE * pw, config.ZOOM_GUARD_EDGE * ph
        near_edge = left < ex or top < ey or right > pw - ex or bottom > ph - ey
        since_move = now - self._moved_at
        if near_edge or fill > config.ZOOM_GUARD_FILL:
            return config.ZOOM_GUARD_STEP if since_move >= config.ZOOM_RATE_LIMIT_S else None
        if abs(fill / config.ZOOM_FILL_TARGET - 1.0) <= config.ZOOM_FILL_DEADBAND:
            self._off_since = None               # not for every small change: each
            return None                          # zoom move costs a refocus
        if self._off_since is None:
            self._off_since = now
        if (now - self._off_since < config.ZOOM_FILL_HOLD_S
                or since_move < config.ZOOM_TRACK_DWELL_S):
            return None
        return (config.ZOOM_FILL_TARGET / fill) ** config.ZOOM_VISION_GAIN
