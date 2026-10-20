import 'package:flutter/material.dart';

import '../models.dart';
import '../theme.dart';

/// Top-left connection indicator: how the app is reaching the camera.
///
///   ● Direct      talking straight to the camera over the LAN
///   ● Server      going through the home server / cloud backend
///   ● Searching…  mDNS sweep in progress (pulsing)
///   ● Offline     nothing reachable — tap to retry
class ConnectionBadge extends StatefulWidget {
  const ConnectionBadge({
    super.key,
    required this.link,
    required this.endpoint,
    required this.onTap,
  });

  final LinkMode link;
  final CameraEndpoint? endpoint;
  final VoidCallback onTap;

  @override
  State<ConnectionBadge> createState() => _ConnectionBadgeState();
}

class _ConnectionBadgeState extends State<ConnectionBadge>
    with SingleTickerProviderStateMixin {
  late final AnimationController _pulse = AnimationController(
    vsync: this,
    duration: const Duration(milliseconds: 900),
  )..repeat(reverse: true);

  @override
  void dispose() {
    _pulse.dispose();
    super.dispose();
  }

  String get _label => switch (widget.link) {
    LinkMode.direct => widget.endpoint?.name ?? 'Direct',
    LinkMode.relay => 'Firebase',
    LinkMode.searching => 'Searching…',
    LinkMode.offline => 'Offline',
  };

  String get _sub => switch (widget.link) {
    LinkMode.direct => 'Direct · ${widget.endpoint?.host ?? ''}',
    LinkMode.relay => 'from anywhere · preview',
    LinkMode.searching => 'looking for camera',
    LinkMode.offline => 'tap to retry',
  };

  @override
  Widget build(BuildContext context) {
    final color = SportColors.forLink(widget.link);
    final dot = Container(
      width: 10,
      height: 10,
      decoration: BoxDecoration(
        color: color,
        shape: BoxShape.circle,
        boxShadow: [
          BoxShadow(color: color.withValues(alpha: 0.6), blurRadius: 6),
        ],
      ),
    );

    return Semantics(
      label: 'Connection: $_label, $_sub',
      button: true,
      child: GestureDetector(
        onTap: widget.onTap,
        child: Container(
          padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 7),
          decoration: BoxDecoration(
            color: SportColors.panel.withValues(alpha: 0.88),
            borderRadius: BorderRadius.circular(12),
            border: Border.all(color: SportColors.border),
          ),
          child: Row(
            mainAxisSize: MainAxisSize.min,
            children: [
              if (widget.link == LinkMode.searching)
                FadeTransition(opacity: _pulse, child: dot)
              else
                dot,
              const SizedBox(width: 8),
              Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                mainAxisSize: MainAxisSize.min,
                children: [
                  Text(
                    _label,
                    style: const TextStyle(
                      fontSize: 13,
                      fontWeight: FontWeight.w600,
                      color: SportColors.ink,
                    ),
                  ),
                  Text(
                    _sub,
                    style: const TextStyle(
                      fontSize: 10.5,
                      color: SportColors.muted,
                    ),
                  ),
                ],
              ),
            ],
          ),
        ),
      ),
    );
  }
}
