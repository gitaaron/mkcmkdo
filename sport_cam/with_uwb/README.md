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

Everything common to both builds — the PTZ base, enclosure, power, Pi, backend
and apps — is in the [shared docs](../README.md#documentation). This
folder has only what is specific to the UWB build.

The camera reports its build to the backend and the apps itself (`TRACKING_MODE` in
`src/with_uwb/device/sportcam/config.py`). To try the apps with a simulated camera
of this build, run `npm run dev` (or `npm run dev:with_uwb`) from the repo root.

## Docs

The docs are numbered in reading order across three folders: product
requirements, design, and setup. Only the ones specific to this build live in
this folder; the rest are shared ([full table of contents](../README.md#documentation)).

| Folder | Doc | Contents |
| --- | --- | --- |
| Product | [01 — Product requirements](../docs/product/01-requirements.md#with-uwb) | this build's session, state machine and requirements (shared doc) |
| Design | [02 — System architecture](../docs/design/02-system-architecture.md#with-uwb) · [03 — Mechanical](../docs/design/03-mechanical-design.md#with-uwb) · [04 — Electronics](../docs/design/04-electronics.md#with-uwb) | this build's sections of the shared design docs |
| Design | [**05 — Tracking system**](docs/design/05-tracking-system.md) | UWB geometry with static anchors, elevation from the third, control loops, vision framing and focus, lock-on, what vision is for |
| Design | [06 — Device software](../docs/design/06-device-software.md#with-uwb) | this build's modules, vision and protocol (shared doc) |
| Setup | [**Setup — start here**](docs/setup/README.md) | the setup docs below, in order, with times |
| Setup | [**10 — Bill of materials**](docs/setup/10-bill-of-materials.md) | Every part, CAD price, Canadian sourcing, printed parts with STL links |
| Setup | [11 — 3D printing](../docs/setup/11-3d-printing.md#with-uwb) | printer, filament, settings; this build's parts (shared doc) |
| Setup | [**12 — Wiring guide**](docs/setup/12-wiring.md) | every connection pin by pin, in order, with checks |
| Setup | [**13 — Assembly guide** (interactive, 3D)](docs/setup/assembly/index.html) | step-by-step build with a live 3D rendering of every step |
| Setup | [**14 — Software setup**](docs/setup/14-software-setup.md) | Radios, Pi, calibration and services, in order, with every command |
| Setup | [**15 — Verification checklist**](docs/setup/15-verification.md) | what to measure before printing, check on arrival, and confirm on the bench |
| Setup | [Interactive wiring schematic](schematics/interactive/index.html) | zoomable view of the whole system (best through `npm run docs`) |
| Appendix | [A — CAD printed parts](../docs/appendix/appendix-a-cad-parts.md#with-uwb) · [B — Open-source alternatives](../docs/appendix/appendix-b-open-source-parts.md#with-uwb) | fitting the layout to your parts; community STL alternatives |

## Files

```
docs/          tracking, BOM, verification, setup guides; images/ is rendered here
cad/           OpenSCAD sources + render_all.sh → cad/stl/ — includes anchor arms, A3 mast, wearable pod
schematics/    render_diagrams.py, render_schematics.py → docs/images/; interactive/ wiring viewer
```

The code for this build is under [`src/with_uwb/`](../src/with_uwb/):

```
device/        Raspberry Pi 4 camera service (Python): PTZ, UWB ranging (uwb.py, rangecal.py), tag sessions, the Firebase link
firmware/      uwb_anchor/ — our own DS-TWR anchor sketch (the `dual-serial` protocol; ULA1s run the vendor firmware)
wearable/      tag_firmware/ — earlier ESP32-UWB tag sketch (pair / record button)
```

```bash
./with_uwb/cad/render_all.sh                    # STLs
python3 with_uwb/cad/render_previews.py         # part previews → docs/images/parts/
python3 with_uwb/schematics/render_diagrams.py  # diagrams → docs/images/
python3 with_uwb/docs/setup/assembly/build_models.py   # assembly guide meshes
```
