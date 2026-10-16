import 'dart:async';
import 'dart:convert';

import 'package:flutter/foundation.dart';
import 'package:http/http.dart' as http;
import 'package:shared_preferences/shared_preferences.dart';
import 'package:web_socket_channel/web_socket_channel.dart';

import 'discovery.dart';
import 'models.dart';

/// Talks to whatever is serving the SportCam callable API — the camera
/// itself (direct, preferred), the home server, or the cloud backend. All
/// three speak the same protocol, so only the base URL differs.
///
/// Connection strategy on launch:
///   1. mDNS sweep for `_sportcam._tcp` → connect directly to the camera
///   2. the endpoint that worked last time (gyms sometimes block multicast)
///   3. the configured fallback server (home/cloud), marked as a relay
class CameraClient extends ChangeNotifier {
  CameraClient({this.fallbackBase});

  /// e.g. "http://homeserver.local:8787" or "https://project.web.app".
  final String? fallbackBase;

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
  bool _disposed = false;

  LinkMode get link => _link;
  CameraEndpoint? get endpoint => _endpoint;
  CamState get state => _state;
  TrackingMode get mode => _mode;
  Telemetry get telemetry => _telemetry;
  List<Recording> get recordings => _recordings;
  UploadProgress? get upload => _upload;
  Recording? get justSaved => _justSaved;
  String? get lastError => _lastError;

  bool get isConnected => _link == LinkMode.direct || _link == LinkMode.relay;
  String? get base => _endpoint?.base;
  String? get streamUrl => _endpoint?.streamUrl;

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
    if (fb != null && await _reachable(fb)) {
      final uri = Uri.parse(fb);
      await _attach(
        CameraEndpoint(
          name: 'Server',
          host: uri.host,
          port: uri.hasPort ? uri.port : (uri.scheme == 'https' ? 443 : 80),
          direct: false,
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
    _openSocket();
    unawaited(refreshRecordings());
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
      case 'state':
        _state = camStateFrom(msg['state'] as String?);
        _mode = trackingModeFrom(msg['mode'] as String?);
        _telemetry = Telemetry.fromJson(
          msg['telemetry'] as Map<String, dynamic>?,
        );
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

  Future<Map<String, dynamic>?> _call(String name, [Object? data]) async {
    final b = base;
    if (b == null) return null;
    try {
      final res = await http
          .post(
            Uri.parse('$b/api/call/$name'),
            headers: const {'Content-Type': 'application/json'},
            body: jsonEncode({'data': data}),
          )
          .timeout(const Duration(seconds: 8));
      final body = jsonDecode(res.body) as Map<String, dynamic>;
      if (res.statusCode != 200) {
        _lastError =
            (body['error'] as Map<String, dynamic>?)?['message'] as String?;
        notifyListeners();
        return null;
      }
      _lastError = null;
      return body['result'] as Map<String, dynamic>?;
    } on Exception catch (err) {
      _lastError = '$err';
      notifyListeners();
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

  Future<void> refreshRecordings() async {
    final result = await _call('getRecordings');
    final list = result?['recordings'] as List<dynamic>?;
    if (list == null) return;
    _recordings = list
        .map((e) => Recording.fromJson(e as Map<String, dynamic>))
        .toList();
    notifyListeners();
  }

  void dismissToast() {
    _justSaved = null;
    notifyListeners();
  }

  Future<void> _closeSocket() async {
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
