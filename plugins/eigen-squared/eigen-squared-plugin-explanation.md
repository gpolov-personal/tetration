# Eigen-Squared Plugin — Complete Pipeline Explanation

## What is Eigen-Squared?

Eigen-local is a Claude Code plugin that decomposes large software development initiatives into parallel, swarm-executable work. It takes an initiative (a strategic document describing 10-150+ features) and progressively breaks it down until autonomous AI agent swarms can implement it in parallel.

The plugin is **language-agnostic** — it supports Python, TypeScript, Go, Rust, C#/.NET, Kotlin/Android, Swift/iOS, Flutter, React Native, and more. It is also **project-type agnostic** — web APIs, mobile apps, CLI tools, libraries, ML pipelines.

## Environment Setup

Required environment variables for ALL commands:

```bash
export EIGEN_ROOT=/path/to/your/project     # Target project root
export EIGEN_BRANCH=main                      # Default branch
export CLAUDE_TASKS_API=http://localhost:8080  # Required for autonomous pipeline scheduling
```

Optional environment variable for Telegram notifications:

```bash
export EIGEN_TELEGRAM_CHAT_ID=<your_chat_id>  # Enables pipeline progress notifications via Telegram
```

Agent teams must be enabled (checked on first command):
```json
// .claude/settings.json
{
  "env": {
    "CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS": "1",
    "teammateMode": "tmux"
  }
}
```

## The Pipeline

The pipeline has 7 stages. Each stage has a main command and a deepen command that reviews and iterates until converged. **All commands are zero-argument** — they auto-detect their target from the pipeline state.

```
Initiative Documents
        |
    /time_split ←→ /deepen_time_split          Stage 1: Decompose across TIME
        |
    /bootstrap ←→ /deepen_bootstrap            Stage 2: Create project foundation
        |
    /space_split ←→ /deepen_space_split        Stage 3: Decompose across SPACE
        |
    /plan_phase_epic ←→ /deepen_plan_phase_epic Stage 4: Plan each epic
        |
    /create_issues_from_plan_swarm              Stage 5: Generate tasks + manifest + branch
        |
    /orchestrate_swarm                          Stage 6: Execute the swarm
        |
    /review_swarm_pr ←→ /orchestrate_swarm     Stage 7: Review PR, fix, iterate until converged
        |
    Manual PR merge → Next epic
```

---

## Stage 1: Time Split — Decompose Across Time

**Command:** `/time_split`
**Scope:** Initiative-level (runs once per initiative)

Takes the initiative documents from `$EIGEN_ROOT/eigen_initiative/` and splits the initiative into **sequential, E2E-testable phases**. Each phase builds on prior phases.

**Input:** Initiative document + Blackbox Requirements (+ optional Whitebox Reference) in `$EIGEN_ROOT/eigen_initiative/`

**Output:**
- `phases/initiative_summary.json` — metadata, DAG stats
- `phases/phase_N_manifest.md` — one per phase, with features, specs, dependencies
- `phases/pipeline_state.json` — created/updated on exit as pipeline state management (single source of truth for the entire pipeline)

**Review:** `/deepen_time_split` reviews the phase split for structural, content, and strategic issues. The deepen command owns convergence decisions (all high+medium findings resolved, max 8 iterations). Each command auto-chains to the next via `$CLAUDE_TASKS_API` when set.

---

## Stage 2: Bootstrap — Create Project Foundation

**Command:** `/bootstrap`
**Scope:** Per-phase (auto-detects first phase needing bootstrap)

Creates the structural scaffolding in `$EIGEN_ROOT` so the swarm has a compiling codebase. **Minimal by design** — only the universal foundation:

- Directory structure from phase domains
- Shared entity stubs (cross-domain types, typed but empty)
- API contracts / OpenAPI stubs and message contract / typed schema stubs
- Package manifests + quality config (linter, type checker, test runner)
- Package index files (`__init__.py`, `index.ts`, etc.)
- Basic CI (lint + type-check + test, no E2E)
- System prerequisites check (JDK, Android SDK, etc.)
- `.gitignore`

Bootstrap is **language-aware** — it uses the `language-profiles` skill for detection, toolchain resolution, and multi-language project support. It computes a delta (required - existing) and applies changes incrementally, optionally using parallel sub-agents for large deltas. A verification gate with up to 3 retry cycles ensures the scaffolding compiles cleanly.

**What bootstrap does NOT do:** No Docker, no database migrations, no E2E infrastructure, no Dockerfiles. These are handled by the feature epics and the E2E Testing epic.

**Review:** `/deepen_bootstrap` reviews the foundation. Iterates until converged.

---

## Stage 3: Space Split — Decompose Across Space

**Command:** `/space_split`
**Scope:** Per-phase (auto-detects first phase needing space split)

Decomposes a single phase into **parallel epics** with a DAG for execution ordering. Each epic can be planned and executed by its own swarm.

**Key concepts:**
- **Clusters** are kept together (strongly preferred, not absolute)
- **Epic DAG** — epics may depend on each other via execution waves
- **Inter-epic interfaces** — defined with concrete file paths from bootstrap
- **Validation criteria** — each epic has criteria for what can be verified after its swarm completes (NOT full E2E — that's phase-level)
- **E2E Testing epic** — mandatory last epic in every phase, blocked by all others. Its scope is writing the full phase-level E2E test suite and setting up any required infrastructure.

**ID Convention:** `P<N>.E<M>` — e.g., `P1.E2` (Phase 1, Epic 2). Deterministic from directory structure, no counter files.

**Output:**
- `phases/phase_N/epic_M/epic.md` — epic definition (scope, features, specs, interfaces)
- `phases/phase_N/epic_dag.json` — DAG with execution waves
- `phases/phase_N/phase_e2e_config.json` — validation scenarios + phase E2E scenarios + infrastructure requirements

**Review:** `/deepen_space_split` reviews the decomposition. Iterates until converged.

---

## Stage 4: Plan Phase Epic — Strategic Plan

**Command:** `/plan_phase_epic`
**Scope:** Per-epic (auto-detects first epic needing a plan, respects wave ordering)

Generates a **strategic development plan** for one epic. The plan is high-level — it defines WHAT and WHY, not HOW at the code level. Includes a machine-parseable **Parallelization Strategy** that defines:

- Independent components with file ownership
- Shared files needing integration
- Interfaces between components
- Execution waves
- E2E test scenarios

**Output:** `phases/phase_N/epic_M/plan.md`

**Review:** `/deepen_plan_phase_epic` reviews the plan. Iterates until converged.

---

## Stage 5: Create Issues — Tasks + Manifest + Integration Branch

**Command:** `/create_issues_from_plan_swarm`
**Scope:** Per-epic (auto-detects first epic with converged plan but no manifest)

Decomposes the plan into **file-disjoint task files** and a **swarm-manifest.json**. Each task:
- Has exclusive file ownership (no overlaps)
- Has clear acceptance criteria
- Has testing requirements
- Is assigned to an execution wave

**Task IDs:** `P<N>.E<M>.T<K>` — e.g., `P1.E2.T3` (Phase 1, Epic 2, Task 3). Integration task: `P<N>.E<M>.INT`.

**Branch creation:** This command creates the integration branch (`feat/P<N>.E<M>`) from `origin/$EIGEN_BRANCH`, checks it out, commits and pushes the artifacts, then returns to `$EIGEN_BRANCH`.

**Output:**
- `phases/phase_N/epic_M/tasks/task_001.md` ... `task_INT.md`
- `phases/phase_N/epic_M/swarm-manifest.json`
- Integration branch `feat/P<N>.E<M>` pushed to origin
- Epic metadata update (`task_ids` array in epic.md frontmatter)
- Initiative index update (`_index.md`)
- Pipeline state update (`swarm_execution` tracking object for downstream commands)

**Next step:** Checkout the integration branch (`git checkout feat/P<N>.E<M>`) and run `/orchestrate_swarm`.

---

## Stage 6: Orchestrate Swarm — Parallel Execution

**Command:** `/orchestrate_swarm`
**Scope:** Per-epic (runs on the integration branch `feat/P<N>.E<M>`, detects epic from branch name)

The **Staff Engineer / Tech Lead** that coordinates parallel swarm execution. It:

1. Verifies it's on the integration branch (`feat/P<N>.E<M>`) — both leader and each worker verify independently
2. Reads the manifest and validates it
3. Detects tech stack via `language-profiles` skill and discovers relevant domain skills
4. Creates a swarm team
5. Spawns workers wave by wave — each runs TDD:
   - Phase A: `design_validation_tests_swarm` — design tests first
   - Phase B: `code_from_validation_tests_swarm` — implement code to pass tests
   - Phase C (consumers only): re-validate against real provider implementations after stubs are replaced
6. Handles questions, blockers, integration requests as Staff Engineer
7. Runs integration phase (shared files) — verifies stub replacement and consumer Phase C completion
8. Creates PR from `feat/P<N>.E<M>` → `$EIGEN_BRANCH`
9. Stores PR info in pipeline_state.json

**Stub/interface lifecycle:** Interface providers create stubs (Protocol/ABC definitions) before Phase A. Consumers import directly from the stub file path (not via package). When providers complete implementation, they overwrite the stub entirely. Consumers then re-validate in Phase C against the real implementation.

**E2E Testing epic:** When running for the E2E Testing epic (last epic in every phase), the orchestrator operates exactly like any other epic — workers create infrastructure setup tasks and E2E test files. There is no special E2E phase inside the orchestrator.

**Testing philosophy (enforced in all workers):** Real dependencies, minimal mocks, ALWAYS. Never SQLite as substitute, never in-memory fakes, never monkeypatch. Workers must only `git add` owned files — never `git add .` or `git add -A`.

**Working notes:** Each worker maintains `swarm_working_notes/working-notes-<task.id>.md` with checkpoints. On crash, re-spawned workers resume from the last checkpoint (max 2 crashes per task before user escalation).

**Compaction resilience:** Leader state is persisted in `[WAVE-STATUS]`, `[STUB-READY]`, `[INTEGRATION-REQUEST]` tasks. Full state can be reconstructed from `TaskList()` at any time.

---

## Stage 7: Review PR — Convergence Loop

**Command:** `/review_swarm_pr`
**Scope:** Per-epic (runs on the same integration branch)

Performs a **scope-aware PR review** and iterates until ALL findings are resolved:

1. Verifies integration branch, parses epic from branch name
2. Fetches PR diff, filters to scope files only
3. Spawns review agents in parallel:
   - **Always:** security-sentinel, architecture-strategist, code-simplicity-reviewer, data-integrity-guardian, test-practices-researcher
   - **Conditional:** performance-oracle (if acceptance criteria mention performance or diff > 500 lines), pattern-recognition-specialist (if diff > 500 lines), language-specific skills (from language-profiles)
4. Triages findings (P1 critical, P2 important, P3 nice-to-have) with cross-iteration tracking (Addressed, Persistent, Regressed, New)
5. **Convergence decision:** converge if zero P1+P2+P3 findings, max 8 iterations, or oscillation detected (finding fixed in iteration N but reappeared in N+1) with no non-oscillating findings remaining
6. If not converged: creates fixup tasks (`P<N>.E<M>.R<K>`), updates manifest, pushes
7. Posts structured review on the PR with inline comments
8. Extracts lessons from P1 findings to `eigen_lessons/review_swarm_pr/`

**The convergence loop:**
```
/review_swarm_pr → finds issues → creates R tasks → pushes
    ↓
/orchestrate_swarm → executes R tasks → pushes fixes
    ↓
/review_swarm_pr → reviews again (iteration 2) → finds fewer issues
    ↓
... repeat until converged (zero findings)
    ↓
User merges PR → cleans up branch
```

---

## Key Design Principles

### Zero Arguments
Every command auto-detects its target from `pipeline_state.json` or the current branch name. No manual path arguments needed.

### Deterministic IDs (Triplets)
- Epics: `P<N>.E<M>` (Phase.Epic)
- Tasks: `P<N>.E<M>.T<K>` (Phase.Epic.Task)
- Review findings: `P<N>.E<M>.R<K>` (Phase.Epic.Review)
- Branches: `feat/P<N>.E<M>`

### Iteration-Convergence
Every main command has a deepen counterpart. The loop: main → deepen → main → deepen → converge. Convergence requires ALL high+medium findings resolved. Max 8 iterations (uniform across all deepen commands). Oscillation detection breaks cycles (finding fixed then reappeared). Deepen commands own the convergence decision — main commands accept feedback and regenerate.

### E2E Testing Epic
Each phase has a mandatory E2E Testing epic (last in the DAG). It writes the full E2E test suite and sets up infrastructure (Docker, emulators). It's just another epic — no special phases in the orchestrator.

### Branch Isolation
Swarm execution happens on the `feat/P<N>.E<M>` branch, created from `$EIGEN_BRANCH`. All code, tasks, manifests, and pipeline state are committed to this branch. The PR merges everything to `$EIGEN_BRANCH`.

### Real Dependencies, Minimal Mocks
Enforced across all workers: use real database connections, real HTTP calls, real file systems. Mocks ONLY when genuinely unavailable (e.g., third-party APIs with no sandbox). Never SQLite as substitute for PostgreSQL, never in-memory fakes, never monkeypatched connections.

### Auto-Chaining
When `$CLAUDE_TASKS_API` is set, each command automatically schedules the next command in the pipeline (with a 3-minute delay). This enables fully autonomous pipeline execution from `/time_split` through `/review_swarm_pr`. Optional Telegram notifications via `$EIGEN_TELEGRAM_CHAT_ID`.

---

## File Structure

```
$EIGEN_ROOT/
  eigen_initiative/
    _index.md                                    # Initiative-wide index
    <initiative_document>.md                     # Input: initiative
    <blackbox_requirements>.md                   # Input: feature specs
    <whitebox_reference>.md                      # Input: implementation patterns (optional)
    eigen_lessons/                               # Lessons from deepen commands
      time_split/
      bootstrap/
      space_split/
      plan_phase_epic/
      review_swarm_pr/
    phases/
      pipeline_state.json                        # Single source of truth
      initiative_summary.json                    # time_split output
      feedback/                                  # Initiative-level feedback
        deepen_time_split_feedback.json
      phase_1_manifest.md                        # time_split output
      phase_1/
        bootstrap-report.json                    # bootstrap output
        epic_dag.json                            # space_split output
        phase_e2e_config.json                    # space_split output
        feedback/                                # Phase-level feedback
          deepen_bootstrap_feedback.json
          deepen_space_split_feedback.json
        epic_1/
          epic.md                                # space_split output (scope definition)
          plan.md                                # plan_phase_epic output (strategy)
          swarm-manifest.json                    # create_issues output
          review_report_iteration_1.md           # review_swarm_pr output
          feedback/                              # Epic-level feedback
            deepen_plan_phase_epic_feedback.json
          tasks/
            task_001.md                          # create_issues output
            task_002.md
            task_INT.md                          # Integration task
            task_R001.md                         # Review fixup task
        epic_2/
          ...
        epic_3/                                  # E2E Testing epic
          epic.md
          plan.md
          ...
  swarm_working_notes/                           # Worker crash recovery checkpoints (on integration branch)
    working-notes-P1.E1.T1.md
    working-notes-P1.E1.T2.md
```

---

## Skills

The plugin bundles 25 skills. Two are **core pipeline skills** loaded by commands at runtime:

- **`pipeline-state-schema`** — Full schema definition for `pipeline_state.json`. Loaded by all commands that read/write pipeline state (time_split, bootstrap, space_split, plan_phase_epic, all deepen commands, eigen_start, eigen_continue).
- **`language-profiles`** — Language detection, toolchain mappings, adaptation notes, system prerequisites, and stack-specific skill lookup. Loaded by language-aware commands (bootstrap, orchestrate_swarm, create_issues_from_plan_swarm, plan_phase_epic, review_swarm_pr, all worker commands).

The remaining 23 skills are **domain skills** available for workers and review agents at runtime. These include: orchestrating-swarms, python-expert, python-testing-patterns, composition-patterns, react-best-practices, react-native-skills, senior-architect, security-best-practices, frontend-design, csharp-pro, agent-browser, agent-native-architecture, brainstorming, document-review, git-worktree, web-design-guidelines, and others. Workers and review agents load relevant skills based on tech stack detection via `language-profiles`.

---

## Commands Not Yet Updated

- `compound_improve.md` — Self-improvement command that reads lessons and rewrites command prompts. Still uses old patterns (arguments, `plan_from_gh_issue_swarm` references).
- `guide_eigen_architecture.md` — Architecture guide document with outdated command references (`plan_from_gh_issue_swarm`, `deepen_plan` which no longer exist), incorrect command signatures (claims positional arguments where current commands are zero-argument), wrong iteration limits (claims 5/3 where all are 8), and obsolete file paths (`Plans/plan-for-epic-<N>.md`). Core architectural concepts (file ownership, interface dependencies, communication protocols) remain accurate.
