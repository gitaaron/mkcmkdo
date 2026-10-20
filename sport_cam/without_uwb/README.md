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
and apps — is in the [shared docs](../README.md#documentation). This
folder has only what is specific to the camera-only build.

Run the server with `TRACKING_MODE=without_uwb`: `npm run dev:without_uwb`
from the repo root.

## Docs

The docs are numbered in reading order across three folders: product
requirements, design, and setup. Only the ones specific to this build live in
this folder; the rest are shared ([full table of contents](../README.md#documentation)).

| Folder | Doc | Contents |
| --- | --- | --- |
| Product | [01 — Product requirements](../docs/product/01-requirements.md#without-uwb) | this build's session, state machine and requirements (shared doc) |
| Design | [02 — System architecture](../docs/design/02-system-architecture.md#without-uwb) · [03 — Mechanical](../docs/design/03-mechanical-design.md#without-uwb) · [04 — Electronics](../docs/design/04-electronics.md#without-uwb) | this build's sections of the shared design docs |
| Design | [**05 — Tracking system**](docs/design/05-tracking-system.md) | Search sweep, lock-on, vision control loops, framing, limitations |
| Design | [06 — Device software](../docs/design/06-device-software.md#without-uwb) | this build's modules, vision and protocol (shared doc) |
| Setup | [**Setup — start here**](docs/setup/README.md) | the setup docs below, in order, with times |
| Setup | [**10 — Bill of materials**](docs/setup/10-bill-of-materials.md) | Every part, CAD price, Canadian sourcing, the four printed parts with STL links, savings vs the UWB build |
| Setup | [11 — 3D printing](../docs/setup/11-3d-printing.md#without-uwb) | printer, filament, settings; this build's parts (shared doc) |
| Setup | [**12 — Wiring guide**](docs/setup/12-wiring.md) | every connection pin by pin, in order, with checks |
| Setup | [**13 — Assembly guide** (interactive, 3D)](docs/setup/assembly/index.html) | step-by-step build with a live 3D rendering of every step |
| Setup | [**14 — Software setup**](docs/setup/14-software-setup.md) | Pi, calibration and services, in order, with every command |
| Setup | [**15 — Verification checklist**](docs/setup/15-verification.md) | what to measure before printing, check on arrival, and confirm on the bench |
| Setup | [Interactive wiring schematic](schematics/interactive/index.html) | zoomable view of the whole system (best through `npm run docs`) |
| Appendix | [A — CAD printed parts](../docs/appendix/appendix-a-cad-parts.md#without-uwb) · [B — Open-source alternatives](../docs/appendix/appendix-b-open-source-parts.md#without-uwb) | fitting the layout to your parts; community STL alternatives |

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
