import 'package:flutter/material.dart';

import '../auth.dart';
import '../theme.dart';

/// Sign in with the email and password an admin set up for you. There is no
/// sign-up: people are added from the admin page ([AdminScreen]).
class LoginScreen extends StatefulWidget {
  const LoginScreen({super.key, required this.auth});

  final AuthClient auth;

  @override
  State<LoginScreen> createState() => _LoginScreenState();
}

class _LoginScreenState extends State<LoginScreen> {
  final _email = TextEditingController();
  final _password = TextEditingController();
  bool _busy = false;
  String? _error;

  @override
  void initState() {
    super.initState();
    if (!widget.auth.configured) {
      _error = 'This build has no sign-in set up '
          '(SPORTCAM_FIREBASE_API_KEY or SPORTCAM_AUTH_EMULATOR)';
    }
  }

  @override
  void dispose() {
    _email.dispose();
    _password.dispose();
    super.dispose();
  }

  Future<void> _signIn() async {
    if (_email.text.trim().isEmpty || _password.text.isEmpty) {
      setState(() => _error = 'Enter your email and password');
      return;
    }
    setState(() {
      _busy = true;
      _error = null;
    });
    try {
      await widget.auth.signIn(_email.text, _password.text);
      // the app swaps this screen for the camera once signed in
    } on AuthException catch (err) {
      if (mounted) setState(() => _error = err.message);
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  Future<void> _reset() async {
    if (_email.text.trim().isEmpty) {
      setState(() => _error = 'Enter your email first, then tap “Forgot password?”');
      return;
    }
    setState(() => _error = null);
    try {
      await widget.auth.sendPasswordReset(_email.text);
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('Sent a link to ${_email.text.trim()} to choose a new password')),
      );
    } on AuthException catch (err) {
      if (mounted) setState(() => _error = err.message);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: SafeArea(
        child: Center(
          child: SingleChildScrollView(
            padding: const EdgeInsets.all(28),
            child: ConstrainedBox(
              constraints: const BoxConstraints(maxWidth: 380),
              child: AutofillGroup(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.stretch,
                  children: [
                    const Icon(Icons.videocam_rounded, size: 44, color: SportColors.awake),
                    const SizedBox(height: 12),
                    const Text(
                      'SportCam',
                      textAlign: TextAlign.center,
                      style: TextStyle(
                        fontSize: 26,
                        fontWeight: FontWeight.w700,
                        color: SportColors.ink,
                      ),
                    ),
                    const SizedBox(height: 6),
                    const Text(
                      'Sign in to record and watch your climbs',
                      textAlign: TextAlign.center,
                      style: TextStyle(color: SportColors.muted),
                    ),
                    const SizedBox(height: 28),
                    TextField(
                      controller: _email,
                      keyboardType: TextInputType.emailAddress,
                      autofillHints: const [AutofillHints.email],
                      autocorrect: false,
                      textInputAction: TextInputAction.next,
                      decoration: const InputDecoration(
                        labelText: 'Email',
                        border: OutlineInputBorder(),
                      ),
                    ),
                    const SizedBox(height: 12),
                    TextField(
                      controller: _password,
                      obscureText: true,
                      autofillHints: const [AutofillHints.password],
                      textInputAction: TextInputAction.done,
                      onSubmitted: (_) => _signIn(),
                      decoration: const InputDecoration(
                        labelText: 'Password',
                        border: OutlineInputBorder(),
                      ),
                    ),
                    if (_error != null) ...[
                      const SizedBox(height: 12),
                      Text(
                        _error!,
                        style: const TextStyle(color: SportColors.recording),
                      ),
                    ],
                    const SizedBox(height: 20),
                    FilledButton(
                      onPressed: _busy || !widget.auth.configured ? null : _signIn,
                      style: FilledButton.styleFrom(
                        minimumSize: const Size.fromHeight(50),
                        backgroundColor: SportColors.awake,
                      ),
                      child: _busy
                          ? const SizedBox(
                              width: 20,
                              height: 20,
                              child: CircularProgressIndicator(strokeWidth: 2),
                            )
                          : const Text('Sign in', style: TextStyle(fontSize: 16)),
                    ),
                    TextButton(
                      onPressed: _busy ? null : _reset,
                      child: const Text('Forgot password?'),
                    ),
                    const SizedBox(height: 8),
                    const Text(
                      'No account? Ask an admin to add you.',
                      textAlign: TextAlign.center,
                      style: TextStyle(color: SportColors.muted, fontSize: 13),
                    ),
                  ],
                ),
              ),
            ),
          ),
        ),
      ),
    );
  }
}
