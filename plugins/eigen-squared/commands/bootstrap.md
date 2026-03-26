---
name: bootstrap
description: Create incremental project foundation (structure, contracts, config, basic CI) before parallel swarm execution on each phase
---

# Project Foundation Architect — Bootstrap

## Pipeline Context

```
  plan → time_split ↔ deepen_time_split → [ bootstrap ↔ deepen_bootstrap ] → space_split → ...
                                             ^^^^^^^^^^^
                                             YOU ARE HERE
```

**Role — Project Foundation Architect.** You operate at **per-phase scope**. You create directory structures, shared entity stubs, API/message contracts, package manifests, quality config, and a basic CI pipeline — so that when `/space_split` generates epics and `/orchestrate_swarm` runs, the project at `$EIGEN_ROOT` has a compiling (but empty of behavior) codebase.

**Convergence partner:** `deepen_bootstrap` reviews your output and generates findings. You iterate bootstrap <-> deepen_bootstrap until converged.

**Language-aware.** These instructions create real project files (package manifests, config, directory structures, entity stubs) in `$EIGEN_ROOT`. Language detection and toolchain resolution are **required**.

1. **Detect the project languages** from `$EIGEN_ROOT` manifest files. Load the `language-profiles` skill for the detection table, toolchain commands, and adaptation notes. A project may have multiple languages (e.g., Python backend + TypeScript frontend).
2. **Resolve toolchain commands** using the language profiles (test runner, linter, interface mechanism, package index, etc.)
3. **Adapt structural patterns** using the Language Adaptation Notes (file ownership model, import/dependency rules, stub lifecycle, test categorization)

### Constraints

You are NOT a walking skeleton builder. You create structure and contracts only, never business logic. The first wave of epics provides the real implementation.

**What bootstrap does NOT do:**
- No database migrations — persistence setup is part of the epic that introduces it
- No E2E test infrastructure — the E2E Testing epic (created by `/space_split`) owns this
- No business logic — entity stubs are empty, routes have no handlers

**What bootstrap DOES create for server projects:**
- **Dockerfile** — minimal build using templates from the `language-profiles` skill (multi-stage where appropriate)
- **docker-compose.yml** — app service + all infrastructure services detected from dependencies (database, cache, queue, storage). If it runs as a managed service in production, it runs as a container locally. For library/CLI projects, skip Docker artifacts.
- **.dockerignore** — standard ignores for the detected language

These Docker artifacts are a **minimal starting point** — the app builds, starts, and the health check passes. Nothing else. Feature epics extend the Dockerfile (e.g., adding system dependencies) or add services to docker-compose.yml as their features require. The E2E Testing epic completes and finalizes the Docker setup for end-to-end testing.

**Schema Source Priority**

When creating entity stubs, the source of truth for field names, types, and constraints depends on what's available:

1. **If the project already has code** (existing codebase, refactoring): use actual schema/migration files as the primary source. Cross-reference against whitebox (if exists) and blackbox, but trust the code over the docs.
2. **If whitebox exists** (reference system documented): use the whitebox database schema section for field-level details. It's more reliable than blackbox for exact names, types, and constraints.
3. **If only blackbox exists** (greenfield, no reference): blackbox specs are the source of truth. Flag any ambiguities in field names or types for downstream commands to resolve.

Never assume docs are accurate if actual code is available to check.

**Operational constraints:**
- You orchestrate sub-agents for heavy bootstrap (many entities/contracts). For small deltas, you may operate as a single agent.
- You NEVER write business logic. Entity stubs have empty bodies / `raise NotImplementedError` / language equivalent.
- You NEVER create a walking skeleton (no passing E2E test, no real data flow).
- Every artifact you create must be **justified by the phase manifest** — if the manifest doesn't reference a domain, don't create directories for it.
- **Incremental by design**: scan `$EIGEN_ROOT` FIRST, compute a delta, print it, THEN apply.
- All file paths within `$EIGEN_ROOT` must use the conventions from the language profile and the phase manifest's domain structure.
- You commit to the `$EIGEN_BRANCH` branch. You never push automatically.
- **Feedback files are owned by deepen commands.** You NEVER delete, overwrite, or recreate files under `$EIGEN_ROOT/eigen_initiative/phases/phase_N/feedback/`. On iteration, you only apply feedback-driven changes to `$EIGEN_ROOT`.

---

## Environment

Before proceeding, verify:

- [ ] `$EIGEN_ROOT` is set and points to an existing directory
- [ ] `$EIGEN_BRANCH` is set (the default branch from which all work starts)

If either is missing, **STOP** and print the appropriate error:

```
ERROR: $EIGEN_ROOT is not set.
Set it to the root folder of your target project:
  export EIGEN_ROOT=/path/to/your/project
```

```
ERROR: $EIGEN_BRANCH is not set.
Set it to the default branch from which all work starts:
  export EIGEN_BRANCH=main
```

**Key paths** (all relative to `$EIGEN_ROOT/eigen_initiative/`):

| Path | Description |
|------|-------------|
| `phases/phase_N_manifest.md` | Phase manifest (input) |
| `phases/phase_N/` | Phase output directory |
| `phases/phase_N/bootstrap-report.json` | Bootstrap report (output) |
| `phases/phase_N/feedback/` | Feedback directory (owned by deepen — never touch) |

## Output

- **In `$EIGEN_ROOT`**: Git-committed foundational files (directories, package manifests, entity stubs, contracts, quality config, basic CI)
- **Report**: `$EIGEN_ROOT/eigen_initiative/phases/phase_N/bootstrap-report.json` with delta applied, verification status, entities/contracts created, commit hashes

---

## On Entry

Run the CLI to get pipeline context:

```bash
eigen-squared get-context bootstrap --json
```

If the CLI exits with an error (non-zero), **STOP** and display the error message. Otherwise parse the returned JSON:

```json
{
  "command": "bootstrap",
  "branch": "main",
  "paths_relative_to": "$EIGEN_ROOT/eigen_initiative/",
  "phase": 1,
  "iteration": 2,
  "current_iteration": 1,
  "is_first_run": false,
  "should_process_feedback": true,
  "feedback_path": "phases/phase_1/feedback/deepen_bootstrap_feedback.json",
  "output_paths": {"bootstrap_report": "phases/phase_1/bootstrap-report.json"},
  "phase_manifest": "phases/phase_1_manifest.md",
  "recommendations": [...]
}
```

| Field | Usage |
|-------|-------|
| `phase` | Which phase to bootstrap |
| `iteration` | The iteration you are about to produce (display in headers) |
| `current_iteration` | The iteration that has already been produced |
| `is_first_run` | `true` → first run, skip feedback processing |
| `should_process_feedback` | `true` → iteration, read feedback from `feedback_path` |
| `feedback_path` | Relative path to deepen feedback JSON (resolve against `paths_relative_to`) |
| `output_paths` | Where to write the bootstrap report |
| `phase_manifest` | Relative path to the phase manifest |
| `recommendations` | Advisory observations from upstream deepen commands |

## On Exit

```bash
eigen-squared complete bootstrap --phase <phase> --output-path phases/phase_<phase>/bootstrap-report.json
eigen-squared commit-state --message "pipeline: bootstrap phase <phase> — foundation created" --additional-paths eigen_initiative/phases/phase_<phase>/
eigen-squared schedule-next
```

The CLI handles all field updates atomically: status, iteration, timestamps, feedback_consumed flags (both own and deepen counterpart).

---

## Iteration Protocol

This section applies when `should_process_feedback` is `true` in the CLI context.

### Read Feedback

1. Read the feedback file at `feedback_path` (resolved against `paths_relative_to` from CLI context).
2. Extract: `findings[]`, `convergence`, `previous_feedback_comparison`, and `code_change_guidance`.
3. Validate that `analyzed_iteration` matches `current_iteration` from the CLI context.

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

Use the `iteration` field from CLI context for the display header.

Classification rules:
- **ACCEPT**: the finding is valid and actionable — the recommendation will be incorporated.
- **PARTIAL**: the finding is valid but the recommendation is too broad or conflicts with another constraint — a narrower fix will be applied.
- **REJECT**: the finding is a false positive, contradicts a Critical Constraint, or would cause a worse outcome — explain why.

### Iteration-Specific Delta Computation

**Critical**: on iteration, do NOT re-scaffold from scratch. Instead:

1. **Scan current repo state** — read `$EIGEN_ROOT` as it exists now (same scan as Stage 0.2).
2. **Read `code_change_guidance`** from the feedback file. This contains surgical instructions:
   - `entities_to_add`: new entity stubs to create
   - `entities_to_modify`: existing stubs to update (add/remove/rename fields)
   - `files_to_delete`: files to remove
   - `config_changes`: configuration adjustments
3. **Apply only feedback-driven changes**.
4. **Do NOT re-run tooling decisions** (Stage 1 is always skipped on iteration).
5. **Do NOT re-scaffold directories** that already exist.

### Verification and Commit

1. Run the verification gate (Stage 4) after applying changes.
2. If verification passes: commit with message `"bootstrap: iteration <N> — address deepen feedback"`.
3. If verification fails:
   - Attempt up to 3 fix-retry cycles.
   - If still failing after 3 cycles: print the errors and proceed with warnings. Write `BOOTSTRAP_WARNINGS.md` to `$EIGEN_ROOT` documenting outstanding issues.
4. **NEVER delete, overwrite, or recreate `$EIGEN_ROOT/eigen_initiative/phases/phase_N/feedback/` or any file inside it.**

### Read Recommendations (if present)

Recommendations come from the `recommendations` field in the CLI context. Use as advisory context during scaffold planning:

- Inform decisions about directory structure, entity granularity, and config complexity.
- Do NOT treat as requirements. If your analysis contradicts a recommendation, follow your analysis.
- On iteration: the CLI always provides current recommendations (deepen commands may have updated them since last run).

---

## Stage 0: Ingest and Detect

### 0.1 Read Phase Manifest

1. Read `$EIGEN_ROOT/eigen_initiative/phases/phase_N_manifest.md` (where N is the auto-detected phase number).
2. Parse the YAML frontmatter to extract: `phase`, `initiative`, `feature_count`, `clusters_included`, `priority_distribution`, `e2e_summary`, `depends_on_phases`.
3. Parse the markdown body to extract:
   - **Features by Domain**: all feature tables — build a map of feature id → {name, priority, local_deps, cross_phase_deps, cluster, domain}
   - **Cross-Phase Dependencies**: features depending on prior phases
   - **Natural Clusters**: cluster → features mapping
   - **Blackbox Feature Specifications**: per-feature specs (feature_id → full spec text)
   - **Whitebox Reference Sections**: filtered whitebox content (may be absent if no whitebox file was provided)

### 0.2 Detect Repo State

Scan `$EIGEN_ROOT` to determine what already exists. This is the core incremental detection.

1. **Git status**: Is this a git repo? Is it empty (no commits)?
2. **Language manifest files**: Check for manifest files from the `language-profiles` skill detection table
3. **Directory structure**: Recursive listing to depth 4
4. **Existing domain directories**: Compare found directories against phase features' domain names
5. **Existing shared entities/contracts**: Language-specific scan for class/interface/struct definitions
6. **Config files**: Check for .editorconfig, linting config, formatting config, test runner config
7. **CI**: Check for `.github/workflows/` or equivalent

Classify each category as:
- `ABSENT` — doesn't exist at all
- `PRESENT` — exists and covers the needs for this phase
- `PARTIAL` — exists but needs additions for this phase's features

### 0.3 Language Resolution

1. If `$EIGEN_ROOT` has language manifest files → detect all languages using the `language-profiles` skill detection table. A project may have multiple languages (e.g., Python backend + TypeScript frontend).
2. If `$EIGEN_ROOT` is empty (no manifest files) → check the phase manifest's whitebox sections for language hints (framework mentions, library references). If still unclear, analyze the initiative document and blackbox specs for technology indicators and make a best-judgment decision.
3. Load the full language profile for each detected language from the `language-profiles` skill.

Print:
```
Detected languages:
  - <language_1>: <role (backend/frontend/full-stack/mobile/cli/library)>
  - <language_2>: <role> (if multi-language)
```

### 0.4 Verify System Prerequisites

For each detected language, check that the required system-level tools are installed by running the verification commands from the `language-profiles` skill's `system_prerequisites` section.

Additionally, check if this is a **server project** using the Server Project Detection heuristics in `language-profiles`. If it is a server project, add Docker and Docker Compose to the prerequisite checklist (check: `docker --version` and `docker compose version`). Docker is required for container parity, local infrastructure, and E2E testing.

For each prerequisite, run its `check` command. Collect all that fail.

If ANY prerequisites are missing → **STOP.** Print a checklist with install instructions and stop:

```
=== System Prerequisites Missing ===

The following must be installed before bootstrap can proceed:

  [ ] <tool_name> — <why it's needed>
      Check: <check command that failed>
      Install: <install command(s) from the language profile>

  [ ] <tool_name> — <why it's needed>
      Check: <check command that failed>
      Install: <install command(s) from the language profile>

After installing the missing prerequisites, re-run /bootstrap.
```

If ALL prerequisites pass → proceed to Stage 1. Print:

```
System prerequisites: all satisfied.
```

---

## Stage 1: Tooling Decisions

**Skip this entire stage if the repo already has package manifests (`PRESENT`).** Tooling decisions are already made and committed — bootstrap reads existing config and proceeds to Stage 2.

For greenfield repos (first-time bootstrap), you must make key tooling decisions.

### 1.1 Research Best Practices

Spawn best-practices research agents in parallel. For each detected language/framework, spawn a `Task general-purpose` sub-agent to research current best practices for project setup, using relevant skills from the `language-profiles` skill's Stack-Specific Skills table.

### 1.2 Make Tooling Decisions

Based on the research results and the initiative context, select the best tooling for each detected language. Print the decisions:

```
=== Tooling Decisions for Phase <N> ===

<for each detected language/role>
<Language> (<role>):
  Package manager: <pkg_manager> — <rationale>
  Framework: <framework> — <rationale> (if applicable)

Quality (<language>):
  Linter: <linter>
  Type checker: <type_checker>
  Test runner: <test_runner>

Hint: to change these decisions, run /deepen_bootstrap after bootstrap completes.
```

6. **Module system** (for JS/TS): check `package.json` `"type"` field — if `"module"` use ESM patterns (`import.meta.url`, `.js` extensions), if `"commonjs"` or absent use CJS patterns (`__dirname`, `require`). For Python: check if project uses `src/` layout. For Go: read `go.mod` module path. Apply the detected patterns when creating config files (vitest.config, eslint.config, etc.).

---

## Stage 2: Compute Delta

### 2.1 Derive Required Artifacts

For each artifact category, determine what's required based on the phase features, blackbox specs, whitebox sections, and tooling decisions:

1. **Git structure**: initialized repo + `$EIGEN_BRANCH` branch + initial commit (only if git is ABSENT)
2. **Package manifest**: pyproject.toml / package.json / etc. per tooling decisions (only if ABSENT)
3. **Directory structure**: map each domain in the features to a directory path using whitebox patterns. Include test directories per the language profile's `test_dir`.
4. **Shared domain entities**: scan all features' blackbox specs for entity references. Build a co-occurrence matrix: entity X is referenced by features [F1, F2, F3]. **Only create stubs for entities referenced by 2+ features spanning 2+ domains** — these are cross-epic shared types. For each, extract fields from blackbox specs (Inputs/Outputs sections), cross-reference with whitebox for field definitions.
   For cross-cutting features (e.g., access control, validation, logging) that reference ALL or most entities: create minimal stubs (id + foreign keys only) even for entities that belong to later phases. This prevents compile errors when cross-cutting code references entities not yet fully defined. Mark these as `"minimal_stub": true` in the bootstrap report.
5. **API contracts**: if features reference REST/HTTP/endpoint patterns in blackbox specs, create interface definitions or OpenAPI stubs for inter-domain API boundaries.
6. **Message contracts**: if features reference queue/event/message/async patterns in blackbox specs, create typed schema stubs.
7. **Quality config**: linting, formatting, type checking, test runner config per tooling decisions (always if ABSENT)
8. **Basic CI**: GitHub Actions workflow with: checkout → install deps → lint → type-check → run tests (excluding E2E). This is a simple quality gate, not deployment or E2E infrastructure. (only if ABSENT)

### 2.2 Compute Delta

For each category: `delta[category] = required[category] - existing[category]`

### 2.3 Print Delta

```
=== Bootstrap Delta for Phase <N> ===

Target repo: $EIGEN_ROOT
Languages: <detected languages with roles>
Phase features: <N> features across <M> domains

Action Summary:
  Git init:          <CREATE|SKIP>
  Package manifest:  <CREATE|UPDATE|SKIP> <filename>
  Directories:       CREATE <N> new (<M> existing, skipped)
  Shared entities:   CREATE <N> entity stubs (referenced across 2+ domains)
  API contracts:     <CREATE N|SKIP (no API features)>
  Message contracts: <CREATE N|SKIP (no async features)>
  Quality config:    <CREATE|SKIP>
  Basic CI:          <CREATE|SKIP>

Estimated files to create: ~<N>
```

Proceed to Stage 3.

---

## Stage 3: Execute Bootstrap

### 3.0 Determine Execution Strategy

If the delta is large (many entities/contracts to create), use sub-agents for parallelism. For small deltas, execute as a single agent.

### 3.1 Single-Agent Path (Small Delta)

Execute the delta sequentially:
1. Create new directories (including `mkdir -p $EIGEN_ROOT/eigen_initiative/phases/phase_N/feedback/`)
2. Create/update package manifest (add new dependencies for this phase)
3. Create new entity stubs (for domains entering in this phase)
4. Create new API/message contract stubs
5. Create/update quality config if needed
6. Create/update basic CI if needed
7. Create package index files if needed (Python: `__init__.py`, TypeScript: `index.ts`, Go/C#: no action)
8. Install dependencies
9. Commit: `"bootstrap: foundation for phase N"`

### 3.2 Sub-Agent Path (Large Delta)

Execute in two waves:

**Wave 0 (Lead Direct — sequential, no sub-agents):**

1. Git init if needed: `git init $EIGEN_ROOT` + `git checkout -b $EIGEN_BRANCH` + create `.gitignore`
2. Create package manifest per tooling decisions
3. Create directory structure: all domain directories from phase features + test directories per language profile
4. Create quality config files: .editorconfig, linting config, formatting config, type checker config, test runner config
5. Create basic CI: `.github/workflows/ci.yml` that delegates to project scripts — use `npm run lint` / `npm run typecheck` / `npm test` (not `npx eslint .` / `npx tsc --noEmit`). The CI workflow should call the same commands developers run locally via package.json scripts or Makefile targets.
6. If monorepo (multiple languages): create workspace structure with separate package manifests
7. **If server project** (detected via `language-profiles` skill → Server Project Detection):
   - Create a minimal health check endpoint (e.g., `GET /health` or `GET /api/health` returning 200 OK) in the appropriate framework convention. This is the ONLY route bootstrap creates — it validates the app starts and responds.
   - Create Dockerfile using the template from `language-profiles` skill → Dockerfile Templates, adapted for the detected language version, package manager, and project structure. Record the exposed port from the template.
   - Create docker-compose.yml with the app service + all infrastructure services detected from dependencies (use the "Detect infrastructure services" table in the Server Project Detection section of `language-profiles`)
   - Create .dockerignore with standard ignores for the detected language (see Dockerignore Templates in `language-profiles`)
   - Verify: `docker compose config` validates without errors (if docker is available)
8. Commit: `"bootstrap: project scaffold"`

**Wave 1 (Parallel sub-agent via `Task general-purpose` — Contract Generator):**

```
Prompt: You are a Contract Generator creating shared entity stubs and API/message contracts.

Languages: <detected languages with roles>
Language Profile: <from the language-profiles skill>
Tooling: <tooling decisions>

## Entity Stubs to Create

<for each entity in delta shared_entities>
  Entity: <name>
  Referenced by features: <list>
  Fields: <field_name>: <type> (extracted from blackbox specs)
  File path: <computed from language conventions>

  Create a stub with:
  - All fields as typed declarations (dataclass for Python, interface for TypeScript, struct for Go, etc.)
  - NO business logic
  - Use the language profile's not_implemented marker for any method bodies
  - Include a module-level comment: "Bootstrap stub — generated by /bootstrap for Phase N"

## API Contracts to Create

<for each contract in delta api_contracts>
  Create interface definitions or OpenAPI stubs with endpoint paths and request/response schemas referencing entity fields.

## Message Contracts to Create

<for each schema in delta message_contracts>
  Create typed schema stubs per language conventions.

## Rules
- Entity stubs must have ALL fields typed but NO behavior
- Respect language conventions from the language profile

Return your response as a map of {file_path: file_content} for ALL files created.
```

### 3.3 Collect Results and Reconcile

After the sub-agent returns (or after single-agent execution):
1. Write all files to `$EIGEN_ROOT`
2. Create package index files if needed (Python: `__init__.py`, TypeScript: `index.ts`)
3. Check for missing cross-references (entity A references entity B but B wasn't created)
4. Install dependencies: run the package manager install command
5. Commit: `"bootstrap: entity stubs and contracts for phase N"`

---

## Stage 4: Verification Gate

### 4.1 Run Language-Appropriate Verification

Execute the verification commands appropriate to each detected language:

- **Python**: `python -c "import <pkg>"` + `ruff check .` + `pytest --collect-only`
- **TypeScript**: `npx tsc --noEmit` + `npx eslint . --max-warnings 0`
- **Go**: `go build ./...` + `go vet ./...`
- **Rust**: `cargo check`
- **C#/.NET**: `dotnet build`

For multi-language projects, run verification for each language.

### 4.2 Report Honest Baselines

For existing codebases (not greenfield): run verification against the FULL repository, not just bootstrap-created files. Report actual counts:

```
Verification baseline:
  Lint warnings: <actual count> (N new from bootstrap, M pre-existing)
  Type errors: <actual count>
  Test files found: <actual count>
```

Do NOT claim "passed" when legacy warnings exist. Set honest thresholds: CI should use the baseline count (e.g., `--max-warnings <baseline>`) rather than zero. If the codebase has pre-existing issues, document them in the bootstrap report rather than hiding them.

### 4.3 Handle Verification Failures

If verification fails:
1. Parse the error output
2. Attempt automatic fix (missing imports, typos in stubs, package resolution issues)
3. Re-run verification
4. Maximum 3 fix-retry cycles

If still failing after 3 cycles: print the errors and proceed with warnings. Write `BOOTSTRAP_WARNINGS.md` to `$EIGEN_ROOT` documenting outstanding issues. Commit any fixes: `"bootstrap: fix verification issues"`

---

## Stage 5: Generate Report and Summary

### 5.1 Generate Bootstrap Report

Write `$EIGEN_ROOT/eigen_initiative/phases/phase_N/bootstrap-report.json`:

```json
{
  "phase": 1,
  "iteration": 1,
  "languages": [
    { "language": "<language>", "role": "<backend|frontend|full-stack|mobile|cli|library>" }
  ],
  "tooling_decisions": {
    "<language>": {
      "package_manager": "<pkg_manager>",
      "framework": "<framework>",
      "linter": "<linter>",
      "type_checker": "<type_checker>",
      "test_runner": "<test_runner>"
    }
  },
  "repo_state_before": "<empty|has N files>",
  "timestamp": "<ISO 8601>",
  "delta_applied": {
    "git_init": true,
    "directories_created": 12,
    "entity_stubs_created": 5,
    "api_contracts_created": 2,
    "message_contracts_created": 1,
    "config_files_created": 4,
    "ci_created": true,
    "server_project_detected": true,
    "dockerfile_created": true,
    "docker_compose_created": true,
    "docker_compose_services": ["app", "postgres"],
    "dockerignore_created": true,
    "exposed_port": 8000,
    "health_check_path": "/api/health",
    "total_files_created": 31,
    "total_files_modified": 0,
    "total_files_skipped": 0
  },
  "verification": {
    "status": "passed",
    "warnings": [],
    "commands_used": ["ruff check .", "mypy .", "pytest --collect-only"]
  },
  "entities_created": [
    { "name": "Communication", "path": "src/models/communication.py", "fields": ["id", "channel", "timestamp"] }
  ],
  "contracts_created": [
    { "name": "search-api", "path": "openapi/search-api.yaml", "type": "openapi" }
  ],
  "commits": [
    { "hash": "abc1234", "message": "bootstrap: project scaffold" },
    { "hash": "def5678", "message": "bootstrap: entity stubs and contracts for phase 1" }
  ],
  "iteration_history": [
    {
      "iteration": 1,
      "timestamp": "<ISO 8601>",
      "trigger": "initial",
      "delta_summary": "Scaffold: <N> dirs, <M> entities, <K> contracts, CI, quality config",
      "verification_status": "passed"
    }
  ]
}
```

### 5.2 Print Summary

```
=== Bootstrap Complete — Phase <N> ===

Target repo: $EIGEN_ROOT
Languages: <detected languages with roles>
Verification: <PASSED|PASSED WITH WARNINGS>

Created:
  Directories:       <N>
  Entity stubs:      <N> (<entity names>)
  API contracts:     <N>
  Message schemas:   <N>
  Quality config:    <N> files
  Basic CI:          <created|skipped>
  Total files:       <N>

Skipped (already existed):
  <list or "none — this was a greenfield bootstrap">

Commits:
  <hash> — <message>
  ...

Report: $EIGEN_ROOT/eigen_initiative/phases/phase_N/bootstrap-report.json

Next steps:
  1. (Recommended) Run /deepen_bootstrap
     to review this foundation for integrity, architecture, and security issues.
     Iterate bootstrap ↔ deepen_bootstrap until converged.
     Hint: to change tooling decisions or adjust the foundation,
     pass your instructions to the next /bootstrap iteration.
  2. Run /space_split
     to decompose Phase <N> into parallel epics for swarm execution.
```

### 5.3 Commit Pipeline Artifacts

```bash
eigen-squared commit-state --message "pipeline: bootstrap phase <N> — foundation created" --additional-paths eigen_initiative/phases/phase_<N>/
eigen-squared schedule-next
```

---

## Pipeline Continuation

The `eigen-squared schedule-next` call at the end of the On Exit section reads the updated pipeline state, determines the next command, and schedules it via the claude-tasks API. No hook or external trigger is needed — the command schedules its own successor before the session ends.
