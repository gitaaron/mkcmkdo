import 'package:flutter/material.dart';

import '../models.dart';
import '../theme.dart';

/// Top-right camera-state indicator — same colours and patterns as the LED
/// ring on the base, per sub-state (telemetry `phase`):
///   sleep      dim blue-grey, solid (the LED shows one dim pixel)
///   awake       blue: solid, or breathing slowly with a person in frame
///   tracking   green: blinking in search (turning to the tag with UWB,
///              sweeping the room without); solid when found, counting down
///   recording  solid red
class StatusRing extends StatefulWidget {
  const StatusRing({
    super.key,
    required this.state,
    required this.connected,
    this.searchingLabel = 'Looking for a person',
    this.phase,
    this.countdown = 0,
  });

  final CamState state;
  final bool connected;
  final String searchingLabel;
  final String? phase;
  final int countdown; // found: seconds left before recording

  bool get searching => state == CamState.tracking && phase == 'search';
  bool get found => state == CamState.tracking && phase == 'found';
  bool get awakePerson => state == CamState.awake && phase == 'person-in-frame';

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
    // Search blinks fast; awake with a person in frame
    // breathes slowly — like the LED ring.
    final period = Duration(
      milliseconds: widget.searching
          ? 500
          : widget.awakePerson
          ? 2400
          : 1200,
    );
    if (_pulse.duration != period) {
      _pulse
        ..stop()
        ..duration = period;
    }
    if (widget.searching || widget.awakePerson) {
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

  String get _stateLabel {
    if (widget.state == CamState.awake) return awakeLabel(widget.phase);
    if (widget.searching) return widget.searchingLabel;
    if (widget.found) {
      final n = widget.countdown > 0 ? widget.countdown : 1;
      return 'Found you — recording in $n';
    }
    return stateLabel(widget.state);
  }

  @override
  Widget build(BuildContext context) {
    final color = SportColors.forState(widget.state);
    return Semantics(
      label:
          'Camera status: '
          '$_stateLabel',
      child: FadeTransition(
        opacity: _pulse,
        child: Container(
          width: 26,
          height: 26,
          decoration: BoxDecoration(
            // hollow while disconnected
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
