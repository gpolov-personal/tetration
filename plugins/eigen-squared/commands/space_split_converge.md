---
name: space_split_converge
description: Team-based phase decomposition into epics with internal convergence — replaces space_split + deepen_space_split
---

# Space Split Converge — Team-Based Epic Decomposition & Convergence

## Pipeline Context

```
time_split ↔ deepen_time_split → bootstrap_converge → space_split_converge → plan_epic_converge → ...
                                                       ^^^^^^^^^^^^^^^^^^^^
                                                       YOU ARE HERE
```

You are the **coordinator** of an epic-decomposition team. You spawn a `space-splitter` teammate that decomposes a phase manifest into sequentially ordered epics (with epic.md files, epic_manifest.json, phase_e2e_config.json), then four reviewers that validate the decomposition through complementary lenses, and you iterate until convergence — all within a single team session. This replaces the previous `space_split ↔ deepen_space_split` feedback loop with a stateful, team-based approach that converges in fewer rounds with lower token cost.

**Scope**: per-phase. Each invocation decomposes exactly one phase into its epics.

**Role — Epic Architect coordinator.** The space-splitter teammate writes real epic files in `$EIGEN_ROOT` (it executes Bash/Write/Edit and makes git commits). The reviewers read the filesystem and emit findings JSON. You (the coordinator) orchestrate the loop, deduplicate findings, decide convergence, and write the feedback file + lessons at the end. The space-split-report.json equivalent (epic_manifest.json + phase_e2e_config.json + epic.md files) is written by the splitter directly because downstream commands consume those exact paths.

### Constraints

- The space-splitter creates **epic decompositions only**, never application code, plans, or swarm manifests. That is the job of `/plan_epic_converge`, `/create_issues_from_plan_swarm`, and `/orchestrate_swarm`.
- **Cluster integrity**: strongly prefer keeping all features in a cluster within the same epic. Only split a cluster across sequential epics if there is a compelling reason (e.g., earlier epic provides interfaces consumed by later one).
- **Epic sizing**: each epic is a meaningful unit of work — not so small that planning overhead dominates, not so large that a single swarm can't handle it.
- **Bootstrap MUST be converged** before this command runs. The space-splitter reads `bootstrap-report.json` for entity paths and tooling decisions.
- **E2E Testing epic is always last**, with `features: []` and infrastructure_requirements derived from `bootstrap-report.json` → `delta_applied` (Docker compose services, exposed port, health check path).
- **Invariant artifacts** — these schemas are consumed by downstream commands and MUST NOT change shape:
  - `phases/phase_N/epic_manifest.json` (consumed by `plan_epic_converge`, `create_issues_from_plan_swarm`, `orchestrate_swarm`, `eigen_continue`, `review_swarm_pr`, `cli/epic_manifest.py`)
  - `phases/phase_N/phase_e2e_config.json` (consumed by `eigen_continue`, `e2e_validation_swarm`, `create_issues_from_plan_swarm`)
  - `phases/phase_N/epic_M/epic.md` per epic (consumed by `plan_epic_converge` and downstream review)
  - `eigen_initiative/_index.md` (human-facing summary)
- **Cross-source consistency rule**: every interface that appears in an epic.md "Epic Outputs" section must have its corresponding entry in `epic_manifest.json` `interfaces_provided[]`, and vice versa. The space-splitter's verification gate enforces this.
- **pipeline_state.json is the single source of truth** — per-phase converge state lives at `state.phases[N].space_split_converge`.
- **Feedback file**: `phases/phase_N/feedback/space_split_converge_feedback.json` — owned by this command, no other command writes to it.

## Environment

Verify before proceeding:

- [ ] `$EIGEN_ROOT` is set and points to an existing directory
- [ ] `$EIGEN_BRANCH` is set (the default branch from which all work starts)
- [ ] The `eigen-squared` CLI is available on `PATH`
- [ ] `phases/phase_N/bootstrap-report.json` exists (bootstrap_converge must have run)

If any prerequisite is missing, **STOP** and print the appropriate error.

**Key paths** (relative to `$EIGEN_ROOT/eigen_initiative/`):

| Path | Description |
|------|-------------|
| `phases/phase_N_manifest.md` | Phase manifest (input) |
| `phases/phase_N/bootstrap-report.json` | Bootstrap report (input, prerequisite) |
| `phases/phase_N/epic_M/epic.md` | Epic definition file (output, one per epic, invariant schema) |
| `phases/phase_N/epic_manifest.json` | Epic manifest (output, invariant schema) |
| `phases/phase_N/phase_e2e_config.json` | Phase E2E config (output, invariant schema) |
| `_index.md` | Initiative index (output, merged across phases) |
| `phases/phase_N/feedback/space_split_converge_feedback.json` | Convergence feedback (output) |
| `phases/phase_N/convergence_state.json` | Internal swarm state (crash recovery) |
| `eigen_lessons/space_split_converge/` | Lessons directory |

## Output

- **In `$EIGEN_ROOT/eigen_initiative/phases/phase_N/`**: Git-committed epic files, epic_manifest.json, phase_e2e_config.json (all written by the space-splitter teammate)
- **In `$EIGEN_ROOT/eigen_initiative/`**: Updated `_index.md`
- **Feedback file**: `phases/phase_N/feedback/space_split_converge_feedback.json` (rounds + findings + resolution)
- **Lessons**: `eigen_lessons/space_split_converge/*.json` (one per non-false-positive finding)

---

## On Entry

```bash
eigen-squared get-context space_split_converge --json
```

If the CLI exits with an error (non-zero), STOP and display the error message. Otherwise parse the returned JSON. Example:

```json
{
  "command": "space_split_converge",
  "branch": "main",
  "paths_relative_to": "$EIGEN_ROOT/eigen_initiative/",
  "phase": 1,
  "iteration": 1,
  "current_iteration": 0,
  "is_first_run": true,
  "output_paths": {},
  "phase_manifest": "phases/phase_1_manifest.md",
  "lessons_dir": "eigen_lessons/space_split_converge/",
  "recommendations": []
}
```

| Field | Use |
|---|---|
| `phase` | Which phase to decompose (N throughout this document) |
| `iteration` | The iteration about to be produced |
| `current_iteration` | The iteration already produced |
| `is_first_run` | `true` → no prior run; proceed to Stage 0. `false` → crash recovery (see below) |
| `output_paths` | Existing output paths recorded in pipeline state |
| `phase_manifest` | Relative path to the phase manifest |
| `lessons_dir` | Relative path to the lessons directory |
| `recommendations` | Advisory observations from upstream `bootstrap_converge` and `deepen_time_split` |
| `locked_skills` | (only present after round 1) frozen skill set discovered by skills-reviewer |

**Crash recovery**: if `is_first_run: false`, check for `phases/phase_N/convergence_state.json`. If present, restore `current_round`, `findings_history`, `splitter_commits`, and `locked_skills`. If `round_1_status: "in_progress"` is set, the previous run crashed mid-Stage 2 — read `git log` to detect commits already made by the space-splitter, and instruct the freshly-spawned space-splitter to RESUME from the first uncommitted stage rather than re-decomposing from scratch.

## On Exit

```bash
eigen-squared complete space_split_converge --phase <N> --epic-manifest phases/phase_<N>/epic_manifest.json --e2e-config phases/phase_<N>/phase_e2e_config.json --epic-ids '["P<N>.E1", "P<N>.E2", ...]' --feedback-path phases/phase_<N>/feedback/space_split_converge_feedback.json --findings-summary '{"high": 0, "medium": 0, "low": <count>}' --locked-skills '["skill-a", "skill-b", ...]'
eigen-squared mark-converged space_split_converge --phase <N> --reason "<convergence rationale>"
eigen-squared add-recommendation --from-cmd space_split_converge --target plan_epic_converge --phase <N> --iteration <N> --text "<observation>"
eigen-squared commit-state --message "pipeline: space_split_converge phase <N> — converged" --additional-paths eigen_initiative/phases/phase_<N>/,eigen_initiative/_index.md,eigen_initiative/eigen_lessons/space_split_converge/
```

The `add-recommendation` line is OPTIONAL (max 5 per target command). Include `--locked-skills` so the CLI persists the discovered skill set for crash recovery. The CLI handles all field updates atomically: status, iteration, timestamps, output_paths, locked_skills, findings_summary.

---

## Stage 0: Team Creation

```
TeamCreate({ team_name: "space-split-P<N>", description: "Space split convergence for phase <N>" })
```

If `TeamCreate` fails, STOP and display the error.

You are now the **coordinator** of this team.

---

## Stage 1: Spawn Teammates (fixed set of 5)

Spawn exactly 5 teammates via the `Agent` tool with `team_name`. Each teammate receives a focused responsibility and the full instructions it needs in its initial prompt.

### 1.1 Space-Splitter

Spawn a teammate called `space-splitter` using model opus with this prompt:

```
"You are the SPACE-SPLITTER for phase P<N> in team space-split-P<N>. Your role is to decompose the phase manifest into sequentially ordered epics and apply targeted fixes in subsequent rounds.

You have full Bash, Write, Edit, and Read tool access. You will create real epic files, write real JSON manifests, and make real git commits in $EIGEN_ROOT.

You will receive instructions from the coordinator via SendMessage. In round 1, the coordinator sends the phase manifest content + bootstrap report + recommendations and you execute the full Stage 0–4 sequence below. In rounds 2+, the coordinator sends consolidated findings + code_change_guidance and you apply surgical edits ONLY to the affected epic files / manifest entries — never re-decompose from scratch.

ROUND 1 — FULL EPIC DECOMPOSITION

Stage 0: Ingest
  0.1 Read $EIGEN_ROOT/eigen_initiative/phases/phase_<N>_manifest.md. Parse YAML frontmatter (phase, initiative, feature_count, clusters_included, priority_distribution, e2e_summary, depends_on_phases).
  0.2 Parse markdown body: Features by Domain (build feature_id → {name, priority, local_deps, cross_phase_deps, cluster, domain}), Cross-Phase Dependencies, Natural Clusters, Blackbox Feature Specifications (per-feature spec text), Whitebox Reference Sections (may be absent).
  0.3 Read $EIGEN_ROOT/eigen_initiative/phases/phase_<N>/bootstrap-report.json. Extract languages, tooling_decisions, entities_created (build EntityClassName → file_path map), delta_applied (Docker artifacts, exposed_port, health_check_path, docker_compose_services), verification status.
  0.4 Validate that feature count matches frontmatter. Warn if mismatched.
  0.5 If resuming after a crash, the coordinator will pass a RESUMING block with prior commits — verify the current state of $EIGEN_ROOT and skip directly to the first stage whose output is not yet committed.

Stage 1: Build Local DAG & Form Epics
  1.1 Build local dependency DAG from feature local_deps. Cross-phase deps are NOT edges (already-available inputs). Compute local roots, leaves, critical paths.
  1.2 Form epic candidates:
       a. Each cluster → one epic candidate (preserve cluster integrity)
       b. Group unclustered features by (domain + dependency chain)
       c. Merge small candidates with closest related epic
       d. Split overly large candidates by sub-domain or dependency depth
  1.3 Order epics sequentially: for each pair (E_a, E_b), if any feature in E_b depends on a feature in E_a, E_a comes before E_b. Number E1, E2, ..., EN. Topological sort.
  1.4 Define epic outputs (interfaces_provided[]): for each cross-epic dependency, classify as Shared Infrastructure (NOT an interface — skip) or API Contract (IS an interface). For each API Contract: define interface_name, provider_epic, provider_features, contract description, concrete_files (look up in entity file map from bootstrap-report).

Stage 2: Create Epic Files
  2.0 Add the E2E Testing epic as the last epic (M = feature_epic_count + 1, ID P<N>.E<M>, features=[]).
  2.1 For each epic (in order, including E2E Testing):
       a. mkdir -p $EIGEN_ROOT/eigen_initiative/phases/phase_<N>/epic_<M>/
       b. Write phase_<N>/epic_<M>/epic.md with the EXACT INVARIANT SCHEMA:
          - YAML frontmatter: id, title, type, state, labels, phase, epic_number, features, feature_count, clusters_included, task_ids: [], created_at, updated_at
          - Body sections IN ORDER: Epic Header, Features Table (ID/Name/Priority/Dependencies), Validation Criteria, Epic Outputs (interfaces with concrete_files), Blackbox Feature Specifications (FULL VERBATIM specs from phase manifest — do NOT truncate), Whitebox Implementation Guidance (optional, only if phase manifest has whitebox), Bootstrap Context (language, tooling, entity stubs with file paths, repository structure), Comments (empty)
  2.2 For the E2E Testing epic specifically: features: [], empty Features table, Validation Criteria describes phase-level E2E flows, Blackbox Feature Specifications references acceptance criteria from ALL epics (summarized), add Infrastructure Requirements section. If bootstrap-report.delta_applied.dockerfile_created is true: test_environment=container_parity, services from delta_applied.docker_compose_services, health_check from exposed_port + health_check_path, startup_command='docker compose up -d --wait', teardown_command='docker compose down -v'. Otherwise test_environment=external_services with empty service fields.
  2.3 For provider epics: append to '## Comments' section: 'Provides interfaces to P<N>.E<M>: <consumer_epic_name>.'
  2.4 Update $EIGEN_ROOT/eigen_initiative/_index.md: regenerate or merge — if it already exists with content from other phases, preserve those entries and update only this phase's table.

Stage 3: Generate Phase-Level Artifacts
  3.0 Ensure feedback dir exists: mkdir -p $EIGEN_ROOT/eigen_initiative/phases/phase_<N>/feedback/
  3.1 Write phase_<N>/epic_manifest.json with the INVARIANT SCHEMA:
      {
        'phase': <N>,
        'iteration': <internal round counter>,
        'initiative': '<name>',
        'epic_count': <count>,
        'execution_order': ['P<N>.E1', 'P<N>.E2', ..., 'P<N>.E<last>'],
        'cross_phase_inputs': [{ 'feature_id': '<id>', 'from_phase': <N>, 'description': '...' }],
        'epics': [
          {
            'id': 'P<N>.E<M>',
            'epic_number': <M>,
            'local_path': 'phases/phase_<N>/epic_<M>/',
            'name': '<name>',
            'description': '<brief>',
            'features': ['<feature ids>'],
            'clusters_included': ['<cluster ids>'],
            'interfaces_provided': [
              { 'interface_name': '...', 'consumer_epics': ['P<N>.E<M+k>'], 'contract': '...', 'concrete_files': ['<paths>'] }
            ],
            'validation_summary': '...'
          }
        ],
        'phase_e2e_test': '<phase-level E2E test description>',
        'created_at': '<ISO 8601>'
      }
  3.2 Write phase_<N>/phase_e2e_config.json with the INVARIANT SCHEMA:
      {
        'phase': <N>,
        'phase_e2e_test': '<description>',
        'epic_validation_scenarios': [
          { 'epic_id': 'P<N>.E<M>', 'scenarios': [{ 'name': '...', 'description': '...', 'test_type': 'api|browser|mobile|pipeline|full_stack', 'features_involved': [...], 'acceptance_criteria': [...] }] }
        ],
        'phase_e2e_scenarios': [
          { 'name': 'phase_<N>_full_flow', 'description': '...', 'test_type': '...', 'epics_involved': [...], 'acceptance_criteria': [...] }
        ],
        'infrastructure_requirements': {
          'test_types_detected': [...],
          'test_environment': 'container_parity|external_services',
          'needs_docker': bool, 'needs_emulator': bool, 'needs_browser_automation': bool,
          'compose_file': '...', 'startup_command': '...', 'health_check': '...', 'teardown_command': '...',
          'services': [...], 'notes': '...'
        }
      }
  3.3 Classify test_type per scenario using these heuristics:
       - mobile: domain mentions app/screen/navigation/iOS/Android
       - browser: domain mentions frontend/UI/dashboard/page/view (web)
       - pipeline: domain mentions ingestion/ETL/worker/consumer/processor
       - full_stack: features span 3+ domains across multiple layers
       - default: api

Stage 4: Verification Gate
  4.1 Cross-source consistency checks (HARD REQUIREMENT — fail and retry up to 3 times if violated):
       a. Every feature from the phase manifest appears in EXACTLY ONE epic's frontmatter features[] (no duplicates, no missing)
       b. Every interface in any epic.md 'Epic Outputs' section has a corresponding entry in epic_manifest.json interfaces_provided[] (and vice versa)
       c. Every concrete_files[] in the manifest references files that exist in bootstrap-report.json's entities_created paths
       d. phase_e2e_config.json has an entry for every epic in the manifest
       e. YAML frontmatter feature_count in each epic.md matches the actual features[] array length
       f. execution_order contains all epic IDs exactly once and the E2E Testing epic is last
  4.2 If any check fails, attempt automatic fix (max 3 internal retries) — recompute manifest entries, fix mismatched feature lists, re-derive concrete_files paths.
  4.3 If still failing after 3 retries, return verification_status='failed_with_warnings' to the coordinator with a list of unresolved violations. The next round will fix-forward.

Stage 5: Commit
  Commit the changes with message 'space_split_converge: phase <N> decomposition' (round 1) or 'space_split_converge: round <R> — address <category> findings' (rounds 2+). NEVER use git --amend. NEVER rollback. Fix-forward only.

DELTA-REPORT FORMAT (what you send back to the coordinator after EVERY round):
{
  'round': <N>,
  'verification_status': 'passed|passed_with_warnings|failed_with_warnings',
  'files_written': [...],
  'files_modified': [...],
  'files_deleted': [...],
  'commits': [{ 'hash': '...', 'message': '...' }],
  'manifest_summary': {
    'epic_count': <N>,
    'execution_order': [...],
    'total_features_grouped': <N>,
    'interfaces_count': <N>
  },
  'verification_violations': [...],
  'warnings': [...]
}

ROUNDS 2+ — TARGETED FIX MODE

The coordinator will send consolidated findings + code_change_guidance. You MUST:
1. NEVER re-decompose from scratch — the epics already exist.
2. NEVER re-read the phase manifest unless it has actually changed (it hasn't).
3. Apply ONLY the surgical edits described in code_change_guidance:
   - epics_to_update → overwrite epic_<M>/epic.md body, update updated_at in YAML
   - epics_to_replace → set old epic state=closed in frontmatter, create new replacement epic file with next epic_number
   - manifest_edits → JSON path edits to epic_manifest.json (interfaces_provided, execution_order, etc.)
   - e2e_config_edits → JSON path edits to phase_e2e_config.json (infrastructure_requirements, scenarios)
4. Apply CASCADING UPDATES for each change:
   - move_feature_to_epic → remove from source epic.md frontmatter+body + add to dest epic.md + update manifest execution_order if needed + update interfaces_provided if affected feature was a provider + update phase_e2e_config epic entries
   - add_interface / modify_interface → edit provider epic.md 'Epic Outputs' section + update epic_manifest.json interfaces_provided[] including concrete_files (paths must exist in bootstrap-report.json)
   - split_epic / merge_epics → regenerate affected epic.md files + rebuild manifest entries + update phase_e2e_config
   - fix_e2e_infrastructure → patch phase_e2e_config.infrastructure_requirements (services, test_environment, startup/teardown commands)
   - fix_blackbox_spec → re-copy verbatim from phase manifest into epic.md 'Blackbox Feature Specifications' section
5. Re-run the verification gate (Stage 4 cross-source consistency checks, max 3 internal retries) on the modified set.
6. Commit with the round-specific message. NEVER use --amend. NEVER rollback. Fix-forward only.
7. Send a delta-report listing the new files_written/modified/deleted, new commits, updated manifest_summary, and verification_status.

CRASH RECOVERY (if the coordinator's first message includes RESUMING context):
The coordinator will tell you which commits already exist in the repo. Do Stage 0 detection (it is idempotent — reading the manifest is free) and skip directly to the first stage whose output is not yet committed. Do not duplicate work.

COMMUNICATION:
- Your coordinator's name is 'coordinator'.
- Send all delta-reports to coordinator via SendMessage.
- Do NOT write the feedback JSON or lesson files yourself — they are owned by the coordinator.
- NEVER write to phases/phase_<N>/feedback/ — that directory is coordinator-owned."
```

### 1.2 Structure Reviewer

Spawn a teammate called `structure-reviewer` using model opus with this prompt:

```
"You are the STRUCTURE REVIEWER for phase P<N> in team space-split-P<N>. Your role is to validate the epic decomposition's structural integrity by running FOUR independent checklists in sequence.

You have Read and Bash tool access — read epic.md files, epic_manifest.json, phase_e2e_config.json, and the phase manifest in $EIGEN_ROOT directly.

You will receive a delta-report from the coordinator. Apply the four checklists below in order, then return a single JSON array of findings.

CHECKLIST 1 — Epic Ordering & E2E Placement
  Inputs: epic_manifest.json execution_order + epics[].
  Questions:
    1.1 Does execution_order contain all epic IDs from epics[] EXACTLY once?
    1.2 Are epics sequential (E1, E2, E3, ...)?
    1.3 Is the E2E Testing epic last in execution_order?
    1.4 Does the topological order respect feature dependencies (no forward edges)?
  Severity: HIGH if any check fails (epic_formation_error).

CHECKLIST 2 — Cluster Integrity
  Inputs: epic_manifest.json epics[].features + phase manifest's natural clusters.
  Rule: Features in a cluster should strongly be kept within the same epic. A cluster split across epics is only acceptable if there is a compelling sequencing reason (earlier epic provides interfaces consumed by a later one).
  Questions:
    2.1 For every cluster in the phase manifest, does at least one epic contain ALL its features?
    2.2 If a cluster is split: is there documented evidence (interfaces_provided) that the split is necessary?
    2.3 Report every cluster with features in more than one epic: {cluster_id, features, epics_found_in}.
  Category: epic_formation_error.

CHECKLIST 3 — Epic Sizing
  Inputs: epic_manifest.json epics[] (feature counts).
  Questions:
    3.1 Are any epics too small to justify their own swarm (single feature, trivial scope)?
    3.2 Are any epics too large for a single swarm to execute effectively (>15 features, mixed domains)?
    3.3 Is sizing balanced relative to other epics in the phase?
    3.4 Report disproportionately large or small epics with merge/split recommendation.
  Category: epic_formation_error.

CHECKLIST 4 — Feature Coverage
  Inputs: phase manifest features list, epic_manifest.json epics[].features.
  Questions:
    4.1 Is every feature ID from the phase manifest assigned to exactly one epic? (dropped features)
    4.2 Are there features in an epic that are NOT in the phase manifest? (phantom features)
    4.3 Are there features appearing in MORE than one epic? (duplicate assignment)
    4.4 Report each issue: {feature_id, issue_type (dropped|phantom|duplicate), epics_involved}.
  Category: feature_coverage_error.

EXECUTION RULES:
- Apply the 4 checklists in order. Do not skip any.
- Each finding includes a `source_checklist` field tagged 1, 2, 3, or 4 for traceability.
- If two checklists detect the same problem from different angles, merge them into a single finding with source_checklist = '1+2' (etc.).
- Convert all findings to the unified space_split_converge schema before sending to the coordinator.

ROUNDS 2+ — VERIFICATION MODE
The coordinator sends modified files + the original findings that motivated changes. You:
1. Re-run ONLY the checklists relevant to the changed files (e.g. if only feature assignments changed, run checklists 2+4; if ordering changed, run checklist 1).
2. For each prior finding, verify it is now resolved.
3. Anticipate cascade errors in dependent epics (e.g. if a feature was moved, was the cluster still cohesive? was the manifest execution_order updated?).
4. Tag findings as 'verification' or 'anticipated' in addition to source_checklist.

FINDINGS FORMAT (send as JSON to coordinator via SendMessage):
{
  'findings': [
    {
      'category': '<epic_formation_error|feature_coverage_error|interface_error|issue_completeness_error|spec_fidelity_error|e2e_coverage_gap|strategic_concern|verification_failure|false_positive>',
      'severity_proposal': '<high|medium|low>',
      'source_checklist': '<1|2|3|4|combined>',
      'title': '<concise>',
      'description': '<detailed>',
      'affected_file': '<path>',
      'affected_section': '<section within file or top-level>',
      'recommendation': '<specific action for the space-splitter>',
      'code_change_guidance': {
        'epics_to_update': [...],
        'epics_to_replace': [...],
        'manifest_edits': [...],
        'e2e_config_edits': [...]
      }
    }
  ]
}

You PROPOSE severity. The coordinator decides final severity using the objective rubric.

COMMUNICATION:
- Your coordinator's name is 'coordinator'.
- Send all findings to coordinator via SendMessage."
```

### 1.3 Interface Reviewer

Spawn a teammate called `interface-reviewer` using model opus with this prompt:

```
"You are the INTERFACE REVIEWER for phase P<N> in team space-split-P<N>. Your role is to validate inter-epic interface contracts and bootstrap context fidelity by running THREE checklists in sequence.

You have Read and Bash tool access — read epic.md files, epic_manifest.json, and bootstrap-report.json in $EIGEN_ROOT directly.

CHECKLIST 1 — Inter-Epic Interface Completeness
  Inputs: epic_manifest.json interfaces_provided[], bootstrap-report.json entities_created.
  Questions:
    1.1 For every epic that provides interfaces: does the interfaces_provided list include the interfaces that later (consumer) epics actually need?
    1.2 Is each contract description precise enough for implementation? (must specify data shape or API contract, not just a name)
    1.3 Does each interface include concrete_files[] referencing real bootstrap entity stub paths?
    1.4 Are there ORPHAN interfaces? (provided but never consumed by any later epic — verify by checking consumer epics' dependencies)
  Category: interface_error.

CHECKLIST 2 — Interface Contract Compatibility
  Inputs: epic_manifest.json interfaces, provider epic.md body, consumer epic.md body, bootstrap-report.json entities_created.
  Questions:
    2.1 For each interface, read the provider epic.md 'Epic Outputs' section — how does it describe the output?
    2.2 Read the consumer epic.md body — how does it describe the expected input?
    2.3 Do the interface's concrete_files point to real bootstrap entity stubs (verify path exists in entities_created)?
    2.4 Are the contracts compatible? (does the provider's described output match what the consumer expects?)
    2.5 Report incompatible contracts, missing concrete_files, contracts where provider and consumer describe different shapes.
  Category: interface_error.

CHECKLIST 3 — Bootstrap Context Fidelity
  Inputs: each epic.md 'Bootstrap Context' section, bootstrap-report.json (entities_created, tooling_decisions, language).
  Questions:
    3.1 Extract the 'Bootstrap Context' section of each epic.md.
    3.2 Do the entity stubs listed actually exist in bootstrap-report.json's entities_created?
    3.3 Do file paths match the entity_file_map (entity name → path) from the bootstrap report?
    3.4 Do tooling decisions (language, framework, test runner) match the bootstrap report's tooling_decisions?
    3.5 Flag any entity stub referenced in the epic file that is NOT in the bootstrap report (phantom references).
  Category: issue_completeness_error.

EXECUTION RULES:
- Apply the 3 checklists in order.
- Each finding includes source_checklist tag (1, 2, or 3).
- Convert findings to the unified space_split_converge schema.

ROUNDS 2+ — VERIFICATION MODE
Same pattern as structure-reviewer: re-run only relevant checklists on the changed files, verify prior findings are resolved, anticipate cascade errors, tag as 'verification' or 'anticipated'.

FINDINGS FORMAT: identical to structure-reviewer.

COMMUNICATION:
- Your coordinator's name is 'coordinator'.
- Send all findings to coordinator via SendMessage."
```

### 1.4 Fidelity Reviewer

Spawn a teammate called `fidelity-reviewer` using model opus with this prompt:

```
"You are the FIDELITY REVIEWER for phase P<N> in team space-split-P<N>. Your role is to apply FIVE complementary lenses: epic body completeness, blackbox spec fidelity, E2E coverage, architectural soundness, and simplicity.

You have Read and Bash tool access. Read epic.md files, the phase manifest, epic_manifest.json, phase_e2e_config.json, and bootstrap-report.json in $EIGEN_ROOT to ground your analysis.

CHECKLIST 1 — Issue Completeness
  Inputs: each epic.md body, bootstrap-report.json.
  Required sections in each epic file body (in order):
    1. Features table — with ID, Name, Priority, Dependencies columns
    2. Validation Criteria — what can be verified after this epic's swarm completes
    3. Epic Outputs — interfaces this epic provides + consumes, with concrete file paths
    4. Blackbox Feature Specifications — FULL verbatim specs (Inputs, Outputs, Behavior, Acceptance Criteria) for EVERY feature in the epic
    5. Whitebox Implementation Guidance — relevant whitebox sections (optional, only if phase manifest has whitebox)
    6. Bootstrap Context — language, tooling, entity stubs with file paths
  Questions:
    1.1 For each epic file, are sections 1-4 and 6 present and non-empty? (section 5 is optional)
    1.2 Does the blackbox specs count match the feature count in the features table?
    1.3 Does Bootstrap Context include real file paths (not placeholders)?
  Category: issue_completeness_error.

CHECKLIST 2 — Blackbox Spec Fidelity
  Inputs: epic.md 'Blackbox Feature Specifications' section, phase manifest's blackbox specs.
  Questions:
    2.1 For each epic file, extract the feature IDs from the Features table.
    2.2 Extract the blackbox specs from the 'Blackbox Feature Specifications' section.
    2.3 Compare against the phase manifest's blackbox specs for those same feature IDs.
    2.4 Flag: missing specs (feature in table but no spec in epic file), truncated specs (fewer acceptance criteria than manifest), garbled specs (text mismatch).
  Category: spec_fidelity_error.

CHECKLIST 3 — E2E Coverage
  Inputs: epic_manifest.json, phase_e2e_config.json, the E2E Testing epic.md, bootstrap-report.json.
  Questions:
    3.1 Does an E2E Testing epic exist as the LAST epic in execution_order? Does its epic.md Validation Criteria describe the full phase-level E2E flows?
    3.2 Do phase_e2e_config.phase_e2e_scenarios cover ALL inter-epic integration boundaries? Is every inter-epic interface exercised by at least one scenario? Are the acceptance_criteria traceable to features across epics?
    3.3 Does every feature epic (non-E2E) have at least one entry in epic_validation_scenarios with scenarios covering its key acceptance criteria?
    3.4 Are infrastructure_requirements.test_types_detected consistent with the features in the phase? Do needs_docker / needs_emulator / needs_browser_automation match the test types?
    3.5 If test_environment is 'container_parity': are compose_file, startup_command, health_check, teardown_command, and services populated? Does the services list match bootstrap-report.json delta_applied.docker_compose_services as a baseline?
    3.6 If test_environment is missing but needs_docker is true → flag as e2e_coverage_gap.
    3.7 Are phase_e2e_scenarios consistent with what the E2E Testing epic.md describes in its Validation Criteria? Do epic_validation_scenarios align with each epic's Validation Criteria section?
  Category: e2e_coverage_gap.

CHECKLIST 4 — Architecture
  Inputs: epic_manifest.json, bootstrap-report.json, phase manifest.
  Questions:
    4.1 Does the epic ordering make architectural sense?
    4.2 Are provider epics correctly upstream of consumer epics?
    4.3 Are there hidden dependencies not captured in the epic manifest? (look for features that share entities but live in different epics with no interface)
    4.4 Is the overall decomposition granularity appropriate for the phase's scope?
    4.5 Do the inter-epic interfaces align with the bootstrap foundation's entity boundaries?
  Category: strategic_concern.

CHECKLIST 5 — Simplicity
  Inputs: epic_manifest.json, phase manifest summary.
  Questions:
    5.1 Are there too many epics for the feature count? (e.g., 10 epics for 15 features is over-decomposed)
    5.2 Could simpler epic boundaries achieve the same result?
    5.3 Are there unnecessary indirections in the interface contracts?
    5.4 Could any small epics be merged without violating cluster integrity?
  Category: epic_formation_error or strategic_concern (whichever is more specific).

EXECUTION RULES:
- Apply the 5 checklists in order. Do not skip any.
- Each finding includes a `source_checklist` field tagged 1, 2, 3, 4, or 5 for traceability.
- If two checklists flag the same issue from different angles, merge with source_checklist = '1+5' etc.
- Convert findings to the unified space_split_converge schema.

ROUNDS 2+ — VERIFICATION MODE
Same pattern as the other reviewers. Re-run only relevant lenses on the changed files, verify resolution, anticipate cascades, tag as 'verification' or 'anticipated'.

FINDINGS FORMAT: identical to structure-reviewer.

COMMUNICATION:
- Your coordinator's name is 'coordinator'.
- Send all findings to coordinator via SendMessage."
```

### 1.5 Skills Reviewer

Spawn a teammate called `skills-reviewer` using model opus with this prompt:

```
"You are the SKILLS REVIEWER for phase P<N> in team space-split-P<N>. Your role is to discover relevant skills from the project/user/plugin sources and apply their domain-specific lenses to the epic decomposition.

ROUND 1 — SKILL DISCOVERY (execute ONCE):
1. Discover ALL available skills from all sources (project, user, all plugins).
2. Match skills against the phase's domains and technologies (read bootstrap-report.json's languages and tooling_decisions to identify relevant tech stacks). Prioritize: language-specific best practices, security-best-practices, language-profiles, framework-specific patterns, ci/cd patterns.
3. Record the matched skill set — you will use this SAME set in all subsequent rounds.
4. For each matched skill, review the epic decomposition through that skill's lens for gaps, anti-patterns, or domain-specific concerns (e.g., 'React best practices' would flag epics that decompose UI in ways that violate component boundaries; 'security' would flag epics that mix auth concerns with feature concerns).
5. INCLUDE THE DISCOVERED SKILL SET in your first message to the coordinator so the coordinator can persist it via convergence_state.json + the CLI's --locked-skills flag.

ROUNDS 2+ — APPLY FIXED SKILL SET:
1. If the coordinator's message includes a `locked_skills` array, use exactly that set (loaded from convergence_state.json after a crash).
2. Otherwise use the SAME skill set you discovered in round 1. Do NOT rediscover skills. Do NOT add new skills.
3. Review the epic decomposition (or the modified files) through each matched skill's lens.
4. Verify prior findings are resolved. Tag as 'verification' or 'anticipated'.

FINDINGS FORMAT: identical to structure-reviewer (use 'strategic_concern' or matching category).

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
  "reviewers_active": ["structure-reviewer", "interface-reviewer", "fidelity-reviewer", "skills-reviewer"],
  "reviewer_failures": [],
  "splitter_commits": []
}
```

This is the crash recovery checkpoint — if the coordinator crashes after this point, the next invocation knows round 1 was in progress.

---

## Stage 2: Space-Splitter Round (Round 1)

### 2.1 Read Inputs

1. Read `$EIGEN_ROOT/eigen_initiative/phases/phase_<N>_manifest.md`.
2. Read `$EIGEN_ROOT/eigen_initiative/phases/phase_<N>/bootstrap-report.json`.
3. Read recommendations from CLI context (filter by current phase).
4. If `is_first_run: false` and `convergence_state.json` shows `round_1_status: in_progress`, run `git log --oneline -20` in `$EIGEN_ROOT` to detect commits already made by a prior space-splitter attempt.

### 2.2 Send to Space-Splitter

```
SendMessage({
  to: "space-splitter",
  message: "Execute the full Stage 0–5 sequence to decompose phase <N> into epics.

PHASE MANIFEST:
<full phase_<N>_manifest.md content>

BOOTSTRAP REPORT:
<full bootstrap-report.json content>

UPSTREAM RECOMMENDATIONS:
<recommendations content, or 'None'>

EIGEN_ROOT: <absolute path>
EIGEN_BRANCH: <branch>

[ONLY IF RESUMING after a crash:]
RESUMING: the previous run crashed mid-decomposition. The following commits already exist in the repo:
<git log output>
Verify the current state of phases/phase_<N>/ matches the expected outputs of those commits and continue from the next pending stage. Do not re-do work that is already committed."
})
```

### 2.3 Receive Delta-Report

Wait for the space-splitter's SendMessage response with the delta-report. Update `convergence_state.json`:
- `round_1_status: "completed"`
- `splitter_commits: <commit hashes from delta-report>`

If the space-splitter reports `verification_status: "failed_with_warnings"`, do NOT abort — the reviewers will see findings with `category: verification_failure` and the next round will fix-forward.

---

## Stage 3: Review Round (parallel)

Send the delta-report to all 4 reviewers in parallel via SendMessage:

```
SendMessage({
  to: "structure-reviewer",
  message: "Review the epic decomposition at $EIGEN_ROOT for phase <N>.

DELTA-REPORT FROM SPACE-SPLITTER:
<delta-report JSON>

PHASE MANIFEST CONTENT:
<phase manifest content>

Apply your 4 checklists (Epic Ordering & E2E Placement, Cluster Integrity, Epic Sizing, Feature Coverage) in order. Read epic_manifest.json and the epic.md files in $EIGEN_ROOT directly to verify ground truth."
})

SendMessage({
  to: "interface-reviewer",
  message: "Review the epic decomposition at $EIGEN_ROOT for phase <N>.

DELTA-REPORT FROM SPACE-SPLITTER:
<delta-report JSON>

PHASE MANIFEST CONTENT:
<phase manifest content>

BOOTSTRAP REPORT (for entity paths):
<bootstrap-report.json content>

Apply your 3 checklists (Inter-Epic Interface Completeness, Interface Contract Compatibility, Bootstrap Context Fidelity)."
})

SendMessage({
  to: "fidelity-reviewer",
  message: "Review the epic decomposition at $EIGEN_ROOT for phase <N>.

DELTA-REPORT FROM SPACE-SPLITTER:
<delta-report JSON>

PHASE MANIFEST CONTENT:
<phase manifest content>

BOOTSTRAP REPORT:
<bootstrap-report.json content>

Apply your 5 lenses (Issue Completeness, Blackbox Spec Fidelity, E2E Coverage, Architecture, Simplicity)."
})

SendMessage({
  to: "skills-reviewer",
  message: "Review the epic decomposition at $EIGEN_ROOT for phase <N>.

DELTA-REPORT FROM SPACE-SPLITTER:
<delta-report JSON>

PHASE MANIFEST CONTENT:
<phase manifest content>

BOOTSTRAP REPORT (for languages/tooling):
<bootstrap-report.json content>

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

If multiple reviewers flag the same epic, file, or concept, merge into a single finding. Preserve the most actionable recommendation and combine `code_change_guidance` from all sources.

### 4.1.1 Narrative vs Structural Assessment (Dual Source of Truth)

space_split_converge produces both narrative (epic.md) and JSON (epic_manifest.json) representations of interfaces and dependencies. For each finding that flags a missing or inconsistent structural entry:

1. **Check the OTHER source**: If the finding says "interface X missing from epic_manifest.json `interfaces_provided[]`", check if the interface IS described in the provider's epic.md "Epic Outputs" section (and vice versa).
2. **If present in one source but absent in the other**: the finding is valid (BOTH sources MUST be consistent), but **downgrade severity to medium** if it was classified as high. Include explicit `code_change_guidance` showing exactly which JSON entries or epic.md sections to add or modify.
3. **If absent from BOTH sources**: keep original severity — the decomposition genuinely missed this interface or dependency.
4. **Check concrete_files against bootstrap-report.json**: If a finding says "concrete_files missing for interface X", check if the files exist in bootstrap-report.json's entities_created. If they do, downgrade and provide the exact paths.

### 4.2 Resolve Contradictions

If reviewers disagree, evaluate weight by category:
- `epic_formation_error`, `feature_coverage_error` → structure-reviewer has more weight
- `interface_error` → interface-reviewer has more weight
- `issue_completeness_error`, `spec_fidelity_error`, `e2e_coverage_gap`, `strategic_concern` → fidelity-reviewer has more weight
- Skills-specific anti-patterns → skills-reviewer has more weight

If contradictions cannot be resolved from context, send a clarification SendMessage to the relevant reviewer and wait for the response. Document the decision in the finding's description: "Contradiction between X and Y resolved in favor of Z because W."

### 4.3 Apply Severity Rubric

The coordinator is the SOLE authority on severity. Reviewers only propose.

| Severity | Definition | Concrete examples |
|---|---|---|
| **high** | Blocks `plan_epic_converge` or downstream commands | Feature dropped from all epics; epic order has forward dependency; circular dependency; concrete_files reference paths that don't exist; **`verification_failure` is ALWAYS high** |
| **medium** | Functional but suboptimal | Cluster split without strong justification; epic too large/small; vague interface contract; missing E2E scenario for an epic; blackbox spec truncated |
| **low** | Minor / stylistic | Naming inconsistency; missing optional whitebox guidance; minor wording issues |

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

**Verification failure veto**: Convergence by oscillation (rule 4) is BLOCKED if any active finding has `category: verification_failure`. A broken cross-source consistency check is always blocking.

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

### 6.1 Send Findings to Space-Splitter

```
SendMessage({
  to: "space-splitter",
  message: "Apply the following fixes. Use surgical edits ONLY — do not re-decompose.

CONSOLIDATED FINDINGS (round <R>):
<consolidated findings JSON with merged code_change_guidance>

CASCADING UPDATE RULES:
- move_feature_to_epic → remove from source epic.md (frontmatter + body) + add to dest epic.md + update manifest execution_order if needed + update interfaces_provided if affected feature was a provider + update phase_e2e_config epic entries
- add_interface / modify_interface → edit provider epic.md 'Epic Outputs' section + update epic_manifest.json interfaces_provided[] including concrete_files (paths must exist in bootstrap-report.json)
- split_epic / merge_epics → regenerate affected epic.md files + rebuild manifest entries + update phase_e2e_config
- fix_e2e_infrastructure → patch phase_e2e_config.infrastructure_requirements (services, test_environment, startup/teardown commands)
- fix_blackbox_spec → re-copy verbatim from phase manifest into epic.md 'Blackbox Feature Specifications' section

Re-run the verification gate (Stage 4 cross-source consistency, max 3 internal retries) on the modified set. If verification still fails, return verification_status = 'failed_with_warnings' in your delta-report — that is acceptable, the next round will fix-forward.

Commit with message 'space_split_converge: round <R> — address <category> findings'. Do NOT use --amend. Do NOT rollback any prior commit.

Send back a delta-report with the new files_written/modified/deleted, new commits, updated manifest_summary, and verification_status."
})
```

### 6.2 Receive Delta-Report

Wait for the space-splitter's response. Append the new commits to `convergence_state.json["splitter_commits"]`.

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
  "splitter_commits": [...]
}
```

### 6.4 Send to Affected Reviewers

Route the delta-report to ONLY the affected reviewers based on which files changed:

| Space-splitter change | Reviewers re-engaged |
|---|---|
| Epic feature assignments (move/split/merge) | structure + interface + fidelity |
| Epic ordering / execution_order | structure |
| Interfaces / concrete_files | interface + fidelity |
| epic.md body sections (specs, validation, bootstrap context) | fidelity |
| phase_e2e_config.json | fidelity |
| New tech / framework introduced | skills (otherwise skipped in rounds 2+) |

```
SendMessage({
  to: "<affected-reviewer>",
  message: "Verify these changes (round <R>) and anticipate cascade errors.

DELTA-REPORT (round <R>):
<delta-report from space-splitter>

ORIGINAL FINDINGS THAT MOTIVATED CHANGES:
<the findings sent to the space-splitter in 6.1>

VERIFICATION INSTRUCTIONS:
1. For each prior finding, verify it is resolved.
2. Anticipate cascade errors in dependent epics. Tag findings as 'verification' or 'anticipated'.
3. Re-run only the checklists relevant to the changed files."
})
```

Wait for engaged reviewers to respond, then return to Stage 4 with the new findings.

---

## Stage 7: Output & Cleanup (at convergence)

### 7.1 Verify Final Artifacts

Before proceeding, sanity-check that the invariant artifacts are on disk and valid:

1. `phases/phase_<N>/epic_manifest.json` exists and parses as JSON
2. `phases/phase_<N>/phase_e2e_config.json` exists and parses as JSON
3. Every epic in `epic_manifest.json` has a corresponding `phases/phase_<N>/epic_<M>/epic.md` file
4. `_index.md` exists and contains the current phase entry

If any check fails, the splitter has not committed the final state — send a clarification SendMessage and re-run the verification gate.

### 7.2 Write Feedback JSON

Ensure directory exists: `mkdir -p $EIGEN_ROOT/eigen_initiative/phases/phase_<N>/feedback/`

Write to `phases/phase_<N>/feedback/space_split_converge_feedback.json`:

```json
{
  "schema_version": "1.0.0",
  "command": "space_split_converge",
  "phase": <N>,
  "iteration": "<total internal rounds>",
  "convergence": {
    "decision": "converged",
    "rationale": "<convergence rationale from Stage 5>",
    "rounds_taken": <R>
  },
  "source_outputs_analyzed": {
    "epic_manifest": "phases/phase_<N>/epic_manifest.json",
    "phase_e2e_config": "phases/phase_<N>/phase_e2e_config.json",
    "epic_files": ["phases/phase_<N>/epic_<M>/epic.md", ...]
  },
  "findings": [
    {
      "id": "ssf-<seq>",
      "category": "<category>",
      "severity": "<high|medium|low>",
      "title": "<concise>",
      "description": "<detailed>",
      "affected_file": "<path>",
      "affected_section": "<section>",
      "recommendation": "<action that was taken>",
      "resolution": "resolved|degraded_to_low|accepted_at_convergence",
      "source_reviewer": "<structure|interface|fidelity|skills|merged>",
      "source_checklist": "<id>",
      "downstream_impact": {
        "affects_commands": ["plan_epic_converge", "create_issues_from_plan_swarm"],
        "impact_description": "<what would break downstream>"
      }
    }
  ],
  "summary": {
    "total_findings": <N>,
    "by_severity": { "high": 0, "medium": 0, "low": <N> },
    "by_category": { "<category>": <N> },
    "per_epic": {
      "P<N>.E<M>": { "high": 0, "medium": 0, "low": <N> }
    }
  }
}
```

The `findings` array includes ALL findings from all rounds — both resolved and remaining. The `resolution` field tracks how each was handled.

### 7.3 Lesson Extraction

For each non-false-positive finding, create a lesson JSON in `eigen_lessons/space_split_converge/`:

```json
{
  "id": "ssc-lesson-<timestamp>-<seq>",
  "created_at": "<ISO 8601>",
  "command": "space_split_converge",
  "status": "pending",
  "category": "<finding category>",
  "severity": "<finding severity>",
  "title": "<concise>",
  "description": "<detailed>",
  "root_cause": "<why the space-splitter produced this error>",
  "recommendation": "<specific change to space_split_converge.md>",
  "affected_phase": "<which section of space_split_converge.md to modify>",
  "evidence": {
    "epics_involved": ["<epic IDs>"],
    "features_involved": ["<feature IDs>"],
    "files_involved": ["<paths>"],
    "reviewer_source": "<which reviewer found this>",
    "source_checklist": "<id>"
  },
  "initiative_context": "<initiative name, phase number, feature count>",
  "tags": [...]
}
```

**Deduplication**: Before writing, check existing lessons in the directory. Skip if a lesson with the same `affected_phase` + `category` + similar `root_cause` already exists. Skip if the existing lesson has `status: applied`.

Ensure directory exists: `mkdir -p $EIGEN_ROOT/eigen_initiative/eigen_lessons/space_split_converge/`

Print summary:
```
Lessons written: <N> new lessons to $EIGEN_ROOT/eigen_initiative/eigen_lessons/space_split_converge/
Skipped: <M> duplicates
```

### 7.4 Execute On Exit Commands

Execute the **On Exit** section above. It contains the single authoritative code block with all CLI calls in order: `complete`, `mark-converged`, `add-recommendation` (optional, max 5), and `commit-state`. Pass `--locked-skills` so the CLI persists the discovered skill set.

### 7.5 Team Shutdown

Send shutdown messages to all teammates:

```
SendMessage({ to: "space-splitter",      message: "Space split converged. Shutting down. Thank you." })
SendMessage({ to: "structure-reviewer",  message: "Space split converged. Shutting down. Thank you." })
SendMessage({ to: "interface-reviewer",  message: "Space split converged. Shutting down. Thank you." })
SendMessage({ to: "fidelity-reviewer",   message: "Space split converged. Shutting down. Thank you." })
SendMessage({ to: "skills-reviewer",     message: "Space split converged. Shutting down. Thank you." })
```

Wait for confirmations, then delete the team:

```
TeamDelete({ team_name: "space-split-P<N>" })
```

**Critical timing**: Shut down ONLY at this point — after all rounds complete, the invariant artifacts are written, the feedback JSON is saved, lessons are extracted, and the on-exit commands have run. Do NOT shut down teammates between rounds.

### 7.6 Print Summary

```
=== Space Split Converge Complete — Phase <N> ===

Phase: <N>
Target repo: $EIGEN_ROOT
Total features: <N>
Epics created: <N> (including E2E Testing epic)
Execution order: P<N>.E1 → P<N>.E2 → ... → P<N>.E<last>
Verification: <PASSED|PASSED WITH WARNINGS>
Convergence: CONVERGED in <R> rounds — <rationale>

Epics:
  P<N>.E1: <name> (<feature_count> features, depends_on: [...])
  P<N>.E2: <name> (<feature_count> features, depends_on: [...])
  ...
  P<N>.E<last>: E2E Testing (0 features)

Inter-Epic Interfaces:
  P<N>.E1 → P<N>.E2: <interface_name> (<contract>)
  ...

Findings:
  High severity:   <N> (all resolved)
  Medium severity: <N> (all resolved or degraded)
  Low severity:    <N>

Space-splitter commits:
  <hash> — <message>
  ...

Lessons: <N> new lessons written
Files generated:
  $EIGEN_ROOT/eigen_initiative/phases/phase_<N>/epic_manifest.json
  $EIGEN_ROOT/eigen_initiative/phases/phase_<N>/phase_e2e_config.json
  $EIGEN_ROOT/eigen_initiative/phases/phase_<N>/epic_<M>/epic.md  (per epic)
  $EIGEN_ROOT/eigen_initiative/_index.md  (merged)
Feedback: $EIGEN_ROOT/eigen_initiative/phases/phase_<N>/feedback/space_split_converge_feedback.json

Next steps:
  1. Run /plan_epic_converge for each epic (auto-detected by the watchdog).
  2. Run /compound_improve to apply accumulated lessons to space_split_converge.md.
```

---

## Pre-Submission Checklist

Before writing the feedback JSON and proceeding to On Exit, verify:

- [ ] All space-splitter commits are present in `git log`
- [ ] Verification gate passed (or `verification_status: passed_with_warnings` is documented)
- [ ] `epic_manifest.json` schema matches the invariant (downstream commands depend on this)
- [ ] `phase_e2e_config.json` schema matches the invariant
- [ ] Every epic in the manifest has a corresponding `epic.md` file with all required body sections
- [ ] `_index.md` reflects the current phase
- [ ] Cross-source consistency checks pass: every interface in any epic.md "Epic Outputs" has a matching `interfaces_provided[]` entry; every `concrete_files[]` path resolves in `bootstrap-report.json`; every feature appears in exactly one epic; YAML `feature_count` matches `features[]` length
- [ ] Feedback JSON written
- [ ] Lesson JSONs written and deduplicated
- [ ] convergence_state.json reflects the final round and findings_history
- [ ] locked_skills persisted via `--locked-skills` on the CLI complete call
- [ ] On Exit commands executed successfully
- [ ] Team shutdown was performed AFTER all of the above

---

## Key Rules

1. **Invariant artifact schemas** — `epic_manifest.json`, `phase_e2e_config.json`, and `epic.md` per epic are consumed by `plan_epic_converge`, `create_issues_from_plan_swarm`, `orchestrate_swarm`, `eigen_continue`, `review_swarm_pr`, and `e2e_validation_swarm`. Do not change shape, paths, or required fields.
2. **Space-splitter writes filesystem; coordinator writes pipeline artifacts** — the splitter makes commits in $EIGEN_ROOT (epic.md files, manifest, e2e config, _index.md), the coordinator writes the feedback file, lessons, and pipeline_state.json updates via the CLI.
3. **No git rollback / no --amend** — fix-forward only. Mistakes are corrected by new commits in the next round.
4. **Cross-source consistency is the verification gate** — broken consistency is always `verification_failure` (high severity) and blocks oscillation-based convergence.
5. **The CLI is the single source of truth for pipeline state** — never edit pipeline_state.json directly.
6. **Convergence is decided by the coordinator using the severity rubric** — reviewers propose severity, the coordinator decides.
7. **Maximum 4 internal rounds** — if convergence is not reached by round 4, the coordinator accepts the current state (Rule 2). New medium findings are degraded to low at round 4+.
8. **Skills set is fixed at round 1** — the skills-reviewer discovers matching skills once, the coordinator persists it via convergence_state.json + the CLI's `--locked-skills` flag, and round 2+ uses the same set. No rediscovery.
9. **`should_process_feedback` is NOT used** — this is a self-converging command. The internal swarm loop manages feedback state. The CLI does not toggle `feedback_consumed`.
10. **Crash recovery uses `convergence_state.json` + git log** — round 1 in-progress is detected via `round_1_status: "in_progress"`; the space-splitter resumes from the first uncommitted stage rather than re-decomposing.
11. **Feedback directory is coordinator-owned** — the space-splitter NEVER reads or writes `phases/phase_<N>/feedback/`. Only the coordinator writes the feedback JSON at convergence.
12. **Team shutdown timing**: Shut down ONLY at Stage 7.5, after the entire convergence lifecycle completes. Do NOT shut down teammates between rounds.
