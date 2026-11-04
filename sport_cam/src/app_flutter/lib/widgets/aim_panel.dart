import 'package:flutter/material.dart';

import '../models.dart';
import '../theme.dart';
import 'joystick.dart';
import 'lens_controls.dart';

/// The awake controls — the zoom slider over the pan and tilt sticks — that
/// rise out of the bottom bar when [open] and sink back into it when not.
/// Closed, they let taps through to the picture (and to tap-to-focus).
class AimPanel extends StatelessWidget {
  const AimPanel({
    super.key,
    required this.open,
    required this.lens,
    required this.onZoom,
    required this.onAim,
    this.duration = const Duration(milliseconds: 260),
  });

  final bool open;
  final Lens lens;
  final void Function(double zoomMm) onZoom;
  final void Function(double pan, double tilt) onAim;
  final Duration duration;

  @override
  Widget build(BuildContext context) {
    return IgnorePointer(
      ignoring: !open,
      child: AnimatedSlide(
        offset: open ? Offset.zero : const Offset(0, 0.5),
        duration: duration,
        curve: Curves.easeOutCubic,
        child: AnimatedOpacity(
          opacity: open ? 1 : 0,
          duration: duration,
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              LensControls(lens: lens, onZoom: onZoom),
              const SizedBox(height: 12),
              AimSticks(onMove: onAim),
            ],
          ),
        ),
      ),
    );
  }
}

/// The arrow on the bottom bar that brings the [AimPanel] up (pointing up)
/// and puts it away (pointing down).
class AimToggle extends StatelessWidget {
  const AimToggle({super.key, required this.open, required this.onTap});

  final bool open;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return Semantics(
      button: true,
      label: open ? 'Hide the aim and zoom controls' : 'Show the aim and zoom controls',
      child: GestureDetector(
        onTap: onTap,
        child: Container(
          width: 52,
          height: 30,
          decoration: BoxDecoration(
            color: SportColors.panel.withValues(alpha: 0.9),
            borderRadius: BorderRadius.circular(15),
            border: Border.all(color: SportColors.border),
          ),
          child: AnimatedRotation(
            turns: open ? 0.5 : 0,
            duration: const Duration(milliseconds: 260),
            child: const Icon(Icons.keyboard_arrow_up, color: SportColors.ink, size: 24),
          ),
        ),
      ),
    );
  }
}
