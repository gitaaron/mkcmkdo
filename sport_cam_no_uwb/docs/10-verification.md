# 10 — Verification checklist

Everything in this build that depends on a part you bought rather than a
number we chose. It is ordered by **when you find out**, because the cost of
being wrong rises sharply down the page: a dimension caught before printing
costs nothing, the same dimension caught after costs a six-hour print.

Nothing here is optional reading. Several of the entries have already bitten
this design once.

## Before you print

These two change the CAD. Measure them with the parts in your hand, edit
[`cad/config.scad`](../cad/config.scad), then `./cad/render_all.sh`.

| # | Measure | Why it matters | If it is out of range |
| --- | --- | --- | --- |
| 1 | **Arducam base bolt spacing** → `ptz_bolt_min` / `ptz_bolt_max` | The lid carries the whole camera on four bolts. Arducam publishes no drawing and the footprint has changed between revisions, so the lid is cut with radial slots spanning 30–72 mm instead of fixed holes | Edit the two numbers and reprint the lid. This is the **six-hour** mistake — measure before the printer starts |
| 2 | **Camera power bank** → `bank_l` / `bank_w` / `bank_h` | The battery tray is a pocket sized to it. Banks of the same advertised capacity vary by 15 mm in every direction | Edit and reprint the tray (3.5 h) |

`tripod_hole_d` is 12.7 mm for a 3/8-16 brass insert. Check yours slips in
snugly and is no longer than the 8 mm boss; open the bore up with a drill
rather than reprinting if it is larger. Then check both threads: a 3/8-16
screw straight into the insert, and a 1/4-20 one with the reducer bushing in.

## On arrival, before you wire anything

| Check | How | If it fails |
| --- | --- | --- |
| **Lid spigot enters the enclosure mouth** | dry fit, no force | sand the spigot or raise `clr` and reprint the lid |
| **The bank sits in the tray with the strap closed** | dry fit | back to item 2 above |

## On the bench, before the first session

Do these in order. Each one assumes the one above passed.

| # | Check | How | If it fails |
| --- | --- | --- | --- |
| 1 | **Buck trimmed to 5.1 V under load** | 4 A dummy load on the output, meter at the Pi end | adjust the trimmer. Open-circuit voltage tells you nothing; a module reading 5.1 V unloaded can sag to 4.8 V and brown the Pi out. **Do this before the Pi is ever connected** |
| 2 | **PD trigger actually at 12 V** | meter on a real bank, with the item 14 cable | the trigger stays at 5 V if the cable is USB-A to C (no PD), or if the bank's PD output has no 12 V profile. Any C-to-C cable is fine |
| 3 | **I2C devices present** | `i2cdetect -y 1` shows `0c` and `40` | `0c` missing: PTZ controller unpowered or leads swapped. `40` missing: set `POWER_MONITOR = "none"` and carry on without a gauge |
| 4 | **Camera detected** | `rpicam-hello` | add `dtoverlay=imx477` to `/boot/firmware/config.txt` |
| 5 | **Ring lights evenly** | run the three state colours | move the ring up or down the window; it should sit 20–32 mm up |
| 6 | **Soft limits and servo direction** | `cd device && python -m sportcam.ptzcheck` | narrow the limits in `config.py` if anything binds. If a positive pan command swings the lens the wrong way, flip `PAN_SIGN`; if a positive tilt command does not tilt it **up**, flip `TILT_SIGN`. Get either backwards and the camera runs away from the subject, which looks like a tracking fault and is not one |
| 7 | **Focus grid** | `python -m sportcam.focuscal <metres>` with a target taped at 2, 5, 10 and 30 m | until you run it, focus is keyed on focal length alone, as before — soft at the tele end away from the distance it happened to be set for |

## Camera-only checks

Run these in a normal room with the camera on its tripod, after the bench
checks above pass. Press **Track & record** in the app to start each one.

| # | Check | How | If it fails |
| --- | --- | --- | --- |
| 1 | **Sweep covers the range and reverses at the limits** | stand out of view, press Track & record, watch the pan for one full pass | it should go from about −80° to +80° and back, on both tilt rows (`SEARCH_TILT_ROWS_DEG`), without the servo binding or buzzing at either end. Binding: narrow the limits in `config.py`; wrong direction: flip `PAN_SIGN` / `TILT_SIGN` |
| 2 | **First-person lock** | walk into view while it sweeps | the sweep stops and the camera centres on the first person the HOG detector sees, ignoring a second person who arrives later |
| 3 | **False-positive rate in your room** | leave the sweep running past a coat stand, hanging coats, a chair with clothes on it, a poster of a person | it should not lock onto them. If it does, raise the detector's confidence threshold or add a minimum-size check, then repeat the sweep |
| 4 | **Lock-and-follow a walking person** | walk across the room, turn and come back | the person stays inside the frame by vision alone; tilt follows as well as pan. Overshoot or oscillation means the pan/tilt PID gains need tuning |
| 5 | **Auto-record on lock** | watch the ring and the app on the first lock | the ring goes from blue to breathing red and the app shows recording with no extra tap (`AUTO_RECORD_ON_LOCK`). The clip is saved when you stop |
| 6 | **Re-search after loss** | leave the frame, then stay out of view for more than `RESEARCH_AFTER_S` (6 s) | the camera holds still and flashes the ring for `LOST_HOLD_S`, then sweeps again; re-enter the view and it locks again |
| 7 | **Zoom and focus estimate sanity** | walk from 2 m to 8 m and back, and check the focus is sharp at each distance | zoom keeps you at about two-thirds of the frame height (`ZOOM_FILL_TARGET`) across that range, without hunting. Until the focus grid has been run, focus follows the height-based distance estimate and may be soft at the tele end |
| 8 | **Give-up to idle** | press Track & record with nobody in the room and do not record | after `SEARCH_GIVE_UP_S` (180 s) the camera stops sweeping and returns to idle (ring blue). If a recording is running it must **not** give up |
| 9 | **Framing** | once recording, you fill roughly two-thirds of the frame height, with space all round | too loose or tight: `ZOOM_FILL_TARGET` |
| 10 | **Chimes** | the phone app chimes on record start and stop — test once with the app in the background and the screen off | no chime in the background: the platform setup in `app_flutter/README.md` (notification permission on Android, `UIBackgroundModes` on iOS) |
| 11 | **Battery estimate is honest** | compare minutes-left against a stopwatch over the first half hour | badly off usually means `BATTERY_WH` is still set to the bank's nameplate instead of the ~91 % that reaches the 12 V rail |
| 12 | **Card space reads as minutes** | the app shows free space as recording time | a 64 GB card reads roughly 10 h when empty |

### Software checks

These need no hardware and should pass before any of the above:

```bash
python3 device/tests/test_tracker.py
python3 device/tests/test_session.py
```

`test_tracker.py` covers the search sweep, lock-on, re-search and the control
loops, and guards both of the tilt bugs below. `test_session.py` covers the
Track & record session: auto-record on lock and the give-up timeout.

## The ones that already caught us

Worth knowing these were real, not hypothetical:

- **The battery gauge was told the wrong capacity.** `BATTERY_WH` was set to
  the number on the bank, but the gauge sits downstream of the bank's own
  converter and only ever sees about 91 % of it. Every estimate ran 10 %
  optimistic.
- **The tilt loop integrated the same measurement repeatedly.** Vision runs at
  3 fps and the control loop at 20 Hz, so a cached detection was applied
  roughly seven times over. `device/tests/test_tracker.py` now guards it.
- **The vision-only tilt loop drove the wrong way.** It applied the PID
  output with an extra minus sign, so a subject low in the frame tilted the
  camera up. Found while reworking the tracking loops; the tracker tests
  now check both directions.
