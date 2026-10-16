# SportCam — subject-tracking robotic camera tripod

A camera on a motorized tripod head that pans **±80°**, tilts **−45° to +85°**,
zooms optically, and automatically follows a person. It runs off a **USB-C
power bank for a full session** with nothing plugged in. An LED ring on the
enclosure and a companion app both show the three system states
(idle / tracking / recording).

Motion comes from an off-the-shelf **Arducam PTZ camera and metal pan-tilt
base**, which is what keeps this to a weekend build: no pan stage, no slip
ring, no second microcontroller. The trade is continuous rotation — see
[02 — Mechanical design](docs/02-hardware-mechanical.md).

## Two builds, one server and app

SportCam comes in two hardware builds. They share the camera, the PTZ base,
the enclosure, the power system, the Pi, the server, the web app and the
phone app. They differ in how the camera knows where the subject is.

| | [**With UWB**](with_uwb/README.md) | [**Without UWB**](without_uwb/README.md) |
| --- | --- | --- |
| How it finds the subject | the subject wears a UWB tag; three anchors on the head range it 20×/s | vision only: the camera sweeps the room and locks on to the first person it sees |
| Starting a session | switch the tag on | tap **Track & record** in the app |
| Tells your subject from a bystander | yes — the tag does | no — it follows whoever it found first |
| Extra hardware | 3 × ULA1 anchors, 2 anchor arms, an A3 mast, a wearable pod | none |
| Head size | ≈ 30 cm across the arms, 28 cm tall to the mast | Ø 135 mm enclosure, nothing sticking out |
| Runtime (92 Wh bank) | ≈ 6.2 h tracking + recording | ≈ 8.4 h |
| Budget (own tripod) | ≈ C$1079 | ≈ C$716 |
| Server setting | `TRACKING_MODE=with_uwb` (default) | `TRACKING_MODE=without_uwb` |

Pick one, then follow its folder: each has its own bill of materials, CAD,
schematics, wiring guide, assembly guide, software setup and Pi software.

## Documentation

In paths, `<build>` means `with_uwb` or `without_uwb`.

Everything common to both builds is in [`docs/`](docs/). Where a common doc
has build-specific detail, the shared material comes first and it ends with
a **With UWB** section and a **Without UWB** section.

| Doc | Contents |
| --- | --- |
| [01 — System overview](docs/01-system-overview.md) | Goals, constraints, subsystems, concept of operations, state machine |
| [02 — Mechanical design](docs/02-hardware-mechanical.md) | PTZ base, enclosure and lid, battery tray, ranges of motion, printed parts |
| [03 — Electronics](docs/03-electronics.md) | Why a Pi 4, PTZ controller, LED ring, power budget and runtime, SD card, bring-up |
| [05 — Device software](docs/05-device-software.md) | Pi camera service, motion, vision, status ring, device ↔ server protocol |
| [06 — Server & app](docs/06-server-and-app.md) | Protocol, function-style API, `TRACKING_MODE`, Vue app, Firebase migration path |
| [08 — Recordings, cloud & gym Wi-Fi](docs/08-recordings-and-cloud.md) | Upload→library pipeline, Firebase deploy, phone-driven Wi-Fi setup |
| [09 — Direct connection & native app](docs/09-direct-connection-and-app.md) | mDNS discovery, camera-hosted API, the Flutter app |
| [3D printing specifications](docs/3d_printer/specifications.md) | Printer requirements, filament, settings, then each build's parts |
| [Appendix A — CAD printed parts](docs/appendix-a-cad-parts.md) | OpenSCAD render workflow, per-part settings, measure-first checklist |
| [Appendix B — Open-source printed parts](docs/appendix-b-open-source-parts.md) | Community STL alternatives and what each trade costs |

Specific to one build:

| | With UWB | Without UWB |
| --- | --- | --- |
| Overview | [with_uwb/README.md](with_uwb/README.md) | [without_uwb/README.md](without_uwb/README.md) |
| 04 — Tracking system | [UWB geometry, anchors, control loops](with_uwb/docs/04-tracking-system.md) | [search sweep, lock-on, vision loops](without_uwb/docs/04-tracking-system.md) |
| 07 — Bill of materials | [BOM](with_uwb/docs/07-bill-of-materials.md) | [BOM](without_uwb/docs/07-bill-of-materials.md) |
| 10 — Verification checklist | [checklist](with_uwb/docs/10-verification.md) | [checklist](without_uwb/docs/10-verification.md) |
| **Setup — start here** | [with_uwb/docs/setup](with_uwb/docs/setup/README.md) | [without_uwb/docs/setup](without_uwb/docs/setup/README.md) |
| &nbsp;&nbsp;1. Assembly guide (interactive 3D) | [index.html](with_uwb/docs/setup/assembly/index.html) | [index.html](without_uwb/docs/setup/assembly/index.html) |
| &nbsp;&nbsp;1a. Wiring guide | [wiring.md](with_uwb/docs/setup/wiring.md) | [wiring.md](without_uwb/docs/setup/wiring.md) |
| &nbsp;&nbsp;2. Software setup | [software_setup.md](with_uwb/docs/setup/software_setup.md) | [software_setup.md](without_uwb/docs/setup/software_setup.md) |

## Repository layout

```
README.md           this file — start here, pick a build
docs/               design docs common to both builds
server/             Node.js + TypeScript API (function-style, Firebase-ready) — one for both builds
web/                Vue 3 companion app (Vite) — one for both builds
app_flutter/        native phone app: mDNS discovery + direct camera connection — one for both builds
firebase/           cloud backend: callable API + hosting + Firestore rules
scripts/            firebase-setup.sh / firebase-deploy.sh
tools/              docs viewer (npm run docs)

with_uwb/           the UWB-tracked build
  docs/             tracking, BOM, verification, setup guides, rendered images
  cad/              OpenSCAD sources (+ render_all.sh → STL), incl. anchor arms, mast, wearable pod
  schematics/       diagram/schematic sources → with_uwb/docs/images/
  device/           Raspberry Pi 4 camera service (Python) — PTZ, UWB ranging, LED, battery
  firmware/         DS-TWR anchor sketch (dual-serial alternative to the vendor ULA1 firmware)
  wearable/         UWB tag firmware (Arduino)

without_uwb/        the camera-only build
  docs/             tracking, BOM, verification, setup guides, rendered images
  cad/              OpenSCAD sources (+ render_all.sh → STL)
  schematics/       diagram/schematic sources → without_uwb/docs/images/
  device/           Raspberry Pi 4 camera service (Python) — PTZ, vision search and tracking, LED, battery
```

The Pi software stays per build because it drives different hardware: the
UWB build ranges a tag; the camera-only build sweeps and tracks by vision.
Each one reports its build to the server and to phones, so the apps word
their buttons for it.

## Quick start (server + app)

```bash
npm install
npm run dev                  # API on :8787 and web app on :5173, both with watch
                             # serves the with_uwb build (the default)
npm run dev:without_uwb      # same, for the camera-only build
```

The server's build is set by **`TRACKING_MODE`** (`with_uwb` or
`without_uwb`, default `with_uwb`). Set it to match the camera you are running.
It goes out to every app in each state snapshot, and the apps change their
wording to match:

| | `with_uwb` | `without_uwb` |
| --- | --- | --- |
| Primary button in idle | **Start tracking** | **Track & record** |
| Primary button while tracking | **Start recording** | **Record now** |
| Status while acquiring | "Acquiring subject…" | "Looking for a person…" |
| Wearable messages (`tagButton`, `lost`) | acted on | ignored — there is no tag |

If a camera of the other build connects, the server logs a warning naming the
`TRACKING_MODE` to restart with. Details:
[06 — Server & app](docs/06-server-and-app.md#tracking-mode).

### Docker workspace (all toolchain requirements pre-installed)

`compose.yaml` + `Dockerfile` define a dev workspace with **Node 22,
OpenSCAD, and the Python render stack** (schemdraw, matplotlib, pillow,
numpy-stl) baked in — this is the environment `sbx_run_claude.sh` brings up:

```bash
docker compose up -d workspace      # build image, npm install, idle ready
TRACKING_MODE=without_uwb docker compose up -d workspace   # …for the camera-only build
docker compose exec workspace bash  # shell with every tool available
```

Ports 5173 (app), 8787 (API), and 8090 (docs) are published to the host; the
repo is bind-mounted at `/workspace` (node_modules live in named volumes so
host and container installs don't clash). Inside the workspace, all repo
tasks work as documented: `npm run dev`, `npm run docs`,
`./with_uwb/cad/render_all.sh`, `python3 with_uwb/cad/render_previews.py`,
and the `<build>/schematics/render_*.py` scripts.

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
server and cloud (`<build>/device/sportcam/local_api.py`), so the app is one
client with three possible backends. See
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
# then: <build>/device/sportcam/config.py → UPLOAD_API_BASE = "https://<project-id>.web.app"
```

At the gym, power the camera on, join its `SportCam-Setup` hotspot from your
phone, open `http://10.42.0.1`, and pick the gym's network — the Pi remembers
it thereafter.

## Building it

Pick a build, then follow its `docs/setup/` in order:

1. The **interactive assembly guide** (`<build>/docs/setup/assembly/index.html`)
   walks through the build with a live 3D model of each step (real STL
   geometry, animated part insertion, callouts, x-ray, motion demo). Open the
   file in a browser, or through the docs viewer below. Regenerate its meshes
   after a CAD change with `python3 <build>/docs/setup/assembly/build_models.py`.
   The **wiring guide** (`<build>/docs/setup/wiring.md`) lists every
   connection pin by pin, in the order the assembly guide makes them.
2. The **software setup guide** (`<build>/docs/setup/software_setup.md`)
   takes the assembled camera from a blank SD card to filming: the Pi (and,
   with UWB, the radio firmware), the bench checks and calibrations, the
   services, and the app.

## Browsing the docs

```bash
npm run docs       # → http://localhost:8090
```

Zero-dependency viewer (`tools/docs-server.mjs`, needs only Node — no npm
install). The sidebar lists this README and the common docs, then one section
per build. Markdown renders with the PNG diagrams inline; doc-to-doc links
navigate inside the viewer, code/STL links open raw in a new tab. Pages are
deep-linkable — e.g. bookmark the UWB build's BOM at
`http://localhost:8090/#with_uwb/docs/07-bill-of-materials.md`. Set
`DOCS_PORT` if 8090 clashes. Runs happily alongside `npm run dev` (app :5173,
API :8787). Markdown rendering pulls the `marked` library from a CDN, so the
first load needs internet; everything else is served from the repo.

Each build's **interactive wiring schematic** is served by the same command:

> http://localhost:8090/with_uwb/schematics/interactive/index.html
> http://localhost:8090/without_uwb/schematics/interactive/index.html

Its libraries (d3, ELK, d3-hwschematic) are vendored in
`<build>/schematics/interactive/vendor/`, so it works fully offline and from
any static file server rooted at the repo — the ELK layout engine must be
same-origin, which is why a CDN-only version can't work
(`Can not locate elk-worker.js`). Re-fetch/upgrade the vendored libs with
`<build>/schematics/interactive/update-vendor.sh`.

## Regenerating the diagrams

```bash
pip install schemdraw matplotlib pillow
python3 with_uwb/schematics/render_diagrams.py       # → with_uwb/docs/images/
python3 with_uwb/schematics/render_schematics.py
python3 without_uwb/schematics/render_diagrams.py    # → without_uwb/docs/images/
python3 without_uwb/schematics/render_schematics.py
```

## Hardware quick facts

Both builds:

- **Pan / tilt**: Arducam metal PTZ base, two digital servos — ±80° pan, −45°…+85° tilt
- **Zoom**: Arducam IMX477 12 MP with motorized zoom lens, 96°→33° (≈ 3.5× optical)
- **Motion control**: one I2C controller at 0x0C drives pan, tilt, zoom and focus
- **Power**: USB-C PD bank, 92 Wh, with an INA260 fuel gauge
- **Brains**: one Raspberry Pi 4, chosen for its hardware H.264 encoder. No base controller

With UWB:

- **Tracking**: three **static** ULA1 UWB anchors (DWM1000) — 250 mm apart on short arms for bearing, one 250 mm up on a mast for elevation, in a head about 30 cm across — plus distance; vision trims both angles and guards the zoom; focus from distance
- **Runtime**: **6.2 h** tracking + recording
- **Budget**: ≈ C$1079 full build (own tripod) — [BOM](with_uwb/docs/07-bill-of-materials.md)

Without UWB:

- **Tracking**: vision only. A HOG person detector drives a search sweep (pan ±80°) until it finds someone, then locks onto the first person, follows them with pan/tilt control loops, and frames them with the zoom. Auto-records on lock; re-sweeps after 6 s lost; gives up to idle after 180 s with nobody found
- **Runtime**: **≈ 8.4 h** tracking + recording (estimated)
- **Budget**: ≈ C$716 full build (own tripod) — [BOM](without_uwb/docs/07-bill-of-materials.md)
