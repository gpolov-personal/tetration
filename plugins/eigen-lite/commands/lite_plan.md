---
name: lite_plan
description: Single-pass planning for a small single-phase initiative — introspection, interview, epic decomposition, per-epic plans + swarm manifests
---

# lite_plan — Initiative Planner (lite)

## Pipeline Context

```
                        eigen-lite pipeline
                        ~~~~~~~~~~~~~~~~~~
  lite_start → lite_plan ──► lite_swarm ◄──► lite_review
                 ▲
                 │
            YOU ARE HERE
```

You are the **planner** for an eigen-lite initiative. Unlike eigen-squared (which splits planning across four commands — `space_split_converge`, `bootstrap_converge`, `plan_epic_converge`, `create_issues_from_plan_swarm` — each with its own convergence loop), lite collapses the whole pipeline into **one command with five stages and a single pass per stage**.

The input is a user-described set of 2–5 features layered onto an existing codebase. The output is everything `lite_swarm` needs to start executing: a feature summary, a phase manifest (always phase 1), a bootstrap report, one epic.md per epic, and per-epic plan.md + tasks/*.md + swarm-manifest.json + integration branches.

**Single-pass philosophy**: lite does not run convergence loops during planning. When a stage needs multiple perspectives, it spawns parallel analyst subagents (via the `Agent` tool) and the main planner synthesises the best candidate. This keeps planning fast while still benefiting from diverse review angles.

## Environment

- `$EIGEN_ROOT` must be set (absolute path to the target project root).
- `$EIGEN_BRANCH` must be set (default `main`).
- The `eigen-lite` CLI must be on `$PATH`.
- Cross-plugin skills from eigen-squared are loaded on demand via `Skill("eigen-squared:<name>")`.

If any required var is missing → **STOP** with a descriptive error.

---

## On Entry

```bash
eigen-lite get-context lite_plan --json
```

Example JSON:
```json
{
  "command": "lite_plan",
  "feature_set": "my-initiative",
  "scope": "initiative",
  "stages_completed": ["A", "B"],
  "output_paths": {
    "feature_summary": "eigen_initiative/feature_summary.md",
    "phase_manifest": "eigen_initiative/phases/phase_1_manifest.md"
  },
  "iteration": 1
}
```

| Field | Meaning |
|-------|---------|
| `stages_completed` | Ordered list of completed stage markers. `"A" "B" "C" "D" "E:1" "E:2"` is the full set when there are 2 epics (no E2E). If E2E is last (e.g. `E:3`), all markers appear. |
| `output_paths` | Absolute-within-repo paths produced by prior stages. Use these to resume without re-reading the whole state. |
| `iteration` | Incremented each time `lite_plan` exits. Non-zero means the user re-invoked the command — resume from the first missing stage. |

**Idempotence contract**: every stage below is skipped if its marker is already in `stages_completed` AND its output file is present on disk. If the marker is present but the output file has been deleted, re-run the stage (disk is ground truth; state is a cache).

---

## Overview of Stages

| Stage | Goal | Output | Subagents |
|-------|------|--------|-----------|
| A | Introspection + feature interview | `eigen_initiative/feature_summary.md` | 0 |
| B | Phase manifest (N=1 collapse of time_split) | `eigen_initiative/phases/phase_1_manifest.md` | 0 |
| C | Bootstrap delta (conditional) | `.eigen-lite/bootstrap-report.json` | 0 |
| D | Multi-epic decomposition | `epic_manifest.json`, `phase_e2e_config.json`, per-epic `epic.md` | 4 (parallel analysts) |
| E | Per-epic plan + tasks + swarm manifest (looped) | `plan.md`, `tasks/*.md`, `swarm-manifest.json`, `feat/P1.E<M>` branch | 4 per epic (parallel analysts) |

After each stage, update state:
```bash
eigen-lite complete lite_plan --stage <marker>
```

After Stage E's last iteration, converge:
```bash
eigen-lite complete lite_plan --converged --reason "all stages complete"
```

---

## Stage A — Introspection + Capture

### A.1 Precondition

If `"A"` in `stages_completed` AND `feature_summary.md` exists → **skip to Stage B**.

### A.2 Load language profile

Invoke the eigen-squared skill:

```
Skill("eigen-squared:language-profiles")
```

Use its detection table to identify the project's primary language(s). If the project is polyglot, rank languages by (a) line count in owned source dirs, (b) presence of a manifest file (`pyproject.toml`, `package.json`, `go.mod`, `Cargo.toml`). Record the full ranked list — do not collapse to a single winner; downstream stages need the full list.

If `language-profiles` returns no match, fall back to a generic profile and emit a warning. Do not stop.

### A.3 Repo introspection

Walk the repo (read-only) and capture:
- Manifest files (one per language): path + detected framework + linter + test runner.
- Top-level domain directories (depth ≤ 2): list with rough file counts.
- Existing entity/contract files (if any): path + kind.
- CI workflows (`.github/workflows/*.yml`, `.gitlab-ci.yml`, etc.).
- Test layout: unit vs integration vs e2e conventions if detectable.

If the repo is a monorepo (multiple manifests in sibling dirs), stop and ask the user to pick a subtree. lite does NOT support multi-package orchestration in a single initiative.

### A.4 Interactive interview

Ask the user, in order (use `AskUserQuestion` — this is the one stage where the command pauses for human input):

1. **Feature set name** — short slug for this initiative (letters, digits, dashes).
2. **Feature list** — 2–5 features. For each:
   - Short name (3–6 words).
   - One-paragraph blackbox description (user-facing behaviour, NOT implementation).
   - Priority (`P1` must-have, `P2` should-have, `P3` nice-to-have).
   - Local dependencies (list of other feature names it depends on, or `none`).
   - External dependencies (third-party APIs, DBs, etc.).
3. **E2E scope** — should this initiative end with a dedicated E2E Testing epic that exercises all features together? (default `yes` unless all features are trivially independent).

**Hard cap**: if the user tries to add a 6th feature, refuse and tell them to use eigen-squared instead. The whole point of lite is small initiatives.

**Dependency cycle check**: if `local_deps` form a cycle among features, stop and ask the user to linearise.

### A.5 Write feature_summary.md

Layout:

```markdown
---
feature_set: <slug>
feature_count: <N>
created_at: <ISO-8601>
languages: [<ranked list from A.2>]
frameworks: {<lang>: <framework>, ...}
e2e_requested: <true|false>
---

# Feature Summary — <slug>

## Features

### F1 — <name>  (<priority>)
**Description:** <paragraph>
**Local deps:** <list or none>
**External deps:** <list or none>

...

## Detected repo profile

- Languages (ranked): <list>
- Primary framework(s): <list>
- Test runner(s): <list>
- Linter(s) + type checker(s): <list>
- CI: <list of workflow paths>
- Top-level domains: <list with counts>
- Existing entities (if any): <list>

## Notes for downstream stages

<any caveats: polyglot, missing test runner, partial coverage, etc.>
```

### A.6 Complete

```bash
eigen-lite complete lite_plan --stage A --output-paths '{"feature_summary": "eigen_initiative/feature_summary.md"}'
```

---

## Stage B — Phase Manifest

### B.1 Precondition

If `"B"` in `stages_completed` AND `phases/phase_1_manifest.md` exists → **skip to Stage C**.

### B.2 Build feature DAG

Parse `feature_summary.md`. Construct the dependency DAG:
- Nodes = features.
- Edges = local_deps (F2 → F1 means F2 depends on F1).

Compute:
- Topological order.
- Roots (features with no deps).
- Leaves (features nothing else depends on).
- Natural clusters — connected components, or dense sub-DAGs with high inner-degree vs outer-degree.
- Critical paths — longest paths through the DAG.

### B.3 Write phase_1_manifest.md

```markdown
---
phase: 1
initiative: <slug>
feature_count: <N>
clusters_included: <list of cluster names, or "none" if all isolated>
priority_distribution: {P1: <x>, P2: <y>, P3: <z>}
e2e_summary: "<one paragraph: what the phase-level E2E validates>"
depends_on_phases: []
created_at: <ISO-8601>
---

# Phase 1 — <slug>

## Phase E2E Test

<paragraph describing the end-to-end flow that exercises all features together>

## Features by Domain

| ID | Name | Priority | Local Deps | Cluster |
|----|------|----------|-----------|---------|
| F1 | ... | P1 | — | cluster-a |
...

## Natural Clusters in This Phase

<list clusters, feature membership, reason for grouping>

## Blackbox Feature Specifications

<verbatim paragraphs from feature_summary.md, one per feature>

## Downstream Notes

<caveats for Stage C/D/E: features that need new tooling, entities that don't exist yet, etc.>
```

**Intentionally omitted** (vs squared's space_split output): `## Cross-Phase Dependencies` — lite is single-phase.

### B.4 Complete

```bash
eigen-lite complete lite_plan --stage B --output-paths '{"phase_manifest": "eigen_initiative/phases/phase_1_manifest.md"}'
```

---

## Stage C — Bootstrap Delta (conditional)

### C.1 Precondition

If `"C"` in `stages_completed` AND `.eigen-lite/bootstrap-report.json` exists → **skip to Stage D**.

### C.2 Delta detection

For each category, classify the repo state as `ABSENT | PARTIAL | PRESENT`:

1. **Language manifest** per detected language.
2. **Linter config** per language (e.g. `ruff.toml`, `.eslintrc.*`).
3. **Type checker config** (e.g. `mypy.ini`, `tsconfig.json`).
4. **Test runner config** (e.g. `pytest.ini` with suitable paths).
5. **Domain directories** referenced in `phase_1_manifest.md`.
6. **Cross-feature entity/contract files** referenced but not present.
7. **CI workflow** (at least one).

`delta = 0` iff every category is `PRESENT` AND the language-profile's verification command (lint + type-check) exits zero.

### C.3 Delta = 0 → synthesize bootstrap-report.json

Write a semantically faithful report (NOT a stub). Consumers read fields like `tooling_decisions` and `entities_created` to plan epics correctly.

```json
{
  "phase": 1,
  "iteration": 0,
  "languages": [{"language": "...", "role": "primary"}, ...],
  "tooling_decisions": {
    "<lang>": {
      "package_manager": "...",
      "framework": "...",
      "linter": "...",
      "type_checker": "...",
      "test_runner": "..."
    }
  },
  "repo_state_before": "existing repo with N files",
  "timestamp": "<ISO-8601>",
  "delta_applied": {
    "git_init": false,
    "directories_created": [],
    "entity_stubs_created": [],
    "api_contracts_created": [],
    "message_contracts_created": [],
    "config_files_created": [],
    "ci_created": false,
    "server_project_detected": <bool>,
    "dockerfile_created": false,
    "docker_compose_created": false,
    "docker_compose_services": [],
    "dockerignore_created": false,
    "exposed_port": null,
    "health_check_path": null,
    "total_files_created": 0,
    "total_files_modified": 0,
    "total_files_skipped": <count of existing>
  },
  "verification": {
    "status": "passed",
    "warnings": [<any>],
    "commands_used": ["<lint cmd>", "<type-check cmd>"]
  },
  "entities_created": [<scan of existing stubs matching domain patterns>],
  "contracts_created": [<scan of openapi/proto/schema dirs>],
  "commits": [],
  "iteration_history": [{"iteration": 0, "trigger": "introspection_only"}]
}
```

### C.4 Delta > 0 → minimal-scope inline bootstrap

When `delta > 0`, scaffold ONLY the missing pieces. NO convergence loop, NO reviewer teammates.

- Load `Skill("eigen-squared:bootstrap-internals")` if it exists, or implement inline following its prescriptions.
- Run **once** through the bootstrapper's equivalent of Stage 0–5:
  1. Lock toolchain decisions per language (use Stage A's detected profile).
  2. Create missing config files (linter, type checker, test runner) — do NOT touch source.
  3. Add missing CI workflow (minimal: lint + type-check + test).
  4. Create missing domain directories with a single `__init__.py` / `index.ts` placeholder.
  5. Never generate entity stubs for an existing non-empty file — skip and record `skipped`.
- Run the verification commands. If lint/type-check fails on newly-added config, roll back the additions and emit a warning. Do NOT retry.
- Commit: `git add <added files> && git commit -m "chore(lite): bootstrap minimal tooling for P1"`.

Write `bootstrap-report.json` with accurate `delta_applied` counts and `verification.status`.

**Explicit abort**: if the user passed `--no-scaffold` (flag on the command invocation), refuse to write config changes. Instead write the report with `verification.status: "failed_with_warnings"` listing every missing item, and stop before Stage D. Let the user fix manually and re-run.

### C.5 Complete

```bash
eigen-lite complete lite_plan --stage C --output-paths '{"bootstrap_report": ".eigen-lite/bootstrap-report.json"}'
```

---

## Stage D — Multi-Epic Decomposition (with parallel analysts)

### D.1 Precondition

If `"D"` in `stages_completed` AND `phases/phase_1/epic_manifest.json` exists → **skip to Stage E**.

### D.2 Spawn 4 decomposition analysts in parallel

Goal: produce candidate epic decompositions from four different angles and synthesise the most orthogonal one.

Use the `Agent` tool to launch these **in parallel** (single message, four tool_use blocks):

1. **cluster-first** — takes natural clusters from `phase_1_manifest.md` as epic seeds. Merges singletons by domain, splits oversized clusters by sub-domain.
2. **dependency-chain** — partitions features by topological layer / critical-path band. Each layer = candidate epic.
3. **domain-first** — groups features by `domain` label. Flags features whose local_deps cross a domain boundary (orthogonality violation).
4. **interface-surface** — enumerates, for each candidate grouping across the three other analysts' proposals, the cross-epic API contracts that would be needed. Ranks: the grouping with the fewest non-trivial interfaces wins.

**Analyst prompt template** (customise subject per analyst):

```
You are a decomposition analyst for a lite initiative. Analyze:
  - Feature summary: eigen_initiative/feature_summary.md
  - Phase manifest: eigen_initiative/phases/phase_1_manifest.md

Produce a decomposition candidate with this shape (JSON):
{
  "strategy": "<cluster-first|dependency-chain|domain-first|interface-surface>",
  "epics": [
    {"epic_number": 1, "name": "...", "features": ["F1", "F2"],
     "rationale": "why these features belong together"}
  ],
  "interfaces": [
    {"name": "...", "provider": "P1.E1", "consumers": ["P1.E2"], "contract": "..."}
  ],
  "orthogonality_score": <0-10, higher = more orthogonal>,
  "concerns": [<list of potential issues>]
}

Output ONLY the JSON, no commentary.
```

### D.3 Synthesise

Read the 4 candidates. Select the final decomposition by:
- Prefer the candidate with the highest `orthogonality_score`.
- If two candidates tie, prefer the one with fewer non-trivial interfaces.
- Balance epic sizes — target 1–3 features per feature epic; merge singletons if they share a domain.
- If no candidate is adequate (e.g. all scores < 5), pick the best and record the concerns verbatim in the final `epic.md` under a "Caveats" section — do NOT loop.

### D.4 Append the E2E Testing epic

If `e2e_requested: true` in `feature_summary.md`:
- Append an epic at the end with `epic_number = feature_epic_count + 1`, `name: "E2E Testing"`, `features: []`, `is_e2e_epic: true`.
- Its validation criteria summarise the phase-level E2E flow from `phase_1_manifest.md`.

### D.5 Write artifacts

**Per feature epic**, write `eigen_initiative/phases/phase_1/epic_<M>/epic.md`:

```markdown
---
id: "P1.E<M>"
title: "<epic name>"
type: epic
state: open
labels: ["lite", "feature-epic"]
phase: 1
epic_number: <M>
features: [<feature IDs>]
feature_count: <N>
clusters_included: [<cluster names>]
is_e2e_epic: false
task_ids: []
created_at: <ISO-8601>
updated_at: <ISO-8601>
---

# <epic title>

## Features
| ID | Name | Priority | Local Deps |
|----|------|----------|-----------|
...

## Validation Criteria
- [ ] <criterion tied to acceptance of the feature(s)>

## Epic Outputs
<interfaces_provided — from D.3 — each with interface_name, consumer_epics, contract, concrete_files>

## Blackbox Feature Specifications
<verbatim paragraphs from feature_summary.md for each feature in this epic>

## Bootstrap Context
<tooling decisions from bootstrap-report.json relevant to this epic's languages>

## Caveats
<from D.3 synthesis, if any>

## Comments
```

**For the E2E Testing epic** (if present), write `epic_<last>/epic.md`:

```markdown
---
id: "P1.E<last>"
title: "E2E Testing"
type: epic
labels: ["lite", "e2e-epic"]
phase: 1
epic_number: <last>
features: []
feature_count: 0
is_e2e_epic: true
task_ids: []
---

# E2E Testing

## Validation Criteria
<initiative-level E2E flows from phase_1_manifest.md>

## Infrastructure Requirements
<what the E2E suite needs — pulled from feature-summary external_deps; if none, state "external_services: none">

## Blackbox Summary of All Features
<one-paragraph recap per feature epic>
```

**Single `epic_manifest.json`** at `phases/phase_1/epic_manifest.json`:

```json
{
  "phase": 1,
  "initiative": "<slug>",
  "epic_count": <N>,
  "execution_order": ["P1.E1", "P1.E2", ..., "P1.E<last>"],
  "cross_phase_inputs": [],
  "epics": [
    {"id": "P1.E1", "epic_number": 1, "local_path": "epic_1/",
     "name": "...", "features": [...], "clusters_included": [...],
     "interfaces_provided": [...], "validation_summary": "...",
     "is_e2e_epic": false},
    ...
  ],
  "phase_e2e_test": "<summary>",
  "created_at": "<ISO-8601>"
}
```

**`phase_e2e_config.json`** at `phases/phase_1/phase_e2e_config.json`:

```json
{
  "phase": 1,
  "test_environment": "external_services",
  "infrastructure_requirements": [<from E2E epic.md, empty list if none>],
  "e2e_test_dir": "tests/e2e/",
  "e2e_test_command": "<detected from language profile>",
  "e2e_marker": "e2e",
  "e2e_output_format": "junit",
  "e2e_file_pattern": "test_e2e_*.py"
}
```

### D.6 Initialise `state.epics`

```bash
eigen-lite init-epics --epics '[{"epic": 1, "is_e2e_epic": false}, ..., {"epic": <last>, "is_e2e_epic": true}]'
```

### D.7 Complete

```bash
eigen-lite complete lite_plan --stage D --output-paths '{"epic_manifest": "eigen_initiative/phases/phase_1/epic_manifest.json"}'
```

---

## Stage E — Per-Epic Plan + Tasks + Manifest (looped)

**Per feature epic** (E2E Testing epic is handled slightly differently — see E.6):
execute E.1–E.5 in order, then commit + checkout the integration branch in E.6, then complete that iteration with marker `E:<M>`.

If `"E:<M>"` in `stages_completed` AND `phases/phase_1/epic_<M>/swarm-manifest.json` exists → **skip to the next epic**.

If `plan.md` exists but `swarm-manifest.json` is missing → resume from E.4 for that epic.

### E.1 Load epic context

Read:
- `phases/phase_1/epic_<M>/epic.md`
- `phases/phase_1/epic_manifest.json` (for interface map)
- `phases/phase_1_manifest.md`
- `feature_summary.md`
- `.eigen-lite/bootstrap-report.json` (for tooling decisions)

### E.2 Spawn 4 design analysts in parallel

Launch via the `Agent` tool, single message, four tool_use blocks:

1. **Parallelization architect** — designs file ownership boundaries, execution waves, shared files, interface dependencies between tasks within the epic.
2. **Strategic/risk architect** — surfaces architectural decisions, external-dep verification needs, acceptance criteria per feature, and risk flags.
3. **Skills/stack specialist** — consults `language-profiles` skill for idiomatic patterns, test conventions, and maps features to appropriate skill invocations inside worker prompts.
4. **E2E scenario designer** — converts the epic's validation criteria into concrete `e2e_scenarios` entries (name, description, components_involved, acceptance_criteria_ref).

Each analyst returns a JSON fragment. The main planner merges the four fragments into a single `plan.md` — no convergence loop; the main planner is the arbiter.

**Analyst prompt template** (customise `role_description` per analyst):

```
You are a <role_description> for epic P1.E<M> in a lite initiative.

INPUT:
  - epic.md: phases/phase_1/epic_<M>/epic.md
  - phase manifest: phases/phase_1_manifest.md
  - bootstrap report: .eigen-lite/bootstrap-report.json
  - cross-epic interfaces: <excerpt from epic_manifest.json>

Produce a JSON fragment with this structure:
{
  "analyst": "<your role>",
  "components": [{"name": "...", "owner_task_id": "P1.E<M>.T001",
                  "files_owned": [...], "test_files_owned": [...]}],
  "shared_files": [...],
  "interfaces_within_epic": [{"provider_task": "...", "consumer_tasks": [...],
                              "stub_file": "...", "contract": "..."}],
  "execution_waves": [{"wave": 1, "tasks": [...], "type": "work|integration"}],
  "e2e_scenarios": [{"name": "...", "description": "...", "components_involved": [...], "acceptance_criteria_ref": "..."}],
  "risk_flags": [...],
  "acceptance_criteria": [{"feature": "F1", "criteria": [...]}]
}

Output ONLY the JSON, no commentary.
```

### E.3 Synthesise plan.md

Merge the 4 fragments. Resolve conflicts by preference:
- File ownership conflicts → parallelization architect wins.
- E2E scenarios → e2e designer wins.
- Acceptance criteria → strategic architect's list, augmented with skills specialist's test conventions.
- Risk flags → union of all four.

Write `phases/phase_1/epic_<M>/plan.md`:

```markdown
---
epic_id: "P1.E<M>"
created_at: <ISO-8601>
analyst_fragments: {parallelization: ..., strategic: ..., skills: ..., e2e: ...}
---

# Plan — P1.E<M>

## Acceptance Criteria
<merged from strategic architect>

## Parallelization Strategy

### Independent Components
<from parallelization architect: one subsection per component>

### Shared Files Map
<list, with which task modifies what>

### Interfaces Within Epic
<provider_task + consumer_tasks + stub_file + contract>

### Execution Waves
<waves and which tasks go in each>

### E2E Scenarios
<from e2e designer>

## Risk Flags
<union across analysts>

## Skills / Idioms
<from skills specialist — relevant eigen-squared skills to invoke inside worker prompts>
```

### E.4 Generate tasks/*.md (deterministic)

For each component from `parallelization_strategy.components`, write `phases/phase_1/epic_<M>/tasks/task_<NNN>.md`:

```markdown
---
id: "P1.E<M>.T<NNN>"
title: "<component name>"
type: task
state: open
labels: ["work"]
phase: 1
epic_id: "P1.E<M>"
priority: <P1/P2/P3>
wave: <from execution_waves>
model: opus
blocked_by: [<task IDs this depends on>]
blocks: [<tasks that depend on this>]
interface_deps: [<provider_id, interface_name, stub_file, contract>]
files_owned:
  - <list>
test_files_owned:
  - <list>
created_at: <ISO-8601>
updated_at: <ISO-8601>
---

## Context
<from strategic architect — why this task matters, which feature it serves>

## Implementation Details
<algorithmic sketch — no code>

## File Ownership (SWARM)
<files_owned + test_files_owned>

## Interface Dependencies
<which stubs this task consumes; which interfaces this task provides>

## Acceptance Criteria
- [ ] <specific, testable>
- [ ] All existing tests pass
- [ ] Only owned files modified

## Testing Requirements
<from skills specialist — test conventions for this language/framework>

## Risk Flags
<if any from risk synthesis>

## Comments
```

If any component is marked `type: "integration"`, write `task_INT.md` with `wave = <last>`, `files_owned = shared_files`, `blocked_by = [all work tasks]`.

### E.5 Generate swarm-manifest.json (deterministic)

```json
{
  "epic_id": "P1.E<M>",
  "plan_file": "phases/phase_1/epic_<M>/plan.md",
  "created_at": "<ISO-8601>",
  "tasks": [
    {
      "id": "P1.E<M>.T001",
      "summary": "...",
      "phase": 1,
      "model": "opus",
      "blocked_by": [],
      "interface_deps": [],
      "files_owned": [...],
      "test_files_owned": [...]
    },
    ...
  ],
  "shared_files": [...],
  "execution_waves": [
    {"wave": 1, "tasks": ["P1.E<M>.T001"]},
    {"wave": 2, "tasks": ["P1.E<M>.T002", "P1.E<M>.T003"]},
    {"wave": 3, "tasks": ["P1.E<M>.TINT"], "type": "integration"}
  ],
  "e2e_config": {
    "e2e_test_dir": "<from phase_e2e_config.json>",
    "e2e_test_command": "<from phase_e2e_config.json>",
    "e2e_marker": "e2e",
    "e2e_output_format": "junit",
    "e2e_file_pattern": "<lang-appropriate>",
    "e2e_scenarios": [...],
    "max_iterations": 3,
    "fix_budget_per_worker": 2,
    "max_total_fix_spawns": 8
  }
}
```

**Validation gate**: reject the manifest if:
- any `files_owned` path appears in more than one task's `files_owned` (ownership overlap),
- any `files_owned` path appears in `shared_files`,
- Wave 1 has no task with empty `blocked_by`,
- any `blocked_by` references an unknown task ID,
- `execution_waves` has any task assigned to multiple waves.

If validation fails, **do not commit**. Emit a structured error describing the conflict and stop Stage E for this epic. The user can manually edit the analyst fragments in `plan.md` and re-run — the idempotence contract will resume from E.4.

### E.6 Create integration branch and commit

```bash
# On $EIGEN_BRANCH (base branch), sync first
eigen-lite sync --branch "$EIGEN_BRANCH"

# Create the integration branch off the latest base
eigen-lite checkout-branch --epic <M> --create

# Commit all epic artifacts on the integration branch
git add eigen_initiative/phases/phase_1/epic_<M>/
git commit -m "chore(P1.E<M>): plan + tasks + swarm-manifest"
git push origin feat/P1.E<M>

# Return to base branch for the next iteration or exit
git checkout "$EIGEN_BRANCH"
```

The E2E Testing epic goes through the same E.1–E.6 but its `plan.md` has no "Components" beyond infrastructure setup + E2E test suites, and its tasks are typically one setup task + one test-suite task per feature epic's integration surface.

### E.7 Complete this epic iteration

```bash
eigen-lite complete lite_plan --stage "E:<M>" --output-paths '{"epic_<M>_manifest": "eigen_initiative/phases/phase_1/epic_<M>/swarm-manifest.json"}'
```

Loop back to E.1 for the next epic in `epic_manifest.execution_order`. When the loop ends, proceed to Convergence.

---

## Convergence

When every epic in `epic_manifest.execution_order` has its `"E:<M>"` marker in `stages_completed`:

```bash
eigen-lite complete lite_plan --converged --reason "all stages complete: A, B, C, D, E:1..E:<last>"
eigen-lite commit-state --message "lite_plan converged — feature_set <slug>, <N> epics"
```

Print the final report:

```
=== lite_plan Complete ===

Initiative: <slug>
Epics: <list with status>
Integration branches created: feat/P1.E1, ..., feat/P1.E<last>

Next step:
  Run /lite_swarm — the pipeline state already points at the first epic.
  Watchdog will schedule it automatically if configured.
```

---

## Idempotence and Resume

| Scenario | Behaviour |
|----------|-----------|
| Crash after Stage A | Re-run lite_plan → A skipped (marker + file), resume at B. |
| Stage C writes partial `bootstrap-report.json` then crashes | Re-run: marker C absent, file present but incomplete → delete the file before re-running, OR run again (C detects it wrote partial JSON via a `complete` flag inside the file; if missing, re-run from scratch for C). |
| Stage D completes but `epic_1/epic.md` deleted by the user | Marker `D` present, file missing. lite_plan detects the mismatch, removes D from `stages_completed` by calling `eigen-lite complete lite_plan --stage D` is NOT destructive — instead, delete the stage marker manually: the user must run `eigen-lite mark-converged lite_plan --reason "..."` is wrong here; the simplest recovery is to delete `epic_manifest.json` and re-run — D will regenerate everything. |
| Stage E crashes after committing epic_2 but before epic_3 | `E:1` and `E:2` markers present, `E:3` absent. Resume from E.1 for epic 3. The integration branches for E1/E2 remain untouched. |
| User adds a 4th feature after Stage A | Re-run requires re-doing all of A onward. Not supported: lite_plan is single-pass. Abort and ask the user to use eigen-squared, OR accept that the user deletes `eigen_initiative/` and `.eigen-lite/bootstrap-report.json` and starts over. |

---

## Error Handling

- **Missing `$EIGEN_ROOT` or `$EIGEN_BRANCH`** → STOP.
- **Monorepo detected** → STOP, ask the user to pick a subtree.
- **>5 features** → STOP, suggest eigen-squared.
- **Dependency cycle among features** → STOP, ask the user to linearise.
- **language-profiles skill unavailable** → warn, fall back to generic profile, continue.
- **Analyst subagent returns invalid JSON** → retry once with a stricter prompt; if still invalid, proceed with the 3 remaining analysts and record the gap in the final `plan.md` Caveats.
- **swarm-manifest validation fails** → do NOT commit; print the conflict; stop for that epic.
- **`--no-scaffold` with delta > 0** → write report with `failed_with_warnings`, stop before Stage D.

---

## Important Rules

- **Single pass, no convergence loops**: lite_plan never iterates over its own stages. If a stage's output is wrong, the user fixes it manually and re-runs — the idempotence contract resumes correctly.
- **Subagents are read-only**: Stage D and Stage E analysts never write files. Only the main lite_plan agent writes to disk.
- **Integration branches are created after the manifest lands on disk**: never branch before the manifest is valid.
- **Cross-plugin skills**: always via `Skill("eigen-squared:<name>")`. lite does NOT vendor eigen-squared skills.
- **Hard cap on features**: 6+ features → use eigen-squared. This is enforced, not a suggestion.
- **E2E epic is always last**: when present, `is_e2e_epic: true` and `features: []`.
- **Shared files are disjoint from files_owned**: enforced in E.5 validation.
