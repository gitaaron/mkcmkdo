import 'dart:async';

import 'package:flutter/material.dart';

import '../theme.dart';

/// Aim the camera by hand: a knob inside a ring. Pull the knob and the camera
/// turns that way (left pans left, up tilts up); the further from the centre,
/// the faster. Let go and the knob springs back and the camera stops.
///
/// While held it reports the knob's offset to [onMove] every [period], even
/// with the finger still: x right +, y up +, each a fraction of how far the
/// knob can travel (so the rim is 1). The camera stops by itself when the
/// reports stop (`JOG_TIMEOUT_S`), so a dropped connection can't leave it
/// turning. Releasing sends one (0, 0).
class Joystick extends StatefulWidget {
  const Joystick({
    super.key,
    required this.onMove,
    this.size = 132,
    this.period = const Duration(milliseconds: 50),
  });

  final void Function(double x, double y) onMove;
  final double size;
  final Duration period;

  @override
  State<Joystick> createState() => _JoystickState();
}

class _JoystickState extends State<Joystick> {
  Offset _knob = Offset.zero; // knob centre from the ring's centre, px
  int? _pointer; // the finger driving it; others are ignored
  Timer? _timer;

  double get _ringR => widget.size / 2;
  double get _knobR => widget.size * 0.21;
  double get _travel => _ringR - _knobR;

  void _down(PointerDownEvent e) {
    if (_pointer != null) return;
    _pointer = e.pointer;
    _place(e.localPosition);
    _send();
    _timer = Timer.periodic(widget.period, (_) => _send());
  }

  void _moveTo(PointerMoveEvent e) {
    if (e.pointer == _pointer) _place(e.localPosition);
  }

  void _up(PointerEvent e) {
    if (e.pointer != _pointer) return;
    _release();
    setState(() => _knob = Offset.zero);
  }

  void _place(Offset local) {
    var o = local - Offset(_ringR, _ringR);
    if (o.distance > _travel) o = o / o.distance * _travel;
    setState(() => _knob = o);
  }

  void _send() => widget.onMove(_knob.dx / _travel, -_knob.dy / _travel);

  void _release() {
    _timer?.cancel();
    _timer = null;
    _pointer = null;
    widget.onMove(0, 0);
  }

  @override
  void dispose() {
    // taken off screen while held (the camera left awake): stop it now
    if (_pointer != null) _release();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final held = _pointer != null;
    return Semantics(
      label: 'Aim the camera: drag the knob, further for faster',
      child: Listener(
        behavior: HitTestBehavior.opaque,
        onPointerDown: _down,
        onPointerMove: _moveTo,
        onPointerUp: _up,
        onPointerCancel: _up,
        child: SizedBox.square(
          dimension: widget.size,
          child: Stack(
            alignment: Alignment.center,
            children: [
              Container(
                decoration: BoxDecoration(
                  shape: BoxShape.circle,
                  color: SportColors.panel.withValues(alpha: 0.55),
                  border: Border.all(
                    color: held ? SportColors.awake : SportColors.border,
                    width: 2,
                  ),
                ),
              ),
              Transform.translate(
                offset: _knob,
                child: Container(
                  width: _knobR * 2,
                  height: _knobR * 2,
                  decoration: BoxDecoration(
                    shape: BoxShape.circle,
                    color: held
                        ? SportColors.awake
                        : SportColors.ink.withValues(alpha: 0.85),
                    boxShadow: const [
                      BoxShadow(color: Colors.black45, blurRadius: 6),
                    ],
                  ),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
