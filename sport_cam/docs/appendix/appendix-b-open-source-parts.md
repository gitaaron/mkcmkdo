# Appendix B — Open-source printed-part alternatives

Open-source alternatives (Printables, MakerWorld, Thingiverse) to the
parametric parts in `<build>/cad/` ([Appendix A](appendix-a-cad-parts.md)),
with the cost of each substitution.

Motion is a bought assembly (Arducam PTZ camera and pan-tilt base);
substitution candidates are the enclosure, LED diffuser and trays.
Both builds print an enclosure, a lid, a diffuser ring and a tray<!--with_uwb-->; the UWB
build adds two arms, a mast and a pod ([With UWB](#with-uwb))<!--/-->.

## Enclosure and lid

- **Lid:** no substitute. It carries the Arducam base on slots and passes
  the ribbon through its centre.
- **Enclosure:** a round box with a light band; candidates below.

- [Parametric Raspberry Pi 4B case — Printables 204101](https://www.printables.com/model/204101-parametric-raspberry-pi-4b-case-30mm-fan-with-vert) — if you would rather bolt a stock Pi case inside a bigger shell than use our standoffs. It has a 30 mm fan: set the Pi's height in `cad/ordered_parts.toml` to the case's and re-run `cad/fit.py`.
- [Motorized Turntable, 3 versions — MakerWorld 1013366](https://makerworld.com/en/models/1013366-motorized-turntable-3-versions) — its base shell is a good donor for a round enclosure with a deck, if you want something chunkier than ours.
- [Universal parametric project box — Printables 60749](https://www.printables.com/model/60749-universal-parametric-project-box) — square alternative; you lose the 360° light band, which is most of why ours is round.

## LED status ring

- [Clip-on WS2812 16-LED diffuser — Printables 628361](https://www.printables.com/model/628361-clip-on-ws2812-neopixel-16-led-diffuser) — direct replacement for our diffuser if you mount the ring flat on the lid instead of in the circumferential window.
- [16-LED ring diffuser — Thingiverse 1396974](https://www.thingiverse.com/thing:1396974) — same idea, older classic.
- [NeoPixel ring articulating mount — Printables 277167](https://www.printables.com/model/277167-neopixel-ring-articulating-mount) — handy during bench bring-up.

## Battery tray

- [Power bank holder with a universal tripod mount — Printables 1094558](https://www.printables.com/model/1094558-holder-for-a-power-bank-with-a-universal-mount-for) — mounts a bank on a photo tripod; check it fits a 150 × 72 × 30 mm bank before printing.
- [Parametric container generator, OpenSCAD — Printables 208305](https://www.printables.com/model/208305-parametric-battery-holder-9v-default-openscad-cust) — made for a 9 V battery, but its OpenSCAD parameters generate a holder to your bank's exact size.
- [Tripod leg accessory clamp — Thingiverse 4536847](https://www.thingiverse.com/thing:4536847) — if you'd rather clamp to a leg than strap to the column.

## If you want continuous pan

Starting points for a continuous-rotation pan stage. Required changes: add a
stepper, driver, slip ring and second microcontroller; rewrite `ptz.py` and
`tracker.py` for velocity rather than position control. <!--with_uwb-->With UWB, the geometry in
[05](../../with_uwb/docs/design/05-tracking-system.md#static-anchors-change-the-loop)
changes to anchors that rotate with the lens<!--/--><!--both-->; <!--/--><!--without_uwb: Without UWB,--><!--both-->without UWB,<!--/--><!--without_uwb--> the search sweep
in [05](../../without_uwb/docs/design/05-tracking-system.md) would no longer be limited
to ±80°, which is the point of doing it<!--/-->.

| Model | Why it's interesting | What you give up |
| --- | --- | --- |
| [Pan Tilt Mount (NEMA 17), talal_malik — Printables 1180365](https://www.printables.com/model/1180365-pan-tilt-mount-nema-17-stepper-motor) | Two NEMA17s + 3:1 GT2 pulleys, compact, well documented. Replaces both axes | No slip ring → pan is wiring-limited to ~±180°, not continuous |
| [Lazy Susan motorized turntable converter — MakerWorld 228118](https://makerworld.com/en/models/228118-experimental-lazy-susan-motorized-turntable-conver) | Bolts a drive onto a stock lazy-susan bearing | A turntable, not a camera mount — you design the rest |

Missing from all of these: a ring pulley whose bore clears a slip ring. A
parametric one (`cad/ring_pulley.scad`, from an earlier SportCam design) is in
the repository's git history.

---

## With UWB

### UWB anchor arms and mast

No substitute. The arms set the 400 mm baseline used by the bearing maths
([05](../../with_uwb/docs/design/05-tracking-system.md)) and carry a specific board
at a specific height. Custom designs must keep the antenna spacing (400 mm)
and the mast height (250 mm).

### Wearable pod

- [DIY smartwatch case for ESP32-C3 — MakerWorld 1749335](https://makerworld.com/en/models/1749335-diy-smartwatch-case-for-esp32-c3-0-96-oled) — comes with a printed armband in three sizes; the best starting point for an arm-worn remix. Our pod holds a ULA1 module (40 × 25 mm) plugged into the end of a small USB power bank, so the cavity needs rethinking rather than enlarging.
- Search [yeggi: "esp32 dw1000 uwb case"](https://www.yeggi.com/q/esp32+dw1000+uwb+case/) — community cases for DW1000 boards appear and disappear; check one fits the ULA1 before printing.

---

## Without UWB

No additional parts. The plain enclosure wall means any round box with a
light band can be used as a donor without adding bosses.
