# 03 — Mechanical design

Both builds share the same head: tripod, battery tray, enclosure, lid, PTZ
base and camera. The UWB build adds two anchor arms, a mast and a wearable
pod — see [With UWB](#with-uwb). The camera-only build adds nothing — see
[Without UWB](#without-uwb).

SportCam is built around the **Arducam IMX477 PTZ camera with metal pan-tilt
base** (B0167B12). That one part supplies the camera, the motorized zoom lens,
and both motion axes, which is why there is no pan stage, no slip ring and no
tilt tower in this design. Everything printed is an enclosure or a bracket.

> **This is a deliberate trade.** An earlier revision used a continuous-rotation
> pan stage: a lazy-susan bearing, a slip ring, a NEMA17 driving a printed 120T
> ring pulley, and a 270° tilt tower. It panned forever and tilted past vertical,
> and it took about a month to build. This one is a weekend, and it gives up
> continuous pan. See [ranges of motion](#ranges-of-motion) for exactly what
> that costs.

## Stack, bottom to top

1. **Any standard tripod** — the floor socket is a 3/8-16 insert with a
   removable 1/4-20 reducer bushing, so photo tripods (1/4-20) and video
   tripods (3/8-16) both screw straight on.
2. **Battery tray** — a printed saddle for the USB-C power bank, strapped to a
   tripod leg or the centre column as low as is convenient. Hanging the
   heaviest single item low is what keeps the thing from being tippy. Its
   cable runs up to a USB-C inlet low in the enclosure wall.
3. **Enclosure** (3D-printed; Ø 141 × 84 mm with UWB, Ø 135 × 73 mm without,
   as solved for the assumed part sizes — see [Layout](#layout-inside-the-enclosure)).
   Inside, in three layers: the power boards on the floor; the WS2812B LED
   ring under a printed shelf, lighting a window all the way round so status is
   visible from any direction; the Raspberry Pi 4 on the shelf. Nothing in here
   moves. The wall differs by build: three bosses for arms and a mast, and a
   slot for the anchor cables, with UWB; plain all round without.
4. **Lid** (3D-printed, 5 mm): structural. It carries the entire camera, so it
   is the one printed part worth extra walls. The Arducam base bolts to it
   through four radial slots; the camera ribbon and the servo lead drop through
   the central opening to the Pi below.
5. **Arducam metal pan-tilt base**: aluminium bracket, two digital servos, both
   axes 0–180°. It arrives assembled with the camera already in it.
6. **Camera and lens**: IMX477 12 MP sensor behind the motorized zoom lens.
   Zoom and focus are driven by the lens's own steppers, commanded over the
   same I2C bus as the two servos.

That is the whole camera-only head. The UWB build adds anchor arms and a mast
on top of this stack ([below](#with-uwb)).

## Layout inside the enclosure

Bottom to top:

| Layer | What | How it's held |
| --- | --- | --- |
| Floor | USB-C PD trigger (its socket at a USB-C inlet in the wall), rocker switch and 5 V jack in the wall, battery gauge, buck converter | foam tape; switch and jack panel-mount |
| LED window | WS2812B ring, LEDs down, lighting a 12 mm window all the way round; a translucent band covers the window outside | ring foam-taped under the shelf; band slid over the outside onto a ledge |
| Shelf | the Raspberry Pi 4 (and the level shifter beside it) | Pi on M2.5 nylon standoffs; shelf on three posts in the wall, M3 into inserts |
| Lid | the Arducam base | a ring under the lid drops into the mouth; four M3 through the wall into inserts in that ring |

Where each board sits, which way the Pi faces, where the wall openings go and
how big the enclosure is are **not drawn by hand**: `cad/fit.py` solves them
from the sizes of the parts you bought (`cad/ordered_parts.toml`) and the
design choices in `<build>/cad/config.scad`, then audits that everything fits
together and prints on a Bambu Lab A1 Mini. Change a part size and the layout
follows — see [Appendix A](../appendix/appendix-a-cad-parts.md#fit-the-layout-to-your-parts).
The last result is in [`cad/FIT_REPORT.md`](../../cad/FIT_REPORT.md).

## Ranges of motion

| Axis | Mechanism | Range | Notes |
| --- | --- | --- | --- |
| Pan | PTZ base servo, direct | **±80° soft (160° total)** | servo sweeps 180°; soft limits stop short of where the bracket fouls |
| Tilt | PTZ base servo, direct | **−45° … +85°** | same; verify yours with `python -m sportcam.ptzcheck` |
| Zoom | Arducam motorized lens | 96° → 33° horizontal (≈ 3.5× optical) | ≈ 2.8–10.6 mm EFL on this sensor |

**What the 160° pan costs you.** There are no end stops on a continuous axis,
so the old build could follow a subject through a full circle and always take
the shorter way round. This one cannot. A subject crossing a soft limit is
lost: the camera stops and holds — then, with UWB, falls back to idle after
5 s; without UWB, sweeps again after a few seconds (the search covers the
same ±80°, so it can never look behind itself). Point the lens at the thing
you are filming — a wall, a pitch, a mat — and this never comes up. Expect to
care if people circulate around the tripod.

**Tilt is enough for climbing.** A 15 m top-out filmed from 7 m back is about
65° of elevation, comfortably inside +85°. At +85° and full wide zoom, the
top edge of the frame looks about 27° past vertical. (With UWB the A3 board
sits just outside that; see [below](#with-uwb).)

## Design rules that matter

- **The lid is the structure.** Print it at 5 walls, 40 % infill. Everything
  above it is cantilevered off those four slots.
- **Mass balance barely matters now** because the pan axis carries only the
  camera, but the *tripod* still cares: keep the battery tray low and spread
  the legs (and spread them wider once the UWB arms and mast are on).
- **Cable service loop**: the camera ribbon and the servo lead cross the pan
  axis, so leave ~80 mm of slack coiled under the lid. Sweep both axes to their
  limits by hand before you tidy the loop, not after.
- Print structural parts in **PETG** (20 % infill, 4 walls); the lid heavier.

## Printed / fabricated parts list

Common to both builds:

| Part | Qty | Notes |
| --- | --- | --- |
| Enclosure | 1 | size solved by `cad/fit.py`; only the UWB one has wall bosses and a cable slot |
| Pi shelf | 1 | rests on three posts in the enclosure wall; white or natural helps the LED light |
| LED diffuser band | 1 | white PETG, 2 walls, 0 % infill; slides over the outside of the window |
| Lid | 1 | 5 walls, 40 % — it carries the camera |
| Battery tray | 1 | sized by `cad/fit.py` to the power bank in `cad/ordered_parts.toml` |

The UWB build adds arms, a mast and a wearable pod ([below](#printed-parts-with-uwb)).
Every part prints in one piece on a Bambu Lab A1 Mini (≤ 170 mm on each side);
`cad/fit.py` checks it.
Settings, orientation and materials are in
[3D printing specifications](../setup/11-3d-printing.md).

Deleted with the pan stage: the rotating platform, the 120T ring pulley, both
tilt-tower uprights and the camera cradle.

## Assembly

Each build has an **interactive assembly guide** that walks the build in 3D —
[with UWB](../../with_uwb/docs/setup/assembly/index.html),
[without UWB](../../without_uwb/docs/setup/assembly/index.html) (open the file, or
use the docs viewer's sidebar): enclosure electronics, lid and camera,
battery, cabling and bring-up — plus, with UWB, the anchor arms and the A3
mast — with the part being fitted highlighted and animated into place.

## CAD sources

All printed parts have parametric OpenSCAD sources in each build's `cad/`
([with UWB](../../with_uwb/cad/), [without UWB](../../without_uwb/cad/)) —
see **[Appendix A — CAD: printed parts](../appendix/appendix-a-cad-parts.md)** for the
fit-and-render workflow, per-part print settings, and the measure-before-printing
checklist.

The one dimension worth measuring twice is the **Arducam base's bolt pattern**.
Arducam publishes no drawing and it has changed between revisions, so the lid
is cut with slots spanning 30–72 mm rather than fixed holes. Mark through the
slots and bolt it down.

---

## With UWB

![Mechanical layout, with UWB](../../with_uwb/docs/images/mechanical-layout.png)

Two more items on top of the common stack:

7. **UWB anchor arms** — two printed arms bolted to the enclosure wall at ±Y,
   each carrying a ULA1 module on a USB extension. The three extensions come
   into the enclosure through a slot high in the wall, behind the Pi's USB
   ports.
   They are **static**: they do not rotate with the camera, which shapes the
   tracking maths (see [05](../../with_uwb/docs/design/05-tracking-system.md)).
8. **A3 mast** — a ½-inch hardwood dowel, 246 mm, standing in a printed foot
   on a third wall boss at −X, directly behind the lens. A printed cradle on
   top carries the third ULA1 **250 mm above A1 and A2**, which is what gives
   the tracker elevation. Pan never points the lens backwards, and at this
   height the mast stays out of the shot even looking straight up.

The whole head is about **30 cm across the arms and 28 cm tall** to the top of
the mast — sized for a cramped room
(see [constraints](../product/01-requirements.md#non-functional-requirements-with-uwb)).

**Tilt and the mast.** At +85° and full wide zoom the top edge of the frame
looks about 27° past vertical. The A3 board sits about 30° past vertical from
the tilt axis, so it stays just out of shot; a taller mast would not, and then
`TILT_MAX_DEG` wants lowering.

### Design rules, with UWB

- **UWB anchors** go at the ends of two printed arms, antennas level with
  *each other* and clear of the enclosure. The baseline sets bearing
  resolution: 250 mm is the compact choice, about 9° filtered against 7° at
  400 mm ([05](../../with_uwb/docs/design/05-tracking-system.md#geometry)). If you have
  room, raise `uwb_half_base` in `with_uwb/cad/config.scad` and
  `UWB_BASELINE_M` to match. A3's height above them, `uwb_v_base` /
  `UWB_A3_UP_M`, sets elevation resolution the same way; keep it at least
  250 mm or the blind corner described in 04 grows.
- **Nothing metal near an antenna.** That is why the mast is wood. An
  aluminium tube under A3 detunes it and biases its range, and every
  centimetre of r₃ bias is over two degrees of elevation at 10 m.

### Printed parts, with UWB

In addition to the common parts:

| Part | Qty | Notes |
| --- | --- | --- |
| UWB anchor arms | 2 | ≈ 70 mm, bolt to the ±Y wall bosses; M3 inserts go in the bosses. The ULA1 lies across the pad, plug to the back |
| A3 mast foot | 1 | bolts to the −X wall boss; M3 insert in the socket for a pinch screw |
| A3 mast cradle | 1 | caps the dowel, carries the third ULA1; M3 insert for a pinch screw |
| ½-inch hardwood dowel | 1 | bought, cut to 246 mm — the mast itself |
| Wearable case + strap loop | 1 | fits a ULA1 module plugged straight into the end of a small USB power bank |

About 420 g of PETG and 40 hours of machine time in total.

---

## Without UWB

![Mechanical layout, without UWB](../../without_uwb/docs/images/mechanical-layout.png)

The common stack is the whole head: the camera on top, a round enclosure
under it, a tray under that. The enclosure wall is plain all round — there
are no bosses for arms or masts. Nothing sticks out sideways, which suits a
cramped room (see [constraints](../product/01-requirements.md#non-functional-requirements-without-uwb)).

**Tilt and the search.** The search only uses two shallow tilt rows (5° and
22°), so the rest of the tilt range is there for following the person once
found.

### Printed parts, without UWB

Just the common parts: enclosure, diffuser ring, lid and battery tray. About
280 g of PETG and 25 hours of machine time.
