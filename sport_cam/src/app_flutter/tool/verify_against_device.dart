/// Cross-language contract check: drives the *real* Python device API with
/// the app's own model parsing, proving the phone and camera agree.
///
/// Start the stub device first, then:
///     dart run tool/verify_against_device.dart [http://127.0.0.1:8787]
///
/// Or check the Firebase backend the same way (the relay path), against the
/// emulators from `npm run dev`, with the simulated camera's key:
///     dart run tool/verify_against_device.dart \
///         http://127.0.0.1:5001/demo-sportcam/us-central1/api dev-camera-key
///
/// Uses dart:io (no pub packages) so it runs without the Flutter SDK.
library;

import 'dart:convert';
import 'dart:io';

import '../lib/models.dart';

int _failures = 0;

/// Set for the Firebase backend: every call names the camera.
String? _cameraKey;

void check(String name, bool ok, [String detail = '']) {
  // ignore: avoid_print
  print('  ${ok ? 'PASS' : 'FAIL'}  $name${ok ? '' : ' — $detail'}');
  if (!ok) _failures++;
}

Future<Map<String, dynamic>> call(
  HttpClient client,
  String base,
  String name, [
  Object? data,
]) async {
  final req = await client.postUrl(Uri.parse('$base/api/call/$name'));
  req.headers.contentType = ContentType.json;
  if (_cameraKey != null) req.headers.set('X-Camera-Key', _cameraKey!);
  req.write(jsonEncode({'data': data}));
  final res = await req.close();
  final body = jsonDecode(
    await res.transform(utf8.decoder).join(),
  ) as Map<String, dynamic>;
  return {'status': res.statusCode, ...body};
}

Future<void> main(List<String> args) async {
  final base = args.isEmpty ? 'http://127.0.0.1:8787' : args.first;
  _cameraKey = args.length > 1 ? args[1] : null;
  final relay = _cameraKey != null;
  final client = HttpClient();

  try {
    // --- health ---------------------------------------------------------
    final healthReq = await client.getUrl(Uri.parse('$base/api/health'));
    final healthRes = await healthReq.close();
    final health = jsonDecode(
      await healthRes.transform(utf8.decoder).join(),
    ) as Map<String, dynamic>;
    check('device reachable', health['ok'] == true, '$health');

    // --- state, parsed by the app's own model code ----------------------
    var res = await call(client, base, 'getState');
    var parsed = camStateFrom(
      (res['result'] as Map<String, dynamic>)['state'] as String?,
    );
    check('getState parses to a CamState', parsed == CamState.awake, '$parsed');

    final telemetry = Telemetry.fromJson(
      (res['result'] as Map<String, dynamic>)['telemetry']
          as Map<String, dynamic>?,
    );
    check(
      'device telemetry parses',
      telemetry.tilt != null,
      'tilt=${telemetry.tilt}',
    );

    // --- control: exactly what the app's buttons send --------------------
    res = await call(client, base, 'startTracking');
    parsed = camStateFrom(
      (res['result'] as Map<String, dynamic>)['state'] as String?,
    );
    check('startTracking → tracking', parsed == CamState.tracking, '$parsed');

    res = await call(client, base, 'startRecording');
    parsed = camStateFrom(
      (res['result'] as Map<String, dynamic>)['state'] as String?,
    );
    check(
      'startRecording → recording',
      parsed == CamState.recording,
      '$parsed',
    );

    res = await call(client, base, 'startRecording');
    check(
      'illegal transition surfaces an error the app can show',
      res['status'] == 412 &&
          (res['error'] as Map<String, dynamic>)['message'] != null,
      '$res',
    );

    res = await call(client, base, 'stopRecording');
    parsed = camStateFrom(
      (res['result'] as Map<String, dynamic>)['state'] as String?,
    );
    check('stopRecording → awake (ends the session)', parsed == CamState.awake, '$parsed');

    // --- recordings, parsed into the library model -----------------------
    res = await call(client, base, 'getRecordings');
    final recs =
        ((res['result'] as Map<String, dynamic>)['recordings'] as List<dynamic>)
            .map((e) => Recording.fromJson(e as Map<String, dynamic>))
            .toList();
    check('device recordings parse', recs.isNotEmpty, '${recs.length} found');
    if (recs.isNotEmpty) {
      final url = recs.first.absoluteUrl(base);
      final playReq = await client.getUrl(Uri.parse(url));
      playReq.headers.set(HttpHeaders.rangeHeader, 'bytes=0-99');
      final playRes = await playReq.close();
      final bytes = await playRes.fold<int>(0, (n, c) => n + c.length);
      check(
        'library playback URL serves ranges',
        playRes.statusCode == 206 && bytes == 100,
        'status=${playRes.statusCode} bytes=$bytes',
      );
    }

    if (relay) {
      // --- Firebase: the preview the relay polls in place of MJPEG ----------
      res = await call(client, base, 'watch');
      check('watch is accepted', res['status'] == 200, '$res');
      await Future<void>.delayed(const Duration(seconds: 2));
      res = await call(client, base, 'getPreview');
      final jpeg = (res['result'] as Map<String, dynamic>?)?['jpeg'] as String?;
      check(
        'getPreview returns a JPEG',
        jpeg != null && base64Decode(jpeg).take(2).toList().toString() == '[255, 216]',
        '$res'.substring(0, 80),
      );
      await call(client, base, 'stopTracking');
      exitCode = _failures == 0 ? 0 : 1;
      // ignore: avoid_print
      print(_failures == 0 ? '\nall contract checks passed' : '\n$_failures failed');
      return;
    }

    // --- websocket: the live state channel the app listens on ------------
    final ws = await WebSocket.connect('$base/ws'.replaceFirst('http', 'ws'));
    final first = jsonDecode(await ws.first as String) as Map<String, dynamic>;
    check('WS pushes state on connect', first['type'] == 'state', '$first');
    await ws.close();

    // --- MJPEG: the live video the app renders ---------------------------
    final streamReq = await client.getUrl(Uri.parse('$base/api/stream.mjpeg'));
    final streamRes = await streamReq.close();
    check(
      'MJPEG stream has the multipart content type',
      streamRes.headers.contentType?.value.contains(
            'multipart/x-mixed-replace',
          ) ??
          false,
      '${streamRes.headers.contentType}',
    );
    await streamRes.drain<void>().timeout(
      const Duration(seconds: 2),
      onTimeout: () {},
    );
  } on Exception catch (err) {
    check('no exceptions talking to the device', false, '$err');
  } finally {
    client.close(force: true);
  }

  // ignore: avoid_print
  print(
    _failures == 0 ? '\napp ↔ device contract verified' : '\n$_failures FAILED',
  );
  if (_failures > 0) exitCode = 1;
}
