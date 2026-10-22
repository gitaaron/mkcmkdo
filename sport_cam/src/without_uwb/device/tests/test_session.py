"""Session flow: track / record → search → found (3 s) → recording → idle.

Two layers, neither of which needs a Pi:

  1. AutoSession's rules, called directly;
  2. the whole flow through Head.apply_state() / Head.control_tick(), with the
     simulated world from test_tracker — which is what the LED and the app
     actually see.

    python3 device/tests/test_session.py
"""
from __future__ import annotations

import asyncio
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.dirname(__file__))

from sportcam import config
from sportcam.led import chase, fill
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
    check("idle: nothing happens", s.update("idle", False, 0.0) is None)
    check("tracking, still searching: nothing yet", s.update("tracking", False, 5.0) is None)
    check("found for FOUND_CONFIRM_S → recording", s.update("tracking", True, 0.0) == "recording")
    check("recording: left alone", s.update("recording", False, 0.0) is None)
    check("empty-room timeout never ends a recording",
          s.update("recording", False, 9999.0) is None)
    check("nobody found for SEARCH_GIVE_UP_S → idle",
          s.update("tracking", False, config.SEARCH_GIVE_UP_S + 1) == "idle")


# ---- fakes for the full flow --------------------------------------------------
class FakeRing:
    def __init__(self):
        self.state, self.lost, self.warn = "idle", False, False
        self.idle_person, self.searching, self.found = False, False, None

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

    def telemetry(self):
        return {}


class FakePower:
    def telemetry(self):
        return {}


class RecCamera(SimCamera):
    def __init__(self, ptz, people):
        super().__init__(ptz, people)
        self.recording = False

    def start_recording(self):
        self.recording = True
        return "/tmp/sportcam-test.mp4"

    def stop_recording(self):
        self.recording = False


def countdown_heard(sent: list[int]) -> list[int]:
    """The countdown values the app heard, without repeats or zeros (one beep each)."""
    return [c for i, c in enumerate(sent) if c and (i == 0 or sent[i - 1] != c)]


async def full_flow() -> None:
    print("\nfull flow through Head")
    import sportcam.main as main_mod
    from sportcam.cloud import CloudLink
    from sportcam.boxlog import BoxLog
    from sportcam.main import Head

    async def no_upload(*a, **k):
        return None
    main_mod.upload_with_retry = no_upload

    person = Person(55.0, dist=5.0)
    ptz = FakePtz()
    ptz.park = lambda: (ptz.set_pan(0.0), ptz.set_tilt(0.0))    # as the real one: centre
    head = Head.__new__(Head)
    head.state = "idle"
    head.camera = RecCamera(ptz, [person])
    head.ptz = ptz
    head.tracker = Tracker(head.camera, ptz)
    head.session = AutoSession()
    head.led = FakeRing()
    head.storage = FakeStorage()
    head.power = FakePower()
    head.local = FakeLocal()
    head.mdns = FakeMdns()
    head.cloud = CloudLink(head)       # not connected: writes are no-ops
    head._rec_path, head._rec_started = "", 0.0
    head._countdown_sent = 0
    head.boxlog = BoxLog()

    countdown_sent: list[int] = []     # what the app hears, in order, to beep on
    send = head.send_telemetry

    async def record_send():
        countdown_sent.append(head.telemetry()["countdown"])
        await send()
    head.send_telemetry = record_send

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

    await tick_for(3.0)
    check("idle: camera does not move", head.ptz.pan_deg == 0.0 and head.state == "idle")
    check("idle sub-state: no person in frame (they are outside the wide view)",
          head.phase == "no-person-in-frame", f"{head.phase}")

    # --- the app's track / record button -----------------------------------------
    await head.apply_state("tracking")
    await head.report_state()
    await tick_for(0.3)
    check("pressing track / record → tracking, search: ring chases, camera sweeping",
          head.state == "tracking" and head.phase == "search" and head.led.searching
          and head.ptz.pan_deg != 0.0, f"{seen}")
    check("not recording while it has found nobody", not head.camera.recording)

    await tick_for(20, until=lambda: head.phase == "found")
    check("person seen → found: ring fills, countdown starts",
          head.phase == "found" and not head.led.searching and head.led.found is not None
          and head.telemetry()["countdown"] == 3, f"{seen[-2:]} {head.telemetry()['countdown']}")
    t0 = CLOCK.t
    await tick_for(10, until=lambda: head.state == "recording")
    check("…still in frame FOUND_CONFIRM_S later → recording",
          head.state == "recording" and head.camera.recording
          and abs(CLOCK.t - t0 - config.FOUND_CONFIRM_S) < 0.2, f"{CLOCK.t - t0:.2f}s")
    check("the app heard 3, 2, 1 (one beep each)", countdown_heard(countdown_sent) == [3, 2, 1],
          f"{countdown_sent}")
    check("phase is track; countdown back to 0",
          head.phase == "track" and head.telemetry()["countdown"] == 0)
    await tick_for(2.0)
    check("camera is pointing at the person", abs(head.ptz.pan_deg - person.bearing) < 5.0,
          f"pan {head.ptz.pan_deg:.1f}")

    # --- they walk off: recording continues, camera sweeps again --------------------
    person.visible = False
    await tick_for(config.LOST_HOLD_S + 0.5)
    check("person missing: ring flashes", head.led.lost)
    await tick_for(config.RESEARCH_AFTER_S + 1.0)
    check("…then it searches again, still recording (the app pings)",
          head.state == "recording" and head.phase == "search" and head.camera.recording,
          f"{seen[-3:]}")
    person.visible, person.bearing = True, -30.0
    await tick_for(30, until=lambda: head.phase == "track")
    check("…and picks them up again, no new countdown", head.phase == "track")

    # --- stop recording: the session ends --------------------------------------------
    await head.apply_state("tracking")          # what an older app sends
    check("stop recording → idle", head.state == "idle" and not head.camera.recording)
    side = "/tmp/sportcam-test.boxes.json"
    frames = json.load(open(side))["frames"] if os.path.exists(side) else []
    check("the clip's person boxes are saved beside it, the climber labelled",
          any(label == "climber" for _, boxes in frames for *_, label in boxes), f"{frames[:3]}")

    # --- a person who walks off during the countdown -----------------------------------
    person.visible, person.bearing = False, 40.0
    await tick_for(config.IDLE_PERSON_HOLD_S + 1.0)
    await head.apply_state("tracking")
    person.visible = True
    await tick_for(20, until=lambda: head.phase == "found")
    await tick_for(1.0)
    person.visible = False
    await tick_for(config.FOUND_LOST_S + 0.5)
    check("person gone during found → back to search, not recording",
          head.state == "tracking" and head.phase == "search" and not head.camera.recording,
          f"{seen[-3:]}")
    await head.apply_state("idle")

    # --- an empty room ---------------------------------------------------------------
    config.SEARCH_GIVE_UP_S = 10.0
    person.visible = False
    await head.apply_state("tracking")
    await tick_for(30, until=lambda: head.state == "idle")
    check("nobody there: gives up and goes back to idle, never recorded",
          head.state == "idle" and not head.camera.recording)

    order = [s for s, _ in seen]
    dedup = [s for i, s in enumerate(order) if i == 0 or order[i - 1] != s]
    check("states ran idle → tracking → recording → idle → tracking → idle …",
          dedup[:5] == ["idle", "tracking", "recording", "idle", "tracking"], f"{dedup}")

    # --- someone already in frame when the session starts ------------------------------
    config.SEARCH_GIVE_UP_S = 180.0
    person.visible, person.bearing = True, 15.0
    await tick_for(3.0)
    check("idle sub-state: person in frame; the ring breathes", head.phase == "person-in-frame"
          and head.led.idle_person, f"{head.phase}")
    await head.apply_state("tracking")
    check("track / record with a person in frame → found, the sweep is skipped",
          head.tracker.mode == "found" and head.phase == "found", head.tracker.mode)
    pans: list[float] = []
    t0 = CLOCK.t
    await tick_for(10, until=lambda: (pans.append(head.ptz.pan_deg), head.state == "recording")[1])
    check("…records after FOUND_CONFIRM_S, never sweeping away",
          head.state == "recording" and CLOCK.t - t0 < config.FOUND_CONFIRM_S + 0.2
          and min(pans) >= -0.5 and max(pans) <= person.bearing + 5.0,
          f"{CLOCK.t - t0:.1f}s, pan {min(pans):.1f}..{max(pans):.1f}")
    await head.apply_state("idle")


def ring_animation() -> None:
    print("\nring")
    frame = chase((0, 200, 0), 0.25, 16)
    check("search: the chase lights every pixel", len(frame) == 16)
    check("…with one bright head and a dim base",
          max(frame)[1] == 200 and min(frame)[1] < 40, f"{frame}")
    check("…and it moves", chase((0, 200, 0), 0.5, 16) != frame)
    lit = lambda f: sum(1 for c in f if c[1] == 200)
    check("found: the ring fills as the countdown runs",
          lit(fill((0, 200, 0), 0.0, 16)) == 1 and lit(fill((0, 200, 0), 0.5, 16)) == 8
          and lit(fill((0, 200, 0), 1.0, 16)) == 16)


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
