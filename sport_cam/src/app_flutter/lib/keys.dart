import 'dart:convert';

import 'package:crypto/crypto.dart';
import 'package:shared_preferences/shared_preferences.dart';

/// The secrets this phone holds: the proof that a session, and so its
/// recordings, are this person's.
///
/// Whoever taps Record is handed a **session secret** by the camera (or by
/// the backend, through Firebase); the camera keeps only its SHA-256. With
/// it, and only with it, the app can stop that session, see its clips still
/// on the camera's card, and claim them in the cloud library
/// (`claimRecordings`), which makes them this person's for good. With UWB,
/// pairing a tag gives a **pairing secret**, which does the same for every
/// session the tag starts.
///
/// Each secret remembers who was signed in when it arrived, so a phone that
/// changes hands doesn't hand one person's clips to the next. Kept in shared
/// preferences; a claimed session secret is dropped after [keepFor].
class SessionKeys {
  SessionKeys._(this._prefs, this._held);

  static const _prefsKey = 'session_secrets';
  static const keepFor = Duration(days: 30);

  final SharedPreferences _prefs;
  final List<HeldSecret> _held;

  /// Who is signed in now: secrets arriving are theirs, and only theirs are
  /// sent. Empty when the app runs without accounts (no Firebase).
  String uid = '';

  static Future<SessionKeys> load() async {
    final prefs = await SharedPreferences.getInstance();
    final held = <HeldSecret>[];
    try {
      for (final e in jsonDecode(prefs.getString(_prefsKey) ?? '[]') as List) {
        final h = HeldSecret.fromJson(e as Map<String, dynamic>);
        if (h != null) held.add(h);
      }
    } on FormatException {
      // nothing usable stored
    }
    return SessionKeys._(prefs, held);
  }

  static String hash(String secret) =>
      sha256.convert(utf8.encode(secret)).toString();

  Iterable<HeldSecret> get _mine => _held.where((h) => h.uid == uid);

  /// Every secret the signed-in person holds, newest first: sent with each
  /// stop, and for their clips on the camera's card.
  List<String> get all => _mine.map((h) => h.secret).toList();

  Set<String> get hashes => _mine.map((h) => hash(h.secret)).toSet();

  /// The secret of the tag this person paired most recently, if any.
  String? get pairing =>
      _mine.where((h) => h.kind == SecretKind.pairing).firstOrNull?.secret;

  /// Not yet registered with the backend under this person.
  List<String> get unclaimed =>
      _mine.where((h) => !h.claimed).map((h) => h.secret).toList();

  Future<void> add(String secret, SecretKind kind, {int? tag}) async {
    // a tag paired again replaces its earlier pairing
    if (kind == SecretKind.pairing) {
      _held.removeWhere((h) => h.kind == kind && h.tag == tag && h.uid == uid);
    }
    _held.removeWhere((h) => h.secret == secret);
    _held.insert(
      0,
      HeldSecret(secret, kind, DateTime.now(), uid, tag: tag),
    );
    await _save();
  }

  Future<void> markClaimed(Iterable<String> secrets) async {
    final set = secrets.toSet();
    for (final h in _held) {
      if (set.contains(h.secret)) h.claimed = true;
    }
    await _save();
  }

  Future<void> _save() async {
    final cutoff = DateTime.now().subtract(keepFor);
    _held.removeWhere(
      (h) => h.kind == SecretKind.session && h.claimed && h.at.isBefore(cutoff),
    );
    await _prefs.setString(
      _prefsKey,
      jsonEncode(_held.map((h) => h.toJson()).toList()),
    );
  }
}

enum SecretKind { session, pairing }

class HeldSecret {
  HeldSecret(
    this.secret,
    this.kind,
    this.at,
    this.uid, {
    this.tag,
    this.claimed = false,
  });

  final String secret;
  final SecretKind kind;
  final DateTime at;
  final String uid;
  final int? tag;
  bool claimed;

  static HeldSecret? fromJson(Map<String, dynamic> j) {
    final secret = j['secret'];
    if (secret is! String) return null;
    return HeldSecret(
      secret,
      j['kind'] == 'pairing' ? SecretKind.pairing : SecretKind.session,
      DateTime.tryParse(j['at'] as String? ?? '') ?? DateTime.now(),
      j['uid'] as String? ?? '',
      tag: (j['tag'] as num?)?.toInt(),
      claimed: j['claimed'] == true,
    );
  }

  Map<String, dynamic> toJson() => {
    'secret': secret,
    'kind': kind.name,
    'at': at.toIso8601String(),
    'uid': uid,
    if (tag != null) 'tag': tag,
    'claimed': claimed,
  };
}
