import 'dart:async';

import 'package:flutter/material.dart';
import 'package:shared_preferences/shared_preferences.dart';

import '../camera_client.dart';
import '../models.dart';
import '../theme.dart';
import '../widgets/connection_badge.dart';
import '../widgets/control_bar.dart';
import '../widgets/joystick.dart';
import '../widgets/mjpeg_view.dart';
import '../widgets/person_boxes.dart';
import '../widgets/status_ring.dart';
import 'admin_screen.dart';
import 'library_screen.dart';

/// The single screen: live video, connection badge (top-left), camera-state
/// ring (top-right) with the account menu under it, state-dependent controls
/// at the bottom, and in awake a joystick (bottom-right) to aim the camera by
/// hand.
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
  // The live view's own Boxes on / off, remembered on the phone (the
  // recording player has another).
  static const _showBoxesKey = 'showLiveBoxes';

  CameraClient get client => widget.client;
  bool _showBoxes = true;

  @override
  void initState() {
    super.initState();
    client.addListener(_onChange);
    client.connect();
    SharedPreferences.getInstance().then((prefs) {
      final show = prefs.getBool(_showBoxesKey) ?? true;
      if (mounted) setState(() => _showBoxes = show);
    });
  }

  Future<void> _toggleBoxes() async {
    setState(() => _showBoxes = !_showBoxes);
    final prefs = await SharedPreferences.getInstance();
    await prefs.setBool(_showBoxesKey, _showBoxes);
  }

  void _onChange() => setState(() {});

  @override
  void dispose() {
    client.removeListener(_onChange);
    super.dispose();
  }

  void _openLibrary() {
    client.dismissToast();
    unawaited(client.refreshRecordings());
    Navigator.of(context).push(
      MaterialPageRoute<void>(builder: (_) => LibraryScreen(client: client)),
    );
  }

  Future<void> _pairTag() async {
    final go = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Pair your tag'),
        content: const Text(
          'Switch on your tag, and make sure no other tag near the camera '
          'is on. Once paired, switching it on starts a recording that is '
          'yours: only this phone can stop it, and only you see the clip.',
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context, false),
            child: const Text('Cancel'),
          ),
          FilledButton(
            onPressed: () => Navigator.pop(context, true),
            child: const Text('Pair'),
          ),
        ],
      ),
    );
    if (go != true) return;
    final said = await client.pairTag();
    if (mounted) {
      ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(said)));
    }
  }

  Future<void> _account(_Account choice) async {
    switch (choice) {
      case _Account.pairTag:
        await _pairTag();
      case _Account.people:
        await Navigator.of(context).push(
          MaterialPageRoute<void>(builder: (_) => AdminScreen(client: client)),
        );
      case _Account.signOut:
        await client.auth.signOut();
    }
  }

  @override
  Widget build(BuildContext context) {
    final top = MediaQuery.of(context).padding.top;
    final upload = client.upload;
    final saved = client.justSaved;
    final text = ModeText.of(client.mode);
    // No picture outside awake, initiate recording and recording: asleep the
    // camera's sensor is off.
    final live = client.isConnected && client.state.isLive;
    final picture = live &&
        (client.link != LinkMode.relay || client.preview != null);
    final boxes = picture ? client.liveBoxes : null;

    return Scaffold(
      body: Stack(
        fit: StackFit.expand,
        children: [
          // Direct: the camera's full-rate MJPEG. Through Firebase: the
          // low-rate preview it posts while someone is watching.
          if (client.link == LinkMode.relay)
            ColoredBox(
              color: Colors.black,
              child: client.preview == null || !live
                  ? const SizedBox.shrink()
                  : Image.memory(
                      client.preview!,
                      fit: BoxFit.contain,
                      gaplessPlayback: true,
                    ),
            )
          else
            MjpegView(
              streamUrl: client.streamUrl,
              // in the background: no stream, so the camera can sleep
              active: live && client.foreground,
            ),

          // person boxes from the camera's last detection
          if (boxes != null && _showBoxes)
            IgnorePointer(
              child: CustomPaint(painter: LiveBoxesPainter(boxes)),
            ),

          if (client.isConnected && client.state == CamState.sleep)
            const Center(
              child: Padding(
                padding: EdgeInsets.symmetric(horizontal: 32),
                child: Text(
                  'Camera is asleep — wake it up or record to see the picture',
                  textAlign: TextAlign.center,
                  style: TextStyle(color: SportColors.muted, fontSize: 18),
                ),
              ),
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
              searchingLabel: text.searching,
              connected: client.isConnected,
              phase: client.telemetry.phase,
              countdown: client.telemetry.countdown,
            ),
          ),

          // who is signed in: pair a tag, add people, sign out
          Positioned(
            top: top + 62,
            right: 14,
            child: _AccountButton(
              email: client.auth.user?.email,
              canPairTag: client.mode == TrackingMode.withUwb,
              admin: client.auth.user?.admin ?? false,
              signOut: client.auth.enabled,
              onSelected: _account,
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

          // person boxes on / off, under the recordings button
          if (picture)
            Positioned(
              top: top + 110,
              left: 14,
              child: _BoxesButton(show: _showBoxes, onTap: _toggleBoxes),
            ),

          // tracking for a while and still not recording: nobody found / vision cannot see the climber
          if (client.state == CamState.tracking &&
              client.telemetry.acquireStalled)
            _Pill(
              text: text.stalled,
              accent: SportColors.tracking,
              alignment: Alignment(0, -0.78),
            ),

          // someone else's session: the stop buttons are theirs
          if (client.isConnected && client.othersSession)
            const _Pill(
              text: "Someone else is recording — only their phone can stop it",
              accent: SportColors.muted,
              alignment: Alignment(0, 0.4),
            ),

          // the camera refused something or is running low: says why
          if (client.warning case final warning?)
            _Pill(
              text: warning.text,
              accent: SportColors.recording,
              onTap: client.dismissWarning,
              alignment: const Alignment(0, 0.56),
            ),

          if (upload != null)
            _Pill(text: 'Uploading… ${(upload.fraction * 100).round()}%')
          else if (saved != null)
            _Pill(
              text: 'Recording saved — watch now',
              accent: SportColors.tracking,
              onTap: _openLibrary,
            ),

          // awake, on the camera's own Wi-Fi link: aim it by hand
          if (client.canAim && client.foreground)
            Positioned(
              right: 18,
              bottom: 96 + MediaQuery.of(context).padding.bottom,
              child: Joystick(onMove: client.aim),
            ),

          Align(
            alignment: Alignment.bottomCenter,
            child: ControlBar(
              state: client.state,
              text: text,
              enabled: client.isConnected,
              locked: client.othersSession,
              onSetPower: client.setPower,
              onStartTracking: client.startTracking,
              onStopTracking: client.stopTracking,
              onStopRecording: client.stopRecording,
            ),
          ),
        ],
      ),
    );
  }
}

enum _Account { pairTag, people, signOut }

class _AccountButton extends StatelessWidget {
  const _AccountButton({
    required this.email,
    required this.canPairTag,
    required this.admin,
    required this.signOut,
    required this.onSelected,
  });

  final String? email;
  final bool canPairTag;
  final bool admin;
  final bool signOut;
  final void Function(_Account) onSelected;

  @override
  Widget build(BuildContext context) {
    if (!canPairTag && !admin && !signOut) return const SizedBox.shrink();
    return PopupMenuButton<_Account>(
      tooltip: 'Account',
      onSelected: onSelected,
      color: SportColors.panel,
      itemBuilder: (_) => [
        if (email != null)
          PopupMenuItem<_Account>(
            enabled: false,
            child: Text(email!, style: const TextStyle(color: SportColors.muted)),
          ),
        if (canPairTag)
          const PopupMenuItem(value: _Account.pairTag, child: Text('Pair my tag')),
        if (admin)
          const PopupMenuItem(value: _Account.people, child: Text('People')),
        if (signOut)
          const PopupMenuItem(value: _Account.signOut, child: Text('Sign out')),
      ],
      child: Container(
        width: 40,
        height: 40,
        decoration: BoxDecoration(
          color: SportColors.panel.withValues(alpha: 0.85),
          borderRadius: BorderRadius.circular(12),
          border: Border.all(color: SportColors.border),
        ),
        child: const Icon(Icons.person_outline, size: 20, color: SportColors.ink),
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
                  color: SportColors.awake,
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

class _BoxesButton extends StatelessWidget {
  const _BoxesButton({required this.show, required this.onTap});

  final bool show;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return Semantics(
      button: true,
      toggled: show,
      label: 'Person boxes',
      child: Tooltip(
        message: show ? 'Hide the person boxes' : 'Show the person boxes',
        child: GestureDetector(
          onTap: onTap,
          child: Container(
            width: 40,
            height: 40,
            decoration: BoxDecoration(
              color: SportColors.panel.withValues(alpha: 0.85),
              borderRadius: BorderRadius.circular(12),
              border: Border.all(color: SportColors.border),
            ),
            child: Icon(
              Icons.crop_free,
              size: 20,
              color: show ? boxColours[BoxLabel.climber] : SportColors.muted,
            ),
          ),
        ),
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
          margin: const EdgeInsets.symmetric(horizontal: 24),
          padding: const EdgeInsets.symmetric(horizontal: 18, vertical: 9),
          decoration: BoxDecoration(
            color: SportColors.panel,
            borderRadius: BorderRadius.circular(999),
            border: Border.all(color: accent ?? SportColors.border),
          ),
          child: Text(
            text,
            textAlign: TextAlign.center,
            style: TextStyle(fontSize: 13.5, color: accent ?? SportColors.ink),
          ),
        ),
      ),
    );
  }
}
