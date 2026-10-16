import 'package:flutter/material.dart';

import '../camera_client.dart';
import '../models.dart';
import '../theme.dart';
import '../widgets/connection_badge.dart';
import '../widgets/control_bar.dart';
import '../widgets/mjpeg_view.dart';
import '../widgets/status_ring.dart';
import 'library_screen.dart';

/// The single screen: live video, connection badge (top-left), camera-state
/// ring (top-right), state-dependent controls at the bottom.
///
/// Opening the app starts streaming — discovery runs on launch and the
/// video view attaches as soon as a camera answers.
class HomeScreen extends StatefulWidget {
  const HomeScreen({super.key, required this.client});

  final CameraClient client;

  @override
  State<HomeScreen> createState() => _HomeScreenState();
}

class _HomeScreenState extends State<HomeScreen> {
  CameraClient get client => widget.client;

  @override
  void initState() {
    super.initState();
    client.addListener(_onChange);
    client.connect();
  }

  void _onChange() => setState(() {});

  @override
  void dispose() {
    client.removeListener(_onChange);
    super.dispose();
  }

  void _openLibrary() {
    final base = client.base;
    if (base == null) return;
    client.dismissToast();
    Navigator.of(context).push(
      MaterialPageRoute<void>(
        builder: (_) =>
            LibraryScreen(recordings: client.recordings, base: base),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final top = MediaQuery.of(context).padding.top;
    final upload = client.upload;
    final saved = client.justSaved;

    return Scaffold(
      body: Stack(
        fit: StackFit.expand,
        children: [
          MjpegView(
            streamUrl: client.streamUrl,
            active: client.isConnected && client.state != CamState.off,
          ),

          // top-left: connection status to the camera
          Positioned(
            top: top + 10,
            left: 14,
            child: ConnectionBadge(
              link: client.link,
              endpoint: client.endpoint,
              onTap: client.connect,
            ),
          ),

          // top-right: camera state (same colours as the LED ring)
          Positioned(
            top: top + 14,
            right: 14,
            child: StatusRing(
              state: client.state,
              connected: client.isConnected,
              acquiring:
                  client.state == CamState.tracking &&
                  client.telemetry.phase == 'acquiring',
            ),
          ),

          // recordings
          Positioned(
            top: top + 62,
            left: 14,
            child: _LibraryButton(
              count: client.recordings.length,
              onTap: _openLibrary,
            ),
          ),

          // acquiring for a while and vision still cannot see the climber
          if (client.state == CamState.tracking &&
              client.telemetry.acquireStalled)
            const _Pill(
              text: "Can't see you — step into view, facing the camera",
              accent: SportColors.tracking,
              alignment: Alignment(0, -0.78),
            ),

          if (upload != null)
            _Pill(text: 'Uploading… ${(upload.fraction * 100).round()}%')
          else if (saved != null)
            _Pill(
              text: 'Recording saved — watch now',
              accent: SportColors.tracking,
              onTap: _openLibrary,
            ),

          Align(
            alignment: Alignment.bottomCenter,
            child: ControlBar(
              state: client.state,
              enabled: client.isConnected,
              onSetPower: client.setPower,
              onStartTracking: client.startTracking,
              onStopTracking: client.stopTracking,
              onStartRecording: client.startRecording,
              onStopRecording: client.stopRecording,
            ),
          ),
        ],
      ),
    );
  }
}

class _LibraryButton extends StatelessWidget {
  const _LibraryButton({required this.count, required this.onTap});

  final int count;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTap: onTap,
      child: Stack(
        clipBehavior: Clip.none,
        children: [
          Container(
            width: 40,
            height: 40,
            decoration: BoxDecoration(
              color: SportColors.panel.withValues(alpha: 0.85),
              borderRadius: BorderRadius.circular(12),
              border: Border.all(color: SportColors.border),
            ),
            child: const Icon(
              Icons.video_library_outlined,
              size: 19,
              color: SportColors.ink,
            ),
          ),
          if (count > 0)
            Positioned(
              top: -5,
              right: -5,
              child: Container(
                padding: const EdgeInsets.symmetric(horizontal: 5, vertical: 1),
                decoration: BoxDecoration(
                  color: SportColors.idle,
                  borderRadius: BorderRadius.circular(9),
                ),
                child: Text(
                  '$count',
                  style: const TextStyle(fontSize: 10.5, color: Colors.white),
                ),
              ),
            ),
        ],
      ),
    );
  }
}

class _Pill extends StatelessWidget {
  const _Pill({
    required this.text,
    this.accent,
    this.onTap,
    this.alignment = const Alignment(0, 0.72),
  });

  final String text;
  final Color? accent;
  final VoidCallback? onTap;
  final Alignment alignment;

  @override
  Widget build(BuildContext context) {
    return Align(
      alignment: alignment,
      child: GestureDetector(
        onTap: onTap,
        child: Container(
          padding: const EdgeInsets.symmetric(horizontal: 18, vertical: 9),
          decoration: BoxDecoration(
            color: SportColors.panel,
            borderRadius: BorderRadius.circular(999),
            border: Border.all(color: accent ?? SportColors.border),
          ),
          child: Text(
            text,
            style: TextStyle(fontSize: 13.5, color: accent ?? SportColors.ink),
          ),
        ),
      ),
    );
  }
}
