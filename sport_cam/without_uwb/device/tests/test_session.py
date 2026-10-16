"""Session flow: track / record → sweep → lock → recording.

Two layers, neither of which needs a Pi:

  1. AutoSession's rules, called directly;
  2. the whole flow through Head.apply_state() / Head.control_tick(), with the
     simulated world from test_tracker — which is what the LED and the app
     actually see.

    python3 device/tests/test_session.py
"""
from __future__ import annotations

import asyncio
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.dirname(__file__))

from sportcam import config
from sportcam.led import chase
from sportcam.session import AutoSession
from sportcam.tracker import Tracker
import test_tracker as tt
from test_tracker import CLOCK, FakePtz, Person, SimCamera

failures: list[str] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    print(f"  {'PASS' if ok else 'FAIL'}  {name}" + (f"  ({detail})" if detail and not ok else ""))
    if not ok:
        failures.append(name)


def session_rules() -> None:
    print("session rules")
    s = AutoSession()
    check("idle: nothing happens", s.update("idle", False, False, 0.0) is None)
    check("tracking, still sweeping: nothing yet", s.update("tracking", False, False, 5.0) is None)
    check("first lock → recording", s.update("tracking", True, True, 0.0) == "recording")
    check("…only once", s.update("tracking", True, True, 0.0) is None)
    check("recording: left alone", s.update("recording", True, True, 0.0) is None)
    check("empty-room timeout never ends a recording",
          s.update("recording", False, False, 9999.0) is None)

    s = AutoSession()
    s.update("tracking", True, True, 0.0)
    s.update("recording", True, True, 0.0)
    check("user stops recording: camera keeps tracking, does not restart",
          s.update("tracking", True, True, 0.0) is None)
    s.update("idle", False, False, 0.0)
    check("a new session records again", s.update("tracking", True, True, 0.0) == "recording")

    s = AutoSession()
    check("recorded by hand first: no second recording",
          (s.update("recording", False, False, 0.0), s.update("tracking", True, True, 0.0))
          == (None, None))

    s = AutoSession()
    check("nobody found for SEARCH_GIVE_UP_S → idle",
          s.update("tracking", False, False, config.SEARCH_GIVE_UP_S + 1) == "idle")
    check("…but not if someone was found earlier in the session",
          s.update("tracking", False, True, config.SEARCH_GIVE_UP_S + 1) is None)

    config.AUTO_RECORD_ON_LOCK = False
    s = AutoSession()
    check("AUTO_RECORD_ON_LOCK = False → recording is a separate tap",
          s.update("tracking", True, True, 0.0) is None)
    config.AUTO_RECORD_ON_LOCK = True


# ---- fakes for the full flow --------------------------------------------------
class FakeRing:
    def __init__(self):
        self.state, self.lost, self.acquiring, self.warn = "idle", False, False, False

    def set_state(self, s):
        self.state = s


class FakeLocal:
    async def broadcast(self, msg):
        pass

    def state_payload(self):
        return {}


class FakeMdns:
    async def update_state(self, s):
        pass


class FakeStorage:
    def can_record(self):
        return True


class RecCamera(SimCamera):
    def __init__(self, ptz, people):
        super().__init__(ptz, people)
        self.recording = False

    def start_recording(self):
        self.recording = True
        return "/tmp/sportcam-test.mp4"

    def stop_recording(self):
        self.recording = False


async def full_flow() -> None:
    print("\nfull flow through Head")
    import sportcam.main as main_mod
    from sportcam.main import Head

    async def no_upload(*a, **k):
        return None
    main_mod.upload_with_retry = no_upload

    person = Person(55.0, dist=5.0)
    ptz = FakePtz()
    head = Head.__new__(Head)
    head.state = "idle"
    head.camera = RecCamera(ptz, [person])
    head.ptz = ptz
    head.tracker = Tracker(head.camera, ptz)
    head.session = AutoSession()
    head.led = FakeRing()
    head.storage = FakeStorage()
    head.local = FakeLocal()
    head.mdns = FakeMdns()
    head.ws = None
    head._rec_path, head._rec_started = "", 0.0

    seen: list[tuple[str, str | None]] = []

    async def tick_for(seconds: float, until=None) -> None:
        end = CLOCK.t + seconds
        while CLOCK.t < end:
            CLOCK.t += 0.05
            await head.control_tick()
            point = (head.state, head.phase)
            if not seen or seen[-1] != point:
                seen.append(point)
            if until and until():
                return

    await tick_for(1.0)
    check("idle: camera does not move", head.ptz.pan_deg == 0.0 and head.state == "idle")

    # --- the app's track / record button -----------------------------------------
    await head.apply_state("tracking")
    await head.report_state()
    await tick_for(1.0)
    check("pressing track / record → tracking, ring shows acquiring, camera sweeping",
          head.state == "tracking" and head.led.acquiring and head.ptz.pan_deg != 0.0,
          f"{seen}")
    check("not recording while it has found nobody", not head.camera.recording)

    await tick_for(20, until=lambda: head.state == "recording")
    await tick_for(1.0)
    check("first person found → recording starts by itself",
          head.state == "recording" and head.camera.recording, f"{seen}")
    check("ring is no longer acquiring; phase is acquired",
          not head.led.acquiring and head.phase == "acquired")
    check("camera is pointing at the person", abs(head.ptz.pan_deg - person.bearing) < 5.0,
          f"pan {head.ptz.pan_deg:.1f}")

    # --- they walk off: recording continues, camera sweeps again --------------------
    person.visible = False
    await tick_for(config.LOST_HOLD_S + 0.5)
    check("person missing: ring flashes", head.led.lost)
    await tick_for(config.RESEARCH_AFTER_S + 1.0)
    check("…then it searches again, still recording",
          head.state == "recording" and head.phase == "acquiring" and head.camera.recording,
          f"{seen[-3:]}")
    person.visible, person.bearing = True, -30.0
    await tick_for(30, until=lambda: head.phase == "acquired")
    check("…and picks them up again", head.phase == "acquired")

    # --- stop recording: tracking carries on, no second clip ----------------------
    await head.apply_state("tracking")
    await tick_for(2.0)
    check("stop recording → tracking continues, recording does not restart",
          head.state == "tracking" and not head.camera.recording)

    await head.apply_state("idle")
    check("stop tracking → idle", head.state == "idle" and not head.camera.recording)

    # --- an empty room ---------------------------------------------------------------
    config.SEARCH_GIVE_UP_S = 10.0
    person.visible = False
    await head.apply_state("tracking")
    await tick_for(30, until=lambda: head.state == "idle")
    check("nobody there: gives up and goes back to idle, never recorded",
          head.state == "idle" and not head.camera.recording)

    order = [s for s, _ in seen]
    dedup = [s for i, s in enumerate(order) if i == 0 or order[i - 1] != s]
    check("states ran idle → tracking → recording → tracking → idle",
          dedup == ["idle", "tracking", "recording", "tracking", "idle"], f"{dedup}")


def ring_animation() -> None:
    print("\nring")
    frame = chase((0, 200, 0), 0.25, 16)
    check("acquiring chase lights every pixel", len(frame) == 16)
    check("…with one bright head and a dim base",
          max(frame)[1] == 200 and min(frame)[1] < 40, f"{frame}")
    check("…and it moves", chase((0, 200, 0), 0.5, 16) != frame)


def main() -> None:
    session_rules()
    asyncio.run(full_flow())
    ring_animation()
    print()
    if failures:
        print(f"{len(failures)} check(s) failed: " + ", ".join(failures))
        sys.exit(1)
    print("all session checks passed")


if __name__ == "__main__":
    main()
