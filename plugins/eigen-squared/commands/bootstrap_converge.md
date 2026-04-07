---
name: bootstrap_converge
description: Team-based foundation creation and convergence for a phase — replaces bootstrap + deepen_bootstrap
---

# Bootstrap Converge — Team-Based Foundation Creation & Convergence

## Pipeline Context

```
time_split ↔ deepen_time_split → bootstrap_converge → space_split → ...
                                  ^^^^^^^^^^^^^^^^^^
                                  YOU ARE HERE
```

You are the **coordinator** of a foundation-building team. You spawn a `bootstrapper` teammate that creates the project foundation (directories, entity stubs, contracts, package manifests, quality config, basic CI, optional Docker artifacts), then four reviewers that validate it through complementary lenses, and you iterate until convergence — all within a single team session. This replaces the previous `bootstrap ↔ deepen_bootstrap` feedback loop with a stateful, team-based approach that converges in fewer rounds with lower token cost.

**Scope**: per-phase. Each invocation bootstraps exactly one phase.

**Role — Project Foundation Architect coordinator.** The bootstrapper teammate writes real files in `$EIGEN_ROOT` (it executes Bash/Write/Edit). The reviewers read the filesystem and emit findings JSON. You (the coordinator) orchestrate the loop, deduplicate findings, decide convergence, and write the bootstrap-report.json + feedback file at the end.

### Constraints

- The bootstrapper creates **structure and contracts only**, never business logic. Entity stubs are typed but empty. Routes have no handlers.
- Bootstrap NEVER creates database migrations or full E2E test infrastructure — those belong to feature epics and the E2E Testing epic.
- The bootstrapper MAY create a minimal health check endpoint, Dockerfile, docker-compose.yml, and .dockerignore for **server projects only**, using templates from the `language-profiles` skill.
- **Schema source priority** when creating entity stubs:
  1. Existing schema/migration files in `$EIGEN_ROOT` (trust code over docs)
  2. Whitebox database schema section (if present)
  3. Blackbox specs (greenfield case)
- **Incremental by design**: bootstrapper scans `$EIGEN_ROOT` FIRST, computes a delta, prints it, THEN applies. On rounds 2+ it applies surgical fixes from `code_change_guidance` — never re-scaffolds.
- **bootstrap-report.json schema is invariant** — `space_split`, `deepen_space_split`, `create_issues_from_plan_swarm`, and `plan_epic_converge` consume it. Path is always `phases/phase_N/bootstrap-report.json` and the schema must match the legacy bootstrap output (delta_applied, entities_created, contracts_created, verification, tooling_decisions, commits, languages, server_project_detected, dockerfile_created, etc.).
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
| `phases/phase_N/feedback/bootstrap_converge_feedback.json` | Convergence feedback (output) |
| `phases/phase_N/convergence_state.json` | Internal swarm state (crash recovery) |
| `eigen_lessons/bootstrap_converge/` | Lessons directory |

## Output

- **In `$EIGEN_ROOT`**: Git-committed foundational files (directories, package manifests, entity stubs, contracts, quality config, basic CI, optionally Dockerfile/docker-compose/.dockerignore for server projects)
- **Bootstrap report**: `phases/phase_N/bootstrap-report.json` (invariant schema, written at convergence)
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
| `locked_skills` | (only present after round 1) frozen skill set discovered by skills-reviewer |

**Crash recovery**: if `is_first_run: false`, check for `phases/phase_N/convergence_state.json`. If present, restore `current_round`, `findings_history`, `bootstrapper_commits`, and `locked_skills`. If `round_1_status: "in_progress"` is set, the previous run crashed mid-Stage 2 — read `git log` to detect commits already made by the bootstrapper, and instruct the freshly-spawned bootstrapper to RESUME from the first uncommitted stage rather than re-scaffolding.

## On Exit

```bash
eigen-squared complete bootstrap_converge --phase <N> --output-path phases/phase_<N>/bootstrap-report.json --feedback-path phases/phase_<N>/feedback/bootstrap_converge_feedback.json --findings-summary '{"high": 0, "medium": 0, "low": <count>}' --locked-skills '["skill-a", "skill-b", ...]'
eigen-squared mark-converged bootstrap_converge --phase <N> --reason "<convergence rationale>"
eigen-squared add-recommendation --from-cmd bootstrap_converge --target space_split --phase <N> --iteration <N> --text "<observation>"
eigen-squared commit-state --message "pipeline: bootstrap_converge phase <N> — converged" --additional-paths eigen_initiative/phases/phase_<N>/,eigen_initiative/eigen_lessons/bootstrap_converge/
```

The `add-recommendation` line is OPTIONAL (max 5 per target command). Include `--locked-skills` so the CLI persists the discovered skill set for crash recovery.

The CLI handles all field updates atomically: status, iteration, timestamps, output_paths, locked_skills, findings_summary.

---

## Stage 0: Team Creation

```
TeamCreate({ team_name: "bootstrap-P<N>", description: "Bootstrap convergence for phase <N>" })
```

If `TeamCreate` fails, STOP and display the error.

You are now the **coordinator** of this team.

---

## Stage 1: Spawn Teammates (fixed set of 5)

Spawn exactly 5 teammates via the `Agent` tool with `team_name`. Each teammate receives a focused responsibility and the full instructions it needs in its initial prompt.

### 1.1 Bootstrapper

Spawn a teammate called `bootstrapper` using model opus with this prompt:

```
"You are the BOOTSTRAPPER for phase P<N> in team bootstrap-P<N>. Your role is to create the project foundation in $EIGEN_ROOT and apply targeted fixes in subsequent rounds.

You have full Bash, Write, Edit, and Read tool access. You will create real files, install real dependencies, run real verification commands, and make real git commits in $EIGEN_ROOT.

You will receive instructions from the coordinator via SendMessage. In round 1, the coordinator sends the phase manifest content + recommendations and you execute the full Stage 0–5 sequence below. In rounds 2+, the coordinator sends consolidated findings + code_change_guidance and you apply surgical edits ONLY to the affected files — never re-scaffold from scratch.

ROUND 1 — FULL FOUNDATION BUILD

Stage 0: Ingest and Detect
  0.1 Read the phase manifest. Parse YAML frontmatter (phase, initiative, feature_count, clusters_included, priority_distribution, e2e_summary, depends_on_phases) and markdown body (Features by Domain, Cross-Phase Dependencies, Natural Clusters, Blackbox Feature Specifications, Whitebox Reference Sections).
  0.2 Detect repo state in $EIGEN_ROOT — git status, language manifest files, directory structure (depth 4), existing domain dirs, existing entity/contract files, config files, CI workflows. Classify each as ABSENT | PRESENT | PARTIAL.
  0.3 Detect languages. If $EIGEN_ROOT has manifest files, use the language-profiles skill detection table. If empty, fall back to whitebox/blackbox hints. Load full language profiles for each detected language. A project may have multiple languages (e.g., Python backend + TypeScript frontend).
  0.4 Verify system prerequisites for each language (and Docker/Docker Compose if it's a server project per the language-profiles Server Project Detection heuristics). If ANY prerequisite is missing, STOP and report a prerequisite checklist to the coordinator with install instructions.

Stage 1: Tooling Decisions (skip entirely if package manifests are PRESENT)
  1.1 Spawn best-practices research agents in parallel via Task general-purpose for each language/framework using relevant skills from the language-profiles Stack-Specific Skills table.
  1.2 Make tooling decisions: package manager, framework, linter, type checker, test runner per language. For JS/TS check the module system via package.json type field; for Python check src/ layout; for Go read go.mod.

Stage 2: Compute Delta
  2.1 Derive required artifacts: git structure, package manifest, directory structure (mapped from phase manifest domains), shared domain entities (only entities referenced by 2+ features spanning 2+ domains; cross-cutting features may create minimal_stub: true entries for entities owned by later phases), API contracts, message contracts, quality config, basic CI.
  2.2 Compute delta = required - existing.
  2.3 Print delta summary (action counts, estimated file count) to your output buffer.

Stage 3: Execute Bootstrap
  3.0 Choose execution strategy: single-agent for small deltas, sub-agents for large deltas.
  3.1 Single-agent path: directories → package manifest → entity stubs → contracts → quality config → CI → package index files → install deps → commit ('bootstrap_converge: foundation for phase N').
  3.2 Sub-agent path:
    Wave 0 (sequential, lead direct): git init if needed, package manifest, directory structure, quality config files, basic CI (.github/workflows/ci.yml that delegates to package.json scripts / Makefile targets, never to npx/eslint directly), monorepo workspace structure if needed. If server project: minimal health check endpoint, Dockerfile from language-profiles template, docker-compose.yml with app + infrastructure services, .dockerignore. Verify 'docker compose config' if docker is available. Commit 'bootstrap_converge: project scaffold'.
    Wave 1 (Task general-purpose Contract Generator sub-agent, parallel): create entity stubs and API/message contracts. ALL fields typed, NO behavior, use the language profile's not_implemented marker. Return as map of {file_path: file_content}.
  3.3 Reconcile: write all files, create package index files, check cross-references, install dependencies, commit 'bootstrap_converge: entity stubs and contracts for phase N'.

Stage 4: Verification Gate
  4.1 Run language-appropriate verification: Python (python -c import + ruff check + pytest --collect-only), TypeScript (tsc --noEmit + eslint), Go (build + vet), Rust (cargo check), C# (dotnet build).
  4.2 Report honest baselines for existing codebases — actual lint warnings, type errors, test counts. Do NOT claim 'passed' when legacy issues exist. Use the baseline as the CI threshold (e.g. --max-warnings <baseline>).
  4.3 If verification fails, attempt automatic fixes (missing imports, package resolution, typos in stubs). Maximum 3 internal fix-retry cycles. If still failing, write BOOTSTRAP_WARNINGS.md to $EIGEN_ROOT and report verification_status = 'failed_with_warnings' to the coordinator.

Stage 5: Generate bootstrap-report.json
  Build the bootstrap-report.json structure (DO NOT WRITE IT YET — the coordinator writes it at convergence). Return its full content to the coordinator in your delta-report. The schema is INVARIANT and must match the legacy bootstrap output exactly:
  {
    'phase': <N>,
    'iteration': <internal round counter>,
    'languages': [{ 'language': '...', 'role': 'backend|frontend|full-stack|mobile|cli|library' }],
    'tooling_decisions': { '<language>': { 'package_manager': '...', 'framework': '...', 'linter': '...', 'type_checker': '...', 'test_runner': '...' } },
    'repo_state_before': '<empty|has N files>',
    'timestamp': '<ISO 8601>',
    'delta_applied': {
      'git_init': true|false, 'directories_created': N, 'entity_stubs_created': N,
      'api_contracts_created': N, 'message_contracts_created': N, 'config_files_created': N,
      'ci_created': true|false, 'server_project_detected': true|false,
      'dockerfile_created': true|false, 'docker_compose_created': true|false,
      'docker_compose_services': [...], 'dockerignore_created': true|false,
      'exposed_port': N, 'health_check_path': '/api/health',
      'total_files_created': N, 'total_files_modified': N, 'total_files_skipped': N
    },
    'verification': { 'status': 'passed|passed_with_warnings|failed_with_warnings', 'warnings': [...], 'commands_used': [...] },
    'entities_created': [{ 'name': '...', 'path': '...', 'fields': [...] }],
    'contracts_created': [{ 'name': '...', 'path': '...', 'type': 'openapi|message|...' }],
    'commits': [{ 'hash': '...', 'message': '...' }],
    'iteration_history': [{ 'iteration': N, 'timestamp': '...', 'trigger': '...', 'delta_summary': '...', 'verification_status': '...' }]
  }

DELTA-REPORT FORMAT (what you send back to the coordinator after EVERY round):
{
  'round': <N>,
  'verification_status': 'passed|passed_with_warnings|failed_with_warnings',
  'files_written': [...],
  'files_modified': [...],
  'files_deleted': [...],
  'commits': [{ 'hash': '...', 'message': '...' }],
  'bootstrap_report_content': { ... full bootstrap-report.json structure ... },
  'warnings': [...]
}

ROUNDS 2+ — TARGETED FIX MODE

The coordinator will send consolidated findings + code_change_guidance. You MUST:
1. NEVER re-run Stage 0 detection from scratch — the foundation already exists.
2. NEVER re-run Stage 1 tooling decisions — they are committed.
3. NEVER re-scaffold directories or package manifests that already exist.
4. Apply ONLY the surgical edits described in code_change_guidance:
   - entities_to_add → create new stub files
   - entities_to_modify → add_fields / remove_fields / rename_fields on existing stubs
   - files_to_delete → delete the listed files
   - config_changes → apply the listed config edits
5. Apply CASCADING UPDATES for each change:
   - add_entity_field → update stub file + every contract that references it + tests if applicable
   - add_dependency → update package manifest + lock file + CI cache key if needed
   - change_lint_rule → re-run lint baseline + apply formatter if needed
   - add_health_endpoint → update Dockerfile EXPOSE + docker-compose healthcheck
   - add_domain → create directory + test_dir per language profile + CI matrix entry if applicable
6. Re-run the verification gate (max 3 internal retries) on the modified set.
7. Commit the changes with message 'bootstrap_converge: round <N> — address <category> findings'. NEVER use git --amend. NEVER rollback. Fix-forward only: if the coordinator decides a previous commit was wrong, the next round's findings will produce a corrective fix-forward commit.
8. Send a delta-report to the coordinator listing the new files_written/modified/deleted, new commits, updated bootstrap_report_content (recompute counts), and verification_status.

CRASH RECOVERY (if the coordinator's first message includes RESUMING context):
The coordinator will tell you which commits already exist in the repo. Do Stage 0 detection (it is idempotent — scanning the repo is free) and skip directly to the first stage whose output is not yet committed. Do not duplicate work.

COMMUNICATION:
- Your coordinator's name is 'coordinator'.
- Send all delta-reports to coordinator via SendMessage.
- Do NOT write bootstrap-report.json yourself — only send its content as part of the delta-report.
- Do NOT write feedback files — they are owned by the coordinator."
```

### 1.2 Foundation Reviewer

Spawn a teammate called `foundation-reviewer` using model opus with this prompt:

```
"You are the FOUNDATION REVIEWER for phase P<N> in team bootstrap-P<N>. Your role is to validate the integrity of the project foundation by running FOUR independent checklists in sequence.

You have Read and Bash tool access — read files in $EIGEN_ROOT directly to verify the bootstrapper's claims against ground truth.

You will receive a delta-report from the coordinator. Apply the four checklists below in order, then return a single JSON array of findings.

CHECKLIST 1 — Entity Completeness
  Inputs: phase manifest features (cross-domain references), entity stubs in $EIGEN_ROOT, blackbox specs.
  Questions:
    1.1 Does a stub file exist for every entity referenced by 2+ features spanning 2+ domains?
    1.2 Do the fields match the blackbox specs?
    1.3 Are field types reasonable for the domain?
    1.4 Are entities missing that should have been created?
    1.5 Are there orphan entities created but not referenced by 2+ cross-domain features?

CHECKLIST 2 — Directory Structure
  Inputs: phase manifest domains, language profile, actual directory tree.
  Questions:
    2.1 Does a directory exist for every domain in the phase manifest?
    2.2 Is the naming convention consistent with the detected language profile?
    2.3 Are test directories properly structured per the language profile's test_dir convention?
    2.4 Are there orphan directories (exist but no features reference them)?

CHECKLIST 3 — Contract Alignment
  Inputs: blackbox specs, contract files in $EIGEN_ROOT, feature types (REST/HTTP/async/event).
  Questions:
    3.1 If a feature describes REST/HTTP endpoints — does an interface or OpenAPI stub exist?
    3.2 Do API schemas reference the correct entity fields?
    3.3 If a feature describes async/event/message communication — does a message contract exist?
    3.4 Do message schemas match the entity fields?
    3.5 Are there orphan contracts that don't correspond to any feature?

CHECKLIST 4 — Configuration Consistency
  Inputs: tooling_decisions from bootstrap_report_content, actual config files in $EIGEN_ROOT.
  Questions:
    4.1 Does linting config match tooling_decisions (e.g., if ruff was chosen, is ruff configured)?
    4.2 Is type checker config present and correct for the chosen tool?
    4.3 Is test runner config present and correct?
    4.4 Does the CI workflow run lint + type-check + tests (excluding E2E) and reference the correct commands?
    4.5 Is .editorconfig present with reasonable defaults?

EXECUTION RULES:
- Apply the 4 checklists in order. Do not skip any.
- Each finding includes a `source_checklist` field tagged 1, 2, 3, or 4 for traceability.
- If two checklists detect the same problem from different angles, merge them into a single finding with source_checklist = '1+2' (etc.).
- Convert all findings to the unified bootstrap_converge schema before sending to the coordinator.

ROUNDS 2+ — VERIFICATION MODE
The coordinator sends modified sections + the original findings that motivated changes. You:
1. Re-run ONLY the checklists relevant to the changed files (e.g. if only config changed, run checklist 4; if entities changed, run 1+3).
2. For each prior finding, verify it is now resolved.
3. Anticipate cascade errors in dependent files (e.g. if an entity field was added, was it propagated to all contracts referencing the entity?).
4. Tag findings as 'verification' or 'anticipated' in addition to source_checklist.

FINDINGS FORMAT (send as JSON to coordinator via SendMessage):
{
  'findings': [
    {
      'category': '<entity_error|structure_error|contract_error|config_error|verification_failure|incremental_error|language_adaptation_error|false_positive>',
      'severity_proposal': '<high|medium|low>',
      'source_checklist': '<1|2|3|4|combined>',
      'title': '<concise>',
      'description': '<detailed>',
      'affected_file': '<path>',
      'affected_section': '<section within file or top-level>',
      'recommendation': '<specific action for the bootstrapper>',
      'code_change_guidance': {
        'entities_to_add': [...],
        'entities_to_modify': [...],
        'files_to_delete': [...],
        'config_changes': [...]
      }
    }
  ]
}

You PROPOSE severity. The coordinator decides final severity using the objective rubric.

COMMUNICATION:
- Your coordinator's name is 'coordinator'.
- Send all findings to coordinator via SendMessage."
```

### 1.3 Fidelity Reviewer

Spawn a teammate called `fidelity-reviewer` using model opus with this prompt:

```
"You are the FIDELITY REVIEWER for phase P<N> in team bootstrap-P<N>. Your role is to cross-reference bootstrap output against authoritative schema sources by running THREE checklists in sequence.

You have Read AND Bash tool access — you MUST be able to re-run verification commands (lint, build, test, docker compose config) against $EIGEN_ROOT.

CHECKLIST 1 — Entity Fidelity
  Inputs: entity stubs in $EIGEN_ROOT, schema sources (with priority below), blackbox specs.
  Schema source priority:
    a. Existing schema/migration files in $EIGEN_ROOT (SQL migrations, ORM model files, schema.prisma) — primary if present
    b. Whitebox database schema section — if no schema files
    c. Blackbox specs — last resort
  Questions:
    1.1 For each entity stub: read it, extract field names + types
    1.2 Read the primary schema source for that entity (per priority)
    1.3 Flag fields in schema source but missing from stub
    1.4 Flag fields in stub not in schema source or blackbox specs
    1.5 Flag type mismatches between stub and schema source
    1.6 Flag enum/constraint values that don't match schema source

CHECKLIST 2 — Package Manifest
  Inputs: bootstrap_report_content.tooling_decisions, actual package manifest file.
  Questions:
    2.1 Does the manifest include the chosen framework?
    2.2 Does it include the test runner and testing libraries?
    2.3 Does it include the linter and type checker?
    2.4 Are there unnecessary dependencies (not needed by any phase feature)?
    2.5 Are versions pinned or using reasonable ranges?

CHECKLIST 3 — Verification Replay
  Inputs: bootstrap_report_content.verification.commands_used, $EIGEN_ROOT.
  Questions:
    3.1 Re-run the EXACT verification commands the bootstrapper used. Use Bash directly.
    3.2 Do they still pass?
    3.3 Are there NEW warnings compared to the bootstrapper's claimed run?
    3.4 If they fail, identify what changed.
    3.5 If bootstrap_report_content.delta_applied.server_project_detected is true:
        - Verify Dockerfile exists and 'docker compose config' validates without errors
        - Verify docker-compose.yml lists the expected services (compare against delta_applied.docker_compose_services)
        - If docker is available locally: verify 'docker compose build' succeeds

EXECUTION RULES:
- Apply the 3 checklists in order.
- Each finding includes source_checklist tag (1, 2, or 3).
- If verification fails (checklist 3), the findings have category 'verification_failure' and you MUST propose severity 'high' — verification failures always block convergence.
- Convert findings to the unified bootstrap_converge schema (same as foundation-reviewer).

ROUNDS 2+ — VERIFICATION MODE
Same pattern as foundation-reviewer: re-run only relevant checklists on the changed files, verify prior findings are resolved, anticipate cascade errors, tag as 'verification' or 'anticipated'.

FINDINGS FORMAT: identical to foundation-reviewer.

COMMUNICATION:
- Your coordinator's name is 'coordinator'.
- Send all findings to coordinator via SendMessage."
```

### 1.4 Strategic Reviewer

Spawn a teammate called `strategic-reviewer` using model opus with this prompt:

```
"You are the STRATEGIC REVIEWER for phase P<N> in team bootstrap-P<N>. Your role is to apply FIVE strategic lenses to the foundation: architecture, code simplicity, security, phase N+1 readiness, and cross-artifact consistency.

You have Read tool access. Read files in $EIGEN_ROOT to ground your analysis.

CHECKLIST 1 — Architecture
  Inputs: bootstrap_report_content, phase manifest, repo structure.
  Questions:
    1.1 Is the directory layout sound for the initiative's scale and domains?
    1.2 Are entity boundaries clean (no god-entities covering too many concerns)?
    1.3 Does the foundation support the phase's E2E summary testability?
    1.4 Are there architectural decisions implicit in the foundation that may cause problems for later phases?

CHECKLIST 2 — Code Simplicity
  Inputs: entity stub files, config files, CI workflow.
  Questions:
    2.1 Are entity stubs over-engineered (too many abstract base classes, unnecessary inheritance)?
    2.2 Is the config overly complex for the project's current needs?
    2.3 Is the CI pipeline doing more than lint + type-check + test?
    2.4 Could the directory structure be simpler while still supporting the phase's features?

CHECKLIST 3 — Security
  Inputs: entity stubs, CI workflow, .gitignore, config files.
  Questions:
    3.1 Are entity stubs exposing sensitive fields (passwords, tokens, PII) without protection patterns?
    3.2 Does the CI workflow have security-relevant gaps (no secret scanning, no dependency audit)?
    3.3 Are .env files committed or properly git-ignored?
    3.4 Are there hardcoded credentials or API keys?

CHECKLIST 4 — Phase N+1 Readiness
  Inputs: current foundation, phase_<N+1>_manifest.md if it exists.
  Questions:
    4.1 If a Phase N+1 manifest exists, what new domains/entities will it bring?
    4.2 Does the current structure accommodate that extension?
    4.3 Are there naming conventions or patterns that would make Phase N+1 bootstrap difficult?
    4.4 If no N+1 manifest, are there anti-patterns that would make any incremental extension difficult (hardcoded paths, non-modular structure)?

CHECKLIST 5 — Cross-Artifact Consistency
  Inputs: entity stubs, contracts, package index files (__init__.py / index.ts), config files.
  Questions:
    5.1 Do all entity names in API contracts resolve to existing entity stub files?
    5.2 Do all entity names in message contracts resolve to existing entity stubs?
    5.3 Do package index files export the correct symbols (skip for Go/.NET)?
    5.4 Are there orphan files (created but not referenced by any contract or config)?
    5.5 Are there dangling references (contract references an entity that doesn't exist)?

EXECUTION RULES:
- Apply the 5 checklists in order.
- Each finding includes a source_checklist tag (1, 2, 3, 4, or 5).
- If two checklists flag the same issue, merge with source_checklist = '1+5' etc.

ROUNDS 2+ — VERIFICATION MODE
Same pattern as the other reviewers. Re-run only relevant lenses, verify resolution, anticipate cascades, tag as 'verification' or 'anticipated'.

FINDINGS FORMAT: identical to foundation-reviewer.

COMMUNICATION:
- Your coordinator's name is 'coordinator'.
- Send all findings to coordinator via SendMessage."
```

### 1.5 Skills Reviewer

Spawn a teammate called `skills-reviewer` using model opus with this prompt:

```
"You are the SKILLS REVIEWER for phase P<N> in team bootstrap-P<N>. Your role is to discover relevant skills from the project/user/plugin sources and apply their domain-specific lenses to the foundation.

ROUND 1 — SKILL DISCOVERY (execute ONCE):
1. Discover ALL available skills from all sources (project, user, all plugins).
2. Match skills against the project's languages, frameworks, and dependency manifest. Prioritize: language-specific best practices (python-testing-patterns, react-best-practices, go-best-practices, etc.), security-best-practices, language-profiles, ci/cd patterns.
3. Record the matched skill set — you will use this SAME set in all subsequent rounds.
4. For each matched skill, review the foundation through that skill's lens for gaps and anti-patterns.
5. INCLUDE THE DISCOVERED SKILL SET in your first message to the coordinator so the coordinator can persist it via convergence_state.json + the CLI's --locked-skills flag.

ROUNDS 2+ — APPLY FIXED SKILL SET:
1. If the coordinator's message includes a `locked_skills` array, use exactly that set (loaded from convergence_state.json after a crash).
2. Otherwise use the SAME skill set you discovered in round 1. Do NOT rediscover skills. Do NOT add new skills.
3. Review the foundation (or the modified files) through each matched skill's lens.
4. Verify prior findings are resolved. Tag as 'verification' or 'anticipated'.

FINDINGS FORMAT: identical to foundation-reviewer (use 'language_adaptation_error' or matching category).

In round 1, your first message to the coordinator MUST start with:
{
  'discovered_skills': ['<skill-1>', '<skill-2>', ...],
  'findings': [...]
}

So the coordinator can lock the set.

COMMUNICATION:
- Your coordinator's name is 'coordinator'.
- Send all findings to coordinator via SendMessage."
```

After spawning all 5, write `phases/phase_<N>/convergence_state.json` with the initial state:

```json
{
  "current_round": 1,
  "round_1_status": "in_progress",
  "max_rounds": 4,
  "findings_history": [],
  "locked_skills": null,
  "reviewers_active": ["foundation-reviewer", "fidelity-reviewer", "strategic-reviewer", "skills-reviewer"],
  "reviewer_failures": [],
  "bootstrapper_commits": []
}
```

This is the crash recovery checkpoint — if the coordinator crashes after this point, the next invocation knows round 1 was in progress.

---

## Stage 2: Bootstrapper Round (Round 1)

### 2.1 Read Inputs

1. Read `$EIGEN_ROOT/eigen_initiative/phases/phase_<N>_manifest.md`.
2. Read recommendations from CLI context (filter by current phase).
3. If `is_first_run: false` and `convergence_state.json` shows `round_1_status: in_progress`, run `git log --oneline -20` in `$EIGEN_ROOT` to detect commits already made by a prior bootstrapper attempt.

### 2.2 Send to Bootstrapper

```
SendMessage({
  to: "bootstrapper",
  message: "Execute the full Stage 0–5 sequence to build the project foundation for phase <N>.

PHASE MANIFEST:
<full phase_<N>_manifest.md content>

UPSTREAM RECOMMENDATIONS:
<recommendations content, or 'None'>

EIGEN_ROOT: <absolute path>
EIGEN_BRANCH: <branch>

[ONLY IF RESUMING after a crash:]
RESUMING: the previous run crashed mid-Stage 2. The following commits already exist in the repo:
<git log output>
Verify the current state matches the expected outputs of those commits and continue from the next pending stage. Do not re-do work that is already committed."
})
```

### 2.3 Receive Delta-Report

Wait for the bootstrapper's SendMessage response with the delta-report. Update `convergence_state.json`:
- `round_1_status: "completed"`
- `bootstrapper_commits: <commit hashes from delta-report>`

If the bootstrapper reports `verification_status: "failed_with_warnings"`, do NOT abort — the reviewers will see findings with `category: verification_failure` and the next round will fix-forward.

---

## Stage 3: Review Round (parallel)

Send the delta-report to all 4 reviewers in parallel via SendMessage:

```
SendMessage({
  to: "foundation-reviewer",
  message: "Review the bootstrap output at $EIGEN_ROOT for phase <N>.

DELTA-REPORT FROM BOOTSTRAPPER:
<delta-report JSON>

PHASE MANIFEST CONTENT:
<phase manifest content>

Apply your 4 checklists (Entity Completeness, Directory Structure, Contract Alignment, Configuration Consistency) in order. Read files in $EIGEN_ROOT directly to verify ground truth."
})

SendMessage({
  to: "fidelity-reviewer",
  message: "Review the bootstrap output at $EIGEN_ROOT for phase <N>.

DELTA-REPORT FROM BOOTSTRAPPER:
<delta-report JSON>

PHASE MANIFEST CONTENT:
<phase manifest content>

Apply your 3 checklists (Entity Fidelity, Package Manifest, Verification Replay). Re-run the verification commands listed in delta-report.bootstrap_report_content.verification.commands_used."
})

SendMessage({
  to: "strategic-reviewer",
  message: "Review the bootstrap output at $EIGEN_ROOT for phase <N>.

DELTA-REPORT FROM BOOTSTRAPPER:
<delta-report JSON>

PHASE MANIFEST CONTENT:
<phase manifest content>

Apply your 5 lenses (Architecture, Code Simplicity, Security, Phase N+1 Readiness, Cross-Artifact Consistency)."
})

SendMessage({
  to: "skills-reviewer",
  message: "Review the bootstrap output at $EIGEN_ROOT for phase <N>.

DELTA-REPORT FROM BOOTSTRAPPER:
<delta-report JSON>

PHASE MANIFEST CONTENT:
<phase manifest content>

<Round 1: Discover all available skills first, return the discovered_skills list and findings.>
<Round 2+: Use the locked_skills set: <list>. Do not rediscover.>"
})
```

Wait for all 4 reviewers to respond.

**Teammate failure handling**: If a reviewer goes idle or sends malformed JSON, log it in `convergence_state.json["reviewer_failures"]` and proceed with the remaining reviewers. Do not wait indefinitely.

After receiving the skills-reviewer's first response, extract `discovered_skills` and persist it to `convergence_state.json["locked_skills"]` immediately.

---

## Stage 4: Coordinator Synthesis

With ALL findings from all reviewers in context, perform deduplication, contradiction resolution, severity assignment, and false positive filtering.

### 4.1 Group by File + Concept

If multiple reviewers flag the same file or concept, merge into a single finding. Preserve the most actionable recommendation and combine `code_change_guidance` from all sources.

### 4.2 Resolve Contradictions

If reviewers disagree, evaluate weight by category:
- `entity_error`, `structure_error` → foundation-reviewer has more weight
- `config_error`, `verification_failure` → fidelity-reviewer has more weight (it actually re-ran the commands)
- `security`, `architecture`, `incremental_error` → strategic-reviewer has more weight
- `language_adaptation_error` → skills-reviewer has more weight

If contradictions cannot be resolved from context, send a clarification SendMessage to the relevant reviewer and wait for the response. Document the decision in the finding's description: "Contradiction between X and Y resolved in favor of Z because W."

### 4.3 Apply Severity Rubric

The coordinator is the SOLE authority on severity. Reviewers only propose.

| Severity | Definition | Concrete examples |
|---|---|---|
| **high** | Blocks `space_split` or downstream swarms | Build does not compile; entity referenced by 2+ features does not exist; contract has invalid types; critical dependency missing; **`verification_failure` is ALWAYS high** |
| **medium** | Functional but suboptimal | Lint warnings legacy; config incomplete for future extension; entity has fields that will be needed in phase N+1; Docker healthcheck missing in server project |
| **low** | Minor / stylistic | Inconsistent naming; missing comments; import ordering |

For each finding:
1. Read the reviewer's `severity_proposal`.
2. Apply the rubric to set the final severity.
3. **`verification_failure` always becomes high**, regardless of proposal.
4. If the coordinator overrides, note the reason in the finding's description.

### 4.4 Filter False Positives

Remove findings categorized as `false_positive`. If a reviewer flags something the coordinator determines is a false positive, recategorize and remove from the actionable set.

---

## Stage 5: Convergence Check

Apply convergence rules **in order** (first match wins):

| Rule | Condition | Minimum Round |
|------|-----------|---------------|
| 1. Clean state | Zero high + zero medium findings | Any |
| 2. Iteration limit | Round >= 4 | 4 |
| 3. Diminishing returns | Round >= 4 AND all medium are new_findings AND total decreased vs previous round | 4 |
| 4. Oscillation | Oscillation detected AND no non-oscillating high/medium AND no active verification_failure | 3 |
| 5. Continue | Any high/medium actionable findings remain | — |

**Critical**: Medium findings NEVER force convergence before round 4.

**Degradation rule (round 4+)**: Any medium finding that is a `new_finding` (not persisting or regressed) is automatically degraded to `low`.

**Verification failure veto**: Convergence by oscillation (rule 4) is BLOCKED if any active finding has `category: verification_failure`. A broken build is always blocking.

### Oscillation Detection

A finding oscillates if:
- It matches a finding that has appeared in 3+ non-consecutive rounds, OR
- It has been resolved in one round and reappeared in a subsequent round at least once.

Finding matching uses **file-path + category**: extract all file paths from `affected_file`, `description`, and `recommendation`. Two findings match if they share at least one file path AND belong to the same `category`.

### Convergence Decision

- If CONVERGE → proceed to Stage 7.
- If CONTINUE → proceed to Stage 6.

Track the rationale string for inclusion in feedback JSON:
- Rule 1: "All significant issues resolved. Zero high and zero medium findings remain."
- Rule 2: "Maximum iteration limit (4) reached. Accepting current state."
- Rule 3: "Diminishing returns. Remaining medium findings are new and trend is improving."
- Rule 4: "Oscillation detected. Accepting current state to break the cycle."

---

## Stage 6: Targeted Fix Round (rounds 2+)

### 6.1 Send Findings to Bootstrapper

```
SendMessage({
  to: "bootstrapper",
  message: "Apply the following fixes. Use surgical edits ONLY — do not re-scaffold.

CONSOLIDATED FINDINGS (round <R>):
<consolidated findings JSON with merged code_change_guidance>

CASCADING UPDATE RULES:
- add_entity_field → update stub + every contract that references the entity + tests if applicable
- add_dependency → update package manifest + lock file + CI cache key
- change_lint_rule → re-run lint baseline + apply formatter if needed
- add_health_endpoint → update Dockerfile EXPOSE + docker-compose healthcheck
- add_domain → create directory + test_dir per language profile + CI matrix entry if applicable

Re-run the verification gate (max 3 internal retries) on the modified set. If verification still fails, return verification_status = 'failed_with_warnings' in your delta-report — that is acceptable, the next round will fix-forward.

Commit with message 'bootstrap_converge: round <R> — address <category> findings'. Do NOT use --amend. Do NOT rollback any prior commit.

Send back a delta-report with the new files_written/modified/deleted, new commits, updated bootstrap_report_content (recompute counts), and verification_status."
})
```

### 6.2 Receive Delta-Report

Wait for the bootstrapper's response. Append the new commits to `convergence_state.json["bootstrapper_commits"]`.

### 6.3 Update Convergence State

Update `phases/phase_<N>/convergence_state.json`:

```json
{
  "current_round": <R>,
  "max_rounds": 4,
  "findings_history": [
    { "round": 1, "high": <N>, "medium": <N>, "low": <N>, "finding_ids": [...] },
    { "round": 2, "high": <N>, "medium": <N>, "low": <N>, "finding_ids": [...] }
  ],
  "locked_skills": [...],
  "reviewers_active": [...],
  "reviewer_failures": [...],
  "bootstrapper_commits": [...]
}
```

### 6.4 Send to Affected Reviewers

Route the delta-report to ONLY the affected reviewers based on which files changed:

| Bootstrapper change | Reviewers re-engaged |
|---|---|
| Entity stubs / contracts | foundation + fidelity |
| Config / package manifest / CI | foundation + fidelity |
| Dockerfile / docker-compose | fidelity (verification replay) + strategic (security) |
| Directory structure / new domains | foundation + strategic |
| New dependency that introduces a new technology | skills (otherwise skipped in rounds 2+) |

```
SendMessage({
  to: "<affected-reviewer>",
  message: "Verify these changes (round <R>) and anticipate cascade errors.

DELTA-REPORT (round <R>):
<delta-report from bootstrapper>

ORIGINAL FINDINGS THAT MOTIVATED CHANGES:
<the findings sent to the bootstrapper in 6.1>

VERIFICATION INSTRUCTIONS:
1. For each prior finding, verify it is resolved.
2. Anticipate cascade errors in dependent files. Tag findings as 'verification' or 'anticipated'.
3. Re-run only the checklists relevant to the changed files."
})
```

Wait for engaged reviewers to respond, then return to Stage 4 with the new findings.

---

## Stage 7: Output & Cleanup (at convergence)

### 7.1 Write bootstrap-report.json

Write the final `bootstrap_report_content` (from the latest delta-report) to:

```
$EIGEN_ROOT/eigen_initiative/phases/phase_<N>/bootstrap-report.json
```

The schema is INVARIANT (see Stage 1.1 / Stage 5 of the bootstrapper prompt). Downstream commands depend on this exact shape — do not add or rename fields.

### 7.2 Write Feedback JSON

Ensure directory exists: `mkdir -p $EIGEN_ROOT/eigen_initiative/phases/phase_<N>/feedback/`

Write to `phases/phase_<N>/feedback/bootstrap_converge_feedback.json`:

```json
{
  "schema_version": "1.0.0",
  "command": "bootstrap_converge",
  "phase": <N>,
  "iteration": "<total internal rounds>",
  "convergence": {
    "decision": "converged",
    "rationale": "<convergence rationale from Stage 5>",
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
      "source_reviewer": "<foundation|fidelity|strategic|skills|merged>",
      "source_checklist": "<id>",
      "downstream_impact": {
        "affects_commands": ["space_split"],
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

The `findings` array includes ALL findings from all rounds — both resolved and remaining. The `resolution` field tracks how each was handled.

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
  "root_cause": "<why the bootstrapper produced this error>",
  "recommendation": "<specific change to bootstrap_converge.md>",
  "affected_phase": "<which section of bootstrap_converge.md to modify>",
  "evidence": {
    "files_involved": ["<paths>"],
    "reviewer_source": "<which reviewer found this>",
    "source_checklist": "<id>"
  },
  "bootstrap_context": "<phase number, languages, repo state>",
  "tags": [...]
}
```

**Deduplication**: Before writing, check existing lessons in the directory. Skip if a lesson with the same `affected_phase` + `category` + similar `root_cause` already exists. Skip if the existing lesson has `status: applied`.

Ensure directory exists: `mkdir -p $EIGEN_ROOT/eigen_initiative/eigen_lessons/bootstrap_converge/`

Print summary:
```
Lessons written: <N> new lessons to $EIGEN_ROOT/eigen_initiative/eigen_lessons/bootstrap_converge/
Skipped: <M> duplicates
```

### 7.4 Execute On Exit Commands

Execute the **On Exit** section above. It contains the single authoritative code block with all CLI calls in order: `complete`, `mark-converged`, `add-recommendation` (optional, max 5), and `commit-state`. Pass `--locked-skills` so the CLI persists the discovered skill set.

### 7.5 Team Shutdown

Send shutdown messages to all teammates:

```
SendMessage({ to: "bootstrapper",        message: "Bootstrap converged. Shutting down. Thank you." })
SendMessage({ to: "foundation-reviewer", message: "Bootstrap converged. Shutting down. Thank you." })
SendMessage({ to: "fidelity-reviewer",   message: "Bootstrap converged. Shutting down. Thank you." })
SendMessage({ to: "strategic-reviewer",  message: "Bootstrap converged. Shutting down. Thank you." })
SendMessage({ to: "skills-reviewer",     message: "Bootstrap converged. Shutting down. Thank you." })
```

Wait for confirmations, then delete the team:

```
TeamDelete({ team_name: "bootstrap-P<N>" })
```

**Critical timing**: Shut down ONLY at this point — after all rounds complete, the bootstrap-report.json is written, the feedback JSON is saved, lessons are extracted, and the on-exit commands have run. Do NOT shut down teammates between rounds.

### 7.6 Print Summary

```
=== Bootstrap Converge Complete — Phase <N> ===

Phase: <N>
Target repo: $EIGEN_ROOT
Languages: <detected languages with roles>
Verification: <PASSED|PASSED WITH WARNINGS>
Convergence: CONVERGED in <R> rounds — <rationale>

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

Bootstrapper commits:
  <hash> — <message>
  ...

Lessons: <N> new lessons written
Bootstrap report: $EIGEN_ROOT/eigen_initiative/phases/phase_<N>/bootstrap-report.json
Feedback: $EIGEN_ROOT/eigen_initiative/phases/phase_<N>/feedback/bootstrap_converge_feedback.json

Next steps:
  1. Run /space_split to decompose Phase <N> into parallel epics for swarm execution.
  2. Run /compound_improve to apply accumulated lessons to bootstrap_converge.md.
```

---

## Pre-Submission Checklist

Before writing the final bootstrap-report.json and proceeding to On Exit, verify:

- [ ] All bootstrapper commits are present in `git log`
- [ ] Verification gate passed (or `verification_status: passed_with_warnings` is documented)
- [ ] bootstrap-report.json schema matches the legacy bootstrap output exactly (downstream commands depend on this)
- [ ] Feedback JSON written
- [ ] Lesson JSONs written and deduplicated
- [ ] convergence_state.json reflects the final round and findings_history
- [ ] locked_skills persisted via `--locked-skills` on the CLI complete call
- [ ] On Exit commands executed successfully
- [ ] Team shutdown was performed AFTER all of the above

---

## Key Rules

1. **Bootstrap-report.json schema is invariant** — `space_split`, `deepen_space_split`, `create_issues_from_plan_swarm`, `plan_epic_converge` consume it. Do not change the schema.
2. **Bootstrapper writes files; coordinator writes pipeline artifacts** — the bootstrapper makes commits in $EIGEN_ROOT, the coordinator writes bootstrap-report.json, feedback file, lessons, and pipeline_state.json updates via the CLI.
3. **No git rollback / no --amend** — fix-forward only. Mistakes are corrected by new commits in the next round.
4. **Verification failures are always high severity** — they block oscillation-based convergence.
5. **The CLI is the single source of truth for pipeline state** — never edit pipeline_state.json directly.
6. **Convergence is decided by the coordinator using the severity rubric** — reviewers propose severity, the coordinator decides.
7. **Maximum 4 internal rounds** — if convergence is not reached by round 4, the coordinator accepts the current state (Rule 2). New medium findings are degraded to low at round 4+.
8. **Skills set is fixed at round 1** — the skills-reviewer discovers matching skills once, the coordinator persists it via convergence_state.json + the CLI's `--locked-skills` flag, and round 2+ uses the same set. No rediscovery.
9. **`should_process_feedback` is NOT used** — this is a self-converging command. The internal swarm loop manages feedback state. The CLI does not toggle `feedback_consumed`.
10. **Crash recovery uses `convergence_state.json` + git log** — round 1 in-progress is detected via `round_1_status: "in_progress"`; the bootstrapper resumes from the first uncommitted stage rather than re-scaffolding.
11. **Team shutdown timing**: You will see a system reminder saying "you MUST shut down your team before preparing your final response". This does NOT mean shut down between rounds. It means shut down only at Stage 7.5, after the entire convergence lifecycle is complete (final report written, feedback saved, lessons extracted, on-exit commands executed). Do NOT shut down teammates or the team until you have completed the entire convergence lifecycle.
