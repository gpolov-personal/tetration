---
name: eigen_start
description: ONE-TIME launcher — validate environment and kick off a fresh eigen-squared pipeline (autonomous or manual mode)
---

# Eigen Start — Launch the Pipeline

## Pipeline Context

```
eigen_start (you are here)
    │
    ▼ [if AUTOCHAIN=true: eigen-squared schedule-next chains commands automatically]
    │ [if AUTOCHAIN=false: user runs each command manually]
    │
    ▼
time_split ↔ deepen_time_split → bootstrap ↔ deepen_bootstrap →
space_split ↔ deepen_space_split → [per epic: plan → create → orchestrate → review] →
STOP at E2E Testing epic convergence
```

This is the **ONE-TIME interactive launcher**. It validates the environment, collects configuration from the user, initializes `pipeline_state.json` via the `eigen-squared` CLI, and optionally schedules the first command. When `AUTOCHAIN=true`, the pipeline runs autonomously after this. When `AUTOCHAIN=false`, the user triggers each command manually. You never run `/eigen_start` again for this pipeline.

## Your Role

You are a **ONE-TIME pipeline launcher**. You validate that everything is ready — environment variables, claude-tasks server, initiative documents, agent teams — and then initialize state and optionally schedule the first command for a **fresh** pipeline. In autonomous mode (`AUTOCHAIN=true`), the pipeline runs itself until a phase is complete. In manual mode, the user triggers each command.

This command is for **brand new pipelines ONLY**. If the pipeline has already started, use `/eigen_continue` instead.

This is an **interactive command** — it asks the user for configuration values on first run.

---

## Step 1: Check Environment Variables

The eigen-squared pipeline requires these env vars to be set in the project's `.claude/settings.json` (NOT in the shell). This ensures each project has its own isolated configuration and prevents cross-project mix-ups.

### 1.1 Check for Shell-Only Variables (ERROR condition)

Check if `EIGEN_ROOT`, `EIGEN_BRANCH`, `CLAUDE_TASKS_API`, `AUTOCHAIN`, or `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS` are set in the current environment BUT do NOT exist in `.claude/settings.json`:

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
  unset EIGEN_ROOT EIGEN_BRANCH CLAUDE_TASKS_API AUTOCHAIN CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS

/eigen_start will help you set them up in .claude/settings.json.
```

### 1.2 Check for Correctly Configured Project (READY condition)

**If env vars are present in `.claude/settings.json`** (and therefore available in the session):

Verify all required vars:
- `$EIGEN_ROOT` is set and points to an existing directory
- `$EIGEN_BRANCH` is set and non-empty
- `$CLAUDE_TASKS_API` is set and non-empty
- `$AUTOCHAIN` is set (either `"true"` or `"false"`)
- `$CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS` is `"1"`

If ALL present and valid → proceed to Step 2.

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

**CLAUDE_TASKS_API:**
```
What is the claude-tasks API URL?
(The server must be running in serve mode)

Default: http://localhost:8080
Press Enter for default, or enter a custom URL:
```

**AUTOCHAIN:**
```
Enable autonomous pipeline execution?

When AUTOCHAIN=true, each command automatically schedules the next one
via claude-tasks. The pipeline runs unattended until a phase completes.

When AUTOCHAIN=false, the pipeline initializes but you trigger each
command manually. You can always run 'eigen-squared schedule-next'
by hand, or enable AUTOCHAIN later in .claude/settings.json.

Enable autonomous mode? (yes/no, default: yes):
```

- **"yes"** or Enter → `AUTOCHAIN=true`
- **"no"** → `AUTOCHAIN=false`

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
    "CLAUDE_TASKS_API": "<user's value>",
    "AUTOCHAIN": "<true or false>",
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

## Step 2: Verify claude-tasks is Running

```bash
curl -s $CLAUDE_TASKS_API/api/v1/health
```

**If the health check succeeds** → Print: `claude-tasks: healthy at $CLAUDE_TASKS_API` and continue.

**If the health check fails AND `AUTOCHAIN=true`** → **STOP.** Print:
```
ERROR: claude-tasks is not responding at $CLAUDE_TASKS_API

Autonomous mode (AUTOCHAIN=true) requires claude-tasks to be running.
Start it in a separate terminal:
  claude-tasks serve

Make sure it's running before re-running /eigen_start.
```

**If the health check fails AND `AUTOCHAIN=false`** → **WARNING**, continue:
```
WARNING: claude-tasks is not responding at $CLAUDE_TASKS_API

This is not blocking because AUTOCHAIN=false (manual mode).
However, you will need claude-tasks running if you later run
'eigen-squared schedule-next' manually or enable AUTOCHAIN.

Start it when ready:
  claude-tasks serve
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

## Step 5: Ask When to Start (AUTOCHAIN=true only)

**If `AUTOCHAIN=false`** → skip this step entirely. The user will trigger commands manually.

**If `AUTOCHAIN=true`** → ask:

```
When should the pipeline start?

Options:
  1. Now (starts in 1 minute)
  2. In N minutes (e.g., "in 30 minutes", "in 2 hours")
  3. At a specific time (e.g., "2026-03-17T15:00:00", "today at 3pm", "tomorrow at 9am")
```

Parse the user's response:

- **"now"** or **option 1** → `scheduled_at` = 1 minute from now
- **"in N minutes"** or **"in N hours"** → calculate the target time and set `scheduled_at`
- **Specific time** → parse to ISO 8601 and set `scheduled_at`

Store the resolved time as the scheduled start.

---

## Step 5.5: Commit Settings to $EIGEN_BRANCH (if not gitignored)

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
Do NOT force-add. **STOP and ask the user** using AskUserQuestion:

```
WARNING: .claude/settings.json is in .gitignore

This will cause problems in later pipeline stages — integration branches created by
/create_issues_from_plan_swarm will NOT inherit pipeline settings
(EIGEN_ROOT, EIGEN_BRANCH, CLAUDE_TASKS_API, AUTOCHAIN, plugin configuration).

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
claude-tasks API:   $CLAUDE_TASKS_API
Agent Teams:        enabled
Mode:               <autonomous (AUTOCHAIN=true) | manual (AUTOCHAIN=false)>

Initiative:         <filename>
Blackbox:           <filename>
Pipeline State:     not started (fresh)

Scheduled Start:    <resolved time if AUTOCHAIN=true, otherwise "manual — run /time_split to begin">

Pipeline sequence:
  time_split ↔ deepen_time_split → bootstrap ↔ deepen_bootstrap →
  space_split ↔ deepen_space_split → [per epic: plan → create → orchestrate → review] →
  STOP at E2E Testing epic convergence

Epics execute one at a time in dependency order.
<if AUTOCHAIN=true: "Each command runs ~3 minutes after the previous finishes.">
<if AUTOCHAIN=false: "You trigger each command manually. Use 'eigen-squared status' to see what's next.">
```

---

## Step 7: Install CLI and Initialize Pipeline

### 7.1 Install the `eigen-squared` CLI globally

The eigen-squared CLI is a Python module inside this plugin. It needs to be accessible from any directory (commands run from `$EIGEN_ROOT`, not the plugin directory). Create a global wrapper script.

**Step 1: Discover the plugin path.** Use the Glob tool to find the `cli/__main__.py` file near this command file. The plugin cache path will look like `~/.claude/plugins/cache/tetration/eigen-squared/<version>/`. Store this as `PLUGIN_PATH`.

**Step 2: Read the version.** Read `$PLUGIN_PATH/.claude-plugin/plugin.json` and extract the `version` field (e.g., `2.1.0`).

**Step 3: Create the wrapper script** at `~/.local/bin/eigen-squared`:

```bash
mkdir -p ~/.local/bin
cat > ~/.local/bin/eigen-squared << 'WRAPPER_EOF'
#!/bin/bash
# eigen-squared CLI v<VERSION> — created by /eigen_start
PLUGIN_PATH="<RESOLVED_PLUGIN_PATH>"
if [ ! -d "$PLUGIN_PATH/cli" ]; then
    echo "ERROR: eigen-squared plugin not found at $PLUGIN_PATH"
    echo "The plugin may have been updated. Run /eigen_start again to fix."
    exit 1
fi
export PYTHONPATH="$PLUGIN_PATH"
exec python3 -m cli "$@"
WRAPPER_EOF
chmod +x ~/.local/bin/eigen-squared
```

Replace `<RESOLVED_PLUGIN_PATH>` with the actual absolute path discovered in Step 1, and `<VERSION>` with the version from Step 2.

**Step 4: Verify it works:**

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

### 7.2 Create `.eigen/` directory

```bash
mkdir -p $EIGEN_ROOT/.eigen
```

Create the env file for logging and retry logic:
```bash
cat > $EIGEN_ROOT/.eigen/env <<EOF
EIGEN_ROOT=$EIGEN_ROOT
EIGEN_BRANCH=$EIGEN_BRANCH
CLAUDE_TASKS_API=$CLAUDE_TASKS_API
AUTOCHAIN=$AUTOCHAIN
EIGEN_TELEGRAM_CHAT_ID=${EIGEN_TELEGRAM_CHAT_ID:-}
EOF
```

Add `.eigen/` to `.gitignore` if not already present:
```bash
grep -qxF '.eigen/' $EIGEN_ROOT/.gitignore 2>/dev/null || echo '.eigen/' >> $EIGEN_ROOT/.gitignore
```

### 7.3 Initialize pipeline state

```bash
eigen-squared init --initiative "<initiative name from Step 3>" --phase-count 0
```

Phase count is 0 because time_split hasn't run yet. The CLI creates `pipeline_state.json` with `time_split.status = "not_started"`.

### 7.4 Verify installation

```bash
eigen-squared validate
eigen-squared status
```

### 7.5 Schedule first command (AUTOCHAIN=true) or print next steps (AUTOCHAIN=false)

**If `AUTOCHAIN=true`:**

```bash
eigen-squared schedule-next
```

This reads pipeline state, sees `time_split.status = "not_started"`, and schedules `/time_split` via claude-tasks.

Print:
```
=== Pipeline Launched! ===

Pipeline controller initialized via eigen-squared CLI.
pipeline_state.json initialized with time_split.status = "not_started"
schedule-next has scheduled /time_split.

IMPORTANT: Make sure claude-tasks server is running:
  claude-tasks serve

Monitor progress:
  - eigen-squared status
  - eigen-squared log
  - Hook log: cat $EIGEN_ROOT/.eigen/hook_log.jsonl

The pipeline runs autonomously until the phase is complete.
It STOPS after the E2E Testing epic converges.

To cancel: disable the pending task in claude-tasks TUI or API.
```

**If `AUTOCHAIN=false`:**

Print:
```
=== Pipeline Initialized (Manual Mode) ===

Pipeline controller initialized via eigen-squared CLI.
pipeline_state.json initialized with time_split.status = "not_started"

To start the pipeline, run the first command:
  /time_split

After each command completes, check what's next:
  eigen-squared status

Then run the next command manually. To switch to autonomous mode later,
set AUTOCHAIN=true in .claude/settings.json.
```

---

## Important Notes

- **This command runs interactively** — it asks questions and validates before launching.
- **Env vars MUST be in `.claude/settings.json`** — never in the shell. This prevents cross-project contamination.
- **Two modes** — `AUTOCHAIN=true` runs the pipeline autonomously (commands auto-schedule via claude-tasks). `AUTOCHAIN=false` initializes state but the user triggers each command manually. You can switch modes at any time by editing `.claude/settings.json`.
- **claude-tasks is always configured** — even in manual mode, `CLAUDE_TASKS_API` is set so you can run `eigen-squared schedule-next` by hand or enable AUTOCHAIN later. In autonomous mode, claude-tasks must be running (`claude-tasks serve`).
- **One claude-tasks server, multiple projects** — each project's `working_dir` points to its own root, and each has its own `.claude/settings.json` with isolated env vars.
- **ONE-TIME use only** — this command is for fresh pipelines. If the pipeline has already started, use `/eigen_continue` to review the completed phase and launch the next one.
- **Pipeline controller** — the `eigen-squared` CLI handles pipeline state and command scheduling. In autonomous mode, commands self-schedule via `eigen-squared schedule-next` (gated by `AUTOCHAIN=true`). In manual mode, the user runs commands and checks `eigen-squared status` for next steps.
