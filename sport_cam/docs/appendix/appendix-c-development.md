# Appendix C — Development workflow

Local development on the Firebase emulators, deployment, the Docker
workspace, the docs viewer, and diagram regeneration. CAD workflow:
[Appendix A](appendix-a-cad-parts.md).

## Where the code is

```
src/
  backend/        Firebase: the api function, Firestore and Storage rules, the simulated camera
  web/            the Vue web app (Firebase Hosting)
  app_flutter/    the native phone app (direct connection + Firebase)
  with_uwb/       Pi software (device/), anchor firmware (firmware/), tag firmware (wearable/)
  without_uwb/    Pi software (device/)
```

npm workspaces: `src/backend`, `src/backend/functions`, `src/web`. Run all
`npm` commands from the repo root.

## Quick start: the emulators

Requirements: Node 22; Java 17+ (Firestore and Storage emulators).

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

Simulated camera: same protocol as the Pi. Maintains `cameras/dev-camera-key`,
adopts app requests, posts preview frames while watched, and on recording
stop uploads `sim/sample.mp4` via `createUploadUrl` → `PUT` →
`finalizeRecording`. The dev web app uses this key automatically.

- First run downloads the emulators (a few hundred MB; cached in
  `~/.cache/firebase`).
- Build of the simulated camera: `TRACKING_MODE` (`npm run dev:without_uwb`
  for camera-only). Wording per build:
  [01 — State machine](../product/01-requirements.md#state-machine).

### A real camera against the emulators

| Setting (Pi `config.py` / environment) | Value |
| --- | --- |
| `FIREBASE_PROJECT` | `"demo-sportcam"` |
| `CAMERA_KEY` | any value |
| `UPLOAD_API_BASE` | `"http://<your-computer>:5001/demo-sportcam/us-central1/api"` |
| environment | `FIRESTORE_EMULATOR_HOST=<your-computer>:8080` |

No credentials needed. Web app: `http://<your-computer>:5173/#key=<that key>`.

### Tests

```bash
npm test                                              # the API, against its own emulators (works alongside npm run dev)
npm run typecheck                                     # function + web app
python3 src/<build>/device/tests/test_cloud.py       # the Pi's Firebase link, against an in-memory Firestore
for t in src/<build>/device/tests/test_*.py; do python3 $t | tail -1; done   # all the Pi's offline tests
```

The Flutter app's checks are in [`src/app_flutter/README.md`](../../src/app_flutter/README.md#verification-without-a-flutter-sdk).

## Deploying

```bash
npx firebase login
./scripts/firebase-setup.sh <project-id>   # once: project, Firestore, bucket, camera account, camera key
npm run deploy                             # build + deploy functions, hosting, rules
```

Then enter the printed values in the camera's `config.py`
([14 — Software setup](../../with_uwb/docs/setup/14-software-setup.md)).
Deployed resources, camera key, cost:
[08](../design/08-recordings-and-cloud.md#deploying-the-firebase-backend).

## Docker workspace (all toolchain requirements pre-installed)

`compose.yaml` + `Dockerfile`: dev workspace with **Node 22, Java 17,
OpenSCAD and the Python render stack** (schemdraw, matplotlib, pillow,
numpy-stl). Used by `sbx_run_claude.sh`:

```bash
docker compose up -d workspace      # build image, npm install, idle ready
TRACKING_MODE=without_uwb docker compose up -d workspace   # …simulating the camera-only build
docker compose exec workspace bash  # shell with every tool available
```

| Aspect | Detail |
| --- | --- |
| Published ports | 5173 (app), 5001 / 8080 / 9199 (emulators), 4000 (emulator UI), 8090 (docs) |
| Repo | bind-mounted at `/workspace`; `node_modules` in named volumes (no host/container conflicts) |
| Supported tasks | `npm run dev`, `npm test`, `npm run docs`, `./<build>/cad/render_all.sh`, `python3 <build>/cad/render_previews.py`, `<build>/schematics/render_*.py` |

## Browsing the docs

```bash
npm run docs       # → http://localhost:8090
```

| Aspect | Detail |
| --- | --- |
| Implementation | `tools/docs-server.mjs` + `tools/docs-viewer.js`; Node only (no npm install); `marked` vendored in `tools/vendor/` (offline) |
| Sidebar | reading order: README, Product, Design, Setup, appendices |
| Links | doc-to-doc links stay in the viewer; code/STL links open raw in a new tab |
| Deep links | e.g. `http://localhost:8090/#with_uwb/docs/setup/10-bill-of-materials.md` |
| Port | 8090; override with `DOCS_PORT`. Coexists with `npm run dev` |
| Code changes | restart `npm run docs` after editing `tools/docs-server.mjs` (sidebar is built by the server) |

**Build toggle.** **With UWB / Without UWB** switch at the top of the
sidebar; one build at a time; persisted per browser (`localStorage`). Hidden
for the non-selected build:

- that build's own docs in the sidebar; switching while reading one (say the
  wiring guide) opens the other build's copy of it
- sections headed **With UWB** / **Without UWB**, or "*something*, with UWB"
- list items that start with the build's name, table columns headed by it,
  and table rows whose first two cells name it
- the other half of a "with UWB · without UWB" link pair; links into the
  other build's docs point at your build's copy where there is one, and a
  link that has no copy switches the toggle when you follow it
- wording marked in the markdown, below

Comparison tables keep both builds: precede the table with a
`<!--compare-->` line.

Mixed-build sentences in shared docs are marked with HTML comments (hidden
by GitHub, so GitHub shows the combined text):

| Marker | Shown on GitHub | Shown in the viewer |
| --- | --- | --- |
| `<!--with_uwb-->…<!--/-->` | yes | with UWB |
| `<!--without_uwb-->…<!--/-->` | yes | without UWB |
| `<!--both-->…<!--/-->` | yes | never: wording for both builds |
| `<!--with_uwb: …-->` | no | with UWB, in place of a `both` passage |
| `<!--without_uwb: …-->` | no | without UWB, in place of a `both` passage |

```markdown
Runtime is about **<!--with_uwb-->6.2 h<!--/--><!--both--> with UWB, <!--/--><!--without_uwb-->8.4 h<!--/--><!--both--> without<!--/-->**.
See <!--both-->each build's section<!--/--><!--with_uwb: [With UWB](#with-uwb)--><!--without_uwb: [Without UWB](#without-uwb)--> below.
```

Rules: a marker never starts a line inside a paragraph, list item or table
row (GitHub renders such a line as raw HTML); for a whole paragraph, put
each marker on its own line with blank lines around. Markers don't nest. The
`<!--with_uwb: …-->` form can't contain `--`. In lists, a build-specific item
can instead start with **With UWB** / **Without UWB** in bold; in tables, a
row whose first two cells name one build is hidden automatically. `python3 tools/check-build-markers.py`
checks all of this (the pre-commit hook runs it when a doc changes), and
`--show with_uwb <doc>` prints a doc as one build sees it.

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
