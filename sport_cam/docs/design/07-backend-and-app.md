# 07 — Backend & companion app

The backend is **Firebase and nothing else**: one HTTPS function for the API,
Firestore for each camera's live state, Cloud Storage for recordings, and
Hosting for the web app. Once it's deployed, nothing runs at home. The same
backend and the same app serve both builds.

Locally the whole backend runs on the **Firebase emulators**, with a
simulated camera standing in for the Pi:

```bash
npm install
npm run dev                  # emulators (functions, Firestore, Storage) + simulated camera + web app :5173
npm run dev:without_uwb      # the same, with the simulated camera as the camera-only build
npm test                     # the API's tests, against their own emulators
```

The function rebuilds on save and the emulator reloads it; Vite hot-reloads
the app and proxies `/api` to the functions emulator, so the app only ever
talks to its own origin, exactly as it does on Hosting. The emulator UI at
http://localhost:4000 shows the camera's document change as you press
buttons. Running and deploying it all: [Appendix C](../appendix/appendix-c-development.md).

## How the pieces talk

```
              Firestore cameras/{key}                 Cloud Storage
         ┌──────── state, telemetry, heartbeat ◄──── recordings/{key}/*.mp4
 camera ─┤        live/preview (while watched)             ▲
  (Pi)   │                    │ onSnapshot                 │ signed PUT / GET
         └── listens for app  ▼                            │
             requests     web app ── /api/call/* ──► api function
                          Flutter app (relay) ──────►  (Express, one function)
```

- **The camera owns its state.** It writes its Firestore
  document directly (`cameras/{CAMERA_KEY}`): build, state, telemetry, a
  heartbeat every 5 s ([06](06-device-software.md#firebase-link)).
- **An app's command** is a call to the API (`startTracking`, …). The
  function checks the transition against the document and writes the new
  state with `stateBy: "app"`. The camera's listener sees it, runs it through
  the same `apply_state()` as every other command, and writes back what it
  actually did (`stateBy: "device"`) — which can differ, if the card is full.
- **Apps follow the document live.** The web app subscribes to it with the
  Firestore SDK; the Flutter app, when it can't reach the camera directly,
  polls `getState`.
- **Live view from anywhere** is a preview, not a stream: while an app calls
  `watch` (every 30 s), the camera posts a frame a second to
  `cameras/{key}/live/preview`. Full-rate video is the camera's own MJPEG or
  WebRTC on its Wi-Fi ([09](09-direct-connection-and-app.md)). Cloud
  Functions can't hold a socket open, so there is no relay to stream through.
- **Recordings** go from the camera straight to Cloud Storage on a signed
  URL, then appear in the library ([08](08-recordings-and-cloud.md)).

### The camera key

Each camera has a **camera key**, a long random string generated at setup
(`CAMERA_KEY` in the camera's `config.py`). It is the camera's document id
and goes with every API call (`X-Camera-Key` header, or `?k=` on a video
URL). The Firestore rules let anyone holding a key *read* that camera's
document, preview and recordings, but never *list* cameras or write anything;
every write goes through the function or the camera's own service account.
So the key is the password: the setup prints an app link with it
(`https://<project>.web.app/#key=…`), the web app keeps it in the browser and
clears it from the address bar, and a leaked key is fixed by changing
`CAMERA_KEY` on the camera.

## Tracking mode

Which build a camera is comes from **the camera itself** (`TRACKING_MODE` in
`src/<build>/device/sportcam/config.py`). It writes it to its document as
`mode`, and the apps word their buttons from it — there is nothing to set on
the backend:

<!--compare-->

| `mode` | Build | |
| --- | --- | --- |
| `with_uwb` | [with UWB](../../with_uwb/README.md) | the subject wears a tag; the tag starts and ends sessions |
| `without_uwb` | [without UWB](../../without_uwb/README.md) | vision only; the camera sweeps for a person and locks on |

The apps read `mode` from the snapshot and pick their wording from it
(`src/web/src/lib/modeText.ts`, `ModeText` in `src/app_flutter/lib/models.dart`).
A snapshot without `mode` — a camera that has never connected — is treated as
`with_uwb`. The tag's and the search's own state changes (tag off → idle,
lock-on → recording) happen on the camera and arrive as ordinary state
reports. In dev, `TRACKING_MODE` picks which build the simulated camera is.

## Backend (`src/backend/`)

The Firebase project root:

```
src/backend/
  firebase.json          functions, hosting (→ src/web/dist), rules, emulator ports
  firebase.test.json     the same rules on other ports, for npm test
  firestore.rules        read a camera by key; no lists, no client writes
  storage.rules          deny all (recordings move on signed URLs)
  functions/src/
    index.ts             the one function: api
    app.ts               the Express app: /api/call/:name, playback, emulator upload, health
    camera.ts            the camera document, snapshots, the state machine, watch/preview
    recordings.ts        createUploadUrl, finalizeRecording, getRecordings, playback
    errors.ts            FnError → HTTP status
    api.test.ts          tests, run against the Firestore and Storage emulators
  sim/
    camera-sim.mjs       the simulated camera (Firestore + the API, like the Pi)
    frames/, sample.mp4  its test picture and its "recording"
```

### The API

`POST /api/call/:name` with `{ data }` → `200 { result }` or
`4xx/5xx { error: { code, message } }`. The camera's own local API speaks the
same protocol ([09](09-direct-connection-and-app.md)), so each app is one
client with two possible backends.

| Call | Does |
| --- | --- |
| `getState` | the camera's snapshot: `mode`, `state`, `telemetry`, `deviceOnline`, `whepUrl`, `upload`, `updatedAt` |
| `setPower({on})` | `off` ↔ `idle`; turning off from any state stops a recording with it |
| `startTracking` / `stopTracking` | `idle` → `tracking`; `tracking`/`recording` → `idle` (stopping and saving a recording) |
| `startRecording` / `stopRecording` | `tracking` → `recording` → `tracking` |
| `watch` | an app is showing the live view: keep previews coming for a minute |
| `getPreview` | the latest preview frame, base64 (for clients that poll) |
| `createUploadUrl` / `finalizeRecording` / `getRecordings` | the recording library ([08](08-recordings-and-cloud.md)) |

Illegal transitions (`startRecording` from `idle`, or asking for the state
it's already in) are `412 failed-precondition`, as on the camera. So is any
command while the camera is **offline** — no heartbeat for 20 s — because
nothing would act on it; `getState` still answers, with `deviceOnline: false`.

## Web app (`src/web/`)

Vue 3 + Vite + TypeScript and the Firebase JS SDK (Firestore only), no UI
framework — one screen:

```
src/web/src/
  App.vue                shell; library button, upload pill, toast; key prompt if no key
  components/
    VideoView.vue        WHEP video when the camera offers it and it's reachable, else the preview
    StatusRing.vue       top-right circular indicator, colours = LED colours
    ControlBar.vue       bottom buttons, swap with state
    LibraryView.vue      recordings list + <video> player (range-seekable)
    KeyPrompt.vue        asks for the camera key if the link didn't carry it
  lib/api.ts             call(name, data) with the camera key + typed wrappers
  lib/firebase.ts        Firestore: the emulator in dev, /__/firebase/init.json deployed
  lib/cameraKey.ts       the key from the link (#key=…), kept in the browser
  lib/useCameraState.ts  live camera document, recordings and preview via onSnapshot
  lib/chime.ts           recording start/stop chimes (Web Audio)
  lib/modeText.ts        the wording that differs between with_uwb and without_uwb
```

Behaviour (the requirements are in [01 — Product requirements](../product/01-requirements.md#companion-app)):

- **Opening the app starts the live view** — `VideoView` mounts immediately;
  no play button.
- Status ring top-right: grey `off` / blue `idle` / green `tracking`
  (blinking fast until the camera locks on, labelled <!--with_uwb-->"Acquiring subject…"<!--/--><!--both--> with
  UWB or <!--/--><!--without_uwb-->"Looking for a person…"<!--/--><!--both--> without<!--/-->, while it sweeps and centres) /
  pulsing red `recording`; it also doubles as the connection indicator
  (hollow while the camera is offline). If acquiring stalls, a pill says <!--with_uwb-->"Can't see you — step into view, facing the camera"<!--/--><!--both--> (with UWB) or<!--/--><!--without_uwb--> "Can't
  find anyone — step into the room, facing the camera" (<!--/--><!--both-->without UWB, <!--/--><!--without_uwb-->after
  15 s with nobody found)<!--/-->.
- **Chimes** (`lib/chime.ts`): a rising two-note chime when recording starts
  and a falling one when it stops, synthesised with Web Audio. Browsers only
  allow sound after a tap, so the first tap on the page arms it. A background
  tab on a computer still chimes; a phone browser suspends background pages,
  so for chimes with the phone in your bag use the native app ([09](09-direct-connection-and-app.md)).
- Bottom buttons by state:
  - `idle` → **Turn off** · <!--with_uwb-->**Start tracking**<!--/--><!--both--> (with UWB) / <!--/--><!--without_uwb-->**Track & record**
    (<!--/--><!--both-->without UWB: <!--/--><!--without_uwb-->starts the search; recording begins on the first lock-on)<!--/-->
  - `tracking` → **Turn off** · <!--with_uwb-->**Start recording**<!--/--><!--both--> / <!--/--><!--without_uwb-->**Record now**<!--/-->
  - `recording` → **Stop recording** · **Stop tracking** (confirm dialog,
    since it also stops the recording)
- All buttons just `call()` a function; the UI never assumes success — it
  waits for the camera's document to change, so app, LED ring, and any second
  phone stay in lock-step.
- **Recording library**: the ▶ button (top-left, badged with the clip count)
  opens `LibraryView`; while a clip uploads the app shows a progress pill,
  and when it lands a **"Recording saved — watch now"** toast opens it in one
  tap. Playback uses a plain `<video>` against the playback URL, which
  redirects to Cloud Storage, so scrubbing works on phones.

## Configuration

| Where | Setting | Meaning |
| --- | --- | --- |
| `src/backend/.firebaserc` | project id | written by `scripts/firebase-setup.sh` |
| function environment | `RECORDINGS_BUCKET` | defaults to `<project>-recordings` |
| camera `config.py` | `FIREBASE_PROJECT`, `CAMERA_KEY`, `UPLOAD_API_BASE`, `FIREBASE_CREDENTIALS` | the camera's link ([14 — Software setup](../../with_uwb/docs/setup/14-software-setup.md)) |
| `npm run dev` | `TRACKING_MODE` | which build the simulated camera is |
| web, dev only | `VITE_CAMERA_KEY` | the camera key in dev (default `dev-camera-key`, the simulator's) |

## Testing

`npm test` (from the repo root or `src/backend`) builds the function and runs
`functions/src/api.test.ts` inside `firebase emulators:exec`, on ports of its
own so it works while `npm run dev` is up. It drives the real Express app
against the real Firestore and Storage emulators:

- the state machine: the happy path, illegal transitions, `setPower`'s
  idempotence, refusal while the camera is offline;
- the camera key: required, well formed, naming a camera that exists;
- the live preview: `watch` and `getPreview`;
- the Firestore rules: a camera, its preview and its recordings readable by
  key; listing cameras and every client write refused;
- the recording library: upload → finalize → list → playback with `Range`,
  size mismatches, unsafe names, and each camera's library kept separate.

The camera's side is tested in `src/<build>/device/tests/test_cloud.py`, and
the Flutter app checks it parses what the API returns with
`dart run tool/verify_against_device.dart <api> <key>` ([09](09-direct-connection-and-app.md#testing-without-hardware-or-a-flutter-sdk)).
