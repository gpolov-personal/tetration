---
name: deepen_plan_phase_epic
description: Review plan_phase_epic output with parallel research agents, produce iteration feedback with plan change guidance, and decide convergence
---

# Deepen Plan Phase Epic — Plan Review & Convergence

## Introduction

This command takes the output of `/plan_phase_epic` (a `plan.md` file) and subjects it to comprehensive review by parallel research, skill, and review agents. Every structural, strategic, and parallelization issue is diagnosed.

**This command never modifies the plan file.** All findings, research insights, and recommendations go into a structured feedback JSON file. This follows the same separation principle as all other deepen commands.

Diagnosed errors are written as structured lesson JSONs to `$EIGEN_ROOT/eigen_initiative/eigen_lessons/plan_phase_epic/`. These lessons are later consumed by `/compound_improve` to permanently improve the `plan_phase_epic` command itself.

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
   Run /time_split, /bootstrap, /space_split, and /plan_phase_epic first.
   ```
2. Scan `state.phases` to find the first phase N (in numeric order) where `space_split` has converged. Within that phase, scan `state.phases[N].plans` to find the first epic M (in wave order) where:
   - `plan_phase_epic.status == "completed"` OR `plan_phase_epic.status == "iterating"` (plan has run)
   - AND `plan_phase_epic.convergence.converged == false` (not yet converged)
3. If no such phase+epic is found → **STOP.** Print:
   ```
   No epic is ready for deepen_plan_phase_epic.
   Either all plans have converged, or plan_phase_epic has not run yet.
   Run /plan_phase_epic if needed, or check pipeline_state.json.
   ```
4. The detected phase N and epic M determine:
   - **Plan file**: `$EIGEN_ROOT/eigen_initiative/phases/phase_N/epic_M/plan.md`
   - **Epic file**: `$EIGEN_ROOT/eigen_initiative/phases/phase_N/epic_M/epic.md`
   - **Feedback file**: `$EIGEN_ROOT/eigen_initiative/phases/phase_N/epic_M/feedback/deepen_plan_phase_epic_feedback.json`
   - **Lessons directory**: `$EIGEN_ROOT/eigen_initiative/eigen_lessons/plan_phase_epic/`
   - **Epic ID**: `P<N>.E<M>`

Print: `Auto-detected Phase <N>, Epic <M> (P<N>.E<M>) for deepen_plan_phase_epic.`

---

## Pipeline Awareness

Deepen plan phase epic operates at per-epic scope within a phase. Load the `pipeline-state-schema` skill for the full schema, field definitions, and feedback lifecycle.

### On Entry

The pipeline state was already read during Epic Auto-Detection. Now check deepen-specific state:

- Check `state.phases[N].plans[M].deepen_plan_phase_epic.feedback_consumed`:
  - `feedback_consumed == false` AND feedback file exists → warn: "Existing feedback has not been consumed by plan_phase_epic yet. Re-analyzing will overwrite it." Proceed anyway.
- Read current iteration to determine iteration context.

### On Exit

Update `$EIGEN_ROOT/eigen_initiative/phases/pipeline_state.json`:
- Initialize `state.phases[N].plans[M].deepen_plan_phase_epic` if it doesn't exist
- Set `state.phases[N].plans[M].deepen_plan_phase_epic.status` to `"completed"`
- Increment `state.phases[N].plans[M].deepen_plan_phase_epic.iteration`
- Set `state.phases[N].plans[M].deepen_plan_phase_epic.last_run_at` to current ISO 8601 timestamp
- Set `state.phases[N].plans[M].deepen_plan_phase_epic.feedback_path` to the feedback file path
- Set `state.phases[N].plans[M].deepen_plan_phase_epic.feedback_consumed` to `false` (fresh feedback)
- Set `state.phases[N].plans[M].plan_phase_epic.feedback_consumed` to `false` (signal to plan_phase_epic)
- Update `state.phases[N].plans[M].deepen_plan_phase_epic.findings_summary` with counts
- If convergence was decided:
  - Set `state.phases[N].plans[M].plan_phase_epic.convergence.converged` to `true`
  - Set `state.phases[N].plans[M].plan_phase_epic.convergence.decided_by` to `"deepen_plan_phase_epic"`
  - Set `state.phases[N].plans[M].plan_phase_epic.convergence.decided_at` to current ISO 8601 timestamp
  - Set `state.phases[N].plans[M].plan_phase_epic.convergence.reason` to the convergence rationale
  - Write low-severity findings with downstream impact to `recommendations` (see Phase 4.5)
- If continuing iteration:
  - Set `state.phases[N].plans[M].plan_phase_epic.status` to `"iterating"`
- Set `updated_at` to current timestamp

---

## Iteration Protocol

### Detect Iteration Context

1. Check if the feedback file already exists (previous feedback from an earlier deepen run).
2. If it exists, read it for comparison, oscillation detection, and progress tracking.
3. If no previous feedback exists, this is the first deepen iteration.

### Finding Matching Protocol (iteration 2+)

When comparing current findings against previous iteration findings, use **file-path matching** — not title or description matching:

1. For each current finding, extract all file paths mentioned in `description`, `recommendation`, and `affected_section` (e.g., `app/lib/websocket/client.ts`, `server/websocket/bridge.ts`).
2. For each previous finding, extract the same file paths.
3. Two findings **match** if they share at least one file path AND belong to the same `category` (e.g., both are `dependency_gap` about `client.ts`).
4. Classify matched findings:
   - **Persisting**: current finding matches a previous finding that was NOT addressed → add previous ID to `findings_persisting`
   - **Regressed**: current finding matches a previous finding that WAS addressed (appeared in `findings_addressed` of the previous comparison) → add to `findings_regressed`
   - **Oscillating**: current finding matches a finding that has appeared in 3+ non-consecutive iterations, or has been in `findings_regressed` at least once → add to `oscillating_findings`
5. Findings with NO file-path match to any previous finding → `new_findings`.

This protocol is deterministic: file paths don't change between reformulations of the same issue, unlike titles and descriptions which the LLM may rephrase each iteration.

### Convergence Decision Protocol

After collecting all findings (Phase 5), apply these convergence rules **in order**:

1. **Converge if**: zero high-severity findings AND zero medium-severity findings remain AND Parallelization Strategy validates clean.
   - Rationale: "All significant issues resolved."

2. **Converge if**: iteration limit reached (`state.phases[N].plans[M].deepen_plan_phase_epic.iteration >= 8`).
   - Rationale: "Maximum iteration limit (8) reached. Accepting current state."

3. **Converge if**: stagnation detected — more than 50% of current high+medium findings match (by file path, per the Finding Matching Protocol) findings from 2 iterations ago (i.e., the findings are cycling without resolution).
   - Rationale: "Stagnation detected. The same files keep appearing in findings across iterations. Accepting current state — remaining issues are better resolved by create_issues_from_plan_swarm's file ownership validation."

4. **Converge if**: oscillation detected AND no non-oscillating high-severity or medium-severity findings remain.
   - Rationale: "Oscillation detected. Accepting current state to break the cycle."

5. **Continue if**: any high-severity or medium-severity actionable findings remain that have not oscillated or stagnated.

---

## Phase 0: Ingest

### 0.1 Read Plan File

1. Read `$EIGEN_ROOT/eigen_initiative/phases/phase_N/epic_M/plan.md`. If it doesn't exist → **STOP.** Print: "No plan found. Run `/plan_phase_epic` first."
2. Extract and identify each major section: Strategic Overview, Technical Strategy, Implementation Approach, Success Criteria, Gap Analysis Results, Parallelization Strategy.

### 0.2 Read Context Files

1. Read `$EIGEN_ROOT/eigen_initiative/phases/phase_N/epic_M/epic.md` — the epic definition (features, blackbox specs, interfaces)
2. Read `$EIGEN_ROOT/eigen_initiative/phases/phase_N_manifest.md` — the parent phase manifest
3. Read `$EIGEN_ROOT/eigen_initiative/phases/phase_N/bootstrap-report.json` — bootstrap context (entity paths, tooling decisions)
4. Read `$EIGEN_ROOT/eigen_initiative/phases/phase_N/epic_dag.json` — inter-epic dependency context

### 0.3 Load Existing Lessons

1. Glob `$EIGEN_ROOT/eigen_initiative/eigen_lessons/plan_phase_epic/*.json`.
2. Read and parse each lesson JSON — used to avoid duplicating known issues.

### 0.4 Read Upstream Recommendations (Awareness)

Read `recommendations.plan_phase_epic` from `$EIGEN_ROOT/eigen_initiative/phases/pipeline_state.json`. Filter by current phase and epic number (include entries where `epic` is null — phase-wide observations).

Use as additional context when reviewing the plan:
- They inform your analysis but do NOT constitute findings on their own.
- Do NOT create findings solely because a recommendation was not addressed.
- You MAY reference a recommendation in a finding's rationale if you independently identify a related issue.

---

## Phase 1: Skills Application

### 1.1 Discover and Apply Available Skills

1. Discover ALL available skills from all sources (project, user, all plugins).
2. Match skills against the plan's technologies and domains.
3. For each matched skill, spawn a sub-agent to review the plan for gaps and anti-patterns.
4. Spawn ALL matched skill agents in parallel.

---

## Phase 2: Per-Section Research

For each major section identified in the plan, spawn research agents in parallel to find best practices, common pitfalls, and real-world patterns relevant to that section's topic.

---

## Phase 3: Review Agents

### 3.1 Discover and Run All Review Agents

1. Discover all available review agents from all sources (project, user, all plugins).
2. For each agent, spawn with instruction to review the plan for gaps, logical failures, and risks.
3. Launch ALL agents in parallel.

### 3.2 Parallelization Strategy Validation

Spawn a dedicated validation agent to check:
1. File ownership boundaries are realistic
2. Interfaces have sufficient contracts for consumers to work from stubs
3. Execution wave dependencies are complete
4. E2E scenarios cover all major acceptance criteria
5. Components are appropriately sized
6. Shared files are correctly identified
7. No implicit circular dependencies in the wave structure

---

## Phase 4: Synthesize & Write Feedback

### 4.1 Collect All Agent Results

Wait for ALL parallel agents to complete. Collect findings from:
- Skills agents (Phase 1)
- Research agents (Phase 2)
- Review agents (Phase 3)

### 4.2 Categorize Findings

For each finding, assign:

- **`category`**: one of:
  - `parallelization_error` — bad wave ordering, file ownership overlap, missing blocked_by
  - `plan_structure_gap` — missing required section, thin strategic overview, vague acceptance criteria
  - `technology_mismatch` — ignores whitebox guidance, wrong framework, incompatible patterns
  - `dependency_gap` — missing interface definition, undeclared shared files, implicit coupling
  - `test_coverage_gap` — missing E2E scenarios, untestable criteria, no edge cases
  - `strategic_concern` — over-engineering, wrong abstraction level, risk concentration
  - `false_positive` — flagged but correct upon analysis

- **`severity`**: `high` (breaks correctness or swarm execution), `medium` (suboptimal but functional), `low` (minor improvement)

- **`affected_section`**: which section of the plan this applies to

- **`downstream_impact`**: what this finding means for downstream `create_issues_from_plan_swarm`

### 4.3 Deduplicate & Prioritize

- Merge similar findings from multiple agents.
- Flag conflicting advice for user review.
- Group by plan section.
- Filter out `false_positive` findings.

### 4.3.1 Narrative vs Structural Assessment

For each finding that flags a missing structural entry (e.g., file not in Shared Files Map, file not in estimated_files, missing interface contract):

1. **Check if the behavior IS described in narrative sections** (Key Architectural Decisions, Implementation Approach, Integration Points, Risk Factors). Search for the file path, function name, or concept in the full plan text.
2. **If narratively present but structurally absent**: the finding is valid (the structural section MUST be fixed), but **downgrade severity to medium** if it was classified as high. The plan author understands the requirement — they just failed to wire it into the structural section. Include in `plan_change_guidance.parallelization_changes` with explicit `structural_edits` showing exactly which YAML/list entries to add or modify.
3. **If neither narratively nor structurally present**: keep original severity — the plan genuinely missed this concern.

This prevents findings from persisting across iterations when the plan author keeps adding narrative explanations instead of editing the structural sections.

### 4.4 Write Feedback File

Write the feedback to `$EIGEN_ROOT/eigen_initiative/phases/phase_N/epic_M/feedback/deepen_plan_phase_epic_feedback.json`.

Ensure directory exists: `mkdir -p $EIGEN_ROOT/eigen_initiative/phases/phase_N/epic_M/feedback/`

```json
{
  "schema_version": "1.0.0",
  "command": "deepen_plan_phase_epic",
  "phase": <N>,
  "epic": <M>,
  "epic_id": "P<N>.E<M>",
  "iteration": "<current deepen iteration>",
  "analyzed_iteration": "<plan_phase_epic iteration that was analyzed>",
  "created_at": "<ISO 8601>",
  "source_outputs_analyzed": {
    "plan_file": "phases/phase_N/epic_M/plan.md",
    "epic_file": "phases/phase_N/epic_M/epic.md"
  },
  "convergence": {
    "decision": "continue|converged",
    "rationale": "<why, referencing downstream impact>",
    "iteration_limit_reached": false,
    "max_iterations": 8,
    "oscillation_detected": false,
    "oscillation_details": null
  },
  "previous_feedback_comparison": {
    "has_previous": "<true if previous feedback existed>",
    "previous_iteration": "<previous iteration number or null>",
    "findings_addressed": ["<finding IDs resolved>"],
    "findings_persisting": ["<finding IDs still present>"],
    "findings_regressed": ["<finding IDs that reappeared>"],
    "new_findings": ["<finding IDs new this iteration>"],
    "oscillating_findings": ["<finding IDs that have oscillated>"]
  },
  "findings": [
    {
      "id": "dpf-<sequential_number>",
      "category": "<parallelization_error|plan_structure_gap|technology_mismatch|dependency_gap|test_coverage_gap|strategic_concern>",
      "severity": "high|medium|low",
      "title": "<concise>",
      "description": "<detailed>",
      "affected_section": "<which plan section>",
      "recommendation": "<specific action for plan_phase_epic to take>",
      "actionable_by": "plan_phase_epic",
      "downstream_impact": {
        "affects_commands": ["create_issues_from_plan_swarm"],
        "impact_description": "<what breaks downstream>"
      }
    }
  ],
  "plan_change_guidance": {
    "description": "Specific instructions for plan_phase_epic's next iteration",
    "section_changes": [
      {
        "section": "<e.g., Technical Strategy>",
        "action": "add|modify|remove",
        "detail": "<what to change and why>"
      }
    ],
    "parallelization_changes": [
      {
        "type": "add_component|remove_component|split_component|merge_components|add_interface|modify_interface|move_file_to_shared|fix_blocked_by|add_e2e_scenario|modify_wave",
        "detail": "<specific change — MUST include ALL structural edits required, not just the primary change>",
        "structural_edits": [
          "<exact edit 1: e.g., 'Add to Shared Files Map: - file: \"path/to/file\" touched_by: [\"comp_a\"] reason: \"...\"'>",
          "<exact edit 2: e.g., 'Add \"path/to/file\" to comp_a estimated_files list'>",
          "<exact edit 3: e.g., 'Update comp_b description to mention this dependency'>"
        ]
      }
    ],
    "research_insights": [
      {
        "target_section": "<e.g., Technical Strategy>",
        "insight_type": "best_practice|performance|security|edge_case",
        "content": "<the research finding to incorporate>"
      }
    ]
  },
  "summary": {
    "total_findings": "<count>",
    "by_severity": { "high": "<count>", "medium": "<count>", "low": "<count>" },
    "by_category": { "<category>": "<count>" }
  }
}
```

The `research_insights` array is where deepen's research depth goes — structured as data for `plan_phase_epic` to weave in naturally during its Iteration Protocol.

Apply the Convergence Decision Protocol to set `convergence.decision`.

### 4.5 Generate Convergence Recommendations (CONVERGED ONLY)

**Skip this section entirely if convergence decision is NOT "converged".**

At convergence, scan low-severity findings for cross-stage insights worth preserving for downstream commands. See the `pipeline-state-schema` skill for the full recommendations specification.

1. **Filter findings with downstream impact:** Only low-severity findings where `downstream_impact.affects_commands` is non-empty.
2. **For `create_issues_from_plan_swarm`**, draft a 1-2 sentence observation about the plan's Parallelization Strategy and its implications for task generation.
3. **Write to pipeline_state.json** — update `recommendations.create_issues_from_plan_swarm`:
   - Replace all entries where `from` == `"deepen_plan_phase_epic"` (preserve entries from other deepen commands).
   - Max 5 entries per target command.
   - Each entry: `{ "from": "deepen_plan_phase_epic", "at_iteration": <current iteration>, "phase": <N>, "epic": <M>, "text": "<observation>" }`
4. If no findings have downstream impact, do not write any recommendations.

**Constraints:**
- Recommendations are OPTIONAL. Only write when you genuinely have cross-stage insight.
- Write observations and implications, NOT action items.

---

## Phase 5: Lesson Extraction

### 5.1 Generate Lesson JSONs

For each non-false-positive finding, create a lesson JSON:

```json
{
  "id": "pl-lesson-<timestamp>-<sequential>",
  "created_at": "<ISO 8601 timestamp>",
  "command": "plan_phase_epic",
  "status": "pending",
  "category": "<category from 5.2>",
  "severity": "<high|medium|low>",
  "title": "<concise description of the error>",
  "description": "<detailed explanation of what went wrong>",
  "root_cause": "<why plan_phase_epic produced this error>",
  "recommendation": "<specific change to make in plan_phase_epic.md>",
  "affected_section": "<which section of plan_phase_epic.md to modify>",
  "evidence": {
    "plan_sections_involved": ["<section titles>"],
    "agent_source": "<which review agent found this>"
  },
  "plan_context": "<epic ID, technology stack>",
  "tags": ["<relevant tags>"]
}
```

### 5.2 Deduplicate Against Existing Lessons

For each new lesson, check the existing lessons loaded in Phase 0.3:
- If a lesson with the same `affected_section` + `category` + similar `root_cause` already exists, **skip it**.
- If the existing lesson has `"status": "applied"`, still skip.

### 5.3 Write Lesson Files

1. Ensure directory exists: `mkdir -p $EIGEN_ROOT/eigen_initiative/eigen_lessons/plan_phase_epic/`
2. For each new non-duplicate lesson, write to: `$EIGEN_ROOT/eigen_initiative/eigen_lessons/plan_phase_epic/<id>.json`
3. Print summary:
   ```
   Lessons written: <N> new lessons to $EIGEN_ROOT/eigen_initiative/eigen_lessons/plan_phase_epic/
   Skipped: <M> duplicates of existing lessons
   ```

---

## Phase 6: Summary & Next Steps

Print a comprehensive summary:

```
=== Plan Phase Epic Review Complete ===

Epic: P<N>.E<M>
Plan file: $EIGEN_ROOT/eigen_initiative/phases/phase_N/epic_M/plan.md
EIGEN_ROOT: $EIGEN_ROOT

Findings:
  High severity:   <N>
  Medium severity:  <N>
  Low severity:     <N>
  False positives:  <N>

Top Issues:
  1. <highest severity finding>
  2. <second highest>
  3. <third highest>

Plan Change Guidance:
  Section changes: <N>
  Parallelization changes: <N>
  Research insights: <N>

Convergence: <CONVERGED — reason | CONTINUE — N high/medium-severity findings remain>
Feedback written to: $EIGEN_ROOT/eigen_initiative/phases/phase_N/epic_M/feedback/deepen_plan_phase_epic_feedback.json
Lessons: <N> new lessons written to $EIGEN_ROOT/eigen_initiative/eigen_lessons/plan_phase_epic/

Next steps:
  If CONTINUE:
    Run /plan_phase_epic to apply the feedback and iterate.
    Hint: to adjust the plan, pass your instructions to the next iteration.
  If CONVERGED:
    Run /create_issues_from_plan_swarm to generate tasks from the plan.
    Run /compound_improve to apply accumulated lessons.
```

### Commit Pipeline Artifacts

```bash
cd $EIGEN_ROOT
git add eigen_initiative/phases/phase_N/epic_M/feedback/ eigen_initiative/phases/pipeline_state.json
git commit -m "pipeline: deepen plan P<N>.E<M> — iteration <N>, <CONVERGED|CONTINUE>"
```

---

## Key Rules

1. **NEVER modify plan.md** — all findings go to the feedback file. Plan modification is owned by `/plan_phase_epic`.
2. **Research insights flow through the feedback file** — the `plan_change_guidance.research_insights` array is the structured equivalent of research depth.
3. **Feedback files are owned by this command** — `plan_phase_epic` reads but never deletes them.
4. **pipeline_state.json is the single source of truth** — per-epic plan state lives at `state.phases[N].plans[M]`.
5. **Convergence decided by this command only** — max 8 iterations, requires all high AND medium findings resolved.

---

## Auto-Chain (claude-tasks integration)

If `$CLAUDE_TASKS_API` is set, schedule the next command based on convergence. If not set, skip.

- **If CONTINUE** → `/plan_phase_epic` (re-iterate on same epic)
- **If CONVERGED** → `/create_issues_from_plan_swarm` (immediately proceed to task generation for THIS epic — epics are done one at a time: plan → create issues → orchestrate → review → next epic)

```bash
NEXT_RUN=$(date -u -d '+3 minutes' +%Y-%m-%dT%H:%M:%SZ)

# If CONTINUE:
# Only include telegram_webhook if $EIGEN_TELEGRAM_CHAT_ID is set and non-empty.
curl -s -X POST $CLAUDE_TASKS_API/api/v1/tasks \
  -H "Content-Type: application/json" \
  -d '{
    "name": "eigen: plan_phase_epic (iteration)",
    "prompt": "Use the Skill tool to invoke Skill(\"eigen-squared:plan_phase_epic\"). Follow all its instructions completely.",
    "cron_expr": "",
    "scheduled_at": "'$NEXT_RUN'",
    "working_dir": "'$EIGEN_ROOT'",
    "enabled": true,
    "telegram_webhook": "'$EIGEN_TELEGRAM_CHAT_ID'"
  }'

# If CONVERGED:
# Only include telegram_webhook if $EIGEN_TELEGRAM_CHAT_ID is set and non-empty.
curl -s -X POST $CLAUDE_TASKS_API/api/v1/tasks \
  -H "Content-Type: application/json" \
  -d '{
    "name": "eigen: create_issues_from_plan_swarm",
    "prompt": "Use the Skill tool to invoke Skill(\"eigen-squared:create_issues_from_plan_swarm\"). Follow all its instructions completely.",
    "cron_expr": "",
    "scheduled_at": "'$NEXT_RUN'",
    "working_dir": "'$EIGEN_ROOT'",
    "enabled": true,
    "telegram_webhook": "'$EIGEN_TELEGRAM_CHAT_ID'"
  }'
```

Print: `Auto-chain: /<next_command> scheduled in 3 minutes.`
