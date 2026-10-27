"""Session flow: track / record → search → found (3 s) → recording → awake.

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
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.dirname(__file__))

from sportcam import config, owners
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
    check("awake: nothing happens", s.update("awake", False, 0.0) is None)
    check("tracking, still searching: nothing yet", s.update("tracking", False, 5.0) is None)
    check("found for FOUND_CONFIRM_S → recording", s.update("tracking", True, 0.0) == "recording")
    check("recording: left alone", s.update("recording", False, 0.0) is None)
    check("empty-room timeout never ends a recording",
          s.update("recording", False, 9999.0) is None)
    check("nobody found for SEARCH_GIVE_UP_S → awake",
          s.update("tracking", False, config.SEARCH_GIVE_UP_S + 1) == "awake")


# ---- fakes for the full flow --------------------------------------------------
class FakeRing:
    def __init__(self):
        self.state, self.lost, self.warn = "awake", False, False
        self.awake_person, self.searching, self.found = False, False, None

    def set_state(self, s):
        self.state = s


class FakeLocal:
    def __init__(self):
        self.sent: list[dict] = []
        self.viewers = 0

    async def broadcast(self, msg):
        self.sent.append(msg)

    def last_boxes(self):
        return next((m for m in reversed(self.sent) if m.get("type") == "boxes"), None)

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
        self.no_detector = None

    def start_recording(self):
        self.recording = True
        return "/tmp/sportcam-test.mp4"

    def stop_recording(self):
        self.recording = False


def labels(boxes: list) -> set[str]:
    return {b[4] for b in boxes}


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
    main_mod.time = CLOCK              # live boxes are aged on the tracker's clock

    person = Person(55.0, dist=5.0)
    ptz = FakePtz()
    ptz.park = lambda: (ptz.set_pan(0.0), ptz.set_tilt(0.0))    # as the real one: centre
    head = Head.__new__(Head)
    head.state = "awake"
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
    head._near_focus = False
    head._tasks = set()
    head._boxes_sent_at = None
    head._jog, head._jog_at = (0.0, 0.0), float("-inf")
    head.session_hash = None
    owner = "c0" * 32                   # the hash of the secret the app was handed
    if os.path.exists("/tmp/sportcam-test.owner"):
        os.remove("/tmp/sportcam-test.owner")
    head._awake_since = CLOCK.t
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
    check("awake: camera does not move", head.ptz.pan_deg == 0.0 and head.state == "awake")
    check("awake sub-state: no person in frame (they are outside the wide view)",
          head.phase == "no-person-in-frame", f"{head.phase}")

    # --- no person detector on this install (an OpenCV without HOG) ---------------
    head.camera.no_detector = "OpenCV 5.0.0 has no person detector (HOG)"
    head.local.sent.clear()
    await head.apply_state("tracking")
    check("no person detector: a session is refused, the camera stays awake",
          head.state == "awake", head.state)
    check("…and the apps are told why",
          any(m.get("type") == "warning" and m.get("code") == "no-detector"
              and "HOG" in m.get("reason", "") for m in head.local.sent), f"{head.local.sent}")
    head.camera.no_detector = None

    # --- the app's track / record button -----------------------------------------
    await head.start_session("tracking", owner)
    await head.report_state()
    looks = head.camera.detections
    pans: list[float] = []             # before each tick's look
    await tick_for(2.0, until=lambda: head.camera.detections > looks or pans.append(head.ptz.pan_deg))
    check("pressing track / record → tracking, search: holds still for the first look",
          head.state == "tracking" and head.phase == "search" and max(map(abs, pans)) == 0.0,
          f"pan {pans}")
    await tick_for(0.3)
    check("…nobody in that look: ring chases, camera sweeping",
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
    check("the clip is stamped with whose session it is",
          owners.owner_of("/tmp/sportcam-test.mp4") == owner and head.session_hash == owner)
    await tick_for(2.0)
    check("camera is pointing at the person", abs(head.ptz.pan_deg - person.bearing) < 5.0,
          f"pan {head.ptz.pan_deg:.1f}")
    msg = head.local.last_boxes()
    check("live view: each detection goes to direct viewers, the climber labelled",
          msg is not None and msg["size"] == list(config.PREVIEW_SIZE)
          and labels(msg["boxes"]) == {"climber"}, f"{msg}")

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
    check("stop recording → awake", head.state == "awake" and not head.camera.recording)
    check("…and nobody owns anything any more", head.session_hash is None)
    side = "/tmp/sportcam-test.boxes.json"
    frames = json.load(open(side))["frames"] if os.path.exists(side) else []
    check("the clip's person boxes are saved beside it, the climber labelled",
          any(label == "climber" for _, boxes in frames for *_, label in boxes), f"{frames[:3]}")

    # --- a person who walks off during the countdown -----------------------------------
    person.visible, person.bearing = False, 40.0
    await tick_for(config.AWAKE_PERSON_HOLD_S + 1.0)
    await head.apply_state("tracking")
    person.visible = True
    await tick_for(20, until=lambda: head.phase == "found")
    await tick_for(1.0)
    person.visible = False
    await tick_for(config.FOUND_LOST_S + 0.5)
    check("person gone during found → back to search, not recording",
          head.state == "tracking" and head.phase == "search" and not head.camera.recording,
          f"{seen[-3:]}")
    await head.apply_state("awake")

    # --- an empty room ---------------------------------------------------------------
    config.SEARCH_GIVE_UP_S = 10.0
    person.visible = False
    await head.apply_state("tracking")
    await tick_for(30, until=lambda: head.state == "awake")
    check("nobody there: gives up and goes back to awake, never recorded",
          head.state == "awake" and not head.camera.recording)

    order = [s for s, _ in seen]
    dedup = [s for i, s in enumerate(order) if i == 0 or order[i - 1] != s]
    check("states ran awake → tracking → recording → awake → tracking → awake …",
          dedup[:5] == ["awake", "tracking", "recording", "awake", "tracking"], f"{dedup}")

    # --- someone already in frame when the session starts ------------------------------
    config.SEARCH_GIVE_UP_S = 180.0
    person.visible, person.bearing = True, 15.0
    await tick_for(3.0)
    check("awake sub-state: person in frame; the ring breathes", head.phase == "person-in-frame"
          and head.led.awake_person, f"{head.phase}")
    check("live view: awake boxes are all 'can't tell' (nobody picked yet)",
          head.live_boxes() and labels(head.live_boxes()) == {"unsure"}, f"{head.live_boxes()}")
    head.state = "sleep"
    check("…and none while asleep", head.live_boxes() == [])
    head.state = "awake"
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
    await head.apply_state("awake")

    # --- sleep: awake AWAKE_TIMEOUT_S with no session ------------------------------
    head.local.viewers = 1
    await tick_for(config.AWAKE_TIMEOUT_S + 5.0)
    check("live view open on the stream: stays awake past AWAKE_TIMEOUT_S", head.state == "awake")
    head.local.viewers = 0
    head.cloud.viewer_at = time.time()
    await tick_for(config.AWAKE_TIMEOUT_S + 5.0)
    check("…and while the app watches through Firebase", head.state == "awake")
    head.cloud.viewer_at = 0.0
    t0 = CLOCK.t
    await tick_for(config.AWAKE_TIMEOUT_S + 1.0, until=lambda: head.state == "sleep")
    check("…then sleeps AWAKE_TIMEOUT_S after the viewer leaves",
          head.state == "sleep" and CLOCK.t - t0 >= config.AWAKE_TIMEOUT_S - 0.1, f"{CLOCK.t - t0:.1f}s")
    check("awake AWAKE_TIMEOUT_S with no session → sleep: camera off, parked",
          head.state == "sleep" and not head.camera.awake and head.ptz.pan_deg == 0.0
          and head.led.state == "sleep" and head.phase is None, f"{head.state} {head.phase}")
    person.visible, person.bearing = True, 5.0
    looks = head.camera.detections
    await tick_for(3.0)
    check("…asleep: nothing is looked at, no live view",
          head.camera.detections == looks and head.live_boxes() == [])

    # --- the app's Record from sleep, the person already in front -------------------
    await head.apply_state("tracking")
    check("record from sleep → tracking, search, skipping awake; camera on",
          head.state == "tracking" and head.phase == "search" and head.camera.awake, f"{head.phase}")
    pans = []
    await tick_for(10, until=lambda: (pans.append(head.ptz.pan_deg), head.phase == "found")[1])
    check("…holds still until its first look, then finds them without sweeping",
          head.phase == "found" and max(abs(p) for p in pans) < 0.5,
          f"{head.phase}, pan {min(pans):.1f}..{max(pans):.1f}")
    await tick_for(10, until=lambda: head.state == "recording")
    check("…and records after FOUND_CONFIRM_S", head.state == "recording" and head.camera.recording)
    await head.apply_state("sleep")
    check("Sleep while recording saves the clip and sleeps",
          head.state == "sleep" and not head.camera.recording and not head.camera.awake)

    # --- Record from sleep with nobody in front: look first, then sweep -------------
    person.visible = False
    await head.apply_state("tracking")
    looks = head.camera.detections
    pans, t0 = [], CLOCK.t
    await tick_for(5.0, until=lambda: head.camera.detections > looks or pans.append(head.ptz.pan_deg))
    check("nobody in front: still through the warm-up until its first look",
          head.camera.detections > looks and max(map(abs, pans)) == 0.0
          and CLOCK.t - t0 >= config.CAMERA_WARMUP_S, f"{CLOCK.t - t0:.2f}s, pan {max(pans):.1f}")
    await tick_for(1.0)
    check("…then it sweeps", head.phase == "search" and head.ptz.pan_deg != 0.0,
          f"pan {head.ptz.pan_deg:.1f}")
    await head.apply_state("awake")

    # the app's joystick turns the head in awake, and stops when the app stops sending
    head.ptz.park()
    head.jog(-1.0, 0.5)
    await tick_for(0.2)
    check("joystick: awake, pulled up and left, the head turns left and up",
          head.ptz.jogs > 0 and head.ptz.pan_deg < 0 and head.ptz.tilt_deg > 0,
          f"pan {head.ptz.pan_deg:.1f}, tilt {head.ptz.tilt_deg:.1f}")
    await tick_for(config.JOG_TIMEOUT_S + 0.2)
    held = head.ptz.jogs
    await tick_for(0.3)
    check("…and stops JOG_TIMEOUT_S after the last message", head.ptz.jogs == held,
          f"{head.ptz.jogs - held} more moves")


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


async def switched_off() -> None:
    """The power switch going off: systemd sends SIGTERM, and the recording is
    closed and the head parked before the service exits (docs/04, power latch)."""
    print("\nswitched off while recording")
    import signal
    import sportcam.main as main_mod
    from sportcam.main import Head

    async def no_upload(*a, **k):
        return None
    main_mod.upload_with_retry = no_upload

    class Stub:
        """Accepts any call; records the ones the test asks about."""
        def __init__(self, *coroutines: str):
            self.calls: list[str] = []
            self.coroutines = coroutines

        def __getattr__(self, name):
            def call(*a, **k):
                self.calls.append(name)
                if name in self.coroutines:
                    return asyncio.sleep(0)
                return "/tmp/sportcam-test.mp4" if name == "start_recording" else None
            return call

    head = Head.__new__(Head)
    head.state = "recording"
    head.camera, head.ptz, head.led, head.tracker = Stub(), Stub(), Stub(), Stub()
    head.boxlog, head.local = Stub(), Stub("broadcast")
    head.cloud, head.mdns = Stub("report_state"), Stub("update_state", "stop")
    head._rec_path, head._rec_started = "/tmp/sportcam-test.mp4", main_mod.time.monotonic()
    head._near_focus = False
    head._tasks = set()
    head.session_hash = None

    async def run_forever():
        await asyncio.sleep(3600)
    head.run = run_forever
    asyncio.get_running_loop().call_later(0.1, os.kill, os.getpid(), signal.SIGTERM)
    await asyncio.wait_for(head.serve(), 5.0)
    check("SIGTERM ends serve()", True)
    check("…with the recording stopped", "stop_recording" in head.camera.calls and head.state == "sleep",
          f"{head.state}, camera {head.camera.calls}")
    check("…the head parked and the ring dark", "park" in head.ptz.calls and "park" in head.led.calls)
    check("…and mDNS withdrawn", "stop" in head.mdns.calls)


def main() -> None:
    session_rules()
    asyncio.run(full_flow())
    asyncio.run(switched_off())
    ring_animation()
    print()
    if failures:
        print(f"{len(failures)} check(s) failed: " + ", ".join(failures))
        sys.exit(1)
    print("all session checks passed")


if __name__ == "__main__":
    main()
