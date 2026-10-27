# 08 — Recordings, cloud backend & gym Wi-Fi

Recording pipeline from the Pi to the Firebase library, backend deployment,
and Wi-Fi provisioning at a new location.

## The recording lifecycle

```
stop recording
   └─► Pi finalizes the MP4 (moov atom written — file is playable)
        └─► background upload  createUploadUrl → PUT, for the clip and its boxes
             │                  → finalizeRecording
             │   (tracking + live streaming continue; app shows progress)
             └─► backend confirms byte count
                  └─► Pi deletes its local copy   (SD card = buffer, not store)
                       └─► app library streams it back, with seeking
```

- The local file is deleted only after `finalizeRecording` returns (byte
  count confirmed). Failed or unconfirmed uploads keep the file; hence the
  retry sweep and the space guard ([failure behaviour](#failure-behaviour)).
- **Decision: recordings are stored in the backend, not on the Pi.**
  Rationale: the Pi is busy encoding and tracking; the SD card is small and
  wears under video writes; the camera is packed away after a session.
- Cost: delay before playback. 12 Mbit/s → ≈ 450 MB per 5 min clip → 30–90 s
  upload on typical Wi-Fi. The app shows progress, then a **"Recording saved
  — watch now"** toast.
- Watching a clip while it is still recording is out of scope
  ([F7](../product/01-requirements.md#functional-requirements)); it would
  need fragmented MP4 or HLS.

## The library in Firebase

Uploads go **directly to Cloud Storage** on a signed URL. The API issues URLs
and verifies results; video never passes through a function (32 MB request
limit).

| Callable | Function |
| --- | --- |
| `createUploadUrl({name})` | V4-signed Cloud Storage `PUT` URL, valid 30 min, for a clip (`.mp4`) or its boxes (`.boxes.json`) |
| `finalizeRecording({name,bytes,durationS,boxes})` | verifies the object exists and its size matches, and with `boxes: true` that the boxes were uploaded too; writes `cameras/{key}/recordings/{name}`; clears the app's upload indicator |
| `getRecordings()` | that collection, newest first, each with `url` and `boxesUrl` (null without boxes) |
| `GET /api/recordings/:name?k=<key>` | a clip: 302 to a signed Cloud Storage `GET` URL, valid 6 h. Its boxes: streamed through the function, so the apps can fetch them without CORS on the bucket |

- **Range requests** are required for seeking in a phone `<video>`; Cloud
  Storage supports them.
- **Emulators:** no URL signing available. `createUploadUrl` returns the
  function's own `PUT /api/recordings/upload/:name`, and playback streams
  through the function with `Range` support. Transparent to the uploader.

### Person boxes

While recording, the camera notes every person the detector finds, a few
times a second, with the tracker's verdict on each (`boxlog.py`). They are
saved beside the clip as `<clip>.boxes.json`, uploaded with it, and deleted
from the card with it. The app's player draws them over the video and has a
**Boxes on / off** control. The same boxes are drawn over the
[live view](#in-the-live-view), with a control of its own.

| Colour | Label | Means |
| --- | --- | --- |
| **green** | `climber` | the person the camera knows is the climber |
| **yellow** | `other` | anyone else |
| **red** | `unsure` | the camera can't yet tell which is the climber; every box is red until it can |

<!--both-->

With UWB the climber is the tag wearer, and red means two people
are still being told apart, or someone near the tag is in view while the
wearer is out of sight ([05](../with_uwb/design/05-tracking-system.md#boxes-in-the-recording)). Without UWB the climber is the person being
followed, and red means they are out of sight while someone else is in
view ([05](../without_uwb/design/05-tracking-system.md#boxes-in-the-recording)).<!--/--><!--with_uwb: The climber is the tag wearer. Red means
two people are still being told apart, or someone near the tag is in view
while the wearer is out of sight ([05](../with_uwb/design/05-tracking-system.md#boxes-in-the-recording)).--><!--without_uwb: The climber is
the person being followed. Red means they are out of sight while someone
else is in view ([05](../without_uwb/design/05-tracking-system.md#boxes-in-the-recording)).-->

```json
{"v": 1, "size": [1280, 720],
 "frames": [[0.33, [[412, 160, 96, 288, "climber"], [880, 170, 90, 280, "other"]]],
            [0.66, []]]}
```

- One frame per detection: seconds from the start of the clip, then boxes as
  x, y, width and height in pixels of a `size` frame (the preview stream,
  the same view as the recording).
- A player shows a frame's boxes until the next detection, or 1 s at most.
  An empty list means the detector looked and saw nobody.
- Times are measured from the moment recording was asked for; the encoder
  starts a fraction of a second later, so boxes can trail the picture
  slightly.
- About 3 detections a second: a 5-minute clip's boxes are ≈ 50 KB.
- Clips without boxes (older ones, or a failed write) play as before, with no
  control.

#### In the live view

The last detection's labelled boxes (`Head.live_boxes()`), in `awake`,
`tracking` and `recording`; none in `sleep`, when the sensor is off. In `awake` nobody has been picked as the climber yet, so
every box is `unsure` (red).

| Link | How they arrive | Rate |
| --- | --- | --- |
| Direct (Flutter app) | WebSocket message `{"type": "boxes", "size": [1280, 720], "boxes": [[x, y, w, h, label], …]}` on each fresh detection | every detection: ≈ 3/s tracking, 1 per 2 s awake |
| Firebase (relay) | inside the preview frame they belong to: `cameras/{key}/live/preview` gets `size` and `boxes: [{x, y, w, h, label}, …]` (maps: Firestore can't nest arrays). `getPreview` returns them as `[x, y, w, h, label]` lists | with each preview frame, 1/s |

- An empty list means the detector looked and saw nobody. The camera drops
  boxes older than 3 s (`LIVE_BOXES_MAX_AGE_S`), and the apps drop them 3 s
  after they arrive if nothing replaces them.
- Over WebRTC the picture is full-rate but the boxes still come with the
  preview, once a second, so they lag a moving climber.
- **Boxes on / off** sits under the recordings button. It is remembered
  separately from the player's (`showLiveBoxes`).

The camera uploads to `UPLOAD_API_BASE` as `CAMERA_KEY` (set in 14 —
Software setup, the Firebase step). Both empty: recordings stay on the card,
and phones play them over the direct connection
([09](09-direct-connection-and-app.md)).

## The deployed backend

Set up once with `firebase-setup.sh` and deployed with `npm run deploy`
(steps: 14 — Software setup, the Firebase step; commands:
[Appendix C](../appendix/appendix-c-development.md#deploying)). The deploy
(`scripts/firebase-deploy.sh`) builds the function, then deploys functions,
hosting and the Firestore and Storage rules from `src/backend`:

| Endpoint / rule | Content |
| --- | --- |
| `https://<project>.web.app` | a one-line page pointing to the phone app |
| `https://<project>.web.app/api/**` | the API (`api` function, `src/backend/functions/src/app.ts`) |
| Firestore rules | no client access; the phone app reads through the API |
| Storage rules | deny all; clients use short-lived signed URLs only |

Storage layout:

| Data | Location |
| --- | --- |
| Video | `recordings/<camera key>/<name>.mp4` in the bucket |
| Metadata | `cameras/<camera key>/recordings/<name>` in Firestore |

**Running cost** ([C11](../product/01-requirements.md#non-functional-requirements)).
Heartbeat every 5 s ≈ 17 000 Firestore writes per powered-on day (free tier:
20 000/day). Previews only while an app is watching. Idle project: no cost.

## Connecting the camera to gym Wi-Fi from your phone

The Pi has no keyboard or display, and a phone won't give a saved Wi-Fi
password to an app or web page. It will show it as a **Wi-Fi share QR code**
(Android: Settings → Wi-Fi → the network → **Share**; iOS 18+: Passwords →
Wi-Fi → the network → **Show Network QR Code**), and the camera can read
that.

The steps the user takes, and the states they pass through, are in
[01 — Pairing](../product/01-requirements.md#pairing).

Two services share the job ([06](06-device-software.md)):

```
 sportcam-wifi (root)                        sportcam-head (pi)
 wifi_portal.py                              main.py + wifi_link.py
 ─────────────────────────                   ─────────────────────────────
 try saved networks ──► /run/sportcam-wifi.json ──► state connecting / pairing / awake
 hotspot + setup page                              LED ring, PTZ park + near focus
 POST /api/join  ◄──────── {ssid, psk, hidden} ◄── Camera.qr_text() 2×/s
   writes "connecting", answers 202,               parse_wifi_qr()
   joins, writes "online" / "pairing"
```

| Implementation | Detail |
| --- | --- |
| Network control | `nmcli` (NetworkManager, standard on Raspberry Pi OS Bookworm) |
| Status file | `/run/sportcam-wifi.json`: `{state: connecting \| pairing \| online \| offline, message, ssid}`, written atomically by the portal. The head waits for it up to 15 s (`WIFI_STATUS_WAIT_S`), then assumes no portal is installed and goes `awake` |
| QR reading | OpenCV `QRCodeDetector` on the 720p preview, off the event loop; ≈ 50–100 ms a frame on a Pi 4. A failed code isn't resent for 20 s (`QR_RETRY_S`) |
| QR format | `WIFI:S:<ssid>;T:<WPA\|SAE\|WEP\|nopass>;P:<password>;H:<true\|false>;;`, fields in any order, `\;` `\:` `\,` `\\` `\"` escaped. Enterprise (`T:WPA2-EAP`, `E:`) is refused |
| Focus | `QR_FOCUS_M` = 0.5 m while pairing (the nearest `set_focus` allows; `FOCUS_GRID` is clamped at its nearest row, so add a 0.5 m row with `focuscal` if codes don't read). Re-homed on leaving |
| Online check | `wlan0` connected to anything but the hotspot (NetworkManager counts its own hotspot as "connected") |
| Hotspot password | `/etc/sportcam/hotspot-password`, made at install and printed on the head's label (14 — Software setup, step 6). Missing: `sportcam123` |
| Portal auto-open | serves Android `/generate_204` and iOS `/hotspot-detect.html` |
| No network at all | **Use without Wi-Fi** on the setup page: status `offline`, the head goes `awake`, hotspot stays up for direct control ([09](09-direct-connection-and-app.md)) |
| Privileges | the portal runs as root (network configuration); the head never touches the network |

**Limitation:** networks with their own browser login page, and
WPA-Enterprise, can't be joined (no browser on the Pi). Workaround: a phone
hotspot (e.g. `SportCam-Hotspot`), paired once the same way; the Pi
reconnects automatically afterwards.

## Failure behaviour

| Situation | Behaviour |
| --- | --- |
| Wi-Fi drops mid-upload | `upload_with_retry`: exponential backoff 5 s → 5 min, 8 attempts; file kept until confirmed |
| Backend unreachable for the whole session | retry ladder ends after ≈ 15 min; file kept. `upload_loop` retries everything on the card at start-up and every 15 min, oldest first |
| Card nearly full | < 20 min of space: ring blinks orange, app warns. < 5 min: new recordings refused, a running one stopped cleanly ([01 — State machine](../product/01-requirements.md#state-machine), [04](04-electronics.md#the-sd-card)) |
| Backend unreachable at record time | no effect on recording (local); only upload needs the network |
| Internet down at the gym | tracking and recording continue; direct phone connection works on the same Wi-Fi; remote apps show the camera offline |
| Partial upload | Cloud Storage creates the object only on PUT completion, and `finalizeRecording` checks size: no partial files in the library |
| Size mismatch on finalize | `failed-precondition`; local copy kept, retried |
