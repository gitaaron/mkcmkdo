# 06 — Server & companion app

One repo, npm workspaces, one command:

```bash
npm install
npm run dev     # concurrently: tsx watch server (API :8787) + vite (web :5173)
```

Both sides hot-reload on `src` changes (`tsx watch` restarts the API, Vite
HMRs the app). The Vite dev server proxies `/api` and `/ws` to the API, so
the app only ever talks to its own origin.

## Server (`server/`)

Node 20+, TypeScript, Express + `ws`. Layout:

```
server/src/
  index.ts            bootstrap: http server, WS hub, function mounting, simulator
  hub.ts              WebSocket hub: app clients + device connections, broadcasts
  state.ts            the state machine (single source of truth) + store interface
  stream.ts           MJPEG relay: latest-frame buffer → multipart HTTP response
  sim.ts              device simulator (SIM=1): fake head that streams test frames
  functions/          ── portable, Firebase-callable-shaped functions ──
    index.ts          registry
    power.ts          setPower({on})
    tracking.ts       startTracking(), stopTracking()
    recording.ts      startRecording(), stopRecording()
    status.ts         getState()
  lib/adapters.ts     mountLocal(app, fns)  — Express adapter
```

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
  [05 — Device software](05-device-software.md)).
- Production video is WebRTC directly from the Pi (MediaMTX/WHEP); the server
  hands the app the WHEP URL in the state payload (`whepUrl`), and the app
  falls back to MJPEG when it's absent — which is how the simulator works.

## Web app (`web/`)

Vue 3 + Vite + TypeScript, no UI framework — one screen, three components:

```
web/src/
  App.vue                shell; opens stream + WS on mount
  components/
    VideoView.vue        WHEP video with MJPEG <img> fallback, full-bleed
    StatusRing.vue       top-right circular indicator, colours = LED colours
    ControlBar.vue       bottom buttons, swap with state
  lib/api.ts             call(name, data) + typed wrappers
  lib/useCameraState.ts  composable: WS client, reconnecting, reactive state
```

Behaviour (matches the mock in [01 — System overview](01-system-overview.md)):

- **Opening the app starts the stream** — `VideoView` mounts immediately;
  no play button.
- Status ring top-right: grey `off` / blue `idle` / green `tracking` /
  pulsing red `recording`; it also doubles as the connection indicator
  (hollow while WS is down).
- Bottom buttons by state:
  - `idle` → **Turn off** · **Start tracking**
  - `tracking` → **Turn off** · **Start recording**
  - `recording` → **Stop recording** · **Stop tracking** (confirm dialog,
    since it also stops the recording)
- All buttons just `call()` a function; the UI never assumes success — it
  waits for the state broadcast, so app, LED ring, and any second phone stay
  in lock-step.

## Configuration

| Env | Default | Meaning |
| --- | --- | --- |
| `PORT` | `8787` | API port |
| `SIM` | `1` in dev | run the built-in device simulator when no head connects |
| `VITE_API_BASE` | same-origin | override for app pointing at a remote server |

## Testing

`server/src/functions` are pure against the `Store` interface — unit-test by
calling them with a memory store (`npm test` runs vitest). The state-machine
transition table in `state.ts` is the one piece of logic worth exhaustive
tests; illegal transitions (e.g. `startRecording` from `idle`) throw
`FnError("failed-precondition")`, which the adapter maps to HTTP 412 and
Firebase would map to the same-named callable error.
