"""Tag-driven sessions: switching the tag on is the start button.

    tag on ─► idle → tracking (search → found, 3 s) ─► recording
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
* **It records once the person has been found for FOUND_CONFIRM_S**,
  however the session started (tag or app). Stopping the recording ends the
  session: the camera goes back to idle.
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
        self._ranging_since: float | None = None

    def update(self, now: float, frame_age_s: float, state: str, ready: bool) -> str | None:
        """One tick. Returns a state to apply, or None to leave things alone.

        `frame_age_s` is how long since the last ranging frame, whatever the
        camera state; `ready` is the tracker's `ready_to_record`.
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

        # --- found for FOUND_CONFIRM_S → record ----------------------------
        if state == "tracking" and ready:
            return "recording"

        if not config.AUTO_SESSION:
            return None

        # --- start ---------------------------------------------------------
        if self._present and self._armed:
            self._armed = False       # this arrival is used up either way
            if state == "idle":
                self.active = True
                return "tracking"
        return None

    @property
    def tag_present(self) -> bool:
        return self._present
