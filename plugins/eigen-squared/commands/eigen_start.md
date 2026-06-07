---
name: eigen_start
description: ONE-TIME launcher — validate environment and kick off a fresh eigen-squared pipeline (autonomous or manual mode)
---

# Eigen Start — Launch the Pipeline

## Pipeline Context

```
eigen_start (you are here)
    │
    ▼ [autonomous mode: cron watchdog schedules commands automatically]
    │ [manual mode: user runs each command by hand]
    │
    ▼
time_split ↔ deepen_time_split → bootstrap_converge →
space_split_converge → [per epic: plan → create → orchestrate → review] →
STOP at E2E Testing epic convergence
```

This is the **ONE-TIME interactive launcher**. It validates the environment, collects configuration from the user, initializes `pipeline_state.json` via the `eigen-squared` CLI, and optionally installs the watchdog cron for autonomous execution. You never run `/eigen_start` again for this pipeline.

## Your Role

You are a **ONE-TIME pipeline launcher**. You validate that everything is ready — environment variables, initiative documents, agent teams — then initialize state and optionally set up autonomous scheduling. In autonomous mode, a cron watchdog polls and schedules commands automatically. In manual mode, the user triggers each command.

This command is for **brand new pipelines ONLY**. If the pipeline has already started, use `/eigen_continue` instead.

This is an **interactive command** — it asks the user for configuration values on first run.

---

## Flag: `--reinstall-cli-only`

If the user invokes this command with `--reinstall-cli-only` (e.g., `/eigen_start --reinstall-cli-only`), **skip ALL steps** and jump directly to **Step 7.1** (Install the `eigen-squared` CLI globally). After completing Step 7.1, print the installed version and **STOP** — do not run Steps 7.2–7.6 or any other step.

This allows updating the CLI wrapper after a plugin version change without requiring a fresh pipeline.

---

## Step 1: Check Environment Variables

The eigen-squared pipeline requires these env vars to be set in the project's `.claude/settings.json` (NOT in the shell). This ensures each project has its own isolated configuration and prevents cross-project mix-ups.

### 1.1 Check for Shell-Only Variables (ERROR condition)

Check if `EIGEN_ROOT`, `EIGEN_BRANCH`, `CLAUDE_TASKS_API`, or `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS` are set in the current environment BUT do NOT exist in `.claude/settings.json`:

```bash
# Check if settings.json exists and has env block
test -f .claude/settings.json && cat .claude/settings.json
```

**If env vars are in the shell but NOT in `.claude/settings.json`** → **STOP.** Print:
```
ERROR: Environment variables are set in your shell session but NOT in
this project's .claude/settings.json. This is unsafe — shell env vars
can leak between projects.

The eigen-squared pipeline requires env vars to be set ONLY in the
project's .claude/settings.json so each project is isolated.

Please unset these shell variables and run /eigen_start again:
  unset EIGEN_ROOT EIGEN_BRANCH CLAUDE_TASKS_API CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS

/eigen_start will help you set them up in .claude/settings.json.
```

### 1.2 Check for Correctly Configured Project (READY condition)

**If env vars are present in `.claude/settings.json`** (and therefore available in the session):

Verify all required vars:
- `$EIGEN_ROOT` is set and points to an existing directory
- `$EIGEN_BRANCH` is set and non-empty
- `$CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS` is `"1"`

Optional vars (may or may not be present yet):
- `$CLAUDE_TASKS_API` — required only for autonomous mode
- `$HUMAN_SWARM_FALLBACK` — determines mode

If required vars present and valid → proceed to Step 2.

If some are missing or invalid → ask the user for the missing values (same flow as 1.3).

### 1.3 First-Time Setup (NO env vars found)

**If neither shell nor settings.json has the required env vars** → interactive setup:

```
=== Eigen-Squared — First-Time Setup ===

I need to configure this project for the eigen-squared pipeline.
These values will be saved to .claude/settings.json so they persist
across sessions and are used by all pipeline tasks.
```

Ask the user for each value:

**EIGEN_ROOT:**
```
What is the absolute path to this project's root?
(This is where the code lives and where eigen_initiative/ must already exist)

Current directory is: <pwd>
Use current directory? Or enter a different path:
```

**EIGEN_BRANCH:**
```
What is the default branch for this project?
(The branch from which all work starts — typically 'main' or 'dev')

Options: main / dev / master / <custom>
```

After the user provides EIGEN_BRANCH, verify it exists locally:
```bash
git -C $EIGEN_ROOT branch --list <user's value>
```

**If the branch does NOT exist locally:**
```
Branch '<branch>' does not exist locally.

Available local branches:
  <list from: git -C $EIGEN_ROOT branch --list>

Would you like to:
  1. Create '<branch>' from the current branch (<current branch name>)
  2. Create '<branch>' from another branch (I'll list them)
  3. Enter a different branch name
```

- **Option 1**: `git -C $EIGEN_ROOT checkout -b <branch>` then `git -C $EIGEN_ROOT checkout -`
- **Option 2**: list local branches, ask user to pick, then `git -C $EIGEN_ROOT checkout -b <branch> <selected>` then `git -C $EIGEN_ROOT checkout -`
- **Option 3**: re-ask for branch name and re-verify

**If the branch exists** → proceed.

**HUMAN_SWARM_FALLBACK (mode selection):**
```
How do you want to run the pipeline?

  1. Autonomous (recommended) — a cron watchdog schedules commands
     automatically. The pipeline runs unattended. The orchestrate_swarm
     makes autonomous decisions and documents them in
     [DECISION-AUTONOMOUS] tasks for your review in the PR.
     Requires: claude-tasks server running.

  2. Manual — you trigger each command yourself. The orchestrate_swarm
     can escalate ambiguous decisions to you interactively.
     Does not require claude-tasks.

Choose mode (1/2, default: 1):
```

- **"1"** or Enter → `HUMAN_SWARM_FALLBACK=false` (autonomous)
- **"2"** → `HUMAN_SWARM_FALLBACK=true` (manual)

**CLAUDE_TASKS_API (only if autonomous mode):**

If `HUMAN_SWARM_FALLBACK=false`:
```
What is the claude-tasks API URL?
(The server must be running in serve mode)

Default: http://localhost:8080
Press Enter for default, or enter a custom URL:
```

If `HUMAN_SWARM_FALLBACK=true`: set `CLAUDE_TASKS_API=""` (not needed).

**WATCHDOG_INTERVAL (only if autonomous mode):**

If `HUMAN_SWARM_FALLBACK=false`:
```
How often should the watchdog check for work? (in minutes)

This is the interval between checks. A shorter interval means
commands start sooner after the previous one finishes, but adds
more cron overhead. 10 minutes is a good tradeoff.

Default: 10
Enter interval in minutes (or press Enter for 10):
```

Store as `WATCHDOG_INTERVAL`. Default: `10`.

If `HUMAN_SWARM_FALLBACK=true`: skip this question.

**WORKERS_MODEL (optional):**
```
Which Claude model should swarm workers use?

Valid values: "opus" (default), "sonnet"
This affects only swarm workers spawned by /orchestrate_swarm and
fixup workers from /review_swarm_pr. Planners, reviewers, and the
integrator always use opus.

Enter model (or press Enter for opus):
```

- **"opus"** or Enter → `WORKERS_MODEL=opus`
- **"sonnet"** → `WORKERS_MODEL=sonnet`
- Any other value → `WORKERS_MODEL=opus` (default)

**EIGEN_TELEGRAM_CHAT_ID (optional):**
```
Would you like Telegram notifications for pipeline progress?
If yes, enter your Telegram chat ID (e.g., 123456789 or -100123456).

To set up Telegram notifications:
  1. Create a bot via @BotFather on Telegram
  2. Send a message to your bot
  3. Call: https://api.telegram.org/bot<token>/getUpdates
  4. Copy your chat ID from the response
  5. Set the bot token in claude-tasks (one-time):
     curl -X PUT $CLAUDE_TASKS_API/api/v1/settings \
       -H 'Content-Type: application/json' \
       -d '{"telegram_bot_token": "YOUR_BOT_TOKEN"}'

Enter chat ID (or press Enter to skip):
```

**teammateMode** is always `tmux`. **CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS** is always `"1"`.

After collecting values, write `.claude/settings.json`:

```bash
mkdir -p .claude
```

Write the file:
```json
{
  "env": {
    "EIGEN_ROOT": "<user's value>",
    "EIGEN_BRANCH": "<user's value>",
    "CLAUDE_TASKS_API": "<user's value or empty>",
    "WORKERS_MODEL": "<user's value or opus>",
    "HUMAN_SWARM_FALLBACK": "<true or false>",
    "WATCHDOG_INTERVAL": "<user's value or 10>",
    "CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS": "1",
    "EIGEN_TELEGRAM_CHAT_ID": "<user's value or empty string>",
    "teammateMode": "tmux"
  }
}
```

If `.claude/settings.json` already exists with other content, **merge** the env block — do NOT overwrite other settings.

Print:
```
Settings saved to .claude/settings.json

IMPORTANT: You need to restart Claude Code for these settings to take effect.
Exit this session, then:
  cd <EIGEN_ROOT>
  claude
  /eigen_start

The settings will be loaded automatically on restart.
```

**STOP** here — the user must restart Claude Code.

---

## Step 2: Verify claude-tasks is Running (autonomous mode only)

**If `$HUMAN_SWARM_FALLBACK` is `true`** → skip this step entirely (manual mode, claude-tasks not needed).

```bash
curl -s $CLAUDE_TASKS_API/api/v1/health
```

**If the health check succeeds** → Print: `claude-tasks: healthy at $CLAUDE_TASKS_API` and continue.

**If the health check fails** → **STOP.** Print:
```
ERROR: claude-tasks is not responding at $CLAUDE_TASKS_API

Autonomous mode requires claude-tasks to be running (the watchdog
schedules commands through it).

Start it in a separate terminal:
  claude-tasks serve

Make sure it's running before re-running /eigen_start.

If you want to run in manual mode instead, re-run /eigen_start
and choose option 2 (Manual).
```

---

## Step 2.5: Check Docker Availability

Check if Docker is available. Most projects need it (container parity, local infrastructure, E2E testing), but some (libraries, CLI tools) don't. This is an early warning — `bootstrap` will enforce Docker as a hard requirement if it detects a server project.

```bash
docker --version 2>/dev/null
docker compose version 2>/dev/null
```

**If both available** → Print: `Docker: available ($(docker --version))` and continue.

**If docker or docker compose is missing** → Print warning and continue:
```
WARNING: Docker is not installed (or not on PATH).

If your project deploys a server, Docker will be required later.
Bootstrap will check and stop if Docker is needed but unavailable.

Install Docker: https://docs.docker.com/get-docker/
```

---

## Step 2.6: Check CodeGraph Availability (optional)

CodeGraph is an **optional, external** code-intelligence tool (a local tree-sitter knowledge graph over MCP + CLI). When present, pipeline agents query it instead of grep/Read to explore existing code, trace call flows, and compute change impact — cheaper and more accurate, especially in `plan_epic_converge` and `review_swarm_pr`. It is **never required**; every command degrades silently to grep/Read when it is absent (see `skills/codegraph/SKILL.md`).

```bash
command -v codegraph >/dev/null 2>&1 && codegraph --version 2>/dev/null
test -d "$EIGEN_ROOT/.codegraph" && echo ".codegraph present"
```

**If the CLI is present and `$EIGEN_ROOT/.codegraph/` exists** → Print `CodeGraph: available` and continue.

**If the CLI is present but `$EIGEN_ROOT/.codegraph/` is missing** → Recommend initializing the project index (one-time), then continue:
```
CodeGraph CLI is installed but this project is not indexed yet.
To let pipeline agents use it, run once:  codegraph init -i
(Optional — the pipeline works without it.)
```

**If the CLI is missing** → Print recommendation and continue (do NOT stop):
```
CodeGraph is not installed (optional).
It speeds up code exploration and review and runs 100% locally.

Install:  curl -fsSL https://raw.githubusercontent.com/colbymchenry/codegraph/main/install.sh | sh
   or:    npm i -g @colbymchenry/codegraph
Then index this project:  codegraph init -i

The pipeline works without it — agents fall back to grep/Read.
```

---

## Step 3: Verify Initiative Documents

Check `$EIGEN_ROOT/eigen_initiative/` exists and has the required files:

1. Verify directory exists
2. Search for initiative document: `*Initiative*` or `*initiative*` (markdown)
3. Search for blackbox requirements: `*Blackbox*` or `*blackbox*` AND `*Requirement*` (markdown)
4. Whitebox reference: `*Whitebox*` (optional)

If directory missing → **STOP.** Print:
```
ERROR: Initiative directory not found at $EIGEN_ROOT/eigen_initiative/

The eigen_initiative/ directory must exist with your initiative documents
before starting the pipeline. Use /initiative_review to help prepare them.
```

If required files missing → **STOP** with specific error listing what's needed.

Print:
```
Initiative documents:
  Initiative: <filename>
  Blackbox Requirements: <filename>
  Whitebox Reference: <filename or "not provided (optional)">
```

---

## Step 4: Check Pipeline State (must be fresh)

Check if `$EIGEN_ROOT/eigen_initiative/phases/pipeline_state.json` exists:

```bash
test -f $EIGEN_ROOT/eigen_initiative/phases/pipeline_state.json && echo "EXISTS" || echo "NOT_FOUND"
```

- **If it exists** → **STOP.** Print:
  ```
  ERROR: Pipeline is already in progress.

  A pipeline_state.json file exists at:
    $EIGEN_ROOT/eigen_initiative/phases/pipeline_state.json

  /eigen_start is for brand new pipelines ONLY.

  To continue the existing pipeline, use:
    /eigen_continue

  To start completely fresh (losing all progress), delete pipeline_state.json first:
    rm $EIGEN_ROOT/eigen_initiative/phases/pipeline_state.json
  Then run /eigen_start again.
  ```

- **If it does NOT exist** → proceed (this is a fresh start).

---

## Step 5: Commit Settings to $EIGEN_BRANCH (if not gitignored)

Integration branches created by `/create_issues_from_plan_swarm` are based on `$EIGEN_BRANCH`. If `.claude/settings.json` is committed to `$EIGEN_BRANCH`, the integration branches will have the pipeline env vars automatically.

```bash
cd $EIGEN_ROOT
# Check if .claude/settings.json is gitignored
git check-ignore -q .claude/settings.json 2>/dev/null
```

**If NOT gitignored** (exit code 1 — git does NOT ignore it):
```bash
git add .claude/settings.json
git commit -m "chore: add eigen-squared pipeline settings"
git push origin $EIGEN_BRANCH
```

Print: `Settings committed and pushed to $EIGEN_BRANCH — integration branches will inherit pipeline configuration.`

**If gitignored** (exit code 0 — git DOES ignore it):
Do NOT force-add. **STOP and ask the user**:

```
WARNING: .claude/settings.json is in .gitignore

This will cause problems in later pipeline stages — integration branches created by
/create_issues_from_plan_swarm will NOT inherit pipeline settings
(EIGEN_ROOT, EIGEN_BRANCH, CLAUDE_TASKS_API, plugin configuration).

There is a defensive fallback in /create_issues_from_plan_swarm that copies
settings into each branch, but the recommended fix is to allow
settings.json in git.

Options:
  1. Fix it now — add '!.claude/settings.json' exception to .gitignore,
     then commit settings to the branch
  2. Continue anyway — rely on the create_issues fallback
  3. Stop — I'll fix .gitignore manually and re-run /eigen_start
```

**If option 1** (fix now):
```bash
echo '!.claude/settings.json' >> $EIGEN_ROOT/.gitignore
cd $EIGEN_ROOT
git add .gitignore .claude/settings.json
git commit -m "chore: add eigen-squared pipeline settings (gitignore exception)"
git push origin $EIGEN_BRANCH
```
Print: `Fixed. .claude/settings.json is now committed and pushed — integration branches will inherit pipeline configuration.`

**If option 2** (continue):
Print: `Continuing. Settings will be available on integration branches since they inherit from $EIGEN_BRANCH.`

**If option 3** (stop):
**STOP.** Print: `Pipeline launch cancelled. Fix .gitignore and re-run /eigen_start.`

---

## Step 6: Print Pre-Launch Summary

```
=== Eigen-Squared Pipeline — Pre-Launch Summary ===

Project:            $EIGEN_ROOT
Branch:             $EIGEN_BRANCH
Mode:               <autonomous | manual>
Workers Model:      <WORKERS_MODEL>
<if autonomous:>
claude-tasks API:   $CLAUDE_TASKS_API
Watchdog interval:  every <WATCHDOG_INTERVAL> minutes
<end if>

Initiative:         <filename>
Blackbox:           <filename>
Pipeline State:     not started (fresh)

Pipeline sequence:
  time_split ↔ deepen_time_split → bootstrap_converge →
  space_split_converge → [per epic: plan → create → orchestrate → review] →
  STOP at E2E Testing epic convergence

<if autonomous:>
Scheduling: cron watchdog (every <WATCHDOG_INTERVAL> minutes)
Epics execute one at a time in dependency order.
<end if>
<if manual:>
You trigger each command manually.
Check what's next: eigen-squared status
<end if>
```

---

## Step 7: Install CLI, Initialize Pipeline, and Start Watchdog

### 7.1 Install the `eigen-squared` CLI globally

The eigen-squared CLI is a Python module inside this plugin. It needs to be accessible from any directory (commands run from `$EIGEN_ROOT`, not the plugin directory). Create a global wrapper script.

**Step 1: Discover the plugin path.** Use the Glob tool to find the `cli/__main__.py` file near this command file. The plugin cache path will look like `~/.claude/plugins/cache/tetration/eigen-squared/<version>/`. Store this as `PLUGIN_PATH`.

**Step 2: Read the version.** Read `$PLUGIN_PATH/.claude-plugin/plugin.json` and extract the `version` field (e.g., `3.0.4`). Store this as `NEW_VERSION`.

**Step 3: Check if already installed.**

```bash
test -x ~/.local/bin/eigen-squared && ~/.local/bin/eigen-squared --version 2>/dev/null
```

Compare the installed version with `NEW_VERSION`:

- **If not installed** (wrapper doesn't exist or not executable) → proceed to Step 4 (install).
- **If installed with the same version** → print `eigen-squared CLI v<VERSION> already installed — skipping.` and skip to Step 5.
- **If installed with a different version** → print a warning and ask the user:
  ```
  WARNING: eigen-squared CLI is already installed at ~/.local/bin/eigen-squared
    Installed version: <INSTALLED_VERSION>
    This plugin version: <NEW_VERSION>

  Overwriting will affect ALL projects that use this CLI.
  If another project's pipeline is running, it will start using v<NEW_VERSION>.

  Options:
    1. Overwrite — install v<NEW_VERSION> (recommended if no other pipeline is active)
    2. Skip — keep v<INSTALLED_VERSION> (use /eigen_start --reinstall-cli-only later)
  ```
  - **Option 1** → proceed to Step 4.
  - **Option 2** → skip to Step 5.

**Step 4: Create the wrapper script** at `~/.local/bin/eigen-squared`:

```bash
mkdir -p ~/.local/bin
cat > ~/.local/bin/eigen-squared << 'WRAPPER_EOF'
#!/bin/bash
# eigen-squared CLI v<VERSION> — created by /eigen_start
PLUGIN_PATH="<RESOLVED_PLUGIN_PATH>"
if [ ! -d "$PLUGIN_PATH/cli" ]; then
    echo "ERROR: eigen-squared plugin not found at $PLUGIN_PATH"
    echo "The plugin may have been updated. Run /eigen_start --reinstall-cli-only to fix."
    exit 1
fi
export PYTHONPATH="$PLUGIN_PATH"
exec python3 -m cli "$@"
WRAPPER_EOF
chmod +x ~/.local/bin/eigen-squared
```

Replace `<RESOLVED_PLUGIN_PATH>` with the actual absolute path discovered in Step 1, and `<VERSION>` with `NEW_VERSION`.

**Step 5: Verify it works:**

```bash
eigen-squared --version
```

If this fails with "command not found", `~/.local/bin` may not be on PATH. Print:
```
WARNING: ~/.local/bin is not on your PATH.
Add this to your shell profile (~/.bashrc or ~/.zshrc):
  export PATH="$HOME/.local/bin:$PATH"
Then restart your terminal or run: source ~/.bashrc
```

### 7.2 Install the `eigen-watchdog` script (autonomous mode only)

**If `$HUMAN_SWARM_FALLBACK` is `true`** → skip this step (manual mode).

Copy the watchdog script from the plugin to `~/.local/bin/eigen-watchdog`:

```bash
cp $PLUGIN_PATH/cli/eigen-watchdog.sh ~/.local/bin/eigen-watchdog
chmod +x ~/.local/bin/eigen-watchdog
```

Verify:
```bash
test -x ~/.local/bin/eigen-watchdog && echo "eigen-watchdog installed" || echo "ERROR: watchdog not installed"
```

### 7.3 Create `.eigen/` directory

```bash
mkdir -p "$EIGEN_ROOT/.eigen"
```

Create the env file (used by the watchdog cron — it sources this to get project config):
```bash
cat > "$EIGEN_ROOT/.eigen/env" <<EOF
EIGEN_ROOT="$EIGEN_ROOT"
EIGEN_BRANCH="$EIGEN_BRANCH"
CLAUDE_TASKS_API="${CLAUDE_TASKS_API:-}"
WORKERS_MODEL="${WORKERS_MODEL:-opus}"
HUMAN_SWARM_FALLBACK="${HUMAN_SWARM_FALLBACK:-false}"
WATCHDOG_INTERVAL="${WATCHDOG_INTERVAL:-10}"
EIGEN_TELEGRAM_CHAT_ID="${EIGEN_TELEGRAM_CHAT_ID:-}"
EOF
```

Add `.eigen/` to `.gitignore` if not already present:
```bash
grep -qxF '.eigen/' "$EIGEN_ROOT/.gitignore" 2>/dev/null || echo '.eigen/' >> "$EIGEN_ROOT/.gitignore"
```

### 7.4 Initialize pipeline state

```bash
eigen-squared init --initiative "<initiative name from Step 3>" --phase-count 0
```

Phase count is 0 because time_split hasn't run yet. The CLI creates `pipeline_state.json` with `time_split.status = "not_started"`.

### 7.5 Verify installation

```bash
eigen-squared validate
eigen-squared status
```

### 7.6 Start the pipeline

**If autonomous mode** (`$HUMAN_SWARM_FALLBACK` is `false`):

Check if a cron entry already exists for this project:

```bash
crontab -l 2>/dev/null | grep "eigen-watchdog.*$EIGEN_ROOT"
```

**If already exists** → print: `Watchdog cron already installed for this project — skipping.`

**If not found** → install it (use `$WATCHDOG_INTERVAL` for the cron schedule):

```bash
(crontab -l 2>/dev/null; echo "*/$WATCHDOG_INTERVAL * * * * ~/.local/bin/eigen-watchdog $EIGEN_ROOT >> $EIGEN_ROOT/.eigen/watchdog.log 2>&1") | crontab -
```

Verify:
```bash
crontab -l | grep "eigen-watchdog.*$EIGEN_ROOT"
```

Print:
```
=== Pipeline Launched (Autonomous Mode) ===

Pipeline initialized via eigen-squared CLI.
pipeline_state.json created with time_split.status = "not_started"

Watchdog cron installed — checks every <WATCHDOG_INTERVAL> minutes.
The watchdog will detect the pending time_split and schedule it automatically.

IMPORTANT: Make sure these are running:
  1. claude-tasks server:  claude-tasks serve
  2. cron daemon:          service cron status (or systemctl status cron)

Monitor progress:
  - Pipeline state:   eigen-squared status
  - Watchdog log:     tail -f $EIGEN_ROOT/.eigen/watchdog.log
  - Hook log:         cat $EIGEN_ROOT/.eigen/hook_log.jsonl

The pipeline runs autonomously until the phase is complete.
It STOPS after the E2E Testing epic converges.
Run /eigen_continue to review and approve the phase.

Handy watchdog management commands:
  - View cron:        crontab -l | grep eigen-watchdog
  - Pause watchdog:   crontab -l | grep -v "eigen-watchdog.*$EIGEN_ROOT" | crontab -
  - Resume watchdog:  (crontab -l 2>/dev/null; echo "*/$WATCHDOG_INTERVAL * * * * ~/.local/bin/eigen-watchdog $EIGEN_ROOT >> $EIGEN_ROOT/.eigen/watchdog.log 2>&1") | crontab -
  - Run manually:     eigen-watchdog $EIGEN_ROOT
```

**If manual mode** (`$HUMAN_SWARM_FALLBACK` is `true`):

Print:
```
=== Pipeline Initialized (Manual Mode) ===

Pipeline initialized via eigen-squared CLI.
pipeline_state.json created with time_split.status = "not_started"

To start the pipeline, run the first command:
  /time_split

After each command completes, check what's next:
  eigen-squared status

Then run the next command manually. To switch to autonomous mode later,
set HUMAN_SWARM_FALLBACK=false in .claude/settings.json and run:
  (crontab -l 2>/dev/null; echo "*/10 * * * * ~/.local/bin/eigen-watchdog $EIGEN_ROOT >> $EIGEN_ROOT/.eigen/watchdog.log 2>&1") | crontab -
```

---

## Important Notes

- **This command runs interactively** — it asks questions and validates before launching.
- **Env vars MUST be in `.claude/settings.json`** — never in the shell. This prevents cross-project contamination.
- **Two modes**:
  - **Autonomous** (`HUMAN_SWARM_FALLBACK=false`, default): a cron watchdog (`eigen-watchdog`) runs every N minutes, checks if anything is running, and schedules the next command via claude-tasks. The orchestrate_swarm makes autonomous decisions.
  - **Manual** (`HUMAN_SWARM_FALLBACK=true`): no cron, no claude-tasks. User runs commands manually. The orchestrate_swarm can escalate to the user.
- **Commands do NOT schedule their successors** — in autonomous mode, the watchdog handles all scheduling. In manual mode, the user does.
- **One cron per project** — each project gets its own cron entry with its own `$EIGEN_ROOT`. Multiple projects run independently.
- **ONE-TIME use only** — this command is for fresh pipelines. If the pipeline has already started, use `/eigen_continue` to review the completed phase and launch the next one.
