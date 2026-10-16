# 08 — Recordings, cloud backend & gym Wi-Fi

How a climb gets from the camera's sensor to your phone's screen — including
when you're at the gym, far from the home server.

## The recording lifecycle

```
stop recording
   └─► Pi finalizes the MP4 (moov atom written — file is playable)
        └─► background upload  createUploadUrl → PUT → finalizeRecording
             │   (tracking + live streaming continue; app shows progress)
             └─► backend confirms byte count
                  └─► Pi deletes its local copy   (SD card = buffer, not store)

The delete happens only after `finalizeRecording` returns, which is the
backend confirming the byte count. A failed or unconfirmed upload keeps the
file, which is why the card needs both a retry sweep and a space guard.
                       └─► app library streams it back, with seeking
```

Design decision: **recordings live on the backend, not on the Pi.** The Pi
is busy encoding and running the tracking loop, its SD card is small and
wears out under video writes, and you pack the tripod away after a session —
a library stranded on the camera goes dark. The cost is a short delay before
"watch now": at the 12 Mbps record bitrate a 5-minute clip is ≈ 450 MB, so
30–90 s on decent Wi-Fi. The app shows upload progress, then a
**"Recording saved — watch now"** toast.

True *instant* replay (playing a clip while it is still recording) would need
fragmented MP4 or HLS. Deliberately out of scope for v1.

## Two backends, one protocol

Both backends speak the identical callable API, so the device and app never
care which they're talking to:

| Callable | Local server | Firebase |
| --- | --- | --- |
| `createUploadUrl({name})` | own `PUT /api/recordings/upload/:name` | V4-signed Cloud Storage PUT URL |
| `finalizeRecording({name,bytes,durationS})` | verify size on disk, write sidecar | verify GCS object, write Firestore doc |
| `getRecordings()` | directory listing, newest first | Firestore query, newest first |
| `GET /api/recordings/:name` | `sendFile` with Range support | 302 → signed GCS URL (GCS serves ranges) |

Range support is the detail that matters: phone browsers need HTTP range
requests to seek inside a `<video>`. Both paths provide it.

| | Home LAN server | Firebase |
| --- | --- | --- |
| Live control + video | ✅ | ❌ (library-only; those callables return `failed-precondition`) |
| Recording library | ✅ | ✅ |
| Reachable from the gym | ❌ (unless you expose it) | ✅ |
| Cost | free | ~$0 at light use (Blaze plan required for Functions) |

Point the Pi at one by setting `UPLOAD_API_BASE` in
`device/sportcam/config.py`:

```python
UPLOAD_API_BASE = "http://homeserver.local:8787"     # home
UPLOAD_API_BASE = "https://sportcam-aaron.web.app"   # gym / anywhere
```

## Deploying the Firebase backend

```bash
npm i -g firebase-tools && firebase login
./scripts/firebase-setup.sh sportcam-aaron   # create project + bucket + .firebaserc
./scripts/firebase-deploy.sh                 # build web app + functions, deploy
```

`firebase-setup.sh` creates the project, writes `firebase/.firebaserc`, and
creates the `<project>-recordings` bucket (via `gcloud` if present, else it
prints the console link). **One manual step Google requires:** upgrade the
project to the Blaze plan — Cloud Functions won't deploy on Spark. Free-tier
quotas still apply, so light personal use costs approximately nothing.

`firebase-deploy.sh` builds the Vue app with a same-origin API base, builds
the functions, and deploys `functions`, `hosting`, and `firestore` rules.
What lands:

- `https://<project>.web.app` — the app (library view works; live control
  shows the camera offline unless you're on the LAN server)
- `https://<project>.web.app/api/**` — the callable API, served by the single
  `api` HTTPS function (`firebase/functions/src/index.ts`)
- Firestore rules are **deny-all**: nothing but the function's Admin SDK
  touches the database, and clients only ever get short-lived signed URLs.

Storage layout: objects at `recordings/<name>.mp4` in the bucket, metadata
docs at `recordings/<name>` in Firestore. Add a bucket lifecycle rule (e.g.
delete after 365 days) if you want automatic cleanup; the local server has an
equivalent `RECORDINGS_MAX_GB` retention budget (default 20 GB, prunes
oldest).

## Connecting the camera to gym Wi-Fi from your phone

The Pi has no keyboard, and gym Wi-Fi isn't in its config. So the head unit
provisions itself through a **captive portal** (`device/sportcam/wifi_portal.py`,
systemd unit `sportcam-wifi.service`):

1. Power the camera on. If it can't reach a network within 60 s, it raises
   its own hotspot: **`SportCam-Setup`**, password `sportcam123`.
2. On your phone, join that network. Android/iOS usually pop the portal
   automatically; otherwise open **`http://10.42.0.1`**.
3. The page lists nearby networks with signal strength. Tap the gym's,
   type its password, hit **Connect**.
4. The Pi drops the hotspot and joins the gym network — NetworkManager
   remembers it, so next visit it connects on its own. Wrong password?
   The hotspot comes back so you can retry.
5. Rejoin the gym Wi-Fi on your phone and open the app.

Implementation notes: uses `nmcli` (NetworkManager is standard on Raspberry
Pi OS Bookworm), serves Android's `/generate_204` and iOS's
`/hotspot-detect.html` probes so the portal auto-opens, and the service runs
as root because changing network config requires it.

**Gym networks with a browser login page** (captive portals of their own) are
the one case this can't solve — the Pi has no browser to accept terms on. Use
your phone's hotspot instead: create one named e.g. `SportCam-Hotspot`, join
the Pi to it once via the portal, and it will reconnect automatically at
every future session.

## Failure behaviour

| Situation | What happens |
| --- | --- |
| Wi-Fi drops mid-upload | `upload_with_retry` retries with exponential backoff (5 s → 5 min, 8 attempts); the file stays on the Pi until confirmed |
| Backend unreachable for the whole session | the ladder above gives up after ~15 min and keeps the file. `upload_loop` then re-attempts everything still on the card at start-up and every 15 min thereafter, oldest first, so the backlog drains as soon as a backend appears |
| Card nearly full | at 20 min of recording space left the ring blinks orange and the app warns; at 5 min the camera refuses to start a new recording and stops a running one cleanly. See [03](03-electronics.md#the-sd-card) |
| Upload never succeeds | File is kept locally; it uploads on the next successful attempt after reconnect |
| Backend unreachable at record time | Recording is unaffected — recording is local; only the upload needs the network |
| Partial upload | Server writes to a `.part` temp file and renames on completion, so a half-file never appears in the library |
| Size mismatch on finalize | `failed-precondition`; the Pi keeps the local copy and retries |
