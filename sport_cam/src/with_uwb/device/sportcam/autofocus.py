"""Contrast autofocus: sweep the focus motor, keep the sharpest position.

The same measure focuscal calibrates FOCUS_GRID with — the variance of the
Laplacian, here over a square around a point of the frame rather than its
centre. The focus motor is slow (≈ 5 s end to end) and a scene is sharp in a
narrow band of it, so a sweep:

  1. runs the motor down through a window around where it already is
     (FOCUS_GRID's focus for the zoom, corrected by the last autofocus) in
     one continuous move, scoring every frame on the way — downward, so it
     ends below the peak, where the fine pass starts. Each frame's position is read off
     the clock: the move runs at a steady speed between the write and the
     controller's busy flag clearing, and a frame shows the lens AF_FRAME_LAG_S
     before it is handed over. No clear peak: once more over the whole travel
     (AF_SWEEP_HALVES). A `narrow` search never does that: its windows walk
     towards rising sharpness (AF_REFOCUS_WINDOWS), and with no peak in them
     the lens goes back where it was;
  2. refines round the peak in short steps (AF_FINE), each move upward and
     the last one onto the best from below, as the gears have backlash;
  3. keeps where it ended, relative to FOCUS_GRID, as the focus trim
     (Ptz.learn_focus): later zoom moves and sweeps stay near focus.

While it runs, Ptz.af_active holds off everyone else's zoom and focus moves,
and the trackers don't count frames it blurs as their person lost.

Awake: on a tap on the live view, once the zoom has come to rest, and on
waking. Tracking: as the camera locks on to its person. Tracking and
recording: once the tracker's own zoom has come to rest, a narrow search
close by. A zoom move refocuses from FOCUS_GRID, whose sharp band is too thin
to hit, and a blurred person can't be seen to be followed. The search shows
briefly in a clip, which is better than the clip staying blurred.

It runs on its own thread, like detection. A newer request, or `cancel()`,
makes a running sweep stop at its next step. Each sweep prints a line — where
it started and stopped, how sharp, how long — to tell a bad sweep from a soft
scene.
"""
from __future__ import annotations

import threading
import time
from typing import Callable

from . import config


def sharpness(rgb, x: float, y: float, region: float) -> float:
    """Variance of the Laplacian over a square around (x, y), each 0…1 of the
    frame; the square's side is `region` of the frame's shorter side."""
    import cv2
    h, w = rgb.shape[:2]
    side = max(16, int(min(w, h) * region))
    x0 = int(max(0, min(w - side, x * w - side / 2)))
    y0 = int(max(0, min(h - side, y * h - side / 2)))
    grey = cv2.cvtColor(rgb[y0:y0 + side, x0:x0 + side], cv2.COLOR_RGB2GRAY)
    return float(cv2.Laplacian(grey, cv2.CV_64F).var())


class AutoFocus:
    def __init__(self, camera, ptz,
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
        self.busy = False      # a sweep is running (telemetry `focusing`)

    def start(self, x: float, y: float, narrow: bool = False) -> None:
        """Focus on (x, y) of the frame, on a thread; replaces a running sweep.
        `narrow`: search only close by (AF_REFOCUS_HALF), for a lens nearly
        right, in a moment that may be being filmed."""
        with self._lock:
            self._gen += 1
            gen = self._gen
            self.busy = True
        threading.Thread(target=self.focus, args=(x, y, gen, narrow),
                         name="autofocus", daemon=True).start()

    def cancel(self) -> None:
        with self._lock:
            self._gen += 1
            self.busy = False
            self.ptz.af_active = False

    def focus(self, x: float, y: float, gen: int | None = None,
              narrow: bool = False) -> float | None:
        """One autofocus, here and now; the motor position chosen (0…1), or
        None if it was cancelled or there is no picture."""
        if gen is None:
            with self._lock:
                self._gen += 1
                gen = self._gen
                self.busy = True
        t0 = self._clock()
        self.ptz.af_active = True
        try:
            self.ptz.wait_lens()                # a zoom still travelling
            start = self.ptz.focus_pos
            start = 0.5 if start is None else start
            if narrow:
                peak = self._walk(gen, x, y, start)
                if peak is None:
                    self._move(gen, start - config.AF_BACKLASH)
                    self._move(gen, start)
                    print(f"[af] ({x:.2f}, {y:.2f}) no peak near {start:.0%} in "
                          f"{self._clock() - t0:.1f} s: lens left where it was")
                    return None
            else:
                peak = self._search(gen, x, y, start)
            if peak is None:
                return None
            step, half = config.AF_FINE
            fine: dict[float, float] = {}
            self._scan(gen, x, y, _steps(peak - half, peak + half, step), fine)
            best = max(fine, key=fine.get)
            # onto the best from below, as every measured move came
            self._move(gen, best - config.AF_BACKLASH)
            self._move(gen, best)
            at_rest = self._score(self._frame(), x, y, config.AF_REGION)
            with self._lock:
                if gen != self._gen:
                    return None
                self.ptz.learn_focus(best)
            print(f"[af] ({x:.2f}, {y:.2f}) from {start:.0%} → focus {best:.3f} in "
                  f"{self._clock() - t0:.1f} s: sharpness {fine[best]:.0f}, {at_rest:.0f} "
                  f"where it stopped"
                  f"{'  (well short: backlash? raise AF_BACKLASH)' if at_rest < 0.7 * fine[best] else ''}")
            return best
        except _Stop:
            return None
        finally:
            with self._lock:
                if gen == self._gen:
                    self.busy = False
                    self.ptz.af_active = False

    def _search(self, gen: int, x: float, y: float, start: float) -> float | None:
        """Where the sharpness peaks, widening until a clear peak shows."""
        peak = None
        for half in config.AF_SWEEP_HALVES:
            lo, hi = max(0.0, start - half), min(1.0, start + half)
            curve = self._sweep(gen, x, y, hi, lo)
            if not curve:
                continue
            best_pos, best = max(curve, key=lambda c: c[1])
            ranked = sorted(v for _p, v in curve)
            at_edge = half < 1.0 and (best_pos <= lo + 0.01 or best_pos >= hi - 0.01)
            peak = best_pos
            if best >= config.AF_PEAK_RATIO * ranked[len(ranked) // 2] and not at_edge:
                break
        return peak

    def _walk(self, gen: int, x: float, y: float, start: float) -> float | None:
        """Where the sharpness peaks close to `start`, or None if it doesn't.

        The window sits near focus, so most of it scores high and a peak is
        not many times the median, as in _search: it is a best position inside
        the window, standing above the window's ends by AF_REFOCUS_RISE. Best
        at an end: sharper further on, so the next window goes that way.
        """
        half, centre = config.AF_REFOCUS_HALF, start
        for _ in range(config.AF_REFOCUS_WINDOWS):
            lo, hi = max(0.0, centre - half), min(1.0, centre + half)
            curve = self._sweep(gen, x, y, hi, lo)
            if len(curve) < 3:
                return None
            best_pos, best = max(curve, key=lambda c: c[1])
            ends = max(curve[0][1], curve[-1][1])
            if best_pos >= hi - 0.01 and hi < 1.0:
                centre = hi + half / 2      # overlapping: a peak on the seam shows
            elif best_pos <= lo + 0.01 and lo > 0.0:
                centre = lo - half / 2
            else:
                return best_pos if best >= config.AF_REFOCUS_RISE * ends else None
        return None

    def _sweep(self, gen: int, x: float, y: float, a: float, b: float) -> list[tuple[float, float]]:
        """Run the focus motor a → b in one move, scoring each frame on the
        way: [(position, sharpness), …], the position read off the clock.
        Rough — backlash and the frame lag blur it by a step or two — which
        the fine pass after puts right."""
        self._move(gen, a)
        with self._lock:
            if gen != self._gen:
                raise _Stop
            self.ptz.set_focus_pos(b)
        t0 = self._clock()
        timed: list[tuple[float, float]] = []
        end = None
        while self._clock() - t0 < config.LENS_TRAVEL_S + 2.0:
            rgb = self.camera._capture()
            if rgb is None:
                raise _Stop                     # the camera went to sleep
            t = self._clock()
            timed.append((t - config.AF_FRAME_LAG_S, self._score(rgb, x, y, config.AF_REGION)))
            if gen != self._gen:
                raise _Stop
            if t - t0 > 0.05 and not self.ptz.lens_busy():
                end = t
                break
        end = end or self._clock()
        span = max(1e-3, end - t0)
        return [(a + (b - a) * max(0.0, min(1.0, (t - t0) / span)), v) for t, v in timed]

    def _scan(self, gen: int, x: float, y: float, positions: list[float],
              scores: dict[float, float]) -> None:
        """Score each position into `scores`, stopping at each, all moves upward."""
        positions = sorted(positions)
        self._move(gen, positions[0] - config.AF_BACKLASH)
        for pos in positions:
            self._move(gen, pos)
            scores[pos] = self._score(self._frame(), x, y, config.AF_REGION)

    def _move(self, gen: int, pos: float) -> None:
        """The focus motor to `pos` and stopped there; _Stop if superseded."""
        with self._lock:
            if gen != self._gen:
                raise _Stop
            self.ptz.set_focus_pos(max(0.0, min(1.0, pos)))
        self.ptz.wait_lens()
        self._sleep(config.AF_EXTRA_SETTLE_S)

    def _frame(self):
        """A frame exposed wholly after the last move: the one already under
        way when it ended is thrown away. _Stop if the camera is asleep."""
        if self.camera._capture() is None:
            raise _Stop
        rgb = self.camera._capture()
        if rgb is None:
            raise _Stop
        return rgb


class _Stop(Exception):
    """A newer request replaced this sweep, or the camera went to sleep."""


def _steps(lo: float, hi: float, step: float) -> list[float]:
    lo, hi = max(0.0, lo), min(1.0, hi)
    n = max(1, round((hi - lo) / step))
    return [lo + i * (hi - lo) / n for i in range(n + 1)]
