# Appendix C — Development workflow

Running the whole system on your computer on the Firebase emulators,
deploying it, the Docker workspace with every tool installed, the docs
viewer, and the commands that regenerate the diagrams. The CAD side (fitting
the layout to your parts, rendering STLs) is in [Appendix A](appendix-a-cad-parts.md).

## Where the code is

```
src/
  backend/        Firebase: the api function, Firestore and Storage rules, the simulated camera
  web/            the Vue web app (Firebase Hosting)
  app_flutter/    the native phone app (direct connection + Firebase)
  with_uwb/       Pi software (device/), anchor firmware (firmware/), tag firmware (wearable/)
  without_uwb/    Pi software (device/)
```

The npm workspaces are `src/backend`, `src/backend/functions` and `src/web`;
every `npm` command below runs from the repo root.

## Quick start: the emulators

Needs Node 22 and Java 17+ (for the Firestore and Storage emulators).

```bash
npm install
npm run dev                  # emulators + simulated camera + web app on :5173
npm run dev:without_uwb      # the same, with the simulated camera as the camera-only build
```

That starts, together:

| | Where | |
| --- | --- | --- |
| Web app (Vite, hot reload) | http://localhost:5173 | proxies `/api` to the functions emulator |
| Functions emulator | :5001 | the `api` function, rebuilt on save (`tsc --watch`) and reloaded |
| Firestore emulator | :8080 | the web app subscribes to it directly |
| Storage emulator | :9199 | recordings |
| Emulator UI | http://localhost:4000 | watch `cameras/dev-camera-key` change as you press buttons |
| Simulated camera | `src/backend/sim/camera-sim.mjs` | test frames, telemetry, a sample recording |

The simulated camera talks to the emulators exactly as the Pi talks to
Firebase: it keeps `cameras/dev-camera-key` current, adopts the app's
requests, posts preview frames while the app watches, and when a recording
stops it uploads `sim/sample.mp4` through `createUploadUrl` → `PUT` →
`finalizeRecording`. In dev the web app uses that key without asking. The
first run downloads the emulators (a few hundred MB, cached in
`~/.cache/firebase`).

The camera's build sets the apps' wording, and in dev `TRACKING_MODE` picks
the simulated camera's:

| | `with_uwb` | `without_uwb` |
| --- | --- | --- |
| Primary button in idle | **Start tracking** | **Track & record** |
| Primary button while tracking | **Start recording** | **Record now** |
| Status while acquiring | "Acquiring subject…" | "Looking for a person…" |

Details: [07 — Backend & app](../design/07-backend-and-app.md#tracking-mode).

### A real camera against the emulators

To try a Pi against your computer before deploying, set in its `config.py`
`FIREBASE_PROJECT = "demo-sportcam"`, a `CAMERA_KEY` of your choice and
`UPLOAD_API_BASE = "http://<your-computer>:5001/demo-sportcam/us-central1/api"`,
and start it with `FIRESTORE_EMULATOR_HOST=<your-computer>:8080`. No
credentials are needed against the emulators. Open the web app with
`http://<your-computer>:5173/#key=<that key>`.

### Tests

```bash
npm test                                              # the API, against its own emulators (works alongside npm run dev)
npm run typecheck                                     # function + web app
python3 src/<build>/device/tests/test_cloud.py       # the Pi's Firebase link, against an in-memory Firestore
for t in src/<build>/device/tests/test_*.py; do python3 $t | tail -1; done   # all the Pi's offline tests
```

The Flutter app's checks are in [09](../design/09-direct-connection-and-app.md#testing-without-hardware-or-a-flutter-sdk).

## Deploying

```bash
npx firebase login
./scripts/firebase-setup.sh <project-id>   # once: project, Firestore, bucket, camera account, camera key
npm run deploy                             # build + deploy functions, hosting, rules
```

Then put the values the setup printed in the camera's `config.py` (your
build's [14 — Software setup](../../with_uwb/docs/setup/14-software-setup.md)).
Everything about the cloud side — what lands, the camera key, cost — is in
[08 — Recordings, cloud & gym Wi-Fi](../design/08-recordings-and-cloud.md#deploying-the-firebase-backend).

At the gym, power the camera on, join its `SportCam-Setup` hotspot from your
phone, open `http://10.42.0.1`, and pick the gym's network — the Pi remembers
it thereafter.

## Docker workspace (all toolchain requirements pre-installed)

`compose.yaml` + `Dockerfile` define a dev workspace with **Node 22, Java 17
(for the emulators), OpenSCAD, and the Python render stack** (schemdraw,
matplotlib, pillow, numpy-stl) baked in — this is the environment
`sbx_run_claude.sh` brings up:

```bash
docker compose up -d workspace      # build image, npm install, idle ready
TRACKING_MODE=without_uwb docker compose up -d workspace   # …simulating the camera-only build
docker compose exec workspace bash  # shell with every tool available
```

Ports 5173 (app), 5001 / 8080 / 9199 (emulators), 4000 (emulator UI) and
8090 (docs) are published to the host; the repo is bind-mounted at
`/workspace` (node_modules live in named volumes so host and container
installs don't clash). Inside the workspace, all repo tasks work as
documented: `npm run dev`, `npm test`, `npm run docs`,
`./with_uwb/cad/render_all.sh`, `python3 with_uwb/cad/render_previews.py`,
and the `<build>/schematics/render_*.py` scripts.

## Connecting straight to the camera

On the same Wi-Fi as the camera (gym network, home LAN, or the camera's own
hotspot), the **Flutter app** finds it over mDNS and connects **directly** —
full-rate video and control with no internet:

```bash
cd src/app_flutter && flutter pub get && flutter run
```

A badge in the top-left shows how the app is reaching the camera (Direct /
Firebase / Searching / Offline). The camera serves the same callable API as
the Firebase function (`src/<build>/device/sportcam/local_api.py`), so the
app is one client with two possible backends. See
[09 — Direct connection & native app](../design/09-direct-connection-and-app.md).

## Browsing the docs

```bash
npm run docs       # → http://localhost:8090
```

Zero-dependency viewer (`tools/docs-server.mjs`, needs only Node — no npm
install). The sidebar follows the docs' reading order: the README, then
Product, Design, Setup and the appendices, with each build-specific doc listed
once per build. Markdown renders with the PNG diagrams inline; doc-to-doc links
navigate inside the viewer, code/STL links open raw in a new tab. Pages are
deep-linkable — e.g. bookmark the UWB build's BOM at
`http://localhost:8090/#with_uwb/docs/setup/10-bill-of-materials.md`. Set
`DOCS_PORT` if 8090 clashes. Runs happily alongside `npm run dev` (app :5173,
emulators :5001/:8080/:9199/:4000). Markdown rendering pulls the `marked` library from a CDN, so the
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

CAD, part previews and the assembly guide's meshes, per build:

```bash
python3 cad/fit.py                                   # fit both builds to cad/ordered_parts.toml, render the STLs
python3 <build>/cad/render_previews.py               # part previews → <build>/docs/images/parts/
python3 <build>/docs/setup/assembly/build_models.py  # assembly guide meshes
```
