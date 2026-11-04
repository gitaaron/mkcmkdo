import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:sportcam/models.dart';
import 'package:sportcam/widgets/lens_controls.dart';

void main() {
  group('lens from telemetry', () {
    test('reads the zoom and its range', () {
      final l = Lens.fromJson({'zoomMm': 6.0, 'zoomRangeMm': [2.8, 10.6]});
      expect(l.zoomMm, 6.0);
      expect(l.zoomMaxMm, 10.6);
    });

    test('an older camera: the Arducam zoom range', () {
      final l = Lens.fromJson({'zoomMm': 2.8});
      expect(l.zoomMinMm, 2.8);
      expect(l.zoomMaxMm, 10.6);
    });

    test('autofocus and the frame a tap is a share of', () {
      final t = Telemetry.fromJson({'focusing': true, 'frameSize': [1280, 720]});
      expect(t.focusing, isTrue);
      expect((t.frameWidth, t.frameHeight), (1280.0, 720.0));
      expect(Telemetry.fromJson({}).focusing, isFalse);
    });
  });

  group('zoom slider', () {
    late List<double> zooms;

    Future<void> pump(WidgetTester tester, Lens lens) async {
      await tester.pumpWidget(MaterialApp(
        home: Scaffold(
          body: Center(
            child: SizedBox(
              width: 360,
              child: LensControls(lens: lens, onZoom: zooms.add),
            ),
          ),
        ),
      ));
    }

    setUp(() => zooms = []);

    testWidgets("shows the camera's zoom, and no focus slider", (tester) async {
      await pump(tester, const Lens(zoomMm: 5.6));
      expect(find.text('2.0×'), findsOneWidget);
      expect(find.byType(Slider), findsOneWidget);
    });

    testWidgets('dragging sends a few, ending where it was let go',
        (tester) async {
      await pump(tester, const Lens());
      final r = tester.getRect(find.byType(Slider));
      final g = await tester.startGesture(r.centerLeft + const Offset(30, 0));
      for (var i = 1; i <= 20; i++) {
        await g.moveBy(const Offset(10, 0));
        await tester.pump(const Duration(milliseconds: 10));
      }
      await g.up();
      await tester.pump();
      expect(zooms, isNotEmpty);
      expect(zooms.length, lessThan(10)); // throttled, not one per move
      expect(zooms.last, greaterThan(2.8));
      final shown = find.textContaining('×');
      expect(tester.widget<Text>(shown).data, isNot('1.0×'));

      // the camera hasn't reported yet: the slider stays where it was left…
      await tester.pump(const Duration(milliseconds: 1000));
      expect(tester.widget<Text>(shown).data, isNot('1.0×'));
      // …then follows the camera again
      await tester.pump(const Duration(milliseconds: 600));
      expect(tester.widget<Text>(shown).data, '1.0×');
    });
  });
}
