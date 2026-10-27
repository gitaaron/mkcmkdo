/// Cross-language contract check: drives the *real* Python device API with
/// the app's own model parsing, proving the phone and camera agree.
///
/// Start the stub device first, then:
///     dart run tool/verify_against_device.dart [http://127.0.0.1:8787]
///
/// Or check the Firebase backend the same way (the relay path), against the
/// emulators from `npm run dev`, with the simulated camera's key, signed in as
/// the simulator's climber (Authentication emulator on 127.0.0.1:9099):
///     dart run tool/verify_against_device.dart \
///         http://127.0.0.1:5001/demo-sportcam/us-central1/api dev-camera-key [auth-host:port]
///
/// Either way it is one phone: it starts a session, is handed the secret,
/// and must send it back to stop it; its library is its own clips.
///
/// Uses dart:io (no pub packages) so it runs without the Flutter SDK.
library;

import 'dart:convert';
import 'dart:io';

import '../lib/models.dart';

int _failures = 0;

/// Set for the Firebase backend: every call names the camera…
String? _cameraKey;

/// …and carries the signed-in person's ID token.
String? _idToken;

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
  if (_idToken != null) req.headers.set('Authorization', 'Bearer $_idToken');
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
    if (relay) {
      // sign in as the app does (auth.dart), as the simulator's climber
      final host = args.length > 2 ? args[2] : '127.0.0.1:9099';
      final req = await client.postUrl(Uri.parse(
        'http://$host/identitytoolkit.googleapis.com/v1/accounts:signInWithPassword?key=emulator',
      ));
      req.headers.contentType = ContentType.json;
      req.write(jsonEncode({
        'email': 'climber@sportcam.dev',
        'password': 'sportcam-dev',
        'returnSecureToken': true,
      }));
      final res = await req.close();
      final body = jsonDecode(await res.transform(utf8.decoder).join()) as Map<String, dynamic>;
      _idToken = body['idToken'] as String?;
      check('signs in to the backend', _idToken != null, '$body');
      final saved = _idToken;
      _idToken = null;
      final refused = await call(client, base, 'getState');
      check('…which answers nobody signed out', refused['status'] == 401, '$refused');
      _idToken = saved;
    }

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
    res = await call(client, base, 'startTracking', {'secrets': <String>[]});
    parsed = camStateFrom(
      (res['result'] as Map<String, dynamic>)['state'] as String?,
    );
    check('startTracking → tracking', parsed == CamState.tracking, '$parsed');
    final secret = (res['result'] as Map<String, dynamic>)['sessionSecret'] as String?;
    final sessionHash = (res['result'] as Map<String, dynamic>)['sessionHash'] as String?;
    check(
      '…handing this phone its secret, the same SHA-256 the app checks (keys.dart)',
      secret != null && sessionHash == _sha256Hex(secret),
      '$res',
    );
    final mine = {'secrets': [if (secret != null) secret]};

    res = await call(client, base, 'startRecording');
    check(
      "another phone can't touch it: the app's buttons go grey (403)",
      res['status'] == 403,
      '$res',
    );

    res = await call(client, base, 'startRecording', mine);
    parsed = camStateFrom(
      (res['result'] as Map<String, dynamic>)['state'] as String?,
    );
    check(
      'startRecording → recording',
      parsed == CamState.recording,
      '$parsed',
    );

    res = await call(client, base, 'startRecording', mine);
    check(
      'illegal transition surfaces an error the app can show',
      res['status'] == 412 &&
          (res['error'] as Map<String, dynamic>)['message'] != null,
      '$res',
    );

    res = await call(client, base, 'stopRecording', mine);
    parsed = camStateFrom(
      (res['result'] as Map<String, dynamic>)['state'] as String?,
    );
    check('stopRecording → awake (ends the session)', parsed == CamState.awake, '$parsed');

    // --- recordings, parsed into the library model -----------------------
    if (relay) {
      // the simulated camera uploads the clip, then the library has it
      for (var i = 0; i < 30; i++) {
        res = await call(client, base, 'getRecordings');
        final list = (res['result'] as Map<String, dynamic>?)?['recordings'] as List?;
        if (list != null && list.isNotEmpty) break;
        await Future<void>.delayed(const Duration(seconds: 1));
      }
    } else {
      res = await call(client, base, 'getRecordings');
      check(
        "the camera's card shows nobody else's clips",
        ((res['result'] as Map<String, dynamic>)['recordings'] as List).isEmpty,
        '$res',
      );
      res = await call(client, base, 'getRecordings', mine);
    }
    final recs =
        ((res['result'] as Map<String, dynamic>)['recordings'] as List<dynamic>)
            .map((e) => Recording.fromJson(e as Map<String, dynamic>))
            .toList();
    check('this phone\'s recordings parse', recs.isNotEmpty, '${recs.length} found');
    check(
      relay ? '…from the cloud library, naming their camera' : '…still on the card, naming no camera',
      recs.isNotEmpty && recs.first.inCloud == relay,
      '${recs.firstOrNull?.camera}',
    );
    if (recs.isNotEmpty) {
      var url = recs.first.absoluteUrl(base);
      if (relay) {
        res = await call(client, base, 'getPlaybackUrl', {'camera': recs.first.camera, 'name': recs.first.name});
        final play = (res['result'] as Map<String, dynamic>)['url'] as String;
        url = play.startsWith('http') ? play : '$base$play';
      }
      final playReq = await client.getUrl(Uri.parse(url));
      playReq.headers.set(HttpHeaders.rangeHeader, 'bytes=0-99');
      if (relay) {
        playReq.headers.set('Authorization', 'Bearer $_idToken');
      } else {
        playReq.headers.set('X-Session-Secrets', secret ?? '');
      }
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
      await call(client, base, 'stopTracking', mine);
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

/// SHA-256 in hex, by the book (FIPS 180-4), so this check needs no pub
/// packages: the app's keys.dart uses package:crypto for the same thing.
String _sha256Hex(String text) {
  const k = [
    0x428a2f98, 0x71374491, 0xb5c0fbcf, 0xe9b5dba5, 0x3956c25b, 0x59f111f1, 0x923f82a4, 0xab1c5ed5,
    0xd807aa98, 0x12835b01, 0x243185be, 0x550c7dc3, 0x72be5d74, 0x80deb1fe, 0x9bdc06a7, 0xc19bf174,
    0xe49b69c1, 0xefbe4786, 0x0fc19dc6, 0x240ca1cc, 0x2de92c6f, 0x4a7484aa, 0x5cb0a9dc, 0x76f988da,
    0x983e5152, 0xa831c66d, 0xb00327c8, 0xbf597fc7, 0xc6e00bf3, 0xd5a79147, 0x06ca6351, 0x14292967,
    0x27b70a85, 0x2e1b2138, 0x4d2c6dfc, 0x53380d13, 0x650a7354, 0x766a0abb, 0x81c2c92e, 0x92722c85,
    0xa2bfe8a1, 0xa81a664b, 0xc24b8b70, 0xc76c51a3, 0xd192e819, 0xd6990624, 0xf40e3585, 0x106aa070,
    0x19a4c116, 0x1e376c08, 0x2748774c, 0x34b0bcb5, 0x391c0cb3, 0x4ed8aa4a, 0x5b9cca4f, 0x682e6ff3,
    0x748f82ee, 0x78a5636f, 0x84c87814, 0x8cc70208, 0x90befffa, 0xa4506ceb, 0xbef9a3f7, 0xc67178f2,
  ];
  final h = [
    0x6a09e667, 0xbb67ae85, 0x3c6ef372, 0xa54ff53a, 0x510e527f, 0x9b05688c, 0x1f83d9ab, 0x5be0cd19,
  ];
  int rotr(int x, int n) => ((x >> n) | (x << (32 - n))) & 0xffffffff;
  final msg = [...utf8.encode(text), 0x80];
  final bits = utf8.encode(text).length * 8;
  while (msg.length % 64 != 56) {
    msg.add(0);
  }
  for (var i = 7; i >= 0; i--) {
    msg.add((bits >> (8 * i)) & 0xff);
  }
  for (var c = 0; c < msg.length; c += 64) {
    final w = List<int>.filled(64, 0);
    for (var i = 0; i < 16; i++) {
      w[i] = (msg[c + 4 * i] << 24) | (msg[c + 4 * i + 1] << 16) | (msg[c + 4 * i + 2] << 8) | msg[c + 4 * i + 3];
    }
    for (var i = 16; i < 64; i++) {
      final s0 = rotr(w[i - 15], 7) ^ rotr(w[i - 15], 18) ^ (w[i - 15] >> 3);
      final s1 = rotr(w[i - 2], 17) ^ rotr(w[i - 2], 19) ^ (w[i - 2] >> 10);
      w[i] = (w[i - 16] + s0 + w[i - 7] + s1) & 0xffffffff;
    }
    var a = h[0], b = h[1], cc = h[2], d = h[3], e = h[4], f = h[5], g = h[6], hh = h[7];
    for (var i = 0; i < 64; i++) {
      final s1 = rotr(e, 6) ^ rotr(e, 11) ^ rotr(e, 25);
      final ch = (e & f) ^ (~e & 0xffffffff & g);
      final t1 = (hh + s1 + ch + k[i] + w[i]) & 0xffffffff;
      final s0 = rotr(a, 2) ^ rotr(a, 13) ^ rotr(a, 22);
      final maj = (a & b) ^ (a & cc) ^ (b & cc);
      final t2 = (s0 + maj) & 0xffffffff;
      hh = g;
      g = f;
      f = e;
      e = (d + t1) & 0xffffffff;
      d = cc;
      cc = b;
      b = a;
      a = (t1 + t2) & 0xffffffff;
    }
    final add = [a, b, cc, d, e, f, g, hh];
    for (var i = 0; i < 8; i++) {
      h[i] = (h[i] + add[i]) & 0xffffffff;
    }
  }
  return h.map((x) => x.toRadixString(16).padLeft(8, '0')).join();
}
