---
name: pipeline-state-schema
description: "Pipeline state schema reference for eigen-squared. Use when any command needs to read, create, or update pipeline_state.json — the single source of truth for iteration tracking. Triggers on: pipeline_state.json operations, feedback lifecycle, convergence decisions, recommendations."
---

# Pipeline State Schema — `$EIGEN_ROOT/eigen_initiative/phases/pipeline_state.json`

This is the **single source of truth** for iteration tracking across all eigen-squared pipeline commands. Every command reads this file on entry and updates it on exit via the `eigen-squared` CLI.

## Commands

**Pipeline commands (tracked in state):**

| Command | Scope | State type | Pattern |
|---|---|---|---|
| `time_split` | initiative | `MainCommandState` | Main/deepen pair with `deepen_time_split` |
| `deepen_time_split` | initiative | `DeepenCommandState` | Reviews time_split, produces feedback |
| `bootstrap_converge` | per-phase | `MainCommandState` | Self-converging (internal swarm loop) |
| `space_split_converge` | per-phase | `MainCommandState` | Self-converging (internal swarm loop) |
| `plan_epic_converge` | per-epic | `MainCommandState` | Self-converging (internal swarm loop) |
| `create_issues_from_plan_swarm` | per-epic | Populates `SwarmExecution` | One-shot |
| `orchestrate_swarm` | per-epic | Drives `SwarmExecution` | Swarm pair with `review_swarm_pr` |
| `review_swarm_pr` | per-epic | Drives `SwarmExecution` | Swarm pair with `orchestrate_swarm` |

**Control and utility commands (not tracked as state slots):**

| Command | Purpose |
|---|---|
| `eigen_start` | One-time launcher: validates env, installs CLI, initializes state |
| `eigen_continue` | Phase transition checkpoint: presents summary, collects approval |
| `initiative_review` | Interactive pre-pipeline document review |
| `e2e_validation_swarm` | Swarm worker for end-to-end tests (runs inside `orchestrate_swarm`) |
| `design_validation_tests_swarm` | Swarm worker Phase A: design TDD tests |
| `code_from_validation_tests_swarm` | Swarm worker Phase B: implement code |
| `compound_improve` | Meta: applies accumulated lessons to command prompts |

---

## Pipeline Traversal Order

Determined by `determine_next()` in the CLI:

```
1. time_split <-> deepen_time_split  (must converge before phases)
2. For each phase (1..phase_count), sequentially:
   a. bootstrap_converge            (must converge)
   b. space_split_converge          (must converge)
   c. For each epic (from epic_manifest.json order):
      - plan_epic_converge          (must converge)
      - create_issues_from_plan_swarm
      - orchestrate_swarm <-> review_swarm_pr  (must converge)
   d. Phase checkpoint: phase_review must reach "approved"
      (managed by /eigen_continue)
3. All phases approved -> pipeline complete
```

---

## Full Schema

```json
{
  "schema_version": "2.0.0",
  "initiative": "<name from initiative document>",
  "created_at": "<ISO 8601>",
  "updated_at": "<ISO 8601>",

  "state": {
    "time_split": {
      "status": "not_started|completed|iterating",
      "iteration": 0,
      "last_run_at": null,
      "output_paths": {},
      "feedback_consumed": false,
      "phase_count": null,
      "convergence": {
        "converged": false,
        "decided_by": null,
        "decided_at": null,
        "reason": null
      }
    },
    "deepen_time_split": {
      "status": "not_started|completed",
      "iteration": 0,
      "last_run_at": null,
      "feedback_path": null,
      "feedback_consumed": false,
      "findings_summary": { "high": 0, "medium": 0, "low": 0 },
      "locked_skills": null
    },
    "phases": {}
  },

  "recommendations": {
    "bootstrap_converge": [],
    "space_split_converge": [],
    "plan_epic_converge": [],
    "create_issues_from_plan_swarm": []
  }
}
```

---

## Per-Phase State Entry

`state.phases` is keyed by phase number (string: `"1"`, `"2"`, ...). Initialized by `time_split`. Each phase entry:

```json
{
  "bootstrap_converge": {
    "status": "not_started|completed|iterating",
    "iteration": 0,
    "last_run_at": null,
    "output_paths": {},
    "feedback_consumed": false,
    "convergence": {
      "converged": false,
      "decided_by": null,
      "decided_at": null,
      "reason": null
    },
    "findings_summary": { "high": 0, "medium": 0, "low": 0 },
    "locked_skills": null
  },
  "space_split_converge": {
    "status": "not_started|completed|iterating",
    "iteration": 0,
    "last_run_at": null,
    "output_paths": {},
    "feedback_consumed": false,
    "convergence": {
      "converged": false,
      "decided_by": null,
      "decided_at": null,
      "reason": null
    },
    "findings_summary": { "high": 0, "medium": 0, "low": 0 },
    "locked_skills": null
  },
  "phase_review": {
    "status": "not_started|testing|approved",
    "summary_presented_at": null,
    "approved_at": null,
    "testing_recipe": null
  },
  "plans": {}
}
```

`findings_summary` and `locked_skills` are **optional** on `MainCommandState` — omitted from JSON when `null`. All three converge commands (`bootstrap_converge`, `space_split_converge`, `plan_epic_converge`) use `findings_summary`. `bootstrap_converge` and `space_split_converge` also use `locked_skills`.

### phase_review

Tracks the phase-level review and transition lifecycle:
- Set to `"testing"` by `/eigen_continue` (Mode 1) when it presents the phase summary and testing recipe to the user.
- Set to `"approved"` by `/eigen_continue` (Mode 2) when the user confirms manual testing passed.
- `testing_recipe` stores the generated testing instructions so they can be re-displayed.
- The pipeline does NOT cross phase boundaries without `phase_review.status == "approved"`.

---

## Per-Epic Plan State Entry

`state.phases[N].plans` is keyed by epic number (string: `"1"`, `"2"`, ...). Initialized as `{}` by `space_split_converge` on exit. Each epic entry:

```json
{
  "plan_epic_converge": {
    "status": "not_started|completed|iterating",
    "iteration": 0,
    "last_run_at": null,
    "output_paths": {},
    "feedback_consumed": false,
    "convergence": {
      "converged": false,
      "decided_by": null,
      "decided_at": null,
      "reason": null
    },
    "findings_summary": { "high": 0, "medium": 0, "low": 0 }
  },
  "swarm_execution": {
    "status": "not_started|pr_created|iterating|converged",
    "integration_branch": null,
    "pr_url": null,
    "pr_number": null,
    "manifest_path": null,
    "completed_at": null,
    "review_iteration": 0,
    "convergence": {
      "converged": false,
      "decided_by": null,
      "decided_at": null,
      "reason": null
    },
    "findings_summary": { "p1": 0, "p2": 0, "p3": 0 },
    "review_reports": []
  }
}
```

### swarm_execution lifecycle

- `"not_started"` — default
- `"pr_created"` — set by `orchestrate_swarm` after creating the PR (populates `pr_url`, `pr_number`, `integration_branch`, `manifest_path`)
- `"iterating"` — set by `review_swarm_pr` when P1/P2 findings remain (fixup tasks created)
- `"converged"` — set by `review_swarm_pr` when zero P1+P2 findings remain (PR ready to merge)

Note: `swarm_execution.findings_summary` uses **`p1/p2/p3`** (not `high/medium/low`).

Both `orchestrate_swarm` and `review_swarm_pr` run on the integration branch (`feat/P<N>.E<M>`). Pipeline state updates are committed to this branch and merge to `$EIGEN_BRANCH` when the PR is merged.

---

## Recommendations

The `recommendations` key sits at the **root level** of `pipeline_state.json`. It is a **forward-only advisory channel** used to pass low-severity observations to downstream commands at convergence time.

### Structure

Keyed by **target command name**. Each value is an array of recommendation objects:

```json
{
  "from": "<source command>",
  "at_iteration": 2,
  "phase": 1,
  "epic": null,
  "text": "Phase 3 has 38 features — bootstrap should plan heavier scaffolding."
}
```

### Valid Source -> Target Pairs

| Source Command | Can Recommend To |
|---|---|
| `deepen_time_split` | `bootstrap_converge`, `space_split_converge`, `plan_epic_converge`, `create_issues_from_plan_swarm` |
| `bootstrap_converge` | `space_split_converge`, `plan_epic_converge`, `create_issues_from_plan_swarm` |
| `space_split_converge` | `plan_epic_converge`, `create_issues_from_plan_swarm` |
| `plan_epic_converge` | `create_issues_from_plan_swarm` |

### Rules

- Maximum **5 entries per source-target pair** (`MAX_RECOMMENDATIONS_PER_PAIR`).
- Recommendations are **advisory, never blocking**. Downstream commands may follow or disregard them.
- Written **only at convergence** — findings that warrant another iteration belong in the feedback file.
- Only **low-severity findings** become recommendations. High and medium must be resolved through iteration.
- On each run, a source command replaces all entries where `from` matches its name (full replacement, not append).

---

## Feedback Lifecycle

### Who uses it

The feedback lifecycle with `feedback_consumed` flags applies **only to the `time_split` / `deepen_time_split` pair** — the only remaining main/deepen pair.

Self-converging commands (`bootstrap_converge`, `space_split_converge`, `plan_epic_converge`) manage their own iterate-until-converged loop internally via their swarm of reviewer agents. They do NOT use the main/deepen feedback exchange.

### Flow (time_split / deepen_time_split only)

```
1. time_split runs (first time)
   -> creates outputs
   -> sets own feedback_consumed = false (no feedback yet)
   -> sets deepen's feedback_consumed = true (deepen hasn't analyzed these outputs)

2. deepen_time_split runs
   -> reads time_split outputs
   -> writes feedback file
   -> sets time_split.feedback_consumed = false (fresh feedback available)
   -> sets own feedback_consumed = false

3. time_split runs again (iteration)
   -> reads feedback file (does NOT delete it)
   -> regenerates outputs incorporating feedback
   -> sets own feedback_consumed = true (feedback processed)
   -> sets deepen's feedback_consumed = true (outputs changed)

4. Repeat until deepen_time_split decides convergence.
```

### On Entry Guards

**time_split:**
- `iteration >= 1` AND feedback file exists AND `feedback_consumed == false` -> proceed (process feedback)
- `iteration >= 1` AND feedback file exists AND `feedback_consumed == true` -> STOP (run deepen again)
- `iteration >= 1` AND no feedback file -> STOP (run deepen first)

**deepen_time_split:**
- time_split `status == "not_started"` -> STOP (run time_split first)
- time_split `convergence.converged == true` -> STOP (already converged)

### Self-converging commands

`bootstrap_converge`, `space_split_converge`, and `plan_epic_converge` use `convergence.converged` as the exit condition and `iteration` to track rounds. Their `feedback_consumed` field exists in the schema but is **NOT toggled by the CLI** — the internal swarm loop manages all feedback state via `convergence_state.json`.

---

## Status Values

| Status | Used by | Meaning |
|---|---|---|
| `"not_started"` | All | Command has never run |
| `"completed"` | Main + Deepen | Command ran successfully on last invocation |
| `"iterating"` | Main only | Has run, feedback produced, awaiting next iteration |

**Swarm statuses** (on `swarm_execution`):

| Status | Meaning |
|---|---|
| `"not_started"` | Swarm has not run |
| `"pr_created"` | PR exists, not yet reviewed |
| `"iterating"` | Review found P1/P2 findings, fixup in progress |
| `"converged"` | Zero P1+P2 findings, PR ready to merge |

**Phase review statuses** (on `phase_review`):

| Status | Meaning |
|---|---|
| `"not_started"` | Phase not yet reviewed |
| `"testing"` | Summary presented, user testing in progress |
| `"approved"` | User confirmed testing passed, ready for next phase |

---

## Output Directory Structure

```
$EIGEN_ROOT/eigen_initiative/
  phases/
    pipeline_state.json                        # Created by time_split, read/updated by ALL
    initiative_summary.json                    # time_split output
    phase_1_manifest.md                        # time_split output
    phase_2_manifest.md                        # time_split output
    feedback/                                  # Initiative-level feedback
      deepen_time_split_feedback.json          # Owned by deepen_time_split
    phase_1/                                   # Per-phase outputs
      bootstrap-report.json                    # bootstrap_converge output
      convergence_state.json                   # bootstrap_converge internal state
      epic_manifest.json                       # space_split_converge output
      phase_e2e_config.json                    # space_split_converge output
      feedback/                                # Phase-level feedback
        bootstrap_converge_feedback.json       # bootstrap_converge convergence feedback
        space_split_converge_feedback.json     # space_split_converge convergence feedback
      epic_1/                                  # Created by space_split_converge
        epic.md                                # Epic definition (space_split_converge output)
        plan.md                                # Plan (plan_epic_converge output)
        feedback/                              # Epic-level feedback
          plan_epic_converge_feedback.json     # plan_epic_converge convergence feedback
        tasks/                                 # Created by create_issues_from_plan_swarm
          task_001.md                          # Task file
          swarm-manifest.json                  # Swarm manifest
      epic_2/
        ...same structure...
    phase_2/
      ...same structure...
  eigen_lessons/                               # Lesson extraction by converge commands
    time_split/                                # Lessons from deepen_time_split
    bootstrap_converge/                        # Lessons from bootstrap_converge
    space_split_converge/                      # Lessons from space_split_converge
    plan_epic_converge/                        # Lessons from plan_epic_converge
```

---

## Legacy Migration

The CLI handles backward compatibility with old state files via migration shims in `PhaseState.from_dict()`:

- Legacy `"bootstrap"` + `"deepen_bootstrap"` keys are migrated to `"bootstrap_converge"`
- Legacy `"space_split"` + `"deepen_space_split"` keys are migrated to `"space_split_converge"`
- Findings summary, locked_skills, and feedback_path are promoted from the old deepen entry

Legacy command names (`bootstrap`, `deepen_bootstrap`, `space_split`, `deepen_space_split`, `plan_phase_epic`, `deepen_plan_phase_epic`) are rejected by `cmd_get_context` and `cmd_mark_converged` with an error pointing to the `_converge` replacement.
