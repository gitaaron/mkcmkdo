"""Session rules: track / record starts a search; a person found for
FOUND_CONFIRM_S starts recording.

    idle ─(app: track/record)─► tracking (search → found, 3 s) ─► recording
    tracking, nobody found for SEARCH_GIVE_UP_S ─► idle
    recording ─(app: stop recording)─► idle

This module decides only *when* to change state on the device's own
initiative. `Head.apply_state()` still makes every change, so a session
advanced here looks the same to the app, the ring and the server as one the
user drove by hand.

Rules:

* **It records once the person has been found for FOUND_CONFIRM_S**, so the
  clip is of the person rather than of an empty room being swept. Stopping
  the recording ends the session: the camera goes back to idle.
* **It gives up on an empty room.** Tracking, and SEARCH_GIVE_UP_S of
  sweeping without finding anyone, the camera goes back to idle. A recording
  is never abandoned this way — losing and re-finding people is normal
  there, and stopping it is the user's call.
"""
from __future__ import annotations

from . import config


class AutoSession:
    def update(self, state: str, ready: bool, searching_for_s: float) -> str | None:
        """One tick. Returns a state to apply, or None to leave things alone.

        `ready` is the tracker's `ready_to_record`.
        """
        if state != "tracking":
            return None
        if ready:
            return "recording"
        if searching_for_s > config.SEARCH_GIVE_UP_S:
            return "idle"
        return None
