# eigen-lite

Destilated variant of [`eigen-squared`](../eigen-squared/) for small initiatives (**2–5 features**) on existing codebases. Single phase, multi-epic: 1–5 feature epics + 1 optional E2E Testing epic as the last epic.

**Status:** beta. All six sprints of the original plan are complete; release E2E on a real user repo pending.

---

## Choosing squared vs lite

```
                ┌─────────────────────────────────────┐
                │ Is this a greenfield / large build? │
                └──────────────┬──────────────────────┘
                               │
            ┌──── Yes (≥10 features, multi-phase) ─────────► eigen-squared
            │
            └──── No (≤5 features on an existing repo)
                               │
                               ▼
                ┌──────────────────────────────────────┐
                │ Can you meaningfully describe each   │
                │ feature in one paragraph without     │
                │ diagrams / internal specs?           │
                └──────────────┬───────────────────────┘
                               │
            ┌──── No (needs time_split, deepen, ...) ──────► eigen-squared
            │
            └──── Yes ─────────────────────────────────────► eigen-lite
```

**Use eigen-squared** when:
- Initiative has ≥6 features (lite hard-caps at 5).
- Features don't fit in a single phase due to deep dependency chains (phase split needed).
- Greenfield scaffolding is a significant part of the work.
- You want convergence loops catching planning mistakes (lite is single-pass).

**Use eigen-lite** when:
- Small delta on an existing repo (e.g. "add 3 new endpoints + migration + tests").
- You've already done squared-scale planning separately and want to execute fast.
- Planning latency matters (lite skips 30+ minutes of convergence loops).

---

## Quick start (5 minutes)

```bash
# 1. In Claude Code inside your project:
/lite_start

# First run asks for EIGEN_ROOT, EIGEN_BRANCH, mode (autonomous/manual),
# claude-tasks URL if autonomous, and a feature-set slug.
# Writes .claude/settings.json, exits with "restart Claude Code".

# 2. After restart:
/lite_start

# Installs the eigen-lite CLI + watchdog, creates .eigen-lite/env,
# calls eigen-lite init, sets up cron if autonomous.

# 3. Plan the initiative:
/lite_plan

# Interview for 2-5 features, then walks through stages A→E,
# spawning parallel analyst subagents at D and E.
# Writes feature_summary.md, phase_1_manifest.md, bootstrap-report.json,
# per-epic epic.md + plan.md + tasks/*.md + swarm-manifest.json,
# and creates feat/P1.E<M> integration branches.

# 4. Execute (autonomous mode: watchdog handles the rest):
#    First tick → /lite_swarm for epic 1
#    After PR → /lite_review
#    Loops until the last epic converges.

# Manual mode:
/lite_swarm
/lite_review
# repeat per epic
```

---

## Differences vs eigen-squared

| Dimension | eigen-squared | eigen-lite |
|-----------|---------------|-----------|
| Scope | 10–50 features, multi-phase | 2–5 features, single phase |
| Codebase | Greenfield or existing | Existing (assumes prior repo) |
| Planning commands | 7 discrete (`time_split`, `bootstrap_converge`, `space_split_converge`, `plan_epic_converge` × N, `create_issues_from_plan_swarm` × N) | 1 condensed (`lite_plan` with 5 stages A–E + checkpoints) |
| Convergence loops in planning | Yes (per command, up to 4 rounds) | None — single pass, subagents for diversity instead |
| Execution commands | `orchestrate_swarm`, `review_swarm_pr` | `lite_swarm`, `lite_review` |
| State shape | Multi-phase with `state.phases[<N>].plans[<M>]` | Flat with `state.lite_plan` + `state.epics[<M>]` |
| Workers | `design_validation_tests_swarm`, `code_from_validation_tests_swarm` | Same workers via `Skill("eigen-squared:...")` cross-plugin |
| Watchdog | `eigen-watchdog` | `eigen-lite-watchdog` (separate lock, separate env) |
| E2E epic gate | Hard STOP at E2E convergence (user reviews) | No stop gate; runs straight through |

See `docs/lite-plan-internals.md` for the rationale on collapsing planning into one command.

---

## Commands

| Command | Purpose |
|---------|---------|
| `/lite_start` | ONE-TIME launcher: configure env, install CLI + watchdog, init state. |
| `/lite_plan` | Single-pass planner: interview → phase manifest → bootstrap delta → epic decomposition → per-epic plans + swarm manifests. |
| `/lite_swarm` | Orchestrate parallel execution of one epic. Creates PR. |
| `/lite_review` | Scope-aware PR review. Loops with `/lite_swarm` until convergence, then auto-merges. |

---

## Architecture

- **Plugin dependency:** `dependencies: ["eigen-squared"]` in `plugin.json` ensures squared's workers and skills are available via cross-plugin `Skill("eigen-squared:...")` references. No squared code is copied into lite.
- **Why no `eigen-core` dependency:** `eigen-core` is a **dev-time-only** shared library. Its modules are vendored into `plugins/eigen-lite/_vendored/eigen_core/` at commit time, so the plugin cache carries a complete copy. Declaring `eigen-core` as a runtime dep would be misleading. Intentionally **not** registered in `marketplace.json` (no user-facing commands).
- **Vendoring mechanics:** canonical source in `plugins/eigen-core/eigen_core/`. A pre-commit hook (`.githooks/pre-commit`) re-runs `tools/vendor-core.sh` when the source changes, and refuses commits that edit `_vendored/` directly without a corresponding source change. CI has a drift-check workflow as a second layer.
- **State file path:** `eigen_initiative/phases/pipeline_state_lite.json`, explicitly distinct from squared's `pipeline_state.json`. A schema guard in `LitePipelineState.from_dict` raises `SquaredSchemaDetected` on shape mismatch to prevent silent overwrite.
- **Branch / path conventions:** `feat/P1.E<M>` and `phases/phase_1/epic_<M>/` are identical to squared so the reused workers find what they expect.
- **Atomic state writes:** every `save_state` uses tempfile + `os.replace` so a crash never leaves a half-written state file.

---

## CLI reference

Install via `/lite_start`, then `eigen-lite` is on `$PATH`. Direct usage:

```bash
python -m cli <subcommand> [options]
```

### Lifecycle

| Subcommand | Purpose |
|-----------|---------|
| `init --feature-set <slug> [--epic-count N] [--force]` | Create `pipeline_state_lite.json`. |
| `status [--json]` | Show pipeline overview. |
| `next [--json]` | Return the next command to run + context. |
| `get-context <lite_plan\|lite_swarm\|lite_review> [--epic N] [--json]` | Produce the JSON context each command consumes in its "On Entry" block. |
| `validate` | Validate state file for internal consistency. |

### State mutation

| Subcommand | Purpose |
|-----------|---------|
| `complete <target> [--epic N] [--stage X] [--pr-url ...] [--pr-number ...] [--report-path ...] [--findings-summary ...] [--converged] [--reason ...]` | Record completion of a command (or a stage for `lite_plan`). |
| `mark-converged <target> [--epic N] --reason ...` | Force convergence on a step. |
| `set-swarm-status <value> --epic N [--pr-url ...] [--pr-number ...]` | Update swarm status (`not_started`, `pr_created`, `iterating`, `converged`). |
| `add-review-report --epic N --report-path ...` | Append a review report path. |
| `init-epics --epics <json-list>` | Populate `state.epics` after `lite_plan` Stage D. |

### Git + infra

| Subcommand | Purpose |
|-----------|---------|
| `sync [--branch <b>]` | `git pull` latest on the specified branch. |
| `commit-state --message ... [--additional-paths ...] [--branch ...]` | Commit + push the state file (plus optional extras). |
| `resolve-branch [--json]` | Print the integration branch the next command should run on. |
| `checkout-branch --epic N [--create]` | Check out `feat/P1.E<N>`, optionally creating it. |

### Installation / automation

| Subcommand | Purpose |
|-----------|---------|
| `write-env` | Write `.eigen-lite/env` from the current process environment. |
| `install --root <path> --branch <b> --tasks-api <url> [--telegram ...]` | Create `.eigen-lite/` + env file (no cron). |
| `schedule-next [--delay-minutes N] [--extra-prompt ...]` | Post the next command to claude-tasks. Used by the watchdog. |

Run `python -m cli <subcommand> --help` for the full argparse list.

---

## State schema (brief)

`pipeline_state_lite.json`:

```json
{
  "schema_version": 1,
  "feature_set": "my-initiative",
  "epic_count": 3,
  "state": {
    "lite_plan": {
      "status": "completed",
      "stages_completed": ["A", "B", "C", "D", "E:1", "E:2", "E:3"],
      "output_paths": {...},
      "iteration": 6,
      "convergence": {"converged": true, "decided_by": "lite_plan", "decided_at": "...", "reason": "..."}
    },
    "epics": {
      "1": {
        "epic_path": "phases/phase_1/epic_1/",
        "swarm_manifest": "phases/phase_1/epic_1/swarm-manifest.json",
        "is_e2e_epic": false,
        "lite_swarm": {
          "status": "pr_created",
          "pr_number": 42,
          "pr_url": "https://...",
          "integration_branch": "feat/P1.E1",
          "convergence": {"converged": false}
        },
        "lite_review": {
          "status": "complete",
          "review_iteration": 1,
          "review_reports": ["phases/phase_1/epic_1/review_report_iteration_0.md"],
          "findings_summary": {"p1": 0, "p2": 0, "p3": 1},
          "convergence": {"converged": false}
        }
      },
      "2": {...},
      "3": {"is_e2e_epic": true, ...}
    }
  },
  "updated_at": "..."
}
```

Full dataclasses are in [`cli/models_lite.py`](./cli/models_lite.py). Validation rules are enforced by `validate_state_lite` in [`cli/state.py`](./cli/state.py).

---

## Coexistence with eigen-squared

**Recommended:** use one or the other per repo. Not both.

Technically possible, with these constraints:

- **Separate state files**: `pipeline_state.json` (squared) and `pipeline_state_lite.json` (lite) never collide.
- **Separate `.eigen/` directories**: squared uses `.eigen/`, lite uses `.eigen-lite/`. Env files, watchdog logs, hook logs, and flock files are all isolated.
- **Separate CLI wrappers**: `eigen-squared` and `eigen-lite` on `$PATH`.
- **Separate watchdog binaries and cron entries**: `eigen-watchdog` (squared) vs `eigen-lite-watchdog` (lite).
- **Shared artifact tree**: `eigen_initiative/phases/phase_1/epic_<M>/` is the shared surface. Because squared and lite use the same branch naming (`feat/P1.E<M>`) and the same per-epic file layout, running both in the same repo would produce PR collisions and branch overwrites.
- **`lite_start` refuses** if `pipeline_state.json` is already present to prevent accidental dual-pipeline startup.

If you need to migrate from squared to lite in the same repo, delete `pipeline_state.json`, keep the artifacts, and rehydrate lite's state via `eigen-lite init` + `init-epics`. Workers, epic layouts, and integration branches stay intact.

---

## Tests

```bash
cd plugins/eigen-lite
python -m pytest cli/tests/ -q   # 138 tests
```

Related test suites:

```bash
cd plugins/eigen-squared
python -m pytest cli/tests/ -q   # 119 tests

cd plugins/eigen-core
python -m pytest eigen_core/cli/tests/ -q   # 44 tests
```

Integration tests in `cli/tests/test_integration_pipeline_flow.py` walk a full 2-epic pipeline end-to-end using subprocess CLI invocations against a real git repo — no mocks.
