#!/bin/bash
# eigen-watchdog — cron-based pipeline scheduler
#
# Runs every N minutes via cron (one cron entry per project).
# Checks if anything is running, and if not, schedules the next command.
# Detects retries and adds a warning to the prompt.
#
# Usage: eigen-watchdog.sh /path/to/project
# Cron:  */10 * * * * /home/user/.local/bin/eigen-watchdog /path/to/project >> /path/to/project/.eigen/watchdog.log 2>&1

set -euo pipefail

PROJECT_ROOT="${1:-}"
[ -z "$PROJECT_ROOT" ] && exit 1
[ -d "$PROJECT_ROOT" ] || exit 1

# Ensure only one watchdog runs per project at a time (MEDIUM-10)
LOCKFILE="$PROJECT_ROOT/.eigen/watchdog.lock"
exec 9>"$LOCKFILE"
flock -n 9 || exit 0

# Load project env (created by /eigen_start)
ENV_FILE="$PROJECT_ROOT/.eigen/env"
[ -f "$ENV_FILE" ] || exit 1
source "$ENV_FILE"

[ -z "$EIGEN_ROOT" ] && exit 1
[ -z "$CLAUDE_TASKS_API" ] && exit 1

# Warn if env file is older than settings.json (MEDIUM-9)
SETTINGS="$PROJECT_ROOT/.claude/settings.json"
if [ -f "$SETTINGS" ] && [ "$SETTINGS" -nt "$ENV_FILE" ]; then
    echo "[$(date -u +%FT%TZ)] WARN: .eigen/env is older than .claude/settings.json — run 'eigen-squared write-env' to sync"
fi

# Export for eigen-squared CLI
export EIGEN_ROOT EIGEN_BRANCH CLAUDE_TASKS_API
export EIGEN_TELEGRAM_CHAT_ID="${EIGEN_TELEGRAM_CHAT_ID:-}"

# 1. Is anything running for this project? (HIGH-3, HIGH-5)
RUNNING=$(curl -sf "$CLAUDE_TASKS_API/api/v1/tasks" 2>/dev/null | \
    EIGEN_ROOT="$EIGEN_ROOT" python3 -c "
import os, sys, json
try:
    root = os.environ['EIGEN_ROOT']
    tasks = json.load(sys.stdin).get('tasks', [])
    for t in tasks:
        if t.get('working_dir') == root and t.get('last_run_status') == 'running':
            print('yes'); sys.exit(0)
    print('no')
except Exception:
    print('error')
" 2>/dev/null || true)

if [ "$RUNNING" = "error" ] || [ -z "$RUNNING" ]; then
    echo "[$(date -u +%FT%TZ)] WARN: claude-tasks API unreachable at $CLAUDE_TASKS_API"
    exit 1
fi
[ "$RUNNING" = "yes" ] && exit 0

# 2. What's next? (HIGH-1, HIGH-2)
NEXT_ERR=$(mktemp)
trap 'rm -f "$NEXT_ERR"' EXIT
NEXT_EXIT=0
NEXT_JSON=$(eigen-squared next --json 2>"$NEXT_ERR") || NEXT_EXIT=$?
if [ $NEXT_EXIT -ne 0 ]; then
    echo "[$(date -u +%FT%TZ)] ERROR: eigen-squared next failed (exit $NEXT_EXIT): $(cat "$NEXT_ERR")"
    exit 1
fi

EXPECTED_NAME=$(echo "$NEXT_JSON" | EIGEN_ROOT="$EIGEN_ROOT" python3 -c "
import sys, json
try:
    d = json.load(sys.stdin)
    cmd = d.get('command')
    if not cmd:
        sys.exit(0)
    ctx = d.get('context', {})
    scope = ctx.get('scope', '')
    phase = ctx.get('phase')
    epic = ctx.get('epic')
    if scope == 'initiative':
        print(f'eigen: {cmd}')
    elif scope == 'phase':
        print(f'eigen: {cmd} P{phase}')
    else:
        print(f'eigen: {cmd} P{phase}.E{epic}')
except Exception:
    pass
" 2>/dev/null)
[ -z "$EXPECTED_NAME" ] && exit 0

# 3. Retry detection — compare full task name against last task for this project (HIGH-5)
LAST_TASK_NAME=$(curl -sf "$CLAUDE_TASKS_API/api/v1/tasks" 2>/dev/null | \
    EIGEN_ROOT="$EIGEN_ROOT" python3 -c "
import os, sys, json
try:
    root = os.environ['EIGEN_ROOT']
    tasks = [t for t in json.load(sys.stdin).get('tasks', [])
             if t.get('working_dir') == root]
    if tasks:
        last = max(tasks, key=lambda t: t['id'])
        print(last.get('name', ''))
except Exception:
    pass
" 2>/dev/null || true)

IS_RETRY=false
[ "$LAST_TASK_NAME" = "$EXPECTED_NAME" ] && IS_RETRY=true

# 4. Schedule (HIGH-4)
EXIT_CODE=0
if [ "$IS_RETRY" = true ]; then
    echo "[$(date -u +%FT%TZ)] INFO: retry detected for $EXPECTED_NAME (last task name matches)"
    eigen-squared schedule-next --extra-prompt "WARNING: This is a RE-RUN. The previous execution of this command failed or timed out. Before modifying any files: (1) read your working notes if they exist, (2) check git status for partial changes, (3) verify pipeline state. Proceed carefully." || EXIT_CODE=$?
else
    eigen-squared schedule-next || EXIT_CODE=$?
fi

if [ $EXIT_CODE -eq 2 ]; then
    echo "[$(date -u +%FT%TZ)] STALLED: pipeline stalled after max retries for $EXPECTED_NAME"
    # Notify via telegram if configured
    if [ -n "${EIGEN_TELEGRAM_CHAT_ID:-}" ]; then
        curl -sf "$CLAUDE_TASKS_API/api/v1/notify" \
            -H "Content-Type: application/json" \
            -d "{\"chat_id\": \"$EIGEN_TELEGRAM_CHAT_ID\", \"message\": \"eigen-squared STALLED: $EXPECTED_NAME after max retries. Manual intervention required.\"}" \
            2>/dev/null || true
    fi
    exit 2
elif [ $EXIT_CODE -ne 0 ]; then
    echo "[$(date -u +%FT%TZ)] ERROR: eigen-squared schedule-next failed (exit $EXIT_CODE)"
    exit 1
else
    RETRY_LABEL=""
    [ "$IS_RETRY" = true ] && RETRY_LABEL=" (RE-RUN)"
    echo "[$(date -u +%FT%TZ)] SCHEDULED: $EXPECTED_NAME$RETRY_LABEL"
fi
