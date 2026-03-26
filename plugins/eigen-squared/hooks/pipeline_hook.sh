#!/bin/bash
# eigen-squared pipeline controller hook (v2)
# Fires on Claude Code "Stop" event.
# Delegates all logic to the eigen-squared CLI.
#
# This script is copied into $EIGEN_ROOT/.eigen/ by eigen_start.

set -euo pipefail

HOOK_DIR="$(cd "$(dirname "$0")" && pwd)"

# Source environment (EIGEN_ROOT, CLAUDE_TASKS_API, etc.)
[ -f "$HOOK_DIR/env" ] && source "$HOOK_DIR/env" || exit 0
[ -z "${EIGEN_ROOT:-}" ] && exit 0
[ -f "$EIGEN_ROOT/eigen_initiative/phases/pipeline_state.json" ] || exit 0

# Lockfile — prevent concurrent hook runs
LOCK_FILE="$EIGEN_ROOT/.eigen/hook.lock"
if command -v flock &>/dev/null; then
    exec 200>"$LOCK_FILE"
    flock -n 200 || exit 0
else
    mkdir "$LOCK_FILE.d" 2>/dev/null || exit 0
    trap 'rmdir "$LOCK_FILE.d" 2>/dev/null || true' EXIT
fi

# The CLI handles: branch resolution, checkout, pull, scheduling
python3 -m cli schedule-next 2>/dev/null || true
