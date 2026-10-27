import 'package:flutter/material.dart';

import 'models.dart';

/// Same palette as the LED ring on the camera base.
class SportColors {
  static const bg = Color(0xFF0D1420);
  static const panel = Color(0xFF131C2C);
  static const border = Color(0xFF2A3850);
  static const ink = Color(0xFFE8EDF6);
  static const muted = Color(0xFF7F8EA8);

  static const sleep = Color(0xFF4A5D85);
  static const awake = Color(0xFF2F6FED);
  static const tracking = Color(0xFF1F9D55);
  static const recording = Color(0xFFD64541);
  static const off = Color(0xFF8A93A6);

  static Color forState(CamState s) => switch (s) {
    CamState.sleep => sleep,
    CamState.awake => awake,
    CamState.tracking => tracking,
    CamState.recording => recording,
    CamState.off => off,
  };

  static Color forLink(LinkMode l) => switch (l) {
    LinkMode.direct => tracking,
    LinkMode.relay => awake,
    LinkMode.searching => const Color(0xFFF2A93B),
    LinkMode.offline => recording,
  };
}

/// Awake's sub-state, from telemetry `phase`.
String awakeLabel(String? phase) => switch (phase) {
  'person-in-frame' => 'Awake — person in frame',
  'no-person-in-frame' => 'Awake — no one in frame',
  _ => 'Awake — not recording',
};

String stateLabel(CamState s) => switch (s) {
  CamState.off => 'Off',
  CamState.sleep => 'Asleep — camera off',
  CamState.awake => 'Awake — not recording',
  CamState.tracking => 'Tracking',
  CamState.recording => 'Recording',
};

ThemeData buildTheme() => ThemeData(
  useMaterial3: true,
  brightness: Brightness.dark,
  scaffoldBackgroundColor: SportColors.bg,
  colorScheme: ColorScheme.fromSeed(
    seedColor: SportColors.awake,
    brightness: Brightness.dark,
  ).copyWith(surface: SportColors.panel),
  fontFamily: 'Roboto',
);
