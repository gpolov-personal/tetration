---
name: deepen_bootstrap
description: Review bootstrap output with parallel research agents, diagnose errors, and write lessons to the initiative
---

# Deepen Bootstrap — Foundation Architecture Review

## Pipeline Context

```
bootstrap ──► deepen_bootstrap ──► bootstrap (if CONTINUE) ──► ... ──► deepen_bootstrap (CONVERGED) ──► space_split
                  │                                                          │
                  └── writes feedback + lessons ◄───────────────────────────┘
```

**Role:** Review agent for the `bootstrap` command. Takes bootstrap's committed foundation files and `bootstrap-report.json`, subjects them to comprehensive validation by parallel research and review agents. Every structural, architectural, tooling, contract quality, and incremental readiness issue is diagnosed.

Bootstrap creates the universal foundation: directories, entity stubs, contracts, package manifests, quality config, basic CI, and optionally Docker artifacts (Dockerfile, docker-compose.yml, .dockerignore — see `bootstrap-report.json` field `delta_applied.dockerfile_created`). It does NOT create database migrations or E2E test infrastructure — those are handled by feature epics and the E2E Testing epic.

**Convergence authority:** This command decides when bootstrap's output is good enough to proceed. It writes the `converged` flag and the rationale.

**Lesson writing:** Diagnosed errors are written as structured lesson JSONs to the `lessons_dir` path. These lessons are later consumed by `/compound_improve` to permanently improve the `bootstrap` command itself.

---

## Environment

Before starting, confirm:

- [ ] `EIGEN_ROOT` is set and points to an existing directory
- [ ] `EIGEN_BRANCH` is set (the default branch)
- [ ] The `eigen-squared` CLI is available on `PATH`

---

## On Entry

```bash
eigen-squared get-context deepen_bootstrap --json
```

If the CLI exits with an error (non-zero), **STOP** and display the error message. Otherwise parse the returned JSON:

```json
{
  "command": "deepen_bootstrap",
  "branch": "main",
  "paths_relative_to": "$EIGEN_ROOT/eigen_initiative/",
  "phase": 1,
  "iteration": 2,
  "main_command_iteration": 3,
  "main_command_outputs": {
    "bootstrap_report": "phases/phase_1/bootstrap-report.json",
    "target_repo": "/home/user/projects/my-app",
    "phase_manifest": "phases/phase_1_manifest.md"
  },
  "lessons_dir": "eigen_lessons/bootstrap/",
  "recommendations": [],
  "previous_feedback_path": "phases/phase_1/feedback/deepen_bootstrap_feedback.json",
  "previous_feedback_exists": true,
  "overwrite_warning": "Existing feedback has not been consumed by bootstrap yet."
}
```

| Field | Use |
|---|---|
| `phase` | The target phase number N for this run |
| `iteration` | Current deepen_bootstrap iteration (for convergence limit checks) |
| `main_command_iteration` | Bootstrap iteration that was analyzed (written into feedback JSON) |
| `main_command_outputs.bootstrap_report` | Relative path to bootstrap-report.json (resolve against `paths_relative_to`) |
| `main_command_outputs.target_repo` | Absolute path to the target repository to scan |
| `main_command_outputs.phase_manifest` | Relative path to the phase manifest (resolve against `paths_relative_to`) |
| `lessons_dir` | Relative path to the lessons directory (resolve against `paths_relative_to`) |
| `recommendations` | Upstream recommendations for bootstrap — use as awareness context |
| `previous_feedback_path` | Relative path to previous feedback file (resolve against `paths_relative_to`) |
| `previous_feedback_exists` | Whether previous feedback exists for iteration comparison |
| `overwrite_warning` | If set, display this warning to the user and proceed |

If `overwrite_warning` is present, print the warning and continue.

---

## On Exit

After completing the review and writing the feedback file:

```bash
eigen-squared complete deepen_bootstrap --phase <phase> --feedback-path <path> --findings-summary '{"high": <N>, "medium": <N>, "low": <N>}'
```

If converging:

```bash
eigen-squared mark-converged bootstrap --phase <phase> --reason "..."
```

If adding downstream recommendations at convergence:

```bash
eigen-squared add-recommendation --from-cmd deepen_bootstrap --target <target> --iteration <main_command_iteration> --text "..."
```

Commit all artifacts:

```bash
eigen-squared commit-state --message "pipeline: deepen_bootstrap phase <phase> — iteration <N>, <CONVERGED|CONTINUE>" --additional-paths eigen_initiative/phases/phase_<phase>/feedback/,eigen_initiative/eigen_lessons/bootstrap/
```

The `eigen-squared schedule-next` hook fires when this session ends. It reads the pipeline state (updated by the CLI) and schedules the next command automatically. You do not need to schedule anything.

---

## Iteration Protocol

### Detect Iteration Context

1. Check if `previous_feedback_exists` is true in the CLI context (previous feedback).
2. If it exists, read the file at `previous_feedback_path` (resolved against `paths_relative_to`) for comparison, oscillation detection, and progress tracking.
3. If no previous feedback exists, this is the first deepen iteration.

### Convergence Decision Protocol

After collecting all findings, apply these convergence rules **in order**:

1. **Converge if**: zero high-severity findings AND zero medium-severity findings remain AND verification passes.
   - Rationale: "All significant issues resolved, verification passes."

2. **Converge if**: iteration limit reached (`iteration >= 8` from CLI context).
   - Rationale: "Maximum iteration limit (8) reached. Accepting current state."

3. **Converge if**: oscillation detected AND no non-oscillating high-severity or medium-severity findings remain.
   - Rationale: "Oscillation detected. Accepting current state to break the cycle."

4. **Continue if**: any high-severity or medium-severity actionable findings remain that have not oscillated.

### Code Change Guidance Generation

For each finding that is actionable by bootstrap, produce explicit surgical instructions in the feedback file's `code_change_guidance` section:

- For entity issues → `entities_to_add` or `entities_to_modify` entries with specific fields
- For missing files → entries in `entities_to_add` with path and rationale
- For unnecessary files → entries in `files_to_delete`
- For config issues → entries in `config_changes` with specific settings

---

## Stage 0: Ingest

### 0.1 Read Phase Manifest

1. Read the phase manifest at `main_command_outputs.phase_manifest` (resolved against `paths_relative_to`).
2. Parse YAML frontmatter: `phase`, `initiative`, `feature_count`, `clusters_included`, `priority_distribution`, `e2e_summary`, `depends_on_phases`.
3. Parse markdown body:
   - **Features by Domain**: feature tables — build a map of feature id → {name, priority, local_deps, cross_phase_deps, cluster, domain}
   - **Cross-Phase Dependencies**: features depending on prior phases
   - **Natural Clusters**: cluster → features mapping
   - **Blackbox Feature Specifications**: per-feature specs (feature_id → full spec text)
   - **Whitebox Reference Sections**: filtered whitebox content (may be absent if no whitebox file was provided)

### 0.2 Read Bootstrap Report

1. Read the bootstrap report at `main_command_outputs.bootstrap_report` (resolved against `paths_relative_to`).
2. If the report file doesn't exist → **STOP.** Print:
   ```
   ERROR: No bootstrap-report.json found at the expected path.
   Bootstrap must have completed before running deepen_bootstrap.
   ```
3. Extract: `delta_applied`, `entities_created`, `contracts_created`, `verification`, `tooling_decisions`, `commits`, `repo_state_before`, `languages`.

### 0.3 Scan Target Repo

Scan `main_command_outputs.target_repo` to build a ground-truth picture of what actually exists:

1. **Directory structure**: recursive listing to depth 4
2. **Entity/model files**: language-specific scan for class/interface/struct definitions
3. **Contract files**: OpenAPI YAML/JSON, message schema files
4. **Config files**: linting, formatting, type checking, test runner, CI workflows
5. **Package manifest**: pyproject.toml, package.json, go.mod, etc.
6. **Test directories**: test directories, conftest/setup files

Compare against the bootstrap report's `delta_applied` to identify discrepancies (report claims X was created, but it doesn't exist — or vice versa).

### 0.4 Load Existing Lessons

1. Glob `lessons_dir` (resolved against `paths_relative_to`) for `*.json`.
2. Read and parse each lesson JSON — used to avoid duplicating known issues in the lesson extraction phase.

### 0.5 Read Upstream Recommendations (Awareness)

Read the `recommendations` array from the CLI context.

Use these as additional context when reviewing bootstrap's output:
- They inform your analysis but do NOT constitute findings on their own.
- Do NOT create findings solely because a recommendation was not addressed.
- You MAY reference a recommendation in a finding's rationale if you independently identify a related issue.

### 0.6 Load Previous Feedback (if exists)

If `previous_feedback_exists` is true in the CLI context, read the feedback file at `previous_feedback_path` (resolved against `paths_relative_to`). This is used for:
- Iteration comparison and progress tracking
- Oscillation detection (findings that flip between present/absent across iterations)
- Identifying which previous findings have been addressed by bootstrap

---

## Stage 1: Foundation Integrity Validation

Spawn **all validation agents in parallel:**

### 1.1 Entity Completeness Agent

```
Prompt: "Validate entity stub completeness for this bootstrap foundation.

For every entity referenced by 2+ features spanning 2+ domains in the phase manifest:
1. Does a stub file exist in $EIGEN_ROOT?
2. Does it have the right fields (compare against blackbox specs)?
3. Are field types reasonable for the domain?
4. Are there entities that SHOULD have been created but weren't?
5. Are there entities that were created but aren't referenced by 2+ cross-domain features?

Phase manifest features:
<features by domain>

Blackbox specs:
<blackbox specs>

Entities bootstrap claims to have created:
<bootstrap_report entities_created>

Actual entity files found in repo:
<entity files from repo scan>

Report every issue: {entity_name, issue_type, details}"
```

### 1.2 Directory Structure Agent

```
Prompt: "Validate directory structure for this bootstrap foundation.

For every domain in the phase manifest's features:
1. Does a corresponding directory exist in $EIGEN_ROOT?
2. Is the naming convention consistent with the detected language profile?
3. Are test directories properly structured per the language profile?
4. Are there orphan directories (exist but no features reference them)?

Domains in phase manifest:
<list of unique domains>

Actual directory structure:
<directory listing from repo scan>

Languages: <detected languages from bootstrap report>

Report every issue: {domain, issue_type, details}"
```

### 1.3 Contract Alignment Agent

```
Prompt: "Validate API and message contracts for this bootstrap foundation.

For every feature's blackbox spec:
1. If it describes REST/HTTP endpoints — does an interface definition or OpenAPI stub exist?
2. Do API schemas reference the correct entity fields?
3. If it describes async/event communication — does a message contract exist?
4. Do message schemas match the entity fields?
5. Are there contracts that don't correspond to any feature?

Blackbox specs:
<blackbox specs>

Contracts created (from report):
<bootstrap_report contracts_created>

Actual contract files:
<contract files from repo scan>

Report every issue: {contract_name, issue_type, details}"
```

### 1.4 Configuration Consistency Agent

```
Prompt: "Validate configuration files for this bootstrap foundation.

Check:
1. Linting config matches tooling_decisions (e.g., if ruff was chosen, is ruff configured?)
2. Type checker config present and correct for chosen tool
3. Test runner config present and correct
4. CI workflow runs lint + type-check + tests (non-E2E) and references the correct commands
5. .editorconfig present with reasonable defaults

Tooling decisions:
<bootstrap_report tooling_decisions>

Actual config files found:
<config files from repo scan>

Report every issue: {config_file, issue_type, details}"
```

---

## Stage 2: Cross-Reference Validation

Spawn **all agents in parallel:**

### 2.1 Entity Fidelity Agent

```
Prompt: "Compare each entity stub's fields against the most authoritative schema source available.

Schema source priority:
- If actual schema/migration files exist in $EIGEN_ROOT (e.g., SQL migrations, ORM model files, schema.prisma): use these as primary source
- If a whitebox reference guide exists with a database schema section: use it as primary source
- Otherwise: use blackbox specs

For each entity stub in $EIGEN_ROOT:
1. Read the stub file and extract field names and types
2. Read the primary schema source (per priority above) for this entity
3. Also read ALL blackbox specs that reference this entity (for cross-reference)
4. Flag: fields in schema source but missing from stub
5. Flag: fields in stub not in schema source or any blackbox spec
6. Flag: type mismatches between stub and schema source
7. Flag: enum/constraint values that don't match schema source

Entity stubs:
<entity files with contents from repo scan>

Schema sources (if found):
<migration files, model files, or whitebox schema section>

Blackbox specs:
<blackbox specs>

Report every mismatch: {entity_name, field_name, issue_type, expected, actual, source}"
```

### 2.2 Package Manifest Agent

```
Prompt: "Validate the package manifest has all required dependencies.

Check:
1. Does the manifest include the chosen framework?
2. Does it include the test runner and testing libraries?
3. Does it include the linter and type checker?
4. Are there unnecessary dependencies (not needed by any phase feature)?
5. Are versions pinned or using reasonable ranges?

Tooling decisions:
<bootstrap_report tooling_decisions>

Actual package manifest:
<package manifest content from repo>

Report every issue: {dependency, issue_type, details}"
```

### 2.3 Verification Replay Agent

```
Prompt: "Re-run the bootstrap verification commands and check results.

Bootstrap used these verification commands:
<bootstrap_report verification commands_used>

1. Run the exact same commands in $EIGEN_ROOT
2. Check: do they still pass?
3. If there are new warnings compared to bootstrap's run, flag them
4. If they fail, identify what changed since bootstrap
5. If bootstrap_report.delta_applied.server_project_detected is true:
   - Verify Dockerfile exists and `docker compose config` validates without errors
   - Verify docker-compose.yml lists the expected services (compare against bootstrap_report.delta_applied.docker_compose_services)
   - If docker is available: verify `docker compose build` succeeds

Report: {status, new_warnings, regressions, docker_status (if applicable)}"
```

---

## Stage 3: Strategic Review

Spawn **review agents in parallel:**

### 3.1 Architecture Strategist Review

Spawn as `Task eigen:architecture-strategist`:

```
Prompt: "Review this project foundation from an architectural perspective.

Check:
1. Is the directory layout sound for the initiative's scale and domains?
2. Are entity boundaries clean (no god-entities covering too many concerns)?
3. Does the foundation support the phase's E2E summary testability?
4. Are there architectural decisions implicit in the bootstrap that may cause problems for later phases?

Bootstrap report:
<bootstrap_report>

Phase manifest summary:
<phase metadata with feature count, domains, e2e_summary>

Repo structure:
<directory listing>"
```

### 3.2 Code Simplicity Review

Spawn as `Task eigen:code-simplicity-reviewer`:

```
Prompt: "Review this bootstrap foundation for unnecessary complexity.

Check:
1. Are any entity stubs over-engineered (too many abstract base classes, unnecessary inheritance)?
2. Is the config overly complex for the project's current needs?
3. Is the CI pipeline doing more than lint + type-check + test?
4. Could the directory structure be simpler while still supporting the phase's features?

Bootstrap report:
<bootstrap_report>

Entity stubs:
<entity file contents>

Config files:
<config file contents>"
```

### 3.3 Security Review

Spawn as `Task eigen:security-sentinel`:

```
Prompt: "Review this bootstrap foundation for security concerns.

Check:
1. Are entity stubs exposing sensitive fields (passwords, tokens, PII) without protection patterns?
2. Does the CI workflow have security-relevant gaps (no secret scanning, no dependency audit)?
3. Are .env files committed or properly git-ignored?
4. Are there hardcoded credentials or API keys?

Relevant files from $EIGEN_ROOT:
<relevant file contents>

Report every concern: {file, concern_type, details, recommendation}"
```

---

## Stage 4: Incremental Readiness

Spawn agents in parallel:

### 4.1 Phase N+1 Preview Agent

```
Prompt: "Preview what the next phase's bootstrap would need to add.

If a Phase N+1 manifest exists (check $EIGEN_ROOT/eigen_initiative/phases/phase_<N+1>_manifest.md):
1. What new domains will enter in Phase N+1?
2. What new entities will be needed?
3. Does the current foundation's directory structure accommodate extension?
4. Are there naming conventions or patterns that would make Phase N+1 bootstrap difficult?

If no Phase N+1 manifest exists, check if the current foundation has any anti-patterns
that would make incremental extension difficult (e.g., hardcoded paths, non-modular structure).

Current phase: <N>
Current foundation structure:
<directory listing>

Phase N+1 manifest (if available):
<content or 'not available'>

Report: extensibility issues, recommended adjustments"
```

### 4.2 Cross-Artifact Consistency Agent

```
Prompt: "Check cross-references between all bootstrap artifacts.

Verify:
1. All entity names in API contracts resolve to existing entity stub files
2. All entity names in message contracts resolve to existing entity stubs
3. All package index files (__init__.py / index.ts) export the correct symbols (skip for Go/.NET)
4. No orphan files (created but not referenced by any contract or config)
5. No dangling references (contract references an entity that doesn't exist)

Entity stubs, contracts, package index files from $EIGEN_ROOT:
<relevant file contents>

Report every broken reference: {source_file, reference, target, issue_type}"
```

---

## Stage 5: Skills Application

### 5.1 Discover and Apply Available Skills

1. Discover ALL available skills from all sources (project, user, all plugins).
2. Match skills to the bootstrap's domains and technologies (e.g., python-testing-patterns for Python projects, react-best-practices for React frontends).
3. Spawn one sub-agent per matched skill to review the foundation through that skill's lens.
4. Spawn all in parallel.

---

## Stage 6: Synthesize & Enhance

### 6.1 Collect All Agent Results

Wait for ALL parallel agents to complete. Collect findings from:
- Foundation integrity agents (Stage 1)
- Cross-reference validation agents (Stage 2)
- Strategic review agents (Stage 3)
- Incremental readiness agents (Stage 4)
- Skills agents (Stage 5)

### 6.2 Categorize Findings

For each finding, assign:

- **`category`**: one of:
  - `entity_error` — wrong fields, missing entity, unnecessary entity, type mismatch
  - `structure_error` — wrong directory layout, missing domain dir, naming convention violation
  - `contract_error` — missing API contract, wrong endpoint, schema mismatch, orphan contract
  - `config_error` — wrong tool version, missing config, inconsistent with tooling_decisions
  - `verification_failure` — code doesn't compile/lint after bootstrap
  - `incremental_error` — foundation doesn't support next phase extension
  - `language_adaptation_error` — wrong language conventions, incorrect profile application
  - `false_positive` — flagged but correct upon analysis

- **`severity`**: `high` (blocks epics), `medium` (suboptimal but functional), `low` (minor improvement)

- **`affected_phase`**: which section of the `bootstrap.md` command caused this (e.g., "Phase 2.1 — Derive Required Artifacts", "Phase 3 — Contract Generator")

### 6.3 Deduplicate & Prioritize

- Merge similar findings from multiple agents.
- Flag conflicting advice for user review.
- Group by affected command phase.
- Filter out `false_positive` findings.

### 6.4 Write Iteration Feedback File

Write the feedback to the feedback path for phase N: `$EIGEN_ROOT/eigen_initiative/phases/phase_N/feedback/deepen_bootstrap_feedback.json`. **Do NOT modify bootstrap-report.json** — feedback is always a separate file.

Ensure directory exists: `mkdir -p $EIGEN_ROOT/eigen_initiative/phases/phase_N/feedback/`

```json
{
  "schema_version": "1.0.0",
  "command": "deepen_bootstrap",
  "iteration": "<current deepen_bootstrap iteration>",
  "analyzed_iteration": "<main_command_iteration from CLI context>",
  "created_at": "<ISO 8601>",
  "source_outputs_analyzed": {
    "bootstrap_report": "phases/phase_N/bootstrap-report.json",
    "target_repo": "$EIGEN_ROOT"
  },
  "convergence": {
    "decision": "continue|converged",
    "rationale": "<why, referencing verification status and downstream impact>",
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
      "id": "dbf-<sequential_number>",
      "category": "<entity_error|structure_error|contract_error|config_error|verification_failure|incremental_error|language_adaptation_error>",
      "severity": "high|medium|low",
      "title": "<concise>",
      "description": "<detailed>",
      "affected_output": "<file path>",
      "affected_section": "<section within file>",
      "recommendation": "<specific action for bootstrap to take>",
      "actionable_by": "bootstrap",
      "downstream_impact": {
        "affects_commands": ["space_split"],
        "impact_description": "<what breaks downstream>"
      }
    }
  ],
  "code_change_guidance": {
    "description": "Surgical instructions for bootstrap's next iteration",
    "entities_to_add": [
      {
        "name": "<EntityName>",
        "path": "<file path>",
        "fields": ["<field1>", "<field2>"],
        "reason": "<why this entity is needed, referencing finding ID>"
      }
    ],
    "entities_to_modify": [
      {
        "name": "<EntityName>",
        "path": "<existing file path>",
        "add_fields": ["<field>"],
        "remove_fields": ["<field>"],
        "rename_fields": { "<old>": "<new>" },
        "reason": "<why, referencing finding ID>"
      }
    ],
    "files_to_delete": [
      {
        "path": "<file path>",
        "reason": "<why, referencing finding ID>"
      }
    ],
    "config_changes": [
      {
        "file": "<config file path>",
        "change": "<description of change>",
        "reason": "<why, referencing finding ID>"
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

Apply the Convergence Decision Protocol (from the Iteration Protocol section above) to set `convergence.decision`.

### 6.5 Generate Convergence Recommendations (CONVERGED ONLY)

**Skip this section entirely if convergence decision is NOT "converged".**

At convergence, scan low-severity findings for cross-stage insights worth preserving for downstream commands.

1. **Filter findings with downstream impact:** Only low-severity findings where `downstream_impact.affects_commands` is non-empty.
2. **For each affected downstream command** (space_split, plan_phase_epic, create_issues_from_plan_swarm), draft a 1-2 sentence observation:
   - Describe the **observed condition** in bootstrap's output.
   - State the **implication** for the downstream command.
3. **Write recommendations via CLI** — for each observation:
   ```bash
   eigen-squared add-recommendation --from-cmd deepen_bootstrap --target <target_command> --iteration <main_command_iteration> --text "<observation>"
   ```
   - Max 5 calls per target command.
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
  "id": "bs-lesson-<timestamp>-<sequential>",
  "created_at": "<ISO 8601 timestamp>",
  "command": "bootstrap",
  "status": "pending",
  "category": "<category from 6.2>",
  "severity": "<high|medium|low>",
  "title": "<concise description of the error>",
  "description": "<detailed explanation of what went wrong>",
  "root_cause": "<why the bootstrap command produced this error>",
  "recommendation": "<specific change to make in bootstrap.md>",
  "affected_phase": "<which phase/section of bootstrap.md to modify>",
  "evidence": {
    "entities_involved": ["<entity names>"],
    "files_involved": ["<file paths>"],
    "agent_source": "<which review agent found this>"
  },
  "bootstrap_context": "<phase number, languages, repo state>",
  "tags": ["<relevant tags>"]
}
```

### 7.2 Deduplicate Against Existing Lessons

For each new lesson, check the existing lessons loaded in Stage 0.4:
- If a lesson with the same `affected_phase` + `category` + similar `root_cause` already exists, **skip it**.
- If the existing lesson has `"status": "applied"`, still skip.

### 7.3 Write Lesson Files

1. Ensure directory exists: `mkdir -p` the `lessons_dir` path (resolved against `paths_relative_to`).
2. For each new non-duplicate lesson, write to: `<lessons_dir>/<id>.json`
3. Print summary:
   ```
   Lessons written: <N> new lessons to <lessons_dir>
   Skipped: <M> duplicates of existing lessons
   ```

---

## Stage 8: Summary & Next Steps

Print a comprehensive summary:

```
=== Bootstrap Review Complete ===

Phase: <N>
Target repo: $EIGEN_ROOT
Languages: <detected languages with roles>
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
Feedback written to: $EIGEN_ROOT/eigen_initiative/phases/phase_N/feedback/deepen_bootstrap_feedback.json
Lessons: <N> new lessons written to <lessons_dir>

Next steps:
  If CONTINUE:
    Run /bootstrap to address the feedback.
    Hint: to change tooling decisions or adjust the foundation,
    pass your instructions to the next /bootstrap iteration.
  If CONVERGED:
    Run /space_split to decompose Phase <N> into parallel epics.
    Run /compound_improve to apply accumulated lessons to the bootstrap command.
```
