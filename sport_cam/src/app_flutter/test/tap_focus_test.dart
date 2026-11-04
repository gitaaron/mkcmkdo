import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:sportcam/models.dart';
import 'package:sportcam/widgets/aim_panel.dart';
import 'package:sportcam/widgets/joystick.dart';
import 'package:sportcam/widgets/oriented_view.dart';
import 'package:sportcam/widgets/tap_focus.dart';

void main() {
  group('tap position → frame', () {
    const frame = Size(1280, 720);

    test('a 16:9 frame in a 16:9 box', () {
      final f = frameFraction(const Offset(320, 180), const Size(640, 360), frame)!;
      expect(f.dx, closeTo(0.5, 1e-9));
      expect(f.dy, closeTo(0.5, 1e-9));
    });

    test('letterboxed: the bars are not the picture', () {
      // 640 × 640 box: the picture is 640 × 360, 140 down
      expect(frameFraction(const Offset(320, 100), const Size(640, 640), frame), isNull);
      final f = frameFraction(const Offset(160, 140 + 90), const Size(640, 640), frame)!;
      expect(f.dx, closeTo(0.25, 1e-9));
      expect(f.dy, closeTo(0.25, 1e-9));
    });
  });

  testWidgets(
      'turned and mirrored like the bench rig, a tap still lands on the '
      "camera's own frame", (tester) async {
    tester.view.physicalSize = const Size(360, 640); // portrait phone
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.reset);
    final taps = <Offset>[];
    var focusing = false;
    Widget build() => MaterialApp(
          home: OrientedView(
            view: const ViewOrientation(quarterTurns: 1, mirror: true),
            child: TapToFocus(
              frameSize: const Size(1280, 720),
              focusing: focusing,
              onFocus: (x, y) => taps.add(Offset(x, y)),
            ),
          ),
        );
    await tester.pumpWidget(build());
    // The 16:9 frame turned a quarter fills the 360 × 640 screen. A quarter
    // turn clockwise, then mirrored: screen (sx, sy) is frame (sy / 640,
    // sx / 360) — the frame's x runs down the screen, its y across it.
    await tester.tapAt(const Offset(90, 480));
    await tester.pump();
    expect(taps.single.dx, closeTo(0.75, 0.01));
    expect(taps.single.dy, closeTo(0.25, 0.01));
    await tester.tapAt(const Offset(359, 1)); // screen top-right
    await tester.pump();
    expect(taps.last.dx, closeTo(0, 0.01));
    expect(taps.last.dy, closeTo(1, 0.01));

    // the square shows where you tapped, and stays while the camera focuses
    expect(find.byKey(const ValueKey('focus-square')), findsOneWidget);
    focusing = true;
    await tester.pumpWidget(build());
    await tester.pump(const Duration(seconds: 3));
    expect(find.byKey(const ValueKey('focus-square')), findsOneWidget);
    focusing = false;
    await tester.pumpWidget(build());
    expect(find.byKey(const ValueKey('focus-square')), findsNothing);
  });

  testWidgets('the aim panel: tucked away it lets taps through, the arrow brings it up',
      (tester) async {
    var open = false;
    final aims = <Offset>[];
    var behind = 0;
    Widget build() => MaterialApp(
          home: Scaffold(
            body: Stack(
              children: [
                Positioned.fill(
                  child: GestureDetector(
                    behavior: HitTestBehavior.opaque,
                    onTap: () => behind++,
                  ),
                ),
                Positioned(
                  left: 18,
                  right: 18,
                  bottom: 96,
                  child: AimPanel(
                    open: open,
                    lens: const Lens(),
                    onZoom: (_) {},
                    onAim: (p, t) => aims.add(Offset(p, t)),
                  ),
                ),
                Positioned(
                  left: 0,
                  right: 0,
                  bottom: 84,
                  child: Center(
                    child: AimToggle(open: open, onTap: () => open = !open),
                  ),
                ),
              ],
            ),
          ),
        );
    await tester.pumpWidget(build());
    await tester.pumpAndSettle();
    final stick = tester.getCenter(find.byType(Joystick).first);
    await tester.tapAt(stick);
    expect(behind, 1); // closed: the tap reaches the picture
    expect(aims, isEmpty);

    await tester.tap(find.byType(AimToggle));
    await tester.pumpWidget(build());
    await tester.pumpAndSettle();
    expect(open, isTrue);
    final g = await tester.startGesture(tester.getCenter(find.byType(Joystick).first));
    await g.moveBy(const Offset(-30, 0));
    await tester.pump(const Duration(milliseconds: 60));
    expect(aims, isNotEmpty); // open: the stick works
    await g.up();
    await tester.pump();
  });
}
