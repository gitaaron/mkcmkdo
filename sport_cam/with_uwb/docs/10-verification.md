# 10 — Verification checklist

Everything in this build that depends on a part you bought rather than a
number we chose. It is ordered by **when you find out**, because the cost of
being wrong rises sharply down the page: a dimension caught before printing
costs nothing, the same dimension caught after costs a six-hour print.

Nothing here is optional reading. Three of the entries have already bitten
this design once.

## Before you print

These five change the CAD. Measure them with the parts in your hand, edit
[`cad/config.scad`](../cad/config.scad), then `./cad/render_all.sh`.

| # | Measure | Why it matters | If it is out of range |
| --- | --- | --- | --- |
| 1 | **Arducam base bolt spacing** → `ptz_bolt_min` / `ptz_bolt_max` | The lid carries the whole camera on four bolts. Arducam publishes no drawing and the footprint has changed between revisions, so the lid is cut with radial slots spanning 30–72 mm instead of fixed holes | Edit the two numbers and reprint the lid. This is the **six-hour** mistake — measure before the printer starts |
| 2 | **Camera power bank** → `bank_l` / `bank_w` / `bank_h` | The battery tray is a pocket sized to it. Banks of the same advertised capacity vary by 15 mm in every direction | Edit and reprint the tray (3.5 h) |
| 3 | **Wearable power bank** → `bank_tag_l/w/h` | Same, for the pod | Edit and reprint the pod (4.5 h) |
| 4 | **ULA1 mounting holes** → `uwb_hole_dx` / `uwb_hole_dy` | The arms and the mast cradle carry the anchors on M2.5 standoffs. The manual gives the 40 × 25 mm outline but not the hole pattern | Edit and reprint the arms (1.5 h each) and the cradle |
| 5 | **Dowel diameter** → `mast_d` | The A3 mast sockets are bored to it. "½-inch" dowels vary by a few tenths of a millimetre | Edit and reprint the foot and cradle (≈ 1.5 h each). Slightly loose is fine — the pinch screws take it up |

`tripod_hole_d` is 12.7 mm for a 3/8-16 brass insert. Check yours slips in
snugly and is no longer than the 8 mm boss; open the bore up with a drill
rather than reprinting if it is larger. Then check both threads: a 3/8-16
screw straight into the insert, and a 1/4-20 one with the reducer bushing in.

## On arrival, before you wire anything

| Check | How | If it fails |
| --- | --- | --- |
| **Lid spigot enters the enclosure mouth** | dry fit, no force | sand the spigot or raise `clr` and reprint the lid |
| **An arm sits flat on each wall boss** | dry fit both | check for elephant's foot on the boss; a few passes with a file |
| **The bank sits in the tray with the strap closed** | dry fit | back to item 2 above |
| **Micro-USB vs USB-A on the radios** | look at the board | the ULA1 has a USB-A plug; if yours does not, you have a different board and need different cables |
| **The LiPo, if you kept the old wearable** | read the four-digit code | 603048 fits, 503450 is 34 mm wide and does not |

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
| 7 | **Radios on the RTLS firmware** | watch the serial for `mc <mask> …` frames carrying **three** ranges, mask `07` | one range means you are on the `RangingAnchor`/`RangingTag` pair: reflash to `RTLS_Anchor`/`RTLS_Tag`, or set `UWB_PROTOCOL = "dual-serial"`. Two (mask `03`) means the tag is not configured for A3 |
| 8 | **Ranging rate, with all three anchors** | count frames per second | each anchor lengthens the cycle, so measure it with A3 in. 8–20 Hz is fine. Below that, lower `UWB_RATE_HZ` to match rather than letting the loop run on stale ranges |
| 9 | **Anchor order and sign** | walk to one side and watch the bearing | if the bearing moves opposite to you, flip `UWB_THETA_SIGN` |
| 10 | **Range bias, per anchor** | centre the pan axis, tape the tag **5.00 m** out on the boresight at A1/A2 board height, run `python -m sportcam.rangecal 5` and paste the `RANGE_BIAS_M` it prints | it also prints each anchor's noise. A bias over 30 cm is a setup error (distance, boresight, or anchor order), not a calibration. Noise well above 10 cm means metal or a body near an antenna. **Do not skip this with the 250 mm mast:** 5 cm of uncorrected A3 bias is about 12° of tilt |
| 11 | **A3 geometry and elevation** | tag 5 m out level with the anchors, then held 2 m higher; watch `tilt` in the app's telemetry | level should settle near −1° (the lens sits 10 cm above the anchors), and 2 m up near +21°. A constant offset after row 10 means `UWB_A3_UP_M` / `UWB_A3_BACK_M` do not match your mast (docs/04, calibration 3). Tilt going the wrong way means the board on the mast is not the one the tag reports as RANGE2: swap boards, or their anchor IDs |
| 12 | **Focus grid** | `python -m sportcam.focuscal` at 2, 5, 10 and 30 m | until you run it, focus is keyed on focal length alone, as before — soft at the tele end away from the distance it happened to be set for |

## First session

| Check | How | If it fails |
| --- | --- | --- |
| **Tag starts and ends a session** | tag off 5 s, then on: ring chases green, then breathes red; tag off: blue again 5 s later, clip saved | nothing on tag-on: `AUTO_SESSION`, or the tag was not off for 5 s first. Chases but never records: it never sees you centred — check the bearing and elevation signs (rows 9 and 11), face the camera, check the light; or the aim keeps jumping more than `ACQUIRE_POINT_TOL_DEG` (noisy ranging: re-run `rangecal`); or the card is full. After 15 s the app says "Can't see you" |
| **Chimes** | the phone app chimes on record start and stop — test once with the app in the background and the screen off | no chime in the background: the platform setup in `app_flutter/README.md` (notification permission on Android, `UIBackgroundModes` on iOS) |
| **Framing** | once recording, you fill roughly two-thirds of the frame height, with space all round | too loose or tight: `ZOOM_FILL_TARGET` |
| **Tracking holds** | walk the arc with the tag | see the calibration section of [04](04-tracking-system.md) |
| **Battery estimate is honest** | compare minutes-left against a stopwatch over the first half hour | badly off usually means `INA226_SHUNT_OHMS` does not match your module's shunt, or `BATTERY_WH` is still set to the bank's nameplate instead of the ~91 % that reaches the 12 V rail |
| **Card space reads as minutes** | the app shows free space as recording time | a 64 GB card reads roughly 10 h when empty |

## The four that already caught us

Worth knowing these were real, not hypothetical:

- **The anchor arm floated 8 mm above the bed.** Caught while measuring print
  times for [the printing spec](../../docs/3d_printer/specifications.md); it would have
  needed support along its whole length.
- **The battery gauge was told the wrong capacity.** `BATTERY_WH` was set to
  the number on the bank, but the gauge sits downstream of the bank's own
  converter and only ever sees about 91 % of it. Every estimate ran 10 %
  optimistic.
- **The tilt loop integrated the same measurement repeatedly.** Vision runs at
  3 fps and the control loop at 20 Hz, so a cached detection was applied
  roughly seven times over. `device/tests/test_tracker.py` now guards it.
- **The vision-only tilt loop drove the wrong way.** It applied the PID
  output with an extra minus sign, so a subject low in the frame tilted the
  camera up. Found while adding the third anchor; the tracker tests now check
  both directions.
