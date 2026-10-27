import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:sportcam/auth.dart';
import 'package:sportcam/keys.dart';
import 'package:sportcam/models.dart';
import 'package:sportcam/widgets/control_bar.dart';

void main() {
  group('control bar', () {
    Future<List<String>> tapBoth(
      WidgetTester tester,
      CamState state, {
      required bool locked,
    }) async {
      final pressed = <String>[];
      await tester.pumpWidget(MaterialApp(
        home: Scaffold(
          body: ControlBar(
            state: state,
            enabled: true,
            locked: locked,
            onSetPower: (on) => pressed.add(on ? 'wake' : 'sleep'),
            onStartTracking: () => pressed.add('start'),
            onStopTracking: () => pressed.add('stopTracking'),
            onStopRecording: () => pressed.add('stopRecording'),
          ),
        ),
      ));
      for (final label in ['Sleep', 'Stop recording', 'Stop tracking', 'Track & record', 'Start tracking']) {
        final f = find.text(label);
        if (f.evaluate().isNotEmpty) await tester.tap(f);
      }
      return pressed;
    }

    testWidgets("someone else's recording: neither Stop nor Sleep does anything", (tester) async {
      expect(await tapBoth(tester, CamState.recording, locked: true), isEmpty);
      expect(await tapBoth(tester, CamState.tracking, locked: true), isEmpty);
    });

    testWidgets('your own recording: both work', (tester) async {
      expect(await tapBoth(tester, CamState.recording, locked: false), ['sleep', 'stopRecording']);
    });

    testWidgets('outside a session there is nothing to lock: anyone can start one', (tester) async {
      expect(await tapBoth(tester, CamState.awake, locked: true), ['sleep', 'start']);
    });
  });

  group('session keys', () {
    setUp(() => SharedPreferences.setMockInitialValues({}));

    test("hashes as the camera and backend do (SHA-256, hex)", () {
      // sha256("abc")
      expect(SessionKeys.hash('abc'),
          'ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad');
    });

    test('each person holds their own secrets, kept across launches', () async {
      final keys = await SessionKeys.load();
      keys.uid = 'alice';
      await keys.add('alice-session-secret-0001', SecretKind.session);
      keys.uid = 'bob';
      expect(keys.all, isEmpty, reason: "bob doesn't get alice's clips");
      await keys.add('bob-session-secret-00001', SecretKind.session);

      final again = await SessionKeys.load();
      again.uid = 'alice';
      expect(again.all, ['alice-session-secret-0001']);
      expect(again.hashes, {SessionKeys.hash('alice-session-secret-0001')});
      expect(again.unclaimed, ['alice-session-secret-0001']);
      await again.markClaimed(again.unclaimed);
      expect(again.unclaimed, isEmpty);
      expect(again.all, ['alice-session-secret-0001'], reason: 'still needed to stop and to play from the card');
    });

    test("pairing a tag again replaces that tag's pairing, not the others'", () async {
      final keys = await SessionKeys.load();
      keys.uid = 'alice';
      await keys.add('pairing-tag-1-first-0001', SecretKind.pairing, tag: 1);
      await keys.add('pairing-tag-2-only-00001', SecretKind.pairing, tag: 2);
      await keys.add('pairing-tag-1-second-001', SecretKind.pairing, tag: 1);
      expect(keys.pairing, 'pairing-tag-1-second-001');
      expect(keys.all.toSet(), {'pairing-tag-1-second-001', 'pairing-tag-2-only-00001'});
    });
  });

  group('sign-in', () {
    String jwt(Map<String, Object?> claims) =>
        'h.${base64Url.encode(utf8.encode(jsonEncode(claims))).replaceAll('=', '')}.s';

    test('reads the admin claim from the ID token', () {
      expect(jwtClaims(jwt({'user_id': 'u', 'admin': true}))['admin'], true);
      expect(jwtClaims(jwt({'user_id': 'u'}))['admin'], isNull);
      expect(jwtClaims('not a token'), isEmpty);
    });

    test("says what went wrong in people's words", () {
      expect(authMessage('INVALID_LOGIN_CREDENTIALS'), 'Wrong email or password');
      expect(authMessage('TOO_MANY_ATTEMPTS_TRY_LATER : Access disabled'), contains('wait'));
      expect(authMessage(null), contains('unknown'));
    });
  });
}
