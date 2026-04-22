# lite_plan — internals

Design notes for `plugins/eigen-lite/commands/lite_plan.md`. Explains the five-stage structure, why lite collapses what eigen-squared splits across four commands, and how subagents are wired in.

Audience: contributors modifying lite_plan. Users should read the command file itself.

## Why five stages, not four commands

eigen-squared splits planning across:

| squared command | role |
|-----------------|------|
| `space_split_converge` | decompose N features into epics across phases |
| `bootstrap_converge` | scaffold missing tooling/entities |
| `plan_epic_converge` | produce per-epic `plan.md` via 4-round review loop |
| `create_issues_from_plan_swarm` | deterministically generate tasks + manifest |

Each has its own agent team and convergence loop. Total cost: ~30min per epic on a typical initiative. lite targets initiatives where that cost dwarfs the implementation itself.

lite collapses the same work into a **single command with five stages** and a **single pass per stage**:

| lite stage | analogue |
|-----------|----------|
| A — Introspection + Capture | (lite-native; uses `language-profiles` skill) |
| B — Phase Manifest | `time_split` + portion of `space_split_converge` for N=1 |
| C — Bootstrap Delta | `bootstrap_converge` without review loop |
| D — Multi-Epic Decomposition | `space_split_converge` epic-formation stages |
| E — Per-Epic Plan + Tasks + Manifest | `plan_epic_converge` + `create_issues_from_plan_swarm` |

The correctness guarantee that squared buys with convergence loops — "diverse reviewers catch gaps the planner missed" — is preserved by **spawning multiple analyst subagents in parallel** at the stages that most need design diversity (D and E). The main lite_plan agent then synthesises rather than iterates. The cost trade-off is acceptable only because lite is capped at 5 features and targets existing codebases where the search space is small.

## State machine contract

lite_plan reads and writes a single state file: `eigen_initiative/phases/pipeline_state_lite.json`. The only fields it mutates are under `lite_plan`:

```
lite_plan:
  status: not_started | in_progress | completed
  stages_completed: [list of markers, ordered]
  output_paths: {key: path}
  iteration: incremented on every `complete` call
  convergence: {converged, decided_by, decided_at, reason}
```

Stage markers are:
- `A`, `B`, `C`, `D` — singleton stages.
- `E:<M>` — one marker per epic processed in Stage E's loop.

**Validation rule** (enforced by `validate_state_lite`): if `lite_plan.convergence.converged == true`, `stages_completed` must include `E:<M>` for every epic in `state.epics`. Missing markers mean an incomplete planning run was force-converged — flagged as an error.

## Idempotence contract

Every stage skips its work if:
1. Its marker is in `stages_completed`, AND
2. Its primary output file exists on disk.

If the marker is present but the file is missing, disk wins — re-run the stage. If the file is present but the marker is missing (e.g. crash between file write and `complete` call), the stage detects the file and writes the marker without redoing the work.

**Non-idempotent operations** (explicitly called out in the command):
- Stage A's interactive interview. Re-running requires the user to re-answer.
- Stage E's integration branch creation. If `feat/P1.E<M>` already exists with commits from a prior partial run, lite_plan does NOT reset — it assumes the branch is a consistent checkpoint. Manual cleanup (`git branch -D feat/P1.E<M>`) is required to force a fresh E.6.

## Subagent wiring (Stages D and E)

lite_plan is the **only** lite command that spawns subagents during planning. It uses the `Agent` tool with `subagent_type="general-purpose"`.

### Stage D — 4 decomposition analysts

Launched in parallel via a single message with 4 `tool_use` blocks. Each analyst reads the same inputs (`feature_summary.md`, `phase_1_manifest.md`) and produces a JSON candidate with a different bias:

| analyst | bias |
|---------|------|
| cluster-first | natural clusters from the DAG |
| dependency-chain | topological layers / critical paths |
| domain-first | domain labels per feature |
| interface-surface | minimise cross-epic API contracts |

Each returns a `{strategy, epics, interfaces, orthogonality_score, concerns}` blob. The main planner picks the highest `orthogonality_score`, breaks ties by fewest non-trivial interfaces, then appends the E2E Testing epic (if `e2e_requested`).

Analysts are **read-only** — they never write files. This is enforced by prompt, not by the `Agent` tool contract. Reviewers auditing contributor changes to Stage D should verify analyst prompts do not include `Write` instructions.

### Stage E — 4 design analysts per epic

For each epic in `execution_order`, launch 4 analysts in parallel:

| analyst | role |
|---------|------|
| Parallelization architect | file ownership, waves, shared files, interfaces within epic |
| Strategic/risk architect | architectural decisions, acceptance criteria, risks |
| Skills/stack specialist | language-profile idioms, test conventions |
| E2E scenario designer | epic validation criteria → `e2e_scenarios` entries |

Each returns a JSON fragment. The main planner merges with per-field conflict rules (see `lite_plan.md` §E.3) — no second pass.

**Worst case cost**: 4 analyst subagents × number of epics. For a 5-epic initiative (4 features + E2E), that's 4 (Stage D) + 20 (Stage E) = 24 subagents total. Each is read-only and runs in parallel within its stage.

## Output contract (what lite_swarm and lite_review consume)

| file | produced by | consumed by |
|------|-------------|-------------|
| `eigen_initiative/feature_summary.md` | Stage A | Stages B, C, D, E (context) |
| `eigen_initiative/phases/phase_1_manifest.md` | Stage B | Stages C, D, E (context) |
| `.eigen-lite/bootstrap-report.json` | Stage C | Stage D (tooling_decisions), `lite_swarm` (language/framework context) |
| `eigen_initiative/phases/phase_1/epic_<M>/epic.md` | Stage D | `lite_swarm` (Stage 0.2), `lite_review` (Stage 0.3) |
| `eigen_initiative/phases/phase_1/epic_manifest.json` | Stage D | Stage E (cross-epic interfaces) |
| `eigen_initiative/phases/phase_1/phase_e2e_config.json` | Stage D | Stage E's `e2e_config` generation |
| `eigen_initiative/phases/phase_1/epic_<M>/plan.md` | Stage E | `lite_swarm` (Stage 0.2) |
| `eigen_initiative/phases/phase_1/epic_<M>/tasks/*.md` | Stage E | `lite_swarm` worker spawn prompts |
| `eigen_initiative/phases/phase_1/epic_<M>/swarm-manifest.json` | Stage E | `lite_swarm` (Stage 0.3), `lite_review` (Stage 0.2) |

A Stage E output that fails the manifest validation gate (ownership overlap, unknown `blocked_by`, etc.) is **not committed**. The user must edit the synthesised `plan.md` or re-run. This prevents broken manifests from reaching `lite_swarm`, where they would cause cascading worker failures.

## CLI calls lite_plan uses

Every lite CLI subcommand invoked from `lite_plan.md`:

- `eigen-lite get-context lite_plan --json` — on entry.
- `eigen-lite complete lite_plan --stage <marker> [--output-paths <json>]` — after each stage.
- `eigen-lite init-epics --epics <json-list>` — Stage D.6.
- `eigen-lite sync --branch $EIGEN_BRANCH` — Stage E.6.
- `eigen-lite checkout-branch --epic <M> --create` — Stage E.6.
- `eigen-lite complete lite_plan --converged --reason ...` — final.
- `eigen-lite commit-state --message ...` — final.

No `schedule-next` call inside lite_plan — the watchdog handles scheduling the next command (`lite_swarm E1`) on its next tick after lite_plan exits.

## Failure modes and their recovery

| mode | detection | recovery |
|------|-----------|----------|
| Stage A crashes mid-interview | no `A` marker, no `feature_summary.md` | re-run, user re-answers |
| Stage C writes partial JSON | no `C` marker, file present but missing required keys | delete `.eigen-lite/bootstrap-report.json`, re-run |
| Stage D commits epic files but crashes before `init-epics` | `D` marker absent, `epic_manifest.json` present | re-run → D detects file present, proceeds to init-epics only |
| Stage E loops crashes after epic 2 but before epic 3 | `E:1`, `E:2` markers present, `E:3` absent | re-run → E loop starts at epic 3 |
| swarm-manifest validation fails in E.5 | stage aborts before commit | user edits `plan.md` manually, re-runs E for that epic |
| user adds/removes a feature mid-run | no automatic detection | **unsupported** — user deletes `eigen_initiative/` + `.eigen-lite/bootstrap-report.json`, starts over |

## Why no convergence loop during planning

squared's loops exist because:
1. large initiatives have many moving parts that interact non-obviously,
2. a bad plan propagates into weeks of wasted worker time,
3. agent teams can cheaply iterate in parallel.

lite's constraints flip these:
1. 2–5 features × ≤5 epics is within a single planner's context window,
2. a bad plan wastes at most a few hours of worker time because the whole initiative is small,
3. teams + flock locks add latency that dominates actual planning time for small inputs.

The trade-off is explicit: lite accepts a somewhat-worse plan in exchange for ~10× faster planning. When this trade-off is wrong for a given initiative, the user should use eigen-squared instead — and lite_plan's hard cap on feature count enforces this.
