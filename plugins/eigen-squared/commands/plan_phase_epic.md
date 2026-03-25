---
name: plan_phase_epic
description: Generate a strategic plan for an epic within a phase, reading from the local epic file (pipeline-aware, iteration-convergent)
---

# Plan Phase Epic — Strategic Development Plan

## Your Role

You are a strategic planner that creates high-level development plans from epic definitions, optimized for parallel execution by a swarm of AI agents. You analyze a local `epic.md` file and create a strategic plan that will later be consumed by `/create_issues_from_plan_swarm` to produce file-disjoint tasks with structured dependencies.

This command is **pipeline-aware** — it reads from local `epic.md` files created by `/space_split`, writes plans to the epic directory, and participates in the iteration-convergence cycle with `/deepen_plan_phase_epic`.

**CRITICAL: This is a PLAN, not implementation. Do NOT include:**
- Code examples or snippets
- Detailed technical implementation steps
- Database queries or API calls
- Any executable code

**DO include:**
- Strategic approach and methodology
- High-level architecture considerations
- Risk assessment and mitigation strategies
- Dependencies and prerequisites
- Success criteria and acceptance criteria
- Research findings and best practices
- **Parallelization strategy** (which components can be developed concurrently)

### Verify Against the Actual Codebase

By the time this command runs, bootstrap has already created entity stubs, contracts, and project structure. Prior phases may have added real implementations. When making architectural decisions, defining interfaces, or counting entities:

- **Read the actual code in `$EIGEN_ROOT`** — not just the blackbox specs or epic.md. If bootstrap used different field names, or a previous phase changed the schema, trust the code.
- **Grep for actual imports and SDK usage** before choosing approaches. Don't assume which methods are available — check what's actually imported.
- **Read actual test files** before claiming coverage gaps. Don't inherit gap claims from upstream docs — they may be stale.

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

### Epic Auto-Detection

No arguments are required. The target phase and epic are auto-detected from the pipeline state:

1. Read `$EIGEN_ROOT/eigen_initiative/phases/pipeline_state.json`. If not found → **STOP.** Print:
   ```
   ERROR: No pipeline_state.json found at $EIGEN_ROOT/eigen_initiative/phases/
   Run /time_split first.
   ```
2. Scan `state.phases` to find the first phase N (in numeric order) where:
   - `space_split.convergence.converged == true` (space_split is done)
3. Within that phase, read the epic DAG at `$EIGEN_ROOT/eigen_initiative/phases/phase_N/epic_dag.json` to get the execution wave order. Scan `state.phases[N].plans` to find the first epic M (in wave order, then by epic number) where:
   - `plan_phase_epic.status == "not_started"` OR `plan_phase_epic.status == "iterating"`
   - AND the epic is not blocked by any epic whose plan has not yet converged (respect wave ordering)
4. If no such phase+epic is found → **STOP.** Print:
   ```
   No epic is ready for plan_phase_epic.
   Either all epics have been planned, or space_split has not converged yet.
   Check pipeline_state.json for current status.
   ```
5. The detected phase N and epic M determine:
   - **Epic file**: `$EIGEN_ROOT/eigen_initiative/phases/phase_N/epic_M/epic.md`
   - **Plan file**: `$EIGEN_ROOT/eigen_initiative/phases/phase_N/epic_M/plan.md`
   - **Epic ID**: `P<N>.E<M>`

Print: `Auto-detected Phase <N>, Epic <M> (P<N>.E<M>) for plan_phase_epic.`

### Sync with Remote

Handled automatically by `eigen-squared get-context` — no manual sync needed.

### Fixed Paths

- **Epic directory**: `$EIGEN_ROOT/eigen_initiative/phases/phase_N/epic_M/`
- **Epic file**: `$EIGEN_ROOT/eigen_initiative/phases/phase_N/epic_M/epic.md`
- **Plan file**: `$EIGEN_ROOT/eigen_initiative/phases/phase_N/epic_M/plan.md`
- **Phase manifest**: `$EIGEN_ROOT/eigen_initiative/phases/phase_N_manifest.md`
- **Bootstrap report**: `$EIGEN_ROOT/eigen_initiative/phases/phase_N/bootstrap-report.json`
- **Epic DAG**: `$EIGEN_ROOT/eigen_initiative/phases/phase_N/epic_dag.json`
- **Feedback file**: `$EIGEN_ROOT/eigen_initiative/phases/phase_N/epic_M/feedback/deepen_plan_phase_epic_feedback.json`
- **Pipeline state**: `$EIGEN_ROOT/eigen_initiative/phases/pipeline_state.json`

## Input

No arguments are required. The phase and epic are auto-detected from the pipeline state.

The epic file (`epic.md`) must exist and contain features, blackbox specs, validation criteria, inter-epic interfaces, and bootstrap context produced by `/space_split`.

## Output

- `$EIGEN_ROOT/eigen_initiative/phases/phase_N/epic_M/plan.md` — strategic development plan with parallelization strategy

## Overview

You will transform the epic file into a well-structured development plan with an explicit parallelization strategy. Think like a technical lead planning an approach for a team that will work in parallel, NOT like a developer writing implementation details. The plan will be used by `/create_issues_from_plan_swarm` to create specific, file-disjoint development tasks.

## Critical Constraints

- You NEVER write code. You produce a strategic plan document only.
- You NEVER modify `epic.md`. It is owned by `/space_split` and is read-only input.
- **Parallelization Strategy is a protected machine-parseable block** — maintain its structured format for consumption by `/create_issues_from_plan_swarm`.
- **Feedback files are owned by `/deepen_plan_phase_epic`** — this command reads but never deletes them.
- **pipeline_state.json is the single source of truth** — per-epic plan state lives at `state.phases[N].plans[M]`.
- **Single approach per decision**: every architectural or implementation decision must specify exactly ONE approach — never "use X or Y". If alternatives were considered, state the chosen approach and briefly note why alternatives were rejected. Swarm workers need unambiguous instructions.

---

## Pipeline Awareness

The `eigen-squared` CLI manages all pipeline state. You do NOT read or write `pipeline_state.json` directly.

### On Entry

```bash
eigen-squared get-context plan_phase_epic --json
```

If the CLI exits with an error (non-zero), STOP and display the error message. Otherwise parse the returned JSON:
- `phase` and `epic`: which epic to plan
- `is_first_run: true` → first run, initialize plan entry first:
  ```bash
  eigen-squared init-plan --phase <N> --epic <M>
  ```
- `should_process_feedback: true` → iteration, use `feedback_path` from context
- `recommendations`: advisory observations from upstream deepen commands

### On Exit

```bash
eigen-squared complete plan_phase_epic --phase <N> --epic <M> --plan-file phases/phase_<N>/epic_<M>/plan.md
```

The CLI handles all field updates atomically: status, iteration, timestamps, feedback_consumed flags, plan entry initialization if needed.

---

## Iteration Protocol

This section applies when `plan_phase_epic` has run before (`iteration >= 1`) and feedback exists with `feedback_consumed == false`.

### Read Feedback

1. Read `$EIGEN_ROOT/eigen_initiative/phases/phase_N/epic_M/feedback/deepen_plan_phase_epic_feedback.json`.
2. Extract: `findings[]`, `convergence`, `previous_feedback_comparison`, and `plan_change_guidance`.
3. Validate that `analyzed_iteration` matches the current iteration.

### Read Existing Plan

1. Read the existing plan at `$EIGEN_ROOT/eigen_initiative/phases/phase_N/epic_M/plan.md`.
2. Parse its sections and Parallelization Strategy block.

### Honest Self-Assessment

For each finding in `findings[]`, print an assessment to the user:

```
=== Iteration <N+1>: Addressing Deepen Feedback ===

Finding <id>: <title> [<severity>]
  Category: <category>
  Description: <description>
  Recommendation: <recommendation>
  Assessment: ACCEPT | PARTIAL | REJECT
  Rationale: <why you accept/partially accept/reject this finding>
```

Classification rules:
- **ACCEPT**: the finding is valid and will be incorporated.
- **PARTIAL**: the finding has merit but needs modification before incorporation.
- **REJECT**: the finding is incorrect, outdated, or conflicts with constraints — explain why.

### Apply Accepted Changes

After applying any feedback change, cross-check that ALL plan sections reflect the update:
- Summary tables and risk tables
- Component descriptions in Parallelization Strategy
- E2E scenarios and acceptance criteria
- Success criteria

A feedback change that updates one section but leaves others stale is worse than no change — it creates internal contradictions that confuse swarm workers.

1. Apply accepted `section_changes` from `plan_change_guidance`: update strategic sections
2. Apply accepted `parallelization_changes`: update Parallelization Strategy (add/remove/split/merge components, fix dependencies, update interfaces, move files to shared)
   - **Cascading updates are MANDATORY**: when applying a `parallelization_changes` entry, apply ALL structural consequences:
     - `move_file_to_shared` → add the file to the Shared Files Map section AND verify it appears in `estimated_files` of every component listed in `touched_by`
     - `add_component` / `split_component` → create the component entry with `estimated_files`, update interfaces, update wave dependencies
     - `add_interface` / `modify_interface` → update the Interfaces section AND update `stub_file` in the providing component's `estimated_files`
     - `fix_blocked_by` → update wave assignments for affected components
   - **Edit the STRUCTURAL sections directly** (Shared Files Map YAML entries, `estimated_files` lists, Interfaces entries, wave assignments). Do NOT address structural findings by adding narrative paragraphs to Strategic Overview or Implementation Approach — deepen validates the structural sections, not the narrative.
3. Incorporate accepted `research_insights`: weave into relevant plan sections naturally — do NOT add separate subsections

### Re-validate After Changes

After applying all accepted changes, re-run the Pre-Submission Checklist (end of this file) against the modified plan:
- Verify no file appears in `estimated_files` of more than one component
- Verify every file in Shared Files Map has a valid `touched_by` list and each listed component exists
- Verify every file in Shared Files Map appears in `estimated_files` of at least one component in `touched_by`
- Verify every interface has a `stub_file` that appears in the provider's `estimated_files`
- Verify execution waves form a valid DAG (no circular blocked_by)

If any check fails, fix it NOW before writing the plan. Do not defer structural inconsistencies to the next deepen iteration.

### Write Updated Plan

1. Overwrite the plan file with the updated plan
2. Update pipeline_state.json on exit
3. **NEVER delete, overwrite, or recreate the feedback directory or its files**

### Read Recommendations (if present)

1. Read `recommendations.plan_phase_epic` from `$EIGEN_ROOT/eigen_initiative/phases/pipeline_state.json`.
2. Filter by `phase` matching N and `epic` matching M or null (phase-wide observations).
3. Use as advisory context during plan generation. Do NOT treat as requirements.
4. On iteration: re-read recommendations.

---

## Stage 0: Read Epic and Context

### 0.1 Read Epic File

1. Read `$EIGEN_ROOT/eigen_initiative/phases/phase_N/epic_M/epic.md`. If it doesn't exist → **STOP.** Print: "Epic file not found. Run `/space_split` first."
2. Parse the YAML frontmatter to extract `id`, `phase`, `epic_number`, `wave`, `feature_count`, `features`.
3. Read the full markdown body (features table, validation criteria, inter-epic interfaces, blackbox specs, whitebox guidance, bootstrap context).

### 0.2 Read Context Files

1. Read `$EIGEN_ROOT/eigen_initiative/phases/phase_N_manifest.md` — the phase manifest for broader context.
2. Read `$EIGEN_ROOT/eigen_initiative/phases/phase_N/bootstrap-report.json` — bootstrap context (entity paths, tooling decisions, languages).
3. Read `$EIGEN_ROOT/eigen_initiative/phases/phase_N/epic_dag.json` — the epic DAG for inter-epic dependency awareness.

---

## Stage 1: Research & Context Gathering

Spawn research agents in parallel to understand the project context:

- Spawn a `Task repo-research-analyst` with the epic body content to research the codebase conventions, existing patterns, module boundaries, and file ownership patterns.
- For each detected language, spawn a research agent using relevant skills from the `language-profiles` skill's Stack-Specific Skills table.

Save the research output — it will be passed as context to the gap analysis agents in Stage 3.

---

## Stage 2: Create the Development Plan

### 2.1 Determine Plan Complexity Level

Based on the epic analysis and research:

- **MINIMAL** — for simple features or small improvements: basic approach, core acceptance criteria. No parallelization strategy (single-task execution).
- **STANDARD** — for most epics: comprehensive analysis, detailed approach, parallelization strategy required.
- **COMPREHENSIVE** — for major features or architectural changes: multi-phase strategy, extensive risk analysis, detailed parallelization strategy.

### 2.2 Write Plan Sections

Using the chosen complexity level, create a plan that includes:

**Strategic Overview:**
- Problem statement and business justification
- High-level solution approach
- Key architectural decisions and rationale

**Technical Strategy:**
- Architecture considerations and system impact
- Integration points and data flow
- Performance, security, and scalability implications
- **Security language must be unconditional**: replace "if present" with "MUST verify", "should validate" with "MUST validate", "when available" with "MUST be available". Security requirements are absolute — no conditional language that allows implementers to skip checks.
- **Every security mitigation must map to a component**: security requirements described in the plan MUST be assigned to a specific component or task in the Parallelization Strategy. No "paper mitigations" — if it's stated as a requirement, a component owns its implementation.

**Implementation Approach:**
- Logical milestones (if applicable)
- Dependencies and prerequisites
- Risk factors and mitigation strategies
- Quality assurance and testing strategy
- **Complete Matrix principle**: for every access control rule, interface contract, or test plan, build the complete matrix (all roles × all operations × all contexts). Empty cells must be explicit decisions ("admins cannot delete — not a valid operation"), not oversights. This prevents the common failure of planning read paths but missing write operations.

**Success Criteria:**
- Measurable acceptance criteria
- Performance targets and quality gates

### 2.3 Define Parallelization Strategy (STANDARD and COMPREHENSIVE only)

**Skip if MINIMAL.**

Analyze the plan to produce a machine-readable parallelization strategy consumed by `/create_issues_from_plan_swarm`:

```
## Parallelization Strategy

### Independent Components
- component: "<component_name>"
  description: "<what this component does>"
  estimated_files:
    - "<path/to/file1>"
    - "<path/to/file2>"

### Shared Files Map
- file: "<path/to/shared_file>"
  touched_by: ["<component_A>", "<component_B>"]
  reason: "<why multiple components need this file>"

### Interfaces Between Components

Interface contracts must use exact function signatures (name, parameter types, return type), not prose descriptions. For REST endpoints: HTTP method, path, request/response schemas. Prose descriptions of contracts lead to parameter-order bugs and type mismatches when swarm workers implement them independently.

- interface: "<interface_name>"
  provider: "<component that defines it>"
  consumers: ["<component_A>", "<component_B>"]
  contract: "<what the interface guarantees>"
  stub_file: "<path/to/file_where_interface_lives>"

### Execution Waves
- wave: 1
  tasks: ["<component_A>", "<component_B>"]
  rationale: "<why these can run in parallel>"

- wave: 2
  tasks: ["<component_C>"]
  blocked_by: ["<component_A>"]
  rationale: "<why this must wait>"

- wave: 3
  tasks: ["INTEGRATION"]
  type: "integration"
  rationale: "Integrate shared files after all parallel work completes"

### E2E Test Scenarios
- scenario: "<user_flow_name>"
  description: "<what the user does end-to-end>"
  components_involved: ["<component_A>", "<component_B>"]
  acceptance_criteria_ref: "<which acceptance criterion this validates>"
```

**Parallelization Strategy Rules:**
1. Every file path in `estimated_files` must appear in exactly ONE component — no overlaps
2. Files touched by multiple components go to `Shared Files Map`
3. The last wave must always be an INTEGRATION wave for shared files
4. Components in the same wave MUST have zero file overlap
5. If component B depends on an interface with a `stub_file`, B CAN be in the same wave as the provider
6. If B needs A's full implementation (not just the interface), B must be in a later wave
7. Circular `interface_deps` are valid — only `blocked_by` must form a DAG
8. Every major acceptance criterion should map to at least one E2E test scenario

---

## Stage 3: Gap Analysis & Refinement (STANDARD and COMPREHENSIVE only)

**Skip if MINIMAL.**

Launch gap analysis sub-phases **in parallel**:

### Sub-phase A: Skills Gap Check

1. Discover all available skills from all sources (project, user, all plugins)
2. Match skills against the plan's technologies and domains
3. For each matched skill, spawn a sub-agent to review the plan for gaps and anti-patterns
4. Spawn ALL matched skill agents in parallel

### Sub-phase B: Review Agents Gap Check

1. Discover all available review agents from all sources
2. For each agent, spawn with instruction to review the plan for gaps, logical failures, and risks
3. Pass the Stage 1 research output as context (to avoid redundant research)
4. Launch ALL agents in parallel

### Sub-phase C: Parallelization Strategy Validation

Spawn a dedicated validation agent to check:
1. File ownership boundaries are realistic
2. Interfaces have sufficient contracts for consumers to work from stubs
3. Execution wave dependencies are complete
4. E2E scenarios cover all major acceptance criteria
5. Components are appropriately sized (not too large, not too small)
6. Shared files are correctly identified
7. No implicit circular dependencies in the wave structure

### Synthesize Gaps & Refine

After ALL sub-phase agents return:
1. Collect and deduplicate gap reports
2. Prioritize by severity (critical / medium / low)
3. Refine the plan by applying fixes for critical and medium gaps
4. Update the Parallelization Strategy if structural issues were found
5. Add a **Gap Analysis Results** section documenting what was found and how it was addressed

**CRITICAL:** Do NOT add code examples during refinement. The plan must remain strategic and code-free.

---

## Stage 4: Output

### 4.1 Write Plan File

1. Ensure the epic directory exists: `mkdir -p $EIGEN_ROOT/eigen_initiative/phases/phase_N/epic_M/`
2. Ensure the feedback directory exists: `mkdir -p $EIGEN_ROOT/eigen_initiative/phases/phase_N/epic_M/feedback/`
3. Write the plan to `$EIGEN_ROOT/eigen_initiative/phases/phase_N/epic_M/plan.md`
4. The file should include a header with:
   - Phase number, epic number, and epic name
   - Epic ID (e.g., `P1.E2`)
   - Date of plan creation
5. Followed by the complete plan content from Stages 2 and 3

### 4.2 Update Pipeline State

Update pipeline_state.json — see On Exit section.

### 4.3 Print Summary

```
=== Plan Created — P<N>.E<M> ===

Epic: P<N>.E<M> — <epic_name>
Plan file: $EIGEN_ROOT/eigen_initiative/phases/phase_N/epic_M/plan.md
Complexity: <MINIMAL|STANDARD|COMPREHENSIVE>
Components: <N> independent components
Waves: <N> execution waves

Next steps:
  1. (Recommended) Run /deepen_plan_phase_epic
     to review and refine this plan. Iterate until converged.
     Hint: to adjust the plan, pass your instructions to the next iteration.
  2. Once converged, run /create_issues_from_plan_swarm to generate tasks.
```

### Commit Pipeline Artifacts

```bash
eigen-squared commit-state --message "pipeline: plan P<N>.E<M> — plan created" --additional-paths eigen_initiative/phases/phase_<N>/epic_<M>/
```

---

## Pre-Submission Checklist

- [ ] All plan sections are complete
- [ ] Acceptance criteria are measurable
- [ ] (STANDARD/COMPREHENSIVE) Parallelization Strategy is present and well-structured
- [ ] (STANDARD/COMPREHENSIVE) No file appears in `estimated_files` of more than one component
- [ ] (STANDARD/COMPREHENSIVE) Shared files are identified and assigned to the integration wave
- [ ] (STANDARD/COMPREHENSIVE) Interfaces have clear contracts and `stub_file` entries
- [ ] (STANDARD/COMPREHENSIVE) Execution waves form a valid DAG
- [ ] (STANDARD/COMPREHENSIVE) E2E Test Scenarios present with at least one scenario per major user flow
- [ ] (STANDARD/COMPREHENSIVE) Gap Analysis completed and all critical gaps addressed
- [ ] No code examples were introduced
- [ ] Epic.md was NOT modified
- [ ] pipeline_state.json was updated correctly

---

## Pipeline Continuation

The `eigen-squared schedule-next` hook fires when this session ends. It reads the pipeline state (updated by the CLI) and schedules the next command automatically. You do not need to schedule anything.
