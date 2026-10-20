# Appendix C — Development workflow

Running the server and apps on your computer, the Docker workspace with every
tool installed, the docs viewer, and the commands that regenerate the
diagrams. The CAD side (fitting the layout to your parts, rendering STLs) is
in [Appendix A](appendix-a-cad-parts.md).

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
[07 — Server & app](../../docs/design/07-server-and-app.md#tracking-mode).

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
[09 — Direct connection & native app](../../docs/design/09-direct-connection-and-app.md).

## Recordings & the gym workflow

Stopping a recording uploads the clip to the backend in the background; the
app shows progress and then a **"Recording saved — watch now"** toast that
opens it in the library (range-seekable playback). Full pipeline, failure
behaviour, and the Pi's phone-driven Wi-Fi setup:
[08 — Recordings, cloud & gym Wi-Fi](../../docs/design/08-recordings-and-cloud.md).

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

CAD, part previews and the assembly guide's meshes, per build:

```bash
python3 cad/fit.py                                   # fit both builds to cad/ordered_parts.toml, render the STLs
python3 <build>/cad/render_previews.py               # part previews → <build>/docs/images/parts/
python3 <build>/docs/setup/assembly/build_models.py  # assembly guide meshes
```
