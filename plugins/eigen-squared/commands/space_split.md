---
name: space_split
description: Decompose a phase manifest into sequentially ordered epics, each ready for orchestrate_swarm. Creates epic definition files for each epic in the phases directory.
---

# Epic Architect — Space Split

## Pipeline Context

```
  time_split ↔ deepen → bootstrap ↔ deepen → [ space_split ↔ deepen_space_split ] → plan_epic_converge → ...
                                                ^^^^^^^^^^^^^
                                                YOU ARE HERE
```

**Role — Epic Architect.** You operate at **per-phase scope**. You decompose a single phase (produced by `/time_split`) into sequentially ordered epics that can each be planned and executed by their own swarm. Epics are numbered E1, E2, ..., EN with E2E Testing always last. Each epic completes fully before the next one starts. You build the epic ordering, define what each epic outputs for downstream epics, and create one epic definition file per epic with sufficient context for downstream `/plan_epic_converge`.

**Convergence partner:** `/deepen_space_split` reviews your output and produces structured feedback. You iterate space_split <-> deepen_space_split until converged.

**Language note:** These instructions are **language-agnostic** at the splitting level — they operate on phase manifests and produce epic definitions, an epic manifest, and epic definition files. Downstream commands (`/plan_epic_converge`, `/create_issues_from_plan_swarm`, `/orchestrate_swarm`) handle language-specific planning and execution.

You do NOT generate plans or swarm manifests — that is the job of `/plan_epic_converge` and `/create_issues_from_plan_swarm` respectively. Your output is the epic decomposition, the manifest, and the epic definition files.

---

## Environment

Before proceeding, verify:

- [ ] `$EIGEN_ROOT` is set and points to an existing directory
- [ ] `$EIGEN_BRANCH` is set (the default branch from which all work starts)

If either is missing, **STOP** and print the appropriate error:

```
ERROR: $EIGEN_ROOT is not set.
Set it to the root folder of your target project:
  export EIGEN_ROOT=/path/to/your/project
```

```
ERROR: $EIGEN_BRANCH is not set.
Set it to the default branch from which all work starts:
  export EIGEN_BRANCH=main
```

**Key paths** (all relative to `$EIGEN_ROOT/eigen_initiative/`):

| Path | Description |
|------|-------------|
| `phases/phase_N_manifest.md` | Phase manifest (input) |
| `phases/phase_N/` | Phase output directory |
| `phases/phase_N/bootstrap-report.json` | Bootstrap report (input) |
| `phases/phase_N/epic_M/epic.md` | Epic definition file (output) |
| `phases/phase_N/epic_manifest.json` | Epic manifest (output) |
| `phases/phase_N/phase_e2e_config.json` | Phase E2E config (output) |
| `phases/phase_N/feedback/` | Feedback directory (owned by deepen — never touch) |

## Output

All outputs are written to `$EIGEN_ROOT/eigen_initiative/phases/phase_N/`:

- `phase_N/epic_M/epic.md` — one epic definition file per epic (scope, features, specs, validation criteria)
- `phase_N/epic_manifest.json` — epic manifest with execution order, cross-phase inputs, inter-epic interfaces
- `phase_N/phase_e2e_config.json` — phase-level E2E test scenarios and per-epic validation scenarios

## Overview

You will:
1. Ingest the phase manifest and bootstrap report
2. Build a local dependency DAG and form epics from clusters + domain groupings
3. Order epics sequentially so dependencies point forward; define what each epic outputs for later epics
4. Create epic definition files (one `epic.md` per epic) defining the scope — which features belong, their specs, interfaces, and validation criteria. These are NOT plans; `/plan_epic_converge` generates the implementation strategy later.
5. Generate phase-level artifacts (epic manifest, phase E2E config)

---

## ID Convention

All IDs in the eigen-squared pipeline use a deterministic triplet derived from directory structure — no counter files needed:

- **Epic ID**: `P<N>.E<M>` — e.g., `P1.E2` (Phase 1, Epic 2)
- **Task ID** (downstream): `P<N>.E<M>.T<K>` — e.g., `P1.E2.T3` (Phase 1, Epic 2, Task 3)
- **Review finding ID** (downstream): `P<N>.E<M>.R<K>` — e.g., `P1.E2.R1`

Epic numbers (M) are sequential within the phase, starting at 1. The last epic is always the E2E Testing epic.

---

## Constraints

- You are a **single agent** orchestrating sub-agents only for heavy research. Epic formation and epic file creation are done by you directly.
- **Cluster integrity**: strongly prefer keeping all features in a cluster within the same epic. Only split a cluster across sequential epics if there is a compelling reason.
- **Epic sizing**: each epic should be a meaningful unit of work — not so small that planning overhead dominates, not so large that a single swarm can't handle it. The right size depends on the phase's feature count and complexity.
- Every epic must have clear **validation criteria** — what can be verified after the epic's swarm completes. This is not a full E2E test (that happens at phase level), but a description of what components work and what tests pass.
- Cross-phase dependencies are treated as **already available** — they are inputs from completed prior phases.
- **Bootstrap must be converged** before running this command. The bootstrap report provides concrete entity paths and project structure.
- You NEVER write application code, plans, or swarm manifests. You produce epic decompositions (scope and feature assignments), the epic manifest, epic definition files, and phase-level E2E configs only. The epic.md files define *what* belongs to each epic; `/plan_epic_converge` later defines *how* to implement it.
- **Feedback files are owned by deepen commands.** You NEVER delete, overwrite, or recreate files under `$EIGEN_ROOT/eigen_initiative/phases/phase_N/feedback/`. On iteration, you only update your own outputs (epic_manifest.json, phase_e2e_config.json, epic files).

---

## On Entry

Run the CLI to get pipeline context:

```bash
eigen-squared get-context space_split --json
```

If the CLI exits with an error (non-zero), **STOP** and display the error message. Otherwise parse the returned JSON:

```json
{
  "command": "space_split",
  "branch": "main",
  "paths_relative_to": "$EIGEN_ROOT/eigen_initiative/",
  "phase": 1,
  "iteration": 2,
  "current_iteration": 1,
  "is_first_run": false,
  "should_process_feedback": true,
  "feedback_path": "phases/phase_1/feedback/deepen_space_split_feedback.json",
  "output_paths": {"epic_dag": "phases/phase_1/epic_manifest.json", "phase_e2e_config": "phases/phase_1/phase_e2e_config.json"},
  "phase_manifest": "phases/phase_1_manifest.md",
  "recommendations": [...]
}
```

| Field | Type | Description |
|-------|------|-------------|
| `command` | string | Always `"space_split"` |
| `branch` | string | The branch to work on (from `$EIGEN_BRANCH`) |
| `paths_relative_to` | string | Base path — all relative paths in this context are relative to this |
| `phase` | int | Which phase to split |
| `iteration` | int | The iteration you are about to produce (1 = first run, 2+ = iteration) |
| `current_iteration` | int | The iteration whose outputs currently exist on disk (0 = none yet) |
| `is_first_run` | bool | `true` when no prior run exists |
| `should_process_feedback` | bool | `true` when unprocessed deepen feedback is waiting |
| `feedback_path` | string | Relative path to the feedback JSON (only when `should_process_feedback` is true) |
| `output_paths` | object | Paths to current outputs (null fields on first run) |
| `phase_manifest` | string | Relative path to the phase manifest |
| `recommendations` | array | Downstream recommendations from deepen commands to incorporate |

**Routing:**

- `is_first_run == true` → proceed to **Stage 0**
- `should_process_feedback == true` → proceed to **Iteration Protocol**

---

## On Exit

After successfully generating outputs (Stage 4), signal completion to the CLI:

```bash
eigen-squared complete space_split --phase <phase> --epic-manifest phases/phase_<phase>/epic_manifest.json --e2e-config phases/phase_<phase>/phase_e2e_config.json --epic-ids '["P<phase>.E1", "P<phase>.E2", "P<phase>.E3"]'
```

The CLI handles all field updates atomically: status, iteration, timestamps, feedback_consumed flags (both own and deepen counterpart), output paths.

Then commit pipeline artifacts:

```bash
eigen-squared commit-state --message "pipeline: space_split phase <phase> — <epic_count> epics created" --additional-paths eigen_initiative/phases/phase_<phase>/
eigen-squared schedule-next
```

---

## Iteration Protocol

This section applies when the CLI context returns `should_process_feedback: true`.

### Read Feedback

1. Read the feedback file at `feedback_path` (resolved against `paths_relative_to` from CLI context).
2. Extract: `findings[]`, `convergence`, `previous_feedback_comparison`, and `epic_updates`.
3. Validate that `analyzed_iteration` matches `current_iteration` from the CLI context.

### Honest Self-Assessment

For each finding in `findings[]`, print an assessment to the user:

```
=== Iteration <iteration>: Addressing Deepen Feedback ===

Finding <id>: <title> [<severity>]
  Category: <category>
  Description: <description>
  Recommendation: <recommendation>
  Assessment: ACCEPT | PARTIAL | REJECT
  Rationale: <why you accept/partially accept/reject this finding>
```

Use the `iteration` field from CLI context for the display header.

Classification rules:
- **ACCEPT**: the finding is valid and actionable — the recommendation will be incorporated as a constraint in regeneration.
- **PARTIAL**: the finding is valid but the recommendation is too broad or conflicts with another constraint — a narrower fix will be applied.
- **REJECT**: the finding is a false positive, contradicts a Critical Constraint, or would cause a worse outcome — explain why.

### Epic File Handling on Iteration

**Critical**: do NOT create duplicate epic files. Instead:

1. Read `epic_updates` from the feedback file:
   - `epics_to_update`: for each entry, overwrite the corresponding `$EIGEN_ROOT/eigen_initiative/phases/phase_N/epic_M/epic.md` with the updated body content. Update the `updated_at` field in the YAML frontmatter.
   - `epics_to_close_and_replace`: for each entry, update the old epic's `state` to `closed` in its frontmatter and create a new replacement epic file with the next sequential epic number.
2. For epics that are **unchanged** (no findings affect them): leave their epic files untouched.

### Apply Accepted Changes

When applying feedback, ensure **cascading updates** and **cross-source consistency** between `epic.md` files and `epic_manifest.json`:

- **Cascading updates are MANDATORY**: when applying a change, apply ALL structural consequences:
  - `move_feature_to_epic` → remove feature from source epic.md (frontmatter + body) AND add to destination epic.md. Update `epic_manifest.json` execution order if needed. Check if moved feature was an interface provider — if so, update `interfaces_provided[]` in the manifest AND the "Epic Outputs" section in the provider epic.md file. Update `phase_e2e_config.json` epic entries.
  - `add_interface` / `modify_interface` → edit the "Epic Outputs" narrative section in the provider epic.md file AND the `interfaces_provided[]` entry in `epic_manifest.json` including `concrete_files[]` (paths must exist in bootstrap-report.json).
  - `split_epic` / `merge_epics` → regenerate all affected epic.md files AND rebuild `epic_manifest.json` entries AND update `phase_e2e_config.json`.
- **Cross-source consistency rule**: after EVERY change, verify that every interface that appears in an epic.md "Epic Outputs" section has its corresponding entry in `epic_manifest.json` `interfaces_provided[]`, and vice versa. Fix any discrepancy immediately.
- **Edit the STRUCTURAL sections directly** (epic_manifest.json entries, epic.md YAML frontmatter, "Epic Outputs" sections, phase_e2e_config.json). Do NOT address structural findings by adding narrative paragraphs to the epic body — deepen validates the structural sections and JSON, not narrative commentary.

### Regeneration Scope

Determine how much of the pipeline to re-run based on finding categories:

- **`epic_formation_error` | `feature_coverage_error`** → re-run from **Stage 1** (rebuild ordering, reform epics, recreate/update all epic files).
- **`interface_error` | `issue_completeness_error` | `spec_fidelity_error`** → re-run from **Stage 2** only (update epic file bodies, fix interface definitions).
- **`e2e_coverage_gap`** → re-run from **Stage 3** only (regenerate E2E config, update phase artifacts).

If findings span multiple categories, use the broadest scope needed.

### Re-validate After Changes

After applying all accepted changes and regeneration, verify structural consistency before writing outputs:
- Every feature from the phase manifest appears in exactly ONE epic's frontmatter `features[]` (no duplicates, no missing)
- Every interface in any epic.md "Epic Outputs" section has a corresponding entry in `epic_manifest.json` `interfaces_provided[]` (and vice versa)
- Every `concrete_files[]` in the manifest references files that exist in bootstrap-report.json entity/contract paths
- `phase_e2e_config.json` has an entry for every epic in the manifest
- YAML frontmatter `feature_count` in each epic.md matches the actual `features[]` array length

If any check fails, fix it NOW before writing the outputs. Do not defer cross-source inconsistencies to the next deepen iteration.

### Post-Regeneration

1. Update `epic_manifest.json` with new iteration number.
2. **NEVER delete, overwrite, or recreate `$EIGEN_ROOT/eigen_initiative/phases/phase_N/feedback/` or any file inside it.** The feedback file (`deepen_space_split_feedback.json`) is owned by `deepen_space_split` and must stay untouched for comparison on the next deepen run.

### Read Recommendations (if present)

Recommendations come from the `recommendations` field in the CLI context. Use as advisory context during epic formation:

- Inform epic boundary decisions, interface definitions, and ordering.
- Do NOT treat as requirements. If your analysis contradicts a recommendation, follow your analysis.
- On iteration: the CLI always provides current recommendations (deepen commands may have updated them since last run).

---

## Stage 0: Ingest

### 0.1 Read Phase Manifest

1. Read `$EIGEN_ROOT/eigen_initiative/phases/phase_N_manifest.md` (where N is the phase from CLI context).
2. Parse the YAML frontmatter to extract: `phase`, `initiative`, `feature_count`, `clusters_included`, `priority_distribution`, `e2e_summary`, `depends_on_phases`.

### 0.2 Parse Phase Body

1. Parse the markdown body to extract:
   - **Features by Domain**: all feature tables — build a map of feature id → {name, priority, local_deps, cross_phase_deps, cluster, domain}
   - **Cross-Phase Dependencies**: table of features depending on prior phases
   - **Natural Clusters**: table of cluster → features mapping
   - **Blackbox Feature Specifications**: per-feature specs (feature_id → full spec text)
   - **Whitebox Reference Sections**: filtered whitebox content (may be absent if no whitebox file was provided)
2. Validate that the feature count matches the frontmatter's `feature_count`. Warn if mismatched.

### 0.3 Read Bootstrap Report

1. Read `$EIGEN_ROOT/eigen_initiative/phases/phase_N/bootstrap-report.json`.
2. If the file does not exist → **STOP.** Print:
   ```
   ERROR: No bootstrap-report.json found at $EIGEN_ROOT/eigen_initiative/phases/phase_N/
   Bootstrap must be converged before running space_split.
   Run /bootstrap and /deepen_bootstrap until converged first.
   ```
3. Extract:
   - `language` — detected project language and frameworks
   - `tooling_decisions` — package manager, framework, test runner, linter, etc.
   - `entities_created` — list of `{file, models[]}` with exact file paths and entity class names
   - `delta_applied` — what was created (directories, entity stubs, schemas, clients, etc.)
   - `verification` — whether the foundation compiles/passes
   - `iteration` — which bootstrap iteration (for review-driven improvements)
4. From `entities_created`, build a map of entity class name → file path. This is used to give epics concrete file paths instead of inferred paths.
5. From `delta_applied`, note directories created by bootstrap, so epic scope references real paths.

---

## Stage 1: Build Local DAG & Form Epics

### 1.1 Build Local Dependency DAG

1. For each feature in the feature map, build edges from `local_deps` (dependencies within this phase).
2. Cross-phase dependencies are **not edges** in this local DAG — they are marked as "already available" inputs.
3. Compute:
   - Local roots (features with no local upstream dependencies)
   - Local leaves (features with no local downstream dependents)
   - Local critical paths
4. This is the local dependency DAG for this phase.

### 1.2 Form Epic Candidates

Build epic groupings using this priority order:

1. **Clusters as starting points**: each cluster from the phase becomes one epic candidate. Strongly prefer keeping clusters intact — only split across sequential epics if there is a compelling reason.
2. **Unclustered features by domain + dependency chains**: group remaining features that:
   - Share the same domain AND have direct dependencies between them
   - OR form a dependency chain (A → B → C all in same domain)
3. **Merge small groups**: if an epic candidate is too small to justify its own swarm, merge with the most closely related epic (shared domain, shared dependencies).
4. **Split large groups**: if an epic candidate is too large for a single swarm to handle effectively, split by sub-domain or dependency depth.

Each epic candidate has: `{epic_id, name, features[], clusters[], domain}`.

### 1.3 Order Epics Sequentially

Order epics so that dependencies point forward in the sequence:

1. For each pair of epics (E_a, E_b): if any feature in E_b depends on a feature in E_a, then E_a must come before E_b.
2. Number epics E1, E2, ..., EN such that all dependency edges point from lower-numbered to higher-numbered epics.
3. The E2E Testing epic is always last (see Stage 2.1).

These are the epic execution order.

### 1.4 Define Epic Outputs

For each epic, define what it produces that later epics will use.

#### Interface Classification

Before defining epic outputs, classify each cross-epic dependency:

1. **Shared Infrastructure** (types, utils, constants, entity stubs) — any epic can import these directly from bootstrap-created files. These are NOT epic outputs. Do not add them to `interfaces_provided`. They may appear as supporting context but do not create ordering dependencies.
2. **API Contracts** (service functions, middleware, client modules, route handlers) — requires the provider epic to implement before later epics can integrate. These ARE epic outputs and inform the sequential ordering.

Only define outputs (steps below) for API Contract dependencies. Shared Infrastructure imports do not need coordination between epics.

For each cross-epic dependency (feature in a later epic depends on a feature in an earlier epic):

1. Identify the **output** — what does the later epic need from the earlier one?
2. Look up the entity stubs and file paths in the entity file map (from the bootstrap report) to define concrete contracts (e.g., "User model at `libs/janus_core/janus_core/models/auth.py`" instead of "user entity").
3. Define:
   - `interface_name`: descriptive name (e.g., "RBAC Role + Rights Resolution")
   - `provider_epic`: the earlier epic's ID (e.g., `P1.E1`)
   - `provider_features`: features in the earlier epic that produce this output
   - `contract`: brief description of the data/API contract
   - `concrete_files`: list of file paths from the entity file map that define this interface

These are the epic outputs (documented as `interfaces_provided` per epic).

### 1.5 Present Epic Split to User

Build a summary table and present:

```
Phase <N>: <feature_count> features → <epic_count> epics

| # | ID | Name | Features | Clusters |
|---|------|------|----------|----------|
| 1 | P<N>.E1 | ...  | N        | ...      |
| 2 | P<N>.E2 | ...  | N        | ...      |
```

Order by epic number. Proceed to Stage 2.

---

## Stage 2: Create Epic Files

### 2.1 Add the E2E Testing Epic

Before creating files, add a mandatory **E2E Testing** epic as the last epic in the sequence:

- This epic has no features from the phase manifest — its scope is to define and implement the full E2E test suite for the phase
- It is always the last epic in the execution order
- Its epic number M is the last sequential number (e.g., if there are 3 feature epics, the E2E epic is epic 4)
- Its ID follows the triplet convention: `P<N>.E<M>`

### 2.2 Create One Epic File Per Epic

For each epic (including the E2E Testing epic), ordered by epic number M:

1. Derive the epic ID: `P<N>.E<M>` (e.g., `P1.E1`, `P1.E2`)
2. Create the epic directory: `mkdir -p $EIGEN_ROOT/eigen_initiative/phases/phase_N/epic_M/`
3. Write `$EIGEN_ROOT/eigen_initiative/phases/phase_N/epic_M/epic.md` with the following format:

```markdown
---
id: "P<N>.E<M>"
title: "[Phase <N>] Epic <M>: <epic_name>"
type: epic
state: open
labels: ["Phase <N>"]
phase: <N>
epic_number: <M>
features: [<feature IDs>]
feature_count: <count>
clusters_included: [<cluster IDs>]
task_ids: []
created_at: "<ISO 8601>"
updated_at: "<ISO 8601>"
---

## Epic: <epic_name>

**ID:** P<N>.E<M>
**Phase:** <N> — <phase_e2e_summary>
**Features:** <feature_count> (<feature IDs joined by comma>)
**Clusters:** <cluster IDs or "none">

---

### Features

| ID | Name | Priority | Dependencies (local) | Dependencies (cross-phase) |
|----|------|----------|---------------------|---------------------------|
<for each feature in this epic, one row>

### Validation Criteria

<What can be verified after this epic's swarm completes. Describe which components work, which tests pass, and what integration points are functional. This is NOT a full E2E test — phase-level E2E testing is handled by the E2E Testing epic.>

### Epic Outputs

**This epic provides to downstream epics:**
<for each interface_provided>
- **<interface_name>** → used by P<N>.E<M>: <contract description>
  - Files: <concrete_files from entity file map>
</for each>
<or "None — this is a leaf epic.">

### Blackbox Feature Specifications

<For each feature in this epic, include the FULL verbatim blackbox spec (Inputs, Outputs, Behavior, Acceptance Criteria) from the phase manifest. This is critical — plan_epic_converge needs complete specs to generate a useful plan.>

#### <feature_id>: <feature_name>

<full verbatim spec>

...

### Whitebox Implementation Guidance (optional)

<If the phase manifest contains whitebox sections, extract those relevant to THIS epic's domains. Include only sections that apply to the features in this epic. If no whitebox reference was provided, omit this section entirely.>

### Bootstrap Context

**Language:** <language>
**Tooling:** <package_manager>, <framework>, <test_runner>, <linter>
**Entity stubs relevant to this epic:**
<for each entity in entity file map that is referenced by this epic's features>
- `<EntityName>` → `<file_path>`
</for each>

**Repository structure:** <relevant directory paths from bootstrap>

## Comments
```

**For the E2E Testing epic**, the format is the same but with these differences:
- `features: []` (no features from the manifest)
- The **Features** table is empty
- The **Validation Criteria** section describes the full phase-level E2E tests: data flows end-to-end, all epics integrated, user-facing flows testable
- The **Blackbox Feature Specifications** section references the acceptance criteria from ALL epics in this phase (summarized, not verbatim)
- Add an **Infrastructure Requirements** section listing what the E2E tests need to run, derived from the `test_type` classifications:
  - `api` → running application server, any backend services (databases, caches, queues) via Docker containers
  - `browser` → running frontend dev server + browser automation (Playwright)
  - `mobile` → emulator/simulator + mobile build toolchain (Detox, Maestro, XCUITest, Espresso)
  - `pipeline` → data source + data sink infrastructure (S3/MinIO, message broker, target database)
  - `full_stack` → combination of the above

  **If bootstrap created Docker artifacts** (check `bootstrap-report.json` → `delta_applied.dockerfile_created`): bootstrap provides a minimal Dockerfile and docker-compose.yml (health check only). Feature epics may extend them as they add functionality (system deps, new services). The E2E Testing epic **completes and finalizes** the Docker setup for testing: ensures the full stack works end-to-end, adds test-specific configuration (seed data, environment variables, additional services if needed), and writes tests against it.

  When populating `infrastructure_requirements` in `phase_e2e_config.json`:
  - Set `test_environment` to `"container_parity"`
  - Set `services` from `bootstrap-report.json` → `delta_applied.docker_compose_services`
  - Set `health_check` to `http://localhost:<port><path>` using `delta_applied.exposed_port` and `delta_applied.health_check_path` from the bootstrap report
  - Set `startup_command` to `docker compose up -d --wait`
  - Set `teardown_command` to `docker compose down -v`

  **If bootstrap did NOT create Docker artifacts**: set `test_environment` to `"external_services"`. The E2E Testing epic sets up its own infrastructure. Leave `compose_file`, `startup_command`, `health_check`, and `teardown_command` empty.

  This section informs `/plan_epic_converge` when it plans the E2E Testing epic — it will know what infrastructure to use.

### 2.3 Update Epic Cross-References

After ALL epic files are created:

1. For epics that provide interfaces to downstream epics, append to the `## Comments` section of the provider epic's file:

```markdown
Provides interfaces to P<N>.E<M>: <consumer_epic_name>.
```

### 2.4 Update Initiative Index

After all epics are created, regenerate `$EIGEN_ROOT/eigen_initiative/_index.md` with a summary of all phases/epics:

```markdown
# Initiative Index

## Phase <N>: <e2e_summary>

| Epic | ID | Name | Features | State |
|------|----|------|----------|-------|
| 1    | P<N>.E1 | <epic_name> | <feature_count> | open |
| 2    | P<N>.E2 | <epic_name> | <feature_count> | open |
| 3    | P<N>.E3 | E2E Testing | 0 | open |
...
```

If `_index.md` already exists with content from other phases, merge the new phase data into the existing index (do not overwrite other phases).

---

## Stage 3: Generate Phase-Level Artifacts

### 3.1 Generate Epic Manifest

Ensure feedback directory exists: `mkdir -p $EIGEN_ROOT/eigen_initiative/phases/phase_N/feedback/`

Write `$EIGEN_ROOT/eigen_initiative/phases/phase_N/epic_manifest.json`:

```json
{
  "phase": <N>,
  "iteration": 1,
  "initiative": "<initiative name>",
  "epic_count": <count>,
  "execution_order": ["P<N>.E1", "P<N>.E2", "P<N>.E3", "P<N>.E<last>"],
  "cross_phase_inputs": [
    {
      "feature_id": "<ID>",
      "from_phase": <N-1>,
      "description": "<what it provides>"
    }
  ],
  "epics": [
    {
      "id": "P<N>.E1",
      "epic_number": 1,
      "local_path": "phases/phase_<N>/epic_1/",
      "name": "<epic name>",
      "description": "<brief description>",
      "features": ["<feature IDs>"],
      "clusters_included": ["<cluster IDs>"],
      "interfaces_provided": [
        {
          "interface_name": "<name>",
          "consumer_epics": ["P<N>.E2"],
          "contract": "<brief contract description>",
          "concrete_files": ["<file paths>"]
        }
      ],
      "validation_summary": "<what can be verified after this epic completes>"
    },
    {
      "id": "P<N>.E<last>",
      "epic_number": <last>,
      "local_path": "phases/phase_<N>/epic_<last>/",
      "name": "E2E Testing",
      "description": "Full phase-level E2E test suite",
      "features": [],
      "clusters_included": [],
      "interfaces_provided": [],
      "validation_summary": "Phase-level E2E tests pass: full data flow from input to output"
    }
  ],
  "phase_e2e_test": "<phase-level E2E test description>",
  "created_at": "<ISO 8601 timestamp>"
}
```

### 3.2 Generate Phase E2E Config

Write `$EIGEN_ROOT/eigen_initiative/phases/phase_N/phase_e2e_config.json`:

```json
{
  "phase": <N>,
  "phase_e2e_test": "<description of end-to-end test for the whole phase>",
  "epic_validation_scenarios": [
    {
      "epic_id": "P<N>.E1",
      "scenarios": [
        {
          "name": "<scenario name>",
          "description": "<what to verify after this epic's swarm completes>",
          "test_type": "<api|browser|pipeline|full_stack>",
          "features_involved": ["<feature IDs>"],
          "acceptance_criteria": ["<from blackbox specs>"]
        }
      ]
    }
  ],
  "phase_e2e_scenarios": [
    {
      "name": "phase_<N>_full_flow",
      "description": "<full phase E2E test combining all epics — implemented by the E2E Testing epic>",
      "test_type": "<api|browser|mobile|pipeline|full_stack>",
      "epics_involved": ["P<N>.E1", "P<N>.E2"],
      "acceptance_criteria": ["<phase-level criteria>"]
    }
  ],
  "infrastructure_requirements": {
    "test_types_detected": ["api", "browser"],
    "test_environment": "<container_parity|external_services>",
    "needs_docker": true,
    "needs_emulator": false,
    "needs_browser_automation": true,
    "compose_file": "docker-compose.yml",
    "startup_command": "docker compose up -d --wait",
    "health_check": "http://localhost:<port><path>",
    "teardown_command": "docker compose down -v",
    "services": ["<from bootstrap-report.docker_compose_services>"],
    "notes": "<any additional infrastructure context derived from the features>"
  }
}
```

### 3.3 Classify test_type per Scenario

For each scenario (both epic validation and phase E2E), determine `test_type` based on the features involved:

- **`api`**: Features are backend-only (REST endpoints, GraphQL, gRPC). No UI involved.
  Test with HTTP requests to the running application.

- **`browser`**: Features include user-facing web frontend (web pages, forms, dashboards).
  Test with Playwright or agent-browser against the running frontend.

- **`mobile`**: Features target a mobile application (iOS/Android screens, navigation, gestures).
  Test with platform-appropriate tools (Detox, Maestro, XCUITest, Espresso) against an emulator or device.

- **`pipeline`**: Features involve async data processing (S3 ingestion, queue consumers,
  ETL pipelines, background workers). Test by injecting input data and polling/waiting
  for output in the target store.

- **`full_stack`**: Features span multiple layers (frontend + backend + pipeline, or mobile + API).
  Test the complete flow across layers. Combines API calls, data injection,
  and UI assertions (browser or mobile).

**Heuristics for classification:**
- If any feature's domain includes "app", "screen", "navigation", "gesture", "mobile", "iOS", "Android" → `mobile` or `full_stack`
- If any feature's domain includes "frontend", "UI", "dashboard", "page", "view" (web) → `browser` or `full_stack`
- If any feature's domain includes "pipeline", "ingestion", "ETL", "worker", "consumer", "processor" → `pipeline` or `full_stack`
- If features span 3+ domains including multiple layers → `full_stack`
- Default: `api`

---

## Stage 4: Print Summary

After generating all files and creating epic files, print:

```
=== Phase <N> Space Split Complete ===

Phase: <N> — <e2e_summary>
Total features: <count>
Epics: <count> (including E2E Testing epic)
Execution order: P<N>.E1 → P<N>.E2 → ... → P<N>.E<last> (E2E Testing)
EIGEN_ROOT: $EIGEN_ROOT

Epics Created (Phase <N>):
  P<N>.E1: <name> (<feature_count> features)
  P<N>.E2: <name> (<feature_count> features)
  P<N>.E<last>: E2E Testing (0 features)

Epic Outputs (interfaces):
  P<N>.E1 → P<N>.E2: <interface_name> (<contract>)
  ...

Files generated:
  $EIGEN_ROOT/eigen_initiative/phases/phase_N/epic_manifest.json
  $EIGEN_ROOT/eigen_initiative/phases/phase_N/phase_e2e_config.json
  $EIGEN_ROOT/eigen_initiative/phases/phase_N/epic_1/epic.md
  $EIGEN_ROOT/eigen_initiative/phases/phase_N/epic_2/epic.md
  $EIGEN_ROOT/eigen_initiative/phases/phase_N/epic_3/epic.md  (E2E Testing)
  ...

Next steps:
  1. (Recommended) Run /deepen_space_split
     to review the epic decomposition and epic file quality.
     Iterate space_split ↔ deepen_space_split until converged.
     Hint: to adjust the split (change epic boundaries, move features),
     pass your instructions to the next /space_split iteration.
  2. Once converged, run /plan_epic_converge for each epic (auto-detected).
  3. Then /create_issues_from_plan_swarm → /orchestrate_swarm → /review_swarm_pr
```

Then run the **On Exit** CLI commands.

---

## Pipeline Continuation

The `eigen-squared schedule-next` call at the end of the On Exit section reads the updated pipeline state, determines the next command, and schedules it via the claude-tasks API. No hook or external trigger is needed — the command schedules its own successor before the session ends.
