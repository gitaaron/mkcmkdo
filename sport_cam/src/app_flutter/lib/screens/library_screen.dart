import 'dart:async';
import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:http/http.dart' as http;
import 'package:shared_preferences/shared_preferences.dart';
import 'package:video_player/video_player.dart';

import '../camera_client.dart';
import '../models.dart';
import '../theme.dart';
import '../widgets/person_boxes.dart';

/// The signed-in person's recordings, and nobody else's: the cloud library,
/// plus their clips still on the card of a camera connected directly.
/// Playback uses `video_player` — ExoPlayer on Android, AVPlayer on iOS — so
/// H.264 decoding is hardware-accelerated and seeking works against the
/// camera's (or Cloud Storage's) range-capable endpoint.
class LibraryScreen extends StatelessWidget {
  const LibraryScreen({super.key, required this.client});

  final CameraClient client;

  Future<void> _play(BuildContext context, Recording r) async {
    final Playback video;
    final Playback? boxes;
    try {
      video = await client.playback(r);
      boxes = await client.boxes(r);
    } on ApiException catch (err) {
      if (context.mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text("Can't play it: ${err.message}")),
        );
      }
      return;
    }
    if (!context.mounted) return;
    await Navigator.of(context).push(
      MaterialPageRoute<void>(
        builder: (_) => PlayerScreen(
          video: video,
          boxes: boxes,
          title: _when(r.createdAt),
        ),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    return ListenableBuilder(
      listenable: client,
      builder: (context, _) => _build(context, client.recordings),
    );
  }

  Widget _build(BuildContext context, List<Recording> recordings) {
    return Scaffold(
      appBar: AppBar(
        backgroundColor: SportColors.panel,
        title: const Text('My recordings'),
      ),
      body: recordings.isEmpty
          ? const Center(
              child: Padding(
                padding: EdgeInsets.all(24),
                child: Text(
                  'No recordings yet. Tap Record on the camera, and your '
                  'clips appear here once they are saved.',
                  textAlign: TextAlign.center,
                  style: TextStyle(color: SportColors.muted),
                ),
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
                      color: SportColors.awake,
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
                        if (!r.inCloud) 'on the camera, uploading soon',
                      ].where((s) => s.isNotEmpty).join(' · '),
                      style: const TextStyle(
                        color: SportColors.muted,
                        fontSize: 12.5,
                      ),
                    ),
                    onTap: () => _play(context, r),
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

class PlayerScreen extends StatefulWidget {
  const PlayerScreen({
    super.key,
    required this.video,
    required this.title,
    this.boxes,
  });

  /// The clip, and the headers that show it's the viewer's.
  final Playback video;
  final String title;

  /// The person boxes saved beside the clip, drawn over it; null if none.
  final Playback? boxes;

  @override
  State<PlayerScreen> createState() => _PlayerScreenState();
}

class _PlayerScreenState extends State<PlayerScreen> {
  static const _showKey = 'showBoxes';

  late final VideoPlayerController _controller =
      VideoPlayerController.networkUrl(
        Uri.parse(widget.video.url),
        httpHeaders: widget.video.headers,
      );
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
    final boxes = widget.boxes;
    if (boxes != null) {
      try {
        final res = await http.get(Uri.parse(boxes.url), headers: boxes.headers);
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
                  if (track != null && _showBoxes) const BoxLegend(),
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
  void paint(Canvas canvas, Size size) => paintBoxes(
    canvas,
    Offset.zero & size,
    track.width,
    track.height,
    track.at(t),
  );

  @override
  bool shouldRepaint(_BoxPainter old) => old.t != t || old.track != track;
}
