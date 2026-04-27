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
      (human checkpoint managed by /eigen_continue, not a CLI command)
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
    "findings_history": [
      { "iteration": 0, "p1": 1, "p2": 6, "p3": 14, "signatures": ["<sha1>", "..."] },
      { "iteration": 1, "p1": 1, "p2": 0, "p3": 19, "signatures": ["<sha1>", "..."] }
    ],
    "review_reports": []
  }
}
```

### swarm_execution lifecycle

- `"not_started"` — default
- `"pr_created"` — set by `orchestrate_swarm` after creating the PR (populates `pr_url`, `pr_number`, `integration_branch`, `manifest_path`)
- `"iterating"` — set by `review_swarm_pr` when P1/P2/P3 findings remain (fixup tasks created)
- `"converged"` — set by `review_swarm_pr` when zero P1+P2+P3 findings remain (PR ready to merge)

Note: `swarm_execution.findings_summary` uses **`p1/p2/p3`** (not `high/medium/low`).

### swarm_execution.findings_history

Per-iteration ledger appended by `review_swarm_pr` via `eigen-squared complete review_swarm_pr --findings-detail <path-to-json>`. Each entry:

```json
{ "iteration": <int>, "p1": <int>, "p2": <int>, "p3": <int>, "signatures": ["<sha1>", "..."] }
```

A finding's signature is `sha1("<normalized_file_path>|<category>|<normalized_title>")` where:
- `normalized_file_path` is the POSIX-style relative path with case preserved,
- `category` is the lowercase short category (`security`, `data-integrity`, `test-quality`, ...),
- `normalized_title` is the title lowercased, whitespace-collapsed, and stripped of trailing punctuation.

`findings_history` and `findings_summary` are coupled: `findings_summary` mirrors the latest `findings_history[-1]` counts. The CLI accepts a JSON file via `--findings-detail` whose `iteration` field MUST match the iteration just completed (i.e. `swarm_execution.review_iteration - 1` after the bump). A mismatch is rejected with a non-zero exit. Re-completing the same iteration replaces the existing entry rather than appending a duplicate.

Consumers:
- `review_swarm_pr` Convergence Protocol — the **oscillation rule** converges immediately with `CAPPED_BY_OSCILLATION` if any `(file, category)` pair (derived from a signature) appears in ≥ 3 distinct iterations within the same epic.
- `review_swarm_pr` Stage 0.6 (prior-context threading, Step 5) — review agents and workers read this ledger to know which signatures were raised before so they don't blindly re-raise or re-introduce them.
- `compound_improve` — historical record for cross-epic learning.

Sidecar: a richer JSON artifact `eigen_initiative/phases/phase_N/epic_M/review_convergence_state.json` stores the same iteration trajectory with full per-finding metadata (file, category, severity, title) the CLI does not need. The signatures in `findings_history` and the signatures in the sidecar are computed from the same scheme and must agree iteration-for-iteration.

Both `orchestrate_swarm` and `review_swarm_pr` run on the integration branch (`feat/P<N>.E<M>`). Pipeline state updates are committed to this branch and merge to `$EIGEN_BRANCH` when the PR is merged.

### swarm_execution.convergence.reason — taxonomy

`convergence.reason` is a free-text field (no CLI-side enum validation), but `review_swarm_pr` writes one of the prefixes below so downstream commands and the PR-comment renderer can dispatch on the leading token. The prefix is followed by a `:` and human-readable details.

| Prefix | Producer | Status set | Semantics |
|---|---|---|---|
| `All findings resolved` | review_swarm_pr Case 1.1 | converged | Clean convergence; no residual findings. |
| `P3 sweep completed` | review_swarm_pr Case 2.1 | converged | Bounded P3 sweep ran successfully; residual P3 list disclosed. |
| `P3 sweep introduced` | review_swarm_pr Case 2.2 | converged | Sweep introduced P1 / P2; commits auto-reverted to `p3_sweep.base_ref`. `swarm-manifest.json.p3_sweep.aborted=true`. |
| `CAPPED_BY_OSCILLATION` | review_swarm_pr oscillation circuit-breaker | converged | Same `(file, category)` pair appeared in ≥ 3 iterations — accepting current state to break the loop. Pairs and signatures recorded in `review_convergence_state.json.oscillation`. |
| `P1_REGRESSION_PERSISTENT` | review_swarm_pr Monotonicity rule M1 — third firing | converged | P1 count grew in three iterations; `monotonicity-violation` + `blocker-real-dep` task tagging did not stabilize the fix. Counter at `swarm-manifest.json.monotonicity.m1_firings == 2` going into the firing iteration. |
| `DIVERGING_LOOP` | review_swarm_pr Monotonicity rule M2 | converged | `p3` count rose while `p1+p2` did not improve across the most recent two iterations (iteration ≥ 2). Trajectory of the last three iterations recorded in `review_convergence_state.json.monotonicity.trajectory`. |
| `Maximum review iterations` | review_swarm_pr outer safety net | converged | Iteration cap (8) hit. Treated as Case 1.1 regardless of finding counts. |
| `<p1+p2> blocking findings remain` | review_swarm_pr Case 1.3 / Case M1 (firings 1–2) | iterating | Continuation; new R-tasks created. M1 firings 1–2 prepend `M1 firing #<count>:` to the reason text and tag tasks. |
| `Entering one-shot P3 sweep` | review_swarm_pr Case 1.2 | iterating | Sweep entry; `swarm-manifest.json.p3_sweep.active=true`. |

`compound_improve` reads these prefixes (and the structured sidecar files referenced by them) when rolling cross-epic patterns into the next-project context.

### swarm-manifest.json.monotonicity (per-epic)

Sibling to `swarm-manifest.json.p3_sweep` and `swarm-manifest.json.residual_p3`. Tracks the M1 firing counter so the third firing converges:

```json
{
  "monotonicity": {
    "m1_firings": <int>,
    "last_fired_at_iteration": <int|null>
  }
}
```

Initialized lazily (default `{ "m1_firings": 0, "last_fired_at_iteration": null }`) when M1 first fires. Read on entry to each iteration's Convergence Decision. Incremented in `review_swarm_pr` Stage 4.5 step 7 in Case M1. M2 does not write to this field.

### review_convergence_state.json.iterations[].file_iteration_counts (per-epic, per-iteration)

Streak counter per file used by the **architectural-escalation rule** (Tier 2 Step 2). Each entry records the count of consecutive recent iterations in which the file was modified by worker commits, ending at the iteration's review:

```json
{
  "iteration": 2,
  "file_iteration_counts": {
    "server/backend/supabase-schema-service.ts": 3,
    "server/ai/tool-dispatcher.ts": 1
  }
}
```

Computation (in `review_swarm_pr` Stage 2.4):
1. Find the prior iteration's report addition commit (`git log -1 --diff-filter=A`) — that is the iteration boundary. Iter 0 uses the merge-base with `$EIGEN_BRANCH`.
2. Run `git diff --name-only <boundary>..HEAD`, filter to `scope_files`.
3. For each modified file F: `count[F] = prev_count[F] + 1` if F was in iter (N-1)'s counts, else `count[F] = 1`.
4. Files NOT modified in this window are dropped (their streak is broken).

Consumer: `review_swarm_pr` Stage 4.1.a builds `escalation_files = { F : count[F] >= 2 }`. Each R-task whose `files_owned ∩ escalation_files ≠ ∅` is tagged with `architectural-escalation`. Backwards-compatible — missing field is treated as empty map.

### swarm-manifest.json.tasks[].architectural_escalation (per-task)

Boolean flag on R-task entries (sibling to `monotonicity_violation`). Set by `review_swarm_pr` Stage 4.5 when Stage 4.1.a's predicate fires for the task. Companion field `architectural_escalation_files: [<file>]` lists which file(s) triggered escalation.

Consumer: `orchestrate_swarm` worker spawn — when this flag is `true`, the spawn prompt prepends an ARCHITECTURAL ESCALATION REQUIRED constraint block (sibling to the P3-SWEEP CONSTRAINT block) requiring the worker to raise `[QUESTION] type: design_decision` before any production-code change. The leader's autonomous `design_decision` handler (orchestrate_swarm autonomous-mode rules) responds with one of: APPROVE INLINE (alternative bounded to files_owned), CONVERT TO SCOPE EXPANSION (alternative requires other files), or REQUEST REVISION (worker's alternatives weren't architectural). After two failed revisions the task is marked `failed` with reason `architectural_escalation_unresolved`.

### `finalize-iteration` CLI verb (atomic complete + status update)

Combines `complete review_swarm_pr` + `mark-converged swarm_execution` (or `set-swarm-status iterating`) into a single CLI call that performs both mutations under one state lock and one `save_state` call. POSIX atomicity (tmp + fsync + rename in `save_state`) then guarantees that a SIGKILL between the legacy paired calls cannot leave half-written state on disk.

```
eigen-squared finalize-iteration \
  --phase <phase> --epic <epic> \
  --status <converged|iterating> \
  [--reason <reason>]                # required when --status converged
  [--report-path <path>] \
  [--findings-summary '{"p1":x,"p2":y,"p3":z}'] \
  [--findings-detail /tmp/eigen_findings_iter_<N>.json]
```

On-disk effect is byte-equivalent to:
- `--status converged` → `complete review_swarm_pr ...` + `mark-converged swarm_execution --reason ...`
- `--status iterating` → `complete review_swarm_pr ...` + `set-swarm-status iterating ...`

Used by `review_swarm_pr` Stage 7 in the convergence-loop hot path. Legacy verbs (`complete`, `mark-converged`, `set-swarm-status`) remain available for non-hot-path callers (e.g., `bootstrap_converge`, `plan_epic_converge`, manual recovery).

The `--findings-detail` validation rules are identical to `complete review_swarm_pr` — iteration must match `swarm_execution.review_iteration - 1` after the bump. A failed validation aborts the entire verb (no partial state written) because the validation runs before any mutation is committed via `save_state`.

### swarm-manifest.json.tasks[].ownership_audit (per-task)

Records the outcome of the post-worker ownership audit run by `orchestrate_swarm` "Implementation Complete Message" step 1. Computed from `git diff --name-only` against the worker's commit range, with `task.files_owned ∪ task.test_files_owned` as the authoritative scope.

```json
"ownership_audit": {
  "out_of_scope_modified": ["<file>", ...],
  "out_of_scope_created": ["<file>", ...],
  "resolution": "clean" | "scope_expanded" | "reverted_modified" | "deleted_created" | "reverted_worker" | "failed"
}
```

`resolution` values:
- `clean` — no out-of-scope edits; audit passed without intervention.
- `scope_expanded` — leader approved INLINE via `mvf_scope_expansion`; `files_owned` was extended in the manifest.
- `reverted_modified` — leader chose REVERT for one or more modified files; `git checkout HEAD~<n> -- <file>` restored them.
- `deleted_created` — leader chose DELETE for newly-created out-of-scope files; `git rm` removed them.
- `reverted_worker` — entire worker commit range was reverted via `git revert`; task continues but with no committed work.
- `failed` — task is marked failed with reason `out_of_scope_unrecoverable`; review-iteration M1/oscillation logic handles re-attempt.

Backwards-compat: missing field on legacy tasks is interpreted as `clean` (audit was not yet implemented when the task ran).

### eigen_lessons/compound_improve/cross_epic_patterns.json (initiative-wide)

Cross-epic aggregation artifact written by `compound_improve` Stage 1.6. Lives at `$EIGEN_ROOT/eigen_initiative/eigen_lessons/compound_improve/cross_epic_patterns.json` (sibling to the per-command lesson directories). Records patterns that recurred in **3 or more epics** across the initiative.

Schema:

```json
{
  "generated_at": "<ISO 8601>",
  "eigen_root": "<absolute path>",
  "threshold": 3,
  "patterns": [
    {
      "kind": "oscillation" | "architectural_escalation" | "type_escape",
      "category": "<category>",
      "threat_class": "<threat_class or null>",
      "path_basename": "<basename or null>",
      "escape_pattern": "<pattern literal or null>",
      "supporting_epics": ["phase_1/epic_3", "phase_2/epic_1", "phase_3/epic_2"],
      "occurrences": 7,
      "first_seen": "<ISO 8601>",
      "last_seen": "<ISO 8601>",
      "recommendation": "<one-sentence deterministic guidance>"
    }
  ]
}
```

Sources walked by the aggregator (per epic):
- `review_convergence_state.json.iterations[].file_iteration_counts` — for kind `oscillation` (streak ≥ 2)
- `swarm-manifest.json.tasks[].architectural_escalation` + `monotonicity.m1_firings` + `pipeline_state.json.swarm_execution.convergence.reason` — for kind `architectural_escalation`
- `pipeline_state.json.swarm_execution.findings_history` (filtered to `category == "type-safety"` with type-escape title patterns) — for kind `type_escape`

Cross-epic equivalence is by `path_basename` (lowercased file basename) — full paths differ across initiatives but basenames carry semantic identity.

Consumers:
- `bootstrap_converge` Stage 2.1 — prepends a "Known oscillation-prone patterns from prior projects" advisory section to the bootstrapper prompt context, filtered to patterns whose category/path-basename plausibly applies to phase scaffolding.
- `plan_epic_converge` Stage 2.1 — same, filtered to patterns relevant to the current epic's features.

Missing artifact is non-fatal everywhere: consumers treat "file does not exist" as "no known patterns" and proceed normally.

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
| `"iterating"` | Review found P1/P2/P3 findings, fixup in progress |
| `"converged"` | Zero P1+P2+P3 findings, PR ready to merge |

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

Legacy command names are handled differently depending on the pair:
- `bootstrap`, `deepen_bootstrap`, `space_split`, `deepen_space_split` — explicitly rejected by `cmd_get_context` and `cmd_mark_converged` with an error pointing to the `_converge` replacement.
- `plan_phase_epic`, `deepen_plan_phase_epic` — silently migrated via `EpicPlan.from_dict()` (no rejection error, old keys are loaded into the new `plan_epic_converge` structure).
