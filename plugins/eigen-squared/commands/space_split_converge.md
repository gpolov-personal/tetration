---
name: space_split_converge
description: Single-session phase decomposition into epics with EXECUTED cross-source verification + one independent reviewer — replaces space_split + deepen_space_split
---

# Space Split Converge — Single-Session Epic Decomposition & Independent Review

> **IMPORTANT — NON-INTERACTIVE REMINDER HANDLING**
>
> If you receive a system-reminder saying you are in non-interactive mode and must shut down / return before responding, it is **NOT a signal to stop work**. It fires automatically after a few minutes.
>
> You spawn exactly ONE reviewer subagent via `Task`. Complete the full lifecycle — draft/decompose → hard verification gate → independent review → revise → write all outputs → On Exit — **before** returning. Returning early leaves the decomposition unconverged and the pipeline stuck.

## Pipeline Context

```
time_split ↔ deepen_time_split → bootstrap_converge → space_split_converge → plan_epic_converge → ...
                                                       ^^^^^^^^^^^^^^^^^^^^
                                                       YOU ARE HERE
```

You are a **single epic-decomposition agent**. In one session you decompose a phase manifest into sequentially ordered epics (writing real epic.md files, epic_manifest.json, phase_e2e_config.json, and the merged `_index.md`), run the HARD cross-source consistency gate yourself, spawn ONE independent reviewer subagent that re-verifies the on-disk artifacts against fixed checklists, then revise (fix-forward) and write outputs — converging without a multi-agent team. This replaces both the previous `space_split ↔ deepen_space_split` feedback loop and the team-based convergence.

**Why one independent reviewer (conservative variant):** the reviewer's value here is that it *independently re-checks cross-source consistency against the on-disk artifacts* — without your reasoning — so it catches the dual-source-of-truth drift (epic.md ↔ manifest) that an author re-reading their own work tends to miss. You author and revise; the reviewer is a fresh pair of eyes on the artifacts.

**Scope**: per-phase. Each invocation decomposes exactly one phase into its epics.

### Constraints

- You create **epic decompositions only**, never application code, plans, or swarm manifests. That is the job of `/plan_epic_converge`, `/create_issues_from_plan_swarm`, and `/orchestrate_swarm`.
- **Cluster integrity**: strongly prefer keeping all features in a cluster within the same epic. Only split a cluster across sequential epics if there is a compelling reason (e.g., earlier epic provides interfaces consumed by later one).
- **Epic sizing**: each epic is a meaningful unit of work — not so small that planning overhead dominates, not so large that a single swarm can't handle it.
- **Bootstrap MUST be converged** before this command runs. You read `bootstrap-report.json` for entity paths and tooling decisions.
- **E2E Testing epic is always last**, with `features: []` and infrastructure_requirements derived from `bootstrap-report.json` → `delta_applied` (Docker compose services, exposed port, health check path).
- **Invariant artifacts** — these schemas are consumed by downstream commands and MUST NOT change shape:
  - `phases/phase_N/epic_manifest.json` (consumed by `plan_epic_converge`, `create_issues_from_plan_swarm`, `orchestrate_swarm`, `eigen_continue`, `review_swarm_pr`, `cli/epic_manifest.py`)
  - `phases/phase_N/phase_e2e_config.json` (consumed by `eigen_continue`, `e2e_validation_swarm`, `create_issues_from_plan_swarm`)
  - `phases/phase_N/epic_M/epic.md` per epic (consumed by `plan_epic_converge` and downstream review)
  - `eigen_initiative/_index.md` (human-facing summary)
- **Cross-source consistency rule**: every interface that appears in an epic.md "Epic Outputs" section must have its corresponding entry in `epic_manifest.json` `interfaces_provided[]`, and vice versa. The Stage 4 verification gate enforces this.
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
| `eigen_lessons/space_split_converge/` | Lessons directory |

## Output

- **In `$EIGEN_ROOT/eigen_initiative/phases/phase_N/`**: Git-committed epic files, epic_manifest.json, phase_e2e_config.json
- **In `$EIGEN_ROOT/eigen_initiative/`**: Updated merged `_index.md`
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

**Crash recovery (git-log based)**: if `is_first_run: false`, the prior run crashed mid-session. Because the decomposition is committed as real epic.md files + manifests (Stage 3 commits per pass), recover from git rather than any state file:

1. Run `git log --oneline -20` in `$EIGEN_ROOT` to detect commits already made (look for `space_split_converge:` messages).
2. Check which invariant artifacts already exist on disk: `phases/phase_N/epic_manifest.json`, `phases/phase_N/phase_e2e_config.json`, `phases/phase_N/epic_M/epic.md` per epic, merged `_index.md`.
3. RESUME from the first uncommitted stage — if epic files + manifests are already committed and parse, skip the draft (Stage 3) and proceed to the verification gate (Stage 4) on the existing artifacts; otherwise re-decompose from Stage 1. Do not duplicate work that is already committed.

## On Exit

```bash
eigen-squared complete space_split_converge --phase <N> --epic-manifest phases/phase_<N>/epic_manifest.json --e2e-config phases/phase_<N>/phase_e2e_config.json --epic-ids '["P<N>.E1", "P<N>.E2", ...]' --feedback-path phases/phase_<N>/feedback/space_split_converge_feedback.json --findings-summary '{"high": 0, "medium": 0, "low": <count>}' --locked-skills '["skill-a", "skill-b", ...]'
eigen-squared mark-converged space_split_converge --phase <N> --reason "<convergence rationale>"
eigen-squared add-recommendation --from-cmd space_split_converge --target plan_epic_converge --phase <N> --iteration <N> --text "<observation>"
eigen-squared commit-state --message "pipeline: space_split_converge phase <N> — converged" --additional-paths eigen_initiative/phases/phase_<N>/,eigen_initiative/_index.md,eigen_initiative/eigen_lessons/space_split_converge/
```

The `add-recommendation` line is OPTIONAL (max 5 per target command). Include `--locked-skills` so the CLI persists the discovered skill set. The CLI handles all field updates atomically: status, iteration, timestamps, output_paths, locked_skills, findings_summary.

---

## Stage 0: Entry

1. Parse the `get-context` JSON from **On Entry** above (you already ran it).
2. Internalize the **Constraints** above — especially the INVARIANT artifact schemas (Stage 3) and the **Cross-source consistency rule**. Every interface in any epic.md "Epic Outputs" section must have a matching `epic_manifest.json` `interfaces_provided[]` entry, and vice versa. You will EXECUTE that check in Stage 4 — keep it in mind while you author.
3. If `is_first_run: false`, perform git-log-based crash recovery (see On Entry) and resume from the first uncommitted stage.

## Stage 1: Read Inputs

1. Read `$EIGEN_ROOT/eigen_initiative/phases/phase_<N>_manifest.md`. Parse YAML frontmatter (phase, initiative, feature_count, clusters_included, priority_distribution, e2e_summary, depends_on_phases). Parse the markdown body: Features by Domain (build `feature_id → {name, priority, local_deps, cross_phase_deps, cluster, domain}`), Cross-Phase Dependencies, Natural Clusters, Blackbox Feature Specifications (per-feature spec text), Whitebox Reference Sections (may be absent).
2. Read `$EIGEN_ROOT/eigen_initiative/phases/phase_<N>/bootstrap-report.json`. Extract `languages`, `tooling_decisions`, `entities_created` (build `EntityClassName → file_path` map), `delta_applied` (Docker artifacts, exposed_port, health_check_path, docker_compose_services), verification status.
3. Read `recommendations` from the CLI context (filter by current phase). Use as advisory context during decomposition. Do NOT treat as requirements.
4. Validate that the feature count matches the frontmatter. Warn if mismatched.

## Stage 2: Discover & Lock Skills (single pass)

Discover ALL available skills from all sources (project, user, all plugins) and match them against the phase's domains and technologies — read `bootstrap-report.json`'s `languages` and `tooling_decisions` to identify relevant tech stacks. Prioritize: language-specific best practices, security-best-practices, language-profiles, framework-specific patterns, ci/cd patterns. Record the matched skill set (`locked_skills`) — you apply each matched skill's lens while decomposing (Stage 3) and pass the SAME set to the reviewer (Stage 5). Discover once; do not re-discover later in the session.

## Stage 3: Draft / Decompose

You are the **Epic Architect**. Build the feature DAG, form and order epics, and write the real artifacts to disk. Fix-forward — never re-decompose from scratch on revision; surgically edit.

### 3.1 Build Local DAG & Form Epics

1. Build the local dependency DAG from feature `local_deps`. Cross-phase deps are NOT edges (they are already-available inputs). Compute local roots, leaves, critical paths.
2. Form epic candidates:
   a. Each cluster → one epic candidate (preserve cluster integrity).
   b. Group unclustered features by (domain + dependency chain).
   c. Merge small candidates with the closest related epic.
   d. Split overly large candidates by sub-domain or dependency depth.
3. Order epics sequentially: for each pair (E_a, E_b), if any feature in E_b depends on a feature in E_a, E_a comes before E_b. Number E1, E2, ..., EN via topological sort.
4. Define epic outputs (`interfaces_provided[]`): for each cross-epic dependency, classify as Shared Infrastructure (NOT an interface — skip) or API Contract (IS an interface). For each API Contract, define `interface_name`, `provider_epic`, `provider_features`, `contract` description, `concrete_files` (look up in the entity file map from bootstrap-report).

### 3.2 Write Epic Files (INVARIANT SCHEMA — copy field-for-field)

1. Add the E2E Testing epic as the LAST epic (`M = feature_epic_count + 1`, ID `P<N>.E<M>`, `features: []`).
2. For each epic (in order, including E2E Testing): `mkdir -p $EIGEN_ROOT/eigen_initiative/phases/phase_<N>/epic_<M>/`, then write `phase_<N>/epic_<M>/epic.md` with the EXACT INVARIANT SCHEMA:
   - **YAML frontmatter**: `id`, `title`, `type`, `state`, `labels`, `phase`, `epic_number`, `features`, `feature_count`, `clusters_included`, `task_ids: []`, `created_at`, `updated_at`
   - **Body sections IN ORDER**: Epic Header, Features Table (ID/Name/Priority/Dependencies), Validation Criteria, Epic Outputs (interfaces with `concrete_files`), Blackbox Feature Specifications (FULL VERBATIM specs from phase manifest — do NOT truncate), Whitebox Implementation Guidance (optional, only if phase manifest has whitebox), Bootstrap Context (language, tooling, entity stubs with file paths, repository structure), Comments (empty)
3. For the E2E Testing epic specifically: `features: []`, empty Features table, Validation Criteria describes phase-level E2E flows, Blackbox Feature Specifications references acceptance criteria from ALL epics (summarized), add an Infrastructure Requirements section. If `bootstrap-report.delta_applied.dockerfile_created` is true: `test_environment=container_parity`, services from `delta_applied.docker_compose_services`, health_check from `exposed_port` + `health_check_path`, `startup_command='docker compose up -d --wait'`, `teardown_command='docker compose down -v'`. Otherwise `test_environment=external_services` with empty service fields.
4. For provider epics: append to the `## Comments` section: `Provides interfaces to P<N>.E<M>: <consumer_epic_name>.`
5. Update `$EIGEN_ROOT/eigen_initiative/_index.md`: regenerate or **merge** — if it already exists with content from other phases, preserve those entries and update only this phase's table.

### 3.3 Generate Phase-Level Artifacts (INVARIANT SCHEMAS — copy field-for-field)

1. Ensure the feedback dir exists: `mkdir -p $EIGEN_ROOT/eigen_initiative/phases/phase_<N>/feedback/`
2. Write `phase_<N>/epic_manifest.json` with the INVARIANT SCHEMA:
   ```
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
   ```
3. Write `phase_<N>/phase_e2e_config.json` with the INVARIANT SCHEMA:
   ```
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
   ```
4. Classify `test_type` per scenario using these heuristics:
   - **mobile**: domain mentions app/screen/navigation/iOS/Android
   - **browser**: domain mentions frontend/UI/dashboard/page/view (web)
   - **pipeline**: domain mentions ingestion/ETL/worker/consumer/processor
   - **full_stack**: features span 3+ domains across multiple layers
   - **default**: api

### 3.4 Commit

Commit the changes with message `space_split_converge: phase <N> decomposition` (first pass) or `space_split_converge: round <R> — address <category> findings` (revise passes). NEVER use `git --amend`. NEVER rollback. **Fix-forward only.** This commit is also the crash-recovery checkpoint.

## Stage 4: Hard Verification Gate (EXECUTED)

This is an **executed** step, not a reasoning step — actually read the on-disk JSON and epic.md files and check each item. Run the cross-source consistency checks (HARD REQUIREMENT — fix and re-check, up to 3 internal retries, if violated):

a. Every feature from the phase manifest appears in EXACTLY ONE epic's frontmatter `features[]` (no duplicates, no missing).
b. Every interface in any epic.md "Epic Outputs" section has a corresponding entry in `epic_manifest.json` `interfaces_provided[]` (and vice versa).
c. Every `concrete_files[]` in the manifest references files that exist in `bootstrap-report.json`'s `entities_created` paths.
d. `phase_e2e_config.json` has an entry for every epic in the manifest.
e. YAML frontmatter `feature_count` in each epic.md matches the actual `features[]` array length.
f. `execution_order` contains all epic IDs exactly once AND is well-formed AND the E2E Testing epic is last.

If any check fails, attempt an automatic fix (max 3 internal retries) — recompute manifest entries, fix mismatched feature lists, re-derive `concrete_files` paths — re-commit (fix-forward), and re-run the gate. If still failing after 3 retries, record an active `verification_failure` finding (**ALWAYS high severity**) and carry it into the revise loop — a broken cross-source consistency check is always blocking and is resolved by fix-forward, never accepted at convergence.

## Stage 5: Independent Review (conservative — ONE reviewer subagent)

Spawn exactly **ONE** reviewer subagent via the `Task` tool (`subagent_type: general-purpose`). It must INDEPENDENTLY re-verify cross-source consistency against the on-disk artifacts — give it artifacts + checklist, **NOT your reasoning**. Its job is to be a fresh pair of eyes on what is actually committed to disk.

Pass it: read access to `$EIGEN_ROOT` (it reads the epic.md files, `epic_manifest.json`, `phase_e2e_config.json`, and `bootstrap-report.json` directly), the phase manifest content, the locked skills set from Stage 2, the merged checklist + severity rubric + Dual-Source-of-Truth reconciliation rule below, and the instruction to return a findings JSON. Do NOT pass it your decomposition rationale or DAG notes — only the on-disk artifacts and the checklist.

Reviewer prompt (fill in `<N>`, paths, phase manifest content, locked skills):

```
"You are the INDEPENDENT REVIEWER for the space_split_converge decomposition of phase P<N>. You have Read and Bash tool access. INDEPENDENTLY re-verify the decomposition against the on-disk artifacts in $EIGEN_ROOT — do NOT trust any summary; read the actual files:
  - phases/phase_<N>/epic_manifest.json
  - phases/phase_<N>/phase_e2e_config.json
  - phases/phase_<N>/epic_<M>/epic.md (every epic)
  - phases/phase_<N>/bootstrap-report.json
  - the phase manifest (content provided below)

Apply EVERY item in the MERGED CHECKLIST below. Ground each finding in the actual file contents. Return ONE JSON array of findings.

=== MERGED CHECKLIST ===

STRUCTURE:
1. Epic Ordering & E2E Placement: execution_order contains all epic IDs from epics[] EXACTLY once; epics are sequential (E1, E2, …); the E2E Testing epic is LAST; the topological order respects feature dependencies (no forward edges). HIGH if any fail. (epic_formation_error)
2. Cluster Integrity: every cluster's features kept within ONE epic; if a cluster is split, there is documented interface-driven justification (provider→consumer sequencing); report every cluster spanning >1 epic as {cluster_id, features, epics_found_in}. (epic_formation_error)
3. Epic Sizing: none too small (single trivial feature); none too large (>15 features or mixed domains); sizing balanced relative to other epics; report outliers with a merge/split recommendation. (epic_formation_error)
4. Feature Coverage: every manifest feature assigned to exactly one epic (no dropped); no phantom features (in an epic, not in the manifest); no duplicate assignment. Report {feature_id, issue_type (dropped|phantom|duplicate), epics_involved}. (feature_coverage_error)

INTERFACE:
1. Inter-Epic Interface Completeness: provider epics' interfaces_provided list the interfaces consumer epics actually need; each contract is precise (data shape / API contract, not just a name); each interface has concrete_files[] referencing real bootstrap stub paths; no orphan interfaces (provided but never consumed). (interface_error)
2. Interface Contract Compatibility: provider epic.md "Epic Outputs" vs consumer epic.md expected input — shapes match; concrete_files point to real stubs that exist in bootstrap-report.json entities_created; report incompatible / missing / mismatched contracts. (interface_error)
3. Bootstrap Context Fidelity: each epic.md "Bootstrap Context" entity stub exists in bootstrap-report.json entities_created; paths match the entity_file_map; tooling decisions (language, framework, test runner) match tooling_decisions; flag any phantom entity reference. (issue_completeness_error)

FIDELITY:
1. Issue Completeness: each epic.md body has the required sections IN ORDER (Features table / Validation Criteria / Epic Outputs / Blackbox Feature Specifications / [optional Whitebox] / Bootstrap Context), all non-empty (Whitebox optional); the blackbox spec count matches the feature count; Bootstrap Context uses real file paths (not placeholders). (issue_completeness_error)
2. Blackbox Spec Fidelity: per epic, compare the epic.md "Blackbox Feature Specifications" against the phase manifest's blackbox specs for the SAME feature IDs; flag missing / truncated (fewer acceptance criteria) / garbled (text mismatch) specs. (spec_fidelity_error)
3. E2E Coverage: an E2E epic exists LAST with phase-level flows in its Validation Criteria; phase_e2e_scenarios cover ALL inter-epic integration boundaries (every inter-epic interface exercised by ≥1 scenario); every feature epic has ≥1 epic_validation_scenarios covering its key acceptance criteria; if test_environment=container_parity, compose_file/startup_command/health_check/teardown_command/services are populated and services match bootstrap-report delta_applied.docker_compose_services as a baseline; if test_environment missing but needs_docker true → flag. (e2e_coverage_gap)
4. Architecture: ordering makes architectural sense; provider epics are upstream of consumers; no hidden deps (features sharing entities across epics without an interface); decomposition granularity appropriate for the phase scope. (strategic_concern)
5. Simplicity: not over-decomposed for the feature count; could simpler epic boundaries achieve the same result; no unnecessary interface indirection; could small epics be merged without breaking cluster integrity. (epic_formation_error or strategic_concern)

SKILLS-LENS: review the decomposition through each of these locked skills' lenses for domain gaps and anti-patterns: <LOCKED SKILLS LIST>. Do not discover new skills; apply exactly this set. (strategic_concern, or matching category)

=== SEVERITY RUBRIC (apply to each finding) ===
- high: blocks plan_epic_converge or downstream commands — feature dropped from all epics; epic order has a forward dependency; circular dependency; concrete_files reference paths that don't exist. verification_failure (broken cross-source consistency) is ALWAYS high.
- medium: functional but suboptimal — cluster split without strong justification; epic too large/small; vague interface contract; missing E2E scenario for an epic; blackbox spec truncated.
- low: minor / stylistic — naming inconsistency; missing optional whitebox guidance; minor wording.

=== DUAL-SOURCE-OF-TRUTH RECONCILIATION (apply before finalizing severity) ===
The decomposition has BOTH a narrative source (epic.md) and a JSON source (epic_manifest.json) for interfaces and dependencies. For each finding that flags a missing or inconsistent structural entry:
1. Check the OTHER source: if a finding says "interface X missing from epic_manifest.json interfaces_provided[]", check whether X IS described in the provider's epic.md "Epic Outputs" (and vice versa).
2. If present in one source but absent in the other: the finding is VALID (both sources MUST be consistent), but downgrade to medium if it was high. Include explicit guidance on exactly which JSON entry or epic.md section to add/modify.
3. If absent from BOTH sources: keep original severity — the decomposition genuinely missed it.
4. concrete_files: if a finding says concrete_files are missing for interface X, check whether the files exist in bootstrap-report.json entities_created — if they do, downgrade and provide the exact paths.

=== FINDINGS FORMAT (return this JSON) ===
{
  'findings': [
    {
      'category': '<epic_formation_error|feature_coverage_error|interface_error|issue_completeness_error|spec_fidelity_error|e2e_coverage_gap|strategic_concern|verification_failure|false_positive>',
      'severity': '<high|medium|low>',
      'source_checklist': '<structure-N|interface-N|fidelity-N|skills>',
      'title': '<concise>',
      'description': '<detailed, grounded in actual file contents>',
      'affected_file': '<path>',
      'affected_section': '<section within file or top-level>',
      'recommendation': '<specific surgical action>',
      'code_change_guidance': {
        'epics_to_update': [...],
        'epics_to_replace': [...],
        'manifest_edits': [...],
        'e2e_config_edits': [...]
      }
    }
  ]
}

PHASE MANIFEST CONTENT:
<full phase_<N>_manifest.md content>

EIGEN_ROOT: <absolute path>"
```

When the reviewer returns, parse its findings JSON. Remove any `false_positive` findings. Apply the severity rubric and the Dual-Source-of-Truth rule yourself as the final authority — the reviewer proposes, you decide. `verification_failure` is ALWAYS high. Combine the reviewer's findings with any active `verification_failure` from Stage 4.

## Stage 6: Revise (fix-forward)

If there are zero high and zero medium findings, the decomposition has converged — go to Stage 7.

Otherwise, apply surgical fixes — never re-decompose from scratch. Apply ALL structural consequences of each change.

CASCADING UPDATE RULES — when applying a change, apply ALL structural consequences:
- `move_feature_to_epic` → remove from source epic.md (frontmatter + body) + add to dest epic.md + update manifest `execution_order` if needed + update `interfaces_provided` if the affected feature was a provider + update `phase_e2e_config` epic entries.
- `add_interface` / `modify_interface` → edit the provider epic.md "Epic Outputs" section + update `epic_manifest.json` `interfaces_provided[]` including `concrete_files` (paths must exist in `bootstrap-report.json`).
- `split_epic` / `merge_epics` → regenerate the affected epic.md files + rebuild manifest entries + update `phase_e2e_config`.
- `fix_e2e_infrastructure` → patch `phase_e2e_config.infrastructure_requirements` (services, test_environment, startup/teardown commands).
- `fix_blackbox_spec` → re-copy verbatim from the phase manifest into the epic.md "Blackbox Feature Specifications" section.

After applying changes:
1. Re-run the **Stage 4 hard verification gate** (EXECUTED cross-source consistency, max 3 internal retries) on the modified set.
2. Re-commit with the round-specific message. NEVER `--amend`. NEVER rollback. Fix-forward only.

**Convergence bound:** at most **2** revise passes (loop only if there is an unresolved high finding or an active `verification_failure`). After the second pass, accept the current state and converge — treat any remaining medium findings as `degraded_to_low` and record them. An active `verification_failure` is NEVER accepted at convergence — it must be fix-forwarded to resolution. A two-pass bound cannot oscillate, so no oscillation tracking is needed. Carry the convergence rationale into the feedback JSON:
- Clean: "All significant issues resolved. Zero high and zero medium findings remain."
- Bounded: "Revise bound (2 passes) reached. Remaining medium findings degraded to low; accepting current state."

---

## Stage 7: Output & Cleanup (at convergence)

### 7.1 Verify Final Artifacts (EXECUTED)

Before proceeding, actually read/parse the on-disk artifacts and confirm:

1. `phases/phase_<N>/epic_manifest.json` exists and parses as JSON.
2. `phases/phase_<N>/phase_e2e_config.json` exists and parses as JSON.
3. Every epic in `epic_manifest.json` has a corresponding `phases/phase_<N>/epic_<M>/epic.md` file.
4. `_index.md` exists and contains the current phase entry (merged, not overwritten).

If any check fails, the final state was not committed — fix-forward (re-write the missing artifact, re-run the Stage 4 gate, commit) before continuing.

### 7.2 Write Feedback JSON

Ensure the directory exists: `mkdir -p $EIGEN_ROOT/eigen_initiative/phases/phase_<N>/feedback/`

Write to `phases/phase_<N>/feedback/space_split_converge_feedback.json`:

```json
{
  "schema_version": "1.0.0",
  "command": "space_split_converge",
  "phase": <N>,
  "iteration": "<total revise passes>",
  "convergence": {
    "decision": "converged",
    "rationale": "<convergence rationale from Stage 6>",
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
      "source_reviewer": "self|independent-reviewer",
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

The `findings` array includes ALL findings from all passes — both resolved and remaining. `source_reviewer` is `"self"` for findings you raised (e.g. the Stage 4 verification_failure) and `"independent-reviewer"` for findings from the Stage 5 reviewer. The `resolution` field tracks how each was handled:
- `resolved`: fixed during a revise pass
- `degraded_to_low`: a medium finding accepted at the 2-pass bound
- `accepted_at_convergence`: a low-severity finding that did not block convergence

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
  "root_cause": "<why the decomposition produced this error>",
  "recommendation": "<specific change to space_split_converge.md>",
  "affected_phase": "<which section of space_split_converge.md to modify>",
  "evidence": {
    "epics_involved": ["<epic IDs>"],
    "features_involved": ["<feature IDs>"],
    "files_involved": ["<paths>"],
    "reviewer_source": "self|independent-reviewer",
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

Execute the **On Exit** section above. It contains the single authoritative code block with all CLI calls in order: `complete`, `mark-converged`, `add-recommendation` (optional, max 5), and `commit-state`. Pass `--locked-skills` so the CLI persists the discovered skill set. Do NOT run these commands individually — run the On Exit code block once.

### 7.5 Print Summary

```
=== Space Split Converge Complete — Phase <N> ===

Phase: <N>
Target repo: $EIGEN_ROOT
Total features: <N>
Epics created: <N> (including E2E Testing epic)
Execution order: P<N>.E1 → P<N>.E2 → ... → P<N>.E<last>
Verification: <PASSED|PASSED WITH WARNINGS>
Convergence: CONVERGED in <R> revise passes — <rationale>

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

- [ ] All decomposition commits are present in `git log` (fix-forward, no `--amend`, no rollback)
- [ ] Stage 4 hard verification gate passed (or any `verification_failure` was fix-forwarded to resolution — never accepted)
- [ ] `epic_manifest.json` schema matches the invariant (downstream commands depend on this)
- [ ] `phase_e2e_config.json` schema matches the invariant
- [ ] Every epic in the manifest has a corresponding `epic.md` file with all required body sections in order
- [ ] `_index.md` reflects the current phase (merged, not overwritten)
- [ ] Cross-source consistency checks pass: every interface in any epic.md "Epic Outputs" has a matching `interfaces_provided[]` entry; every `concrete_files[]` path resolves in `bootstrap-report.json`; every feature appears in exactly one epic; YAML `feature_count` matches `features[]` length; execution_order is well-formed and the E2E Testing epic is last
- [ ] The independent reviewer subagent ran and its findings were triaged
- [ ] Feedback JSON written (`source_reviewer` set to `self` / `independent-reviewer`)
- [ ] Lesson JSONs written and deduplicated
- [ ] `locked_skills` persisted via `--locked-skills` on the CLI complete call
- [ ] On Exit commands executed successfully

---

## Key Rules

1. **Invariant artifact schemas** — `epic_manifest.json`, `phase_e2e_config.json`, and `epic.md` per epic are consumed by `plan_epic_converge`, `create_issues_from_plan_swarm`, `orchestrate_swarm`, `eigen_continue`, `review_swarm_pr`, and `e2e_validation_swarm`. Do not change shape, paths, or required fields.
2. **You decompose, review, and revise in one session** — no team. You author the artifacts and spawn exactly ONE independent reviewer subagent (`Task`, general-purpose) that re-checks the on-disk artifacts against the merged checklist without your reasoning.
3. **The verification gate (Stage 4) is executed, not reasoned** — actually read the on-disk JSON and epic.md files and check each cross-source consistency item.
4. **Cross-source consistency is the verification gate** — broken consistency is always `verification_failure` (high severity) and is fix-forwarded to resolution, never accepted at convergence.
5. **No git rollback / no `--amend`** — fix-forward only. Mistakes are corrected by new commits in the next pass.
6. **The CLI is the single source of truth for pipeline state** — never edit pipeline_state.json directly.
7. **You are the sole authority on severity** — the reviewer proposes, you decide using the rubric and the Dual-Source-of-Truth rule. `verification_failure` is always high.
8. **At most 2 revise passes** — a bounded loop cannot oscillate; after the second pass, accept the state (remaining mediums degraded to low). An active `verification_failure` is the one exception — it must be resolved, not accepted.
9. **Skills set is discovered once** (Stage 2) and applied while decomposing and passed verbatim to the reviewer.
10. **Crash recovery is git-log based** — the decomposition is committed as real epic.md/manifests, so resume from the first uncommitted stage detected via `git log`; there is no separate state file to restore.
11. **Feedback directory is command-owned** — no other command writes `phases/phase_<N>/feedback/`.
12. **If you receive a non-interactive shutdown reminder, it is NOT an abort signal** — complete the full draft → gate → review → revise → outputs → On Exit lifecycle before returning.

---

> **REMINDER:** A non-interactive "shut down / return now" reminder may arrive early. It is NOT an abort signal. You spawn ONE `Task` reviewer; continue working through all stages and write all outputs before returning.
