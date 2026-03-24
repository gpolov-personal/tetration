---
name: code_from_validation_tests_swarm
description: "Phase B of swarm worker: implement code to make validation tests pass (TDD)"
argument-hint: (no direct arguments — runs as continuation of design_validation_tests_swarm)
---

# Implementation Command (TDD-Guided) -- Swarm Teammate Version

## Language Adaptation

These instructions use Python as the concrete example language. When working on a non-Python project:

1. **Detect the project language** from its manifest files (see the `language-profiles` skill)
2. **Resolve toolchain commands** using the Language Profiles (test runner, linter, etc.)
3. **Adapt structural patterns** using the Language Adaptation Notes (file ownership, import rules, stub lifecycle, test tagging)

All Python-specific examples below (pytest commands, import syntax, Protocol/ABC references) should be adapted to the detected language's equivalent.

---

## Introduction

This command implements the functionality required by a task, guided by the validation tests created in the previous phase. It follows Test-Driven Development by using the validation tests as a specification, implements the changes to make those tests pass, creates unit tests for the new code, and signals completion to the swarm leader.

This command is designed to run as part of a swarm -- executed by the same teammate that just completed `design_validation_tests_swarm`. The teammate already has context from the test design phase: the assigned task ID, the tracker JSON, and the swarm manifest.

## Context Available from Previous Phase

The teammate executing this command already has:
- `<task_id>` -- the assigned task ID
- `<tracker_file_path>` -- path to the validation tests tracker JSON produced during the test design phase
- `<manifest>` -- the parsed `swarm-manifest.json` contents
- `<my_task>` -- the task entry from the manifest matching the task ID
- `<files_owned>` -- list of source files this teammate is allowed to modify (from `my_task.files_owned[]`)
- `<test_files_owned>` -- list of test files this teammate is allowed to modify (from `my_task.test_files_owned[]`)
- `<shared_files>` -- list of files that are OFF-LIMITS (from `manifest.shared_files[]`)

## Prerequisites

- Validation tests already created and tracked in `<tracker_file_path>`
- `swarm-manifest.json` already loaded and parsed
- File ownership boundaries known from the manifest
- Working directory is the shared repository root (no worktree, no branch switching)

## Communication Protocol

Every significant event MUST be communicated to the leader. Communication uses two mechanisms:

1. **SendMessage** — for progress updates, integration requests, and non-blocking notifications
2. **TaskCreate + TaskUpdate** — for questions and blockers that need leader decisions (creates traceability)

The leader's name is `team-lead`.

### Message Formats

**Implementation started** -- send immediately when beginning this stage:
```javascript
SendMessage({
  to: "team-lead",
  type: "message",
  content: "Implementation started for <task_id>. Files to modify: <files_owned>.",
  summary: "Started: <task_id> implementation"
})
```

**Blocker resolved** -- send when completing code that unblocks another task:
```javascript
SendMessage({
  to: "team-lead",
  type: "message",
  content: "Blocker resolved for <task_id>. Unblocks: <task IDs>. Files completed: <files>. Interfaces exposed: <public classes/functions>. Stub replaced: <stub_file if interface provider, otherwise omit>.",
  summary: "Blocker resolved: <task_id> unblocks <task IDs>"
})
```

**Ownership violation request** -- send when implementation requires a file outside ownership:
```javascript
// 1. Create a blocker task for the leader
TaskCreate({
  subject: "[BLOCKER] Ownership request: <file path>",
  description: "Task: <task_id>\nBlocker type: ownership_violation\n\nFile needed: <path to file outside ownership>\nReason: <why this file needs to be modified>\n\nI am STOPPED and waiting for your decision.",
  activeForm: "Blocked: waiting for ownership decision"
})
TaskUpdate({ taskId: "<new_task_id>", owner: "team-lead" })

// 2. Notify the leader
SendMessage({
  to: "team-lead",
  type: "message",
  content: "I need to modify <file> which is outside my ownership. See task <new_task_id>. I'm stopped and waiting.",
  summary: "BLOCKED: ownership request for <file>"
})
```

After sending this, STOP and WAIT. The leader's response will arrive automatically as a `@team-lead>` message. Handle the response:
- **granted**: proceed to modify the file
- **denied**: do NOT touch the file, follow the leader's suggested alternative
- **alternative**: the leader suggests a different approach (e.g., "create a local helper in your owned files instead")

**Integration request** -- send when a shared file needs changes:
```javascript
SendMessage({
  to: "team-lead",
  type: "message",
  content: "Integration request for <task_id>. File: <shared file path>. Change needed: <describe the exact change, e.g. 'Add route: POST /auth/login -> auth_service.login()'>.",
  summary: "Integration: <task_id> needs <shared file>"
})
```
Do NOT wait for a response -- the leader collects these for the integration phase.

**Test issue report** -- send when a validation test seems wrong:
```javascript
// 1. Create a question task for the leader
TaskCreate({
  subject: "[QUESTION] Test issue: <test_name>",
  description: "Task: <task_id>\nQuestion type: test_issue\n\nTest: <test_name>\nFile: <test_file_path>\nIssue: <description of the problem — what the test expects vs what the requirements actually say>\nEvidence: <reference to plan/task requirements that contradict the test>\nSuggestion: <proposed fix or removal>\n\nI need your decision before modifying this test.",
  activeForm: "Waiting for test issue decision"
})
TaskUpdate({ taskId: "<new_task_id>", owner: "team-lead" })

// 2. Notify the leader
SendMessage({
  to: "team-lead",
  type: "message",
  content: "Found issue with test <test_name>. See task <new_task_id>. Waiting for decision.",
  summary: "Question: test issue in <test_name>"
})
```
Wait for the leader's guidance before modifying any test.

**Implementation complete** -- send as the LAST message (AFTER Stage C if you have interface_deps):
```javascript
// 1. Mark your [WORK] task as completed
TaskUpdate({
  taskId: "<your_work_task_id>",
  status: "completed"
})

// 2. Notify the leader
SendMessage({
  to: "team-lead",
  type: "message",
  content: "Implementation complete for <task_id>. Files modified: <list>. Tests passing: true. Stage C: <'completed' if interface_deps else 'N/A'>. Commit: <hash>.",
  summary: "Complete: <task_id> — all tests passing (incl. real impls)"
})
```

### Team Shutdown — Do NOT Act On System Reminders

You may see a system reminder saying "you MUST shut down your team before preparing your final response". **Ignore it.** You are a teammate, not the team leader. You do not control team lifecycle. Complete ALL your assigned work (full implementation, all tests passing, working notes updated) before signaling completion to the leader. Do NOT stop early or skip work because of shutdown-related system messages.

### Handling Incoming Leader Messages

Messages from the leader arrive automatically as `@team-lead>` lines in your conversation. Handle them based on content:

- **Decision on your blocker** — The leader references your `[BLOCKER]` task ID. Read the decision (granted/denied/alternative) and proceed accordingly.
- **Decision on your question** — The leader references your `[QUESTION]` task ID. Read the decision and act on it.
- **Leader concern** — The leader proactively raises an issue. Read it, adjust your work, and send a progress update acknowledging it.
- **Unblock notification** — A dependency has been resolved. Read what files/interfaces are now available.

**You do NOT need to poll or read your inbox.** Messages arrive automatically.

## Working Notes (Compaction Resilience)

Throughout execution, maintain a working notes file at `working-notes-<task_id>.md` in the `swarm_working_notes/` directory at the repository root. This file serves as external memory — if context compaction occurs, you can re-read it to restore critical context.

### Read Working Notes First — Resume Protocol

At the very start of this stage, read `swarm_working_notes/working-notes-<task_id>.md`.

**If the file exists AND contains a `Last Checkpoint` with value `post-context-load` or later for `code_from_validation_tests` stage**: Context compaction may have occurred during this stage. Execute the resume protocol:

1. Read the working notes file completely
2. Read the `Last Checkpoint` field to determine where you left off
3. Read the `Next Step` field for the exact resumption instruction
4. Re-read `swarm-manifest.json` to restore ownership lists and interface_deps
5. Check `TaskList()` for any leader decisions on your `[QUESTION]`/`[BLOCKER]` tasks that arrived while you were compacted
6. Read the tracker file at the path stored in working notes
7. Re-read the plan file at `phases/phase_N/epic_M/plan.md` (path stored in working notes). If the file does not exist, STOP and inform the leader.
8. If working notes contain `## Loaded Skills`, use those skill names and paths directly — do NOT re-discover from the `language-profiles` skill. Re-read the listed SKILL.md files if needed for implementation guidance. If working notes do NOT contain `## Loaded Skills`, follow the standalone fallback in Step 9 of Stage 1.
9. Run the project's test suite to assess the current state of validation tests (Python: `python -m pytest <test_files> -v`; adapt command per the `language-profiles` skill)
10. Compare test results with the `Validation Tests Status` from working notes to understand what has changed
11. Follow the `Next Step` instruction to continue from the correct point

**If the file exists but is from the `design_validation_tests` phase only** (no `code_from_validation_tests` checkpoint): This is the normal flow — the previous phase completed. Read it for context (ownership, decisions, patterns), then proceed to update it for the new phase.

**If the file does not exist** (unexpected): Create it with the initial template.

### Update for Implementation Phase

Update the working notes to reflect the new phase:

```markdown
## Phase: code_from_validation_tests (updated)

## Implementation Plan
(add your implementation plan here after Stage 1)

## Validation Tests Status
- Total: N
- Passing: 0
- Failing: N
(update after each implementation step)

## Files Modified
(track as you go)

## Integration Requests Sent
(track shared file changes requested)

## Progress
- [ ] Context loaded and working notes read
- [ ] Tracker file parsed
- [ ] Initial validation tests run
- [ ] Codebase explored
- [ ] Implementation plan created
- [ ] Implementation complete — all validation tests passing
- [ ] Unit tests created
- [ ] Final validation passed
- [ ] Final commit created
```

### Update Working Notes — Mandatory Checkpoints

Update the working notes file at each of the following checkpoint moments. Each checkpoint **MUST** include a `Last Checkpoint` and `Next Step` entry describing what to do if resuming from this point.

| # | Checkpoint | When | What to persist |
|---|-----------|------|-----------------|
| 1 | post-context-load | After loading tracker, reading issue, and exploring codebase (Stage 1) | tracker summary, failing test count, plan file path |
| 2 | post-plan | After creating implementation plan with TodoWrite (Stage 1 step 8) | **implementation plan summary** (persist key steps here — TodoWrite is in-memory only and lost on compaction) |
| 3 | post-impl-step | After each major implementation step that passes new tests (Stage 2) | which validation tests now pass, which still fail, files modified so far |
| 4 | post-all-validation | After all validation tests pass (end of Stage 2) | all validation tests passing confirmation, total passing count |
| 5 | post-unit-tests | After unit tests created (Stage 3) | unit test files and counts, any discovered issues |
| 6 | post-phase-c | After Stage C re-validation (if applicable) (Stage C) | Stage C result, fixes applied, providers validated |
| 7 | post-final-commit | After final commit (Stage 5) | final commit hash, all files modified list, integration requests sent list |

**Checkpoint format in working notes:**

```markdown
## Phase: code_from_validation_tests
## Last Checkpoint: <checkpoint_name>

## Next Step
If resuming: <specific instruction, e.g., "Read tracker at <path>. Run validation tests. 3 of 8 were passing at last checkpoint. Continue implementing from step 4 of the plan below.">

## Validation Tests Status
- Total: 8
- Passing: 3
- Failing: 5 (test_login_flow, test_register_validation, ...)

## Attempt Tracking
- test_login_flow: 2 consecutive failures (same TypeError)
- test_register_validation: 1 attempt (new failure)

## Implementation Plan Summary
1. Create auth models (DONE)
2. Implement login handler (DONE)
3. Implement register handler (IN PROGRESS - step 3a done, 3b pending)
4. Add error handling (PENDING)
...

## Integration Requests Sent
- routes.py: "Add POST /auth/login -> auth_service.login()"
- package index file (e.g. __init__.py in Python, index.ts in TypeScript): "Export AuthService from auth module" — skip for Go/.NET

## Plan File: phases/phase_N/epic_M/plan.md

## Detected Tech Stack
- Language: <detected_language>
- Framework: <detected_framework>

## Loaded Skills
- <skill_name_1>: <skill_path_1> (loaded, <N> lines)
- <skill_name_2>: <skill_path_2> (skipped — not relevant to this task)
```

**IMPORTANT**: Keep the file concise. Overwrite sections rather than appending. The `Last Checkpoint` and `Next Step` fields are the most critical — they enable deterministic resume after compaction.

---

## Execution Workflow

### Stage 1: Signal Start and Load Context

1. **Signal implementation started**

   Send the implementation started message to the leader immediately.

2. **Check for dependency context**

   If `<my_task>` has `blocked_by` entries:
   - The leader should have already sent an unblock message with details about which files are now available
   - Read any messages from the leader about unblocked dependencies
   - Read the files mentioned in the unblock message to understand the interfaces you depend on
   - Verify those files exist and contain the expected interfaces

2b. **Check for interface dependencies**

   If `<my_task>` has `interface_deps` entries:
   - For each interface dep:
     a. Read the stub file to understand the interface
     b. Verify importable (Python: `python -c "from <module> import <Name>"`; adapt per the `language-profiles` skill verify_import)
     c. If import fails with a parse/compilation error (SyntaxError in Python), retry once after 2 seconds (provider may be mid-write)
   - Store interfaces in `<available_interfaces>`
   - Your implementation MUST:
     - Import directly from the stub file path (e.g. `from src.auth.models import UserModel`)
     - Accept dependencies via constructor/function params typed against the interface
     - Never instantiate the provider's class directly

3. **Load Tracker File**

   Parse `<tracker_file_path>`:
   - Extract the validation tests list
   - Understand what functionality each test validates
   - Note the test command to run

4. **Read Task Details**

   - Read the task file from the `phases/` directory. Find the task by its ID: scan `phases/phase_*/epic_*/tasks/task_*.md` for a matching `id` in the YAML frontmatter, or derive the path from the manifest. Extract the title, body content, labels, and comments from the markdown file.
   - Extract `<epic_id>` from the `epic_id` field in `<manifest>` (already loaded from previous phase)
   - Read the plan file at `phases/phase_N/epic_M/plan.md` (derive the phase and epic from the manifest or task path). If the file does not exist, STOP and inform the leader that no plan was found for task <epic_id>.
   - Store the plan file path in working notes for re-reading after compaction.
   - Store the plan content and the parent task body for reference
   - Identify all deliverables, requirements, constraints, and edge cases

5. **Run Initial Validation Tests**

   - Execute the validation tests from `<tracker_file_path>`
   - Document which tests are failing and why
   - Confirm tests fail for expected reasons (not due to missing dependencies or setup issues)

6. **Explore Codebase**

   - Identify modules/files that need changes -- cross-reference with `<files_owned>`
   - Understand current architecture and patterns
   - Review domain-driven design structure
   - Identify integration points

7. **Validate File Ownership**

   Before planning any changes, verify:
   - Every file you plan to modify is in `<files_owned>` or `<test_files_owned>`
   - No file you plan to modify is in `<shared_files>`
   - If a needed file is outside ownership, create a `[BLOCKER]` task and WAIT
   - If a shared file needs changes, send an integration request (no waiting needed)

   **Checkpoint: post-context-load** — Update working notes with tracker summary, failing test count, plan file path, and Next Step.

8. **Create Implementation Plan with TodoWrite**

   - Break down implementation into logical steps
   - Order steps by dependencies
   - Include validation test checkpoints after each major change
   - Add unit test creation tasks
   - Include lint/typecheck validation
   - Plan atomic commits at logical boundaries

   **Checkpoint: post-plan** — Update working notes with:

   ```markdown
   ## Last Checkpoint: post-plan

   ## Next Step
   If resuming: Read the implementation plan summary below. Read tracker at <tracker_path>. Run validation tests to see current state. Start implementing from step 1 of the plan.

   ## Implementation Plan Summary
   1. <step 1 description> (PENDING)
   2. <step 2 description> (PENDING)
   ...
   ```

   This ensures the implementation sequence survives compaction even if the TodoWrite internal state is lost.

9. **Load Relevant Skills**

   Read `<detected_tech_stack>` and `<relevant_skills>` from:
   1. Your spawn prompt context above (normal flow)
   2. Your working notes `## Detected Tech Stack` and `## Loaded Skills` sections
      (if spawn prompt was compacted — resume flow)
   3. If neither is present: standalone fallback below

   If `<relevant_skills>` is present and non-empty:

   a. For each skill in `<relevant_skills>`, evaluate if it's relevant to YOUR specific task
      based on the files you own and what you're implementing.

   b. For each relevant skill, check if a `SKILL_INDEX.md` exists in the same directory.
      - If `SKILL_INDEX.md` exists: read it first, then load only the sections relevant
        to your task (saves context vs reading the full SKILL.md).
      - If no index: read the full SKILL.md.
      Load a maximum of ~300 lines of skill content total.
      Prioritize:
      1. Language/framework best practices (e.g., `react-best-practices`)
      2. Architecture patterns relevant to your task (e.g., `composition-patterns`)
      3. Domain-specific skills (e.g., `rag-implementation` if building RAG features)

   c. Store loaded skill knowledge as `<skill_guidance>` and reference it during
      implementation. Apply skill recommendations as you write code in Stage 2,
      but do NOT let skills override the validation tests — tests are the
      specification, skills inform HOW you implement.

   If `<relevant_skills>` is NOT present (standalone execution without orchestrator):
   - Read the "Stack-Specific Skills" section from the `language-profiles` skill
   - Detect your project's tech stack from the Language Detection table in the same skill
   - Look up relevant skills and load up to ~300 lines total

   **Checkpoint update (compaction resilience)**: Add to working notes:
   - `## Detected Tech Stack` with `<detected_language>` and `<detected_framework>`
   - `## Loaded Skills` with skill names, paths, and line counts loaded
   This ensures skill info survives context compaction.

### Stage 2: Implementation Loop

<thinking> You are a Senior AI Backend Engineer working as a teammate in a swarm. You MUST respect file ownership boundaries. You MUST communicate progress to the leader. You follow TDD -- let validation tests guide your implementation. </thinking>

1. **Iterative Implementation**
```
   for each implementation task:
     1. Verify the target file is in <files_owned> -- STOP if it is not
     2. Review what validation tests this will help pass
     3. Explore relevant code sections
     4. Implement the change following best practices
     5. Run affected validation tests
     6. If tests pass: mark task complete, move to next
     7. If tests fail: analyze failure, refine implementation
     8. Run lint and typecheck after each significant change
     9. If this change unblocks another task (check my_task.blocks[]):
        -> Send blocker resolved message to the leader IMMEDIATELY
        -> Do not wait until the end to signal this
     10. If you are an interface PROVIDER (check: does any task's interface_deps list your
         id as provider_id in swarm-manifest.json):
         -> Your stub_file currently contains the stub you generated at the start
         -> OVERWRITE the file entirely with your real implementation
         -> Implement ALL methods from the contract with real business logic
         -> Maintain the same public API (class name, method signatures) as the stub
         -> Send "Blocker resolved" message IMMEDIATELY after replacing the stub
            so consumers know the real implementation is available
     11. If you have interface dependencies (<my_interface_deps> not empty):
         -> Use dependency injection for ALL interface dependencies
         -> Type params using the interface/abstract type (Protocol/ABC in Python; adapt per the `language-profiles` skill for your tech stack), not concrete class
         -> Import directly from the file path, not the package (Python/TypeScript-specific rule; see "Import / Dependency Rules" in the `language-profiles` skill):
            CORRECT: from src.auth.models import UserModel  # Protocol/ABC (adapt command per the `language-profiles` skill for your tech stack)
            WRONG:   from src.auth import UserModel  # depends on shared __init__.py
         -> This ensures your code works with both stub AND real implementation
         -> If import fails with a parse/compilation error (SyntaxError in Python), retry once after 2 seconds
```

   **Progress Heartbeat** — After each validation test run, send a progress message to the leader:
   ```javascript
   SendMessage({
     to: "team-lead",
     type: "message",
     content: "Progress <task_id>: <passing>/<total> validation tests passing. Step: <current_step>. Attempts on current step: <N>.",
     summary: "Progress: <task_id> — <passing>/<total> tests"
   })
   ```

   **Stuck Detection** — Track consecutive failed attempts on the same failing test(s). If you have attempted to fix the same test 3+ consecutive times and it still fails with a similar error:

   ```javascript
   TaskCreate({
     subject: "[STUCK] <task_id> — <test_name> failing <N> consecutive attempts",
     description: "Task: <task_id>\nStuck type: repeated_failure\nTest: <test_name>\nAttempts: <N>\nError pattern: <consistent error type/message>\nFiles modified so far: <list>\nLast 2 errors:\n<error_1_summary>\n<error_2_summary>\n\nI have tried <N> approaches and cannot resolve this. Requesting guided assistance.",
     activeForm: "Stuck: waiting for guidance"
   })
   TaskUpdate({ taskId: "<new_task_id>", owner: "team-lead" })

   SendMessage({
     to: "team-lead",
     type: "message",
     content: "STUCK on <task_id>: <test_name> has failed <N> consecutive attempts. See task <new_task_id>. Waiting for guidance.",
     summary: "STUCK: <task_id> — <test_name> (<N> attempts)"
   })
   ```

   After sending a `[STUCK]` task, **continue working on OTHER implementation steps** that don't depend on the stuck test. Only STOP entirely if all remaining steps depend on the stuck test. When the leader responds with guidance, apply it and retry.

   **Checkpoint: post-impl-step** — Update working notes with current test pass/fail counts, files modified, attempt counts, and Next Step.

2. **File Ownership Enforcement**

   Before EVERY file modification, check:
   - Is this file in `<files_owned>`? -> Proceed
   - Is this file in `<test_files_owned>`? -> Proceed (for test files only)
   - Is this file in `<shared_files>`? -> Send integration request, do NOT modify
   - Is this file not in any of the above? -> Create `[BLOCKER]` task, WAIT for response

3. **Code Quality Standards**

   - Follow existing code patterns and conventions
   - Maintain domain-driven design principles
   - Write clean, readable, maintainable code
   - Add appropriate error handling
   - Include docstrings/comments for complex logic
   - Ensure type hints are correct

4. **Design Decision Escalation**

   During implementation, if you face a decision where there are multiple reasonable approaches, you MUST escalate it to the leader before proceeding. Do NOT pick an option silently.

   **When to escalate:**
   - Choosing between two or more design patterns (e.g., inheritance vs composition, strategy vs factory)
   - Deciding the structure of a new module, class, or service
   - Choosing how to handle an edge case not covered by validation tests
   - Defining the public API of a class or function (method signatures, return types)
   - Deciding on error handling strategy (raise vs return, custom exceptions vs generic)
   - Any decision where a different developer might reasonably choose differently

   **When NOT to escalate** (just implement):
   - Variable naming (follow existing conventions)
   - Import ordering
   - Formatting choices covered by the linter
   - Implementation details with only one reasonable approach

   **How to escalate:**

   ```javascript
   TaskCreate({
     subject: "[QUESTION] Design decision: <brief description>",
     description: "Task: <task_id>\nQuestion type: design_decision\n\nContext: <what you are implementing and why this decision arose>\n\nOptions:\n1. <option A — description, pros, cons>\n2. <option B — description, pros, cons>\n\nMy recommendation: <preferred option and why>",
     activeForm: "Waiting for design decision"
   })
   TaskUpdate({ taskId: "<new_task_id>", owner: "team-lead" })

   SendMessage({
     to: "team-lead",
     type: "message",
     content: "Design decision needed for <task_id>. See task <new_task_id>.",
     summary: "Question: design decision for <brief>"
   })
   ```

   Wait for the leader's response before implementing the decision.

5. **Continuous Validation**

   After each logical implementation step:
```bash
   # Run validation tests (adapt command per the `language-profiles` skill)
   python -m pytest <test_files_from_tracker>

   # Run linter
   <project_lint_command>

   # Run type checker
   <project_typecheck_command>
```

5. **Atomic Commits**

   After completing each logical unit of work:
```bash
   # Stage ONLY files in files_owned and test_files_owned
   git add <specific files from files_owned>

   # Commit with issue number reference
   git commit -m "feat(#<task_id>): <brief description of what was implemented>

   <detailed list of changes if needed>"
```

   Rules for commits:
   - ONLY `git add` files that are in `<files_owned>` or `<test_files_owned>`
   - NEVER `git add .` or `git add -A` -- this could stage files owned by other teammates
   - Reference `#<task_id>` in every commit message
   - Keep commits logically atomic -- one concern per commit

6. **Progress Tracking**

   - Update TodoWrite tasks as you complete them
   - Note any unexpected issues or discoveries
   - Track which validation tests are now passing

   **Checkpoint: post-all-validation** — Update working notes confirming all validation tests pass and Next Step.

### Stage 3: Unit Test Creation

**ONLY proceed after all validation tests are passing**

1. **Identify Code Requiring Unit Tests**

   - List all new functions/methods/classes created
   - List all modified functions with changed behavior
   - Identify complex logic that needs isolated testing
   - Note any utility functions or helpers added

2. **Create Unit Tests**

   For each function/method requiring unit tests:

   a. **Verify test file ownership**: The test file MUST be in `<test_files_owned>`

   b. **Create focused unit tests:**
   - Test individual functions in isolation
   - **Use real dependencies first** — mocks ONLY when a dependency is genuinely unavailable (e.g., a third-party API with no sandbox, a paid service with no test tier)
   - NEVER use SQLite as a substitute for PostgreSQL, in-memory fakes for real services, or monkeypatched connections — these hide real integration bugs
   - Cover happy path, edge cases, and error cases
   - Use descriptive test names
   - Aim for high code coverage of new/modified code

   c. **Organize tests properly:**
   - Place unit tests in appropriate test files (within `<test_files_owned>`)
   - Follow project's test organization conventions
   - Group related tests logically
   - Use proper test fixtures and setup

   d. **Run and verify unit tests:**
```bash
   <command_to_run_unit_tests>
```

3. **Review Implementation Quality**

   While writing unit tests, assess:
   - Is the code properly structured?
   - Are functions doing one thing well?
   - Is there proper separation of concerns?
   - Are there any code smells or anti-patterns?

   If issues found:
   - Refactor the implementation (within `<files_owned>` only)
   - Ensure validation tests still pass
   - Update unit tests if needed

   **Checkpoint: post-unit-tests** — Update working notes with unit test files/counts and Next Step.

### Stage 4: Final Validation

1. **Comprehensive Test Suite**
```bash
   # Run ALL tests (validation + unit tests)
   <command_to_run_all_tests>
```

   - Verify all validation tests pass
   - Verify all unit tests pass
   - Ensure no test regressions
   - Check test coverage if applicable

2. **Code Quality Checks**
```bash
   # Run linter
   <project_lint_command>

   # Run type checker
   <project_typecheck_command>
```

   - Fix any linting issues
   - Resolve any type errors
   - Address any quality warnings

3. **Update Tracker File**

   Update the validation tests tracker JSON:
   - Set `"all_tests_passing": true`
   - Add implementation completion timestamp
   - Add any relevant notes about the implementation

4. **Verify File Ownership Compliance**

   Final check before completion:
   - Run `git diff --name-only` to see all modified files
   - Verify EVERY modified file is in `<files_owned>` or `<test_files_owned>`
   - If any file was modified that should not have been, revert those changes

5. **Document Integration Needs**

   If any shared files need changes, ensure you have already sent integration request messages for each one. Review and send any that were missed.

### Stage C: Re-validate Against Real Implementations (consumers with interface_deps only)

**Skip this stage if `<my_interface_deps>` is empty.** Proceed directly to Stage 5.

This phase ensures your code works with the REAL provider implementations, not just with your test fakes/mocks.

#### C.1 Check Provider Status

For each interface dependency in `<my_interface_deps>`:
1. Check if the provider has sent "Blocker resolved ... Stub replaced" via leader notification
2. If YES for ALL providers: proceed to C.2
3. If NO (some providers still working):
   - Send progress update to leader:
     ```javascript
     SendMessage({
       to: "team-lead",
       type: "message",
       content: "Implementation done for <task_id>. Waiting for real interfaces from providers: <list of pending provider issues>. Will re-validate when ready.",
       summary: "Waiting for providers: <task_id> Stage C pending"
     })
     ```
   - WAIT for leader messages. When you receive "Interface <name> real impl ready — run Stage C", check again if ALL providers are done. Only proceed to C.2 when all are ready.

#### C.2 Re-run Tests Against Real Implementations

1. Re-run your FULL test suite (Python: `python -m pytest <my_test_files> -v`; adapt per the `language-profiles` skill).

2. **If all tests pass**: Stage C complete. Proceed to Stage 5 (Final Commit).

3. **If tests fail**: The real implementation differs from what your fakes/mocks assumed.
   - Analyze each failure:
     a. **Contract mismatch** (provider changed method signatures): Create `[BLOCKER]` for leader. You cannot fix this — the provider needs to honor the original contract.
     b. **Behavioral assumption** (your code assumed specific behavior the real impl doesn't have): Fix your code to work with the real implementation. This is YOUR responsibility.
     c. **Import error** (parse/compilation error — SyntaxError or ModuleNotFoundError in Python): The provider's file may be mid-write. Retry once after 2 seconds. If still fails, create `[BLOCKER]`.
   - After fixing, re-run tests. Repeat until all pass.
   - Commit fixes:
     ```bash
     git add <modified_files>
     git commit -m "fix(#<task_id>): adapt to real <interface_name> implementation"
     ```

4. Send Stage C completion to leader:
   ```javascript
   SendMessage({
     to: "team-lead",
     type: "message",
     content: "Stage C complete for <task_id>. All tests pass against real implementations. Providers validated: <list>. Fixes applied: <count or 'none'>.",
     summary: "Stage C done: <task_id> validated against real impls"
   })
   ```

   **Checkpoint: post-phase-c** — Update working notes with Stage C results and Next Step.

### Stage 5: Final Commit and Signal Completion

1. **Final Commit**
```bash
   # Stage only owned files
   git add <specific files from files_owned and test_files_owned>

   # Create final commit
   git commit -m "feat(#<task_id>): Complete implementation with unit tests

   All validation tests passing
   Unit tests created and passing
   Lint and typecheck passing"
```

2. **Capture Commit Hash**
```bash
   COMMIT_HASH=$(git rev-parse --short HEAD)
```

   **Checkpoint: post-final-commit** — Update working notes with final commit hash, files modified, and integration requests sent.

3. **Signal Implementation Complete**

   This MUST be the last action. Before sending, verify:
   - All validation tests pass
   - All unit tests pass
   - If you have interface_deps: Stage C is complete (tests pass against real implementations)

   Only then:

```javascript
// 1. Mark your [WORK] task as completed
TaskUpdate({
  taskId: "<your_work_task_id>",
  status: "completed"
})

// 2. Notify the leader
SendMessage({
  to: "team-lead",
  type: "message",
  content: "Implementation complete for <task_id>. Files modified: <list>. Tests passing: true. Stage C: <'completed' if interface_deps else 'N/A'>. Commit: <COMMIT_HASH>.",
  summary: "Complete: <task_id> — all tests passing (incl. real impls)"
})
```

### Post-Completion: E2E Fix Readiness

After signaling completion, your process will be shut down. However, if E2E tests fail later,
the leader may respawn you in **E2E FIX MODE**. To support this:

1. Ensure your working notes (`swarm_working_notes/working-notes-<task_id>.md`) are complete
   with the `post-final-commit` checkpoint including:
   - All files you modified and WHY
   - Key implementation decisions and their rationale
   - Integration points with other components
   - Any known edge cases or limitations
   - Interface contracts you depend on or provide

2. If you are respawned in fix mode, the leader's spawn prompt will include:
   - The specific E2E failure (test name, error, stack trace)
   - Your owned files list
   - Your `[E2E-FIX]` task ID in the shared task list
   - Instructions to read your working notes first

3. In fix mode, you will follow a simplified workflow:
   - Read working notes to restore context
   - Analyze the E2E failure
   - Fix the root cause in your owned files ONLY
   - If the fix requires files outside your ownership, report to the leader as CROSS-BOUNDARY
   - If the E2E test itself appears wrong, report to the leader as TEST-ISSUE
   - Run your own validation/unit tests to confirm no regressions
   - Commit the fix and signal completion

You do NOT need to take any special action now — just ensure your working notes
are thorough at the `post-final-commit` checkpoint.

## Important Rules

- **TDD DRIVEN**: Let validation tests guide implementation
- **FILE OWNERSHIP IS ABSOLUTE**: NEVER modify a file outside `<files_owned>` and `<test_files_owned>` without explicit leader authorization via a `[BLOCKER]` task
- **SHARED FILES ARE OFF-LIMITS**: Never modify files in `<shared_files>` -- send integration request instead
- **COMMUNICATE EVERYTHING**: Every significant event (start, blocker resolved, ownership violation, integration need, completion) must be communicated
- **SIGNAL BLOCKERS IMMEDIATELY**: If your task blocks others, send blocker resolved message as soon as the blocking code is ready -- do not wait until the end
- **ATOMIC COMMITS**: Commit frequently with only owned files, referencing the issue number
- **NO WORKTREE**: Work directly in the shared repository directory
- **NO BRANCH SWITCHING**: Stay on the current branch -- do not checkout, create branches, or switch branches
- **NO PR CREATION**: The swarm leader handles PR creation after all tasks complete
- **QUALITY FIRST**: Do not compromise on code quality for speed
- **CLEAN CODE**: Follow best practices and project conventions
- **MARK TASK COMPLETE**: Always mark your `[WORK]` task as completed when done

## Quality Checklist

Before signaling `implementation_complete`:

- [ ] All validation tests passing
- [ ] Unit tests created for new/modified code
- [ ] All unit tests passing
- [ ] Linting passes with no warnings
- [ ] Type checking passes with no errors
- [ ] No regressions in existing tests
- [ ] Code follows project conventions
- [ ] Docstrings/comments added for complex logic
- [ ] Error handling is appropriate
- [ ] Tracker file updated
- [ ] All issue requirements implemented
- [ ] Every modified file is within file ownership boundaries
- [ ] All blocker resolved messages sent for tasks that depend on this one
- [ ] All integration request messages sent for shared file changes needed
- [ ] Final commit created with issue number reference
- [ ] Working notes file (`working-notes-<task_id>.md`) kept up to date throughout execution
- [ ] `[WORK]` task marked as completed
- [ ] Implementation complete message sent as the LAST action

## Error Handling

If validation tests do not pass after implementation:
- Analyze the test failure carefully
- Review the test's expected behavior
- Check implementation against requirements
- Debug and fix the issue
- Re-run tests
- Do not proceed until all validation tests pass

If you discover a validation test does not make sense or has issues:
- Create a `[QUESTION]` task for the leader explaining the problem
- Wait for the leader's guidance before modifying any test
- Document any test modifications in the commit message

If you need a file outside your ownership:
- Create a `[BLOCKER]` task for the leader
- STOP work on that specific task item
- Continue with other implementation tasks that do not require the external file
- Resume when the leader responds with authorization or an alternative approach

If a dependency interface does not match expectations:
- Create a `[BLOCKER]` task for the leader describing the mismatch
- Do NOT modify the dependency file (it belongs to another teammate)
- Wait for the leader to coordinate with the other teammate
