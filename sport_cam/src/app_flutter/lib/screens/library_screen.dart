import 'dart:async';
import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:http/http.dart' as http;
import 'package:shared_preferences/shared_preferences.dart';
import 'package:video_player/video_player.dart';

import '../models.dart';
import '../theme.dart';

/// Recording library. Playback uses `video_player` — ExoPlayer on Android,
/// AVPlayer on iOS — so H.264 decoding is hardware-accelerated and seeking
/// works against the camera's (or server's) range-capable endpoint.
class LibraryScreen extends StatelessWidget {
  const LibraryScreen({
    super.key,
    required this.recordings,
    required this.base,
  });

  final List<Recording> recordings;
  final String base;

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        backgroundColor: SportColors.panel,
        title: const Text('Recordings'),
      ),
      body: recordings.isEmpty
          ? const Center(
              child: Text(
                'No recordings yet.',
                style: TextStyle(color: SportColors.muted),
              ),
            )
          : ListView.separated(
              padding: const EdgeInsets.all(14),
              itemCount: recordings.length,
              separatorBuilder: (_, __) => const SizedBox(height: 8),
              itemBuilder: (context, i) {
                final r = recordings[i];
                return Material(
                  color: SportColors.panel,
                  borderRadius: BorderRadius.circular(12),
                  child: ListTile(
                    shape: RoundedRectangleBorder(
                      borderRadius: BorderRadius.circular(12),
                      side: const BorderSide(color: SportColors.border),
                    ),
                    leading: const Icon(
                      Icons.play_arrow_rounded,
                      color: SportColors.idle,
                    ),
                    title: Text(
                      _when(r.createdAt),
                      style: const TextStyle(
                        color: SportColors.ink,
                        fontSize: 15,
                      ),
                    ),
                    subtitle: Text(
                      [
                        r.durationLabel,
                        r.sizeLabel,
                      ].where((s) => s.isNotEmpty).join(' · '),
                      style: const TextStyle(
                        color: SportColors.muted,
                        fontSize: 12.5,
                      ),
                    ),
                    onTap: () => Navigator.of(context).push(
                      MaterialPageRoute<void>(
                        builder: (_) => PlayerScreen(
                          url: r.absoluteUrl(base),
                          boxesUrl: r.absoluteBoxesUrl(base),
                          title: _when(r.createdAt),
                        ),
                      ),
                    ),
                  ),
                );
              },
            ),
    );
  }

  static String _when(DateTime d) =>
      '${d.day}/${d.month} ${d.hour.toString().padLeft(2, '0')}:'
      '${d.minute.toString().padLeft(2, '0')}';
}

/// Box colours: green for the climber, yellow for anyone else, red while
/// the camera can't tell which is the climber.
const boxColours = {
  BoxLabel.climber: Color(0xFF34C759),
  BoxLabel.other: Color(0xFFFFCC00),
  BoxLabel.unsure: Color(0xFFFF3B30),
};

class PlayerScreen extends StatefulWidget {
  const PlayerScreen({
    super.key,
    required this.url,
    required this.title,
    this.boxesUrl,
  });

  final String url;
  final String title;

  /// The person boxes saved beside the clip, drawn over it; null if none.
  final String? boxesUrl;

  @override
  State<PlayerScreen> createState() => _PlayerScreenState();
}

class _PlayerScreenState extends State<PlayerScreen> {
  static const _showKey = 'showBoxes';

  late final VideoPlayerController _controller =
      VideoPlayerController.networkUrl(Uri.parse(widget.url));
  String? _error;
  BoxTrack? _track;
  bool _showBoxes = true;
  // The controller reports its position only twice a second; the boxes
  // change three times a second, so ask it more often while they show.
  Duration _position = Duration.zero;
  Timer? _ticker;

  @override
  void initState() {
    super.initState();
    _controller
        .initialize()
        .then((_) {
          if (mounted) {
            setState(() {});
            _controller.play();
          }
        })
        .catchError((Object err) {
          if (mounted) setState(() => _error = '$err');
        });
    _loadBoxes();
    _ticker = Timer.periodic(const Duration(milliseconds: 100), (_) async {
      if (_track == null || !_showBoxes) return;
      final p = await _controller.position;
      if (mounted && p != null && p != _position) {
        setState(() => _position = p);
      }
    });
  }

  Future<void> _loadBoxes() async {
    final prefs = await SharedPreferences.getInstance();
    final show = prefs.getBool(_showKey) ?? true;
    BoxTrack? track;
    final url = widget.boxesUrl;
    if (url != null) {
      try {
        final res = await http.get(Uri.parse(url));
        if (res.statusCode == 200)
          track = BoxTrack.fromJson(jsonDecode(res.body));
      } catch (_) {
        // no boxes: the video plays without them
      }
    }
    if (mounted) {
      setState(() {
        _showBoxes = show;
        _track = track;
      });
    }
  }

  Future<void> _toggleBoxes() async {
    setState(() => _showBoxes = !_showBoxes);
    final prefs = await SharedPreferences.getInstance();
    await prefs.setBool(_showKey, _showBoxes);
  }

  @override
  void dispose() {
    _ticker?.cancel();
    _controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final track = _track;
    return Scaffold(
      backgroundColor: Colors.black,
      appBar: AppBar(
        backgroundColor: SportColors.panel,
        title: Text(widget.title),
      ),
      body: Center(
        child: _error != null
            ? Padding(
                padding: const EdgeInsets.all(24),
                child: Text(
                  'Could not play this recording.\n$_error',
                  textAlign: TextAlign.center,
                  style: const TextStyle(color: SportColors.muted),
                ),
              )
            : _controller.value.isInitialized
            ? Column(
                mainAxisSize: MainAxisSize.min,
                children: [
                  AspectRatio(
                    aspectRatio: _controller.value.aspectRatio,
                    child: Stack(
                      fit: StackFit.expand,
                      children: [
                        VideoPlayer(_controller),
                        if (track != null && _showBoxes)
                          CustomPaint(
                            painter: _BoxPainter(
                              track,
                              _position.inMilliseconds / 1000.0,
                            ),
                          ),
                      ],
                    ),
                  ),
                  VideoProgressIndicator(_controller, allowScrubbing: true),
                  Row(
                    mainAxisAlignment: MainAxisAlignment.center,
                    children: [
                      IconButton(
                        color: SportColors.ink,
                        icon: Icon(
                          _controller.value.isPlaying
                              ? Icons.pause
                              : Icons.play_arrow,
                        ),
                        onPressed: () => setState(() {
                          _controller.value.isPlaying
                              ? _controller.pause()
                              : _controller.play();
                        }),
                      ),
                      if (track != null)
                        TextButton.icon(
                          style: TextButton.styleFrom(
                            foregroundColor: SportColors.ink,
                          ),
                          icon: Icon(
                            _showBoxes
                                ? Icons.crop_free
                                : Icons.crop_free_outlined,
                            color: _showBoxes
                                ? boxColours[BoxLabel.climber]
                                : SportColors.muted,
                          ),
                          label: Text(_showBoxes ? 'Boxes on' : 'Boxes off'),
                          onPressed: _toggleBoxes,
                        ),
                    ],
                  ),
                  if (track != null && _showBoxes) const _Legend(),
                ],
              )
            : const CircularProgressIndicator(),
      ),
    );
  }
}

/// The boxes of the detection on screen at [t], scaled from the frame they
/// were measured in to the video as drawn.
class _BoxPainter extends CustomPainter {
  _BoxPainter(this.track, this.t);

  final BoxTrack track;
  final double t;

  @override
  void paint(Canvas canvas, Size size) {
    final sx = size.width / track.width;
    final sy = size.height / track.height;
    for (final b in track.at(t)) {
      final paint = Paint()
        ..style = PaintingStyle.stroke
        ..strokeWidth = 2.5
        ..color = boxColours[b.label]!;
      canvas.drawRect(
        Rect.fromLTWH(b.x * sx, b.y * sy, b.w * sx, b.h * sy),
        paint,
      );
    }
  }

  @override
  bool shouldRepaint(_BoxPainter old) => old.t != t || old.track != track;
}

class _Legend extends StatelessWidget {
  const _Legend();

  @override
  Widget build(BuildContext context) {
    Widget key(BoxLabel l, String text) => Row(
      mainAxisSize: MainAxisSize.min,
      children: [
        Container(
          width: 12,
          height: 12,
          decoration: BoxDecoration(
            border: Border.all(color: boxColours[l]!, width: 2),
          ),
        ),
        const SizedBox(width: 6),
        Text(
          text,
          style: const TextStyle(color: SportColors.muted, fontSize: 12.5),
        ),
      ],
    );
    return Wrap(
      spacing: 14,
      children: [
        key(BoxLabel.climber, 'climber'),
        key(BoxLabel.other, 'someone else'),
        key(BoxLabel.unsure, "can't tell yet"),
      ],
    );
  }
}
