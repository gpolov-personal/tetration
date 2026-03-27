---
name: pipeline-state-schema
description: "Pipeline state schema reference for eigen-squared. Use when any command needs to read, create, or update pipeline_state.json — the single source of truth for iteration tracking. Triggers on: pipeline_state.json operations, feedback lifecycle, convergence decisions, recommendations."
---

# Pipeline State Schema — `$EIGEN_ROOT/eigen_initiative/phases/pipeline_state.json`

This is the **single source of truth** for iteration tracking across all eigen-squared pipeline commands. Every command reads this file on entry and updates it on exit.

Created by `time_split` on first run. Read and updated by all 10 initiative-scale commands: `time_split`, `deepen_time_split`, `bootstrap`, `deepen_bootstrap`, `space_split`, `deepen_space_split`, `plan_epic_converge`, `create_issues_from_plan_swarm`, `orchestrate_swarm`, `review_swarm_pr`.

---

## Full Schema

```json
{
  "schema_version": "1.0.0",
  "initiative": "<name from initiative document>",
  "created_at": "<ISO 8601>",
  "updated_at": "<ISO 8601>",

  "workflow": {
    "description": "Eigen-local pipeline: decompose across time, bootstrap foundations, decompose across space, plan for it, create tickets and then execute via agent swarm.",
    "commands": {
      "time_split": {
        "scope": "initiative",
        "description": "Split initiative into sequential E2E-testable phases using dependency DAG",
        "produces": ["phases/initiative_summary.json", "phases/phase_N_manifest.md", "phases/pipeline_state.json"],
        "consumed_by": ["bootstrap", "space_split", "deepen_time_split"]
      },
      "deepen_time_split": {
        "scope": "initiative",
        "description": "Review time_split output, produce iteration feedback, optionally write plugin lessons",
        "produces": ["phases/feedback/deepen_time_split_feedback.json"],
        "consumed_by": ["time_split"]
      },
      "bootstrap": {
        "scope": "per_phase",
        "description": "Create incremental project foundation (stubs, contracts, config) before swarm execution",
        "produces": ["phases/phase_N/bootstrap-report.json", "committed files in target repo and set required environment for the current phase taking into account previous phases executed"],
        "consumed_by": ["space_split", "deepen_bootstrap"]
      },
      "deepen_bootstrap": {
        "scope": "per_phase",
        "description": "Review bootstrap output, produce iteration feedback with code change guidance",
        "produces": ["phases/phase_N/feedback/deepen_bootstrap_feedback.json"],
        "consumed_by": ["bootstrap"]
      },
      "space_split": {
        "scope": "per_phase",
        "description": "Decompose phase into parallel epics with DAG ordering, create local epic files",
        "produces": ["phases/phase_N/epic_dag.json", "phases/phase_N/phase_e2e_config.json", "phases/phase_N/epic_M/epic.md"],
        "consumed_by": ["plan_epic_converge", "deepen_space_split"]
      },
      "deepen_space_split": {
        "scope": "per_phase",
        "description": "Review space_split output, produce iteration feedback with epic file guidance",
        "produces": ["phases/phase_N/feedback/deepen_space_split_feedback.json"],
        "consumed_by": ["space_split"]
      },
      "plan_epic_converge": {
        "scope": "per_epic",
        "description": "Self-converging command that generates and iteratively refines a strategic plan for an epic within a phase using an internal agent team",
        "produces": ["phases/phase_N/epic_M/plan.md", "phases/phase_N/epic_M/feedback/plan_epic_converge_feedback.json"],
        "consumed_by": ["create_issues_from_plan_swarm"]
      },
      "create_issues_from_plan_swarm": {
        "scope": "per_epic",
        "description": "Decompose a development plan into file-disjoint task files and generate a swarm-manifest.json",
        "produces": ["phases/phase_N/epic_M/tasks/task_NNN.md", "phases/phase_N/epic_M/swarm-manifest.json"],
        "consumed_by": ["orchestrate_swarm"]
      },
      "orchestrate_swarm": {
        "scope": "per_epic",
        "description": "Orchestrate parallel swarm execution across autonomous teammates",
        "produces": ["code changes", "PR"],
        "consumed_by": ["review_swarm_pr"]
      },
      "review_swarm_pr": {
        "scope": "per_epic",
        "description": "Scope-aware post-swarm PR review that spawns review agents, triages findings, and creates fixup task files",
        "produces": ["phases/phase_N/epic_M/review_report.md", "phases/phase_N/epic_M/tasks/task_NNN.md (review findings)", "updated swarm-manifest.json"],
        "consumed_by": ["orchestrate_swarm"]
      }
    },
    "chain_order": ["time_split", "bootstrap", "space_split", "plan_epic_converge", "create_issues_from_plan_swarm", "orchestrate_swarm", "review_swarm_pr"]
  },

  "state": {
    "time_split": {
      "status": "not_started|completed|iterating",
      "iteration": 0,
      "last_run_at": null,
      "output_paths": {
        "initiative_summary": null,
        "phase_manifests": []
      },
      "phase_count": null,
      "feedback_consumed": false,
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
      "findings_summary": { "high": 0, "medium": 0, "low": 0 }
    },
    "phases": {}
  },

  "recommendations": {
    "bootstrap": [],
    "space_split": [],
    "plan_epic_converge": [],
    "create_issues_from_plan_swarm": []
  }
}
```

---

## Per-Phase State Entry

`state.phases` (see above the `"phases": {}`) is keyed by phase number (string, e.g. `"1"`, `"2"`). Initialized as `{}` by `time_split`. Each phase entry:

```json
{
  "bootstrap": {
    "status": "not_started|completed|iterating",
    "iteration": 0,
    "last_run_at": null,
    "output_paths": {
      "bootstrap_report": null,
      "target_repo": null
    },
    "feedback_consumed": false,
    "convergence": {
      "converged": false,
      "decided_by": null,
      "decided_at": null,
      "reason": null
    }
  },
  "deepen_bootstrap": {
    "status": "not_started|completed",
    "iteration": 0,
    "last_run_at": null,
    "feedback_path": null,
    "feedback_consumed": false,
    "findings_summary": { "high": 0, "medium": 0, "low": 0 }
  },
  "space_split": {
    "status": "not_started|completed|iterating",
    "iteration": 0,
    "last_run_at": null,
    "output_paths": {
      "epic_dag": null,
      "phase_e2e_config": null,
      "github_issues": []
    },
    "feedback_consumed": false,
    "convergence": {
      "converged": false,
      "decided_by": null,
      "decided_at": null,
      "reason": null
    }
  },
  "deepen_space_split": {
    "status": "not_started|completed",
    "iteration": 0,
    "last_run_at": null,
    "feedback_path": null,
    "feedback_consumed": false,
    "findings_summary": { "high": 0, "medium": 0, "low": 0 }
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

---

## Per-Epic Plan State Entry

`state.phases[N].plans` (see above `"plans": {}`) is keyed by epic number (string, e.g. `"1"`, `"2"`). Initialized as `{}` by `space_split` on exit. Each epic plan entry:

```json
{
  "plan_epic_converge": {
    "status": "not_started|completed|iterating",
    "iteration": 0,
    "last_run_at": null,
    "output_paths": {
      "plan_file": null
    },
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

`plan_epic_converge` is a self-converging command that manages its own iteration cycle internally via an agent team. Unlike the other main/deepen pairs, it does NOT use separate main and deepen commands. It produces both `plan.md` and a feedback JSON, and decides convergence on its own. See Convergence section below.

`swarm_execution` tracks the full lifecycle of a swarm epic:
- Set to `"pr_created"` by `orchestrate_swarm` after creating the PR (includes `pr_url`, `pr_number`, `integration_branch`, `manifest_path`).
- Set to `"iterating"` by `review_swarm_pr` when P1/P2 findings remain (fixup tasks created, awaiting next orchestrate_swarm + review cycle).
- Set to `"converged"` by `review_swarm_pr` when zero P1+P2 findings remain (PR is ready to merge).
- `review_iteration` tracks how many review passes have occurred (0 = not reviewed yet).
- `convergence` follows the same pattern as deepen commands (max 8 iterations, oscillation detection).
- `review_reports` is an array of review report paths, one per iteration.

Both `orchestrate_swarm` and `review_swarm_pr` run from inside the same worktree on the `feat/P<N>.E<M>` branch. All pipeline_state updates are committed to this branch and merge to `$EIGEN_BRANCH` when the PR is merged.

`phase_review` tracks the phase-level review and transition lifecycle:
- Set to `"testing"` by `/eigen_continue` (Mode 1) when it presents the phase summary and testing recipe to the user.
- Set to `"approved"` by `/eigen_continue` (Mode 2) when the user confirms manual testing passed.
- `testing_recipe` stores the generated testing instructions so they can be re-displayed.
- The pipeline does NOT cross phase boundaries without `phase_review.status == "approved"`.

---

## Recommendations

The `recommendations` key sits at the **root level** of `pipeline_state.json`, alongside `state` and `workflow`. It is a **forward-only advisory channel** used exclusively by deepen commands **at convergence time** to pass low-severity observations to the next commands in the pipeline chain.

**Key distinction from feedback files:** During the iterative deepen cycle, all findings — high, medium, and low — go into the feedback file for the paired main command. Recommendations are **not** for the counterpart command; they are for downstream commands. Only **low-severity findings** that do not justify another iteration round but should not be lost are promoted to recommendations when the deepen command decides to converge. This ensures that useful context flows forward through the pipeline without forcing unnecessary iteration loops.

Each recommendation targets the **next command(s) in the chain** (never the paired main command), so the information reaches the stage that can actually act on it.

### Structure

`recommendations` is a dictionary keyed by **target command name** (always a downstream command in the chain). Each value is an array of observation objects:

```json
"recommendations": {
  "bootstrap": [
    {
      "from": "deepen_time_split",
      "at_iteration": 2,
      "phase": 1,
      "epic": null,
      "text": "Phase 3 has 38 features concentrated in 2 domains — bootstrap should plan heavier scaffolding for those domains."
    }
  ],
  "space_split": [],
  "plan_epic_converge": [],
  "create_issues_from_plan_swarm": []
}
```

Valid target keys: `bootstrap`, `space_split`, `plan_epic_converge`, `create_issues_from_plan_swarm`.

### Field Definitions

| Field | Type | Description |
|---|---|---|
| `from` | string | Which deepen/converge command wrote this (e.g., `"deepen_time_split"`, `"plan_epic_converge"`) |
| `at_iteration` | integer >= 1 | Which iteration of the source deepen command produced this |
| `phase` | integer >= 1 or null | Phase number this applies to (null = initiative-level) |
| `epic` | integer >= 1 or null | Epic number this applies to (null = all epics in the phase) |
| `text` | string | 1-2 sentence observation. Max ~200 characters. Describes observed condition + downstream implication. |

### Valid Source → Target Pairs

| Source (deepen/converge command) | Can write to |
|---|---|
| `deepen_time_split` | bootstrap, space_split, plan_epic_converge, create_issues_from_plan_swarm |
| `deepen_bootstrap` | space_split, plan_epic_converge, create_issues_from_plan_swarm |
| `deepen_space_split` | plan_epic_converge, create_issues_from_plan_swarm |
| `plan_epic_converge` | create_issues_from_plan_swarm |

### Ownership Rules

- **Deepen/converge commands own their entries**: on each run, a deepen or self-converging command replaces all entries where `from` matches its command name. It preserves entries written by other commands.
- **Produce commands are read-only**: they read `recommendations[my_name]` but never modify the dictionary.
- **Deepen commands also read** `recommendations[their_produce_command]` as review context — this gives them awareness of upstream observations when reviewing their paired produce command's output.
- **Self-converging commands** (`plan_epic_converge`) both read `recommendations[plan_epic_converge]` and write to downstream targets (e.g., `create_issues_from_plan_swarm`).

### Limits

- Maximum **5 entries per source-target pair** (e.g., at most 5 entries in `recommendations.bootstrap` where `from == "deepen_time_split"`).

### Behavioral Notes

- Recommendations are **advisory, never blocking**. Downstream commands may follow or disregard them based on their own analysis.
- Recommendations are written **only at convergence** — when a deepen or self-converging command decides the current stage is good enough. Findings that warrant another iteration belong in the feedback file, not here.
- Only **low-severity findings** should become recommendations. High and medium findings must be resolved through the feedback/iteration cycle before convergence.
- On each run, a deepen or self-converging command replaces all entries where `from` matches its name (full replacement, not append). Entries from other sources are left untouched.
- **Initial state**: all four arrays are empty. Initialized by `time_split` when creating `pipeline_state.json` for the first time.

---

## Status Values

- `"not_started"` — command has never run (or deepen state was reset after main command re-ran)
- `"completed"` — command ran successfully on its most recent invocation
- `"iterating"` — main command has run, deepen has produced feedback, awaiting next iteration (only used on main command states, not deepen states)

---

## Feedback Lifecycle

Feedback files are **owned by deepen commands** — they create and overwrite them. Main commands **read but never delete** feedback files.

### `feedback_consumed` field

Located on the **main command's** state entry (e.g., `state.time_split.feedback_consumed`, `state.phases[N].bootstrap.feedback_consumed`).

| Value | Meaning | Set by |
|-------|---------|--------|
| `false` | Fresh/unprocessed feedback exists — main command should read it on next run | deepen command (on exit) |
| `true` | Feedback has been read and incorporated by the main command | main command (on exit, after processing feedback) |

### `feedback_consumed` on deepen state

Located on the **deepen command's** state entry (e.g., `state.deepen_time_split.feedback_consumed`).

| Value | Meaning | Set by |
|-------|---------|--------|
| `false` | The deepen command's feedback file reflects the latest analysis | deepen command (on exit) |
| `true` | The main command has since re-run, producing new outputs that this feedback doesn't cover — deepen should re-analyze | main command (on exit, after regenerating) |

### Flow

```
1. main command runs (first time)
   → creates outputs
   → sets own feedback_consumed = false (no feedback yet to consume)
   → sets deepen's feedback_consumed = true (deepen hasn't analyzed these outputs)

2. deepen command runs
   → reads main command's outputs
   → writes feedback file (overwrites if previous exists)
   → sets main command's feedback_consumed = false (fresh feedback available)
   → sets own feedback_consumed = false (feedback reflects current analysis)

3. main command runs again (iteration)
   → reads feedback file (does NOT delete it)
   → regenerates outputs incorporating feedback
   → sets own feedback_consumed = true (feedback was processed)
   → sets deepen's feedback_consumed = true (outputs changed, deepen should re-analyze)

4. deepen command runs again
   → reads its own previous feedback file (still there — enables comparison)
   → reads main command's new outputs
   → overwrites feedback file with new assessment
   → sets main command's feedback_consumed = false
   → sets own feedback_consumed = false
   → ... cycle continues until convergence
```

### On Entry Guards (using feedback_consumed)

**Main commands** (time_split, bootstrap, space_split):
- `iteration >= 1` AND feedback file exists AND `feedback_consumed == false` → proceed to Iteration Protocol (process the feedback)
- `iteration >= 1` AND feedback file exists AND `feedback_consumed == true` → STOP ("feedback already processed, run deepen again for fresh review")
- `iteration >= 1` AND no feedback file → STOP ("run deepen first")

**Deepen commands** (deepen_time_split, deepen_bootstrap, deepen_space_split):
- Main command `status == "not_started"` → STOP ("run main command first")
- Main command `convergence.converged == true` → STOP ("already converged")
- Deepen's own `feedback_consumed == false` AND main command's `feedback_consumed == false` → feedback exists that main command hasn't used yet; warn user but proceed with re-analysis

**Self-converging commands** (`plan_epic_converge`):
- `plan_epic_converge` does NOT follow the main/deepen feedback pattern. It manages its own iteration cycle internally via an agent team, producing both plan output and feedback in a single invocation. The `feedback_consumed` field on its state entry is managed internally and does not require an external deepen command.

---

## Convergence

Convergence is **decided by deepen commands** for main/deepen pairs, and **internally** by self-converging commands. When convergence is decided:

```json
{
  "converged": true,
  "decided_by": "deepen_time_split|deepen_bootstrap|deepen_space_split|plan_epic_converge",
  "decided_at": "<ISO 8601>",
  "reason": "<rationale>"
}
```

For main/deepen pairs: once converged, both the main command and deepen command will STOP on entry with a convergence message. The next command in the chain can proceed.

For `plan_epic_converge`: convergence is managed internally by its agent team. The `decided_by` field is set to `"plan_epic_converge"` itself. Once converged, re-running `plan_epic_converge` will STOP on entry with a convergence message.

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
      bootstrap-report.json                    # bootstrap output
      epic_dag.json                            # space_split output
      phase_e2e_config.json                    # space_split output
      feedback/                                # Phase-level feedback
        deepen_bootstrap_feedback.json         # Owned by deepen_bootstrap
        deepen_space_split_feedback.json       # Owned by deepen_space_split
      epic_1/                                  # Created by space_split
        epic.md                                # Epic content (space_split output)
        plan.md                                # Plan (plan_epic_converge output)
        feedback/                              # Epic-level feedback
          plan_epic_converge_feedback.json  # Owned by plan_epic_converge
      epic_2/
        epic.md
        plan.md
        feedback/
          plan_epic_converge_feedback.json
    phase_2/
      ...same structure...
  eigen_lessons/                               # Lesson extraction by deepen commands
    time_split/                                # Lessons from deepen_time_split
    bootstrap/                                 # Lessons from deepen_bootstrap
    space_split/                               # Lessons from deepen_space_split
    plan_phase_epic/                           # Lessons from plan_epic_converge (dir name kept for backward compat)
```
