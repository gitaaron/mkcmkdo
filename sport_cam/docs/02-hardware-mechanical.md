# 02 — Mechanical design

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
2. **Battery tray** — a printed saddle that sandwiches between the tripod plate
   and the enclosure, carrying the USB-C power bank under the whole assembly.
   Hanging the heaviest single item lowest is what keeps the thing from being
   tippy.
3. **Enclosure** (3D-printed, Ø 135 × 66 mm): the Raspberry Pi 4 flat on
   standoffs, the 5 V buck and PD trigger, the INA260 battery gauge, and the
   WS2812B LED ring in a diffused window around the circumference so status is
   visible from any direction. Nothing in here moves. The wall differs by
   build: three bosses for arms and a mast with UWB, plain all round without.
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
| Enclosure + LED diffuser ring | 1 | diffuser in white PETG, 2 walls, 0 % infill. Same outline in both builds; only the UWB one has wall bosses |
| Lid | 1 | 5 walls, 40 % — it carries the camera |
| Battery tray | 1 | sized in `<build>/cad/config.scad` to your power bank |

The UWB build adds arms, a mast and a wearable pod ([below](#printed-parts-with-uwb)).
Everything prints on any printer with a 170 × 150 × 80 mm build volume.
Settings, orientation and materials are in
[3D printing specifications](3d_printer/specifications.md).

Deleted with the pan stage: the rotating platform, the 120T ring pulley, both
tilt-tower uprights and the camera cradle.

## Assembly

Each build has an **interactive assembly guide** that walks the build in 3D —
[with UWB](../with_uwb/docs/setup/assembly/index.html),
[without UWB](../without_uwb/docs/setup/assembly/index.html) (open the file, or
use the docs viewer's sidebar): enclosure electronics, lid and camera,
battery, cabling and bring-up — plus, with UWB, the anchor arms and the A3
mast — with the part being fitted highlighted and animated into place.

## CAD sources

All printed parts have parametric OpenSCAD sources in each build's `cad/`
([with UWB](../with_uwb/cad/), [without UWB](../without_uwb/cad/)) —
see **[Appendix A — CAD: printed parts](appendix-a-cad-parts.md)** for the
render workflow, per-part print settings, and the measure-before-printing
checklist.

The one dimension worth measuring twice is the **Arducam base's bolt pattern**.
Arducam publishes no drawing and it has changed between revisions, so the lid
is cut with slots spanning 30–72 mm rather than fixed holes. Mark through the
slots and bolt it down.

---

## With UWB

![Mechanical layout, with UWB](../with_uwb/docs/images/mechanical-layout.png)

Two more items on top of the common stack:

7. **UWB anchor arms** — two printed arms bolted to the enclosure wall at ±Y,
   each carrying a ULA1 module on a USB extension.
   They are **static**: they do not rotate with the camera, which shapes the
   tracking maths (see [04](../with_uwb/docs/04-tracking-system.md)).
8. **A3 mast** — a ½-inch hardwood dowel, 246 mm, standing in a printed foot
   on a third wall boss at −X, directly behind the lens. A printed cradle on
   top carries the third ULA1 **250 mm above A1 and A2**, which is what gives
   the tracker elevation. Pan never points the lens backwards, and at this
   height the mast stays out of the shot even looking straight up.

The whole head is about **30 cm across the arms and 28 cm tall** to the top of
the mast — sized for a cramped room
(see [constraints](01-system-overview.md#constraints-with-uwb)).

**Tilt and the mast.** At +85° and full wide zoom the top edge of the frame
looks about 27° past vertical. The A3 board sits about 30° past vertical from
the tilt axis, so it stays just out of shot; a taller mast would not, and then
`TILT_MAX_DEG` wants lowering.

### Design rules, with UWB

- **UWB anchors** go at the ends of two printed arms, antennas level with
  *each other* and clear of the enclosure. The baseline sets bearing
  resolution: 250 mm is the compact choice, about 9° filtered against 7° at
  400 mm ([04](../with_uwb/docs/04-tracking-system.md#geometry)). If you have
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
| UWB anchor arms | 2 | ≈ 80 mm, bolt to the ±Y wall bosses; M3 inserts go in the bosses |
| A3 mast foot | 1 | bolts to the −X wall boss; M3 insert in the socket for a pinch screw |
| A3 mast cradle | 1 | caps the dowel, carries the third ULA1; M3 insert for a pinch screw |
| ½-inch hardwood dowel | 1 | bought, cut to 246 mm — the mast itself |
| Wearable case + strap loop | 1 | fits a ULA1 module beside a small USB power bank |

About 380 g of PETG and 35 hours of machine time in total.

---

## Without UWB

![Mechanical layout, without UWB](../without_uwb/docs/images/mechanical-layout.png)

The common stack is the whole head: the camera on top, a round enclosure
under it, a tray under that. The enclosure wall is plain all round — there
are no bosses for arms or masts. Nothing sticks out sideways, which suits a
cramped room (see [constraints](01-system-overview.md#constraints-without-uwb)).

**Tilt and the search.** The search only uses two shallow tilt rows (5° and
22°), so the rest of the tilt range is there for following the person once
found.

### Printed parts, without UWB

Just the common parts: enclosure, diffuser ring, lid and battery tray. About
280 g of PETG and 25 hours of machine time.
