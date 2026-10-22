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
  final acq = Telemetry.fromJson({'phase': 'search', 'acquireStalled': true});
  check(
    'search phase and stall flag parse',
    acq.phase == 'search' && acq.acquireStalled,
  );
  check(
    'stall flag defaults to false',
    !Telemetry.fromJson(null).acquireStalled,
  );
  check(
    'countdown parses, defaulting to 0',
    Telemetry.fromJson({'phase': 'found', 'countdown': 2}).countdown == 2 &&
        Telemetry.fromJson(null).countdown == 0,
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
  check(
    'no boxes → no boxes url',
    recs.first.boxesUrl == null &&
        recs.first.absoluteBoxesUrl('http://b') == null,
  );
  final withBoxes = Recording.fromJson({
    ...(recJson['recordings'] as List<dynamic>).first as Map<String, dynamic>,
    'boxesUrl': '/api/recordings/rec_20260921010951.boxes.json',
  });
  check(
    'boxes url resolves against base',
    withBoxes.absoluteBoxesUrl('http://10.0.0.5:8787') ==
        'http://10.0.0.5:8787/api/recordings/rec_20260921010951.boxes.json',
  );

  // The person boxes beside a clip, as the device's boxlog.py writes them.
  final track = BoxTrack.fromJson(
    jsonDecode(
      '{"v":1,"size":[1280,720],"frames":['
      '[0.5,[[10,20,30,90,"unsure"],[300,20,30,90,"unsure"]]],'
      '[1.0,[[12,20,30,90,"climber"],[300,20,30,90,"other"]]],'
      '[1.33,[]],'
      '[3.0,[[14,20,30,90,"climber"]]]]}',
    ),
  );
  check(
    'box track parses',
    track != null && track.width == 1280 && track.frames.length == 4,
  );
  check('no boxes before the first detection', track!.at(0.2).isEmpty);
  final now = track.at(1.2);
  check(
    'boxes at a moment are the last detection before it',
    now.length == 2 &&
        now[0].label == BoxLabel.climber &&
        now[0].x == 12 &&
        now[1].label == BoxLabel.other,
  );
  check('an empty detection clears them', track.at(1.5).isEmpty);
  check('…and a stale one is not shown past the hold', track.at(4.2).isEmpty);
  check(
    'unknown labels read as unsure',
    boxLabelFrom('bogus') == BoxLabel.unsure,
  );
  check(
    'a box file of another version is ignored',
    BoxTrack.fromJson({'v': 2}) == null,
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

  // The live view's boxes: a `boxes` message on the device's WebSocket, and
  // the same shape inside `getPreview` from Firebase.
  final boxesMsg = jsonDecode('''
  {"type":"boxes","size":[1280,720],
   "boxes":[[412,160,96,288,"climber"],[820,230,140,400,"other"]]}
  ''') as Map<String, dynamic>;
  final live = LiveBoxes.fromJson(boxesMsg['size'], boxesMsg['boxes']);
  check(
    'live boxes parse',
    live != null &&
        live.width == 1280 &&
        live.boxes.length == 2 &&
        live.boxes.first.label == BoxLabel.climber &&
        live.boxes.last.x == 820,
  );
  check(
    'an empty list is "looked and saw nobody", not "no boxes"',
    LiveBoxes.fromJson([1280, 720], [])?.boxes.isEmpty == true,
  );
  check(
    'a preview from an older camera has no boxes',
    LiveBoxes.fromJson(null, null) == null,
  );
  check(
    'malformed boxes are skipped, not fatal',
    LiveBoxes.fromJson([1280, 720], [
          [1, 2, 3],
          ['a', 2, 3, 4, 'other'],
          [1, 2, 3, 4, 'bogus'],
        ])?.boxes.single.label ==
        BoxLabel.unsure,
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
