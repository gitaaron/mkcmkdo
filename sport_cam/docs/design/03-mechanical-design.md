# 03 — Mechanical design

Both builds share the same head: tripod, battery tray, enclosure, lid, PTZ
base and camera. <!--with_uwb-->The UWB build adds two anchor arms, a mast and a wearable
pod — see [With UWB](#with-uwb).<!--/--><!--both--> <!--/--><!--without_uwb-->The camera-only build adds nothing — see
[Without UWB](#without-uwb).<!--/-->

SportCam is built around the **Arducam IMX477 PTZ camera with metal pan-tilt
base** (B0167B12). That one part supplies the camera, the motorized zoom lens,
and both motion axes, which is why there is no pan stage, no slip ring and no
tilt tower in this design. Everything printed is an enclosure or a bracket.

> **This is a deliberate trade.** A pan stage that turns all the way round
> needs a bearing, a slip ring, a stepper and its driver, and about a month to
> build. The PTZ base is a weekend, and it pans ±80° instead. See
> [ranges of motion](#ranges-of-motion) for what that costs, and
> [Appendix B](../appendix/appendix-b-open-source-parts.md#if-you-want-continuous-pan)
> if you want continuous pan anyway.

## Stack, bottom to top

1. **Any standard tripod** — the floor socket is a 3/8-16 insert with a
   removable 1/4-20 reducer bushing, so photo tripods (1/4-20) and video
   tripods (3/8-16) both screw straight on.
2. **Battery tray** — a printed saddle for the USB-C power bank, strapped to a
   tripod leg or the centre column as low as is convenient. Hanging the
   heaviest single item low is what keeps the thing from being tippy. Its
   cable runs up to a USB-C inlet low in the enclosure wall.
3. **Enclosure** (3D-printed; <!--with_uwb-->Ø 141 × 84 mm<!--/--><!--both--> with UWB, <!--/--><!--without_uwb-->Ø 135 × 73 mm<!--/--><!--both--> without<!--/-->,
   as solved for the assumed part sizes — see [Layout](#layout-inside-the-enclosure)).
   Inside, in three layers: the power boards on the floor; the WS2812B LED
   ring under a printed shelf, lighting a window all the way round so status is
   visible from any direction; the Raspberry Pi 4 on the shelf. Nothing in here
   moves. <!--both-->The wall differs by build: three bosses for arms and a mast, and a
   slot for the anchor cables, with UWB; plain all round without.<!--/--><!--with_uwb: The wall has three bosses for the arms and mast, and a slot for the anchor cables.--><!--without_uwb: The wall is plain all round.-->
4. **Lid** (3D-printed, 5 mm): structural. It carries the entire camera, so it
   is the one printed part worth extra walls. The Arducam base bolts to it
   through four radial slots; the camera ribbon and the servo lead drop through
   the central opening to the Pi below.
5. **Arducam metal pan-tilt base**: aluminium bracket, two digital servos, both
   axes 0–180°. It arrives assembled with the camera already in it.
6. **Camera and lens**: IMX477 12 MP sensor behind the motorized zoom lens.
   Zoom and focus are driven by the lens's own steppers, commanded over the
   same I2C bus as the two servos.

That is the whole <!--both-->camera-only <!--/-->head.<!--with_uwb--> The UWB build adds anchor arms and a mast
on top of this stack ([below](#with-uwb)).<!--/-->

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

**What the 160° pan costs you.** The camera can't follow a subject all the
way round, or take the short way past its back. A subject crossing a soft
limit is lost: the camera stops and holds — then<!--with_uwb-->, with UWB, falls back to idle after
5 s<!--/--><!--both-->; without UWB,<!--/--><!--without_uwb--> sweeps again after a few seconds (the search covers the
same ±80°, so it can never look behind itself)<!--/-->. Point the lens at the thing
you are filming — a wall, a pitch, a mat — and this never comes up. Expect to
care if people circulate around the tripod.

**Tilt is enough for climbing.** A 15 m top-out filmed from 7 m back is about
65° of elevation, comfortably inside +85°. At +85° and full wide zoom, the
top edge of the frame looks about 27° past vertical.<!--with_uwb--> (With UWB the A3 board
sits just outside that; see [below](#with-uwb).)<!--/-->

### How far the zoom reaches

The lens covers 96° to 33° horizontally, which on the IMX477's 16:9 frame is
a vertical field of 64° down to 18.9°. At full zoom the frame is 0.333 · d
tall at distance d, so a 1.8 m subject fills `5.4 / d` of its height:

| Distance | Subject height in frame, full zoom | Verdict |
| --- | --- | --- |
| 3 m | fills the frame — zoom out to fit | close-up work |
| 6 m | 90 % | tight |
| 8.3 m | 65 % (the framing target) | **last distance at target framing** |
| 10 m | 54 % | excellent |
| 13.5 m | 40 % | good |
| 20 m | 27 % | usable, visibly wider shot |
| 30 m | 18 % | small; the person detector needs about 15 % to see a body |

Past about 8 m framing degrades gracefully rather than failing: the lens is
at full zoom and the person simply fills less of the frame. At the wide end
a full body fits from about 1.5 m out, so close range is never the limit.
The figures come from the lens's published field of view (roughly 2.8–10.6 mm
on this sensor); the zoom calibration in 14 — Software setup confirms them for
your lens.

## Design rules that matter

- **The lid is the structure.** Print it at 5 walls, 40 % infill. Everything
  above it is cantilevered off those four slots.
- **Mass balance barely matters now** because the pan axis carries only the
  camera, but the *tripod* still cares: keep the battery tray low and spread
  the legs<!--with_uwb--> (and spread them wider once the UWB arms and mast are on)<!--/-->.
- **Cable service loop**: the camera ribbon and the servo lead cross the pan
  axis, so leave ~80 mm of slack coiled under the lid. Sweep both axes to their
  limits by hand before you tidy the loop, not after.

## Printed parts and CAD

Every build prints five parts: the enclosure, the Pi shelf, the LED diffuser
band, the lid and the battery tray.<!--with_uwb--> The UWB build adds two anchor arms,
the mast foot and cradle, and the wearable pod.<!--/--> Each prints in one piece on a
Bambu Lab A1 Mini (≤ 170 mm on each side), and `cad/fit.py` checks it.

- **What to print**, with previews and STL links: the bill of materials
  ([with UWB](../../with_uwb/docs/setup/10-bill-of-materials.md#printed-parts),
  [without UWB](../../without_uwb/docs/setup/10-bill-of-materials.md#printed-parts)).
- **How to print it** (settings, orientation, supports, times):
  [11 — 3D printing](../setup/11-3d-printing.md).
- **The OpenSCAD sources** in each build's `cad/`, and how `cad/fit.py` sizes
  them to the parts you bought:
  [Appendix A](../appendix/appendix-a-cad-parts.md).

## Assembly

Each build has an **interactive assembly guide** that walks the build in 3D —
[with UWB](../../with_uwb/docs/setup/assembly/index.html),
[without UWB](../../without_uwb/docs/setup/assembly/index.html) (open the file, or
use the docs viewer's sidebar): enclosure electronics, lid and camera,
battery, cabling and bring-up<!--with_uwb--> — plus, with UWB, the anchor arms and the A3
mast<!--/--> — with the part being fitted highlighted and animated into place.

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
  400 mm ([05](../../with_uwb/docs/design/05-tracking-system.md#geometry)). A3's
  height above them sets elevation resolution the same way. Keep both at
  least 250 mm, or the noise and the blind corner described in
  [05](../../with_uwb/docs/design/05-tracking-system.md#elevation-from-the-third-anchor)
  grow quickly. Widening them if you have room is in
  [Appendix A](../appendix/appendix-a-cad-parts.md#with-uwb).
- **Nothing metal near an antenna.** That is why the mast is wood. An
  aluminium tube under A3 detunes it and biases its range, and every
  centimetre of r₃ bias is over two degrees of elevation at 10 m.

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
