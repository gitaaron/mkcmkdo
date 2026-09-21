# Appendix B — Open-source printed-part alternatives

If you'd rather remix proven community designs than print the parametric parts
in [`cad/`](../cad/) ([Appendix A](appendix-a-cad-parts.md)), this doc maps each SportCam printed part to open-source
models on Printables / MakerWorld / Thingiverse, and is honest about what each
substitution costs you.

## The big one: complete pan-tilt mechanisms

| Model | Why it's interesting | What you give up |
| --- | --- | --- |
| [Pan Tilt Mount (NEMA 17), talal_malik — Printables 1180365](https://www.printables.com/model/1180365-pan-tilt-mount-nema-17-stepper-motor) | Two NEMA17s + 3:1 GT2 pulleys, compact, well-documented. Replaces our pan stage **and** tilt tower/servo (drop the DS3225, add a second TMC2209) | No slip ring in the design → pan is wiring-limited to ~±180°, not continuous 360°. Tilt range as-designed is ~±90°, so the >180° vertical spec needs a remix of the tilt-side pulley limits |
| [NEMA 17 Pan Tilt (archived), link.state — Printables 511349](https://www.printables.com/model/511349-nema-17-pan-tilt-archived) | Built around a 4" lazy-susan bearing — structurally the closest thing to our pan stage; sturdy for heavier heads | Same ±180° wiring limit; archived project (no support); uses direct gear, slightly noisier than belt |
| [Pan & Tilt Stepper Gimbal, ChrisVaisnor — Printables 921719](https://www.printables.com/model/921719-pan-tilt-stepper-motor-gimbal) | Simple, quick print; good for a proof-of-concept before committing to the full build | Smaller motors/frames — marginal for the Pi-5-plus-zoom-lens head mass |

**Recommended remix path**: use talal_malik's or link.state's *pan base* largely
as-is, but keep three parts from `cad/`: the **ring pulley** (theirs don't
encircle a slip ring — this is what buys continuous 360°), the **anchor arms**,
and the **camera cradle**. That combination has no equivalent in the wild
because the UWB-anchor geometry is specific to this project.

## Pan/turntable stages only

- [Motorized Turntable, 3 versions — MakerWorld 1013366](https://makerworld.com/en/models/1013366-motorized-turntable-3-versions) — has a NEMA17 variant; a good base-housing donor.
- [Lazy Susan / Motorized Turntable Converter — MakerWorld 228118](https://makerworld.com/en/models/228118-experimental-lazy-susan-motorized-turntable-conver) — bolts a drive onto a stock lazy-susan bearing, same trick as our pan stage.
- [Motorized Lazy Susan Platform — Thingiverse 4593164](https://www.thingiverse.com/thing:4593164) — 6" lazy susan + GT2 belt; swap its 28BYJ-48 for the NEMA17 (the 28BYJ is far too weak for our head).
- [MGX3D heavy-duty scanning turntable — GitHub](https://github.com/MGX3D/Turntable) — overbuilt NEMA23 option if you want a very heavy head.

## Camera enclosures

- [Case for Arducam Camera Module — Printables 983982](https://www.printables.com/model/983982-case-for-arducam-camera-module-for-raspberry-pi) — snap-fit Arducam board case; remix the front plate for the zoom-lens barrel.
- [Raspberry Pi Camera Module 3 case — MakerWorld 530855](https://makerworld.com/en/models/530855-raspberry-pi-camera-case-for-cam-module-3) — for the budget (digital-zoom) build; tiny, prints in minutes.
- [Official 3D-printable HQ-camera cases — raspberrypi.com](https://www.raspberrypi.com/news/3d-printable-cases-for-the-raspberry-pi-high-quality-camera/) — if you ever move to the HQ camera + C-mount zoom lens.

## LED status ring

- [Clip-on WS2812 16-LED diffuser — Printables 628361](https://www.printables.com/model/628361-clip-on-ws2812-neopixel-16-led-diffuser) — direct replacement for our diffuser if you mount the ring flat on the base top instead of in the circumferential window.
- [16-LED ring diffuser — Thingiverse 1396974](https://www.thingiverse.com/thing:1396974) — same idea, older classic.
- [NeoPixel ring articulating mount — Printables 277167](https://www.printables.com/model/277167-neopixel-ring-articulating-mount) — handy during bench bring-up.

## Wearable pod

- [DIY smartwatch case for ESP32-C3 — MakerWorld 1749335](https://makerworld.com/en/models/1749335-diy-smartwatch-case-for-esp32-c3-0-96-oled) — comes with printed armband in three sizes; the best starting point for a wrist/arm-worn remix, but you must enlarge the cavity for the bigger ESP32-UWB board (55 × 30 mm vs the C3's footprint).
- Search [yeggi: "makerfabs esp32 dw1000 uwb"](https://www.yeggi.com/q/makerfabs+esp32+dw1000+uwb/) — community cases for the exact UWB board appear and disappear; check before designing.

## Generic bits worth grabbing instead of modeling

- [NEMA17 bracket — Printables 152887](https://www.printables.com/model/152887-nema-17-mounting-bracketholder)
- [Printables tag: nema17steppermotor](https://www.printables.com/tag/nema17steppermotor), [tag: lazysusan](https://www.printables.com/tag/lazysusan), [tag: neopixelring](https://www.printables.com/tag/neopixelring)
- Cross-site search: [yeggi "stepper motor pan tilt"](https://www.yeggi.com/q/stepper+motor+pan+tilt/)

## What has no community substitute

Print these from `cad/` regardless of which path you take: **ring pulley**
(slip-ring-encircling, ID 60 mm), **UWB anchor arms** (400 mm baseline
geometry), **rotating platform** (its hole pattern ties bearing + pulley + Pi
+ towers + arms together). Everything else can be remixed.
