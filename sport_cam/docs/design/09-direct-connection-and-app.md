# 09 — Direct phone ↔ camera connection & the native app

Open the app on the same Wi-Fi as the camera and it finds it, streams live
video, and controls it — with no cloud and no internet in the path, at full
frame rate. Away from the camera, the same app reaches it through Firebase.

## Why the camera serves its own API

Firebase gets the app to the camera from anywhere, but only as far as the
cloud reaches: a frame a second of preview, and nothing at all when the gym's
internet is down. So the head unit also runs its own copy of the API
(`src/<build>/device/sportcam/local_api.py`) — the **same callable protocol**
as the Firebase function:

| | Firebase | **Camera (direct)** |
| --- | --- | --- |
| `POST /api/call/*` | ✅ (with the camera key) | ✅ |
| Live view | preview, ~1 frame/s, while watched | `GET /api/stream.mjpeg`, 15 fps (or WebRTC) |
| `GET /api/recordings/:name` | signed URL | ✅ (clips not yet uploaded) |
| Live state | Firestore document | `WS /ws` |
| Works at the gym | needs internet | ✅ **needs nothing** |

Because the protocol is the same, the app's calls are the same; only the
base URL changes. State still lives in one place on the device
(`Head.apply_state`), so a command from a phone connected directly, one
arriving through Firebase, or the camera itself (<!--with_uwb-->the tag being switched on or
off<!--/--><!--both--> with UWB; <!--/--><!--without_uwb-->the first lock-on<!--/--><!--both--> without<!--/-->) all take the same route and everyone
is told the result — app, LED ring, and Firestore stay in lock-step.

The camera's state includes `mode` (`with_uwb` or `without_uwb`, from its
`config.TRACKING_MODE`), so a phone connected directly words its buttons for
that build — see [07 — Tracking mode](07-backend-and-app.md#tracking-mode).

## Discovery: mDNS / Bonjour

The camera publishes `_sportcam._tcp.local` (`src/<build>/device/sportcam/discovery.py`)
with the API port and TXT records:

```
name=SportCam   state=tracking   ver=1
api=/api/call   stream=/api/stream.mjpeg
```

It also answers to `sportcam.local`. The TXT `state` is refreshed on every
transition, so a picker can show what each camera is doing *before*
connecting. This matters because the Pi gets a new DHCP address at every
gym — mDNS is what makes "open the app and it's there" work without typing
IP addresses.

The app's connection strategy (`camera_client.dart`), in order:

1. **mDNS sweep** → connect directly (`LinkMode.direct`)
2. **last known address** — some guest networks block multicast; the app
   remembers the last camera that worked and tries it
3. **Firebase** (`LinkMode.relay`) — when the app was built with the
   backend's address and the camera key (`--dart-define`, [below](#running-it)).
   State is polled every 2 s and the live view is the camera's preview
4. otherwise `LinkMode.offline`, retrying every 3 s

## Why the app is native (Flutter)

The web app is fine through Firebase. For direct connection it hits two hard
walls that are not matters of taste:

1. **Browsers cannot do service discovery.** There is no mDNS/Bonjour API in
   any browser. A web app can only try `http://sportcam.local:8787` and hope
   the platform resolves `.local` — reliable on iOS/macOS, unreliable on
   Android. It can never *enumerate* cameras or read their TXT state.
2. **Mixed content.** The app served from Firebase over HTTPS is forbidden by
   the browser from making plain-HTTP requests to the camera on the LAN. The
   camera can't have a valid TLS certificate for a private IP either. A
   native app has no such restriction.

Given native, the rest follows: hardware-accelerated H.264 playback through
ExoPlayer/AVPlayer, an MJPEG decoder that owns its socket (so a Wi-Fi blip
reconnects in ~2 s instead of leaving a dead `<img>`), and room for
background uploads and notifications later.

**The Vue web app stays** — it's what Firebase Hosting serves, so it works on
any phone or laptop with nothing installed. Both clients speak the same
protocol.

## The app's screen

<!--both-->

![App UI (with UWB wording; the camera-only build shows "Track & record")](../../with_uwb/docs/images/app-ui.png)

<!--/-->

<!--with_uwb: ![App UI](../../with_uwb/docs/images/app-ui.png)-->

<!--without_uwb: ![App UI (with UWB wording; this build shows "Track & record")](../../with_uwb/docs/images/app-ui.png)-->

Same layout as the web app, plus the connection badge:

- **Top-left — connection status** (`ConnectionBadge`): a coloured dot and
  label showing how the app is reaching the camera. Green **"SportCam ·
  Direct · 10.0.0.42"**, blue **"Firebase"** when reaching it from anywhere, amber pulsing
  **"Searching…"** during discovery, red **"Offline — tap to retry"**. Tap it
  any time to re-scan.
- **Top-right — camera state** (`StatusRing`): the LED-ring colours (blue
  idle, green tracking — blinking fast and labelled <!--with_uwb-->"Acquiring subject…"<!--/--><!--both-->
  (with UWB) or <!--/--><!--without_uwb-->"Looking for a person…"<!--/--><!--both--> (without)<!--/--> until the camera locks on —
  pulsing red recording); hollow while disconnected. A pill says <!--with_uwb-->"Can't see
  you — step into view, facing the camera"<!--/--><!--both--> (with UWB) or <!--/--><!--without_uwb-->"Can't find anyone —
  step into the room, facing the camera"<!--/--><!--both--> (without)<!--/--> if acquiring stalls. The
  bottom buttons follow the same wording as the web app
  ([07](07-backend-and-app.md#web-app-srcweb)).
- **Chimes** (`lib/session_audio.dart`): rising when recording starts,
  falling when it stops — **also with the app in the background**, which is
  the usual case with the phone in a bag at the foot of the wall. While the
  app is connected to a camera it keeps itself awake: a foreground service
  with a quiet "SportCam connected" notification on Android, the background
  audio mode (a looping second of silence) on iOS. Both need a line or two of
  platform setup — see [`src/app_flutter/README.md`](../../src/app_flutter/README.md).
  The chimes mix over your music rather than stopping it, and on iOS they
  play with the silent switch on.
- **Below the badge** — the recordings button, badged with the clip count.
- **Bottom** — the same state-dependent buttons, driving the same callables
  over whichever connection is active.

## Running it

```bash
cd src/app_flutter
flutter pub get
flutter run                                            # LAN only: finds the camera directly
flutter run --dart-define=SPORTCAM_FALLBACK=https://<project>.web.app \
            --dart-define=SPORTCAM_CAMERA_KEY=<CAMERA_KEY>   # and from anywhere
```

`firebase-setup.sh` prints both values. Against the emulators from
`npm run dev`, the fallback is `http://<your-computer>:5001/demo-sportcam/us-central1/api`
and the key `dev-camera-key`.

Platform setup (iOS `NSBonjourServices`, Android multicast + cleartext
permissions) is in [`src/app_flutter/README.md`](../../src/app_flutter/README.md) —
without those, discovery silently finds nothing.

## Testing without hardware or a Flutter SDK

```bash
python3 src/<build>/device/tests/test_local_api.py   # 20 checks: API, MJPEG, WS, mDNS
python3 src/<build>/device/tests/stub_device.py &    # stubbed hardware, real protocol
cd src/app_flutter
dart run tool/verify_models.dart                     # parsing checks
dart run tool/verify_against_device.dart             # cross-language contract, direct
dart run tool/verify_against_device.dart \
    http://127.0.0.1:5001/demo-sportcam/us-central1/api dev-camera-key   # …and through Firebase
```

The contract check is the interesting one: it drives the real Python camera
API — or the real Firebase function on the emulators, with `npm run dev`
running — using the app's own Dart model code, so a protocol drift between
the phone and either backend fails the check.

## Known limits

- **Multicast-blocked networks** (some corporate/guest Wi-Fi) break
  discovery; the app falls back to the remembered address, and
  `sportcam.local` still works if the platform resolves it.
- **MJPEG costs bandwidth** (~2–4 Mbps at 720p15). Fine on a LAN. The WebRTC
  path (MediaMTX on the Pi, `WHEP_URL` in `config.py`) is the upgrade for
  lower bitrate and latency; the app already receives the URL in the state
  payload.
- **No authentication on the local API.** Anyone on the same Wi-Fi can
  control the camera. Acceptable for a home LAN or phone hotspot; if you
  care at a public gym, run the camera on your own hotspot rather than the
  gym's network. Checking the camera key's header, as the Firebase API does,
  would be the natural fix.
