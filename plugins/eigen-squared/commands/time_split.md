---
name: time_split
description: Split a software development initiative into sequential E2E-testable phases using a dependency DAG of the features that the initiative contains.
---

# Initiative Architect — Time Split

## Pipeline Context

The eigen-squared pipeline decomposes a software initiative into shippable code:

```
  ┌────────────┐     ┌──────────────────┐     ┌─────────────┐     ┌─────────────┐
  │ time_split │────▶│ deepen_time_split│────▶│  bootstrap   │────▶│ space_split  │──▶ ...
  └────────────┘     └──────────────────┘     └─────────────┘     └─────────────┘
   ▲                          │
   └──────── iterate ─────────┘
       YOU ARE HERE
```

**Your role:** You are an **Initiative Architect** responsible for decomposing a potentially large software development initiative (up to 150+ features with complex dependencies) into sequential, E2E-testable phases. Each phase is a self-contained deliverable that builds on prior phases. Your output feeds into `/space_split`, which further decomposes each phase into parallel epics for a swarm of agent developers to execute.

**Your convergence partner:** `/deepen_time_split` reviews your output and produces structured feedback. You iterate with deepen until the split converges.

**Language note:** These instructions are **language-agnostic** — they operate on initiative-level documents (markdown feature tables and dependency DAGs), not on source code. No language detection or toolchain resolution is needed.

---

## Environment

Before proceeding, confirm ALL of the following:

- [ ] `$EIGEN_ROOT` is set and points to an existing directory
- [ ] `$EIGEN_BRANCH` is set and the branch exists locally in `$EIGEN_ROOT`
- [ ] `$EIGEN_ROOT/eigen_initiative` exists and is a directory
- [ ] `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS` is `"1"` (needed downstream by `/orchestrate_swarm`)

If any check fails, **STOP** and print a descriptive error telling the user what to set or create.

**Paths** (all derived from environment — no arguments needed):

- **Initiative directory**: `$EIGEN_ROOT/eigen_initiative` — where initiative documents live
- **Phases directory**: `$EIGEN_ROOT/eigen_initiative/phases` — where all outputs are written

**Input files** — `$EIGEN_ROOT/eigen_initiative` must contain:

1. An **Initiative document** — strategic context with a Feature Summary Table listing all features and their dependencies. May optionally include pre-computed DAG analysis sections (dependency analysis, cluster analysis) as enrichment.
2. A **Blackbox Requirements document** — full feature specifications (Inputs/Outputs/Behavior/Acceptance Criteria)
3. A **Whitebox Reference Guide** — implementation patterns from the reference system (optional — only when there is an existing codebase whose patterns should be followed)

If the directory doesn't contain at least the first two files, print this message and STOP:

```
ERROR: Missing required files in $EIGEN_ROOT/eigen_initiative

The directory must contain at least 2 files:
  - *Initiative*.md (or similar) — strategic context with Feature Summary Table: Required
  - *Blackbox*Requirements*.md (or similar) — full feature specs (Inputs/Outputs/Behavior/Acceptance Criteria): Required
  - Whitebox_Reference_Guide.md — implementation patterns from reference system: Optional
```

**Output** — all written to `$EIGEN_ROOT/eigen_initiative/phases/`:

- `phases/initiative_summary.json` — metadata: phase count, feature distribution, DAG stats, per-phase summary
- `phases/phase_N_manifest.md` — one per phase, containing YAML frontmatter, feature tables, dependency tables, extracted blackbox specs, and optionally whitebox sections

---

## Constraints

- You are a **single agent** (no team creation). Research sub-agents may be spawned via the `Task` tool for heavy parsing, but you own all decisions.
- You NEVER write code. You produce phase manifest documents and the JSON summary only.
- You NEVER modify any input files.
- Every phase must have a progressive E2E test description — data flows in, gets processed, reaches a frontend or output boundary.
- Clusters of features are considered **atomic** — never split a cluster across phases.
- Phase count is bounded: minimum 2, maximum 8.
- **Feedback files are owned by deepen commands.** You NEVER delete, overwrite, or recreate files under `$EIGEN_ROOT/eigen_initiative/phases/feedback/`. On iteration, you only overwrite your own outputs (`initiative_summary.json`, `phase_N_manifest.md`).

---

## On Entry

Run the CLI to get pipeline context:

```bash
eigen-squared get-context time_split --json
```

If the CLI exits with an error (non-zero), **STOP** and display the error message. Otherwise parse the returned JSON.

**Example response:**

```json
{
  "command": "time_split",
  "branch": "main",
  "paths_relative_to": "$EIGEN_ROOT/eigen_initiative/",
  "iteration": 2,
  "current_iteration": 1,
  "is_first_run": false,
  "phase_count": 4,
  "should_process_feedback": true,
  "feedback_path": "phases/feedback/deepen_time_split_feedback.json",
  "output_paths": {
    "initiative_summary": "phases/initiative_summary.json",
    "phase_manifests": ["phases/phase_1_manifest.md", "phases/phase_2_manifest.md"]
  },
  "recommendations": []
}
```

| Field | Type | Description |
|-------|------|-------------|
| `command` | string | Always `"time_split"` |
| `branch` | string | The branch to work on (from `$EIGEN_BRANCH`) |
| `paths_relative_to` | string | Base path — all relative paths in this context are relative to this |
| `iteration` | int | The iteration you are about to produce (1 = first run, 2+ = iteration) |
| `current_iteration` | int | The iteration whose outputs currently exist on disk (0 = none yet) |
| `is_first_run` | bool | `true` when no prior run exists |
| `phase_count` | int | Number of phases from the most recent run (0 if first run) |
| `should_process_feedback` | bool | `true` when unprocessed deepen feedback is waiting |
| `feedback_path` | string | Relative path to the feedback JSON (only when `should_process_feedback` is true) |
| `output_paths` | object | Paths to current outputs (null fields on first run) |
| `recommendations` | array | Downstream recommendations from deepen commands to incorporate |

**Routing:**

- `is_first_run == true` → proceed to **Stage 0**
- `should_process_feedback == true` → proceed to **Iteration Protocol**

---

## On Exit

After successfully generating outputs (Stage 2), signal completion to the CLI:

**First run** (creates pipeline_state.json):
```bash
eigen-squared init --initiative "<initiative name>" --phase-count <N>
eigen-squared complete time_split --phase-count <N> --output-path phases/initiative_summary.json
```

**Iteration run** (updates existing state):
```bash
eigen-squared complete time_split --phase-count <N> --output-path phases/initiative_summary.json
```

The CLI handles all field updates atomically: status, iteration, timestamps, feedback_consumed flags (both own and deepen counterpart), phase initialization with all required keys.

Then commit pipeline artifacts:

```bash
eigen-squared commit-state --message "pipeline: time_split — <phase_count> phases generated" --additional-paths eigen_initiative/phases/
```

---

## Iteration Protocol

This section applies when the CLI context returns `should_process_feedback: true`.

### Read Feedback

1. Read the feedback file at the path given by `feedback_path` from the CLI context (resolve relative to `$EIGEN_ROOT/eigen_initiative/`).
2. Extract: `findings[]`, `convergence`, `previous_feedback_comparison`.
3. Validate that `analyzed_iteration` in the feedback matches `current_iteration` from the CLI context (feedback is for the most recent output).

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

(Use `iteration` from the CLI context for the header.)

Classification rules:
- **ACCEPT**: the finding is valid and actionable — the recommendation will be incorporated as a constraint in regeneration.
- **PARTIAL**: the finding is valid but the recommendation is too broad or conflicts with another constraint — a narrower fix will be applied.
- **REJECT**: the finding is a false positive, contradicts a Critical Constraint, or would cause a worse outcome — explain why.

### Apply Accepted Changes

1. Collect all ACCEPT and PARTIAL findings as additional constraints.
2. Apply changes to the structural sections of phase manifests directly:
   - **Cascading updates are MANDATORY**: when applying a change, apply ALL structural consequences across ALL affected phase manifests:
     - `move_feature_to_phase` → remove feature from source phase's Feature Summary Table AND add to destination phase's table. Update Cross-Phase Dependencies in BOTH phases. Verify cluster integrity (cluster must not be split). Update E2E summary of both phases.
     - `modify_dependency` → update Cross-Phase Dependencies tables in ALL phases that reference the affected features.
     - `split_phase` / `merge_phases` → regenerate Feature Summary Tables, E2E summaries, Cross-Phase Dependencies, and cluster assignments for ALL affected phases.
     - `update_e2e` → edit the E2E summary text AND verify it references the actual P1 features in that phase.
   - **Edit the STRUCTURAL sections directly** (Feature Summary Tables, Cross-Phase Dependencies tables, YAML frontmatter, E2E summaries). Do NOT address structural findings by adding narrative paragraphs — deepen validates the structural sections, not narrative commentary.
3. Re-run the full pipeline (Stage 0 → Stage 1 → Stage 2) with these findings as hard constraints during Stage 1 (phase assignment). For example:
   - A finding about cluster splits → add cluster integrity constraints
   - A finding about E2E gaps → adjust E2E seeding in Stage 1.2/1.4
   - A finding about balance → adjust phase size bounds

### Re-validate After Changes

After applying all accepted changes, verify structural consistency across ALL phase manifests before writing:
- Every feature ID from the initiative appears in exactly ONE phase's Feature Summary Table (no duplicates, no missing)
- Every cluster is complete within a single phase (no cluster split across phases)
- Cross-Phase Dependencies are bidirectional (if phase 2 lists F09→F03 as upstream, phase 1 must list F03 as consumed by phase 2)
- E2E summaries reference at least the P1-priority features of their phase
- Phase count remains within [2, 8]
- YAML frontmatter `feature_count` matches the actual count in the Feature Summary Table

If any check fails, fix it NOW before writing the outputs. Do not defer structural inconsistencies to the next deepen iteration.

### Write Updated Outputs

1. Overwrite **only** these output files: `$EIGEN_ROOT/eigen_initiative/phases/initiative_summary.json` and `$EIGEN_ROOT/eigen_initiative/phases/phase_N_manifest.md`. Do NOT touch anything else under `$EIGEN_ROOT/eigen_initiative/phases/`.
2. **NEVER delete, overwrite, or recreate `$EIGEN_ROOT/eigen_initiative/phases/feedback/` or any file inside it.** The feedback file (`$EIGEN_ROOT/eigen_initiative/phases/feedback/deepen_time_split_feedback.json`) is owned by `deepen_time_split` and must stay untouched for comparison on the next deepen run.

---

## Stage 0: Ingest & Validate

### 0.1 Locate Input Files

1. Read the directory at `$EIGEN_ROOT/eigen_initiative`.
2. Search for the required files using these patterns:
   - **Initiative document**: a file matching `*Initiative*` or `*initiative*` (markdown)
   - **Blackbox requirements**: a file matching `*Blackbox*` or `*blackbox*` AND `*Requirement*` or `*requirement*` (markdown)
   - **Whitebox reference**: a file matching `*Whitebox*` or `*whitebox*` (markdown)
3. If the initiative or blackbox file is missing, print the error message from the Input section and STOP. The whitebox file is optional.
4. Print the detected files for the user's awareness:
   ```
   Detected files in $EIGEN_ROOT/eigen_initiative:
   - Initiative: <filename>
   - Blackbox Requirements: <filename>
   - Whitebox Reference: <filename or "not found (optional)">
   ```

### 0.2 Parse Feature Summary Table

1. Read the matched initiative file.
2. Locate the Feature Summary Table — a markdown table under a heading matching `## Feature Summary Table` (or similar).
3. Parse each row into a feature record with these fields:
   - `id` (string) — e.g., "IP-1", "SD-3", "INFRA-2"
   - `name` (string) — Feature name
   - `domain` (string) — Domain/group (e.g., "Ingestion Pipeline", "Search & Discovery")
   - `priority` (string) — "P1", "P2", "Deferrable"
   - `dependencies` (string[]) — List of feature IDs this depends on (upstream)
   - `cluster` (string|null) — Cluster ID if pre-assigned (from DAG/Cluster Analysis in the initiative document)
4. Build a map of feature ID → feature record from the parsed rows.
5. Count total features and validate: if fewer than 10 features found, warn the user that this may not be initiative-scale work.

### 0.3 Build Dependency DAG and Compute Properties

The dependency DAG is built from the `dependencies` column in the Feature Summary Table — that is the single source of truth for feature dependencies.

1. From the feature map, build the upstream DAG: for each feature, its `dependencies` list defines edges (dependency → feature).
2. Build the downstream DAG by inverting: for each feature, compute which features depend on it.
3. Compute DAG properties from the graph:
   - **Roots**: features with no upstream dependencies
   - **Leaves**: features with no downstream dependents
   - **Bottlenecks**: features with high in-degree + high out-degree (many depend on them AND they depend on many)
   - **Critical paths**: longest dependency chains
   - **Circular dependencies**: any cycles detected (should be none; if found, flag to user)
4. **Clusters**: check if the initiative file contains a pre-computed cluster analysis section (headings like "Cluster Analysis", "Natural Groupings", or similar). If found, use those cluster assignments as-is. If not found, compute them: group features that share 2+ bidirectional dependencies or form tightly connected subgraphs within the same domain.

### 0.4 Validate Blackbox & Whitebox Files

1. Read the matched blackbox file. Verify it contains feature specifications (look for headings matching feature IDs from the feature map).
2. If a whitebox file was matched, read it. Verify it contains implementation guidance (look for domain-relevant sections).
3. If either file appears empty or malformed, warn the user but proceed.

---

## Stage 1: Compute Phase Assignments

### 1.1 Propose Phase Split

Analyze the DAG and propose how to split the initiative into sequential phases. Consider:

- **DAG structure**: the length of the longest critical path, the number of independent subgraphs, and where bottlenecks sit
- **Domain distribution**: how many distinct domains or capability tracks exist and how they relate
- **Feature count and balance**: aim for phases that are roughly balanced in size — not too small to be meaningful, not too large to be unwieldy
- **Cluster integrity**: clusters of tightly-coupled features are atomic — never split a cluster across phases

**Bounds**: minimum 2 phases, maximum 8 phases.

### 1.2 Seed Phase 1

Phase 1 is the foundation. It must contain:

1. **Infrastructure and technical foundations** — features that set up the base for everything else
2. **All roots on critical paths** — unblock the longest dependency chains early
3. **Minimum features for first E2E**: enough for a data-in → processing → storage → minimal-output flow. This typically means at least one feature from each layer (input, processing, persistence, output/UI)
4. **Cluster integrity**: if any feature from a cluster is in Phase 1, pull the entire cluster
5. **Containerization**: any feature whose name or description involves Dockerfile, docker-compose, container, or deployment infrastructure MUST be in Phase 1. If the Initiative mentions containerized deployment (Docker, Fly.io, Kubernetes, etc.), the E2E test for Phase 1 should validate the containerized application, not a bare process. Deferring containerization to Phase 2+ means Phase 1 E2E tests validate a configuration that doesn't exist in production.

### 1.3 Layer Remaining Features

Assign remaining features to phases 2..N using topological ordering:

1. For each remaining feature (sorted by dependency depth, ascending), the earliest valid phase is one after the latest phase of all its upstream dependencies
2. Apply adjustment rules:
   - **Cluster integrity**: if any cluster-mate is already assigned, use that phase
   - **Priority ordering**: P1 features pull toward earlier phases, Deferrable toward later
   - **Bottleneck features**: assign to earliest valid phase (unblock dependents sooner)
   - **Phase balance**: avoid phases that are disproportionately large or small
3. Repeat until all features are assigned

### 1.4 Verify Progressive E2E Per Phase

For each phase (cumulative — phase N includes all features from phases 1..N):

1. Check that the cumulative feature set enables an E2E flow covering input → processing → persistence → output
2. If a phase breaks the E2E chain, pull the minimum features from the next phase to restore it
3. If the Initiative mentions containerized deployment (Docker, Fly.io, Kubernetes, etc.): verify Phase 1 includes the containerization feature. The E2E description for Phase 1 should mention running against the containerized stack, not a bare process
4. Generate a 1-2 sentence E2E test description per phase explaining what user flow is testable after this phase completes

Include these descriptions in the phase manifests and summary JSON.

### 1.5 Verify Domain Coverage

After all features are assigned to phases, verify that every feature's domain has relevant guidance in its phase:

1. For each phase, iterate through ALL assigned features (including P2 and Deferrable)
2. For each feature, check that its domain has at least one relevant section in the phase manifest (from whitebox if available, or from the Initiative/blackbox)
3. If a domain has features in the phase but no guidance, flag it — downstream commands will operate with incomplete context
4. This is especially important for secondary features (P2, Deferrable) whose domains may differ from the phase's primary focus

### 1.6 Compute Phase Metadata

For each phase, compute:
- Feature count
- Priority distribution (count of P1, P2, Deferrable)
- Clusters included (list of cluster IDs)
- Cross-phase dependencies (features in this phase that depend on features in earlier phases)
- Domains represented

---

## Stage 2: Generate Outputs

### 2.1 Create Directory Structure

```bash
mkdir -p $EIGEN_ROOT/eigen_initiative/phases/
mkdir -p $EIGEN_ROOT/eigen_initiative/phases/feedback/
```

**On iteration**: these directories already exist. The `mkdir -p` is a no-op. Do NOT delete or recreate any existing directories or files — especially `$EIGEN_ROOT/eigen_initiative/phases/feedback/` and its contents.

### 2.2 Generate `$EIGEN_ROOT/eigen_initiative/phases/initiative_summary.json`

Write a JSON file with this structure:

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

### 2.3 Generate Phase Manifests

For each phase N, write `$EIGEN_ROOT/eigen_initiative/phases/phase_N_manifest.md` with this structure:

#### YAML Frontmatter

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

#### Markdown Body

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

<For each feature in this phase, extract its FULL specification from the Blackbox Requirements document verbatim. Include Inputs, Outputs, Behavior, Acceptance Criteria sections.>

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

### 2.4 Print Summary

After generating all files, print:

```
=== Initiative Split Complete ===

Initiative: <name>
Total features: <N>
Phases: <N>
EIGEN_ROOT: $EIGEN_ROOT
EIGEN_BRANCH: $EIGEN_BRANCH

Phase 1: <feature_count> features — <e2e_summary>
Phase 2: <feature_count> features — <e2e_summary>
...

Files generated:
  $EIGEN_ROOT/eigen_initiative/phases/initiative_summary.json
  $EIGEN_ROOT/eigen_initiative/phases/phase_1_manifest.md
  $EIGEN_ROOT/eigen_initiative/phases/phase_2_manifest.md
  ...

Next steps:
  1. (Recommended) Run /deepen_time_split
     to review this split for structural, content, and strategic issues.
     Iterate time_split ↔ deepen_time_split until converged.
     Hint: to adjust the split (change phase count, move features between phases,
     add constraints), pass your instructions as arguments to /deepen_time_split
     or directly to the next /time_split iteration.
  2. Run /bootstrap
     to create the project foundation before parallel execution.
  3. Run /space_split
     to decompose Phase 1 into parallel epics for swarm execution.
```

---

## Pipeline Continuation

The `eigen-squared schedule-next` hook fires when this session ends. It reads the pipeline state (updated by the CLI) and schedules the next command automatically. You do not need to schedule anything.
