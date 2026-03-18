---
name: eigen_start
description: ONE-TIME launcher — validate environment and kick off a fresh autonomous eigen-squared pipeline
---

# Eigen Start — Launch the Autonomous Pipeline

## Your Role

You are a **ONE-TIME pipeline launcher**. You validate that everything is ready — environment variables, claude-tasks server, initiative documents, agent teams — and then create the first one-off task in claude-tasks to start a **fresh** autonomous pipeline. After this, the pipeline runs itself until a phase is complete.

This command is for **brand new pipelines ONLY**. If the pipeline has already started, use `/eigen_continue` instead.

This is an **interactive command** — it asks the user for configuration values on first run.

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
- `$CLAUDE_TASKS_API` is set and non-empty
- `$CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS` is `"1"`

If ALL present and valid → proceed to Step 2.

If some are missing or invalid → ask the user for the missing values (same flow as 1.3).

### 1.3 First-Time Setup (NO env vars found)

**If neither shell nor settings.json has the required env vars** → interactive setup:

```
=== Eigen-Squared — First-Time Setup ===

I need to configure this project for the eigen-squared pipeline.
These values will be saved to .claude/settings.json so they persist
across sessions and are used by all autonomous pipeline tasks.
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

**CLAUDE_TASKS_API:**
```
What is the claude-tasks API URL?
(The server must be running in serve mode)

Default: http://localhost:8080
Press Enter for default, or enter a custom URL:
```

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

If the health check fails → **STOP.** Print:
```
ERROR: claude-tasks is not responding at $CLAUDE_TASKS_API

Start it in a separate terminal:
  claude-tasks serve

Make sure it's running before re-running /eigen_start.
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

Load the `pipeline-state-schema` skill to understand the pipeline state format.

Check if `$EIGEN_ROOT/eigen_initiative/phases/pipeline_state.json` exists:

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

## Step 5: Ask When to Start

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

## Step 6: Print Pre-Launch Summary

```
=== Eigen-Squared Pipeline — Pre-Launch Summary ===

Project:            $EIGEN_ROOT
Branch:             $EIGEN_BRANCH
claude-tasks API:   $CLAUDE_TASKS_API
Agent Teams:        enabled

Initiative:         <filename>
Blackbox:           <filename>
Pipeline State:     <not started | in progress at stage X>

Scheduled Start:    <resolved time — e.g., "2026-03-17 15:00:00 UTC (in 30 minutes)">

The autonomous pipeline will run:
  time_split ↔ deepen_time_split → bootstrap ↔ deepen_bootstrap →
  space_split ↔ deepen_space_split → [per epic: plan → create → orchestrate → review] →
  STOP at E2E Testing epic convergence

Each command runs ~3 minutes after the previous finishes.
```

---

## Step 7: Create the First Task

```bash
# Only include telegram_webhook if $EIGEN_TELEGRAM_CHAT_ID is set and non-empty.
curl -s -X POST $CLAUDE_TASKS_API/api/v1/tasks \
  -H "Content-Type: application/json" \
  -d '{
    "name": "eigen: time_split (pipeline start)",
    "prompt": "Use the Skill tool to invoke Skill(\"eigen-squared:time_split\"). Follow all its instructions completely.",
    "cron_expr": "",
    "scheduled_at": "'$SCHEDULED_AT'",
    "working_dir": "'$EIGEN_ROOT'",
    "enabled": true,
    "telegram_webhook": "'$EIGEN_TELEGRAM_CHAT_ID'"
  }'
```


Print:
```
=== Pipeline Launched! ===

First task: /time_split
Scheduled: <human-readable time>

Monitor progress:
  - List tasks: curl $CLAUDE_TASKS_API/api/v1/tasks
  - Latest run: curl $CLAUDE_TASKS_API/api/v1/tasks/<id>/runs/latest
  - Task output: curl $CLAUDE_TASKS_API/api/v1/tasks/<id>/runs/latest | jq .output

The pipeline runs autonomously until the phase is complete.
It STOPS after the E2E Testing epic converges.

To cancel: disable the pending task in claude-tasks TUI or API.
```

---

## Important Notes

- **This command runs interactively** — it asks questions and validates before launching.
- **Env vars MUST be in `.claude/settings.json`** — never in the shell. This prevents cross-project contamination.
- **First run requires a restart** — after writing settings.json, Claude Code must restart to load the new env vars.
- **claude-tasks must be running** in a separate terminal (`claude-tasks serve`).
- **One claude-tasks server, multiple projects** — each project's `working_dir` points to its own root, and each has its own `.claude/settings.json` with isolated env vars.
- **ONE-TIME use only** — this command is for fresh pipelines. If the pipeline has already started, use `/eigen_continue` to review the completed phase and launch the next one.
