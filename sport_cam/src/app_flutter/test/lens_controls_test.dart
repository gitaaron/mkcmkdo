import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:sportcam/models.dart';
import 'package:sportcam/widgets/lens_controls.dart';

void main() {
  group('lens from telemetry', () {
    test('reads zoom, focus and their ranges', () {
      final l = Lens.fromJson({
        'zoomMm': 6.0,
        'zoomRangeMm': [2.8, 10.6],
        'focusM': 4.0,
        'focusRangeM': [0.5, 30],
      });
      expect(l.zoomMm, 6.0);
      expect(l.focusM, 4.0);
      expect(l.focusMaxM, 30);
    });

    test('an older camera: the Arducam defaults, focus unknown', () {
      final l = Lens.fromJson({'zoomMm': 2.8});
      expect(l.zoomMinMm, 2.8);
      expect(l.zoomMaxMm, 10.6);
      expect(l.focusM, isNull);
    });

    test('focus slider is even in 1/distance, near to far', () {
      const l = Lens();
      expect(l.sliderToFocus(0), closeTo(0.5, 1e-9));
      expect(l.sliderToFocus(1), closeTo(30, 1e-9));
      for (final m in [0.5, 1.0, 3.0, 12.0, 30.0]) {
        expect(l.sliderToFocus(l.focusToSlider(m)), closeTo(m, 1e-9));
      }
      // halfway in 1/d is near the near end: 1 / ((2 + 1/30) / 2) ≈ 0.98 m
      expect(l.sliderToFocus(0.5), closeTo(0.984, 1e-3));
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
      await pump(tester, const Lens(zoomMm: 5.6, focusM: 4.5));
      expect(find.text('2.0×'), findsOneWidget);
      expect(find.text('4.5 m'), findsOneWidget);
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

    testWidgets('focus sends a distance in metres', (tester) async {
      await pump(tester, const Lens(focusM: 30));
      final r = tester.getRect(find.byType(Slider).last);
      await tester.tapAt(r.center);
      await tester.pump();
      expect(focuses, isNotEmpty);
      expect(focuses.last, inInclusiveRange(0.5, 30));
      expect(focuses.last, lessThan(5)); // the middle of the slider is near
      await tester.pump(const Duration(seconds: 2));
    });
  });
}
