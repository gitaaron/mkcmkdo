import 'package:flutter/material.dart';

import 'camera_client.dart';
import 'screens/home_screen.dart';
import 'session_audio.dart';
import 'theme.dart';

/// The deployed Firebase backend, used when the camera isn't reachable on the
/// LAN, and the camera key that names your camera there. Set at build time:
///   flutter run --dart-define=SPORTCAM_FALLBACK=https://<project>.web.app \
///               --dart-define=SPORTCAM_CAMERA_KEY=<CAMERA_KEY from config.py>
/// For the emulators (npm run dev), the fallback is
///   http://<your-computer>:5001/demo-sportcam/us-central1/api
/// and the key is dev-camera-key. Leave the fallback empty for LAN-only.
const String kFallbackBase = String.fromEnvironment('SPORTCAM_FALLBACK');
const String kCameraKey = String.fromEnvironment('SPORTCAM_CAMERA_KEY');

Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();
  await SessionAudio.init();
  runApp(const SportCamApp());
}

class SportCamApp extends StatefulWidget {
  const SportCamApp({super.key});

  @override
  State<SportCamApp> createState() => _SportCamAppState();
}

class _SportCamAppState extends State<SportCamApp> {
  final CameraClient _client = CameraClient(
    fallbackBase: kFallbackBase.isEmpty ? null : kFallbackBase,
    cameraKey: kCameraKey,
  );
  late final SessionAudio _audio = SessionAudio(_client);

  @override
  void initState() {
    super.initState();
    _audio; // start listening for recording start/stop straight away
  }

  @override
  void dispose() {
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
      home: HomeScreen(client: _client),
    );
  }
}
