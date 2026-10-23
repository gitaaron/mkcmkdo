# SportCam app (Flutter)

Native companion app. Finds the camera on the local network over mDNS and
connects **directly** to it for live video and control — no internet needed.
Away from the camera's network it reaches it through the Firebase backend.

See [09 — Direct connection & native app](../../docs/design/09-direct-connection-and-app.md)
for the architecture and why this is native rather than web.

## Run

```bash
flutter pub get
flutter run                                    # device/emulator on the same Wi-Fi
flutter run --dart-define=SPORTCAM_FALLBACK=https://<project>.web.app \
            --dart-define=SPORTCAM_CAMERA_KEY=<CAMERA_KEY>
```

`SPORTCAM_FALLBACK` is only used when no camera answers on the LAN; it points
at the deployed Firebase backend, and `SPORTCAM_CAMERA_KEY` names your camera
there (`scripts/firebase-setup.sh` prints both). Through Firebase the app
polls the camera's state and shows its once-a-second preview. Against the
emulators (`npm run dev`), use
`http://<your-computer>:5001/demo-sportcam/us-central1/api` and `dev-camera-key`.

## Layout

```
lib/
  main.dart                    app entry, fallback backend config
  models.dart                  CamState, LinkMode, CameraEndpoint, Recording…
  discovery.dart               mDNS sweep for _sportcam._tcp
  camera_client.dart           connection strategy + callable API + WS state
  theme.dart                   palette shared with the LED ring / web app
  session_audio.dart           search pings, countdown beeps and recording chimes, kept awake in the background
  screens/home_screen.dart     live view, badges, controls
  screens/library_screen.dart  recordings list + native player
  widgets/
    connection_badge.dart      top-left: how we're reaching the camera
    status_ring.dart           top-right: camera state (LED colours)
    mjpeg_view.dart            native MJPEG decoder with auto-reconnect
    control_bar.dart           state-dependent bottom buttons
    joystick.dart              awake: aim the camera by hand, faster the further you pull
assets/sounds/                 rec_start.wav, rec_stop.wav, silence.wav
tool/
  make_chimes.py               renders assets/sounds/ (same notes as the web chime)
  verify_models.dart           parsing checks (pure Dart — no Flutter needed)
  verify_against_device.dart   contract check against the live device API
```

## Verification without a Flutter SDK

Both `tool/` scripts run on a plain Dart SDK. From the repo root:

```bash
python3 src/<build>/device/tests/test_local_api.py   # the camera's own API: callables, MJPEG, WS, mDNS
python3 src/<build>/device/tests/stub_device.py &    # stubbed hardware, real protocol
cd src/app_flutter
dart run tool/verify_models.dart                     # parsing checks
dart run tool/verify_against_device.dart             # contract check against the camera, direct
dart run tool/verify_against_device.dart \
    http://127.0.0.1:5001/demo-sportcam/us-central1/api dev-camera-key   # …and through Firebase (npm run dev running)
```

The contract check is the one that matters: it drives the real Python camera
API, or the real Firebase function on the emulators, with the app's own Dart
model code, so a protocol drift between the phone and either backend fails
it.

## Platform setup notes

Local-network access must be declared, or discovery silently returns nothing:

- **iOS** — add to `ios/Runner/Info.plist`:
  ```xml
  <key>NSLocalNetworkUsageDescription</key>
  <string>SportCam finds your camera on this Wi-Fi network.</string>
  <key>NSBonjourServices</key>
  <array><string>_sportcam._tcp</string></array>
  ```
- **Android** — `android/app/src/main/AndroidManifest.xml` needs
  `INTERNET`, `ACCESS_NETWORK_STATE`, and (for mDNS on some devices)
  `CHANGE_WIFI_MULTICAST_STATE`. The camera serves plain HTTP on the LAN, so
  keep `android:usesCleartextTraffic="true"` on `<application>`.

**Recording chimes in the background** (`lib/session_audio.dart`) need two
more edits:

- **iOS** — allow background audio in `ios/Runner/Info.plist`. The app loops
  a second of silence while connected so iOS does not suspend it:
  ```xml
  <key>UIBackgroundModes</key>
  <array><string>audio</string></array>
  ```
  Fine for your own phone. App Store review rejects silent audio used only
  to stay awake, so a store build would need push notifications instead.
- **Android** — the app runs a foreground service with a quiet "SportCam
  connected" notification while connected. In
  `android/app/src/main/AndroidManifest.xml`, add the permissions next to the
  others and the service inside `<application>`:
  ```xml
  <uses-permission android:name="android.permission.FOREGROUND_SERVICE" />
  <uses-permission android:name="android.permission.FOREGROUND_SERVICE_DATA_SYNC" />
  <uses-permission android:name="android.permission.POST_NOTIFICATIONS" />
  <uses-permission android:name="android.permission.WAKE_LOCK" />

  <service
      android:name="com.pravera.flutter_foreground_task.service.ForegroundService"
      android:foregroundServiceType="dataSync"
      android:exported="false" />
  ```
  Android 15 caps `dataSync` services at 6 hours a day, which covers a
  session. The app asks for notification permission the first time it
  connects; refuse it and the chimes only play with the app open.

The sounds themselves are `assets/sounds/ping.wav` (every 3 s while the
camera searches), `beep.wav` (one per second
of the found countdown), `rec_start.wav` (rising) and `rec_stop.wav`
(falling), rendered by `python3 tool/make_chimes.py` from the same notes as
the web app's.

Run `flutter create --platforms=android,ios .` in this directory once to
generate the platform folders, then apply the edits above.
