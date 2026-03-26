---
name: deepen_space_split
description: Review space_split output with parallel research agents, diagnose errors, and write lessons to the initiative
---

# Deepen Space Split — Epic Decomposition Review

## Pipeline Context

```
space_split ──► DEEPEN_SPACE_SPLIT ──► space_split (if CONTINUE)
                       │                      │
                       └── (if CONVERGED) ──► plan_phase_epic
```

**Role.** Review partner for `space_split`. This command takes the output of `/space_split` (epic definition files, `epic_manifest.json`, and `phase_e2e_config.json`) and subjects it to comprehensive review by parallel research and review agents. Every structural, interface, epic formation, and cross-epic consistency issue is diagnosed.

`/space_split` produces epic definitions, a manifest, and epic files — it does NOT produce per-epic plans or swarm manifests. Those are created later by `/plan_phase_epic` and `/create_issues_from_plan_swarm` when each epic is ready for execution. This review command therefore validates the epic decomposition and epic file quality, not plans or manifests.

**Convergence authority.** This command decides when `space_split` output is good enough. It sets convergence on the `space_split` stage and writes the rationale.

**Lesson writing.** Diagnosed errors are written as structured lesson JSONs to the initiative's lessons directory (`space_split/`). These lessons are later consumed by `/compound_improve` to permanently improve the `space_split` command itself.

**Language.** All feedback, lessons, and summaries are written in the same language as the initiative files.

## Environment

Before anything else, verify:

- [ ] `$EIGEN_ROOT` is set and points to an existing directory
- [ ] `$EIGEN_BRANCH` is set

If either is missing, **STOP** and tell the user which variable to set.

---

## On Entry

```bash
eigen-squared get-context deepen_space_split --json
```

If the CLI exits with an error (non-zero), **STOP** and display the error message. The CLI handles all pre-flight checks (pipeline_state existence, space_split status, convergence guard, overwrite warnings, git sync).

Otherwise parse the returned JSON:

```json
{
  "command": "deepen_space_split",
  "branch": "main",
  "paths_relative_to": "$EIGEN_ROOT/eigen_initiative/",
  "phase": 1,
  "iteration": 2,
  "main_command_iteration": 3,
  "main_command_outputs": {
    "epic_manifest": "phases/phase_1/epic_manifest.json",
    "phase_e2e_config": "phases/phase_1/phase_e2e_config.json",
    "phase_manifest": "phases/phase_1_manifest.md"
  },
  "lessons_dir": "eigen_lessons/space_split/",
  "recommendations": [],
  "previous_feedback_path": "phases/phase_1/feedback/deepen_space_split_feedback.json",
  "previous_feedback_exists": true,
  "overwrite_warning": "Existing feedback has not been consumed by space_split yet. Re-analyzing will overwrite it."
}
```

| Field | Use |
|---|---|
| `phase` | The target phase number N for this run. |
| `iteration` | Current deepen_space_split iteration (for convergence limit checks). |
| `main_command_iteration` | The space_split iteration whose output is being reviewed. Written into feedback as `analyzed_iteration`. |
| `main_command_outputs.epic_manifest` | Relative path to epic_manifest.json (resolve against `paths_relative_to`). |
| `main_command_outputs.phase_e2e_config` | Relative path to phase_e2e_config.json (resolve against `paths_relative_to`). |
| `main_command_outputs.phase_manifest` | Relative path to the phase manifest (resolve against `paths_relative_to`). |
| `lessons_dir` | Relative path to the lessons directory (resolve against `paths_relative_to`). |
| `recommendations` | Upstream recommendations for space_split — use as awareness context. |
| `previous_feedback_path` | Relative path to previous feedback file (resolve against `paths_relative_to`). |
| `previous_feedback_exists` | Whether previous feedback exists — gates the Iteration Protocol. |
| `overwrite_warning` | If set, display this warning to the user and proceed. |

If `overwrite_warning` is present, print the warning and continue.

## On Exit

After completing the review, writing the feedback file, and writing lessons:

```bash
# Always — mark this deepen run complete
eigen-squared complete deepen_space_split \
  --phase <phase> \
  --feedback-path <feedback_file_path> \
  --findings-summary '{"high": <N>, "medium": <N>, "low": <N>}'
```

```bash
# Conditional — only if convergence decision is "converged"
eigen-squared mark-converged space_split --phase <phase> --reason "<convergence rationale>"
```

```bash
# Conditional — only at convergence, one call per recommendation
eigen-squared add-recommendation \
  --from-cmd deepen_space_split \
  --target <target_cmd> \
  --iteration <main_command_iteration> \
  --text "<observation>"
```

Commit all artifacts:

```bash
eigen-squared commit-state \
  --message "pipeline: deepen_space_split phase <phase> — iteration <N>, <CONVERGED|CONTINUE>" \
  --additional-paths eigen_initiative/phases/phase_<phase>/feedback/,eigen_initiative/eigen_lessons/space_split/
eigen-squared schedule-next
```

---

## Iteration Protocol

### Detect Iteration Context

1. Check if `previous_feedback_exists` is true in the CLI context (previous feedback).
2. If it exists, read the file at `previous_feedback_path` (resolved against `paths_relative_to`) for comparison, oscillation detection, and progress tracking.
3. If no previous feedback exists, this is the first deepen iteration.

### Finding Matching Protocol (iteration 2+)

When comparing current findings against previous iteration findings, use **epic-number + feature-ID matching** — not title or description matching:

1. For each current finding, extract all epic numbers (E1, E2...) and feature IDs (F01, F02...) mentioned in `description`, `recommendation`, and `affected_output`.
2. For each previous finding, extract the same epic numbers and feature IDs.
3. Two findings **match** if they share at least one epic number OR feature ID AND belong to the same `category` (e.g., both are `interface_error` about E2).
4. Classify matched findings:
   - **Persisting**: current finding matches a previous finding that was NOT addressed → add previous ID to `findings_persisting`
   - **Regressed**: current finding matches a previous finding that WAS addressed (appeared in `findings_addressed` of the previous comparison) → add to `findings_regressed`
   - **Oscillating**: current finding matches a finding that has appeared in 3+ non-consecutive iterations, or has been in `findings_regressed` at least once → add to `oscillating_findings`
5. Findings with NO epic/feature-ID match to any previous finding → `new_findings`.

This protocol is deterministic: epic numbers and feature IDs are stable across reformulations, unlike titles and descriptions which the LLM may rephrase each iteration.

### Convergence Decision Protocol

After collecting all findings, apply these convergence rules **in order**:

1. **Converge if**: zero high-severity findings AND zero medium-severity findings remain.
   - Rationale: "All significant issues resolved."

2. **Converge if**: iteration limit reached (`iteration >= 8` from CLI context).
   - Rationale: "Maximum iteration limit (8) reached. Accepting current state."

3. **Converge if**: oscillation detected AND no non-oscillating high-severity or medium-severity findings remain.
   - Rationale: "Oscillation detected. Accepting current state to break the cycle."

4. **Converge if**: stagnation detected — more than 50% of current high+medium findings match (by epic/feature ID, per the Finding Matching Protocol) findings from 2 iterations ago (i.e., the same epics/features keep appearing in findings without resolution).
   - Rationale: "Stagnation detected. The same epics/features keep appearing in findings across iterations. Accepting current state — remaining issues are better resolved by plan_phase_epic's deeper analysis."

5. **Converge if**: epic decomposition is unchanged from previous iteration AND no new high-severity or medium-severity findings.
   - Epic file stability weight: if the epic decomposition hasn't changed, favor convergence.

6. **Converge if**: downstream `/plan_phase_epic` has already run on any epic in this phase.
   - Strongly favor convergence to avoid invalidating downstream work.
   - Rationale: "Downstream plan generation has already started. Accepting current decomposition."

7. **Continue if**: any high-severity or medium-severity actionable findings remain that have not oscillated or stagnated.

### Epic Update Guidance

For each finding that requires changes to epic files, produce explicit instructions in the feedback file's `epic_updates` section:

- `epics_to_update`: epic_id + list of specific changes to the epic file at `phases/phase_<N>/epic_<M>/epic.md`
- `epics_to_replace`: epic_id + reason + replacement epic file description

---

## Stage 0: Ingest

### 0.1 Read Epic Manifest

1. Read the epic manifest at `main_command_outputs.epic_manifest` (resolved against `paths_relative_to`).
2. Extract: `phase` number, `initiative`, `epic_count`, `cross_phase_inputs`, `epics[]`, `execution_order`, `phase_e2e_test`.

### 0.2 Read Phase E2E Config

1. Read the phase E2E config at `main_command_outputs.phase_e2e_config` (resolved against `paths_relative_to`).
2. Extract: `phase_e2e_test`, `epic_validation_scenarios`, `phase_e2e_scenarios`.

### 0.3 Read Bootstrap Report

1. Read the bootstrap report at `phases/phase_<N>/bootstrap-report.json` (resolved against `paths_relative_to`).
2. If the file does not exist → **STOP.** Print:
   ```
   ERROR: No bootstrap-report.json found for phase <N>.
   Bootstrap must be converged before running deepen_space_split.
   ```
3. Extract: `entities_created`, `tooling_decisions`, `language`, `verification`, `delta_applied`.

### 0.4 Read Epic Files

For each epic in the epic manifest's `epics[]`:

1. Read the epic file at `phases/phase_<N>/epic_<M>/epic.md` (resolved against `paths_relative_to`). Parse the YAML frontmatter for title and labels, and the markdown body for content.
2. If an epic file doesn't exist, warn: "Cannot read epic file — epic file body quality checks will be skipped for this epic."

### 0.5 Read Phase Manifest (parent)

1. Read the phase manifest at `main_command_outputs.phase_manifest` (resolved against `paths_relative_to`).
2. If found, parse YAML frontmatter and body.
3. If not found, warn but proceed — some validations will be limited.

### 0.6 Load Existing Lessons

1. Glob `<lessons_dir>/*.json` (resolved against `paths_relative_to`).
2. Read and parse each lesson JSON — used to avoid duplicating known issues in the lesson extraction phase.

### 0.7 Read Upstream Recommendations (Awareness)

The `recommendations` array from the CLI context contains upstream recommendations for `space_split`.

Use these as additional context when reviewing space_split's output:
- They inform your analysis but do NOT constitute findings on their own.
- Do NOT create findings solely because a recommendation was not addressed.
- You MAY reference a recommendation in a finding's rationale if you independently identify a related issue.
- Pass relevant recommendations to review agents as background context alongside the epic manifest and phase manifest.

---

## Stage 1: Epic Manifest Validation

Spawn **all manifest validation agents in parallel:**

### 1.1 Epic Ordering Check

Verify the epic ordering is valid:

1. The `execution_order` array contains all epic IDs from `epics[]` exactly once.
2. Epics are sequential (E1, E2, E3, ...).
3. The E2E Testing epic is last in `execution_order`.

If any check fails, record as an `epic_formation_error` finding with high severity.

### 1.2 Cluster Integrity Agent

```
Prompt: "Check cluster integrity within epics.

Rule: All features in a cluster should strongly be kept within the same epic. A cluster split across epics is a concern — only acceptable if there is a compelling reason (e.g., sequential epics where an earlier epic provides interfaces consumed by a later one).

Epic definitions (features per epic):
<epics[] from epic_manifest with their features lists>

Phase manifest clusters:
<clusters from phase_manifest>

Report every cluster that has features in more than one epic: {cluster_id, features, epics_found_in}"
```

### 1.3 Inter-Epic Interface Completeness Agent

```
Prompt: "Validate that inter-epic interfaces are complete and consistent.

For every epic that provides interfaces to later epics:
1. Does the epic's interfaces_provided list include the interfaces that later epics need?
2. Is the contract description precise enough for implementation? (must specify data shape or API contract, not just a name)
3. Do interfaces include concrete_files from the bootstrap? (file paths to entity stubs that define the contract)
4. Are there any ORPHAN interfaces? (provided but never consumed by any later epic)

Epic manifest:
<epic_manifest JSON>

Bootstrap entity map:
<bootstrap_report.entities_created>

Report: missing interfaces, orphan interfaces, vague contracts, missing concrete_files."
```

### 1.4 Epic Size Agent

```
Prompt: "Check epic sizing.

Each epic should be a meaningful unit of work — not so small that planning overhead dominates, not so large that a single swarm can't handle it. Consider:
- Are any epics too small to justify their own swarm (single feature, trivial scope)?
- Are any epics too large for one swarm to execute effectively?
- Is the sizing balanced relative to other epics in this phase?

Epics:
<epics[] from epic_manifest with feature counts>

Report: epics that seem disproportionately large or small, with recommendation to merge or split."
```

---

## Stage 2: Epic Quality Validation

This phase validates the epic file bodies created by `/space_split`. These epic file bodies are the primary input to `/plan_phase_epic` — if they are incomplete, the downstream plans will be poor.

**Skip this entire stage if epic files could not be read in Stage 0.4.** Print: "Skipping epic quality checks — epic files could not be read."

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

## Stage 3: Cross-Epic Consistency

Spawn agents to check consistency **across** all epics:

### 3.1 Feature Coverage Agent

```
Prompt: "Check that every feature in the phase manifest is assigned to exactly one epic.

1. Extract all feature IDs from the phase manifest
2. Extract all feature IDs from each epic in the epic manifest
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

For each interface defined in epic_manifest.json:
1. Read the provider epic file body — how does it describe the output?
2. Read the consumer epic file body — how does it describe the expected input?
3. Do the interface's concrete_files point to real bootstrap entity stubs?
4. Are the contracts compatible? (does the provider's output match what the consumer expects?)

Epic manifest interfaces:
<interfaces from epic_manifest>

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
   - Does an E2E Testing epic exist as the last epic in the execution order?
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
   - If `test_environment` is `"container_parity"`: the project has a docker-compose.yml (from bootstrap). The E2E epic should reference it as the test environment — not set up its own Docker from scratch. If `test_environment` is missing but `needs_docker` is true, flag as `e2e_coverage_gap` — the config should specify how Docker is used.
   - Are `compose_file`, `startup_command`, `health_check`, `teardown_command`, and `services` populated when `test_environment` is `"container_parity"`?
   - Does the `services` list match `bootstrap-report.json` → `delta_applied.docker_compose_services`? (Feature epics may add more, but the bootstrap set should be present as a baseline.)

5. Consistency:
   - Are the phase_e2e_scenarios consistent with what the E2E Testing epic describes in its validation criteria?
   - Do the epic_validation_scenarios align with each epic's validation criteria section in its epic.md?

Phase E2E config:
<phase_e2e_config JSON>

Epic manifest (for epic list, interfaces, and E2E epic):
<epic_manifest JSON>

E2E Testing epic file:
<E2E Testing epic.md content>

Report: missing E2E epic, E2E epic misconfigured, epics without validation scenarios, inter-epic boundaries not covered by phase scenarios, inconsistencies between config and epic files."
```

---

## Stage 4: Strategic Review

Spawn **review agents in parallel:**

### 4.1 Architecture Strategist Review

Spawn as `Task eigen:architecture-strategist`:

```
Prompt: "Review this phase-to-epics decomposition from an architectural perspective.

Check:
1. Does the epic ordering make architectural sense?
2. Are provider epics correctly upstream of consumer epics?
3. Are there any hidden dependencies not captured in the epic manifest?
4. Is the overall decomposition granularity appropriate?
5. Do the inter-epic interfaces align with the bootstrap foundation's entity boundaries?

Epic manifest:
<epic_manifest JSON>

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
4. Could any small epics be merged without violating cluster constraints?

Epic manifest:
<epic_manifest JSON>

Phase manifest summary:
<phase_metadata>"
```

---

## Stage 5: Skills & Learnings Application

### 5.1 Discover and Apply Available Skills

1. Discover ALL available skills from all sources (project, user, all plugins).
2. Match skills to the phase's domains and technologies.
3. Spawn one sub-agent per matched skill to review the epic decomposition through that skill's lens.
4. Spawn all in parallel.

---

## Stage 6: Synthesize & Enhance

### 6.1 Collect All Agent Results

Wait for ALL parallel agents to complete. Collect findings from:
- Manifest validation agents (Stage 1)
- Epic quality agents (Stage 2)
- Cross-epic consistency agents (Stage 3)
- Strategic review agents (Stage 4)
- Skills agents (Stage 5)

### 6.2 Categorize Findings

For each finding, assign:

- **`category`**: one of:
  - `epic_formation_error` — cluster split across epics, epic too large/small, poor grouping, ordering issues
  - `interface_error` — missing interface, incompatible contract, orphan interface, vague contract, missing concrete_files
  - `issue_completeness_error` — epic file body missing required sections (blackbox specs, whitebox guidance, bootstrap context)
  - `spec_fidelity_error` — blackbox specs in issue body don't match phase manifest (truncated, garbled, missing)
  - `feature_coverage_error` — feature dropped from all epics, duplicated across epics, or phantom feature
  - `e2e_coverage_gap` — epic not covered by phase E2E, missing integration scenario
  - `strategic_concern` — architectural ordering issue, over-engineering
  - `false_positive` — agent flagged something that's actually correct

- **`severity`**: `high` (breaks correctness or downstream plan generation), `medium` (suboptimal but functional), `low` (minor improvement)

- **`affected_phase`**: which section of the `space_split.md` command caused this (e.g., "Phase 1.2 — Form Epic Candidates", "Phase 2.3 — Create One Issue Per Epic")

### 6.3 Deduplicate & Prioritize

- Merge similar findings from multiple agents.
- Flag conflicting advice for user review.
- Group by affected command phase and epic.
- Filter out `false_positive` findings.

### 6.3.1 Narrative vs Structural Assessment (Dual Source of Truth)

space_split produces both narrative (epic.md) and JSON (epic_manifest.json) representations of interfaces and dependencies. For each finding that flags a missing or inconsistent structural entry:

1. **Check the OTHER source**: If the finding says "interface X missing from epic_manifest.json `interfaces_provided[]`", check if the interface IS described in the provider's epic.md "Inter-Epic Interfaces" section (and vice versa).
2. **If present in one source but absent in the other**: the finding is valid (BOTH sources MUST be consistent), but **downgrade severity to medium** if it was classified as high. The author understands the interface — they just failed to wire it into both representations. Include explicit `structural_edits` in the finding showing exactly which JSON entries or epic.md sections to add or modify.
3. **If absent from BOTH sources**: keep original severity — the decomposition genuinely missed this interface or dependency.
4. **Check concrete_files against bootstrap-report.json**: If a finding says "concrete_files missing for interface X", check if the files exist in bootstrap-report.json's entity/contract paths. If they do, downgrade and provide the exact paths as `structural_edits`.

### 6.4 Write Iteration Feedback File

Write the feedback to `phases/phase_<N>/feedback/deepen_space_split_feedback.json` (resolved against `paths_relative_to`). **Do NOT modify epic_manifest.json or phase_e2e_config.json** — feedback is always a separate file.

Ensure directory exists: `mkdir -p <paths_relative_to>/phases/phase_<N>/feedback/`

```json
{
  "schema_version": "1.0.0",
  "command": "deepen_space_split",
  "iteration": "<current deepen_space_split iteration from CLI context>",
  "analyzed_iteration": "<main_command_iteration from CLI context>",
  "created_at": "<ISO 8601>",
  "source_outputs_analyzed": {
    "epic_manifest": "phases/phase_N/epic_manifest.json",
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
      "category": "<epic_formation_error|interface_error|issue_completeness_error|spec_fidelity_error|feature_coverage_error|e2e_coverage_gap|strategic_concern>",
      "severity": "high|medium|low",
      "title": "<concise>",
      "description": "<detailed>",
      "affected_output": "<file path or issue number>",
      "affected_section": "<section within file or issue>",
      "recommendation": "<specific action for space_split to take>",
      "structural_edits": [
        "<exact edit 1: e.g., 'Add to epic_manifest.json epics[1].interfaces_provided[]: { name: \"UserAuth\", consumer_epics: [3], concrete_files: [\"app/lib/auth/session.ts\"] }'>",
        "<exact edit 2: e.g., 'Add to epic_3/epic.md Inter-Epic Interfaces consumed section: UserAuth from E1'>"
      ],
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

### Stage 6.5: Generate Convergence Recommendations (CONVERGED ONLY)

**Skip this section entirely if convergence decision is NOT "converged".**

At convergence, scan findings for cross-stage insights worth preserving for downstream commands.

1. **Filter findings with downstream impact:** Only findings where `downstream_impact.affects_commands` is non-empty.
2. **For each affected downstream command** (plan_phase_epic, create_issues_from_plan_swarm), draft a 1-2 sentence observation:
   - Describe the **observed condition** in space_split's output.
   - State the **implication** for the downstream command.
   - Use `"epic": <M>` for epic-specific observations, `"epic": null` for phase-wide observations.
   - Example: "Epic 1 provides 2 critical interfaces (User, Product). Plan should finalize interface contracts before implementing independent components."
   - Example: "Cross-epic dependency Epic 1 → Epic 2 uses UserService interface. Plan should verify interface is testable in isolation before Epic 2 starts."
3. **Write recommendations via CLI** — one call per recommendation:
   ```bash
   eigen-squared add-recommendation \
     --from-cmd deepen_space_split \
     --target <target_cmd> \
     --iteration <main_command_iteration> \
     --text "<observation>"
   ```
   The CLI replaces all entries where `from == "deepen_space_split"` (preserves entries from other deepen commands). Max 5 entries per target command.
4. If no findings have downstream impact, do not write any recommendations.

**Constraints:**
- Recommendations are OPTIONAL. Only write when you genuinely have cross-stage insight.
- Write observations and implications, NOT action items.
- Do NOT prescribe what the downstream command should do — describe what you observed and why it matters.

---

## Stage 7: Lesson Extraction

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

For each new lesson, check the existing lessons loaded in Stage 0.6:
- If a lesson with the same `affected_phase` + `category` + similar `root_cause` already exists, **skip it**.
- If the existing lesson has `"status": "applied"`, still skip.

### 7.3 Write Lesson Files

1. Ensure directory exists: `mkdir -p <paths_relative_to>/<lessons_dir>`
2. For each new non-duplicate lesson, write to: `<paths_relative_to>/<lessons_dir>/<id>.json`
3. Print summary:
   ```
   Lessons written: <N> new lessons to <lessons_dir>
   Skipped: <M> duplicates of existing lessons
   ```

---

## Stage 8: Summary & Next Steps

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
Feedback written to: phases/phase_N/feedback/deepen_space_split_feedback.json
Lessons: <N> new lessons written to <lessons_dir>

Next steps:
  If CONTINUE:
    Run /space_split to re-generate the epic decomposition incorporating the feedback.
    Hint: to add constraints (change epic boundaries, move features), pass your
    instructions as arguments to the next /space_split run.
  If CONVERGED:
    Run /plan_phase_epic to generate plans for the epics.
    Run /compound_improve to apply accumulated lessons to the space_split command.
```
