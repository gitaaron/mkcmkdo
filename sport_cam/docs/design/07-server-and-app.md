# 07 — Server & companion app

One repo, npm workspaces, one command — and **one server and one app for
both builds**:

```bash
npm install
npm run dev                  # concurrently: tsx watch server (API :8787) + vite (web :5173)
npm run dev:without_uwb      # the same, serving the camera-only build
```

Both sides hot-reload on `src` changes (`tsx watch` restarts the API, Vite
HMRs the app). The Vite dev server proxies `/api` and `/ws` to the API, so
the app only ever talks to its own origin.

## Tracking mode

The server serves one build at a time, set by the **`TRACKING_MODE`**
environment variable:

| `TRACKING_MODE` | Build | |
| --- | --- | --- |
| `with_uwb` *(default)* | [with UWB](../../with_uwb/README.md) | the subject wears a tag; the tag starts and ends sessions |
| `without_uwb` | [without UWB](../../without_uwb/README.md) | vision only; the camera sweeps for a person and locks on |

Anything else stops the server at start-up with a message listing the valid
values. `npm run dev:with_uwb` / `npm run dev:without_uwb` set it for you, and
`compose.yaml` passes `TRACKING_MODE` through from the host.

What the mode changes is deliberately small, because the state machine, the
API and the protocol are the same for both builds:

| | `with_uwb` | `without_uwb` |
| --- | --- | --- |
| `mode` in every state snapshot (`getState`, `WS /ws`, `GET /api/health`) | `"with_uwb"` | `"without_uwb"` |
| `tagButton` from the head (long press toggles recording) | acted on | ignored |
| `lost` from the head (tag gone → idle, saving the clip) | acted on | ignored — a lost person means sweep again, which the head handles |
| Every other message and callable | same | same |

The apps read `mode` from the snapshot and pick their wording from it
(`web/src/lib/modeText.ts`, `ModeText` in `app_flutter/lib/models.dart`). A
snapshot without `mode` — an older backend — is treated as `with_uwb`.

Each camera also knows its own build (`TRACKING_MODE` in
`<build>/device/sportcam/config.py`), sends it in its `hello`, and includes it
in the state it serves to phones that connect directly
([09](09-direct-connection-and-app.md)). The server keeps its own setting
either way, but if a head reports a different mode it logs:

```
[hub] head reports mode 'without_uwb' but TRACKING_MODE is 'with_uwb' — restart the server with TRACKING_MODE=without_uwb
```

## Server (`server/`)

Node 20+, TypeScript, Express + `ws`. Layout:

```
server/src/
  index.ts            bootstrap: http server, WS hub, function mounting, simulator
  hub.ts              WebSocket hub: app clients + device connections, broadcasts
  state.ts            the state machine (single source of truth), store interface, TRACKING_MODE
  stream.ts           MJPEG relay: latest-frame buffer → multipart HTTP response
  recordings.ts       recording store: upload → disk, range-served playback, retention
  sim.ts              device simulator (SIM=1): test frames + sample recordings
  functions/          ── portable, Firebase-callable-shaped functions ──
    index.ts          registry
    power.ts          setPower({on})
    tracking.ts       startTracking(), stopTracking()
    recording.ts      startRecording(), stopRecording()
    recordings.ts     createUploadUrl(), finalizeRecording(), getRecordings()
    status.ts         getState()
  lib/adapters.ts     mountLocal(app, fns)  — Express adapter
```

### The recording library

`recordings.ts` owns uploaded clips: `PUT /api/recordings/upload/:name`
streams to a `.part` temp file and renames on completion (so a partial upload
never appears in the library), `GET /api/recordings/:name` serves them with
HTTP **range** support (phones need it to seek), and a retention budget
(`RECORDINGS_MAX_GB`, default 20) prunes oldest first. The callables
`createUploadUrl` / `finalizeRecording` / `getRecordings` are shared verbatim
with the Firebase deployment — see
[08 — Recordings, cloud backend & gym Wi-Fi](08-recordings-and-cloud.md).

### The Firebase migration trick

Every API operation is a **`CallableFn`**: `(data, ctx) => Promise<result>` —
exactly the shape of a Firebase `onCall` handler. Locally they're mounted as
`POST /api/call/:name` by a ~20-line Express adapter. To move to Firebase:

```ts
// functions/index.ts (Firebase project)
import { onCall } from "firebase-functions/v2/https";
import { fns } from "./functions";           // ← the same files, unchanged
export const startTracking = onCall((req) => fns.startTracking(req.data, req));
```

Only two things need swapping, and both are behind interfaces:
`state.ts`'s `Store` (in-memory now → Firestore doc later) and the realtime
channel (WS broadcast now → Firestore `onSnapshot` later). The web app's API
client (`web/src/lib/api.ts`) likewise has one `call(name, data)` function to
repoint at `httpsCallable`. Device connections stay on a plain WS server
(Cloud Functions don't hold sockets — in a Firebase world the devices would
talk to Firestore/RTDB directly or you'd keep a tiny relay).

### Realtime & video

- `GET /api/stream.mjpeg` — multipart MJPEG relay of the latest device frames
  (dev + fallback path).
- `WS /ws` — app clients; server pushes `{type:"state", ...}` on every change
  plus telemetry at 5 Hz.
- `WS /ws/device` — head/base/sim connections (protocol in
  [06 — Device software](06-device-software.md)).
- Production video is WebRTC directly from the Pi (MediaMTX/WHEP); the server
  hands the app the WHEP URL in the state payload (`whepUrl`), and the app
  falls back to MJPEG when it's absent — which is how the simulator works.

## Web app (`web/`)

Vue 3 + Vite + TypeScript, no UI framework — one screen, three components:

```
web/src/
  App.vue                shell; opens stream + WS on mount, library button, toast
  components/
    VideoView.vue        WHEP video with MJPEG <img> fallback, full-bleed
    StatusRing.vue       top-right circular indicator, colours = LED colours
    ControlBar.vue       bottom buttons, swap with state
    LibraryView.vue      recordings list + <video> player (range-seekable)
  lib/api.ts             call(name, data) + typed wrappers
  lib/chime.ts           recording start/stop chimes (Web Audio)
  lib/modeText.ts        the wording that differs between with_uwb and without_uwb
  lib/useCameraState.ts  composable: WS client, reconnecting, reactive state
```

Behaviour (matches the mock in [01 — System overview](../product/01-requirements.md)):

- **Opening the app starts the stream** — `VideoView` mounts immediately;
  no play button.
- Status ring top-right: grey `off` / blue `idle` / green `tracking`
  (blinking fast until the camera locks on, labelled "Acquiring subject…" with
  UWB or "Looking for a person…" without, while it sweeps and centres) /
  pulsing red `recording`; it also doubles as the connection indicator
  (hollow while WS is down). If acquiring stalls, a pill says "Can't see you
  — step into view, facing the camera" (with UWB) or "Can't find anyone —
  step into the room, facing the camera" (without UWB, after 15 s with nobody
  found).
- **Chimes** (`lib/chime.ts`): a rising two-note chime when recording starts
  and a falling one when it stops, synthesised with Web Audio. Browsers only
  allow sound after a tap, so the first tap on the page arms it. A background
  tab on a computer still chimes; a phone browser suspends background pages,
  so for chimes with the phone in your bag use the native app ([09](09-direct-connection-and-app.md)).
- Bottom buttons by state:
  - `idle` → **Turn off** · **Start tracking** (with UWB) / **Track & record**
    (without UWB: starts the search; recording begins on the first lock-on)
  - `tracking` → **Turn off** · **Start recording** / **Record now**
  - `recording` → **Stop recording** · **Stop tracking** (confirm dialog,
    since it also stops the recording)
- All buttons just `call()` a function; the UI never assumes success — it
  waits for the state broadcast, so app, LED ring, and any second phone stay
  in lock-step.
- **Recording library**: the ▶ button (top-left, badged with the clip count)
  opens `LibraryView`; while a clip uploads the app shows a progress pill,
  and when it lands a **"Recording saved — watch now"** toast opens it in one
  tap. Playback uses a plain `<video>` against the range-capable endpoint, so
  scrubbing works on phones.

## Configuration

| Env | Default | Meaning |
| --- | --- | --- |
| `TRACKING_MODE` | `with_uwb` | which build the server serves: `with_uwb` or `without_uwb` ([above](#tracking-mode)) |
| `PORT` | `8787` | API port |
| `SIM` | `1` in dev | run the built-in device simulator when no head connects |
| `RECORDINGS_DIR` | `server/recordings` | where uploaded clips are stored |
| `RECORDINGS_MAX_GB` | `20` | retention budget; oldest clips pruned beyond it |
| `VITE_API_BASE` | same-origin | override for app pointing at a remote server |

## Testing

`server/src/functions` are pure against the `Store` interface — unit-test by
calling them with a memory store (`npm test` runs vitest). The state-machine
transition table in `state.ts` is the one piece of logic worth exhaustive
tests; illegal transitions (e.g. `startRecording` from `idle`) throw
`FnError("failed-precondition")`, which the adapter maps to HTTP 412 and
Firebase would map to the same-named callable error.

`server/src/hub.test.ts` runs the device side of the protocol over a real
socket in both modes: state reports adopted, no push on reconnect, tag
messages acted on with `with_uwb` and ignored with `without_uwb`, and an
unknown `TRACKING_MODE` rejected.
