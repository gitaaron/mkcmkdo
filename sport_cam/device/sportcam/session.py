"""Tag-driven sessions: switching the tag on is the start button.

    tag on ─► idle → tracking (acquiring) ─► locked ─► recording
    tag off ─► … LOST_IDLE_S later … ─► idle (the recording is saved)

The camera ranges all the time, even in standby, so it notices the tag the
moment the wearer powers it. This module decides only *when* to change state.
`Head.apply_state()` still makes every change, so a session started by the
tag looks the same to the app, the ring and the server as one started by
hand.

Rules, in the order they are checked:

* **A session starts on the tag's arrival, not its presence.** The tag must
  have been gone for LOST_IDLE_S first. Stop a session from the app while
  the tag is still on, and the camera stays in standby until the tag has
  been switched off and on again — it does not argue with you.
* **It starts only from idle.** If you are already tracking or recording by
  hand, turning the tag on changes nothing.
* **It records once, on the first lock.** After that, anything the app does
  (drop back to tracking, say) stands.
* **It ends the way every session ends:** no ranges for LOST_IDLE_S, and the
  control loop drops to idle (5 s by default). A tag switched off and a tag
  hidden behind a body look the same, so a long enough dropout ends the
  session too — and the tag reappearing then starts a fresh one.
"""
from __future__ import annotations

from . import config


class AutoSession:
    def __init__(self) -> None:
        self.active = False           # this session was started by the tag
        self._present = False         # the tag is on, as far as we can tell
        self._armed = True            # the next arrival may start a session
        self._recorded = False        # this session has already gone to recording
        self._ranging_since: float | None = None

    def update(self, now: float, frame_age_s: float, state: str, locked: bool) -> str | None:
        """One tick. Returns a state to apply, or None to leave things alone.

        `frame_age_s` is how long since the last ranging frame, whatever the
        camera state; `locked` comes from the tracker.
        """
        # --- presence, debounced in both directions -----------------------
        if frame_age_s < 0.5:
            if self._ranging_since is None:
                self._ranging_since = now
            if now - self._ranging_since >= config.TAG_PRESENT_S:
                self._present = True
        else:
            self._ranging_since = None
            if frame_age_s >= config.LOST_IDLE_S:
                self._present = False
                self._armed = True    # gone long enough: the next arrival counts

        # --- a session ended, by whatever route ----------------------------
        if state in ("idle", "off"):
            self.active = False
            self._recorded = False

        if not config.AUTO_SESSION:
            return None

        # --- start ---------------------------------------------------------
        if self._present and self._armed:
            self._armed = False       # this arrival is used up either way
            if state == "idle":
                self.active = True
                return "tracking"

        # --- acquired → record, once ---------------------------------------
        if self.active and not self._recorded and state == "tracking" and locked:
            self._recorded = True
            return "recording"
        return None

    @property
    def tag_present(self) -> bool:
        return self._present
