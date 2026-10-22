#!/usr/bin/env bash
# SportCam checks for Claude Code (replaces the GitHub Actions workflow).
#
#   tools/claude-check.sh          Stop-hook mode: run the checks that the
#                                  uncommitted changes touch. On failure, print
#                                  the failures to stderr and exit 2, which
#                                  tells Claude to keep working and fix them.
#   tools/claude-check.sh all      run every check (also: npm run check)
#
# Wired up in the repo's .claude/settings.json as a Stop hook. A state that
# already passed is remembered (by a hash of the diff), so an unchanged tree
# isn't re-tested on every stop. After 3 consecutive failed stops on the same
# failures it lets Claude stop and tells the user instead of looping.
set -u

app=$(cd "$(dirname "$0")/.." && pwd)
cd "$app"
gitdir=$(git rev-parse --absolute-git-dir)
mode=${1:-hook}
hook_input=""
[ "$mode" = hook ] && [ ! -t 0 ] && hook_input=$(cat || true)

# --- what changed --------------------------------------------------------------
changed=$( { git diff --name-only --relative HEAD; git ls-files --others --exclude-standard; } 2>/dev/null | sort -u)
if [ "$mode" = hook ]; then
    [ -z "$changed" ] && exit 0
    fingerprint=$( { git diff --relative HEAD; git ls-files --others --exclude-standard -z | xargs -0 -r sha1sum; } 2>/dev/null | sha1sum | cut -c1-40)
    if [ "$(cat "$gitdir/sportcam-check-pass" 2>/dev/null)" = "$fingerprint" ]; then
        rm -f "$gitdir/sportcam-check-attempts"
        exit 0
    fi
fi
touches() { [ "$mode" = all ] || printf '%s\n' "$changed" | grep -Eq "$1"; }

# --- running checks ------------------------------------------------------------
log=$(mktemp -d)
trap 'rm -rf "$log"' EXIT
failed=()
skipped=()
ran=()
run() {   # run <name> <command...>
    local name=$1; shift
    ran+=("$name")
    if ! "$@" >"$log/$name.out" 2>&1; then failed+=("$name"); fi
}

# Python test environment for the Pi software (system python lacks its deps).
venv="$app/.venv-test"
py_deps="aiohttp zeroconf pyserial simple-pid numpy opencv-python-headless"
ensure_venv() {
    [ -x "$venv/bin/python" ] && [ "$(cat "$venv/.deps" 2>/dev/null)" = "$py_deps" ] && return 0
    if command -v uv >/dev/null; then
        uv venv -q --allow-existing "$venv" && uv pip install -q --python "$venv/bin/python" $py_deps
    else
        python3 -m venv "$venv" && "$venv/bin/pip" install -q $py_deps
    fi && echo "$py_deps" >"$venv/.deps"
}
device_tests() {   # device_tests <build>
    local dir="src/$1/device" t rc=0
    for t in "$dir"/tests/test_*.py; do
        echo "== $t"
        (cd "$dir" && "$venv/bin/python" "tests/$(basename "$t")") || rc=1
    done
    return $rc
}

if touches '\.md$|^tools/check-build-markers\.py$'; then
    run docs-build-markers python3 tools/check-build-markers.py
fi

if touches '^cad/|^[^/]+/cad/|^src/[^/]+/device/sportcam/config\.py$'; then
    if command -v openscad >/dev/null; then
        run cad-fit python3 cad/fit.py --check --deep
    else
        run cad-fit python3 cad/fit.py --check
        skipped+=("cad-fit --deep (OpenSCAD not installed)")
    fi
fi

if touches '^src/backend/|^src/web/|^package(-lock)?\.json$'; then
    [ -d node_modules ] || npm install --no-audit --no-fund >"$log/npm-install.out" 2>&1
    run typecheck npm run --silent typecheck
fi
if touches '^src/backend/'; then
    if command -v java >/dev/null; then
        run backend-tests npm test --silent
    else
        skipped+=("backend-tests (Java not installed; the Firebase emulators need it)")
    fi
fi

for build in with_uwb without_uwb; do
    if touches "^src/$build/device/"; then
        if ensure_venv >"$log/venv.out" 2>&1; then
            run "device-tests-$build" device_tests "$build"
        else
            failed+=("venv"); cp "$log/venv.out" "$log/venv.out" 2>/dev/null
        fi
    fi
done

if touches '^src/app_flutter/'; then
    if command -v dart >/dev/null; then
        run flutter-models sh -c 'cd src/app_flutter && dart run tool/verify_models.dart'
    else
        skipped+=("flutter-models (Dart SDK not installed)")
    fi
fi

if touches '^tools/docs-(server\.mjs|viewer\.js)$'; then
    run docs-viewer-syntax sh -c 'node --check tools/docs-server.mjs && node --check tools/docs-viewer.js'
fi

# --- report --------------------------------------------------------------------
if [ ${#failed[@]} -eq 0 ]; then
    [ "$mode" = hook ] && { echo "$fingerprint" >"$gitdir/sportcam-check-pass"; rm -f "$gitdir/sportcam-check-attempts"; }
    if [ "$mode" = all ]; then
        echo "SportCam checks passed: ${ran[*]:-none}"
        [ ${#skipped[@]} -gt 0 ] && printf 'skipped: %s\n' "${skipped[@]}"
    fi
    exit 0
fi

report() {
    echo "SportCam checks FAILED: ${failed[*]}"
    echo "Fix the code (not the tests, unless a test is wrong) until these pass. Re-run with: sport_cam/tools/claude-check.sh all"
    for name in "${failed[@]}"; do
        echo
        echo "---- $name (last 60 lines) ----"
        tail -n 60 "$log/$name.out" 2>/dev/null
    done
    [ ${#skipped[@]} -gt 0 ] && printf '\nskipped: %s\n' "${skipped[@]}"
}

if [ "$mode" = all ]; then
    report
    exit 1
fi

# Hook mode: block the stop so Claude fixes it, but not forever.
signature=$(printf '%s ' "${failed[@]}")
attempts_file="$gitdir/sportcam-check-attempts"
read -r last_sig count <<<"$(cat "$attempts_file" 2>/dev/null)"
[ "$last_sig" = "${signature// /,}" ] && count=$((count + 1)) || count=1
echo "${signature// /,} $count" >"$attempts_file"
if [ "$count" -gt 3 ]; then
    rm -f "$attempts_file"
    msg="SportCam checks still failing after 3 fix attempts: ${failed[*]}. Run sport_cam/tools/claude-check.sh all to see the output."
    printf '{"systemMessage": %s}\n' "$(printf '%s' "$msg" | python3 -c 'import json,sys; print(json.dumps(sys.stdin.read()))')"
    exit 0
fi
report >&2
exit 2
