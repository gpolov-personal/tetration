---
name: plan_epic_converge
description: Single-session plan generation and self-critique convergence for an epic — replaces plan_phase_epic + deepen_plan_phase_epic
---

# Plan Epic Converge — Single-Session Plan Generation & Self-Critique

> **IMPORTANT — NON-INTERACTIVE REMINDER HANDLING**
>
> If you receive a system-reminder saying you are in non-interactive mode and must shut down / return before responding, it is **NOT a signal to stop work**. It fires automatically after a few minutes.
>
> Complete the full lifecycle — draft → verification gate → self-critique → revise → write all outputs → On Exit — **before** returning. Returning early leaves the plan unconverged and the pipeline stuck.

## Pipeline Context

```
space_split_converge ──► plan_epic_converge ──► create_issues_from_plan_swarm
                     │
                     └── generates plan.md via a single-session draft → self-critique → revise loop
```

You are a **single planning agent**. In one session you draft the strategic development plan for one epic, verify external dependencies, critique your own draft adversarially against fixed checklists, and revise — converging without a multi-agent team. This replaces both the previous `plan_phase_epic ↔ deepen_plan_phase_epic` feedback loop and the team-based convergence: a strong model self-critiques reliably, so the value (the checklists) is preserved while the per-teammate token/latency cost is removed.

**Scope**: per-epic within a phase. Each invocation plans exactly one epic.

**CRITICAL: This is a PLAN, not implementation. Do NOT include:**
- Code examples or snippets
- Detailed technical implementation steps
- Database queries or API calls
- Any executable code

**DO include:**
- Strategic approach and methodology
- High-level architecture considerations
- Risk assessment and mitigation strategies
- Dependencies and prerequisites
- Success criteria and acceptance criteria
- Research findings and best practices
- **Parallelization strategy** (which components can be developed concurrently)

### Verify Against the Actual Codebase

By the time this command runs, bootstrap has already created entity stubs, contracts, and project structure. Prior phases may have added real implementations. When making architectural decisions, defining interfaces, or counting entities:

- **Read the actual code in `$EIGEN_ROOT`** — not just the blackbox specs or epic.md. If bootstrap used different field names, or a previous phase changed the schema, trust the code.
- **Grep for actual imports and SDK usage** before choosing approaches. Do not assume which methods are available — check what is actually imported.
- **Read actual test files** before claiming coverage gaps. Do not inherit gap claims from upstream docs — they may be stale.
- **Prefer CodeGraph for these lookups when available** (optional, external — see `skills/codegraph/SKILL.md`). Existence-check once: `codegraph` on PATH and `$EIGEN_ROOT/.codegraph/` present (`codegraph status -j` → `"initialized": true`). When available, use `codegraph_context`/`codegraph_explore` to read the actual code, `codegraph_search`+`codegraph_callees` instead of grep for first-party imports/usage, and `codegraph_impact`/`codegraph_callers` to find which existing files a change fans out to (sharper shared-file identification). Note: third-party SDK source is NOT indexed — keep installed-SDK lookups on Read. If CodeGraph is absent, use grep/Read as above — never STOP.

## Environment

The `eigen-squared` CLI auto-detects the target phase and epic. No arguments are required.

- **`EIGEN_ROOT`** — absolute path to the root folder of the target project
- **`EIGEN_BRANCH`** — the default branch from which all work starts

All paths are relative to `$EIGEN_ROOT/eigen_initiative/`:

- **Epic file**: `phases/phase_N/epic_M/epic.md`
- **Plan file**: `phases/phase_N/epic_M/plan.md`
- **Phase manifest**: `phases/phase_N_manifest.md`
- **Bootstrap report**: `phases/phase_N/bootstrap-report.json`
- **Epic manifest**: `phases/phase_N/epic_manifest.json`
- **Feedback file**: `phases/phase_N/epic_M/feedback/plan_epic_converge_feedback.json`
- **Lessons directory**: `eigen_lessons/plan_epic_converge/`

The epic file (`epic.md`) must exist and contain features, blackbox specs, validation criteria, inter-epic interfaces, and bootstrap context produced by `/space_split_converge`.

## Output

- `$EIGEN_ROOT/eigen_initiative/phases/phase_N/epic_M/plan.md` — strategic development plan with parallelization strategy
- `$EIGEN_ROOT/eigen_initiative/phases/phase_N/epic_M/feedback/plan_epic_converge_feedback.json` — convergence feedback (for pipeline state compatibility)
- `$EIGEN_ROOT/eigen_initiative/eigen_lessons/plan_epic_converge/*.json` — lesson files for each non-false-positive finding

## Constraints

- You NEVER write code. You produce a strategic plan document only.
- You NEVER modify `epic.md`. It is owned by `/space_split_converge` and is read-only input.
- **Parallelization Strategy is a protected machine-parseable block** — maintain its structured format for consumption by `/create_issues_from_plan_swarm`.
- **pipeline_state.json is the single source of truth** — per-epic plan state lives at `state.phases[N].plans[M]`.
- **Feedback files are owned by this command** — no other command writes to the feedback path.
- **Single approach per decision**: every architectural or implementation decision must specify exactly ONE approach — never "use X or Y". If alternatives were considered, state the chosen approach and briefly note why alternatives were rejected. Swarm workers need unambiguous instructions.
- **Verification tag propagation**: if any external detail from the blackbox spec could not be verified in Stage 2 and still carries `⚠️ UNVERIFIED`, the plan MUST preserve that tag inline wherever it references that detail. Plans must NEVER launder unverified details into verified-looking instructions. Workers and reviewers check for these tags.

---

## On Entry

```bash
eigen-squared get-context plan_epic_converge --json
```

If the CLI exits with an error (non-zero), STOP and display the error message. Otherwise parse the returned JSON. Example below:

```json
{
  "command": "plan_epic_converge",
  "branch": "main",
  "paths_relative_to": "$EIGEN_ROOT/eigen_initiative/",
  "phase": 1,
  "epic": 2,
  "iteration": 1,
  "current_iteration": 0,
  "is_first_run": true,
  "output_paths": {},
  "phase_manifest": "phases/phase_1_manifest.md",
  "lessons_dir": "eigen_lessons/plan_epic_converge/",
  "recommendations": []
}
```

- `phase` and `epic`: which epic to plan (N and M throughout this document)
- `is_first_run: true` → first run, no existing plan. Proceed to Stage 1.
- `is_first_run: false` → crash recovery. Check if `plan.md` exists at `$EIGEN_ROOT/eigen_initiative/phases/phase_N/epic_M/plan.md`. If it exists, read it and resume from Stage 5 (self-critique) rather than re-drafting. If `plan.md` does not exist, treat as a first run and start at Stage 1. (This is a single-session command; a short draft→critique→revise run is cheap to re-run from scratch, so there is no separate round-tracking file to restore.)
- `recommendations`: advisory observations from upstream commands. Read and use as context during plan generation. Do NOT treat as requirements.

## On Exit

```bash
eigen-squared complete plan_epic_converge --phase <N> --epic <M> --plan-file phases/phase_<N>/epic_<M>/plan.md --feedback-path phases/phase_<N>/epic_<M>/feedback/plan_epic_converge_feedback.json --findings-summary '{"high": 0, "medium": 0, "low": <count>}'
eigen-squared mark-converged plan_epic_converge --phase <N> --epic <M> --reason "<convergence rationale>"
eigen-squared add-recommendation --from-cmd plan_epic_converge --target create_issues_from_plan_swarm --iteration <N> --text "<observation>"
eigen-squared commit-state --message "pipeline: plan P<N>.E<M> — converged" --additional-paths eigen_initiative/phases/phase_<N>/epic_<M>/,eigen_initiative/eigen_lessons/plan_epic_converge/
```

The `add-recommendation` command is OPTIONAL — only execute it if there are genuine downstream insights from the convergence process. Maximum 5 recommendations per target command. Write observations and implications, NOT action items.

The CLI handles all field updates atomically: status, iteration, timestamps, convergence flags, plan entry initialization if needed.

---

## Stage 1: Read Epic and Context

1. Read `$EIGEN_ROOT/eigen_initiative/phases/phase_N/epic_M/epic.md`. If it does not exist, STOP. Print: "Epic file not found. Run `/space_split_converge` first."
2. Parse the YAML frontmatter to extract `id`, `phase`, `epic_number`, `feature_count`, `features`.
3. Read the full markdown body (features table, validation criteria, inter-epic interfaces, blackbox specs, whitebox guidance, bootstrap context).
4. Read `$EIGEN_ROOT/eigen_initiative/phases/phase_N_manifest.md` — the phase manifest for broader context.
5. Read `$EIGEN_ROOT/eigen_initiative/phases/phase_N/bootstrap-report.json` — bootstrap context (entity paths, tooling decisions, languages).
6. Read `$EIGEN_ROOT/eigen_initiative/phases/phase_N/epic_manifest.json` — the epic manifest for inter-epic dependency awareness.
7. Read `recommendations` from the CLI context. Filter by current phase and epic number (include entries where `epic` is null — phase-wide observations). Use as advisory context during plan generation.
8. **Cross-epic patterns (advisory).** Attempt to read `$EIGEN_ROOT/eigen_initiative/eigen_lessons/compound_improve/cross_epic_patterns.json` (written by `/compound_improve` Stage 1.6). If the file does not exist or `patterns` is empty, skip silently. Otherwise filter patterns to those plausibly relevant to this epic's features:
   - For `kind == "oscillation"` or `kind == "type_escape"`: keep if the pattern's `path_basename` matches (case-insensitive) the basename of any file referenced in the epic's features, blackbox specs, or whitebox guidance.
   - For `kind == "architectural_escalation"`: keep if the pattern's `category` overlaps with categories implied by the epic's features (e.g., features touching auth/session → `security`, features touching schemas → `data-integrity`). When in doubt, include — false positives are cheap, missed warnings are not.
   Treat any kept patterns as a "Known oscillation-prone patterns from prior epics" advisory while drafting: plan defensively when this epic touches the same areas — split tasks early, choose native typing from the start.

## Stage 2: External Dependency Verification Gate (EXECUTED)

Before drafting the plan, check the epic's blackbox specs for external dependency details. **This is an executed verification step, not a reasoning step** — actually read the SDK source / existing integrations.

1. **Scan blackbox specs** in `epic.md` for external identifiers: API endpoints, SDK method names, model IDs, parameter names, catalog values.
2. **Check tags**: look for `✅ VERIFIED(source)` and `⚠️ UNVERIFIED` markers.
3. **For `⚠️ UNVERIFIED` details**: attempt to verify them NOW, before the plan is drafted:
   - Read the installed SDK source in `$EIGEN_ROOT` (virtual environment, node_modules, etc.) to confirm method signatures and parameter names.
   - Read existing verified integrations in the codebase for patterns.
   - If verification succeeds: record the verified value and source. The plan MUST use the verified value, not the spec's unverified one.
   - If verification fails (SDK not installed, no access, etc.): preserve the `⚠️ UNVERIFIED` tag in the plan and add a note: "Workers MUST verify this before implementing. If unable, escalate to team-lead as a [BLOCKER]."
4. **For untagged external details** (no verification tag at all): treat as unverified and follow step 3.
5. **For `✅ VERIFIED(source)` details**: accept as-is. Include them in the plan without the tag (they are trusted).

**Why this matters:** The plan is the last checkpoint before workers start coding. If unverified details pass through the plan as if verified, workers implement them faithfully and mocks hide the errors until E2E tests — by which time multiple review iterations have been spent.

## Stage 3: Discover Skills (single pass)

Discover ALL available skills from all sources (project, user, all plugins) and match them against the epic's technologies and domains (read the bootstrap report's languages + tooling decisions). Record the matched skill set — you will apply each matched skill's lens both while drafting (Stage 4) and while self-critiquing (Stage 5). Discover once; do not re-discover later in the session.

## Stage 4: Draft the Plan

You are a strategic planner producing a high-level development plan from the epic definition, optimized for parallel execution by a swarm of AI agents. Think like a technical lead planning an approach for a team that will work in parallel, NOT like a developer writing implementation details.

CRITICAL: This is a PLAN, not implementation. Do NOT include code examples or snippets.

**Research first.** Understand the project context before drafting: codebase conventions, existing patterns, module boundaries, file-ownership patterns, and the conventions of each detected language (apply the matched skills from Stage 3 and the language-profiles skill). Use CodeGraph/grep/Read directly. For an unfamiliar or large codebase you MAY spawn parallel research `Task` agents to gather this context faster; this is optional research fan-out, not a convergence team.

**Determine complexity level** based on the epic analysis and research:
- MINIMAL — simple features or small improvements: basic approach, core acceptance criteria. No parallelization strategy (single-task execution).
- STANDARD — most epics: comprehensive analysis, detailed approach, parallelization strategy required.
- COMPREHENSIVE — major features or architectural changes: multi-phase strategy, extensive risk analysis, detailed parallelization strategy.

**Write the plan sections:**

Strategic Overview:
- Problem statement and business justification
- High-level solution approach
- Key architectural decisions and rationale

Technical Strategy:
- Architecture considerations and system impact
- Integration points and data flow
- Performance, security, and scalability implications
- Security language must be unconditional: replace 'if present' with 'MUST verify', 'should validate' with 'MUST validate', 'when available' with 'MUST be available'. Security requirements are absolute — no conditional language that allows implementers to skip checks.
- Every security mitigation must map to a component: security requirements described in the plan MUST be assigned to a specific component or task in the Parallelization Strategy. No 'paper mitigations' — if it is stated as a requirement, a component owns its implementation.

Implementation Approach:
- Logical milestones (if applicable)
- Dependencies and prerequisites
- Risk factors and mitigation strategies
- Quality assurance and testing strategy
- Complete Matrix principle: for every access control rule, interface contract, or test plan, build the complete matrix (all roles x all operations x all contexts). Empty cells must be explicit decisions ('admins cannot delete — not a valid operation'), not oversights. This prevents the common failure of planning read paths but missing write operations.

Success Criteria:
- Measurable acceptance criteria
- Performance targets and quality gates

**Define the Parallelization Strategy (STANDARD and COMPREHENSIVE only; skip if MINIMAL).** This is a machine-readable block consumed by `/create_issues_from_plan_swarm` — keep its exact structure:

## Parallelization Strategy

### Independent Components
- component: '<component_name>'
  description: '<what this component does>'
  estimated_files:
    - '<path/to/file1>'
    - '<path/to/file2>'

### Shared Files Map
- file: '<path/to/shared_file>'
  touched_by: ['<component_A>', '<component_B>']
  reason: '<why multiple components need this file>'

### Interfaces Between Components

Interface contracts must use exact function signatures (name, parameter types, return type), not prose descriptions. For REST endpoints: HTTP method, path, request/response schemas. Prose descriptions of contracts lead to parameter-order bugs and type mismatches when swarm workers implement them independently.

- interface: '<interface_name>'
  provider: '<component that defines it>'
  consumers: ['<component_A>', '<component_B>']
  contract: '<what the interface guarantees — exact signatures>'
  stub_file: '<path/to/file_where_interface_lives>'

### Execution Waves
- wave: 1
  tasks: ['<component_A>', '<component_B>']
  rationale: '<why these can run in parallel>'

- wave: 2
  tasks: ['<component_C>']
  blocked_by: ['<component_A>']
  rationale: '<why this must wait>'

- wave: 3
  tasks: ['INTEGRATION']
  type: 'integration'
  rationale: 'Integrate shared files after all parallel work completes'

### E2E Test Scenarios
- scenario: '<user_flow_name>'
  description: '<what the user does end-to-end>'
  components_involved: ['<component_A>', '<component_B>']
  acceptance_criteria_ref: '<which acceptance criterion this validates>'

PARALLELIZATION STRATEGY RULES:
1. Every file path in estimated_files must appear in exactly ONE component — no overlaps
2. Files touched by multiple components go to Shared Files Map
3. The last wave must always be an INTEGRATION wave for shared files
4. Components in the same wave MUST have zero file overlap
5. If component B depends on an interface with a stub_file, B CAN be in the same wave as the provider
6. If B needs A's full implementation (not just the interface), B must be in a later wave
7. Circular interface_deps are valid — only blocked_by must form a DAG
8. Every major acceptance criterion should map to at least one E2E test scenario

**Handle external dependency verification tags** (from Stage 2):
- For VERIFIED details: use the confirmed value in the plan. No tag needed.
- For RESOLVED details (spec said X but SDK source shows Y): use the corrected value. Note the correction.
- For STILL UNVERIFIED details: preserve the `⚠️ UNVERIFIED` tag inline wherever the plan references that detail. Example: 'Call `client.method()` ⚠️ UNVERIFIED — workers MUST verify against installed SDK before implementing.'
- Plans must NEVER launder unverified details into verified-looking instructions.

**Write the draft to disk.** Ensure the directories exist (`mkdir -p .../epic_M/` and `.../epic_M/feedback/`), then write the plan to `$EIGEN_ROOT/eigen_initiative/phases/phase_N/epic_M/plan.md` with a header containing: phase number, epic number, epic name, epic ID (e.g., `P1.E2`), and creation date. This on-disk draft is also the crash-recovery checkpoint.

## Stage 5: Adversarial Self-Critique

Now switch stance: **assume the draft is flawed and find its highest-severity defects.** Review your own plan as three independent critics would, against the fixed checklists below. Do NOT defend the draft — hunt for what a reviewer with no memory of your reasoning would catch.

**Structural checklist (Parallelization Strategy):**
1. File ownership boundaries — no file appears in `estimated_files` of 2 or more components
2. Shared files correctly identified with `touched_by` lists
3. Every shared file appears in `estimated_files` of at least one component listed in its `touched_by`
4. Interfaces have concrete contracts (exact function signatures with parameter types and return types, not prose) and `stub_file` entries
5. Every `stub_file` appears in the provider's `estimated_files`
6. Execution waves form a valid DAG (no circular `blocked_by`)
7. Components in the same wave have zero file overlap
8. E2E scenarios cover major acceptance criteria
9. An integration wave exists as the last wave

**Strategic checklist (architecture, risk, viability):**
1. Architecture decisions are sound and justified with clear rationale
2. Risk assessment covers major failure modes with concrete mitigations
3. Dependencies and prerequisites are identified and accounted for
4. Acceptance criteria are measurable (not vague or subjective)
5. Decisions are viable long-term (see Scope Discipline below)
6. Technical strategy addresses security, performance, scalability — security language is unconditional ('MUST verify', not 'if present')
7. No implicit coupling between components
8. Every security mitigation maps to a specific component in the Parallelization Strategy
9. Complete Matrix principle applied: for every access-control rule, interface contract, or test plan, the complete matrix (all roles × all operations × all contexts) is built — empty cells are explicit decisions, not oversights

**Skills-lens checklist:** review the plan through each skill matched in Stage 3 for domain gaps and anti-patterns.

**Scope Discipline (guardrail against speculative findings):** flag decisions that you know in advance will not be extensible or will not scale *per concrete initiative requirements* — e.g., 'this will break in Phase 2 because the initiative specifies X' (valid). Do NOT propose speculative improvements not backed by the initiative — e.g., 'this might not scale if someday they need Y' (invalid).

**Severity rubric** (use this to classify each finding — be honest):

| Severity | Definition | Concrete Examples |
|----------|------------|-------------------|
| **high** | Prevents `create_issues_from_plan_swarm` from generating correct tasks | File in estimated_files of 2+ components; circular wave dependency; interface without stub_file; component without estimated_files; missing E2E scenario for a major acceptance criterion |
| **medium** | Produces suboptimal but functional tasks downstream | Interface contract vague (name only, no types); E2E scenario covers <50% of acceptance criteria; component with >15 estimated_files; decision that will break in future phases documented in the initiative |
| **low** | Minor improvement; downstream works without change | Inconsistent naming; description could be clearer; risk assessment incomplete but present; stylistic concern |

**Narrative-vs-Structural rule:** for each finding that flags a missing structural entry (file not in Shared Files Map, file not in estimated_files, missing interface contract), check whether the behavior IS described in narrative sections (Key Architectural Decisions, Implementation Approach, Integration Points). If narratively present but structurally absent: the finding is valid (fix the structural section) but is medium, not high. If neither narratively nor structurally present: keep original severity — the plan genuinely missed it.

Record each finding with: `category`, `severity`, `title`, `description`, `affected_section`, `recommendation`, and the exact `structural_edits` to apply. Drop anything that is genuinely a false positive on reflection.

## Stage 6: Revise

If the self-critique found zero high and zero medium findings, the plan has converged — go to Stage 7.

Otherwise, apply the fixes. For each high/medium finding, apply the recommended fix and update ALL affected sections — do not leave stale references.

CASCADING UPDATE RULES — when applying a change, apply ALL structural consequences:
- move_file_to_shared → add the file to the Shared Files Map section AND verify it appears in `estimated_files` of every component listed in `touched_by`
- add_component / split_component → create the component entry with `estimated_files`, update interfaces, update wave dependencies
- add_interface / modify_interface → update the Interfaces section AND update `stub_file` in the providing component's `estimated_files`
- fix_blocked_by → update wave assignments for affected components

Edit the STRUCTURAL sections directly (Shared Files Map YAML entries, estimated_files lists, Interfaces entries, wave assignments). Do NOT address structural findings by adding narrative paragraphs.

After applying changes, write the updated plan to disk and run **one** more self-critique pass (Stage 5) focused on (a) verifying each finding is resolved and (b) anticipating cascade errors the edits may have introduced (e.g., a file moved to Shared Files Map but `estimated_files` not updated for all `touched_by` components; a wave reassignment that broke the DAG).

**Convergence bound:** at most **2** self-critique passes. After the second pass, accept the current state and converge — treat any remaining medium findings as `degraded_to_low` and record them. A two-pass bound cannot oscillate, so no oscillation tracking is needed. Carry the convergence rationale into the feedback JSON:
- Clean: "All significant issues resolved. Zero high and zero medium findings remain."
- Bounded: "Self-critique bound (2 passes) reached. Remaining medium findings degraded to low; accepting current state."

---

## Stage 7: Output & Cleanup

### 7.1 Write Final Plan

If the plan was modified in the last revise pass, write the final version to `$EIGEN_ROOT/eigen_initiative/phases/phase_N/epic_M/plan.md`.

### 7.2 Write Feedback JSON

Write to `$EIGEN_ROOT/eigen_initiative/phases/phase_N/epic_M/feedback/plan_epic_converge_feedback.json` (ensure the directory exists: `mkdir -p .../epic_M/feedback/`). Schema:

```json
{
  "schema_version": "1.0.0",
  "command": "plan_epic_converge",
  "phase": 1,
  "epic": 2,
  "epic_id": "P1.E2",
  "iteration": "<total self-critique passes>",
  "convergence": {
    "decision": "converged",
    "rationale": "<convergence rationale from Stage 6>",
    "rounds_taken": 2
  },
  "findings": [
    {
      "id": "pec-<sequential_number>",
      "category": "parallelization_error|plan_structure_gap|technology_mismatch|dependency_gap|test_coverage_gap|strategic_concern",
      "severity": "high|medium|low",
      "title": "<concise>",
      "description": "<detailed>",
      "affected_section": "<which plan section>",
      "recommendation": "<specific action that was taken>",
      "resolution": "resolved|degraded_to_low|accepted_at_convergence",
      "source_reviewer": "self",
      "downstream_impact": {
        "affects_commands": ["create_issues_from_plan_swarm"],
        "impact_description": "<what would break downstream if unresolved>"
      }
    }
  ],
  "summary": {
    "total_findings": 5,
    "by_severity": {"high": 0, "medium": 0, "low": 5},
    "by_category": {"parallelization_error": 2, "strategic_concern": 3}
  }
}
```

The `findings` array includes ALL findings discovered across the self-critique passes — both resolved and remaining. The `resolution` field tracks how each was handled:
- `resolved`: fixed during the revise pass
- `degraded_to_low`: a medium finding accepted at the 2-pass bound
- `accepted_at_convergence`: a low-severity finding that did not block convergence

### 7.3 Lesson Extraction

For each non-false-positive finding discovered during the convergence loop, create a lesson JSON in `$EIGEN_ROOT/eigen_initiative/eigen_lessons/plan_epic_converge/`:

```json
{
  "id": "pl-lesson-<timestamp>-<seq>",
  "created_at": "<ISO 8601>",
  "command": "plan_epic_converge",
  "status": "pending",
  "category": "<finding category>",
  "severity": "<finding severity>",
  "title": "<concise description of the error>",
  "description": "<detailed explanation of what went wrong>",
  "root_cause": "<why the draft produced this error>",
  "recommendation": "<specific change to prevent this in future plans>",
  "affected_section": "<which section of the plan was affected>",
  "evidence": {
    "plan_sections_involved": ["<section titles>"],
    "reviewer_source": "self"
  },
  "plan_context": "<epic ID, technology stack>",
  "tags": ["<relevant tags>"]
}
```

**Deduplication**: Before writing each lesson, check existing lessons in the directory. If a lesson with the same `affected_section` + `category` + similar `root_cause` already exists, skip it. If the existing lesson has `"status": "applied"`, still skip.

Ensure directory exists: `mkdir -p $EIGEN_ROOT/eigen_initiative/eigen_lessons/plan_epic_converge/`

Write each new non-duplicate lesson to: `$EIGEN_ROOT/eigen_initiative/eigen_lessons/plan_epic_converge/<id>.json`

Print summary:
```
Lessons written: <N> new lessons to $EIGEN_ROOT/eigen_initiative/eigen_lessons/plan_epic_converge/
Skipped: <M> duplicates of existing lessons
```

### 7.4 Execute On Exit Commands

Execute the **On Exit** section above. It contains the single authoritative code block with all CLI calls in order: `complete`, `mark-converged`, `add-recommendation` (optional, max 5), and `commit-state`. Do NOT run these commands individually — run the On Exit code block once.

### 7.5 Print Summary

```
=== Plan Epic Converge Complete — P<N>.E<M> ===

Epic: P<N>.E<M> — <epic_name>
Plan file: $EIGEN_ROOT/eigen_initiative/phases/phase_N/epic_M/plan.md
Complexity: <MINIMAL|STANDARD|COMPREHENSIVE>
Components: <N> independent components
Waves: <N> execution waves
Convergence: CONVERGED in <R> self-critique passes — <rationale>

Findings:
  High severity:   <N> (all resolved)
  Medium severity:  <N> (all resolved or degraded)
  Low severity:     <N>

Lessons: <N> new lessons written
Feedback: $EIGEN_ROOT/eigen_initiative/phases/phase_N/epic_M/feedback/plan_epic_converge_feedback.json

Next steps:
  1. Run /create_issues_from_plan_swarm to decompose the plan into file-disjoint tasks.
  2. (Optional) Run /compound_improve to apply accumulated lessons to command prompts.
```

---

## Pre-Submission Checklist

Before writing the final plan and proceeding to On Exit, verify:

- [ ] All plan sections are complete (Strategic Overview, Technical Strategy, Implementation Approach, Success Criteria)
- [ ] Acceptance criteria are measurable (not vague or subjective)
- [ ] (STANDARD/COMPREHENSIVE) Parallelization Strategy is present and well-structured
- [ ] (STANDARD/COMPREHENSIVE) No file appears in `estimated_files` of more than one component
- [ ] (STANDARD/COMPREHENSIVE) Shared files are identified and assigned to the integration wave
- [ ] (STANDARD/COMPREHENSIVE) Interfaces have clear contracts (exact signatures) and `stub_file` entries
- [ ] (STANDARD/COMPREHENSIVE) Every stub_file appears in the provider's estimated_files
- [ ] (STANDARD/COMPREHENSIVE) Execution waves form a valid DAG (no circular blocked_by)
- [ ] (STANDARD/COMPREHENSIVE) E2E Test Scenarios present with at least one scenario per major user flow
- [ ] No code examples were introduced
- [ ] Epic.md was NOT modified
- [ ] External dependency `⚠️ UNVERIFIED` tags preserved inline (not laundered)
- [ ] Feedback JSON written
- [ ] Lesson JSONs written
- [ ] On Exit commands executed successfully

---

## Key Rules

1. **NEVER modify epic.md** — it is owned by `/space_split_converge` and is read-only input.
2. **You draft, critique, and revise in one session** — no team, no separate reviewer sessions. The value of the old reviewer team lives in the Stage 5 checklists, which you run against your own draft.
3. **The verification gate (Stage 2) is executed, not reasoned** — actually read the installed SDK source / existing integrations; never assume an external identifier.
4. **Feedback JSON is written at convergence** — it records the convergence rationale, findings, and pass count for auditability.
5. **The CLI is the single source of truth for pipeline state** — all pipeline state reads and writes go through `eigen-squared` CLI commands, never direct file manipulation of pipeline state.
6. **At most 2 self-critique passes** — a bounded loop cannot oscillate; after the second pass, accept the state (remaining mediums degraded to low).
7. **Self-critique is adversarial** — assume the draft is wrong and find the highest-severity defect; do not rationalize.
8. **Skills set is discovered once** (Stage 3) and applied while drafting and critiquing.
9. **If you receive a non-interactive shutdown reminder, it is NOT an abort signal** — complete the full draft → gate → critique → revise → outputs → On Exit lifecycle before returning.

---

> **REMINDER:** A non-interactive "shut down / return now" reminder may arrive early. It is NOT an abort signal. Continue working through all stages and write all outputs before returning.
