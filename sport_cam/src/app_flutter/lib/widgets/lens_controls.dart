import 'dart:async';

import 'package:flutter/material.dart';

import '../models.dart';
import '../theme.dart';

/// Zoom and focus by hand: two sliders above the aim sticks, awake only.
///
/// Zoom runs wide → tele and reads as a multiple of the widest view. Focus
/// moves the focus motor across its travel (0–100 %): you focus by eye,
/// watching the picture. Until the camera's focus is calibrated
/// (`focuscal`), a distance would mean nothing to it.
///
/// While a slider moves it reports at most once per [period], and once more
/// where it was let go. The camera reports the lens back about once a
/// second; until then the slider stays where the finger left it.
class LensControls extends StatelessWidget {
  const LensControls({
    super.key,
    required this.lens,
    required this.onZoom,
    required this.onFocus,
    this.period = const Duration(milliseconds: 120),
  });

  final Lens lens;
  final void Function(double zoomMm) onZoom;
  final void Function(double focusPos) onFocus;
  final Duration period;

  @override
  Widget build(BuildContext context) {
    final l = lens;
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
      decoration: BoxDecoration(
        color: SportColors.panel.withValues(alpha: 0.7),
        borderRadius: BorderRadius.circular(14),
        border: Border.all(color: SportColors.border),
      ),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          LensSlider(
            key: const ValueKey('zoom'),
            icon: Icons.zoom_in,
            name: 'Zoom',
            value: l.zoomMm,
            min: l.zoomMinMm,
            max: l.zoomMaxMm,
            label: (mm) => '${(mm / l.zoomMinMm).toStringAsFixed(1)}×',
            period: period,
            onSend: onZoom,
          ),
          LensSlider(
            key: const ValueKey('focus'),
            icon: Icons.center_focus_strong,
            name: 'Focus',
            // unknown until the camera has moved it: at its low stop, where
            // waking the lens leaves it
            value: l.focusPos ?? 0,
            min: 0,
            max: 1,
            label: (t) => '${(t * 100).round()}%',
            period: period,
            onSend: onFocus,
          ),
        ],
      ),
    );
  }
}

/// One slider of [LensControls]: shows the camera's [value] unless a finger
/// has moved it in the last [settle], and sends what the finger asks for,
/// throttled to one per [period].
class LensSlider extends StatefulWidget {
  const LensSlider({
    super.key,
    required this.icon,
    required this.name,
    required this.value,
    required this.min,
    required this.max,
    required this.label,
    required this.onSend,
    this.period = const Duration(milliseconds: 120),
    this.settle = const Duration(milliseconds: 1500),
  });

  final IconData icon;
  final String name;
  final double value;
  final double min;
  final double max;
  final String Function(double) label;
  final void Function(double) onSend;
  final Duration period;
  final Duration settle;

  @override
  State<LensSlider> createState() => _LensSliderState();
}

class _LensSliderState extends State<LensSlider> {
  double? _local; // where the finger put it, until the camera catches up
  double? _pending; // moved since the last send
  Timer? _throttle;
  Timer? _settle;

  void _start(double v) {
    _settle?.cancel();
    _settle = null;
  }

  void _changed(double v) {
    setState(() => _local = v);
    _pending = v;
    if (_throttle != null) return;
    _flush();
    _throttle = Timer.periodic(widget.period, (_) {
      if (_pending == null) {
        _throttle?.cancel();
        _throttle = null;
      } else {
        _flush();
      }
    });
  }

  void _end(double v) {
    _pending = v;
    _flush();
    _settle = Timer(widget.settle, () {
      if (mounted) setState(() => _local = null);
    });
  }

  void _flush() {
    final v = _pending;
    _pending = null;
    if (v != null) widget.onSend(v);
  }

  @override
  void dispose() {
    _throttle?.cancel();
    _settle?.cancel();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final shown = (_local ?? widget.value).clamp(widget.min, widget.max);
    final text = widget.label(shown);
    return Row(
      children: [
        Icon(widget.icon, size: 18, color: SportColors.ink),
        Expanded(
          child: SliderTheme(
            data: SliderTheme.of(context).copyWith(
              activeTrackColor: SportColors.awake,
              inactiveTrackColor: SportColors.border,
              thumbColor: _local != null ? SportColors.awake : SportColors.ink,
              overlayColor: SportColors.awake.withValues(alpha: 0.2),
              trackHeight: 3,
            ),
            child: Slider(
              value: shown,
              min: widget.min,
              max: widget.max,
              onChangeStart: _start,
              onChanged: _changed,
              onChangeEnd: _end,
              semanticFormatterCallback: (v) =>
                  '${widget.name} ${widget.label(v)}',
            ),
          ),
        ),
        SizedBox(
          width: 44,
          child: Text(
            text,
            textAlign: TextAlign.right,
            style: const TextStyle(
              fontSize: 12.5,
              color: SportColors.ink,
              fontFeatures: [FontFeature.tabularFigures()],
            ),
          ),
        ),
      ],
    );
  }
}
