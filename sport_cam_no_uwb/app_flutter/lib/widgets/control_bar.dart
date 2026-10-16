import 'package:flutter/material.dart';

import '../models.dart';
import '../theme.dart';

/// Bottom buttons — same rules as the LED/web app:
///   idle      → Turn off      · Track & record (sweeps, locks on, records)
///   tracking  → Turn off      · Record now
///   recording → Stop recording · Stop tracking (confirms; it ends the clip)
class ControlBar extends StatelessWidget {
  const ControlBar({
    super.key,
    required this.state,
    required this.enabled,
    required this.onSetPower,
    required this.onStartTracking,
    required this.onStopTracking,
    required this.onStartRecording,
    required this.onStopRecording,
  });

  final CamState state;
  final bool enabled;
  final void Function(bool on) onSetPower;
  final VoidCallback onStartTracking;
  final VoidCallback onStopTracking;
  final VoidCallback onStartRecording;
  final VoidCallback onStopRecording;

  Future<void> _confirmStopTracking(BuildContext context) async {
    final ok = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        backgroundColor: SportColors.panel,
        title: const Text('Stop tracking?'),
        content: const Text('This also stops and saves the recording.'),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(ctx, false),
            child: const Text('Cancel'),
          ),
          TextButton(
            onPressed: () => Navigator.pop(ctx, true),
            child: const Text('Stop'),
          ),
        ],
      ),
    );
    if (ok ?? false) onStopTracking();
  }

  @override
  Widget build(BuildContext context) {
    final (String leftLabel, VoidCallback leftAction) = switch (state) {
      CamState.off => ('Turn on', () => onSetPower(true)),
      CamState.idle => ('Turn off', () => onSetPower(false)),
      CamState.tracking => ('Turn off', () => onSetPower(false)),
      CamState.recording => ('Stop recording', onStopRecording),
    };
    final (String? rightLabel, VoidCallback? rightAction) = switch (state) {
      CamState.off => (null, null),
      CamState.idle => ('Track & record', onStartTracking),
      CamState.tracking => ('Record now', onStartRecording),
      CamState.recording => (
        'Stop tracking',
        () => _confirmStopTracking(context),
      ),
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
                background: SportColors.forState(state),
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
