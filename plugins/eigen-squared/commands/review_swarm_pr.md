---
name: review_swarm_pr
description: Scope-aware post-swarm PR review that spawns review agents, triages findings, creates fixup tasks, and iterates until converged
---

# Scope-Aware Post-Swarm PR Review

## Pipeline Context

```
                        eigen-squared pipeline
                        ~~~~~~~~~~~~~~~~~~~~~~
  plan_epic_converge ──► orchestrate_swarm ◄──► review_swarm_pr
                                         ▲
                                         │
                                    YOU ARE HERE
```

You are a **Senior Code Review Architect** performing a scope-aware review of the work produced by a development swarm. You understand exactly what the swarm was supposed to deliver — and you only flag gaps within that scope. You do NOT flag missing functionality that belongs to other swarms or future work.

This command participates in a **convergence loop** with `orchestrate_swarm`:
- `review_swarm_pr` reviews the PR, creates fixup tasks if needed
- `orchestrate_swarm` executes fixup tasks
- `review_swarm_pr` reviews again
- Loop continues until all P1 and P2 findings are resolved. Residual P3 findings do not block convergence — they are recorded in `pipeline_state.json` for downstream visibility.

**Scope**: one epic at a time (P<N>.E<M>).

This command spawns review agents that need to understand the project's language conventions. Load the `language-profiles` skill to detect the project's languages and discover relevant review skills from the Stack-Specific Skills table.

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
eigen-squared get-context review_swarm_pr --json
```

Example JSON:
```json
{
  "command": "review_swarm_pr",
  "paths_relative_to": "$EIGEN_ROOT/eigen_initiative/",
  "phase": 1,
  "epic": 2,
  "branch": "feat/P1.E2",
  "manifest_path": "phases/phase_1/epic_2/swarm-manifest.json",
  "swarm_status": "pr_created",
  "review_iteration": 0,
  "pr_number": 42,
  "pr_url": "https://github.com/..."
}
```

| Field | Meaning |
|-------|---------|
| `phase`, `epic` | Which epic's PR to review. |
| `branch` | Integration branch. Must be checked out. |
| `manifest_path` | Path to swarm-manifest.json. |
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

Read `swarm-manifest.json.p3_sweep` (default `{ "active": false, "entered_at_iteration": null, "base_ref": null, "aborted": false, "regression_signatures": [] }` if absent) to detect whether this iteration is reviewing the output of a P3 sweep round.

If a previous review report exists (`review_report_iteration_<review_iteration - 1>.md`), read it for cross-iteration comparison.

### Convergence Decision (after collecting findings, Stage 3)

The pipeline runs as a small state machine over `(p1, p2, p3, p3_sweep.active)`. Apply the case that matches the current substate; both cases are mutually exclusive.

#### Case 1 — Normal iteration (`p3_sweep.active == false`)

Apply these rules **in order**:

1. **Converge if**: zero P1 AND zero P2 AND zero P3.
   - Rationale: "All findings resolved."

2. **Enter P3 sweep if**: zero P1 AND zero P2 AND P3 > 0.
   - This is **not** an immediate convergence. The pipeline runs **one** bounded P3-sweep round before merging.
   - Set `swarm-manifest.json.p3_sweep` to `{ "active": true, "entered_at_iteration": <current_iteration>, "base_ref": "<git rev-parse HEAD>", "aborted": false, "regression_signatures": [] }`. The `base_ref` is captured **before** any sweep fixup commits land — it is the rollback target if the sweep introduces regressions.
   - Decision is **CONTINUE**. Stage 4 generates fixup tasks for **all P3 findings** (one task per finding) in a single new wave with `"type": "p3-sweep"`.
   - Rationale: "All P1/P2 resolved. Entering one-shot P3 sweep for `<p3>` residual finding(s)."

3. **Continue if**: P1 > 0 or P2 > 0.
   - Decision is **CONTINUE**. Stage 4 generates fixup tasks for **P1 and P2 only**. P3 findings are recorded in `swarm-manifest.json.residual_p3` (file/severity/category/title) but never produce a `task_R*.md` during normal iterations.
   - Rationale: "<p1+p2> blocking findings remain (P1: <p1>, P2: <p2>); <p3> P3 carried as residual."

#### Case 2 — Post-sweep iteration (`p3_sweep.active == true`)

This iteration reviews the commits produced by the P3 sweep. The sweep is one-shot and bounded — convergence is mandatory. The post-sweep review never spawns another fixup round; instead, any new blocking findings trigger an autonomous auto-revert.

Because the sweep entered with `p1 == 0 AND p2 == 0`, **any P1 or P2 found in this iteration is "new" by construction** — it was introduced by a sweep fixup.

1. **Converge cleanly if**: zero P1 AND zero P2.
   - Set `p3_sweep.active = false` in the manifest. Leave `aborted: false`.
   - Rationale: "P3 sweep completed. <addressed> P3 finding(s) resolved; <residual> recorded as residual."

2. **Auto-revert and converge if**: P1 > 0 OR P2 > 0 (sweep regression).
   - Execute the auto-revert protocol in Stage 4.6. This reverts every commit between `p3_sweep.base_ref` and current HEAD as a single revert commit.
   - Update the manifest: `p3_sweep.active = false`, `p3_sweep.aborted = true`, `p3_sweep.regression_signatures = [<signatures of new P1/P2>]`.
   - Rationale: "P3 sweep introduced <x> P1 and <y> P2 finding(s). Auto-reverted sweep commits to base ref <base_ref:0:7>. Converging with original residual P3 list (<residual>). Recorded for compound_improve."
   - This branch terminates with `swarm_status == converged` and `sweep_aborted == true`. **No further fixup iterations are spawned, ever.** The next watchdog tick proceeds to merge as normal.

A post-sweep iteration **always** terminates with `swarm_status == converged`. There is no third state. If state corruption produces both `p3_sweep.active == true` AND nonzero P1/P2 yet the auto-revert cannot run (e.g., `base_ref` is missing), STOP with a hard error so the watchdog halts instead of silently looping.

#### Outer safety net

- `review_iteration >= 8` → converge regardless of substate. Rationale: "Maximum review iterations (8) reached. Accepting current state."

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

The agent roster is **locked at iteration 0** for the lifetime of the epic's PR. This guarantees that any cross-iteration growth in apparent finding counts reflects genuine new code-quality regressions, not late-discovered latent issues from a newly-added reviewer type.

**If `review_iteration == 0`** — compute the roster:

  **Always spawn (universal):**
  - `security-sentinel`, `architecture-strategist`, `code-simplicity-reviewer`, `data-integrity-guardian`, `test-practices-researcher-no-vs`

  **Conditionally spawn (from language-profiles skill Stack-Specific Skills):**
  - Matched language/domain skills
  - `performance-oracle` — if acceptance criteria mention performance or diff > 500 lines
  - `pattern-recognition-specialist` — if diff > 500 lines

  Persist the resolved roster to the iteration-0 review report's YAML front-matter (Stage 5.2) under the `agents_used` key so subsequent iterations can read it back verbatim.

**If `review_iteration >= 1`** — reuse the iter-0 roster:

  Read `eigen_initiative/phases/phase_<phase>/epic_<epic>/review_report_iteration_0.md` from the integration branch and parse its YAML front-matter. Use `agents_used` verbatim. Ignore the conditional triggers (diff size, performance-mention) entirely — even if the diff has grown past 500 lines or new acceptance criteria mention performance, **do not add agents**.

  If the iter-0 report is missing or its front-matter does not contain an `agents_used` list, **STOP** with:

  ```
  ERROR: review_report_iteration_0.md not found on integration branch (or missing agents_used front-matter) — agent roster cannot be reconstructed for iteration <N>.
  ```

  Do not silently recompute the roster. A missing iter-0 report indicates a force-push regression of the integration branch and must be surfaced to the operator.

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

Apply the state machine in the Convergence Protocol section against the just-collected findings, the manifest's `p3_sweep` substate, and `review_iteration`.

The decision dispatches Stage 4's behavior:

| Case | Decision | Stage 4 behavior |
|---|---|---|
| Case 1.1 (clean: `p1=p2=p3=0`) | **CONVERGED** | Skip Stage 4 entirely; proceed to Stage 5. |
| Case 1.2 (entering sweep: `p1=p2=0, p3>0`) | **CONTINUE — sweep entry** | Stage 4 generates one fixup task per P3 finding in a single `p3-sweep` wave; sets `p3_sweep.active=true` in manifest. |
| Case 1.3 (normal iter: `p1>0 OR p2>0`) | **CONTINUE — iterating** | Stage 4 generates fixup tasks for P1+P2 only. P3s recorded in `residual_p3`. |
| Case 2.1 (post-sweep clean: `p3_sweep.active=true`, `p1=p2=0`) | **CONVERGED** | Skip Stage 4; proceed to Stage 5. Manifest's `p3_sweep.active` set to `false`. |
| Case 2.2 (post-sweep regression: `p3_sweep.active=true`, `p1>0 OR p2>0`) | **CONVERGED — sweep aborted** | Skip 4.1–4.5; execute Stage 4.6 (auto-revert) only. Manifest's `p3_sweep.aborted=true` and `regression_signatures` populated. Then Stage 5. |
| Iteration cap (`review_iteration >= 8`) | **CONVERGED** | Same as Case 1.1, regardless of counts. |

The post-sweep cases (2.1 / 2.2) **never** spawn another fixup round. The pipeline cannot re-arm the sweep loop.

---

## Stage 4: Create Fixup Tasks (only if not converged)

The behavior of Stage 4 depends on the case selected in Stage 3:

- **Case 1.3 (normal iterating)**: run Stage 4.1–4.7 over **P1 + P2 findings only**. Record P3s in `residual_p3`.
- **Case 1.2 (sweep entry)**: run Stage 4.1–4.7 over **P3 findings only**. The new wave has `"type": "p3-sweep"`. Persist `p3_sweep` block in the manifest (Stage 4.5).
- **Case 2.2 (sweep regression)**: skip Stage 4.1–4.5; run **Stage 4.6 (auto-revert)** then proceed to Stage 5. No new tasks are created.

### 4.1 Derive File Ownership

The "selected findings" set depends on the Stage 3 case (P1+P2 in Case 1.3; P3 only in Case 1.2; nothing in Case 2.2). For each selected finding:
- Look up which manifest task owns the finding's file → `original_task_id`
- Determine `files_owned` and `test_files_owned` for the fix
- If file is in `shared_files` → integration finding (final wave)

### 4.2 Build Dependency Graph and Assign Waves

- Serialize findings that need the same file
- Continue wave numbering from manifest's last wave
- Integration findings in final wave

### 4.3 Create Task Files

For each finding, create directly on the integration branch:

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

1. Mark original tasks (from previous waves) as `"status": "completed"`.
2. Append new review tasks with `"status": "pending"` and `"model": "<worker_model>"`.
3. Append new execution waves. Use `"type": "review-fixup"` for normal iterations (Case 1.3) and `"type": "p3-sweep"` for the single sweep wave (Case 1.2).
4. Update `e2e_config.e2e_scenarios` for P1 findings.
5. **In Case 1.3 only**: refresh `swarm-manifest.json.residual_p3` with the current P3 findings (replace, don't append) so downstream consumers see the live residual list.
6. **In Case 1.2 only (sweep entry)**: write `swarm-manifest.json.p3_sweep`:
   ```json
   {
     "active": true,
     "entered_at_iteration": <current_iteration>,
     "base_ref": "<git rev-parse HEAD>",
     "aborted": false,
     "regression_signatures": []
   }
   ```
   Capture `base_ref` **before** any fixup commits land — this is the rollback target if the sweep regresses.

### 4.6 Auto-revert P3 Sweep on Regression (Case 2.2 only)

Triggered exclusively by Case 2.2 (post-sweep iteration with new P1 or P2). All other cases skip this section.

```bash
# Read the sweep base ref from the manifest. If missing, the sweep state is corrupt — STOP.
base_ref=$(jq -r '.p3_sweep.base_ref' eigen_initiative/phases/phase_<phase>/epic_<epic>/swarm-manifest.json)
if [ -z "$base_ref" ] || [ "$base_ref" = "null" ]; then
    echo "ERROR: p3_sweep.base_ref missing — cannot auto-revert. Halting Stage 4.6."
    exit 1
fi

# Verify we're on the integration branch.
current=$(git rev-parse --abbrev-ref HEAD)
[ "$current" = "feat/P<N>.E<M>" ] || { echo "ERROR: must be on integration branch. Got $current."; exit 1; }

# Working tree must be clean before reverting.
if ! git diff --quiet || ! git diff --cached --quiet; then
    echo "ERROR: working tree dirty before sweep auto-revert."
    exit 1
fi

# Capture the list of reverted SHAs for the report and PR comment.
reverted_shas=$(git rev-list "${base_ref}..HEAD")

# Revert every commit between base_ref and HEAD as a single revert commit.
# --no-commit accumulates the reverts; one commit captures the whole rollback.
git revert --no-commit "${base_ref}..HEAD" || {
    echo "ERROR: git revert failed during sweep auto-revert. Manual reconciliation required."
    exit 1
}
git commit -m "chore: auto-revert P3 sweep for P<N>.E<M> — sweep introduced new P1/P2 findings, restoring base ref ${base_ref:0:7}"
git push origin feat/P<N>.E<M>
```

Compute `regression_signatures` for each new P1/P2 finding. The signature is the SHA-1 hex digest of `<normalized_file_path>|<category>|<normalized_title>`, where `normalized_file_path` is the POSIX-style relative path with case preserved, `category` is the lowercase short category (e.g. `security`, `data-integrity`), and `normalized_title` is the title lowercased, whitespace-collapsed, and stripped of trailing punctuation. Persist the signatures in `swarm-manifest.json.p3_sweep`:

```json
{
  "active": false,
  "entered_at_iteration": <iteration_when_entered>,
  "base_ref": "<base_ref_sha>",
  "aborted": true,
  "regression_signatures": [
    {"sig": "<sha1>", "file": "<path>", "category": "<cat>", "severity": "P1|P2", "title": "<title>"}
  ]
}
```

Record the reverted SHAs and the regression signatures in `review_report_iteration_<N>.md` under a "Sweep Aborted" heading. Surface them in the PR comment in Stage 5.1.

After Stage 4.6 completes, **skip Stage 4.7 (commit/push of fixup tasks — there are none) and Stage 4.8 (index update — no new tasks)**. Proceed directly to Stage 5.

### 4.7 Commit and Push (Cases 1.2 and 1.3 only)

```bash
git add eigen_initiative/phases/phase_N/epic_M/
git commit -m "chore: review iteration <N> — <M> fixup tasks for P<N>.E<M>"
git push origin feat/P<N>.E<M>
```

### 4.8 Update Initiative Index (Cases 1.2 and 1.3 only)

Update `eigen_initiative/_index.md` with the new review tasks.

---

## Stage 5: Post Review on PR

### 5.1 Post Structured Review

Post via GitHub API with inline comments at finding locations:

```bash
gh api repos/{owner}/{repo}/pulls/<pr_number>/reviews --input review.json
```

The review body must include:
- **Findings table** — every finding raised this iteration (P1, P2, P3). Show in-line locations.
- **Residual P3 list** — the live `swarm-manifest.json.residual_p3` array, regardless of which case fired. P3 findings are always disclosed even when no fixup task is created for them.
- **Sweep state line** — exactly one of:
  - `Sweep state: not entered` (any normal iteration before the sweep)
  - `Sweep state: entering — <p3_count> P3 fixup task(s) queued in wave <N>` (Case 1.2)
  - `Sweep state: post-sweep clean — <addressed> P3 resolved, <residual> remaining` (Case 2.1)
  - `Sweep state: post-sweep ABORTED — sweep introduced <p1_new> P1 / <p2_new> P2; reverted <revert_count> commit(s) to <base_ref:0:7>. See "Sweep Aborted" in the report.` (Case 2.2)
- **Convergence status** — CONVERGED / CONTINUE — with the case identifier (e.g., "Case 1.2 — sweep entry").
- **Next steps** — directives for the watchdog: "run /orchestrate_swarm" (Cases 1.2/1.3) or "merging now" (Cases 1.1/2.1/2.2).

Use `event: "COMMENT"`.

If no findings (Case 1.1 — converged clean): post a simple approval comment.

### 5.2 Write Review Report

Write `eigen_initiative/phases/phase_N/epic_M/review_report_iteration_<N>.md` with:

**YAML front-matter** (machine-readable; required on every iteration):
```yaml
---
iteration: <N>
epic_id: "P<phase>.E<epic>"
agents_used:
  - <agent_id>
  - <agent_id>
  - ...
---
```

The `agents_used` list MUST be the exact set of agents spawned in Stage 1. On iteration 0 this is the freshly-computed roster; on iteration ≥ 1 it is the verbatim list read from `review_report_iteration_0.md`. Downstream iterations and tooling depend on this field — never omit it.

**Body**:
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

## Stage 6: Lesson Extraction

### 6.1 Determine Lesson Scope

Check if the current epic is the **E2E Testing epic** (read `epic_manifest.json` — the E2E epic has `name == "E2E Testing"` and `features == []`).

- **If E2E Testing epic**: create lessons for **ALL findings (P1, P2, and P3)**. The E2E Testing epic is the most critical learning opportunity in each phase — every finding here (infrastructure failures, cross-component bugs, integration patterns) is a systemic insight that improves future phases. Do not skip any severity.

- **If regular feature epic**: create lessons for **P1 findings only**.

### 6.2 Generate Lessons

For each finding in scope (determined by 6.1), create a lesson JSON.

### 6.3 Deduplicate and Write

Write to `$EIGEN_ROOT/eigen_initiative/eigen_lessons/review_swarm_pr/`.

---

## Stage 7: Update Pipeline State and Report

### 7.1 Update Pipeline State

Use the CLI to update pipeline state. The exact calls depend on the Stage 3 case. `swarm_status` is set to `"iterating"` for any case that creates fixup tasks (Cases 1.2 and 1.3) and to `"converged"` for any terminal case (1.1, 2.1, 2.2). The Convergence Protocol's substate (`p3_sweep.active`, `aborted`, `regression_signatures`) lives in `swarm-manifest.json` already (committed via Stage 4) and is not duplicated here.

The `--reason` string MUST mention residual P3 count when `p3 > 0` and MUST mention sweep abort when applicable so downstream commands and the PR-comment renderer can parse/display it.

**Case 1.1 — converged clean (`p1=p2=p3=0`):**
```bash
eigen-squared complete review_swarm_pr --phase <phase> --epic <epic> --report-path <report_path> --findings-summary '{"p1": 0, "p2": 0, "p3": 0}'
eigen-squared mark-converged swarm_execution --phase <phase> --epic <epic> --reason "All findings resolved."
eigen-squared commit-state --message "pipeline: review P<phase>.E<epic> — CONVERGED" --additional-paths eigen_initiative/phases/phase_<phase>/epic_<epic>/
```

**Case 1.2 — entering P3 sweep (`p1=p2=0, p3>0`, sweep tasks queued):**
```bash
# Substate transition: still "iterating" from the watchdog's perspective so it auto-runs orchestrate_swarm next.
eigen-squared complete review_swarm_pr --phase <phase> --epic <epic> --report-path <report_path> --findings-summary '{"p1": 0, "p2": 0, "p3": <z>}'
eigen-squared set-swarm-status iterating --phase <phase> --epic <epic>
eigen-squared commit-state --message "pipeline: review P<phase>.E<epic> — iteration <N>, ENTER P3 SWEEP (<z> P3 task(s) queued)" --additional-paths eigen_initiative/phases/phase_<phase>/epic_<epic>/
```

**Case 1.3 — continuing iteration (`p1>0 OR p2>0`):**
```bash
eigen-squared complete review_swarm_pr --phase <phase> --epic <epic> --report-path <report_path> --findings-summary '{"p1": <x>, "p2": <y>, "p3": <z>}'
eigen-squared set-swarm-status iterating --phase <phase> --epic <epic>
eigen-squared commit-state --message "pipeline: review P<phase>.E<epic> — iteration <N>, CONTINUE" --additional-paths eigen_initiative/phases/phase_<phase>/epic_<epic>/
```

**Case 2.1 — post-sweep clean (`p1=p2=0`, sweep succeeded):**
```bash
# Use the original residual P3 count (the count *before* the sweep ran; many P3s may now be addressed).
eigen-squared complete review_swarm_pr --phase <phase> --epic <epic> --report-path <report_path> --findings-summary '{"p1": 0, "p2": 0, "p3": <z>}'
eigen-squared mark-converged swarm_execution --phase <phase> --epic <epic> --reason "P3 sweep completed. <addressed> P3 finding(s) resolved; <z> recorded as residual."
eigen-squared commit-state --message "pipeline: review P<phase>.E<epic> — CONVERGED (post-sweep)" --additional-paths eigen_initiative/phases/phase_<phase>/epic_<epic>/
```

**Case 2.2 — post-sweep aborted (`p1>0 OR p2>0`, sweep regressed):**

Stage 4.6 has already auto-reverted the sweep commits and updated `swarm-manifest.json.p3_sweep.aborted=true`. The findings_summary reported here uses the **pre-sweep** counts (which by definition were `p1=0, p2=0` and the original residual P3 list) since the branch is now back at `base_ref` content-wise.

```bash
# <z> here is the original residual P3 count from before the sweep ran.
eigen-squared complete review_swarm_pr --phase <phase> --epic <epic> --report-path <report_path> --findings-summary '{"p1": 0, "p2": 0, "p3": <z>}'
eigen-squared mark-converged swarm_execution --phase <phase> --epic <epic> --reason "P3 sweep introduced <x> P1 / <y> P2 finding(s). Auto-reverted to base ref <base_ref:0:7>. Converging with original residual P3 list (<z>). Sweep aborted; regression recorded for compound_improve."
eigen-squared commit-state --message "pipeline: review P<phase>.E<epic> — CONVERGED (sweep aborted)" --additional-paths eigen_initiative/phases/phase_<phase>/epic_<epic>/
```

In Cases 2.1 and 2.2, also write a lesson to `eigen_initiative/eigen_lessons/review_swarm_pr/` capturing whichever signal applies (clean sweep success, regression vectors). This is consumed by `compound_improve` on its next pass and is the only persistent record of the sweep outcome outside of `swarm-manifest.json.p3_sweep`.

### 7.2 Merge PR and Return to $EIGEN_BRANCH (CONVERGED only)

**Skip this section entirely if not converged.**

When converged, atomically merge the PR, reconcile `$EIGEN_BRANCH`, and
verify the post-merge state reflects convergence. **Every step must
succeed; a failure aborts 7.2 loudly so the next watchdog tick does not
race against a half-applied merge.** This is the fix for the
2026-04-22 P2.E1 regression, where a silent failure in this block left
local `$EIGEN_BRANCH` stale and triggered an auto re-run of
`create_issues_from_plan_swarm`.

```bash
# Precondition: working tree must be clean before merging. If 7.1's
# commit-state left anything unstaged, stop here and fix it first.
if ! git diff --quiet || ! git diff --cached --quiet; then
    echo "ERROR: working tree is dirty before Stage 7.2 merge. Aborting."
    exit 1
fi

# Merge the PR (squash to keep history clean, --delete-branch removes remote branch).
# Abort on any failure — a failed merge must NOT be followed by the checkout/pull sequence.
gh pr merge <pr_number> --squash --delete-branch || {
    echo "ERROR: gh pr merge failed for PR #<pr_number>. Stage 7.2 aborted."
    exit 1
}

# Return to $EIGEN_BRANCH. Use --ff-only on the pull so a diverged local
# branch fails loudly instead of producing a silent merge commit that
# masks the real state.
git fetch origin $EIGEN_BRANCH || {
    echo "ERROR: git fetch origin $EIGEN_BRANCH failed post-merge."
    exit 1
}
git checkout $EIGEN_BRANCH || {
    echo "ERROR: checkout $EIGEN_BRANCH failed post-merge."
    exit 1
}
git pull --ff-only origin $EIGEN_BRANCH || {
    echo "ERROR: ff-only pull of $EIGEN_BRANCH failed after merging PR. Local state is DIVERGED — manual reconciliation required before the next tick."
    exit 1
}

# Verify the post-merge pipeline_state.json reflects convergence on
# $EIGEN_BRANCH. If it does not, the squash either didn't carry the
# state update or the state was committed to a different branch — either
# way, downstream decisions would be wrong.
converged=$(eigen-squared status --json 2>/dev/null | python3 -c "
import sys, json
d = json.load(sys.stdin)
sw = (d.get('phases', {})
       .get('<phase>', {})
       .get('plans', {})
       .get('<epic>', {})
       .get('swarm_execution', {}))
print(sw.get('convergence', {}).get('converged', False))
")
if [ "$converged" != "True" ]; then
    echo "ERROR: swarm_execution.convergence.converged is not True on $EIGEN_BRANCH after merge for P<phase>.E<epic>. Stage 7 did not reach a consistent state. Manual reconciliation required (likely: state update commit was lost in the squash)."
    exit 1
fi

# Delete local integration branch. Use -D (force) because a squash-merge
# is not a traditional merge from git's perspective — `git branch -d`
# would refuse with "not fully merged" even though the content landed.
git branch -D feat/P<N>.E<M> 2>/dev/null || true
```

This ensures:
1. The merge, checkout, pull, and state-verification are **fail-fast** — a failure at any step leaves a loud error for the watchdog/operator instead of silently proceeding to Stage 7.3.
2. `$EIGEN_BRANCH` is actually up to date with the squash (`--ff-only` guarantees this or errors).
3. The next epic's `/plan_epic_converge` and the next watchdog `cmd_next` read the correct pipeline state.
4. The integration branch is cleaned up both remotely (`--delete-branch`) and locally (`branch -D`).

### 7.3 Report

```
=== Review Complete — P<N>.E<M> (Iteration <N>) ===

PR: #<pr_number> (<pr_url>)
Branch: feat/P<N>.E<M> → $EIGEN_BRANCH

Findings:
  P1: <x>, P2: <y>, P3: <z>
  <if iteration 2+:>
  vs Previous: <addressed> fixed, <persistent> remaining, <new> new
  <if Case 2.1 or 1.1 with z > 0:>
  Residual (non-blocking): P3 × <z> — recorded in swarm-manifest.json.residual_p3 and pipeline_state.json
  <if Case 2.2 (sweep aborted):>
  Sweep regression: <x_new> P1 + <y_new> P2 introduced; auto-reverted <revert_count> commit(s) to <base_ref:0:7>.

Sweep state: <not entered | entering — z P3 fixup task(s) queued | post-sweep clean | post-sweep ABORTED>

Convergence: <CONVERGED — Case 1.1 | CONTINUE — Case 1.2 sweep entry | CONTINUE — Case 1.3 iterating | CONVERGED — Case 2.1 post-sweep | CONVERGED — Case 2.2 sweep aborted>

Next steps:
  Case 1.2 / 1.3 (CONTINUE):
    Stay on this branch and run /orchestrate_swarm.
    The manifest has been updated — only new review tasks will execute. In Case 1.2, the new tasks are P3-sweep tasks and the leader will inject the P3-SWEEP CONSTRAINT block into each worker's spawn prompt.
    After fixups complete, run /review_swarm_pr again (iteration <N+1>).
  Case 1.1 / 2.1 / 2.2 (CONVERGED):
    PR #<pr_number> merged to $EIGEN_BRANCH. Branch feat/P<N>.E<M> deleted.
    Now on $EIGEN_BRANCH with latest changes.
    If more epics remain in this phase: proceeding to next epic.
    If all epics are complete: run /eigen_continue to review and approve the phase.
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
- **Runs from the integration branch**: same branch as orchestrate_swarm. All artifacts committed to `feat/P<N>.E<M>`.
- **Review task IDs**: `P<N>.E<M>.R<K>` format (R for Review).
- **Convergence**: all P1 and P2 findings must be resolved. Residual P3 findings are allowed and recorded in `pipeline_state.json` (`swarm_execution.findings_summary.p3` and `swarm_execution.convergence.reason`) and in `swarm-manifest.json.residual_p3`. Max 8 iterations. Oscillation breaks the cycle.
- **P3 fixup policy**: P3 findings do **not** trigger per-iteration fixup tasks. They are addressed in **one bounded P3-sweep round** that runs after all P1/P2 are resolved (Case 1.2). The post-sweep review (Case 2.1 / 2.2) **always** terminates: either it converges cleanly, or — if the sweep introduced new P1/P2 — the sweep commits are auto-reverted (Stage 4.6) and the epic converges with the original residual P3 list and `sweep_aborted: true`. The pipeline never re-enters fixup mode after a sweep, even if the sweep regressed. Sweep regressions are recorded for `compound_improve` learning, not for human escalation — the loop is fully autonomous and bounded by construction.
- **Push after every commit**: the PR updates automatically when the branch is pushed.
- **Merge is automatic on convergence**: when converged, the command merges the PR via `gh pr merge --squash --delete-branch`, checks out `$EIGEN_BRANCH`, pulls, and deletes the local branch. No manual step needed.
- **Post-merge state**: after auto-merge, the working directory is on `$EIGEN_BRANCH` with all epic artifacts (code, tasks, manifest, pipeline_state, reports) merged in.
- **Testing philosophy**: when evaluating tests, prefer real dependencies over mocks. Flag tests that mock where real infrastructure is available.
- **Agent roster is locked at iteration 0**: the set of review agents spawned for an epic's PR is computed once on iteration 0 and persisted to that iteration's report front-matter. Iterations ≥ 1 reuse the iter-0 roster verbatim. Conditional triggers (diff size, performance-mention) are evaluated only on iteration 0. Any new reviewer type only takes effect starting from the next epic. This guarantees that growth in apparent finding count across iterations of the same epic reflects genuine new regressions, not late-discovered latent issues from an expanded roster.

