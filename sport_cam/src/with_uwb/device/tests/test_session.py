"""Tag-driven sessions: tag on → search → found (3 s) → recording; tag off → standby.

Three layers, none of which needs a Pi:

  1. AutoSession's rules, on a synthetic clock;
  2. the tracker's search / found rules, against the fakes from test_tracker;
  3. the whole flow through Head.control_tick(), with fake hardware, which
     is what the LED and the app actually see.

    python3 device/tests/test_session.py
"""
from __future__ import annotations

import asyncio
import math
import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.dirname(__file__))

from sportcam import config
from sportcam.led import chase, fill
from sportcam.session import AutoSession
from sportcam.tracker import Tracker
from test_tracker import FakeCamera, FakePtz, FakeUwb

failures: list[str] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    print(f"  {'PASS' if ok else 'FAIL'}  {name}" + (f"  ({detail})" if detail and not ok else ""))
    if not ok:
        failures.append(name)


GONE = float("inf")


def run_session(s: AutoSession, steps, state="idle", ready=False):
    """Feed (now, frame_age) pairs; return the states it asked for."""
    asked = []
    for now, age in steps:
        want = s.update(now, age, state, ready)
        if want:
            asked.append(want)
            state = want
    return asked, state


def session_rules() -> None:
    print("session rules")
    present = config.TAG_PRESENT_S

    s = AutoSession()
    asked, _ = run_session(s, [(t / 20, GONE) for t in range(100)])
    check("no tag → stays in standby", asked == [])

    s = AutoSession()
    asked, _ = run_session(s, [(t / 20, 0.05) for t in range(int(present * 20) - 2)])
    check("a moment of ranging is not 'on' yet", asked == [])
    asked, state = run_session(s, [(present + t / 20, 0.05) for t in range(5)])
    check("tag on → tracking", asked == ["tracking"] and s.active, f"{asked}")

    check("search / found: no recording before FOUND_CONFIRM_S",
          s.update(2.0, 0.05, "tracking", False) is None)
    check("found for FOUND_CONFIRM_S → recording", s.update(2.1, 0.05, "tracking", True) == "recording")

    # a body in the way for a few seconds changes nothing
    check("a short gap does not end or restart anything",
          s.update(5.0, config.LOST_IDLE_S * 0.8, "recording", True) is None and s.active)

    # tag switched off: the control loop drops to idle after LOST_IDLE_S
    s.update(40.0, config.LOST_IDLE_S + 1, "idle", False)
    check("tag off → session over", not s.active and not s.tag_present)
    asked, _ = run_session(s, [(60 + t / 20, 0.05) for t in range(40)])
    check("tag back on → a new session", asked == ["tracking"], f"{asked}")

    # stopped from the app with the tag still on: do not argue
    s = AutoSession()
    run_session(s, [(t / 20, 0.05) for t in range(40)])
    asked, _ = run_session(s, [(2 + t / 20, 0.05) for t in range(100)], state="idle")
    check("stopped from the app → stays stopped while the tag stays on", asked == [])
    short = config.LOST_IDLE_S * 0.6
    run_session(s, [(10 + t / 10, short * t / 5) for t in range(6)], state="idle")
    asked, _ = run_session(s, [(20 + t / 20, 0.05) for t in range(40)])
    check("…and a short off/on does not restart it", asked == [])
    s.update(60.0, config.LOST_IDLE_S, "idle", False)
    asked, _ = run_session(s, [(70 + t / 20, 0.05) for t in range(40)])
    check("…but off for LOST_IDLE_S and on again does", asked == ["tracking"])

    # manual sessions: the tag starts nothing, but found → record still applies
    s = AutoSession()
    asked, _ = run_session(s, [(t / 20, 0.05) for t in range(40)], state="tracking")
    check("tag on during a manual session → no change", asked == [])
    check("…and a manual session records once found for FOUND_CONFIRM_S",
          s.update(3.0, 0.05, "tracking", True) == "recording")

    config.AUTO_SESSION = False
    s = AutoSession()
    asked, _ = run_session(s, [(t / 20, 0.05) for t in range(40)])
    check("AUTO_SESSION = False → the tag starts nothing", asked == [])
    check("…but found still records", s.update(3.0, 0.05, "tracking", True) == "recording")
    config.AUTO_SESSION = True


def run_tracker(tr: Tracker, seconds: float, until=None) -> float:
    t0 = time.monotonic()
    while time.monotonic() - t0 < seconds:
        tr.step()
        if until and until():
            break
        time.sleep(0.005)
    return time.monotonic() - t0


def tracker_found() -> None:
    print("\ntracker search / found")
    confirm_s, config.FOUND_CONFIRM_S = config.FOUND_CONFIRM_S, 0.6
    config.ACQUIRE_SETTLE_S = 0.1
    config.ACQUIRE_STALLED_S = 0.6
    pw, ph = config.PREVIEW_SIZE
    centred = (pw // 2 - 50, ph // 2 - 100, 100, 200)
    off_centre = (int(pw * 0.8), ph // 2 - 100, 100, 200)

    ptz = FakePtz()
    tr = Tracker(FakeUwb(theta_deg=40.0), FakeCamera(centred), ptz)
    tr.step()
    check("still SEARCH while turning toward the tag", tr.mode == "search", tr.mode)
    took = run_tracker(tr, 3.0, until=lambda: tr.mode == "found")
    check("FOUND once on target and the detector sees someone", tr.mode == "found",
          f"{took:.2f}s")
    check("…countdown starts", tr.countdown == math.ceil(config.FOUND_CONFIRM_S), f"{tr.countdown}")
    check("…not ready yet", not tr.ready_to_record)
    run_tracker(tr, config.FOUND_CONFIRM_S + 0.1)
    check("still seen FOUND_CONFIRM_S later → ready to record", tr.ready_to_record)
    tr.confirm()
    check("confirm() → TRACK, countdown 0", tr.mode == "track" and tr.countdown == 0)

    tr2 = Tracker(FakeUwb(theta_deg=10.0), FakeCamera(None), FakePtz())
    run_tracker(tr2, 1.5)
    check("no detection → never found on ranging alone", tr2.mode == "search")
    check("…and after ACQUIRE_STALLED_S it reports it cannot see anyone",
          tr2.acquire_stalled)

    tr3 = Tracker(FakeUwb(theta_deg=10.0), FakeCamera(off_centre), FakePtz())
    run_tracker(tr3, 1.5, until=lambda: tr3.ready_to_record)
    check("a person off-centre is still found and recorded (no centring needed)",
          tr3.ready_to_record)

    tr4 = Tracker(FakeUwb(theta_deg=170.0), FakeCamera(centred), FakePtz())
    run_tracker(tr4, 4.0, until=lambda: tr4.mode == "found")
    check("subject past the soft limit: found from the limit", tr4.mode == "found")

    tr4.reset_lock()
    check("reset_lock → back to SEARCH", tr4.mode == "search", tr4.mode)

    cam5 = FakeCamera(centred)
    tr5 = Tracker(FakeUwb(theta_deg=5.0), cam5, FakePtz())
    run_tracker(tr5, 3.0, until=lambda: tr5.mode == "found")
    cam5._bbox = None
    run_tracker(tr5, config.FOUND_LOST_S + 0.3)
    check("FOUND with nobody seen for FOUND_LOST_S → SEARCH, countdown reset",
          tr5.mode == "search" and tr5.countdown == 0, tr5.mode)

    cam6 = FakeCamera(centred)
    tr6 = Tracker(FakeUwb(theta_deg=5.0), cam6, FakePtz())
    tr6.watch_idle()
    check("idle: a person in frame is noticed", tr6.idle_person_in_frame)
    tr6.reset_lock()
    check("a session started with a person in frame begins in FOUND",
          tr6.mode == "found" and not tr6.idle_person_in_frame, tr6.mode)
    config.FOUND_CONFIRM_S = confirm_s


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


class SwitchableUwb(FakeUwb):
    """A tag that can be switched on and off."""
    def __init__(self):
        super().__init__(theta_deg=20.0)
        self.on_since: float | None = None
        self.off_at: float | None = None

    def fix(self):
        return self.fix_value if self.on_since is not None else None

    def frame_age(self):
        if self.on_since is not None:
            return 0.0
        return GONE if self.off_at is None else time.monotonic() - self.off_at


class FakeRecCamera(FakeCamera):
    def __init__(self, bbox):
        super().__init__(bbox)
        self.recording = False

    def start_recording(self):
        self.recording = True
        return "/tmp/sportcam-test.mp4"

    def stop_recording(self):
        self.recording = False

    def set_detect_fps(self, fps):
        pass


def countdown_heard(sent: list[int]) -> list[int]:
    """The countdown values the app heard, without repeats or zeros (one beep each)."""
    return [c for i, c in enumerate(sent) if c and (i == 0 or sent[i - 1] != c)]


async def full_flow() -> None:
    print("\nfull flow through Head.control_tick()")
    import sportcam.main as main_mod
    from sportcam.cloud import CloudLink
    from sportcam.main import Head

    async def no_upload(*a, **k):
        return None
    main_mod.upload_with_retry = no_upload

    config.TAG_PRESENT_S = 0.1
    config.ACQUIRE_SETTLE_S = 0.1
    config.LOST_HOLD_S = 0.2
    config.LOST_IDLE_S = 0.6
    config.IDLE_PERSON_HOLD_S = 1.0

    pw, ph = config.PREVIEW_SIZE
    head = Head.__new__(Head)
    head.state = "idle"
    head.camera = FakeRecCamera((pw // 2 - 50, ph // 2 - 100, 100, 200))
    head.ptz = FakePtz()
    head.ptz.park = lambda: None
    head.uwb = SwitchableUwb()
    head.tracker = Tracker(head.uwb, head.camera, head.ptz)
    head.session = AutoSession()
    head.led = FakeRing()
    head.storage = FakeStorage()
    head.power = FakePower()
    head.local = FakeLocal()
    head.mdns = FakeMdns()
    head.cloud = CloudLink(head)       # not connected: writes are no-ops
    head._rec_path, head._rec_started = "", 0.0
    head._countdown_sent = 0

    countdown_sent: list[int] = []     # what the app hears, in order, to beep on
    send = head.send_telemetry

    async def record_send():
        countdown_sent.append(head.telemetry()["countdown"])
        await send()
    head.send_telemetry = record_send

    seen: list[tuple[str, str | None]] = []

    async def tick_for(seconds: float) -> None:
        t0 = time.monotonic()
        while time.monotonic() - t0 < seconds:
            await head.control_tick(time.monotonic())
            point = (head.state, head.phase)
            if not seen or seen[-1] != point:
                seen.append(point)
            await asyncio.sleep(0.01)

    await tick_for(0.3)
    check("standby with the tag off", head.state == "idle")
    check("idle sub-state: person in frame; the ring breathes",
          head.phase == "person-in-frame" and head.led.idle_person, f"{head.phase}")
    bbox, head.camera._bbox = head.camera._bbox, None
    await tick_for(config.IDLE_PERSON_HOLD_S + 0.5)
    check("idle sub-state: no person in frame once they have gone for IDLE_PERSON_HOLD_S; ring solid",
          head.phase == "no-person-in-frame" and not head.led.idle_person, f"{head.phase}")
    head.camera._bbox = bbox
    await tick_for(0.5)
    check("…and back to person in frame", head.phase == "person-in-frame", f"{head.phase}")

    head.uwb.on_since, head.uwb.off_at = time.monotonic(), None
    await tick_for(0.25)
    check("tag on with a person in frame → tracking, found (search skipped), ring fills",
          head.state == "tracking" and head.phase == "found" and head.led.found is not None
          and not head.led.searching, f"{seen}")

    await tick_for(config.FOUND_CONFIRM_S + 1.0)
    check("found for FOUND_CONFIRM_S → recording",
          head.state == "recording" and head.camera.recording and head.phase == "track",
          f"{seen}")
    check("the app heard 3, 2, 1 (one beep each)", countdown_heard(countdown_sent) == [3, 2, 1],
          f"{countdown_sent}")

    head.uwb.on_since, head.uwb.off_at = None, time.monotonic()
    head.tracker.last_fix_at = time.monotonic()
    await tick_for(1.0)
    check("tag off → back to standby, recording stopped",
          head.state == "idle" and not head.camera.recording, f"{seen}")

    order = [s for s, _ in seen]
    dedup = [s for i, s in enumerate(order) if i == 0 or order[i - 1] != s]
    check("states ran idle → tracking → recording → idle",
          dedup == ["idle", "tracking", "recording", "idle"], f"{dedup}")
    check("idle reports its sub-state; tracking found; recording track",
          all(p in ("person-in-frame", "no-person-in-frame") for s, p in seen if s == "idle")
          and all(p == "found" for s, p in seen if s == "tracking")
          and all(p == "track" for s, p in seen if s == "recording"), f"{seen}")

    # --- nobody in frame when the tag goes on: SEARCH, turning to the tag ---------
    head.camera._bbox = None
    await tick_for(max(config.IDLE_PERSON_HOLD_S, config.LOST_IDLE_S) + 0.3)
    check("idle sub-state: no person in frame", head.phase == "no-person-in-frame", f"{head.phase}")
    head.uwb.on_since, head.uwb.off_at = time.monotonic(), None
    await tick_for(0.25)
    check("tag on with nobody in frame → search; ring chases (the app pings)",
          head.state == "tracking" and head.phase == "search" and head.led.searching,
          head.tracker.mode)
    head.camera._bbox = bbox
    await tick_for(config.FOUND_CONFIRM_S + 1.5)
    check("…turns to the tag, finds them, and records 3 s later",
          head.state == "recording" and head.phase == "track", f"{head.state} {head.phase}")

    # --- stop recording from the app: the session ends --------------------------
    await head.apply_state("tracking")          # what an older app sends
    check("stop recording → idle", head.state == "idle" and not head.camera.recording)
    await tick_for(0.5)
    check("…and stays idle while the tag stays on", head.state == "idle")


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
    tracker_found()
    asyncio.run(full_flow())
    ring_animation()
    print()
    if failures:
        print(f"{len(failures)} check(s) failed: " + ", ".join(failures))
        sys.exit(1)
    print("all session checks passed")


if __name__ == "__main__":
    main()
