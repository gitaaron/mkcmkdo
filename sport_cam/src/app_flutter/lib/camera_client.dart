import 'dart:async';
import 'dart:convert';

import 'package:flutter/foundation.dart';
import 'package:http/http.dart' as http;
import 'package:shared_preferences/shared_preferences.dart';
import 'package:web_socket_channel/web_socket_channel.dart';

import 'discovery.dart';
import 'models.dart';

/// Talks to whatever is serving the SportCam callable API — the camera
/// itself (direct, preferred) or the Firebase backend. Both speak the same
/// protocol, so the calls are the same; only how state arrives differs:
///
///   direct   the camera's WebSocket pushes state, recordings and the live
///            person boxes, and its MJPEG stream is the live view
///   relay    Firebase: poll `getState` and `getRecordings`, and show the
///            preview frames (with their person boxes) the camera posts
///            while someone is watching (`watch` / `getPreview`). Every call
///            carries the camera key.
///
/// Connection strategy on launch:
///   1. mDNS sweep for `_sportcam._tcp` → connect directly to the camera
///   2. the endpoint that worked last time (gyms sometimes block multicast)
///   3. the Firebase backend, marked as a relay
class CameraClient extends ChangeNotifier {
  CameraClient({this.fallbackBase, this.cameraKey = ''});

  /// The Firebase backend, e.g. "https://project.web.app".
  final String? fallbackBase;

  /// Names this camera on the Firebase backend (CAMERA_KEY in config.py).
  final String cameraKey;

  static const _prefsHostKey = 'last_camera_host';
  static const _prefsPortKey = 'last_camera_port';

  LinkMode _link = LinkMode.searching;
  CameraEndpoint? _endpoint;
  CamState _state = CamState.off;
  TrackingMode _mode = TrackingMode.withUwb;
  Telemetry _telemetry = const Telemetry();
  List<Recording> _recordings = const [];
  UploadProgress? _upload;
  Recording? _justSaved;
  String? _lastError;

  WebSocketChannel? _ws;
  StreamSubscription<dynamic>? _wsSub;
  Timer? _retry;
  Timer? _poll;
  int _pollTick = 0;
  int _pollFailures = 0;
  Uint8List? _preview;
  LiveBoxes? _liveBoxes;
  Timer? _liveBoxesExpiry;
  bool _disposed = false;
  bool _foreground = true;

  LinkMode get link => _link;
  CameraEndpoint? get endpoint => _endpoint;
  CamState get state => _state;
  TrackingMode get mode => _mode;
  Telemetry get telemetry => _telemetry;
  List<Recording> get recordings => _recordings;
  UploadProgress? get upload => _upload;
  Recording? get justSaved => _justSaved;
  String? get lastError => _lastError;

  /// The app is on screen. In the background it stops asking for the live
  /// view (no `watch`, no previews, no stream), so the camera can go to
  /// sleep; state polling carries on for the record chimes.
  bool get foreground => _foreground;
  set foreground(bool on) {
    if (on == _foreground) return;
    _foreground = on;
    if (!on) {
      _preview = null;
      _setLiveBoxes(null);
    } else if (_link == LinkMode.relay) {
      // previews resume without waiting for the next ping
      unawaited(_call('watch'));
    }
    if (!_disposed) notifyListeners();
  }

  bool get isConnected => _link == LinkMode.direct || _link == LinkMode.relay;
  String? get base => _endpoint?.base;
  String? get streamUrl => _endpoint?.streamUrl;

  /// Latest preview frame when connected through Firebase (null when direct).
  Uint8List? get preview => _preview;

  /// The person boxes of the camera's last detection, for the live view;
  /// null when none have arrived in [LiveBoxes.hold].
  LiveBoxes? get liveBoxes => _liveBoxes;

  void _setLiveBoxes(LiveBoxes? boxes) {
    _liveBoxes = boxes;
    _liveBoxesExpiry?.cancel();
    if (boxes != null) {
      _liveBoxesExpiry = Timer(LiveBoxes.hold, () {
        _liveBoxes = null;
        if (!_disposed) notifyListeners();
      });
    }
  }

  // ---- connection ---------------------------------------------------------

  /// Discover and connect. Safe to call again to re-scan.
  Future<void> connect() async {
    _setLink(LinkMode.searching);

    final cameras = await CameraDiscovery.discover();
    if (cameras.isNotEmpty) {
      await _attach(cameras.first, LinkMode.direct);
      return;
    }

    final remembered = await _rememberedEndpoint();
    if (remembered != null && await _reachable(remembered.base)) {
      await _attach(remembered, LinkMode.direct);
      return;
    }

    final fb = fallbackBase;
    if (fb != null && cameraKey.isNotEmpty && await _reachable(fb)) {
      final uri = Uri.parse(fb);
      await _attach(
        CameraEndpoint(
          name: 'Firebase',
          host: uri.host,
          port: uri.hasPort ? uri.port : (uri.scheme == 'https' ? 443 : 80),
          direct: false,
          baseUrl: fb,
        ),
        LinkMode.relay,
      );
      return;
    }

    _setLink(LinkMode.offline);
    _scheduleRetry();
  }

  /// Connect to a camera the user picked from the discovery list.
  Future<void> connectTo(CameraEndpoint endpoint) =>
      _attach(endpoint, endpoint.direct ? LinkMode.direct : LinkMode.relay);

  Future<void> _attach(CameraEndpoint endpoint, LinkMode mode) async {
    _retry?.cancel();
    await _closeSocket();
    _endpoint = endpoint;
    _setLink(mode);
    if (endpoint.direct) {
      final prefs = await SharedPreferences.getInstance();
      await prefs.setString(_prefsHostKey, endpoint.host);
      await prefs.setInt(_prefsPortKey, endpoint.port);
    }
    if (endpoint.direct) {
      _openSocket();
    } else {
      _startPolling();
    }
    unawaited(refreshRecordings());
  }

  // ---- relay (Firebase): poll ----------------------------------------------

  void _startPolling() {
    _pollTick = 0;
    _pollFailures = 0;
    _poll = Timer.periodic(const Duration(seconds: 1), (_) => _pollOnce());
    unawaited(_pollOnce());
  }

  Future<void> _pollOnce() async {
    final tick = _pollTick++;
    // Keep the camera posting previews, and awake (it stops a minute after
    // the last watch). Not from the background: let it sleep.
    if (_foreground && tick % 30 == 0) unawaited(_call('watch'));
    if (tick % 10 == 9) unawaited(refreshRecordings(announce: true));
    if (_foreground && _state.isLive) {
      final p = await _call('getPreview', null, true);
      final jpeg = p?['jpeg'] as String?;
      if (jpeg != null) {
        _preview = base64Decode(jpeg);
        _setLiveBoxes(LiveBoxes.fromJson(p?['size'], p?['boxes']));
        notifyListeners();
      }
    }
    if (tick.isEven) {
      final s = await _call('getState', null, true);
      if (s == null) {
        if (++_pollFailures >= 5) _onDisconnected();
        return;
      }
      _pollFailures = 0;
      _applyState(s);
      final up = s['upload'] as Map<String, dynamic>?;
      _upload = up == null
          ? null
          : UploadProgress(
              up['name'] as String? ?? '',
              (up['sent'] as num?)?.toInt() ?? 0,
              (up['total'] as num?)?.toInt() ?? 0,
            );
      notifyListeners();
    }
  }

  void _applyState(Map<String, dynamic> msg) {
    _state = camStateFrom(msg['state'] as String?);
    _mode = trackingModeFrom(msg['mode'] as String?);
    _telemetry = Telemetry.fromJson(msg['telemetry'] as Map<String, dynamic>?);
  }

  void _openSocket() {
    final endpoint = _endpoint;
    if (endpoint == null) return;
    try {
      final ws = WebSocketChannel.connect(Uri.parse(endpoint.wsUrl));
      _ws = ws;
      _wsSub = ws.stream.listen(
        _onMessage,
        onError: (Object _) => _onDisconnected(),
        onDone: _onDisconnected,
        cancelOnError: true,
      );
    } on Exception {
      _onDisconnected();
    }
  }

  void _onMessage(dynamic raw) {
    if (raw is! String) return;
    final Map<String, dynamic> msg;
    try {
      msg = jsonDecode(raw) as Map<String, dynamic>;
    } on FormatException {
      return;
    }
    switch (msg['type']) {
      case 'boxes':
        _setLiveBoxes(LiveBoxes.fromJson(msg['size'], msg['boxes']));
        notifyListeners();
      case 'state':
        _applyState(msg);
        notifyListeners();
      case 'recordings':
        final previousNewest = _recordings.isEmpty
            ? null
            : _recordings.first.name;
        _recordings = ((msg['recordings'] as List<dynamic>?) ?? const [])
            .map((e) => Recording.fromJson(e as Map<String, dynamic>))
            .toList();
        if (previousNewest != null &&
            _recordings.isNotEmpty &&
            _recordings.first.name != previousNewest) {
          _justSaved = _recordings.first;
        }
        _upload = null;
        notifyListeners();
      case 'uploadProgress':
        _upload = UploadProgress(
          msg['name'] as String? ?? '',
          (msg['sent'] as num?)?.toInt() ?? 0,
          (msg['total'] as num?)?.toInt() ?? 0,
        );
        notifyListeners();
    }
  }

  void _onDisconnected() {
    if (_disposed) return;
    _setLink(LinkMode.offline);
    _scheduleRetry();
  }

  void _scheduleRetry() {
    _retry?.cancel();
    _retry = Timer(const Duration(seconds: 3), () {
      if (!_disposed) unawaited(connect());
    });
  }

  Future<CameraEndpoint?> _rememberedEndpoint() async {
    final prefs = await SharedPreferences.getInstance();
    final host = prefs.getString(_prefsHostKey);
    final port = prefs.getInt(_prefsPortKey);
    if (host == null || port == null) return null;
    return CameraEndpoint(name: 'SportCam', host: host, port: port);
  }

  Future<bool> _reachable(String base) async {
    try {
      final res = await http
          .get(Uri.parse('$base/api/health'))
          .timeout(const Duration(seconds: 2));
      return res.statusCode == 200;
    } on Exception {
      return false;
    }
  }

  void _setLink(LinkMode mode) {
    if (_link == mode) return;
    _link = mode;
    notifyListeners();
  }

  // ---- callable API -------------------------------------------------------

  /// `quiet` calls (the relay's polling) don't surface errors in the UI.
  Future<Map<String, dynamic>?> _call(
    String name, [
    Object? data,
    bool quiet = false,
  ]) async {
    final b = base;
    if (b == null) return null;
    try {
      final res = await http
          .post(
            Uri.parse('$b/api/call/$name'),
            headers: {
              'Content-Type': 'application/json',
              if (cameraKey.isNotEmpty) 'X-Camera-Key': cameraKey,
            },
            body: jsonEncode({'data': data}),
          )
          .timeout(const Duration(seconds: 8));
      final body = jsonDecode(res.body) as Map<String, dynamic>;
      if (res.statusCode != 200) {
        if (!quiet) {
          _lastError =
              (body['error'] as Map<String, dynamic>?)?['message'] as String?;
          notifyListeners();
        }
        return null;
      }
      if (!quiet) _lastError = null;
      return body['result'] as Map<String, dynamic>?;
    } on Exception catch (err) {
      if (!quiet) {
        _lastError = '$err';
        notifyListeners();
      }
      return null;
    }
  }

  // The UI never assumes success — it waits for the state broadcast, so the
  // app, the LED ring, and any second phone stay in lock-step.
  Future<void> startTracking() => _call('startTracking').then((_) {});
  Future<void> stopTracking() => _call('stopTracking').then((_) {});
  Future<void> startRecording() => _call('startRecording').then((_) {});
  Future<void> stopRecording() => _call('stopRecording').then((_) {});
  Future<void> setPower(bool on) => _call('setPower', {'on': on}).then((_) {});

  /// The joystick works in awake, over the direct connection: tracking and
  /// recording own the head, asleep there is no picture to aim by, and
  /// through Firebase the second of lag would make it overshoot.
  bool get canAim => _link == LinkMode.direct && _state == CamState.awake;

  /// Turn the camera at a speed set by the joystick's pull ([Joystick]):
  /// pan right +, tilt up +, each −1…1. Sent on the WebSocket, ≈ 20 a second
  /// while it is held; the camera stops when they stop.
  void aim(double pan, double tilt) {
    final ws = _ws;
    if (ws == null || _link != LinkMode.direct) return;
    double r(double v) => (v.clamp(-1.0, 1.0) * 1000).roundToDouble() / 1000;
    ws.sink.add(jsonEncode({'type': 'jog', 'pan': r(pan), 'tilt': r(tilt)}));
  }

  /// `announce`: a new newest recording shows the "saved" toast (the relay's
  /// polling; direct connections get that from the WebSocket).
  Future<void> refreshRecordings({bool announce = false}) async {
    final result = await _call('getRecordings', null, announce);
    final list = result?['recordings'] as List<dynamic>?;
    if (list == null) return;
    final previousNewest = _recordings.isEmpty ? null : _recordings.first.name;
    _recordings = list
        .map((e) => Recording.fromJson(e as Map<String, dynamic>))
        .toList();
    if (announce &&
        previousNewest != null &&
        _recordings.isNotEmpty &&
        _recordings.first.name != previousNewest) {
      _justSaved = _recordings.first;
    }
    notifyListeners();
  }

  void dismissToast() {
    _justSaved = null;
    notifyListeners();
  }

  Future<void> _closeSocket() async {
    _poll?.cancel();
    _poll = null;
    _preview = null;
    _setLiveBoxes(null);
    await _wsSub?.cancel();
    _wsSub = null;
    await _ws?.sink.close();
    _ws = null;
  }

  @override
  void dispose() {
    _disposed = true;
    _retry?.cancel();
    unawaited(_closeSocket());
    super.dispose();
  }
}
