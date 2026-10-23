"""Tag-driven sessions: tag on → search → found (3 s) → recording; tag off → standby.

Three layers, none of which needs a Pi:

  1. AutoSession's rules, on a synthetic clock;
  2. the tracker's search / found rules, against the fakes from test_tracker,
     including picking the tag wearer out from other people;
  3. the whole flow through Head.control_tick(), with fake hardware, which
     is what the LED and the app actually see.

    python3 device/tests/test_session.py
"""
from __future__ import annotations

import asyncio
import json
import math
import os
import random
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


def run_session(s: AutoSession, steps, state="awake", ready=False):
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
          s.update(5.0, config.LOST_END_S * 0.8, "recording", True) is None and s.active)

    # tag switched off: the control loop drops to awake after LOST_END_S
    s.update(40.0, config.LOST_END_S + 1, "awake", False)
    check("tag off → session over", not s.active and not s.tag_present)
    asked, _ = run_session(s, [(60 + t / 20, 0.05) for t in range(40)])
    check("tag back on → a new session", asked == ["tracking"], f"{asked}")

    # stopped from the app with the tag still on: do not argue
    s = AutoSession()
    run_session(s, [(t / 20, 0.05) for t in range(40)])
    asked, _ = run_session(s, [(2 + t / 20, 0.05) for t in range(100)], state="awake")
    check("stopped from the app → stays stopped while the tag stays on", asked == [])
    short = config.LOST_END_S * 0.6
    run_session(s, [(10 + t / 10, short * t / 5) for t in range(6)], state="awake")
    asked, _ = run_session(s, [(20 + t / 20, 0.05) for t in range(40)])
    check("…and a short off/on does not restart it", asked == [])
    s.update(60.0, config.LOST_END_S, "awake", False)
    asked, _ = run_session(s, [(70 + t / 20, 0.05) for t in range(40)])
    check("…but off for LOST_END_S and on again does", asked == ["tracking"])

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


def run_tracker(tr: Tracker, seconds: float, until=None, period=0.005) -> float:
    t0 = time.monotonic()
    while time.monotonic() - t0 < seconds:
        tr.step()
        if until and until():
            break
        time.sleep(period)
    return time.monotonic() - t0


class People(FakeCamera):
    """People at real bearings and distances, boxed as the lens would see them.

    Each person is (bearing_deg, dist_m). The boxes follow the head's pan and
    zoom, so a person only sits where the tag says if they are the tag wearer.
    """

    def __init__(self, ptz, people):
        super().__init__(None)
        self.ptz, self.people = ptz, list(people)

    def boxes(self):
        pw, ph = config.PREVIEW_SIZE
        half_w = pw / 2
        half_fov = math.radians(self.ptz.hfov_deg / 2)
        out = []
        for deg, dist in self.people:
            off = math.radians(deg - self.ptz.pan_deg)
            if abs(off) >= half_fov:
                continue
            cx = half_w + half_w * math.tan(off) / math.tan(half_fov)
            body = config.SUBJECT_HEIGHT_M * self.ptz.zoom_mm / (config.SENSOR_H_MM * dist) * ph
            h = int(body / config.PERSON_IN_BOX_H)
            w = int(h * 0.4)
            out.append((int(cx - w / 2), ph // 2 - h // 2, w, h))
        return out

    def person_boxes(self):
        _, fresh = self.person_bbox()
        return self.boxes(), fresh


class NoisyUwb(FakeUwb):
    """A tag with the filtered bearing's noise (TAG_BEARING_SIGMA_DEG RMS).

    Filtered, so it wanders rather than jumps: an Ornstein–Uhlenbeck process
    with a TAG_BEARING_CORR_S correlation time, stepped at the radio's 20 Hz
    on the real clock and held in between.
    """

    def __init__(self, theta_deg, dist, sigma_deg=None, seed=1):
        super().__init__(theta_deg=theta_deg, dist=dist)
        self.theta = theta_deg
        self.sigma = config.TAG_BEARING_SIGMA_DEG if sigma_deg is None else sigma_deg
        self.rng = random.Random(seed)
        self.err, self.at = 0.0, time.monotonic()

    def fix(self):
        period = 1.0 / config.UWB_RATE_HZ
        k = math.exp(-period / config.TAG_BEARING_CORR_S)
        while time.monotonic() - self.at >= period:
            self.at += period
            self.err = k * self.err + self.sigma * math.sqrt(1 - k * k) * self.rng.gauss(0, 1)
        self.fix_value.theta_rad = math.radians(self.theta + self.err)
        return self.fix_value


def labels_seen(tr: Tracker) -> set[str]:
    """Every box label the tracker gives from now on, collected as it steps."""
    seen: set[str] = set()
    step = tr.step

    def labelled_step() -> None:
        step()
        seen.update(label for _, label in tr.labelled)
    tr.step = labelled_step
    return seen


def tag_wearer() -> None:
    print("\ntag wearer, not just a person")
    config.ACQUIRE_SETTLE_S = 0.1

    ptz = FakePtz()
    tr = Tracker(FakeUwb(theta_deg=0.0, dist=10.0), People(ptz, [(16.0, 10.0)]), ptz)
    labels = labels_seen(tr)
    run_tracker(tr, 1.5)
    check("someone well off the tag's bearing is never found", tr.mode == "search", tr.mode)
    check("…and moves nothing: no pan bias", tr._pan_bias == 0.0, f"{tr._pan_bias:.2f}")
    check("…and is boxed yellow: not the climber", labels == {"other"}, f"{labels}")

    ptz = FakePtz()
    tr = Tracker(FakeUwb(theta_deg=0.0, dist=10.0), People(ptz, [(0.0, 3.0)]), ptz)
    labels = labels_seen(tr)
    run_tracker(tr, 1.5)
    check("someone on the tag's bearing but far nearer the lens is never found",
          tr.mode == "search", tr.mode)
    check("…and is boxed yellow too", labels == {"other"}, f"{labels}")

    ptz = FakePtz()
    tr = Tracker(FakeUwb(theta_deg=0.0, dist=10.0),
                 People(ptz, [(25.0, 10.0), (0.0, 10.0), (-30.0, 6.0)]), ptz)
    run_tracker(tr, 2.0, until=lambda: tr.mode == "found")
    check("the wearer among bystanders is found", tr.mode == "found"
          and abs(tr._chosen.deg) < 1.0, tr.mode)
    check("…boxed green, and anyone else in view yellow",
          [lab for _, lab in tr.labelled].count("climber") == 1
          and set(lab for _, lab in tr.labelled) <= {"climber", "other"}
          and abs(tr._box_deg(next(b for b, lab in tr.labelled if lab == "climber"))) < 1.0,
          f"{tr.labelled}")

    # A belayer beside the climber, with the real bearing noise, at the real
    # 20 Hz loop rate. 14° is 2.5 m at 10 m; closer pairs take longer (≈ 17 s
    # at 1.5 m) and are covered by the sweep in 05, too slow for this file.
    wrong, slow = [], []
    for seed in (4, 7):
        ptz = FakePtz()
        tr = Tracker(NoisyUwb(0.0, 10.0, seed=seed), People(ptz, [(0.0, 10.0), (14.0, 9.5)]), ptz)
        run_tracker(tr, 20.0, until=lambda: tr.ready_to_record, period=0.05)
        if not tr.ready_to_record:
            slow.append(seed)
        elif abs(tr._chosen.deg) > 1.0:
            wrong.append(seed)
    check("climber with a belayer beside them: records the climber", not wrong, f"seeds {wrong}")
    check("…decided within 20 s", not slow, f"seeds {slow}")

    ptz = FakePtz()
    tr = Tracker(NoisyUwb(0.0, 10.0), People(ptz, [(-1.0, 10.0), (1.0, 10.0)]), ptz)
    run_tracker(tr, 6.0, until=lambda: tr.ready_to_record, period=0.05)
    check("two people too close to tell apart: never records", not tr.ready_to_record,
          tr.mode)
    check("…the countdown holds at 1 rather than starting over",
          tr.mode != "found" or tr.countdown == 1, f"{tr.mode} {tr.countdown}")
    check("…and the pan bias stands still while they are told apart",
          tr._pan_bias == 0.0, f"{tr._pan_bias:.2f}")
    check("…and both are boxed red: it cannot tell which is the climber",
          [lab for _, lab in tr.labelled] == ["unsure", "unsure"], f"{tr.labelled}")


def tracker_found() -> None:
    print("\ntracker search / found")
    confirm_s, config.FOUND_CONFIRM_S = config.FOUND_CONFIRM_S, 0.6
    config.ACQUIRE_SETTLE_S = 0.1
    config.ACQUIRE_STALLED_S = 0.6
    pw, ph = config.PREVIEW_SIZE
    centred = (pw // 2 - 50, ph // 2 - 150, 100, 300)   # a 1.8 m body at 10 m

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

    ptz3 = FakePtz()           # the person stands 6° off where the tag reads: off-centre
    tr3 = Tracker(FakeUwb(theta_deg=10.0), People(ptz3, [(16.0, 10.0)]), ptz3)
    run_tracker(tr3, 1.5, until=lambda: tr3.ready_to_record)
    check("a person off-centre is still found and recorded (no centring needed)",
          tr3.ready_to_record)

    tr4 = Tracker(FakeUwb(theta_deg=88.0), FakeCamera(centred), FakePtz())
    run_tracker(tr4, 4.0, until=lambda: tr4.mode == "found")
    check("subject just past the soft limit: found from the limit", tr4.mode == "found")

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
    tr6 = Tracker(FakeUwb(theta_deg=0.0), cam6, FakePtz())
    tr6.watch_awake()
    check("awake: a person in frame is noticed", tr6.awake_person_in_frame)
    tr6.reset_lock()
    check("a session always starts in SEARCH, even with a person in frame in awake",
          tr6.mode == "search" and not tr6.awake_person_in_frame, tr6.mode)
    took = run_tracker(tr6, 2.0, until=lambda: tr6.mode == "found")
    check("…and is found once settled, when the head already points at the tag",
          tr6.mode == "found" and took < config.ACQUIRE_SETTLE_S + 0.5, f"{took:.2f}s")
    config.FOUND_CONFIRM_S = confirm_s


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


def labels(boxes: list) -> set[str]:
    return {b[4] for b in boxes}


def countdown_heard(sent: list[int]) -> list[int]:
    """The countdown values the app heard, without repeats or zeros (one beep each)."""
    return [c for i, c in enumerate(sent) if c and (i == 0 or sent[i - 1] != c)]


async def full_flow() -> None:
    print("\nfull flow through Head.control_tick()")
    import sportcam.main as main_mod
    from sportcam.cloud import CloudLink
    from sportcam.boxlog import BoxLog
    from sportcam.main import Head

    async def no_upload(*a, **k):
        return None
    main_mod.upload_with_retry = no_upload

    config.TAG_PRESENT_S = 0.1
    config.ACQUIRE_SETTLE_S = 0.1
    config.LOST_HOLD_S = 0.2
    config.LOST_END_S = 0.6
    config.AWAKE_PERSON_HOLD_S = 1.0

    pw, ph = config.PREVIEW_SIZE
    head = Head.__new__(Head)
    head.state = "awake"
    head.camera = FakeRecCamera((pw // 2 - 50, ph // 2 - 150, 100, 300))
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
    head._near_focus = False
    head._boxes_sent_at = None
    head._jog, head._jog_at = (0.0, 0.0), float("-inf")
    head._awake_since = time.monotonic()
    head.boxlog = BoxLog()

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
    check("standby with the tag off", head.state == "awake")

    # the app's joystick turns the head in awake, and stops when the app stops sending
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
    head.ptz.set_pan(0.0)
    head.ptz.set_tilt(0.0)
    check("awake sub-state: person in frame; the ring breathes",
          head.phase == "person-in-frame" and head.led.awake_person, f"{head.phase}")
    bbox, head.camera._bbox = head.camera._bbox, None
    await tick_for(config.AWAKE_PERSON_HOLD_S + 0.5)
    check("awake sub-state: no person in frame once they have gone for AWAKE_PERSON_HOLD_S; ring solid",
          head.phase == "no-person-in-frame" and not head.led.awake_person, f"{head.phase}")
    head.camera._bbox = bbox
    await tick_for(0.5)
    check("…and back to person in frame", head.phase == "person-in-frame", f"{head.phase}")
    check("live view: awake boxes are all 'can't tell' (nobody picked yet)",
          head.live_boxes() and labels(head.live_boxes()) == {"unsure"}, f"{head.live_boxes()}")

    head.uwb.on_since, head.uwb.off_at = time.monotonic(), None
    await tick_for(0.15)
    check("tag on with a person in frame → tracking, search (awake cannot say who they are)",
          head.state == "tracking" and head.phase == "search" and head.led.searching, f"{seen}")
    await tick_for(config.ACQUIRE_SETTLE_S + 0.4)
    check("…found once the head is on the tag and vision agrees; ring fills",
          head.state == "tracking" and head.phase == "found" and head.led.found is not None
          and not head.led.searching, f"{seen}")

    await tick_for(config.FOUND_CONFIRM_S + 1.0)
    check("found for FOUND_CONFIRM_S → recording",
          head.state == "recording" and head.camera.recording and head.phase == "track",
          f"{seen}")
    check("the app heard 3, 2, 1 (one beep each)", countdown_heard(countdown_sent) == [3, 2, 1],
          f"{countdown_sent}")
    msg = head.local.last_boxes()
    check("live view: each detection goes to direct viewers, the climber labelled",
          msg is not None and msg["size"] == list(config.PREVIEW_SIZE)
          and "climber" in labels(msg["boxes"]), f"{msg}")

    head.uwb.on_since, head.uwb.off_at = None, time.monotonic()
    head.tracker.last_fix_at = time.monotonic()
    await tick_for(1.0)
    check("tag off → back to standby, recording stopped",
          head.state == "awake" and not head.camera.recording, f"{seen}")
    side = "/tmp/sportcam-test.boxes.json"
    frames = json.load(open(side))["frames"] if os.path.exists(side) else []
    check("the clip's person boxes are saved beside it, the climber labelled",
          any(label == "climber" for _, boxes in frames for *_, label in boxes), f"{frames[:3]}")

    order = [s for s, _ in seen]
    dedup = [s for i, s in enumerate(order) if i == 0 or order[i - 1] != s]
    check("states ran awake → tracking → recording → awake",
          dedup == ["awake", "tracking", "recording", "awake"], f"{dedup}")
    check("awake reports its sub-state; tracking search/found; recording track",
          all(p in ("person-in-frame", "no-person-in-frame") for s, p in seen if s == "awake")
          and all(p in ("search", "found") for s, p in seen if s == "tracking")
          and all(p == "track" for s, p in seen if s == "recording"), f"{seen}")

    # --- nobody in frame when the tag goes on: SEARCH, turning to the tag ---------
    head.camera._bbox = None
    await tick_for(max(config.AWAKE_PERSON_HOLD_S, config.LOST_END_S) + 0.3)
    check("awake sub-state: no person in frame", head.phase == "no-person-in-frame", f"{head.phase}")
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
    check("stop recording → awake", head.state == "awake" and not head.camera.recording)
    await tick_for(0.5)
    check("…and stays awake while the tag stays on", head.state == "awake")

    # --- sleep: awake AWAKE_TIMEOUT_S with no session ------------------------------
    config.AWAKE_TIMEOUT_S = 0.5
    head.local.viewers = 1
    await tick_for(0.8)
    check("live view open on the stream: stays awake past AWAKE_TIMEOUT_S", head.state == "awake")
    head.local.viewers = 0
    head.cloud.viewer_at = time.time()
    await tick_for(0.8)
    check("…and while the app watches through Firebase", head.state == "awake")
    head.cloud.viewer_at = 0.0
    await tick_for(0.8)
    check("awake AWAKE_TIMEOUT_S with no session → sleep: camera off, no sub-state",
          head.state == "sleep" and not head.camera.awake and head.phase is None
          and head.led.state == "sleep", f"{head.state} {head.phase}")
    check("…and no live view while asleep", head.live_boxes() == [])
    head.uwb.on_since, head.uwb.off_at = None, time.monotonic()
    await tick_for(config.LOST_END_S + 0.2)
    check("tag off: still asleep", head.state == "sleep")
    head.uwb.on_since, head.uwb.off_at = time.monotonic(), None
    await tick_for(0.25)
    check("tag on while asleep → straight into tracking, search; camera on",
          head.state == "tracking" and head.phase == "search" and head.camera.awake,
          f"{head.state} {head.phase}")
    await head.apply_state("sleep")
    check("the app's Sleep stops the session", head.state == "sleep" and not head.camera.awake)
    await head.apply_state("tracking")
    check("the app's Record from sleep → tracking, skipping awake",
          head.state == "tracking" and head.camera.awake)
    await head.apply_state("awake")
    config.AWAKE_TIMEOUT_S = 30.0


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
    tracker_found()
    tag_wearer()
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
