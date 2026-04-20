---
name: lite_start
description: ONE-TIME launcher — configure environment, install CLI + watchdog, initialize a fresh eigen-lite pipeline
---

# lite_start — Launch the Lite Pipeline

## Pipeline Context

```
lite_start (you are here)
    │
    ▼ [autonomous mode: cron watchdog schedules commands automatically]
    │ [manual mode: user runs each command by hand]
    │
    ▼
lite_plan → lite_swarm ↔ lite_review (loop per epic)
```

ONE-TIME interactive launcher. Validates the environment, collects configuration, installs the `eigen-lite` CLI + watchdog globally, and initialises `pipeline_state_lite.json`. You never run `/lite_start` again for this initiative — use `/lite_plan` to do the actual planning.

**This command is for brand new lite pipelines ONLY.** If `pipeline_state_lite.json` already exists, `eigen-lite init` will refuse unless `--force` is passed.

## Flag: `--reinstall-cli-only`

If invoked as `/lite_start --reinstall-cli-only`, skip every step except **Step 7.1** (install `eigen-lite` CLI wrapper). Useful after a plugin version bump.

---

## Step 1: Check Environment Variables

The lite pipeline requires these in the project's `.claude/settings.json` (never the shell — prevents cross-project contamination):

- `EIGEN_ROOT` — absolute path to project root
- `EIGEN_BRANCH` — default branch (e.g. `main`)
- `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS` — `"1"` (required for `lite_swarm`)

Optional:
- `CLAUDE_TASKS_API` — required in autonomous mode only
- `HUMAN_SWARM_FALLBACK` — mode flag
- `WORKERS_MODEL` — `"opus"` (default) or `"sonnet"`
- `WATCHDOG_INTERVAL` — cron interval in minutes (default 10)
- `EIGEN_TELEGRAM_CHAT_ID` — optional notifications

### 1.1 Shell-only vars → ERROR

If any of the required vars are set in the shell but NOT in `.claude/settings.json`, **STOP** with the same error message as `eigen_start` (shell leakage risk).

### 1.2 Project already configured → proceed to Step 2

If `.claude/settings.json` already has a coherent env block → proceed.

### 1.3 First-time setup

Ask, in order:

1. **EIGEN_ROOT** (default: `pwd`)
2. **EIGEN_BRANCH** — verify it exists (`git branch --list`). If not, offer: (a) create from current, (b) create from another, (c) re-enter.
3. **Mode**:
   ```
   1. Autonomous (recommended) — cron watchdog schedules commands
   2. Manual — you trigger each command
   ```
   `1` → `HUMAN_SWARM_FALLBACK=false`. `2` → `HUMAN_SWARM_FALLBACK=true`.
4. **CLAUDE_TASKS_API** (autonomous only, default `http://localhost:8080`)
5. **WATCHDOG_INTERVAL** (autonomous only, default `10`)
6. **WORKERS_MODEL** (`opus` default, `sonnet` also valid)
7. **EIGEN_TELEGRAM_CHAT_ID** (optional, skip with Enter)

**Initiative-specific: feature_set slug.** Unlike eigen_start, which reads initiative docs from disk, lite collects a short slug up front and defers the detailed feature interview to `/lite_plan`:

```
What's a short slug for this initiative? (letters, digits, dashes, 3-30 chars)

Example: "add-user-auth" or "refactor-billing"
```

Validate: `^[a-z][a-z0-9-]{2,29}$`. Re-ask on mismatch.

Write `.claude/settings.json` merging with any existing content:

```json
{
  "env": {
    "EIGEN_ROOT": "...",
    "EIGEN_BRANCH": "...",
    "CLAUDE_TASKS_API": "<or empty>",
    "WORKERS_MODEL": "opus",
    "HUMAN_SWARM_FALLBACK": "false",
    "WATCHDOG_INTERVAL": "10",
    "CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS": "1",
    "EIGEN_TELEGRAM_CHAT_ID": "<or empty>",
    "teammateMode": "tmux"
  }
}
```

Print the restart instructions:
```
Settings saved. Restart Claude Code to pick them up:
  exit, then:  claude
  /lite_start
```

**STOP** here on first run — user must restart.

---

## Step 2: Verify claude-tasks (autonomous only)

Skip if `HUMAN_SWARM_FALLBACK=true`.

```bash
curl -sf "$CLAUDE_TASKS_API/api/v1/health"
```

If it fails, **STOP** with instructions to start `claude-tasks serve` (or switch to manual).

---

## Step 3: Check Pipeline State (must be fresh)

```bash
test -f "$EIGEN_ROOT/eigen_initiative/phases/pipeline_state_lite.json" && echo EXISTS
```

If it exists → **STOP.** Print:
```
ERROR: lite pipeline already in progress.

State file exists at:
  $EIGEN_ROOT/eigen_initiative/phases/pipeline_state_lite.json

/lite_start is for fresh pipelines only. To continue, just run:
  /lite_plan

To start completely over, delete the state file first:
  rm $EIGEN_ROOT/eigen_initiative/phases/pipeline_state_lite.json
```

Also refuse if `$EIGEN_ROOT/eigen_initiative/phases/pipeline_state.json` exists (squared pipeline). Tell the user they can't run both in the same repo without manual namespace work.

---

## Step 4: Commit Settings (if not gitignored)

Same logic as `eigen_start` Step 5 — if `.claude/settings.json` is not gitignored, `git add/commit/push` to `$EIGEN_BRANCH` so integration branches inherit config. If gitignored, offer the `!.claude/settings.json` exception.

---

## Step 5: Pre-Launch Summary

```
=== eigen-lite — Pre-Launch Summary ===

Project:           $EIGEN_ROOT
Branch:            $EIGEN_BRANCH
Mode:              <autonomous | manual>
Workers Model:     <WORKERS_MODEL>
<if autonomous:>
claude-tasks API:  $CLAUDE_TASKS_API
Watchdog interval: every <WATCHDOG_INTERVAL> minutes
<end if>

Feature set:       <slug>
Pipeline State:    not started (fresh)

Pipeline sequence:
  lite_plan  → lite_swarm ↔ lite_review (per epic)

<if autonomous:>
Scheduling: cron watchdog (every <WATCHDOG_INTERVAL> minutes)
Epics execute one at a time in dependency order.
<end if>
```

---

## Step 6: Install CLI + Watchdog

### 6.1 Install `eigen-lite` CLI globally

Discover the plugin path via Glob (`cli/__main__.py` under `~/.claude/plugins/cache/tetration/eigen-lite/<version>/`). Store as `PLUGIN_PATH`. Read `$PLUGIN_PATH/.claude-plugin/plugin.json` for `version`.

Check if already installed:
```bash
test -x ~/.local/bin/eigen-lite && ~/.local/bin/eigen-lite --version
```

- Not installed → install.
- Same version → skip, print `eigen-lite v<V> already installed`.
- Different version → ask user: overwrite or skip.

Install wrapper:
```bash
mkdir -p ~/.local/bin
cat > ~/.local/bin/eigen-lite <<WRAPPER_EOF
#!/bin/bash
# eigen-lite CLI v<VERSION> — created by /lite_start
PLUGIN_PATH="<RESOLVED_PLUGIN_PATH>"
if [ ! -d "$PLUGIN_PATH/cli" ]; then
    echo "ERROR: eigen-lite plugin not found at $PLUGIN_PATH"
    echo "Run /lite_start --reinstall-cli-only to fix."
    exit 1
fi
export PYTHONPATH="$PLUGIN_PATH"
exec python3 -m cli "\$@"
WRAPPER_EOF
chmod +x ~/.local/bin/eigen-lite
```

Verify: `eigen-lite --version`. If `~/.local/bin` isn't on `PATH`, print the bashrc/zshrc fix instruction.

### 6.2 Install `eigen-lite-watchdog` (autonomous only)

Skip if manual. Copy the watchdog:
```bash
cp "$PLUGIN_PATH/cli/eigen-lite-watchdog.sh" ~/.local/bin/eigen-lite-watchdog
chmod +x ~/.local/bin/eigen-lite-watchdog
```

### 6.3 Create `.eigen-lite/` and env file

```bash
eigen-lite install --root "$EIGEN_ROOT" --branch "$EIGEN_BRANCH" \
    --tasks-api "${CLAUDE_TASKS_API:-http://localhost:8080}" \
    ${EIGEN_TELEGRAM_CHAT_ID:+--telegram "$EIGEN_TELEGRAM_CHAT_ID"}
```

This creates `.eigen-lite/env` and `.eigen-lite/` directory. Add `.eigen-lite/` to `.gitignore`:
```bash
grep -qxF '.eigen-lite/' "$EIGEN_ROOT/.gitignore" 2>/dev/null || \
    echo '.eigen-lite/' >> "$EIGEN_ROOT/.gitignore"
```

### 6.4 Initialise pipeline state

```bash
eigen-lite init --feature-set "<slug>" --epic-count 0
```

`epic_count=0` because `lite_plan` sets the real count after Stage D.

### 6.5 Verify

```bash
eigen-lite validate
eigen-lite status
```

Expect `valid: true` and `plan.status: not_started`.

---

## Step 7: Launch

### Autonomous mode

Check for an existing cron entry for this project:
```bash
crontab -l 2>/dev/null | grep "eigen-lite-watchdog.*$EIGEN_ROOT"
```

If missing, install:
```bash
(crontab -l 2>/dev/null; echo "*/$WATCHDOG_INTERVAL * * * * ~/.local/bin/eigen-lite-watchdog $EIGEN_ROOT >> $EIGEN_ROOT/.eigen-lite/watchdog.log 2>&1") | crontab -
```

Print:
```
=== eigen-lite Launched (Autonomous Mode) ===

Watchdog installed — checks every <WATCHDOG_INTERVAL> minutes.
On its next tick, it will detect the pending lite_plan and schedule it.

IMPORTANT: these must be running:
  1. claude-tasks server:  claude-tasks serve
  2. cron daemon:          service cron status

Monitor:
  - Pipeline state:   eigen-lite status
  - Watchdog log:     tail -f $EIGEN_ROOT/.eigen-lite/watchdog.log
  - Hook log:         cat $EIGEN_ROOT/.eigen-lite/hook_log.jsonl

The pipeline runs autonomously until the last epic converges.
No E2E stop gate like squared — lite runs straight through.

Watchdog management:
  - View cron:       crontab -l | grep eigen-lite-watchdog
  - Pause:           crontab -l | grep -v "eigen-lite-watchdog.*$EIGEN_ROOT" | crontab -
  - Resume:          (crontab -l 2>/dev/null; echo "*/$WATCHDOG_INTERVAL * * * * ~/.local/bin/eigen-lite-watchdog $EIGEN_ROOT >> $EIGEN_ROOT/.eigen-lite/watchdog.log 2>&1") | crontab -
  - Run now:         eigen-lite-watchdog $EIGEN_ROOT
```

### Manual mode

Print:
```
=== eigen-lite Initialised (Manual Mode) ===

To plan the initiative, run:
  /lite_plan

After each command completes, check what's next:
  eigen-lite status
  eigen-lite next

Then run the next command manually. To switch to autonomous later,
set HUMAN_SWARM_FALLBACK=false in .claude/settings.json and install
the cron:
  (crontab -l 2>/dev/null; echo "*/10 * * * * ~/.local/bin/eigen-lite-watchdog $EIGEN_ROOT >> $EIGEN_ROOT/.eigen-lite/watchdog.log 2>&1") | crontab -
```

---

## Important Notes

- **ONE-TIME use only**: for fresh pipelines. For an existing lite pipeline, just run `/lite_plan`.
- **Env vars live in `.claude/settings.json`**: never in the shell.
- **Watchdog polls, doesn't chain**: commands don't schedule their successors; the watchdog does.
- **One cron per project**: each project gets its own entry; they run independently.
- **No coexistence with squared in the same repo**: `lite_start` refuses if `pipeline_state.json` exists. See `plugins/eigen-lite/README.md` for the rationale.
- **Feature interview is deferred to `/lite_plan`**: this command only collects a slug. The 2–5 feature description interview happens in `lite_plan` Stage A.
