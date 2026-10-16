"""Session rules: track / record starts a search, the first lock starts recording.

    idle ─(app: track/record)─► tracking, sweeping ─► locked ─► recording
    tracking, nobody found for SEARCH_GIVE_UP_S ─► idle

This module decides only *when* to change state on the device's own
initiative. `Head.apply_state()` still makes every change, so a session
advanced here looks the same to the app, the ring and the server as one the
user drove by hand.

Rules:

* **It records once, on the first lock** of a session that began in idle, so
  the clip is of the person rather than of an empty room being swept.
  After that, anything the app does stands: stop recording and the camera
  keeps tracking without recording again until the next session.
* **It gives up on an empty room.** Tracking, never locked, never recorded,
  and SEARCH_GIVE_UP_S of sweeping later the camera goes back to idle. A
  recording is never abandoned this way — losing and re-finding people is
  normal there, and stopping it is the user's call.
"""
from __future__ import annotations

from . import config


class AutoSession:
    def __init__(self) -> None:
        self._recorded = False        # this session has already gone to recording

    def update(self, state: str, locked: bool, ever_locked: bool,
               searching_for_s: float) -> str | None:
        """One tick. Returns a state to apply, or None to leave things alone."""
        if state in ("idle", "off"):
            self._recorded = False    # a session ended, by whatever route
            return None

        if (config.AUTO_RECORD_ON_LOCK and state == "tracking"
                and locked and not self._recorded):
            self._recorded = True
            return "recording"
        if state == "recording":
            self._recorded = True     # started by hand: do not start a second

        if (state == "tracking" and not ever_locked
                and searching_for_s > config.SEARCH_GIVE_UP_S):
            return "idle"
        return None
