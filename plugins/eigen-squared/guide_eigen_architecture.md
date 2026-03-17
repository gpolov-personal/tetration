# Eigen Architecture Guide

A comprehensive guide to the eigen system: its decomposition-convergence pipeline, iteration-aware commands, parallel swarm execution, and compound self-improvement.

---

## Table of Contents

0. [Initiative-Scale Pipeline](#0-initiative-scale-pipeline)
   - [Pipeline State](#01-pipeline-state)
   - [time_split](#02-time_split)
   - [bootstrap](#03-bootstrap)
   - [space_split](#04-space_split)
   - [Iteration-Convergence Cycle](#05-iteration-convergence-cycle)
   - [Manual Epic Execution Workflow](#06-manual-epic-execution-workflow)
   - [Two Feedback Systems](#07-two-feedback-systems)
1. [System Overview](#1-system-overview)
2. [The Complete Pipeline](#2-the-complete-pipeline)
3. [Command Reference](#3-command-reference)
   - [time_split](#30a-time_split)
   - [space_split](#30b-space_split)
   - [deepen_time_split](#30c-deepen_time_split)
   - [deepen_space_split](#30d-deepen_space_split)
   - [compound_improve](#30e-compound_improve)
   - [bootstrap](#30f-bootstrap)
   - [deepen_bootstrap](#30g-deepen_bootstrap)
   - [Pipeline State Reference](#30h-pipeline-state-reference)
   - [plan_phase_epic](#30i-plan_phase_epic)
   - [deepen_plan_phase_epic](#30j-deepen_plan_phase_epic)
   - [plan_from_gh_issue_swarm](#31-plan_from_gh_issue_swarm)
   - [create_issues_from_plan_swarm](#32-create_issues_from_plan_swarm)
   - [orchestrate_swarm](#33-orchestrate_swarm)
   - [design_validation_tests_swarm](#34-design_validation_tests_swarm)
   - [code_from_validation_tests_swarm](#35-code_from_validation_tests_swarm)
   - [e2e_validation_swarm](#36-e2e_validation_swarm)
   - [review_swarm_pr](#37-review_swarm_pr)
4. [Core Concepts](#4-core-concepts)
   - [File Ownership](#41-file-ownership)
   - [Dependency Types: blocked_by vs interface_deps](#42-dependency-types)
   - [Execution Waves](#43-execution-waves)
   - [Interface Stubs and the Provider/Consumer Pattern](#44-interface-stubs)
   - [Compaction Resilience](#45-compaction-resilience)
   - [E2E Validation and the Fix Loop](#46-e2e-validation-and-the-fix-loop)
5. [Communication Protocol](#5-communication-protocol)
6. [Scenarios](#6-scenarios)
   - [Scenario A: Provider Creates Interface, Consumer Uses It](#scenario-a)
   - [Scenario B: Teammate Asks Leader a Question](#scenario-b)
   - [Scenario C: Leader Criticizes Test Quantity](#scenario-c)
   - [Scenario D: Ownership Violation Request](#scenario-d)
   - [Scenario E: Multi-Wave Execution with Integration](#scenario-e)
   - [Scenario F: Consumer Re-validates Against Real Implementation (Phase C)](#scenario-f)
   - [Scenario G: E2E Test Fails and Fix Loop Executes](#scenario-g)
   - [Scenario H: Cross-Boundary E2E Failure](#scenario-h)
   - [Scenario I: Stuck Test Detection and Human Escalation](#scenario-i)
7. [Variable Reference](#7-variable-reference)
8. [Task System Tags Reference](#8-task-system-tags-reference)
9. [Language-Agnostic Design](#9-language-agnostic-design)

---

## 0. Initiative-Scale Pipeline

For initiative-scale work (50+ features with complex dependencies), the eigen system provides commands that sit **above** the standard swarm pipeline. They decompose a large initiative into manageable units, iteratively refine those decompositions until they converge, and then enter the standard plan → issues → swarm cycle.

### 3-Level Hierarchy

```
Initiative (104 features, complex DAG)
    │
    │  /time_split ←──── /deepen_time_split ←─┐
    │       │                    │              │
    │       └─── iterate until convergence ────┘
    ▼
Phases (3-5 sequential, E2E-testable stages)
    │
    │  /bootstrap (per phase) ←──── /deepen_bootstrap ←─┐
    │       │                             │              │
    │       └──── iterate until convergence ─────────────┘
    │
    │  /space_split (per phase) ←── /deepen_space_split ←─┐
    │       │                             │                │
    │       └──── iterate until convergence ───────────────┘
    ▼
Epics (3-6 parallel groups per phase, DAG-ordered)
    │
    │  /plan_phase_epic (per epic) ←── /deepen_plan_phase_epic ←─┐
    │       │                                │                    │
    │       └──── iterate until convergence ──────────────────────┘
    │
    │  /orchestrate_swarm (per epic, manual trigger)
    ▼
Tasks (file-disjoint workers within each epic)
```

### 0.1 Pipeline State

All eight initiative-scale commands (time_split, deepen_time_split, bootstrap, deepen_bootstrap, space_split, deepen_space_split, plan_phase_epic, deepen_plan_phase_epic) share a single source of truth: **`phases/pipeline_state.json`**.

Created by `/time_split` on first run, read and updated by every command on entry and exit. It tracks:

- **Iteration counts** — how many times each command has run
- **Status** — `not_started` | `completed` | `iterating` for each command
- **Convergence** — whether deepen commands have declared the output converged
- **Feedback consumption** — whether feedback from deepen commands has been consumed by the next iteration of the main command
- **Output paths** — where each command's outputs live
- **Per-phase state** — bootstrap, deepen_bootstrap, space_split, deepen_space_split each tracked independently per phase

The full schema is defined in `schemas/pipeline_state.md` in the eigen plugin.

**Why a shared state file:** Without it, commands have no awareness of each other. time_split wouldn't know if deepen_time_split found critical issues. bootstrap wouldn't know if it's been run before. The pipeline state file enables idempotency guards, prerequisite checks, and the iteration-convergence cycle.

### 0.2 time_split

**Purpose:** Split an initiative into sequential, E2E-testable phases using the dependency DAG.

**Pipeline Awareness:** On entry, checks `pipeline_state.json`. If converged, stops. If unconsumed deepen feedback exists, enters iteration protocol. If no feedback and iteration >= 1, stops with "run /deepen_time_split first". On exit, creates or updates the pipeline state.

**Input:**
- A directory containing 3 files: Initiative document (feature summary table + DAG properties), Blackbox Requirements (full feature specs), Whitebox Reference Guide (implementation patterns)

**Process:**
1. Parse the Feature Summary Table and build a dependency DAG
2. Load pre-computed DAG properties (roots, leaves, bottlenecks, critical paths, clusters)
3. Compute phase count: `max(ceil(critical_path/3), ceil(capability_tracks/2), 3)`, capped at 8
4. Seed Phase 1 with infrastructure + roots + minimum E2E features
5. Layer remaining features by dependency depth (respect clusters, priorities, bottlenecks)
6. Verify progressive E2E per phase; balance phase sizes (target 8-35 features)
7. Present summary to user for confirmation (accept / adjust / re-constrain)

**On Iteration:** Reads `phases/feedback/deepen_time_split_feedback.json`. Performs an honest self-assessment of each finding (ACCEPT/PARTIAL/REJECT), prints rationale to user, then regenerates with accepted findings as constraints. Overwrites existing output files. Does NOT delete the feedback file — it stays for deepen_time_split to compare on the next review.

**Output:**
- `phases/pipeline_state.json` — created on first run, updated on every run
- `phases/initiative_summary.json` — metadata and per-phase summary
- `phases/phase_N_manifest.md` — per phase: YAML frontmatter, feature tables, cross-phase deps, clusters, verbatim blackbox specs, filtered whitebox sections

**Key Rules:**
- Clusters are atomic — never split across phases
- Every phase must enable a progressive E2E test (data in → processing → storage → output)
- Phase count: minimum 3, maximum 8
- Phase sizes: target 8-35 features per phase

### 0.3 bootstrap

**Purpose:** Create the project foundation (structure, contracts, config) before parallel epics can execute. Runs once per phase — Phase 1 is heavy (greenfield), Phase 2+ is incremental.

**Pipeline Awareness:** Validates that time_split has completed (prerequisite). Checks per-phase bootstrap state in `pipeline_state.json`. Same entry guards as time_split: converged → stop, unconsumed feedback → iterate, no feedback + iteration >= 1 → stop.

**Why before space_split:** Bootstrap uses zero information from space_split, but space_split benefits hugely — it reads the bootstrap report to reference real file paths, real entity stubs, and real directory structure in the epic files it creates.

**Input:**
- A `phase_N_manifest.md` from `/time_split` (contains features, domains, blackbox specs, filtered whitebox sections)
- Path to the target repository (may be empty)

**Process:**
1. Scan the target repo to detect what already exists (incremental detection)
2. Resolve language from repo manifest files or ask user
3. For greenfield repos: make tooling decisions with user (package manager, framework, linting, CI) — informed by best-practices research agents
4. Derive required artifacts from phase manifest: directory structure, shared entity stubs (entities referenced by 2+ features across 2+ domains), API contracts, message contracts, config, CI, infrastructure
5. Compute delta (required - existing), present to user for confirmation
6. Execute: Wave 0 (lead creates scaffold), Wave 1 (parallel sub-agents: Contract Generator + Infrastructure Architect)
7. Run verification gate (compilation/linting check)
8. Generate bootstrap-report.json

**On Iteration (Surgical Delta):** Reads `phases/phase_N/feedback/deepen_bootstrap_feedback.json`, specifically the `code_change_guidance` section. Does NOT re-scaffold from scratch. Scans current repo state, applies only the feedback-driven changes (entities_to_add, entities_to_modify, config_changes, files_to_delete). Does NOT re-run tooling decisions. Commits with `"bootstrap: iteration N — address deepen feedback"`. Does NOT delete the feedback file.

**Output:**
- Committed foundation files in the target repo (on `dev` branch)
- `phases/phase_N/bootstrap-report.json` — what was created, verification status, commit hashes, iteration number, iteration history

**Key Rules:**
- Never writes business logic — entity stubs have empty bodies / `NotImplementedError`
- Never creates a walking skeleton — first wave of epics provides real E2E flow
- Incremental: Phase 1 creates everything, Phase 2+ only adds what's new for that phase
- Every artifact must be justified by the phase manifest
- User confirms the delta before any files are written

### 0.4 space_split

**Purpose:** Decompose a single phase manifest into parallel epics with DAG ordering. Creates one local epic file per epic with full context for downstream `/plan_from_gh_issue_swarm`.

**Pipeline Awareness:** Validates that bootstrap has completed for this phase (prerequisite). Same entry guards and feedback consumption pattern as other main commands.

**Input:**
- A `phase_N_manifest.md` (from `/time_split`)
- The `phases/phase_N/` directory (containing `bootstrap-report.json` from `/bootstrap`)

**Process:**
1. Parse phase manifest (features, dependencies, clusters, blackbox specs, whitebox sections)
2. Read bootstrap report (entity stubs, file paths, tooling decisions)
3. Build local DAG (cross-phase deps = "already available")
4. Form epics: clusters as atomic units → merge unclustered by domain/dependency → target 3-8 features per epic
5. Build Epic DAG: topological sort into execution waves
6. Define inter-epic interfaces with concrete file paths from bootstrap entity map
7. Present epic split to user for confirmation
8. Create one epic file per epic at `phases/phase_N/epic_M/epic.md` with full blackbox specs, whitebox guidance, bootstrap context, and inter-epic interfaces
9. Generate phase-level artifacts

**On Iteration (Epic File Handling):** Reads `phases/phase_N/feedback/deepen_space_split_feedback.json`, specifically the `epic_updates` section. Does NOT create duplicate files. Updates existing files for `epics_to_update`, replaces for `epics_to_replace`, leaves unchanged epics untouched. Regeneration scope determined by finding category: epic formation/DAG errors → re-run from Phase 1, interface/spec errors → re-run from Phase 2, E2E coverage gaps → re-run from Phase 3 only. Does NOT delete the feedback file.

**Output:**
- Epic files — one per epic at `phases/phase_N/epic_M/epic.md`, with full context for `/plan_phase_epic`
- `phases/phase_N/epic_dag.json` — epic DAG with execution waves, interfaces, local epic IDs, `local_path` per epic, iteration number
- `phases/phase_N/phase_e2e_config.json` — phase-level E2E test scenarios
- `phases/phase_N/epic_M/epic.md` — per-epic file with unified YAML frontmatter (id, title, state, phase, epic_number, wave, feature_count, features, task_ids, timestamps) and full epic content. Read by downstream `/plan_phase_epic`.
- Initializes empty `plans` section in `pipeline_state.json` for downstream `plan_phase_epic` to populate

**Does NOT produce:** Per-epic `plan.md` or `swarm-manifest.json`. Plans are created downstream by `/plan_phase_epic` (pipeline-aware) or `/plan_from_gh_issue_swarm` (standalone). Swarm manifests are created by `/create_issues_from_plan_swarm`.

**Key Rules:**
- Clusters are atomic within epics — never split
- Epic size: 3-8 features (max 10 for large clusters)
- Epic files contain complete context (blackbox specs, whitebox, bootstrap entity paths) so `/plan_from_gh_issue_swarm` can generate plans from the epic file alone
- User confirms the epic split before issues are created

### 0.5 Iteration-Convergence Cycle

The core power of the eigen pipeline is the **iteration-convergence cycle**: each main command runs, its deepen counterpart reviews the output, and if issues are found, the main command re-runs with the feedback as input. This repeats until the deepen command declares convergence.

```
  ┌──────────────────────────────────────────────────────────┐
  │                                                          │
  │  /time_split ──→ /deepen_time_split ──→ feedback file    │
  │       ▲                                      │           │
  │       │          ┌───────── converged? ───────┤           │
  │       │          │                     │      │           │
  │       │         YES                    NO     │           │
  │       │          │                     │      │           │
  │       │          ▼                     ▼      │           │
  │       │     STOP (proceed         /time_split │           │
  │       │     to bootstrap)        (with feedback)          │
  │       │                                │      │           │
  │       └────────────────────────────────┘      │           │
  │                                                          │
  │  Same cycle applies to bootstrap, space_split,            │
  │  and plan_phase_epic                                     │
  └──────────────────────────────────────────────────────────┘
```

**Convergence is decided by deepen commands only.** Main commands never decide if their own output is "good enough" — they defer to the independent reviewer. Deepen commands always write a feedback file, even when converged (with zero findings and `convergence.decision: "converged"`).

**Convergence Rules:**
1. **Zero high-severity findings** → converge
2. **Iteration limit reached** → converge (time_split: 5 iterations, bootstrap/space_split/plan_phase_epic: 3 iterations)
3. **Oscillation detected** → converge (finding that was fixed then regressed — accept current state)
4. **Continue** if actionable high-severity findings remain

**Oscillation Detection:** If a finding was present in iteration N, absent in N+1, and present again in N+2, it's classified as oscillating. Oscillating findings force convergence because further iteration would just re-introduce the issue. The feedback file records oscillation details.

**Feedback File Lifecycle:**
1. Main command runs (first time) → creates outputs → marks own `feedback_consumed=true`, deepen's `feedback_consumed=true`
2. Deepen runs → writes feedback file → marks main's `feedback_consumed=false`, own `feedback_consumed=false`
3. Main runs again → reads feedback (does NOT delete it) → marks own `feedback_consumed=true`, deepen's `feedback_consumed=true`
4. Deepen runs again → reads own previous feedback + new outputs → overwrites feedback file → cycle continues
5. Convergence → deepen writes final feedback with `convergence.decision: "converged"` → main command sees converged state and stops

**Feedback files are separate from main command outputs.** Deepen commands never modify phase manifests, bootstrap reports, or epic DAGs. They write to dedicated `feedback/` directories:
- `phases/feedback/deepen_time_split_feedback.json`
- `phases/phase_N/feedback/deepen_bootstrap_feedback.json`
- `phases/phase_N/feedback/deepen_space_split_feedback.json`
- `phases/phase_N/epic_M/feedback/deepen_plan_phase_epic_feedback.json`

Each feedback file contains: convergence decision, previous feedback comparison, findings with severity/category/downstream impact, and command-specific guidance (code_change_guidance for bootstrap, epic_file_updates for space_split, plan_change_guidance for plan_phase_epic).

### 0.6 Manual Epic Execution Workflow

After the decomposition commands converge, the user drives execution **manually**, reviewing between each epic:

```
For each phase (sequential):
  Run /time_split (iterate with /deepen_time_split until converged)
  Run /bootstrap on the phase manifest + target repo
    (iterate with /deepen_bootstrap until converged)
  Run /space_split on the phase manifest + phase directory
    (iterate with /deepen_space_split until converged)
  │
  For each epic wave (sequential by DAG):
    For each epic in this wave (can be parallel):
      │
      ├─ 1. Run /plan_phase_epic <phase_number> <epic_number>
      │      (iterate with /deepen_plan_phase_epic until converged)
      ├─ 2. Run /create_issues_from_plan_swarm <epic_issue_number>
      ├─ 3. Run /orchestrate_swarm <issue_number> <branch>
      └─ 4. Review results before proceeding to next epic
```

The human-in-the-loop design ensures:
- Review checkpoints between every epic
- Iterative refinement of decompositions before execution
- Ability to adjust plans based on learnings from earlier epics
- No runaway execution of 100+ features without oversight
- Freedom to re-order or skip epics based on changing priorities

### 0.7 Two Feedback Systems

Eigen has **two completely separate feedback systems** that serve different purposes:

#### A. Project Iteration Feedback (within a single project)

The iteration-convergence cycle described in [Section 0.5](#05-iteration-convergence-cycle). Feedback files live in the **project's `phases/` directory** and guide the next iteration of the same command within the same project.

- **Purpose:** Refine this project's decomposition until it's good enough to execute
- **Stored in:** `phases/**/feedback/` (project repo)
- **Consumed by:** The next iteration of the same main command
- **Lifecycle:** Created by deepen, read by main command, overwritten by next deepen run

#### B. Plugin Lessons (across projects)

Lessons extracted by deepen commands that improve the **plugin command prompts permanently**. Lessons live in the **plugin source repo** and are applied by `/compound_improve`.

- **Purpose:** Make the command prompts better over time based on patterns observed across multiple projects
- **Stored in:** `lessons/time_split/`, `lessons/bootstrap/`, `lessons/space_split/`, `lessons/plan/` (plugin source repo)
- **Consumed by:** `/compound_improve` (reads lessons, rewrites command `.md` files)
- **Lifecycle:** Accumulated across projects, applied in bulk, marked as `"applied"`

```
PROJECT FEEDBACK (per-project)          PLUGIN LESSONS (across projects)
────────────────────────────            ─────────────────────────────────
phases/feedback/                        lessons/time_split/
  deepen_time_split_feedback.json         ts-lesson-001.json
phases/phase_1/feedback/                lessons/bootstrap/
  deepen_bootstrap_feedback.json          bs-lesson-001.json
  deepen_space_split_feedback.json      lessons/space_split/
phases/phase_1/epic_1/feedback/           ss-lesson-001.json
  deepen_plan_phase_epic_feedback.json  lessons/plan/
                                          pl-lesson-001.json
        │                                       │
        ▼                                       ▼
  Next iteration of                     /compound_improve rewrites
  time_split/bootstrap/space_split/     command .md files permanently
  plan_phase_epic within THIS project   for ALL future projects
```

The optional plugin source path argument on deepen commands controls lesson extraction:
- With path: review + project feedback + lessons written (enables compound improvement)
- Without path: review + project feedback only (still useful for iteration within the project)

**Six deepen/apply commands:**

- **`deepen_time_split`** — Reviews `/time_split` output. Writes project feedback to `phases/feedback/`. Optionally writes lesson JSONs to `lessons/time_split/`.
- **`deepen_bootstrap`** — Reviews `/bootstrap` output. Writes project feedback (with `code_change_guidance`) to `phases/phase_N/feedback/`. Optionally writes lesson JSONs to `lessons/bootstrap/`.
- **`deepen_space_split`** — Reviews `/space_split` output. Writes project feedback (with `epic_file_updates`) to `phases/phase_N/feedback/`. Optionally writes lesson JSONs to `lessons/space_split/`.
- **`deepen_plan_phase_epic`** — Reviews `/plan_phase_epic` output. Writes project feedback (with `plan_change_guidance`) to `phases/phase_N/epic_M/feedback/`. Optionally writes lesson JSONs to `lessons/plan/`. Never modifies the plan file directly.
- **`deepen_plan`** — Reviews standalone plan output (from `/plan_from_gh_issue_swarm`). Diagnoses parallelization, structure, technology, and dependency errors. Embeds `### Research Insights` directly into the plan. Writes lesson JSONs to `lessons/plan/`.
- **`compound_improve`** — Reads all pending lessons, identifies recurring patterns across projects, rewrites the command `.md` files in the plugin source repo, bumps the plugin version. User commits and updates the plugin.

Lessons are JSON files stored in the plugin source repo (not the cache, not the project). They persist across plugin updates and are version-controlled. See `lessons/README.md` for the full schema.

---

## 1. System Overview

The swarm engineering system orchestrates **parallel development** by autonomous AI agents (teammates). A single **team lead** (the orchestrator) coordinates multiple **workers**, each owning a disjoint set of files, executing TDD-driven development in parallel. After all workers complete and shared files are integrated, a dedicated **e2e-tester** validates the assembled feature end-to-end.

```
                         User
                          |
                    Local Epic File #100
                          |
              +-----------+-----------+
              |                       |
    plan_from_gh_issue_swarm    (reviews plan)
              |
    create_issues_from_plan_swarm
              |
              v
    swarm-manifest.json + Task Files (#101, #102, #103...)
              |
       orchestrate_swarm
              |
     +--------+--------+--------+
     |        |        |        |
  worker    worker   worker   integrator
   #101      #102     #103    (shared files)
     |        |        |
  Phase A  Phase A  Phase A    (design_validation_tests_swarm)
     |        |        |
  Phase B  Phase B  Phase B    (code_from_validation_tests_swarm)
     |        |        |
     +--------+--------+
              |
        Integration Phase
              |
        E2E Validation          (e2e_validation_swarm)
         /    |    \
      pass?  fail?  fail?
        |      |      |
        |   fix loop (up to 3 iterations)
        |      |
        +------+
              |
         Shutdown & Report
```

**Key principles:**
- **File ownership is absolute** — no two workers edit the same file
- **TDD-first** — validation tests are designed before implementation
- **E2E mandatory** — end-to-end validation runs after integration, before success
- **Communication is mandatory** — silent workers are invisible workers
- **Language-agnostic** — all commands adapt via `language-profiles.md`

---

## 2. The Complete Pipeline

> **Note:** For initiative-scale work (50+ features), see [Section 0: Initiative-Scale Pipeline](#0-initiative-scale-pipeline) which covers the decomposition-convergence cycle (time_split → deepen → iterate → converge → bootstrap → deepen → iterate → converge → space_split → deepen → iterate → converge). The pipeline below describes per-epic execution — each epic produced by `/space_split` enters this pipeline individually.

### Step 1: Plan from Local Epic File

**Command:** `plan_from_gh_issue_swarm <issue_number>`

**What happens:**
1. Reads local epic file details from the file system
2. Spawns `repo-research-analyst` subagent to explore codebase
3. Determines complexity level (MINIMAL / STANDARD / COMPREHENSIVE)
4. Generates a strategic plan (no code, only architecture) with a **Parallelization Strategy** section (includes **E2E Test Scenarios**)
5. Runs gap analysis with parallel subagents (skills, learnings, review agents, parallelization validation) for STANDARD/COMPREHENSIVE plans

**Output:** Local plan file at `Plans/plan-for-epic-<N>.md` with Independent Components, Shared Files, Interfaces, Execution Waves, E2E Test Scenarios

### Step 2: Create Issues from Plan

**Command:** `create_issues_from_plan_swarm <plan_path> <parent_issue_number>`

**What happens:**
1. Reads the local plan file at `<plan_path>` (e.g., `Plans/plan-for-epic-<N>.md`)
2. Parses the Parallelization Strategy section (Independent Components, Shared Files, Interfaces, Execution Waves, E2E Scenarios)
3. Decomposes plan into file-disjoint tasks with exclusive file ownership
4. Creates local task files for each task (under `phases/phase_N/epic_M/tasks/`)
5. Generates `swarm-manifest.json` — the machine-readable execution spec (includes mandatory `e2e_config`)
6. Commits plan to current branch, then manifest + plan to integration branch

**Output:** N task files + `swarm-manifest.json` (with `e2e_config`)

### Step 3: Orchestrate the Swarm

**Command:** `orchestrate_swarm <parent_issue_number> <integration_branch> <manifest_path>`

**What happens:**
1. Parses arguments: parent issue number, integration branch name, manifest file path
2. Creates an isolated git worktree at `.claude/worktrees/<branch-slug>` on `<integration_branch>`
3. Reads and validates manifest (including `e2e_config` presence, no circular `blocked_by`, no file ownership overlaps)
4. Detects project tech stack and discovers relevant skills from `language-profiles.md`
5. Creates team (`swarm-<parent_issue_number>`) and tasks in shared task list
6. Spawns workers wave by wave (all teammates operate inside the worktree)
7. Reacts to worker messages (questions, blockers, progress)
8. Runs integration phase for shared files → **shuts down integrator**
9. **Runs E2E validation phase** (spawns `e2e-tester`)
10. **If E2E fails: runs fix loop** (up to 3 iterations with progressive escalation)
11. Shuts down team, removes worktree, and reports results

### Step 4-5: Worker Execution (Automatic)

Each spawned worker executes two phases automatically:

- **Phase A:** `design_validation_tests_swarm` — creates validation tests (TDD)
- **Phase B:** `code_from_validation_tests_swarm` — implements code to pass tests
- **Phase C (conditional):** Re-validates against real implementations if interface dependencies exist

### Step 6: E2E Validation (Automatic)

After all workers complete and integration finishes:

- **`e2e_validation_swarm`** — dedicated `e2e-tester` writes AND runs E2E tests (iteration 1)
- If failures: orchestrator runs **fix loop** — respawns workers with targeted fix instructions, re-runs E2E
- Up to 3 iterations: independent fix → guided fix → human escalation

---

## 3. Command Reference

### 3.0a time_split

**Purpose:** Split an initiative into sequential E2E-testable phases using the dependency DAG.

**Pipeline Awareness:**
- On entry: reads `pipeline_state.json` — converged → STOP, unconsumed feedback → iteration protocol, no feedback + iteration >= 1 → STOP ("run /deepen_time_split first")
- On exit: creates/updates `pipeline_state.json` with iteration count, status, output paths

**Input:**
| Variable | Source | Description |
|----------|--------|-------------|
| `<initiative_directory>` | `$ARGUMENTS` | Path to directory with Initiative doc, Blackbox Requirements, Whitebox Reference |

**Process (first run):**
1. **Locate & validate** 3 required files in the initiative directory
2. **Parse Feature Summary Table** — build features map `{id, name, domain, priority, dependencies[], cluster}`
3. **Build dependency DAG** — upstream edges from table, downstream by inversion
4. **Load DAG properties** — roots, leaves, bottlenecks, critical paths, clusters (from Section 9.3/9.4)
5. **Compute phase count** — `max(ceil(critical_path/3), ceil(tracks/2), 3)`, cap at 8
6. **Seed Phase 1** — INFRA-* + TECH-* + critical path roots + minimum E2E features
7. **Layer remaining** — modified topological sort respecting clusters, priorities, bottlenecks
8. **Verify E2E** — each phase enables progressive end-to-end testing
9. **Balance sizes** — merge phases <8 features, split phases >35 features
10. **User confirmation** — present summary, accept / adjust count / add constraints
11. **Generate outputs** — `phases/initiative_summary.json` + `phases/phase_N_manifest.md` per phase

**Process (iteration):**
1. Read `phases/feedback/deepen_time_split_feedback.json`
2. Honest self-assessment: classify each finding as ACCEPT / PARTIAL / REJECT, print rationale
3. Regenerate with accepted findings as constraints — overwrite existing output files
4. Do NOT delete the feedback file (owned by deepen_time_split)

**Output:**
- `phases/pipeline_state.json` — single source of truth for all commands
- `phases/initiative_summary.json` — initiative metadata, DAG stats, per-phase summary
- `phases/phase_N_manifest.md` — YAML frontmatter + feature tables + cross-phase deps + blackbox specs + whitebox sections

**Key Rules:**
- Clusters are never split across phases
- Every phase enables a progressive E2E test
- Phase count: 3-8; phase size: 8-35 features
- Blackbox specs are extracted verbatim per feature
- Whitebox sections are filtered to relevant domains per phase

---

### 3.0b space_split

**Purpose:** Decompose a phase manifest into parallel epics with DAG ordering. Creates one local epic file per epic with full context for downstream `/plan_from_gh_issue_swarm`.

**Pipeline Awareness:**
- Prerequisite: bootstrap must be completed for this phase
- On entry: reads per-phase state in `pipeline_state.json` — converged → STOP, unconsumed feedback → iteration protocol, no feedback + iteration >= 1 → STOP
- On exit: updates `state.phases[N].space_split`

**Input:**
| Variable | Source | Description |
|----------|--------|-------------|
| `<phase_manifest_path>` | `$ARGUMENTS` (token 1) | A `phase_N_manifest.md` from `/time_split` |
| `<phase_directory>` | `$ARGUMENTS` (token 2) | The `phases/phase_N/` directory containing `bootstrap-report.json` |

**Process (first run):**
1. **Parse phase manifest** — YAML frontmatter + features, deps, clusters, blackbox specs, whitebox sections
2. **Read bootstrap report** — entity stubs, file paths, tooling decisions, language
3. **Build local DAG** — only intra-phase dependencies; cross-phase deps = "already available"
4. **Form epic candidates** — clusters as atomic units → merge unclustered by domain/deps → target 3-8 features
5. **Build Epic DAG** — topological sort into execution waves
6. **Define inter-epic interfaces** — provider/consumer contracts with concrete file paths from bootstrap entity map
7. **Present to user** — summary table of epics with wave assignments, user confirms before proceeding
8. **Create epic files** — one per epic at `phases/phase_N/epic_M/epic.md`, body includes full blackbox specs, whitebox guidance, bootstrap context, inter-epic interfaces
9. **Generate phase artifacts** — epic_dag.json (with real issue numbers), phase_e2e_config.json

**Process (iteration — epic file handling):**
1. Read `phases/phase_N/feedback/deepen_space_split_feedback.json`
2. Honest self-assessment of each finding
3. **Epic file handling:** Do NOT create duplicate files. Update existing files for `epics_to_update`. Replace for `epics_to_replace`. Leave unchanged epics untouched.
4. **Regeneration scope** determined by finding category:
   - `epic_formation_error` | `dag_error` | `feature_coverage_error` → re-run from step 4
   - `interface_error` | `issue_completeness_error` | `spec_fidelity_error` → re-run from step 6
   - `e2e_coverage_gap` → re-run from step 9 only
5. Do NOT delete the feedback file

**Output:**
- Epic files — one per epic at `phases/phase_N/epic_M/epic.md`, with full context for `/plan_phase_epic`
- `phases/phase_N/epic_dag.json` — epic DAG, execution waves, cross-phase inputs, inter-epic interfaces, local epic IDs, iteration number
- `phases/phase_N/phase_e2e_config.json` — phase-level E2E test scenarios

**Does NOT produce:** Per-epic `plan.md` or `swarm-manifest.json`. Plans are created downstream by `/plan_phase_epic` (pipeline-aware) or `/plan_from_gh_issue_swarm` (standalone). Swarm manifests are created by `/create_issues_from_plan_swarm`.

**Key Rules:**
- Clusters are atomic within epics
- Epic size: 3-8 features (max 10 for large clusters)
- Epic files are self-contained — `/plan_phase_epic` reads from local `epic.md` files
- On iteration, epic files are updated in place (single source of truth)
- User confirms the epic split before any files are created

---

### 3.0c deepen_time_split

**Purpose:** Review `/time_split` output, write iteration feedback, decide convergence, and optionally extract plugin lessons.

**Pipeline Awareness:**
- On entry: reads `pipeline_state.json`, validates time_split has run. Warns if previous unconsumed feedback exists (will be overwritten).
- On exit: updates `state.deepen_time_split` — sets `feedback_consumed=false` on both self and time_split

**Input:**
| Variable | Source | Description |
|----------|--------|-------------|
| `<phases_dir>` | `$ARGUMENTS` (token 1) | Path to `phases/` directory from `/time_split` |
| `<plugin_source_path>` | `$ARGUMENTS` (token 2, optional) | Path to local eigen plugin source repo. Enables lesson extraction |

**Process:**
1. **Ingest** — read `initiative_summary.json`, all phase manifests, original initiative files
2. **Structural validation** (parallel agents) — DAG correctness, cluster integrity, E2E progressiveness, phase balance, cross-phase dependency accuracy
3. **Content validation** (parallel agents) — blackbox spec completeness, whitebox section relevance
4. **Strategic review** (parallel agents) — architecture-strategist, best-practices-researcher
5. **Skills & learnings** — discover and apply all available skills and documented learnings
6. **Convergence decision** — apply convergence rules (see [Section 0.5](#05-iteration-convergence-cycle)):
   - Zero high-severity findings → converge
   - Iteration limit reached (max 5) → converge
   - Oscillation detected + no non-oscillating high findings → converge
   - Medium finding with high downstream impact → treat as high
7. **Write iteration feedback** — `phases/feedback/deepen_time_split_feedback.json` with convergence decision, previous feedback comparison, findings with downstream impact
8. **Lesson extraction** (if plugin path provided) — write lesson JSONs to `lessons/time_split/`

**Output:**
- `phases/feedback/deepen_time_split_feedback.json` — iteration feedback with convergence decision, findings, downstream impact analysis
- Lesson JSONs in plugin source repo (if path provided)
- Does NOT modify phase manifests or initiative_summary.json

**Key Rules:**
- Feedback file and plugin lessons are completely separate outputs
- Lessons are deduplicated against existing lessons (same affected_phase + category + root_cause)
- Applied lessons (`status: "applied"`) are always skipped
- Always writes a feedback file, even when converged (with zero findings)

---

### 3.0d deepen_space_split

**Purpose:** Review `/space_split` output, write iteration feedback with epic file guidance, decide convergence, and optionally extract plugin lessons.

**Pipeline Awareness:**
- On entry: reads per-phase state in `pipeline_state.json`, validates space_split has run for this phase. Warns if previous unconsumed feedback exists.
- On exit: updates `state.phases[N].deepen_space_split` — sets `feedback_consumed=false` on both self and space_split

**Input:**
| Variable | Source | Description |
|----------|--------|-------------|
| `<phase_dir>` | `$ARGUMENTS` (token 1) | Path to `phases/phase_N/` directory from `/space_split` |
| `<plugin_source_path>` | `$ARGUMENTS` (token 2, optional) | Path to local eigen plugin source repo. Enables lesson extraction |

**Process:**
1. **Ingest** — read `epic_dag.json`, `phase_e2e_config.json`, bootstrap report, read local epic file bodies from the file system
2. **Epic DAG validation** (parallel agents) — DAG correctness, cluster integrity, interface completeness, epic sizing
3. **Epic file quality** (parallel agents) — epic file body completeness (blackbox specs, whitebox guidance, bootstrap context), spec fidelity vs phase manifest
4. **Cross-epic consistency** (parallel agents) — feature coverage (every feature in exactly one epic), interface contract compatibility, E2E coverage
5. **Strategic review** (parallel agents) — architecture-strategist, code-simplicity-reviewer
6. **Skills & learnings** — discover and apply all available skills and documented learnings
7. **Convergence decision** — apply convergence rules (max 3 iterations). Epic file stability weighted: if epic decomposition unchanged, favor convergence. Downstream awareness: if plan_from_gh_issue_swarm already ran, strongly favor convergence.
8. **Write iteration feedback** — `<phase_dir>/feedback/deepen_space_split_feedback.json` with convergence decision, findings, `epic_file_updates` section
9. **Lesson extraction** (if plugin path provided) — write lesson JSONs to `lessons/space_split/`

**Output:**
- `<phase_dir>/feedback/deepen_space_split_feedback.json` — iteration feedback with convergence decision, findings, epic file update guidance
- Lesson JSONs in plugin source repo (if path provided)
- Does NOT modify epic_dag.json or phase_e2e_config.json

---

### 3.0e compound_improve

**Purpose:** Read accumulated **plugin lessons** (not project feedback) and permanently rewrite command prompts in the plugin source repo. See [Section 0.7](#07-two-feedback-systems) for the distinction between project iteration feedback and plugin lessons.

**Input:**
| Variable | Source | Description |
|----------|--------|-------------|
| `<plugin_source_path>` | `$ARGUMENTS` | Path to local eigen plugin source repo (required) |

**Process:**
1. **Load lessons** — read all pending lessons from `lessons/time_split/`, `lessons/bootstrap/`, `lessons/space_split/`, `lessons/plan/`
2. **Pattern analysis** — group by command + affected_phase, identify recurring patterns (strong: 3+ lessons, moderate: 2), detect conflicts
3. **User confirmation** — present patterns, ask which to apply (all / strong only / pick individually)
4. **Rewrite commands** — surgically edit command `.md` files in the source repo (add constraints, reorder logic, strengthen instructions, add steps)
5. **Update metadata** — bump patch version in `plugin.json`, update/create `CHANGELOG.md`
6. **Mark lessons applied** — set `status: "applied"` on contributing lessons

**Output:**
- Modified command `.md` files in plugin source repo
- Updated `plugin.json` (version bump)
- Updated/created `CHANGELOG.md`
- Lessons marked as applied

**Key Rules:**
- Never deletes existing logic — only adds constraints or strengthens instructions
- Each edit is surgical (touches only the affected section)
- HTML comments mark each edit's origin (lesson IDs)
- User must review (`git diff`), commit, and update plugin for changes to take effect
- Applied lessons are never re-processed in future runs

---

### 3.0f bootstrap

**Purpose:** Create incremental project foundation before parallel swarm execution on each phase.

**Pipeline Awareness:**
- Prerequisite: time_split must be completed
- On entry: reads per-phase state in `pipeline_state.json` — converged → STOP, unconsumed feedback → iteration protocol, no feedback + iteration >= 1 → STOP
- On exit: updates `state.phases[N].bootstrap` with iteration count, status, output paths

**Input:**
| Variable | Source | Description |
|----------|--------|-------------|
| `<phase_manifest_path>` | `$ARGUMENTS` (token 1) | A `phase_N_manifest.md` from `/time_split` (includes blackbox specs + whitebox sections) |
| `<target_repo_path>` | `$ARGUMENTS` (token 2) | Path to target repository (may be empty for Phase 1) |

**Process (first run):**
1. **Ingest** — parse phase manifest (features, domains, blackbox specs, whitebox sections)
2. **Detect repo state** — scan target repo: git status, language manifests, directories, entities, config, infrastructure, tests, migrations. Classify each as ABSENT/PRESENT/PARTIAL
3. **Resolve language** — from repo manifest files, whitebox hints, or user prompt
4. **Tooling decisions** (Phase 1 only, skip if repo has tooling) — research best practices via skills, present choices to user (package manager, framework, linting, CI)
5. **Compute delta** — derive required artifacts from manifest, subtract existing → delta
6. **User confirmation** — present delta summary, user approves/adjusts/aborts
7. **Execute** — Wave 0: lead creates scaffold. Wave 1: parallel sub-agents (Contract Generator + Infrastructure Architect)
8. **Verify** — language-appropriate compilation/lint check, auto-fix up to 3 cycles
9. **Report** — generate `bootstrap-report.json`, print summary

**Process (iteration — surgical delta):**
1. Read `phases/phase_N/feedback/deepen_bootstrap_feedback.json`
2. Read `code_change_guidance` section for surgical instructions
3. Honest self-assessment (ACCEPT / PARTIAL / REJECT per finding)
4. Do NOT re-scaffold from scratch. Scan current repo state.
5. Apply only feedback-driven changes: `entities_to_add`, `entities_to_modify`, `config_changes`, `files_to_delete`
6. Do NOT re-run tooling decisions
7. Run verification, commit with `"bootstrap: iteration N — address deepen feedback"`
8. If verification fails: git stash, report to user, offer options
9. Do NOT delete the feedback file

**Output:**
- Committed foundation files in target repo on `dev` branch
- `phases/phase_N/bootstrap-report.json` — delta applied, verification status, entities/contracts created, commits, iteration number, iteration history

**Key Rules:**
- Never writes business logic — stubs only
- Incremental: Phase 1 = heavy (greenfield), Phase 2+ = scan & delta, Phase 4 = possibly no-op
- Every artifact justified by phase manifest
- User confirms delta before any files are written
- Runs before `/space_split` so epic plans reference real paths

---

### 3.0g deepen_bootstrap

**Purpose:** Review `/bootstrap` output, write iteration feedback with code change guidance, decide convergence, and optionally extract plugin lessons.

**Pipeline Awareness:**
- On entry: reads per-phase state in `pipeline_state.json`, validates bootstrap has run for this phase. Warns if previous unconsumed feedback exists.
- On exit: updates `state.phases[N].deepen_bootstrap` — sets `feedback_consumed=false` on both self and bootstrap

**Input:**
| Variable | Source | Description |
|----------|--------|-------------|
| `<target_repo_path>` | `$ARGUMENTS` (token 1) | The bootstrapped target repository |
| `<phase_manifest_path>` | `$ARGUMENTS` (token 2) | The `phase_N_manifest.md` used as bootstrap input |
| `<plugin_source_path>` | `$ARGUMENTS` (token 3, optional) | Path to local eigen plugin source repo. Enables lesson extraction |

**Process:**
1. **Ingest** — read bootstrap-report.json, scan target repo, read phase manifest, load existing lessons
2. **Foundation integrity** (parallel agents) — entity completeness, directory structure, contract alignment, config consistency, infrastructure alignment
3. **Cross-reference validation** (parallel agents) — entity-to-blackbox fidelity, package manifest completeness, verification replay
4. **Strategic review** (parallel agents) — architecture-strategist, code-simplicity-reviewer, security-sentinel
5. **Incremental readiness** (parallel agents) — Phase N+1 preview, cross-artifact consistency
6. **Skills & learnings** — discover and apply all available skills and documented learnings
7. **Convergence decision** — apply convergence rules (max 3 iterations — lower because code changes are expensive). Verification weight: passing verification + zero high findings = converge.
8. **Write iteration feedback** — `phases/phase_N/feedback/deepen_bootstrap_feedback.json` with convergence decision, findings, `code_change_guidance` section (entities_to_add, entities_to_modify, files_to_delete, config_changes)
9. **Lesson extraction** (if plugin path provided) — write lesson JSONs to `lessons/bootstrap/`

**Output:**
- `phases/phase_N/feedback/deepen_bootstrap_feedback.json` — iteration feedback with convergence decision, findings, surgical code change guidance
- Lesson JSONs in plugin source repo (if path provided)
- Does NOT modify bootstrap-report.json

---

### 3.0h Pipeline State Reference

All eight initiative-scale commands interact with `phases/pipeline_state.json`. This section summarizes what each command reads and writes.

| Command | Reads | Writes/Updates | Creates |
|---------|-------|----------------|---------|
| time_split | pipeline_state, deepen feedback | time_split state, phase entries | pipeline_state.json (first run), initiative_summary, phase manifests |
| deepen_time_split | pipeline_state, time_split outputs | deepen_time_split state, feedback_consumed flags | deepen_time_split_feedback.json |
| bootstrap | pipeline_state, deepen feedback, phase manifest | phases[N].bootstrap state | bootstrap-report.json, foundation files |
| deepen_bootstrap | pipeline_state, bootstrap outputs, target repo | phases[N].deepen_bootstrap state, feedback_consumed flags | deepen_bootstrap_feedback.json |
| space_split | pipeline_state, deepen feedback, bootstrap report | phases[N].space_split state, plans init | epic_dag.json, phase_e2e_config.json, epic_M/epic.md |
| deepen_space_split | pipeline_state, space_split outputs, epic files | phases[N].deepen_space_split state, feedback_consumed flags | deepen_space_split_feedback.json |
| plan_phase_epic | pipeline_state, deepen feedback, epic.md, epic_dag | phases[N].plans[M].plan_phase_epic state | epic_M/plan.md, epic_M/feedback/ |
| deepen_plan_phase_epic | pipeline_state, plan.md, epic.md, epic_dag | phases[N].plans[M].deepen_plan_phase_epic state, feedback_consumed flags | deepen_plan_phase_epic_feedback.json |

**Output directory structure:**
```
phases/
  pipeline_state.json                        # Created by time_split, read/updated by ALL
  initiative_summary.json                    # time_split output
  phase_1_manifest.md                        # time_split output
  phase_2_manifest.md                        # time_split output
  feedback/                                  # Initiative-level feedback
    deepen_time_split_feedback.json          # deepen_time_split output
  phase_1/                                   # Per-phase outputs
    bootstrap-report.json                    # bootstrap output
    epic_dag.json                            # space_split output
    phase_e2e_config.json                    # space_split output
    feedback/                                # Phase-level feedback
      deepen_bootstrap_feedback.json         # deepen_bootstrap output
      deepen_space_split_feedback.json       # deepen_space_split output
    epic_1/                                  # Created by space_split
      epic.md                                # Epic content (space_split output)
      plan.md                                # Plan (plan_phase_epic output)
      feedback/                              # Epic-level feedback
        deepen_plan_phase_epic_feedback.json  # deepen_plan_phase_epic output
    epic_2/
      epic.md
      plan.md
      feedback/
        deepen_plan_phase_epic_feedback.json
  phase_2/
    ...same structure...
```

Full schema: see `schemas/pipeline_state.md` in the eigen plugin.

---

### 3.0i plan_phase_epic

**Purpose:** Generate a strategic plan for an epic within a phase, reading from the local epic file. Pipeline-aware with iteration-convergence cycle.

**Pipeline Awareness:**
- Prerequisite: space_split must be converged for this phase
- On entry: reads per-epic plan state in `pipeline_state.json` — converged → STOP, unconsumed feedback → iteration protocol, no feedback + iteration >= 1 → STOP
- On exit: updates `state.phases[N].plans[M].plan_phase_epic`

**Relationship to `plan_from_gh_issue_swarm`:** Nearly identical core logic (same plan generation, complexity levels, Parallelization Strategy format, Gap Analysis). Key differences: reads from local `epic.md` instead of standalone epic file, writes to `epic_M/plan.md` instead of `Plans/`, adds Pipeline Awareness and Iteration Protocol.

**Input:**
| Variable | Source | Description |
|----------|--------|-------------|
| `<phase_number>` | `$ARGUMENTS` (token 1) | Phase number (e.g., `1`) |
| `<epic_number>` | `$ARGUMENTS` (token 2) | Epic number within the phase (e.g., `2`) |

**Process (first run):**
1. **Read local epic file** — `phases/phase_N/epic_M/epic.md` (parse YAML frontmatter + full content), phase manifest, bootstrap report, epic DAG
2. **Parallel Research** — spawn `repo-research-analyst` with epic content as input (identical to plan_from_gh_issue_swarm Step 1)
3. **Determine Complexity** — MINIMAL / STANDARD / COMPREHENSIVE (identical)
4. **Create Plan** — Strategic Overview, Technical Strategy, Implementation Approach, Success Criteria, Project Considerations (identical)
5. **Parallelization Strategy** — Independent Components, Shared Files, Interfaces, Waves, E2E Scenarios (identical)
6. **Gap Analysis** — Sub-phases A (Skills), B (Learnings), C (Review Agents), D (Parallelization Validation) (identical)
7. **Synthesize & Refine** — deduplicate, prioritize, fix critical/medium gaps (identical)
8. **Output** — write to `phases/phase_N/epic_M/plan.md`, create `feedback/` directory, update `pipeline_state.json`
9. **Final Review** — same pre-submission checklist

**Process (iteration):**
1. Read `phases/phase_N/epic_M/feedback/deepen_plan_phase_epic_feedback.json`
2. Honest self-assessment (ACCEPT / PARTIAL / REJECT per finding)
3. Apply accepted `section_changes`, `parallelization_changes`, `research_insights` from `plan_change_guidance`
4. Weave research insights into plan sections naturally (NOT as separate subsections)
5. Re-run Gap Analysis as sanity check
6. Overwrite `plan.md`, update pipeline_state. Do NOT delete the feedback file.

**Output:**
- `phases/phase_N/epic_M/plan.md` — strategic plan with Parallelization Strategy
- Updated `pipeline_state.json` at `state.phases[N].plans[M].plan_phase_epic`

**Key Rules:**
- NO code examples — plan remains strategic and code-free
- Parallelization Strategy is a protected machine-parseable block
- `epic.md` is read-only input — never modified by this command
- Feedback files are owned by `/deepen_plan_phase_epic` — read but never delete

---

### 3.0j deepen_plan_phase_epic

**Purpose:** Review `/plan_phase_epic` output, write iteration feedback with plan change guidance, decide convergence, and optionally extract plugin lessons.

**Pipeline Awareness:**
- On entry: reads per-epic plan state in `pipeline_state.json`, validates plan_phase_epic has run. Warns if previous unconsumed feedback exists.
- On exit: updates `state.phases[N].plans[M].deepen_plan_phase_epic` — sets `feedback_consumed=false` on both self and plan_phase_epic

**Relationship to `deepen_plan`:** Nearly identical analysis engine (same skills discovery, learnings check, per-section research, review agent spawning). Key differences: never modifies the plan file (all findings go to structured feedback JSON), adds Pipeline Awareness and Convergence Protocol, includes `plan_change_guidance` in feedback for plan_phase_epic's next iteration.

**Input:**
| Variable | Source | Description |
|----------|--------|-------------|
| `<phase_number>` | `$ARGUMENTS` (token 1) | Phase number |
| `<epic_number>` | `$ARGUMENTS` (token 2) | Epic number within the phase |
| `<plugin_source_path>` | `$ARGUMENTS` (token 3, optional) | Path to local eigen plugin source repo. Enables lesson extraction |

**Process:**
1. **Parse plan structure** — read `plan.md`, extract sections, create section manifest. Also read `epic.md`, phase manifest, bootstrap report, `epic_dag.json` for context
2. **Discover & apply skills** — same 5-source discovery, same parallel spawning
3. **Discover & apply learnings** — same `docs/solutions/` primary location, same filtering
4. **Per-section research** — same Explore agents, Context7, WebSearch
5. **Discover & run ALL review agents** — same 6-source discovery, same "run ALL" principle, same "20-40 parallel agents is fine"
6. **Synthesize** — same collection, categorization, deduplication. Adds `downstream_impact` per finding (medium finding causing high downstream impact in `create_issues_from_plan_swarm` = treat as high)
7. **Convergence decision** — max 3 iterations, oscillation detection, downstream impact escalation
8. **Write feedback file** — `phases/phase_N/epic_M/feedback/deepen_plan_phase_epic_feedback.json` with convergence, findings, `plan_change_guidance` (section_changes, parallelization_changes, research_insights)
9. **Lesson extraction** (if plugin path provided) — write lesson JSONs to `lessons/plan/`

**Output:**
- `phases/phase_N/epic_M/feedback/deepen_plan_phase_epic_feedback.json` — iteration feedback with convergence decision, findings, plan change guidance
- Lesson JSONs in plugin source repo (if path provided)
- Does NOT modify `plan.md`

**Key Rules:**
- NEVER modifies the plan file — all findings go to the feedback file
- `plan_change_guidance.research_insights` is the pipeline-aware equivalent of `deepen_plan`'s `### Research Insights` subsections
- Convergence decided by this command only — max 3 iterations
- Plugin lessons and project feedback are separate outputs

---

### 3.1 plan_from_gh_issue_swarm

**Purpose:** Transform a local epic file into a strategic development plan.

**Input:**
| Variable | Source | Description |
|----------|--------|-------------|
| `<epic_id>` | `#$ARGUMENTS` | The local epic ID to plan |
| `$GITHUB_PROJECT` | Environment | Repository path (owner/repo) |

**Process:**
1. **Detect language** from manifest files (pyproject.toml, package.json, go.mod, Cargo.toml, etc.)
2. **Read local epic file** from the file system
3. **Research codebase** via `repo-research-analyst` subagent
4. **Determine complexity** (MINIMAL / STANDARD / COMPREHENSIVE)
5. **Generate plan** with sections: Strategic Overview, Technical Strategy, Implementation Approach, Success Criteria, Project Considerations
6. **Generate Parallelization Strategy** (STANDARD/COMPREHENSIVE only) with:
   - Independent Components (with `estimated_files`)
   - Shared Files Map
   - Interfaces Between Components (`provider`, `consumers`, `contract`, `stub_file`)
   - Execution Waves
   - **E2E Test Scenarios** (describes end-to-end user flows)
7. **Gap Analysis** (STANDARD/COMPREHENSIVE only) — spawns 4 parallel subagents: Skills Gap, Learnings Gap, Review Agents Gap, Parallelization Strategy Validation

**Output:**
- Local plan file at `Plans/plan-for-epic-<N>.md`

**Key rules:**
- NO code examples in the plan — only strategic guidance
- Each file appears in exactly ONE component's `estimated_files` OR in `Shared Files Map`
- Each `stub_file` must be within its provider's `estimated_files`
- Execution waves must form a valid DAG for `blocked_by`
- **Every major acceptance criterion must map to at least one E2E test scenario**

**E2E Test Scenarios format in the plan:**
```yaml
### E2E Test Scenarios
- scenario: "user_registration_flow"
  description: "User registers with email, verifies account, logs in"
  components_involved: ["AuthService", "EmailService"]
  acceptance_criteria_ref: "AC-1"

- scenario: "payment_checkout_flow"
  description: "User adds items, enters payment, receives confirmation"
  components_involved: ["CartService", "PaymentProcessor", "OrderService"]
  acceptance_criteria_ref: "AC-3"
```

---

### 3.2 create_issues_from_plan_swarm

**Purpose:** Decompose plan into task files + machine-readable manifest.

**Input:**
| Variable | Source | Description |
|----------|--------|-------------|
| `<plan_path>` | `$ARGUMENTS` (token 1) | Path to plan file (e.g., `Plans/plan-for-epic-<N>.md` or `phases/phase_N/epic_M/plan.md`) |
| `<parent_issue_number>` | `$ARGUMENTS` (token 2) | Parent epic ID |

**Process:**
1. **Read plan** from local file at `<plan_path>`
2. **Parse Parallelization Strategy** section (Independent Components, Shared Files, Interfaces, Waves, E2E Scenarios)
3. **Analyze task boundaries** — enforce file-disjoint ownership
4. **Build dependency graph** — `blocked_by` (DAG) + `interface_deps` (may be circular)
5. **Compute execution waves** via topological sort
6. **Generate task specifications** — title, context, acceptance criteria, file ownership, dependencies
7. **Create task files** at `phases/phase_N/epic_M/tasks/task_NNN.md`
8. **Generate `swarm-manifest.json`** with full task metadata
9. **Extract E2E Test Scenarios** from plan, transform component names → issue numbers, populate `e2e_config`
10. **Validate manifest** against 11 rules
11. **Commit manifest** to repository

**Output: `swarm-manifest.json` schema:**
```json
{
  "parent_issue_number": 100,
  "plan_file": "Plans/plan-for-epic-100.md",
  "created_at": "2026-02-20T15:30:00Z",
  "tasks": [
    {
      "issue_number": 101,
      "summary": "Implement AuthModels",
      "phase": 1,
      "model": "sonnet",
      "blocked_by": [],
      "interface_deps": [],
      "files_owned": ["src/auth/models.py"],
      "test_files_owned": ["tests/test_auth_models.py"]
    },
    {
      "issue_number": 102,
      "summary": "Implement LoginHandler",
      "phase": 1,
      "model": "sonnet",
      "blocked_by": [],
      "interface_deps": [
        {
          "provider_issue": 101,
          "interface_name": "UserModel",
          "stub_file": "src/auth/models.py",
          "contract": "verify_password(plain: str) -> bool"
        }
      ],
      "files_owned": ["src/auth/login.py"],
      "test_files_owned": ["tests/test_login.py"]
    }
  ],
  "shared_files": ["src/routes.py", "src/__init__.py"],
  "execution_waves": [
    {"wave": 1, "tasks": [101, 102]},
    {"wave": 2, "tasks": ["INTEGRATION"], "type": "integration"}
  ],
  "e2e_config": {
    "e2e_test_dir": "tests/e2e/",
    "e2e_test_command": "python -m pytest tests/e2e/ -v",
    "e2e_marker": "@pytest.mark.e2e",
    "e2e_output_format": "--junitxml=e2e-report.xml",
    "e2e_file_pattern": "test_e2e_*.py",
    "e2e_setup_command": null,
    "e2e_scenarios": [
      {
        "name": "user_registration_flow",
        "description": "User registers, verifies email, logs in",
        "components_involved": [101, 102],
        "acceptance_criteria_ref": "AC-1"
      }
    ],
    "max_iterations": 3,
    "fix_budget_per_worker": 2,
    "max_total_fix_spawns": 8
  }
}
```

**`e2e_config` fields:**

| Field | Type | Description | Source |
|-------|------|-------------|--------|
| `e2e_test_dir` | string | Directory for E2E tests (isolated from workers) | Language profile |
| `e2e_test_command` | string | Command to run E2E tests | Language profile |
| `e2e_marker` | string | How E2E tests are tagged | Language profile |
| `e2e_output_format` | string | Output format flags for parseable results | Language profile |
| `e2e_file_pattern` | string | File naming pattern for E2E tests | Language profile |
| `e2e_setup_command` | string/null | Optional setup before E2E runs | Project-specific |
| `e2e_scenarios` | array | User flows to validate (with `components_involved` as issue numbers) | Plan transformation |
| `max_iterations` | int | Max fix loop iterations (default: 3) | Fixed default |
| `fix_budget_per_worker` | int | Max fix attempts per worker (default: 2) | Fixed default |
| `max_total_fix_spawns` | int | Global cap on fix worker spawns (default: 8) | Fixed default |

**Manifest validation rules:**
1. No circular `blocked_by` (must be DAG)
2. No file ownership overlaps
3. All `blocked_by` references are valid issue numbers
4. Wave 1 has at least one task
5. Integration task exists in final wave
6. All mentioned files accounted for
7. Interface deps: provider exists, `stub_file` in provider's `files_owned`
8. Multiple interfaces per `stub_file` must have same provider
9. **`e2e_config` present with at least one scenario** (mandatory — fail-fast if missing)
10. **E2E directory isolation**: no task's `test_files_owned` entry starts with `e2e_test_dir`
11. **E2E scenario references valid**: every issue number in `components_involved` exists in `tasks[]`

---

### 3.3 orchestrate_swarm

**Purpose:** Central orchestration engine — the Staff Engineer / Tech Lead.

**Input:**
| Variable | Source | Description |
|----------|--------|-------------|
| `<parent_issue_number>` | `$ARGUMENTS` (token 1) | Parent epic local ID |
| `<integration_branch>` | `$ARGUMENTS` (token 2) | Branch name for the worktree (e.g., `feat/auth-module`) |
| `<manifest_path>` | `$ARGUMENTS` (token 3) | Path to `swarm-manifest.json` |
| `$GITHUB_PROJECT` | Environment | Repository path |

**Orchestrator state variables:**

| Variable | Description | Persisted In |
|----------|-------------|-------------|
| `<active_teammates>` | Map of worker name → task ID | `[WAVE-STATUS]` task |
| `<completed_tasks>` | Set of completed task IDs | `[WAVE-STATUS]` task |
| `<current_wave>` | Current execution wave number | `[WAVE-STATUS]` task |
| `<integration_requests>` | Collected shared file changes | `[INTEGRATION-REQUEST]` tasks |
| `<task_to_swarm_id>` | Manifest issue → task system ID | `[WAVE-STATUS]` task |
| `<decision_precedents>` | Previous decisions for consistency | `[QUESTION]` tasks (completed) |
| `<interface_providers>` | Map of stub_file → provider info | Re-derived from manifest |
| `<stubs_ready>` | Set of confirmed ready stubs | `[STUB-READY]` tasks |
| `<plan_content>` | Plan file content | Local file (path from manifest `plan_file`) |
| `<worktree_abs_path>` | Absolute path to the git worktree | `[WAVE-STATUS]` task |
| `<integration_branch>` | Branch name for the worktree | `[WAVE-STATUS]` task |
| `<manifest_path>` | Manifest file path | `[WAVE-STATUS]` task |
| `<detected_tech_stack>` | Detected language + framework | `[WAVE-STATUS]` task |
| `<relevant_skills>` | Skills discovered for worker prompts | `[WAVE-STATUS]` task |
| `<e2e_iteration>` | Current E2E fix loop iteration (0 = not started) | `[WAVE-STATUS]` task |
| `<e2e_status>` | E2E phase status | `[WAVE-STATUS]` task |
| `<fix_budgets>` | Per-worker remaining fix budget | `[WAVE-STATUS]` task |
| `<total_fix_spawns>` | Global fix worker spawn counter | `[WAVE-STATUS]` task |
| `<stuck_tests>` | Tests with same error 2+ consecutive iterations | Derived from `[E2E-RESULT]` tasks |
| `<e2e_failures_history>` | Array of per-iteration failure details | `[E2E-RESULT]` tasks |

**`e2e_status` values:** `not_started` | `running` | `fix_loop` | `completed` | `escalated`

**Lifecycle phases:**

```
Phase 0: Setup & Validation
  0.0 Parse arguments (parent_issue_number, integration_branch, manifest_path)
  0.1 Fetch parent issue context
  0.1.5 Create integration worktree at .claude/worktrees/<branch-slug>
  0.2 Read and validate swarm-manifest.json (including e2e_config)
  0.3 Derive interface_providers map
  0.4 Create team "swarm-<parent_issue_number>"
  0.5 Detect tech stack and discover relevant skills from language-profiles.md

Phase 1: Create Tasks in Shared List
  1.1 Create [WORK] task per manifest task
  1.2 Wire blocked_by dependencies (NOT interface_deps)
  1.3 Create [INTEGRATION] task blocked by all [WORK] tasks
  1.4 Create [E2E-VALIDATION] task blocked by [INTEGRATION]
  1.5 Create [WAVE-STATUS] task for state persistence (with E2E fields)

Phase 2: Spawn Teammates (Wave by Wave)
  IF wave has BOTH providers and consumers:
    2A: Spawn providers + independent tasks
    2B: Wait for all "Stub ready" messages → spawn consumers
  ELSE:
    Spawn all tasks in wave simultaneously

Phase 3: React and Respond (Event-Driven)
  Handle incoming messages:
    [QUESTION] → Decide autonomously OR forward to user
    [BLOCKER]  → Resolve ownership/dependency issues
    Progress   → Log and monitor
    Blocker resolved → Notify dependent tasks
    Integration request → Persist for Phase 4
    Completion → Update state, check wave completion

Phase 4: Integration
  4.1   Prepare integration context
  4.1.5 Verify all stubs replaced with real implementations
  4.1.6 Verify consumer Phase C completion
  4.2   Spawn integrator with all integration requests
  4.3   Monitor integrator
  4.4   Run full test suite

Phase 4.4.5: Shut Down Integrator
  Free resources before E2E phase

Phase 4.5: E2E Validation
  4.5.1 Initialize E2E state (iteration=1, budgets, status=running)
  4.5.2 Spawn e2e-tester (model: opus, mode: write_and_run)
  4.5.3 Process E2E results:
        ALL pass → Phase 5
        Deterministic failures → Phase 4.6

Phase 4.6: E2E Fix Loop (up to max_iterations)
  4.6.1 Failure attribution (4-tier system)
  4.6.2 Spawn fix workers per attributed failure
  4.6.3 Wait for fixes, handle CROSS-BOUNDARY and TEST-ISSUE
  4.6.4 Shut down fix workers
  4.6.5 Re-run E2E (spawn e2e-tester, model: sonnet, mode: run_only)
  4.6.6 Check progress → continue loop, early terminate, or escalate to user

Phase 5: Shutdown & Cleanup
  5.1 Send shutdown requests to all teammates
  5.2 Verify no active members remain
  5.3 Delete team resources
  5.4 Report results to user (including E2E summary)
```

**Decision framework:**

| Decision Type | Who Decides | Examples |
|---------------|-------------|---------|
| `task_classification` | Leader (autonomous) | NEW_FEATURE vs ENHANCEMENT vs REFACTORING |
| `coverage_decision` | Leader (autonomous) | Extend existing test? Create new? Skip? |
| `test_placement` | Leader (autonomous) | Which test file to use |
| `final_review` | Leader (autonomous) | Approve/reject test designs |
| `design_decision` | User (via AskUserQuestion) | Architecture patterns, API design |
| E2E failure attribution | Leader (autonomous, Tiers 1-2) or User (Tier 3) | Which worker should fix a failing E2E test |

---

### 3.4 design_validation_tests_swarm

**Purpose:** Phase A of worker execution — design validation tests (TDD).

**Input:**
| Variable | Source | Description |
|----------|--------|-------------|
| `<task_id>` | `#$ARGUMENTS` | Task ID for this task |
| `<my_files_owned>` | `swarm-manifest.json` | Source files owned |
| `<my_test_files_owned>` | `swarm-manifest.json` | Test files owned |
| `<blocked_by>` | `swarm-manifest.json` | Tasks that must complete first |
| `<my_interface_deps>` | `swarm-manifest.json` | Interface dependencies |

**Workflow with checkpoints:**

| Checkpoint | Phase | What Happens |
|------------|-------|-------------|
| `post-manifest` | 1 | Manifest read, ownership established |
| `post-task-analysis` | 2 | Issue + plan fetched and analyzed |
| `post-classification` | 2.5 | Task classified (leader consulted) |
| `post-discovery` | 2.7 | Existing tests discovered, coverage mapped |
| `post-test-batch` | 3 | Tests created per task type |
| `post-tracker` | 4.1 | Tracker JSON generated |
| `post-commit` | 4.3 | Tests committed to branch |

**Task classification determines test strategy:**

| Task Type | Test Phase | Marker | Tests Should... |
|-----------|-----------|--------|-----------------|
| `NEW_FEATURE` | Phase 3A (validation) | `tdd_validation` | FAIL (code not written yet) |
| `ENHANCEMENT` | Phase 3A (validation) | `tdd_validation` | FAIL (enhancement not implemented) |
| `REFACTORING` | Phase 3B (existing) | `tdd_unit` | PASS (existing behavior preserved) |
| `INTERFACE_ABSTRACTION` | Phase 3C (contract) | `tdd_contract` | FAIL (interfaces don't exist yet) |
| E2E (post-integration) | N/A | `e2e` | Written by e2e-tester, NOT workers |

**E2E test boundary:** Workers do NOT write E2E tests. E2E tests are written by the dedicated `e2e-tester` teammate after all workers complete and integration finishes. Workers focus exclusively on `tdd_validation`, `tdd_contract`, and `tdd_unit` tests. The `e2e` marker is documented here for awareness only — workers should never apply it.

**Test quality gate (before writing any test):**
> "If this test were deleted, would we risk a real bug going undetected in production?"
> - YES → create the test
> - NO → do NOT create (tautological)

**Output: Tracker JSON** at `tests/tracker-files/validation_tests_tracker_<task_id>.json`:
```json
{
  "task_id": "101",
  "task_type": "NEW_FEATURE",
  "detected_language": "python",
  "validation_tests": [
    {
      "test_file": "tests/test_auth.py",
      "test_name": "test_login_succeeds",
      "markers": ["tdd_validation"],
      "status": "CREATED_NEW"
    }
  ],
  "tests_not_created": [
    {
      "scenario": "User login with session",
      "reason": "ALREADY_COVERED",
      "existing_test": "tests/test_session.py::test_login_creates_session"
    }
  ],
  "test_command": "python -m pytest tests/ -m tdd_validation",
  "all_tests_passing": false
}
```

---

### 3.5 code_from_validation_tests_swarm

**Purpose:** Phase B of worker execution — implement code to make validation tests pass.

**Input:**
| Variable | Source | Description |
|----------|--------|-------------|
| `<task_id>` | `#$ARGUMENTS` | Task ID |
| Tracker JSON | `tests/tracker-files/validation_tests_tracker_<task_id>.json` | Tests to satisfy |
| `<my_files_owned>` | `swarm-manifest.json` | Files to implement in |
| `<my_interface_deps>` | `swarm-manifest.json` | Available interfaces |

**Implementation phases:**

| Phase | Purpose | Key Actions |
|-------|---------|-------------|
| 1 | Load context | Read tracker, explore codebase, create plan |
| 2 | Implementation loop | Iteratively implement code to pass validation tests |
| 3 | Unit tests | Create focused unit tests for new/modified code |
| 4 | Final validation | Run all tests, lint, typecheck, verify ownership |
| C | Re-validate (conditional) | If `interface_deps`: re-run against real implementations |
| 5 | Commit & signal | Final commit, mark task complete, notify leader |

**Interface provider actions during Phase B:**
1. Implement real code in the `stub_file`
2. OVERWRITE stub entirely with real implementation
3. Immediately send "Blocker resolved" with "Stub replaced: `<stub_file>`"

**Interface consumer Phase C trigger:**
- Leader sends: "Interface `<name>` real implementation available — run Phase C"
- Consumer re-runs all tests against real implementation
- If tests fail due to **contract mismatch** → create `[BLOCKER]`
- If tests fail due to **behavioral assumption** → fix own code

**Post-Completion E2E Fix Readiness:**

Before signaling completion, workers must ensure their working notes are thorough at the `post-final-commit` checkpoint, including:
- All files modified and WHY
- Key implementation decisions and their rationale
- Integration points with other components
- Any known edge cases or limitations
- Interface contracts they depend on or provide

This is critical because workers may be **respawned in fix mode** during the E2E fix loop (Phase 4.6). If respawned, the worker receives:
- The specific E2E failure (test name, error, stack trace)
- Their owned files list
- A `[E2E-FIX]` task ID
- Instructions to read working notes first

**Fix mode workflow (simplified):**
1. Read working notes to restore context
2. Analyze the E2E failure
3. Fix the root cause in owned files ONLY
4. If fix requires files outside ownership → report as **CROSS-BOUNDARY**
5. If E2E test itself appears wrong → report as **TEST-ISSUE**
6. Run own validation/unit tests to confirm no regressions
7. Commit the fix and signal completion

---

### 3.6 e2e_validation_swarm

**Purpose:** Write and run end-to-end tests that validate the assembled feature across component boundaries.

**Executed by:** `e2e-tester` teammate (spawned by orchestrator in Phase 4.5)

**Input:**
| Variable | Source | Description |
|----------|--------|-------------|
| `<parent_issue_number>` | Spawn prompt | Parent epic local ID |
| MODE | Spawn prompt | `write_and_run` (iteration 1) or `run_only` (iteration 2+) |
| ITERATION | Spawn prompt | Current iteration number |
| `e2e_config` | `swarm-manifest.json` | E2E configuration (test dir, command, scenarios, etc.) |

**Two operational modes:**

| Mode | When | Model | What Happens |
|------|------|-------|-------------|
| `write_and_run` | Iteration 1 | **Opus** | Write E2E tests from scenarios + run them |
| `run_only` | Iteration 2+ | **Sonnet** | Re-run existing E2E tests (no new tests written) |

**Workflow phases:**

```
Phase 0: Determine mode (write_and_run or run_only)
Phase 1: Load context (manifest, issue, plan, existing tests)
Phase 2: Design E2E tests (write_and_run ONLY — skipped in run_only)
Phase 3: Run E2E tests (both modes)
Phase 4: Report results + create [E2E-RESULT] task
Phase 5: Signal completion to leader
```

**Phase 2 (write_and_run): How E2E tests are written:**
- For each scenario in `e2e_config.e2e_scenarios[]`:
  - Check if already covered by existing E2E test → SKIP if yes
  - Write a test exercising the **full user flow** described in the scenario
  - Use the application's test client/HTTP API — NOT internal unit-level imports
  - Mock external services only (third-party APIs), NOT internal components
  - Apply `e2e_marker` (e.g., `@pytest.mark.e2e`)
- After scenarios: check acceptance criteria from parent issue, write additional tests for uncovered flows
- Verify tests can be collected without syntax/import errors
- Commit test files: `git add <e2e_test_dir> && git commit`

**Phase 3: Flaky test detection (mandatory for ALL failing tests):**

For each failing test, retry up to 2 times individually:
- **Passes on retry** → classified as `FLAKY` (intermittent — leader does NOT spawn fix workers)
- **Fails on all 3 attempts** (initial + 2 retries) → classified as `DETERMINISTIC` (real bug — fix workers assigned)

**File ownership:** The e2e-tester exclusively owns `<e2e_config.e2e_test_dir>`. No worker can modify files in this directory. The e2e-tester cannot modify files outside this directory.

**Compaction resilience — 4 checkpoints:**

| Checkpoint | When | What's Persisted |
|------------|------|-----------------|
| `post-context-load` | After loading manifest + issue + existing tests | e2e_config summary, iteration, mode, existing test list |
| `post-test-design` | After writing tests (write_and_run only) | Test files created, scenario-to-test mapping |
| `post-test-run` | After running tests + retries | Total/passed/failed/flaky counts, per-failure details |
| `post-report` | After creating [E2E-RESULT] task + commit | Task ID, commit hash |

Working notes file: `swarm_working_notes/working-notes-e2e-<parent_issue_number>.md`

**Output: [E2E-RESULT] task:**
```
Subject: [E2E-RESULT] Iteration 1 — 42/45 passed
Description:
  Iteration: 1
  Total: 45
  Passed: 42
  Failed: 2
  Flaky: 1
  Failures:
  - test_auth_session_timeout | TimeoutError | src/auth/session.ext, src/cache/redis.ext | DETERMINISTIC
  - test_payment_retry | AssertionError | src/payment/processor.ext | DETERMINISTIC
  - test_dashboard_race | RuntimeError | src/dashboard/api.ext | FLAKY
```

---

### 3.7 review_swarm_pr

**Purpose:** Post-swarm quality gate — scope-aware code review that spawns review agents, triages findings, and creates fixup issues with swarm-compatible format.

**Input:**
| Variable | Source | Description |
|----------|--------|-------------|
| `<parent_issue_number>` | `$ARGUMENTS` (token 1) | Parent epic local ID |
| `<integration_branch>` | `$ARGUMENTS` (token 2) | Branch the swarm worked on |
| `<pr_number_or_url>` | `$ARGUMENTS` (token 3) | PR number or URL |
| `<manifest_path>` | `$ARGUMENTS` (token 4) | Path to swarm manifest |

**Process:**

1. **Setup** — Validate PR exists and is open. Create a review worktree. Read manifest to determine scope (all `files_owned` + `shared_files`). Fetch PR diff filtered to scope files only. Detect tech stack.

2. **Spawn review agents** (5-8 in parallel, based on tech stack and diff size):
   - **Always:** `security-sentinel`, `architecture-strategist`, `code-simplicity-reviewer`, `data-integrity-guardian`, `test-practices-researcher-no-vs`
   - **Conditional:** `vs-python-reviewer` (Python), `performance-oracle` (large diff or perf criteria), `pattern-recognition-specialist` (diff > 500 lines)
   - Each agent receives the scoped diff + scope context with strict rules: only flag in-scope files, only flag acceptance-criteria-related gaps.

3. **Collect and triage findings** — Each finding has: Severity (P1/P2/P3), Category, In-Scope Justification, Location (file:line), Impact, Proposed Fix, Effort. Filter out-of-scope and vague findings. Deduplicate across agents. Present to user for approval.

4. **Decompose findings into swarm-executable tasks** — For each approved finding:
   - Derive `files_owned` and `test_files_owned` from the finding location
   - Detect file ownership conflicts between findings → serialize with `blocked_by`
   - Assign execution waves via topological sort (continue numbering from original manifest)
   - Select model tier (score ≥ 4 → opus, else sonnet)
   - Create task files with `[REVIEW]` prefix

5. **Update manifest** — Mark original tasks as `"status": "completed"`. Append new finding tasks with `"status": "pending"`. Append execution waves. Merge E2E config with new scenarios for P1 findings. Commit updated manifest.

6. **Post review** — Submit PR review via git/PR tooling with inline comments at finding locations. Post summary comment on parent epic.

**Output:**
- Task files with `[REVIEW]` prefix for each approved finding
- Updated `swarm-manifest.json` (original tasks completed, new finding tasks pending)
- PR review with inline comments
- Summary comment on parent issue

**Key rules:**
- **Scope is king** — never flag out-of-scope files or missing features not in acceptance criteria
- **Swarm-compatible** — created issues follow the exact format of `create_issues_from_plan_swarm` (with `files_owned`, `test_files_owned`, `blocked_by`)
- **File ownership exclusivity** — no two finding tasks can own the same file (conflicts resolved by serializing)
- **Fixup swarm ready** — updated manifest can be fed directly to `/orchestrate_swarm` to address findings

---

## 4. Core Concepts

### 4.1 File Ownership

**The fundamental rule enabling parallel execution: no two workers edit the same file.**

Every file in the project falls into exactly one category:

| Category | Who Can Modify | How Enforced |
|----------|---------------|-------------|
| `files_owned` by Task N | Only worker-N | Manifest validation + runtime checks |
| `test_files_owned` by Task N | Only worker-N | Manifest validation + runtime checks |
| `shared_files` | Only the integrator (Phase 4) | Workers send integration requests |
| `e2e_test_dir` | Only e2e-tester (Phase 4.5) | Manifest validation rule #10 |
| Unowned files | Nobody (create `[BLOCKER]` to request) | Leader grants or denies |

**Before every file modification, a worker must verify:**
```
Is file in my files_owned?      → YES: proceed
Is file in my test_files_owned? → YES: proceed (tests only)
Is file in e2e_test_dir?        → NO: off-limits (e2e-tester only)
Is file in shared_files?        → NO: send integration request, do NOT modify
Is file unaccounted for?        → NO: create [BLOCKER], WAIT for leader
```

**Commit discipline:**
```bash
# CORRECT — explicit file listing
git add src/auth/models.py tests/test_auth_models.py
git commit -m "feat(#101): Implement UserModel"

# WRONG — could stage other workers' files
git add .
git add -A
```

---

### 4.2 Dependency Types

#### `blocked_by` — Full Implementation Dependency

```
Task #102 has blocked_by: [101]
```

- Task #102 **cannot start** until Task #101 is 100% complete
- Enforces **wave segregation**: #102 must be in a later wave than #101
- Must form a **DAG** (Directed Acyclic Graph) — no circular dependencies
- Used when: consumer needs provider's **full implementation**, not just an interface

#### `interface_deps` — Interface-Only Dependency

```
Task #102 has interface_deps: [{
  provider_issue: 101,
  interface_name: "UserModel",
  stub_file: "src/auth/models.py",
  contract: "verify_password(plain: str) -> bool"
}]
```

- Task #102 **can start in the same wave** as #101
- Provider (#101) generates stub first, consumer (#102) codes against it
- **Circular dependencies allowed** (A provides interface to B, B provides interface to A)
- Used when: a well-defined interface contract exists with a `stub_file` + `contract`

#### Decision table: which dependency type to use

| Situation | Dependency Type | Why |
|-----------|----------------|-----|
| B needs A's entire database schema | `blocked_by` | No stub possible for schema |
| B calls A's interface methods | `interface_deps` | Contract is clear, stub works |
| B reads A's configuration output | `blocked_by` | Output unknown until A runs |
| B implements A's interface consumer | `interface_deps` | DI pattern enables mock testing |
| A and B share a utility function | Neither — move to `shared_files` | Both need it, integration handles it |

---

### 4.3 Execution Waves

Waves determine the order of teammate spawning:

```
Wave 1: Tasks with blocked_by: []  (no blockers — start immediately)
Wave 2: Tasks whose blocked_by are ALL in Wave 1
Wave 3: Tasks whose blocked_by are ALL in Waves 1-2
...
Final Wave: INTEGRATION (blocked by ALL other waves)
```

**Important:** `interface_deps` do NOT affect wave placement. A consumer with only `interface_deps` (no `blocked_by`) can be in Wave 1 alongside its provider.

**Wave spawning logic within a single wave:**
```
IF wave contains BOTH interface providers AND consumers:
  Sub-phase A: Spawn providers + independent tasks
  Wait for "Stub ready" from ALL providers
  Sub-phase B: Spawn consumer tasks

ELSE:
  Spawn all tasks simultaneously
```

---

### 4.4 Interface Stubs

The stub lifecycle enables parallel execution between providers and consumers:

```
Timeline:
  T=0  Provider spawns → generates stub file (Protocol/ABC/interface with empty bodies)
  T=1  Provider commits stub → sends "Stub ready" to leader
  T=2  Leader confirms → spawns consumer
  T=3  Consumer imports from stub, creates mock/fake for testing
  T=4  Consumer implements code against interface, tests pass with mock
  ...  (provider implements real code in parallel)
  T=N  Provider replaces stub with real implementation → sends "Blocker resolved"
  T=N+1 Leader notifies consumer → consumer runs Phase C (re-validates against real impl)
```

**Language-specific stub mechanisms:**

| Language | Stub Type | Verification Command | Stub Lifecycle |
|----------|-----------|---------------------|---------------|
| Python | `Protocol` / `ABC` with `...` bodies | `python -c "from module import Class"` | Overwrite entirely |
| TypeScript | `interface` declaration | `tsc --noEmit` | Overwrite entirely |
| Go | N/A — consumers define own interfaces | N/A | No stubs needed |
| Rust | `trait` definition | `cargo check` | Add `impl` alongside (never overwrite) |
| .NET | `interface` in class file | `dotnet build` | Implement in separate class |

---

### 4.5 Compaction Resilience

Context compaction (when conversation grows too large) can lose in-memory state. The system survives this via two mechanisms:

**A. Task System Persistence (Orchestrator)**

| State | Persisted As | Reconstruction |
|-------|-------------|---------------|
| `completed_tasks` | `[WORK]` tasks with status=completed | Parse "Issue: #NNN" from descriptions |
| `current_wave` | `[WAVE-STATUS]` "Wave: N" | Read description field |
| `active_teammates` | `[WAVE-STATUS]` "Active: ..." | Parse comma-separated list |
| `task_to_swarm_id` | `[WAVE-STATUS]` "Task map: ..." | Parse "101->t1, 102->t2" |
| `integration_requests` | `[INTEGRATION-REQUEST]` tasks (pending) | Read descriptions |
| `stubs_ready` | `[STUB-READY]` tasks (completed) | Extract stub_file |
| `decision_precedents` | `[QUESTION]` tasks (completed, with "DECISION:") | Parse decision + reasoning |
| `e2e_iteration` | `[WAVE-STATUS]` "E2E iteration: N" | Read field (default 0) |
| `e2e_status` | `[WAVE-STATUS]` "E2E status: ..." | Read field (default not_started) |
| `fix_budgets` | `[WAVE-STATUS]` "Fix budgets: 101:2, 102:1" | Parse pairs |
| `e2e_failures_history` | `[E2E-RESULT]` tasks (completed) | Parse iteration, totals, failures |
| `detected_tech_stack` | `[WAVE-STATUS]` "Tech stack: ..." | Re-derive from `language-profiles.md` if missing |
| `relevant_skills` | `[WAVE-STATUS]` "Relevant skills: ..." | Re-derive from tech stack + skill lookup if missing |
| `worktree_abs_path` | `[WAVE-STATUS]` "Worktree path: ..." | Re-derive from integration branch slug if missing |
| `integration_branch` | `[WAVE-STATUS]` "Integration branch: ..." | Read field |
| `manifest_path` | `[WAVE-STATUS]` "Manifest path: ..." | Read field |

**B. Working Notes (Teammates)**

File: `swarm_working_notes/working-notes-<task_id>.md`

```markdown
# Working Notes — 101
## Phase: design_validation_tests
## Last Checkpoint: post-discovery
## Next Step: Create validation tests for login scenarios.
             Coverage mapping shows 2 NOT_COVERED, 1 PARTIALLY_COVERED.

## Ownership
- Files owned: src/auth/models.py
- Test files owned: tests/test_auth_models.py

## Coverage Mapping
- login_succeeds: NOT_COVERED
- login_fails_invalid_password: NOT_COVERED
- session_management: ALREADY_COVERED (tests/test_session.py::test_login_session)
```

On resume: read working notes → restore context → continue from "Next Step".

**C. E2E Tester Working Notes**

File: `swarm_working_notes/working-notes-e2e-<parent_issue_number>.md`

Iteration-aware: if the iteration number in the file matches the spawn prompt, it's compaction recovery (resume from checkpoint). If different, it's a new iteration (start fresh).

---

### 4.6 E2E Validation and the Fix Loop

After all workers complete and integration finishes, the system runs a **mandatory E2E validation phase** that tests the assembled feature end-to-end.

#### Phase 4.5: E2E Validation

1. **Initialize state**: `e2e_iteration=1`, `e2e_status=running`, `fix_budgets` from manifest defaults
2. **Spawn `e2e-tester`** (model: opus, mode: write_and_run)
3. **E2E tester writes tests** from `e2e_config.e2e_scenarios` and runs them
4. **Process results**:
   - ALL deterministic tests pass → `e2e_status=completed` → Phase 5
   - Deterministic failures exist → `e2e_status=fix_loop` → Phase 4.6

#### Phase 4.6: Fix Loop (up to `max_iterations`)

**4-tier failure attribution system:**

| Tier | Method | Confidence | When Used |
|------|--------|-----------|-----------|
| 1 | Stack trace file matching vs `files_owned` | HIGH | Files in stack match a worker's ownership |
| 2 | Semantic test/task name matching | MEDIUM | Test name keywords match task summary |
| 3 | User escalation | LOW | No confident attribution possible → AskUserQuestion |
| 4 | Cross-boundary analysis | SPECIAL | Stack spans 2+ workers' files |

**Iteration behavior:**

| Iteration | Name | Fix Worker Mode | Leader Involvement |
|-----------|------|----------------|-------------------|
| 1 | Independent Fix | `independent` — workers receive ONLY error details | Minimal — workers try blind |
| 2 | Guided Fix | `guided` — workers receive leader's specific analysis | High — leader provides targeted guidance |
| 3 | Final Check | No new fixes — run tests one last time | If still failing → ask user |

**Per-worker fix budget:** Each worker starts with `fix_budget_per_worker` (default: 2) fix attempts. Decremented each time a fix worker is spawned for that issue. When exhausted, that worker's failures are escalated to the user.

**Global fix spawn cap:** `max_total_fix_spawns` (default: 8) limits total fix worker spawns across ALL iterations and workers. Prevents unbounded resource usage.

**Stuck test detection:** A test is "stuck" if the same worker fails with the same root cause for 2+ consecutive iterations. Error comparison ignores timestamps, session IDs, memory addresses, temp paths. Stuck tests are not reassigned to the same worker — try a secondary suspect or escalate.

**Progress-based early termination:** If 2 consecutive iterations show zero improvement (failure count not decreasing, no previously-failing tests now passing), skip ahead to the final-check behavior and ask the user.

**Fix worker communication:**
- **CROSS-BOUNDARY**: "Fix requires changes in files owned by another worker" → leader coordinates
- **TEST-ISSUE**: "The E2E test itself appears wrong" → leader evaluates, may ask e2e-tester to revise

**Crash recovery:**
- E2E tester crash: check if `[E2E-RESULT]` task exists for current iteration. If yes, use it. If no, respawn. If crashes twice in same iteration → escalate to user.
- Fix worker crash: respawn with same prompt. If crashes twice → mark `[E2E-FIX]` failed, escalate.
- Git `index.lock` during parallel fix commits: retry up to 3 times with 2-second backoff.
- Worker name collision on respawn: if `worker-<issue>` is rejected, use `fixer-<issue>` instead.

---

## 5. Communication Protocol

### Message Types

| Type | From | To | Mechanism | Blocks Sender? |
|------|------|----|-----------|---------------|
| Progress update | Worker | Leader | `SendMessage` | No |
| Question | Worker | Leader | `TaskCreate([QUESTION])` + `SendMessage` | **Yes** |
| Blocker | Worker | Leader | `TaskCreate([BLOCKER])` + `SendMessage` | **Yes** |
| Decision response | Leader | Worker | `TaskUpdate` + `SendMessage` | No |
| Unblock notification | Leader | Worker | `SendMessage` | No |
| Integration request | Worker | Leader | `SendMessage` | No |
| Stub ready | Worker (provider) | Leader | `SendMessage` | No (leader waits for all) |
| Implementation complete | Worker | Leader | `TaskUpdate(completed)` + `SendMessage` | No |
| Real impl ready | Leader | Worker (consumer) | `SendMessage` | No (triggers Phase C) |
| E2E results | e2e-tester | Leader | `TaskCreate([E2E-RESULT])` + `SendMessage` | No |
| E2E fix complete | Fix worker | Leader | `TaskUpdate([E2E-FIX] completed)` + `SendMessage` | No |
| CROSS-BOUNDARY | Fix worker | Leader | `SendMessage` | **Yes** (waits for leader) |
| TEST-ISSUE | Fix worker | Leader | `SendMessage` | **Yes** (waits for leader) |
| Run Phase C | Leader | Worker (consumer) | `SendMessage` | No |

### Question flow (detailed)

```
Worker creates [QUESTION] task:
  TaskCreate({
    subject: "[QUESTION] Task classification for #101",
    description: "Task: #101\nQuestion type: task_classification\n
                  Context: ...\nOptions:\n1. NEW_FEATURE\n2. ENHANCEMENT\n
                  My recommendation: NEW_FEATURE"
  })
  TaskUpdate({ taskId: "<id>", owner: "team-lead" })
  SendMessage({ to: "team-lead", content: "Decision needed. See task <id>." })
  // WAIT for leader response

Leader processes:
  IF question_type in [task_classification, coverage_decision, test_placement, final_review]:
    Decides autonomously (Route A)
  ELSE IF question_type == "design_decision":
    Asks user via AskUserQuestion (Route B)

  TaskUpdate({ taskId: "<id>", status: "completed",
               description: "... DECISION: NEW_FEATURE REASONING: ..." })
  SendMessage({ to: "worker-101", content: "Decision: NEW_FEATURE. Reasoning: ..." })

Worker receives response → continues execution
```

### Blocker flow (detailed)

```
Worker creates [BLOCKER] task:
  TaskCreate({
    subject: "[BLOCKER] Need access to src/routes.py",
    description: "Task: #101\nBlocker type: ownership_violation\n
                  File needed: src/routes.py\nReason: Must register /auth/login route"
  })
  TaskUpdate({ taskId: "<id>", owner: "team-lead" })
  SendMessage({ to: "team-lead", content: "BLOCKED. See task <id>. Waiting." })
  // STOP and WAIT

Leader evaluates:
  IF file in another_active_teammate.files_owned → DENY
  IF file in shared_files → DENY ("send integration request instead")
  IF file is unowned → consider granting
  IF owning teammate finished → consider granting

  TaskUpdate({ taskId: "<id>", status: "completed",
               description: "... DECISION: denied. Send integration request." })
  SendMessage({ to: "worker-101", content: "Denied. File is shared.
                Send integration request instead." })
```

---

## 6. Scenarios

<a name="scenario-a"></a>
### Scenario A: Provider Creates Interface, Consumer Uses It

**Setup:** An application needs an authentication module. Two tasks are planned:
- Task #201: **AuthModels** — define the UserModel interface + real implementation
- Task #202: **LoginHandler** — implement login logic using UserModel

**Manifest configuration:**
```json
{
  "tasks": [
    {
      "issue_number": 201,
      "summary": "Implement AuthModels",
      "blocked_by": [],
      "interface_deps": [],
      "files_owned": ["src/auth/models.ext"],
      "test_files_owned": ["tests/test_auth_models.ext"]
    },
    {
      "issue_number": 202,
      "summary": "Implement LoginHandler",
      "blocked_by": [],
      "interface_deps": [
        {
          "provider_issue": 201,
          "interface_name": "UserModel",
          "stub_file": "src/auth/models.ext",
          "contract": "verify_password(plain) -> bool; get_by_email(email) -> UserModel|None"
        }
      ],
      "files_owned": ["src/auth/login.ext"],
      "test_files_owned": ["tests/test_login.ext"]
    }
  ],
  "execution_waves": [
    {"wave": 1, "tasks": [201, 202]}
  ]
}
```

**Note:** Both tasks are in Wave 1 because #202 uses `interface_deps`, not `blocked_by`.

**Execution timeline:**

```
T=0  Orchestrator spawns worker-201 (Sub-phase A: provider)
     worker-201's spawn prompt includes:
       "INTERFACE PROVIDER — generate stub at src/auth/models.ext
        Define interface: UserModel
        Contract: verify_password(plain) -> bool; get_by_email(email) -> UserModel|None"

T=1  worker-201 generates stub file:
       UserModel interface/protocol with empty method bodies
     worker-201 commits: "chore: stub for UserModel"
     worker-201 sends: "Stub ready: src/auth/models.ext. Interfaces: UserModel."

T=2  Orchestrator receives "Stub ready"
     Creates [STUB-READY] task
     Updates [WAVE-STATUS]: "Stubs ready: src/auth/models.ext"
     All stubs for Wave 1 are ready → spawns worker-202 (Sub-phase B: consumer)

     worker-202's spawn prompt includes:
       "INTERFACE STUBS AVAILABLE:
        - Interface: UserModel (from #201, parallel)
          File: src/auth/models.ext
          Contract: verify_password(plain) -> bool; get_by_email(email) -> UserModel|None

        DEPENDENCY INJECTION RULES:
        - Import from src/auth/models.ext directly
        - Accept via constructor params
        - Create test fakes/mocks satisfying the interface"

T=3  PARALLEL EXECUTION:
     worker-201: Designs validation tests → implements real AuthModels
     worker-202: Designs validation tests with FakeUserModel → implements LoginHandler

T=4  worker-201 replaces stub with real implementation
     Sends: "Blocker resolved for #201. Stub replaced: src/auth/models.ext"

T=5  Orchestrator sends to worker-202:
     "Interface UserModel real impl available. Run Phase C."

T=6  worker-202 re-runs tests against real UserModel (Phase C)
     Tests pass → signals completion
```

**Key variables set by orchestrator:**
- `<interface_providers>` = `{"src/auth/models.ext": {provider_issue: 201, interface_names: ["UserModel"], consumers: [202]}}`
- `<stubs_ready>` = `{"src/auth/models.ext"}` (after T=1)

---

<a name="scenario-b"></a>
### Scenario B: Teammate Asks Leader a Question

**Setup:** worker-201 is implementing an authentication module and encounters a design decision: should password hashing use bcrypt or argon2?

**What happens:**

```
worker-201 creates a [QUESTION] task:

  TaskCreate({
    subject: "[QUESTION] Design decision: password hashing algorithm for #201",
    description: "Task: #201
                  Question type: design_decision

                  Context: Implementing UserModel.verify_password(). Need to choose
                  a password hashing algorithm for the project.

                  Options:
                  1. bcrypt — Industry standard, widely supported, well-tested.
                     Pros: Battle-tested, simple API. Cons: CPU-only, fixed work factor.
                  2. argon2 — Modern winner of Password Hashing Competition.
                     Pros: Memory-hard, configurable. Cons: Less library support.

                  My recommendation: argon2 (memory-hard prevents GPU attacks)"
  })
  TaskUpdate({ taskId: "q1", owner: "team-lead" })
  SendMessage({
    to: "team-lead",
    content: "Design decision needed for #201: password hashing algorithm. See task q1.",
    summary: "Question: password hashing for #201"
  })
  // worker-201 STOPS and WAITS
```

**Leader processes the question:**

Because `question_type` is `design_decision`, the leader forwards to the user:

```
Leader calls AskUserQuestion:
  AskUserQuestion({
    questions: [{
      question: "Which password hashing algorithm should task #201 use?",
      header: "Design",
      options: [
        { label: "argon2 (Recommended)", description: "Modern, memory-hard. Worker recommends this." },
        { label: "bcrypt", description: "Industry standard, simpler, wider library support." }
      ]
    }]
  })
```

User selects "argon2". Leader records decision and responds:

```
  TaskUpdate({
    taskId: "q1",
    status: "completed",
    description: "... DECISION: argon2 DECIDED_BY: user REASONING: Memory-hard, modern standard"
  })
  SendMessage({
    to: "worker-201",
    content: "Design decision: Use argon2 for password hashing. User approved.",
    summary: "Decision: use argon2 for #201"
  })
```

worker-201 receives the response and resumes implementation with argon2.

**If it had been a `task_classification` question instead:**
- Leader would decide **autonomously** (Route A) without asking the user
- Example: "Classification: NEW_FEATURE. Reasoning: New authentication module, no pre-existing code."

**Decision stored in `<decision_precedents>`:**
```
decision_precedents["password_hashing"] = {
  decision: "argon2",
  decided_by: "user",
  task: 201
}
```
If another worker asks about hashing later, leader can reference this precedent for consistency.

---

<a name="scenario-c"></a>
### Scenario C: Leader Criticizes Test Quantity

**Setup:** worker-301 sends a `final_review` question after creating validation tests. The leader (acting as Staff Engineer) reviews and finds the tests insufficient.

**What happens:**

```
worker-301 creates [QUESTION] task:

  TaskCreate({
    subject: "[QUESTION] Final review: validation tests for #301",
    description: "Task: #301
                  Question type: final_review

                  Tests created: 2
                  Tracker: tests/tracker-files/validation_tests_tracker_301.json

                  Tests:
                  1. test_payment_processes_valid_card (tdd_validation)
                  2. test_payment_returns_receipt (tdd_validation)

                  All tests currently fail (TDD approach).
                  Requesting approval to proceed to implementation."
  })
  TaskUpdate({ taskId: "q2", owner: "team-lead" })
  SendMessage({
    to: "team-lead",
    content: "Final review requested for #301. 2 validation tests. See task q2.",
    summary: "Review request: #301 tests"
  })
  // worker-301 WAITS
```

**Leader reviews (autonomous Route A — `final_review`):**

The leader reads the tracker JSON and actual test files. As Staff Engineer, evaluates:
- Are 2 tests sufficient for a payment module?
- Are edge cases covered?
- Does the test quality meet the bar?

Leader decides the tests are insufficient:

```
  TaskUpdate({
    taskId: "q2",
    status: "completed",
    description: "... DECISION: REJECTED
                  REASONING: Only 2 tests for a payment module is insufficient.
                  Missing critical scenarios:
                  - Invalid card number (edge case)
                  - Expired card (edge case)
                  - Network timeout during processing (error handling)
                  - Duplicate payment prevention (business logic)
                  - Partial refund calculation (business logic)

                  Add at least 3 more tests covering error/edge cases before proceeding."
  })
  SendMessage({
    to: "worker-301",
    content: "REJECTED: 2 tests insufficient for payment module.
              Missing: invalid card, expired card, network timeout,
              duplicate prevention, partial refund.
              Add at least 3 more covering error/edge cases.
              Resubmit for review when done.",
    summary: "Rejected: #301 needs more tests"
  })
```

**worker-301 receives rejection → adds more tests → resubmits:**

```
worker-301 adds tests:
  3. test_payment_rejects_invalid_card
  4. test_payment_rejects_expired_card
  5. test_payment_handles_network_timeout

Updates tracker JSON, creates new [QUESTION] task:

  TaskCreate({
    subject: "[QUESTION] Final review (revised): validation tests for #301",
    description: "Task: #301
                  Question type: final_review

                  Tests created: 5 (was 2, added 3 per leader feedback)
                  Added: invalid card, expired card, network timeout

                  Requesting re-approval."
  })
```

Leader re-reviews → 5 tests is acceptable → APPROVES:

```
  TaskUpdate({
    taskId: "q3",
    status: "completed",
    description: "... DECISION: APPROVED. 5 tests cover critical happy path,
                  error cases, and edge cases. Proceed to implementation."
  })
  SendMessage({
    to: "worker-301",
    content: "APPROVED: 5 tests provide adequate coverage. Proceed to Phase B.",
    summary: "Approved: #301 tests (5 total)"
  })
```

---

<a name="scenario-d"></a>
### Scenario D: Ownership Violation Request

**Setup:** worker-401 needs to modify `src/config/settings.ext` which is in `shared_files`.

**What happens:**

```
worker-401 recognizes the file is shared:

  TaskCreate({
    subject: "[BLOCKER] Need to modify shared file src/config/settings.ext",
    description: "Task: #401
                  Blocker type: ownership_violation_request

                  File needed: src/config/settings.ext
                  Reason: Need to add PAYMENT_GATEWAY_URL configuration constant.
                  This is required for the payment service to connect to the gateway."
  })
  TaskUpdate({ taskId: "b1", owner: "team-lead" })
  SendMessage({
    to: "team-lead",
    content: "BLOCKED: Need to modify src/config/settings.ext (shared file). See task b1.",
    summary: "BLOCKED: shared file access #401"
  })
  // worker-401 STOPS and WAITS
```

**Leader evaluates:**

```
File src/config/settings.ext is in shared_files[]
→ DENY direct modification

  TaskUpdate({
    taskId: "b1",
    status: "completed",
    description: "... DECISION: DENIED. File is shared.
                  ALTERNATIVE: Send an integration request instead. The integrator
                  will add PAYMENT_GATEWAY_URL during Phase 4."
  })
  SendMessage({
    to: "worker-401",
    content: "Denied. src/config/settings.ext is a shared file.
              Send an integration request with the specific change needed.
              The integrator will apply it during the integration phase.",
    summary: "Denied: use integration request for shared file"
  })
```

**worker-401 sends integration request instead:**

```
  SendMessage({
    to: "team-lead",
    content: "Integration request for #401.
              File: src/config/settings.ext
              Change needed: Add constant PAYMENT_GATEWAY_URL with default value
              from environment variable.",
    summary: "Integration: #401 needs config change"
  })
  // Does NOT wait — continues with other work
```

**Leader persists integration request:**

```
  TaskCreate({
    subject: "[INTEGRATION-REQUEST] Add PAYMENT_GATEWAY_URL to settings",
    description: "From: #401
                  File: src/config/settings.ext
                  Change: Add PAYMENT_GATEWAY_URL constant"
  })
```

This will be handled during Phase 4 (Integration).

---

<a name="scenario-e"></a>
### Scenario E: Multi-Wave Execution with Integration

**Setup:** A feature requires three components with dependencies:

```json
{
  "tasks": [
    {
      "issue_number": 501,
      "summary": "Database Models",
      "blocked_by": [],
      "interface_deps": [],
      "files_owned": ["src/models/user.ext", "src/models/order.ext"],
      "test_files_owned": ["tests/test_models.ext"]
    },
    {
      "issue_number": 502,
      "summary": "API Endpoints",
      "blocked_by": [501],
      "interface_deps": [],
      "files_owned": ["src/api/users.ext", "src/api/orders.ext"],
      "test_files_owned": ["tests/test_api.ext"]
    },
    {
      "issue_number": 503,
      "summary": "Background Jobs",
      "blocked_by": [501],
      "interface_deps": [],
      "files_owned": ["src/jobs/order_processor.ext"],
      "test_files_owned": ["tests/test_jobs.ext"]
    }
  ],
  "shared_files": ["src/routes.ext", "src/config.ext"],
  "execution_waves": [
    {"wave": 1, "tasks": [501]},
    {"wave": 2, "tasks": [502, 503]},
    {"wave": 3, "tasks": ["INTEGRATION"], "type": "integration"}
  ],
  "e2e_config": {
    "e2e_test_dir": "tests/e2e/",
    "e2e_test_command": "...",
    "e2e_scenarios": [
      {"name": "order_placement_flow", "components_involved": [501, 502, 503], "acceptance_criteria_ref": "AC-1"}
    ],
    "max_iterations": 3,
    "fix_budget_per_worker": 2,
    "max_total_fix_spawns": 8
  }
}
```

**Execution timeline:**

```
WAVE 1:
  Orchestrator creates tasks:
    [WORK] t1: Database Models (#501)
    [WORK] t2: API Endpoints (#502) — blocked by t1
    [WORK] t3: Background Jobs (#503) — blocked by t1
    [INTEGRATION] t4: Shared files — blocked by t1, t2, t3
    [E2E-VALIDATION] t5: E2E tests — blocked by t4
    [WAVE-STATUS]: "Wave: 1, Active: none, Completed: none, E2E iteration: 0, E2E status: not_started"

  Spawns worker-501 (Wave 1 — no blockers)
  worker-501 executes Phase A → Phase B → signals completion

WAVE 2:
  Spawns worker-502 AND worker-503 simultaneously
  Both execute Phase A → Phase B → signal completion

INTEGRATION (Phase 4):
  Spawns integrator → wires routes + config → full test suite passes
  Integrator shut down (Phase 4.4.5)

E2E VALIDATION (Phase 4.5):
  Initialize: e2e_iteration=1, e2e_status=running, fix_budgets={501:2, 502:2, 503:2}
  Spawn e2e-tester (opus, write_and_run)
  e2e-tester writes tests for "order_placement_flow" scenario → runs them
  Results: all pass → e2e_status=completed → Phase 5

SHUTDOWN:
  Shut down e2e-tester
  Delete team resources
  Report final summary (including E2E results)
```

---

<a name="scenario-f"></a>
### Scenario F: Consumer Re-validates Against Real Implementation (Phase C)

**Setup:** worker-602 implemented LoginHandler using a FakeUserModel. Provider worker-601 has now finished the real UserModel implementation.

**What happens:**

```
T=N  worker-601 finishes real UserModel implementation:
     Sends: "Blocker resolved for #601. Unblocks: [602]. Stub replaced: src/auth/models.ext"

T=N+1  Orchestrator processes:
     Updates [WAVE-STATUS]
     Sends to worker-602:
       "Interface UserModel real implementation available in src/auth/models.ext.
        You should now re-run your tests against the real implementation (Phase C)."

T=N+2  worker-602 enters Phase C:

     C.1 Check provider status:
       All interface_deps providers have sent "Stub replaced" → proceed

     C.2 Re-run tests:
       Runs: full test suite

       CASE 1: All tests pass
         → Phase C complete. worker-602 proceeds to Phase 5 (final commit)

       CASE 2: Tests fail — contract mismatch
         Example: Real UserModel.verify_password returns a tuple, not a bool
         → Creates [BLOCKER]:
           "Contract mismatch: UserModel.verify_password was specified as -> bool
            but real implementation returns tuple. Provider #601 violated contract."
         → Orchestrator coordinates with worker-601 to fix

       CASE 3: Tests fail — behavioral assumption
         Example: FakeUserModel always returned None for unknown emails,
                  but real UserModel raises UserNotFoundError
         → worker-602 fixes own code to handle UserNotFoundError
         → Re-runs tests → pass
         → Commits fix: "fix(#602): Handle UserNotFoundError from real UserModel"

       CASE 4: Import error
         Example: Real implementation file has temporary syntax error
         → Retry after 2 seconds (provider may be mid-write)
         → If still fails → Create [BLOCKER] and escalate
```

---

<a name="scenario-g"></a>
### Scenario G: E2E Test Fails and Fix Loop Executes

**Setup:** A swarm with 3 workers (#701, #702, #703) has completed all work and integration. The e2e-tester runs and finds 2 deterministic failures.

**What happens:**

```
PHASE 4.5: E2E Validation (Iteration 1)
  Leader initializes:
    e2e_iteration = 1
    e2e_status = running
    fix_budgets = {701:2, 702:2, 703:2}
    total_fix_spawns = 0

  Spawns e2e-tester (model: opus, mode: write_and_run)
  e2e-tester writes 6 tests, runs them:
    Results: 4 passed, 2 failed (deterministic), 0 flaky

  Leader shuts down e2e-tester
  Creates [E2E-RESULT] task: "Iteration 1 — 4/6 passed"
  e2e_status = fix_loop → enters Phase 4.6

PHASE 4.6: Fix Loop — Iteration 1 (Independent Fix)
  Leader attributes failures:
    Failure 1: test_user_login_flow
      Stack files: [src/auth/session.ext] → worker-701 owns src/auth/ → HIGH confidence
    Failure 2: test_order_checkout
      Stack files: [src/payment/processor.ext] → worker-702 owns src/payment/ → HIGH confidence

  Creates [E2E-FIX] tasks:
    "[E2E-FIX] test_user_login_flow → worker-701 (iter 1)" — mode: independent
    "[E2E-FIX] test_order_checkout → worker-702 (iter 1)" — mode: independent

  Spawns worker-701 and worker-702 in fix mode (model: from manifest)
  fix_budgets = {701:1, 702:1, 703:2}
  total_fix_spawns = 2

  worker-701: reads working notes → analyzes failure → fixes session handling → commits
  worker-702: reads working notes → analyzes failure → fixes payment logic → commits

  Leader shuts down both fix workers

  Re-run E2E (Iteration 2):
    Spawns e2e-tester (model: sonnet, mode: run_only)
    Results: 5 passed, 1 failed (test_order_checkout still fails), 0 flaky

  Leader creates [E2E-RESULT]: "Iteration 2 — 5/6 passed"
  Progress detected (2 failures → 1 failure) → continue loop

PHASE 4.6: Fix Loop — Iteration 2 (Guided Fix)
  Leader attributes remaining failure:
    test_order_checkout → worker-702 (same as before, but different error now)

  This is NOT stuck (error changed between iterations — different root cause)

  Creates [E2E-FIX] task with mode: guided
    Leader adds specific guidance: "The error is now a null reference in
    OrderConfirmation. Check the OrderService.confirm() method — it may not
    handle the case where payment returns a pending status."

  Spawns worker-702 in fix mode (guided)
  fix_budgets = {701:1, 702:0, 703:2}
  total_fix_spawns = 3

  worker-702: reads guidance → finds the null reference → fixes it → commits
  Leader shuts down worker-702

  Re-run E2E (Iteration 3 — Final Check):
    Spawns e2e-tester (model: sonnet, mode: run_only)
    Results: 6 passed, 0 failed

  ALL E2E tests pass!
  e2e_status = completed → Phase 5 (Shutdown)
```

**Key variables after completion:**
- `e2e_iteration` = 3
- `e2e_status` = completed
- `fix_budgets` = {701:1, 702:0, 703:2}
- `total_fix_spawns` = 3
- `e2e_failures_history` = [{iter:1, failed:2}, {iter:2, failed:1}, {iter:3, failed:0}]

---

<a name="scenario-h"></a>
### Scenario H: Cross-Boundary E2E Failure

**Setup:** During the E2E fix loop, worker-801 is respawned to fix `test_user_dashboard_flow`. But the root cause is in a file owned by worker-802.

**What happens:**

```
Leader attributes test_user_dashboard_flow to worker-801:
  Stack files: [src/dashboard/api.ext, src/auth/middleware.ext]
  worker-801 owns src/dashboard/ → HIGH confidence (most file mentions)
  But src/auth/middleware.ext is owned by worker-802

Spawns worker-801 in fix mode (independent, iteration 1)

worker-801 reads working notes → analyzes the failure:
  "The test fails because the auth middleware rejects the test token.
   The middleware validation logic in src/auth/middleware.ext has a bug
   where it doesn't recognize the test user's role.
   I cannot modify src/auth/middleware.ext — it's owned by worker-802."

worker-801 sends CROSS-BOUNDARY message:
  SendMessage({
    to: "team-lead",
    content: "CROSS-BOUNDARY: E2E fix for test_user_dashboard_flow requires
              change in src/auth/middleware.ext owned by worker-802.
              The middleware doesn't recognize test user roles correctly.",
    summary: "CROSS-BOUNDARY: need worker-802's file"
  })
  // worker-801 STOPS and WAITS

Leader evaluates:
  This is a Tier 4 (cross-boundary) failure.

  Option A: Respawn worker-802 with specific fix instructions
    → "Fix the role validation in src/auth/middleware.ext to handle
       the 'viewer' role from the dashboard component."
  Option B: Fix directly during integration verification
  Option C: Escalate to user

  Leader chooses Option A:
    Creates [E2E-FIX] task for worker-802
    Spawns worker-802 with guided instructions
    fix_budgets[802] decremented

  worker-802 fixes middleware.ext → commits

  Leader sends to worker-801: "Cross-boundary dependency resolved.
    worker-802 fixed src/auth/middleware.ext. Your files should work now."

  worker-801 verifies own tests still pass → signals completion
  Next E2E iteration re-runs tests → test_user_dashboard_flow passes
```

---

<a name="scenario-i"></a>
### Scenario I: Stuck Test Detection and Human Escalation

**Setup:** `test_realtime_sync` fails in iteration 1 and iteration 2 with the same error, attributed to worker-901. The fix loop detects it's stuck.

**What happens:**

```
Iteration 1:
  test_realtime_sync fails: "WebSocket connection refused on port 8080"
  Attributed to worker-901 (owns src/realtime/) → HIGH confidence
  worker-901 spawned in independent fix mode → attempts fix → commits
  fix_budgets[901] = 1 (was 2)

Iteration 2 (re-run E2E):
  test_realtime_sync STILL fails: "WebSocket connection refused on port 8080"

  Leader compares errors:
    Iteration 1 error: "WebSocket connection refused on port 8080"
    Iteration 2 error: "WebSocket connection refused on port 8080"
    Normalize: remove timestamps, temp paths → IDENTICAL
    Same worker (901), same test, same root cause for 2 consecutive iterations

  → test_realtime_sync added to <stuck_tests>

  Leader does NOT respawn worker-901 for this test.
  Instead, checks for secondary suspects:
    Stack also mentions src/config/settings.ext (shared file)
    → Possible that the WebSocket port config was never set during integration

  Leader has two options:
    1. Try different worker (secondary suspect)
    2. Escalate to user

  No other worker owns WebSocket config → escalate to user

  Also: check if 2 consecutive iterations show zero overall improvement:
    Iteration 1: 4/6 failed
    Iteration 2: 4/6 failed (same failures, no progress)
    → Early termination triggered

  Leader presents to user:
    AskUserQuestion({
      question: "3 E2E iterations completed. Remaining 4 failures.
                Stuck tests: [test_realtime_sync].
                My hypothesis: WebSocket port config missing from integration.
                How would you like to proceed?",
      options: [
        { label: "Accept current state",
          description: "Proceed with some E2E failures unresolved." },
        { label: "Provide guidance",
          description: "You provide specific fix instructions for remaining failures." },
        { label: "Take manual control",
          description: "Stop the swarm. You fix the remaining issues." }
      ]
    })

  User selects "Provide guidance":
    User: "The WebSocket port needs to be set in the E2E setup command.
           Add 'export WS_PORT=8080' to the e2e_setup_command."

  Leader spawns ONE MORE fix iteration (exception to max_iterations):
    Modifies e2e_setup_command or instructs e2e-tester to add setup
    Re-runs E2E → test_realtime_sync passes!
    e2e_status = completed → Phase 5
```

---

## 7. Variable Reference

### Environment Variables

| Variable | Required By | Description |
|----------|-------------|-------------|
| `$GITHUB_PROJECT` | All commands | Repository path (owner/repo) |

### Per-Command Variables

#### plan_from_gh_issue_swarm

| Variable | Set By | Consumed By |
|----------|--------|-------------|
| `<epic_id>` | User input (#$ARGUMENTS) | Read local epic file |
| `<feature_description>` | Local epic file read | Plan generation |
| `<detected_language>` | Manifest file detection | Language-specific adaptation |
| `<plan_content>` | Generated plan | Local plan file creation (`Plans/plan-for-epic-<N>.md`) |

#### create_issues_from_plan_swarm

| Variable | Set By | Consumed By |
|----------|--------|-------------|
| `<plan_path>` | User input ($ARGUMENTS token 1) | Plan file reading |
| `<parent_issue_number>` | User input ($ARGUMENTS token 2) | Local file operations, task file creation |
| `<plan_description>` | Local plan file | Task decomposition |
| Task N → issue_number mapping | Task file creation | Manifest generation |
| Component name → issue_number mapping | Task file creation | E2E scenario transformation |

#### orchestrate_swarm

| Variable | Set By | Consumed By |
|----------|--------|-------------|
| `<parent_issue_number>` | User input ($ARGUMENTS token 1) | Team naming, context |
| `<integration_branch>` | User input ($ARGUMENTS token 2) | Worktree creation, branch management |
| `<manifest_path>` | User input ($ARGUMENTS token 3) | Manifest file location |
| `<worktree_abs_path>` | Phase 0.1.5 worktree creation | All teammate spawn prompts |
| `<detected_tech_stack>` | Phase 0.5 detection | Worker spawn prompts |
| `<relevant_skills>` | Phase 0.5 skill discovery | Worker spawn prompts |
| `<manifest>` | swarm-manifest.json | All phases |
| `<tasks>` | Manifest parsing | Task creation, spawning |
| `<execution_waves>` | Manifest parsing | Wave scheduling |
| `<shared_files>` | Manifest parsing | Integration phase |
| `<interface_providers>` | Derived from manifest | Provider/consumer orchestration |
| `<active_teammates>` | Phase 2 spawning | Monitoring, shutdown |
| `<completed_tasks>` | Completion signals | Wave progression |
| `<current_wave>` | Wave progression | Spawning decisions |
| `<stubs_ready>` | "Stub ready" messages | Consumer spawning |
| `<integration_requests>` | Worker messages | Integration phase |
| `<decision_precedents>` | Question resolutions | Consistent decisions |
| `<plan_content>` | Local plan file (path from manifest `plan_file`) | Decision context |
| `<e2e_iteration>` | Phase 4.5 init | Fix loop progression |
| `<e2e_status>` | Phase 4.5 init | Phase transitions |
| `<fix_budgets>` | Phase 4.5 init (from e2e_config) | Fix worker spawning |
| `<total_fix_spawns>` | Phase 4.6 counting | Global spawn cap enforcement |
| `<stuck_tests>` | Phase 4.6 detection | Preventing futile respawns |
| `<e2e_failures_history>` | [E2E-RESULT] tasks | Progress analysis, stuck detection |

#### design_validation_tests_swarm

| Variable | Set By | Consumed By |
|----------|--------|-------------|
| `<task_id>` | Worker's assigned issue (#$ARGUMENTS) | All phases |
| `<my_files_owned>` | Manifest lookup | Ownership enforcement |
| `<my_test_files_owned>` | Manifest lookup | Test file placement |
| `<blocked_by>` | Manifest lookup | Dependency checking |
| `<my_interface_deps>` | Manifest lookup | Contract testing |
| `<task_type>` | Leader classification | Test strategy selection |
| Coverage mapping | Discovery phase | Test creation decisions |
| Tracker JSON | Phase 4.1 output | Handoff to Phase B |

#### code_from_validation_tests_swarm

| Variable | Set By | Consumed By |
|----------|--------|-------------|
| `<task_id>` | Worker's assigned issue (#$ARGUMENTS) | All phases |
| Tracker JSON | Previous phase output | Implementation guidance |
| `<available_interfaces>` | Stub file reading | DI implementation |
| Implementation plan | Phase 1 planning | Iterative implementation |

#### e2e_validation_swarm

| Variable | Set By | Consumed By |
|----------|--------|-------------|
| `<parent_issue_number>` | Spawn prompt | Context, working notes naming |
| MODE | Spawn prompt | Phase 2 skip logic |
| ITERATION | Spawn prompt | Compaction recovery, model selection |
| `e2e_config` | swarm-manifest.json | Test dir, command, scenarios, markers |
| E2E test files | Phase 2 output (write_and_run) | Phase 3 test execution |
| `[E2E-RESULT]` task | Phase 4 output | Leader's failure analysis |

---

## 8. Task System Tags Reference

All tasks in the shared task list use prefix tags for identification:

| Tag | Created By | Purpose | Lifecycle |
|-----|-----------|---------|-----------|
| `[WORK]` | Orchestrator (Phase 1) | One per manifest task | pending → in_progress → completed |
| `[INTEGRATION]` | Orchestrator (Phase 1) | Shared file integration | Blocked until all [WORK] done |
| `[E2E-VALIDATION]` | Orchestrator (Phase 1) | E2E validation tracking | Blocked until [INTEGRATION] done |
| `[WAVE-STATUS]` | Orchestrator (Phase 1) | State persistence across compaction | Updated continuously |
| `[QUESTION]` | Workers | Decision requests to leader | pending → completed (with DECISION:) |
| `[BLOCKER]` | Workers | Blocking issues for leader | pending → completed (with DECISION:) |
| `[STUB-READY]` | Orchestrator | Records confirmed stubs | Created as completed |
| `[INTEGRATION-REQUEST]` | Orchestrator | Records shared file changes needed | pending → consumed in Phase 4 |
| `[E2E-RESULT]` | e2e-tester | Records E2E results per iteration | Created as completed (fact record) |
| `[E2E-FIX]` | Orchestrator (Phase 4.6) | Tracks fix worker assignments | pending → in_progress → completed |

**[WAVE-STATUS] full field reference:**
```
Wave: 2
Active: worker-101, worker-102
Completed: 101, 102
Stubs ready: src/auth/models.ext
Task map: 101->t1, 102->t2
E2E iteration: 2
E2E status: fix_loop
Fix budgets: 101:1, 102:0, 103:2
Fix workers active: worker-101, fixer-103
Tech stack: python + fastapi
Relevant skills: python-testing-patterns, security-best-practices
Worktree path: /home/user/project/.claude/worktrees/feat-auth
Integration branch: feat/auth-module
Manifest path: swarm-manifest.json
```

---

## 9. Language-Agnostic Design

All swarm commands reference `language-profiles.md` to adapt behavior per detected language. The language is detected by checking for manifest files in order:

| File | Language |
|------|----------|
| `pyproject.toml` | Python |
| `package.json` | TypeScript/JavaScript |
| `go.mod` | Go |
| `Cargo.toml` | Rust |
| `*.csproj` | .NET (C#) |
| `pom.xml` / `build.gradle` | Java/Kotlin |

**Key adaptations:**

| Aspect | Python | TypeScript | Go | Rust | .NET |
|--------|--------|------------|-----|------|------|
| Test runner | `pytest` | `vitest`/`jest` | `go test` | `cargo test` | `dotnet test` |
| Test marker | `@pytest.mark.tdd_validation` | describe block or file dir | `TestTDDValidation_` prefix | `mod tdd_validation` | `[Trait("Category", "tdd_validation")]` |
| Interface | `Protocol` / `ABC` | `interface` | implicit (consumer-defined) | `trait` | `interface` |
| Stub lifecycle | Overwrite entirely | Overwrite entirely | No stubs needed | Add `impl` alongside | Implement in separate class |
| Package index | `__init__.py` | `index.ts` | N/A | `mod.rs` / `lib.rs` | N/A |
| Ownership level | File (module) | File | Package (directory) | File/module | Project (.csproj) |
| Verify import | `python -c "from m import C"` | `tsc --noEmit` | `go build` | `cargo check` | `dotnet build` |

**E2E-specific adaptations:**

| Aspect | Python | TypeScript | Go | Rust | .NET |
|--------|--------|------------|-----|------|------|
| E2E test dir | `tests/e2e/` | `tests/e2e/` | `e2e/` (top-level) | `tests/e2e/` | `<Project>.Tests.E2E/` |
| E2E marker | `@pytest.mark.e2e` | File naming `*.e2e.test.ts` | Build tag `//go:build e2e` | Test target naming | `[Trait("Category", "E2E")]` |
| E2E runner | `python -m pytest tests/e2e/ -v` | Playwright or vitest/jest | `go test -tags=e2e ./e2e/...` | `cargo test --test e2e` | `dotnet test <Project>.Tests.E2E/` |
| E2E output | `--junitxml=e2e-report.xml` | `--reporter=json` (Playwright) | `-json` flag | Terminal (no JSON in stable) | `--logger "junit;LogFileName=e2e-report.xml"` |
| E2E file pattern | `test_e2e_*.py` | `*.e2e.test.ts` | `*_test.go` (with build tag) | `tests/e2e/main.rs` entry | `*E2ETests.cs` |

**Language-specific E2E notes:**
- **Go**: E2E tests use a top-level `e2e/` package (intentional exception to Go's co-location model). Build tags exclude E2E from `go test ./...`.
- **Rust**: E2E tests use `tests/e2e/main.rs` as entry point. Sub-modules declared via `mod`. The trait is never overwritten.
- **.NET**: E2E tests require a separate `.csproj` project. Uses `WebApplicationFactory<T>` for in-process API testing.
- **TypeScript**: Playwright detection heuristic — if `playwright.config.ts` exists, use Playwright for browser-based E2E. Otherwise use vitest/jest.
- **Python**: Check for `behave` in dependencies. If present, existing BDD scenarios may already cover E2E flows.

**E2E marker naming**: Use `e2e` (NOT `tdd_e2e`). E2E tests are post-integration validation, not part of the TDD cycle. The TDD cycle is complete before E2E runs.

**In all scenarios shown in this guide**, `.ext` is used as a placeholder for the language-specific file extension. The actual extension depends on the detected language.

---

## Quick Reference: End-to-End Flow

### Initiative-Scale (50+ features)

```
1. User runs: /time_split <initiative_dir>
   → phases/pipeline_state.json created
   → phases/initiative_summary.json + phase manifests generated

2. User runs: /deepen_time_split <phases_dir>
   → phases/feedback/deepen_time_split_feedback.json written
   → Convergence decision: continue or converged
   → If continue: re-run /time_split (reads feedback, iterates) → repeat step 2
   → If converged: proceed to step 3

3. For each phase:
   a. /bootstrap <phase_manifest> <target_repo>
      → Foundation created, bootstrap-report.json generated
   b. /deepen_bootstrap <target_repo> <phase_manifest>
      → Feedback with code_change_guidance written
      → Iterate until converged (max 3)
   c. /space_split <phase_manifest> <phase_dir>
      → Epic files created at phases/phase_N/epic_M/epic.md, epic_dag.json generated
   d. /deepen_space_split <phase_dir>
      → Feedback with epic_updates written
      → Iterate until converged (max 3)

4. For each epic (per DAG wave order):
   → Steps 5-9 below
```

### Per-Epic Execution

```
5. User runs: /plan_phase_epic <phase_number> <epic_number>
   → Reads from phases/phase_N/epic_M/epic.md
   → Plan created at phases/phase_N/epic_M/plan.md

6. User runs: /deepen_plan_phase_epic <phase_number> <epic_number>
   → Feedback with plan_change_guidance written
   → Iterate until converged (max 3)

8. User runs: /create_issues_from_plan_swarm <plan_path> <issue_number>
   → Task files created at phases/phase_N/epic_M/tasks/
   → swarm-manifest.json generated (with mandatory e2e_config)

9. User runs: /orchestrate_swarm <issue_number> <integration_branch> <manifest_path>
   → Git worktree created at .claude/worktrees/<branch-slug>
   → Team "swarm-<issue>" created
   → Wave 1: worker-101 spawns → designs tests → implements code
   → Wave 1: worker-102 spawns (after stub ready) → designs tests → implements code
   → Wave 2: worker-103 spawns → designs tests → implements code
   → Phase C: consumers re-validate against real implementations
   → Integration: integrator wires shared files → shut down integrator
   → E2E: e2e-tester writes + runs E2E tests (opus, write_and_run)
   → If E2E fails: fix loop (up to 3 iterations)
     → Iteration 1: workers fix independently (sonnet for re-run)
     → Iteration 2: leader provides guided fix instructions
     → Iteration 3: final check, escalate to user if still failing
   → All tests pass → team shut down → results reported

10. (Optional) User runs: /review_swarm_pr <issue_number> <integration_branch> <pr_number> <manifest_path>
    → Review agents spawned (security, architecture, simplicity, etc.)
    → Findings triaged and approved by user
    → Task files created with [REVIEW] prefix
    → Manifest updated with fixup tasks (original tasks marked completed)
    → If findings exist: re-run /orchestrate_swarm for fixup swarm
```
