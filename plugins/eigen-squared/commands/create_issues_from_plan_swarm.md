---
name: create_issues_from_plan_swarm
description: Decompose a development plan into file-disjoint task files and generate a swarm-manifest.json
---

# Swarm Task Generation — Plan to Tasks + Manifest

## Language Adaptation

These instructions are **language-aware** — task specifications reference file paths, import conventions, and test patterns that depend on the project's languages. Load the `language-profiles` skill for detection, toolchain commands, and adaptation notes.

The following aspects must be resolved from the language profile for the detected languages:
- **File extensions** in `files_owned` and `test_files_owned` — use the project's actual extensions
- **Import rules** in Interface Dependencies — how consumers import from stubs varies by language (see "Import / Dependency Rules" in the `language-profiles` skill)
- **Package index files** in `shared_files` — some languages have barrel/index files that become shared files, others don't (see "Package Index / Shared Files" in the skill)
- **Test file patterns and directories** — where tests live and how they're named
- **File ownership model** — some languages use file-level ownership, others use package/module-level (see "File Ownership Model" in the skill)

---

## Your Role

You are a senior technical architect responsible for decomposing a comprehensive development plan into discrete, implementable tasks **optimized for parallel execution by a swarm of autonomous agents**. You produce task files and a machine-readable `swarm-manifest.json` that the orchestrator will use to coordinate the swarm.

## Objective

Generate tasks that:
1. **Are independently implementable** — each task is atomic, containing code development and its tests
2. **Follow the plan's structure** — respect the Parallelization Strategy's components, waves, and dependencies
3. **Are appropriately scoped** — not too granular (avoid "add one line") nor too broad (avoid "implement entire epic")
4. **Include sufficient context** — sub-agents should understand WHY and HOW, not just WHAT
5. **Have clear success criteria** — verifiable acceptance criteria and validation steps
6. **Declare file ownership** — each task explicitly lists which files it creates/modifies
7. **Have no file ownership overlaps** — no two tasks can own the same file; shared files go to the integration task

## Environment Variables

This command uses the same environment variables as all eigen-squared commands:

- **`EIGEN_ROOT`** — absolute path to the root folder of the target project
- **`EIGEN_BRANCH`** — the default branch from which all work starts

### On Entry: Validate Environment

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
3. Verify `$EIGEN_ROOT` exists and is a directory.

## Pipeline Awareness

The `eigen-squared` CLI manages all pipeline state. You do NOT read or write `pipeline_state.json` directly.

### On Entry

```bash
eigen-squared get-context create_issues_from_plan_swarm --json
```

If the CLI exits with an error (non-zero), STOP and display the error message. Otherwise parse the returned JSON for `phase`, `epic`, `branch`, `manifest_path`, and `recommendations`.

### On Exit

After creating tasks, manifest, and integration branch:

```bash
eigen-squared complete create_issues_from_plan_swarm --phase <N> --epic <M> --manifest-path <manifest_path> --integration-branch feat/P<N>.E<M>
```

To create the integration branch:
```bash
eigen-squared checkout-branch --phase <N> --epic <M> --create
```

The CLI handles all state updates atomically.

### Fixed Paths

- **Plan file**: `$EIGEN_ROOT/eigen_initiative/phases/phase_N/epic_M/plan.md`
- **Epic file**: `$EIGEN_ROOT/eigen_initiative/phases/phase_N/epic_M/epic.md`
- **Task directory**: `$EIGEN_ROOT/eigen_initiative/phases/phase_N/epic_M/tasks/`
- **Manifest file**: `$EIGEN_ROOT/eigen_initiative/phases/phase_N/epic_M/swarm-manifest.json`
- **Phase E2E config**: `$EIGEN_ROOT/eigen_initiative/phases/phase_N/phase_e2e_config.json`
- **Bootstrap report**: `$EIGEN_ROOT/eigen_initiative/phases/phase_N/bootstrap-report.json`
- **Pipeline state**: `$EIGEN_ROOT/eigen_initiative/phases/pipeline_state.json`
- **Initiative index**: `$EIGEN_ROOT/eigen_initiative/_index.md`

## Input

No arguments are required. The phase and epic are auto-detected from the pipeline state.

The plan file must exist and contain the strategic plan with a Parallelization Strategy section produced by `/plan_phase_epic`.

## Output

- `$EIGEN_ROOT/eigen_initiative/phases/phase_N/epic_M/tasks/task_001.md` ... `task_NNN.md` — one task file per task
- `$EIGEN_ROOT/eigen_initiative/phases/phase_N/epic_M/tasks/task_INT.md` — the integration task
- `$EIGEN_ROOT/eigen_initiative/phases/phase_N/epic_M/swarm-manifest.json` — the swarm execution manifest

## ID Convention

Task IDs use the triplet convention:
- **Task ID**: `P<N>.E<M>.T<K>` — e.g., `P1.E2.T3` (Phase 1, Epic 2, Task 3)
- Task numbers (K) are sequential within the epic, starting at 1
- The integration task uses `P<N>.E<M>.INT` as its ID
- Task file names: `task_001.md`, `task_002.md`, ..., `task_INT.md`

---

## CRITICAL: No Code Implementation in Tasks

**These are planning documents, not implementation documents.**
- Provide architectural guidance, not code
- Describe algorithms conceptually, not line-by-line
- Reference patterns and approaches, not actual syntax
- Let the sub-agents write the code based on your guidance

---

## Stage 0: Ingest

### 0.1 Read Plan File

1. Read `$EIGEN_ROOT/eigen_initiative/phases/phase_N/epic_M/plan.md`. If not found → **STOP.** Print: "No plan found. Run `/plan_phase_epic` first."
2. Extract the full plan content, including the Parallelization Strategy section.
3. If no Parallelization Strategy section exists, derive one from the plan before proceeding (identify independent components, shared files, and interfaces).

### 0.2 Read Epic File

1. Read `$EIGEN_ROOT/eigen_initiative/phases/phase_N/epic_M/epic.md`.
2. Parse YAML frontmatter for `id`, `phase`, `epic_number`, `features`, `feature_count`.

### 0.3 Read Phase E2E Config

1. Read `$EIGEN_ROOT/eigen_initiative/phases/phase_N/phase_e2e_config.json`.
2. Determine the epic type:
   - **Feature epic**: this epic has features (non-empty `features` array in epic.md). Read `epic_validation_scenarios` filtered to this epic's ID.
   - **E2E Testing epic**: this epic has no features (empty `features` array, name is "E2E Testing"). Read `phase_e2e_scenarios` and `infrastructure_requirements`.
3. Extract the relevant E2E/validation scenarios for the manifest.

### 0.4 Read Bootstrap Report

1. Read `$EIGEN_ROOT/eigen_initiative/phases/phase_N/bootstrap-report.json`.
2. Extract: `languages`, `tooling_decisions`, `entities_created`.

### 0.5 Read Recommendations (if present)

1. Parse `recommendations` from the JSON returned by `eigen-squared get-context` (see **On Entry** above).
2. Use as advisory context for task boundary analysis and dependency graph construction.
3. Do NOT embed recommendations in task bodies or the manifest.

---

## Stage 1: Analyze Plan

### 1.1 Analyze the Plan

Before generating tasks, analyze the plan to:
- Identify critical dependencies between plan components
- Assess complexity of each planned change
- Map file ownership boundaries — which files belong to which logical component
- Identify shared files — files that multiple components need to modify (routes, configs, package index files per the language profile, etc.)

### 1.2 Extract Parallelization Strategy

From the plan's Parallelization Strategy section, extract:
- Independent components with their estimated files
- Shared Files Map
- Interfaces Between Components (with contracts and stub files)
- Execution Waves
- E2E Test Scenarios

---

## Stage 2: Generate Tasks

### 2.1 Determine Task Boundaries with File Ownership

Create tasks that align with natural boundaries:
- **Feature completeness**: each task delivers a testable unit of functionality
- **File cohesion**: group related changes to the same file/module
- **Testability**: each task should have clear unit/integration test requirements
- **File isolation**: each task MUST own a disjoint set of files

#### File Ownership Rules

1. **Exclusive ownership**: each source file appears in exactly ONE task's `files_owned[]`, OR in `shared_files[]`. Never both.
2. **Test file ownership**: each task owns the test files for its source files. Same exclusivity rule.
3. **Shared files**: files that multiple tasks need to modify go into `shared_files[]` and are handled by the integration task.
4. **Overlap detection**: if two tasks both need a file, move it to `shared_files[]`.

### 2.2 Build the Dependency Graph

1. **Identify blocking relationships**: if Task B imports a module that Task A creates, B is blocked by A.
2. **Distinguish interface dependencies**: if an interface has `stub_file` + `contract`, record as `interface_deps` (NOT `blocked_by`). Interface deps do NOT enforce later-wave placement.
3. A dependency goes into `blocked_by` when B needs A's FULL implementation, not just the interface.
4. Circular `interface_deps` are valid. Only `blocked_by` must form a DAG.
5. **Compute execution waves** via topological sort:
   - Wave 1: tasks with no blockers
   - Wave N: tasks whose blockers are all in waves 1..N-1
   - Final wave: always an integration wave for `shared_files[]`
6. At least one task MUST have zero blockers (Wave 1 must be non-empty).

### 2.3 Generate Task Specifications

For each task, produce:

1. **Task Title**: `[PHASE-<N>] <Action Verb> <Component> - <Brief Description>`
2. **Task Description** with Context, Implementation Details, Technical Approach — all strategic, no code
3. **File Ownership**: explicit `files_owned` and `test_files_owned` lists
4. **Interface Dependencies**: stub file, contract, import rules per the `language-profiles` skill
5. **Acceptance Criteria**: specific, verifiable criteria
6. **Testing Requirements**: unit tests, integration tests, edge cases
7. **Dependencies**: blocked_by, blocks
8. **Risk Flags**: breaking changes, performance sensitivity, complexity

### 2.4 Generate the Integration Task

Always create a final integration task that:
- Is blocked by ALL other tasks
- Owns all `shared_files[]`
- Responsible for wiring up routes/endpoints, updating shared config, updating package index files (per language — skip for Go/.NET), running the full test suite

---

## Stage 3: Create Task Files

### 3.1 Create Task Files

For each task, ordered by task number K:

1. Derive the task ID: `P<N>.E<M>.T<K>` (sequential, starting at 1)
2. Create the task directory: `mkdir -p $EIGEN_ROOT/eigen_initiative/phases/phase_N/epic_M/tasks/`
3. Write the task file at `$EIGEN_ROOT/eigen_initiative/phases/phase_N/epic_M/tasks/task_<K padded to 3 digits>.md`

Task file format with YAML frontmatter:

```markdown
---
id: "P<N>.E<M>.T<K>"
title: "[PHASE-<N>] <Title>"
type: task
state: open
labels: ["Phase <N>", "P0-critical"]
phase: <N>
epic_id: "P<N>.E<M>"
priority: P0
wave: <wave_number>
estimated_effort: "N days"
blocked_by: ["P<N>.E<M>.T<X>"]
blocks: ["P<N>.E<M>.T<Y>"]
interface_deps: []
files_owned:
  - path/to/file1
test_files_owned:
  - tests/test_file1
created_at: "<ISO 8601>"
updated_at: "<ISO 8601>"
---

## Task: [PHASE-<N>] <Title>

**Parent Epic:** P<N>.E<M> — <epic_name>
**Phase:** <N>
**Priority:** P0
**Estimated Effort:** N days
**Wave:** <wave_number>

### Context
...

### Implementation Details
...

### File Ownership
**Source files owned by this task:**
- ...

**Test files owned by this task:**
- ...

### Interface Dependencies
...

### Acceptance Criteria
- [ ] ...

### Testing Requirements
...

### Dependencies
- **Blocked by**: ...
- **Blocks**: ...

### Risk Flags
...

## Comments

```

For the integration task, use `task_INT.md` with ID `P<N>.E<M>.INT`.

### 3.2 Update Parent Epic

Update the parent epic's `task_ids` array in `$EIGEN_ROOT/eigen_initiative/phases/phase_N/epic_M/epic.md` YAML frontmatter to include all created task IDs.

### 3.3 Document Dependencies

After ALL tasks are created, append dependency comments to each task's `## Comments` section:

```markdown
Blocked by P<N>.E<M>.T<X>: <blocker task title>
```

### 3.4 Update Initiative Index

Update `$EIGEN_ROOT/eigen_initiative/_index.md` to include the new tasks. If it doesn't exist, create it.

---

## Stage 4: Generate Swarm Manifest

### 4.1 Build Manifest

Generate `$EIGEN_ROOT/eigen_initiative/phases/phase_N/epic_M/swarm-manifest.json`:

```json
{
  "epic_id": "P<N>.E<M>",
  "plan_file": "phases/phase_N/epic_M/plan.md",
  "created_at": "<ISO-8601 timestamp>",
  "tasks": [
    {
      "id": "P<N>.E<M>.T1",
      "summary": "<task title>",
      "phase": <N>,
      "model": "opus",
      "blocked_by": [],
      "interface_deps": [],
      "files_owned": ["src/auth/models.py", "src/auth/service.py"],
      "test_files_owned": ["tests/test_auth_models.py"]
    }
  ],
  "shared_files": ["src/routes.py", "src/config.py"],
  "execution_waves": [
    {"wave": 1, "tasks": ["P<N>.E<M>.T1", "P<N>.E<M>.T2"]},
    {"wave": 2, "tasks": ["P<N>.E<M>.T3"]},
    {"wave": 3, "tasks": ["P<N>.E<M>.INT"], "type": "integration"}
  ],
  "e2e_config": {
    "e2e_test_dir": "tests/e2e/",
    "e2e_test_command": "python -m pytest tests/e2e/ -v",
    "e2e_marker": "@pytest.mark.e2e",
    "e2e_output_format": "--junitxml=e2e-report.xml",
    "e2e_file_pattern": "test_e2e_*.py",
    "e2e_scenarios": [
      {
        "name": "user_registration_flow",
        "description": "User registers, verifies email, and logs in",
        "components_involved": ["P<N>.E<M>.T1", "P<N>.E<M>.T2"],
        "acceptance_criteria_ref": "AC-1"
      }
    ],
    "max_iterations": 3,
    "fix_budget_per_worker": 2,
    "max_total_fix_spawns": 8
  }
}
```

**E2E config population — depends on epic type:**

- **For feature epics**: populate `e2e_scenarios` from the `epic_validation_scenarios` in `phase_e2e_config.json` for this epic. Resolve `e2e_test_dir`, `e2e_test_command`, `e2e_marker`, `e2e_output_format`, `e2e_file_pattern` from the `language-profiles` skill for the detected language. No infrastructure setup/teardown — feature epic validation tests run against whatever the development environment provides.

- **For the E2E Testing epic**: populate `e2e_scenarios` from the `phase_e2e_scenarios` in `phase_e2e_config.json`. The tasks in this epic will CREATE the E2E infrastructure (docker-compose, emulator setup, etc.) based on `infrastructure_requirements` from `phase_e2e_config.json`. The `e2e_test_command` and related fields are resolved from the language profile.

**Field descriptions:**

- `epic_id`: the parent epic's triplet ID (e.g., `P1.E2`)
- `plan_file`: relative path to the plan file
- `created_at`: ISO-8601 timestamp of when the manifest was generated
- `tasks[]`: array of task objects:
  - `id`: task triplet ID (e.g., `P1.E2.T1`)
  - `summary`: the task title
  - `phase`: the phase number
  - `model`: the Claude model to use for this task's teammate. Always `"opus"` for all tasks.
  - `blocked_by`: array of task triplet IDs that must complete before this task can start
  - `interface_deps`: array of interface dependencies satisfied by stubs (default: `[]`). Each entry:
    - `provider_id`: task triplet ID of the provider task (e.g., `P1.E2.T1`)
    - `interface_name`: name of the class/protocol/interface
    - `stub_file`: file path where the interface is defined — must be in the provider task's `files_owned`
    - `contract`: human-readable description of method signatures the provider must implement
    - Interface deps do NOT block wave placement — consumers can be co-waved with providers
  - `files_owned`: array of source file paths this task is allowed to create/modify
  - `test_files_owned`: array of test file paths this task is allowed to create/modify
  - `status`: optional — not set on initial creation. Added later by `/review_swarm_pr` (set to `"completed"` for tasks from a previous swarm run during review fixup cycles)
- `shared_files`: array of file paths that no individual task owns — handled by the integration task in the final wave
- `execution_waves[]`: array of wave objects (topologically sorted):
  - `wave`: wave number (1-indexed)
  - `tasks`: array of task triplet IDs that can execute in parallel within this wave
  - `type`: optional — set to `"integration"` for the final wave
- `e2e_config`: configuration for validation/E2E testing:
  - `e2e_test_dir`: directory where E2E/validation tests live (resolved from `language-profiles` skill)
  - `e2e_test_command`: command to run tests (resolved from language profile)
  - `e2e_marker`: how tests are tagged (resolved from language profile)
  - `e2e_output_format`: output format flag for parseable results (resolved from language profile)
  - `e2e_file_pattern`: file naming pattern for tests (resolved from language profile)
  - `e2e_scenarios[]`: array of test scenarios. Each entry:
    - `name`: scenario name (string)
    - `description`: what the flow validates (string)
    - `components_involved`: array of task triplet IDs involved in this flow
    - `acceptance_criteria_ref`: reference to the acceptance criterion this validates (string)
  - `max_iterations`: maximum E2E fix loop iterations (default: 3)
  - `fix_budget_per_worker`: max fix attempts per individual worker (default: 2)
  - `max_total_fix_spawns`: global cap on total fix worker spawns across all iterations (default: 8)

### 4.2 Validate Manifest

Before writing, run these validations:

1. **No circular `blocked_by`**: the dependency graph must be a valid DAG (circular `interface_deps` are allowed)
2. **No file ownership overlaps**: `files_owned` sets must be disjoint across all tasks
3. **All `blocked_by` references are valid**: every ID must correspond to a task in the manifest
4. **Wave 1 is non-empty**: at least one task has no blockers
5. **Integration task exists**: last wave contains the integration task owning all `shared_files`
6. **All files accounted for**: every file from task descriptions appears in exactly one task's `files_owned` OR in `shared_files`
7. **Interface deps consistency**: `provider_id` is valid, `stub_file` is in provider's `files_owned`, no dependency in both `blocked_by` and `interface_deps`
8. **E2E config present**: `e2e_scenarios` has at least one entry
9. **E2E test directory isolation**: `e2e_test_dir` does not overlap with any task's `test_files_owned`
10. **E2E scenario references**: all task IDs in `components_involved` are valid

#### Language-Specific Manifest Notes

- **Go**: `files_owned` should list entire package directories, not individual files
- **Rust**: `test_files_owned` may overlap with `files_owned` for co-located unit tests
- **Go**: `interface_deps[].stub_file` may be empty (consumers define their own interfaces)

### 4.3 Write Manifest

Write the validated manifest to `$EIGEN_ROOT/eigen_initiative/phases/phase_N/epic_M/swarm-manifest.json`.

---

### 4.4 Finalize Pipeline State

Pipeline state updates are handled by the CLI on exit (see **On Exit** above). You do not modify `pipeline_state.json` directly.

---

## Stage 5: Create Integration Branch and Commit Artifacts

After all tasks and the manifest are created, create the integration branch and commit the artifacts. The orchestrator and workers will operate on this branch from `$EIGEN_ROOT`.

### Sync with Remote

```bash
eigen-squared sync
```

### 5.1 Create the Integration Branch from $EIGEN_BRANCH

```bash
eigen-squared checkout-branch --phase <N> --epic <M> --create
```

### 5.2 Commit Manifest and Tasks on the Integration Branch

The manifest, task files, and plan are already at `$EIGEN_ROOT/eigen_initiative/phases/phase_N/epic_M/`. Since we checked out `feat/P<N>.E<M>` (which was created from `origin/$EIGEN_BRANCH`), these files are already present in the working directory — no copying needed.

```bash
eigen-squared commit-state --message "chore: add swarm manifest, tasks, and plan for P<N>.E<M>" --additional-paths eigen_initiative/phases/phase_<N>/epic_<M>/
```

### 5.3 Branch state

After committing and pushing, the working directory remains on the `feat/P<N>.E<M>` integration branch. The pipeline controller hook handles checking out the correct branch for the next command (orchestrate_swarm on this same branch, or EIGEN_BRANCH for other commands).

---

## Stage 6: Output Summary

Print:

```
=== Task Generation Complete — P<N>.E<M> ===

Epic: P<N>.E<M> — <epic_name>
Tasks created: <N> + 1 integration task
Waves: <N> execution waves

Task Summary:
  P<N>.E<M>.T1: <title> — Wave 1
  P<N>.E<M>.T2: <title> — Wave 1
  P<N>.E<M>.T3: <title> — Wave 2, blocked by T1
  P<N>.E<M>.INT: Integration — Wave 3, blocked by all

File Ownership Map:
  P<N>.E<M>.T1: <files>
  P<N>.E<M>.T2: <files>
  Shared: <shared files>
  Integration: <shared files>

Integration branch: feat/P<N>.E<M> (created from $EIGEN_BRANCH)

Files generated:
  $EIGEN_ROOT/eigen_initiative/phases/phase_N/epic_M/tasks/task_001.md
  ...
  $EIGEN_ROOT/eigen_initiative/phases/phase_N/epic_M/swarm-manifest.json

Next steps:
  To start the swarm, checkout the integration branch and run orchestrate_swarm:
    cd $EIGEN_ROOT
    git checkout feat/P<N>.E<M>
    /orchestrate_swarm

  The manifest, tasks, and plan are committed and pushed on the feat/P<N>.E<M> branch.
```

---

## Quality Checklist

Before finalizing, verify:
- [ ] Each task has 3-5 specific acceptance criteria
- [ ] Dependencies form a valid DAG (no circular `blocked_by`)
- [ ] No file appears in `files_owned` of two different tasks
- [ ] All shared files are listed in `shared_files` and assigned to the integration task
- [ ] At least one task has zero blockers (Wave 1 is non-empty)
- [ ] All `blocked_by` references point to valid task IDs
- [ ] An integration task exists as the final wave
- [ ] `interface_deps` only reference valid provider tasks
- [ ] Each `stub_file` is in the provider's `files_owned`
- [ ] No dependency in both `blocked_by` and `interface_deps` for the same task pair
- [ ] Circular `interface_deps` are NOT flagged as errors
- [ ] `e2e_config` is present with at least one scenario
- [ ] `e2e_test_dir` does not overlap with any task's `test_files_owned`
- [ ] `e2e_scenarios` `components_involved` reference valid task IDs
- [ ] E2E config fields resolved from the `language-profiles` skill
- [ ] No code examples in task descriptions — pseudocode and architectural descriptions only
- [ ] Epic.md `task_ids` updated with all created task IDs
- [ ] Task IDs use triplet format (`P<N>.E<M>.T<K>`)

---

**Remember**: These tasks will be executed by autonomous sub-agents **running in parallel as a swarm**. Your task specifications are their PRIMARY GUIDANCE. The `swarm-manifest.json` is the KEY ARTIFACT that the orchestrator will use to coordinate execution. File ownership boundaries are CONTRACTUAL — violating them causes silent data loss in a swarm.

---

## Pipeline Continuation

The `eigen-squared schedule-next` hook fires when this session ends. It reads the pipeline state (updated by the CLI) and schedules the next command automatically. You do not need to schedule anything.
