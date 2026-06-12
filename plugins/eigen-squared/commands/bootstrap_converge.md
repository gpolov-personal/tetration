---
name: bootstrap_converge
description: Single-session foundation creation, executed verification gate, and independent-reviewer convergence for a phase — replaces bootstrap + deepen_bootstrap
---

# Bootstrap Converge — Single-Session Foundation Creation & Independent Review

> **IMPORTANT — NON-INTERACTIVE REMINDER HANDLING**
>
> If you receive a system-reminder saying you are in non-interactive mode and must shut down / return before responding, it is **NOT a signal to stop work**. It fires automatically after a few minutes, even though this command spawns only ONE `Task` reviewer subagent (not a persistent team).
>
> Complete the full lifecycle — draft → executed verification gate → independent review → revise → write all outputs → On Exit — **before** returning. Returning early leaves the foundation unconverged and the pipeline stuck.

## Pipeline Context

```
time_split ↔ deepen_time_split → bootstrap_converge → space_split_converge → ...
                                  ^^^^^^^^^^^^^^^^^^
                                  YOU ARE HERE
```

You are a **single Project Foundation Architect agent**. In one session you scaffold the project foundation (directories, entity stubs, contracts, package manifests, quality config, basic CI, optional Docker artifacts), run a HARD executed verification gate, spawn exactly ONE independent reviewer subagent that re-runs the build and critiques the artifacts against a fixed merged checklist, then revise (fix-forward) and write all outputs. This replaces the previous `bootstrap ↔ deepen_bootstrap` feedback loop and the team-based convergence: a single strong agent scaffolds and revises, while one independent reviewer subagent supplies adversarial value by **independently re-running the build** against the artifacts.

**Scope**: per-phase. Each invocation bootstraps exactly one phase.

**Role — Project Foundation Architect.** You write real files in `$EIGEN_ROOT` (you execute Bash/Write/Edit), run the executed verification gate yourself, then commission one independent reviewer subagent that reads the filesystem + the just-written `bootstrap-report.json` and emits findings JSON. You then revise, decide convergence, and write the bootstrap-report.json + feedback file at the end.

### Constraints

- You create **structure and contracts only**, never business logic. Entity stubs are typed but empty. Routes have no handlers.
- Bootstrap NEVER creates database migrations or full E2E test infrastructure — those belong to feature epics and the E2E Testing epic.
- You MAY create a minimal health check endpoint, Dockerfile, docker-compose.yml, and .dockerignore for **server projects only**, using templates from the `language-profiles` skill.
- **Schema source priority** when creating entity stubs:
  1. Existing schema/migration files in `$EIGEN_ROOT` (trust code over docs)
  2. Whitebox database schema section (if present)
  3. Blackbox specs (greenfield case)
- **Incremental by design**: scan `$EIGEN_ROOT` FIRST, compute a delta, print it, THEN apply. On revise passes apply surgical fixes — never re-scaffold.
- **bootstrap-report.json schema is invariant** — `space_split_converge`, `create_issues_from_plan_swarm`, and `plan_epic_converge` consume it. Path is always `phases/phase_N/bootstrap-report.json` and the schema must match the legacy bootstrap output (delta_applied, entities_created, contracts_created, verification, tooling_decisions, commits, languages, server_project_detected, dockerfile_created, etc.).
- **pipeline_state.json is the single source of truth** — per-phase converge state lives at `state.phases[N].bootstrap_converge`.
- **Feedback file**: `phases/phase_N/feedback/bootstrap_converge_feedback.json` — owned by this command, no other command writes to it.

## Environment

Verify before proceeding:

- [ ] `$EIGEN_ROOT` is set and points to an existing directory
- [ ] `$EIGEN_BRANCH` is set (the default branch from which all work starts)
- [ ] The `eigen-squared` CLI is available on `PATH`

If either env var is missing, **STOP** and print the appropriate error.

**Key paths** (relative to `$EIGEN_ROOT/eigen_initiative/`):

| Path | Description |
|------|-------------|
| `phases/phase_N_manifest.md` | Phase manifest (input) |
| `phases/phase_N/bootstrap-report.json` | Bootstrap report (output, invariant schema) |
| `phases/phase_N/bootstrap_baseline.json` | Project-bootstrap baseline (output, consumed by orchestrate_swarm gates) |
| `phases/phase_N/feedback/bootstrap_converge_feedback.json` | Convergence feedback (output) |
| `eigen_lessons/bootstrap_converge/` | Lessons directory |

## Output

- **In `$EIGEN_ROOT`**: Git-committed foundational files (directories, package manifests, entity stubs, contracts, quality config, basic CI, optionally Dockerfile/docker-compose/.dockerignore for server projects)
- **Bootstrap report**: `phases/phase_N/bootstrap-report.json` (invariant schema, written at convergence)
- **Project-bootstrap baseline**: `phases/phase_N/bootstrap_baseline.json` (green-state suite snapshot, consumed by downstream epic gates)
- **Feedback file**: `phases/phase_N/feedback/bootstrap_converge_feedback.json` (rounds + findings + resolution)
- **Lessons**: `eigen_lessons/bootstrap_converge/*.json` (one per non-false-positive finding)

---

## On Entry

```bash
eigen-squared get-context bootstrap_converge --json
```

If the CLI exits with an error (non-zero), STOP and display the error message. Otherwise parse the returned JSON. Example:

```json
{
  "command": "bootstrap_converge",
  "branch": "main",
  "paths_relative_to": "$EIGEN_ROOT/eigen_initiative/",
  "phase": 1,
  "iteration": 1,
  "current_iteration": 0,
  "is_first_run": true,
  "output_paths": {},
  "phase_manifest": "phases/phase_1_manifest.md",
  "bootstrap_report": "phases/phase_1/bootstrap-report.json",
  "lessons_dir": "eigen_lessons/bootstrap_converge/",
  "recommendations": []
}
```

| Field | Use |
|---|---|
| `phase` | Which phase to bootstrap (N throughout this document) |
| `iteration` | The iteration about to be produced |
| `current_iteration` | The iteration already produced |
| `is_first_run` | `true` → no prior run; proceed to Stage 0. `false` → crash recovery (see below) |
| `output_paths` | Existing output paths recorded in pipeline state |
| `bootstrap_report` | Relative path where bootstrap-report.json is expected |
| `phase_manifest` | Relative path to the phase manifest |
| `lessons_dir` | Relative path to the lessons directory |
| `recommendations` | Advisory observations from upstream `deepen_time_split` |
| `locked_skills` | (only present after a prior run) frozen skill set discovered in the earlier session |

**Crash recovery**: if `is_first_run: false`, the scaffolder commits real files, so already-committed foundation work must not be redone. Run `git log --oneline -20` in `$EIGEN_ROOT` to detect commits already made (look for `bootstrap_converge: ...` messages — `project scaffold`, `entity stubs and contracts`, `foundation for phase N`, `round <N> ...`). Verify the current working tree matches the expected outputs of those commits, then RESUME from the first stage whose output is not yet committed rather than re-scaffolding. Stage 0 detection is idempotent (scanning the repo is free), so always re-run it to ground the resume.

## On Exit

```bash
eigen-squared complete bootstrap_converge --phase <N> --output-path phases/phase_<N>/bootstrap-report.json --feedback-path phases/phase_<N>/feedback/bootstrap_converge_feedback.json --findings-summary '{"high": 0, "medium": 0, "low": <count>}' --locked-skills '["skill-a", "skill-b", ...]'
eigen-squared mark-converged bootstrap_converge --phase <N> --reason "<convergence rationale>"
eigen-squared add-recommendation --from-cmd bootstrap_converge --target space_split_converge --phase <N> --iteration <N> --text "<observation>"
eigen-squared commit-state --message "pipeline: bootstrap_converge phase <N> — converged" --additional-paths eigen_initiative/phases/phase_<N>/,eigen_initiative/eigen_lessons/bootstrap_converge/
```

The `add-recommendation` line is OPTIONAL (max 5 per target command). Include `--locked-skills` so the CLI persists the discovered skill set for crash recovery.

The CLI handles all field updates atomically: status, iteration, timestamps, output_paths, locked_skills, findings_summary.

---

## Stage 1: Read Inputs

1. Read `$EIGEN_ROOT/eigen_initiative/phases/phase_<N>_manifest.md`. Parse YAML frontmatter (phase, initiative, feature_count, clusters_included, priority_distribution, e2e_summary, depends_on_phases) and markdown body (Features by Domain, Cross-Phase Dependencies, Natural Clusters, Blackbox Feature Specifications, Whitebox Reference Sections).
2. Read `recommendations` from the CLI context (filter by current phase). Use as advisory context — not requirements.
3. If `is_first_run: false`, run `git log --oneline -20` in `$EIGEN_ROOT` to detect already-committed foundation work and resume from the first uncommitted stage (see On Entry crash recovery).
4. **Cross-epic patterns (advisory).** Attempt to read `$EIGEN_ROOT/eigen_initiative/eigen_lessons/compound_improve/cross_epic_patterns.json` (written by `/compound_improve` Stage 1.6). If the file does not exist or `patterns` is empty, skip silently. Otherwise extract patterns whose `kind` is `oscillation` or `architectural_escalation` AND whose `category` is in {`infrastructure`, `tooling`, `architecture`, `dependency`, `type-safety`} (the categories that affect phase scaffolding). Treat any kept patterns as a "Known oscillation-prone patterns from prior projects" advisory while scaffolding: plan defensively when scaffolding decisions touch these areas.

## Stage 2: Discover & Lock Skills (single pass)

Discover ALL available skills from all sources (project, user, all plugins) in ONE pass, early in the session. Match them against the detected languages/frameworks and dependency manifest. Prioritize: language-specific best practices (python-testing-patterns, react-best-practices, go-best-practices, etc.), security-best-practices, language-profiles, ci/cd patterns. Record the matched skill set — you will apply each matched skill's lens both while scaffolding (Stage 3) and as the skills-lens in the independent review (Stage 5). Discover once; do not re-discover later in the session. If `locked_skills` was present in the CLI context (prior-run resume), use exactly that set.

## Stage 3: Draft / Scaffold the Foundation

You scaffold the project foundation in `$EIGEN_ROOT` with real files, real dependency installs, and real git commits. Fix-forward only: NEVER use `git --amend`, NEVER rollback. If a commit is later found wrong, the revise pass produces a corrective fix-forward commit.

### 3.1 Detect

- Detect repo state in `$EIGEN_ROOT` — git status, language manifest files, directory structure (depth 4), existing domain dirs, existing entity/contract files, config files, CI workflows. Classify each as ABSENT | PRESENT | PARTIAL.
- Detect languages. If `$EIGEN_ROOT` has manifest files, use the `language-profiles` skill detection table. If empty, fall back to whitebox/blackbox hints. Load full language profiles for each detected language. A project may have multiple languages (e.g., Python backend + TypeScript frontend).
- Verify system prerequisites for each language (and Docker/Docker Compose if it's a server project per the `language-profiles` Server Project Detection heuristics). If ANY prerequisite is missing, STOP and report a prerequisite checklist with install instructions.

### 3.2 Tooling Decisions (skip entirely if package manifests are PRESENT)

- Research best practices per language/framework using relevant skills from the `language-profiles` Stack-Specific Skills table. You MAY spawn parallel research `Task` agents for this — optional research fan-out, not a convergence team.
- Make tooling decisions: package manager, framework, linter, type checker, test runner per language. For JS/TS check the module system via `package.json` type field; for Python check src/ layout; for Go read `go.mod`.

### 3.3 Compute Delta

- Derive required artifacts: git structure, package manifest, directory structure (mapped from phase manifest domains), shared domain entities (only entities referenced by 2+ features spanning 2+ domains; cross-cutting features may create `minimal_stub: true` entries for entities owned by later phases), API contracts, message contracts, quality config, basic CI.
- Compute delta = required − existing.
- Print the delta summary (action counts, estimated file count) before applying.

### 3.4 Execute

- Choose strategy: single-agent for small deltas, parallel `Task` sub-agents for large deltas.
- Create in order: git init if needed → package manifest → directory structure (a dir per domain + `test_dir` per language profile) → quality config files → basic CI (`.github/workflows/ci.yml` that delegates to package.json scripts / Makefile targets, never to npx/eslint directly) → monorepo workspace structure if needed → entity stubs (ALL fields typed, NO behavior, use the language profile's `not_implemented` marker) → API/message contracts → package index files.
- If server project: minimal health check endpoint, Dockerfile from `language-profiles` template, docker-compose.yml with app + infrastructure services, .dockerignore. Verify `docker compose config` if docker is available.
- Install dependencies. Commit the work: `bootstrap_converge: project scaffold` for structure/config/CI, then `bootstrap_converge: entity stubs and contracts for phase N` for stubs+contracts (a single combined `bootstrap_converge: foundation for phase N` commit is acceptable for small single-agent deltas).
- Check cross-references between stubs, contracts, and index files.

## Stage 4: Hard Verification Gate (EXECUTED)

Run the language-appropriate verification commands **for real** (Bash, not reasoning) per detected language:

- **Python**: `python -c import` checks + `ruff check` + `pytest --collect-only`
- **TypeScript/JS**: `tsc --noEmit` + `eslint`
- **Go**: `go build` + `go vet`
- **Rust**: `cargo check`
- **C#/.NET**: `dotnet build`

For **server projects** also run `docker compose config` (always) and `docker compose build` (if docker is available locally).

Report honest baselines for existing codebases — actual lint warnings, type errors, test counts. Do NOT claim 'passed' when legacy issues exist. Use the baseline as the CI threshold (e.g. `--max-warnings <baseline>`).

If verification fails, attempt automatic fixes (missing imports, package resolution, typos in stubs) — maximum 3 internal fix-retry cycles. A broken build is a `verification_failure`, which is **ALWAYS high severity and blocks convergence**. If still failing after 3 retries, record `verification_status: 'failed_with_warnings'`; the independent reviewer and the revise pass will fix-forward.

Record the exact commands run and their results — the independent reviewer will RE-RUN them independently in Stage 5.

## Stage 5: Independent Review (CONSERVATIVE — one reviewer subagent)

Spawn **exactly ONE** reviewer subagent via the `Task` tool with `subagent_type: general-purpose`. Its value is **independence**: it re-runs the build against ground truth and critiques the artifacts without seeing your reasoning.

Give the reviewer ONLY:
- Read access to `$EIGEN_ROOT` and Bash (it MUST be able to re-run verification commands).
- The just-written artifacts: the entity stubs, contracts, config, CI, Docker files, and the in-memory `bootstrap-report.json` content (the `bootstrap_report_content` you assembled — paste it in the prompt).
- The phase manifest content.
- The MERGED critique checklist + the severity rubric below.
- An instruction to INDEPENDENTLY re-run the verification gate and verify your claims against ground truth.

Do **NOT** give the reviewer your reasoning, your delta narrative, or any justification for choices — only the artifacts + checklist. This preserves adversarial independence.

The reviewer returns a findings JSON array (no SendMessage — it returns its result as the `Task` output). Each finding: `category`, `severity_proposal`, `source_checklist`, `title`, `description`, `affected_file`, `affected_section`, `recommendation`, and `code_change_guidance` ({ entities_to_add, entities_to_modify, files_to_delete, config_changes }). The reviewer PROPOSES severity; you decide final severity using the rubric.

### Reviewer prompt — merged critique checklist

```
You are an INDEPENDENT FOUNDATION REVIEWER for phase P<N>. You did not build this foundation and have no knowledge of the author's reasoning. Your job is to critique the artifacts against ground truth and the checklist below, then return findings JSON.

You have Read AND Bash tool access. You MUST re-run verification commands against $EIGEN_ROOT — do not trust the report's claims; verify them.

ARTIFACTS PROVIDED:
- $EIGEN_ROOT (read the real files directly)
- bootstrap-report.json content: <pasted>
- phase manifest content: <pasted>

Run the checklist below in full, then return a JSON array of findings.

=== FOUNDATION CHECKLIST ===
1. Entity Completeness:
   1.1 A stub file exists for every entity referenced by 2+ features spanning 2+ domains.
   1.2 Fields match the blackbox specs.
   1.3 Field types are reasonable for the domain.
   1.4 No entities missing that should have been created.
   1.5 No orphan entities created but not referenced by 2+ cross-domain features.
2. Directory Structure:
   2.1 A directory exists for every domain in the phase manifest.
   2.2 Naming convention matches the detected language profile.
   2.3 Test directories are structured per the language profile's test_dir convention.
   2.4 No orphan directories (exist but no features reference them).
3. Contract Alignment:
   3.1 Every REST/HTTP feature has an interface or OpenAPI stub.
   3.2 API schemas reference the correct entity fields.
   3.3 Every async/event/message feature has a message contract.
   3.4 Message schemas match the entity fields.
   3.5 No orphan contracts that don't correspond to any feature.
4. Configuration Consistency:
   4.1 Lint config matches tooling_decisions (e.g. ruff chosen → ruff configured).
   4.2 Type-checker config present and correct for the chosen tool.
   4.3 Test-runner config present and correct.
   4.4 CI workflow runs lint + type-check + tests (excluding E2E) with the correct commands.
   4.5 .editorconfig present with reasonable defaults.

=== FIDELITY CHECKLIST ===
1. Entity Fidelity: per-entity, extract field names + types from each stub and compare against the schema source BY PRIORITY:
     a. Existing schema/migration files in $EIGEN_ROOT (SQL migrations, ORM model files, schema.prisma) — primary if present
     b. Whitebox database schema section — if no schema files
     c. Blackbox specs — last resort
   Flag: fields in schema source but missing from stub; fields in stub not in schema source or blackbox; type mismatches; enum/constraint mismatches.
2. Package Manifest:
   2.1 Manifest includes the chosen framework.
   2.2 Includes the test runner and testing libraries.
   2.3 Includes the linter and type checker.
   2.4 No unnecessary dependencies (not needed by any phase feature).
   2.5 Versions pinned or using reasonable ranges.
3. Verification Replay (EXECUTED — use Bash):
   3.1 Re-run the EXACT verification commands from bootstrap-report.json verification.commands_used.
   3.2 Do they still pass?
   3.3 Any NEW warnings compared to the report's claimed run?
   3.4 If they fail, identify what changed.
   3.5 If delta_applied.server_project_detected is true:
       - Dockerfile exists AND 'docker compose config' validates without errors
       - docker-compose.yml lists the expected services (compare against delta_applied.docker_compose_services)
       - If docker is available locally: 'docker compose build' succeeds
   verification_failure → propose severity 'high' (always blocks convergence).

=== STRATEGIC CHECKLIST (5 lenses) ===
1. Architecture: layout sound for the initiative's scale and domains; clean entity boundaries (no god-entities); supports the phase's E2E summary testability; no implicit decisions that hurt later phases.
2. Code Simplicity: stubs not over-engineered (no needless abstract bases/inheritance); config not over-complex for current needs; CI does no more than lint + type-check + test; directory structure not needlessly deep.
3. Security: no sensitive fields (passwords/tokens/PII) exposed without protection patterns; CI has secret-scanning / dependency-audit; no .env committed; no hardcoded credentials or API keys.
4. Phase N+1 Readiness: if phase_<N+1>_manifest.md exists, the current structure accommodates its new domains/entities; naming/patterns allow incremental extension; no anti-patterns (hardcoded paths, non-modular structure) that block extension.
5. Cross-Artifact Consistency: entity names in API/message contracts resolve to real stub files; package index files export the correct symbols (skip for Go/.NET); no orphan files; no dangling references (contract references an entity that doesn't exist).

=== SKILLS-LENS ===
Review the foundation through each matched skill's lens for domain gaps and anti-patterns. Matched skills for this project: <list from Stage 2>.

=== SEVERITY RUBRIC (propose per finding; verification_failure ALWAYS high) ===
- high: blocks space_split_converge or downstream swarms — build does not compile; entity referenced by 2+ features does not exist; contract has invalid types; critical dependency missing; verification_failure is ALWAYS high.
- medium: functional but suboptimal — legacy lint warnings; config incomplete for future extension; entity missing fields needed in phase N+1; Docker healthcheck missing in a server project.
- low: minor/stylistic — inconsistent naming; missing comments; import ordering.

RETURN FORMAT — a JSON object:
{
  "findings": [
    {
      "category": "<entity_error|structure_error|contract_error|config_error|verification_failure|incremental_error|language_adaptation_error|false_positive>",
      "severity_proposal": "<high|medium|low>",
      "source_checklist": "<foundation-1|fidelity-3|strategic-2|skills|combined>",
      "title": "<concise>",
      "description": "<detailed, with file paths>",
      "affected_file": "<path>",
      "affected_section": "<section within file or top-level>",
      "recommendation": "<specific action>",
      "code_change_guidance": {
        "entities_to_add": [...],
        "entities_to_modify": [...],
        "files_to_delete": [...],
        "config_changes": [...]
      }
    }
  ]
}
```

When the reviewer returns, apply the severity rubric to set the FINAL severity for each finding (`verification_failure` always becomes high regardless of the proposal), and drop anything that is genuinely a `false_positive` on reflection.

## Stage 6: Revise (fix-forward)

If the independent review found zero high findings and there is no active `verification_failure`, the foundation has converged — go to Stage 7.

Otherwise, apply the fixes with **surgical edits ONLY** — never re-scaffold. For each high finding (and any active verification_failure), apply the recommended fix:
- `entities_to_add` → create new stub files
- `entities_to_modify` → add_fields / remove_fields / rename_fields on existing stubs
- `files_to_delete` → delete the listed files
- `config_changes` → apply the listed config edits

**CASCADING UPDATE RULES** — when applying a change, apply ALL structural consequences:
- `add_entity_field` → update the stub file + every contract that references the entity + tests if applicable
- `add_dependency` → update the package manifest + lock file + CI cache key if needed
- `change_lint_rule` → re-run the lint baseline + apply the formatter if needed
- `add_health_endpoint` → update Dockerfile EXPOSE + docker-compose healthcheck
- `add_domain` → create directory + test_dir per language profile + CI matrix entry if applicable

After applying, **re-run the Stage 4 verification gate** on the modified set (max 3 internal retries) and **commit per pass**: `bootstrap_converge: round <R> — address <category> findings`. NEVER use `git --amend`. NEVER rollback. Fix-forward only.

**Convergence bound:** at most **2** revise passes, and only while a high finding or an active `verification_failure` remains. After the second pass, accept the current state and converge — degrade any remaining medium findings to `low` and record them. A 2-pass bound cannot oscillate, so no oscillation tracking is needed. Carry the convergence rationale into the feedback JSON:
- Clean: "All significant issues resolved. Zero high findings remain and the build passes."
- Bounded: "Revise bound (2 passes) reached. Remaining medium findings degraded to low; accepting current state."

> **Verification-failure veto:** convergence is BLOCKED while any active finding has `category: verification_failure`. A broken build is always blocking. If the 2-pass bound is reached with an active verification_failure, do NOT mark converged — record `verification_status: failed_with_warnings`, write the outputs honestly, and surface the unresolved build failure in the summary.

---

## Stage 7: Output & Cleanup (at convergence)

### 7.1 Write bootstrap-report.json

Write the final `bootstrap_report_content` to:

```
$EIGEN_ROOT/eigen_initiative/phases/phase_<N>/bootstrap-report.json
```

The schema is **INVARIANT** — `space_split_converge`, `create_issues_from_plan_swarm`, and `plan_epic_converge` depend on this exact shape. Do not add or rename fields:

```json
{
  "phase": <N>,
  "iteration": <internal round counter>,
  "languages": [{ "language": "...", "role": "backend|frontend|full-stack|mobile|cli|library" }],
  "tooling_decisions": { "<language>": { "package_manager": "...", "framework": "...", "linter": "...", "type_checker": "...", "test_runner": "..." } },
  "repo_state_before": "<empty|has N files>",
  "timestamp": "<ISO 8601>",
  "delta_applied": {
    "git_init": true|false, "directories_created": N, "entity_stubs_created": N,
    "api_contracts_created": N, "message_contracts_created": N, "config_files_created": N,
    "ci_created": true|false, "server_project_detected": true|false,
    "dockerfile_created": true|false, "docker_compose_created": true|false,
    "docker_compose_services": [...], "dockerignore_created": true|false,
    "exposed_port": N, "health_check_path": "/api/health",
    "total_files_created": N, "total_files_modified": N, "total_files_skipped": N
  },
  "verification": { "status": "passed|passed_with_warnings|failed_with_warnings", "warnings": [...], "commands_used": [...] },
  "entities_created": [{ "name": "...", "path": "...", "fields": [...] }],
  "contracts_created": [{ "name": "...", "path": "...", "type": "openapi|message|..." }],
  "commits": [{ "hash": "...", "message": "..." }],
  "iteration_history": [{ "iteration": N, "timestamp": "...", "trigger": "...", "delta_summary": "...", "verification_status": "..." }]
}
```

### 7.2 Write Feedback JSON

Ensure the directory exists: `mkdir -p $EIGEN_ROOT/eigen_initiative/phases/phase_<N>/feedback/`

Write to `phases/phase_<N>/feedback/bootstrap_converge_feedback.json`:

```json
{
  "schema_version": "1.0.0",
  "command": "bootstrap_converge",
  "phase": <N>,
  "iteration": "<total internal rounds>",
  "convergence": {
    "decision": "converged",
    "rationale": "<convergence rationale from Stage 6>",
    "rounds_taken": <R>
  },
  "findings": [
    {
      "id": "bcf-<seq>",
      "category": "<category>",
      "severity": "<high|medium|low>",
      "title": "<concise>",
      "description": "<detailed>",
      "affected_file": "<path>",
      "affected_section": "<section>",
      "recommendation": "<action that was taken>",
      "resolution": "resolved|degraded_to_low|accepted_at_convergence",
      "source_reviewer": "independent-reviewer",
      "source_checklist": "<id>",
      "downstream_impact": {
        "affects_commands": ["space_split_converge"],
        "impact_description": "<what would break downstream>"
      }
    }
  ],
  "summary": {
    "total_findings": <N>,
    "by_severity": { "high": 0, "medium": 0, "low": <N> },
    "by_category": { "<category>": <N> }
  }
}
```

The `findings` array includes ALL findings — both resolved and remaining. `resolution` tracks how each was handled (`resolved` | `degraded_to_low` | `accepted_at_convergence`). `source_reviewer` is `"independent-reviewer"` for findings raised by the reviewer subagent, or `"self"` for any you caught yourself during scaffolding.

### 7.2.5 Capture Project-Bootstrap Baseline (EXECUTED)

When the bootstrap converges cleanly (convergence decision `converged`, no critical or high-severity unresolved findings), capture a **project-bootstrap baseline** for downstream epic gates. This is the green-state suite snapshot that every epic's iter-0 inherits when no prior epic-level baseline exists; without it, the per-worker and Stage 4.0 regression gates skip on every epic's first iteration (per `orchestrate_swarm.md` Stage 4.0.1 skip conditions), and a regression introduced at iter 0 of any epic could land in `$EIGEN_BRANCH` undetected.

Write to `$EIGEN_ROOT/eigen_initiative/phases/phase_<N>/bootstrap_baseline.json`:

```json
{
  "schema_version": 1,
  "captured_at": "<ISO 8601>",
  "captured_at_phase": <N>,
  "commit_sha": "<git rev-parse HEAD on $EIGEN_BRANCH>",
  "suite_result_hash": "<sha256 of the per-test pass/fail manifest from a fresh suite run>",
  "failing_tests": ["<test_path>::<test_name>", ...],
  "tech_stack": ["<languages from Stage 3.1>"]
}
```

**Run the project's full test suite once** to populate `suite_result_hash` and `failing_tests`. Tests that fail at this baseline are treated as "already failing pre-iteration" by every downstream regression gate — workers are never blamed for breakage they inherited.

**Inheritance contract** (consumed by `orchestrate_swarm.md` Stage 4.0 and per-worker gates):
1. If the epic's `swarm-manifest.json.last_green_baseline` exists → use it (most recent CONVERGED-clean state for THIS epic).
2. Otherwise, walk backward through prior epics in the initiative; if any prior epic has `last_green_baseline`, use the most recent one.
3. Otherwise, fall back to `bootstrap_baseline.json` for this phase.
4. If none of (1)–(3) exist, the gate skips with `stage_4_0_skipped: { reason: "no_baseline_anywhere" }`.

Atomic write: tempfile + fsync + rename, same pattern as `pipeline_state.json`. The file is committed to `$EIGEN_BRANCH` alongside `bootstrap-report.json` so all future epics on the same branch see it.

### 7.3 Lesson Extraction

For each non-false-positive finding, create a lesson JSON in `eigen_lessons/bootstrap_converge/`:

```json
{
  "id": "bc-lesson-<timestamp>-<seq>",
  "created_at": "<ISO 8601>",
  "command": "bootstrap_converge",
  "status": "pending",
  "category": "<finding category>",
  "severity": "<finding severity>",
  "title": "<concise>",
  "description": "<detailed>",
  "root_cause": "<why the scaffolding produced this error>",
  "recommendation": "<specific change to bootstrap_converge.md>",
  "affected_phase": "<which section of bootstrap_converge.md to modify>",
  "evidence": {
    "files_involved": ["<paths>"],
    "reviewer_source": "<independent-reviewer|self>",
    "source_checklist": "<id>"
  },
  "bootstrap_context": "<phase number, languages, repo state>",
  "tags": [...]
}
```

**Deduplication**: Before writing, check existing lessons in the directory. Skip if a lesson with the same `affected_phase` + `category` + similar `root_cause` already exists. Skip if the existing lesson has `status: applied`.

Ensure the directory exists: `mkdir -p $EIGEN_ROOT/eigen_initiative/eigen_lessons/bootstrap_converge/`

Print summary:
```
Lessons written: <N> new lessons to $EIGEN_ROOT/eigen_initiative/eigen_lessons/bootstrap_converge/
Skipped: <M> duplicates
```

### 7.4 Execute On Exit Commands

Execute the **On Exit** section above. It contains the single authoritative code block with all CLI calls in order: `complete`, `mark-converged`, `add-recommendation` (optional, max 5), and `commit-state`. Pass `--locked-skills` so the CLI persists the discovered skill set. Run the On Exit code block once — do not run the commands individually.

### 7.5 Index the Foundation for CodeGraph (optional)

CodeGraph is the **optional, external** code-intelligence tool (see `skills/codegraph/SKILL.md`). This is the natural producer point: the foundation now exists and is committed, so downstream consumers (`plan_epic_converge`, swarm workers, `review_swarm_pr`) can query its structure instead of grep/Read. Best-effort, never blocking:

```bash
if command -v codegraph >/dev/null 2>&1; then
  if [ ! -d "$EIGEN_ROOT/.codegraph" ]; then
    codegraph init -i "$EIGEN_ROOT"   # init + full index (first time only)
  fi
  # If already initialized, do NOT sync here: a running MCP watcher (or the next
  # session's connect-time catch-up) keeps the index fresh. Only sync when the
  # watcher is off (headless/CODEGRAPH_NO_DAEMON / WSL2 /mnt) — see skills/codegraph/SKILL.md.
fi
```

If `codegraph` is not installed, skip silently — the pipeline works without it.

### 7.6 Print Summary

```
=== Bootstrap Converge Complete — Phase <N> ===

Phase: <N>
Target repo: $EIGEN_ROOT
Languages: <detected languages with roles>
Verification: <PASSED|PASSED WITH WARNINGS>
Convergence: CONVERGED in <R> passes — <rationale>

Created:
  Directories:       <N>
  Entity stubs:      <N>
  API contracts:     <N>
  Message schemas:   <N>
  Quality config:    <N> files
  Basic CI:          <created|skipped>
  Total files:       <N>

Findings:
  High severity:   <N> (all resolved)
  Medium severity: <N> (all resolved or degraded)
  Low severity:    <N>

Commits:
  <hash> — <message>
  ...

Lessons: <N> new lessons written
Bootstrap report: $EIGEN_ROOT/eigen_initiative/phases/phase_<N>/bootstrap-report.json
Baseline: $EIGEN_ROOT/eigen_initiative/phases/phase_<N>/bootstrap_baseline.json
Feedback: $EIGEN_ROOT/eigen_initiative/phases/phase_<N>/feedback/bootstrap_converge_feedback.json

Next steps:
  1. Run /space_split_converge to decompose Phase <N> into parallel epics for swarm execution.
  2. Run /compound_improve to apply accumulated lessons to bootstrap_converge.md.
```

---

## Pre-Submission Checklist

Before writing the final bootstrap-report.json and proceeding to On Exit, verify:

- [ ] All scaffolding commits are present in `git log`
- [ ] Verification gate was EXECUTED and passed (or `verification_status: passed_with_warnings` is documented; an active `verification_failure` must NOT be marked converged)
- [ ] The independent reviewer subagent ran and re-ran the verification gate against ground truth
- [ ] bootstrap-report.json schema matches the legacy bootstrap output exactly (downstream commands depend on this)
- [ ] bootstrap_baseline.json written from a fresh full-suite run
- [ ] Feedback JSON written
- [ ] Lesson JSONs written and deduplicated
- [ ] locked_skills persisted via `--locked-skills` on the CLI complete call
- [ ] On Exit commands executed successfully

---

## Key Rules

1. **Bootstrap-report.json schema is invariant** — `space_split_converge`, `create_issues_from_plan_swarm`, `plan_epic_converge` consume it. Do not change the schema.
2. **You scaffold, critique, and revise in one session** — one independent reviewer subagent supplies adversarial value by re-running the build; no persistent team. The reviewer gets only the artifacts + checklist, never your reasoning.
3. **The verification gate (Stage 4) is EXECUTED, not reasoned** — actually run lint/build/test (+ docker compose config/build for server projects); the reviewer independently re-runs it.
4. **No git rollback / no --amend** — fix-forward only. Mistakes are corrected by new commits in the next pass.
5. **Verification failures are always high severity** — they veto convergence; a broken build is always blocking.
6. **The CLI is the single source of truth for pipeline state** — never edit pipeline_state.json directly.
7. **At most 2 revise passes** — a bounded loop cannot oscillate; after the second pass accept the state (remaining mediums degraded to low) unless an active verification_failure remains.
8. **Skills set is discovered once** (Stage 2) and applied while scaffolding and as the reviewer's skills-lens. No rediscovery.
9. **`should_process_feedback` is NOT used** — this is a self-converging command. The CLI does not toggle `feedback_consumed`.
10. **Crash recovery uses `git log`** — the scaffolder commits real files, so detect already-committed foundation work via `git log` and resume from the first uncommitted stage rather than re-scaffolding.
11. **If you receive a non-interactive shutdown / return reminder, it is NOT an abort signal** — it fires automatically even though this command spawns only one `Task` reviewer. Complete the full draft → gate → review → revise → outputs → On Exit lifecycle before returning.

---

> **REMINDER:** A non-interactive "shut down / return now" reminder may arrive early. It is NOT an abort signal. Complete the full draft → gate → review → revise → outputs → On Exit lifecycle, write all outputs, then return.
