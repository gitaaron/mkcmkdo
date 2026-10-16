# SportCam — without UWB (camera-only)

**Nothing to wear and nothing mounted around the head.** Tap **Track &
record** in the app: the camera zooms wide and sweeps the room until its
person detector sees someone, turns to centre them, locks on and starts
recording. From then on it follows them by vision alone and frames them with
the zoom. Lose them for 6 s and it sweeps again.

Pick this build for simplicity, size and cost: about C$360 cheaper than the
UWB build, two hours more runtime, four printed parts, and a head with nothing
sticking out. The trade: vision cannot tell people apart, so in a busy room
the camera follows whoever it found first. If that matters, build
[with UWB](../with_uwb/README.md).

Everything common to both builds — the PTZ base, enclosure, power, Pi, server
and apps — is in the [top-level docs](../README.md#documentation). This
folder has only what is specific to the camera-only build.

Run the server with `TRACKING_MODE=without_uwb`: `npm run dev:without_uwb`
from the repo root.

## Docs

| Doc | Contents |
| --- | --- |
| [04 — Tracking system](docs/04-tracking-system.md) | Search sweep, lock-on, vision control loops, framing, limitations |
| [07 — Bill of materials](docs/07-bill-of-materials.md) | Every part, CAD price, Canadian sourcing, the four printed parts with STL links, savings vs the UWB build |
| [10 — Verification checklist](docs/10-verification.md) | What to measure before printing, check on arrival, and confirm on the bench |
| [**Setup — start here**](docs/setup/README.md) | The guides to follow, in order: |
| &nbsp;&nbsp;1. [**Assembly guide** (interactive, 3D)](docs/setup/assembly/index.html) | Step-by-step build with a live 3D rendering of every step |
| &nbsp;&nbsp;1a. [**Wiring guide**](docs/setup/wiring.md) | Every connection pin by pin, in order, with checks |
| &nbsp;&nbsp;2. [**Software setup**](docs/setup/software_setup.md) | Pi, calibration and services, in order, with every command |
| [Interactive wiring schematic](schematics/interactive/index.html) | Zoomable view of the whole system (best through `npm run docs`) |

The camera-only sections of the common docs:
[overview](../docs/01-system-overview.md#without-uwb) ·
[mechanical](../docs/02-hardware-mechanical.md#without-uwb) ·
[electronics](../docs/03-electronics.md#without-uwb) ·
[device software](../docs/05-device-software.md#without-uwb) ·
[3D printing](../docs/3d_printer/specifications.md#without-uwb) ·
[CAD](../docs/appendix-a-cad-parts.md#without-uwb).

## Files

```
docs/          tracking, BOM, verification, setup guides; images/ is rendered here
cad/           OpenSCAD sources + render_all.sh → cad/stl/ — enclosure, lid, diffuser, battery tray
schematics/    render_diagrams.py, render_schematics.py → docs/images/; interactive/ wiring viewer
device/        Raspberry Pi 4 camera service (Python): PTZ, vision search and tracking, auto-record sessions
```

```bash
./without_uwb/cad/render_all.sh                    # STLs
python3 without_uwb/cad/render_previews.py         # part previews → docs/images/parts/
python3 without_uwb/schematics/render_diagrams.py  # diagrams → docs/images/
python3 without_uwb/docs/setup/assembly/build_models.py   # assembly guide meshes
```
