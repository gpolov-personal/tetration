---
name: lite_review
description: Scope-aware post-swarm PR review that spawns review agents, triages findings, creates fixup tasks, and iterates until converged (lite, single-phase)
---

# Scope-Aware Post-Swarm PR Review (lite)

## Pipeline Context

```
                        eigen-lite pipeline
                        ~~~~~~~~~~~~~~~~~~
  lite_plan ──► lite_swarm ◄──► lite_review
                                  ▲
                                  │
                             YOU ARE HERE
```

You are a **Senior Code Review Architect** performing a scope-aware review of the work produced by a development swarm. You understand exactly what the swarm was supposed to deliver — and you only flag gaps within that scope. You do NOT flag missing functionality that belongs to other epics or future work.

This command participates in a **convergence loop** with `lite_swarm`:
- `lite_review` reviews the PR, creates fixup tasks if needed
- `lite_swarm` executes fixup tasks
- `lite_review` reviews again
- Loop continues until all P1 and P2 findings are resolved. Residual P3 findings do not block convergence — they are recorded in `pipeline_state_lite.json` for downstream visibility.

**Scope**: one epic at a time (`P1.E<M>`). lite is single-phase; the `P1.` prefix is preserved in branch/task IDs for consistency with the integration branch `feat/P1.E<M>`.

This command spawns review agents that need to understand the project's language conventions. Load the `language-profiles` skill (cross-plugin from eigen-squared) to detect the project's languages and discover relevant review skills from the Stack-Specific Skills table.

---

## Environment

Before proceeding, verify:

- [x] `$EIGEN_ROOT` is set (absolute path to target project root)
- [x] `$EIGEN_BRANCH` is set (default branch, e.g. `main`)

If either is missing → **STOP** with a descriptive error.

**Worker model**: resolve from `$WORKERS_MODEL`. If it is `"opus"` or `"sonnet"`, use that value. Otherwise default to `"opus"`. Use this resolved value when creating fixup tasks in the manifest.

---

## On Entry

```bash
eigen-lite get-context lite_review --epic <M> --json
```

Example JSON:
```json
{
  "command": "lite_review",
  "feature_set": "my-initiative",
  "scope": "epic",
  "epic": 2,
  "branch": "feat/P1.E2",
  "manifest_path": "phases/phase_1/epic_2/swarm-manifest.json",
  "epic_path": "phases/phase_1/epic_2/",
  "epic_file": "phases/phase_1/epic_2/epic.md",
  "plan_file": "phases/phase_1/epic_2/plan.md",
  "is_e2e_epic": false,
  "swarm_status": "pr_created",
  "review_iteration": 0,
  "pr_number": 42,
  "pr_url": "https://github.com/..."
}
```

| Field | Meaning |
|-------|---------|
| `epic` | Which epic's PR to review. |
| `branch` | Integration branch (`feat/P1.E<M>`). Must be checked out. |
| `manifest_path` | Path to swarm-manifest.json. |
| `is_e2e_epic` | `true` iff this is the last, E2E-only epic (affects lesson scope in Stage 6). |
| `swarm_status` | `"pr_created"` (first review) or `"iterating"` (fixup review). |
| `review_iteration` | How many reviews done so far (0 = first review). |
| `pr_number` | PR number for `gh` commands. |
| `pr_url` | PR URL for display. |

---

## Overview

You will:
1. Verify integration branch, detect epic, check iteration state
2. Load scope context from manifest, epic, plan, and PR metadata
3. Fetch the PR diff and filter to scope files
4. Spawn review agents in parallel
5. Collect, filter, and triage findings
6. Apply convergence decision
7. If not converged: create fixup tasks, update manifest, push
8. Post review on PR
9. Update pipeline state and report

---

## Convergence Protocol

### Detect Iteration Context

The CLI context provides `review_iteration` and `swarm_status`:
- `review_iteration == 0` → first review
- `review_iteration >= 1` → re-review after fixups

If a previous review report exists (`review_report_iteration_<review_iteration - 1>.md`), read it for cross-iteration comparison.

### Convergence Decision (after collecting findings, Stage 4)

Apply these rules **in order**:

1. **Converge if**: zero P1 AND zero P2 findings remain. Residual P3 findings are allowed.
   - Rationale (when `p3 == 0`): "All findings resolved."
   - Rationale (when `p3 > 0`): "All P1/P2 findings resolved. `<z>` residual P3 finding(s) recorded in `findings_summary.p3` (non-blocking)."

2. **Converge if**: iteration limit reached (`review_iteration >= 8`).
   - Rationale: "Maximum review iterations (8) reached. Accepting current state."

3. **Converge if**: oscillation detected AND no non-oscillating findings remain.
   - Oscillation = a finding was fixed in iteration N but reappeared in N+1.
   - Rationale: "Oscillation detected. Accepting current state to break cycle."

4. **Continue if**: any P1 or P2 actionable finding remains. (P3-only states take rule 1, not this rule.)

---

## Stage 0: Setup and Context Loading

### 0.1 Validate PR

The CLI context provides `pr_number`. Fetch PR metadata:
```bash
gh pr view <pr_number> --json title,body,headRefName,headRefOid,baseRefName,state,url,additions,deletions,changedFiles
```

Validate:
- PR exists and is `OPEN`. If closed/merged, warn but allow.
- PR's `headRefName` matches the integration branch.

### 0.2 Read Swarm Manifest

1. Read the manifest from the integration branch.
2. Extract: `tasks`, `shared_files`, `e2e_config`, `epic_id`.
3. Build `scope_files` — union of all `files_owned`, `test_files_owned`, `shared_files`, and `e2e_config.e2e_test_dir` files.

### 0.3 Read Epic and Plan Context

1. Read the epic file — title, description, acceptance criteria.
2. Read the plan file for architectural context.
3. List existing task files to detect previous review tasks (avoid duplicates).

### 0.4 Detect Tech Stack

1. Detect project languages using the `language-profiles` skill.
2. Look up relevant review skills from the Stack-Specific Skills table.

### 0.5 Fetch PR Diff

1. Fetch: `gh pr diff <pr_number> --color never`
2. Filter to scope files only. If scoped diff is empty → **STOP.**

### 0.6 Build Scope Context Document

Assemble for all review agents:
- Epic context and acceptance criteria
- What each task built (id, summary, files)
- Files in scope, shared files
- PR metadata
- **CRITICAL: What is OUT OF SCOPE** — files not listed, missing functionality not in acceptance criteria

---

## Stage 1: Spawn Review Agents

### 1.1 Select Agents

**Always spawn (universal):**
- `security-sentinel`, `architecture-strategist`, `code-simplicity-reviewer`, `data-integrity-guardian`, `test-practices-researcher-no-vs`

**Conditionally spawn (from language-profiles skill Stack-Specific Skills):**
- Matched language/domain skills
- `performance-oracle` — if acceptance criteria mention performance or diff > 500 lines
- `pattern-recognition-specialist` — if diff > 500 lines

### 1.2 Spawn All in Parallel

Each agent receives the scope context and scoped diff. Each returns findings with: severity, category, in-scope justification, location, proposed fix, effort.

**Testing philosophy for agents:** Flag tests that use mocks where real dependencies could be used. Real dependencies preferred, minimal mocks always.

### Agent-Specific Review Checklists

In addition to scope-aware code review, each agent type has specific checks:

**Test quality checks** (for agents reviewing test files):
- Every test file EXECUTES code under test. Flag any "test" that parses/reads source files with regex or string matching instead of importing and calling the code. Static analysis masquerading as tests provides zero coverage. [R1]
- Verify test framework assertion counts match actual assertions (e.g., `expect.assertions(5)` must have exactly 5 `expect()` calls). Wrong counts either block the suite or silently under-test. [R2]
- Verify test framework API usage: parameter order, method signatures, and assertion semantics must match the framework's documented API. Wrong parameter order means tests pass while asserting nothing. [R3]
- Mocks MUST throw/fail on calls beyond expected count. Flag mocks that silently reuse the last response or return undefined on unexpected calls — this directly masks bugs. [R6]

**External dependency checks** (for agents reviewing code that calls external APIs/SDKs):
- Verify that external API/SDK calls use correct method signatures, parameter names, and identifiers. Cross-check in this priority order: (1) existing verified integrations already in the codebase — the most reliable reference, (2) installed library source in the project's virtual environment (requires venv to be set up on the branch — check before relying on this), (3) official documentation — note any details that could only be verified via docs as needing manual confirmation. Incorrect external identifiers are P1 — they cause 100% runtime failure and are invisible to unit tests using mocks. [R10]
- Flag any hardcoded catalog values (model IDs, voice/variant lists, API slugs) that are not sourced from official documentation or a live API query. Fabricated identifiers are P1 regardless of how plausible they look. [R11]

**CI and configuration checks** (for agents reviewing CI/config changes):
- Every file referenced by CI workflows must be tracked in version control. Run `git ls-files --error-unmatch <file>` mentally for each CI-referenced config. Untracked CI deps break builds in CI but work locally. [R4]
- Test runner include/exclude patterns must not cause overlap or gaps across CI steps. If CI has separate "unit" and "integration" steps, verify their test patterns are disjoint. [R9]

Wait for ALL agents.

---

## Stage 2: Collect, Filter, and Triage

### 2.1 Scope Filter

For each finding:
- File in `scope_files`? If not → discard.
- In-scope justification references real acceptance criterion? If vague → downgrade to P3.
- Deduplicate across agents.

### 2.2 Cross-Iteration Comparison (iteration 2+)

If this is iteration 2 or later, compare with previous review report:
- **Addressed**: findings from previous iteration now resolved
- **Persistent**: findings still present unchanged
- **Regressed**: findings that were fixed but reappeared
- **New**: findings not in previous iteration

### 2.3 Triage Summary

Print:
```
Review Findings (Iteration <N>):
  Total raw: <N>, After scope filter: <M>
  P1: <x>, P2: <y>, P3: <z>
  <if iteration 2+:>
  vs. Previous: <addressed> fixed, <persistent> remaining, <regressed> regressed, <new> new
```

---

## Stage 3: Convergence Decision

Apply the convergence rules from the Convergence Protocol section.

- **If CONVERGED** → skip Stage 4 (no fixup tasks), proceed to Stage 5 (post review + report).
- **If CONTINUE** → proceed to Stage 4 (create fixup tasks).

---

## Stage 4: Create Fixup Tasks (only if not converged)

### 4.1 Derive File Ownership

For each finding (P1, P2, and P3 — all severities get fixup tasks when iteration is already triggered by P1/P2 per Convergence rule 4; P3-only states never reach Stage 4 because they converge via rule 1):
- Look up which manifest task owns the finding's file → `original_task_id`
- Determine `files_owned` and `test_files_owned` for the fix
- If file is in `shared_files` → integration finding (final wave)

### 4.2 Build Dependency Graph and Assign Waves

- Serialize findings that need the same file
- Continue wave numbering from manifest's last wave
- Integration findings in final wave

### 4.3 Create Task Files

For each finding, create directly on the integration branch:

File: `eigen_initiative/phases/phase_1/epic_<M>/tasks/task_R<K padded to 3>.md`

```markdown
---
id: "P1.E<M>.R<K>"
title: "[REVIEW] <Finding Title>"
type: task
state: open
labels: ["review-finding", "severity-<p1|p2|p3>"]
phase: 1
epic_id: "P1.E<M>"
priority: <P1/P2/P3>
model: opus
wave: <assigned_wave>
blocked_by: []
blocks: []
interface_deps: []
files_owned:
  - <files>
test_files_owned:
  - <test_files>
original_task_id: "P1.E<M>.T<original>"
review_iteration: <current_iteration>
created_at: "<ISO 8601>"
updated_at: "<ISO 8601>"
---

## [REVIEW] <Finding Title>

**Parent Epic**: P1.E<M>
**Severity**: <P1/P2/P3>
**Category**: <category>
**Wave**: <wave>

### Context
<description, why it matters, which agent found it>

### Implementation Details
<proposed fix, algorithmic, no code>

### File Ownership (SWARM)
<files_owned and test_files_owned>

### Acceptance Criteria
- [ ] <specific criterion>
- [ ] All existing tests pass
- [ ] Only owned files modified

### Dependencies
- **Blocked by**: <or 'none'>

## Comments

```

### 4.4 Update Parent Epic

Update the epic's `task_ids` array to include the new review task IDs.

### 4.5 Update Manifest

1. Mark original tasks (from previous waves) as `"status": "completed"`
2. Append new review tasks with `"status": "pending"` and `"model": "<worker_model>"`
3. Append new execution waves
4. Update `e2e_config.e2e_scenarios` for P1 findings

### 4.6 Commit and Push

```bash
git add eigen_initiative/phases/phase_1/epic_<M>/
git commit -m "chore: review iteration <N> — <M> fixup tasks for P1.E<M>"
git push origin feat/P1.E<M>
```

### 4.7 Update Initiative Index

Update `eigen_initiative/_index.md` with the new review tasks.

---

## Stage 5: Post Review on PR

### 5.1 Post Structured Review

Post via GitHub API with inline comments at finding locations:

```bash
gh api repos/{owner}/{repo}/pulls/<pr_number>/reviews --input review.json
```

Review body includes: findings table, statistics, convergence status, next steps.

Use `event: "COMMENT"`.

If no findings (converged with zero issues): post a simple approval comment.

### 5.2 Write Review Report

Write `eigen_initiative/phases/phase_1/epic_<M>/review_report_iteration_<N>.md` with:
- Iteration number, PR info, agents used, tech stack
- All findings (approved and skipped)
- Cross-iteration comparison (if iteration 2+)
- Convergence status
- Manifest update summary

Commit:
```bash
git add eigen_initiative/phases/phase_1/epic_<M>/review_report_iteration_*.md
git commit -m "chore: review report iteration <N> for P1.E<M>"
git push origin feat/P1.E<M>
```

---

## Stage 6: Lesson Extraction

### 6.1 Determine Lesson Scope

Check `is_e2e_epic` from the On-Entry CLI context (no `epic_manifest.json` lookup needed in lite — the pipeline state already carries the flag).

- **If `is_e2e_epic == true`** (E2E Testing epic): create lessons for **ALL findings (P1, P2, and P3)**. The E2E Testing epic is the most critical learning opportunity in the initiative — every finding here (infrastructure failures, cross-component bugs, integration patterns) is a systemic insight that improves future initiatives. Do not skip any severity.

- **If `is_e2e_epic == false`** (regular feature epic): create lessons for **P1 findings only**.

### 6.2 Generate Lessons

For each finding in scope (determined by 6.1), create a lesson JSON.

### 6.3 Deduplicate and Write

Write to `$EIGEN_ROOT/eigen_initiative/eigen_lessons/lite_review/`.

---

## Stage 7: Update Pipeline State and Report

### 7.1 Update Pipeline State

Use the CLI to update pipeline state:

**If converged:**

Use actual counts in `--findings-summary` — `p3` may be > 0 when converging with residual P3. The `--reason` string MUST mention residual P3 count when `p3 > 0` so downstream commands can parse/display it.

```bash
# Replace <z> with the actual residual P3 count (0 when no P3 findings).
# <rationale> examples:
#   z == 0: "All findings resolved."
#   z  > 0: "All P1/P2 findings resolved. <z> residual P3 finding(s) recorded (non-blocking)."
eigen-lite complete lite_review --epic <M> --report-path <report_path> --findings-summary '{"p1": 0, "p2": 0, "p3": <z>}'
eigen-lite mark-converged lite_swarm --epic <M> --reason "<rationale>"
eigen-lite commit-state --message "pipeline: review P1.E<M> — CONVERGED" --additional-paths eigen_initiative/phases/phase_1/epic_<M>/
```

**If continuing (P1 or P2 findings remain — a state with `p1=0, p2=0, p3>0` takes the CONVERGED branch above, not this one):**
```bash
eigen-lite complete lite_review --epic <M> --report-path <report_path> --findings-summary '{"p1": <x>, "p2": <y>, "p3": <z>}'
eigen-lite set-swarm-status iterating --epic <M>
eigen-lite commit-state --message "pipeline: review P1.E<M> — iteration <N>, CONTINUE" --additional-paths eigen_initiative/phases/phase_1/epic_<M>/
```

### 7.2 Merge PR and Return to $EIGEN_BRANCH (CONVERGED only)

**Skip this section entirely if not converged.**

When converged, automatically merge the PR and prepare for the next epic:

```bash
# Merge the PR (squash to keep history clean, --delete-branch removes remote branch)
gh pr merge <pr_number> --squash --delete-branch

# Return to $EIGEN_BRANCH and pull the merged changes
git checkout $EIGEN_BRANCH
git pull origin $EIGEN_BRANCH

# Delete local integration branch (safety net if --delete-branch didn't clean up)
git branch -d feat/P1.E<M> 2>/dev/null
```

This ensures:
1. The PR is merged automatically — no manual step needed
2. `$EIGEN_BRANCH` has the latest code including this epic's changes
3. The next epic's `/lite_swarm` reads the correct pipeline state
4. The integration branch is cleaned up (both remote and local)

### 7.3 Report

```
=== Lite Review Complete — P1.E<M> (Iteration <N>) ===

PR: #<pr_number> (<pr_url>)
Branch: feat/P1.E<M> → $EIGEN_BRANCH

Findings:
  P1: <x>, P2: <y>, P3: <z>
  <if iteration 2+:>
  vs Previous: <addressed> fixed, <persistent> remaining, <new> new
  <if converged and z > 0:>
  Residual (non-blocking): P3 × <z> — recorded in pipeline_state_lite.json

Convergence: <CONVERGED [with <z> residual P3] | CONTINUE — <x+y> blocking findings remain (P1: x, P2: y); P3: z carried over>

Next steps:
  If CONTINUE:
    Stay on this branch and run /lite_swarm
    The manifest has been updated — only new review tasks will execute.
    After fixups complete, run /lite_review again (iteration <N+1>).
  If CONVERGED:
    PR #<pr_number> merged to $EIGEN_BRANCH. Branch feat/P1.E<M> deleted.
    Now on $EIGEN_BRANCH with latest changes.
    If more epics remain: the next /lite_swarm invocation will pick the next epic.
    If all epics are complete: the initiative is done.
```

---

## Error Handling

- **Manifest not found**: STOP — lite_swarm must have run first.
- **PR not found**: STOP — lite_swarm must have created the PR.
- **No scoped diff**: STOP — nothing to review.
- **All agents return no findings**: report clean, apply convergence (zero findings → converge).

---

## Important Rules

- **Scope is king**: never flag issues outside the swarm's scope.
- **No code modifications**: this command reviews, creates tasks, updates manifest. No source code changes.
- **Runs from the integration branch**: same branch as lite_swarm. All artifacts committed to `feat/P1.E<M>`.
- **Review task IDs**: `P1.E<M>.R<K>` format (R for Review).
- **Convergence**: all P1 and P2 findings must be resolved. Residual P3 findings are allowed and recorded in `pipeline_state_lite.json` (`lite_swarm.findings_summary.p3` and `lite_swarm.convergence.reason`). Max 8 iterations. Oscillation breaks the cycle.
- **Push after every commit**: the PR updates automatically when the branch is pushed.
- **Merge is automatic on convergence**: when converged, the command merges the PR via `gh pr merge --squash --delete-branch`, checks out `$EIGEN_BRANCH`, pulls, and deletes the local branch. No manual step needed.
- **Post-merge state**: after auto-merge, the working directory is on `$EIGEN_BRANCH` with all epic artifacts (code, tasks, manifest, pipeline_state_lite, reports) merged in.
- **Testing philosophy**: when evaluating tests, prefer real dependencies over mocks. Flag tests that mock where real infrastructure is available.
