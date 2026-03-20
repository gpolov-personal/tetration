---
name: e2e_validation_swarm
description: "Write and run end-to-end tests that validate the assembled feature across component boundaries"
argument-hint: <parent_issue_number>
---

# E2E Validation — Swarm Teammate Version

## Language Adaptation

These instructions use Python as the concrete example language. When working on a non-Python project:

1. **Detect the project language** from its manifest files (use the `language-profiles` skill in the eigen plugin)
2. **Resolve toolchain commands** using the Language Profiles (test runner, E2E runner, etc.)
3. **Adapt structural patterns** using the Language Adaptation Notes (E2E test directory, markers, framework detection)

All Python-specific examples below (pytest commands, import syntax) should be adapted to the detected language's equivalent.

---

## Introduction

This command is the E2E validation phase of the swarm. It runs as the **`e2e-tester` teammate**, invoked by workers within the E2E Testing epic. The E2E tester both **writes** new E2E tests based on acceptance criteria and **runs** them to validate the assembled feature.

The E2E tester may be spawned multiple times across fix loop iterations. On iteration 1, it writes and runs tests. On iterations 2+, it only re-runs existing tests to verify fixes.

This command receives its epic ID via the orchestrator's spawn prompt (passed as `#$ARGUMENTS`).

<parent_issue_number>
#$ARGUMENTS
</parent_issue_number>

### Critical Learning Opportunity

This command runs within the **E2E Testing epic** — the most critical learning opportunity in each phase. Every finding here (infrastructure failures, cross-component bugs, integration patterns) should be documented thoroughly in your working notes because it feeds into the lesson system for improving future phases. All findings from this epic's review (P1, P2, and P3) are captured as lessons — unlike feature epics where only P1 findings become lessons. Be detailed about WHY things fail, not just WHAT fails.

### Testing Philosophy — NON-NEGOTIABLE

This applies to ALL E2E tests written by this command:

- Test with REAL dependencies ALWAYS — real database connections, real HTTP calls, real file systems
- NEVER use SQLite as a substitute for PostgreSQL
- NEVER use in-memory fakes for Redis, S3, queues, or any service
- NEVER monkeypatch or mock database/cache/queue connections
- If infrastructure is needed and not running, report as `[BLOCKER]` to team-lead — do NOT substitute with mocks
- The ONLY acceptable mocks are for TRUE external third-party services (payment gateways, external APIs not under your control)

## Prerequisites

- `swarm-manifest.json` in the worktree with `e2e_config` section
- All `[WORK]` tasks in the current epic completed
- Integration phase completed (if applicable)
- Full test suite passing (verified by the leader after integration)
- Iteration number and mode received from the leader's spawn prompt

## CRITICAL: Swarm Constraints

<thinking>
I am the e2e-tester teammate. I own ONLY the E2E test directory. I MUST NOT modify any source file or any test file outside my E2E test directory. I communicate with the leader, not with other workers.
</thinking>

### No Source File Modifications

This teammate MUST NOT modify any source file. If a production code bug is found, report it to the leader — do not fix it.

### File Ownership

- You own ONLY files in `<e2e_config.e2e_test_dir>`
- You MUST NOT modify any file outside this directory
- You MUST NOT modify existing worker test files
- If you need to create shared test infrastructure (e.g., conftest.py), it MUST be inside `<e2e_config.e2e_test_dir>`

### Communication Protocol

<thinking>
I must communicate every significant event to the leader. The leader cannot help me or coordinate fixes if I stay silent.
</thinking>

Communication uses two mechanisms:

1. **SendMessage** — for progress updates and structured results
2. **TaskCreate + TaskUpdate** — for questions and blockers that need leader decisions

The leader's name is `team-lead`.

#### Sending a Progress Update

```javascript
SendMessage({
  to: "team-lead",
  type: "message",
  content: "Progress on E2E validation: <status>. <details>",
  summary: "E2E progress: <brief status>"
})
```

#### Asking the Leader a Question

```javascript
TaskCreate({
  subject: "[QUESTION] E2E: <brief description>",
  description: "E2E iteration: <iteration>\nContext: <detailed context>\n\nOptions:\n1. <option A>\n2. <option B>\n\nMy recommendation: <preferred option>",
  activeForm: "Waiting for leader decision"
})
TaskUpdate({ taskId: "<new_task_id>", owner: "team-lead" })

SendMessage({
  to: "team-lead",
  type: "message",
  content: "I need a decision on <brief>. See task <new_task_id> for details.",
  summary: "Question pending: <brief>"
})
```

#### Reporting a Blocker

```javascript
TaskCreate({
  subject: "[BLOCKER] E2E: <brief description>",
  description: "E2E iteration: <iteration>\nBlocker: <what is blocked and why>",
  activeForm: "Blocked: waiting for leader"
})
TaskUpdate({ taskId: "<new_task_id>", owner: "team-lead" })

SendMessage({
  to: "team-lead",
  type: "message",
  content: "I'm blocked on <brief>. See task <new_task_id>. Waiting for response.",
  summary: "BLOCKED: <brief>"
})
```

After sending a blocker, **STOP and WAIT** for the leader's response.

#### Sending Structured E2E Results

```javascript
SendMessage({
  to: "team-lead",
  type: "message",
  content: "E2E results for iteration <iteration>:\n- Test connection method: <real_http|test_client_real_services|no_infrastructure_needed>\n- Services used: [<list with ports>]\n- Total: <total>, Passed: <passed>, Failed: <failed>\n- Flaky (passed on retry): <flaky_count>\n- Infrastructure failures: <infra_count>\n- Code bugs: <code_bug_count>\n- Test issues (unfixable): <test_issue_count>\n- Infrastructure status: <healthy|degraded|down>\n- Failures:\n  - test_name: <name>, error_type: <type>, error: <msg>, stack_files: [<files>], category: <FLAKY|INFRASTRUCTURE|CODE_BUG|TEST_ISSUE>\n  ...\n- New tests written: <count>\n- Test files: [<list>]",
  summary: "E2E iteration <N>: <passed>/<total> passed, <failed> failed"
})
```

#### Sending Completion Signal

```javascript
SendMessage({
  to: "team-lead",
  type: "message",
  content: "E2E validation complete for iteration <iteration>. All tests: <passing/failing>. Commit: <hash>. [E2E-RESULT] task: <task_id>.",
  summary: "E2E complete: iteration <N> — <result>"
})
```

## Working Notes (Compaction Resilience)

Maintain working notes at `swarm_working_notes/working-notes-e2e-<parent_issue_number>.md`.

### Initialize Working Notes

At the start, check if working notes exist:

- **If they exist**: Read the `## Iteration:` field and compare with the iteration number from your spawn prompt:
  - **Same iteration** → compaction recovery. Read `Last Checkpoint` and `Next Step`, resume from there.
  - **Different iteration** → new iteration. Clear the notes and start fresh (the previous iteration's results are persisted in `[E2E-RESULT]` tasks).
- **If they do not exist**: Create them with the initial template.

```markdown
# Working Notes — E2E Validation #<parent_issue_number>
## Phase: e2e_validation
## Iteration: <iteration_number>
## Mode: <write_and_run | run_only>

## Context
- Parent issue: #<parent_issue_number>
- E2E test dir: <e2e_test_dir>
- E2E command: <e2e_test_command>
- Scenarios: <count>

## Detected Tech Stack
- Language: <detected_language>
- Framework: <detected_framework>

## Loaded Skills
- <skill_name>: <skill_path> (loaded, <N> lines)

## Progress
- [ ] Context loaded
- [ ] Existing E2E tests discovered
- [ ] E2E tests designed (iteration 1 only)
- [ ] E2E tests executed
- [ ] Results reported
- [ ] Committed
```

### Mandatory Checkpoints

| # | Checkpoint | When | What to persist |
|---|-----------|------|-----------------|
| 1 | `post-context-load` | After reading manifest, plan, acceptance criteria | e2e_config summary, parent_issue_number, existing E2E tests found, iteration number, mode, detected tech stack, loaded skills |
| 1.5 | `post-infra-verify` | After verifying infrastructure availability | Services running, services unavailable, connection method |
| 2 | `post-test-design` | After writing E2E tests (iteration 1 only) | Test files created (paths), scenarios covered vs not covered, test names |
| 3 | `post-test-run` | After running tests and capturing results | Full parsed results: total, passed, failed, flaky; per-failure details; iteration number |
| 4 | `post-report` | After sending report and committing | Commit hash, report sent confirmation, [E2E-RESULT] task ID |

**Checkpoint format:**

```markdown
## Last Checkpoint: <checkpoint_name>

## Next Step
If resuming: <specific instruction>
```

---

## Main Workflow

### Phase 0: Determine Mode

Read the `MODE` and `ITERATION` from your spawn prompt:

- **`MODE: write_and_run`** (iteration 1): Proceed through all phases (1→1.5→2→3→4→5)
- **`MODE: run_only`** (iteration 2+): Skip Phase 2, go 1→1.5→3→4→5

### Phase 1: Load Context

1. Read `swarm-manifest.json` from the repository root
2. Extract `e2e_config` — store test dir, command, marker, output format, file pattern, scenarios
3. Read the parent epic from local files. Locate it by either:
      - Scanning `phases/phase_*/epic_*/epic.md` for a YAML frontmatter `id` matching `<parent_issue_number>`, OR
      - Deriving the path from the manifest's `plan_file` field
4. Extract acceptance criteria from the epic body
5. Read the plan from the manifest's `plan_file` field (e.g., `phases/phase_<N>/epic_<M>/plan.md`)
6. Read task summaries from the manifest to understand what was built
7. Discover existing E2E tests in `<e2e_test_dir>`:
   - List all files matching `<e2e_file_pattern>` in `<e2e_test_dir>`
   - If files exist, catalog their test functions/names
   - Store as `<existing_e2e_tests>`

8. **Discover Available Infrastructure**

   Scan the project for infrastructure that other tasks in the E2E Testing epic should have set up:

   a. Check for `docker-compose.yml` or similar orchestration files
   b. Check for running services (database, cache, queue, app servers) by attempting health checks
   c. Check for `conftest.py` in the repository root and in common test directories:
      - Look for testcontainer imports (`testcontainers`, `testcontainers-python`, `@testcontainers`)
      - Look for in-process client fixtures (`TestClient`, `Client`, `WebApplicationFactory`)
      - Store findings as `<existing_fixtures>` with: type (testcontainer/test_client), services covered, file path

   d. This information is used in Phase 1.5 to verify infrastructure readiness.

9. **Discover E2E-Relevant Skills**

   Read `<detected_tech_stack>` and `<relevant_skills>` from:
   1. Your spawn prompt context above (normal flow)
   2. Your working notes `## Detected Tech Stack` and `## Loaded Skills` sections
      (if spawn prompt was compacted — resume flow)
   3. If neither is present: standalone fallback below

   If `<relevant_skills>` is present:

   a. Check if `agent-browser` is in `<relevant_skills>`:
      - If the E2E scenarios involve browser interaction (web UI, forms, navigation),
        load the `agent-browser` skill and use its Vercel agent-browser CLI commands
        as part of your E2E test execution toolset in Phase 3.
      - This is especially valuable when scenarios describe user interactions
        (clicks, form submissions, page navigation).

   b. Check for stack-specific testing skills in `<relevant_skills>`:
      - Load at most 1 testing skill.
      - Total skill content (agent-browser + testing skill) should stay within
        ~300 lines max, same cap as implementation workers.

   If `<relevant_skills>` is NOT present (standalone execution):
   - Load the `language-profiles` skill (sibling of the `commands/` directory in this plugin)
     and read the "Stack-Specific Skills" section
   - Check if `agent-browser` appears in the "By Domain" table and if your
     scenarios match browser interaction patterns

   **Checkpoint update (compaction resilience)**: Add to working notes:
   - `## Detected Tech Stack` with `<detected_language>` and `<detected_framework>`
   - `## Loaded Skills` with skill names, paths, and line counts loaded
   This ensures skill info survives context compaction.

**Checkpoint: post-context-load**

```markdown
## Last Checkpoint: post-context-load

## Next Step
If resuming (MODE write_and_run): Read scenarios below, proceed to Phase 2 test design.
If resuming (MODE run_only): Read existing tests below, proceed to Phase 3 test execution.

## Existing E2E Tests
- <file1>: <test_count> tests (<test_names>)
- <file2>: <test_count> tests (<test_names>)
(or "none found")
```

Send progress update:
```javascript
SendMessage({
  to: "team-lead",
  type: "message",
  content: "E2E context loaded. Iteration: <N>. Mode: <mode>. Found <count> existing E2E tests. Scenarios to cover: <count>.",
  summary: "E2E started: iteration <N>, <count> scenarios"
})
```

### Phase 1.5: Infrastructure Verification (MANDATORY)

<thinking>
E2E tests MUST run against real infrastructure. In the new model, infrastructure (docker-compose, emulators, etc.) is created by other worker tasks in the E2E Testing epic. My job is to VERIFY it is running, not to set it up. If infrastructure is missing, I report a blocker — I do NOT substitute with mocks or fakes.
</thinking>

Refer to the **Testing Philosophy** at the top of this command — it is non-negotiable during infrastructure verification.

#### Step 1: Check Infrastructure Availability

Verify that infrastructure set up by other tasks in the E2E Testing epic is running:

1. Check for running Docker containers (`docker ps`, `docker-compose ps`)
2. Attempt health checks on expected services (database, cache, queue, app server)
3. Check connectivity to expected ports

#### Step 2: Classify Infrastructure Tier

Based on what is available, classify into one of three tiers:

- **Tier 1 — Full Stack** (preferred): App server + all backing services are running and healthy.
  - Tests MUST use real HTTP/network requests to the running server (e.g., `http://localhost:<port>`)
  - Do NOT use in-process test clients, test app factories, or embedded servers
  - The test exercises the REAL deployed application, including routing, middleware, and serialization
  - See "E2E Test Type Tooling" → `test_type: api` in the `language-profiles` skill for language-specific HTTP clients

- **Tier 2 — Infrastructure Only** (fallback): Some services running (e.g., DB, cache) but app server not available.
  - In-process test clients are acceptable, BUT they MUST connect to the REAL running services (real database, real cache, real queue)
  - NEVER substitute with SQLite, in-memory fakes, or mocked connections
  - The test verifies business logic against real data stores, even if the HTTP layer is in-process

- **Tier 3 — No Infrastructure**: Nothing is running.
  - Report as `[BLOCKER]` — infrastructure should have been set up by other tasks in the E2E Testing epic
  - Do NOT fall back to mocks or fakes. Wait for infrastructure to be available.

- **NEVER acceptable** (regardless of tier): Pure mocks, SQLite as PostgreSQL substitute, in-memory fakes for Redis/S3/queues, monkeypatched connections, tests passing without ANY real service running.

#### Step 3: Request Tier Approval from Leader (MANDATORY)

Send a tier proposal to team-lead and **WAIT** for approval:

```javascript
SendMessage({
  to: "team-lead",
  type: "message",
  content: "E2E Infrastructure Tier Proposal:\n- Proposed tier: <1_full_stack|2_infra_only|3_no_infrastructure>\n- Reason: <why this tier — what succeeded, what failed>\n- Services available: <list with ports>\n- Services unavailable: <list>\n- Existing fixtures found: <list from Phase 1 discovery, or 'none'>\n- Proposed test connection method: <real_http|test_client_real_services|no_infrastructure_needed>\n\nWaiting for approval or override.",
  summary: "E2E tier proposal: Tier <N>"
})
```

**STOP and WAIT** for the leader's response. The leader may:
- **Approve** the proposed tier → proceed with that connection method
- **Override** to a higher tier with fix instructions (e.g., "Use Tier 1 — the app service error is a missing env var, set X=Y and retry")
- **Reject** and investigate further before approving

#### Step 4: Handle Missing Infrastructure (Tier 3)

**If classified as Tier 3 (no infrastructure) AND leader does not provide a fix:**

Report a `[BLOCKER]` to team-lead:

```javascript
TaskCreate({
  subject: "[BLOCKER] E2E: Required infrastructure not running",
  description: "E2E iteration: <iteration>\nBlocker: Infrastructure expected from other E2E Testing epic tasks is not available.\n- Expected services: <list based on project config>\n- Actually running: <list or 'none'>\n- Health check results: <details>\n\nThe e2e-tester does not set up infrastructure — this is the responsibility of other tasks in the epic.",
  activeForm: "Blocked: waiting for infrastructure"
})
TaskUpdate({ taskId: "<new_task_id>", owner: "team-lead" })

SendMessage({
  to: "team-lead",
  type: "message",
  content: "I'm blocked: required infrastructure is not running. See task <new_task_id>. Other tasks in the E2E Testing epic should set up infrastructure before the e2e-tester runs.",
  summary: "BLOCKED: infrastructure not running"
})
```

**STOP and WAIT** for the leader's response. The leader may:
- Direct other workers to set up infrastructure first
- Confirm that no infrastructure is needed for the current scenarios
- Provide alternative instructions

**If no infrastructure is needed** (e.g., pure CLI tool, no external services):
- Proceed without infrastructure
- Note in working notes that tests run without external services

#### Step 5: Persist Infrastructure State

Update working notes:
```markdown
## Infrastructure
- Approved tier: <1|2|3>
- Tier reason: <reason>
- Leader approval: confirmed
- Status: <running|partial|none>
- Services running: <list with ports>
- Services unavailable: <list, or 'none'>
- Test connection method: <real_http|test_client_real_services|no_infrastructure_needed>
```

---

### Phase 2: Design E2E Tests (MODE: write_and_run ONLY)

**Skip this phase entirely if MODE is `run_only`.**

<thinking>
I must write meaningful E2E tests that validate real user flows. Each test should exercise the full feature across component boundaries, connecting to REAL running services verified in Phase 1.5. If this test were deleted, would we risk a real user-facing bug going undetected?
</thinking>

1. **Create E2E test directory** if it does not exist:
   ```bash
   mkdir -p <e2e_test_dir>
   ```

2. **For each scenario in `e2e_config.e2e_scenarios`:**

   a. Check if `<existing_e2e_tests>` already covers this scenario. If covered → skip.

   b. If not covered, write a new E2E test:
      - Place in `<e2e_test_dir>` following `<e2e_file_pattern>`
      - Apply `<e2e_marker>` (e.g., `@pytest.mark.e2e` for Python)
      - Test should exercise the FULL user flow described in the scenario
      - Connect to the REAL running services verified in Phase 1.5:
        - If full stack is available: make real HTTP requests (`httpx`, `requests`, `fetch`) to `http://localhost:<port>`
        - If only backing services are available: in-process test client is acceptable, BUT it MUST connect to the REAL running DB/cache/queue — NEVER use SQLite or in-memory substitutes
        - If no infrastructure is available: structure tests to validate what is possible, and note limitations
      - For browser tests: use Playwright or `agent-browser` skill against the running frontend
      - For pipeline tests: inject real data into the source (S3, queue, file) and poll the output store
      - The ONLY acceptable mocks are for TRUE external third-party services (payment gateways,
        external APIs not under your control). If the service is running in Docker, it is NOT external — use the real service
      - **Create E2E-specific conftest.py** inside `<e2e_test_dir>`, NOT in project root.
        Do NOT reuse root conftest.py fixtures (they may use mocks or different service URLs)

   c. **Test Quality Gate**: "If this E2E test were deleted, would we risk a real user-facing bug going undetected?" If no → don't write it.

3. **Check acceptance criteria** from the parent issue for any flows not captured in scenarios. Write additional E2E tests for uncovered acceptance criteria.

4. **Verify all E2E tests can be collected** (Python: `python -m pytest tests/e2e/ --collect-only`; adapt per language profile). If collection fails, fix syntax/import issues.

**Checkpoint: post-test-design**

```markdown
## Last Checkpoint: post-test-design

## Next Step
If resuming: Tests are written. Proceed to Phase 3 (run tests). Test files: <list>.

## Tests Designed
- <file>: <test_name> — covers scenario <scenario_name>
- <file>: <test_name> — covers acceptance criterion <AC-ref>
```

Send progress update:
```javascript
SendMessage({
  to: "team-lead",
  type: "message",
  content: "E2E tests designed. Created <N> new tests in <M> files. Scenarios covered: <list>. Proceeding to run.",
  summary: "E2E tests designed: <N> tests"
})
```

### Phase 3: Run E2E Tests

1. **Verify infrastructure is still running** (verified in Phase 1.5):
   - If infrastructure went down (connection errors, service not responding): report `[BLOCKER]` to team-lead — do NOT attempt to restart infrastructure yourself
   - If infrastructure was never verified (Phase 1.5 was skipped): STOP — go back and run Phase 1.5

2. **Execute E2E test suite**:
   ```bash
   <e2e_test_command>
   # e.g., python -m pytest tests/e2e/ -v --junitxml=e2e-report.xml
   ```

3. **Capture and parse results**:
   - Total tests, passed, failed
   - For each failure, extract: `test_name`, `error_type`, `error_message`, `stack_trace`, `files_in_stack`

4. **Failure classification** (MANDATORY):

   **Step 1 — Flaky detection:**
   For each failing test, re-run it individually up to 2 additional times:
   ```bash
   # e.g., python -m pytest tests/e2e/test_e2e_login.py::test_full_login_flow -v
   ```
   - If it passes on ANY retry → classify as `FLAKY`
   - If it fails on ALL retries → proceed to Step 2

   **Step 2 — Failure type classification** (for non-flaky failures):
   Analyze the error message and stack trace to classify each failure:

   - `INFRASTRUCTURE`: Connection refused, timeout, service unavailable, DNS resolution
     failed, "connection reset by peer", socket errors, health check failures, "could not
     connect to server", database connection pool exhausted.
     → The infrastructure is down or misconfigured. NOT a code bug.

   - `CODE_BUG`: Assertion failures (expected vs actual mismatch), wrong HTTP status codes,
     missing data in responses, incorrect data transformations, business logic errors,
     wrong field values, missing fields in API responses.
     → Real bug in the application code. Fix workers should be assigned.

   - `TEST_ISSUE`: Import errors in the test file itself, fixture setup failures within the
     test code, invalid test configuration, test referencing non-existent endpoints or fields,
     test using wrong URL or port.
     → The E2E test itself is wrong. Self-fix before reporting to team-lead.

   **Step 3 — Self-fix TEST_ISSUE failures:**
   For each `TEST_ISSUE` failure: fix the test code (you own the E2E test files), re-run
   the individual test, and re-classify. Only report to team-lead if you cannot self-fix.

5. **Categorize results**:
   - `FLAKY` tests: intermittent failures (reported but NOT assigned to fix workers)
   - `INFRASTRUCTURE` failures: infra problems (reported with service details, NOT assigned to fix workers)
   - `CODE_BUG` failures: real bugs that need fixing (assigned to fix workers by team-lead)
   - `TEST_ISSUE` failures: test defects that could not be self-fixed (reported for awareness)

**Checkpoint: post-test-run**

```markdown
## Last Checkpoint: post-test-run

## Next Step
If resuming: Results parsed. Proceed to Phase 4 (report results).

## Test Results
- Total: <N>
- Passed: <P>
- Failed (deterministic): <F>
- Flaky: <K>
- Failures:
  - <test_name>: <error_type> — <brief error> — files: [<stack_files>] — category: DETERMINISTIC
  - <test_name>: <error_type> — <brief error> — category: FLAKY
```

### Phase 4: Report Results

1. **Create `[E2E-RESULT]` task** (persists results for leader's state reconstruction):

   ```javascript
   TaskCreate({
     subject: "[E2E-RESULT] Iteration <iteration> — <passed>/<total> passed",
     description: "Iteration: <iteration>\nApproved tier: <1|2|3>\nTest connection method: <real_http|test_client_real_services|no_infrastructure_needed>\nServices: <list>\nTotal: <total>\nPassed: <passed>\nFailed: <failed>\nFlaky: <flaky_count>\nInfrastructure failures: <infra_count>\nCode bugs: <code_bug_count>\nTest issues: <test_issue_count>\nFailures:\n- <test_name> | <error_type> | <stack_files comma-separated> | <FLAKY|INFRASTRUCTURE|CODE_BUG|TEST_ISSUE>\n- ...\nInfrastructure status: <healthy|degraded|down>",
     activeForm: "E2E results recorded"
   })
   // Immediately mark completed — it is a fact record
   TaskUpdate({ taskId: "<new_task_id>", status: "completed" })
   ```

   **IMPORTANT**: Use prefix `[E2E-RESULT]`, NOT `[E2E-RUN]`. The leader's state reconstruction scans for `[E2E-RESULT]` tasks.

2. **Send structured results to team-lead** using the "Sending Structured E2E Results" format defined above.

3. **Commit E2E test files** (only on iteration 1, or if new tests were written):

   ```bash
   git add <e2e_test_dir files>
   git commit -m "test(#<parent_issue_number>): E2E validation tests — iteration <iteration>"
   ```

   **NEVER** use `git add .` or `git add -A`.

   **IMPORTANT**: Include the approved tier in the results. The leader will verify tier compliance by reading one of your test files to check that the connection method matches the approved tier:
   - Tier 1: should see `httpx`, `requests`, `fetch`, or real URL like `http://localhost:`
   - Tier 2: should see `TestClient` with real DB URL (NOT `sqlite://` or `:memory:`)
   - If your test code contradicts the reported tier, the leader will reject results and re-spawn you with corrections.

**Checkpoint: post-report**

```markdown
## Last Checkpoint: post-report

## Next Step
If resuming: Report already sent. Proceed to Phase 5 (Signal Completion).

## Report Details
- [E2E-RESULT] task ID: <task_id>
- Commit hash: <hash> (or "no new files committed" for run_only)
```

### Phase 5: Signal Completion

1. **Do NOT mark `[E2E-VALIDATION]` task** — the leader manages this task's lifecycle.

2. **Send completion signal** using the format defined above.

---

## Important Notes

### General Principles
- **NO SOURCE CODE MODIFICATIONS**: This command only writes and runs E2E tests
- **FILE OWNERSHIP IS LAW**: Only files in `<e2e_test_dir>` may be created or modified
- **COMMUNICATE CONSTANTLY**: Every phase transition must be communicated to the leader
- **LEADER AS STAFF ENGINEER**: The leader has full context — trust its decisions

### Test Quality Principle
- **Meaningful tests only**: Each E2E test must validate a real user flow
- **No tautological tests**: Don't test that the framework works
- **Cross-component focus**: E2E tests should exercise multiple components working together
- **Acceptance criteria driven**: Every test should trace back to an acceptance criterion

### What NOT to Do
- Do NOT modify source files
- Do NOT modify worker test files
- Do NOT create branches or worktrees
- Do NOT push to remote
- Do NOT create pull requests
- Do NOT run `git add .` or `git add -A`
- Do NOT mark the `[E2E-VALIDATION]` task (the leader does this)
- Do NOT write tests outside `<e2e_test_dir>`

## Quality Checklist

### Swarm Constraints
- [ ] Read `swarm-manifest.json` and extracted `e2e_config`
- [ ] All created/modified files are within `<e2e_test_dir>`
- [ ] No source files were touched
- [ ] No worker test files were touched
- [ ] All communication via SendMessage and TaskCreate
- [ ] Working notes file kept up to date throughout execution

### Test Quality
- [ ] MODE correctly determined (write_and_run vs run_only)
- [ ] All scenarios from `e2e_scenarios` have corresponding tests (iteration 1)
- [ ] Acceptance criteria from parent issue checked for additional flows
- [ ] Test Quality Gate applied to every test
- [ ] Flaky test detection executed for all failures
- [ ] E2E marker applied to all tests

### Results and Handoff
- [ ] `[E2E-RESULT]` task created with correct prefix and structured description
- [ ] Structured results sent to team-lead
- [ ] E2E test files committed (iteration 1)
- [ ] Completion signal sent
