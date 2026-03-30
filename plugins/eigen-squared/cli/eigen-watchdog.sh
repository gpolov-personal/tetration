#!/bin/bash
# eigen-watchdog — cron-based pipeline scheduler
#
# Runs every N minutes via cron (one cron entry per project).
# Checks if anything is running, and if not, schedules the next command.
# Detects retries and adds a warning to the prompt.
#
# Usage: eigen-watchdog.sh /path/to/project
# Cron:  */5 * * * * /home/user/.local/bin/eigen-watchdog /path/to/project

set -euo pipefail

PROJECT_ROOT="$1"
[ -z "$PROJECT_ROOT" ] && exit 1
[ -d "$PROJECT_ROOT" ] || exit 1

# Load project env (created by /eigen_start)
ENV_FILE="$PROJECT_ROOT/.eigen/env"
[ -f "$ENV_FILE" ] || exit 1
source "$ENV_FILE"

[ -z "$EIGEN_ROOT" ] && exit 1
[ -z "$CLAUDE_TASKS_API" ] && exit 1

# Export for eigen-squared CLI
export EIGEN_ROOT EIGEN_BRANCH CLAUDE_TASKS_API
export EIGEN_TELEGRAM_CHAT_ID="${EIGEN_TELEGRAM_CHAT_ID:-}"

# 1. Is anything running for this project?
RUNNING=$(curl -s "$CLAUDE_TASKS_API/api/v1/tasks" 2>/dev/null | python3 -c "
import sys, json
try:
    tasks = json.load(sys.stdin).get('tasks', [])
    for t in tasks:
        if t.get('working_dir') == '$EIGEN_ROOT' and t.get('last_run_status') == 'running':
            print('yes'); sys.exit(0)
    print('no')
except Exception:
    print('error')
" 2>/dev/null)

# If something is running or API unreachable, do nothing
[ "$RUNNING" != "no" ] && exit 0

# 2. What's next?
NEXT=$(eigen-squared next 2>/dev/null || true)
[ -z "$NEXT" ] && exit 0

# 3. Retry detection — compare next command against last task for this project
LAST_TASK_NAME=$(curl -s "$CLAUDE_TASKS_API/api/v1/tasks" 2>/dev/null | python3 -c "
import sys, json
try:
    tasks = [t for t in json.load(sys.stdin).get('tasks', [])
             if t.get('working_dir') == '$EIGEN_ROOT']
    if tasks:
        last = max(tasks, key=lambda t: t['id'])
        print(last.get('name', ''))
except Exception:
    pass
" 2>/dev/null)

EXPECTED_NAME="eigen: $NEXT"

# 4. Schedule — with retry warning if same command as last task
if [ "$LAST_TASK_NAME" = "$EXPECTED_NAME" ]; then
    eigen-squared schedule-next \
        --extra-prompt "WARNING: This is a RE-RUN. The previous execution of this command failed or timed out. Before modifying any files: (1) read your working notes if they exist, (2) check git status for partial changes, (3) verify pipeline state. Proceed carefully."
else
    eigen-squared schedule-next
fi
