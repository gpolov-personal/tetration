---
name: deepen_time_split
description: Review time_split output with parallel research agents, diagnose errors, and write lessons to the initiative
---

# Deepen Time Split — Initiative Phase Review

## Introduction

This command takes the output of `/time_split` and subjects it to comprehensive review by parallel research and review agents. Every structural, content, and strategic issue is diagnosed.

Diagnosed errors are written as structured lesson JSONs to `$EIGEN_ROOT/eigen_initiative/eigen_lessons/time_split/`. These lessons are later consumed by `/compound_improve` to permanently improve the `time_split` command itself.

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
4. Verify `$EIGEN_ROOT/eigen_initiative/phases` exists and contains `initiative_summary.json` and at least one `phase_*_manifest.md`. If not → **STOP.** Print:
   ```
   ERROR: No time_split output found at $EIGEN_ROOT/eigen_initiative/phases
   Run /time_split first to generate the phase split.
   ```

### Fixed Paths

- **Phases directory**: `$EIGEN_ROOT/eigen_initiative/phases`
- **Feedback file**: `$EIGEN_ROOT/eigen_initiative/phases/feedback/deepen_time_split_feedback.json`
- **Lessons directory**: `$EIGEN_ROOT/eigen_initiative/eigen_lessons/time_split/`
- **Pipeline state**: `$EIGEN_ROOT/eigen_initiative/phases/pipeline_state.json`

---

## Pipeline Awareness

Load the `pipeline-state-schema` skill for the full schema, field definitions, and feedback lifecycle.

### On Entry

1. Read `$EIGEN_ROOT/eigen_initiative/phases/pipeline_state.json`.
   - **Not found** → **STOP.** Print: "No pipeline_state.json found. Run `/time_split` first to generate the phase split."
   - **Found** → check `state.time_split`:
     - `state.time_split.status == "not_started"` → **STOP.** Print: "time_split has not run yet. Run `/time_split` first."
     - `state.time_split.convergence.converged == true` → **STOP.** Print: "time_split has already converged (decided at `<decided_at>`: `<reason>`). No further review needed."
   - Check `state.deepen_time_split.feedback_consumed`:
     - `feedback_consumed == false` AND feedback file exists → warn: "Existing feedback has not been consumed by time_split yet. Re-analyzing will overwrite it." Proceed anyway.
   - Read current `state.deepen_time_split.iteration` to determine iteration context.

### On Exit

Update `$EIGEN_ROOT/eigen_initiative/phases/pipeline_state.json`:
- Set `state.deepen_time_split.status` to `"completed"`
- Increment `state.deepen_time_split.iteration`
- Set `state.deepen_time_split.last_run_at` to current ISO 8601 timestamp
- Set `state.deepen_time_split.feedback_path` to the feedback file path
- Set `state.deepen_time_split.feedback_consumed` to `false` (fresh feedback, not yet processed)
- Set `state.time_split.feedback_consumed` to `false` (signal to time_split that fresh feedback is available)
- Update `state.deepen_time_split.findings_summary` with counts from the feedback file
- If convergence was decided:
  - Set `state.time_split.convergence.converged` to `true`
  - Set `state.time_split.convergence.decided_by` to `"deepen_time_split"`
  - Set `state.time_split.convergence.decided_at` to current ISO 8601 timestamp
  - Set `state.time_split.convergence.reason` to the convergence rationale
  - Write low-severity findings with downstream impact to `recommendations` (see Phase 5.5 — Generate Convergence Recommendations)
- If continuing iteration:
  - Set `state.time_split.status` to `"iterating"`
- Set `updated_at` to current timestamp

---

## Iteration Protocol

### Detect Iteration Context

1. Check if `$EIGEN_ROOT/eigen_initiative/phases/feedback/deepen_time_split_feedback.json` already exists (previous feedback from an earlier deepen run).
2. If it exists, read it. This enables:
   - Comparison of findings across iterations
   - Oscillation detection
   - Progress tracking
3. If no previous feedback exists, this is the first deepen iteration — proceed with fresh analysis.

### Finding Matching Protocol (iteration 2+)

When comparing current findings against previous iteration findings, use **feature-ID matching** — not title or description matching:

1. For each current finding, extract all feature IDs (F01, F02...) and phase numbers mentioned in `description`, `recommendation`, and `affected_output`.
2. For each previous finding, extract the same feature IDs and phase numbers.
3. Two findings **match** if they share at least one feature ID AND belong to the same `category` (e.g., both are `cross_phase_dep_error` about F09).
4. Classify matched findings:
   - **Persisting**: current finding matches a previous finding that was NOT addressed → add previous ID to `findings_persisting`
   - **Regressed**: current finding matches a previous finding that WAS addressed (appeared in `findings_addressed` of the previous comparison) → add to `findings_regressed`
   - **Oscillating**: current finding matches a finding that has appeared in 3+ non-consecutive iterations, or has been in `findings_regressed` at least once → add to `oscillating_findings`
5. Findings with NO feature-ID match to any previous finding → `new_findings`.

This protocol is deterministic: feature IDs (F01, F02...) are stable across reformulations, unlike titles and descriptions which the LLM may rephrase each iteration.

### Convergence Decision Protocol

After collecting all findings (Phase 5), apply these convergence rules **in order**:

1. **Converge if**: zero high-severity findings AND zero medium-severity findings remain.
   - Rationale: "All significant issues resolved."

2. **Converge if**: iteration limit reached (`state.deepen_time_split.iteration >= 8`).
   - Rationale: "Maximum iteration limit (8) reached. Accepting current state."
   - Set `convergence.iteration_limit_reached` to `true` in the feedback file.

3. **Converge if**: stagnation detected — more than 50% of current high+medium findings match (by feature ID, per the Finding Matching Protocol) findings from 2 iterations ago (i.e., the same features keep appearing in findings across iterations without resolution).
   - Rationale: "Stagnation detected. The same features keep appearing in findings across iterations. Accepting current state — remaining issues are better resolved by downstream commands (bootstrap, space_split)."

4. **Converge if**: oscillation detected AND no non-oscillating high-severity or medium-severity findings remain.
   - Oscillation = a finding was fixed in iteration N, reappeared in N+1, fixed again in N+2 (or a finding alternates between accept/reject across iterations).
   - Rationale: "Oscillation detected on findings [<ids>]. Accepting current state to break the cycle."
   - Set `convergence.oscillation_detected` to `true` and record `oscillation_details` in the feedback file.

5. **Continue if**: any high-severity or medium-severity actionable findings remain that have not oscillated or stagnated.
   - Decision: `"continue"`

### Downstream Impact Assessment

For each finding, assess its downstream impact on later pipeline commands:
- Document which downstream commands (bootstrap, space_split, etc.) would be affected in `findings[].downstream_impact`.
- Downstream impact informs recommendations at convergence — findings with downstream impact that are low-severity become candidates for the `recommendations` channel.

---

## Phase 0: Ingest

### 0.1 Read Initiative Summary

1. Read `$EIGEN_ROOT/eigen_initiative/phases/initiative_summary.json`.
2. Extract: initiative name, total features, phase count, DAG stats, source files, per-phase summaries.

### 0.2 Read All Phase Manifests

1. Glob `$EIGEN_ROOT/eigen_initiative/phases/phase_*_manifest.md`.
2. For each manifest, parse YAML frontmatter and markdown body:
   - Frontmatter: `phase`, `feature_count`, `clusters_included`, `priority_distribution`, `e2e_summary`, `depends_on_phases`
   - Body: features by domain tables, cross-phase dependencies, clusters, blackbox specs, whitebox sections

### 0.3 Read Original Initiative Files

1. From the initiative summary's `source_files` field, get the filenames of the original initiative, blackbox, and whitebox files. These files are located in `$EIGEN_ROOT/eigen_initiative/`.
2. Read all available files (whitebox may not exist).

### 0.4 Load Existing Lessons

1. Glob `$EIGEN_ROOT/eigen_initiative/eigen_lessons/time_split/*.json`.
2. Read and parse each lesson JSON — used to avoid duplicating known issues in Phase 6.

---

## Phase 1: Structural Validation

Spawn **all validation agents in parallel** (one `Task general-purpose` per check):

### 1.1 DAG Correctness Agent

```
Prompt: "Validate the dependency DAG for this initiative phase split.

For each phase manifest, check:
1. Every feature's dependencies (local_deps + cross_phase_deps) point to features in the SAME or EARLIER phase — never a later phase
2. No circular dependencies within any phase
3. Cross-phase dependencies correctly identify the source phase
4. All feature IDs in dependency lists actually exist in the initiative

Phase manifests:
<all phase manifests>

Report every violation as: {feature_id, violation_type, details}"
```

### 1.2 Cluster Integrity Agent

```
Prompt: "Check cluster integrity across phases.

Rule: All features in a cluster MUST be in the same phase. A cluster split across phases is always an error.

Clusters from initiative:
<clusters from initiative_summary or phase manifests>

Phase assignments:
<feature → phase mapping from all manifests>

Report every cluster that appears in more than one phase: {cluster_id, features, phases_found_in}"
```

### 1.3 E2E Progressiveness Agent

```
Prompt: "Evaluate whether each phase enables a progressive E2E test.

For each phase (cumulative — phase N includes features from phases 1..N):
1. Is there at least one data ingestion/input feature?
2. Is there at least one processing/business logic feature?
3. Is there at least one persistence/storage feature?
4. Is there at least one frontend/output/API feature?
5. Does the e2e_summary in the manifest accurately describe a testable flow?

Phase manifests with their e2e_summary:
<all phase manifests>

For each phase, rate E2E coverage as: COMPLETE / PARTIAL (missing which layer?) / BROKEN (no testable flow)"
```

### 1.4 Phase Balance Agent

```
Prompt: "Evaluate phase balance for this initiative split.

Check:
- P1 features should be front-loaded (earlier phases)
- No phase should have ALL deferrable features
- Bottleneck features (high fan-out) should be in early phases
- Phases should be roughly balanced in size

Initiative summary:
<initiative_summary JSON>

Phase manifests:
<all phase manifests>

Report:
1. Phases that are disproportionately large or small compared to others
2. P1 features in late phases that have no dependency-driven reason for being late
3. Bottleneck features in late phases
4. Phases with skewed priority distribution"
```

### 1.5 Cross-Phase Dependencies Agent

```
Prompt: "Validate cross-phase dependencies are complete and accurate.

For each feature in phase N that depends on a feature in phase M (where M < N):
1. Is this dependency listed in the 'Cross-Phase Dependencies' table of phase N's manifest?
2. Is the nature/description of the dependency accurate?
3. Are there any MISSING cross-phase dependencies (feature A in phase 2 depends on feature B in phase 1, but this isn't listed)?

Phase manifests:
<all phase manifests>

Report missing, incorrect, or incomplete cross-phase dependency entries."
```

---

## Phase 2: Content Validation

Spawn **all content agents in parallel:**

### 2.1 Blackbox Completeness Agent

```
Prompt: "Check that every feature in every phase manifest has its full blackbox specification.

For each feature ID found in any phase manifest's feature tables:
1. Does the 'Blackbox Feature Specifications' section of that manifest contain a spec for this feature?
2. Is the spec complete (has Inputs, Outputs, Behavior, Acceptance Criteria)?
3. Does the spec match the original blackbox document (not truncated or garbled)?

Phase manifests:
<all phase manifests>

Original blackbox document:
<blackbox document content>

Report: missing specs, truncated specs, mismatched specs."
```

### 2.2 Whitebox Relevance Agent

**Skip this agent if no whitebox file was provided** (check `source_files.whitebox` in the initiative summary — if null, the initiative has no whitebox reference and phase manifests won't have whitebox sections).

```
Prompt: "Check that whitebox reference sections in each phase manifest are relevant and complete.

For each phase manifest:
1. Which domains are represented by the phase's features?
2. Does the 'Whitebox Reference Sections' include guidance for ALL those domains?
3. Are there any whitebox sections included that are NOT relevant to the phase's domains (noise)?
4. Are there important whitebox sections MISSING for the phase's domains?

Phase manifests:
<all phase manifests>

Full whitebox reference:
<whitebox document content>

Report: missing domain coverage, irrelevant sections included, important sections omitted."
```

---

## Phase 3: Strategic Review

Spawn **review agents in parallel:**

### 3.1 Architecture Strategist Review

Spawn as `Task eigen:architecture-strategist`:

```
Prompt: "Review this initiative-to-phases decomposition from an architectural perspective.

Check:
1. Does the phase ordering make architectural sense? (foundations before features, data layer before UI)
2. Are there phases that are too ambitious (too many complex features) or too thin?
3. Is there risk concentration (many bottleneck features in one phase)?
4. Are integration points between phases well-defined?
5. Does each phase build meaningfully on the prior one?

Initiative summary:
<initiative_summary>

Phase manifests:
<all phase manifests>"
```

### 3.2 Best Practices Research

Spawn as `Task eigen:best-practices-researcher`:

```
Prompt: "Research best practices for decomposing large software initiatives into sequential phases.

Compare the phase split against:
1. Industry patterns for incremental delivery
2. Progressive E2E testing strategies
3. Risk management through phased delivery
4. Team scaling patterns across phases

Initiative context:
<initiative_summary>

Phase split summary:
<phase count, feature counts, E2E summaries>"
```

---

## Phase 4: Skills Application

### 4.1 Discover and Apply Available Skills

1. Discover ALL available skills from all sources (project, user, all plugins).
2. Match skills to the initiative's domains and technologies.
3. Spawn one sub-agent per matched skill to review the phase split through that skill's lens.
4. Spawn all in parallel.

---

## Phase 5: Synthesize & Enhance

### 5.1 Collect All Agent Results

Wait for ALL parallel agents to complete. Collect findings from:
- Structural validation agents (Phase 1)
- Content validation agents (Phase 2)
- Strategic review agents (Phase 3)
- Skills agents (Phase 4)

### 5.2 Categorize Findings

For each finding, assign:

- **`category`**: one of:
  - `structural_error` — DAG violation, cluster split, missing dependency
  - `balance_issue` — phase too large/small, priority misordering, bottleneck placement
  - `content_gap` — missing blackbox spec, irrelevant/missing whitebox section
  - `e2e_gap` — phase doesn't enable progressive E2E testing
  - `strategic_concern` — risk concentration, architectural ordering issue
  - `cross_phase_dep_error` — missing or incorrect cross-phase dependency
  - `false_positive` — agent flagged something that's actually correct upon analysis

- **`severity`**: `high` (breaks correctness), `medium` (suboptimal but functional), `low` (minor improvement)

- **`affected_phase`**: which section of the `time_split.md` command caused this (e.g., "Phase 1.2 — Seed Phase 1", "Phase 1.3 — Layer Remaining Features")

### 5.3 Deduplicate & Prioritize

- Merge similar findings from multiple agents.
- Flag conflicting advice for user review.
- Group by affected command phase.
- Filter out `false_positive` findings.

### 5.3.1 Narrative vs Structural Assessment

For each finding that flags a missing structural entry (e.g., feature not in Cross-Phase Dependencies table, cluster assignment inconsistent, E2E summary missing features):

1. **Check if the concern IS described in narrative sections** of the phase manifest (context paragraphs, whitebox reference sections). Search for the feature ID, dependency, or concept in the full manifest text.
2. **If narratively present but structurally absent**: the finding is valid (the structural section MUST be fixed), but **downgrade severity to medium** if it was classified as high. The author understands the requirement — they just failed to update the structural table/YAML. Include explicit `structural_edits` in the finding's `recommendation` showing exactly which table rows or YAML fields to add or modify.
3. **If neither narratively nor structurally present**: keep original severity — the manifest genuinely missed this concern.

### 5.4 Write Iteration Feedback File

Write the feedback to `$EIGEN_ROOT/eigen_initiative/phases/feedback/deepen_time_split_feedback.json`. **Do NOT modify phase manifests or initiative_summary.json** — feedback is always a separate file.

Ensure directory exists: `mkdir -p $EIGEN_ROOT/eigen_initiative/phases/feedback/`

```json
{
  "schema_version": "1.0.0",
  "command": "deepen_time_split",
  "iteration": "<current deepen_time_split iteration>",
  "analyzed_iteration": "<state.time_split.iteration that was analyzed>",
  "created_at": "<ISO 8601>",
  "source_outputs_analyzed": {
    "initiative_summary": "phases/initiative_summary.json",
    "phase_manifests": ["phases/phase_1_manifest.md", "..."]
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
    "findings_addressed": ["<finding IDs from previous feedback that are now resolved>"],
    "findings_persisting": ["<finding IDs still present unchanged>"],
    "findings_regressed": ["<finding IDs that were fixed but reappeared>"],
    "new_findings": ["<finding IDs that are new in this iteration>"],
    "oscillating_findings": ["<finding IDs that have oscillated across iterations>"]
  },
  "findings": [
    {
      "id": "dtf-<sequential_number>",
      "category": "<structural_error|balance_issue|content_gap|e2e_gap|cross_phase_dep_error|strategic_concern>",
      "severity": "high|medium|low",
      "title": "<concise>",
      "description": "<detailed>",
      "affected_output": "<file path of the output file with the issue>",
      "affected_section": "<section within that file>",
      "recommendation": "<specific action for time_split to take>",
      "structural_edits": [
        "<exact edit 1: e.g., 'Add row to Phase 2 Feature Summary Table: F09 | Live Preview | P1 | F03 (cross-phase) | C2-RUNTIME'>",
        "<exact edit 2: e.g., 'Add to Phase 2 Cross-Phase Dependencies: F09 (Phase 2) depends on F03 (Phase 1)'>",
        "<exact edit 3: e.g., 'Update Phase 2 YAML frontmatter feature_count from 5 to 6'>"
      ],
      "actionable_by": "time_split",
      "downstream_impact": {
        "affects_commands": ["bootstrap", "space_split"],
        "impact_description": "<what breaks downstream if this is not fixed>"
      }
    }
  ],
  "summary": {
    "total_findings": "<count>",
    "by_severity": { "high": "<count>", "medium": "<count>", "low": "<count>" },
    "by_category": { "<category>": "<count>" }
  }
}
```

Apply the Convergence Decision Protocol (from the Iteration Protocol section above) to set `convergence.decision`.

### 5.5 Generate Convergence Recommendations (CONVERGED ONLY)

**Skip this section entirely if convergence decision is NOT "converged".**

At convergence, scan low-severity findings for cross-stage insights worth preserving for downstream commands. See the `pipeline-state-schema` skill for the full recommendations specification.

1. **Filter findings with downstream impact:** Only low-severity findings where `downstream_impact.affects_commands` is non-empty.
2. **For each affected downstream command** (bootstrap, space_split, plan_phase_epic, create_issues_from_plan_swarm), draft a 1-2 sentence observation:
   - Describe the **observed condition** in the time_split output.
   - State the **implication** for the downstream command.
3. **Write to pipeline_state.json** — update `recommendations[<target_command>]`:
   - Replace all entries where `from` == `"deepen_time_split"` (preserve entries from other deepen commands).
   - Max 5 entries per target command.
   - Each entry: `{ "from": "deepen_time_split", "at_iteration": <current iteration>, "phase": <N or null>, "epic": null, "text": "<observation>" }`
4. If no findings have downstream impact, do not write any recommendations. Leave existing entries from other sources untouched.

**Constraints:**
- Recommendations are OPTIONAL. Only write when you genuinely have cross-stage insight.
- Write observations and implications, NOT action items.
- Do NOT prescribe what the downstream command should do — describe what you observed and why it matters.

---

## Phase 6: Lesson Extraction

### 6.1 Generate Lesson JSONs

For each non-false-positive finding, create a lesson JSON:

```json
{
  "id": "ts-lesson-<timestamp>-<sequential>",
  "created_at": "<ISO 8601 timestamp>",
  "command": "time_split",
  "status": "pending",
  "category": "<category from 5.2>",
  "severity": "<high|medium|low>",
  "title": "<concise description of the error>",
  "description": "<detailed explanation of what went wrong>",
  "root_cause": "<why the time_split command produced this error>",
  "recommendation": "<specific change to make in the time_split command>",
  "affected_phase": "<which phase/section of time_split.md to modify>",
  "evidence": {
    "features_involved": ["<feature IDs>"],
    "phases_involved": [1, 2],
    "agent_source": "<which review agent found this>"
  },
  "initiative_context": "<initiative name, feature count>",
  "tags": ["<relevant tags>"]
}
```

### 6.2 Deduplicate Against Existing Lessons

For each new lesson, check the existing lessons loaded in Phase 0.4:
- If a lesson with the same `affected_phase` + `category` + similar `root_cause` already exists, **skip it** (don't write a duplicate).
- If the existing lesson has `"status": "applied"`, still skip (the command has already been improved for this).

### 6.3 Write Lesson Files

1. Ensure directory exists: `mkdir -p $EIGEN_ROOT/eigen_initiative/eigen_lessons/time_split/`
2. For each new non-duplicate lesson, write to: `$EIGEN_ROOT/eigen_initiative/eigen_lessons/time_split/<id>.json`
3. Print summary:
   ```
   Lessons written: <N> new lessons to $EIGEN_ROOT/eigen_initiative/eigen_lessons/time_split/
   Skipped: <M> duplicates of existing lessons
   ```

---

## Phase 7: Summary & Next Steps

Print a comprehensive summary:

```
=== Time Split Review Complete ===

Initiative: <name>
Phases reviewed: <N>
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

Convergence: <CONVERGED — reason | CONTINUE — N high/medium-severity findings remain>
Feedback written to: $EIGEN_ROOT/eigen_initiative/phases/feedback/deepen_time_split_feedback.json
Lessons: <N> new lessons written to $EIGEN_ROOT/eigen_initiative/eigen_lessons/time_split/

Next steps:
  If CONTINUE:
    Run /time_split to re-generate the phase split incorporating the feedback.
    Hint: to add constraints (move features, change phase count), pass your
    instructions as arguments to the next /time_split run.
  If CONVERGED:
    Run /bootstrap to create the project foundation for Phase 1.
    Run /compound_improve to apply accumulated lessons to the time_split command.
```

### Commit Pipeline Artifacts

```bash
cd $EIGEN_ROOT
git add eigen_initiative/phases/feedback/ eigen_initiative/phases/pipeline_state.json
git commit -m "pipeline: deepen_time_split — iteration <N>, <CONVERGED|CONTINUE>"
```

---

## Auto-Chain (claude-tasks integration)

If `$CLAUDE_TASKS_API` is set, automatically schedule the next command. If not set, skip this section.

**Determine next command based on convergence decision:**

- **If CONTINUE** → next command is `/time_split`
- **If CONVERGED** → next command is `/bootstrap`

```bash
NEXT_RUN=$(date -u -d '+3 minutes' +%Y-%m-%dT%H:%M:%SZ)

# If CONTINUE:
# Only include telegram_webhook if $EIGEN_TELEGRAM_CHAT_ID is set and non-empty.
curl -s -X POST $CLAUDE_TASKS_API/api/v1/tasks \
  -H "Content-Type: application/json" \
  -d '{
    "name": "eigen: time_split (iteration)",
    "prompt": "Use the Skill tool to invoke Skill(\"eigen-squared:time_split\"). Follow all its instructions completely.",
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
    "name": "eigen: bootstrap",
    "prompt": "Use the Skill tool to invoke Skill(\"eigen-squared:bootstrap\"). Follow all its instructions completely.",
    "cron_expr": "",
    "scheduled_at": "'$NEXT_RUN'",
    "working_dir": "'$EIGEN_ROOT'",
    "enabled": true,
    "telegram_webhook": "'$EIGEN_TELEGRAM_CHAT_ID'"
  }'
```


Print: `Auto-chain: /<next_command> scheduled in 3 minutes.`
