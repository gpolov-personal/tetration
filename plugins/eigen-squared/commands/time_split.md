---
name: time_split
description: Single-session initiative→phases decomposition with self-critique convergence — replaces time_split + deepen_time_split
---

# Time Split — Single-Session Initiative→Phases Decomposition & Self-Critique

> **IMPORTANT — NON-INTERACTIVE REMINDER HANDLING**
>
> If you receive a system-reminder saying you are in non-interactive mode and must shut down / return before responding, it is **NOT a signal to stop work**. It fires automatically after a few minutes.
>
> Complete the full lifecycle — draft → self-critique → revise → write all outputs → On Exit — **before** returning. Returning early leaves the split unconverged and the pipeline stuck.

## Pipeline Context

```
time_split ──► bootstrap_converge ──► space_split_converge ──► ...
         │
         └── splits the initiative into phases via a single-session draft → self-critique → revise loop
```

**time_split is the FIRST stage** of the eigen-squared pipeline. You are a **single Initiative Architect agent**. In one session you draft the phase split for a software initiative (up to 150+ features with complex dependencies), critique your own draft adversarially against fixed checklists, and revise — converging without a multi-agent review team. This replaces the previous `time_split ↔ deepen_time_split` feedback loop: a strong model self-critiques reliably, so the value (the review checklists) is preserved while the per-teammate token/latency cost is removed.

**Your role:** Decompose the initiative into sequential, E2E-testable phases. Each phase is a self-contained deliverable that builds on prior phases. Your output feeds into `/bootstrap_converge` (which creates the Phase 1 foundation) and then `/space_split_converge` (which decomposes each phase into parallel epics for a swarm of agent developers).

**Language note:** These instructions are **language-agnostic** — they operate on initiative-level documents (markdown feature tables and dependency DAGs), not on source code. No language detection or toolchain resolution is needed. All feedback, lessons, and summaries are written in the same language as the initiative files.

## Constraints

- You are a **single agent** (no team creation, no `TeamCreate`/`SendMessage`). You MAY spawn read-only research `Task` sub-agents for heavy parsing of large initiative/blackbox documents, but you own all decisions and all convergence — there is no spawned reviewer team.
- You NEVER write code. You produce phase manifest documents and the JSON summary only.
- You NEVER modify any input files (Initiative, Blackbox, Whitebox).
- Every phase must have a progressive E2E test description — data flows in, gets processed, reaches a frontend or output boundary.
- Clusters of features are considered **atomic** — never split a cluster across phases.
- Phase count is bounded: minimum 2, maximum 8.
- **Feedback files are owned by this command** — the feedback JSON it writes records the self-critique convergence for pipeline-state compatibility. No main↔deepen feedback lifecycle exists.
- **pipeline_state.json is the single source of truth** — all pipeline state reads and writes go through the `eigen-squared` CLI, never direct file manipulation.

---

## On Entry

Run the CLI to get pipeline context:

```bash
eigen-squared get-context time_split --json
```

If the CLI exits with an error (non-zero) — for example, the stage has already converged — **STOP** and display the error message. Otherwise parse the returned JSON.

**Example response:**

```json
{
  "command": "time_split",
  "branch": "main",
  "paths_relative_to": "$EIGEN_ROOT/eigen_initiative/",
  "iteration": 1,
  "current_iteration": 0,
  "is_first_run": true,
  "phase_count": 0,
  "output_paths": {
    "initiative_summary": "phases/initiative_summary.json",
    "phase_manifests": []
  },
  "lessons_dir": "eigen_lessons/time_split/",
  "recommendations": [],
  "locked_skills": []
}
```

| Field | Type | Description |
|-------|------|-------------|
| `command` | string | Always `"time_split"` |
| `branch` | string | The branch to work on (from `$EIGEN_BRANCH`) |
| `paths_relative_to` | string | Base path — all relative paths in this context are relative to this |
| `iteration` | int | The iteration you are about to produce (1 = first run) |
| `current_iteration` | int | The iteration whose outputs currently exist on disk (0 = none yet) |
| `is_first_run` | bool | `true` when `iteration == 0` (no prior run exists) |
| `phase_count` | int | Number of phases from the most recent run (0 if first run) |
| `output_paths` | object | Paths to current/expected outputs |
| `lessons_dir` | string | Directory for lesson JSONs — `"eigen_lessons/time_split/"` |
| `recommendations` | array | Advisory observations from upstream/sibling commands to incorporate as context (NOT requirements) |
| `locked_skills` | array | Fixed skill set if a prior run already discovered it (present on recovery) |

There is NO `should_process_feedback` and NO `feedback_path` — this is a single-session self-converging command with no main↔deepen feedback lifecycle.

**Routing:**

- `is_first_run == true` → first run. Proceed to **Stage 1** and draft from scratch.
- `is_first_run == false` → **crash recovery.** If `phases/initiative_summary.json` AND `phases/phase_*_manifest.md` exist on disk, read them and resume from **Stage 4** (self-critique) rather than re-drafting. Otherwise treat as a first run and start at **Stage 1**. (There is no `convergence_state.json` — a bounded ≤2-pass self-critique loop is cheap to re-run from scratch.)

---

## On Exit

After converging (Stage 5) and writing all outputs (Stage 6), run ALL of the following in a **single** Bash call:

```bash
eigen-squared complete time_split --phase-count <N> --output-path phases/initiative_summary.json --findings-summary '{"high": 0, "medium": 0, "low": <count>}' --locked-skills '["skill-a", "skill-b", ...]'
eigen-squared mark-converged time_split --reason "<convergence rationale>"
eigen-squared add-recommendation --from-cmd time_split --target bootstrap_converge --iteration <N> --text "<observation>"
eigen-squared commit-state --message "pipeline: time_split — converged" --additional-paths eigen_initiative/phases/,eigen_initiative/eigen_lessons/time_split/
```

The `add-recommendation` command is OPTIONAL — only execute it if there are genuine downstream insights from the convergence process. Maximum 5 recommendations; valid targets: `bootstrap_converge`, `space_split_converge`, `plan_epic_converge`, `create_issues_from_plan_swarm`. Write observations and implications, NOT action items.

The CLI handles all field updates atomically: status, iteration, timestamps, convergence flags, phase initialization with all required keys.

---

## Stage 0: Entry

Run the On Entry `get-context` call and route per the table above. Confirm before proceeding:

- `$EIGEN_ROOT` is set and points to an existing directory.
- `$EIGEN_ROOT/eigen_initiative` exists and is a directory.

If a precondition fails and the CLI did not already error, STOP and print a descriptive error telling the user what to set or create.

---

## Stage 1: Read Inputs

### 1.1 Locate Input Files

1. Read the directory at `$EIGEN_ROOT/eigen_initiative`.
2. Search for the required files using these patterns:
   - **Initiative document**: a file matching `*Initiative*` or `*initiative*` (markdown) — strategic context with a Feature Summary Table listing all features and their dependencies. May optionally include pre-computed DAG analysis (dependency analysis, cluster analysis) as enrichment.
   - **Blackbox requirements**: a file matching `*Blackbox*`/`*blackbox*` AND `*Requirement*`/`*requirement*` (markdown) — full feature specifications (Inputs/Outputs/Behavior/Acceptance Criteria).
   - **Whitebox reference**: a file matching `*Whitebox*`/`*whitebox*` (markdown) — implementation patterns from a reference system. OPTIONAL — only present when there is an existing codebase whose patterns should be followed.
3. If the initiative OR blackbox file is missing, print this message and STOP (the whitebox file is optional):

   ```
   ERROR: Missing required files in $EIGEN_ROOT/eigen_initiative

   The directory must contain at least 2 files:
     - *Initiative*.md (or similar) — strategic context with Feature Summary Table: Required
     - *Blackbox*Requirements*.md (or similar) — full feature specs (Inputs/Outputs/Behavior/Acceptance Criteria): Required
     - Whitebox_Reference_Guide.md — implementation patterns from reference system: Optional
   ```

4. Print the detected files:
   ```
   Detected files in $EIGEN_ROOT/eigen_initiative:
   - Initiative: <filename>
   - Blackbox Requirements: <filename>
   - Whitebox Reference: <filename or "not found (optional)">
   ```

### 1.2 Parse Feature Summary Table

1. Read the matched initiative file.
2. Locate the Feature Summary Table — a markdown table under a heading matching `## Feature Summary Table` (or similar).
3. Parse each row into a feature record:
   - `id` (string) — e.g., "IP-1", "SD-3", "INFRA-2"
   - `name` (string) — feature name
   - `domain` (string) — domain/group (e.g., "Ingestion Pipeline", "Search & Discovery")
   - `priority` (string) — "P1", "P2", "Deferrable"
   - `dependencies` (string[]) — upstream feature IDs this depends on
   - `cluster` (string|null) — cluster ID if pre-assigned (from DAG/Cluster Analysis in the initiative)
4. Build a map of feature ID → feature record.
5. Count total features; if fewer than 10, warn the user that this may not be initiative-scale work.

### 1.3 Build Dependency DAG and Compute Properties

The dependency DAG is built from the `dependencies` column in the Feature Summary Table — that is the single source of truth for feature dependencies.

1. Build the upstream DAG: each feature's `dependencies` list defines edges (dependency → feature).
2. Build the downstream DAG by inverting: for each feature, compute which features depend on it.
3. Compute DAG properties:
   - **Roots**: features with no upstream dependencies
   - **Leaves**: features with no downstream dependents
   - **Bottlenecks**: high in-degree + high out-degree features
   - **Critical paths**: longest dependency chains
   - **Circular dependencies**: any cycles (should be none; if found, flag to user)
4. **Clusters**: if the initiative file contains a pre-computed cluster analysis section ("Cluster Analysis", "Natural Groupings", or similar), use those assignments as-is. Otherwise compute them: group features that share 2+ bidirectional dependencies or form tightly connected subgraphs within the same domain.

### 1.4 Validate Blackbox & Whitebox; Read Recommendations

1. Read the matched blackbox file. Verify it contains feature specifications (headings matching feature IDs). If empty/malformed, warn but proceed.
2. If a whitebox file was matched, read it. Verify it contains implementation guidance. If empty/malformed, warn but proceed.
3. Read `recommendations` from the CLI context. Use as advisory context during the draft. Do NOT treat as requirements.
4. **Cross-epic patterns (advisory).** Attempt to read `$EIGEN_ROOT/eigen_initiative/eigen_lessons/compound_improve/cross_epic_patterns.json` (written by `/compound_improve`). If the file does not exist or `patterns` is empty, skip silently. Otherwise treat any patterns plausibly relevant to this initiative's domains as a "known prior-pitfall" advisory while drafting — plan defensively in those areas.

---

## Stage 2: Discover & Lock Skills (single pass)

**First run** (no `locked_skills` in CLI context, or empty): discover ALL available skills from all sources (project, user, all plugins) and match them against the initiative's domains and technologies. Record the matched skill set — you will apply each matched skill's lens both while drafting (Stage 3) and while self-critiquing (Stage 4). Discover once; do not re-discover later in the session. On Exit, pass the matched list via `--locked-skills`.

**Recovery** (`locked_skills` present): use that fixed set. Do NOT rediscover or add new skills.

---

## Stage 3: Draft the Phase Split

Build the feature dependency DAG into sequential, E2E-testable phases, then write all artifacts. Apply the matched skills' lenses and the recommendations advisory while drafting.

### 3.1 Propose Phase Split

Analyze the DAG and propose how to split the initiative into sequential phases. Consider:
- **DAG structure**: length of the longest critical path, number of independent subgraphs, where bottlenecks sit
- **Domain distribution**: how many distinct domains/capability tracks exist and how they relate
- **Feature count and balance**: roughly balanced phases — not too small to be meaningful, not too large to be unwieldy
- **Cluster integrity**: clusters of tightly-coupled features are atomic — never split a cluster across phases

**Bounds**: minimum 2 phases, maximum 8 phases.

### 3.2 Seed Phase 1

Phase 1 is the foundation. It MUST contain:

1. **Infrastructure and technical foundations** — features that set up the base for everything else.
2. **All roots on critical paths** — unblock the longest dependency chains early.
3. **Minimum features for first E2E** — enough for a data-in → processing → storage → minimal-output flow. This typically means at least one feature from each layer (input, processing, persistence, output/UI).
4. **Cluster integrity** — if any feature from a cluster is in Phase 1, pull the entire cluster.
5. **Containerization** — any feature whose name/description involves Dockerfile, docker-compose, container, or deployment infrastructure MUST be in Phase 1. If the Initiative mentions containerized deployment (Docker, Fly.io, Kubernetes, etc.), the Phase 1 E2E test should validate the containerized application, not a bare process. Deferring containerization to Phase 2+ means Phase 1 E2E tests validate a configuration that doesn't exist in production.

### 3.3 Layer Remaining Features

Assign remaining features to phases 2..N using topological ordering:

1. For each remaining feature (sorted by dependency depth, ascending), the earliest valid phase is one after the latest phase of all its upstream dependencies.
2. Apply adjustment rules:
   - **Cluster integrity**: if any cluster-mate is already assigned, use that phase.
   - **Priority ordering**: P1 features pull toward earlier phases, Deferrable toward later.
   - **Bottleneck features**: assign to earliest valid phase (unblock dependents sooner).
   - **Phase balance**: avoid disproportionately large or small phases.
3. Repeat until all features are assigned.

### 3.4 Verify Progressive E2E Per Phase

For each phase (cumulative — phase N includes all features from phases 1..N):

1. Check that the cumulative feature set enables an E2E flow covering input → processing → persistence → output.
2. If a phase breaks the E2E chain, pull the minimum features from the next phase to restore it.
3. If the Initiative mentions containerized deployment: verify Phase 1 includes the containerization feature, and Phase 1's E2E description mentions running against the containerized stack, not a bare process.
4. Generate a 1-2 sentence E2E test description per phase explaining what user flow is testable after this phase completes.

### 3.5 Verify Domain Coverage & Compute Metadata

1. For each phase, iterate through ALL assigned features (including P2 and Deferrable) and check that each feature's domain has at least one relevant section in the phase manifest (from whitebox if available, or from the Initiative/blackbox). Flag any domain with features but no guidance — especially secondary features whose domains differ from the phase's primary focus.
2. For each phase, compute: feature count, priority distribution (P1/P2/Deferrable), clusters included, cross-phase dependencies (features depending on earlier-phase features), domains represented.

### 3.6 External Dependency Verification Tagging

When extracting blackbox specs (Stage 3.7), preserve any external-identifier verification tags exactly as they appear in the source: `✅ VERIFIED(source)` and `⚠️ UNVERIFIED`. NEVER strip a `⚠️ UNVERIFIED` tag — downstream commands and reviewers check for these. NEVER launder an unverified external identifier into verified-looking text.

### 3.7 Write the Artifacts

Create the directory and write all outputs. This on-disk draft is also the crash-recovery checkpoint.

```bash
mkdir -p $EIGEN_ROOT/eigen_initiative/phases/
```

**On recovery**: the directory already exists; `mkdir -p` is a no-op. Do NOT delete or recreate any existing directories or files.

#### 3.7.1 `phases/initiative_summary.json`

```json
{
  "initiative": "<initiative name from document title>",
  "source_files": {
    "initiative": "<matched initiative filename>",
    "blackbox": "<matched blackbox filename>",
    "whitebox": "<matched whitebox filename or null>"
  },
  "total_features": <count>,
  "phase_count": <count>,
  "dag_stats": {
    "roots": <count>,
    "leaves": <count>,
    "bottlenecks": ["<feature_id>", ...],
    "longest_critical_path": <length>,
    "clusters": <count>
  },
  "phases": [
    {
      "phase": 1,
      "feature_count": <count>,
      "priority_distribution": { "P1": <n>, "P2": <n>, "Deferrable": <n> },
      "clusters_included": ["A", "B"],
      "domains": ["Ingestion Pipeline", "Core Processing"],
      "e2e_summary": "<1-2 sentence E2E test description>",
      "depends_on_phases": []
    },
    {
      "phase": 2,
      "feature_count": <count>,
      "priority_distribution": { "P1": <n>, "P2": <n>, "Deferrable": <n> },
      "clusters_included": ["D", "E"],
      "domains": ["Search & Discovery", "Alerting"],
      "e2e_summary": "<1-2 sentence E2E test description>",
      "depends_on_phases": [1]
    }
  ],
  "created_at": "<ISO 8601 timestamp>"
}
```

#### 3.7.2 Phase Manifests

For each phase N, write `phases/phase_N_manifest.md`:

**YAML Frontmatter:**

```yaml
---
phase: <N>
initiative: "<initiative name>"
initiative_source: "<matched initiative filename>"
feature_count: <count>
clusters_included: [<cluster IDs>]
priority_distribution:
  P1: <n>
  P2: <n>
  Deferrable: <n>
e2e_summary: "<1-2 sentence E2E test description>"
depends_on_phases: [<list of earlier phase numbers>]
created_at: "<ISO 8601 timestamp>"
---
```

**Markdown Body:**

```markdown
# Phase <N> Manifest — <Initiative Name>

## Phase E2E Test

<Detailed E2E test description for this phase. What user flow is testable after this phase completes? What inputs go in, what processing happens, what outputs are visible?>

## Features by Domain

### <Domain 1>

| ID | Name | Priority | Local Deps (this phase) | Cross-Phase Deps | Cluster |
|----|------|----------|------------------------|-------------------|---------|
| IP-1 | ... | P1 | — | — | A |
| IP-2 | ... | P1 | IP-1 | — | A |

### <Domain 2>

| ID | Name | Priority | Local Deps (this phase) | Cross-Phase Deps | Cluster |
|----|------|----------|------------------------|-------------------|---------|
| SD-1 | ... | P1 | — | IP-3 (Phase 1) | D |

## Cross-Phase Dependencies

| Feature | Depends On | Phase of Dependency | Nature |
|---------|-----------|-------------------|--------|
| SD-1 | IP-3 | Phase 1 | Needs parsed metadata output |

## Natural Clusters in This Phase

| Cluster | Features | Domain | Rationale |
|---------|----------|--------|-----------|
| A | IP-1, IP-2, IP-3 | Ingestion Pipeline | Share S3 ingestion path |

## Blackbox Feature Specifications

<For each feature in this phase, extract its FULL specification from the Blackbox Requirements document VERBATIM. Include Inputs, Outputs, Behavior, Acceptance Criteria sections. Preserve any ✅ VERIFIED / ⚠️ UNVERIFIED tags exactly.>

### IP-1: <Feature Name>

<Verbatim spec from Blackbox Requirements>

### IP-2: <Feature Name>

<Verbatim spec from Blackbox Requirements>

...

## Whitebox Reference Sections (optional)

<If a Whitebox Reference Guide was provided, extract relevant sections that apply to this phase's domains and features. Filter to only include guidance relevant to the domains present in this phase. If no whitebox file was provided, omit this section entirely.>

### <Relevant Whitebox Section Title>

<Filtered whitebox content>

## Downstream Notes

<Scan all available documentation (whitebox, Initiative, blackbox) for binding architectural decisions, migration requirements, system transitions, or anti-patterns requiring work that is NOT captured as a feature in this phase. List each as an actionable note with its source reference. If none found, write "None identified for this phase.">
```

---

## Stage 4: Adversarial Self-Critique

Now switch stance: **assume the draft is wrong and find its highest-severity defects.** Review your own split as four independent critics would, against the fixed checklists below. Do NOT defend the draft — hunt for what a reviewer with no memory of your reasoning would catch. (These checklists are the value migrated from the former parallel review team; you run them against your own output.)

**Validation / Structural checklist:**
1. **Feature placement** — every feature ID from the initiative appears in exactly ONE phase's Feature Summary Table (no duplicates, no missing).
2. **DAG correctness** — every feature's dependencies (local + cross-phase) point to features in the SAME or an EARLIER phase, never a later phase (no forward edges). No circular dependencies within any phase.
3. **Phase ordering** respects dependencies; cross-phase dependencies correctly identify the source phase, and every cross-phase dependency is listed in the depending phase's Cross-Phase Dependencies table (no MISSING entries). All feature IDs in dependency lists actually exist in the initiative.
4. **Cluster integrity** — every cluster is complete within a single phase (no cluster split across phases).
5. **Phase 1 E2E-viability** — Phase 1 enables a real input→processing→persistence→output slice; if the Initiative mentions containerized deployment, Phase 1 includes the containerization feature and its E2E mentions the containerized stack (a deferral here is HIGH severity).
6. **Frontmatter consistency** — each manifest's `feature_count` matches the actual count in its Feature Summary Table; `depends_on_phases` is accurate.

**Content-Fidelity checklist:**
1. **Blackbox completeness** — every feature in every phase has its full blackbox spec (Inputs, Outputs, Behavior, Acceptance Criteria) in the Blackbox Feature Specifications section.
2. **Verbatim & ungarbled** — specs are copied VERBATIM from the source, not truncated, paraphrased, or garbled, and match the original blackbox document.
3. **Feature counts match** — the total features across all phases equals the initiative's feature count.
4. **External-dependency tags** — external identifiers (API endpoints, SDK method names, model IDs, parameter names, catalog values) retain their `✅ VERIFIED(source)` / `⚠️ UNVERIFIED` tags. An untagged external identifier is HIGH severity (verified by omission); `⚠️ UNVERIFIED` is acceptable but note it as medium so downstream resolves it. **Skip this check if no feature references any external system.**
5. **Whitebox relevance** (skip if no whitebox provided) — each phase's Whitebox Reference Sections cover all of the phase's domains, with no irrelevant noise and no important domain omitted.

**Strategic checklist:**
1. **Phase boundaries sound** — phase ordering makes architectural sense (foundations before features, data layer before UI); each phase builds meaningfully on the prior one; integration points between phases are well-defined.
2. **No phase too large/small** — phases are roughly balanced; no phase is too ambitious (too many complex features) or too thin; no phase holds ALL deferrable features; bottleneck features are not stranded in late phases; P1 features are front-loaded unless a dependency forces them later.
3. **E2E testability** — each phase's `e2e_summary` accurately describes a testable cumulative flow and references at least the P1-priority features of that phase.
4. **Risk concentration** — flag phases that concentrate many bottleneck/high-risk features.

**Skills-lens checklist:** review the split through each skill matched in Stage 2 for domain gaps and anti-patterns.

**Scope Discipline (guardrail against speculative findings):** flag boundaries that you know in advance will break *per concrete initiative requirements* (valid). Do NOT propose speculative improvements not backed by the initiative — e.g., "this might not scale if someday they need Y" (invalid).

**Narrative-vs-Structural rule:** for each finding that flags a missing structural entry (feature not in Cross-Phase Dependencies table, cluster assignment inconsistent, E2E summary missing features), check whether the concern IS described in narrative sections of the manifest. If narratively present but structurally absent: the finding is valid (fix the structural section) but is **medium**, not high — the author understood the requirement and just failed to update the table/YAML. Include the exact `structural_edits` to apply. If neither narratively nor structurally present: keep original severity.

**Severity rubric** (classify each finding honestly):

| Severity | Definition | Concrete Examples |
|----------|------------|-------------------|
| **high** | Breaks correctness or blocks downstream | Feature in 2 phases or missing; forward dependency edge; cluster split across phases; Phase 1 not E2E-viable / containerization deferred; missing blackbox spec; untagged external identifier |
| **medium** | Suboptimal but functional | Phase imbalance with no dependency reason; P1 stranded late; missing cross-phase dependency that IS narratively present; `⚠️ UNVERIFIED` external identifier; whitebox domain gap |
| **low** | Minor improvement; downstream works without change | Inconsistent naming; e2e_summary could be clearer; risk note incomplete but present; stylistic concern |

Record each finding with: `category`, `severity`, `title`, `description`, `affected_output`, `affected_section`, `recommendation`, and the exact `structural_edits` to apply. Drop anything that is genuinely a false positive on reflection.

---

## Stage 5: Revise

If the self-critique found zero high and zero medium findings, the split has converged — go to Stage 6.

Otherwise, apply the fixes. **Edit the STRUCTURAL sections directly** (Feature Summary Tables, Cross-Phase Dependencies tables, YAML frontmatter, E2E summaries, Blackbox Feature Specifications). Do NOT address structural findings by adding narrative paragraphs.

CASCADING UPDATE RULES — when applying a change, apply ALL structural consequences across ALL affected phase manifests:
- **move_feature_to_phase** → remove the feature from the source phase's Feature Summary Table AND add it to the destination phase's table; update Cross-Phase Dependencies in BOTH phases; verify cluster integrity (the cluster must not split); update the E2E summary of both phases; update both `feature_count` frontmatter values.
- **modify_dependency** → update Cross-Phase Dependencies tables in ALL phases that reference the affected features.
- **split_phase / merge_phases** → regenerate Feature Summary Tables, E2E summaries, Cross-Phase Dependencies, cluster assignments, and frontmatter for ALL affected phases; re-derive `phase_count` and `initiative_summary.json`.
- **update_e2e** → edit the E2E summary text AND verify it references the actual P1 features in that phase.
- **fix_blackbox_spec** → re-copy the affected spec VERBATIM from the source blackbox.

After applying changes, regenerate the affected manifests and `initiative_summary.json`, then run **one** more self-critique pass (Stage 4) focused on (a) verifying each finding is resolved and (b) anticipating cascade errors the edits may have introduced (e.g., a feature moved but the source phase's E2E summary not updated; a `feature_count` left stale; phase count drifted outside [2, 8]).

**Convergence bound:** at most **2** self-critique passes. After the second pass, accept the current state and converge — treat any remaining medium findings as `degraded_to_low` and record them. A two-pass bound cannot oscillate, so no oscillation/stagnation tracking is needed. Carry the convergence rationale into the feedback JSON:
- Clean: "All significant issues resolved. Zero high and zero medium findings remain."
- Bounded: "Self-critique bound (2 passes) reached. Remaining medium findings degraded to low; accepting current state."

---

## Stage 6: Output & Cleanup

### 6.1 Write Final Artifacts

If the artifacts were modified in the last revise pass, write the final `phases/initiative_summary.json` and each `phases/phase_N_manifest.md`.

### 6.2 Write Feedback JSON

Write to `$EIGEN_ROOT/eigen_initiative/phases/feedback/time_split_feedback.json` (ensure the directory exists: `mkdir -p $EIGEN_ROOT/eigen_initiative/phases/feedback/`). This records the self-critique convergence for pipeline-state compatibility. Schema (`source_reviewer: "self"`):

```json
{
  "schema_version": "1.0.0",
  "command": "time_split",
  "iteration": "<total self-critique passes>",
  "created_at": "<ISO 8601>",
  "source_outputs_analyzed": {
    "initiative_summary": "phases/initiative_summary.json",
    "phase_manifests": ["phases/phase_1_manifest.md", "..."]
  },
  "convergence": {
    "decision": "converged",
    "rationale": "<convergence rationale from Stage 5>",
    "rounds_taken": 2
  },
  "findings": [
    {
      "id": "ts-<sequential_number>",
      "category": "structural_error|balance_issue|content_gap|e2e_gap|cross_phase_dep_error|strategic_concern|external_dep_unverified",
      "severity": "high|medium|low",
      "title": "<concise>",
      "description": "<detailed>",
      "affected_output": "<file path of the output with the issue>",
      "affected_section": "<section within that file>",
      "recommendation": "<specific action that was taken>",
      "structural_edits": ["<exact edits applied>"],
      "resolution": "resolved|degraded_to_low|accepted_at_convergence",
      "source_reviewer": "self",
      "downstream_impact": {
        "affects_commands": ["bootstrap_converge", "space_split_converge"],
        "impact_description": "<what would break downstream if unresolved>"
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

The `findings` array includes ALL findings discovered across the self-critique passes — both resolved and remaining. `resolution`: `resolved` (fixed during revise), `degraded_to_low` (a medium accepted at the 2-pass bound), or `accepted_at_convergence` (a low-severity finding that did not block convergence).

### 6.3 Lesson Extraction

For each non-false-positive finding discovered during the convergence loop, create a lesson JSON in `$EIGEN_ROOT/eigen_initiative/eigen_lessons/time_split/`:

```json
{
  "id": "ts-lesson-<timestamp>-<seq>",
  "created_at": "<ISO 8601 timestamp>",
  "command": "time_split",
  "status": "pending",
  "category": "<category from the finding>",
  "severity": "<high|medium|low>",
  "title": "<concise description of the error>",
  "description": "<detailed explanation of what went wrong>",
  "root_cause": "<why the draft produced this error>",
  "recommendation": "<specific change to make in the time_split command to prevent it>",
  "affected_section": "<which stage/section of time_split.md to modify>",
  "evidence": {
    "features_involved": ["<feature IDs>"],
    "phases_involved": [1, 2],
    "reviewer_source": "self"
  },
  "initiative_context": "<initiative name, feature count>",
  "tags": ["<relevant tags>"]
}
```

**Deduplication**: before writing each lesson, check existing lessons in the directory. If a lesson with the same `affected_section` + `category` + similar `root_cause` already exists, skip it. If the existing lesson has `"status": "applied"`, still skip.

Ensure directory exists: `mkdir -p $EIGEN_ROOT/eigen_initiative/eigen_lessons/time_split/`. Write each new non-duplicate lesson to `$EIGEN_ROOT/eigen_initiative/eigen_lessons/time_split/<id>.json`.

Print summary:
```
Lessons written: <N> new lessons to $EIGEN_ROOT/eigen_initiative/eigen_lessons/time_split/
Skipped: <M> duplicates of existing lessons
```

### 6.4 Execute On Exit Commands

Execute the **On Exit** section above as one Bash block: `complete`, `mark-converged`, `add-recommendation` (optional, max 5), `commit-state`. Do NOT run these individually.

### 6.5 Print Summary

```
=== Initiative Split Complete (Converged) ===

Initiative: <name>
Total features: <N>
Phases: <N>
EIGEN_ROOT: $EIGEN_ROOT
EIGEN_BRANCH: $EIGEN_BRANCH

Phase 1: <feature_count> features — <e2e_summary>
Phase 2: <feature_count> features — <e2e_summary>
...

Convergence: CONVERGED in <R> self-critique passes — <rationale>

Findings:
  High severity:   <N> (all resolved)
  Medium severity:  <N> (all resolved or degraded)
  Low severity:     <N>

Files generated:
  $EIGEN_ROOT/eigen_initiative/phases/initiative_summary.json
  $EIGEN_ROOT/eigen_initiative/phases/phase_1_manifest.md
  $EIGEN_ROOT/eigen_initiative/phases/phase_2_manifest.md
  ...
Lessons: <N> new lessons written
Feedback: $EIGEN_ROOT/eigen_initiative/phases/feedback/time_split_feedback.json

Next steps:
  1. Run /bootstrap_converge to create the project foundation for Phase 1.
  2. Run /space_split_converge to decompose Phase 1 into parallel epics for swarm execution.
  3. (Optional) Run /compound_improve to apply accumulated lessons to the time_split command.
```

---

## Pre-Submission Checklist

Before writing the final artifacts and proceeding to On Exit, verify:

- [ ] Every feature ID from the initiative appears in exactly ONE phase's Feature Summary Table (no duplicates, no missing).
- [ ] No cluster is split across phases.
- [ ] Every cross-phase dependency points backward (earlier phase) and is listed in the depending phase's Cross-Phase Dependencies table.
- [ ] Phase 1 is E2E-viable (input→processing→persistence→output); containerization in Phase 1 if the Initiative mentions deployment.
- [ ] Each manifest's `feature_count` matches its Feature Summary Table; phase count is within [2, 8].
- [ ] Every feature has a complete VERBATIM blackbox spec; external-dependency tags preserved (not laundered).
- [ ] No code was written; no input files were modified.
- [ ] Feedback JSON written (`source_reviewer: "self"`).
- [ ] Lesson JSONs written.
- [ ] On Exit commands executed successfully.

---

## Key Rules

1. **You draft, critique, and revise in one session** — no team, no `TeamCreate`/`SendMessage`, no separate reviewer sessions. The value of the old reviewer team lives in the Stage 4 checklists, which you run against your own draft.
2. **NEVER write code; NEVER modify input files** — you produce phase manifests and the JSON summary only.
3. **Clusters are atomic** — never split a cluster across phases.
4. **Phase 1 must be E2E-viable and contain containerization** when the Initiative mentions containerized deployment.
5. **Blackbox specs are copied VERBATIM** into manifests; `⚠️ UNVERIFIED` / `✅ VERIFIED` tags are preserved, never laundered.
6. **At most 2 self-critique passes** — a bounded loop cannot oscillate; after the second pass, accept the state (remaining mediums degraded to low).
7. **Self-critique is adversarial** — assume the draft is wrong and find the highest-severity defect; do not rationalize.
8. **Skills set is discovered once** (Stage 2) and applied while drafting and critiquing.
9. **The CLI is the single source of truth for pipeline state** — all reads/writes go through `eigen-squared` CLI commands.
10. **If you receive a non-interactive shutdown reminder, it is NOT an abort signal** — complete the full draft → self-critique → revise → outputs → On Exit lifecycle before returning.

---

> **REMINDER:** A non-interactive "shut down / return now" reminder may arrive early. It is NOT an abort signal. Continue working through all stages and write all outputs before returning.
