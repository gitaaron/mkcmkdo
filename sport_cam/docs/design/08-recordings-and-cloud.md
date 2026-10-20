# 08 — Recordings, cloud backend & gym Wi-Fi

How a climb gets from the camera's sensor to your phone's screen, wherever
you are: the library lives in Firebase, so it's there at the gym and at home
alike.

## The recording lifecycle

```
stop recording
   └─► Pi finalizes the MP4 (moov atom written — file is playable)
        └─► background upload  createUploadUrl → PUT → finalizeRecording
             │   (tracking + live streaming continue; app shows progress)
             └─► backend confirms byte count
                  └─► Pi deletes its local copy   (SD card = buffer, not store)
                       └─► app library streams it back, with seeking
```

The delete happens only after `finalizeRecording` returns, which is the
backend confirming the byte count. A failed or unconfirmed upload keeps the
file, which is why the card needs both a retry sweep and a space guard.

Design decision: **recordings live on the backend, not on the Pi.** The Pi
is busy encoding and running the tracking loop, its SD card is small and
wears out under video writes, and you pack the tripod away after a session —
a library stranded on the camera goes dark. The cost is a short delay before
"watch now": at the 12 Mbps record bitrate a 5-minute clip is ≈ 450 MB, so
30–90 s on decent Wi-Fi. The app shows upload progress, then a
**"Recording saved — watch now"** toast.

True *instant* replay (playing a clip while it is still recording) would need
fragmented MP4 or HLS. Deliberately out of scope for v1.

## The library in Firebase

The camera uploads **straight to Cloud Storage**: the API only hands out a
signed URL and checks the result, so the video never passes through a
function (whose request size is capped at 32 MB anyway).

| Callable | Does |
| --- | --- |
| `createUploadUrl({name})` | a V4-signed Cloud Storage `PUT` URL, valid 30 min |
| `finalizeRecording({name,bytes,durationS})` | checks the object exists and its size matches, writes `cameras/{key}/recordings/{name}` in Firestore, clears the app's upload bar |
| `getRecordings()` | that collection, newest first (the web app subscribes to it instead) |
| `GET /api/recordings/:name?k=<key>` | 302 to a signed Cloud Storage `GET` URL, valid 6 h |

Range support is the detail that matters: phone browsers need HTTP range
requests to seek inside a `<video>`, and Cloud Storage serves them.

Under the emulators there is nothing to sign URLs with, so the function
stands in: `createUploadUrl` returns its own `PUT /api/recordings/upload/:name`,
and playback streams the object through the function, honouring `Range`. The
camera's uploader doesn't know the difference.

The camera finds the API through `UPLOAD_API_BASE` in
`src/<build>/device/sportcam/config.py`, and names itself with `CAMERA_KEY`:

```python
UPLOAD_API_BASE = "https://sportcam-aaron.web.app"
CAMERA_KEY = "…"                                    # printed by firebase-setup.sh
```

Leave them empty and the camera keeps its recordings on the card; the phone
can still play them over the direct connection ([09](09-direct-connection-and-app.md)).

## Deploying the Firebase backend

You run `./scripts/firebase-setup.sh <project-id>` once, then
`npm run deploy` ([Appendix C](../appendix/appendix-c-development.md#deploying)
has the commands). `firebase-setup.sh` creates the project and writes `src/backend/.firebaserc`;
creates the Firestore database and the `<project>-recordings` bucket; lets
the function sign URLs; creates the camera's service account (Firestore
only) and saves its key as `sportcam-firebase.json` for you to copy to the
Pi; and generates the camera key. It prints the lines for the camera's
`config.py` and your app link. Without `gcloud` it prints the console steps
instead. **One manual step Google requires:** upgrade the project to the
Blaze plan — Cloud Functions won't deploy on Spark. Free-tier quotas still
apply, so light personal use costs approximately nothing.

`npm run deploy` (`scripts/firebase-deploy.sh`) builds the web app and the
function and deploys functions, hosting and the Firestore and Storage rules
from `src/backend`. What lands:

- `https://<project>.web.app` — the app; open it with your `#key=…` link once
  and the browser remembers the camera
- `https://<project>.web.app/api/**` — the API, served by the single `api`
  function (`src/backend/functions/src/app.ts`)
- Firestore rules: a camera's document, preview and recordings are readable
  by anyone holding its key; nobody can list cameras or write from a client.
  Storage rules deny everything — clients only ever get short-lived signed URLs.

Storage layout: objects at `recordings/<camera key>/<name>.mp4` in the
bucket, metadata at `cameras/<camera key>/recordings/<name>` in Firestore.
Add a bucket lifecycle rule (e.g. delete after 365 days) if you want
automatic cleanup.

**What it costs to leave running.** The camera writes a heartbeat every 5 s
(≈ 17 000 writes in a day it's switched on, inside Firestore's free 20 000)
and previews only while an app is watching. Nothing runs when nobody is
using it, so an idle project costs nothing.

## Connecting the camera to gym Wi-Fi from your phone

The Pi has no keyboard, and gym Wi-Fi isn't in its config. So the head unit
provisions itself through a **captive portal** (`src/<build>/device/sportcam/wifi_portal.py`,
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
| Card nearly full | at 20 min of recording space left the ring blinks orange and the app warns; at 5 min the camera refuses to start a new recording and stops a running one cleanly. See [04](04-electronics.md#the-sd-card) |
| Backend unreachable at record time | Recording is unaffected — recording is local; only the upload needs the network |
| Internet down at the gym | The camera keeps tracking and recording, and the phone still connects directly on the same Wi-Fi; the app from elsewhere shows the camera offline until it's back |
| Partial upload | Cloud Storage only creates the object when the PUT completes, and `finalizeRecording` checks its size, so a half-file never appears in the library |
| Size mismatch on finalize | `failed-precondition`; the Pi keeps the local copy and retries |
