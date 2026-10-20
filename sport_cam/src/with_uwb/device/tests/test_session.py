"""Tag-driven sessions: tag on → acquiring → recording; tag off → standby.

Three layers, none of which needs a Pi:

  1. AutoSession's rules, on a synthetic clock;
  2. the tracker's lock-on test, against the fakes from test_tracker;
  3. the whole flow through Head.control_tick(), with fake hardware, which
     is what the LED and the app actually see.

    python3 device/tests/test_session.py
"""
from __future__ import annotations

import asyncio
import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.dirname(__file__))

from sportcam import config
from sportcam.led import chase
from sportcam.session import AutoSession
from sportcam.tracker import Tracker
from test_tracker import FakeCamera, FakePtz, FakeUwb

failures: list[str] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    print(f"  {'PASS' if ok else 'FAIL'}  {name}" + (f"  ({detail})" if detail and not ok else ""))
    if not ok:
        failures.append(name)


GONE = float("inf")


def run_session(s: AutoSession, steps, state="idle", locked=False):
    """Feed (now, frame_age) pairs; return the states it asked for."""
    asked = []
    for now, age in steps:
        want = s.update(now, age, state, locked)
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

    check("acquiring: no recording before lock",
          s.update(2.0, 0.05, "tracking", False) is None)
    check("locked → recording", s.update(2.1, 0.05, "tracking", True) == "recording")
    check("records once: dropping back to tracking from the app stands",
          s.update(2.2, 0.05, "tracking", True) is None)

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

    # manual sessions are left alone
    s = AutoSession()
    asked, _ = run_session(s, [(t / 20, 0.05) for t in range(40)], state="tracking", locked=True)
    check("tag on during a manual session → no change, no auto-record", asked == [])

    config.AUTO_SESSION = False
    s = AutoSession()
    asked, _ = run_session(s, [(t / 20, 0.05) for t in range(40)])
    check("AUTO_SESSION = False → the tag starts nothing", asked == [])
    config.AUTO_SESSION = True


def run_tracker(tr: Tracker, seconds: float, until_locked=False) -> float:
    t0 = time.monotonic()
    while time.monotonic() - t0 < seconds:
        tr.step()
        if until_locked and tr.locked:
            break
        time.sleep(0.005)
    return time.monotonic() - t0


def tracker_lock() -> None:
    print("\ntracker lock-on")
    config.ACQUIRE_SETTLE_S = 0.1
    config.ACQUIRE_STALLED_S = 0.6
    pw, ph = config.PREVIEW_SIZE
    centred = (pw // 2 - 50, ph // 2 - 100, 100, 200)
    off_centre = (int(pw * 0.85), ph // 2 - 100, 100, 200)

    ptz = FakePtz()
    tr = Tracker(FakeUwb(theta_deg=40.0), FakeCamera(centred), ptz)
    tr.step()
    check("not locked while still turning toward the tag", not tr.locked)
    took = run_tracker(tr, 3.0, until_locked=True)
    check("locks once on target and the detector sees someone centred", tr.locked,
          f"{took:.2f}s")

    tr2 = Tracker(FakeUwb(theta_deg=10.0), FakeCamera(None), FakePtz())
    run_tracker(tr2, 1.5)
    check("no detection → never locks on ranging alone", not tr2.locked)
    check("…and after ACQUIRE_STALLED_S it reports it cannot see anyone",
          tr2.acquire_stalled)

    tr3 = Tracker(FakeUwb(theta_deg=10.0), FakeCamera(off_centre), FakePtz())
    run_tracker(tr3, 1.5)
    check("a person at the edge of the frame does not verify the lock", not tr3.locked)

    tr4 = Tracker(FakeUwb(theta_deg=170.0), FakeCamera(centred), FakePtz())
    run_tracker(tr4, 4.0, until_locked=True)
    check("subject past the soft limit: locks from the limit", tr4.locked)
    check("a locked tracker is not stalled", not tr4.acquire_stalled)

    tr4.reset_lock()
    check("reset_lock clears it", not tr4.locked and not tr4.acquire_stalled)


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
    head.local = FakeLocal()
    head.mdns = FakeMdns()
    head.cloud = CloudLink(head)       # not connected: writes are no-ops
    head._rec_path, head._rec_started = "", 0.0

    seen: list[tuple[str, str | None]] = []

    async def tick_for(seconds: float) -> None:
        t0 = time.monotonic()
        while time.monotonic() - t0 < seconds:
            await head.control_tick(time.monotonic())
            point = (head.state, "acquiring" if head.led.acquiring else head.phase)
            if not seen or seen[-1] != point:
                seen.append(point)
            await asyncio.sleep(0.01)

    await tick_for(0.3)
    check("standby with the tag off", head.state == "idle" and not head.led.acquiring)

    head.uwb.on_since, head.uwb.off_at = time.monotonic(), None
    await tick_for(0.25)
    check("tag on → tracking, ring shows acquiring",
          head.state == "tracking" and head.led.acquiring, f"{seen}")

    await tick_for(1.5)
    check("locked on → recording, ring no longer acquiring",
          head.state == "recording" and not head.led.acquiring and head.camera.recording,
          f"{seen}")

    head.uwb.on_since, head.uwb.off_at = None, time.monotonic()
    head.tracker.last_fix_at = time.monotonic()
    await tick_for(1.0)
    check("tag off → back to standby, recording stopped",
          head.state == "idle" and not head.camera.recording, f"{seen}")

    order = [s for s, _ in seen]
    dedup = [s for i, s in enumerate(order) if i == 0 or order[i - 1] != s]
    check("states ran idle → tracking → recording → idle",
          dedup == ["idle", "tracking", "recording", "idle"], f"{dedup}")
    check("phase ran acquiring → acquired",
          ("tracking", "acquiring") in seen and ("recording", "acquired") in seen, f"{seen}")


def ring_animation() -> None:
    print("\nring")
    frame = chase((0, 200, 0), 0.25, 16)
    check("acquiring chase lights every pixel", len(frame) == 16)
    check("…with one bright head and a dim base",
          max(frame)[1] == 200 and min(frame)[1] < 40, f"{frame}")
    check("…and it moves", chase((0, 200, 0), 0.5, 16) != frame)


def main() -> None:
    session_rules()
    tracker_lock()
    asyncio.run(full_flow())
    ring_animation()
    print()
    if failures:
        print(f"{len(failures)} check(s) failed: " + ", ".join(failures))
        sys.exit(1)
    print("all session checks passed")


if __name__ == "__main__":
    main()
