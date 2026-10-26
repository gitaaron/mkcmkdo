# SportCam — subject-tracking robotic camera tripod

Motorized pan/tilt/zoom camera head on a standard tripod that follows a
person and records them. Battery powered; status on an LED ring and in a
companion app.

| Spec | Value |
| --- | --- |
| Pan | ±80° (servo, soft-limited) |
| Tilt | −45° to +85° |
| Zoom | optical, 96° → 33° horizontal FOV (≈ 3.5×) |
| Recording | 1080p H.264, 12 Mbit/s, on the Pi; uploaded to Firebase after each clip |
| Power | USB-C PD power bank, 92 Wh: <!--with_uwb-->6.2 h<!--/--><!--both--> (with UWB) / <!--/--><!--without_uwb-->8.4 h<!--/--><!--both--> (without UWB)<!--/--> tracking and recording |
| States | sleep, awake, tracking (initiate recording), recording ([01](docs/product/01-requirements.md#state-machine)) |
| Control | web app and Flutter app; from anywhere through Firebase, or direct on the camera's Wi-Fi |

## Builds

Two builds share the camera, enclosure, power, Pi, backend and apps. They
differ in how the subject is located. Comparison:
[01 — The two builds](docs/product/01-requirements.md#the-two-builds).
Setup entry point:
[with UWB](docs/with_uwb/setup/README.md) ·
[without UWB](docs/without_uwb/setup/README.md).

### With UWB

- **Sensing:** wearable UWB tag; three anchors on the head range it at
  20 Hz. Bearing, elevation and distance come from the ranges. Vision trims
  the aim, sets the zoom and confirms the person before recording.
- **Session control:** tag on starts a session; tag off ends it.
- **Use when:** the subject must be told apart from bystanders.
- **Locations:** docs in [`docs/with_uwb/`](docs/with_uwb/); CAD and
  schematics in [`with_uwb/`](with_uwb/); code in [`src/with_uwb/`](src/with_uwb/).

### Without UWB

- **Sensing:** vision only. **Track & record** starts a pan sweep (skipped if
  a person is already in frame); the first person detected is followed
  and, still in frame 3 s later, recorded. Re-sweeps after 6 s
  without a detection.
- **Session control:** app buttons.
- **Use when:** cost, size and runtime matter more than identity. Versus the
  UWB build: ≈ C$360 cheaper, ≈ 2 h more runtime, 5 printed parts instead of
  10, nothing worn. Follows the first person found.
- **Locations:** docs in [`docs/without_uwb/`](docs/without_uwb/); CAD and
  schematics in [`without_uwb/`](without_uwb/); code in
  [`src/without_uwb/`](src/without_uwb/).

## Documentation

Docs are numbered in reading order, in three folders plus appendices:

| Folder | Scope |
| --- | --- |
| Product | functional and non-functional requirements |
| Design | system, mechanics, electronics, software |
| Setup | ordering, printing, wiring, assembly, software, verification |

Conventions:

- Shared docs are in [`docs/`](docs/). A shared doc covers common material
  first, then a **With UWB** and a **Without UWB** section.
- Docs that differ entirely by build are in `docs/<build>/`. `<build>` in
  paths means `with_uwb` or `without_uwb`.
- Terms: [Appendix D — Glossary](docs/appendix/appendix-d-glossary.md).
- In the [docs viewer](#reading-the-docs), a toggle shows one build at a time.

| # | Doc | Where | Contents |
| --- | --- | --- | --- |
| | **Product** | [`docs/product/`](docs/product/) | |
| 01 | [Product requirements](docs/product/01-requirements.md) | shared | The two builds, functional and non-functional requirements, concept of operations, state machine |
| | **Design** | [`docs/design/`](docs/design/), `docs/<build>/design/` | |
| 02 | [System architecture](docs/design/02-system-architecture.md) | shared | Subsystems, key decisions, each build's architecture |
| 03 | [Mechanical design](docs/design/03-mechanical-design.md) | shared | PTZ base, enclosure, shelf and lid, layout inside, ranges of motion, printed parts |
| 04 | [Electronics](docs/design/04-electronics.md) | shared | Why a Pi 4, PTZ controller, LED ring, power switch and latch, power budget and runtime, SD card, bring-up |
| 05 | Tracking system: [with UWB](docs/with_uwb/design/05-tracking-system.md) · [without UWB](docs/without_uwb/design/05-tracking-system.md) | per build | <!--with_uwb-->UWB geometry, anchors and control loops<!--/--><!--both--> · <!--/--><!--without_uwb-->search sweep, found → record and vision loops<!--/--> |
| 06 | [Device software](docs/design/06-device-software.md) | shared | Pi camera service, motion, vision, status ring, the Firebase link |
| 07 | [Backend & app](docs/design/07-backend-and-app.md) | shared | Firebase (one function, Firestore, Storage), the camera key, the API, the Vue app |
| 08 | [Recordings, cloud & gym Wi-Fi](docs/design/08-recordings-and-cloud.md) | shared | Upload → library pipeline, Firebase backend, phone-driven Wi-Fi setup |
| 09 | [Direct connection & native app](docs/design/09-direct-connection-and-app.md) | shared | mDNS discovery, camera-hosted API, the Flutter app |
| | **Setup** | [`docs/setup/`](docs/setup/), `docs/<build>/setup/` | start here: [with UWB](docs/with_uwb/setup/README.md) · [without UWB](docs/without_uwb/setup/README.md) |
| 10 | Bill of materials: [with UWB](docs/with_uwb/setup/10-bill-of-materials.md) · [without UWB](docs/without_uwb/setup/10-bill-of-materials.md) | per build | Every part, price, Canadian sourcing, printed parts with STL links |
| 11 | [3D printing](docs/setup/11-3d-printing.md) | shared | Printer requirements and what to buy, filament, settings, orientation, print order |
| 12 | Wiring guide: [with UWB](docs/with_uwb/setup/12-wiring.md) · [without UWB](docs/without_uwb/setup/12-wiring.md) | per build | Every connection pin by pin, in wiring order, with checks |
| 13 | Assembly guide (interactive 3D): [with UWB](docs/with_uwb/setup/assembly/index.html) · [without UWB](docs/without_uwb/setup/assembly/index.html) | per build | Step-by-step build with a live 3D model of every step |
| 14 | Software setup: [with UWB](docs/with_uwb/setup/14-software-setup.md) · [without UWB](docs/without_uwb/setup/14-software-setup.md) | per build | Blank SD card to filming: Pi, calibration, services, app |
| 15 | Verification checklist: [with UWB](docs/with_uwb/setup/15-verification.md) · [without UWB](docs/without_uwb/setup/15-verification.md) | per build | What to measure before printing, check on arrival, confirm on the bench |
| | **Appendices** | [`docs/appendix/`](docs/appendix/) | |
| A | [CAD printed parts](docs/appendix/appendix-a-cad-parts.md) | shared | Fitting the layout to your parts (`cad/fit.py`), render workflow, per-part notes, measure-first list |
| B | [Open-source printed parts](docs/appendix/appendix-b-open-source-parts.md) | shared | Community STL alternatives and what each trade costs |
| C | [Development workflow](docs/appendix/appendix-c-development.md) | shared | Where the code is, running everything on the Firebase emulators, tests, deploying, Docker workspace, docs viewer |
| D | [Glossary](docs/appendix/appendix-d-glossary.md) | shared | The terms the docs use, from *buck converter* to *WS2812B* |
| | Interactive wiring schematic: [with UWB](with_uwb/schematics/interactive/index.html) · [without UWB](without_uwb/schematics/interactive/index.html) | per build | Zoomable view of the whole system (best through `npm run docs`) |

## Reading the docs

On GitHub, or in the local docs viewer (sidebar in reading order, inline
diagrams, working cross-links, and a **With UWB / Without UWB** toggle that
filters docs, sections, table rows and wording; the choice persists):

```bash
npm run docs       # → http://localhost:8090
```

Running the system on the Firebase emulators (`npm install && npm run dev`)
and deploying: [Appendix C](docs/appendix/appendix-c-development.md).

## Repository layout

```
README.md           this file
docs/               all the docs
  product/          01 — requirements
  design/           02–09 — architecture, mechanical, electronics, software, backend, cloud, app
  setup/            11 — 3D printing; assembly/ holds the guides' shared parts catalogue
  appendix/         A — CAD, B — open-source parts, C — development workflow, D — glossary
  with_uwb/         the UWB build's own docs
    design/         05 — tracking system
    setup/          README (start here), 10, 12–15 — BOM, wiring, assembly guide (assembly/), software setup, verification
    images/         rendered diagrams and part previews
  without_uwb/      the camera-only build's own docs — same layout
src/                all the code and apps
  backend/          Firebase: the api function, Firestore/Storage rules, the simulated camera — runs on the emulators locally
  web/              Vue 3 web app (Vite, served by Firebase Hosting)
  app_flutter/      native phone app: mDNS discovery + direct camera connection, Firebase from anywhere
  with_uwb/         Pi software (device/: PTZ, UWB ranging, tag sessions, the Firebase link),
                    our own DS-TWR anchor sketch (firmware/, for the dual-serial protocol; ULA1s run
                    the vendor's firmware), optional ESP32-UWB tag sketch (wearable/)
  without_uwb/      Pi software (device/: PTZ, vision search and tracking, auto-record sessions, the Firebase link)
cad/                ordered_parts.toml + fit.py: fits both builds' CAD to the parts you bought
scripts/            firebase-setup.sh / firebase-deploy.sh
tools/              docs viewer (npm run docs) + its build-marker check, git hooks

with_uwb/           the UWB build's own CAD and schematics
  cad/              OpenSCAD sources (+ render_all.sh → stl/), incl. anchor arms, mast, wearable pod
  schematics/       render_diagrams.py, render_schematics.py → docs/with_uwb/images/; interactive/ wiring viewer

without_uwb/        the camera-only build — same layout, without the anchor and wearable parts
```
