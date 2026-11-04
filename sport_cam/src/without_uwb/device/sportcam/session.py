"""Session rules: track starts a search; the person found is followed.

    awake ─(app: track)─► tracking (search → found → following)
    tracking ─(app: record)─► recording ─(app: stop)─► tracking
    tracking, nobody found for SEARCH_GIVE_UP_S ─► awake

This module decides only *when* to change state on the device's own
initiative. `Head.apply_state()` still makes every change, so a session
advanced here looks the same to the app, the ring and the server as one the
user drove by hand.

Rules:

* **It never records by itself.** Recording starts only on the app's Record,
  from tracking; Stop goes back to tracking, still following.
* **It gives up on an empty room.** Tracking, and SEARCH_GIVE_UP_S of
  sweeping without finding anyone, the camera goes back to awake. A recording
  is never abandoned this way — losing and re-finding people is normal
  there, and stopping it is the user's call.
"""
from __future__ import annotations

from . import config


class AutoSession:
    def update(self, state: str, searching_for_s: float) -> str | None:
        """One tick. Returns a state to apply, or None to leave things alone."""
        if state != "tracking":
            return None
        if searching_for_s > config.SEARCH_GIVE_UP_S:
            return "awake"
        return None
