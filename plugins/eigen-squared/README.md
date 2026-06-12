# eigen-squared

A Claude Code plugin that decomposes large software initiatives into shippable code through autonomous AI agent swarms.

Give it an initiative document (10-150+ features with dependencies), and it progressively breaks it down — phases, epics, plans, tasks — until parallel agent swarms can implement each piece. The pipeline runs autonomously, stopping only for human review between phases.

**Language-agnostic**: Python, TypeScript, Go, Rust, C#/.NET, Kotlin, Swift, Flutter, React Native, and more.
**Project-type agnostic**: web APIs, mobile apps, CLI tools, libraries, ML pipelines.

## How it works

```
Initiative Documents (feature tables + specs)
        |
    time_split (self-converging)           Split initiative into sequential phases
        |
    bootstrap_converge                      Create project foundation (per phase, self-converging)
        |
    space_split_converge                    Decompose phase into sequential epics (self-converging)
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

Most stages are **self-converging**: a single command session drafts its output, critiques it against fixed checklists, and revises — converging internally with no separate reviewer command. The one remaining `↔` loop is `orchestrate_swarm ↔ review_swarm`: parallel workers implement, a review pass finds issues, and they iterate (bounded to ≤3 rounds, then merge with any residuals disclosed). The `eigen-squared` CLI tracks all state deterministically.

Epics within a phase execute **sequentially** (E1 fully done, then E2, then E3...). Workers within each epic execute **in parallel** via agent swarms.

## Prerequisites

### claude-tasks (autonomous mode only)

The autonomous pipeline requires [claude-tasks](https://github.com/kylemclaren/claude-tasks) — a task scheduling server that runs Claude Code sessions on a schedule or in response to events.

```bash
# Install the prebuilt binary into ~/.local/bin...
curl -fsSL https://raw.githubusercontent.com/kylemclaren/claude-tasks/main/install.sh | bash
# ...or build from source (Go 1.24+): go build -o claude-tasks ./cmd/claude-tasks

# Start the server (keep running in a separate terminal; requires an authenticated Claude CLI)
claude-tasks serve

# Verify it's reachable (eigen_start checks this in autonomous mode)
curl http://localhost:8080/api/v1/health
```

A cron-based watchdog (`eigen-watchdog`) polls every N minutes, checks if anything is running, and schedules the next command via claude-tasks. Commands do NOT schedule their successors — the watchdog handles all scheduling.

In manual mode, claude-tasks is not required.

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

`eigen_start` writes these for you during setup — this block just shows what it configures.

### CodeGraph (optional)

[CodeGraph](https://github.com/colbymchenry/codegraph) is an optional, external code-intelligence tool: a 100%-local tree-sitter knowledge graph (symbols, call edges, files) exposed over MCP + CLI. When present and the project is indexed, pipeline agents query it instead of grep/Read to explore existing code, trace call flows, and compute change impact — cheaper and more accurate. It is **never required**: every command existence-checks it and degrades silently to grep/Read when it is absent (see `skills/codegraph/SKILL.md`).

```bash
# Install (bundles its own runtime)
curl -fsSL https://raw.githubusercontent.com/colbymchenry/codegraph/main/install.sh | sh
#   or: npm i -g @colbymchenry/codegraph

# Index this project once (init + full index)
codegraph init -i
```

`eigen_start` recommends it during setup, and `bootstrap_converge` indexes the foundation after creating it. Where it helps most: `plan_epic_converge` (verify against the real codebase), the swarm workers (explore existing code), and `review_swarm_pr` (blast-radius / caller analysis for scope-aware review). The index auto-syncs while an agent session is running, so manual `codegraph sync` is needed only when the file-watcher is off (headless runs / `CODEGRAPH_NO_DAEMON` / WSL2 `/mnt`).

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

`eigen_start` is interactive. On a fresh project it runs in **two passes**, with a Claude Code restart in between.

**Pass 1 — configure.** It collects your settings and writes them to `.claude/settings.json` (`EIGEN_ROOT`, `EIGEN_BRANCH`, the pipeline mode, and — in autonomous mode — `CLAUDE_TASKS_API` and `WATCHDOG_INTERVAL`; optionally `WORKERS_MODEL` and `EIGEN_TELEGRAM_CHAT_ID`). It also sets `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1` and `teammateMode=tmux`. Then it **stops and asks you to restart Claude Code** so the harness picks up the new environment variables.

> **Environment variables must live in `.claude/settings.json`, not be exported in your shell.** `eigen_start` aborts if it finds them only in the shell — this prevents one project's config from leaking into another. If you have them exported, clear them first:
> ```bash
> unset EIGEN_ROOT EIGEN_BRANCH CLAUDE_TASKS_API CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS
> ```

**Restart.** Exit and reopen Claude Code in the project: `exit`, then `cd /path/to/your/project && claude`.

**Pass 2 — install.** Run `/eigen_start` again. Now that the variables are loaded, it:
1. Verifies the environment (env vars, claude-tasks health in autonomous mode, Docker, initiative documents present, and that no `pipeline_state.json` exists yet)
2. Installs the `eigen-squared` CLI globally (`~/.local/bin/eigen-squared`)
3. In autonomous mode: installs `eigen-watchdog`, writes `.eigen/env`, and installs the cron job
4. Initializes pipeline state (`eigen-squared init`)

On later runs, when the variables already exist, `eigen_start` skips the configure pass and goes straight to install. Use `/eigen_start --reinstall-cli-only` to only refresh the CLI wrapper after a plugin version bump.

In autonomous mode, the watchdog detects the pending `time_split` and schedules it within the configured interval. From there, the pipeline runs itself until a phase completes.

In manual mode, run `/time_split` to begin, then check `eigen-squared status` after each command.

## Pipeline modes

### Autonomous mode (`HUMAN_SWARM_FALLBACK=false`, default)

- A cron watchdog (`eigen-watchdog`) runs every N minutes (default: 10)
- It checks claude-tasks for running tasks, and schedules the next command if nothing is running
- The orchestrate_swarm makes autonomous decisions at escalation points and documents them in `[DECISION-AUTONOMOUS]` tasks
- The pipeline stops at phase boundaries for human review (`/eigen_continue`)

### Manual mode (`HUMAN_SWARM_FALLBACK=true`)

- No cron, no claude-tasks required
- You trigger each command manually
- The orchestrate_swarm can escalate ambiguous decisions to you interactively
- Check what's next: `eigen-squared status`

## Pipeline state management

### The eigen-squared CLI

All pipeline state is managed by a Python CLI (`cli/`) that commands call via bash. Commands never read or write `pipeline_state.json` directly.

```bash
# What should run next?
eigen-squared next --json

# Get context for a command (syncs, auto-detects phase/epic, runs guards)
eigen-squared get-context bootstrap_converge --json

# Record command completion (sets all fields atomically)
eigen-squared complete bootstrap_converge --phase 1 --output-path report.json

# Mark convergence (self-marking for converge commands)
eigen-squared mark-converged bootstrap_converge --phase 1 --reason "Zero high/medium findings"

# Commit state + artifacts to git
eigen-squared commit-state --message "pipeline: bootstrap_converge phase 1" --additional-paths eigen_initiative/phases/phase_1/

# Human-readable status
eigen-squared status
```

The CLI eliminates the class of bugs where an LLM misinterprets JSON schema or forgets to update a cross-flag. Every state transition is deterministic Python code with 98 tests.

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
  → CLI handles all bookkeeping: status, iteration, timestamps, convergence flags
  → The watchdog detects the state change and schedules the next command
```

### Convergence

The planning/decomposition stages (`time_split`, `bootstrap_converge`, `space_split_converge`, `plan_epic_converge`) are **self-converging single sessions**: the command drafts its output, runs any executed verification gate (e.g. the bootstrap build gate), critiques the draft against fixed checklists, and revises — bounded to ≤2 internal passes. `bootstrap_converge` and `space_split_converge` additionally spawn ONE independent reviewer subagent that re-runs the build / re-checks cross-source consistency against ground truth. Each self-marks convergence via `eigen-squared mark-converged <command>`, and the watchdog advances to the next stage.

The one cross-command loop is `orchestrate_swarm ↔ review_swarm`: the review pass either finds zero P1/P2 (converge clean) or, after ≤3 fixup rounds, converges with residuals disclosed (`CAP_REACHED_WITH_RESIDUAL`, surfaced at the human checkpoint). The CLI tracks this via the per-unit `status` + `convergence` fields — there is no main↔deepen feedback handshake.

### Watchdog scheduling

In autonomous mode, a cron job runs `eigen-watchdog $EIGEN_ROOT` every N minutes:

1. **Check**: Is anything running for this project? (queries claude-tasks API)
2. **Decide**: What's next? (calls `eigen-squared next`)
3. **Detect retry**: Is this the same command that just ran? (compares with last task in claude-tasks)
4. **Schedule**: Calls `eigen-squared schedule-next` — with a re-run warning in the prompt if retry detected

Commands do NOT schedule their successors. This eliminates the class of bugs where the LLM skips `schedule-next`, calls it twice, or the env var check fails silently.

## Pipeline stages

### Stage 1: time_split

Decomposes the initiative into **sequential, E2E-testable phases**. Each phase is a self-contained deliverable. Output: phase manifests with feature tables, dependency graphs, blackbox specs. Self-converging: a single session drafts the phase split and critiques it against fixed checklists (structural/content-fidelity/strategic/skills), iterating ≤2 passes.

### Stage 2: bootstrap_converge (per phase)

Creates the project foundation: directory structure, entity stubs, API/message contracts, package manifests, quality config, basic CI, and Docker artifacts for server projects. Incremental — scans what exists before creating. Self-converging: a single session scaffolds the foundation, runs an executed verification gate (build/lint/test + `docker compose config`), then spawns ONE independent reviewer subagent that re-runs the build before a bounded revise loop.

### Stage 3: space_split_converge (per phase)

Decomposes a phase into **sequential epics**. Each epic is a focused unit of work with clear boundaries. Output: epic definition files, `epic_manifest.json` with execution order, `phase_e2e_config.json` with test scenarios. The last epic is always the E2E Testing epic. Self-converging: a single session decomposes the phase, runs an executed cross-source consistency gate, then spawns ONE independent reviewer subagent before a bounded revise loop.

### Stage 4: plan_epic_converge (per epic)

Creates a strategic development plan from the epic definition. Self-converging: a single session drafts the plan and critiques it against fixed checklists (structural/strategic/skills) in the same session, iterating ≤2 passes. Includes a Parallelization Strategy — how to decompose the epic into parallel tasks for the swarm. No code, only architecture and strategy.

### Stage 5: create_issues_from_plan_swarm (per epic)

One-shot command (no convergence loop). Transforms the converged plan into task files + `swarm-manifest.json`. Tasks have file ownership boundaries, dependency graphs, execution waves, and interface contracts. Creates the integration branch `feat/P<N>.E<M>`.

### Stage 6: orchestrate_swarm (per epic)

The swarm leader. Spawns parallel agent teammates (workers), each implementing a task via TDD (design tests → write code → verify). Manages waves, handles blockers, coordinates shared files, creates the PR. Operates autonomously by default — documents decisions in `[DECISION-AUTONOMOUS]` tasks. If `$HUMAN_SWARM_FALLBACK` is `true`, can escalate to the user instead.

### Stage 7: review_swarm_pr (per epic)

Scope-aware code review with parallel review agents (security, architecture, simplicity, performance, testing). Creates fixup tasks if needed, iterates with orchestrate_swarm until all findings (P1, P2, P3) are resolved. On convergence, auto-merges the PR.

When the scoped diff touches frontend surfaces (`.tsx/.jsx/.vue/.svelte/.html/.css`) **and** the optional external [`impeccable`](https://impeccable.style) design skill is installed, an extra `design-critique` reviewer joins the iter-0 roster. It runs only impeccable's deterministic anti-pattern detector (`detect.mjs --json`, no network/browser/interactive setup) and reports objective, location-anchored findings (accessibility, contrast, semantic HTML, broken images, documented anti-patterns) at P2/P3 — never subjective polish. impeccable is never required: if absent at iteration 0 it is simply skipped, and the review behaves exactly as before.

### Human checkpoint: eigen_continue

After all epics in a phase converge (including E2E Testing), the pipeline stops. `eigen_continue` presents what was built, generates a testing recipe, and waits for human confirmation. After approval, the watchdog resumes the next phase (or the user runs the next command in manual mode).

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
      bootstrap_converge/
      space_split_converge/
      plan_epic_converge/
      review_swarm_pr/
  .eigen/
    env                               # Pipeline environment variables
    hook_log.jsonl                    # Scheduler execution log
    watchdog.log                      # Watchdog cron output
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
| `eigen-squared schedule-next [--delay-minutes <N>] [--extra-prompt <text>]` | Schedule next command via claude-tasks (called by watchdog, not by commands) |

### Watchdog management

```bash
# View cron
crontab -l | grep eigen-watchdog

# Pause watchdog for a project
crontab -l | grep -v "eigen-watchdog.*/path/to/project" | crontab -

# Resume watchdog
(crontab -l 2>/dev/null; echo "*/10 * * * * ~/.local/bin/eigen-watchdog /path/to/project >> /path/to/project/.eigen/watchdog.log 2>&1") | crontab -

# Run watchdog manually (one-shot)
eigen-watchdog /path/to/project
```

## Notifications

The pipeline supports optional notifications via:
- **Telegram**: Set `EIGEN_TELEGRAM_CHAT_ID` in `.claude/settings.json`
- **Slack**: Set `EIGEN_SLACK_WEBHOOK`
- **Discord**: Set `EIGEN_DISCORD_WEBHOOK`

Configure the notification channel in claude-tasks, then set the env var. The watchdog passes it through to the scheduling API.

## Development

### Running tests

```bash
cd plugins/eigen-squared
python -m pytest cli/tests/ -v
```

153 tests covering: state transitions, self-converging transitions, swarm state machine, model serialization, backward compatibility, epic manifest loading, scheduler dedup logic, and a full multi-phase pipeline walk.

### Plugin structure

```
plugins/eigen-squared/
  .claude-plugin/plugin.json    # Plugin metadata (v3.9.0)
  cli/                          # Python CLI (the brain)
    models.py                   # Typed dataclasses for pipeline state
    state.py                    # Load/save/validate JSON
    transitions.py              # Pipeline state machine (determine_next)
    epic_manifest.py            # Sequential epic ordering
    scheduler.py                # claude-tasks API scheduling + dedup
    git_ops.py                  # Git sync/commit/branch operations
    main.py                     # Argparse dispatch (20 subcommands)
    eigen-watchdog.sh           # Cron-based pipeline scheduler
    subcommands/                # All subcommand implementations
    tests/                      # 153 tests
  commands/                     # Pipeline command prompts (14 commands)
  skills/                       # Supporting skills (language-profiles, etc.)
```
