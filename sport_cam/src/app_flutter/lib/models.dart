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
    required this.searching,
    required this.stalled,
  });

  /// Primary button in idle.
  final String startTracking;

  /// Status label while tracking, in search.
  final String searching;

  /// Hint when tracking has gone on too long without recording.
  final String stalled;

  static const withUwb = ModeText._(
    startTracking: 'Start tracking',
    searching: 'Turning to your tag',
    stalled: "Can't pick you out — step into view, away from anyone else",
  );

  static const withoutUwb = ModeText._(
    startTracking: 'Track & record',
    searching: 'Looking for a person',
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
    this.countdown = 0,
    this.acquireStalled = false,
  });

  final double? pan;
  final double? tilt;
  final double? distM;

  /// idle: 'person-in-frame' or 'no-person-in-frame'. Tracking: 'search'
  /// (with UWB turning to the tag, without sweeping the room — the app pings
  /// every three seconds), then 'found'. Recording: 'track' ('search' again,
  /// without UWB, while it looks for a person it has lost).
  final String? phase;

  /// Found: whole seconds left before recording starts (3, 2, 1); else 0.
  /// The app beeps on each.
  final int countdown;

  /// Acquiring for a while and the camera still cannot see / has not found anyone.
  final bool acquireStalled;

  factory Telemetry.fromJson(Map<String, dynamic>? j) => Telemetry(
    pan: (j?['pan'] as num?)?.toDouble(),
    tilt: (j?['tilt'] as num?)?.toDouble(),
    distM: (j?['dist'] as num?)?.toDouble(),
    phase: j?['phase'] as String?,
    countdown: (j?['countdown'] as num?)?.toInt() ?? 0,
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
    this.boxesUrl,
  });

  final String name;
  final int bytes;
  final DateTime createdAt;
  final String url;
  final double? durationS;

  /// The person boxes to draw over the video ([BoxTrack]); null if the
  /// camera sent none.
  final String? boxesUrl;

  factory Recording.fromJson(Map<String, dynamic> j) => Recording(
    name: j['name'] as String,
    bytes: (j['bytes'] as num).toInt(),
    createdAt:
        DateTime.tryParse(j['createdAt'] as String? ?? '')?.toLocal() ??
        DateTime.now(),
    url: j['url'] as String,
    durationS: (j['durationS'] as num?)?.toDouble(),
    boxesUrl: j['boxesUrl'] as String?,
  );

  String absoluteUrl(String base) => _absolute(url, base);

  String? absoluteBoxesUrl(String base) =>
      boxesUrl == null ? null : _absolute(boxesUrl!, base);

  static String _absolute(String u, String base) =>
      u.startsWith('http') ? u : '$base$u';

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

/// Who a person box is, for its colour: the climber (green), anyone else
/// (yellow), or not yet known (red).
enum BoxLabel { climber, other, unsure }

BoxLabel boxLabelFrom(Object? s) => switch (s) {
  'climber' => BoxLabel.climber,
  'other' => BoxLabel.other,
  _ => BoxLabel.unsure,
};

class PersonBox {
  const PersonBox(this.x, this.y, this.w, this.h, this.label);

  final double x, y, w, h;
  final BoxLabel label;

  /// One `[x, y, w, h, label]` box as the camera sends it; null if malformed.
  static PersonBox? fromJson(Object? b) {
    if (b is! List || b.length != 5) return null;
    final n = b.take(4).whereType<num>().toList();
    if (n.length != 4) return null;
    return PersonBox(
      n[0].toDouble(),
      n[1].toDouble(),
      n[2].toDouble(),
      n[3].toDouble(),
      boxLabelFrom(b[4]),
    );
  }

  static List<PersonBox> listFromJson(Object? list) => list is List
      ? list.map(PersonBox.fromJson).whereType<PersonBox>().toList()
      : const [];
}

/// The person boxes the camera saves beside a clip (`<clip>.boxes.json`,
/// written by the device's boxlog.py): one frame per detection, a few a
/// second, each the seconds from the clip's start and the boxes in pixels of
/// a [width] × [height] frame with the same field of view as the video.
class BoxTrack {
  const BoxTrack(this.width, this.height, this.times, this.frames);

  /// A frame's boxes are shown until the next detection, or this long at most.
  static const holdS = 1.0;

  final double width, height;
  final List<double> times;
  final List<List<PersonBox>> frames;

  static BoxTrack? fromJson(Object? json) {
    if (json is! Map || json['v'] != 1) return null;
    final size = json['size'];
    final raw = json['frames'];
    if (size is! List || size.length != 2 || raw is! List) return null;
    final times = <double>[];
    final frames = <List<PersonBox>>[];
    for (final f in raw) {
      if (f is! List || f.length != 2 || f[1] is! List) continue;
      times.add((f[0] as num).toDouble());
      frames.add(PersonBox.listFromJson(f[1]));
    }
    return BoxTrack(
      (size[0] as num).toDouble(),
      (size[1] as num).toDouble(),
      times,
      frames,
    );
  }

  /// The boxes on screen at [t] seconds: the last detection at or before it.
  List<PersonBox> at(double t) {
    if (times.isEmpty || times.first > t) return const [];
    var lo = 0, hi = times.length - 1;
    while (lo < hi) {
      final mid = (lo + hi + 1) >> 1;
      if (times[mid] <= t) {
        lo = mid;
      } else {
        hi = mid - 1;
      }
    }
    return t - times[lo] <= holdS ? frames[lo] : const [];
  }
}

/// The live view's person boxes: the camera's last detection, in pixels of a
/// [width] × [height] frame with the same field of view as the live picture.
/// Direct, a `boxes` message on the WebSocket at each detection; through
/// Firebase, with each preview frame from `getPreview`.
class LiveBoxes {
  const LiveBoxes(this.width, this.height, this.boxes);

  /// Dropped this long after arriving unless replaced. The camera sends a
  /// fresh list at least every 2 s, so this only bites when it goes quiet.
  static const hold = Duration(seconds: 3);

  final double width, height;
  final List<PersonBox> boxes;

  /// `size` is `[width, height]`; `boxes` a list of `[x, y, w, h, label]`.
  static LiveBoxes? fromJson(Object? size, Object? boxes) {
    if (size is! List || size.length != 2 || boxes is! List) return null;
    final w = size[0], h = size[1];
    if (w is! num || h is! num || w <= 0 || h <= 0) return null;
    return LiveBoxes(w.toDouble(), h.toDouble(), PersonBox.listFromJson(boxes));
  }
}

class UploadProgress {
  const UploadProgress(this.name, this.sent, this.total);

  final String name;
  final int sent;
  final int total;

  double get fraction => total == 0 ? 0 : sent / total;
}
