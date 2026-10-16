# SportCam — subject-tracking robotic camera tripod

A camera on a motorized tripod head that pans **±80°**, tilts **−45° to +85°**,
zooms optically, and automatically follows a person wearing an ultra-wideband
tracking tag. It runs off a **USB-C power bank for a 7-hour session** with
nothing plugged in. An LED ring on the enclosure and a companion web app both
show the three system states (idle / tracking / recording).

Motion comes from an off-the-shelf **Arducam PTZ camera and metal pan-tilt
base**, which is what keeps this to a weekend build: no pan stage, no slip
ring, no second microcontroller. The trade is continuous rotation — see
[02 — Mechanical design](docs/02-hardware-mechanical.md).

![System architecture](docs/images/system-architecture.png)

## Documentation

| Doc | Contents |
| --- | --- |
| [01 — System overview](docs/01-system-overview.md) | Goals, concept of operations, state machine |
| [02 — Mechanical design](docs/02-hardware-mechanical.md) | PTZ base, enclosure and lid, anchor arms, battery tray, 3D-printed parts |
| [03 — Electronics](docs/03-electronics.md) | Schematics, wiring, battery power budget and runtime, why a Pi 4 |
| [04 — Tracking system](docs/04-tracking-system.md) | UWB geometry with static anchors, elevation from the third, control loops, vision framing and focus, lock-on, what vision is for |
| [05 — Device software](docs/05-device-software.md) | Pi camera service, wearable firmware, video streaming |
| [06 — Server & app](docs/06-server-and-app.md) | Protocol, function-style API, Vue app, Firebase migration path |
| [07 — Bill of materials](docs/07-bill-of-materials.md) | Every part, CAD price, Canadian sourcing (< 2-week delivery to Toronto), printed parts with STL links |
| [08 — Recordings, cloud & gym Wi-Fi](docs/08-recordings-and-cloud.md) | Upload→library pipeline, Firebase deploy, phone-driven Wi-Fi setup |
| [09 — Direct connection & native app](docs/09-direct-connection-and-app.md) | mDNS discovery, camera-hosted API, the Flutter app |
| [10 — Verification checklist](docs/10-verification.md) | What to measure before printing, check on arrival, and confirm on the bench |
| [**Setup — start here**](docs/setup/README.md) | The two guides to follow, in order: |
| &nbsp;&nbsp;1. [**Assembly guide** (interactive, 3D)](docs/setup/assembly/index.html) | Step-by-step build with a live 3D rendering of every step — open the file directly or via `npm run docs` |
| &nbsp;&nbsp;1a. [**Wiring guide**](docs/setup/wiring.md) | Every connection pin by pin, in order, with checks — linked to the schematics |
| &nbsp;&nbsp;2. [**Software setup**](docs/setup/software_setup.md) | Radios, Pi, calibration and services, in order, with every command |
| [3D printing specifications](docs/3d_printer/specifications.md) | Printer requirements, filament, per-part settings, orientation and print times |
| [Appendix A — CAD printed parts](docs/appendix-a-cad-parts.md) | OpenSCAD render workflow, print settings, measure-first checklist |
| [Appendix B — Open-source printed parts](docs/appendix-b-open-source-parts.md) | Community STL alternatives on Printables/MakerWorld and what each trade costs |

## Repository layout

```
docs/               design docs + rendered PNG diagrams
cad/                parametric OpenSCAD sources for all printed parts (+ render_all.sh → STL)
app_flutter/        native phone app: mDNS discovery + direct camera connection
firebase/           cloud backend: callable API + hosting + Firestore rules
scripts/            firebase-setup.sh / firebase-deploy.sh
schematics/         diagram/schematic sources
  render_diagrams.py      matplotlib → docs/images/*.png
  render_schematics.py    schemdraw   → docs/images/schematic-*.png
  interactive/index.html  d3-hwschematic interactive wiring viewer
server/             Node.js + TypeScript API (function-style, Firebase-ready)
web/                Vue 3 companion app (Vite)
device/             Raspberry Pi 4 camera service (Python) — pan/tilt/zoom, LED, battery
wearable/           UWB tag firmware (Arduino) — see docs/05 for the ULA1 port
```

## Quick start (server + app)

```bash
npm install
npm run dev        # starts API on :8787 and web app on :5173, both with watch
```

### Docker workspace (all toolchain requirements pre-installed)

`compose.yaml` + `Dockerfile` define a dev workspace with **Node 22,
OpenSCAD, and the Python render stack** (schemdraw, matplotlib, pillow,
numpy-stl) baked in — this is the environment `sbx_run_claude.sh` brings up:

```bash
docker compose up -d workspace      # build image, npm install, idle ready
docker compose exec workspace bash  # shell with every tool available
```

Ports 5173 (app), 8787 (API), and 8090 (docs) are published to the host; the
repo is bind-mounted at `/workspace` (node_modules live in named volumes so
host and container installs don't clash). Inside the workspace, all repo
tasks work as documented: `npm run dev`, `npm run docs`,
`./cad/render_all.sh`, `python3 cad/render_previews.py`, and the
`schematics/render_*.py` scripts.

Open http://localhost:5173. With no hardware attached the server runs a built-in
**device simulator** (`SIM=1`, on by default in dev) so the full app — stream
placeholder, state machine, buttons, status ring — works end to end.

## Connecting straight to the camera

On the same Wi-Fi as the camera (gym network, home LAN, or the camera's own
hotspot), the **Flutter app** finds it over mDNS and connects **directly** —
live video and full control with no home server and no internet:

```bash
cd app_flutter && flutter pub get && flutter run
```

A badge in the top-left shows how the app is reaching the camera (Direct /
Server / Searching / Offline) and the status ring top-right shows the camera
state in the LED colours. The camera serves the same callable API as the
server and cloud (`device/sportcam/local_api.py`), so the app is one client
with three possible backends. See
[09 — Direct connection & native app](docs/09-direct-connection-and-app.md).

## Recordings & the gym workflow

Stopping a recording uploads the clip to the backend in the background; the
app shows progress and then a **"Recording saved — watch now"** toast that
opens it in the library (range-seekable playback). Full pipeline, failure
behaviour, and the Pi's phone-driven Wi-Fi setup:
[08 — Recordings, cloud & gym Wi-Fi](docs/08-recordings-and-cloud.md).

To film away from home, deploy the cloud backend and point the Pi at it:

```bash
npm i -g firebase-tools && firebase login
./scripts/firebase-setup.sh <project-id>   # project + bucket + .firebaserc
./scripts/firebase-deploy.sh               # functions + hosting + rules
# then: device/sportcam/config.py → UPLOAD_API_BASE = "https://<project-id>.web.app"
```

At the gym, power the camera on, join its `SportCam-Setup` hotspot from your
phone, open `http://10.42.0.1`, and pick the gym's network — the Pi remembers
it thereafter.

## Building it

Everything you follow to build one is in [`docs/setup/`](docs/setup/README.md),
in order:

1. The **interactive assembly guide**,
   [`docs/setup/assembly/index.html`](docs/setup/assembly/index.html), walks
   through the build in 14 steps with a live 3D model of each one (real STL
   geometry, animated part insertion, callouts, x-ray, motion demo). Open the
   file in a browser, or through the docs viewer below. Regenerate its meshes
   after a CAD change with `python3 docs/setup/assembly/build_models.py`
   (see [docs/setup/assembly/README.md](docs/setup/assembly/README.md)).
   The **[wiring guide](docs/setup/wiring.md)** lists every connection pin by
   pin, in the order the assembly guide makes them.
2. The **[software setup guide](docs/setup/software_setup.md)** takes the
   assembled camera from a blank SD card to filming: radio firmware, the Pi,
   the bench checks and calibrations, the services, and the app.

## Browsing the docs

```bash
npm run docs       # → http://localhost:8090
```

Zero-dependency viewer (`tools/docs-server.mjs`, needs only Node — no npm
install): sidebar listing the README, all design docs, and the CAD readme;
rendered markdown with the PNG diagrams inline; doc-to-doc links navigate
inside the viewer, code/STL links open raw in a new tab. Pages are
deep-linkable — e.g. bookmark the BOM at
`http://localhost:8090/#docs/07-bill-of-materials.md`. Set `DOCS_PORT` if
8090 clashes. Runs happily alongside `npm run dev` (app :5173, API :8787).
Markdown rendering pulls the `marked` library from a CDN, so the first load
needs internet; everything else is served from the repo.

The **interactive wiring schematic** is served by the same command:

> http://localhost:8090/schematics/interactive/index.html

Its libraries (d3, ELK, d3-hwschematic) are vendored in
`schematics/interactive/vendor/`, so it works fully offline and from any
static file server rooted at the repo — the ELK layout engine must be
same-origin, which is why a CDN-only version can't work
(`Can not locate elk-worker.js`). Re-fetch/upgrade the vendored libs with
`schematics/interactive/update-vendor.sh`.

## Regenerating the diagrams

```bash
pip install schemdraw matplotlib pillow
python3 schematics/render_diagrams.py
python3 schematics/render_schematics.py
```

## Hardware quick facts

- **Pan / tilt**: Arducam metal PTZ base, two digital servos — ±80° pan, −45°…+85° tilt
- **Zoom**: Arducam IMX477 12 MP with motorized zoom lens, 96°→33° (≈ 3.5× optical)
- **Motion control**: one I2C controller at 0x0C drives pan, tilt, zoom and focus
- **Tracking**: three **static** ULA1 UWB anchors (DWM1000) — 250 mm apart on short arms for bearing, one 250 mm up on a mast for elevation, in a head about 30 cm across — plus distance; vision trims both angles and guards the zoom; focus from distance
- **Power**: USB-C PD bank, 92 Wh → **6.2 h** tracking + recording, with an INA260 fuel gauge
- **Brains**: one Raspberry Pi 4, chosen for its hardware H.264 encoder. No base controller
- **Budget**: ≈ C$1079 full build (own tripod) — Canadian-sourced [BOM](docs/07-bill-of-materials.md)
