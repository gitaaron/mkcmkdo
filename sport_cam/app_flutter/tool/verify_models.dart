/// Verifies the app's parsing against real payloads from the device API.
/// Pure Dart (no Flutter), so it runs without the Flutter SDK:
///
///     dart run tool/verify_models.dart
library;

import 'dart:convert';

import '../lib/models.dart';

int _failures = 0;

void check(String name, bool ok, [String detail = '']) {
  // ignore: avoid_print
  print('  ${ok ? 'PASS' : 'FAIL'}  $name${ok ? '' : ' — $detail'}');
  if (!ok) _failures++;
}

void main() {
  // Captured verbatim from `POST /api/call/getState` on the device.
  final state = jsonDecode('''
  {"type":"state","state":"tracking",
   "telemetry":{"pan":90.0,"tilt":12.0,"dist":4.2},
   "deviceOnline":true,"whepUrl":null,"updatedAt":"2026-09-22T10:31:00Z"}
  ''') as Map<String, dynamic>;

  check(
    'state parses',
    camStateFrom(state['state'] as String?) == CamState.tracking,
  );
  check(
    'unknown state falls back to off',
    camStateFrom('bogus') == CamState.off,
  );
  check('null state falls back to off', camStateFrom(null) == CamState.off);

  check(
    'mode defaults to with UWB when the backend omits it',
    trackingModeFrom(state['mode'] as String?) == TrackingMode.withUwb,
  );
  check(
    'without_uwb mode parses and picks its wording',
    trackingModeFrom('without_uwb') == TrackingMode.withoutUwb &&
        ModeText.of(TrackingMode.withoutUwb).startTracking == 'Track & record',
  );

  final t = Telemetry.fromJson(state['telemetry'] as Map<String, dynamic>?);
  check('telemetry parses', t.pan == 90.0 && t.tilt == 12.0 && t.distM == 4.2);
  check('telemetry tolerates null', Telemetry.fromJson(null).pan == null);
  final acq = Telemetry.fromJson({
    'phase': 'acquiring',
    'acquireStalled': true,
  });
  check(
    'acquiring phase and stall flag parse',
    acq.phase == 'acquiring' && acq.acquireStalled,
  );
  check(
    'stall flag defaults to false',
    !Telemetry.fromJson(null).acquireStalled,
  );

  // Captured from `POST /api/call/getRecordings`.
  final recJson = jsonDecode('''
  {"recordings":[
    {"name":"rec_20260921010951.mp4","bytes":131669,
     "createdAt":"2026-09-21T01:09:51Z","durationS":3.0,
     "url":"/api/recordings/rec_20260921010951.mp4"}]}
  ''') as Map<String, dynamic>;

  final recs = (recJson['recordings'] as List<dynamic>)
      .map((e) => Recording.fromJson(e as Map<String, dynamic>))
      .toList();
  check('recording parses', recs.length == 1 && recs.first.bytes == 131669);
  check(
    'relative url resolves against base',
    recs.first.absoluteUrl('http://10.0.0.5:8787') ==
        'http://10.0.0.5:8787/api/recordings/rec_20260921010951.mp4',
    recs.first.absoluteUrl('http://10.0.0.5:8787'),
  );
  check(
    'absolute url passes through',
    Recording(
          name: 'a.mp4',
          bytes: 1,
          createdAt: DateTime(2026),
          url: 'https://x.web.app/api/recordings/a.mp4',
        ).absoluteUrl('http://ignored') ==
        'https://x.web.app/api/recordings/a.mp4',
  );
  check(
    'size label',
    recs.first.sizeLabel == '132 MB' || recs.first.sizeLabel == '1 MB',
    recs.first.sizeLabel,
  );
  check(
    'duration label',
    recs.first.durationLabel == '0:03',
    recs.first.durationLabel,
  );

  // Endpoint URL construction — what the app actually connects to.
  const ep = CameraEndpoint(name: 'SportCam', host: '10.0.0.5', port: 8787);
  check('stream url', ep.streamUrl == 'http://10.0.0.5:8787/api/stream.mjpeg');
  check('ws url', ep.wsUrl == 'ws://10.0.0.5:8787/ws');
  check(
    'endpoints dedupe by host:port',
    {
          ep,
          const CameraEndpoint(name: 'other', host: '10.0.0.5', port: 8787),
        }.length ==
        1,
  );

  final upload = const UploadProgress('rec.mp4', 45, 90);
  check('upload fraction', upload.fraction == 0.5);
  check(
    'upload fraction guards div-by-zero',
    const UploadProgress('x', 0, 0).fraction == 0,
  );

  // ignore: avoid_print
  print(_failures == 0 ? '\nall model checks passed' : '\n$_failures FAILED');
  if (_failures > 0) throw StateError('model verification failed');
}
