# 12 — Wiring guide (bench test, without UWB)

The bench rig: mains supply → fuse → buck → the Pi and the PTZ controller,
and the controller's I2C on the Pi's header. No soldering.
Parts are the [bench bill of materials](10-bill-of-materials.md)'s; the
full build's wiring, with the battery, latch, gauge and ring, is the
[camera-only wiring guide](../setup/12-wiring.md).

```
 wall ── B2 cord ──► L N ⏚   BOSYTRO 12 V supply
                            +V ── B3 fuse 5 A ──► buck IN+        buck OUT+ ──► lever nut "+5 V" ──┬─► pigtail (B5) ──► Pi USB-C
                            −V ─────────────────► buck IN−        buck OUT− ──► lever nut "GND"  ──┴─► PTZ controller 5V / GND
                                                  (470 µF across OUT+/OUT−)
                                              Pi pin 3 SDA ─┬─ breadboard ─┬─ PTZ controller SDA
                                              Pi pin 5 SCL ─┘              └─ PTZ controller SCL
                                              camera ribbon ──► Pi CSI
```

**Rules**, the same as the full build's:

- **One ground.** Everything's ground meets at the buck's OUT− (the GND
  lever nut). The pigtail carries it into the Pi, so the Pi and the
  controller share it without a ground jumper.
- **Nothing is powered from the Pi's header.** The controller takes its 5 V
  from the lever nut, not pin 2 or 4.
- **Set the buck before anything is connected to it** (step 2).
- **Power on the lever nuts, signals on the breadboard.** Breadboard rails
  are rated about 1 A.

## Mains

The supply's AC terminals are live whenever the cord is plugged in. **Unplug
it before touching any terminal**, and close the supply's terminal cover
before plugging in.

| # | From | To | Notes |
| --- | --- | --- | --- |
| A1 | cord **live** (black, or brown) | supply **L** | |
| A2 | cord **neutral** (white, or blue) | supply **N** | |
| A3 | cord **ground** (green, or green-yellow) | supply **⏚** (earth) | never left off: it earths the supply's metal case |

If the supply has a **115 / 230 V selector** on its side, check it reads
**115** before the first plug-in (230 on a 115 V outlet gives a low or no
output; 115 on 230 destroys the supply).

## Power — 12 V and 5 V

| # | From | To | Wire | Notes |
| --- | --- | --- | --- | --- |
| P1 | supply **+V** | fuse holder (B3) → buck **IN+** | 18 AWG red | the fuse right at the supply, so the whole run is protected |
| P2 | supply **−V** (COM) | buck **IN−** | 18 AWG black | |
| R1 | buck **OUT+ / OUT−** | 470 µF capacitor | — | **stripe (−) to OUT−**. Into the lever nuts with the wires (R2) if the buck's terminals won't take a third lead |
| R2 | buck **OUT+** / **OUT−** | lever nut **+5 V** / lever nut **GND** | 18 AWG, short | |
| R3 | lever nuts **+5 V / GND** | USB-C pigtail **red / black** → Pi USB-C | the pigtail's own leads | the Pi's power. ≈ 1.2 A average, 2 A peaks. Red to +5 V (step 3) |
| R4 | lever nuts **+5 V / GND** | Arducam PTZ controller **5V / GND** | Dupont, or 22 AWG | the zoom and focus motors and both servos |

## Signals and camera

| # | From | To | Notes |
| --- | --- | --- | --- |
| I1 | Pi **pin 3** (GPIO2, SDA) | breadboard row → PTZ controller **SDA** | F-M jumper to the breadboard, M-F on to the controller. Or a single F-F jumper: the breadboard is only a tidy junction |
| I2 | Pi **pin 5** (GPIO3, SCL) | breadboard row → PTZ controller **SCL** | |
| C1 | camera ribbon (15-pin, from the kit) | Pi **CSI** connector | silver contacts **toward the HDMI ports**; lift the latch, insert fully, press it down |

The servo leads stay plugged into the PTZ controller, as the kit came
(`SERVO_DRIVER = "arducam"` in [14](14-software-setup.md)).

## Wiring order, with checks

1. **Supply, alone.** Mains (A1–A3), terminal cover closed, nothing on the
   output. Plug in. **Check:** **12.0 V** between +V and −V. Trim the
   supply's **V.ADJ** pot to 12.0 V if it's off. Unplug.
2. **Buck, alone.** P1, P2. Plug in, put the dummy load (B7) across the
   buck's output, and trim the buck to **5.1 V under the load**; take the
   load off within 30 s. Open-circuit voltage tells you nothing: a buck that
   reads 5.1 V unloaded can sag to 4.8 V and brown the Pi out. Unplug, add
   the capacitor (R1).
3. **5 V rail.** R2, R3 and R4, with the pigtail **not** in the Pi and the
   controller's 5V lead not on yet. Plug in. **Check:** **5.0–5.1 V** at
   the lever nuts, + in the +5 V nut. Make sure the pigtail's red lead is
   the one in the +5 V nut: a pigtail in backwards puts −5 V into the Pi.
   Unplug.
4. **Signals and camera.** I1, I2, C1, and the controller's 5V / GND (R4).
   Plug in with the pigtail in the Pi: it boots.
   **Check**, once you can SSH in ([14](14-software-setup.md)):
   `i2cdetect -y 1` shows **0c**, and `rpicam-hello -t 2000` shows a
   picture.

## If something is wrong

| Symptom | Likely | Fix |
| --- | --- | --- |
| No output from the supply | the mains wiring, or the 115/230 selector | unplug; recheck A1–A3 and the selector |
| Fuse blows at plug-in | a short on the 12 V side | P1/P2 swapped or touching at the buck |
| Pi reboots under load, or shows a lightning bolt | the buck's setting, or a thin pigtail | re-trim to 5.1 V **under load**; a pigtail with 20 AWG or heavier power leads |
| `0c` missing from `i2cdetect` | R4, I1 or I2 | controller unpowered, SDA and SCL swapped, or a loose jumper in the breadboard |
| No picture | C1 | ribbon backwards or not fully in; add `dtoverlay=imx477` ([14](14-software-setup.md)) |
| Pan moves in whole-degree ticks | — | expected on the bench: the servos run from the controller (`SERVO_DRIVER = "arducam"`) |
