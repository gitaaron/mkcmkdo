/// Shared types for the SportCam app.
library;

/// Camera states — identical to the server/device state machine.
enum CamState { off, idle, tracking, recording }

CamState camStateFrom(String? s) => switch (s) {
  'idle' => CamState.idle,
  'tracking' => CamState.tracking,
  'recording' => CamState.recording,
  _ => CamState.off,
};

/// How the app is currently reaching the camera. Shown top-left.
enum LinkMode {
  /// Searching the local network via mDNS.
  searching,

  /// Connected straight to the camera on the LAN (no server, no internet).
  direct,

  /// Talking to the home server or cloud backend instead.
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
  });

  final String name;
  final String host;
  final int port;

  /// State advertised in the mDNS TXT record (available before connecting).
  final String? state;
  final bool direct;

  String get base => 'http://$host:$port';
  String get wsUrl => 'ws://$host:$port/ws';
  String get streamUrl => '$base/api/stream.mjpeg';

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
    this.acquireStalled = false,
  });

  final double? pan;
  final double? tilt;
  final double? distM;

  /// While tracking: 'acquiring' (sweeping the room / centring on someone) until
  /// the camera has locked on, then 'acquired'.
  final String? phase;

  /// Sweeping for a while and the camera still has not found anyone.
  final bool acquireStalled;

  factory Telemetry.fromJson(Map<String, dynamic>? j) => Telemetry(
    pan: (j?['pan'] as num?)?.toDouble(),
    tilt: (j?['tilt'] as num?)?.toDouble(),
    distM: (j?['dist'] as num?)?.toDouble(),
    phase: j?['phase'] as String?,
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
