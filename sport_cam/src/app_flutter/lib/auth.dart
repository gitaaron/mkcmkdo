import 'dart:async';
import 'dart:convert';

import 'package:flutter/foundation.dart';
import 'package:http/http.dart' as http;
import 'package:shared_preferences/shared_preferences.dart';

/// Signing in with an email and a password: Firebase Authentication, over its
/// REST API (plain `http`, like the rest of the app — no native Firebase
/// SDK, no google-services files).
///
/// There is no sign-up here. An admin adds people from the admin page
/// ([AdminScreen]), and the first admin is made with `npm run add-admin`.
///
/// The ID token goes with every call to the backend; it lasts an hour and is
/// renewed with the refresh token, which is kept on the phone so the person
/// stays signed in. Offline, the app still works directly with the camera:
/// that needs no token.
class AuthClient extends ChangeNotifier {
  AuthClient({required this.apiKey, this.emulatorHost = '', this.enabled = true});

  /// The Firebase project's Web API key. Anything will do on the emulator.
  final String apiKey;

  /// `host:port` of the Authentication emulator (`npm run dev`), or empty.
  final String emulatorHost;

  /// False when the app has no backend (LAN only): nobody signs in.
  final bool enabled;

  static const _prefsRefresh = 'auth_refresh';
  static const _prefsUid = 'auth_uid';
  static const _prefsEmail = 'auth_email';
  static const _prefsAdmin = 'auth_admin';

  SignedInUser? _user;
  String? _idToken;
  String? _refreshToken;
  DateTime _expiresAt = DateTime.fromMillisecondsSinceEpoch(0);
  Future<String?>? _refreshing;
  bool _restored = false;

  SignedInUser? get user => _user;
  bool get signedIn => _user != null;

  /// Set once [restore] has looked for a saved sign-in.
  bool get restored => _restored;

  bool get configured => apiKey.isNotEmpty || emulatorHost.isNotEmpty;

  String get _identity => emulatorHost.isEmpty
      ? 'https://identitytoolkit.googleapis.com/v1'
      : 'http://$emulatorHost/identitytoolkit.googleapis.com/v1';

  String get _secureToken => emulatorHost.isEmpty
      ? 'https://securetoken.googleapis.com/v1'
      : 'http://$emulatorHost/securetoken.googleapis.com/v1';

  String get _key => apiKey.isEmpty ? 'emulator' : apiKey;

  /// Pick up where the last launch left off, if someone was signed in.
  Future<void> restore() async {
    final prefs = await SharedPreferences.getInstance();
    final refresh = prefs.getString(_prefsRefresh);
    final uid = prefs.getString(_prefsUid);
    if (enabled && refresh != null && uid != null) {
      _refreshToken = refresh;
      _user = SignedInUser(
        uid,
        prefs.getString(_prefsEmail) ?? '',
        admin: prefs.getBool(_prefsAdmin) ?? false,
      );
    }
    _restored = true;
    notifyListeners();
  }

  /// Throws [AuthException] with a message to show.
  Future<void> signIn(String email, String password) async {
    final body = await _post(
      Uri.parse('$_identity/accounts:signInWithPassword?key=$_key'),
      {'email': email.trim(), 'password': password, 'returnSecureToken': true},
    );
    _refreshToken = body['refreshToken'] as String?;
    await _adopt(
      body['idToken'] as String,
      body['expiresIn'],
      body['localId'] as String,
      body['email'] as String? ?? email.trim(),
    );
  }

  /// Emails a link to choose a new password. Throws [AuthException].
  Future<void> sendPasswordReset(String email) => _post(
    Uri.parse('$_identity/accounts:sendOobCode?key=$_key'),
    {'requestType': 'PASSWORD_RESET', 'email': email.trim()},
  );

  Future<void> signOut() async {
    _user = null;
    _idToken = null;
    _refreshToken = null;
    final prefs = await SharedPreferences.getInstance();
    for (final k in [_prefsRefresh, _prefsUid, _prefsEmail, _prefsAdmin]) {
      await prefs.remove(k);
    }
    notifyListeners();
  }

  /// A current ID token for the backend, renewed when it is nearly out;
  /// null when there is none to be had (signed out, or offline).
  Future<String?> idToken() {
    if (_user == null) return Future.value(null);
    if (_idToken != null &&
        DateTime.now().isBefore(_expiresAt.subtract(const Duration(minutes: 5)))) {
      return Future.value(_idToken);
    }
    return _refreshing ??= _refresh().whenComplete(() => _refreshing = null);
  }

  /// The backend said the token is no good: renew it before the next call.
  void tokenRejected() => _expiresAt = DateTime.fromMillisecondsSinceEpoch(0);

  Future<String?> _refresh() async {
    final refresh = _refreshToken;
    if (refresh == null) return null;
    final http.Response res;
    try {
      res = await http
          .post(
            Uri.parse('$_secureToken/token?key=$_key'),
            headers: {'Content-Type': 'application/x-www-form-urlencoded'},
            body: {'grant_type': 'refresh_token', 'refresh_token': refresh},
          )
          .timeout(const Duration(seconds: 8));
    } on Exception {
      return null; // offline: try again next time
    }
    if (res.statusCode != 200) {
      // revoked, deleted or disabled: sign in again
      await signOut();
      return null;
    }
    final body = jsonDecode(res.body) as Map<String, dynamic>;
    _refreshToken = body['refresh_token'] as String? ?? refresh;
    await _adopt(
      body['id_token'] as String,
      body['expires_in'],
      body['user_id'] as String,
      _user?.email ?? '',
    );
    return _idToken;
  }

  Future<void> _adopt(
    String idToken,
    Object? expiresIn,
    String uid,
    String email,
  ) async {
    _idToken = idToken;
    _expiresAt = DateTime.now().add(
      Duration(seconds: int.tryParse('$expiresIn') ?? 3600),
    );
    final claims = jwtClaims(idToken);
    final changed = _user?.uid != uid || _user?.admin != (claims['admin'] == true);
    _user = SignedInUser(uid, email, admin: claims['admin'] == true);
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString(_prefsRefresh, _refreshToken ?? '');
    await prefs.setString(_prefsUid, uid);
    await prefs.setString(_prefsEmail, email);
    await prefs.setBool(_prefsAdmin, _user!.admin);
    if (changed) notifyListeners();
  }

  Future<Map<String, dynamic>> _post(Uri uri, Map<String, Object?> data) async {
    final http.Response res;
    try {
      res = await http
          .post(
            uri,
            headers: {'Content-Type': 'application/json'},
            body: jsonEncode(data),
          )
          .timeout(const Duration(seconds: 10));
    } on Exception {
      throw const AuthException("Can't reach the server — check your connection");
    }
    final body = jsonDecode(res.body) as Map<String, dynamic>;
    if (res.statusCode != 200) {
      final code = (body['error'] as Map<String, dynamic>?)?['message'] as String?;
      throw AuthException(authMessage(code));
    }
    return body;
  }
}

class SignedInUser {
  const SignedInUser(this.uid, this.email, {this.admin = false});

  final String uid;
  final String email;

  /// May add people (custom claim `admin`).
  final bool admin;
}

class AuthException implements Exception {
  const AuthException(this.message);

  final String message;

  @override
  String toString() => message;
}

/// What to tell the person for Firebase Authentication's error codes.
String authMessage(String? code) => switch (code?.split(' ').first) {
  'EMAIL_NOT_FOUND' ||
  'INVALID_PASSWORD' ||
  'INVALID_LOGIN_CREDENTIALS' => 'Wrong email or password',
  'INVALID_EMAIL' => "That isn't an email address",
  'MISSING_PASSWORD' => 'Enter your password',
  'USER_DISABLED' => 'This account has been turned off — ask an admin',
  'TOO_MANY_ATTEMPTS_TRY_LATER' => 'Too many tries — wait a few minutes',
  _ => "Couldn't sign in (${code ?? 'unknown error'})",
};

/// The claims in a JWT's payload (unverified: the backend checks the token;
/// the app only reads `admin` to decide which pages to show).
Map<String, dynamic> jwtClaims(String jwt) {
  final parts = jwt.split('.');
  if (parts.length < 2) return const {};
  try {
    return jsonDecode(utf8.decode(base64Url.decode(base64Url.normalize(parts[1]))))
        as Map<String, dynamic>;
  } on FormatException {
    return const {};
  }
}
