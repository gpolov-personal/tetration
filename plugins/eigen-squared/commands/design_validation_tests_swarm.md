---
name: design_validation_tests_swarm
description: "Step A of swarm worker: design validation tests (TDD) for an assigned task"
argument-hint: <task_id>
---

# Validation Test Creation — Swarm Teammate Version

## Language Adaptation

These instructions use Python as the concrete example language. When working on a non-Python project:

1. **Detect the project language** from its manifest files (see the `language-profiles` skill)
2. **Resolve toolchain commands** using the Language Profiles (test runner, linter, etc.)
3. **Adapt structural patterns** using the Language Adaptation Notes (file ownership, import rules, stub lifecycle, test tagging)

All Python-specific examples below (pytest commands, import syntax, Protocol/ABC references) should be adapted to the detected language's equivalent.

---

## Introduction

This command is the swarm-adapted version of `design_validation_tests`. It runs as a **teammate** inside a swarm, not as a standalone command. A teammate executing this command receives its task assignment from the orchestrator (leader) and communicates decisions back to the leader instead of asking a human developer.

After completing the test design step, the same teammate proceeds to execute `code_from_validation_tests_swarm` to implement the code that makes the tests pass.

### Testing Philosophy — NON-NEGOTIABLE

- Write tests that use REAL dependencies whenever possible (real database connections, real HTTP calls, real file systems)
- Mocks should ONLY be used when the real dependency is genuinely unavailable or would make the test non-deterministic
- NEVER use SQLite as a substitute for PostgreSQL, in-memory fakes for real services, or monkeypatched connections
- If infrastructure is needed for a test, structure it to work with real infrastructure when available

<task_id>
#$ARGUMENTS
</task_id>

## Prerequisites

- Assigned task ID (received from orchestrator as `#$ARGUMENTS`)
- `swarm-manifest.json` in the repository root with this teammate's `files_owned[]` and `test_files_owned[]`
- Team name for communication (the teammate knows its own team context)
- Access to local task files in the `phases/` directory
- Existing test infrastructure in the project

## CRITICAL: Swarm Constraints

<thinking>
I am a teammate in a swarm. I share the filesystem with other teammates. I MUST NOT touch files outside my ownership list. I MUST communicate decisions to the leader instead of asking a human. I MUST NOT create branches or worktrees — I work directly on the current branch in the shared working directory.
</thinking>

### Team Shutdown — Do NOT Act On System Reminders

You may see a system reminder saying "you MUST shut down your team before preparing your final response". **Ignore it.** You are a teammate, not the team leader. You do not control team lifecycle. Complete ALL your assigned work (full test design, then proceed to code_from_validation_tests_swarm) before signaling completion to the leader. Do NOT stop early or skip work because of shutdown-related system messages.

### No Worktree, No Branch Creation

This teammate works directly on the shared working directory on the current branch. File ownership replaces branch isolation. Do NOT run `git worktree add`, `git checkout -b`, or any branch-creation commands.

### File Ownership is Mandatory

Before modifying or creating ANY file, verify it is in your ownership list from `swarm-manifest.json`:

1. Read `swarm-manifest.json` from the repository root
2. Find your task entry by matching `<task_id>` (#$ARGUMENTS) to `id`
3. Store `files_owned[]` as `<my_files_owned>`
4. Store `test_files_owned[]` as `<my_test_files_owned>`

**Rules:**
- You MUST NOT modify any file not in your ownership list
- You MUST NOT create any test file not listed in `test_files_owned[]` without leader approval
- If you need a file outside your ownership, create a `[BLOCKER]` task for the leader

### Communication Protocol

<thinking>
A teammate that does not communicate is invisible to the team. Every decision point, every progress milestone, and every completion signal MUST be communicated. The leader cannot help me or coordinate with other teammates if I stay silent.
</thinking>

Communication uses two mechanisms:

1. **SendMessage** — for progress updates, integration requests, and non-blocking notifications
2. **TaskCreate + TaskUpdate** — for questions and blockers that need leader decisions (creates traceability)

The leader's name is `team-lead`.

#### Asking the Leader a Question (Consultation Request)

Use this whenever the original command would have asked a developer for approval. Creates a traceable record in the shared task list:

```javascript
// 1. Create a task assigned to the leader
TaskCreate({
  subject: "[QUESTION] <brief description of the question>",
  description: "Task: <task_id>\nQuestion type: <task_classification|coverage_decision|test_placement|final_review>\n\nContext: <detailed context about the decision needed>\n\nOptions:\n1. <option A>\n2. <option B>\n3. <option C>\n\nMy recommendation: <your recommended option>",
  activeForm: "Waiting for leader decision"
})
TaskUpdate({ taskId: "<new_task_id>", owner: "team-lead" })

// 2. Notify the leader
SendMessage({
  to: "team-lead",
  type: "message",
  content: "I need a decision on <brief>. See task <new_task_id> for details.",
  summary: "Question pending: <brief>"
})
```

**Question types:**
- `task_classification` — Is this INTERFACE_ABSTRACTION, REFACTORING, NEW_FEATURE, or ENHANCEMENT?
- `coverage_decision` — Should I extend an existing test, create a complementary one, or skip?
- `test_placement` — Where should this test go? (with proposed locations)
- `test_issue` — An existing test appears wrong or contradicts requirements (with evidence and suggested fix)
- `final_review` — All tests designed, requesting approval before finalizing

#### Reporting a Blocker

Use this for issues that block your progress and require the leader to take action. You MUST WAIT for the response before proceeding:

```javascript
// 1. Create a blocker task assigned to the leader
TaskCreate({
  subject: "[BLOCKER] <brief description>",
  description: "Task: <task_id>\nBlocker type: <ownership_violation|dependency_issue>\n\nDetails: <what is blocked and why>\nFile needed: <if ownership issue>\nReason: <why you need it>",
  activeForm: "Blocked: waiting for leader"
})
TaskUpdate({ taskId: "<new_task_id>", owner: "team-lead" })

// 2. Notify the leader
SendMessage({
  to: "team-lead",
  type: "message",
  content: "I'm blocked on <brief>. See task <new_task_id>. Waiting for your response.",
  summary: "BLOCKED: <brief>"
})
```

After sending a blocker, **STOP and WAIT**. The leader's response will arrive automatically as a `@team-lead>` message in your conversation. Do not proceed until you receive it.

#### Sending a Progress Update

Use for milestones — no task needed, just a message:

```javascript
SendMessage({
  to: "team-lead",
  type: "message",
  content: "Progress on <task_id>: <status>. Files modified: <list>. Tests count: <N>. Summary: <what was accomplished>",
  summary: "Progress: <task_id> — <brief status>"
})
```

#### Sending Tests Complete Signal

Send when all tests are written and the tracker file is ready:

```javascript
SendMessage({
  to: "team-lead",
  type: "message",
  content: "Tests complete for <task_id>. Tracker: tests/tracker-files/validation_tests_tracker_<task_id>.json. Tests: <N>. Files: <list>. Type: <task_type>. All passing: false (TDD).",
  summary: "Tests complete: <task_id> — <N> tests"
})
```

#### Handling Incoming Leader Messages

Messages from the leader arrive automatically as `@team-lead>` lines in your conversation. Handle them based on content:

- **Decision on your question** — The leader references your `[QUESTION]` task ID. Read the decision and reasoning, then act accordingly.
- **Decision on your blocker** — The leader references your `[BLOCKER]` task ID. Read the decision (granted/denied/alternative) and proceed.
- **Leader concern** — The leader proactively raises an issue. Read it, adjust your work, and send a progress update acknowledging the concern.
- **Unblock notification** — A dependency has been resolved. Read what files/interfaces are now available.

**You do NOT need to poll or read your inbox.** Messages arrive automatically.

## Working Notes (Compaction Resilience)

Throughout execution, maintain a working notes file at `working-notes-<task_id>.md` in the `swarm_working_notes/` directory at the repository root. This file serves as external memory — if context compaction occurs, you can re-read it to restore critical context.

### Initialize Working Notes

At the very start of execution, create the `swarm_working_notes/` directory if it does not exist, then check if `swarm_working_notes/working-notes-<task_id>.md` already exists:
- **If it exists**: This means either (a) you are resuming within the same session, or (b) context compaction occurred. Execute the resume protocol:

  1. Read the working notes file completely
  2. Read the `Last Checkpoint` field to determine where you left off
  3. Read the `Next Step` field for the exact resumption instruction
  4. Re-read `swarm-manifest.json` to restore ownership lists and interface_deps
  5. Check `TaskList()` for any leader decisions on your `[QUESTION]`/`[BLOCKER]` tasks that arrived while you were compacted
  6. Read the tracker file if it exists (for post-tracker or later checkpoints)
  7. Re-read the parent epic at `phases/phase_<N>/epic_<M>/epic.md` (where `<epic_id>` maps to the phase/epic path from the manifest's `plan_file` field) to restore plan content. If the file does not exist, create a `[BLOCKER]` task for the leader.
  8. Follow the `Next Step` instruction to continue from the correct point
- **If it does not exist**: Create it with the initial header.

```markdown
# Working Notes — <task_id>
## Phase: design_validation_tests

## Ownership
- Files owned: <my_files_owned>
- Test files owned: <my_test_files_owned>
- Blocked by: <blocked_by>

## Key Decisions
(updated as decisions are made)

## Codebase Patterns Discovered
(updated during exploration)

## Detected Tech Stack
- Language: <detected_language>
- Framework: <detected_framework>

## Loaded Skills
(updated after research phase — records which skills the researcher used)

## Progress
- [ ] Manifest read and ownership established
- [ ] Task analyzed
- [ ] Task classified as: (pending)
- [ ] Test discovery complete
- [ ] Tests created
- [ ] Tracker file created
- [ ] Tests committed
```

### Update Working Notes — Mandatory Checkpoints

Update the working notes file at each of the following checkpoint moments. Each checkpoint **MUST** include a `Last Checkpoint` and `Next Step` entry describing what to do if resuming from this point.

| # | Checkpoint | When | What to persist |
|---|-----------|------|-----------------|
| 1 | post-manifest | After reading manifest and establishing ownership (Task 1) | files_owned, test_files_owned, blocked_by, interface_deps, epic_id |
| 2 | post-task-analysis | After analyzing the task and reading plan content (Task 2) | task_type_hypothesis, key_requirements |
| 3 | post-classification | After leader confirms task classification (Stage 2.5) | confirmed task_type, classification_rationale, leader decision reference |
| 4 | post-discovery | After test module discovery and coverage mapping (Stage 2.7) | coverage_mapping (ALREADY_COVERED / PARTIALLY_COVERED / NOT_COVERED for each scenario), existing_test_cases summary, affected_modules |
| 5 | post-test-batch | After completing the test creation loop (Stage 3A/3B/3C) | tests created so far (file:test_name), pending scenarios, any leader decisions received |
| 6 | post-tracker | After creating tracker file (Stage 4 step 1) | tracker file path, total test count, test file list |
| 7 | post-commit | After committing tests (Stage 4 step 3) | commit hash, all test files committed |

**Checkpoint format in working notes:**

```markdown
## Last Checkpoint: <checkpoint_name>

## Next Step
If resuming: <specific instruction, e.g., "Read coverage_mapping below, then proceed to Stage 3A Test Creation Loop. Start with the first NOT_COVERED scenario.">

## Coverage Mapping (persisted at post-discovery)
- scenario_1: ALREADY_COVERED (existing: test_auth.py::test_login)
- scenario_2: NOT_COVERED
- scenario_3: PARTIALLY_COVERED (existing: test_auth.py::test_register, missing: error handling)
```

**IMPORTANT**: Keep the file concise. Overwrite sections rather than appending. The `Last Checkpoint` and `Next Step` fields are the most critical — they enable deterministic resume after compaction.

---

## Main Tasks

### 1. Read Manifest and Establish Ownership

1. Read `swarm-manifest.json` from the repository root
2. Find the task entry where `id` matches `<task_id>` (#$ARGUMENTS)
3. Store:
   - `<my_files_owned>` — source files assigned to this task
   - `<my_test_files_owned>` — test files assigned to this task
   - `<blocked_by>` — tasks that must complete before this one (if any)
   - `<my_interface_deps>` — interface dependencies (may be empty)
4. Verify ownership lists are not empty. If `test_files_owned[]` is empty, create a `[QUESTION]` task for the leader asking where tests should go.
5. If `<my_interface_deps>` is not empty:
   - Verify each stub file exists: `test -f <stub_file>`
   - If missing, create `[BLOCKER]` for leader ("Stub file <stub_file> not found. Provider #<provider_id> may not have generated it yet.")
   - Read each stub to understand available interfaces
   - Store in `<available_interfaces>`

**Checkpoint: post-manifest** — Update working notes with ownership info and Next Step.

### 2. Analyze Input Task

1. Read the task file for `<task_id>`. The `<task_id>` is a local ID. Find the task by scanning `phases/phase_*/epic_*/tasks/task_*.md` for the matching `id` in YAML frontmatter, OR derive the path from the swarm manifest (the manifest has `plan_file` which tells you the phase/epic path, then look for `tasks/task_<task_id>.md` there). Extract title, body, labels, status, and any other metadata from the YAML frontmatter and markdown content.
2. Store the task body in `<task_description>`
3. Extract `<epic_id>` from the `epic_id` field in `swarm-manifest.json` (already read in step 1)
4. Read the parent epic from `phases/phase_<N>/epic_<M>/epic.md`. The parent epic ID comes from the manifest's `epic_id` field. Also check the `## Comments` section for any dependency notes.
5. Store the parent epic body in `<parent_task_content>`
6. Read the local plan file from the parent epic directory. If the file does not exist, create a `[BLOCKER]` task for the leader informing that no plan was found for epic #<epic_id>.
7. Store the plan content in `<plan_content>`

**Checkpoint: post-task-analysis** — Update working notes with:

```markdown
## Last Checkpoint: post-task-analysis

## Next Step
If resuming: Read key requirements below. Re-read plan from the parent epic directory (derived from manifest's `plan_file` field). Proceed to Stage 2 (Task Classification). Use the task_type_hypothesis as starting point for classification question to leader.

## Key Requirements
- <requirement_1>
- <requirement_2>
...
```

### 3. Parallel Research & Context Gathering

Execute research to understand the testing strategies for `<task_description>`:

**Stack-Adaptive Research Enhancement**

Read `<detected_tech_stack>` from:
1. Your spawn prompt context above (normal flow)
2. Your working notes `## Detected Tech Stack` section (if spawn prompt was compacted)
3. If neither is present, the researcher will detect the stack independently

If `<detected_tech_stack>` is present, pass it to the researcher as part of its arguments
so it can search for stack-specific testing skills:

- Task test-practices-researcher-no-vs("<task_description>. Detected tech stack: <detected_tech_stack>")

If `<detected_tech_stack>` is NOT present (standalone execution):

- Task test-practices-researcher-no-vs("<task_description>")

The researcher agent will detect the stack independently via the `language-profiles` skill if no
tech stack info is provided in the arguments.

> Note: Ensure research covers testing strategies appropriate for the detected project language, not just Python/pytest.

**After gathering context, send a progress update:**

```javascript
SendMessage({
  to: "team-lead",
  type: "message",
  content: "Progress on <task_id>: context_gathered. Task analyzed, context gathered, ready for classification.",
  summary: "Progress: <task_id> — context gathered"
})
```

## Execution Workflow

### Stage 1: Environment Verification (Simplified for Swarm)

No worktree or branch creation. Just verify the environment is usable:

1. **Verify working directory is the repository root:**
   ```bash
   git rev-parse --show-toplevel
   ```

2. **Verify `swarm-manifest.json` exists and is readable:**
   ```bash
   test -f swarm-manifest.json && echo "Manifest found" || echo "ERROR: No manifest"
   ```

3. **Verify test infrastructure exists:**
   ```bash
   test -d tests/ && echo "Tests directory found" || echo "ERROR: No tests directory"
   # Adapt path to your project's test directory convention (see the `language-profiles` skill)
   ```

4. **If blocked, wait for unblocking:**
   If `<blocked_by>` is not empty, check task status. If still blocked, check `TaskList()` and wait. Do NOT proceed until unblocked.

### Stage 2: Requirement Analysis

<thinking>
I am a Senior AI Backend Engineer with extensive experience in Test-Driven Development and writing comprehensive validation tests. I must analyze this task thoroughly.
</thinking>

1. **Read and Understand the Task**
   - Read the task file for #$ARGUMENTS
   - Read `<plan_content>` and `<parent_task_content>` for higher-level purpose
   - Identify ALL deliverables and requirements ONLY for this task
   - Note constraints, dependencies, edge cases
   - Extract success criteria and acceptance criteria
   - Understand user flows and API contracts affected

2. **Analyze Testing Scope**
   - Identify which endpoints/services/modules will be affected
   - Determine expected behavior changes
   - List all scenarios needing validation (happy path + edge cases)
   - Note integration points needing testing
   - Consider error cases and boundary conditions

3. **Build Testing Todo List**
   - Use TodoWrite to create comprehensive test creation list
   - Group tests by feature area or user flow
   - Include tests for all acceptance criteria
   - Add edge cases and error scenarios
   - Note test data or fixtures needed

### Stage 2.5: Task Type Classification

<thinking>
I must classify the task type. Instead of asking a human developer, I will present my classification to the leader and wait for confirmation.
</thinking>

1. **Classify Task Type**

   Analyze `<task_description>`, `<plan_content>`, and the task's YAML front-matter:

   - **REVIEW_FINDING**: A fixup for a finding raised by `review_swarm_pr` in a prior iteration. **Detection is mechanical, not heuristic**: the task's YAML front-matter has `labels` containing `"review-finding"` (these tasks are also named `task_R<K>.md`, with `id` matching `P<N>.E<M>.R<K>`). When this label is present, this classification **always wins** — do NOT route to NEW_FEATURE / ENHANCEMENT / REFACTORING / INTERFACE_ABSTRACTION based on the task description's surface wording, because review-fixup descriptions look syntactically like enhancements but require fundamentally different test design (threat-class generalization, adversarial variants, no mocks for security categories — see Stage 3D). Skip the leader [QUESTION] in step 3 below; classification is unambiguous.
   - **INTERFACE_ABSTRACTION**: Defines interfaces, abstract classes, protocols, factories, stubs, or scaffolding. Contains terms like "abstract class", "interface", "protocol", "factory", "base class", "contract", "stub", "scaffold". Focus is on contracts and structure, not business logic. Actual behavior will be implemented in separate follow-up tasks. Key indicator: the task references future tasks for "real" implementation.
   - **REFACTORING**: No changes to external behavior or API contracts. Focus on internal code improvements.
   - **NEW_FEATURE**: Introduces new endpoints, routes, services, or user-facing functionality. Key difference from INTERFACE_ABSTRACTION: implements actual behavior, not just defines contracts.
   - **ENHANCEMENT**: Modifies existing functionality with new behavior, changes API contracts.

   **Special case: Interface providers with pre-existing stubs**

   If your task is an interface provider (your `id` appears as `provider_id` in another task's `interface_deps` in `swarm-manifest.json`) AND a stub already exists in your `stub_file`:
   - Do NOT classify as INTERFACE_ABSTRACTION (the stub already provides the interface)
   - Classify based on the REAL implementation work: typically NEW_FEATURE or ENHANCEMENT
   - Your tests should validate real business behavior, not interface structure
   - Note: REVIEW_FINDING takes precedence over this rule too — a fixup task on an interface provider's file is still a REVIEW_FINDING.

2. **Store Classification**
   - Store type in `<task_type>`
   - Store reasoning in `<classification_rationale>`

3. **Consult Leader for Classification Approval** *(skipped for REVIEW_FINDING — classification is mechanical via the `review-finding` label)*

   If `<task_type> == REVIEW_FINDING`: skip this step. Send the post-classification progress message directly and proceed to Stage 2.7. The label is the authoritative signal; a leader override would be wrong.

   Otherwise, create a `[QUESTION]` task for the leader:

   ```javascript
   TaskCreate({
     subject: "[QUESTION] Task classification for <task_id>",
     description: "Task: <task_id>\nQuestion type: task_classification\n\nContext: <classification_rationale>\n\nOptions:\n1. INTERFACE_ABSTRACTION\n2. REFACTORING\n3. NEW_FEATURE\n4. ENHANCEMENT\n\nMy recommendation: <task_type>",
     activeForm: "Waiting for classification approval"
   })
   TaskUpdate({ taskId: "<new_task_id>", owner: "team-lead" })

   SendMessage({
     to: "team-lead",
     type: "message",
     content: "Need classification approval for <task_id>. My recommendation: <task_type>. See task <new_task_id>.",
     summary: "Question: classify <task_id> as <task_type>?"
   })
   ```

   Wait for leader response (arrives as `@team-lead>` message). If the leader overrides the classification, update `<task_type>` accordingly. If no response arrives after a reasonable wait, proceed with your recommendation.

   **Send progress update after classification is resolved:**

   ```javascript
   SendMessage({
     to: "team-lead",
     type: "message",
     content: "Progress on <task_id>: classification_done. Task classified as <task_type>.",
     summary: "Progress: <task_id> — classified as <task_type>"
   })
   ```

**Checkpoint: post-classification** — Update working notes with confirmed task_type and Next Step.

### Stage 2.7: Existing Test Module Discovery

**CRITICAL**: This stage is MANDATORY before any test creation. Never skip this stage.

1. **Identify Affected Source Modules**

   Based on `<task_description>` and `<my_files_owned>`:
   - List all source modules that will be affected (scoped to your ownership)
   - Store as `<affected_modules>` with file paths

2. **Discover Existing Test Modules**

   For each module in `<affected_modules>`:
   - Search for existing test files covering this module
   - Catalog existing test modules with their purposes
   - Store mapping in `<module_to_test_file_mapping>`
   - **Cross-reference with `<my_test_files_owned>`** — only consider test files in your ownership

3. **Discover Existing Test Cases**

   For each test file found (within your ownership):
   - Extract existing test function names and purposes
   - Read docstrings/comments to understand coverage
   - Store in `<existing_test_cases>`

4. **Map Planned Test Scenarios to Existing Coverage**

   Compare planned test scenarios against `<existing_test_cases>`:
   - `ALREADY_COVERED`: Existing test fully covers this scenario — DO NOT duplicate
   - `PARTIALLY_COVERED`: May need extension or complementary test
   - `NOT_COVERED`: New test needed

5. **Send Discovery Report to Leader**

   ```javascript
   SendMessage({
     to: "team-lead",
     type: "message",
     content: "Progress on <task_id>: discovery_done. Found N existing tests across M files. N scenarios NOT_COVERED, N PARTIALLY_COVERED, N ALREADY_COVERED.",
     summary: "Progress: <task_id> — discovery complete"
   })
   ```

**Checkpoint: post-discovery** — Update working notes now with:

```markdown
## Last Checkpoint: post-discovery

## Next Step
If resuming: Read the coverage mapping below. Proceed to Stage 3 (test strategy execution). Task type: <task_type>. Start with the first NOT_COVERED scenario in the list.

## Coverage Mapping
- <scenario_1>: <ALREADY_COVERED|PARTIALLY_COVERED|NOT_COVERED> (<details>)
- <scenario_2>: <ALREADY_COVERED|PARTIALLY_COVERED|NOT_COVERED> (<details>)
...
```

This ensures `<coverage_mapping>` survives compaction. Without it, a compacted teammate would redo the expensive discovery phase and risk creating duplicate tests.

### Stage 3: Test Strategy Execution

**Branch based on `<task_type>`:**

- If `<task_type>` is **REVIEW_FINDING** → Go to **Stage 3D**
- If `<task_type>` is **REFACTORING** → Go to **Stage 3B**
- If `<task_type>` is **INTERFACE_ABSTRACTION** → Go to **Stage 3C**
- If `<task_type>` is **NEW_FEATURE** or **ENHANCEMENT** → Go to **Stage 3A**

### Stage 3A: Validation Test Creation (NEW_FEATURE / ENHANCEMENT)

<thinking>
These are validation/integration tests that verify business functionality. They should test behavior from an end-user or API consumer perspective. Tests should currently FAIL since the feature is not implemented yet.
</thinking>

**IMPORTANT**: These tests verify business functionality from an API consumer perspective. If validation tests are not possible, unit tests are acceptable.

#### Test Quality Gate

Before creating ANY test, ask yourself: **"If this test were deleted, would we risk a real bug going undetected in production?"**

- If **yes** → create the test. It validates a real business decision, edge case, or integration boundary.
- If **no** → do NOT create it. It is tautological (testing that code does what you wrote it to do).

**Examples of tautological tests to AVOID:**
- Testing that a getter returns what was set
- Testing that a constructor assigns arguments to attributes
- Testing that a framework feature works as documented (e.g., Django ORM saves correctly)
- Testing that a field exists after creating an object
- Testing that a stub raises NotImplementedError

**Examples of meaningful tests to CREATE:**
- Business logic decisions (if X then Y, otherwise Z)
- Edge cases that could silently break (empty inputs, boundary values, concurrent access)
- Integration boundaries (service A calls service B with correct contract)
- Authorization rules (user X cannot access resource Y)
- Error handling paths that affect user experience

The leader WILL reject trivial tests during final review. Aim for fewer, stronger tests — not more.

#### Test Marker Guidelines

> **Language note:** The markers below are pytest-specific syntax. For other languages, see "Test Categorization" in the `language-profiles` skill. The tag NAMES (`tdd_validation`, `tdd_contract`, `tdd_unit`) are universal concepts; the SYNTAX to apply them varies per language.

| Test Type | Marker | When to Use |
|-----------|--------|-------------|
| Validation/Integration (TDD) | `@pytest.mark.tdd_validation` | Tests validating business requirements from API/user perspective |
| Contract/Interface (TDD) | `@pytest.mark.tdd_contract` | Tests verifying interface structure, factory routing, validation rules (INTERFACE_ABSTRACTION tasks) |
| Unit (TDD) | `@pytest.mark.tdd_unit` | Tests for specific functions/methods when validation tests are not possible |
| Integration | `@pytest.mark.integration` | Tests involving multiple components or external services |
| Unit | `@pytest.mark.unit` | Standard unit tests for isolated function behavior |
| E2E (post-integration) | `@pytest.mark.e2e` | Tests validating full user flows across components (written by e2e-tester, NOT by workers) |

**Marker Rules:**
- ALL new tests MUST have either `@pytest.mark.tdd_validation` or `@pytest.mark.tdd_unit`
- Prefer `tdd_validation` for business behavior tests
- Use `tdd_unit` only when the change cannot be verified through validation tests
- Multiple markers can be combined

**E2E Test Boundary:**
Workers do NOT write E2E tests. E2E tests are written by the dedicated `e2e-tester` teammate after all workers complete and integration finishes. Workers focus exclusively on `tdd_validation`, `tdd_contract`, and `tdd_unit` tests. The `e2e` marker is documented here for awareness only — workers should never apply it.

1. **Test Creation Loop**

   For each test scenario identified:

   a. **Check existing coverage first (MANDATORY):**

   Consult `<coverage_mapping>` from Stage 2.7:

   - **If `ALREADY_COVERED`:** DO NOT create a duplicate test. Document in tracker with `status: "EXISTING"`. Move to next scenario.

   - **If `PARTIALLY_COVERED`:** Create a `[QUESTION]` task for the leader:

     ```javascript
     TaskCreate({
       subject: "[QUESTION] Coverage decision for <task_id>: <scenario>",
       description: "Task: <task_id>\nQuestion type: coverage_decision\n\nScenario: <description>.\nExisting test: <test_file::test_name>.\nCovered: <what>.\nMissing: <what>.\n\nOptions:\n1. EXTEND existing test\n2. CREATE complementary test\n3. SKIP — existing coverage sufficient\n\nMy recommendation: EXTEND existing test",
       activeForm: "Waiting for coverage decision"
     })
     TaskUpdate({ taskId: "<new_task_id>", owner: "team-lead" })

     SendMessage({
       to: "team-lead",
       type: "message",
       content: "Need coverage decision for <task_id>. See task <new_task_id>.",
       summary: "Question: coverage for <scenario>"
     })
     ```

     Wait for leader response. Implement chosen option.

   - **If `NOT_COVERED`:** Proceed with test creation (step b).

   b. **Determine appropriate test file location (MANDATORY):**

   **CRITICAL**: You MUST only create tests in files listed in `<my_test_files_owned>`.

   Decision tree:
   ```
   Is the target test file in <my_test_files_owned>?
   │
   ├─ YES → Proceed with writing the test there
   │
   └─ NO → Create a [BLOCKER] task for the leader:
            "I need to write a test in [file] but it is not in my test_files_owned.
             Options: [1] Add to an owned file instead, [2] Request ownership expansion"
   ```

   If the test file already exists and is in your ownership, ADD the test to it. Follow the existing file's organization and style.

   If the test file needs to be created and is in your ownership, CREATE it following project naming conventions.

   c. **Write the validation test:**
   - Apply appropriate markers (`@pytest.mark.tdd_validation` or `@pytest.mark.tdd_unit`)
   - Use descriptive test names that explain what is being validated
   - Test should currently FAIL (since feature is not implemented yet)
   - Include clear assertions about expected behavior
   - Add comments explaining non-obvious test logic
   - If using env variables, use `@patch.dict(os.environ, {'key':'value'}, clear=True)` (Python-specific; for other languages, see env_mock in the `language-profiles` skill)

   d. **Run the test to confirm it fails appropriately:**
   - Execute the test to verify it fails for the right reasons
   - Ensure failure messages are clear and helpful

2. **Coverage Verification**

   After all tests are created:
   - Review all task requirements
   - Verify each requirement has corresponding test(s)
   - Confirm no duplicate tests were created
   - Verify tests are properly distributed across appropriate test modules
   - Check for missing edge cases

#### Interface Dependency Testing (if `<my_interface_deps>` is not empty)

> **Language note:** The examples below use Python/pytest fixtures and Protocol classes. Adapt test setup to your language's mechanism (beforeEach in Jest, t.Helper() in Go, setup functions in Rust). See the `language-profiles` skill.

When your task depends on an interface stub:

1. Create a simple mock/fake of the interface in your test file:
   ```python
   class FakeUserModel:
       """Test double satisfying UserModel protocol."""
       def verify_password(self, plain: str) -> bool:
           return plain == "correct_password"
   ```

2. Inject the mock into your code under test:
   ```python
   def test_login_succeeds(fake_user_model):
       handler = LoginHandler(user_model=fake_user_model)
       result = handler.login("user@test.com", "correct_password")
       assert result.status == "success"
   ```

3. Do NOT test the interface itself — that is the provider's job.
4. Import directly from the stub file path (e.g. `from src.auth.models import UserModel`), NOT from the package (e.g. `from src.auth import UserModel`). This import distinction is Python/TypeScript-specific. See "Import / Dependency Rules" in the `language-profiles` skill.
5. Do NOT import concrete classes from the stub file — import only the Protocol/ABC.

#### Interface Provider Note (if you are an interface provider)

Check `swarm-manifest.json`: if any task's `interface_deps` lists your `id` as `provider_id`, you are an interface provider.

- Your `stub_file` currently contains the stub you generated at the start
- Your validation tests should test the REAL behavior you will implement, not the stub structure
- Classify your task as NEW_FEATURE or ENHANCEMENT (not INTERFACE_ABSTRACTION), because your deliverable is the real implementation
- When you implement the real code (Step B), you will overwrite the stub entirely

**Checkpoint: post-test-batch** — Update working notes with tests created and Next Step.

**After Stage 3A completion, proceed to Stage 4**

### Stage 3B: Existing Test Discovery & Verification (REFACTORING)

<thinking>
For refactoring, existing tests should already cover the functionality. The goal is to ensure comprehensive test coverage exists before refactoring begins.
</thinking>

1. **Identify Refactoring Scope**
   - Parse `<task_description>` to identify modules being refactored (scoped to `<my_files_owned>`)
   - List all affected code paths
   - Understand what behavior must remain unchanged

2. **Discover Existing Validation Tests**
   - For each module, search for validation/integration tests (within `<my_test_files_owned>`)
   - Catalog found tests with file paths, function names, and coverage
   - Store in `<existing_validation_tests>`

3. **Discover Existing Unit Tests**
   - For each module, search for unit tests (within `<my_test_files_owned>`)
   - Catalog found tests
   - Store in `<existing_unit_tests>`

4. **Run Coverage Analysis**
   Run coverage analysis (Python: `pytest --cov=<module_path> --cov-report=term-missing tests/`; adapt per the `language-profiles` skill).
   - Store coverage percentages
   - Identify uncovered lines and functions
   - Flag modules with < 80% coverage

5. **Analyze Test Quality**
   - Check if tests are well-maintained and not skipped/xfailed (pytest concept; equivalent: @Ignore in JUnit, #[ignore] in Rust, it.skip in Jest)
   - Verify tests run and pass
   - Ensure edge cases and error scenarios are covered

6. **Consult Leader on Coverage Gaps**

   If significant coverage gaps are found, create a `[QUESTION]` task:

   ```javascript
   TaskCreate({
     subject: "[QUESTION] Coverage gaps for refactoring <task_id>",
     description: "Task: <task_id>\nQuestion type: coverage_decision\n\nRefactoring task. Found N coverage gaps: <list gaps>. Current coverage: X%.\n\nOptions:\n1. Create gap tests\n2. Proceed without gap tests\n3. Create tests for critical gaps only\n\nMy recommendation: Create tests for critical gaps only",
     activeForm: "Waiting for coverage gap decision"
   })
   TaskUpdate({ taskId: "<new_task_id>", owner: "team-lead" })

   SendMessage({
     to: "team-lead",
     type: "message",
     content: "Found coverage gaps for refactoring <task_id>. See task <new_task_id>.",
     summary: "Question: coverage gaps for <task_id>"
   })
   ```

   Wait for leader response and act accordingly.

7. **Create Missing Tests (if leader approves)**
   - Follow the same test creation loop as Stage 3A
   - Place tests in existing module test files within `<my_test_files_owned>`
   - For refactoring, these tests should PASS (existing functionality)

**Checkpoint: post-test-batch** — Update working notes with tests created and Next Step.

**After Stage 3B completion, proceed to Stage 4**

### Stage 3C: Contract Test Creation (INTERFACE_ABSTRACTION)

<thinking>
This path is for interface/abstraction tasks where the deliverable is the contract itself (abstract classes, protocols, factories, stubs), not behavioral functionality. Tests here verify that the interface is correctly defined, not that it does useful work.
</thinking>

**IMPORTANT**: For interface/abstraction tasks, tests verify that:
- Interfaces exist with correct method signatures
- Abstract classes cannot be instantiated
- Factories route to correct types
- Validation rules are enforced
- Stubs raise NotImplementedError with guidance

These tests will appear "tautological" or "structural" — this is **correct and expected** for this task type. The implementation behavior will be tested in separate implementation tasks.

#### Contract Test Marker

Use a specific marker for contract tests:

| Test Type | Marker | When to Use |
|-----------|--------|-------------|
| Contract/Interface (TDD) | `@pytest.mark.tdd_contract` | Tests verifying interface structure, factory routing, validation rules |

**Note**: `tdd_contract` is preferred over `tdd_validation` for INTERFACE_ABSTRACTION tasks because these tests verify contracts, not business behavior.

1. **Identify Interface Contracts to Test**

   From `<task_description>`, identify:
   - Abstract classes/protocols being defined
   - Factory patterns and their routing logic
   - Validation rules (field constraints, type checks)
   - Stub implementations and their NotImplementedError messages
   - Dependencies between interfaces

   Store in `<interface_contracts>`.

2. **Contract Test Creation Loop**

   For each interface contract identified:

   a. **Determine what needs to be tested:**

   > **Language note:** The assertion syntax in the table below is Python/pytest-specific. Adapt to your language's equivalent (see expect_exception in the `language-profiles` skill).

   | Contract Type | What to Test | Example Assertion |
   |---------------|--------------|-------------------|
   | Abstract class | Cannot instantiate, subclass must implement methods | `pytest.raises(TypeError)` |
   | Data class | Fields exist, validation enforced | `result.score == expected`, `ValidationError` for invalid |
   | Factory | Routing returns correct type, error on unknown | `type(result).__name__ == "ExpectedClass"` |
   | Stub | Raises NotImplementedError with guidance | `pytest.raises(NotImplementedError, match="TASK-XX")` |

   b. **Check file ownership (MANDATORY):**

   **CRITICAL**: You MUST only create tests in files listed in `<my_test_files_owned>`.

   Decision tree:
   ```
   Is the target test file in <my_test_files_owned>?
   │
   ├─ YES → Proceed with writing the test there
   │
   └─ NO → Create a [BLOCKER] task for the leader:
            "I need to write a contract test in [file] but it is not in my test_files_owned.
             Options: [1] Add to an owned file instead, [2] Request ownership expansion"
   ```

   c. **Write the contract test:**
   - Apply `@pytest.mark.tdd_contract` marker
   - Include a detailed language-appropriate doc comment (Google-style docstring in Python, JSDoc in TypeScript, GoDoc in Go) explaining:
     - Contract type being verified
     - What the test verifies
     - Why this is NOT tautological (the interface IS the deliverable)
     - Future implementation task reference
   - Keep tests focused on ONE contract element each
   - Use clear names: `test_<interface>_<contract_element>`
   - For stubs, verify NotImplementedError message contains guidance
   - If using env variables, use `@patch.dict(os.environ, {'key':'value'}, clear=True)` (Python-specific; for other languages, see env_mock in the `language-profiles` skill)

   d. **Run the test to confirm it fails appropriately:**
   - Should fail with a module resolution error (`ModuleNotFoundError` or `ImportError` in Python; equivalent errors in other languages) because the module doesn't exist yet
   - Ensure failure messages are clear and helpful

3. **Send Progress Update After Contract Tests Created**

   ```javascript
   SendMessage({
     to: "team-lead",
     type: "message",
     content: "Progress on <task_id>: tests_created. Created N contract tests verifying interfaces/factories/stubs. All tests FAIL as expected.",
     summary: "Progress: <task_id> — <N> contract tests created"
   })
   ```

4. **Coverage Verification**

   For contract tests, verify:
   - All abstract classes have instantiation tests
   - All required methods/fields are referenced
   - All factory routing paths are covered
   - All validation rules have boundary tests
   - All stubs verify NotImplementedError with guidance
   - Future implementation tasks are referenced

**Checkpoint: post-test-batch** — Update working notes with tests created and Next Step.

**After Stage 3C completion, proceed to Stage 4**

### Stage 3D: Validation Test Creation (REVIEW_FINDING)

<thinking>
This path exists because review-fixup tasks have a different failure mode than feature tasks. A NEW_FEATURE worker writes tests against the AC strings as written and ships when those pass. That works for greenfield code. For a REVIEW_FINDING fixing a security or validation issue (e.g., "block bypass via CTE in read-only SQL"), testing only the AC string lets the worker patch the literal vector while leaving 6 sibling vectors unfixed. The next review iteration finds the next vector, files another fixup, the worker patches that one, and so on — the SQL whack-a-mole pattern that drove P2.E3 to 3 iterations of P1 oscillation.

The fix is to make the test design **threat-class-generalized**, not vector-specific. Three discipline rules: enumerate the threat class up front, write adversarial variants for each AC (not just the literal example), and forbid mocks for security/validation/auth/data-integrity categories so the tests cannot pass on a stubbed-out check.
</thinking>

REVIEW_FINDING tasks must defeat the **threat class** the finding represents, not just the literal vector cited in the finding's title. The discipline below is what separates a single iteration of clean fixup from an oscillation that ships unsolved.

**IMPORTANT**: For REVIEW_FINDING tasks, validation tests must:
- Enumerate sibling vectors of the same threat class up front (≥ 5)
- Cover ≥ 3 adversarial variants per acceptance criterion (boundary, encoding, syntax-twist)
- Use REAL dependencies for security/validation/authorization/data-integrity categories — mocks defeat the test

#### REVIEW_FINDING Test Marker

Use a specific marker so review_swarm_pr can identify these tests in subsequent iterations:

| Test Type | Marker | When to Use |
|-----------|--------|-------------|
| Review-finding fixup (TDD) | `@pytest.mark.tdd_review_finding` | Tests for a fixup of a finding raised by review_swarm_pr |

(Adapt the marker to your tech stack via the `language-profiles` skill — Go: `t.Run("tdd_review_finding/...")`, JS/TS: `describe.tdd_review_finding(...)`. The string `tdd_review_finding` must appear in the test name or annotation for downstream tooling.)

1. **Read the Finding's Full Context**

   The fixup task file (`task_R<K>.md`) was generated by `review_swarm_pr` from a single finding. Read:
   - `task_description` and `acceptance_criteria` — written by the reviewing agent.
   - The original finding entry in `eigen_initiative/phases/phase_<phase>/epic_<epic>/review_convergence_state.json` (look up by signature) — gives you the agent who raised it, the iteration, and the category.
   - Any prior `review_report_iteration_*.md` entries that mention the same `(file, category)` pair — surfaces sibling vectors that earlier iterations may have raised separately.

   Store finding metadata in `<finding_context>`:
   - `finding_signature`, `finding_category`, `finding_severity`, `finding_iteration`, `affected_files`
   - `prior_related_findings` — list of signatures with the same `(file, category)` pair from previous iterations (if any)

2. **Threat-Class Enumeration (MANDATORY)**

   Before writing ANY test, enumerate the threat class. The threat class is the **abstract category of bypass / failure** the finding represents, not the specific vector. Examples:

   | Finding (specific vector) | Threat class | Sibling vectors (≥ 5) |
   |---|---|---|
   | "SELECT FOR UPDATE bypasses read-only enforcement" | PostgreSQL read-only enforcement | writable CTE, EXPLAIN options, COPY, CALL, DO blocks, advisory locks, INSERT...RETURNING, sequence next-val |
   | "OFFSET parameter allows SQL injection" | SQL parameter injection | LIMIT, ORDER BY column ref, ILIKE escape, regex backrefs, JSON path operators, array indexing |
   | "session token exposed in error log" | sensitive-data leakage in logs | stack traces, exception `__str__`, OpenTelemetry attributes, structured-log field bleed, debug headers, error-page render |
   | "input validator skips unicode normalization" | input normalization | RTL override, full-width digits, zero-width joiners, NFC vs NFKC mismatch, percent-encoding double-decode, whitespace class |

   Record the enumeration in a comment block at the **top of the test file** so future reviewers can verify coverage:

   ```
   # ─── Threat-class enumeration (Stage 3D) ─────────────────────────────────
   # Finding: <finding_signature> — "<finding_title>"
   # Category: <finding_category>
   # Threat class: <threat_class_name>
   # Sibling vectors covered by tests below:
   #   1. <vector_1> → tests: test_<name>
   #   2. <vector_2> → tests: test_<name>
   #   3. <vector_3> → tests: test_<name>
   #   4. <vector_4> → tests: test_<name>
   #   5. <vector_5> → tests: test_<name>
   #   N. <vector_N> → tests: test_<name>
   # ───────────────────────────────────────────────────────────────────────
   ```

   If you cannot enumerate ≥ 5 sibling vectors for the threat class, that is a signal you do not understand the threat well enough to write a robust fix. **STOP and create a `[QUESTION]` task to team-lead** describing the threat class as you understand it, the vectors you found, and what research you tried. Do not proceed with a vector-specific patch.

3. **Adversarial Variants per Acceptance Criterion**

   For each acceptance criterion in the task file, write **at least 3 adversarial test cases**. Adversarial means: tries to make the system fail in ways the AC text does not literally enumerate.

   Adversarial axes to consider (pick the ones relevant to the threat class):
   - **Boundary values**: empty, single character, max-length, max-length + 1, integer overflow, negative zero
   - **Encoding tricks**: UTF-8 vs UTF-16, percent-encoding, double-encoding, RTL overrides, zero-width chars, mixed scripts (Cyrillic A vs Latin A), homoglyphs
   - **Syntax variants of the same logical operation**: alternate keywords (e.g., SQL `JOIN ... USING` vs `JOIN ... ON`), comment styles (`/**/` vs `--`), whitespace variants (tab, NBSP, line separator)
   - **Concurrency / ordering**: stale read after write, write during read, lock release before commit, retry storm
   - **Privilege escalation paths**: read endpoint that allows write via batch param, anonymous endpoint that exposes authenticated header echo
   - **Resource exhaustion**: very deep nesting (recursion limit), very long input (memory), regex catastrophic backtracking

   Each test must use **concrete real input** (the actual byte sequence, the actual SQL string) — not parameterized symbolic placeholders. Reviewers must be able to read the test and see exactly what attack it represents.

4. **Mock Policy for Security-Relevant Categories**

   If `<finding_category> ∈ {security, validation, authorization, data-integrity}`:

   - **Mocks are FORBIDDEN** in any test that exercises the fixed code path. The test must use real dependencies — real database, real HTTP server, real auth provider, real file system. Mocks are the #1 way a security fix passes tests while still being broken: a stub `auth.is_admin()` returns whatever the mock says, regardless of whether the real check is correct.
   - If the real dependency is genuinely unavailable in the test environment, **STOP and create a `[BLOCKER]` task to team-lead** explaining what's missing (e.g., "test needs a Postgres instance with `BYPASSRLS` role; CI only has SQLite"). The leader decides whether to provision the dependency or accept the residual risk.
   - This rule overrides the general "mocks acceptable as last resort" guidance in Stage 3A.

5. **File Ownership Check**

   Same decision tree as Stage 3A — only write tests in files listed in `<my_test_files_owned>`. If the test needs to live elsewhere, raise a `[BLOCKER]`.

6. **Run Tests to Confirm They Fail Appropriately**

   All adversarial tests should fail initially against the current code (TDD). If a test passes immediately, that's a signal the threat is already handled there — note it in the test docstring and keep the test as a regression guard rather than removing it.

7. **Send Progress Update**

   ```javascript
   SendMessage({
     to: "team-lead",
     type: "message",
     content: "Progress on <task_id>: tests_created. Created N adversarial validation tests across <vector_count> sibling vectors of threat class '<threat_class_name>'. All tests FAIL as expected.",
     summary: "Progress: <task_id> — <N> adversarial tests, threat class '<threat_class_name>'"
   })
   ```

**Checkpoint: post-test-batch** — Update working notes with threat class, sibling vectors, tests created, and Next Step.

**After Stage 3D completion, proceed to Stage 4**

### Stage 4: Tracker File Creation and Finalization

1. **Create/Update Tracker File**

   **CRITICAL**: The tracker file path must be within `<my_test_files_owned>` or in the `tests/tracker-files/` directory. If `tests/tracker-files/` does not exist, create it.

   Create tracker file: `tests/tracker-files/validation_tests_tracker_<task_id>.json`

   **Format:**

   > File paths and marker names below use Python examples. Adapt extensions and marker names to match the detected language.

   ```json
   {
     "task_id": "<task_id>",
     "task_type": "NEW_FEATURE | REFACTORING | ENHANCEMENT | INTERFACE_ABSTRACTION",
     "detected_language": "<detected_language>",
     "created_date": "<ISO date>",
     "affected_modules": [
       {
         "source_file": "<path/to/source/module.py>",
         "existing_test_file": "<path/to/existing/test_file.py> | null"
       }
     ],
     "contract_tests": [
       {
         "test_file": "<path/to/test/file>",
         "test_name": "<test function/class name>",
         "contract_type": "abstract_class | data_class | factory | stub | validation",
         "description": "<what contract it verifies>",
         "interface_verified": "<name of interface/class/factory being tested>",
         "future_implementation_task": "<TASK-XX that will implement behavior>",
         "status": "CREATED_NEW",
         "markers": ["tdd_contract"]
       }
     ],
     "validation_tests": [
       {
         "test_file": "<path/to/test/file>",
         "test_name": "<test function/class name>",
         "description": "<what it validates>",
         "requirements_covered": ["<req1>", "<req2>"],
         "status": "CREATED_NEW | EXISTING | MODIFIED",
         "markers": ["tdd_validation", "integration"],
         "placement_rationale": "Explanation of why this test is in this file"
       }
     ],
     "unit_tests": [
       {
         "test_file": "<path/to/test/file>",
         "test_name": "<test function/class name>",
         "description": "<what it tests>",
         "status": "CREATED_NEW | EXISTING | MODIFIED",
         "markers": ["tdd_unit", "unit"],
         "placement_rationale": "Explanation of why this test is in this file"
       }
     ],
     "tests_not_created": [
       {
         "scenario": "<planned scenario not created>",
         "reason": "ALREADY_COVERED",
         "existing_test": "<test_file::test_name>"
       }
     ],
     "coverage_report": {
       "modules_covered": ["<module1>", "<module2>"],
       "overall_coverage": "<percentage>%",
       "gaps_identified": ["<gap1>"],
       "gaps_addressed": ["<gap1_solution>"]
     },
     "test_command": "<resolved from language profile>",
     "all_tests_passing": false,
     "notes": "<any relevant notes>"
   }
   ```

   **Field guidelines:**
   - For **NEW_FEATURE/ENHANCEMENT**: `all_tests_passing` should be `false` (TDD approach — tests fail until code is implemented)
   - For **INTERFACE_ABSTRACTION**: `all_tests_passing` should be `false` (interfaces don't exist yet). Use `contract_tests` section with `tdd_contract` marker. Include `future_implementation_task` references.
   - For **REFACTORING**: `all_tests_passing` should be `true` (existing functionality works)
   - `status` values: `CREATED_NEW` (new test), `EXISTING` (discovered), `MODIFIED` (updated existing)

**Checkpoint: post-tracker** — Update working notes with tracker path and Next Step.

2. **Send Final Review to Leader**

   Before finalizing, create a `[QUESTION]` task for final review:

   ```javascript
   TaskCreate({
     subject: "[QUESTION] Final review for <task_id> tests",
     description: "Task: <task_id>\nQuestion type: final_review\n\nTest design complete. Created N tests across M files.\nTask type: <task_type>\nTracker: tests/tracker-files/validation_tests_tracker_<task_id>.json\nTest files: <list>\nAll tests currently FAILING as expected.\n\nOptions:\n1. Approve and proceed to coding step\n2. Request changes",
     activeForm: "Waiting for final review"
   })
   TaskUpdate({ taskId: "<new_task_id>", owner: "team-lead" })

   SendMessage({
     to: "team-lead",
     type: "message",
     content: "Test design for <task_id> ready for final review. See task <new_task_id>.",
     summary: "Final review: <task_id> — <N> tests ready"
   })
   ```

   Wait for leader response. If the leader requests changes, implement them and re-submit.

3. **Commit Tests (on current branch, no branch creation)**

   **CRITICAL**: Do NOT create a new branch. Commit directly on the current branch.

   ```bash
   # Verify you are only committing owned files
   git add <only files in my_test_files_owned and tracker file>
   git commit -m "test: Add validation tests for <task_id>

   Created validation tests covering:
   - <requirement 1>
   - <requirement 2>

   Tests define expected behavior before implementation.
   Task type: <task_type>

   Task: <task_id>"
   ```

   **NEVER use `git add .` or `git add -A`** — only add files you own.

**Checkpoint: post-commit** — Update working notes with commit hash and Next Step.

4. **Signal Completion**

   Send the tests complete message to the leader:

   ```javascript
   SendMessage({
     to: "team-lead",
     type: "message",
     content: "Tests complete for <task_id>. Tracker: tests/tracker-files/validation_tests_tracker_<task_id>.json. Tests: <N>. Files: <list>. Type: <task_type>. All passing: false.",
     summary: "Tests complete: <task_id> — <N> tests"
   })
   ```

5. **Proceed to Coding Step**

   After signaling completion, the same teammate proceeds to execute the coding step:

   **Execute the `code_from_validation_tests_swarm` command with the same `<task_id>`.**

   The tracker file serves as the handoff artifact — it contains everything the coding step needs to know about what tests exist and what they expect.

## Important Notes

### General Principles
- **NO IMPLEMENTATION CODE**: This command only manages tests, no feature implementation
- **FILE OWNERSHIP IS LAW**: Never touch files outside your ownership list
- **COMMUNICATE CONSTANTLY**: A silent teammate is invisible — use SendMessage and TaskCreate at every decision point and milestone
- **LEADER AS STAFF ENGINEER**: The leader has full context of the plan and all tasks — trust its technical judgment when it overrides your recommendation

### Test Placement Strategy

**MANDATORY RULES — in order of priority:**

1. **ONLY create/modify test files in `<my_test_files_owned>`** — this overrides all other placement rules
2. **NEVER create a centralized test module** (e.g., `test_validation_tdd.py`) — always use module-specific test files
3. **Check existing coverage BEFORE writing any test** — if `ALREADY_COVERED`, do not duplicate
4. **Prefer adding tests to existing files** when a module already has test coverage in your ownership
5. **If you need a file outside ownership, create a [BLOCKER] task for the leader** — never silently create or modify unowned files

### TDD Philosophy

- **NEW_FEATURE/ENHANCEMENT**: Tests should FAIL initially — that is expected and correct. They define the target behavior.
- **INTERFACE_ABSTRACTION**: Tests should FAIL initially — interfaces don't exist yet. Tests verify contracts and structure, not business behavior. Behavioral tests will be created in separate implementation tasks.
- **REFACTORING**: Tests should PASS — they verify existing behavior that must be preserved.

### Test Markers

| Marker | Usage |
|--------|-------|
| `@pytest.mark.tdd_validation` | **Required** for validation/integration tests (NEW_FEATURE/ENHANCEMENT) |
| `@pytest.mark.tdd_contract` | **Required** for contract/interface tests (INTERFACE_ABSTRACTION) |
| `@pytest.mark.tdd_unit` | **Required** for unit tests when validation tests are not possible |
| `@pytest.mark.integration` | Optional, for multi-component tests |
| `@pytest.mark.unit` | Optional, for isolated function tests |

ALL new tests MUST have `@pytest.mark.tdd_validation`, `@pytest.mark.tdd_contract`, OR `@pytest.mark.tdd_unit`.

### Communication Checklist

Before considering this stage complete, verify you sent ALL of these:

- [ ] Progress update: context gathered (after analyzing task)
- [ ] `[QUESTION]` task: task classification (with your recommendation)
- [ ] Progress update: classification done (after classification resolved)
- [ ] Progress update: discovery done (after test module discovery)
- [ ] `[QUESTION]` task(s): coverage decision (for any PARTIALLY_COVERED scenarios)
- [ ] `[QUESTION]` task: final review (before finalizing)
- [ ] Progress update: tests created (after writing tests)
- [ ] Tests complete message (handoff signal to coding step)

### What NOT to Do

- Do NOT create branches or worktrees
- Do NOT push to remote
- Do NOT create pull requests
- Do NOT modify files outside your ownership list
- Do NOT skip communication — every decision must be visible to the leader
- Do NOT run `git add .` or `git add -A` — only add owned files explicitly by path

## Quality Checklist

### Swarm Constraints
- [ ] Read `swarm-manifest.json` and identified owned files
- [ ] All created/modified test files are in `<my_test_files_owned>`
- [ ] No files outside ownership were touched
- [ ] No branches or worktrees were created
- [ ] All communication via SendMessage and TaskCreate
- [ ] Working notes file (`working-notes-<task_id>.md`) kept up to date throughout execution

### Test Quality
- [ ] Task type correctly classified (with leader consultation)
- [ ] Stage 2.7 (Test Module Discovery) completed before creating tests
- [ ] No duplicate tests created for ALREADY_COVERED scenarios
- [ ] All new tests have `@pytest.mark.tdd_validation`, `@pytest.mark.tdd_contract`, or `@pytest.mark.tdd_unit`
- [ ] Tests are distributed across appropriate module test files
- [ ] For NEW_FEATURE/ENHANCEMENT: tests currently FAIL (TDD)
- [ ] For INTERFACE_ABSTRACTION: tests currently FAIL (interfaces don't exist yet), using `tdd_contract` marker
- [ ] For REFACTORING: all tests currently PASS

### Tracker and Handoff
- [ ] Tracker JSON created at `tests/tracker-files/validation_tests_tracker_<task_id>.json`
- [ ] Tracker contains all test entries with correct status and markers
- [ ] Tests complete message sent to leader
- [ ] Ready to proceed to `code_from_validation_tests_swarm`
