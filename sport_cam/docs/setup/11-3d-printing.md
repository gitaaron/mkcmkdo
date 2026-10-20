# 11 — 3D printing: requirements, materials and settings

Everything SportCam needs you to print, what the printer has to be able to do,
and what to buy. No exotic printer required: a stock Ender 3, Prusa Mini,
Bambu A1 or anything comparable will do all of it, for either build.

| Build | Parts | PETG | Machine time |
| --- | --- | --- | --- |
| [With UWB](#with-uwb) | 10 (5 common + 2 arms, mast foot, mast cradle, wearable pod) | ≈ 420 g | ≈ 40 h |
| [Without UWB](#without-uwb) | 5 (the common parts) | ≈ 280 g | ≈ 26 h |

Sizes below are for the part sizes assumed in
[`cad/ordered_parts.toml`](../../cad/ordered_parts.toml). `cad/fit.py`
re-sizes the enclosure, shelf, lid and diffuser to the parts you actually
buy, so [`cad/FIT_REPORT.md`](../../cad/FIT_REPORT.md) has the current
figures.

Sources are in <!--both-->each build's<!--/--><!--with_uwb: the build's--><!--without_uwb: the build's--> `cad/` ([with UWB](../../with_uwb/cad/),
[without UWB](../../without_uwb/cad/)); the workflow for regenerating STLs is
in [Appendix A](../appendix/appendix-a-cad-parts.md). The parts and their place in the
build are in [03 — Mechanical design](../design/03-mechanical-design.md).

The same printer is also meant for **Croc charms (Jibbitz)**, a separate
project with its own requirements — see [Croc charms](#croc-charms-jibbitz)
at the end, and [One printer for both](#one-printer-for-both) if you are
buying a printer.

## Printer requirements

| Requirement | Minimum | Why |
| --- | --- | --- |
| Technology | FDM / FFF | all parts are designed for it |
| Build volume | **160 × 155 × 90 mm** | the battery tray is 155 mm long; the with-UWB enclosure is 147 × 149 mm and 84 mm tall |
| Nozzle | 0.4 mm | every setting below assumes it. 0.6 works if you raise wall counts |
| Hotend temperature | **250 °C** | PETG |
| Heated bed | **80 °C** | PETG will not stay down without one |
| Part cooling fan | yes, controllable | PETG wants it at 30–50 %, not 100 % |
| Enclosure | not needed | PETG does not warp like ABS |
| Extruder | either | bowden is fine. Direct drive only matters for the optional TPU wearable pod (UWB build) |

### Design rule: every part prints on a Bambu Lab A1 Mini

The reference printer for this project is the **Bambu Lab A1 Mini**
(180 × 180 × 180 mm build volume). **Every printed part, in both builds, must
fit on it in one piece**, so any change to the CAD has to keep it that way:

- **No part may exceed 170 mm on any axis.** That is the 180 mm bed less
  5 mm a side for a brim or skirt. The bed is a cube, so a part that is
  under 170 mm on all three sides fits whichever way up it prints.
- **Don't split a part to get round the limit.** Change the design instead;
  a glued seam in the enclosure or the lid is a weak point under the camera.
- **It's checked automatically.** `python3 cad/fit.py` measures every STL in
  both builds, and fails if one is too big or comes out in more than one
  piece. It also never widens the enclosure past what fits — 162 mm across
  with UWB, where the arm bosses add 8 mm. It runs on every render, on every
  commit that touches the CAD, and in CI
  ([Appendix A](../appendix/appendix-a-cad-parts.md#fit-the-layout-to-your-parts)).

Sizes with the assumed parts (bounding box, mm):

| Part | Build | Size | Margin to 170 |
| --- | --- | --- | --- |
| Enclosure | with UWB | 147 × 149 × 84 | 21 |
| Enclosure | without UWB | 139 × 139 × 73 | 31 |
| Pi shelf | <!--both-->with UWB / without<!--/--><!--with_uwb: with UWB--><!--without_uwb: without UWB--> | <!--with_uwb-->132 × 117 × 3<!--/--><!--both--> / <!--/--><!--without_uwb-->128 × 87 × 3<!--/--> | 38+ |
| Lid | <!--both-->with UWB / without<!--/--><!--with_uwb: with UWB--><!--without_uwb: without UWB--> | <!--with_uwb-->141 × 141 × 11<!--/--><!--both--> / <!--/--><!--without_uwb-->135 × 135 × 11<!--/--> | 29+ |
| LED diffuser band | <!--both-->with UWB / without<!--/--><!--with_uwb: with UWB--><!--without_uwb: without UWB--> | <!--with_uwb-->Ø 145 × 16<!--/--><!--both--> / <!--/--><!--without_uwb-->Ø 139 × 16<!--/--> | 25+ |
| Battery tray | both | 155 × 77 × 12 | 15 |
| Wearable pod | with UWB | 142 × 74 × 31 | 28 |
| Anchor arm, mast foot, mast cradle | with UWB | ≤ 69 mm | 100+ |

For SportCam alone, **build volume is the only hard gate.** 160 × 155 mm clears every part
with the assumed sizes; the A1 Mini's 180 × 180 leaves room for bigger ones. Resin printers are the wrong
tool here — these are structural brackets, not miniatures.

## What to buy

| Material | Qty | Notes |
| --- | --- | --- |
| **PETG, 1 kg, any colour** | 1 spool | the structural parts: ≈ <!--with_uwb-->380 g<!--/--><!--both--> with UWB, ≈ <!--/--><!--without_uwb-->240 g<!--/--><!--both--> without<!--/-->. A 1 kg spool leaves plenty for reprints |
| **PETG, white or natural** | ≈ 40 g | the LED diffuser band, which has to pass light, and ideally the shelf, whose underside bounces the ring's light out. They can't be your main colour unless that colour is white or natural. A 250 g sample spool is the cheap way to get it |
| Glue stick (PVA) | 1 | see the warning below — this is a release agent, not an adhesive |
| TPU 95A *(optional, UWB build)* | ≈ 30 g | nicer wearable pod against the skin. Needs direct drive |

> **PETG sticks to smooth PEI too well.** On a bare smooth PEI sheet it can
> fuse and tear chunks out of the surface when you remove the part. Put down a
> thin layer of glue stick first. It is there to stop the part bonding, which
> is the opposite of what glue stick normally does. Textured PEI, garolite and
> glass with glue are all fine.

PLA will physically work and is easier to print, but it creeps under sustained
load and softens around 60 °C. The lid holds the entire camera cantilevered
off four bolts, and the whole thing lives on a tripod that may sit in a hot
car. Use PETG. ABS or ASA are also fine if you have an enclosure.

## The common parts

Every build prints these five; their sizes are in the
[table above](#design-rule-every-part-prints-on-a-bambu-lab-a1-mini).<!--both--> Links go to the UWB build's sources; the
camera-only build has the same files in `without_uwb/cad/`. Masses and times
are the with-UWB ones (camera-only in brackets where they differ).<!--/-->

| Part | Walls | Infill | Layer | Est. mass | Est. time |
| --- | --- | --- | --- | --- | --- |
| [Enclosure](../../with_uwb/cad/base_housing.scad) | 4 | 20 % | 0.2 | <!--with_uwb-->≈ 180 g<!--/--><!--both--> (<!--/--><!--without_uwb: ≈ --><!--without_uwb-->145 g<!--/--><!--both-->)<!--/--> | <!--with_uwb-->≈ 18 h<!--/--><!--both--> (<!--/--><!--without_uwb: ≈ --><!--without_uwb-->14 h<!--/--><!--both-->)<!--/--> |
| [Pi shelf](../../with_uwb/cad/shelf.scad) | 3 | 20 % | 0.2 | ≈ 32 g | ≈ 2.5 h |
| [Lid](../../with_uwb/cad/lid.scad) | **5** | **40 %** | 0.2 | <!--with_uwb-->≈ 65 g<!--/--><!--both--> (<!--/--><!--without_uwb: ≈ --><!--without_uwb-->60 g<!--/--><!--both-->)<!--/--> | ≈ 4 h |
| [LED diffuser band](../../with_uwb/cad/led_diffuser_ring.scad) | **2** | **0 %** | 0.2 | ≈ 6 g | ≈ 1.5 h |
| [Battery tray](../../with_uwb/cad/battery_tray.scad) | 3 | 20 % | 0.2 | ≈ 38 g | ≈ 3.5 h |

The enclosure differs between builds in size, because `fit.py` solves each
one, and in its wall. <!--with_uwb-->The UWB one has three bosses for the arms and mast, and
a slot for the anchor cables<!--/--><!--both-->; the camera-only one is plain all round<!--/--><!--without_uwb: The camera-only one is plain all round-->.

Masses are computed from the STL solid volume at PETG's 1.27 g/cm³ and scaled
for the walls and infill above. Times assume a 0.4 nozzle at 0.2 mm and
ordinary speeds. **Your slicer is the authority on both** — these are for
deciding how much filament to buy and which evening to start.

### Orientation and supports

Every part is modelled in its print orientation. Drop it on the bed as it
comes out of OpenSCAD and you need **no supports anywhere**<!--with_uwb--> — except under
the UWB enclosure's wall bosses ([below](#with-uwb))<!--/-->.

| Part | Orientation | Supports |
| --- | --- | --- |
| Enclosure | open end up, as modelled | <!--without_uwb-->none<!--/--><!--both--> without UWB<!--/--><!--with_uwb: see [below](#with-uwb) for the bosses; otherwise none-->. The LED window is cut in bays with a thin rib every 22 mm, so the wall above it bridges short spans; the ledge under the window has a 45° underside; the shelf posts grow straight up out of the wall<!--both-->. With UWB, see below<!--/--> |
| Pi shelf | flat, as modelled | none |
| Lid | **flip it: top face on the bed**, locating ring up | none |
| Diffuser band | standing, as modelled | none. **Brim recommended**: it is a tall thin ring with a small footprint |
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
| Open every M3 clearance hole | 3.2 mm drill bit, by hand | enclosure lid-screw holes, shelf, lid slots<!--with_uwb--> (and, with UWB, arms and mast foot)<!--/--> |
| Check the tripod bore fits your 3/8-16 insert | drill or step bit if it is larger than the bore | enclosure floor |
| Fit heat-set inserts | soldering iron, flat tip, ≈ 200 °C | M3: one in the top of each of the three shelf posts, and four pushed sideways into the lid's ring (7 total) |
| Dry-fit before wiring | — | lid ring in the enclosure mouth; shelf on its posts; diffuser band over the window onto its ledge; the bank in the tray |

The 3/8-16 brass tripod insert is epoxied.<!--with_uwb--> The UWB build adds more heat-set
inserts ([below](#with-uwb)).<!--/-->

## Measure before you print

Measure the parts you've bought, put the numbers in
[`cad/ordered_parts.toml`](../../cad/ordered_parts.toml) and run
`python3 cad/fit.py`, before you print a 4-hour lid or an 18-hour enclosure.
It re-solves the layout, re-renders every part and checks they fit. What to
measure, and what each one changes, is the first table of your build's
**15 — Verification checklist**
([with UWB](../../with_uwb/docs/setup/15-verification.md#before-you-print),
[without UWB](../../without_uwb/docs/setup/15-verification.md#before-you-print)).

## Print order

If you want to start building before everything is done:

1. **Enclosure** — longest print, and nothing else can be assembled without it.
2. **Shelf** — the LED ring and the Pi mount on it.
3. **Lid** — needed as soon as the Arducam base arrives.
4. **Diffuser band** — only needed once the LED ring is in.
5. **Battery tray** — last; measure your bank first.

<!--with_uwb-->

The UWB build slots its arms and pod in ([below](#print-order-with-uwb)).

<!--/-->

---

## With UWB

Four more parts on top of the common ones:

| Part | Walls | Infill | Layer | Est. mass | Est. time |
| --- | --- | --- | --- | --- | --- |
| [Anchor arm](../../with_uwb/cad/anchor_arm.scad) ×2 | 4 | 25 % | 0.2 | ≈ 16 g each | ≈ 1.7 h each |
| [Mast foot](../../with_uwb/cad/anchor_mast.scad) | 4 | 25 % | 0.2 | ≈ 11 g | ≈ 1.5 h |
| [Mast cradle](../../with_uwb/cad/anchor_mast.scad) | 4 | 25 % | 0.2 | ≈ 14 g | ≈ 1.5 h |
| [Wearable pod](../../with_uwb/cad/wearable_case.scad) | 2 | 20 % | 0.2 | ≈ 44 g | ≈ 4 h |

### Orientation and supports, with UWB

| Part | Orientation | Supports |
| --- | --- | --- |
| Enclosure | open end up, as modelled | **Yes, but only under the three wall bosses.** They are 6 mm ledges on the outside wall at ±Y and −X, starting 10 mm up. Paint-on or support-blocker supports just there, or accept a slightly droopy underside nobody sees |
| Anchor arm | flat, as modelled | none |
| Mast foot, mast cradle | socket opening up, as modelled | none |
| Wearable pod | body and lid side by side, as modelled | none |

### After printing, with UWB

| Step | Tool | Where |
| --- | --- | --- |
| Fit heat-set inserts | soldering iron, flat tip, ≈ 200 °C | 2 × M3 in each of the three wall bosses, 1 × M3 in each mast socket (8 more, 15 in all) |
| Dry-fit | — | an arm on each side boss; the foot on the back boss and the dowel in both sockets |

### Print order, with UWB

Print the **anchor arms** ×2 after the lid — they can print while you wire
the enclosure. The **wearable pod** is independent of everything else; print
it whenever.

---

## Without UWB

Just the five common parts — about 280 g of PETG and 26 hours. Nothing needs
supports. Sources: [`without_uwb/cad/`](../../without_uwb/cad/).

---

## Croc charms (Jibbitz)

Small, detailed charms that push into the holes of a Croc. They do **not**
need an expensive or high-end printer: a compact, modern desktop printer
handles them easily.

### Printer requirements for charms

| Feature / spec | Recommended minimum | Why it matters for charms |
| --- | --- | --- |
| Build volume | **150 × 150 × 150 mm** (or larger) | charms are small (~25–35 mm); a compact bed keeps the printer cheap and small |
| Nozzle | **0.4 mm** (standard) | works fine. Being able to swap to a **0.2 mm** nozzle is ideal for sharp micro-detail on small logos and faces |
| Extruder | **direct drive** | **crucial for TPU** (flexible filament). Bowden extruders struggle or jam pushing the rubber-like material that makes durable stems |
| Materials | **PLA, PETG, TPU** | PLA for quick detailed designs, PETG for impact and heat resistance, TPU for flexible charms or non-snap buttons |
| Bed levelling | **auto bed levelling (ABL)** | small prints depend on a perfect first layer; ABL saves fighting manual calibration |
| Bed surface | **textured PEI spring-steel sheet** | grips without tape or glue stick, and prints pop off when the sheet is flexed |

### FDM, not resin

Resin (SLA) printers give finer surface detail on tiny figurines, but resin
is brittle and usually snaps when pushed into the stiff rubber holes of a
Croc. **Use FDM (filament).** TPU or PETG charms survive daily wear.

### Which printer

Compact, modern direct-drive printers such as the **Bambu Lab A1 Mini** or
the **Creality Ender-3 V3 SE / KE** series meet every spec above out of the
box at an entry-level price.

---

## One printer for both

Buying one printer for SportCam and the charms means meeting the stricter of
each requirement:

| Spec | SportCam | Croc charms | Buy |
| --- | --- | --- | --- |
| Build volume | 160 × 155 × 90 mm | 150 × 150 × 150 mm | **≥ 160 × 155 × 150 mm** — a 150 × 150 bed is too small for the SportCam battery tray (155 mm long) |
| Nozzle | 0.4 mm | 0.4 mm, 0.2 mm swappable is ideal | 0.4 mm, with swappable nozzles |
| Extruder | either | direct drive | **direct drive** |
| Materials | PETG (TPU optional for the UWB wearable pod) | PLA, PETG, TPU | PLA, PETG, TPU — hotend to **250 °C** for PETG |
| Heated bed | 80 °C | — | 80 °C |
| Bed levelling | — | auto | **auto (ABL)** |
| Bed surface | textured PEI, garolite, or glass with glue (not bare smooth PEI) | textured PEI | **textured PEI** spring steel |
| Technology | FDM | FDM | FDM |

### Printers to buy

Every printer below meets the **Buy** column above. Specs are as listed by the
makers; prices move with sales, so check the live page before ordering.

| # | Printer | Build volume | Fits both? | Buy | Notes |
| --- | --- | --- | --- | --- | --- |
| 1 | **Bambu Lab A1 Mini** — *top choice* | 180 × 180 × 180 mm | yes | [Bambu Lab Canada](https://ca.store.bambulab.com/products/a1-mini) · [Amazon.ca](https://www.amazon.ca/s?k=bambu+lab+a1+mini) | direct drive, full auto calibration, textured PEI included, tool-free nozzle swap (0.2 mm sold separately). Smallest and quietest of the list, and clears the 155 mm battery tray. ≈ C$249 on sale, C$389 list |
| 2 | Bambu Lab A1 | 256 × 256 × 256 mm | yes | [Bambu Lab Canada](https://ca.store.bambulab.com/products/a1) · [Amazon.ca](https://www.amazon.ca/s?k=bambu+lab+a1+3d+printer) | the same machine with a bigger bed — pick it if you'll print anything larger than SportCam |
| 3 | Creality Ender-3 V3 SE | 220 × 220 × 250 mm | yes, add a textured PEI sheet | [Creality](https://www.creality.com/products/creality-ender-3-v3-se) · [Amazon.ca](https://www.amazon.ca/s?k=creality+ender-3+v3+se) | cheapest route; direct drive and auto levelling. Ships with a coated sheet rather than textured PEI, so budget ≈ C$25 for a 235 mm textured PEI sheet |
| 4 | Creality Ender-3 V3 KE | 220 × 220 × 240 mm | yes | [Creality](https://www.creality.com/products/creality-ender-3-v3-ke) · [Amazon.ca](https://www.amazon.ca/s?k=creality+ender-3+v3+ke) | faster, 300 °C hotend; check the listing for which bed sheet is included |

### Pros and cons

#### 1. Bambu Lab A1 Mini (top choice)

| Pros | Cons |
| --- | --- |
| Works out of the box: auto bed levelling, flow and vibration calibration, all automatic | 180 × 180 mm bed clears every SportCam part, but leaves little room to batch them |
| Textured PEI sheet included, so no extras to buy | Open frame, no enclosure or filter: keep it in a room with some fresh air, not a bedroom |
| Tool-free nozzle swap; 0.2 mm nozzle for fine charm detail is a click-in part | 80 °C bed max: fine for PLA, PETG and TPU, rules out ABS/ASA |
| Direct drive handles TPU | Bambu ecosystem: slicer, firmware and spare parts come from Bambu; cloud by default (LAN-only mode available) |
| Quiet, small footprint, built-in camera to watch long prints | Its cantilevered gantry is stiff for its size, but it is not a printer to grow into large parts |
| Optional AMS Lite for multi-colour charms | Cheapest at sale price; list price is noticeably higher |

#### 2. Bambu Lab A1

| Pros | Cons |
| --- | --- |
| Everything the A1 Mini has, on a 256 mm cube | Costs more than the Mini for no benefit on SportCam or charms |
| Room to print several SportCam parts, or a tray of charms, at once | Bed slinger: needs roughly twice its depth in clear desk space as the bed moves |
| 100 °C bed | Same Bambu-ecosystem and open-frame points as the Mini |
| Room for future projects bigger than 180 mm | Had a heated-bed cable recall in 2024; units sold now ship with the fixed cable, but check a second-hand one |

#### 3. Creality Ender-3 V3 SE

| Pros | Cons |
| --- | --- |
| Usually the cheapest printer on this list | Doesn't come with a textured PEI sheet, so add ≈ C$25 for one |
| Large 220 × 220 × 250 mm volume | Slower, and needs more hands-on tuning to print well than the Bambu printers |
| Direct drive extruder and auto levelling | No Wi-Fi or camera: prints go over USB stick or SD card |
| Open firmware, huge community, cheap generic spare parts | 260 °C hotend is enough for PETG, but has little margin |
| | Nozzle swaps take tools and a hot hotend; louder than the Bambu printers |

#### 4. Creality Ender-3 V3 KE

| Pros | Cons |
| --- | --- |
| Faster than the SE, with a 300 °C hotend | Costs more than the SE, and gets close to the A1 Mini, which needs less setup |
| Wi-Fi and Klipper-based firmware for remote control and tuning | Creality's firmware and app are less polished than Bambu's |
| Large 220 × 220 × 240 mm volume | Bed sheet type varies by listing: check that it includes textured PEI |
| Direct drive and auto levelling | Camera costs extra; louder than the Bambu printers |

**Top choice: the Bambu Lab A1 Mini.** It meets every requirement in the
table out of the box, at the lowest price, with the least setup. Get the
A1 instead if you want room for bigger prints.
