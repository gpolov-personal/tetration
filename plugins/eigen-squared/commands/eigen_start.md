---
name: eigen_start
description: Validate environment and kick off the autonomous eigen-squared pipeline by creating the first claude-tasks task
---

# Eigen Start — Launch the Autonomous Pipeline

## Your Role

You are the **pipeline launcher**. You validate that everything is ready — environment variables, claude-tasks server, initiative documents, agent teams — and then create the first one-off task in claude-tasks to start the autonomous pipeline. After this, the pipeline runs itself until a phase is complete.

## Environment Variables

This command requires:

- **`EIGEN_ROOT`** — absolute path to the root folder of the target project
- **`EIGEN_BRANCH`** — the default branch from which all work starts
- **`CLAUDE_TASKS_API`** — URL of the claude-tasks REST API (e.g., `http://localhost:8080`)
- **`CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS`** — must be `"1"`

### Step 1: Validate Environment

1. Read `$EIGEN_ROOT`. If not set or empty → **STOP.** Print:
   ```
   ERROR: $EIGEN_ROOT is not set.
   Set it to the root folder of your target project:
     export EIGEN_ROOT=/path/to/your/project
   ```

2. Read `$EIGEN_BRANCH`. If not set or empty → **STOP.** Print:
   ```
   ERROR: $EIGEN_BRANCH is not set.
   Set it to the default branch from which all work starts:
     export EIGEN_BRANCH=main
   ```

3. Read `$CLAUDE_TASKS_API`. If not set or empty → **STOP.** Print:
   ```
   ERROR: $CLAUDE_TASKS_API is not set.
   Start claude-tasks in serve mode and set the API URL:
     claude-tasks serve
     export CLAUDE_TASKS_API=http://localhost:8080
   ```

4. Read `$CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS`. If not `"1"` → **STOP.** Print:
   ```
   ERROR: Agent teams are not enabled. The eigen-squared pipeline requires agent teams.
   Add these to your .claude/settings.json under "env":
     "CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS": "1"
     "teammateMode": "tmux"
   ```

5. Verify `$EIGEN_ROOT` exists and is a directory.

### Step 2: Verify claude-tasks is running

```bash
curl -s $CLAUDE_TASKS_API/api/v1/health
```

If the health check fails or returns an error → **STOP.** Print:
```
ERROR: claude-tasks is not running at $CLAUDE_TASKS_API
Start it with:
  claude-tasks serve
Then re-run /eigen_start
```

### Step 3: Verify Initiative Documents

Check `$EIGEN_ROOT/eigen_initiative/` exists and contains the required files:

1. Verify directory exists: `$EIGEN_ROOT/eigen_initiative/`
2. Search for initiative document: files matching `*Initiative*` or `*initiative*` (markdown)
3. Search for blackbox requirements: files matching `*Blackbox*` or `*blackbox*` AND `*Requirement*` or `*requirement*` (markdown)

If the directory doesn't exist → **STOP.** Print:
```
ERROR: Initiative directory not found at $EIGEN_ROOT/eigen_initiative/
Create it and place the initiative documents inside:
  mkdir -p $EIGEN_ROOT/eigen_initiative

Hint: Run /initiative_review first to prepare your initiative documents.
```

If no initiative document or blackbox requirements found → **STOP.** Print:
```
ERROR: Missing required files in $EIGEN_ROOT/eigen_initiative/

The directory must contain at least 2 files:
  - *Initiative*.md — strategic context with Feature Summary Table
  - *Blackbox*Requirements*.md — full feature specs

Hint: Run /initiative_review to help create these documents.
```

Print what was found:
```
Initiative documents found:
  - Initiative: <filename>
  - Blackbox Requirements: <filename>
  - Whitebox Reference: <filename or "not found (optional)">
```

### Step 4: Check if pipeline already started

If `$EIGEN_ROOT/eigen_initiative/phases/pipeline_state.json` exists:
- Read it and check `state.time_split.status`
- If `time_split` has already run or converged, warn:
  ```
  WARNING: The pipeline has already started (time_split status: <status>).
  Starting again will re-run time_split from the current state.
  ```
- Proceed anyway (time_split has its own entry guards).

### Step 5: Verify .claude/settings.json

Check if `$EIGEN_ROOT/.claude/settings.json` exists with the required env vars. If not, create or update it:

```bash
mkdir -p $EIGEN_ROOT/.claude
```

Verify or create `$EIGEN_ROOT/.claude/settings.json` with:
```json
{
  "env": {
    "EIGEN_ROOT": "<$EIGEN_ROOT value>",
    "EIGEN_BRANCH": "<$EIGEN_BRANCH value>",
    "CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS": "1",
    "teammateMode": "tmux",
    "CLAUDE_TASKS_API": "<$CLAUDE_TASKS_API value>"
  }
}
```

This ensures all claude-tasks subprocesses inherit the env vars via the project settings, even if the user's shell doesn't have them.

### Step 6: Print Pre-Launch Summary

```
=== Eigen-Squared Pipeline — Pre-Launch Check ===

Environment:
  EIGEN_ROOT:       $EIGEN_ROOT
  EIGEN_BRANCH:     $EIGEN_BRANCH
  CLAUDE_TASKS_API: $CLAUDE_TASKS_API
  Agent Teams:      enabled

claude-tasks:       running at $CLAUDE_TASKS_API

Initiative Documents:
  Initiative:       <filename>
  Blackbox:         <filename>
  Whitebox:         <filename or "not provided (optional)">

Pipeline State:     <not started | time_split at iteration N | etc.>

The autonomous pipeline will:
  1. /time_split — split initiative into phases
  2. /deepen_time_split — review and iterate until converged
  3. /bootstrap — create project foundation
  4. /deepen_bootstrap — review and iterate until converged
  5. /space_split — decompose into epics
  6. /deepen_space_split — review and iterate until converged
  7. For each epic (one at a time):
     a. /plan_phase_epic + /deepen_plan_phase_epic (converge)
     b. /create_issues_from_plan_swarm (generate tasks + worktree)
     c. /orchestrate_swarm (execute swarm in worktree)
     d. /review_swarm_pr (review PR, iterate with orchestrate until converged)
  8. STOP when the E2E Testing epic converges (phase complete)

Each command runs 3 minutes after the previous one finishes.
All commands run as claude -p (non-interactive, autonomous).
```

### Step 7: Create the First Task

```bash
NEXT_RUN=$(date -u -d '+1 minute' +%Y-%m-%dT%H:%M:%SZ)

curl -s -X POST $CLAUDE_TASKS_API/api/v1/tasks \
  -H "Content-Type: application/json" \
  -d '{
    "name": "eigen: time_split (pipeline start)",
    "prompt": "Use the Skill tool to invoke Skill(\"eigen-squared:time_split\"). Follow all its instructions completely.",
    "cron_expr": "",
    "scheduled_at": "'$NEXT_RUN'",
    "working_dir": "'$EIGEN_ROOT'",
    "enabled": true
  }'
```

Print:
```
=== Pipeline Launched! ===

First task created: /time_split
Scheduled to run in 1 minute.

Monitor progress:
  - claude-tasks TUI: run 'claude-tasks' in another terminal
  - API: curl $CLAUDE_TASKS_API/api/v1/tasks
  - Task runs: curl $CLAUDE_TASKS_API/api/v1/tasks/<id>/runs/latest

The pipeline will run autonomously until the phase is complete.
It will STOP after the E2E Testing epic converges.

To cancel: disable the latest pending task in claude-tasks.
```

---

## Important Notes

- **This command runs ONCE** — it's a launcher, not a pipeline step. It creates the first task and exits.
- **The first task starts in 1 minute** (not 3) — shorter delay since there's no previous command to cool down from.
- **All subsequent commands chain automatically** — each command creates the next one-off task when it finishes.
- **The pipeline stops at phase boundary** — when the E2E Testing epic's review converges, no next task is created.
- **To resume after manual testing** — run `/eigen_start` again. time_split's entry guards will detect the current state and either proceed or inform you what to run next.
- **The .claude/settings.json is critical** — it ensures env vars are available to all claude-tasks subprocesses, even across different Claude Code sessions.
