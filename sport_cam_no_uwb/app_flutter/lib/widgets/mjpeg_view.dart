import 'dart:async';
import 'dart:typed_data';

import 'package:flutter/material.dart';
import 'package:http/http.dart' as http;

import '../theme.dart';

/// Live video: decodes the camera's `multipart/x-mixed-replace` MJPEG stream
/// frame by frame.
///
/// Doing this natively (rather than an `<img>` in a webview) is one of the
/// reasons this app is Flutter: we control the socket, so a dropped Wi-Fi
/// connection reconnects in a second instead of leaving a stalled image, and
/// frames are decoded off the UI thread.
class MjpegView extends StatefulWidget {
  const MjpegView({super.key, required this.streamUrl, this.active = true});

  final String? streamUrl;
  final bool active;

  @override
  State<MjpegView> createState() => _MjpegViewState();
}

class _MjpegViewState extends State<MjpegView> {
  static final _soi = Uint8List.fromList([0xFF, 0xD8]); // JPEG start
  static final _eoi = Uint8List.fromList([0xFF, 0xD9]); // JPEG end

  http.Client? _client;
  StreamSubscription<List<int>>? _sub;
  Uint8List? _frame;
  bool _live = false;
  Timer? _retry;

  @override
  void initState() {
    super.initState();
    _start();
  }

  @override
  void didUpdateWidget(MjpegView old) {
    super.didUpdateWidget(old);
    if (old.streamUrl != widget.streamUrl || old.active != widget.active) {
      _stop();
      _start();
    }
  }

  Future<void> _start() async {
    final url = widget.streamUrl;
    if (url == null || !widget.active) return;
    final client = http.Client();
    _client = client;
    try {
      final req = http.Request('GET', Uri.parse(url));
      final res = await client.send(req).timeout(const Duration(seconds: 8));
      if (res.statusCode != 200) return _scheduleRetry();
      var buffer = BytesBuilder(copy: false);
      _sub = res.stream.listen(
        (chunk) {
          buffer.add(chunk);
          final bytes = buffer.toBytes();
          final start = _indexOf(bytes, _soi);
          final end = start < 0 ? -1 : _indexOf(bytes, _eoi, start + 2);
          if (start >= 0 && end > start) {
            final jpeg = Uint8List.sublistView(bytes, start, end + 2);
            if (mounted) {
              setState(() {
                _frame = jpeg;
                _live = true;
              });
            }
            buffer = BytesBuilder(copy: false)
              ..add(Uint8List.sublistView(bytes, end + 2));
          } else if (bytes.length > 4 << 20) {
            buffer = BytesBuilder(copy: false); // desync guard
          }
        },
        onError: (Object _) => _scheduleRetry(),
        onDone: _scheduleRetry,
        cancelOnError: true,
      );
    } on Exception {
      _scheduleRetry();
    }
  }

  void _scheduleRetry() {
    if (!mounted) return;
    setState(() => _live = false);
    _retry?.cancel();
    _retry = Timer(const Duration(seconds: 2), () {
      _stop();
      _start();
    });
  }

  void _stop() {
    _retry?.cancel();
    unawaited(_sub?.cancel());
    _sub = null;
    _client?.close();
    _client = null;
  }

  static int _indexOf(Uint8List data, Uint8List pattern, [int from = 0]) {
    for (var i = from; i <= data.length - pattern.length; i++) {
      var match = true;
      for (var j = 0; j < pattern.length; j++) {
        if (data[i + j] != pattern[j]) {
          match = false;
          break;
        }
      }
      if (match) return i;
    }
    return -1;
  }

  @override
  void dispose() {
    _stop();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final frame = _frame;
    if (frame == null) {
      return Container(
        color: Colors.black,
        alignment: Alignment.center,
        child: Text(
          widget.streamUrl == null
              ? 'No camera connected'
              : 'Connecting to video…',
          style: const TextStyle(color: SportColors.muted, fontSize: 16),
        ),
      );
    }
    return Stack(
      fit: StackFit.expand,
      children: [
        Container(color: Colors.black),
        Image.memory(frame, gaplessPlayback: true, fit: BoxFit.contain),
        if (!_live)
          const Align(
            alignment: Alignment.center,
            child: Text(
              'Reconnecting…',
              style: TextStyle(color: SportColors.muted, fontSize: 14),
            ),
          ),
      ],
    );
  }
}
