"""Contrast autofocus: sweep the focus motor, keep the sharpest position.

The same measure focuscal calibrates FOCUS_GRID with — the variance of the
Laplacian, here over a square around a point of the frame rather than its
centre. The focus motor is slow (about a tenth of its travel a second) and a
scene is sharp in a narrow band of it, so a sweep starts where the lens is
already — FOCUS_GRID's focus for the zoom, or the last autofocus — and looks
outward in widening windows (AF_WINDOWS), stopping at the first with a clear
peak, then refines round it (AF_FINE_PASSES).

Two things a sweep must get right, or it passes through focus and stops
somewhere else:

  * the frame scored is one taken with the lens where it was sent: each step
    waits out the move by time (Ptz.wait_lens: the controller's busy flag is
    never set), then throws away the frame already being exposed, and
    scores the next;
  * the lens gears have backlash, so the same motor position is a different
    focus coming from above or from below. Every measured move goes upward
    (each pass starts AF_BACKLASH below its first position), and so does the
    last move onto the best one.

Awake only (main.py): when the app taps the live view, focusing on what is
under the tap, and after the app's zoom comes to rest, on the last point
tapped (the centre until then). Never while tracking or recording: the
search would show in the clip. Those focus from FOCUS_GRID by distance.

It runs on its own thread, like detection: each step waits on the motor and
for frames, which the 20 Hz control loop can't. A newer request, or
`cancel()`, makes a running sweep stop at its next step. Each sweep prints a
line — the scores, and how sharp it is where it stopped — to tell a bad
sweep from a soft scene.
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
                 sleep: Callable[[float], None] = time.sleep) -> None:
        self.camera = camera
        self.ptz = ptz
        self._score = score
        self._sleep = sleep
        self._lock = threading.Lock()
        self._gen = 0          # bumped by every start/cancel: older sweeps stop
        self.busy = False      # a sweep is running (telemetry `focusing`)

    def start(self, x: float, y: float) -> None:
        """Focus on (x, y) of the frame, on a thread; replaces a running sweep."""
        with self._lock:
            self._gen += 1
            gen = self._gen
            self.busy = True
        threading.Thread(target=self.focus, args=(x, y, gen),
                         name="autofocus", daemon=True).start()

    def cancel(self) -> None:
        with self._lock:
            self._gen += 1
            self.busy = False

    def focus(self, x: float, y: float, gen: int | None = None) -> float | None:
        """One sweep, here and now; the motor position chosen (0…1), or None
        if it was cancelled or there is no picture."""
        if gen is None:
            with self._lock:
                self._gen += 1
                gen = self._gen
                self.busy = True
        t0 = time.monotonic()
        try:
            self.ptz.wait_lens()                # a zoom still travelling
            start = self.ptz.focus_pos
            start = 0.5 if start is None else start
            scores: dict[float, float] = {}
            step = config.AF_SCAN_STEP
            for half in config.AF_WINDOWS:
                lo = max(0.0, start - half)
                hi = min(1.0, start + half)
                grid = [round(k * step, 6) for k in range(int(lo / step + 0.999), int(hi / step + 1e-6) + 1)]
                todo = [p for p in grid if p not in scores]
                if todo:
                    self._scan(gen, x, y, todo, scores)
                best = max(scores, key=scores.get)
                at_edge = (best in (min(grid), max(grid))) and 0.0 < best < 1.0 and half < 1.0
                ranked = sorted(scores.values())
                if scores[best] >= config.AF_PEAK_RATIO * ranked[len(ranked) // 2] and not at_edge:
                    break
            scan = dict(sorted(scores.items()))
            for fine_step, fine_half in config.AF_FINE_PASSES:
                fine: dict[float, float] = {}
                self._scan(gen, x, y, _steps(best - fine_half, best + fine_half, fine_step), fine)
                best = max(fine, key=fine.get)
                best_score = fine[best]
            # onto the best from below, as every measured move came
            self._move(gen, best - config.AF_BACKLASH)
            self._move(gen, best)
            at_rest = self._score(self._frame(), x, y, config.AF_REGION)
            print(f"[af] ({x:.2f}, {y:.2f}) from {start:.0%} → focus {best:.3f} in "
                  f"{time.monotonic() - t0:.1f} s: sharpness {best_score:.0f} in the sweep, "
                  f"{at_rest:.0f} where it stopped"
                  f"{'  (well short: backlash? raise AF_BACKLASH)' if at_rest < 0.7 * best_score else ''}"
                  f"\n[af]   scan: " + " ".join(f"{p:.0%}:{v:.0f}" for p, v in scan.items()))
            return best
        except _Stop:
            return None
        finally:
            with self._lock:
                if gen == self._gen:
                    self.busy = False

    def _scan(self, gen: int, x: float, y: float, positions: list[float],
              scores: dict[float, float]) -> None:
        """Score each position into `scores`, all moves upward."""
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
        self.ptz.wait_lens()                    # by time: the controller never says
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
