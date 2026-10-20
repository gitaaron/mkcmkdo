# SportCam — subject-tracking robotic camera tripod

A camera on a motorized tripod head that pans **±80°**, tilts **−45° to +85°**,
zooms optically, and automatically follows a person. It runs off a **USB-C
power bank for a full session** with nothing plugged in. An LED ring on the
enclosure and a companion app both show the system state
(idle / tracking / recording).

It comes in two builds that share the camera, enclosure, power, Pi, server and
apps, and differ in how the camera finds the subject:

- **[With UWB](with_uwb/README.md)**: the subject wears a UWB tag that the
  camera ranges. It tells your subject from a bystander.
- **[Without UWB](without_uwb/README.md)**: vision only. Nothing to wear, smaller
  and cheaper, but it follows whoever it finds first.

[01 — Product requirements](docs/product/01-requirements.md#the-two-builds)
compares the two. Pick one, then follow its
**setup docs ([with UWB](with_uwb/docs/setup/README.md) ·
[without UWB](without_uwb/docs/setup/README.md))**.

## Documentation

The docs are numbered in reading order and grouped in three folders, with the
appendices last:

- **Product**: what SportCam must do. Functional and non-functional requirements.
- **Design**: how the system, mechanics, electronics and software meet them.
- **Setup**: building it, from ordering and printing the parts to wiring,
  assembly, software and checks.

Shared docs are in [`docs/`](docs/). A doc with build-specific detail covers
the shared material first, then has a **With UWB** section and a **Without
UWB** section. Docs that differ entirely between the builds live in the
build's folder; in paths, `<build>` means `with_uwb` or `without_uwb`.

| # | Doc | Where | Contents |
| --- | --- | --- | --- |
| | **Product** | [`docs/product/`](docs/product/) | |
| 01 | [Product requirements](docs/product/01-requirements.md) | shared | The two builds, functional and non-functional requirements, concept of operations, state machine |
| | **Design** | [`docs/design/`](docs/design/), `<build>/docs/design/` | |
| 02 | [System architecture](docs/design/02-system-architecture.md) | shared | Subsystems, key decisions, each build's architecture |
| 03 | [Mechanical design](docs/design/03-mechanical-design.md) | shared | PTZ base, enclosure, shelf and lid, layout inside, ranges of motion, printed parts |
| 04 | [Electronics](docs/design/04-electronics.md) | shared | Why a Pi 4, PTZ controller, LED ring, power budget and runtime, SD card, bring-up |
| 05 | Tracking system: [with UWB](with_uwb/docs/design/05-tracking-system.md) · [without UWB](without_uwb/docs/design/05-tracking-system.md) | per build | UWB geometry, anchors and control loops · search sweep, lock-on and vision loops |
| 06 | [Device software](docs/design/06-device-software.md) | shared | Pi camera service, motion, vision, status ring, device ↔ server protocol |
| 07 | [Server & app](docs/design/07-server-and-app.md) | shared | Protocol, function-style API, `TRACKING_MODE`, Vue app, Firebase migration path |
| 08 | [Recordings, cloud & gym Wi-Fi](docs/design/08-recordings-and-cloud.md) | shared | Upload → library pipeline, Firebase backend, phone-driven Wi-Fi setup |
| 09 | [Direct connection & native app](docs/design/09-direct-connection-and-app.md) | shared | mDNS discovery, camera-hosted API, the Flutter app |
| | **Setup** | [`docs/setup/`](docs/setup/), `<build>/docs/setup/` | start here: [with UWB](with_uwb/docs/setup/README.md) · [without UWB](without_uwb/docs/setup/README.md) |
| 10 | Bill of materials: [with UWB](with_uwb/docs/setup/10-bill-of-materials.md) · [without UWB](without_uwb/docs/setup/10-bill-of-materials.md) | per build | Every part, price, Canadian sourcing, printed parts with STL links |
| 11 | [3D printing](docs/setup/11-3d-printing.md) | shared | Printer requirements and what to buy, filament, settings, orientation, print order |
| 12 | Wiring guide: [with UWB](with_uwb/docs/setup/12-wiring.md) · [without UWB](without_uwb/docs/setup/12-wiring.md) | per build | Every connection pin by pin, in wiring order, with checks |
| 13 | Assembly guide (interactive 3D): [with UWB](with_uwb/docs/setup/assembly/index.html) · [without UWB](without_uwb/docs/setup/assembly/index.html) | per build | Step-by-step build with a live 3D model of every step |
| 14 | Software setup: [with UWB](with_uwb/docs/setup/14-software-setup.md) · [without UWB](without_uwb/docs/setup/14-software-setup.md) | per build | Blank SD card to filming: Pi, calibration, services, app |
| 15 | Verification checklist: [with UWB](with_uwb/docs/setup/15-verification.md) · [without UWB](without_uwb/docs/setup/15-verification.md) | per build | What to measure before printing, check on arrival, confirm on the bench |
| | **Appendices** | [`docs/appendix/`](docs/appendix/) | |
| A | [CAD printed parts](docs/appendix/appendix-a-cad-parts.md) | shared | Fitting the layout to your parts (`cad/fit.py`), render workflow, per-part notes, measure-first list |
| B | [Open-source printed parts](docs/appendix/appendix-b-open-source-parts.md) | shared | Community STL alternatives and what each trade costs |
| C | [Development workflow](docs/appendix/appendix-c-development.md) | shared | Running the server and apps locally, Docker workspace, docs viewer, regenerating diagrams |

Also in each build's folder: an
interactive wiring schematic ([with UWB](with_uwb/schematics/interactive/index.html) ·
[without UWB](without_uwb/schematics/interactive/index.html)).

## Reading the docs

Browse them on GitHub, or run the docs viewer, which lists every doc in the
order above with diagrams inline and doc-to-doc links working:

```bash
npm run docs       # → http://localhost:8090
```

To run the server and app on your computer (`npm install && npm run dev`), see
[Appendix C](docs/appendix/appendix-c-development.md).

## Repository layout

```
README.md           this file
docs/               docs shared by both builds
  product/          01 — requirements
  design/           02–09 — architecture, mechanical, electronics, software, server, cloud, app
  setup/            11 — 3D printing; assembly/ holds the guides' shared parts catalogue
  appendix/         A — CAD, B — open-source parts, C — development workflow
cad/                ordered_parts.toml + fit.py: fits both builds' CAD to the parts you bought
server/             Node.js + TypeScript API (function-style, Firebase-ready) — one for both builds
web/                Vue 3 companion app (Vite) — one for both builds
app_flutter/        native phone app: mDNS discovery + direct camera connection — one for both builds
firebase/           cloud backend: callable API + hosting + Firestore rules
scripts/            firebase-setup.sh / firebase-deploy.sh
tools/              docs viewer (npm run docs), git hooks

with_uwb/           the UWB-tracked build — README.md is its overview
  docs/design/      05 — tracking system
  docs/setup/       10, 12–15 — BOM, wiring, assembly guide (assembly/), software setup, verification
  docs/images/      rendered diagrams and part previews
  cad/              OpenSCAD sources (+ render_all.sh → STL), incl. anchor arms, mast, wearable pod
  schematics/       diagram/schematic sources → docs/images/; interactive/ wiring viewer
  device/           Raspberry Pi 4 camera service (Python) — PTZ, UWB ranging, LED, battery
  firmware/         DS-TWR anchor sketch (dual-serial alternative to the vendor ULA1 firmware)
  wearable/         UWB tag firmware (Arduino)

without_uwb/        the camera-only build — same layout, without firmware/ and wearable/
```
