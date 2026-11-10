"""Contrast autofocus: the continuous sweep and the fine pass find the
sharpest focus, quickly, say how it ended, and stop when told; and Refocus
decides when one runs. No camera or I2C bus: a simulated lens moves at the
bench kit's measured speed on a simulated clock, each frame carries when it
was exposed (a little before it is handed over), and a made-up sharpness
curve peaks as narrowly as the real lens's. Positions are motor steps.

    python3 device/tests/test_autofocus.py
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from sportcam import config
from sportcam.autofocus import (CANCELLED, FOCUSED, NO_PEAK, AutoFocus, Outcome, Refocus,
                                _steps)
from sportcam.ptz import LENS_STEPS

failures: list[str] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    print(f"  {'PASS' if ok else 'FAIL'}  {name}" + (f"  ({detail})" if detail and not ok else ""))
    if not ok:
        failures.append(name)


TRAVEL_S = 5.4            # measured: 525 steps of 2100 in 1.35 s
FRAME_S = 1 / 30
EXPOSED_AGO_S = 0.05      # a frame is handed over this long after its exposure
MID = LENS_STEPS // 2


class World:
    def __init__(self) -> None:
        self.t = 0.0

    def clock(self) -> float:
        return self.t

    def sleep(self, s: float) -> None:
        self.t += s


class Ptz:
    """The focus motor, moving at a steady speed toward where it was sent:
    autofocus's Lens."""
    zoom_mm = 6.0
    zoom_steps = 1000
    subject_m = 5.0

    def __init__(self, world: World, at: int | None = MID) -> None:
        self.w = world
        self.focus_steps = at            # where it was last sent (None: never)
        self._from, self._t0 = float(at or 0), 0.0
        self.moves: list[int] = []
        self.lens_owner = None
        self.learned: float | None = None
        self.others_held = True          # the lens was autofocus's at every move

    def take_lens(self, owner) -> None:
        self.lens_owner = owner

    def give_lens(self, owner) -> None:
        if self.lens_owner is owner:
            self.lens_owner = None

    @property
    def lens_moving(self) -> bool:
        return self.lens_owner is not None or self.lens_busy()

    def _run_s(self) -> float:
        target = self.focus_steps if self.focus_steps is not None else 0
        return abs(target - self._from) / LENS_STEPS * TRAVEL_S

    @property
    def lens_run(self) -> tuple[float, float]:
        return self._t0, self._t0 + self._run_s()

    def actual(self, t: float | None = None) -> float:
        t = self.w.t if t is None else t
        target = float(self.focus_steps if self.focus_steps is not None else 0)
        run = self._run_s()
        if run == 0 or t - self._t0 >= run:
            return target
        return self._from + (target - self._from) * max(0.0, t - self._t0) / run

    def set_focus_steps(self, steps: float, owner=None) -> None:
        self.others_held &= owner is not None and self.lens_owner is owner
        self._from, self._t0 = self.actual(), self.w.t
        self.focus_steps = int(round(steps))
        self.moves.append(self.focus_steps)

    def lens_busy(self) -> bool:
        target = self.focus_steps if self.focus_steps is not None else 0
        return abs(self.actual() - target) > 1e-9

    def wait_lens(self, timeout_s=None) -> None:
        while self.lens_busy():
            self.w.t += 0.01
        self.w.t += config.LENS_SETTLE_S

    def learn_focus(self, steps: float) -> None:
        self.learned = steps


class Shot:
    """A frame: its grey picture (here, where the lens was) and when it was exposed."""

    def __init__(self, luma: float, at: float) -> None:
        self.luma, self.at = luma, at


class Camera:
    def __init__(self, world: World, ptz: Ptz) -> None:
        self.w, self.ptz = world, ptz
        self.awake = True

    def frame(self, newer_than=None):
        self.w.t += FRAME_S
        at = self.w.t - EXPOSED_AGO_S
        return Shot(self.ptz.actual(at), at) if self.awake else None


def peaked_at(best: float, where: dict | None = None):
    """Sharp only within ±2 % of the travel of `best`, flat (and a little
    noisy-looking) elsewhere: the real lens's band is about that narrow."""
    band = 0.02 * LENS_STEPS

    def score(luma, x, y, region):
        if where is not None:
            where["at"] = (x, y, region)
        d = abs(luma - best)
        return 4.0 + (120.0 * (1 - d / band) if d < band else 0.0) + (luma * 7.919 % 1) * 0.3
    return score


def run(best: float, start: int | None = MID):
    w = World()
    ptz = Ptz(w, start)
    where: dict = {}
    af = AutoFocus(Camera(w, ptz), ptz, score=peaked_at(best, where),
                   sleep=w.sleep, clock=w.clock)
    got = af.focus(0.2, 0.8)
    return got, ptz, af, w, where


def narrow(score, start: int = MID):
    w = World()
    ptz = Ptz(w, start)
    af = AutoFocus(Camera(w, ptz), ptz, score=score, sleep=w.sleep, clock=w.clock)
    return af.focus(0.5, 0.5, narrow=True), ptz, w


def hill(best: float):
    """Near focus: sharpness falls off gently, so a peak isn't many medians."""
    return lambda luma, x, y, region: 100.0 - 300.0 * abs(luma - best) / LENS_STEPS


class StubAutoFocus:
    """What Refocus starts, and a way to end it."""

    def __init__(self, ptz) -> None:
        self.ptz = ptz
        self.started: list[tuple[float, float, bool]] = []
        self._on_done = None

    def start(self, x, y, narrow=False, on_done=None) -> None:
        self.started.append((x, y, narrow))
        self._on_done = on_done
        self.ptz.lens_owner = self

    def end(self, result: str) -> None:
        self.ptz.lens_owner = None
        self._on_done(Outcome(result))


def refocus_checks() -> None:
    print("\nwhen to autofocus (Refocus)")
    w = World()
    ptz = Ptz(w)
    af = StubAutoFocus(ptz)
    r = Refocus(ptz, af, clock=w.clock)
    gap = config.AF_TRACK_GAP_S

    def tick(seconds: float = 0.05, **kw) -> None:
        end = w.t + seconds
        while w.t < end:
            w.t += 0.05
            r.tick(0.4, 0.6, narrow=True, gap_s=gap, **kw)

    tick(1.0)
    check("nothing due: no autofocus", af.started == [])
    ptz.zoom_mm = 6.0 + config.AF_REZOOM_MM / 2
    tick(1.0)
    check("a zoom change under AF_REZOOM_MM doesn't ask for one", af.started == [])
    ptz.zoom_mm = 7.0
    ptz.set_focus_steps(MID + 600)               # the zoom's refocus: the lens is moving
    tick(0.5)
    check("zoomed: not while the lens is still moving", af.started == [] and ptz.lens_busy())
    tick(3.0)
    check("…as soon as it has stopped, a narrow autofocus on the point given, once",
          af.started == [(0.4, 0.6, True)], f"{af.started}")
    af.end(FOCUSED)
    tick(1.0)
    check("focused: that zoom is done with", len(af.started) == 1)

    ptz.zoom_mm = 8.0
    tick(1.0)
    check("zoomed again inside AF_TRACK_GAP_S of the last: it waits", len(af.started) == 1)
    tick(gap)
    check("…and runs once the gap has passed", len(af.started) == 2)
    t = w.t
    af.end(NO_PEAK)
    tick(gap - 0.5)
    check("no peak found: not again at once", len(af.started) == 2)
    tick(1.0)
    check("…but once more, AF_TRACK_GAP_S later", len(af.started) == 3, f"{w.t - t:.1f} s")
    af.end(NO_PEAK)
    tick(3 * gap)
    check("…and after AF_REFOCUS_RETRIES it is left until the next zoom",
          len(af.started) == 2 + config.AF_REFOCUS_RETRIES, f"{len(af.started)}")

    ptz.zoom_mm = 9.0
    tick(gap + 1.0)
    n = len(af.started)
    af.end(CANCELLED)
    tick(2 * gap)
    check("cancelled: whoever cancelled decides, no retry", len(af.started) == n)

    r.reset()
    r.request(delay_s=2.0)
    tick(1.5, watch_zoom=False)
    check("asked for with a delay (waking): not before it", len(af.started) == n)
    tick(1.0, watch_zoom=False)
    check("…then it runs", len(af.started) == n + 1)
    af.end(FOCUSED)
    ptz.zoom_mm = 5.0
    tick(2 * gap, watch_zoom=False)
    check("watch_zoom off (awake): a zoom alone doesn't ask for one", len(af.started) == n + 1)
    r.now(0.1, 0.2)
    check("now(): at once, where asked, whatever the gap",
          af.started[-1] == (0.1, 0.2, False) and len(af.started) == n + 2)


def main() -> None:
    print("autofocus")
    # after a zoom: the lens nearly right, perhaps on film
    step, _half = config.AF_FINE_STEPS
    near = MID + 60
    got, ptz, w = narrow(hill(near))
    check("narrow: a gentle peak close by is found",
          got.focused and abs(got.steps - near) <= step, f"{got}")
    check("…in a moment", w.t < 4.0, f"{w.t:.1f} s")
    check("…and says where the time went",
          got.seconds == w.t and 0 < got.waiting_s < got.seconds and got.samples > 5
          and abs(got.sweep_s + got.fine_s - got.seconds) < 0.5, f"{got}")
    far = MID + 520
    got, ptz, w = narrow(hill(far))
    check("narrow: outside the window, it walks to the peak",
          got.focused and abs(got.steps - far) <= step, f"{got}")
    reach = (config.AF_REFOCUS_WINDOWS * 2 * config.AF_REFOCUS_HALF_STEPS
             + 2 * config.AF_BACKLASH_STEPS)
    check("…without running the whole travel",
          max(ptz.moves) - min(ptz.moves) <= reach, f"{ptz.moves}")
    got, ptz, w = narrow(lambda luma, x, y, region: 5.0)
    check("narrow: no peak at all says so, and learns nothing",
          got.result == NO_PEAK and got.steps is None and ptz.learned is None, f"{got}")
    check("…and puts the lens back", ptz.focus_steps == MID, f"{ptz.focus_steps}")
    check("fine steps stay inside the travel, whole steps",
          min(_steps(-50, 50, 10)) == 0 and max(_steps(LENS_STEPS - 50, LENS_STEPS + 50, 10))
          == LENS_STEPS and all(isinstance(s, int) for s in _steps(100, 160, 10)))

    for share, within_s in ((0.43, 6.0), (0.62, 6.0), (0.95, 19.0), (0.05, 19.0)):
        best = round(share * LENS_STEPS)
        got, ptz, af, w, where = run(best, MID)
        close = abs(MID - best) <= config.AF_SWEEP_HALVES_STEPS[0]
        check(f"finds the sharp band (step {best}, from {MID})",
              got.focused and abs(got.steps - best) <= step, f"{got}")
        check(f"…in {w.t:.1f} s ({'one window' if close else 'then the whole travel'})",
              w.t <= within_s, f"{w.t:.1f} s")
        check("…and leaves the motor there, arriving from below",
              ptz.focus_steps == got.steps and (ptz.moves[-2] < ptz.moves[-1] or got.steps == 0),
              f"{ptz.moves[-3:]}")
        check("…keeping it as the focus trim", ptz.learned == got.steps)
        check("…the lens its own while it ran, and given back after",
              ptz.others_held and ptz.lens_owner is None and not af.busy)
        check("…scoring round the point asked for",
              where["at"] == (0.2, 0.8, config.AF_REGION), f"{where}")

    got, ptz, *_ = run(MID, start=None)
    check("never focused before: starts from the middle",
          got.focused and abs(got.steps - MID) <= step, f"{got}")

    # the outcome reaches whoever asked
    w = World()
    ptz = Ptz(w)
    af = AutoFocus(Camera(w, ptz), ptz, score=peaked_at(MID + 40), sleep=w.sleep, clock=w.clock)
    told: list = []
    out = af.focus(0.5, 0.5, on_done=told.append)
    check("on_done is handed the outcome", told == [out] and out.focused)

    # asleep partway: no picture, nothing chosen
    w = World()
    ptz = Ptz(w)
    cam = Camera(w, ptz)
    n = {"scores": 0}

    def sleepy(luma, x, y, region):
        n["scores"] += 1
        if n["scores"] == 10:
            cam.awake = False
        return 4.0
    af = AutoFocus(cam, ptz, score=sleepy, sleep=w.sleep, clock=w.clock)
    check("the camera going to sleep stops it, nothing learned",
          af.focus(0.5, 0.5).result == CANCELLED and not af.busy and ptz.lens_owner is None
          and ptz.learned is None)

    # a newer request (or cancel) stops a running one at its next step
    w = World()
    ptz = Ptz(w)
    holder: dict = {}

    def cancelling(luma, x, y, region):
        holder.setdefault("n", 0)
        holder["n"] += 1
        if holder["n"] == 5:
            holder["af"].cancel()
            holder["moves"] = len(ptz.moves)
        return 4.0
    af = AutoFocus(Camera(w, ptz), ptz, score=cancelling, sleep=w.sleep, clock=w.clock)
    holder["af"] = af
    got = af.focus(0.5, 0.5)
    check("cancelled: the sweep stops, moves nothing more, learns nothing",
          got.result == CANCELLED and len(ptz.moves) == holder["moves"] and not af.busy
          and ptz.lens_owner is None and ptz.learned is None, f"{got}")

    refocus_checks()

    print()
    if failures:
        print(f"{len(failures)} check(s) failed: " + ", ".join(failures))
        sys.exit(1)
    print("all autofocus checks passed")


if __name__ == "__main__":
    main()
