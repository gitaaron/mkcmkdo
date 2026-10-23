import 'dart:async';
import 'dart:io' show Platform;

import 'package:audioplayers/audioplayers.dart';
import 'package:flutter_foreground_task/flutter_foreground_task.dart';

import 'camera_client.dart';
import 'models.dart';

/// Pings like sonar every three seconds while the camera searches, beeps for
/// each second of the found countdown (3, 2, 1), then chimes when it starts
/// recording (and again when it stops) — including with the app in the
/// background, which is the usual case: the phone is in a bag at the foot of
/// the wall while you climb.
///
/// Sounds: `assets/sounds/ping.wav`, `beep.wav`, `rec_start.wav` (rising) and
/// `rec_stop.wav` (falling), rendered by `tool/make_chimes.py` from the same
/// notes as the web app's sounds. Beeps and chimes queue rather than cut each
/// other off, so the start chime plays after the last beep; the ping has its
/// own player and never holds them up.
///
/// Staying awake in the background needs help on both platforms, and it is
/// held only while the app is connected to a camera:
///
/// * **Android** — a foreground service (`flutter_foreground_task`) with a
///   quiet notification. Without it Android freezes a backgrounded app and
///   its connection to the camera within seconds.
/// * **iOS** — the `audio` background mode, kept by looping a second of
///   digital silence. iOS suspends any other backgrounded app almost at once.
///   (This is fine for your own phone; App Store review frowns on silent
///   audio used only to stay awake.)
///
/// Platform setup — manifest permissions, the service entry, and the
/// Info.plist key — is in the app's README.
class SessionAudio {
  SessionAudio(this.client) {
    client.addListener(_onClientChanged);
  }

  final CameraClient client;

  static const _pingEvery = Duration(seconds: 3);

  final AudioPlayer _chime = AudioPlayer();
  final AudioPlayer _ping = AudioPlayer();
  final AudioPlayer _silence = AudioPlayer();

  CamState? _last; // null until the first snapshot after (re)connecting
  int _lastCountdown = 0;
  Future<void> _queue = Future.value();
  bool _wasConnected = false;
  bool _keepingAwake = false;
  Timer? _pingTimer;

  /// Call once at start-up.
  static Future<void> init() async {
    // Chimes mix over whatever else is playing and duck it briefly, rather
    // than stopping your music. iOS's `playback` category also plays with
    // the silent switch on — a chime you cannot hear is no use.
    await AudioPlayer.global.setAudioContext(
      AudioContext(
        iOS: AudioContextIOS(
          category: AVAudioSessionCategory.playback,
          options: const {
            AVAudioSessionOptions.mixWithOthers,
            AVAudioSessionOptions.duckOthers,
          },
        ),
        android: const AudioContextAndroid(
          audioFocus: AndroidAudioFocus.gainTransientMayDuck,
        ),
      ),
    );
    if (Platform.isAndroid) {
      FlutterForegroundTask.initCommunicationPort();
      FlutterForegroundTask.init(
        androidNotificationOptions: AndroidNotificationOptions(
          channelId: 'sportcam_session',
          channelName: 'SportCam connection',
          channelDescription: 'Keeps the app connected so it can chime when recording starts and stops',
          channelImportance: NotificationChannelImportance.LOW,
          priority: NotificationPriority.LOW,
        ),
        iosNotificationOptions: const IOSNotificationOptions(
          showNotification: false,
        ),
        foregroundTaskOptions: ForegroundTaskOptions(
          eventAction: ForegroundTaskEventAction.nothing(),
          allowWakeLock: true,
          allowWifiLock: true,
        ),
      );
    }
  }

  void _onClientChanged() {
    final connected = client.isConnected;
    if (connected != _wasConnected) {
      _wasConnected = connected;
      _last = null; // a reconnect's first snapshot is not a change
      _keepAwake(connected);
    }
    _pingWhile(
      connected &&
          (client.state == CamState.tracking ||
              client.state == CamState.recording) &&
          client.telemetry.phase == 'search',
    );
    if (!connected) return;

    final next = client.state;
    final countdown = client.telemetry.countdown;
    final prev = _last;
    final prevCountdown = _lastCountdown;
    _last = next;
    _lastCountdown = countdown;
    if (prev == null) return;
    // One beep per second counted down. An update can skip a second (the
    // relay polls every two seconds), so beep for each one missed.
    if (countdown > 0 && countdown != prevCountdown) {
      final steps = prevCountdown > countdown ? prevCountdown - countdown : 1;
      for (var i = 0; i < steps; i++) {
        _play('sounds/beep.wav');
      }
    }
    if (prev == next) return;
    if (next == CamState.recording) {
      _play('sounds/rec_start.wav');
    } else if (prev == CamState.recording) {
      _play('sounds/rec_stop.wav');
    }
  }

  /// Sonar ping every [_pingEvery] while the camera is in SEARCH. It has its
  /// own player, so it rings on under a beep rather than holding it up.
  void _pingWhile(bool searching) {
    if (searching && _pingTimer == null) {
      _playPing();
      _pingTimer = Timer.periodic(_pingEvery, (_) => _playPing());
    } else if (!searching && _pingTimer != null) {
      _pingTimer!.cancel();
      _pingTimer = null;
    }
  }

  Future<void> _playPing() async {
    try {
      await _ping.play(AssetSource('sounds/ping.wav'));
    } catch (_) {
      // A ping is a nicety too.
    }
  }

  /// Queue a sound to play after anything already playing.
  void _play(String asset) {
    _queue = _queue.then((_) async {
      try {
        final done = _chime.onPlayerComplete.first;
        await _chime.play(AssetSource(asset));
        await done.timeout(const Duration(seconds: 2));
      } catch (_) {
        // A chime is a nicety; never let audio take the app down.
      }
    });
  }

  Future<void> _keepAwake(bool on) async {
    if (on == _keepingAwake) return;
    _keepingAwake = on;
    try {
      if (Platform.isAndroid) {
        if (on) {
          await FlutterForegroundTask.requestNotificationPermission();
          if (!await FlutterForegroundTask.isRunningService) {
            await FlutterForegroundTask.startService(
              notificationTitle: 'SportCam connected',
              notificationText: 'Chimes when recording starts and stops',
              callback: startSessionTask,
            );
          }
        } else {
          await FlutterForegroundTask.stopService();
        }
      } else if (Platform.isIOS) {
        if (on) {
          await _silence.setReleaseMode(ReleaseMode.loop);
          await _silence.play(AssetSource('sounds/silence.wav'));
        } else {
          await _silence.stop();
        }
      }
    } catch (_) {
      // Without the keep-alive the chimes still play in the foreground.
    }
  }

  void dispose() {
    client.removeListener(_onClientChanged);
    _pingWhile(false);
    _keepAwake(false);
    _chime.dispose();
    _ping.dispose();
    _silence.dispose();
  }
}

/// Entry point of the Android foreground service. The service's only job is
/// to exist — it keeps the process, and so the camera connection in the main
/// isolate, alive. All the work stays in [SessionAudio].
@pragma('vm:entry-point')
void startSessionTask() {
  FlutterForegroundTask.setTaskHandler(_KeepAliveHandler());
}

class _KeepAliveHandler extends TaskHandler {
  @override
  Future<void> onStart(DateTime timestamp, TaskStarter starter) async {}

  @override
  void onRepeatEvent(DateTime timestamp) {}

  @override
  Future<void> onDestroy(DateTime timestamp, bool isTimeout) async {}
}
