import 'package:flutter/material.dart';

import '../models.dart';
import '../theme.dart';

/// Bottom buttons — same rules as the web app (the awake label depends on the
/// build, see [ModeText]):
///   off       → none (the camera is still booting)
///   sleep     → Wake up · Record (skips awake: straight into the search)
///   awake     → Sleep · Start tracking | Track & record
///   tracking  → Sleep · Stop tracking (search → found → recording runs by itself)
///   recording → Sleep · Stop recording (saves the clip, back to awake)
class ControlBar extends StatelessWidget {
  const ControlBar({
    super.key,
    required this.state,
    this.text = ModeText.withUwb,
    required this.enabled,
    required this.onSetPower,
    required this.onStartTracking,
    required this.onStopTracking,
    required this.onStopRecording,
  });

  final CamState state;
  final ModeText text;
  final bool enabled;
  final void Function(bool on) onSetPower;
  final VoidCallback onStartTracking;
  final VoidCallback onStopTracking;
  final VoidCallback onStopRecording;

  @override
  Widget build(BuildContext context) {
    final (String? leftLabel, VoidCallback? leftAction) = switch (state) {
      CamState.off => (null, null),
      CamState.sleep => ('Wake up', () => onSetPower(true)),
      CamState.awake => ('Sleep', () => onSetPower(false)),
      CamState.tracking => ('Sleep', () => onSetPower(false)),
      CamState.recording => ('Sleep', () => onSetPower(false)),
    };
    final (String? rightLabel, VoidCallback? rightAction) = switch (state) {
      CamState.off => (null, null),
      CamState.sleep => ('Record', onStartTracking),
      CamState.awake => (text.startTracking, onStartTracking),
      CamState.tracking => ('Stop tracking', onStopTracking),
      CamState.recording => ('Stop recording', onStopRecording),
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
          if (leftLabel != null)
            Expanded(
              child: _Btn(
                label: leftLabel,
                onTap: enabled ? leftAction : null,
                background: SportColors.panel,
                foreground: SportColors.ink,
                border: SportColors.border,
              ),
            ),
          if (rightLabel != null) ...[
            const SizedBox(width: 10),
            Expanded(
              child: _Btn(
                label: rightLabel,
                onTap: enabled ? rightAction : null,
                // Record from sleep starts a recording session: red
                background: state == CamState.sleep
                    ? SportColors.recording
                    : SportColors.forState(state),
                foreground: Colors.white,
              ),
            ),
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
