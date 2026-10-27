import 'dart:async';

import 'package:multicast_dns/multicast_dns.dart';

import 'models.dart';

/// Finds SportCam cameras on the local network via mDNS/Bonjour.
///
/// This is why the app is native: browsers expose no service discovery API
/// at all. The camera publishes `_sportcam._tcp.local` (see
/// device/sportcam/discovery.py); we resolve SRV → A and read the TXT record
/// so the picker can show each camera's name and current state before the
/// app connects to anything.
class CameraDiscovery {
  static const String serviceType = '_sportcam._tcp.local';

  /// One discovery sweep. Returns everything answering within [timeout].
  static Future<List<CameraEndpoint>> discover({
    Duration timeout = const Duration(seconds: 4),
  }) async {
    final client = MDnsClient();
    final found = <CameraEndpoint>{};
    try {
      await client.start();
      final deadline = Future<void>.delayed(timeout);

      await for (final ptr
          in client
              .lookup<PtrResourceRecord>(
                ResourceRecordQuery.serverPointer(serviceType),
              )
              .takeUntil(deadline)) {
        await for (final srv
            in client
                .lookup<SrvResourceRecord>(
                  ResourceRecordQuery.service(ptr.domainName),
                )
                .takeUntil(deadline)) {
          // TXT gives us name/state without opening a connection.
          String? advertisedState;
          String? friendlyName;
          await for (final txt
              in client
                  .lookup<TxtResourceRecord>(
                    ResourceRecordQuery.text(ptr.domainName),
                  )
                  .takeUntil(deadline)) {
            for (final line in txt.text.split('\n')) {
              final i = line.indexOf('=');
              if (i <= 0) continue;
              final key = line.substring(0, i).trim();
              final value = line.substring(i + 1).trim();
              if (key == 'state') advertisedState = value;
              if (key == 'name') friendlyName = value;
            }
            break;
          }

          await for (final ip
              in client
                  .lookup<IPAddressResourceRecord>(
                    ResourceRecordQuery.addressIPv4(srv.target),
                  )
                  .takeUntil(deadline)) {
            found.add(
              CameraEndpoint(
                name: friendlyName ?? _labelOf(ptr.domainName),
                host: ip.address.address,
                port: srv.port,
                state: advertisedState,
              ),
            );
            break;
          }
        }
      }
    } on Exception catch (err) {
      // No multicast on this network (some guest/gym Wi-Fi blocks it) —
      // callers fall back to the manual/last-known endpoint.
      // ignore: avoid_print
      print('[mdns] discovery failed: $err');
    } finally {
      client.stop();
    }
    return found.toList();
  }

  static String _labelOf(String domainName) {
    final dot = domainName.indexOf('.');
    return dot > 0 ? domainName.substring(0, dot) : domainName;
  }
}

extension<T> on Stream<T> {
  /// Stop listening when [signal] completes (mDNS streams never end on their
  /// own — they keep waiting for more responders).
  Stream<T> takeUntil(Future<void> signal) {
    final controller = StreamController<T>();
    late StreamSubscription<T> sub;
    var closed = false;
    Future<void> close() async {
      if (closed) return;
      closed = true;
      await sub.cancel();
      await controller.close();
    }

    sub = listen(controller.add, onError: controller.addError, onDone: close);
    signal.then((_) => close());
    return controller.stream;
  }
}
