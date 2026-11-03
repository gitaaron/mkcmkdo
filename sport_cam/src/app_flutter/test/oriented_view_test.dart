import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:sportcam/models.dart';
import 'package:sportcam/widgets/oriented_view.dart';

void main() {
  test('orientation from telemetry', () {
    final v = ViewOrientation.fromJson({'rotateDeg': 270, 'mirror': true});
    expect(v.quarterTurns, 3);
    expect(v.mirror, isTrue);
    expect(ViewOrientation.fromJson(null), const ViewOrientation());
    expect(Telemetry.fromJson({}).view, const ViewOrientation());
  });

  // A 400 × 800 portrait screen; markers placed in the camera's frame.
  Future<Offset> whereIs(
    WidgetTester tester,
    ViewOrientation view,
    Alignment inFrame,
  ) async {
    tester.view.physicalSize = const Size(400, 800);
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.reset);
    await tester.pumpWidget(Directionality(
      textDirection: TextDirection.ltr,
      child: OrientedView(
        view: view,
        child: Stack(
          fit: StackFit.expand,
          children: [
            Align(
              alignment: inFrame,
              child: const SizedBox.square(
                key: ValueKey('mark'),
                dimension: 10,
              ),
            ),
          ],
        ),
      ),
    ));
    final c = tester.getCenter(find.byKey(const ValueKey('mark')));
    return Offset((c.dx / 200 - 1).roundToDouble(), (c.dy / 400 - 1).roundToDouble());
  }

  testWidgets('the bench rig: what came out on the right stands at the top',
      (tester) async {
    const rig = ViewOrientation(quarterTurns: 3, mirror: true);
    // the head, at the right of the sideways frame → top centre
    expect(await whereIs(tester, rig, Alignment.centerRight), const Offset(0, -1));
    // the frame's top-left → bottom-right (a reflection across the diagonal)
    expect(await whereIs(tester, rig, Alignment.topLeft), const Offset(1, 1));
    // its top centre (left of the upright picture, mirrored) → right
    expect(await whereIs(tester, rig, Alignment.topCenter), const Offset(1, 0));
  });

  testWidgets('a camera that says nothing is shown as it comes',
      (tester) async {
    expect(
      await whereIs(tester, const ViewOrientation(), Alignment.topLeft),
      const Offset(-1, -1),
    );
  });
}
