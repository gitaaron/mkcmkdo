# Appendix B — Open-source printed-part alternatives

If you'd rather remix proven community designs than print the parametric parts
in [`cad/`](../cad/) ([Appendix A](appendix-a-cad-parts.md)), this doc maps each
SportCam printed part to open-source models on Printables / MakerWorld /
Thingiverse, and is honest about what each substitution costs you.

This build buys its motion as one assembly (the Arducam PTZ camera and metal
pan-tilt base), so there is far less to substitute than there used to be. The
printed parts are an enclosure, a lid, two arms, a tray and a pod.

## Enclosure and lid

The lid is the one part not worth replacing: it is cut to carry the Arducam
base on slots and pass the ribbon through the middle, and nothing generic does
that. The enclosure, though, is just a round box with a light band.

- [Raspberry Pi 5 case, parametric — Printables 1036702](https://www.printables.com/model/1036702-raspberry-pi-5-case) — if you would rather bolt a stock Pi case inside a bigger shell than use our standoffs.
- [Motorized Turntable, 3 versions — MakerWorld 1013366](https://makerworld.com/en/models/1013366-motorized-turntable-3-versions) — its base shell is a good donor for a round enclosure with a deck, if you want something chunkier than ours.
- [Project box generator, parametric — Printables 149967](https://www.printables.com/model/149967-parametric-project-box) — square alternative; you lose the 360° light band, which is most of why ours is round.

## LED status ring

- [Clip-on WS2812 16-LED diffuser — Printables 628361](https://www.printables.com/model/628361-clip-on-ws2812-neopixel-16-led-diffuser) — direct replacement for our diffuser if you mount the ring flat on the lid instead of in the circumferential window.
- [16-LED ring diffuser — Thingiverse 1396974](https://www.thingiverse.com/thing:1396974) — same idea, older classic.
- [NeoPixel ring articulating mount — Printables 277167](https://www.printables.com/model/277167-neopixel-ring-articulating-mount) — handy during bench bring-up.

## Battery tray

- [Universal power bank holder — Printables 455094](https://www.printables.com/model/455094-power-bank-holder) — strap-mount tray; check it fits a 150 × 72 × 30 mm bank before printing.
- [Parametric battery holder — Printables 309048](https://www.printables.com/model/309048-parametric-battery-holder) — generate to your bank's exact size.
- [Tripod leg accessory clamp — Thingiverse 4536847](https://www.thingiverse.com/thing:4536847) — if you'd rather clamp to a leg than strap to the column.

## UWB anchor arms

No substitute exists. The arms set the 250 mm baseline that the bearing maths
in [04](04-tracking-system.md) depends on, and they carry a specific board at
a specific height. Print ours, or model your own to the same geometry — the
one number that matters is the distance between the two antennas.

## Wearable pod

- [DIY smartwatch case for ESP32-C3 — MakerWorld 1749335](https://makerworld.com/en/models/1749335-diy-smartwatch-case-for-esp32-c3-0-96-oled) — comes with a printed armband in three sizes; the best starting point for an arm-worn remix, but the pod now has to hold a ULA1 module (40 × 25 mm) beside a small USB power bank, so the cavity needs rethinking rather than enlarging.
- Search [yeggi: "makerfabs esp32 dw1000 uwb"](https://www.yeggi.com/q/makerfabs+esp32+dw1000+uwb/) — community cases for the exact UWB board appear and disappear; check before designing.

## If you want continuous pan back

The parts below rebuild the pan stage this design deleted. Going this way
means returning to a stepper, a driver, a slip ring and a second
microcontroller, and rewriting `ptz.py` and `tracker.py` to command pan
velocity rather than position — the geometry in
[04](04-tracking-system.md#static-anchors-change-the-loop) goes back to
anchors that rotate with the lens.

| Model | Why it's interesting | What you give up |
| --- | --- | --- |
| [Pan Tilt Mount (NEMA 17), talal_malik — Printables 1180365](https://www.printables.com/model/1180365-pan-tilt-mount-nema-17-stepper-motor) | Two NEMA17s + 3:1 GT2 pulleys, compact, well documented. Replaces both axes | No slip ring → pan is wiring-limited to ~±180°, not continuous |
| [NEMA 17 Pan Tilt (archived), link.state — Printables 511349](https://www.printables.com/model/511349-nema-17-pan-tilt-archived) | Built around a 4" lazy-susan bearing; sturdy for a heavy head | Same ±180° wiring limit; archived, no support |
| [Lazy Susan motorized turntable converter — MakerWorld 228118](https://makerworld.com/en/models/228118-experimental-lazy-susan-motorized-turntable-conver) | Bolts a drive onto a stock lazy-susan bearing | A turntable, not a camera mount — you design the rest |

For true continuous rotation you need a ring pulley whose bore clears a slip
ring, which is the one piece none of these have. The git history of this
repository has a parametric one (`cad/ring_pulley.scad`) if you want it back.
