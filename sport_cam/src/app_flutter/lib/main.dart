import 'package:flutter/material.dart';

import 'auth.dart';
import 'camera_client.dart';
import 'keys.dart';
import 'screens/home_screen.dart';
import 'screens/login_screen.dart';
import 'session_audio.dart';
import 'theme.dart';

/// The deployed Firebase backend, used when the camera isn't reachable on the
/// LAN, and the camera key that names your camera there. Set at build time:
///   flutter run --dart-define=SPORTCAM_FALLBACK=https://<project>.web.app \
///               --dart-define=SPORTCAM_CAMERA_KEY=<CAMERA_KEY from config.py> \
///               --dart-define=SPORTCAM_FIREBASE_API_KEY=<the project's Web API key>
/// For the emulators (npm run dev), the fallback is
///   http://<your-computer>:5001/demo-sportcam/us-central1/api
/// the key is dev-camera-key, and SPORTCAM_AUTH_EMULATOR is
/// <your-computer>:9099 in place of the API key. Leave the fallback empty for
/// LAN-only: then nobody signs in, and each phone sees only the clips of the
/// sessions it started.
const String kFallbackBase = String.fromEnvironment('SPORTCAM_FALLBACK');
const String kCameraKey = String.fromEnvironment('SPORTCAM_CAMERA_KEY');
const String kFirebaseApiKey = String.fromEnvironment('SPORTCAM_FIREBASE_API_KEY');
const String kAuthEmulator = String.fromEnvironment('SPORTCAM_AUTH_EMULATOR');

Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();
  await SessionAudio.init();
  final auth = AuthClient(
    apiKey: kFirebaseApiKey,
    emulatorHost: kAuthEmulator,
    enabled: kFallbackBase.isNotEmpty,
  );
  await auth.restore();
  final keys = await SessionKeys.load();
  runApp(SportCamApp(auth: auth, keys: keys));
}

class SportCamApp extends StatefulWidget {
  const SportCamApp({super.key, required this.auth, required this.keys});

  final AuthClient auth;
  final SessionKeys keys;

  @override
  State<SportCamApp> createState() => _SportCamAppState();
}

class _SportCamAppState extends State<SportCamApp>
    with WidgetsBindingObserver {
  late final CameraClient _client = CameraClient(
    fallbackBase: kFallbackBase.isEmpty ? null : kFallbackBase,
    cameraKey: kCameraKey,
    auth: widget.auth,
    keys: widget.keys,
  );
  late final SessionAudio _audio = SessionAudio(_client);

  @override
  void initState() {
    super.initState();
    _audio; // start listening for recording start/stop straight away
    WidgetsBinding.instance.addObserver(this);
  }

  /// Watching the live view keeps the camera awake, so stop watching while
  /// the app is in the background ("inactive" is still on screen).
  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    _client.foreground = state == AppLifecycleState.resumed ||
        state == AppLifecycleState.inactive;
  }

  @override
  void dispose() {
    WidgetsBinding.instance.removeObserver(this);
    _audio.dispose();
    _client.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'SportCam',
      debugShowCheckedModeBanner: false,
      theme: buildTheme(),
      // With a backend, the app is for signed-in people only.
      home: ListenableBuilder(
        listenable: widget.auth,
        builder: (context, _) => widget.auth.enabled && !widget.auth.signedIn
            ? LoginScreen(auth: widget.auth)
            : HomeScreen(client: _client),
      ),
    );
  }
}
