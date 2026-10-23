# 15 — Verification checklist

Checks for everything that depends on a bought part rather than a design
value, ordered by **when the problem becomes detectable**. Cost of an error
rises down the page: a dimension caught before printing costs nothing; after
printing, up to an 18-hour reprint.

All sections are required. [Mistakes this design has already made](#mistakes-this-design-has-already-made)
lists four errors these checks catch.

## Before you print

Nine measurements that change the CAD. Procedure: measure the part, enter the
value in [`cad/ordered_parts.toml`](../../../cad/ordered_parts.toml) with
`measured = true`, run `python3 cad/fit.py` from `sport_cam/` (re-solves the
layout, re-renders, audits fit).
[`cad/FIT_REPORT.md`](../../../cad/FIT_REPORT.md) lists the checks and any sizes
still assumed.

| # | Measure | Why it matters | What fit.py does / what a mistake costs |
| --- | --- | --- | --- |
| 1 | **Arducam base bolt spacing** → `[ptz] bolt_spacing` | The lid carries the whole camera on four bolts. Arducam publishes no drawing and the footprint has changed between revisions, so the lid is cut with radial slots, 30–72 mm by default | `fit.py` stretches the slots to your spacing; set `bolt_l` to the screws you have and it relieves the lid under the slots if they're short. Reprinting the lid is the **four-hour** mistake — measure before the printer starts |
| 2 | **Buck converter, PD trigger, battery gauge** → `[buck]`, `[pd_trigger]`, `[gauge]` | They sit on the enclosure floor round the tripod boss and the shelf posts, under the LED window. Modules of the same rating vary a lot | `fit.py` rearranges them, lifts the boards onto risers over the boss, or makes the enclosure taller or wider. An **18-hour** reprint if you skip it |
| 3 | **Rocker switch and barrel jack** → `[switch]`, `[jack]` | Their cut-outs go in the wall, and the switch clips need a thin enough panel | `fit.py` sizes the cut-outs and thins the wall round the switch |
| 4 | **Pi heatsinks or fan case** → `[pi] heatsink_h` | The Pi sits on the shelf under the lid; a fan case is taller than stick-on heatsinks | `fit.py` makes the enclosure taller |
| 5 | **Camera power bank** → `[power_bank]` | The battery tray is a pocket sized to it. Banks of the same advertised capacity vary by 15 mm in every direction | Reprint the tray (3.5 h) |
| 6 | **Wearable power bank** → `[tag_bank]` | The pod is sized to it, with the ULA1 plugged into its end | Reprint the pod (4 h) |
| 7 | **ULA1 outline, holes and USB plug** → `[ula1]` | The arms and the mast cradle carry the anchors on M2.5 standoffs. The manual gives the 40 × 25 mm outline but not the hole pattern | Reprint the arms (1.7 h each) and the cradle |
| 8 | **USB extension ends** → `[usb_extension]` | The rigid socket end has to fit between each anchor's plug and the enclosure, or `fit.py` turns the boards across the arms; the plug end sets the size of the cable slot | Reprint the arms and cradle |
| 9 | **Dowel diameter** → `[dowel] d` | The A3 mast sockets are bored to it. "½-inch" dowels vary by a few tenths of a millimetre | Reprint the foot and cradle (≈ 1.5 h each). Slightly loose is fine — the pinch screws take it up |

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
| **An arm sits flat on each wall boss** | dry fit both | check for elephant's foot on the boss; a few passes with a file |
| **The bank sits in the tray with the strap closed** | dry fit | back to item 5 above |
| **Micro-USB vs USB-A on the radios** | look at the board | the ULA1 has a USB-A plug; if yours does not, you have a different board and need different cables |

## On the bench, before the first session

Do these in order. Each one assumes the one above passed.

| # | Check | How | If it fails |
| --- | --- | --- | --- |
| 1 | **Buck trimmed to 5.1 V under load** | 4 A dummy load on the output, meter at the Pi end | adjust the trimmer. Open-circuit voltage tells you nothing; a module reading 5.1 V unloaded can sag to 4.8 V and brown the Pi out. **Do this before the Pi is ever connected** |
| 2 | **PD trigger actually at 12 V** | meter on a real bank, with the item 14 cable | the trigger stays at 5 V if the cable is USB-A to C (no PD), or if the bank's PD output has no 12 V profile. Any C-to-C cable is fine |
| 3 | **I2C devices present** | `i2cdetect -y 1` shows `0c` and `40` | `0c` missing: PTZ controller unpowered or leads swapped. `40` missing: set `POWER_MONITOR = "none"` and carry on without a gauge |
| 4 | **Camera detected** | `rpicam-hello` | add `dtoverlay=imx477` to `/boot/firmware/config.txt` |
| 5 | **Ring lights evenly** | run the three state colours | move the ring up or down the window; it should sit 20–32 mm up |
| 6 | **Soft limits and servo direction** | from `~/sportcam/src/with_uwb/device`: `python3 -m sportcam.ptzcheck` | narrow the limits in `config.py` if anything binds. If a positive pan command swings the lens the wrong way, flip `PAN_SIGN`; if a positive tilt command does not tilt it **up**, flip `TILT_SIGN`. Get either backwards and the camera runs away from the subject, which looks like a tracking fault and is not one |
| 7 | **Radios on the RTLS firmware** | watch the serial for `mc <mask> …` frames carrying **three** ranges, mask `07` | one range means you are on the `RangingAnchor`/`RangingTag` pair: reflash to `RTLS_Anchor`/`RTLS_Tag`, or set `UWB_PROTOCOL = "dual-serial"`. Two (mask `03`) means the tag is not configured for A3 |
| 8 | **Ranging rate, with all three anchors** | count frames per second | each anchor lengthens the cycle, so measure it with A3 in. 8–20 Hz is fine. Below that, lower `UWB_RATE_HZ` to match rather than letting the loop run on stale ranges |
| 9 | **Anchor order and sign** | walk to one side and watch the bearing | if the bearing moves opposite to you, flip `UWB_THETA_SIGN` |
| 10 | **Range bias, per anchor** | centre the pan axis, tape the tag **5.00 m** out on the boresight at A1/A2 board height, run `python -m sportcam.rangecal 5` and paste the `RANGE_BIAS_M` it prints | it also prints each anchor's noise. A bias over 30 cm is a setup error (distance, boresight, or anchor order), not a calibration. Noise well above 10 cm means metal or a body near an antenna. **Do not skip this with the 250 mm mast:** 5 cm of uncorrected A3 bias is about 12° of tilt |
| 11 | **A3 geometry and elevation** | tag 5 m out level with the anchors, then held 2 m higher; watch `tilt` in the app's telemetry | level should settle near −1° (the lens sits 10 cm above the anchors), and 2 m up near +21°. A constant offset after row 10 means `UWB_A3_UP_M` / `UWB_A3_BACK_M` do not match your mast ([05 — Calibration](../design/05-tracking-system.md#calibration), step 3). Tilt going the wrong way means the board on the mast is not the one the tag reports as RANGE2: swap boards, or their anchor IDs |
| 12 | **Focus grid** | `python -m sportcam.focuscal` at 2, 5, 10 and 30 m | until you run it, focus is keyed on focal length alone — soft at the tele end away from the distance it happened to be set for |
| 13 | **Bearing noise** | after row 10, the wearer stands still on the boresight with the tag on as when climbing: `python -m sportcam.bearingcal 5`, then `10`. Paste the larger `TAG_BEARING_SIGMA_DEG` and the longer `TAG_BEARING_CORR_S` | σ above 10° or τ above 1 s: look for metal near an antenna, or a body between the tag and the anchors, and re-run row 10. A mean over 3° off straight ahead means the wearer is off the boresight or the range bias is stale. Values above the defaults make it wait longer beside a belayer; never paste in smaller ones than you measured |

## First session

| Check | How | If it fails |
| --- | --- | --- |
| **Tag starts and ends a session** | tag off 5 s, then on: ring chases green, fills green over 3 s, then turns solid red; tag off: blue again 5 s later, clip saved | nothing on tag-on: `AUTO_SESSION`, or the tag was not off for 5 s first. Chases but never records: it never sees you — check the bearing and elevation signs (rows 9 and 11), face the camera, check the light; or the aim keeps jumping more than `ACQUIRE_POINT_TOL_DEG` (noisy ranging: re-run `rangecal`); or the card is full; or someone is standing too close beside you to tell apart ([05](../design/05-tracking-system.md#telling-the-tag-wearer-from-everyone-else)): step away. After 15 s the app says "Can't pick you out" |
| **Pings, beeps and chimes** | the phone app pings every 3 s while the camera searches, beeps 3, 2, 1 while found, then chimes on record start, and chimes on stop — test once with the app in the background and the screen off | no chime in the background: the platform setup in `src/app_flutter/README.md` (notification permission on Android, `UIBackgroundModes` on iOS) |
| **Framing** | once recording, you fill roughly two-thirds of the frame height, with space all round | too loose or tight: `ZOOM_FILL_TARGET` |
| **Tracking holds** | walk the arc with the tag | see the calibration section of [05](../design/05-tracking-system.md) |
| **Battery estimate is honest** | compare minutes-left against a stopwatch over the first half hour | badly off usually means `INA226_SHUNT_OHMS` does not match your module's shunt, or `BATTERY_WH` is still set to the bank's nameplate instead of the ~91 % that reaches the 12 V rail |
| **Card space reads as minutes** | the app shows free space as recording time | a 64 GB card reads roughly 10 h when empty |

## Mistakes this design has already made

Each of these really happened, and each is now caught by a check above or a
test:

- **The anchor arm floated 8 mm above the bed.** Caught while measuring print
  times for [the printing spec](../../../docs/setup/11-3d-printing.md); it would have
  needed support along its whole length.
- **The battery gauge was told the wrong capacity.** `BATTERY_WH` was set to
  the number on the bank, but the gauge sits downstream of the bank's own
  converter and only ever sees about 91 % of it. Every estimate ran 10 %
  optimistic.
- **The tilt loop integrated the same measurement repeatedly.** Vision runs at
  3 fps and the control loop at 20 Hz, so a cached detection was applied
  roughly seven times over. `src/with_uwb/device/tests/test_tracker.py` now guards it.
- **The vision-only tilt loop drove the wrong way.** It applied the PID
  output with an extra minus sign, so a subject low in the frame tilted the
  camera up. Found while adding the third anchor; the tracker tests now check
  both directions.
