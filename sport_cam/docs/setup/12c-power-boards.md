# 12c — Preparing the PD trigger and the buck

The two power boards you buy, rather than build: the **PD trigger** (BOM 10), which
asks the bank for 12 V, and the **buck** (BOM 11), which turns that 12 V into the
camera's 5 V rail. Each needs setting up on the bench **before** it goes in, and both
stand on standoffs screwed up through the enclosure floor, like the power latch.

They're the same in both builds. This guide is steps 1 and 2 of the wiring guide
([with UWB](../with_uwb/setup/12-wiring.md#wiring-order-with-checks) ·
[without UWB](../without_uwb/setup/12-wiring.md#wiring-order-with-checks)) in full, and how
each board is mounted.

| | |
| --- | --- |
| Time | ≈ 30 min |
| Parts | BOM 10, 11 and 14 (the bank cable); the buck's own standoffs and Schottky diode; 2 × M3 standoffs for the trigger (item 21); M3 screws (item 22) |
| Tools | multimeter, small flat screwdriver for the buck's trimmer, soldering iron; the 4 A dummy load (BOM 14b); the power bank |

## The PD trigger

### 1 · Check it has a socket

The bank's cable plugs into the trigger through the inlet in the enclosure wall, so
the trigger needs a USB-C **socket**: a slot the cable's plug goes into. Some
trigger boards have a USB-C **plug** sticking out of one end instead, made to plug
straight into a charger. That kind won't work here, short of a USB-C female-to-female
adapter, which the wall inlet isn't sized for. Look at the end of the metal shell: a
socket has an opening with a tongue inside it, a plug is closed at the tip.

### 2 · Set it to 12 V and lock it

On the common button type:

1. Plug it into the **real bank with the real cable** (BOM 14).
2. **Press the button until the 12 V LED lights.** It steps 5 → 9 → 12 → 15 → 20 V,
   one step per press, and saves the setting, so it comes back at 12 V after every
   power cycle and bank swap.
3. **Short its S1 key-lock pad** with a blob of solder, so a stray press can't take it
   to 15 or 20 V. To change it later, hold the button while plugging the bank in.
4. **Leave the F1/F2 test pads open.**

A jumper or resistor type is set per its silkscreen instead.

**Check:** 12 V at the screw terminal. Unplug the bank, plug it back in, and check it
still reads 12 V.

### 3 · Mount it

It stands on **two** M3 standoffs, through the two holes at its socket end. A small
block printed into the floor holds up the other end, under the screw terminal.

1. **Screw the two standoffs on from the top**, through the holes at the socket end,
   with M3 × 6 screws. If an M3 screw won't pass, use M2.5 and set `screw_d = 2.5`.
2. **Stand it in the enclosure** at the USB-C inlet, the socket hard against the inside
   of the opening, the terminal end on the printed rest.
3. **Screw it down from underneath** with two M3 countersunk screws up through the
   floor into the standoffs. The length is in `cad/FIT_REPORT.md`.
4. **Check the bank's cable plugs in from outside**, all the way, without pushing the
   board back.

## The buck

### 4 · Trim it to 5.1 V under load

Do this with nothing else connected to it, and long before the Pi is anywhere near.

1. Feed its input 12 V, from the trigger and the bank or a bench supply.
2. Put the **4 A dummy load** (BOM 14b) across its output. It gets hot: lay it on
   something metal and keep each go under 30 s.
3. Turn the voltage trimmer until the output reads **5.1 V with the load on**.

Open-circuit voltage tells you nothing: a buck that reads 5.1 V unloaded can sag to
4.8 V under load and brown the Pi out.

**If yours has an ON/OFF button** (the ZK-series boards with a display do), check that
its output comes up by itself when power is applied. Switch the 12 V off and on a few
times from cold: if the output stays off until you press the button, the rocker switch
won't start the camera. Most of these boards have a setting for the output's state at
power-up: see its manual.

### 5 · Fit the input diode

The Schottky diode that comes with the buck goes in series on its **12 V input**, band
(cathode) toward the buck's IN+. The wiring guide's input-diode section has why, the
rating to check, and how to fit it ([with UWB](../with_uwb/setup/12-wiring.md#input-diode) ·
[without UWB](../without_uwb/setup/12-wiring.md#input-diode)).

### 6 · Mount it

It stays on the four brass standoffs it comes with.

1. **Take the screws out of the standoffs' bottom ends.** Leave the top ones in.
2. **Stand it over its four countersunk holes in the floor** (on its four printed
   risers, if `fit.py` has raised it over the tripod boss), where the 3D model
   shows it.
3. **Drive four M3 countersunk screws up from underneath** into the standoffs; the
   length is in `cad/FIT_REPORT.md`. Do it before the other floor boards go in, while
   you can still get at the standoffs.

If the standoffs' bottom ends have a threaded stud rather than a hole, use a nut on
each from underneath instead.

## Measure them first

The floor's holes are cut from the sizes in
[`cad/ordered_parts.toml`](../../cad/ordered_parts.toml). Before you print, measure:

- **`[pd_trigger]`**: `hole_x` (from the socket end to the two holes' centres),
  `hole_dy` (the holes centre to centre), `screw_d`, `standoff_h`, `pcb_t`, and the
  rest of its entry;
- **`[buck]`**: `hole_dx` × `hole_dy` (its standoffs, centre to centre), `screw_d`,
  and `h` from the bottom of the standoffs.

The verification checklist's row 2 shows each one
([with UWB](../with_uwb/setup/15-verification.md#before-you-print) ·
[without UWB](../without_uwb/setup/15-verification.md#before-you-print)). Then run
`python3 cad/fit.py`.
