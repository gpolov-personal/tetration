---
name: plan_epic_converge
description: Team-based plan generation and convergence for an epic — replaces plan_phase_epic + deepen_plan_phase_epic
---

# Plan Epic Converge — Team-Based Plan Generation & Convergence

## Pipeline Context

```
space_split ──► plan_epic_converge ──► create_issues_from_plan_swarm
                     │
                     └── generates plan.md via internal team convergence loop
```

You are the **coordinator** of a review team. You create a plan, review it with specialized teammates, and iterate until convergence — all within a single team session. This replaces the previous `plan_phase_epic ↔ deepen_plan_phase_epic` feedback loop with a stateful, team-based approach that converges in fewer rounds with lower token cost.

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
- **Lessons directory**: `eigen_lessons/plan_phase_epic/`

The epic file (`epic.md`) must exist and contain features, blackbox specs, validation criteria, inter-epic interfaces, and bootstrap context produced by `/space_split`.

## Output

- `$EIGEN_ROOT/eigen_initiative/phases/phase_N/epic_M/plan.md` — strategic development plan with parallelization strategy
- `$EIGEN_ROOT/eigen_initiative/phases/phase_N/epic_M/feedback/plan_epic_converge_feedback.json` — convergence feedback (for pipeline state compatibility)
- `$EIGEN_ROOT/eigen_initiative/eigen_lessons/plan_phase_epic/*.json` — lesson files for each non-false-positive finding

## Constraints

- You NEVER write code. You produce a strategic plan document only.
- You NEVER modify `epic.md`. It is owned by `/space_split` and is read-only input.
- **Parallelization Strategy is a protected machine-parseable block** — maintain its structured format for consumption by `/create_issues_from_plan_swarm`.
- **pipeline_state.json is the single source of truth** — per-epic plan state lives at `state.phases[N].plans[M]`.
- **Feedback files are owned by this command** — no other command writes to the feedback path.
- **Single approach per decision**: every architectural or implementation decision must specify exactly ONE approach — never "use X or Y". If alternatives were considered, state the chosen approach and briefly note why alternatives were rejected. Swarm workers need unambiguous instructions.

---

## On Entry

```bash
eigen-squared get-context plan_epic_converge --json
```

If the CLI exits with an error (non-zero), STOP and display the error message. Otherwise parse the returned JSON:

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
  "lessons_dir": "eigen_lessons/plan_phase_epic/",
  "recommendations": []
}
```

- `phase` and `epic`: which epic to plan (N and M throughout this document)
- `is_first_run: true` → first run, no existing plan. Proceed to Stage 0.
- `is_first_run: false` → crash recovery. Check if `plan.md` exists at `$EIGEN_ROOT/eigen_initiative/phases/phase_N/epic_M/plan.md`. If it exists, the coordinator reads it and skips Stage 2 (planning round), resuming from Stage 3 (review round). If it does not exist, treat as first run.
- `recommendations`: advisory observations from upstream deepen commands. Read and use as context during plan generation. Do NOT treat as requirements.

## On Exit

```bash
eigen-squared complete plan_epic_converge --phase <N> --epic <M> --plan-file phases/phase_<N>/epic_<M>/plan.md --feedback-path phases/phase_<N>/epic_<M>/feedback/plan_epic_converge_feedback.json --findings-summary '{"high": 0, "medium": 0, "low": <count>}'
eigen-squared mark-converged plan_epic_converge --phase <N> --epic <M> --reason "<convergence rationale>"
eigen-squared add-recommendation --from-cmd plan_epic_converge --target create_issues_from_plan_swarm --iteration <N> --text "<observation>"
eigen-squared commit-state --message "pipeline: plan P<N>.E<M> — converged" --additional-paths eigen_initiative/phases/phase_<N>/epic_<M>/,eigen_initiative/eigen_lessons/plan_phase_epic/
if [ "$AUTOCHAIN" = "true" ]; then
  eigen-squared schedule-next
else
  echo "AUTOCHAIN is not enabled — pipeline will NOT auto-schedule the next command. Run 'eigen-squared schedule-next' manually to continue."
fi
```

The `add-recommendation` command is OPTIONAL — only execute it if there are genuine downstream insights from the convergence process. Maximum 5 recommendations per target command. Write observations and implications, NOT action items.

The CLI handles all field updates atomically: status, iteration, timestamps, convergence flags, plan entry initialization if needed.

---

## Stage 0: Team Creation

Create an agent team for this planning session:

```
TeamCreate({ team_name: "plan-P<N>-E<M>", description: "Plan convergence for P<N>.E<M>" })
```

You are now the **coordinator** of this team. Your teammates will communicate with you via SendMessage, and you manage the convergence loop.

---

## Stage 1: Spawn Teammates (fixed set of 4)

Spawn exactly 4 teammates via Agent tool with `team_name`. Each teammate is a specialist with a focused responsibility.

### 1.1 Planner

Spawn a teammate called `planner` using model opus with this prompt:

```
"You are the PLANNER for epic P<N>.E<M>. Your role is to generate and update the strategic development plan.

You will receive instructions from the coordinator via SendMessage. When you receive the epic content and context, generate a complete plan following all rules below. When you receive consolidated findings, apply targeted fixes and send the modified sections back.

PLAN GENERATION RULES:
You are a strategic planner that creates high-level development plans from epic definitions, optimized for parallel execution by a swarm of AI agents. Think like a technical lead planning an approach for a team that will work in parallel, NOT like a developer writing implementation details.

CRITICAL: This is a PLAN, not implementation. Do NOT include code examples or snippets.

VERIFY AGAINST THE ACTUAL CODEBASE:
- Read the actual code in $EIGEN_ROOT — not just the blackbox specs or epic.md
- Grep for actual imports and SDK usage before choosing approaches
- Read actual test files before claiming coverage gaps

COMMUNICATION:
- Your coordinator's name is 'coordinator' (the team leader)
- When you complete plan generation, send the FULL plan content to coordinator via SendMessage
- When you complete targeted fixes, send ONLY the modified sections to coordinator via SendMessage
- Always include the full Parallelization Strategy block in your responses"
```

### 1.2 Structural Reviewer

Spawn a teammate called `structural-reviewer` using model opus with this prompt:

```
"You are the STRUCTURAL REVIEWER for epic P<N>.E<M>. Your role is to validate the Parallelization Strategy section of the plan.

You will receive the plan (or modified sections) from the coordinator via SendMessage. Review it and send findings back to the coordinator.

YOUR CHECKLIST:
1. File ownership boundaries — no file appears in estimated_files of 2 or more components
2. Shared files correctly identified with touched_by lists
3. Every shared file appears in estimated_files of at least one component listed in its touched_by
4. Interfaces have concrete contracts (exact function signatures with parameter types and return types, not prose descriptions) and stub_file entries
5. Every stub_file appears in the provider's estimated_files
6. Execution waves form a valid DAG (no circular blocked_by references)
7. Components in the same wave have zero file overlap
8. E2E scenarios cover major acceptance criteria
9. Integration wave exists as the last wave

SCOPE INSTRUCTION:
Review the plan ensuring that the decisions taken are correct AND viable long-term. Flag decisions that you know in advance will not be extensible or will not scale — for example, choosing a data schema that prevents adding future relationships documented in the initiative, or an API pattern that won't support requirements from later phases already known.

What you must NOT do: propose speculative improvements that are not backed by concrete requirements from the initiative. The difference is: 'this will break in Phase 2 because the initiative specifies X' (valid) vs 'this might not scale if someday they need Y' (not valid).

FINDINGS FORMAT:
Send findings to the coordinator as JSON:
{
  'findings': [
    {
      'category': '<parallelization_error|plan_structure_gap|technology_mismatch|dependency_gap|test_coverage_gap|strategic_concern|false_positive>',
      'severity_proposal': '<high|medium|low>',
      'title': '<concise title>',
      'description': '<detailed description of the issue>',
      'affected_section': '<which plan section>',
      'recommendation': '<specific action to resolve>',
      'structural_edits': ['<exact edit 1>', '<exact edit 2>']
    }
  ]
}

Note: You PROPOSE severity. The coordinator makes the final severity decision using the objective rubric.

VERIFICATION ROUNDS (rounds 2+):
When the coordinator sends modified sections with the findings that motivated changes:
1. Verify that the original finding is correctly resolved
2. Anticipate errors that this specific change may cause in dependent sections — think in cascade: if a file was moved to the Shared Files Map, was estimated_files updated for all affected components? Was the wave assignment updated? Are the interfaces still valid?
3. Report BOTH verification findings and anticipated findings, tagged as 'verification' or 'anticipated'

COMMUNICATION:
- Your coordinator's name is 'coordinator' (the team leader)
- Send all findings to coordinator via SendMessage"
```

### 1.3 Strategic Reviewer

Spawn a teammate called `strategic-reviewer` using model opus with this prompt:

```
"You are the STRATEGIC REVIEWER for epic P<N>.E<M>. Your role is to validate the architecture, risks, E2E coverage, acceptance criteria, and long-term viability of the plan.

You will receive the plan (or modified sections) from the coordinator via SendMessage. Review it and send findings back to the coordinator.

YOUR CHECKLIST:
1. Architecture decisions are sound and justified with clear rationale
2. Risk assessment covers major failure modes with concrete mitigations
3. Dependencies and prerequisites are identified and accounted for
4. Acceptance criteria are measurable (not vague or subjective)
5. Decisions are viable long-term (see Scope Instruction below)
6. Technical strategy addresses security, performance, and scalability — security language must be unconditional (replace 'if present' with 'MUST verify', 'should validate' with 'MUST validate')
7. No implicit coupling between components
8. Every security mitigation maps to a specific component in the Parallelization Strategy
9. Complete Matrix principle applied: for every access control rule, interface contract, or test plan, the complete matrix (all roles x all operations x all contexts) is built — empty cells are explicit decisions, not oversights

SCOPE INSTRUCTION:
Review the plan ensuring that the decisions taken are correct AND viable long-term. Flag decisions that you know in advance will not be extensible or will not scale — for example, choosing a data schema that prevents adding future relationships documented in the initiative, or an API pattern that won't support requirements from later phases already known.

What you must NOT do: propose speculative improvements that are not backed by concrete requirements from the initiative. The difference is: 'this will break in Phase 2 because the initiative specifies X' (valid) vs 'this might not scale if someday they need Y' (not valid).

FINDINGS FORMAT:
Send findings to the coordinator as JSON:
{
  'findings': [
    {
      'category': '<parallelization_error|plan_structure_gap|technology_mismatch|dependency_gap|test_coverage_gap|strategic_concern|false_positive>',
      'severity_proposal': '<high|medium|low>',
      'title': '<concise title>',
      'description': '<detailed description of the issue>',
      'affected_section': '<which plan section>',
      'recommendation': '<specific action to resolve>',
      'structural_edits': ['<exact edit 1>', '<exact edit 2>']
    }
  ]
}

Note: You PROPOSE severity. The coordinator makes the final severity decision using the objective rubric.

VERIFICATION ROUNDS (rounds 2+):
When the coordinator sends modified sections with the findings that motivated changes:
1. Verify that the original finding is correctly resolved
2. Anticipate errors that this specific change may cause in dependent sections — think in cascade: if a file was moved to the Shared Files Map, was estimated_files updated for all affected components? Was the wave assignment updated? Are the interfaces still valid?
3. Report BOTH verification findings and anticipated findings, tagged as 'verification' or 'anticipated'

COMMUNICATION:
- Your coordinator's name is 'coordinator' (the team leader)
- Send all findings to coordinator via SendMessage"
```

### 1.4 Skills Reviewer

Spawn a teammate called `skills-reviewer` using model opus with this prompt:

```
"You are the SKILLS REVIEWER for epic P<N>.E<M>. Your role is to discover relevant skills and apply their domain-specific lenses to the plan.

ROUND 1 — SKILL DISCOVERY (execute ONCE):
1. Discover ALL available skills from all sources (project, user, all plugins)
2. Match skills against the plan's technologies and domains
3. Record the matched skill set — you will use this SAME set in all subsequent rounds
4. For each matched skill, review the plan through that skill's lens for gaps and anti-patterns

ROUNDS 2+ — APPLY FIXED SKILL SET:
Use the SAME skill set discovered in round 1. Do NOT rediscover skills.
Review the plan (or modified sections) through each matched skill's lens.

SCOPE INSTRUCTION:
Review the plan ensuring that the decisions taken are correct AND viable long-term. Flag decisions that you know in advance will not be extensible or will not scale — for example, choosing a data schema that prevents adding future relationships documented in the initiative, or an API pattern that won't support requirements from later phases already known.

What you must NOT do: propose speculative improvements that are not backed by concrete requirements from the initiative. The difference is: 'this will break in Phase 2 because the initiative specifies X' (valid) vs 'this might not scale if someday they need Y' (not valid).

FINDINGS FORMAT:
Send findings to the coordinator as JSON:
{
  'findings': [
    {
      'category': '<parallelization_error|plan_structure_gap|technology_mismatch|dependency_gap|test_coverage_gap|strategic_concern|false_positive>',
      'severity_proposal': '<high|medium|low>',
      'title': '<concise title>',
      'description': '<detailed description of the issue>',
      'affected_section': '<which plan section>',
      'recommendation': '<specific action to resolve>',
      'structural_edits': ['<exact edit 1>', '<exact edit 2>']
    }
  ]
}

Note: You PROPOSE severity. The coordinator makes the final severity decision using the objective rubric.

COMMUNICATION:
- Your coordinator's name is 'coordinator' (the team leader)
- In round 1, include the discovered skill set in your first message to coordinator so the coordinator has visibility into which skills were matched
- Send all findings to coordinator via SendMessage"
```

---

## Stage 2: Planning Round

### 2.1 Read Epic and Context

1. Read `$EIGEN_ROOT/eigen_initiative/phases/phase_N/epic_M/epic.md`. If it does not exist, STOP. Print: "Epic file not found. Run `/space_split` first."
2. Parse the YAML frontmatter to extract `id`, `phase`, `epic_number`, `feature_count`, `features`.
3. Read the full markdown body (features table, validation criteria, inter-epic interfaces, blackbox specs, whitebox guidance, bootstrap context).
4. Read `$EIGEN_ROOT/eigen_initiative/phases/phase_N_manifest.md` — the phase manifest for broader context.
5. Read `$EIGEN_ROOT/eigen_initiative/phases/phase_N/bootstrap-report.json` — bootstrap context (entity paths, tooling decisions, languages).
6. Read `$EIGEN_ROOT/eigen_initiative/phases/phase_N/epic_manifest.json` — the epic manifest for inter-epic dependency awareness.
7. Read `recommendations` from the CLI context. Filter by current phase and epic number (include entries where `epic` is null — phase-wide observations). Use as advisory context during plan generation.

### 2.2 Send to Planner

Send the epic content, context files, and research instructions to the `planner` via SendMessage:

```
SendMessage({
  to: "planner",
  message: "Generate a strategic development plan for this epic.

EPIC CONTENT:
<full epic.md content>

CONTEXT FILES:
Phase manifest: <phase manifest content>
Bootstrap report: <bootstrap report content>
Epic manifest: <epic manifest content>

RECOMMENDATIONS FROM UPSTREAM:
<recommendations content, or 'None'>

PLAN GENERATION INSTRUCTIONS:

1. RESEARCH FIRST:
Spawn research agents in parallel to understand the project context:
- Spawn a Task with the epic body content to research the codebase conventions, existing patterns, module boundaries, and file ownership patterns
- For each detected language, spawn a research agent using relevant skills from the language-profiles skill's Stack-Specific Skills table
Save the research output — it will inform the plan and gap analysis.

2. DETERMINE COMPLEXITY LEVEL:
Based on the epic analysis and research:
- MINIMAL — for simple features or small improvements: basic approach, core acceptance criteria. No parallelization strategy (single-task execution).
- STANDARD — for most epics: comprehensive analysis, detailed approach, parallelization strategy required.
- COMPREHENSIVE — for major features or architectural changes: multi-phase strategy, extensive risk analysis, detailed parallelization strategy.

3. WRITE PLAN SECTIONS:

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

4. DEFINE PARALLELIZATION STRATEGY (STANDARD and COMPREHENSIVE only):

Skip if MINIMAL.

Analyze the plan to produce a machine-readable parallelization strategy consumed by /create_issues_from_plan_swarm:

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

5. GAP ANALYSIS (STANDARD and COMPREHENSIVE only):

Skip if MINIMAL.

Launch gap analysis sub-phases in parallel:

Sub-phase A: Skills Gap Check
- Discover all available skills from all sources (project, user, all plugins)
- Match skills against the plan's technologies and domains
- For each matched skill, spawn a sub-agent to review the plan for gaps and anti-patterns
- Spawn ALL matched skill agents in parallel

Sub-phase B: Parallelization Strategy Validation
- Spawn a dedicated validation agent to check file ownership boundaries, interface contracts, execution wave dependencies, E2E scenario coverage, component sizing, shared file identification, and circular dependency detection

After ALL sub-phase agents return:
- Collect and deduplicate gap reports
- Prioritize by severity (critical / medium / low)
- Refine the plan by applying fixes for critical and medium gaps
- Update the Parallelization Strategy if structural issues were found
- Add a Gap Analysis Results section documenting what was found and how it was addressed

CRITICAL: Do NOT add code examples during refinement. The plan must remain strategic and code-free.

6. SEND THE COMPLETED PLAN:
Send the complete plan content to the coordinator. Include ALL sections and the full Parallelization Strategy block."
})
```

### 2.3 Receive Plan from Planner

Wait for the planner's response via SendMessage. The planner sends the complete plan content back to the coordinator.

### 2.4 Write Plan to Disk (Crash Recovery Checkpoint)

1. Ensure the epic directory exists: `mkdir -p $EIGEN_ROOT/eigen_initiative/phases/phase_N/epic_M/`
2. Ensure the feedback directory exists: `mkdir -p $EIGEN_ROOT/eigen_initiative/phases/phase_N/epic_M/feedback/`
3. Write the plan to `$EIGEN_ROOT/eigen_initiative/phases/phase_N/epic_M/plan.md`
4. The file should include a header with:
   - Phase number, epic number, and epic name
   - Epic ID (e.g., `P1.E2`)
   - Date of plan creation
5. Keep the plan content in memory for the review round.

---

## Stage 3: Review Round (parallel)

Send the plan to all 3 reviewers in parallel via SendMessage:

```
SendMessage({
  to: "structural-reviewer",
  message: "Review this plan's Parallelization Strategy for structural correctness.

PLAN CONTENT:
<full plan content>

EPIC CONTEXT:
<epic.md content summary — features, acceptance criteria, inter-epic interfaces>

Focus on: file ownership, shared files, interfaces, wave DAG, E2E coverage, integration wave."
})

SendMessage({
  to: "strategic-reviewer",
  message: "Review this plan's architecture, risks, and strategic soundness.

PLAN CONTENT:
<full plan content>

EPIC CONTEXT:
<epic.md content summary — features, acceptance criteria, inter-epic interfaces>

Focus on: architecture decisions, risk assessment, dependency identification, acceptance criteria measurability, security language, component coupling."
})

SendMessage({
  to: "skills-reviewer",
  message: "Review this plan through domain-specific skill lenses.

PLAN CONTENT:
<full plan content>

EPIC CONTEXT:
<epic.md content summary — features, acceptance criteria, inter-epic interfaces>

<Round 1: Discover all available skills first, then apply matched skills to the plan.>
<Round 2+: Use the same skill set from round 1. Review the plan (or modified sections) through each matched skill's lens.>"
})
```

Wait for all 3 reviewers to send their findings back via SendMessage.

Each reviewer sends findings in this format:

```json
{
  "findings": [
    {
      "category": "parallelization_error|plan_structure_gap|technology_mismatch|dependency_gap|test_coverage_gap|strategic_concern|false_positive",
      "severity_proposal": "high|medium|low",
      "title": "...",
      "description": "...",
      "affected_section": "...",
      "recommendation": "...",
      "structural_edits": ["..."]
    }
  ]
}
```

Reviewers propose severity; the coordinator decides.

---

## Stage 4: Coordinator Synthesis

With ALL findings from all reviewers in context, the coordinator performs deduplication, contradiction resolution, severity assignment, and false positive filtering.

### 4.1 Group by Section + Concept

If two reviewers flag the same file, interface, or concept, merge into one finding. Preserve the most actionable recommendation and combine structural_edits from both sources.

### 4.2 Detect Contradictions

If reviewers disagree (e.g., structural-reviewer says "split component A" and strategic-reviewer says "component A is fine"):

1. Evaluate which reviewer has more weight based on the finding category:
   - `parallelization_error`, `dependency_gap` → structural-reviewer has more weight
   - `strategic_concern`, `technology_mismatch` → strategic-reviewer has more weight
   - `test_coverage_gap`, `plan_structure_gap` → evaluate case by case
2. If the contradiction cannot be resolved from context alone, send a clarification question via SendMessage to the relevant reviewer and wait for the response.
3. Make a decision and document it in the finding's description: "Contradiction between structural-reviewer and strategic-reviewer resolved in favor of X because Y."

### 4.3 Apply Severity Rubric

The coordinator is the SOLE authority on severity. Reviewers only propose.

| Severity | Definition | Concrete Examples |
|----------|------------|-------------------|
| **high** | Prevents `create_issues_from_plan_swarm` from generating correct tasks | File in estimated_files of 2+ components; circular wave dependency; interface without stub_file; component without estimated_files; missing E2E scenario for a major acceptance criterion |
| **medium** | Produces suboptimal but functional tasks downstream | Interface contract vague (name only, no types); E2E scenario covers <50% of acceptance criteria; component with >15 estimated_files; decision that will break in future phases documented in the initiative |
| **low** | Minor improvement; downstream works without change | Inconsistent naming; description could be clearer; risk assessment incomplete but present; stylistic concern |

For each finding:
1. Read the reviewer's `severity_proposal`
2. Apply the rubric above to determine the final severity
3. If the coordinator overrides a reviewer's proposal, note the reason

### 4.4 Filter False Positives

Remove findings categorized as `false_positive`. If a reviewer flags something as a real issue but the coordinator determines it is a false positive upon analysis, recategorize it and remove it from the actionable set.

### 4.5 Narrative vs Structural Assessment

For each finding that flags a missing structural entry (e.g., file not in Shared Files Map, file not in estimated_files, missing interface contract):

1. Check if the behavior IS described in narrative sections (Key Architectural Decisions, Implementation Approach, Integration Points, Risk Factors). Search for the file path, function name, or concept in the full plan text.
2. If narratively present but structurally absent: the finding is valid (the structural section MUST be fixed), but downgrade severity to medium if it was classified as high. Include explicit structural_edits showing exactly which YAML/list entries to add or modify.
3. If neither narratively nor structurally present: keep original severity — the plan genuinely missed this concern.

---

## Stage 5: Convergence Check

After synthesis, apply convergence rules **in order** (first match wins):

| Rule | Condition | Minimum Round |
|------|-----------|---------------|
| 1. Clean state | Zero high + zero medium findings | Any |
| 2. Iteration limit | Round >= 4 | 4 |
| 3. Diminishing returns | Round >= 4 AND all medium are new_findings AND total count decreased vs previous round | 4 |
| 4. Oscillation | Oscillation detected AND no non-oscillating high/medium findings | 3 |
| 5. Continue | Any high/medium actionable findings remain | — |

**Critical**: Medium findings NEVER force convergence before round 4. Before round 4, only Rule 1 (zero high + zero medium) allows convergence.

**Degradation rule (round 4+)**: Any medium finding that is a `new_finding` (not persisting or regressed from a previous round) is automatically degraded to `low`. This prevents new medium findings from blocking convergence after round 4.

### Oscillation Detection

A finding is oscillating if:
- It matches a finding that has appeared in 3+ non-consecutive rounds, OR
- It has been resolved in one round and reappeared in a subsequent round at least once

Finding matching uses **file-path matching**: extract all file paths from `description`, `recommendation`, and `affected_section`. Two findings match if they share at least one file path AND belong to the same `category`.

### Convergence Decision

If CONVERGE (Rules 1, 2, 3, or 4 match) → proceed to Stage 7 (Output & Cleanup)
If CONTINUE (Rule 5) → proceed to Stage 6 (Targeted Fix Round)

Track the convergence rationale for inclusion in the feedback JSON:
- Rule 1: "All significant issues resolved. Zero high and zero medium findings remain."
- Rule 2: "Maximum iteration limit (4) reached. Accepting current state."
- Rule 3: "Diminishing returns detected. All remaining medium findings are new and total count decreased."
- Rule 4: "Oscillation detected. Accepting current state to break the cycle."

---

## Stage 6: Targeted Fix Round

Instead of re-running everything, the coordinator sends only the consolidated findings to the planner.

### 6.1 Send Findings to Planner

```
SendMessage({
  to: "planner",
  message: "Apply these changes to the plan. For each finding, apply the recommended fix and update ALL affected sections — do not leave stale references.

CONSOLIDATED FINDINGS:
<findings with structural_edits>

CASCADING UPDATE RULES:
When applying a change, apply ALL structural consequences:
- move_file_to_shared → add the file to the Shared Files Map section AND verify it appears in estimated_files of every component listed in touched_by
- add_component / split_component → create the component entry with estimated_files, update interfaces, update wave dependencies
- add_interface / modify_interface → update the Interfaces section AND update stub_file in the providing component's estimated_files
- fix_blocked_by → update wave assignments for affected components

Edit the STRUCTURAL sections directly (Shared Files Map YAML entries, estimated_files lists, Interfaces entries, wave assignments). Do NOT address structural findings by adding narrative paragraphs to Strategic Overview or Implementation Approach.

After applying all changes, re-validate:
- No file in estimated_files of more than one component
- Every shared file has a valid touched_by list
- Every interface has a stub_file in the provider's estimated_files
- Execution waves form a valid DAG

Send back ONLY the modified sections of the plan."
})
```

### 6.2 Receive Modified Sections

Wait for the planner's response. The planner sends the modified sections back to the coordinator.

### 6.3 Update Plan on Disk (Crash Recovery Checkpoint)

Write the updated plan to `$EIGEN_ROOT/eigen_initiative/phases/phase_N/epic_M/plan.md`. This ensures crash recovery can resume from the latest version.

### 6.4 Send to Affected Reviewers

Route the modified sections to ONLY the affected reviewers:

**Routing logic:**
- Parallelization Strategy changed → structural-reviewer only
- Technical Strategy changed → strategic-reviewer only
- Cross-cutting change (affects both structural and strategic sections) → both structural-reviewer and strategic-reviewer
- skills-reviewer is NOT re-engaged in rounds 2+ unless there are technology changes (new frameworks, languages, or tools added to the plan)

```
SendMessage({
  to: "<affected-reviewer>",
  message: "Review these modified sections. The coordinator applied changes based on your findings.

MODIFIED SECTIONS:
<modified plan sections>

ORIGINAL FINDINGS THAT MOTIVATED CHANGES:
<the findings that were addressed>

VERIFICATION INSTRUCTIONS:
For each applied change:
1. Verify that the original finding is correctly resolved
2. Anticipate errors that this specific change may cause in dependent sections — think in cascade: if a file was moved to the Shared Files Map, was estimated_files updated for all affected components? Was the wave assignment updated? Are the interfaces still valid?
3. Report BOTH verification findings and anticipated findings, tagged as 'verification' or 'anticipated'"
})
```

Wait for all engaged reviewers to respond. Then return to Stage 4 (Coordinator Synthesis) with the new findings.

---

## Stage 7: Output & Cleanup

### 7.1 Write Final Plan

If the plan was modified in the last fix round, write the final version to `$EIGEN_ROOT/eigen_initiative/phases/phase_N/epic_M/plan.md`.

### 7.2 Write Feedback JSON

Write to `$EIGEN_ROOT/eigen_initiative/phases/phase_N/epic_M/feedback/plan_epic_converge_feedback.json`.

Ensure directory exists: `mkdir -p $EIGEN_ROOT/eigen_initiative/phases/phase_N/epic_M/feedback/`

Use the same feedback schema as deepen_plan_phase_epic for pipeline state compatibility:

```json
{
  "schema_version": "1.0.0",
  "command": "plan_epic_converge",
  "phase": 1,
  "epic": 2,
  "epic_id": "P1.E2",
  "iteration": "<total internal rounds>",
  "convergence": {
    "decision": "converged",
    "rationale": "<convergence rationale from Stage 5>",
    "rounds_taken": 3
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
      "source_reviewer": "<structural-reviewer|strategic-reviewer|skills-reviewer|merged>",
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

The `findings` array includes ALL findings from all rounds — both resolved and remaining. The `resolution` field tracks how each finding was handled:
- `resolved`: the finding was fixed during the convergence loop
- `degraded_to_low`: a medium finding that was degraded at round 4+ because it was a new_finding
- `accepted_at_convergence`: a low-severity finding that did not block convergence

### 7.3 Lesson Extraction

For each non-false-positive finding discovered during the convergence loop, create a lesson JSON in `$EIGEN_ROOT/eigen_initiative/eigen_lessons/plan_phase_epic/`:

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
  "root_cause": "<why the planner produced this error>",
  "recommendation": "<specific change to prevent this in future plans>",
  "affected_section": "<which section of the plan was affected>",
  "evidence": {
    "plan_sections_involved": ["<section titles>"],
    "reviewer_source": "<which reviewer found this>"
  },
  "plan_context": "<epic ID, technology stack>",
  "tags": ["<relevant tags>"]
}
```

**Deduplication**: Before writing each lesson, check existing lessons in the directory. If a lesson with the same `affected_section` + `category` + similar `root_cause` already exists, skip it. If the existing lesson has `"status": "applied"`, still skip.

Ensure directory exists: `mkdir -p $EIGEN_ROOT/eigen_initiative/eigen_lessons/plan_phase_epic/`

Write each new non-duplicate lesson to: `$EIGEN_ROOT/eigen_initiative/eigen_lessons/plan_phase_epic/<id>.json`

Print summary:
```
Lessons written: <N> new lessons to $EIGEN_ROOT/eigen_initiative/eigen_lessons/plan_phase_epic/
Skipped: <M> duplicates of existing lessons
```

### 7.4 Execute On Exit Commands

Run the On Exit commands sequentially:

```bash
eigen-squared complete plan_epic_converge --phase <N> --epic <M> --plan-file phases/phase_<N>/epic_<M>/plan.md --feedback-path phases/phase_<N>/epic_<M>/feedback/plan_epic_converge_feedback.json --findings-summary '{"high": 0, "medium": 0, "low": <count>}'
```

```bash
eigen-squared mark-converged plan_epic_converge --phase <N> --epic <M> --reason "<convergence rationale>"
```

If there are genuine downstream insights from the convergence process (max 5):
```bash
eigen-squared add-recommendation --from-cmd plan_epic_converge --target create_issues_from_plan_swarm --iteration <N> --text "<observation>"
```

Commit all artifacts:
```bash
eigen-squared commit-state --message "pipeline: plan P<N>.E<M> — converged" --additional-paths eigen_initiative/phases/phase_<N>/epic_<M>/,eigen_initiative/eigen_lessons/plan_phase_epic/
```

Schedule the next command:
```bash
if [ "$AUTOCHAIN" = "true" ]; then
  eigen-squared schedule-next
else
  echo "AUTOCHAIN is not enabled — pipeline will NOT auto-schedule the next command. Run 'eigen-squared schedule-next' manually to continue."
fi
```

### 7.5 Team Shutdown

Send a shutdown message to all teammates:

```
SendMessage({ to: "planner", message: "Plan converged. Shutting down. Thank you." })
SendMessage({ to: "structural-reviewer", message: "Plan converged. Shutting down. Thank you." })
SendMessage({ to: "strategic-reviewer", message: "Plan converged. Shutting down. Thank you." })
SendMessage({ to: "skills-reviewer", message: "Plan converged. Shutting down. Thank you." })
```

Wait for confirmations, then cleanup the team.

### 7.6 Print Summary

```
=== Plan Epic Converge Complete — P<N>.E<M> ===

Epic: P<N>.E<M> — <epic_name>
Plan file: $EIGEN_ROOT/eigen_initiative/phases/phase_N/epic_M/plan.md
Complexity: <MINIMAL|STANDARD|COMPREHENSIVE>
Components: <N> independent components
Waves: <N> execution waves
Convergence: CONVERGED in <R> rounds — <rationale>

Findings:
  High severity:   <N> (all resolved)
  Medium severity:  <N> (all resolved or degraded)
  Low severity:     <N>

Lessons: <N> new lessons written
Feedback: $EIGEN_ROOT/eigen_initiative/phases/phase_N/epic_M/feedback/plan_epic_converge_feedback.json

Next: if AUTOCHAIN=true, eigen-squared schedule-next will route to create_issues_from_plan_swarm
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
- [ ] Feedback JSON written
- [ ] Lesson JSONs written
- [ ] On Exit commands executed successfully

---

## Pipeline Continuation

The `eigen-squared schedule-next` call at the end of the On Exit section reads the updated pipeline state, determines the next command, and schedules it via the claude-tasks API — **but only when the `AUTOCHAIN` environment variable is set to `true`**. If `AUTOCHAIN` is not enabled, the command prints a notice and the pipeline stops, requiring manual invocation of `eigen-squared schedule-next` to continue.

---

## Key Rules

1. **NEVER modify epic.md** — it is owned by `/space_split` and is read-only input.
2. **Plan.md is written by the planner teammate, managed by the coordinator** — the coordinator writes it to disk, the planner generates and updates the content.
3. **Feedback JSON is written at convergence for pipeline state compatibility** — it uses the same schema as deepen_plan_phase_epic so downstream commands and the CLI can read it without changes.
4. **The CLI is the single source of truth for pipeline state** — all pipeline state reads and writes go through `eigen-squared` CLI commands, never through direct file manipulation of pipeline state.
5. **Convergence is decided by the coordinator using the severity rubric** — reviewers propose severity, the coordinator decides.
6. **Maximum 4 internal rounds** — if convergence is not reached by round 4, the coordinator accepts the current state (Rule 2).
7. **Reviewers propose severity; coordinator decides** — the coordinator applies the objective rubric consistently across all findings from all reviewers.
8. **Skills set is fixed at round 1** — the skills-reviewer discovers matching skills once and uses that same set in all subsequent rounds. No rediscovery.
