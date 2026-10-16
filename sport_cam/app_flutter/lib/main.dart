import 'package:flutter/material.dart';

import 'camera_client.dart';
import 'screens/home_screen.dart';
import 'session_audio.dart';
import 'theme.dart';

/// Fallback backend used only when the camera isn't reachable on the LAN —
/// your home server, or the deployed Firebase backend. Override at build
/// time:  flutter run --dart-define=SPORTCAM_FALLBACK=https://project.web.app
const String kFallbackBase = String.fromEnvironment(
  'SPORTCAM_FALLBACK',
  defaultValue: 'http://homeserver.local:8787',
);

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
  final CameraClient _client = CameraClient(fallbackBase: kFallbackBase);
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
