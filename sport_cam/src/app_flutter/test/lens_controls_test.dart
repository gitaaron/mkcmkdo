import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:sportcam/models.dart';
import 'package:sportcam/widgets/lens_controls.dart';

void main() {
  group('lens from telemetry', () {
    test('reads zoom, its range and the focus position', () {
      final l = Lens.fromJson({
        'zoomMm': 6.0,
        'zoomRangeMm': [2.8, 10.6],
        'focusPos': 0.42,
      });
      expect(l.zoomMm, 6.0);
      expect(l.zoomMaxMm, 10.6);
      expect(l.focusPos, 0.42);
    });

    test('an older camera: the Arducam zoom range, focus unknown', () {
      final l = Lens.fromJson({'zoomMm': 2.8});
      expect(l.zoomMinMm, 2.8);
      expect(l.zoomMaxMm, 10.6);
      expect(l.focusPos, isNull);
    });
  });

  group('lens sliders', () {
    late List<double> zooms;
    late List<double> focuses;

    Future<void> pump(WidgetTester tester, Lens lens) async {
      await tester.pumpWidget(MaterialApp(
        home: Scaffold(
          body: Center(
            child: SizedBox(
              width: 360,
              child: LensControls(
                lens: lens,
                onZoom: zooms.add,
                onFocus: focuses.add,
              ),
            ),
          ),
        ),
      ));
    }

    setUp(() {
      zooms = [];
      focuses = [];
    });

    testWidgets('show the camera\'s zoom and focus', (tester) async {
      await pump(tester, const Lens(zoomMm: 5.6, focusPos: 0.42));
      expect(find.text('2.0×'), findsOneWidget);
      expect(find.text('42%'), findsOneWidget);
    });

    testWidgets('dragging zoom sends a few, ending where it was let go',
        (tester) async {
      await pump(tester, const Lens());
      final slider = find.byType(Slider).first;
      final r = tester.getRect(slider);
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
      expect((tester.widget<Text>(shown).data!), isNot('1.0×'));

      // the camera hasn't reported yet: the slider stays where it was left…
      await tester.pump(const Duration(milliseconds: 1000));
      expect(tester.widget<Text>(shown).data, isNot('1.0×'));
      // …then follows the camera again
      await tester.pump(const Duration(milliseconds: 600));
      expect(tester.widget<Text>(shown).data, '1.0×');
    });

    testWidgets('focus sends the motor position the slider is at',
        (tester) async {
      await pump(tester, const Lens(focusPos: 0));
      final r = tester.getRect(find.byType(Slider).last);
      await tester.tapAt(r.center);
      await tester.pump();
      expect(focuses, isNotEmpty);
      expect(focuses.last, closeTo(0.5, 0.05));
      expect(find.text('50%'), findsOneWidget);
      await tester.pump(const Duration(seconds: 2));
    });
  });
}
