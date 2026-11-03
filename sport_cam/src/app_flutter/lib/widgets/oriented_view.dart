import 'package:flutter/material.dart';

import '../models.dart';

/// Turns [child] (the live picture and its boxes) as the camera says: a
/// quarter turn on its mount comes out sideways, so turn it [view]'s
/// quarter turns clockwise, then mirror it left-right.
///
/// The mirror goes outside the turn: turning then mirroring is not the same
/// as mirroring then turning when the turn is a quarter.
class OrientedView extends StatelessWidget {
  const OrientedView({super.key, required this.view, required this.child});

  final ViewOrientation view;
  final Widget child;

  @override
  Widget build(BuildContext context) {
    Widget w = view.quarterTurns == 0
        ? child
        : RotatedBox(quarterTurns: view.quarterTurns, child: child);
    if (view.mirror) w = Transform.flip(flipX: true, child: w);
    return w;
  }
}
