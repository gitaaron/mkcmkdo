import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:sportcam/widgets/joystick.dart';

void main() {
  // 132 px ring, knob radius 0.21 × 132: the knob's centre travels 38.28 px
  const size = 132.0;
  const travel = size / 2 - size * 0.21;

  late List<Offset> sent;

  Future<Offset> centre(WidgetTester tester) async {
    sent = [];
    await tester.pumpWidget(MaterialApp(
      home: Scaffold(
        body: Center(
          child: Joystick(onMove: (x, y) => sent.add(Offset(x, y))),
        ),
      ),
    ));
    return tester.getCenter(find.byType(Joystick));
  }

  testWidgets('pull left pans left, pull up tilts up', (tester) async {
    final c = await centre(tester);
    final g = await tester.startGesture(c);
    await g.moveTo(c + const Offset(-travel, 0));
    await tester.pump(const Duration(milliseconds: 60));
    expect(sent.last.dx, closeTo(-1, 1e-9));
    expect(sent.last.dy, closeTo(0, 1e-9));

    await g.moveTo(c + const Offset(0, -travel / 2)); // screen up
    await tester.pump(const Duration(milliseconds: 60));
    expect(sent.last.dx, closeTo(0, 1e-9));
    expect(sent.last.dy, closeTo(0.5, 1e-9));
    await g.up();
  });

  testWidgets('a pull past the rim counts as the rim', (tester) async {
    final c = await centre(tester);
    final g = await tester.startGesture(c);
    await g.moveTo(c + const Offset(300, 300));
    await tester.pump(const Duration(milliseconds: 60));
    expect(sent.last.distance, closeTo(1, 1e-9));
    expect(sent.last.dx, greaterThan(0)); // right
    expect(sent.last.dy, lessThan(0)); // and down
    await g.up();
  });

  testWidgets('keeps sending while held, stops with (0, 0) on release',
      (tester) async {
    final c = await centre(tester);
    final g = await tester.startGesture(c);
    await g.moveTo(c + const Offset(travel / 2, 0));
    final before = sent.length;
    await tester.pump(const Duration(milliseconds: 500)); // finger still
    expect(sent.length - before, greaterThanOrEqualTo(9)); // every 50 ms

    await g.up();
    await tester.pump();
    expect(sent.last, Offset.zero);
    final after = sent.length;
    await tester.pump(const Duration(milliseconds: 500));
    expect(sent.length, after); // nothing more once let go
  });

  testWidgets('removed while held: the camera is told to stop',
      (tester) async {
    final c = await centre(tester);
    final g = await tester.startGesture(c);
    await g.moveTo(c + const Offset(travel, 0));
    await tester.pump(const Duration(milliseconds: 60));
    await tester.pumpWidget(const MaterialApp(home: SizedBox()));
    expect(sent.last, Offset.zero);
    await g.up();
  });
}
