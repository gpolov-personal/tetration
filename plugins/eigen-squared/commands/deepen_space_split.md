---
name: deepen_space_split
description: Review space_split output with parallel research agents, diagnose errors, and write lessons to the initiative
---

# Deepen Space Split — Epic Decomposition Review

## Introduction

This command takes the output of `/space_split` (epic definition files, `epic_dag.json`, and `phase_e2e_config.json`) and subjects it to comprehensive review by parallel research and review agents. Every structural, interface, epic formation, and cross-epic consistency issue is diagnosed.

`/space_split` produces epic definitions, a DAG, and epic files — it does NOT produce per-epic plans or swarm manifests. Those are created later by `/plan_phase_epic` and `/create_issues_from_plan_swarm` when each epic is ready for execution. This review command therefore validates the epic decomposition and epic file quality, not plans or manifests.

Diagnosed errors are written as structured lesson JSONs to `$EIGEN_ROOT/eigen_initiative/eigen_lessons/space_split/`. These lessons are later consumed by `/compound_improve` to permanently improve the `space_split` command itself.

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

### Phase Auto-Detection

No arguments are required. The target phase is auto-detected from the pipeline state:

1. Read `$EIGEN_ROOT/eigen_initiative/phases/pipeline_state.json`. If not found → **STOP.** Print:
   ```
   ERROR: No pipeline_state.json found at $EIGEN_ROOT/eigen_initiative/phases/
   Run /time_split, /bootstrap, and /space_split first.
   ```
2. Scan `state.phases` to find the first phase N (in numeric order) where:
   - `space_split.status == "completed"` OR `space_split.status == "iterating"` (space_split has run)
   - AND `space_split.convergence.converged == false` (not yet converged)
3. If no such phase is found → **STOP.** Print:
   ```
   No phase is ready for deepen_space_split.
   Either all phases have converged, or space_split has not run yet.
   Run /space_split if needed, or check pipeline_state.json for current status.
   ```
4. The detected phase number N determines:
   - **Phase directory**: `$EIGEN_ROOT/eigen_initiative/phases/phase_N/`
   - **Feedback file**: `$EIGEN_ROOT/eigen_initiative/phases/phase_N/feedback/deepen_space_split_feedback.json`
   - **Lessons directory**: `$EIGEN_ROOT/eigen_initiative/eigen_lessons/space_split/`

Print: `Auto-detected Phase <N> for deepen_space_split.`

---

## Pipeline Awareness

Deepen space split operates at per-phase scope. The phase number N was auto-detected during environment validation. Load the `pipeline-state-schema` skill for the full schema, field definitions, and feedback lifecycle.

### On Entry

The pipeline state was already read during Phase Auto-Detection. Now check deepen-specific state for phase N:

- Check `state.phases[N].deepen_space_split.feedback_consumed`:
  - `feedback_consumed == false` AND feedback file exists → warn: "Existing feedback has not been consumed by space_split yet. Re-analyzing will overwrite it." Proceed anyway.
- Read current `state.phases[N].deepen_space_split.iteration` to determine iteration context.

### On Exit

Update `$EIGEN_ROOT/eigen_initiative/phases/pipeline_state.json`:
- Set `state.phases[N].deepen_space_split.status` to `"completed"`
- Increment `state.phases[N].deepen_space_split.iteration`
- Set `state.phases[N].deepen_space_split.last_run_at` to current ISO 8601 timestamp
- Set `state.phases[N].deepen_space_split.feedback_path` to the feedback file path
- Set `state.phases[N].deepen_space_split.feedback_consumed` to `false` (fresh feedback, not yet processed)
- Set `state.phases[N].space_split.feedback_consumed` to `false` (signal to space_split that fresh feedback is available)
- Update `state.phases[N].deepen_space_split.findings_summary` with counts from the feedback file
- If convergence was decided:
  - Set `state.phases[N].space_split.convergence.converged` to `true`
  - Set `state.phases[N].space_split.convergence.decided_by` to `"deepen_space_split"`
  - Set `state.phases[N].space_split.convergence.decided_at` to current ISO 8601 timestamp
  - Set `state.phases[N].space_split.convergence.reason` to the convergence rationale
  - Write low-severity findings with downstream impact to `recommendations` (see Convergence Recommendations phase)
- If continuing iteration:
  - Set `state.phases[N].space_split.status` to `"iterating"`
- Set `updated_at` to current timestamp

---

## Iteration Protocol

### Detect Iteration Context

1. Check if `$EIGEN_ROOT/eigen_initiative/phases/phase_N/feedback/deepen_space_split_feedback.json` already exists (previous feedback).
2. If it exists, read it for comparison, oscillation detection, and progress tracking.
3. If no previous feedback exists, this is the first deepen iteration.

### Convergence Decision Protocol

After collecting all findings, apply these convergence rules **in order**:

1. **Converge if**: zero high-severity findings AND zero medium-severity findings remain.
   - Rationale: "All significant issues resolved."

2. **Converge if**: iteration limit reached (`state.phases[N].deepen_space_split.iteration >= 8`).
   - Rationale: "Maximum iteration limit (8) reached. Accepting current state."

3. **Converge if**: oscillation detected AND no non-oscillating high-severity or medium-severity findings remain.
   - Rationale: "Oscillation detected. Accepting current state to break the cycle."

4. **Converge if**: epic decomposition is unchanged from previous iteration AND no new high-severity or medium-severity findings.
   - Epic file stability weight: if the epic decomposition hasn't changed, favor convergence.

5. **Converge if**: downstream `/plan_phase_epic` has already run on any epic in this phase.
   - Strongly favor convergence to avoid invalidating downstream work.
   - Rationale: "Downstream plan generation has already started. Accepting current decomposition."

6. **Continue if**: any high-severity or medium-severity actionable findings remain that have not oscillated.

### Epic Update Guidance

For each finding that requires changes to epic files, produce explicit instructions in the feedback file's `epic_updates` section:

- `epics_to_update`: epic_id + list of specific changes to the epic file at `phases/phase_<N>/epic_<M>/epic.md`
- `epics_to_replace`: epic_id + reason + replacement epic file description

---

## Phase 0: Ingest

### 0.1 Read Epic DAG

1. Read `$EIGEN_ROOT/eigen_initiative/phases/phase_N/epic_dag.json`.
2. Extract: `phase` number, `initiative`, `epic_count`, `cross_phase_inputs`, `epics[]`, `execution_waves[]`, `phase_e2e_test`.

### 0.2 Read Phase E2E Config

1. Read `$EIGEN_ROOT/eigen_initiative/phases/phase_N/phase_e2e_config.json`.
2. Extract: `phase_e2e_test`, `epic_validation_scenarios`, `phase_e2e_scenarios`.

### 0.3 Read Bootstrap Report

1. Read `$EIGEN_ROOT/eigen_initiative/phases/phase_N/bootstrap-report.json`.
2. If the file does not exist → **STOP.** Print:
   ```
   ERROR: No bootstrap-report.json found at $EIGEN_ROOT/eigen_initiative/phases/phase_N/
   Bootstrap must be converged before running deepen_space_split.
   ```
3. Extract: `entities_created`, `tooling_decisions`, `language`, `verification`, `delta_applied`.

### 0.4 Read Epic Files

For each epic in the epic DAG's `epics[]`:

1. Read the epic file at `$EIGEN_ROOT/eigen_initiative/phases/phase_N/epic_M/epic.md`. Parse the YAML frontmatter for title and labels, and the markdown body for content.
2. If an epic file doesn't exist, warn: "Cannot read epic file — epic file body quality checks will be skipped for this epic."

### 0.5 Read Phase Manifest (parent)

1. Read `$EIGEN_ROOT/eigen_initiative/phases/phase_N_manifest.md`.
2. If found, parse YAML frontmatter and body.
3. If not found, warn but proceed — some validations will be limited.

### 0.6 Load Existing Lessons

1. Glob `$EIGEN_ROOT/eigen_initiative/eigen_lessons/space_split/*.json`.
2. Read and parse each lesson JSON — used to avoid duplicating known issues in the lesson extraction phase.

### 0.7 Read Upstream Recommendations (Awareness)

Read `recommendations.space_split` from `$EIGEN_ROOT/eigen_initiative/phases/pipeline_state.json`.

Use these as additional context when reviewing space_split's output:
- They inform your analysis but do NOT constitute findings on their own.
- Do NOT create findings solely because a recommendation was not addressed.
- You MAY reference a recommendation in a finding's rationale if you independently identify a related issue.
- Pass relevant recommendations to review agents as background context alongside the epic_dag and phase manifest.

---

## Phase 1: Epic DAG Validation

Spawn **all DAG validation agents in parallel:**

### 1.1 DAG Correctness Agent

```
Prompt: "Validate the epic DAG structure.

Check:
1. The epic DAG is acyclic — no epic transitively blocks itself
2. Execution waves are consistent with blocked_by: if epic_b is blocked_by epic_a, epic_b must be in a LATER wave than epic_a
3. Every epic_id in blocked_by references an epic that actually exists in the epics[] array
4. Wave 1 contains at least one epic (some epics must have no blockers)
5. Every epic appears in exactly one execution wave

Epic DAG:
<epic_dag JSON>

Report every violation: {epic_id, violation_type, details}"
```

### 1.2 Cluster Integrity Agent

```
Prompt: "Check cluster integrity within epics.

Rule: All features in a cluster should strongly be kept within the same epic. A cluster split across epics is a concern — only acceptable if there is a compelling reason (e.g., sequential epics where one blocks the other).

Epic definitions (features per epic):
<epics[] from epic_dag with their features lists>

Phase manifest clusters:
<clusters from phase_manifest>

Report every cluster that has features in more than one epic: {cluster_id, features, epics_found_in}"
```

### 1.3 Inter-Epic Interface Completeness Agent

```
Prompt: "Validate that inter-epic interfaces are complete and consistent.

For every dependency between epics (epic_b depends on epic_a):
1. Does epic_a's interfaces_provided list include an interface consumed by epic_b?
2. Does epic_b's interfaces_consumed list reference epic_a as provider?
3. Is the contract description precise enough for implementation? (must specify data shape or API contract, not just a name)
4. Do interfaces include concrete_files from the bootstrap? (file paths to entity stubs that define the contract)
5. Are there any ORPHAN interfaces? (provided but never consumed, or consumed but never provided)

Epic DAG:
<epic_dag JSON>

Bootstrap entity map:
<bootstrap_report.entities_created>

Report: missing interfaces, orphan interfaces, vague contracts, missing concrete_files, mismatched provider/consumer pairs."
```

### 1.4 Epic Size Agent

```
Prompt: "Check epic sizing.

Each epic should be a meaningful unit of work — not so small that planning overhead dominates, not so large that a single swarm can't handle it. Consider:
- Are any epics too small to justify their own swarm (single feature, trivial scope)?
- Are any epics too large for one swarm to execute effectively?
- Is the sizing balanced relative to other epics in this phase?

Epics:
<epics[] from epic_dag with feature counts>

Report: epics that seem disproportionately large or small, with recommendation to merge or split."
```

---

## Phase 2: Epic Quality Validation

This phase validates the epic file bodies created by `/space_split`. These epic file bodies are the primary input to `/plan_phase_epic` — if they are incomplete, the downstream plans will be poor.

**Skip this entire phase if epic files could not be read in Phase 0.4.** Print: "Skipping epic quality checks — epic files could not be read."

Spawn **all agents in parallel:**

### 2.1 Issue Completeness Agent

```
Prompt: "Validate that each epic file body contains all required sections for downstream /plan_phase_epic to generate a useful plan.

Required sections in each epic file body:
1. Features table — with ID, Name, Priority, Dependencies columns
2. Validation Criteria — what can be verified after this epic's swarm completes (components that work, tests that pass)
3. Inter-Epic Interfaces — what this epic provides and consumes, with concrete file paths
4. Blackbox Feature Specifications — FULL verbatim specs (Inputs, Outputs, Behavior, Acceptance Criteria) for EVERY feature in the epic
5. Whitebox Implementation Guidance — relevant whitebox sections for this epic's domains (may be absent if no whitebox file was provided — this is OK)
6. Bootstrap Context — language, tooling, entity stubs with file paths

For each epic file:
- Check that sections 1-4 and 6 are present and non-empty (section 5 is optional)
- Check that the blackbox specs count matches the feature count in the features table
- Check that bootstrap context includes real file paths (not placeholders)

Epic files:
<for each epic: {epic_id, title, body}>

Report: {epic_id, missing_section, details}"
```

### 2.2 Blackbox Spec Fidelity Agent

```
Prompt: "Verify that the blackbox specs in epic file bodies match the phase manifest's specs.

For each epic file body:
1. Extract the feature IDs from the Features table
2. Extract the blackbox specs from the 'Blackbox Feature Specifications' section
3. Compare against the phase manifest's blackbox specs for those same feature IDs
4. Flag: missing specs (feature in table but no spec in epic file), truncated specs (fewer acceptance criteria than manifest), garbled specs

Phase manifest blackbox specs:
<blackbox_specs from phase_manifest>

Epic files:
<for each epic: {epic_id, body}>

Report: {epic_id, feature_id, issue_type (missing|truncated|garbled), details}"
```

### 2.3 Bootstrap Context Agent

```
Prompt: "Verify that the bootstrap context in epic file bodies is accurate and useful.

For each epic file body:
1. Extract the 'Bootstrap Context' section
2. Check that entity stubs listed actually exist in the bootstrap report
3. Check that file paths match the bootstrap report's entity_file_map
4. Check that tooling decisions (language, framework, test runner) match the bootstrap report
5. Flag any entity stubs referenced in the epic file that are NOT in the bootstrap report (phantom references)

Bootstrap report:
<bootstrap_report>

Epic files:
<for each epic: {epic_id, body}>

Report: {epic_id, issue_type, details}"
```

---

## Phase 3: Cross-Epic Consistency

Spawn agents to check consistency **across** all epics:

### 3.1 Feature Coverage Agent

```
Prompt: "Check that every feature in the phase manifest is assigned to exactly one epic.

1. Extract all feature IDs from the phase manifest
2. Extract all feature IDs from each epic in the epic DAG
3. Flag: features in the manifest but NOT in any epic (dropped features)
4. Flag: features in an epic but NOT in the manifest (phantom features)
5. Flag: features appearing in more than one epic (duplicate assignment)

Phase manifest features:
<feature IDs from phase_manifest>

Epic features:
<for each epic: {epic_id, features[]}>

Report: {feature_id, issue_type (dropped|phantom|duplicate), epics_involved}"
```

### 3.2 Interface Contract Compatibility Agent

```
Prompt: "Check that inter-epic interface contracts are compatible.

For each interface defined in epic_dag.json:
1. Read the provider epic file body — how does it describe the output?
2. Read the consumer epic file body — how does it describe the expected input?
3. Do the interface's concrete_files point to real bootstrap entity stubs?
4. Are the contracts compatible? (does the provider's output match what the consumer expects?)

Epic DAG interfaces:
<interfaces from epic_dag>

Epic files:
<for each epic: {epic_id, body}>

Bootstrap entities:
<bootstrap_report.entities_created>

Report: incompatible contracts, missing concrete_files, contracts where provider and consumer describe different shapes."
```

### 3.3 E2E Coverage Agent

```
Prompt: "Validate the E2E testing setup for this phase.

1. E2E Testing epic structure:
   - Does an E2E Testing epic exist as the last epic in the DAG?
   - Is it blocked by ALL other epics?
   - Is it in the final execution wave (with type 'e2e')?
   - Does its epic.md validation criteria describe the full phase-level E2E flows?

2. Phase E2E scenarios (phase_e2e_config.json → phase_e2e_scenarios):
   - Do the phase_e2e_scenarios cover all inter-epic integration boundaries?
   - Is every inter-epic interface exercised by at least one scenario?
   - Are the acceptance_criteria traceable to features across epics?

3. Epic validation scenarios (phase_e2e_config.json → epic_validation_scenarios):
   - Does every feature epic (non-E2E) have at least one validation scenario?
   - Do the validation scenarios cover the epic's key acceptance criteria?

4. Infrastructure requirements (phase_e2e_config.json → infrastructure_requirements):
   - Are the test_types_detected consistent with the features in the phase?
   - Does needs_docker / needs_emulator / needs_browser_automation match the test types?
   - Does the E2E Testing epic's Infrastructure Requirements section align with the config?

5. Consistency:
   - Are the phase_e2e_scenarios consistent with what the E2E Testing epic describes in its validation criteria?
   - Do the epic_validation_scenarios align with each epic's validation criteria section in its epic.md?

Phase E2E config:
<phase_e2e_config JSON>

Epic DAG (for epic list, interfaces, and E2E epic):
<epic_dag JSON>

E2E Testing epic file:
<E2E Testing epic.md content>

Report: missing E2E epic, E2E epic misconfigured, epics without validation scenarios, inter-epic boundaries not covered by phase scenarios, inconsistencies between config and epic files."
```

---

## Phase 4: Strategic Review

Spawn **review agents in parallel:**

### 4.1 Architecture Strategist Review

Spawn as `Task eigen:architecture-strategist`:

```
Prompt: "Review this phase-to-epics decomposition from an architectural perspective.

Check:
1. Does the epic ordering (execution waves) make architectural sense?
2. Are provider epics correctly upstream of consumer epics?
3. Could any epics be parallelized that are currently sequential?
4. Are there any hidden dependencies not captured in the DAG?
5. Is the overall decomposition granularity appropriate?
6. Do the inter-epic interfaces align with the bootstrap foundation's entity boundaries?

Epic DAG:
<epic_dag JSON>

Bootstrap report:
<bootstrap_report>

Phase manifest:
<phase_manifest>"
```

### 4.2 Simplicity Review

Spawn as `Task eigen:code-simplicity-reviewer`:

```
Prompt: "Review this epic decomposition for unnecessary complexity.

Check:
1. Are there too many epics for the feature count? (e.g., 10 epics for 15 features is over-decomposed)
2. Could simpler epic boundaries achieve the same result?
3. Are there unnecessary indirections in the interface contracts?
4. Are any execution waves artificially sequential (epics that could be parallel but are blocked)?
5. Could any small epics be merged without violating cluster constraints?

Epic DAG:
<epic_dag JSON>

Phase manifest summary:
<phase_metadata>"
```

---

## Phase 5: Skills & Learnings Application

### 5.1 Discover and Apply Available Skills

1. Discover ALL available skills from all sources (project, user, all plugins).
2. Match skills to the phase's domains and technologies.
3. Spawn one sub-agent per matched skill to review the epic decomposition through that skill's lens.
4. Spawn all in parallel.

---

## Phase 6: Synthesize & Enhance

### 6.1 Collect All Agent Results

Wait for ALL parallel agents to complete. Collect findings from:
- DAG validation agents (Phase 1)
- Epic quality agents (Phase 2)
- Cross-epic consistency agents (Phase 3)
- Strategic review agents (Phase 4)
- Skills agents (Phase 5)

### 6.2 Categorize Findings

For each finding, assign:

- **`category`**: one of:
  - `epic_formation_error` — cluster split across epics, epic too large/small, poor grouping
  - `dag_error` — missing blocked_by, cycle in epic DAG, wrong wave assignment
  - `interface_error` — missing interface, incompatible contract, orphan interface, vague contract, missing concrete_files
  - `issue_completeness_error` — epic file body missing required sections (blackbox specs, whitebox guidance, bootstrap context)
  - `spec_fidelity_error` — blackbox specs in issue body don't match phase manifest (truncated, garbled, missing)
  - `feature_coverage_error` — feature dropped from all epics, duplicated across epics, or phantom feature
  - `e2e_coverage_gap` — epic not covered by phase E2E, missing integration scenario
  - `strategic_concern` — architectural ordering issue, over-engineering, missed parallelization
  - `false_positive` — agent flagged something that's actually correct

- **`severity`**: `high` (breaks correctness or downstream plan generation), `medium` (suboptimal but functional), `low` (minor improvement)

- **`affected_phase`**: which section of the `space_split.md` command caused this (e.g., "Phase 1.2 — Form Epic Candidates", "Phase 2.3 — Create One Issue Per Epic")

### 6.3 Deduplicate & Prioritize

- Merge similar findings from multiple agents.
- Flag conflicting advice for user review.
- Group by affected command phase and epic.
- Filter out `false_positive` findings.

### 6.4 Write Iteration Feedback File

Write the feedback to `$EIGEN_ROOT/eigen_initiative/phases/phase_N/feedback/deepen_space_split_feedback.json`. **Do NOT modify epic_dag.json or phase_e2e_config.json** — feedback is always a separate file.

Ensure directory exists: `mkdir -p $EIGEN_ROOT/eigen_initiative/phases/phase_N/feedback/`

```json
{
  "schema_version": "1.0.0",
  "command": "deepen_space_split",
  "iteration": "<current deepen_space_split iteration>",
  "analyzed_iteration": "<state.phases[N].space_split.iteration that was analyzed>",
  "created_at": "<ISO 8601>",
  "source_outputs_analyzed": {
    "epic_dag": "phases/phase_N/epic_dag.json",
    "phase_e2e_config": "phases/phase_N/phase_e2e_config.json",
    "epic_files": ["phases/phase_N/epic_M/epic.md"]
  },
  "convergence": {
    "decision": "continue|converged",
    "rationale": "<why, referencing downstream impact and issue stability>",
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
      "id": "dsf-<sequential_number>",
      "category": "<epic_formation_error|dag_error|interface_error|issue_completeness_error|spec_fidelity_error|feature_coverage_error|e2e_coverage_gap|strategic_concern>",
      "severity": "high|medium|low",
      "title": "<concise>",
      "description": "<detailed>",
      "affected_output": "<file path or issue number>",
      "affected_section": "<section within file or issue>",
      "recommendation": "<specific action for space_split to take>",
      "actionable_by": "space_split",
      "downstream_impact": {
        "affects_commands": ["plan_phase_epic"],
        "impact_description": "<what breaks downstream>"
      }
    }
  ],
  "epic_updates": {
    "epics_to_update": [
      {
        "epic_id": "P<N>.E<M>",
        "epic_file": "phases/phase_N/epic_M/epic.md",
        "changes": ["<description of change 1>", "<description of change 2>"],
        "finding_ids": ["<finding IDs driving this update>"]
      }
    ],
    "epics_to_replace": [
      {
        "epic_id": "P<N>.E<M>",
        "epic_file": "phases/phase_N/epic_M/epic.md",
        "reason": "<why replace>",
        "replacement_description": "<what the replacement epic file should contain>",
        "finding_ids": ["<finding IDs driving this>"]
      }
    ]
  },
  "summary": {
    "total_findings": "<count>",
    "by_severity": { "high": "<count>", "medium": "<count>", "low": "<count>" },
    "by_category": { "<category>": "<count>" },
    "per_epic": {
      "P<N>.E<M>": { "high": "<count>", "medium": "<count>", "low": "<count>" }
    }
  }
}
```

Apply the Convergence Decision Protocol (from the Iteration Protocol section above) to set `convergence.decision`.

### Phase 6.5: Generate Convergence Recommendations (CONVERGED ONLY)

**Skip this section entirely if convergence decision is NOT "converged".**

At convergence, scan findings for cross-stage insights worth preserving for downstream commands.

1. **Filter findings with downstream impact:** Only findings where `downstream_impact.affects_commands` is non-empty.
2. **For each affected downstream command** (plan_phase_epic, create_issues_from_plan_swarm), draft a 1-2 sentence observation:
   - Describe the **observed condition** in space_split's output.
   - State the **implication** for the downstream command.
   - Use `"epic": <M>` for epic-specific observations, `"epic": null` for phase-wide observations.
   - Example: "Epic 1 (Wave 1) provides 2 critical interfaces (User, Product). Plan should finalize interface contracts before implementing independent components."
   - Example: "Cross-epic dependency Epic 1 → Epic 2 uses UserService interface. Plan should verify interface is testable in isolation before Wave 2."
3. **Write to pipeline_state.json** — update `recommendations[<target_command>]`:
   - Replace all entries where `from` == `"deepen_space_split"` (preserve entries from other deepen commands).
   - Max 5 entries per target command.
   - Each entry: `{ "from": "deepen_space_split", "at_iteration": <current iteration>, "phase": <N>, "epic": <M or null>, "text": "<observation>" }`
4. If no findings have downstream impact, do not write any recommendations.

**Constraints:**
- Recommendations are OPTIONAL. Only write when you genuinely have cross-stage insight.
- Write observations and implications, NOT action items.
- Do NOT prescribe what the downstream command should do — describe what you observed and why it matters.

---

## Phase 7: Lesson Extraction

### 7.1 Generate Lesson JSONs

For each non-false-positive finding, create a lesson JSON:

```json
{
  "id": "ss-lesson-<timestamp>-<sequential>",
  "created_at": "<ISO 8601 timestamp>",
  "command": "space_split",
  "status": "pending",
  "category": "<category from 6.2>",
  "severity": "<high|medium|low>",
  "title": "<concise description of the error>",
  "description": "<detailed explanation of what went wrong>",
  "root_cause": "<why the space_split command produced this error>",
  "recommendation": "<specific change to make in the space_split command>",
  "affected_phase": "<which phase/section of space_split.md to modify>",
  "evidence": {
    "epics_involved": ["<epic IDs>"],
    "features_involved": ["<feature IDs>"],
    "epics_involved_files": ["phases/phase_N/epic_M/epic.md"],
    "agent_source": "<which review agent found this>"
  },
  "initiative_context": "<initiative name, phase number, feature count>",
  "tags": ["<relevant tags>"]
}
```

### 7.2 Deduplicate Against Existing Lessons

For each new lesson, check the existing lessons loaded in Phase 0.6:
- If a lesson with the same `affected_phase` + `category` + similar `root_cause` already exists, **skip it**.
- If the existing lesson has `"status": "applied"`, still skip.

### 7.3 Write Lesson Files

1. Ensure directory exists: `mkdir -p $EIGEN_ROOT/eigen_initiative/eigen_lessons/space_split/`
2. For each new non-duplicate lesson, write to: `$EIGEN_ROOT/eigen_initiative/eigen_lessons/space_split/<id>.json`
3. Print summary:
   ```
   Lessons written: <N> new lessons to $EIGEN_ROOT/eigen_initiative/eigen_lessons/space_split/
   Skipped: <M> duplicates of existing lessons
   ```

---

## Phase 8: Summary & Next Steps

Print a comprehensive summary:

```
=== Space Split Review Complete ===

Phase: <N>
Epics reviewed: <N>
Total features: <N>
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

Per-Epic Summary:
  Epic 1: <N> findings (<severity breakdown>)
  Epic 2: <N> findings (<severity breakdown>)
  ...

Convergence: <CONVERGED — reason | CONTINUE — N high/medium-severity findings remain>
Feedback written to: $EIGEN_ROOT/eigen_initiative/phases/phase_N/feedback/deepen_space_split_feedback.json
Lessons: <N> new lessons written to $EIGEN_ROOT/eigen_initiative/eigen_lessons/space_split/

Next steps:
  If CONTINUE:
    Run /space_split to re-generate the epic decomposition incorporating the feedback.
    Hint: to add constraints (change epic boundaries, move features), pass your
    instructions as arguments to the next /space_split run.
  If CONVERGED:
    Run /plan_phase_epic to generate plans for the epics.
    Run /compound_improve to apply accumulated lessons to the space_split command.
```

### Commit Pipeline Artifacts

```bash
cd $EIGEN_ROOT
git add eigen_initiative/phases/phase_N/feedback/ eigen_initiative/phases/pipeline_state.json
git commit -m "pipeline: deepen_space_split phase <N> — iteration <N>, <CONVERGED|CONTINUE>"
```

---

## Auto-Chain (claude-tasks integration)

If `$CLAUDE_TASKS_API` is set, schedule the next command based on convergence. If not set, skip.

- **If CONTINUE** → `/space_split`
- **If CONVERGED** → `/plan_phase_epic`

```bash
NEXT_RUN=$(date -u -d '+3 minutes' +%Y-%m-%dT%H:%M:%SZ)

# If CONTINUE:
# Only include telegram_webhook if $EIGEN_TELEGRAM_CHAT_ID is set and non-empty.
curl -s -X POST $CLAUDE_TASKS_API/api/v1/tasks \
  -H "Content-Type: application/json" \
  -d '{
    "name": "eigen: space_split (iteration)",
    "prompt": "Use the Skill tool to invoke Skill(\"eigen-squared:space_split\"). Follow all its instructions completely.",
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
    "name": "eigen: plan_phase_epic",
    "prompt": "Use the Skill tool to invoke Skill(\"eigen-squared:plan_phase_epic\"). Follow all its instructions completely.",
    "cron_expr": "",
    "scheduled_at": "'$NEXT_RUN'",
    "working_dir": "'$EIGEN_ROOT'",
    "enabled": true,
    "telegram_webhook": "'$EIGEN_TELEGRAM_CHAT_ID'"
  }'
```

Print: `Auto-chain: /<next_command> scheduled in 3 minutes.`
