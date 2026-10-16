# SportCam — with UWB

The subject wears a matchbox-sized **UWB tag**; three static ULA1 anchors on
the head range it 20 times a second, through the body and clothing, and the
camera points where the ranges say. Vision only trims the angles, frames the
shot with the zoom, and confirms lock-on before recording. Switching the tag
on starts a session; switching it off ends it.

Pick this build if you film one person in a room with other people in it: the
tag is how the camera tells your subject from a bystander. The other build,
[without UWB](../without_uwb/README.md), needs nothing worn and nothing
mounted around the head, but follows whoever it finds first.

Everything common to both builds — the PTZ base, enclosure, power, Pi, server
and apps — is in the [top-level docs](../README.md#documentation). This
folder has only what is specific to the UWB build.

Run the server with `TRACKING_MODE=with_uwb` (the default): `npm run dev` or
`npm run dev:with_uwb` from the repo root.

## Docs

| Doc | Contents |
| --- | --- |
| [04 — Tracking system](docs/04-tracking-system.md) | UWB geometry with static anchors, elevation from the third, control loops, vision framing and focus, lock-on, what vision is for |
| [07 — Bill of materials](docs/07-bill-of-materials.md) | Every part, CAD price, Canadian sourcing, printed parts with STL links |
| [10 — Verification checklist](docs/10-verification.md) | What to measure before printing, check on arrival, and confirm on the bench |
| [**Setup — start here**](docs/setup/README.md) | The guides to follow, in order: |
| &nbsp;&nbsp;1. [**Assembly guide** (interactive, 3D)](docs/setup/assembly/index.html) | Step-by-step build with a live 3D rendering of every step |
| &nbsp;&nbsp;1a. [**Wiring guide**](docs/setup/wiring.md) | Every connection pin by pin, in order, with checks |
| &nbsp;&nbsp;2. [**Software setup**](docs/setup/software_setup.md) | Radios, Pi, calibration and services, in order, with every command |
| [Interactive wiring schematic](schematics/interactive/index.html) | Zoomable view of the whole system (best through `npm run docs`) |

The UWB-specific sections of the common docs:
[overview](../docs/01-system-overview.md#with-uwb) ·
[mechanical](../docs/02-hardware-mechanical.md#with-uwb) ·
[electronics](../docs/03-electronics.md#with-uwb) ·
[device software](../docs/05-device-software.md#with-uwb) ·
[3D printing](../docs/3d_printer/specifications.md#with-uwb) ·
[CAD](../docs/appendix-a-cad-parts.md#with-uwb).

## Files

```
docs/          tracking, BOM, verification, setup guides; images/ is rendered here
cad/           OpenSCAD sources + render_all.sh → cad/stl/ — includes anchor arms, A3 mast, wearable pod
schematics/    render_diagrams.py, render_schematics.py → docs/images/; interactive/ wiring viewer
device/        Raspberry Pi 4 camera service (Python): PTZ, UWB ranging (uwb.py, rangecal.py), tag sessions
firmware/      uwb_anchor/ — our own DS-TWR anchor sketch (the `dual-serial` protocol; ULA1s run the vendor firmware)
wearable/      tag_firmware/ — earlier ESP32-UWB tag sketch (pair / record button)
```

```bash
./with_uwb/cad/render_all.sh                    # STLs
python3 with_uwb/cad/render_previews.py         # part previews → docs/images/parts/
python3 with_uwb/schematics/render_diagrams.py  # diagrams → docs/images/
python3 with_uwb/docs/setup/assembly/build_models.py   # assembly guide meshes
```
