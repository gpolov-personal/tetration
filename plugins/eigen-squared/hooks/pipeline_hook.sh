#!/bin/bash
# eigen-squared pipeline controller hook
# Fires on Claude Code "Stop" event
# Responsibilities: env setup, lockfile, branch checkout, delegate to Python
#
# This script is copied into $EIGEN_ROOT/.eigen/ by eigen_start.
# It sources .eigen/env (in the same directory) for environment variables,
# resolves the correct git branch for the next command, checks it out,
# then delegates scheduling to pipeline_controller.py (also in this directory).

set -euo pipefail

# ── 1. Source environment ──

# The hook script lives at $EIGEN_ROOT/.eigen/pipeline_hook.sh
# The env file lives at $EIGEN_ROOT/.eigen/env (same directory)
HOOK_DIR="$(cd "$(dirname "$0")" && pwd)"
EIGEN_ENV_FILE="$HOOK_DIR/env"

if [ ! -f "$EIGEN_ENV_FILE" ]; then
    exit 0  # No env file — hook not set up for this project
fi

# Guard against syntax errors in env file
source "$EIGEN_ENV_FILE" || exit 0

# Verify required vars after sourcing
if [ -z "${EIGEN_ROOT:-}" ] || [ -z "${CLAUDE_TASKS_API:-}" ]; then
    exit 0  # Missing required config — silent exit
fi

STATE_FILE="$EIGEN_ROOT/eigen_initiative/phases/pipeline_state.json"
if [ ! -f "$STATE_FILE" ]; then
    exit 0  # No pipeline state — nothing to do
fi

EIGEN_DIR="$EIGEN_ROOT/.eigen"
LOCK_FILE="$EIGEN_DIR/hook.lock"
mkdir -p "$EIGEN_DIR"

# ── 2. Lockfile — prevent concurrent hook runs ──

# flock is Linux-only. On macOS, use mkdir-based lock as fallback.
if command -v flock &>/dev/null; then
    exec 200>"$LOCK_FILE"
    if ! flock -n 200; then
        exit 0  # Another hook invocation is running — skip
    fi
    # Lock released automatically when fd 200 closes (script exit)
else
    # macOS fallback: mkdir is atomic
    if ! mkdir "$LOCK_FILE.d" 2>/dev/null; then
        exit 0  # Another hook invocation is running — skip
    fi
    trap 'rmdir "$LOCK_FILE.d" 2>/dev/null || true' EXIT
fi

# ── 3. Resolve target branch for the next command ──

TARGET_BRANCH=$(python3 "$HOOK_DIR/pipeline_controller.py" --resolve-branch 2>/dev/null || echo "")

if [ -z "$TARGET_BRANCH" ]; then
    # Empty = pipeline complete or at human checkpoint
    # Still run --schedule for logging/alerting purposes
    python3 "$HOOK_DIR/pipeline_controller.py" --schedule 2>/dev/null || true
    exit 0
fi

# ── 4. Checkout target branch if needed ──

cd "$EIGEN_ROOT"
CURRENT_BRANCH=$(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo "")

if [ -n "$CURRENT_BRANCH" ] && [ "$CURRENT_BRANCH" != "$TARGET_BRANCH" ]; then
    git checkout "$TARGET_BRANCH" --quiet 2>/dev/null || {
        # Checkout failed — maybe branch doesn't exist locally yet
        git fetch origin "$TARGET_BRANCH" --quiet 2>/dev/null || true
        git checkout "$TARGET_BRANCH" --quiet 2>/dev/null || {
            # Still failed — let the Python script handle the error
            python3 "$HOOK_DIR/pipeline_controller.py" --schedule 2>/dev/null || true
            exit 0
        }
    }

    git pull origin "$TARGET_BRANCH" --quiet 2>/dev/null || true
fi

# ── 5. Delegate scheduling to Python ──

python3 "$HOOK_DIR/pipeline_controller.py" --schedule 2>/dev/null || true
