/// Shared types for the SportCam app.
library;

/// Camera states — identical to the Firebase API's and the device's state machine.
enum CamState { off, idle, tracking, recording }

CamState camStateFrom(String? s) => switch (s) {
  'idle' => CamState.idle,
  'tracking' => CamState.tracking,
  'recording' => CamState.recording,
  _ => CamState.off,
};

/// Which hardware build the camera is — the server's TRACKING_MODE, or the
/// camera's own build when connected directly. Only the wording differs.
enum TrackingMode { withUwb, withoutUwb }

/// Missing or unknown (older backends) → with UWB, the original build.
TrackingMode trackingModeFrom(String? s) =>
    s == 'without_uwb' ? TrackingMode.withoutUwb : TrackingMode.withUwb;

/// Text that differs between the two builds; everything else is shared.
class ModeText {
  const ModeText._({
    required this.startTracking,
    required this.startRecording,
    required this.acquiring,
    required this.stalled,
  });

  /// Primary button in idle.
  final String startTracking;

  /// Primary button while tracking.
  final String startRecording;

  /// Status label while tracking but not yet locked on.
  final String acquiring;

  /// Hint when acquiring has gone on too long.
  final String stalled;

  static const withUwb = ModeText._(
    startTracking: 'Start tracking',
    startRecording: 'Start recording',
    acquiring: 'Acquiring subject',
    stalled: "Can't see you — step into view, facing the camera",
  );

  static const withoutUwb = ModeText._(
    startTracking: 'Track & record',
    startRecording: 'Record now',
    acquiring: 'Looking for a person',
    stalled: "Can't find anyone — step into the room, facing the camera",
  );

  static ModeText of(TrackingMode mode) =>
      mode == TrackingMode.withoutUwb ? withoutUwb : withUwb;
}

/// How the app is currently reaching the camera. Shown top-left.
enum LinkMode {
  /// Searching the local network via mDNS.
  searching,

  /// Connected straight to the camera on the LAN (no server, no internet).
  direct,

  /// Talking to the Firebase backend instead (from anywhere).
  relay,

  /// Nothing reachable.
  offline,
}

class CameraEndpoint {
  const CameraEndpoint({
    required this.name,
    required this.host,
    required this.port,
    this.state,
    this.direct = true,
    this.baseUrl,
  });

  final String name;
  final String host;
  final int port;

  /// State advertised in the mDNS TXT record (available before connecting).
  final String? state;
  final bool direct;

  /// Full API base for the Firebase backend (https://<project>.web.app);
  /// direct cameras are plain http on the LAN.
  final String? baseUrl;

  String get base => baseUrl ?? 'http://$host:$port';
  String get wsUrl => 'ws://$host:$port/ws';
  /// Full-rate MJPEG — only the camera itself serves it. Through Firebase the
  /// live view is the camera's low-rate preview instead.
  String? get streamUrl => direct ? '$base/api/stream.mjpeg' : null;

  @override
  bool operator ==(Object other) =>
      other is CameraEndpoint && other.host == host && other.port == port;

  @override
  int get hashCode => Object.hash(host, port);
}

class Telemetry {
  const Telemetry({
    this.pan,
    this.tilt,
    this.distM,
    this.phase,
    this.centred = 0,
    this.acquireStalled = false,
  });

  final double? pan;
  final double? tilt;
  final double? distM;

  /// While tracking: 'acquiring' until the camera has locked on, then
  /// 'acquired'. With UWB it is turning to the tag; without, sweeping the room.
  final String? phase;

  /// Consecutive centred detections toward the lock (ACQUIRE_DETECTIONS once
  /// locked, 0 when not tracking). The app beeps once per step up.
  final int centred;

  /// Acquiring for a while and the camera still cannot see / has not found anyone.
  final bool acquireStalled;

  factory Telemetry.fromJson(Map<String, dynamic>? j) => Telemetry(
    pan: (j?['pan'] as num?)?.toDouble(),
    tilt: (j?['tilt'] as num?)?.toDouble(),
    distM: (j?['dist'] as num?)?.toDouble(),
    phase: j?['phase'] as String?,
    centred: (j?['centred'] as num?)?.toInt() ?? 0,
    acquireStalled: j?['acquireStalled'] as bool? ?? false,
  );
}

class Recording {
  const Recording({
    required this.name,
    required this.bytes,
    required this.createdAt,
    required this.url,
    this.durationS,
  });

  final String name;
  final int bytes;
  final DateTime createdAt;
  final String url;
  final double? durationS;

  factory Recording.fromJson(Map<String, dynamic> j) => Recording(
    name: j['name'] as String,
    bytes: (j['bytes'] as num).toInt(),
    createdAt:
        DateTime.tryParse(j['createdAt'] as String? ?? '')?.toLocal() ??
        DateTime.now(),
    url: j['url'] as String,
    durationS: (j['durationS'] as num?)?.toDouble(),
  );

  String absoluteUrl(String base) => url.startsWith('http') ? url : '$base$url';

  String get sizeLabel => bytes >= 1000000000
      ? '${(bytes / 1e9).toStringAsFixed(1)} GB'
      : '${(bytes / 1e6).clamp(1, double.infinity).round()} MB';

  String get durationLabel {
    final d = durationS;
    if (d == null) return '';
    final m = d ~/ 60;
    final s = (d % 60).round().toString().padLeft(2, '0');
    return '$m:$s';
  }
}

class UploadProgress {
  const UploadProgress(this.name, this.sent, this.total);

  final String name;
  final int sent;
  final int total;

  double get fraction => total == 0 ? 0 : sent / total;
}
