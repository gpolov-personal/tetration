---
name: review_swarm_pr
description: Scope-aware post-swarm PR review that spawns review agents, triages findings, creates fixup tasks, and iterates until converged
---

# Scope-Aware Post-Swarm PR Review

## Language Adaptation

This command spawns review agents that need to understand the project's language conventions. Load the `language-profiles` skill to detect the project's languages and discover relevant review skills from the Stack-Specific Skills table.

---

## Your Role

You are a **Senior Code Review Architect** performing a scope-aware review of the work produced by a development swarm. You understand exactly what the swarm was supposed to deliver — and you only flag gaps within that scope. You do NOT flag missing functionality that belongs to other swarms or future work.

This command participates in a **convergence loop** with `/orchestrate_swarm`:
- review_swarm_pr reviews the PR, creates fixup tasks if needed
- orchestrate_swarm executes fixup tasks
- review_swarm_pr reviews again
- Loop continues until ALL findings (P1, P2, and P3) are resolved (converged)

## Environment Variables

This command uses the same environment variables as all eigen-squared commands:

- **`EIGEN_ROOT`** — absolute path to the root folder of the target project
- **`EIGEN_BRANCH`** — the default branch from which all work starts

### On Entry: Validate Environment

1. Read `$EIGEN_ROOT`. If not set or empty → **STOP.** Print:
   ```
   ERROR: $EIGEN_ROOT is not set.
   Set it to the root folder of your target project:
     export EIGEN_ROOT=/path/to/your/project
   ```
2. Read `$EIGEN_BRANCH`. If not set or empty → **STOP.** Print:
   ```
   ERROR: $EIGEN_BRANCH is not set.
   Set it to the default branch from which all work starts:
     export EIGEN_BRANCH=main
   ```

### Worktree Verification and Epic Detection

This command MUST run from inside the same worktree used by `/orchestrate_swarm`. No arguments needed — everything is derived from the branch name.

1. Verify we are inside a worktree:
   ```bash
   test -f "$(git rev-parse --show-toplevel)/.git" && echo "INSIDE_WORKTREE" || echo "MAIN_REPO"
   ```
   If `MAIN_REPO` → **STOP.** Print:
   ```
   ERROR: You are NOT inside a worktree. review_swarm_pr must run from inside
   the integration worktree (same one used by /orchestrate_swarm).

   cd $EIGEN_ROOT/.claude/worktrees/feat-P<N>.E<M>
   claude
   Then run /review_swarm_pr
   ```

2. Parse the branch name to extract phase N and epic M from `feat/P<N>.E<M>`:
   ```bash
   git rev-parse --abbrev-ref HEAD
   ```
   If branch doesn't match the pattern → **STOP.**

3. Resolve the worktree absolute path:
   ```bash
   WORKTREE_ABS=$(pwd)
   ```

4. Verify the manifest exists:
   ```bash
   test -f eigen_initiative/phases/phase_N/epic_M/swarm-manifest.json
   ```
   If missing → **STOP.**

Print: `Detected Phase <N>, Epic <M> (P<N>.E<M>) from branch feat/P<N>.E<M>.`

### Fixed Paths

All paths are relative to the worktree root (current working directory):

- **Manifest**: `eigen_initiative/phases/phase_N/epic_M/swarm-manifest.json`
- **Epic file**: `eigen_initiative/phases/phase_N/epic_M/epic.md`
- **Plan file**: `eigen_initiative/phases/phase_N/epic_M/plan.md`
- **Task directory**: `eigen_initiative/phases/phase_N/epic_M/tasks/`
- **Pipeline state**: `eigen_initiative/phases/pipeline_state.json`
- **Review report**: `eigen_initiative/phases/phase_N/epic_M/review_report_iteration_<N>.md`
- **Lessons directory**: `$EIGEN_ROOT/eigen_initiative/eigen_lessons/review_swarm_pr/`

## Overview

You will:
1. Verify worktree, detect epic, check iteration state
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

1. Read `eigen_initiative/phases/pipeline_state.json` from the worktree.
2. Check `state.phases[N].plans[M].swarm_execution`:
   - `status == "converged"` → **STOP.** Print: "Review for P<N>.E<M> has already converged. PR is ready to merge."
   - `review_iteration` field → current iteration number (0 = first review)
3. If a previous review report exists (`review_report_iteration_<N-1>.md`), read it for cross-iteration comparison.

### Convergence Decision (after collecting findings, Phase 4)

Apply these rules **in order**:

1. **Converge if**: zero P1, zero P2, AND zero P3 findings remain.
   - Rationale: "All findings resolved."

2. **Converge if**: iteration limit reached (`review_iteration >= 8`).
   - Rationale: "Maximum review iterations (8) reached. Accepting current state."

3. **Converge if**: oscillation detected AND no non-oscillating findings remain.
   - Oscillation = a finding was fixed in iteration N but reappeared in N+1.
   - Rationale: "Oscillation detected. Accepting current state to break cycle."

4. **Continue if**: any P1, P2, or P3 actionable findings remain.

---

## Phase 0: Setup and Context Loading

### 0.1 Validate PR

Read the PR number from pipeline state (`swarm_execution.pr_number`) or derive it:
```bash
gh pr list --head feat/P<N>.E<M> --json number,url,state --jq '.[0]'
```

Fetch PR metadata:
```bash
gh pr view <pr_number> --json title,body,headRefName,headRefOid,baseRefName,state,url,additions,deletions,changedFiles
```

Validate:
- PR exists and is `OPEN`. If closed/merged, warn but allow.
- PR's `headRefName` matches the integration branch.

### 0.2 Read Swarm Manifest

1. Read the manifest from the worktree.
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

## Phase 1: Spawn Review Agents

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

Wait for ALL agents.

---

## Phase 2: Collect, Filter, and Triage

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

## Phase 3: Convergence Decision

Apply the convergence rules from the Convergence Protocol section.

- **If CONVERGED** → skip Phase 4 (no fixup tasks), proceed to Phase 5 (post review + report).
- **If CONTINUE** → proceed to Phase 4 (create fixup tasks).

---

## Phase 4: Create Fixup Tasks (only if not converged)

### 4.1 Derive File Ownership

For each finding (P1, P2, and P3 — all severities get fixup tasks):
- Look up which manifest task owns the finding's file → `original_task_id`
- Determine `files_owned` and `test_files_owned` for the fix
- If file is in `shared_files` → integration finding (final wave)

### 4.2 Build Dependency Graph and Assign Waves

- Serialize findings that need the same file
- Continue wave numbering from manifest's last wave
- Integration findings in final wave

### 4.3 Create Task Files

For each finding, create directly in the worktree:

File: `eigen_initiative/phases/phase_N/epic_M/tasks/task_R<K padded to 3>.md`

```markdown
---
id: "P<N>.E<M>.R<K>"
title: "[REVIEW] <Finding Title>"
type: task
state: open
labels: ["review-finding", "severity-<p1|p2|p3>"]
phase: <N>
epic_id: "P<N>.E<M>"
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
original_task_id: "P<N>.E<M>.T<original>"
review_iteration: <current_iteration>
created_at: "<ISO 8601>"
updated_at: "<ISO 8601>"
---

## [REVIEW] <Finding Title>

**Parent Epic**: P<N>.E<M>
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
2. Append new review tasks with `"status": "pending"` and `"model": "opus"`
3. Append new execution waves
4. Update `e2e_config.e2e_scenarios` for P1 findings

### 4.6 Commit and Push

```bash
git add eigen_initiative/phases/phase_N/epic_M/
git commit -m "chore: review iteration <N> — <M> fixup tasks for P<N>.E<M>"
git push origin feat/P<N>.E<M>
```

### 4.7 Update Initiative Index

Update `eigen_initiative/_index.md` with the new review tasks.

---

## Phase 5: Post Review on PR

### 5.1 Post Structured Review

Post via GitHub API with inline comments at finding locations:

```bash
gh api repos/{owner}/{repo}/pulls/<pr_number>/reviews --input review.json
```

Review body includes: findings table, statistics, convergence status, next steps.

Use `event: "COMMENT"`.

If no findings (converged with zero issues): post a simple approval comment.

### 5.2 Write Review Report

Write `eigen_initiative/phases/phase_N/epic_M/review_report_iteration_<N>.md` with:
- Iteration number, PR info, agents used, tech stack
- All findings (approved and skipped)
- Cross-iteration comparison (if iteration 2+)
- Convergence status
- Manifest update summary

Commit:
```bash
git add eigen_initiative/phases/phase_N/epic_M/review_report_iteration_*.md
git commit -m "chore: review report iteration <N> for P<N>.E<M>"
git push origin feat/P<N>.E<M>
```

---

## Phase 6: Lesson Extraction

### 6.1 Determine Lesson Scope

Check if the current epic is the **E2E Testing epic** (read `epic_dag.json` from the worktree — the E2E epic has `name == "E2E Testing"` and `features == []`).

- **If E2E Testing epic**: create lessons for **ALL findings (P1, P2, and P3)**. The E2E Testing epic is the most critical learning opportunity in each phase — every finding here (infrastructure failures, cross-component bugs, integration patterns) is a systemic insight that improves future phases. Do not skip any severity.

- **If regular feature epic**: create lessons for **P1 findings only**.

### 6.2 Generate Lessons

For each finding in scope (determined by 6.1), create a lesson JSON.

### 6.3 Deduplicate and Write

Write to `$EIGEN_ROOT/eigen_initiative/eigen_lessons/review_swarm_pr/`.

---

## Phase 7: Update Pipeline State and Report

### 7.1 Update Pipeline State

Update `eigen_initiative/phases/pipeline_state.json` in the worktree:

**If converged:**
```json
"swarm_execution": {
  "status": "converged",
  "review_iteration": <N>,
  "convergence": {
    "converged": true,
    "decided_by": "review_swarm_pr",
    "decided_at": "<ISO 8601>",
    "reason": "<rationale>"
  },
  "review_reports": ["..._iteration_1.md", "..._iteration_2.md"],
  ...existing fields preserved...
}
```

**If continuing:**
```json
"swarm_execution": {
  "status": "iterating",
  "review_iteration": <N>,
  "convergence": { "converged": false },
  "findings_summary": { "p1": <x>, "p2": <y>, "p3": <z> },
  "review_reports": ["..._iteration_1.md", ...],
  ...existing fields preserved...
}
```

Commit and push:
```bash
git add eigen_initiative/phases/pipeline_state.json
git commit -m "chore: update pipeline state — review iteration <N> for P<N>.E<M>"
git push origin feat/P<N>.E<M>
```

### 7.2 Report

```
=== Review Complete — P<N>.E<M> (Iteration <N>) ===

PR: #<pr_number> (<pr_url>)
Branch: feat/P<N>.E<M> → $EIGEN_BRANCH

Findings:
  P1: <x>, P2: <y>, P3: <z>
  <if iteration 2+:>
  vs Previous: <addressed> fixed, <persistent> remaining, <new> new

Convergence: <CONVERGED | CONTINUE — N findings remain (P1: x, P2: y, P3: z)>

Next steps:
  If CONTINUE:
    Stay in this worktree and run /orchestrate_swarm
    The manifest has been updated — only new review tasks will execute.
    After fixups complete, run /review_swarm_pr again (iteration <N+1>).
  If CONVERGED:
    Merge the PR:
      gh pr merge <pr_number> --squash
    Then clean up:
      cd $EIGEN_ROOT
      git worktree remove .claude/worktrees/feat-P<N>.E<M>
      git branch -d feat/P<N>.E<M>
    Proceed to the next epic in the phase.
```

---

## Error Handling

- **Manifest not found**: STOP — orchestrate_swarm must have run first.
- **PR not found**: STOP — orchestrate_swarm must have created the PR.
- **No scoped diff**: STOP — nothing to review.
- **All agents return no findings**: report clean, apply convergence (zero findings → converge).

---

## Important Rules

- **Scope is king**: never flag issues outside the swarm's scope.
- **No code modifications**: this command reviews, creates tasks, updates manifest. No source code changes.
- **Runs from the worktree**: same worktree as orchestrate_swarm. All artifacts committed to `feat/P<N>.E<M>`.
- **Review task IDs**: `P<N>.E<M>.R<K>` format (R for Review).
- **Convergence**: ALL findings (P1, P2, and P3) must be resolved. Max 8 iterations. Oscillation breaks the cycle.
- **Push after every commit**: the PR updates automatically when the branch is pushed.
- **Merge is manual**: after convergence, the user merges the PR. This brings all artifacts (code, tasks, manifest, pipeline_state, reports) to `$EIGEN_BRANCH`.
- **Worktree cleanup is manual**: after merge, user removes the worktree and deletes the local branch.
- **Testing philosophy**: when evaluating tests, prefer real dependencies over mocks. Flag tests that mock where real infrastructure is available.

---

## Auto-Chain (claude-tasks integration)

If `$CLAUDE_TASKS_API` is set, schedule the next command based on convergence. If not set, skip.

**Determine next command:**

- **If CONTINUE** (findings remain) → `/orchestrate_swarm` (same worktree, fixup tasks)
- **If CONVERGED** → check if this is the E2E Testing epic (last epic in phase):
  1. Read `eigen_initiative/phases/phase_N/epic_dag.json` from the worktree
  2. Find the last epic in the `epics[]` array
  3. **If current epic IS the E2E Testing epic** (`name == "E2E Testing"` AND `features == []`) → **STOP.** Phase is complete. Do NOT create a next task. Print: `Phase <N> complete. All epics including E2E Testing have converged. Manual testing and PR merges required.`
  4. **If current epic is NOT the last** → schedule `/plan_phase_epic` for the next epic (working_dir back to `$EIGEN_ROOT`)

```bash
NEXT_RUN=$(date -u -d '+3 minutes' +%Y-%m-%dT%H:%M:%SZ)

# If CONTINUE (fixup needed):
# Only include telegram_webhook if $EIGEN_TELEGRAM_CHAT_ID is set and non-empty.
WORKTREE_ABS=$(pwd)
curl -s -X POST $CLAUDE_TASKS_API/api/v1/tasks \
  -H "Content-Type: application/json" \
  -d '{
    "name": "eigen: orchestrate_swarm P<N>.E<M> (fixup)",
    "prompt": "Use the Skill tool to invoke Skill(\"eigen-squared:orchestrate_swarm\"). Follow all its instructions completely.",
    "cron_expr": "",
    "scheduled_at": "'$NEXT_RUN'",
    "working_dir": "'$WORKTREE_ABS'",
    "enabled": true,
    "telegram_webhook": "'$EIGEN_TELEGRAM_CHAT_ID'"
  }'

# If CONVERGED + NOT E2E epic (more epics to do — plan the next one):
# Only include telegram_webhook if $EIGEN_TELEGRAM_CHAT_ID is set and non-empty.
curl -s -X POST $CLAUDE_TASKS_API/api/v1/tasks \
  -H "Content-Type: application/json" \
  -d '{
    "name": "eigen: plan_phase_epic (next epic)",
    "prompt": "Use the Skill tool to invoke Skill(\"eigen-squared:plan_phase_epic\"). Follow all its instructions completely.",
    "cron_expr": "",
    "scheduled_at": "'$NEXT_RUN'",
    "working_dir": "'$EIGEN_ROOT'",
    "enabled": true,
    "telegram_webhook": "'$EIGEN_TELEGRAM_CHAT_ID'"
  }'

# If CONVERGED + IS E2E epic:
# DO NOT create any task. Print phase completion message.
```

Print (if chaining): `Auto-chain: /<next_command> scheduled in 3 minutes.`
Print (if stopping): `Phase <N> complete. Autonomous pipeline finished. Review and merge PRs manually.`
