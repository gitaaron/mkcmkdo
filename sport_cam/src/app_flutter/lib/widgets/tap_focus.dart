import 'dart:async';

import 'package:flutter/material.dart';

import '../theme.dart';

/// Where a tap at [tap] in a [box] lands on a [frame] drawn there with
/// [BoxFit.contain]: each 0…1 of the frame, or null outside the picture.
Offset? frameFraction(Offset tap, Size box, Size frame) {
  final fitted = applyBoxFit(BoxFit.contain, frame, box).destination;
  final picture = Alignment.center.inscribe(fitted, Offset.zero & box);
  if (!picture.contains(tap)) return null;
  return Offset(
    (tap.dx - picture.left) / picture.width,
    (tap.dy - picture.top) / picture.height,
  );
}

/// Tap the live view to focus there: sends the point as a share of the
/// camera's [frameSize] frame to [onFocus], and shows a square where you
/// tapped, blue while the camera is [focusing], green once it is done.
///
/// Goes inside the live view's [OrientedView], with the picture: the tap
/// position is then already in the camera's own frame, however the view is
/// turned or mirrored.
class TapToFocus extends StatefulWidget {
  const TapToFocus({
    super.key,
    required this.frameSize,
    required this.focusing,
    required this.onFocus,
    this.hold = const Duration(milliseconds: 1500),
  });

  final Size frameSize;
  final bool focusing;
  final void Function(double x, double y) onFocus;

  /// The square stays at least this long, and while the camera focuses.
  final Duration hold;

  @override
  State<TapToFocus> createState() => _TapToFocusState();
}

class _TapToFocusState extends State<TapToFocus> {
  Offset? _at; // where the square is, in this widget
  bool _fresh = false; // tapped within [hold]
  Timer? _timer;

  void _tap(Offset local, Size box) {
    final f = frameFraction(local, box, widget.frameSize);
    if (f == null) return;
    widget.onFocus(f.dx, f.dy);
    _timer?.cancel();
    _timer = Timer(widget.hold, () {
      if (mounted) setState(() => _fresh = false);
    });
    setState(() {
      _at = local;
      _fresh = true;
    });
  }

  @override
  void dispose() {
    _timer?.cancel();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final show = _at != null && (_fresh || widget.focusing);
    return LayoutBuilder(
      builder: (context, box) => GestureDetector(
        behavior: HitTestBehavior.translucent,
        onTapUp: (d) => _tap(d.localPosition, box.biggest),
        child: Stack(
          fit: StackFit.expand,
          children: [
            if (show)
              Positioned(
                left: _at!.dx - 36,
                top: _at!.dy - 36,
                child: IgnorePointer(
                  child: Container(
                    key: const ValueKey('focus-square'),
                    width: 72,
                    height: 72,
                    decoration: BoxDecoration(
                      border: Border.all(
                        color: widget.focusing
                            ? SportColors.awake
                            : SportColors.tracking,
                        width: 2,
                      ),
                      borderRadius: BorderRadius.circular(6),
                    ),
                  ),
                ),
              ),
          ],
        ),
      ),
    );
  }
}
