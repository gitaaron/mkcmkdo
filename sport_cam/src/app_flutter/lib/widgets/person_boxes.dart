import 'package:flutter/material.dart';

import '../models.dart';
import '../theme.dart';

/// Box colours: green for the climber, yellow for anyone else, red while
/// the camera can't tell which is the climber. As in the web app.
const boxColours = {
  BoxLabel.climber: Color(0xFF34C759),
  BoxLabel.other: Color(0xFFFFCC00),
  BoxLabel.unsure: Color(0xFFFF3B30),
};

/// Stroke [boxes], measured in a [frameW] × [frameH] frame, over [picture]:
/// where that frame is drawn on the canvas.
void paintBoxes(
  Canvas canvas,
  Rect picture,
  double frameW,
  double frameH,
  List<PersonBox> boxes,
) {
  final sx = picture.width / frameW;
  final sy = picture.height / frameH;
  for (final b in boxes) {
    final paint = Paint()
      ..style = PaintingStyle.stroke
      ..strokeWidth = 2.5
      ..color = boxColours[b.label]!;
    canvas.drawRect(
      Rect.fromLTWH(
        picture.left + b.x * sx,
        picture.top + b.y * sy,
        b.w * sx,
        b.h * sy,
      ),
      paint,
    );
  }
}

/// The live view's boxes, over a picture drawn with [BoxFit.contain] (the
/// live frames have the boxes' frame's shape, so that is where it sits).
class LiveBoxesPainter extends CustomPainter {
  LiveBoxesPainter(this.live);

  final LiveBoxes live;

  @override
  void paint(Canvas canvas, Size size) {
    final fitted = applyBoxFit(
      BoxFit.contain,
      Size(live.width, live.height),
      size,
    ).destination;
    final picture = Alignment.center.inscribe(fitted, Offset.zero & size);
    paintBoxes(canvas, picture, live.width, live.height, live.boxes);
  }

  @override
  bool shouldRepaint(LiveBoxesPainter old) => old.live != live;
}

/// What the colours mean.
class BoxLegend extends StatelessWidget {
  const BoxLegend({super.key});

  @override
  Widget build(BuildContext context) {
    Widget key(BoxLabel l, String text) => Row(
      mainAxisSize: MainAxisSize.min,
      children: [
        Container(
          width: 12,
          height: 12,
          decoration: BoxDecoration(
            border: Border.all(color: boxColours[l]!, width: 2),
          ),
        ),
        const SizedBox(width: 6),
        Text(
          text,
          style: const TextStyle(color: SportColors.muted, fontSize: 12.5),
        ),
      ],
    );
    return Wrap(
      spacing: 14,
      children: [
        key(BoxLabel.climber, 'climber'),
        key(BoxLabel.other, 'someone else'),
        key(BoxLabel.unsure, "can't tell yet"),
      ],
    );
  }
}
