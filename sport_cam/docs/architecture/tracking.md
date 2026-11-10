# Person tracking: audit and improvements

An audit of the tracking code as of commit `f495695` (2026-11-10), with a
list of changes for others to implement. The companion audit of the lens is
in [zoom_focus.md](zoom_focus.md).

**Scope.** `tracker.py`, `camera.py`, `detector.py`, `motion.py`, the
tracking and joystick parts of `main.py` and `ptz.py`, and their tests. The
vision-only tracker (`src/without_uwb/device`) is the main subject; file and
line references are to that build unless noted.

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
| Frames | `camera.py` `Camera._capture` | One 1280×720 preview frame per call, converted from YUV to RGB, under a lock shared by every consumer. |
| Detection | `camera.py` `_detect_loop`, `detector.py` | A thread runs MobileNet-SSD at `DETECT_FPS_TRACKING` (3 per second), on a strip around the followed person or, every sixth time, the whole frame. Each result is handed to the tracker once (`fresh`). |
| Choosing the person | `tracker.py` `_pick`, `_select`, `_looks_like` | The nearest box to the last position inside a gate, checked against a short-lived colour memory of the person's torso. |
| Pointing | `tracker.py` `_seen`, `_slew`, `motion.py` | Each fresh detection sets pan and tilt goals from the pose the head had when the frame was taken; the 20 Hz loop eases the servos toward them. |
| Framing | `tracker.py` `_frame_zoom`, `_look_wide` | One zoom correction per lens move; straight to wide when the person has been missing `LOST_ZOOM_OUT_S`. |
| Modes | `tracker.py` `step` | SEARCH (sweep), FOUND (following, not yet confirmed), TRACK. |

## Defects (P0)

### TR-1 The last seen position drifts to the frame centre while the person is lost

`Tracker._look_wide` (`tracker.py:467-486`) runs on every 20 Hz tick once the
person has been missing `LOST_ZOOM_OUT_S`. Each call scales `_last_centre`
toward the frame centre by the zoom ratio, assuming the zoom-out it requests
happens. `Ptz.set_zoom_mm` refuses the move when the lens is within
`ZOOM_MIN_STEP_MM` (0.15 mm) of wide, or while autofocus runs. The zoom then
stays above `ZOOM_MIN_MM`, the condition stays true, and the scaling is
applied again on every tick. Within a few seconds the remembered position has
collapsed to the centre of the frame, and the gate that decides who is "our"
person is centred on the wrong place.

- Fix: scale the position once, when a zoom-out is actually accepted. This
  needs `set_zoom_mm` to say whether it moved the lens
  ([zoom_focus.md](zoom_focus.md), ZF-3). TR-3 removes the need for the
  scaling altogether.
- Test: lens at 4.45 mm, person lost, step for 3 s, and assert
  `_last_centre` has moved by one zoom ratio at most.

### TR-2 Dead assignments in `_look_wide`

`tracker.py:482-483` set `_zoom_moved_at` to minus infinity and
`_zoom_off_since` to `None`; line 485 then overwrites `_zoom_moved_at`. The
two lines were inserted by a text replacement in commit `763efcb` that
matched one place too many. Delete line 482; keep the `_zoom_off_since`
reset.

### TR-3 The "same person" gate is measured in pixels of a picture that moves

`Tracker._select` (`tracker.py:302-333`) accepts the box nearest to
`_last_centre` within `TRACK_GATE_FRACTION` of the frame width. Both
positions are in pixels, from two frames between which the head has turned
and the lens may have zoomed. The camera's own motion is counted as the
person's. At full zoom the frame is about 33° wide, so a pan at 20°/s moves a
stationary person by a fifth of the frame between detections, which is the
whole gate. `_look_wide` already carries a special case to patch this for one
zoom move.

- Fix: remember the last position as angles (pan and tilt of the head when
  the frame was taken, plus the box's offset converted with `_px_to_hdeg` /
  `_px_to_vdeg`), and gate on the angular distance to each new box computed
  the same way. `_pose_at` already supplies the pose at capture. The
  `_look_wide` rescaling and TR-1 then disappear.

### TR-4 The joystick moves the head by a nominal time step, not the real one

`Head.manual_aim` (`main.py:428`) calls `ptz.jog(pan, tilt,
1.0 / CONTROL_RATE_HZ)`. When a control tick runs late (the `[timing]` log
exists because they do), the head still advances by 50 ms of travel, so it
slows and then appears to catch up. `Tracker.step` and `Head._ease_head`
both use the measured time since the last tick.

- Fix: pass the measured interval, capped as the tracker caps it (0.25 s).

### TR-5 A detection's capture time is taken before the capture

`Camera._detect_loop` (`camera.py`, `_detect_at = now` … `captured_at = now`)
stamps a result with the time *before* `_capture` was called. `_capture`
then waits for the camera lock, which autofocus and the live view also hold,
and for the next frame. `Tracker._pose_at` uses that stamp to find where the
head pointed when the frame was taken, so under contention the pan and tilt
corrections are computed from the wrong pose.

- Fix: stamp each frame with its exposure time from the camera
  (`SensorTimestamp` in the Picamera2 request metadata) and carry it with the
  boxes. Confirm first that it shares a clock with `time.monotonic()`
  ([zoom_focus.md](zoom_focus.md), ZF-17).

## Code quality

### TR-6 (P1) The two builds' framing logic has drifted

The vision-only tracker waits for the fill to stay off target
(`ZOOM_FILL_HOLD_S`) and applies a deadband (`ZOOM_FILL_DEADBAND`) before a
zoom correction. The UWB tracker's `_frame_zoom` has neither, though
`ZOOM_FILL_HOLD_S` sits unused in its `config.py`. The guard and fill
arithmetic is otherwise copied.

- Fix: one framing function used by both trackers. It is nearly pure
  already: given the box, the current zoom, the time and a small state
  (last move, off-target since), it returns a zoom step or nothing.

### TR-7 (P1) `Tracker` is five jobs in one class

`tracker.py` holds the mode machine, the choice of person (gate and colour
memory), pointing, the distance estimate and zoom framing in one class of
about 25 fields, most of them created in `_begin_search` and not in
`__init__`. The tests reach into private members to exercise one job at a
time (`tr._frame_zoom`, `tr._efl`, `tr._select`, `tr._look`).

- Fix: lift the choice of person and the framing into small units with their
  own state and no camera or servo dependencies, tested directly. `Tracker`
  keeps the mode machine and pointing. Declare every field in `__init__`.

### TR-8 (P2) Comments describe a detector and a state machine that have changed

- `tracker.py:424-429` and `config.py:305-314` justify the zoom guard by
  what "HOG cannot detect"; the detector is SSD, whose boxes are clipped at
  the frame edge, which is why the edge test works.
- `tracker.py:9`, `:32`, `:69`, `:105`, `:468`: TRACK is described as
  "recording" and `confirm()` as "Recording has started". Since the state
  change, tracking and recording are separate states and `confirm()` is
  called at lock-on. Rename `confirmed` to what it means (locked on).
- `camera.py:89` gives the detection time as HOG's.

### TR-9 (P2) Labels are matched by value

`Tracker._label` (`tracker.py:254`) marks a box CLIMBER when
`b == followed`. Boxes are tuples, so two detections with the same
coordinates are both the climber. Compare by identity (`is`).

### TR-10 (P2) Production code bends to its test fakes

`getattr(self.ptz, "lens_moving", False)` and
`getattr(self.camera, "captured_at", None)` exist only because the fakes in
`tests/test_tracker.py` lack those members. See
[zoom_focus.md](zoom_focus.md), ZF-11, for the fix.

## Performance

### TR-11 (P1) The live view is produced when nobody is watching

`Head.frame_loop` (`main.py:586-596`) captures a frame, converts it to RGB
and encodes a JPEG 15 times a second in every awake, tracking and recording
state. `LocalApi.publish_frame` stores it and `CloudLink.preview` returns
early when unwatched, so with no viewer the work is thrown away. It also
takes the camera lock 15 times a second, which the detector and autofocus
wait on.

- Fix: skip the capture and encode unless `Head.watched` is true. The only
  reader of `LocalApi._frame` is the MJPEG stream, which counts as a viewer.
  A recording with the phone put away is the common case and gets the whole
  saving.

### TR-12 (P1) Every consumer waits for its own frame

`Camera._capture` holds `_cam_lock` while it waits for the next frame, so the
detector, autofocus, the live view and QR reading queue behind one another
and each gets a different frame. With the live view open during an autofocus
sweep, the sweep's sample rate falls by the share the others take.

- Fix: one place that fetches frames on demand and hands the same frame to
  everyone waiting ("a frame newer than the one I had"). It should fetch only
  while someone is waiting, so an idle camera costs nothing, and keep the
  frame as YUV so each consumer converts only what it needs.

### TR-13 (P1) Convert each frame once, to what is needed

- `Camera.preview_jpeg` converts YUV to RGB and then passes
  `rgb[:, :, ::-1]` to the encoder, a reversed view that must be copied to
  be encoded. Convert straight to BGR (`COLOR_YUV2BGR_I420`).
- `Camera.qr_text` converts YUV to RGB to grey. The grey image is the Y
  plane of the frame; use it directly.
- Autofocus has the same waste ([zoom_focus.md](zoom_focus.md), ZF-14).

### TR-14 (P1) Measure detection

Nothing records how long a detection takes or how old a result is when the
tracker acts on it. `DETECT_FPS_TRACKING`, the easing time and the gate were
all tuned without those numbers, and the `[timing]` log covers only control
ticks and joystick messages.

- Fix: log, every so many detections, the inference time, the time from
  exposure to the tracker using the boxes, and whether it was a strip or a
  whole-frame pass. Any change to the detection rate should start from this.

### TR-15 (P2) Unchanged servo positions are re-sent every tick

`Tracker._slew` calls `set_pan` and `set_tilt` on every tick, and
`PigpioServos.write` (`ptz.py:278-285`) sends each to the pigpio daemon over
its socket even when the value is the same as last time. `ArducamServos`
already skips unchanged values.

- Fix: remember the last duty sent per channel and skip a repeat. This
  removes two socket round trips per tick whenever the head is still.

## Not recommended yet

These may help, but it is not certain, so they are not recommendations. Each
needs a measurement on the camera first.

| Idea | What is unknown |
|---|---|
| Predict the person's motion (a velocity term in the pan and tilt goals) to remove the stop-start movement seen in recordings | At 3 detections a second with noisy boxes, a velocity estimate may add more jitter than it removes. Needs TR-14 and TR-5 first. |
| Raise `DETECT_FPS_TRACKING` | Bounded by the inference time on the Pi, which has not been measured (TR-14). |
| A different inference backend or thread count for OpenCV's DNN module | Not measured on the Pi 4. |
| Sudden pan and tilt jumps during lens moves | Suspected to be the 5 V supply sagging when the focus motor runs. Unconfirmed: needs `vcgencmd get_throttled` after a jump. |
| Widen or narrow the gate and colour thresholds | Tuned on a handful of samples from one room. Needs recordings from the climbing wall. |
