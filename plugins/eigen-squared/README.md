# eigen-squared

A Claude Code plugin that decomposes large software initiatives into shippable code through autonomous AI agent swarms.

Give it an initiative document (10-150+ features with dependencies), and it progressively breaks it down — phases, epics, plans, tasks — until parallel agent swarms can implement each piece. The pipeline runs autonomously, stopping only for human review between phases.

**Language-agnostic**: Python, TypeScript, Go, Rust, C#/.NET, Kotlin, Swift, Flutter, React Native, and more.
**Project-type agnostic**: web APIs, mobile apps, CLI tools, libraries, ML pipelines.

## How it works

```
Initiative Documents (feature tables + specs)
        |
    time_split ↔ deepen_time_split         Split initiative into sequential phases
        |
    bootstrap ↔ deepen_bootstrap           Create project foundation (per phase)
        |
    space_split ↔ deepen_space_split       Decompose phase into sequential epics
        |
    For each epic (one at a time):
        |
        plan_epic_converge                  Strategic implementation plan (self-converging)
        |
        create_issues_from_plan_swarm      Plan → task files + swarm manifest
        |
        orchestrate_swarm ↔ review_swarm   Parallel agent implementation + code review
        |
    All epics done → eigen_continue        Human checkpoint: test + approve phase
        |
    Next phase (repeat)
```

Each `↔` is a **convergence loop**: the main command produces output, the deepen command reviews it with parallel research agents, and they iterate until quality is sufficient (zero high/medium findings). The `eigen-squared` CLI tracks all state deterministically.

Epics within a phase execute **sequentially** (E1 fully done, then E2, then E3...). Workers within each epic execute **in parallel** via agent swarms.

## Prerequisites

### claude-tasks

The autonomous pipeline requires [claude-tasks](https://github.com/anthropics/claude-code) — a task scheduling server that runs Claude Code sessions on a schedule or in response to events.

```bash
# Start the server (keep running in a separate terminal)
claude-tasks serve
```

Each command calls `eigen-squared schedule-next` at the end of its On Exit to chain the next command.

### Claude Code with agent teams

Agent teams must be enabled for swarm execution:

```json
// .claude/settings.json
{
  "env": {
    "CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS": "1",
    "teammateMode": "tmux"
  }
}
```

### Initiative documents

Place these in `$EIGEN_ROOT/eigen_initiative/`:

1. **Initiative document** (`*Initiative*.md`) — Feature Summary Table with IDs, dependencies, priorities, domains. **Required.**
2. **Blackbox Requirements** (`*Blackbox*Requirement*.md`) — Full specs per feature (Inputs, Outputs, Behavior, Acceptance Criteria). **Required.**
3. **Whitebox Reference Guide** (`*Whitebox*.md`) — Implementation patterns from an existing system. **Optional.**

## Quick start

```bash
cd /path/to/your/project
claude
/eigen_start
```

`eigen_start` is interactive. It:
1. Configures environment variables in `.claude/settings.json`
2. Verifies claude-tasks is running
3. Checks initiative documents exist
4. Installs the `eigen-squared` CLI globally (`~/.local/bin/eigen-squared`) — a small wrapper that sets PYTHONPATH to the plugin cache and calls `python3 -m cli`
5. Initializes pipeline state

Each command calls `eigen-squared schedule-next` at the end of its On Exit to chain the next command. From `time_split` onward, the pipeline runs autonomously until a phase completes.

## Pipeline state management

### The eigen-squared CLI

All pipeline state is managed by a Python CLI (`cli/`) that commands call via bash. Commands never read or write `pipeline_state.json` directly.

```bash
# What should run next?
eigen-squared next --json

# Get context for a command (syncs, auto-detects phase/epic, runs guards)
eigen-squared get-context bootstrap --json

# Record command completion (sets all fields atomically)
eigen-squared complete bootstrap --phase 1 --output-path report.json

# Mark convergence (only called by deepen commands)
eigen-squared mark-converged bootstrap --phase 1 --reason "Zero high/medium findings"

# Commit state + artifacts to git
eigen-squared commit-state --message "pipeline: bootstrap phase 1" --additional-paths eigen_initiative/phases/phase_1/

# Human-readable status
eigen-squared status
```

The CLI eliminates the class of bugs where an LLM misinterprets JSON schema or forgets to update a cross-flag. Every state transition is deterministic Python code with 91 tests.

### How commands use the CLI

Every command follows this pattern:

```
On Entry:
  eigen-squared get-context <command> --json
  → CLI syncs with remote, auto-detects phase/epic, runs guards
  → Returns JSON with iteration, feedback paths, recommendations, etc.
  → If error (wrong command, already converged, etc.) → command STOPs

Core Work:
  (the actual non-deterministic work the LLM does)

On Exit:
  eigen-squared complete <command> --phase N [flags]
  eigen-squared commit-state --message "..." --additional-paths ...
  → CLI handles all bookkeeping: status, iteration, timestamps, feedback flags
```

### Convergence loops

Main commands (time_split, bootstrap, space_split, plan_epic_converge) produce output. Deepen commands review it with parallel agents and decide:

- **Continue**: Write feedback file, signal fresh feedback available. The CLI schedules the main command to iterate.
- **Converge**: Set convergence flag, optionally write downstream recommendations. The CLI advances to the next stage.

The feedback lifecycle is managed entirely by the CLI — `complete` for a main command sets `feedback_consumed=true` on both itself and its deepen counterpart. `complete` for a deepen command sets `feedback_consumed=false` to signal fresh feedback. This cross-flag handshake was the #1 source of bugs before the CLI.

## Pipeline stages

### Stage 1: time_split

Decomposes the initiative into **sequential, E2E-testable phases**. Each phase is a self-contained deliverable. Output: phase manifests with feature tables, dependency graphs, blackbox specs.

### Stage 2: bootstrap (per phase)

Creates the project foundation: directory structure, entity stubs, API/message contracts, package manifests, quality config, basic CI, and Docker artifacts for server projects. Incremental — scans what exists before creating.

### Stage 3: space_split (per phase)

Decomposes a phase into **sequential epics**. Each epic is a focused unit of work with clear boundaries. Output: epic definition files, `epic_manifest.json` with execution order, `phase_e2e_config.json` with test scenarios. The last epic is always the E2E Testing epic.

### Stage 4: plan_epic_converge (per epic)

Creates a strategic development plan from the epic definition. Self-converging: generates the plan and reviews it with parallel research agents in a single command, iterating until quality is sufficient. Includes a Parallelization Strategy — how to decompose the epic into parallel tasks for the swarm. No code, only architecture and strategy.

### Stage 5: create_issues_from_plan_swarm (per epic)

One-shot command (no deepen counterpart). Transforms the converged plan into task files + `swarm-manifest.json`. Tasks have file ownership boundaries, dependency graphs, execution waves, and interface contracts. Creates the integration branch `feat/P<N>.E<M>`.

### Stage 6: orchestrate_swarm (per epic)

The swarm leader. Spawns parallel agent teammates (workers), each implementing a task via TDD (design tests → write code → verify). Manages waves, handles blockers, coordinates shared files, creates the PR.

### Stage 7: review_swarm_pr (per epic)

Scope-aware code review with parallel review agents (security, architecture, simplicity, performance, testing). Creates fixup tasks if needed, iterates with orchestrate_swarm until all findings (P1, P2, P3) are resolved. On convergence, auto-merges the PR.

### Human checkpoint: eigen_continue

After all epics in a phase converge (including E2E Testing), the pipeline stops. `eigen_continue` presents what was built, generates a testing recipe, and waits for human confirmation. After approval, the next phase begins.

## File structure

```
$EIGEN_ROOT/
  eigen_initiative/
    Simulacros_Initiative.md          # Your initiative document
    Blackbox_Feature_Requirements.md  # Your feature specs
    Whitebox_Reference_Guide.md       # Optional reference patterns
    phases/
      pipeline_state.json             # Pipeline state (managed by CLI)
      initiative_summary.json         # time_split output
      phase_1_manifest.md             # Phase 1 definition
      phase_1/
        bootstrap-report.json         # Bootstrap output
        epic_manifest.json            # Epic ordering + interfaces
        phase_e2e_config.json         # E2E test configuration
        epic_1/
          epic.md                     # Epic definition
          plan.md                     # Strategic plan
          tasks/                      # Task files for swarm
          swarm-manifest.json         # Swarm execution manifest
          feedback/                   # Deepen feedback files
        epic_2/
          ...
      phase_2/
        ...
    eigen_lessons/                    # Lessons for compound_improve
      time_split/
      bootstrap/
      space_split/
      plan_epic_converge/
      review_swarm_pr/
  .eigen/
    env                               # Pipeline environment variables
    hook_log.jsonl                    # Scheduler execution log
```

## CLI reference

### Read commands

| Command | Purpose |
|---------|---------|
| `eigen-squared status [--json]` | Human-readable pipeline overview |
| `eigen-squared next [--json]` | Next command to run + context |
| `eigen-squared get-context <cmd> [--json]` | Full execution context for a command |
| `eigen-squared validate [--fix]` | Validate pipeline_state.json against schema |
| `eigen-squared resolve-branch` | Branch for next command |

### Write commands

| Command | Purpose |
|---------|---------|
| `eigen-squared init --initiative <name> --phase-count <N>` | Create pipeline_state.json |
| `eigen-squared complete <cmd> [flags]` | Record command completion |
| `eigen-squared mark-converged <cmd> --reason <text>` | Set convergence |
| `eigen-squared set-phase-review --phase <N> --status <s>` | Update phase review |
| `eigen-squared add-recommendation --from-cmd <c> --target <t> --text <s>` | Add downstream observation |
| `eigen-squared init-plan --phase <N> --epic <M>` | Create epic plan entry |
| `eigen-squared set-swarm-status <status> --phase <N> --epic <M>` | Update swarm state |

### Git commands

| Command | Purpose |
|---------|---------|
| `eigen-squared sync [--branch <b>]` | Git pull from branch |
| `eigen-squared commit-state --message <m> [--additional-paths <p>]` | Git add + commit + push |
| `eigen-squared checkout-branch --phase <N> --epic <M> [--create]` | Checkout integration branch |

### Scheduling

| Command | Purpose |
|---------|---------|
| `eigen-squared schedule-next [--delay-minutes <N>]` | Called by every command's On Exit to chain the next command via claude-tasks |
| `eigen-squared install --root <p> --branch <b> --tasks-api <u>` | Install pipeline environment in project |

## Notifications

The pipeline supports optional notifications via:
- **Telegram**: Set `EIGEN_TELEGRAM_CHAT_ID` in `.claude/settings.json`
- **Slack**: Set `EIGEN_SLACK_WEBHOOK`
- **Discord**: Set `EIGEN_DISCORD_WEBHOOK`

Configure the notification channel in claude-tasks, then set the env var. The hook passes it through to the scheduling API.

## Development

### Running tests

```bash
cd plugins/eigen-squared
python -m pytest cli/tests/ -v
```

91 tests covering: state transitions, convergence pairs, swarm state machine, model serialization, backward compatibility, epic manifest loading, and a full multi-phase pipeline walk.

### Plugin structure

```
plugins/eigen-squared/
  .claude-plugin/plugin.json    # Plugin metadata (v2.0.0)
  cli/                          # Python CLI (the brain)
    models.py                   # Typed dataclasses for pipeline state
    state.py                    # Load/save/validate JSON
    transitions.py              # Pipeline state machine (determine_next)
    epic_manifest.py            # Sequential epic ordering
    scheduler.py                # claude-tasks API scheduling
    git_ops.py                  # Git sync/commit/branch operations
    main.py                     # Argparse dispatch (20 subcommands)
    subcommands/                # All subcommand implementations
    tests/                      # 91 tests
  commands/                     # Pipeline command prompts (13 commands)
  hooks/                        # (reserved)
  skills/                       # Supporting skills (language-profiles, etc.)
```
