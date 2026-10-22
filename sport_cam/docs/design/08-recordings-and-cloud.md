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
- Out of scope (v1): playback during recording (would need fragmented MP4 or
  HLS).

## The library in Firebase

Uploads go **directly to Cloud Storage** on a signed URL. The API issues URLs
and verifies results; video never passes through a function (32 MB request
limit).

| Callable | Function |
| --- | --- |
| `createUploadUrl({name})` | V4-signed Cloud Storage `PUT` URL, valid 30 min, for a clip (`.mp4`) or its boxes (`.boxes.json`) |
| `finalizeRecording({name,bytes,durationS,boxes})` | verifies the object exists and its size matches, and with `boxes: true` that the boxes were uploaded too; writes `cameras/{key}/recordings/{name}`; clears the app's upload indicator |
| `getRecordings()` | that collection, newest first, each with `url` and `boxesUrl` (null without boxes; the web app subscribes instead) |
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
from the card with it. Both apps' players draw them over the video and have a
**Boxes on / off** control.

| Colour | Label | Means |
| --- | --- | --- |
| **green** | `climber` | the person the camera knows is the climber |
| **yellow** | `other` | anyone else |
| **red** | `unsure` | the camera can't yet tell which is the climber; every box is red until it can |

<!--both-->

With UWB the climber is the tag wearer, and red means two people
are still being told apart, or someone near the tag is in view while the
wearer is out of sight ([05](../../with_uwb/docs/design/05-tracking-system.md#boxes-in-the-recording)). Without UWB the climber is the person being
followed, and red means they are out of sight while someone else is in
view ([05](../../without_uwb/docs/design/05-tracking-system.md#boxes-in-the-recording)).<!--/--><!--with_uwb: The climber is the tag wearer. Red means
two people are still being told apart, or someone near the tag is in view
while the wearer is out of sight ([05](../../with_uwb/docs/design/05-tracking-system.md#boxes-in-the-recording)).--><!--without_uwb: The climber is
the person being followed. Red means they are out of sight while someone
else is in view ([05](../../without_uwb/docs/design/05-tracking-system.md#boxes-in-the-recording)).-->

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

Camera configuration (`src/<build>/device/sportcam/config.py`):

```python
UPLOAD_API_BASE = "https://sportcam-aaron.web.app"
CAMERA_KEY = "…"                                    # printed by firebase-setup.sh
```

Both empty: recordings stay on the card; phones can play them over the
direct connection ([09](09-direct-connection-and-app.md)).

## Deploying the Firebase backend

Commands: `./scripts/firebase-setup.sh <project-id>` (once), then
`npm run deploy` ([Appendix C](../appendix/appendix-c-development.md#deploying)).

`firebase-setup.sh`:

| Step | Result |
| --- | --- |
| Create project | `src/backend/.firebaserc` |
| Create Firestore database and bucket | `<project>-recordings` |
| Grant URL signing | function's service account gets Token Creator on itself |
| Create camera service account | Firestore-only; key saved as `sportcam-firebase.json` (copy to the Pi) |
| Generate camera key | printed with the `config.py` lines and the app link |
| No `gcloud` installed | prints the equivalent console steps |

**Manual step:** upgrade the project to the **Blaze** plan (required for Cloud
Functions). Free-tier quotas still apply.

`npm run deploy` (`scripts/firebase-deploy.sh`) builds the web app and the
function, then deploys functions, hosting and the Firestore and Storage rules
from `src/backend`:

| Endpoint / rule | Content |
| --- | --- |
| `https://<project>.web.app` | web app; opening the `#key=…` link once stores the key in the browser |
| `https://<project>.web.app/api/**` | the API (`api` function, `src/backend/functions/src/app.ts`) |
| Firestore rules | camera document, preview and recordings readable with the key; no listing; no client writes |
| Storage rules | deny all; clients use short-lived signed URLs only |

Storage layout:

| Data | Location |
| --- | --- |
| Video | `recordings/<camera key>/<name>.mp4` in the bucket |
| Metadata | `cameras/<camera key>/recordings/<name>` in Firestore |

Automatic cleanup: add a bucket lifecycle rule (e.g. delete after 365 days).

**Running cost.** Heartbeat every 5 s ≈ 17 000 Firestore writes per powered-on
day (free tier: 20 000/day). Previews only while an app is watching. Idle
project: no cost.

## Connecting the camera to gym Wi-Fi from your phone

The Pi has no keyboard or display, and a phone won't give a saved Wi-Fi
password to an app or web page. It will show it as a **Wi-Fi share QR code**
(Android: Settings → Wi-Fi → the network → **Share**; iOS 18+: Passwords →
Wi-Fi → the network → **Show Network QR Code**), and the camera can read
that. Requirements and states: [01 — Pairing](../product/01-requirements.md#pairing).

1. Power on. State `connecting` (ring: white chase). A saved network joins:
   `idle`, done.
2. None of the saved networks in range at the first scan (≈ 10 s), or none
   joined in 60 s: state `pairing` (ring: white, slow blink). Hotspot
   **`SportCam-Setup`** up, head parked, lens wide and focused near.
3. Hold the phone's Wi-Fi share code 15–30 cm in front of the lens. *Or*
   join `SportCam-Setup` (password on the head's label), let the setup page
   open (or go to **`http://10.42.0.1`**), pick the network and paste the
   password.
4. `connecting` while the Pi drops the hotspot and joins; NetworkManager
   stores the network for next time. Wrong password: the hotspot returns,
   `pairing` again.
5. Joined: `idle`. Open the app.

Two services share the job ([06](06-device-software.md)):

```
 sportcam-wifi (root)                        sportcam-head (pi)
 wifi_portal.py                              main.py + wifi_link.py
 ─────────────────────────                   ─────────────────────────────
 try saved networks ──► /run/sportcam-wifi.json ──► state connecting / pairing / idle
 hotspot + setup page                              LED ring, PTZ park + near focus
 POST /api/join  ◄──────── {ssid, psk, hidden} ◄── Camera.qr_text() 2×/s
   writes "connecting", answers 202,               parse_wifi_qr()
   joins, writes "online" / "pairing"
```

| Implementation | Detail |
| --- | --- |
| Network control | `nmcli` (NetworkManager, standard on Raspberry Pi OS Bookworm) |
| Status file | `/run/sportcam-wifi.json`: `{state: connecting \| pairing \| online \| offline, message, ssid}`, written atomically by the portal. The head waits for it up to 15 s (`WIFI_STATUS_WAIT_S`), then assumes no portal is installed and goes `idle` |
| QR reading | OpenCV `QRCodeDetector` on the 720p preview, off the event loop; ≈ 50–100 ms a frame on a Pi 4. A failed code isn't resent for 20 s (`QR_RETRY_S`) |
| QR format | `WIFI:S:<ssid>;T:<WPA\|SAE\|WEP\|nopass>;P:<password>;H:<true\|false>;;`, fields in any order, `\;` `\:` `\,` `\\` `\"` escaped. Enterprise (`T:WPA2-EAP`, `E:`) is refused |
| Focus | `QR_FOCUS_M` = 0.5 m while pairing (the nearest `set_focus` allows; `FOCUS_GRID` is clamped at its nearest row, so add a 0.5 m row with `focuscal` if codes don't read). Re-homed on leaving |
| Online check | `wlan0` connected to anything but the hotspot (NetworkManager counts its own hotspot as "connected") |
| Hotspot password | `/etc/sportcam/hotspot-password`, made at install and printed on the head's label (14 — Software setup, step 6). Missing: `sportcam123` |
| Portal auto-open | serves Android `/generate_204` and iOS `/hotspot-detect.html` |
| No network at all | **Use without Wi-Fi** on the setup page: status `offline`, the head goes `idle`, hotspot stays up for direct control ([09](09-direct-connection-and-app.md)) |
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
| Card nearly full | < 20 min of space: ring blinks orange, app warns. < 5 min: new recordings refused, a running one stopped cleanly ([04](04-electronics.md#the-sd-card)) |
| Backend unreachable at record time | no effect on recording (local); only upload needs the network |
| Internet down at the gym | tracking and recording continue; direct phone connection works on the same Wi-Fi; remote apps show the camera offline |
| Partial upload | Cloud Storage creates the object only on PUT completion, and `finalizeRecording` checks size: no partial files in the library |
| Size mismatch on finalize | `failed-precondition`; local copy kept, retried |
