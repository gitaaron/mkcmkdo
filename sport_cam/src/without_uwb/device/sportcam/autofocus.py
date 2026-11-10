"""Contrast autofocus: sweep the focus motor, keep the sharpest position.

The measure is the variance of the Laplacian over a square around a point of
the frame, on the frame's grey (Y) plane as the sensor gives it: no colour
conversion. The focus motor is slow (≈ 5 s end to end) and a scene is sharp
in a narrow band of it, so a sweep:

  1. runs the motor down through a window around where it already is
     (FOCUS_GRID_STEPS's focus for the zoom, corrected by the last autofocus)
     in one continuous move, scoring every frame on the way — downward, so it
     ends below the peak, where the fine pass starts. Each frame's position
     comes from when it was exposed (camera.Frame.at) between the moment the
     move was written and the moment the motor stopped (Ptz.lens_run): the
     motor runs at a steady speed between them. No clear peak: once more over
     the whole travel (AF_SWEEP_HALVES_STEPS). A `narrow` search never does
     that: its windows walk towards rising sharpness (AF_REFOCUS_WINDOWS),
     and with no peak in them the lens goes back where it was;
  2. refines round the peak in short steps (AF_FINE_STEPS), each move upward
     and the last one onto the best from below, as the gears have backlash;
  3. keeps where it ended, relative to FOCUS_GRID_STEPS, as the focus trim
     (Ptz.learn_focus): later zoom moves and sweeps stay near focus.

Positions are lens motor steps throughout (ptz.LENS_STEPS).

While it runs the lens is autofocus's (Ptz.take_lens): everyone else's zoom
and focus requests come back held, and the trackers don't count the frames it
blurs as their person lost.

Every sweep ends in an `Outcome` — focused, no peak, or cancelled — handed to
whoever asked (`on_done`) and printed, with where the time went. A focused
one also prints an `[af-data]` line: a measured point of the lens's real
zoom → focus curve, for correcting FOCUS_GRID_STEPS.

`Refocus` is the one place that decides *when*: after a zoom, once the lens
has really stopped; on waking; and again if a search found no peak.

It runs on its own thread, like detection. A newer request, or `cancel()`,
makes a running sweep stop at its next step.
"""
from __future__ import annotations

import json
import threading
import time
from dataclasses import dataclass
from typing import Callable, Protocol

from . import config
from .ptz import LENS_STEPS

FOCUSED, NO_PEAK, CANCELLED = "focused", "no-peak", "cancelled"
_EDGE_STEPS = 21          # a best this close to a window's end is "at the end"


class Lens(Protocol):
    """What autofocus needs of the lens: ptz.Ptz, or a test's stand-in."""
    zoom_mm: float
    lens_moving: bool

    @property
    def focus_steps(self) -> int | None: ...
    @property
    def zoom_steps(self) -> int | None: ...
    @property
    def subject_m(self) -> float | None: ...
    @property
    def lens_owner(self) -> object | None: ...
    @property
    def lens_run(self) -> tuple[float, float]: ...
    def take_lens(self, owner: object) -> None: ...
    def give_lens(self, owner: object) -> None: ...
    def set_focus_steps(self, steps: float, owner: object | None = None): ...
    def wait_lens(self, timeout_s: float | None = None) -> None: ...
    def lens_busy(self) -> bool: ...
    def learn_focus(self, steps: float) -> None: ...


class Frames(Protocol):
    """What autofocus needs of the camera: frames with `luma` and `at`."""
    def frame(self, newer_than=None): ...


@dataclass
class Outcome:
    """How one autofocus ended."""
    result: str                    # FOCUSED, NO_PEAK or CANCELLED
    steps: int | None = None       # focus motor position chosen
    sharpness: float = 0.0         # the best scored, and…
    at_rest: float = 0.0           # …the picture where the lens stopped
    seconds: float = 0.0           # the whole of it
    sweep_s: float = 0.0           # of which: the continuous sweep(s)
    fine_s: float = 0.0            # the stepped pass
    waiting_s: float = 0.0         # waiting on the lens and settling, within both
    samples: int = 0               # frames scored during the sweeps

    @property
    def focused(self) -> bool:
        return self.result == FOCUSED


def sharpness(grey, x: float, y: float, region: float) -> float:
    """Variance of the Laplacian over a square around (x, y), each 0…1 of the
    frame; the square's side is `region` of the frame's shorter side. `grey`
    is the frame's grey picture (Frame.luma)."""
    import cv2
    h, w = grey.shape[:2]
    side = max(16, int(min(w, h) * region))
    x0 = int(max(0, min(w - side, x * w - side / 2)))
    y0 = int(max(0, min(h - side, y * h - side / 2)))
    return float(cv2.Laplacian(grey[y0:y0 + side, x0:x0 + side], cv2.CV_64F).var())


class _Run:
    """One sweep's own numbers: several can be alive for a moment when a
    newer request replaces a running one."""

    def __init__(self, gen: int, x: float, y: float) -> None:
        self.gen, self.x, self.y = gen, x, y
        self.waiting_s = 0.0
        self.samples = 0
        self.moved_at = 0.0        # when the last stepped move had settled


class AutoFocus:
    def __init__(self, camera: Frames, ptz: Lens,
                 score: Callable[..., float] = sharpness,
                 sleep: Callable[[float], None] = time.sleep,
                 clock: Callable[[], float] = time.monotonic) -> None:
        self.camera = camera
        self.ptz = ptz
        self._score = score
        self._sleep = sleep
        self._clock = clock
        self._lock = threading.Lock()
        self._gen = 0          # bumped by every start/cancel: older sweeps stop

    @property
    def busy(self) -> bool:
        """A sweep is running, or about to (telemetry `focusing`): the lens
        is autofocus's."""
        return self.ptz.lens_owner is self

    def start(self, x: float, y: float, narrow: bool = False,
              on_done: Callable[[Outcome], None] | None = None) -> None:
        """Focus on (x, y) of the frame, on a thread; replaces a running sweep.
        `narrow`: search only close by (AF_REFOCUS_HALF_STEPS), for a lens
        nearly right, in a moment that may be being filmed. `on_done` gets
        the Outcome, on that thread."""
        gen = self._begin()
        threading.Thread(target=self.focus, args=(x, y, gen, narrow, on_done),
                         name="autofocus", daemon=True).start()

    def _begin(self) -> int:
        with self._lock:
            self._gen += 1
            self.ptz.take_lens(self)
            return self._gen

    def cancel(self) -> None:
        with self._lock:
            self._gen += 1
            self.ptz.give_lens(self)

    def focus(self, x: float, y: float, gen: int | None = None, narrow: bool = False,
              on_done: Callable[[Outcome], None] | None = None) -> Outcome:
        """One autofocus, here and now, and how it ended."""
        run = _Run(self._begin() if gen is None else gen, x, y)
        t0 = self._clock()
        out = Outcome(CANCELLED)
        sweep_s = fine_s = 0.0
        start = None
        try:
            self._wait(run)                     # a zoom still travelling
            start = self.ptz.focus_steps
            start = LENS_STEPS / 2 if start is None else start
            t = self._clock()
            peak = self._walk(run, start) if narrow else self._search(run, start)
            sweep_s = self._clock() - t
            if peak is None:
                if narrow:                      # back where it was, from below
                    self._move(run, start - config.AF_BACKLASH_STEPS)
                    self._move(run, start)
                out = Outcome(NO_PEAK, sweep_s=sweep_s)
            else:
                t = self._clock()
                step, half = config.AF_FINE_STEPS
                fine: dict[int, float] = {}
                self._scan(run, _steps(peak - half, peak + half, step), fine)
                best = max(fine, key=fine.get)
                # onto the best from below, as every measured move came
                self._move(run, best - config.AF_BACKLASH_STEPS)
                self._move(run, best)
                at_rest = self._score(self._frame(run).luma, x, y, config.AF_REGION)
                fine_s = self._clock() - t
                with self._lock:
                    if run.gen != self._gen:
                        raise _Stop
                    self.ptz.learn_focus(best)
                out = Outcome(FOCUSED, best, fine[best], at_rest,
                              sweep_s=sweep_s, fine_s=fine_s)
        except _Stop:
            out = Outcome(CANCELLED, sweep_s=sweep_s, fine_s=fine_s)
        finally:
            with self._lock:
                if run.gen == self._gen:
                    self.ptz.give_lens(self)
        out.seconds = self._clock() - t0
        out.waiting_s, out.samples = run.waiting_s, run.samples
        self._report(out, run, start, narrow)
        if on_done is not None:
            on_done(out)
        return out

    def _report(self, out: Outcome, run: _Run, start: float | None, narrow: bool) -> None:
        """One line for a person, and for a focused sweep one for a program."""
        if out.result == CANCELLED:
            return
        where = f"({run.x:.2f}, {run.y:.2f}) from step {start:.0f}"
        spent = (f"in {out.seconds:.1f} s (sweep {out.sweep_s:.1f} s, fine {out.fine_s:.1f} s; "
                 f"{out.waiting_s:.1f} s of it waiting on the lens; {out.samples} sweep samples)")
        if not out.focused:
            print(f"[af] {where}: no peak {spent}"
                  f"{': lens left where it was' if narrow else ''}")
            return
        short = out.at_rest < 0.7 * out.sharpness
        print(f"[af] {where} → focus {out.steps} {spent}: sharpness {out.sharpness:.0f}, "
              f"{out.at_rest:.0f} where it stopped"
              f"{'  (well short: backlash? raise AF_BACKLASH_STEPS)' if short else ''}")
        print("[af-data] " + json.dumps({
            "zoom_mm": round(self.ptz.zoom_mm, 2), "zoom_steps": self.ptz.zoom_steps,
            "focus_steps": out.steps, "from_steps": round(start), "narrow": narrow,
            "subject_m": None if self.ptz.subject_m is None else round(self.ptz.subject_m, 2),
            "sharpness": round(out.sharpness, 1), "at_rest": round(out.at_rest, 1),
            "seconds": round(out.seconds, 2), "waiting_s": round(out.waiting_s, 2),
            "samples": out.samples}))

    # ---- finding the peak ---------------------------------------------------
    def _search(self, run: _Run, start: float) -> float | None:
        """Where the sharpness peaks, widening until a clear peak shows."""
        peak = None
        for half in config.AF_SWEEP_HALVES_STEPS:
            lo, hi = max(0.0, start - half), min(float(LENS_STEPS), start + half)
            curve = self._sweep(run, hi, lo)
            if not curve:
                continue
            best_pos, best = max(curve, key=lambda c: c[1])
            ranked = sorted(v for _p, v in curve)
            whole = half >= LENS_STEPS
            at_edge = not whole and (best_pos <= lo + _EDGE_STEPS or best_pos >= hi - _EDGE_STEPS)
            peak = best_pos
            if best >= config.AF_PEAK_RATIO * ranked[len(ranked) // 2] and not at_edge:
                break
        return peak

    def _walk(self, run: _Run, start: float) -> float | None:
        """Where the sharpness peaks close to `start`, or None if it doesn't.

        The window sits near focus, so most of it scores high and a peak is
        not many times the median, as in _search: it is a best position inside
        the window, standing above the window's ends by AF_REFOCUS_RISE. Best
        at an end: sharper further on, so the next window goes that way.
        """
        half, centre = config.AF_REFOCUS_HALF_STEPS, start
        for _ in range(config.AF_REFOCUS_WINDOWS):
            lo, hi = max(0.0, centre - half), min(float(LENS_STEPS), centre + half)
            curve = self._sweep(run, hi, lo)
            if len(curve) < 3:
                return None
            best_pos, best = max(curve, key=lambda c: c[1])
            ends = max(curve[0][1], curve[-1][1])
            if best_pos >= hi - _EDGE_STEPS and hi < LENS_STEPS:
                centre = hi + half / 2      # overlapping: a peak on the seam shows
            elif best_pos <= lo + _EDGE_STEPS and lo > 0.0:
                centre = lo - half / 2
            else:
                return best_pos if best >= config.AF_REFOCUS_RISE * ends else None
        return None

    def _sweep(self, run: _Run, a: float, b: float) -> list[tuple[float, float]]:
        """Run the focus motor a → b in one move, scoring each frame on the
        way: [(position, sharpness), …]. A frame's position is where the
        motor was when it was exposed. Rough — backlash blurs it by a step
        or two — which the fine pass after puts right."""
        self._move(run, a)
        with self._lock:
            if run.gen != self._gen:
                raise _Stop
            self.ptz.set_focus_steps(b, owner=self)
        t0 = self._clock()
        timed: list[tuple[float, float]] = []
        while self._clock() - t0 < config.LENS_TRAVEL_S + 2.0:
            got = self.camera.frame()
            if got is None:
                raise _Stop                     # the camera went to sleep
            timed.append((got.at, self._score(got.luma, run.x, run.y, config.AF_REGION)))
            run.samples += 1
            if run.gen != self._gen:
                raise _Stop
            if not self.ptz.lens_busy():
                break
        started, stopped = self.ptz.lens_run
        if not t0 - 0.5 <= started < stopped:   # no controller to say: by our own clock
            started, stopped = t0, self._clock()
        span = max(1e-3, stopped - started)
        return [(a + (b - a) * max(0.0, min(1.0, (t - started) / span)), v) for t, v in timed]

    def _scan(self, run: _Run, positions: list[int], scores: dict[int, float]) -> None:
        """Score each position into `scores`, stopping at each, all moves upward."""
        positions = sorted(positions)
        self._move(run, positions[0] - config.AF_BACKLASH_STEPS)
        for pos in positions:
            self._move(run, pos)
            scores[pos] = self._score(self._frame(run).luma, run.x, run.y, config.AF_REGION)

    # ---- the lens and the camera ----------------------------------------------
    def _move(self, run: _Run, steps: float) -> None:
        """The focus motor to `steps` and stopped there; _Stop if superseded."""
        with self._lock:
            if run.gen != self._gen:
                raise _Stop
            self.ptz.set_focus_steps(max(0.0, min(float(LENS_STEPS), steps)), owner=self)
        self._wait(run, config.AF_EXTRA_SETTLE_S)

    def _wait(self, run: _Run, settle_s: float = 0.0) -> None:
        """Until the lens has stopped, and `settle_s` more; the time is kept."""
        t = self._clock()
        self.ptz.wait_lens()
        if settle_s:
            self._sleep(settle_s)
        run.moved_at = self._clock()
        run.waiting_s += run.moved_at - t

    def _frame(self, run: _Run):
        """The first frame exposed wholly after the last move settled: one
        already under way then shows the lens moving. _Stop if the camera is
        asleep."""
        for _ in range(4):
            got = self.camera.frame()
            if got is None:
                raise _Stop
            if got.at >= run.moved_at:
                break
        return got


class Refocus:
    """When to autofocus: zoom, wait until the lens has really stopped, then
    focus. One operation, in one place.

    Whoever moves the zoom needn't know about focus. Each control tick
    (`tick`) this notices that the zoom is AF_REZOOM_MM from where the picture
    was last focused, waits for the lens to be at rest (Ptz.lens_moving, which
    the lens thread keeps: not a guess at how long a move takes), and starts
    an autofocus. A search that finds no peak is tried again
    AF_REFOCUS_RETRIES times, AF_TRACK_GAP_S apart; a zoom counts as focused
    only once one succeeds or those run out.
    """

    def __init__(self, ptz: Lens, autofocus: AutoFocus,
                 clock: Callable[[], float] = time.monotonic) -> None:
        self.ptz = ptz
        self.autofocus = autofocus
        self._clock = clock
        self.reset()

    def reset(self) -> None:
        """A new state or session: nothing is due, and the picture counts as
        focused for the zoom it has."""
        self._focused_mm = self.ptz.zoom_mm
        self._due: float | None = None       # autofocus wanted from then
        self._started_at = float("-inf")     # when the last one began
        self._tries = 0                      # retries used since it was last due afresh

    def request(self, delay_s: float = 0.0) -> None:
        """Autofocus wanted, `delay_s` from now at the earliest (a moment for
        the exposure to settle after waking, or the zoom slider to stop)."""
        self._due = self._clock() + delay_s
        self._tries = 0

    def now(self, x: float, y: float, narrow: bool = False) -> None:
        """Autofocus on (x, y) at once: a tap, or locking on to a person."""
        self._tries = 0
        self._start(x, y, narrow)

    def tick(self, x: float, y: float, narrow: bool = False, gap_s: float = 0.0,
             watch_zoom: bool = True) -> None:
        """One control tick: start the autofocus that is due, on (x, y), once
        the lens is at rest and the last one began at least `gap_s` ago.
        `watch_zoom`: a zoom moved by AF_REZOOM_MM makes one due."""
        now = self._clock()
        if (watch_zoom and self._due is None
                and abs(self.ptz.zoom_mm - self._focused_mm) >= config.AF_REZOOM_MM):
            self._due, self._tries = now, 0
        if (self._due is None or now < self._due or self.ptz.lens_moving
                or now - self._started_at < gap_s):
            return
        self._start(x, y, narrow)

    def _start(self, x: float, y: float, narrow: bool) -> None:
        self._due = None
        self._focused_mm = self.ptz.zoom_mm
        self._started_at = self._clock()
        self.autofocus.start(x, y, narrow, on_done=self._done)

    def _done(self, out: Outcome) -> None:
        """On the autofocus thread. No peak: due again, a few times."""
        if out.result == NO_PEAK and self._tries < config.AF_REFOCUS_RETRIES:
            self._tries += 1
            self._due = self._clock() + config.AF_TRACK_GAP_S


class _Stop(Exception):
    """A newer request replaced this sweep, or the camera went to sleep."""


def _steps(lo: float, hi: float, step: float) -> list[int]:
    """Whole motor positions from `lo` to `hi`, about `step` apart, inside
    the travel."""
    lo, hi = max(0.0, lo), min(float(LENS_STEPS), hi)
    n = max(1, round((hi - lo) / step))
    return sorted({int(round(lo + i * (hi - lo) / n)) for i in range(n + 1)})
