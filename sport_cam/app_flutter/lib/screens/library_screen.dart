import 'package:flutter/material.dart';
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

class PlayerScreen extends StatefulWidget {
  const PlayerScreen({super.key, required this.url, required this.title});

  final String url;
  final String title;

  @override
  State<PlayerScreen> createState() => _PlayerScreenState();
}

class _PlayerScreenState extends State<PlayerScreen> {
  late final VideoPlayerController _controller =
      VideoPlayerController.networkUrl(Uri.parse(widget.url));
  String? _error;

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
  }

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
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
                    child: VideoPlayer(_controller),
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
                    ],
                  ),
                ],
              )
            : const CircularProgressIndicator(),
      ),
    );
  }
}
