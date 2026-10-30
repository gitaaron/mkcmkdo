# 15 — Verification checklist

Checks for everything that depends on a bought part rather than a design
value, ordered by **when the problem becomes detectable**. Cost of an error
rises down the page: a dimension caught before printing costs nothing; after
printing, up to a 14-hour reprint.

All sections are required. [Mistakes this design has already made](#mistakes-this-design-has-already-made)
lists three errors these checks catch.

## Before you print

Five measurements that change the CAD. Procedure: measure the part, enter the
value in [`cad/ordered_parts.toml`](../../../cad/ordered_parts.toml) with
`measured = true`, run `python3 cad/fit.py` from `sport_cam/` (re-solves the
layout, re-renders, audits fit).
[`cad/FIT_REPORT.md`](../../../cad/FIT_REPORT.md) lists the checks and any sizes
still assumed.

| # | Measure | Why it matters | What fit.py does / what a mistake costs |
| --- | --- | --- | --- |
| 1 | **Arducam base bolt spacing** → `[ptz] bolt_spacing` | The lid carries the whole camera on four bolts. Arducam publishes no drawing and the footprint has changed between revisions, so the lid is cut with radial slots, 30–72 mm by default | `fit.py` stretches the slots to your spacing; set `bolt_l` to the screws you have and it relieves the lid under the slots if they're short. Reprinting the lid is the **four-hour** mistake — measure before the printer starts |
| 2 | **Buck converter, PD trigger, battery gauge, power latch** → `[buck]`, `[pd_trigger]`, `[gauge]`, `[latch]` | They sit on the enclosure floor round the tripod boss and the shelf posts, under the LED window. Modules of the same rating vary a lot | `fit.py` rearranges them, lifts the boards onto risers over the boss, or makes the enclosure taller or wider. A **14-hour** reprint if you skip it |
| 3 | **Rocker switch and barrel jack** → `[switch]`, `[jack]` | Their cut-outs go in the wall, and the switch clips need a thin enough panel | `fit.py` sizes the cut-outs and thins the wall round the switch |
| 4 | **Pi heatsinks or fan case** → `[pi] heatsink_h` | The Pi sits on the shelf under the lid; a fan case is taller than stick-on heatsinks | `fit.py` makes the enclosure taller |
| 5 | **Camera power bank** → `[power_bank]` | The battery tray is a pocket sized to it. Banks of the same advertised capacity vary by 15 mm in every direction | Reprint the tray (3.5 h) |

**Tripod insert** (`[tripod_insert]`): floor bore = insert outside diameter
(12.7 mm assumed); insert length ≤ 8 mm (boss height). If the insert doesn't
fit, enlarge the bore with a drill rather than reprinting. Check both
threads: 3/8-16 screw into the insert; 1/4-20 screw with the bushing fitted.

## On arrival, before you wire anything

| Check | How | If it fails |
| --- | --- | --- |
| **Lid ring enters the enclosure mouth, and its inserts line up with the wall holes** | dry fit, no force | sand the ring or raise `clr` and reprint the lid |
| **Shelf drops onto its three posts** | dry fit, screws into the post inserts | check the post tops for stringing; a pass with a file |
| **Diffuser band slides down over the window onto its ledge** | dry fit | raise `clr` and reprint the band (1.5 h) |
| **The bank sits in the tray with the strap closed** | dry fit | back to item 5 above |

## Software checks

These need no hardware. Run them first, on any computer:

```bash
python3 src/without_uwb/device/tests/test_tracker.py
python3 src/without_uwb/device/tests/test_session.py
```

`test_tracker.py` covers the awake sub-states, the search sweep (and skipping
it when a person is already in frame), found → ready to record, re-search and the control
loops, and guards both of the tilt bugs below. `test_session.py` covers the
Track & record session: recording 3 s after found, stop recording → awake,
awake 30 s → sleep (held off while the live view is open), Record from sleep (still for the first look, then found or
the sweep),
the give-up timeout, and a session started with a person in frame.

## On the bench, before the first session

Do these in order. Each one assumes the one above passed.

| # | Check | How | If it fails |
| --- | --- | --- | --- |
| 1 | **Buck trimmed to 5.1 V under load** | 4 A dummy load on the output, meter at the Pi end | adjust the trimmer. Open-circuit voltage tells you nothing; a module reading 5.1 V unloaded can sag to 4.8 V and brown the Pi out. **Do this before the Pi is ever connected** |
| 2 | **PD trigger actually at 12 V** | meter on a real bank, with the item 14 cable | the trigger stays at 5 V if the cable is USB-A to C (no PD), or if the bank's PD output has no 12 V profile. Any C-to-C cable is fine |
| 2a | **Switch and latch, before the Pi** | rocker off: 0 V at the buck input. On: 12 V. SENSE: 2.7–3.0 V with the rocker on, 0 V off ([wiring, step 3](12-wiring.md#wiring-order-with-checks)) | 12 V with the rocker off: Q1 in backwards (S and D swapped), or R1 missing. 0 V with it on: Q3 or R2/R3, or S1/S2. SENSE above 3.3 V: R7/R8 swapped. **Don't connect S4 to the Pi until it reads right** |
| 3 | **I2C devices present** | `./scripts/pi/run sudo i2cdetect -y 1` shows `0c` and `40` | `0c` missing: PTZ controller unpowered or leads swapped. `40` missing: set `POWER_MONITOR = "none"` and carry on without a gauge |
| 4 | **Camera detected** | `./scripts/pi/camera-check.sh` | add `dtoverlay=imx477` to `/boot/firmware/config.txt` |
| 4a | **Switch off saves and powers down** | after the [Pi setup for the switch](14-software-setup.md#power-switch): start a recording, wait 30 s, switch off | the ring goes dark within a few seconds and the buck's LED ≈ 10 s later. After switching back on, the clip is in the library and plays to the end. Dies at once: HOLD (S3, `gpio=17=op,dh`). Never goes off: SENSE (S4, the `gpio-shutdown` line) or `POWER_OFF_ON_HALT` ([wiring: if something is wrong](12-wiring.md#if-something-is-wrong)) |
| 5 | **Ring lights evenly** | run the three state colours | move the ring up or down the window; it should sit 20–32 mm up |
| 6 | **Soft limits and servo direction** | `./scripts/pi/run ptzcheck` | narrow the limits in `config.py` if anything binds. If a positive pan command swings the lens the wrong way, flip `PAN_SIGN`; if a positive tilt command does not tilt it **up**, flip `TILT_SIGN`. Get either backwards and the camera runs away from the subject, which looks like a tracking fault and is not one |
| 6a | **Fine steps** | the last part of `ptzcheck`: the pan creeps 0° → 3° in 0.1° steps | smooth creep. Ticks of about a degree: the pan lead is still on the PTZ controller, or `SERVO_DRIVER = "arducam"` ([wiring, Servos](12-wiring.md#servos)). Nothing moves: `pigs hwver` (pigpiod up?), then M1–M7 |
| 6b | **Which person detector** | after `getmodel` ([software setup](14-software-setup.md)), with someone climbing in front of the camera — reaching, crouching, back turned, high on the wall: `./scripts/pi/run detectbench 120` | it prints each detector's time per frame, the rate that allows, and the share of frames that found a person, for the whole frame and for the tracking strip. Choose `DETECTOR = "ssd"` if it finds the climber in clearly more frames **and** manages 3 fps or better on the strip (its whole-frame search runs as two passes, so it is slower there). Otherwise keep `"hog"`. Lower `SSD_CONFIDENCE` if SSD misses a far climber; raise it on false people |
| 6a | **Joystick aims the head** | in the phone app on the camera's Wi-Fi (badge says Direct), camera awake: pull the knob a little left, then all the way; then up; then let go | a small pull creeps left, a full pull turns quickly; up tilts up; let go and it stops at once. Turns the wrong way: `PAN_SIGN` / `TILT_SIGN` (as above). No joystick: the app is connected through Firebase, or the camera isn't awake |
| 7 | **Focus grid** | `python -m sportcam.focuscal <metres>` with a target taped at 2, 5, 10 and 30 m | until you run it, focus is keyed on focal length alone — soft at the tele end away from the distance it happened to be set for |

## Camera-only checks

Run these in a normal room with the camera on its tripod, after the bench
checks above pass. Press **Track & record** in the app to start each one.

| # | Check | How | If it fails |
| --- | --- | --- | --- |
| 1 | **Sweep covers the range and reverses at the limits** | stand out of view, press Track & record, watch the pan for one full pass | it should go from about −80° to +80° and back, on both tilt rows (`SEARCH_TILT_ROWS_DEG`), without the servo binding or buzzing at either end. Binding: narrow the limits in `config.py`; wrong direction: flip `PAN_SIGN` / `TILT_SIGN` |
| 2 | **First-person lock** | walk into view while it sweeps | the sweep stops and the camera centres on the first person the HOG detector sees, ignoring a second person who arrives later |
| 2a | **Awake sub-state and sweep skip** | press Stop tracking, then stand in view of the parked camera for 5 s; check the app's status ring label; press Track & record | label "Awake — person in frame" (and "Awake — no one in frame" a few seconds after you leave). Track & record turns straight to you and locks within ≈ 2 s, with no sweep. Not detected while awake: same fixes as check 3, in reverse (`DETECT_HIT_THRESHOLD` lower) |
| 2b | **Sleep, then Record with you in front** | with the app open on the live view, leave the camera awake for a minute; then close the app for 30 s (≈ 1½ min if the app reaches it through Firebase), reopen it, stand in view and press **Record** | it stays awake while you watch; after you close the app the ring drops to one dim blue pixel and the app says the camera is asleep (no live view), with **Wake up** · **Record**. Record: the camera holds still for about a second, then locks on you with no sweep. Sweeps away from you: its first look missed you — raise `CAMERA_WARMUP_S` (dark room) or lower `DETECT_HIT_THRESHOLD` |
| 3 | **False-positive rate in your room** | leave the sweep running past a coat stand, hanging coats, a chair with clothes on it, a poster of a person | it should not record them. If it does, raise `DETECT_HIT_THRESHOLD` (0.3 → 0.4) or `FOUND_CONFIRM_S` (3 → 4), then repeat the sweep |
| 4 | **Lock-and-follow a walking person** | walk across the room, turn and come back | the person stays inside the frame by vision alone; tilt follows as well as pan. Overshoot or oscillation means `TRACK_PAN_GAIN` / `TRACK_TILT_GAIN` are too high ([05 — Tuning](../design/05-tracking-system.md#tuning)) |
| 5 | **Found, then record** | watch the ring and the app when it first finds you | the ring fills green over 3 s, then turns solid red, and the app shows recording with no extra tap. **Stop recording** saves the clip and the ring goes back to blue (awake) |
| 6 | **Re-search after loss** | leave the frame, then stay out of view for more than `RESEARCH_AFTER_S` (6 s) | the camera holds still and flashes the ring for `LOST_HOLD_S`, then sweeps again; re-enter the view and it locks again |
| 7 | **Zoom and focus estimate sanity** | walk from 2 m to 8 m and back, and check the focus is sharp at each distance | zoom keeps you at about two-thirds of the frame height (`ZOOM_FILL_TARGET`) across that range, without hunting. Until the focus grid has been run, focus follows the height-based distance estimate and may be soft at the tele end |
| 8 | **Give-up to awake** | press Track & record with nobody in the room and do not record | after `SEARCH_GIVE_UP_S` (180 s) the camera stops sweeping and returns to awake (ring blue). If a recording is running it must **not** give up |
| 9 | **Framing** | once recording, you fill roughly two-thirds of the frame height, with space all round | too loose or tight: `ZOOM_FILL_TARGET` |
| 10 | **Pings, beeps and chimes** | the phone app pings every 3 s while the camera searches, beeps 3, 2, 1 while found, then chimes on record start, and chimes on stop — test once with the app in the background and the screen off | no chime in the background: the platform setup in `src/app_flutter/README.md` (notification permission on Android, `UIBackgroundModes` on iOS) |
| 11 | **Battery estimate is honest** | compare minutes-left against a stopwatch over the first half hour | badly off usually means `BATTERY_WH` is still set to the bank's nameplate instead of the ~91 % that reaches the 12 V rail |
| 12 | **Card space reads as minutes** | the app shows free space as recording time | a 64 GB card reads roughly 10 h when empty |

## Mistakes this design has already made

Each of these really happened, and each is now caught by a check above or a
test:

- **The battery gauge was told the wrong capacity.** `BATTERY_WH` was set to
  the number on the bank, but the gauge sits downstream of the bank's own
  converter and only ever sees about 91 % of it. Every estimate ran 10 %
  optimistic.
- **The tilt loop integrated the same measurement repeatedly.** Vision runs at
  3 fps and the control loop at 20 Hz, so a cached detection was applied
  roughly seven times over. `src/without_uwb/device/tests/test_tracker.py` now guards it.
- **The vision-only tilt loop drove the wrong way.** It applied the PID
  output with an extra minus sign, so a subject low in the frame tilted the
  camera up. Found while reworking the tracking loops; the tracker tests
  now check both directions.
