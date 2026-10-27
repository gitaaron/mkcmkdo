import 'dart:async';
import 'dart:convert';

import 'package:flutter/foundation.dart';
import 'package:http/http.dart' as http;
import 'package:shared_preferences/shared_preferences.dart';
import 'package:web_socket_channel/web_socket_channel.dart';

import 'auth.dart';
import 'discovery.dart';
import 'keys.dart';
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
///
/// Whose is what (camera owners.py, backend sessions.ts): starting a session
/// hands this phone its secret, kept in [SessionKeys]; every stop sends the
/// secrets back, so only the person who tapped Record can stop it. The
/// library is the signed-in person's own clips — from the backend, plus,
/// connected directly, the ones still on the camera's card — and secrets
/// are claimed with the backend whenever it can be reached.
class CameraClient extends ChangeNotifier {
  CameraClient({
    this.fallbackBase,
    this.cameraKey = '',
    required this.auth,
    required this.keys,
  }) {
    auth.addListener(_onAuthChanged);
    keys.uid = auth.user?.uid ?? '';
    _claimTimer = Timer.periodic(const Duration(minutes: 1), (_) => claim());
  }

  /// The Firebase backend, e.g. "https://project.web.app".
  final String? fallbackBase;

  /// Names this camera on the Firebase backend (CAMERA_KEY in config.py).
  final String cameraKey;

  /// Who is signed in; their ID token goes with every backend call.
  final AuthClient auth;

  /// The session and pairing secrets this phone holds.
  final SessionKeys keys;

  Timer? _claimTimer;
  String? _sessionHash;

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
  CamWarning? _warning;
  Timer? _warningExpiry;
  // Relay: the `at` of the warning last seen in getState. The first poll
  // only sets it, so connecting doesn't replay an old warning.
  String? _relayWarningAt;
  bool _relayWarningSeen = false;

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
  // Bumped by every connect / attach. Async work started under an older
  // value (a slow discovery, a poll still waiting on the last endpoint)
  // checks it after each await and drops its result: otherwise a retry and
  // a tap racing each other open two sockets, and a late reply from the old
  // endpoint overwrites the new one's state.
  int _gen = 0;
  int? _pollingGen; // the connection a poll is in flight for

  LinkMode get link => _link;
  CameraEndpoint? get endpoint => _endpoint;
  CamState get state => _state;
  TrackingMode get mode => _mode;
  Telemetry get telemetry => _telemetry;
  List<Recording> get recordings => _recordings;
  UploadProgress? get upload => _upload;
  Recording? get justSaved => _justSaved;
  String? get lastError => _lastError;

  /// A session is running and this phone started it (or paired the tag that
  /// did): it may stop it.
  bool get ownsSession =>
      _sessionHash != null && keys.hashes.contains(_sessionHash);

  /// A session someone else started is running: its stop buttons are theirs.
  bool get othersSession =>
      (_state == CamState.tracking || _state == CamState.recording) &&
      _sessionHash != null &&
      !ownsSession;

  /// The backend can be reached for the library and claims (signed in, and
  /// a backend configured), whichever way the camera is connected.
  bool get hasCloud =>
      fallbackBase != null && auth.enabled && auth.signedIn;

  void _onAuthChanged() {
    final uid = auth.user?.uid ?? '';
    if (uid == keys.uid) return;
    keys.uid = uid;
    // someone else's library is not this person's
    _recordings = const [];
    _justSaved = null;
    if (!_disposed) notifyListeners();
    if (uid.isNotEmpty) unawaited(claim());
  }

  /// The camera's latest warning, for [CamWarning.hold]; null otherwise.
  CamWarning? get warning => _warning;

  void _raiseWarning(Object? code) {
    final w = CamWarning.of(code);
    if (w == null) return;
    _warning = w;
    _warningExpiry?.cancel();
    _warningExpiry = Timer(CamWarning.hold, dismissWarning);
    if (!_disposed) notifyListeners();
  }

  void dismissWarning() {
    _warningExpiry?.cancel();
    if (_warning == null) return;
    _warning = null;
    if (!_disposed) notifyListeners();
  }

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
    final gen = ++_gen;
    _setLink(LinkMode.searching);

    final cameras = await CameraDiscovery.discover();
    if (gen != _gen) return;
    if (cameras.isNotEmpty) {
      await _attach(cameras.first, LinkMode.direct, gen);
      return;
    }

    final remembered = await _rememberedEndpoint();
    if (remembered != null && await _reachable(remembered.base)) {
      if (gen != _gen) return;
      await _attach(remembered, LinkMode.direct, gen);
      return;
    }

    final fb = fallbackBase;
    // through the backend only signed in: it answers nobody else
    if (fb != null &&
        cameraKey.isNotEmpty &&
        (!auth.enabled || auth.signedIn) &&
        await _reachable(fb)) {
      if (gen != _gen) return;
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
        gen,
      );
      return;
    }

    if (gen != _gen) return;
    _setLink(LinkMode.offline);
    _scheduleRetry();
  }

  /// Connect to a camera the user picked from the discovery list.
  Future<void> connectTo(CameraEndpoint endpoint) => _attach(
    endpoint,
    endpoint.direct ? LinkMode.direct : LinkMode.relay,
    ++_gen,
  );

  Future<void> _attach(CameraEndpoint endpoint, LinkMode mode, int gen) async {
    _retry?.cancel();
    await _closeSocket();
    if (gen != _gen || _disposed) return;
    _endpoint = endpoint;
    _relayWarningAt = null;
    _relayWarningSeen = false;
    _setLink(mode);
    if (endpoint.direct) {
      final prefs = await SharedPreferences.getInstance();
      await prefs.setString(_prefsHostKey, endpoint.host);
      await prefs.setInt(_prefsPortKey, endpoint.port);
      if (gen != _gen || _disposed) return;
    }
    if (endpoint.direct) {
      _openSocket();
    } else {
      _startPolling();
    }
    unawaited(refreshRecordings());
    unawaited(claim());
  }

  // ---- relay (Firebase): poll ----------------------------------------------

  void _startPolling() {
    _pollTick = 0;
    _pollFailures = 0;
    _poll = Timer.periodic(const Duration(seconds: 1), (_) => _pollOnce());
    unawaited(_pollOnce());
  }

  /// One poll. Skipped while the last is still waiting (a slow link takes
  /// longer than the 1 s tick), so replies can't arrive out of order.
  Future<void> _pollOnce() async {
    if (_pollingGen == _gen) return;
    final gen = _pollingGen = _gen;
    try {
      await _pollStep(gen);
    } finally {
      if (_pollingGen == gen) _pollingGen = null;
    }
  }

  Future<void> _pollStep(int gen) async {
    final tick = _pollTick++;
    // Keep the camera posting previews, and awake (it stops a minute after
    // the last watch). Not from the background: let it sleep.
    if (_foreground && tick % 30 == 0) unawaited(_call('watch'));
    if (tick % 10 == 9) unawaited(refreshRecordings(announce: true));
    if (_foreground && _state.isLive) {
      final p = await _call('getPreview', null, true);
      if (gen != _gen) return;
      final jpeg = p?['jpeg'] as String?;
      if (jpeg != null) {
        _preview = base64Decode(jpeg);
        _setLiveBoxes(LiveBoxes.fromJson(p?['size'], p?['boxes']));
        notifyListeners();
      }
    }
    if (tick.isEven) {
      final s = await _call('getState', null, true);
      if (gen != _gen) return;
      if (s == null) {
        if (++_pollFailures >= 5) _onDisconnected();
        return;
      }
      _pollFailures = 0;
      _applyState(s);
      final w = s['warning'] as Map<String, dynamic>?;
      final at = w?['at'] as String?;
      if (_relayWarningSeen && at != null && at != _relayWarningAt) {
        _raiseWarning(w?['code']);
      }
      _relayWarningAt = at;
      _relayWarningSeen = true;
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
    _sessionHash = msg['sessionHash'] as String?;
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
      case 'recordingsChanged':
        // a clip finished uploading: ask for this person's own list
        _upload = null;
        notifyListeners();
        unawaited(refreshRecordings(announce: true));
      case 'warning':
        _raiseWarning(msg['code']);
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

  /// A call to the camera this phone is connected to: directly, or through
  /// the backend. `quiet` calls (the relay's polling) don't surface errors
  /// in the UI.
  Future<Map<String, dynamic>?> _call(
    String name, [
    Object? data,
    bool quiet = false,
  ]) async {
    final b = base;
    if (b == null) return null;
    try {
      return await _post(b, name, data, relay: _endpoint?.direct == false);
    } on ApiException catch (err) {
      if (!quiet) {
        _lastError = err.message;
        notifyListeners();
      }
      return null;
    }
  }

  /// A call to the backend, whichever way the camera is connected: the
  /// library, claims, admin. Throws [ApiException].
  Future<Map<String, dynamic>?> cloud(String name, [Object? data]) {
    final fb = fallbackBase;
    if (fb == null || !auth.enabled) {
      throw const ApiException('This app has no backend set up');
    }
    return _post(fb, name, data, relay: true);
  }

  /// `relay`: the backend, which wants the signed-in person's ID token.
  Future<Map<String, dynamic>?> _post(
    String b,
    String name,
    Object? data, {
    required bool relay,
  }) async {
    final token = relay ? await auth.idToken() : null;
    if (relay && auth.enabled && token == null) {
      throw ApiException(
        auth.signedIn ? "Can't reach the server" : 'Sign in first',
      );
    }
    final http.Response res;
    try {
      res = await http
          .post(
            Uri.parse('$b/api/call/$name'),
            headers: {
              'Content-Type': 'application/json',
              if (cameraKey.isNotEmpty) 'X-Camera-Key': cameraKey,
              if (token != null) 'Authorization': 'Bearer $token',
            },
            body: jsonEncode({'data': data}),
          )
          .timeout(const Duration(seconds: 8));
    } on Exception catch (err) {
      throw ApiException('$err');
    }
    final Map<String, dynamic> body;
    try {
      body = jsonDecode(res.body) as Map<String, dynamic>;
    } on FormatException {
      throw ApiException('HTTP ${res.statusCode}');
    }
    if (res.statusCode == 401) auth.tokenRejected();
    if (res.statusCode != 200) {
      throw ApiException(
        (body['error'] as Map<String, dynamic>?)?['message'] as String? ??
            'HTTP ${res.statusCode}',
        res.statusCode,
      );
    }
    if (_lastError != null) _lastError = null;
    return body['result'] as Map<String, dynamic>?;
  }

  /// Every stop, sleep or advance carries the secrets this phone holds: the
  /// camera (or backend) lets it through only for the session's owner.
  Map<String, Object?> _withSecrets([Map<String, Object?> data = const {}]) =>
      {...data, 'secrets': keys.all};

  // The UI never assumes success — it waits for the state broadcast, so the
  // app, the LED ring, and any second phone stay in lock-step.

  /// Track & record / Record: starts a session that is this person's. A
  /// phone with a paired tag starts it with that pairing (UWB: the camera
  /// follows that tag).
  Future<void> startTracking() async {
    final result = await _call(
      'startTracking',
      _withSecrets({'pairing': keys.pairing}),
    );
    final secret = result?['sessionSecret'] as String?;
    if (secret != null && secret != keys.pairing) {
      await keys.add(secret, SecretKind.session);
    }
    if (result != null) {
      _applyState(result);
      notifyListeners();
    }
    unawaited(claim());
  }

  Future<void> stopTracking() =>
      _call('stopTracking', _withSecrets()).then((_) {});
  Future<void> startRecording() =>
      _call('startRecording', _withSecrets()).then((_) {});
  Future<void> stopRecording() =>
      _call('stopRecording', _withSecrets()).then((_) {});
  Future<void> setPower(bool on) =>
      _call('setPower', _withSecrets({'on': on})).then((_) {});

  /// With UWB, on the camera's own connection: pair the one tag switched on
  /// to this phone, so the sessions it starts are this person's. Returns
  /// what to tell them.
  Future<String> pairTag() async {
    if (_link != LinkMode.direct) {
      return "Pair your tag on the camera's Wi-Fi, standing next to it";
    }
    final b = base;
    if (b == null) return 'Not connected';
    try {
      final r = await _post(b, 'pairTag', null, relay: false);
      final secret = r?['pairingSecret'] as String?;
      final tag = (r?['tag'] as num?)?.toInt();
      if (secret == null) return "The camera didn't answer";
      await keys.add(secret, SecretKind.pairing, tag: tag);
      unawaited(claim());
      return 'Tag T$tag is yours: switching it on starts your recording';
    } on ApiException catch (err) {
      return err.message;
    }
  }

  /// Register the secrets this phone holds with the backend, under the
  /// person signed in: their clips — uploaded already or later — become
  /// theirs. Quietly does nothing until it can.
  Future<void> claim() async {
    final secrets = keys.unclaimed;
    if (!hasCloud || secrets.isEmpty) return;
    try {
      await cloud('claimRecordings', {'secrets': secrets});
      await keys.markClaimed(secrets);
      await refreshRecordings(announce: true);
    } on ApiException {
      // offline, or the backend is down: the next tick tries again
    }
  }

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

  /// The signed-in person's clips: the backend's library, and, connected
  /// directly, those of theirs still on the camera's card (until they
  /// upload). `announce`: a new newest recording shows the "saved" toast.
  Future<void> refreshRecordings({bool announce = false}) async {
    List<Recording>? parse(Map<String, dynamic>? r) =>
        (r?['recordings'] as List<dynamic>?)
            ?.map((e) => Recording.fromJson(e as Map<String, dynamic>))
            .toList();
    List<Recording>? fromCloud;
    if (hasCloud) {
      try {
        fromCloud = parse(await cloud('getRecordings'));
      } on ApiException {
        // offline: keep what we had from it
        fromCloud = _recordings.where((r) => r.inCloud).toList();
      }
    }
    List<Recording>? onCard;
    if (_link == LinkMode.direct) {
      onCard = parse(await _call('getRecordings', _withSecrets(), true));
    }
    if (fromCloud == null && onCard == null) return;
    final uploaded = {for (final r in fromCloud ?? const <Recording>[]) r.name};
    final merged = [
      ...?fromCloud,
      ...?onCard?.where((r) => !uploaded.contains(r.name)),
    ]..sort((a, b) => b.createdAt.compareTo(a.createdAt));
    final previousNewest = _recordings.isEmpty ? null : _recordings.first.name;
    _recordings = merged;
    if (announce &&
        previousNewest != null &&
        _recordings.isNotEmpty &&
        _recordings.first.name != previousNewest) {
      _justSaved = _recordings.first;
    }
    notifyListeners();
  }

  /// Where the player gets a clip: the owner's signed URL from the backend,
  /// or the camera's own copy, with the secrets that show it's theirs.
  /// Throws [ApiException].
  Future<Playback> playback(Recording r) async {
    if (r.inCloud) {
      final res = await cloud('getPlaybackUrl', {'camera': r.camera, 'name': r.name});
      final url = res?['url'] as String? ?? r.url;
      // under the emulator it is the API's own route, which wants the token
      return url.startsWith('http')
          ? Playback(url)
          : Playback(r.absoluteUrl(fallbackBase!), await _bearer());
    }
    final b = base;
    if (b == null) throw const ApiException('Not connected to the camera');
    return Playback(r.absoluteUrl(b), _secretsHeader());
  }

  /// Where the player gets a clip's person boxes; null if it has none.
  Future<Playback?> boxes(Recording r) async {
    if (r.boxesUrl == null) return null;
    if (r.inCloud) {
      return Playback(r.absoluteBoxesUrl(fallbackBase!)!, await _bearer());
    }
    final b = base;
    return b == null ? null : Playback(r.absoluteBoxesUrl(b)!, _secretsHeader());
  }

  Future<Map<String, String>> _bearer() async {
    final token = await auth.idToken();
    return token == null ? const {} : {'Authorization': 'Bearer $token'};
  }

  Map<String, String> _secretsHeader() =>
      {'X-Session-Secrets': keys.all.join(',')};

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
    auth.removeListener(_onAuthChanged);
    _claimTimer?.cancel();
    _retry?.cancel();
    _warningExpiry?.cancel();
    unawaited(_closeSocket());
    super.dispose();
  }
}

/// A call the camera or the backend refused, or couldn't be made; [message]
/// is fit to show.
class ApiException implements Exception {
  const ApiException(this.message, [this.status]);

  final String message;
  final int? status;

  @override
  String toString() => message;
}
