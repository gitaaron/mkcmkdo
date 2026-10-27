"""Tag-driven sessions: switching the tag on is the start button.

    tag on ─► awake or sleep → tracking (search → found, 3 s) ─► recording
    tag off ─► … LOST_END_S later … ─► awake (the recording is saved)

The camera ranges all the time, even in standby, so it notices the tag the
moment the wearer powers it. This module decides only *when* to change state.
`Head.apply_state()` still makes every change, so a session started by the
tag looks the same to the app, the ring and the server as one started by
hand.

Rules, in the order they are checked:

* **A session starts on the tag's arrival, not its presence.** The tag must
  have been gone for LOST_END_S first. Stop a session from the app while
  the tag is still on, and the camera stays in standby until the tag has
  been switched off and on again — it does not argue with you.
* **It starts only from awake or sleep.** The radios keep ranging in sleep,
  so the tag wakes the camera straight into a session. If you are already
  tracking or recording by hand, turning the tag on changes nothing.
* **It records once the person has been found for FOUND_CONFIRM_S**,
  however the session started (tag or app). Stopping the recording ends the
  session: the camera goes back to awake.
* **It ends the way every session ends:** no ranges for LOST_END_S, and the
  control loop drops to awake (5 s by default). A tag switched off and a tag
  hidden behind a body look the same, so a long enough dropout ends the
  session too — and the tag reappearing then starts a fresh one.
* **Each tag is its own.** Several tags can be on at once (one per climber
  waiting their turn); presence and arming are kept per tag, and `tag` says
  which one started the session, for the camera to follow and to look up
  whose it is. Only a tag `startable` allows starts one — with
  TAG_NEEDS_PAIRING, one paired to a phone (pairing.py). An unpaired tag's
  arrival is used up all the same, so pairing a tag that is already on does
  not start a session out of the blue.
"""
from __future__ import annotations

from typing import Callable

from . import config


class AutoSession:
    def __init__(self) -> None:
        self.active = False           # this session was started by a tag
        self.tag: int | None = None   # …this one
        self.startable: Callable[[int | None], bool] = lambda _tag: True
        self._present: set[int | None] = set()      # tags on, as far as we can tell
        self._disarmed: set[int | None] = set()     # tags whose arrival is used up
        self._ranging_since: dict[int | None, float] = {}

    def update(self, now: float, ages: dict[int, float] | float, state: str,
               ready: bool) -> str | None:
        """One tick. Returns a state to apply, or None to leave things alone.

        `ages` is how long since each tag's last ranging frame, whatever the
        camera state (`UwbArray.tag_ages()`); a bare number is one unnamed
        tag. `ready` is the tracker's `ready_to_record`.
        """
        if not isinstance(ages, dict):
            ages = {None: ages}
        # --- presence, debounced in both directions, per tag ---------------
        for tag, age in ages.items():
            if age < 0.5:
                since = self._ranging_since.setdefault(tag, now)
                if now - since >= config.TAG_PRESENT_S:
                    self._present.add(tag)
            else:
                self._ranging_since.pop(tag, None)
                if age >= config.LOST_END_S:
                    self._present.discard(tag)
                    self._disarmed.discard(tag)   # gone long enough: the next arrival counts

        # --- a session ended, by whatever route ----------------------------
        if state in ("awake", "sleep"):
            self.active = False
            self.tag = None

        # --- found for FOUND_CONFIRM_S → record ----------------------------
        if state == "tracking" and ready:
            return "recording"

        if not config.AUTO_SESSION:
            return None

        # --- start ---------------------------------------------------------
        for tag in sorted(self._present - self._disarmed, key=lambda t: (t is None, t or 0)):
            self._disarmed.add(tag)   # this arrival is used up either way
            if state in ("awake", "sleep") and self.startable(tag):
                self.active = True
                self.tag = tag
                return "tracking"
        return None

    @property
    def tag_present(self) -> bool:
        """Any tag is on."""
        return bool(self._present)
