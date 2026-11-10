# Zoom and focus: audit and improvements

An audit of the lens code as of commit `f495695` (2026-11-10), with a list of
changes for others to implement. The companion audit of person tracking is in
[tracking.md](tracking.md).

**Scope.** `ptz.py`, `autofocus.py`, `focuscal.py`, `lenscheck.py`, the lens
parts of `main.py` and `config.py`, and their tests, in both builds
(`src/with_uwb/device`, `src/without_uwb/device`). File and line references
are to the `without_uwb` build unless noted.

**How to read this.** Every item was found by reading the code and is certain
to improve correctness, code quality or performance. None has been reproduced
or measured on the camera unless the item says so. Ideas that might help but
are not certain are listed separately at the end and are *not*
recommendations.

Priorities: **P0** a defect in behaviour, **P1** worth doing soon, **P2**
cleanup.

## How it works today

| Part | Where | What it does |
|---|---|---|
| Controller access | `ptz.py` `Focuser` | I2C register reads and writes. Lens moves go through a queue on a `lens` thread, which waits for the controller's busy flag to clear before each write, because a write to a moving lens cuts the earlier move short. |
| Lens in engineering units | `ptz.py` `Ptz` | Zoom in mm through `ZOOM_CURVE`; focus from `FOCUS_GRID` (focal length × distance → motor position) plus a "trim" learned from the last autofocus. Rate limits and deadbands on both. |
| Autofocus | `autofocus.py` `AutoFocus` | Contrast autofocus on its own thread. A continuous sweep scores every frame, a stepped fine pass refines the peak, and the result is given to `Ptz.learn_focus`. A `narrow` search is used after a tracking zoom. |
| When to focus | `main.py` `Head` | On wake, on a tap, at lock-on, and after a tracking zoom has rested (`refocus_after_zoom`). |
| Calibration tools | `lenscheck.py`, `focuscal.py` | Measure which register is the zoom, the zoom range, and zoom → focus pairs. |

Lens positions are expressed on three scales: the controller's registers
(0–2100 on this kit), a legacy scale used by `config.py` and `Ptz`
(zoom 3000–20000, focus 0–20000), and a fraction of travel (0–1) used by
autofocus.

## Defects (P0)

### ZF-1 The autofocus trim cap is in the wrong unit, so the trim does almost nothing

`FOCUS_TRIM_MAX = 150` (`config.py:372`) is commented as "motor steps" and
was meant as controller steps (0–2100). `Ptz._trim` (`ptz.py:441-451`)
applies it to `_focus_trim`, which is on the legacy 0–20000 scale. The cap is
therefore 0.75 % of the focus travel, about 16 controller steps, where the
sharp band is about 100 controller steps wide and the corrections autofocus
learns are routinely larger than that. Since commit `763efcb` the learned
correction is in effect discarded, and every refocus after a zoom starts from
the uncorrected `FOCUS_GRID` position.

- Fix: express the cap on the scale `_focus_trim` uses (150 controller steps
  is about 1430 legacy units), and name the unit in the constant.
- Test: `tests/test_ptz.py` asserts the cap using `config.FOCUS_TRIM_MAX`
  itself, so it passes with any value. Assert against a figure in controller
  steps.
- ZF-5 removes the cause.

### ZF-2 `Ptz.lens_moving` says the lens has stopped while it is still moving

`Ptz._lens_set` (`ptz.py:472-482`) estimates when a move will finish as
`max(previous estimate, now + share of LENS_TRAVEL_S)`. But queued moves run
one after the other on the lens thread (`Focuser._lens_loop`,
`ptz.py:168-180`), so a zoom move and the focus move that follows it take the
*sum* of their times. After any zoom, `lens_moving` turns false while the
focus motor is still travelling, or before it has started.

Two callers depend on it:

- `Tracker.step` holds the "person lost" clock while the lens moves, so
  blurred frames are not counted as the person missing.
- `Tracker._frame_zoom` refuses to judge framing from a picture of a moving
  lens.

Both are wrong for the tail of every zoom move.

- Fix: the lens thread already knows the truth, since it polls the busy flag
  before every write. Have it publish "queue empty and controller idle" (a
  `threading.Event`), and make `lens_moving` read that. No I2C is needed from
  the control loop. Keep the time estimate only for a controller that never
  sets its busy flag.

### ZF-3 `Ptz.set_zoom_mm` drops requests without telling the caller

`set_zoom_mm` (`ptz.py:484-509`) returns nothing and silently ignores a
request when autofocus is running, when the change is under
`ZOOM_MIN_STEP_MM`, or inside `ZOOM_RATE_LIMIT_S`. Callers cope by asking
again every tick and by keeping their own copy of the pacing. This was the
root of the zoom overshoot fixed in `763efcb`, and it still causes:

- `Tracker._frame_zoom` records a framing move and spends its
  `ZOOM_TRACK_DWELL_S` even when the lens refused the move.
- `Tracker._look_wide` corrupts the last seen position
  ([tracking.md](tracking.md), TR-1).

- Fix: return whether the move was accepted (and why not), and have callers
  act on it. Do the same for `set_focus`.

## Code quality

### ZF-4 (P1) Calibration tools and configuration use different units

`lenscheck` prints controller register values (0–2100). `ZOOM_CURVE` and
`FOCUS_GRID` want the legacy scale, so every calibration is converted by
hand (for example focus 225 → 2140). ZF-1 is the same confusion inside the
code.

- Fix, minimum: make `lenscheck` and `focuscal` print ready-to-paste
  `ZOOM_CURVE` and `FOCUS_GRID` lines in the unit `config.py` uses, and put
  the unit in the name of every constant that holds a motor position or
  offset.

### ZF-5 (P1) Three scales for one motor position

`Focuser._register` rescales legacy values to register values;
`Ptz.focus_pos`, `set_focus_pos` and `learn_focus` convert fractions to
legacy values; logs mix all three. Each conversion is a place for the ZF-1
class of bug.

- Fix: keep one internal unit for lens positions, convert once at the I2C
  boundary, and give positions a small type (or at least consistently
  suffixed names) so a trim in one unit cannot be compared with a cap in
  another.

### ZF-6 (P1) Three implementations of "wait for the lens"

`Focuser._wait_idle` (`ptz.py:224-229`), `Ptz.lens_busy` (`ptz.py:459-470`)
and `Ptz.wait_lens` (`ptz.py:516-546`) each poll the busy flag with their own
rules (`_busy_seen`, 0.05 s, 0.3 s, fall back to time). They can disagree
about whether the lens is moving.

- Fix: with the idle event from ZF-2, `wait_lens` becomes a wait on that
  event and `lens_busy` a read of it. Keep one fallback path for a controller
  with no busy flag.

### ZF-7 (P1) Who may move the lens is a bare boolean shared between threads

`Ptz.af_active` is set by the autofocus thread and read by the control loop
in `set_zoom_mm`, `set_focus` and `refocus`. The check and the move are not
atomic, so a zoom can be accepted just as a sweep begins. `AutoFocus.busy` is
a second flag for the same fact.

- Fix: make lens ownership explicit in `Ptz` (one lock-guarded owner, taken
  by autofocus for the length of a sweep) and derive `busy` from it.

### ZF-8 (P1) Autofocus does not report how it ended

`AutoFocus.start` is fire-and-forget. `Head.focus_on_subject`
(`main.py:467-479`) stamps `_af_zoom` and `_af_track_at` when the sweep
*starts*, so a sweep that found no peak, or was cancelled, counts as done and
is not retried until the zoom changes by another `AF_REZOOM_MM`. The only
record of the outcome is a printed line.

- Fix: deliver the outcome (focused at X, no peak, cancelled) to the caller
  through a callback or future. `Head` then marks a zoom as focused only on
  success and owns the retry decision.

### ZF-9 (P1) Lens pacing is spread over four classes

| Class | Pacing it holds |
|---|---|
| `Ptz` | `ZOOM_RATE_LIMIT_S`, `FOCUS_RATE_LIMIT_S`, `_lens_until` |
| `Tracker` | `_zoom_moved_at`, `ZOOM_TRACK_DWELL_S`, `ZOOM_FILL_HOLD_S` |
| `Head` | `_zoom_seen`, `_zoom_moved_at`, `_af_track_at`, `_af_due`, `AF_AFTER_ZOOM_S`, `AF_TRACK_GAP_S` |
| `AutoFocus` | `wait_lens` before a sweep |

`Head` and `Tracker` each have a `_zoom_moved_at` with a different meaning.
`Head.refocus_after_zoom` decides the zoom "has rested" by polling the
*commanded* zoom and waiting `AF_AFTER_ZOOM_S`, which says nothing about
whether the motor has stopped.

- Fix: make "zoom, wait until the lens is really idle, then narrow
  autofocus" one operation in one place, built on ZF-2 and ZF-8. `Tracker`
  asks for a framing change; it does not need to know about refocusing.
  This also starts the refocus as soon as the lens stops, not after a fixed
  delay.

### ZF-10 (P2) Remove `LENS_SWAP_ZOOM_FOCUS`

`lenscheck` measured which register is the zoom (0x01) and `_IMX477_LENS`
records it. The flag is `False` in both builds, and with it `_lens_motor` and
half of `Focuser._register` exist only to support a wiring that was a wrong
guess.

### ZF-11 (P2) Production code bends to its test fakes

`getattr(self.ptz, "lens_moving", False)`,
`getattr(self.focuser, "lens_pending", False)` and
`getattr(self.camera, "captured_at", None)` appear ten times across the two
builds, only because the fakes in `tests/` lack those members. A typo in the
real attribute would silently read as `False`.

- Fix: define the interfaces the tracker and autofocus need
  (`typing.Protocol`), make the fakes implement them, and use plain attribute
  access.

### ZF-12 (P2) The same files are maintained twice

`autofocus.py`, `motion.py`, `lenscheck.py`, `samples.py` and the tests
`test_ptz.py`, `test_autofocus.py`, `test_camera.py`, `test_detector.py` are
byte-identical in the two builds; `ptz.py`, `detector.py` and `focuscal.py`
differ only in comments (and one HOG argument). Every change so far was made
twice by hand.

- Fix, minimum: add a check to `tools/claude-check.sh` that the files meant
  to be identical are identical.
- Fix, better: one shared package that both builds import, with
  `scripts/pi/deploy.sh` copying it alongside the build.

### ZF-13 (P2) Stale comments, dead settings

- `ptz.py:1-19`: the module header leads with the older controller's
  register table, which is the opposite of this kit's.
- `ptz.py:558-565`: `set_focus_pos` is described as "the app's focus
  slider"; the slider was removed and autofocus is its only caller.
- `ptz.py:388-389`: `park` says "relax the lens. Called on shutdown"; it
  only centres pan and tilt, and is called at boot and on leaving sleep too.
- `ptz.py:490-495`: `set_zoom_mm` refers to calibration "in docs/04".
- `ZOOM_DEADBAND_M` is unused in both builds; `ZOOM_FILL_HOLD_S` is unused
  in `with_uwb`.
- `Head` keeps autofocus state (`_af_zoom`, `_af_track_at`, `_zoom_seen`,
  `_zoom_moved_at`) as class attributes; move it to `__init__` with the rest.

## Performance

### ZF-14 (P1) Autofocus converts a whole frame to RGB to score a small grey square

Each autofocus frame goes through `Camera._capture`, which converts the full
1280×720 YUV frame to RGB; `sharpness` then crops a square and converts that
back to grey (`autofocus.py:45-54`). The grey image is already the Y plane of
the YUV frame.

- Fix: give `Camera` a luma capture (the first `height` rows of the YUV
  array, no conversion) and score on that. This removes a full-frame colour
  conversion from every frame of every sweep, which raises the number of
  samples a sweep gets.

### ZF-15 (P1) Record what autofocus measures

Each successful autofocus is a measured point on the lens's real zoom →
focus curve, and is printed in a format meant for people. The curve in
`FOCUS_GRID` comes from six points, linearly interpolated.

- Fix: log every successful autofocus as one machine-readable line (zoom
  position, focus position found, estimated distance, sharpness, duration,
  number of sweep samples), and let `lenscheck` take its stop list as an
  argument (it is fixed at four stops, `lenscheck.py:35`). More measured
  stops reduce the interpolation error with no code risk, and the log shows
  where the grid is wrong.

### ZF-16 (P1) Measure where an autofocus spends its time

A narrow autofocus makes roughly ten stepped moves in its fine pass. Each
carries fixed waits: `_LENS_BUSY_RISE_S` (50 ms), `LENS_SETTLE_S` (50 ms),
`AF_EXTRA_SETTLE_S` (30 ms) and two frame captures (about 66 ms). That is
about 2 s of waiting in a refocus that is on film. Nobody has measured which
of these waits are needed.

- Fix: time each phase (sweep, fine pass, waits) and report it in the
  autofocus log line. The waits should only be shortened from that data; see
  "Not recommended yet".

### ZF-17 (P1) Use the frame's own timestamp

A sweep works out the lens position of each frame from the wall clock and a
guessed constant, `AF_FRAME_LAG_S`. `AutoFocus._frame` throws away one frame
after every move to be sure the next was exposed after it. Picamera2 reports
when each frame was exposed (`SensorTimestamp` in the request metadata).

- Fix: carry the exposure time with each frame, use it for sweep positions,
  and in `_frame` accept the first frame exposed after the move ended instead
  of discarding one blindly.
- First step: confirm on the Pi that `SensorTimestamp` and `time.monotonic()`
  share a clock (compare once at start-up, and apply the offset if there is
  one).
- The tracker benefits from the same timestamp
  ([tracking.md](tracking.md), TR-5).

## Not recommended yet

These may help, but it is not certain, so they are not recommendations. Each
needs a measurement on the camera first.

| Idea | What is unknown |
|---|---|
| Move zoom and focus together through the controller's combined register (0x0F), or program its built-in zoom → focus map (0x50/0x5B) | Not tested on this firmware (0x0104). The map registers read back empty. |
| Calibrate `FOCUS_GRID` at two or three distances | Every row of the grid is flat in distance today, so the distance estimate has no effect on focus. Whether distance matters enough at these focal lengths, given how noisy a distance from box height is, has not been measured. |
| Scale the trim with the square of the focal length (in the code since `763efcb`) | A heuristic. It holds for a distance error but not for interpolation error in the grid. Judge it from the ZF-15 log once ZF-1 is fixed. |
| Shorten the settle waits in the fine pass | Depends on ZF-16. |
| Replace the fine pass with a fit to the sweep's curve | Gear backlash may make the sweep too coarse. |
| A measured, non-linear `ZOOM_CURVE` | The curve has two points. The one scale measurement so far rested on 12 matched points. |
| Skip the refocus when the person is lost and the lens has gone wide | It blurs the picture while the detector is looking for them, but the wide end has also been reported soft. |
