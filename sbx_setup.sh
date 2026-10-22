#!/usr/bin/env bash
# Tools for the Docker sandbox that sbx_run_claude.sh / sbx_resume_claude.sh
# start, installed once and kept on the host.
#
# Everything goes in .sbx-cache/ in this repo. The repo is mounted from the
# host, so the cache survives the sandbox being reset or recreated; only the
# first session after a fresh checkout pays for the downloads.
#
#   flutter + dart   .sbx-cache/flutter            (the app, tool/verify_models.dart)
#   pub packages     .sbx-cache/pub-cache
#   Firebase jars    .sbx-cache/firebase           (~/.cache/firebase links here)
#   python test env  sport_cam/.venv-test          (tools/claude-check.sh venv)
#   node_modules     sport_cam/node_modules
#
# Run by the SessionStart hook in .claude/settings.json on every session
# start and resume; once installed it only checks and exits in about a second.
# Safe to run by hand. Does nothing outside Linux (i.e. on the Mac itself).
set -u

[ "$(uname -s)" = Linux ] || exit 0

repo=$(cd "$(dirname "$0")" && pwd)
cache="$repo/.sbx-cache"
mkdir -p "$cache"
touch "$cache/.metadata_never_index"      # keep Spotlight out of it on the Mac
log="$cache/setup.log"
flutter_dir="$cache/flutter"
say() { echo "[sbx-setup] $*" >&2; }

# ---- environment for every later shell ---------------------------------------
# The persistent env file is sourced before each Bash command (CLAUDE_ENV_FILE).
# Add our lines once, marked, so re-running never duplicates them.
env_file=${CLAUDE_ENV_FILE:-/etc/sandbox-persistent.sh}
marker="# --- sbx_setup.sh ---"
if [ -w "$env_file" ] && ! grep -qF "$marker" "$env_file"; then
    cat >>"$env_file" <<EOF
$marker
export PATH="$flutter_dir/bin:\$PATH"
export PUB_CACHE="$cache/pub-cache"
export FLUTTER_SUPPRESS_ANALYTICS=true
EOF
fi
export PATH="$flutter_dir/bin:$PATH" PUB_CACHE="$cache/pub-cache" FLUTTER_SUPPRESS_ANALYTICS=true

# ---- Flutter (with its own Dart) ---------------------------------------------
if [ ! -f "$cache/.flutter-ready" ]; then
    say "installing Flutter into .sbx-cache (one time, a few minutes)…"
    [ -d "$flutter_dir/.git" ] || git clone -q --depth 1 -b stable \
        https://github.com/flutter/flutter.git "$flutter_dir" >>"$log" 2>&1
    # The first run downloads the Dart SDK and engine for this machine.
    if flutter --version >>"$log" 2>&1 && dart --version >>"$log" 2>&1; then
        touch "$cache/.flutter-ready"
    else
        say "Flutter install failed — see $log"
    fi
fi

# ---- Firebase emulator jars ----------------------------------------------------
# firebase-tools keeps them in ~/.cache/firebase; point that at the cache,
# moving anything already downloaded.
fb="$HOME/.cache/firebase"
if [ ! -L "$fb" ]; then
    mkdir -p "$cache/firebase" "$HOME/.cache"
    if [ -d "$fb" ]; then
        cp -a "$fb/." "$cache/firebase/" >>"$log" 2>&1 && rm -rf "$fb"
    fi
    [ -e "$fb" ] || ln -s "$cache/firebase" "$fb"
fi

# ---- project dependencies (already on the host mount; only if missing) ---------
app="$repo/sport_cam"
if [ -d "$app" ]; then
    [ -d "$app/node_modules" ] || { say "npm install…"; (cd "$app" && npm install --no-audit --no-fund >>"$log" 2>&1) || say "npm install failed — see $log"; }
    bash "$app/tools/claude-check.sh" venv >>"$log" 2>&1 || say "python test env failed — see $log"
fi
exit 0
