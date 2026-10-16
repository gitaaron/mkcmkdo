# 3D printing — requirements, materials and settings

Everything SportCam needs you to print, what the printer has to be able to do,
and what to buy. Four parts, about **280 g of PETG**, roughly **25 hours** of
machine time. No exotic printer required: a stock Ender 3, Prusa Mini, Bambu
A1 or anything comparable will do all of it.

Sources are in [`cad/`](../../cad/); the workflow for regenerating STLs is in
[Appendix A](../appendix-a-cad-parts.md). The parts and their place in the
build are in [02 — Mechanical design](../02-hardware-mechanical.md).

## Printer requirements

| Requirement | Minimum | Why |
| --- | --- | --- |
| Technology | FDM / FFF | all parts are designed for it |
| Build volume | **170 × 150 × 80 mm** | the enclosure is the widest part at 139 × 143 mm and is 66 mm tall |
| Nozzle | 0.4 mm | every setting below assumes it. 0.6 works if you raise wall counts |
| Hotend temperature | **250 °C** | PETG |
| Heated bed | **80 °C** | PETG will not stay down without one |
| Part cooling fan | yes, controllable | PETG wants it at 30–50 %, not 100 % |
| Enclosure | not needed | PETG does not warp like ABS |
| Extruder | either | bowden is fine. bowden or direct drive both work |

**Build volume is the only hard gate.** 170 × 150 mm clears every part
with a little room; 180 × 180 is comfortable. Resin printers are the wrong
tool here — these are structural brackets, not miniatures.

## What to buy

| Material | Qty | Notes |
| --- | --- | --- |
| **PETG, 1 kg, any colour** | 1 spool | the three structural parts, ≈ 260 g. A 1 kg spool leaves plenty for reprints |
| **PETG, white or natural** | ≈ 50 g | the LED diffuser **only**. It has to pass light, so it cannot be your main colour unless that colour is white or natural. A 250 g sample spool is the cheap way to get it |
| Glue stick (PVA) | 1 | see the warning below — this is a release agent, not an adhesive |

> **PETG sticks to smooth PEI too well.** On a bare smooth PEI sheet it can
> fuse and tear chunks out of the surface when you remove the part. Put down a
> thin layer of glue stick first. It is there to stop the part bonding, which
> is the opposite of what glue stick normally does. Textured PEI, garolite and
> glass with glue are all fine.

PLA will physically work and is easier to print, but it creeps under sustained
load and softens around 60 °C. The lid holds the entire camera cantilevered
off four bolts, and the whole thing lives on a tripod that may sit in a hot
car. Use PETG. ABS or ASA are also fine if you have an enclosure.

## The parts

| Part | Size (mm) | Walls | Infill | Layer | Est. mass | Est. time |
| --- | --- | --- | --- | --- | --- | --- |
| [Enclosure](../../cad/base_housing.scad) | 139 × 143 × 66 | 4 | 20 % | 0.2 | ≈ 132 g | ≈ 13 h |
| [Lid](../../cad/lid.scad) | 135 × 135 × 9 | **5** | **40 %** | 0.2 | ≈ 92 g | ≈ 6 h |
| [LED diffuser ring](../../cad/led_diffuser_ring.scad) | Ø 137 × 16 | **2** | **0 %** | 0.2 | ≈ 14 g | ≈ 2.5 h |
| [Battery tray](../../cad/battery_tray.scad) | 155 × 77 × 12 | 3 | 20 % | 0.2 | ≈ 38 g | ≈ 3.5 h |

Masses are computed from the STL solid volume at PETG's 1.27 g/cm³ and scaled
for the walls and infill above. Times assume a 0.4 nozzle at 0.2 mm and
ordinary speeds. **Your slicer is the authority on both** — these are for
deciding how much filament to buy and which evening to start.

### Orientation and supports

Every part is modelled in its print orientation. Drop it on the bed as it
comes out of OpenSCAD and you need **no supports anywhere**.

| Part | Orientation | Supports |
| --- | --- | --- |
| Enclosure | open end up, as modelled | none — the wall is plain all round |
| Lid | as modelled, spigot on the bed | none — the 3 mm step bridges |
| Diffuser ring | standing, as modelled | none. **Brim recommended**: it is a tall thin ring with a small footprint |
| Battery tray | flat, as modelled | none |

### Why the lid is different

It is the only part with raised settings, and the only one worth not cutting
corners on. The Arducam base, the camera, the zoom lens and both servos all
hang off four M3 bolts through this plate. Five walls and 40 % infill is the
difference between a rigid mount and one that flexes every time the pan servo
accelerates, which shows up as wobble in the footage.

### Why the diffuser is different

The opposite problem: it has to be as hollow as possible. Two walls, zero
infill and **no top or bottom solid layers** is what turns 16 point sources
into an even glowing band. If your slicer insists on solid layers, set top and
bottom layers to 0 explicitly. Printed any denser, it reads as 16 bright dots.

## Settings that are not per-part

| Setting | Value | Note |
| --- | --- | --- |
| Nozzle | 235–245 °C | start at 240 and tune down until stringing stops |
| Bed | 80 °C | 70 also works on textured sheets |
| First layer | +0.02 to 0.05 mm higher than PLA | squashing PETG makes it stick too hard and look rough |
| Part cooling | 30–50 % | full cooling makes PETG brittle and weakens layer bonding |
| Retraction | 4–6 mm bowden / 1–2 mm direct | PETG strings; dry filament matters more than retraction tuning |
| Flow | ~95 % | PETG tends to over-extrude at default flow |

Dry your filament if it has been open more than a few weeks. Wet PETG is the
single most common cause of stringy, weak prints, and the diffuser shows it
worst because every string is visible once the LEDs are on.

## After printing

| Step | Tool | Where |
| --- | --- | --- |
| Remove brims, clean up strings | flush cutters, deburring tool | all parts |
| Open every M3 clearance hole | 3.2 mm drill bit, by hand | enclosure, lid |
| Check the tripod bore fits your 3/8-16 insert | drill or step bit if it is larger than the 12.7 mm bore | enclosure floor |
| Dry-fit before wiring | — | lid spigot in the enclosure mouth; the bank in the tray |

There is no insert work except the 3/8-16 brass tripod insert, which is
epoxied. Everything else is bolt-and-nut.

## Measure before you print

The full list, with what to do when a measurement is out of range, is in
**[10 — Verification checklist](../10-verification.md#before-you-print)**.
In short, two dimensions in [`cad/config.scad`](../../cad/config.scad) depend
on parts you bought, and getting them wrong means reprinting:

1. **`ptz_bolt_min` / `ptz_bolt_max` — the important one.** Arducam publishes
   no drawing for the metal pan-tilt base and the footprint has changed
   between revisions, so the lid is cut with radial slots spanning 30–72 mm
   instead of fixed holes. Measure your base's bolt spacing and check it falls
   inside that range before you print a 6-hour part.
2. **`bank_l` / `bank_w` / `bank_h`** — the camera's power bank. Banks of the
   same advertised capacity vary by 15 mm in every direction.

Change them, re-run `./cad/render_all.sh`, and every part stays consistent.

## Print order

If you want to start building before everything is done:

1. **Enclosure** — longest print, and nothing else can be assembled without it.
2. **Lid** — needed as soon as the Arducam base arrives.
3. **Diffuser ring** — only needed once the LED ring is in and aligned.
4. **Battery tray** — last; measure your bank first.
