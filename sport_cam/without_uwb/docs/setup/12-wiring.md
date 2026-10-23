# 12 — Wiring guide

Every electrical connection in the camera, in the order you make
them. The [assembly guide](assembly/index.html) tells you *when* in the build
each one happens, and links back here.

**Schematics**, if you want the picture first:

| Diagram | Shows |
| --- | --- |
| [Interactive wiring schematic](../../schematics/interactive/index.html) | the whole system as one clickable graph. Open it in a browser or from `npm run docs` |
| [Head schematic](../images/schematic-head.png) | every signal into and out of the Pi |
| [Power tree](../images/power-tree.png) | the bank → 12 V → 5 V chain and what hangs off it |

The design reasons behind each connection are in
[04 — Electronics](../../../docs/design/04-electronics.md).

## Before you start

**Tools:** soldering iron, multimeter, heat-shrink, a **4 A dummy load** (a
power resistor or electronic load) for setting the buck, and a USB-C PD bank
for testing the trigger.

**Wire:** 18 AWG silicone for the 12 V and 5 V power runs (the 5 V rail
carries up to 4 A); 22 AWG or Dupont leads for signals (BOM item 18).

**Rules:**
- **One ground.** Every ground in the camera meets at the buck's output
  negative. A signal with no shared ground is not a signal.
- **The Pi's GPIO header powers nothing.** The PTZ controller, the ring and
  the level shifter all take 5 V from the buck. The header carries signals,
  plus 3.3 V for the gauge.
- **Set the buck before anything is connected to it** (step 1).

## Connection list

Pi pin numbers are physical header pins. Pin 1 is at the end of the header
away from the USB ports, and its pad is square.

### Power — 12 V side

| # | From | To | Wire | Notes |
| --- | --- | --- | --- | --- |
| P1 | Power bank USB-C | PD trigger USB-C | 30 cm C-to-C cable (BOM 14) | must be a full C-to-C cable; a charge-only or A-to-C cable leaves the trigger at 5 V |
| P2 | PD trigger **+12 V** | power latch **IN** | 18 AWG | the latch switches the positive line only. The rocker is wired to the latch, not in this line ([below](#power-latch)) |
| P3 | power latch **OUT** | gauge **VIN+** (INA260; **IN+** on an INA226) | 18 AWG | the gauge sits in series on the positive line, or it measures nothing |
| P4 | gauge **VIN−** (**IN−**) | buck **IN+** | 18 AWG | |
| P5 | PD trigger **GND** | buck **IN−** | 18 AWG | |
| P6 | power latch **GND** | buck **IN−** | 22 AWG | the latch draws ≈ 1 mA; GND only references its transistors |

### Power latch

The rocker doesn't switch the power itself. It tells a small latch board to,
so switching off is a clean shutdown and not a power cut: the Pi saves the
recording, parks the head and halts, and only then does the latch let go.
Design reasons: [04 — Electronics](../../../docs/design/04-electronics.md#power-switch).

Build it on a scrap of perfboard (BOM 13a), ≈ 30 × 24 mm, with the IRF4905
bent over flat so it stays below the LED window.

```
  IN (+12 V) ───────●────────── Q1 S ┐
                    │                ├ IRF4905   Q1 D ──── OUT (to the gauge)
                 R1 100k   ┌── Q1 G ┘
                    │      │
                    ●──────┘  gate
                    │
                 R2 10k
                    │
                    ● node C
           ┌────────┴────────┐
         Q3 C              Q2 C
  SW ─ R3 47k ─ Q3 B      Q2 B ─ R5 4.7k ─ HOLD   (S3 → Pi GPIO17)
         Q3 E → GND        Q2 E → GND
  (R4 100k, Q3 B → GND)   (R6 100k, Q2 B → GND)

  SW ─ R7 22k ─●─ SENSE   (S4 → Pi GPIO27)
               R8 6.8k → GND

  IN ── S1 ── rocker ── S2 ── SW
```

| Part | From | To | Why |
| --- | --- | --- | --- |
| Q1 IRF4905 (P-MOSFET) | **S** to IN | **D** to OUT | carries the camera's 12 V, ≈ 1.7 A; 0.02 Ω, so it stays cool without a heatsink |
| R1 100 kΩ | Q1 gate | Q1 source | holds Q1 off unless something pulls the gate down |
| R2 10 kΩ | Q1 gate | node C (both collectors) | pulls the gate to ≈ −11 V from the source when either transistor is on |
| Q3 2N3904 | C to node C | E to GND | on while the rocker is on |
| R3 47 kΩ, R4 100 kΩ | SW → Q3 base; base → GND | | base drive from the rocker's 12 V, and a pull-down |
| Q2 2N3904 | C to node C | E to GND | on while the Pi holds HOLD high: it carries the camera through the shutdown |
| R5 4.7 kΩ, R6 100 kΩ | HOLD → Q2 base; base → GND | | base drive from the Pi's 3.3 V. The pull-down keeps Q2 off while the Pi is off |
| R7 22 kΩ, R8 6.8 kΩ | SW → SENSE → GND | | 12 V → 2.8 V for the Pi (12.6 V at most → 2.97 V). Never 12 V straight to a GPIO |

| Rocker | Pi | Q1 | What happens |
| --- | --- | --- | --- |
| off | off | off | nothing draws from the bank |
| **on** | booting | on, through Q3 | the Pi boots and sets HOLD high within ≈ 1 s |
| **off** | running | on, through Q2 | SENSE falls, the Pi shuts down cleanly (≈ 10–15 s) |
| off | halted | off | the Pi's 3.3 V goes with the halt, HOLD drops, Q2 lets go |

If your rocker is lit (three terminals), its lamp terminal goes to GND, and it
lights only while it's on.

### Switch and Pi signals

| # | From | To | Wire | Notes |
| --- | --- | --- | --- | --- |
| S1 | latch **IN** (+12 V, always live) | rocker terminal 1 | 22 AWG | signal only: under 1 mA |
| S2 | rocker terminal 2 | latch **SW** | 22 AWG | |
| S3 | latch **HOLD** | Pi **pin 11** (GPIO17) | Dupont | the Pi's "keep the power on" line |
| S4 | latch **SENSE** | Pi **pin 13** (GPIO27) | Dupont | the switch's position, at 2.8 V. **Check it's under 3.3 V before plugging it in** |

The latch's GND is the camera's one ground (P6), so S3 and S4 need no ground
wire of their own.

### Power — 5 V rail

| # | From | To | Wire | Notes |
| --- | --- | --- | --- | --- |
| R1 | buck **OUT+ / OUT−** | 470 µF capacitor | — | across the output, **stripe (−) to OUT−** |
| R2 | buck OUT+ / OUT− | USB-C pigtail → Pi 4 USB-C | 18 AWG, short | the Pi's power input. ≈ 1.2 A average, 2 A peaks |
| R3 | buck OUT+ / OUT− | Arducam PTZ controller **5V / GND** | 18–22 AWG | not the Pi's 5 V pin: two stalled servos draw ≈ 0.7 A |
| R4 | buck OUT+ / OUT− | WS2812B ring **5V / GND** | 22 AWG | ≈ 1 A at full white; ≈ 0.45 A at the `LED_BRIGHTNESS = 0.45` the code uses |
| R5 | buck OUT+ / OUT− | 74AHCT125 **VCC (pin 14) / GND (pin 7)** | 22 AWG | |
| R6 | buck OUT+ / OUT− | panel barrel jack (in the wall, low) | 22 AWG | optional 5 V service tap, centre positive |

The pigtail (R2) carries ground into the Pi, so the Pi's GPIO ground and the
rail are already one net. No separate ground wire to the header is needed.

### I2C bus — Pi GPIO 2/3

Two devices share it: the PTZ controller at **0x0C** and the gauge at
**0x40**.

| # | From | To | Notes |
| --- | --- | --- | --- |
| I1 | Pi **pin 3** (GPIO2, SDA) | PTZ controller **SDA** and gauge **SDA** | |
| I2 | Pi **pin 5** (GPIO3, SCL) | PTZ controller **SCL** and gauge **SCL** | |
| I3 | Pi **pin 1** (3.3 V) | gauge **VCC** | 3.3 V, not 5 V: the breakout's pull-ups go to its VCC, and 5 V on SDA/SCL can damage the Pi |
| I4 | Pi **pin 9** (GND) | gauge **GND** | |

No gauge? Leave out I1–I4 at the gauge end, wire the 12 V straight through
(P3 to P4), and set `POWER_MONITOR = "none"`.

### LED ring — SPI through the level shifter

| # | From | To | Notes |
| --- | --- | --- | --- |
| L1 | Pi **pin 19** (GPIO10, SPI0 MOSI) | 74AHCT125 **1A (pin 2)** | 3.3 V data in |
| L2 | 74AHCT125 **1Y (pin 3)** | ring **DIN** | 5 V data out. Keep it short |
| L3 | 74AHCT125 **1OE (pin 1)** | GND | the enable is active-low: tied low, the gate is always on |
| L4 | 74AHCT125 **2A, 3A, 4A** (pins 5, 9, 12) and **2OE, 3OE, 4OE** (pins 4, 10, 13) | GND | unused gates; floating inputs oscillate |

Use the ring's **DIN** pad, not DOUT. The arrows printed on the ring point
away from DIN.

### Camera and PTZ — plug-in connections

| # | From | To | Notes |
| --- | --- | --- | --- |
| C1 | camera ribbon (15-pin, from the Arducam kit) | Pi **CSI** connector | silver contacts **toward the HDMI ports**; lift the latch, insert fully, press the latch down. Leave ≈ 80 mm of slack coiled under the lid |
| C2 | PTZ controller's servo and lens leads | as fitted in the Arducam kit | factory-wired; only R3, I1 and I2 are yours |

## Pi header, pins used

```
  I3 gauge VCC    3.3V  [ 1] [ 2]  5V     ← 5 V pins: not used, nothing is powered from the header
  I1 SDA         GPIO2  [ 3] [ 4]  5V
  I2 SCL         GPIO3  [ 5] [ 6]  GND
                        [ 7] [ 8]
  I4 gauge GND     GND  [ 9] [10]
  S3 latch HOLD GPIO17  [11] [12]
  S4 latch SENSE GPIO27 [13] [14]
                        ...
                        [17] [18]
  L1 ring data  GPIO10  [19] [20]  GND
```

## Wiring order, with checks

Each step points at the assembly-guide step it belongs to.

1. **Set the buck, alone** ([assembly: power](assembly/index.html#power)).
   Feed it 12 V from a bench supply or the trigger. Put the 4 A dummy load on
   the output and trim it to **5.1 V under load**. Open-circuit voltage tells
   you nothing: a unit that reads 5.1 V unloaded can sag to 4.8 V and brown
   the Pi out.
2. **Set the trigger to 12 V** (solder jumper or resistor, per its
   silkscreen). Check it with a meter on the real bank and the real cable
   (P1).
3. **Build the 12 V chain**: the [power latch](#power-latch) on its
   perfboard, then P2–P6, S1, S2, and the capacitor (R1). **Check:** rocker
   off, **0 V** at the buck input. Rocker on, **12 V** at the buck input and
   **5.1 V** at its output, with nothing else connected. Measure **2.7–3.0 V**
   on SENSE with the rocker on, and 0 V with it off. Rocker off again:
   the buck input drops to 0 V at once (HOLD isn't connected yet, so nothing
   holds the latch on).
4. **5 V rail out to the Pi** (R2) ([assembly: Pi](assembly/index.html#pi)).
   **Check:** before plugging in the Pi, measure **5.0–5.1 V** at the pigtail
   end, correct polarity. Then boot the Pi.
5. **Gauge on the bus** (I1–I4), **latch to the Pi** (S3, S4). **Check:**
   `i2cdetect -y 1` shows **40**. After the
   [Pi setup for the switch](14-software-setup.md#power-switch), switch off
   while the camera is running: it stays powered for ≈ 10–15 s while the Pi
   shuts down, then everything goes dark.
6. **LED ring** (R4, R5, L1–L4)
   ([assembly: LED](assembly/index.html#led)). **Check:** the ring cycles
   blue, green and red. A ring that stays dark usually has its data on DOUT
   or a floating 1OE.
7. **PTZ controller and camera** (R3, I1, I2, C1, C2) — when the lid goes on
   ([assembly: lid on](assembly/index.html#lid-on)). **Check:**
   `i2cdetect -y 1` shows **0c** and **40**; `rpicam-hello -t 2000` shows a
   picture.
8. **Dress the cables** ([assembly: cabling](assembly/index.html#cabling)).
   Sweep both axes by hand to their limits and watch the ribbon and leads.
   Nothing may hang where a tripod leg folds or reach the pan axis.

Then carry on with the [software setup](14-software-setup.md).

## If something is wrong

| Symptom | Likely wire | Fix |
| --- | --- | --- |
| Pi reboots under load, or shows a lightning bolt | R2, or the buck setting | re-trim to 5.1 V **under load**; shorten R2 and keep it 18 AWG |
| Trigger stays at 5 V | P1 | use a full USB-C to USB-C cable; check the bank has a 12 V PD profile |
| `0c` missing from `i2cdetect` | R3 or I1/I2 | PTZ controller unpowered, or SDA/SCL swapped |
| `40` missing | I1–I4 | gauge VCC or GND, or swapped SDA/SCL. Or run without it: `POWER_MONITOR = "none"` |
| Ring dark | L1–L4, R4, R5 | data on DOUT, 1OE not grounded, or the shifter unpowered |
| Ring flickers random colours | L2, L4 | long data lead, or unused shifter inputs left floating |
| Camera dies the instant you switch off | S3, or the Pi setup | HOLD isn't reaching Q2: check S3 is on pin 11, and that `gpio=17=op,dh` is in `config.txt` |
| Camera never turns off after switching off | S4, or the Pi setup | SENSE isn't reaching the Pi (pin 13, `gpio-shutdown` overlay), or `POWER_OFF_ON_HALT` isn't set, so the halted Pi keeps HOLD high |
| Switched back on during a shutdown and it stays dark | — | expected: the Pi has halted. Switch off, wait 5 s, switch on |
| Gauge reads 0 W while the camera runs | P3/P4 | the gauge is wired in parallel or on the ground line, not in series on 12 V+ |

The full bench checklist is in
[15 — Verification](15-verification.md#on-the-bench-before-the-first-session).
