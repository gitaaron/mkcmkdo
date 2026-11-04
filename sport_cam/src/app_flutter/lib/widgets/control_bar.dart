import 'package:flutter/material.dart';

import '../models.dart';
import '../theme.dart';

/// Bottom buttons (the awake label depends on the build, see [ModeText]):
///   off       → none (the camera is still booting)
///   sleep     → Wake up · Track (skips awake: straight into the search)
///   awake     → Sleep · Start tracking
///   tracking  → Sleep · Stop tracking · Record (follows the person; Record
///               only once the camera has seen someone lately, [canRecord])
///   recording → Stop recording (saves the clip, back to tracking)
///
/// A recording starts only from tracking, and stops only back to it.
///
/// [locked]: the session running is someone else's — only the phone that
/// started it can advance or stop it (or put the camera to sleep), so all
/// its buttons are off.
class ControlBar extends StatelessWidget {
  const ControlBar({
    super.key,
    required this.state,
    this.text = ModeText.withUwb,
    required this.enabled,
    this.locked = false,
    this.canRecord = true,
    required this.onSetPower,
    required this.onStartTracking,
    required this.onStopTracking,
    required this.onStartRecording,
    required this.onStopRecording,
  });

  final CamState state;
  final ModeText text;
  final bool enabled;
  final bool locked;
  final bool canRecord;
  final void Function(bool on) onSetPower;
  final VoidCallback onStartTracking;
  final VoidCallback onStopTracking;
  final VoidCallback onStartRecording;
  final VoidCallback onStopRecording;

  @override
  Widget build(BuildContext context) {
    final inSession = state == CamState.tracking || state == CamState.recording;
    final active = enabled && !(locked && inSession);
    VoidCallback? on(VoidCallback f, [bool allowed = true]) =>
        active && allowed ? f : null;
    _Btn quiet(String label, VoidCallback? onTap) => _Btn(
      label: label,
      onTap: onTap,
      background: SportColors.panel,
      foreground: SportColors.ink,
      border: SportColors.border,
    );
    final buttons = switch (state) {
      CamState.off => const <_Btn>[],
      CamState.sleep => [
        quiet('Wake up', on(() => onSetPower(true))),
        _Btn(
          label: 'Track',
          onTap: on(onStartTracking),
          background: SportColors.tracking,
          foreground: Colors.white,
        ),
      ],
      CamState.awake => [
        quiet('Sleep', on(() => onSetPower(false))),
        _Btn(
          label: text.startTracking,
          onTap: on(onStartTracking),
          background: SportColors.tracking,
          foreground: Colors.white,
        ),
      ],
      CamState.tracking => [
        quiet('Sleep', on(() => onSetPower(false))),
        quiet('Stop tracking', on(onStopTracking)),
        _Btn(
          label: 'Record',
          onTap: on(onStartRecording, canRecord),
          background: SportColors.recording,
          foreground: Colors.white,
        ),
      ],
      CamState.recording => [
        _Btn(
          label: 'Stop recording',
          onTap: on(onStopRecording),
          background: SportColors.recording,
          foreground: Colors.white,
        ),
      ],
    };

    return Container(
      padding: EdgeInsets.fromLTRB(
        14,
        14,
        14,
        14 + MediaQuery.of(context).padding.bottom,
      ),
      decoration: const BoxDecoration(
        gradient: LinearGradient(
          begin: Alignment.topCenter,
          end: Alignment.bottomCenter,
          colors: [Colors.transparent, Color(0xE60D1420)],
        ),
      ),
      child: Row(
        children: [
          for (final (i, b) in buttons.indexed) ...[
            if (i > 0) const SizedBox(width: 10),
            Expanded(child: b),
          ],
        ],
      ),
    );
  }
}

class _Btn extends StatelessWidget {
  const _Btn({
    required this.label,
    required this.onTap,
    required this.background,
    required this.foreground,
    this.border,
  });

  final String label;
  final VoidCallback? onTap;
  final Color background;
  final Color foreground;
  final Color? border;

  @override
  Widget build(BuildContext context) {
    final disabled = onTap == null;
    return Opacity(
      opacity: disabled ? 0.5 : 1,
      child: Material(
        color: background,
        borderRadius: BorderRadius.circular(12),
        child: InkWell(
          onTap: onTap,
          borderRadius: BorderRadius.circular(12),
          child: Container(
            height: 54,
            alignment: Alignment.center,
            decoration: BoxDecoration(
              borderRadius: BorderRadius.circular(12),
              border: border == null ? null : Border.all(color: border!),
            ),
            child: Text(
              label,
              textAlign: TextAlign.center,
              style: TextStyle(
                color: foreground,
                fontSize: 16,
                fontWeight: FontWeight.w600,
              ),
            ),
          ),
        ),
      ),
    );
  }
}
