import 'dart:async';

import 'package:flutter/material.dart';
import 'package:mkcmkdo/video_player_screen.dart';

void main() => runApp(VideoPlayerApp());

class VideoPlayerApp extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'Video Player Demo',
      home: Scaffold(
      appBar: AppBar(
        title: Text('MKCMKDO'),
      ),
      body:ListView(children:[
        VideoPlayerScreen(1),
        VideoPlayerScreen(2),
        VideoPlayerScreen(3),
        VideoPlayerScreen(4),
        VideoPlayerScreen(5),
      ]),
      )
    );
  }
}


