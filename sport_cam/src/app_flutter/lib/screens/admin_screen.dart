import 'dart:async';

import 'package:flutter/material.dart';

import '../camera_client.dart';
import '../theme.dart';

/// Admins only: everyone who can sign in, and **Add person** — the only way
/// an account is made. The backend checks the admin claim on every call;
/// the app just doesn't offer this page to anyone else.
class AdminScreen extends StatefulWidget {
  const AdminScreen({super.key, required this.client});

  final CameraClient client;

  @override
  State<AdminScreen> createState() => _AdminScreenState();
}

class _AdminScreenState extends State<AdminScreen> {
  List<({String email, bool admin})>? _people;
  String? _error;

  @override
  void initState() {
    super.initState();
    unawaited(_load());
  }

  Future<void> _load() async {
    try {
      final r = await widget.client.cloud('listUsers');
      final users = (r?['users'] as List<dynamic>? ?? const [])
          .cast<Map<String, dynamic>>()
          .map((u) => (email: u['email'] as String? ?? '(no email)', admin: u['admin'] == true))
          .toList();
      if (mounted) setState(() => _people = users);
    } on ApiException catch (err) {
      if (mounted) setState(() => _error = err.message);
    }
  }

  Future<void> _addPerson() async {
    final added = await showModalBottomSheet<String>(
      context: context,
      isScrollControlled: true,
      backgroundColor: SportColors.panel,
      builder: (_) => _AddPersonSheet(client: widget.client),
    );
    if (added == null || !mounted) return;
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(content: Text('Added $added — give them their password to sign in')),
    );
    unawaited(_load());
  }

  @override
  Widget build(BuildContext context) {
    final people = _people;
    return Scaffold(
      appBar: AppBar(
        backgroundColor: SportColors.panel,
        title: const Text('People'),
      ),
      floatingActionButton: FloatingActionButton.extended(
        onPressed: _addPerson,
        backgroundColor: SportColors.awake,
        icon: const Icon(Icons.person_add_alt_1),
        label: const Text('Add person'),
      ),
      body: _error != null
          ? Center(
              child: Padding(
                padding: const EdgeInsets.all(24),
                child: Text(_error!, style: const TextStyle(color: SportColors.muted)),
              ),
            )
          : people == null
          ? const Center(child: CircularProgressIndicator())
          : ListView.separated(
              padding: const EdgeInsets.fromLTRB(14, 14, 14, 96),
              itemCount: people.length,
              separatorBuilder: (_, __) => const SizedBox(height: 8),
              itemBuilder: (context, i) => Material(
                color: SportColors.panel,
                borderRadius: BorderRadius.circular(12),
                child: ListTile(
                  shape: RoundedRectangleBorder(
                    borderRadius: BorderRadius.circular(12),
                    side: const BorderSide(color: SportColors.border),
                  ),
                  leading: Icon(
                    people[i].admin ? Icons.admin_panel_settings : Icons.person_outline,
                    color: people[i].admin ? SportColors.tracking : SportColors.muted,
                  ),
                  title: Text(people[i].email, style: const TextStyle(color: SportColors.ink)),
                  subtitle: people[i].admin
                      ? const Text('Admin', style: TextStyle(color: SportColors.muted))
                      : null,
                ),
              ),
            ),
    );
  }
}

/// Email, a password to hand them, and whether they can add people too.
/// Pops with the email once the account exists.
class _AddPersonSheet extends StatefulWidget {
  const _AddPersonSheet({required this.client});

  final CameraClient client;

  @override
  State<_AddPersonSheet> createState() => _AddPersonSheetState();
}

class _AddPersonSheetState extends State<_AddPersonSheet> {
  static const _minPassword = 8; // as the backend's auth.ts

  final _email = TextEditingController();
  final _password = TextEditingController();
  bool _admin = false;
  bool _busy = false;
  String? _error;

  @override
  void dispose() {
    _email.dispose();
    _password.dispose();
    super.dispose();
  }

  Future<void> _submit() async {
    final email = _email.text.trim();
    if (!email.contains('@')) {
      setState(() => _error = "That isn't an email address");
      return;
    }
    if (_password.text.length < _minPassword) {
      setState(() => _error = 'The password needs at least $_minPassword characters');
      return;
    }
    setState(() {
      _busy = true;
      _error = null;
    });
    try {
      await widget.client.cloud('createUser', {
        'email': email,
        'password': _password.text,
        'admin': _admin,
      });
      if (mounted) Navigator.of(context).pop(email.toLowerCase());
    } on ApiException catch (err) {
      if (mounted) setState(() => _error = err.message);
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: EdgeInsets.fromLTRB(
        20,
        20,
        20,
        20 + MediaQuery.of(context).viewInsets.bottom,
      ),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          const Text(
            'Add person',
            style: TextStyle(fontSize: 20, fontWeight: FontWeight.w600, color: SportColors.ink),
          ),
          const SizedBox(height: 16),
          TextField(
            controller: _email,
            keyboardType: TextInputType.emailAddress,
            autocorrect: false,
            decoration: const InputDecoration(labelText: 'Email', border: OutlineInputBorder()),
          ),
          const SizedBox(height: 12),
          TextField(
            controller: _password,
            autocorrect: false,
            decoration: const InputDecoration(
              labelText: 'Password',
              helperText: 'Tell them this; they can change it with “Forgot password?”',
              border: OutlineInputBorder(),
            ),
          ),
          SwitchListTile(
            contentPadding: EdgeInsets.zero,
            value: _admin,
            onChanged: (v) => setState(() => _admin = v),
            title: const Text('Admin'),
            subtitle: const Text('Can add people too'),
          ),
          if (_error != null)
            Padding(
              padding: const EdgeInsets.only(bottom: 8),
              child: Text(_error!, style: const TextStyle(color: SportColors.recording)),
            ),
          FilledButton(
            onPressed: _busy ? null : _submit,
            style: FilledButton.styleFrom(
              minimumSize: const Size.fromHeight(48),
              backgroundColor: SportColors.awake,
            ),
            child: Text(_busy ? 'Adding…' : 'Add person'),
          ),
        ],
      ),
    );
  }
}
