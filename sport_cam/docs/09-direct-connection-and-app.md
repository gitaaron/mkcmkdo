# 09 — Direct phone ↔ camera connection & the native app

Open the app on the same Wi-Fi as the camera and it finds it, streams live
video, and controls it — with no home server, no cloud, and no internet in
the path.

## Why the camera serves its own API

Previously every byte went phone → home server → camera. At the gym that
path doesn't exist. So the head unit now runs its own copy of the API
(`<build>/device/sportcam/local_api.py`) — the **third implementation of the same
callable protocol**, identical to the home server's and Firebase's:

| | Home server | Firebase | **Camera (direct)** |
| --- | --- | --- | --- |
| `POST /api/call/*` | ✅ | library only | ✅ |
| `GET /api/stream.mjpeg` | relayed | ❌ | ✅ **source** |
| `GET /api/recordings/:name` | ✅ | signed URL | ✅ (clips not yet uploaded) |
| `WS /ws` | ✅ | ❌ | ✅ |
| Works at the gym | ❌ | needs internet | ✅ **needs nothing** |

Because the protocol is the same, the app's code path is the same; only the
base URL changes. State still lives in one place on the device
(`Head.apply_state`), so a command from the phone, the home server, or the
camera itself (the tag being switched on or off with UWB; the first lock-on
without) all take the same route and everyone is told the result —
app, LED ring, and server stay in lock-step.

The camera's state includes `mode` (`with_uwb` or `without_uwb`, from its
`config.TRACKING_MODE`), so a phone connected directly words its buttons for
that build with no server involved — see
[06 — Tracking mode](06-server-and-app.md#tracking-mode).

Latency improves too: direct MJPEG on a LAN is ~80–120 ms versus ~250 ms
through the relay, because the frames stop making a round trip.

## Discovery: mDNS / Bonjour

The camera publishes `_sportcam._tcp.local` (`<build>/device/sportcam/discovery.py`)
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
3. **fallback backend** — home server or Firebase (`LinkMode.relay`)
4. otherwise `LinkMode.offline`, retrying every 3 s

## Why the app is native (Flutter)

The web app was fine while everything went through a server. For direct
connection it hits two hard walls that are not matters of taste:

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

**The Vue web app stays** — it's still the right interface on a laptop on the
home LAN, and it's what Firebase Hosting serves. Both clients speak the same
protocol.

## The app's screen

![App UI (with UWB wording; the camera-only build shows "Track & record")](../with_uwb/docs/images/app-ui.png)

Same layout as the web app, plus the connection badge:

- **Top-left — connection status** (`ConnectionBadge`): a coloured dot and
  label showing how the app is reaching the camera. Green **"SportCam ·
  Direct · 10.0.0.42"**, blue **"Server"** when relayed, amber pulsing
  **"Searching…"** during discovery, red **"Offline — tap to retry"**. Tap it
  any time to re-scan.
- **Top-right — camera state** (`StatusRing`): the LED-ring colours (blue
  idle, green tracking — blinking fast and labelled "Acquiring subject…"
  (with UWB) or "Looking for a person…" (without) until the camera locks on —
  pulsing red recording); hollow while disconnected. A pill says "Can't see
  you — step into view, facing the camera" (with UWB) or "Can't find anyone —
  step into the room, facing the camera" (without) if acquiring stalls. The
  bottom buttons follow the same wording as the web app
  ([06](06-server-and-app.md#web-app-web)).
- **Chimes** (`lib/session_audio.dart`): rising when recording starts,
  falling when it stops — **also with the app in the background**, which is
  the usual case with the phone in a bag at the foot of the wall. While the
  app is connected to a camera it keeps itself awake: a foreground service
  with a quiet "SportCam connected" notification on Android, the background
  audio mode (a looping second of silence) on iOS. Both need a line or two of
  platform setup — see [`app_flutter/README.md`](../app_flutter/README.md).
  The chimes mix over your music rather than stopping it, and on iOS they
  play with the silent switch on.
- **Below the badge** — the recordings button, badged with the clip count.
- **Bottom** — the same state-dependent buttons, driving the same callables
  over whichever connection is active.

## Running it

```bash
cd app_flutter
flutter pub get
flutter run
```

Platform setup (iOS `NSBonjourServices`, Android multicast + cleartext
permissions) is in [`app_flutter/README.md`](../app_flutter/README.md) —
without those, discovery silently finds nothing.

## Testing without hardware or a Flutter SDK

```bash
python3 device/tests/test_local_api.py        # 20 checks: API, MJPEG, WS, mDNS
python3 device/tests/stub_device.py &         # stubbed hardware, real protocol
dart run app_flutter/tool/verify_models.dart           # 15 parsing checks
dart run app_flutter/tool/verify_against_device.dart   # cross-language contract
```

The last one is the interesting one: it drives the real Python camera API
using the app's own Dart model code, so a protocol drift between the phone
and the camera fails the check.

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
  gym's network. A shared-secret header would be the natural fix.
