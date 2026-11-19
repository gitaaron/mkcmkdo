# 12c — Preparing the PD trigger and the buck

The two power boards you buy, rather than build: the **PD trigger** (BOM 10), which
asks the bank for 12 V, and the **buck** (BOM 11), which turns that 12 V into the
camera's 5 V rail. Each needs setting up on the bench **before** it goes in. Both go
in the power drum under the enclosure: the trigger on standoffs screwed up through the
drum's floor, the buck standing on edge against a wall of the bank pocket, screwed
through it, like the power latch.

They're the same in both builds. This guide is steps 1 and 2 of the wiring guide
([with UWB](../with_uwb/setup/12-wiring.md#wiring-order-with-checks) ·
[without UWB](../without_uwb/setup/12-wiring.md#wiring-order-with-checks)) in full, and how
each board is mounted.

| | |
| --- | --- |
| Time | ≈ 30 min |
| Parts | BOM 10, 11 and 14 (the bank cable); the buck's own standoffs and Schottky diode; 2 × M3 standoffs for the trigger (item 21); M3 screws (item 22) |
| Tools | multimeter, small flat screwdriver for the buck's trimmer, soldering iron; the 4 A dummy load (BOM 14b); the power bank; a stubby Phillips screwdriver (≤ 70 mm long) |

## The PD trigger

### 1 · Check it has a socket

The bank's cable plugs into the trigger inside the drum, so the trigger needs a
USB-C **socket**: a slot the cable's plug goes into. Some trigger boards have a USB-C
**plug** sticking out of one end instead, made to plug straight into a charger. That
kind won't work here, short of a USB-C female-to-female adapter, which there is no
room for. Look at the end of the metal shell: a
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

It lies on the power drum's floor beside the bank's opening, on **two** M3 standoffs
through the two holes at its socket end. A small block printed into the floor holds up
the other end, under the screw terminal.

1. **Screw the two standoffs on from the top**, through the holes at the socket end,
   with M3 × 6 screws. If an M3 screw won't pass, use M2.5 and set `screw_d = 2.5`.
2. **Stand it in the drum** where the 3D model shows it, the terminal end on the
   printed rest.
3. **Screw it down from underneath** with two M3 countersunk screws up through the
   drum floor into the standoffs. The length is in `cad/FIT_REPORT.md`.
4. **Plug in the bank cable** (BOM 14, right-angle at one end): its straight end into
   the trigger, then lead it out through the nearer finger window beside the bank's
   opening. The right-angle end plugs into the bank's face.

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

It stays on the four brass standoffs it comes with, and stands **on its long edge**
against a wall of the bank pocket in the power drum, components facing out.

1. **Take the screws out of the standoffs' bottom ends.** Leave the top ones in.
2. **Hold it against the pocket wall** over its four countersunk holes, where the 3D
   model shows it. The bank plate must be out of the pocket.
3. **Drive four M3 countersunk screws through the wall from inside the pocket** into
   the standoffs; the length is in `cad/FIT_REPORT.md`. On a side wall, use a stubby
   screwdriver across the pocket; on the closed end, reach in through the open end.
   The heads sit flush, so the bank slides past them.

If the standoffs' ends have a threaded stud rather than a hole, use a nut on each from
inside the pocket instead, and file it flush if the bank catches on it.

## Measure them first

The drum's holes are cut from the sizes in
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
