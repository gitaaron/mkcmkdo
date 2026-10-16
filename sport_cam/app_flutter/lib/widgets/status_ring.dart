import 'package:flutter/material.dart';

import '../models.dart';
import '../theme.dart';

/// Top-right camera-state indicator — same colours as the LED ring on the
/// base: blue idle, green tracking (blinking while it acquires the subject),
/// pulsing red while recording.
class StatusRing extends StatefulWidget {
  const StatusRing({
    super.key,
    required this.state,
    required this.connected,
    this.acquiring = false,
  });

  final CamState state;
  final bool connected;
  final bool acquiring;

  @override
  State<StatusRing> createState() => _StatusRingState();
}

class _StatusRingState extends State<StatusRing>
    with SingleTickerProviderStateMixin {
  late final AnimationController _pulse = AnimationController(
    vsync: this,
    duration: const Duration(milliseconds: 1200),
  );

  @override
  void initState() {
    super.initState();
    _syncAnimation();
  }

  @override
  void didUpdateWidget(StatusRing old) {
    super.didUpdateWidget(old);
    _syncAnimation();
  }

  void _syncAnimation() {
    // Acquiring blinks fast; recording breathes slowly, like the LED ring.
    final period = Duration(milliseconds: widget.acquiring ? 500 : 1200);
    if (_pulse.duration != period) {
      _pulse
        ..stop()
        ..duration = period;
    }
    if (widget.state == CamState.recording || widget.acquiring) {
      if (!_pulse.isAnimating) _pulse.repeat(reverse: true);
    } else {
      _pulse
        ..stop()
        ..value = 1.0;
    }
  }

  @override
  void dispose() {
    _pulse.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final color = SportColors.forState(widget.state);
    return Semantics(
      label:
          'Camera status: '
          '${widget.acquiring ? 'Acquiring subject' : stateLabel(widget.state)}',
      child: FadeTransition(
        opacity: _pulse,
        child: Container(
          width: 26,
          height: 26,
          decoration: BoxDecoration(
            // hollow while disconnected — matches the web app's behaviour
            color: widget.connected ? color : Colors.transparent,
            shape: BoxShape.circle,
            border: Border.all(
              color: widget.connected
                  ? Colors.white.withValues(alpha: 0.85)
                  : color,
              width: 3,
            ),
            boxShadow: [
              BoxShadow(color: color.withValues(alpha: 0.55), blurRadius: 12),
            ],
          ),
        ),
      ),
    );
  }
}
