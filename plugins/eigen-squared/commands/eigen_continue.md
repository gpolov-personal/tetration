---
name: eigen_continue
description: Phase transition checkpoint — summarize completed phase, provide testing recipe, and launch the next phase after user confirmation
---

# Eigen Continue — Phase Transition Checkpoint

## Pipeline Context

```
eigen_start → space_split_converge → plan_epic_converge → create_issues_from_plan_swarm
  → orchestrate_swarm ↔ review_swarm_pr → eigen_continue → (next phase)
                                               ▲ YOU ARE HERE
```

This command is the **human checkpoint** between phases. The autonomous pipeline runs each phase to completion (all epics converged), then stops. This command presents the results and asks the user to test and approve before the next phase begins.

**Two modes, same command:**
- **Mode 1 (Summary)**: all epics converged, review not started → present summary + testing recipe → set status to `"testing"`
- **Mode 2 (Continue)**: review status is `"testing"` → ask if testing passed → if yes, approve and schedule next phase

---

## Environment

Before proceeding, verify:

- [x] `$EIGEN_ROOT` is set (absolute path to target project root)
- [x] `$EIGEN_BRANCH` is set (default branch, e.g. `main`)

If either is missing → **STOP** with a descriptive error.

---

## On Entry

```bash
eigen-squared status --json
```

Parse the returned JSON to find the phase that needs review. Scan `phases` in numeric order (phase 1, 2, etc.):

1. If a phase has `phase_review.status == "testing"` → that phase is awaiting user confirmation → **go to Mode 2** with that phase number N.

2. If a phase has all epics with `swarm_execution.status == "converged"` AND (`phase_review.status == "not_started"` or no `phase_review`) → that phase just completed → **go to Mode 1** with that phase number N.

3. If no phase matches either condition → **STOP.** Print:
   ```
   No phase is ready for review.
   Either the pipeline hasn't completed a phase yet, or all phases have been approved.
   ```

---

## Mode 1: Summary & Testing Recipe

**Entry condition:** Phase N has all epics converged, `phase_review.status` is `"not_started"` or doesn't exist.

### 1.1 Load All Artifacts

For the completed phase N, read:
- `$EIGEN_ROOT/eigen_initiative/phases/phase_N_manifest.md` — phase name, e2e_summary, features
- `$EIGEN_ROOT/eigen_initiative/phases/phase_N/epic_manifest.json` — all epics, execution order
- `$EIGEN_ROOT/eigen_initiative/phases/phase_N/phase_e2e_config.json` — validation scenarios, E2E scenarios, infrastructure requirements
- For each epic M in the phase:
  - `state.phases[N].plans[M].swarm_execution` — PR url, PR number, review iterations, **`convergence.reason`** (free-text; the prefix classifies the case — see `pipeline-state-schema/SKILL.md` "Convergence reason taxonomy")
  - `state.phases[N].plans[M].swarm_execution.findings_history` — per-iteration `(p1, p2, p3)` trajectory, used when surfacing degraded convergence
  - `$EIGEN_ROOT/eigen_initiative/phases/phase_N/epic_M/epic.md` — epic name, features
  - Latest review report (if exists): `$EIGEN_ROOT/eigen_initiative/phases/phase_N/epic_M/review_report_iteration_*.md`
  - `$EIGEN_ROOT/eigen_initiative/phases/phase_N/epic_M/review_convergence_state.json` (if exists) — for degraded epics, contains `oscillation` / `monotonicity` blocks with the structured detail referenced by the convergence reason

### 1.2 Fetch PR Status

For each epic with a `swarm_execution.pr_url`, fetch current PR status:
```bash
gh pr view <pr_number> --json state,title,additions,deletions,changedFiles,mergedAt
```

### 1.3 Classify Convergence Outcomes

Before presenting the summary, classify each epic's `convergence.reason` into **clean** or **degraded**:

| Reason prefix | Class | Why it's degraded |
|---|---|---|
| `All findings resolved` | clean | Case 1.1 — zero P1/P2/P3. |
| `P3 sweep completed` | clean | Case 2.1 — bounded sweep ran, residual P3 list disclosed. |
| `Maximum review iterations` (residual = 0) | clean | Cap reached AND `findings_history[-1].p1 + p2 + p3 == 0`. Final iteration was genuinely empty. |
| `Maximum review iterations` (residual > 0) → `CAP_REACHED_WITH_RESIDUAL` | **degraded** | Cap reached BEFORE any rule converged AND `findings_history[-1].p1 + p2 + p3 > 0`. Findings remain in code. **Reclassify the reason internally to `CAP_REACHED_WITH_RESIDUAL`** and treat exactly like the other degraded reasons (re-show in the Degraded Epics section, require typed APPROVE-DEGRADED in Mode 2 confirmation, always promote findings to lessons via Stage 6.1). The PR Stage 7.2 auto-merge SHOULD NOT have fired here in the first place; if it did (legacy state from before this rule), surface a `cap_with_residual_post_merge: true` warning so the user knows to manually inspect the merged PR. |
| `P3 sweep introduced` (SWEEP_ABORTED) | **degraded** | Sweep introduced new P1/P2; commits auto-reverted. Epic ships at the pre-sweep state with the original residual P3 list. |
| `CAPPED_BY_OSCILLATION` | **degraded** | Same `(file, category)` pair appeared in ≥ 3 iterations; loop accepted to break the cycle. Findings remain in code. |
| `P1_REGRESSION_PERSISTENT` | **degraded** | M1 fired three times; architectural escalation could not stabilize the fix. P1 finding(s) remain in code. |
| `DIVERGING_LOOP` | **degraded** | M2 fired; `p3` rose while `p1+p2` did not improve. Findings remain in code. |

For each **degraded** epic, also pull:
- The full `convergence.reason` text (it carries human-readable detail after the prefix).
- The last 3 entries of `findings_history` for the trajectory.
- The relevant block from `review_convergence_state.json` (`oscillation` for `CAPPED_BY_OSCILLATION`, `monotonicity` for the M-rule reasons; `swarm-manifest.json.p3_sweep` for `SWEEP_ABORTED`).

### 1.3.1 Present Phase Summary

```
=== Phase <N> Complete — Summary ===

Phase: <N> — <phase_e2e_summary from manifest>
Status: All epics converged (including E2E Testing)<if any degraded: " — see Degraded Epics section below">

Epics Completed:
  | Epic | Name | Features | PR | Review Iterations | Convergence |
  |------|------|----------|----|-------------------|-------------|
  | P<N>.E1 | <name> | <count> | #<pr> | <iterations> | clean |
  | P<N>.E2 | <name> | <count> | #<pr> | <iterations> | DEGRADED — <reason_prefix> |
  | P<N>.E<last> | E2E Testing | 0 | #<pr> | <iterations> | clean |

PRs to Review and Merge (in order):
  1. gh pr merge <pr_1> --squash   # P<N>.E1 — <name>
  2. gh pr merge <pr_2> --squash   # P<N>.E2 — <name>
  ...
  <last>. gh pr merge <pr_last> --squash   # P<N>.E<last> — E2E Testing

  Merge in epic order (E1 first, E2E Testing last).
```

### 1.3.2 Degraded Epics (only if any exist)

If any epic was classified **degraded** above, append this section to the summary; otherwise skip it entirely. The user MUST see this before deciding whether to test/approve — degraded epics shipped with known unresolved findings.

```
=== Degraded Epics — Manual Verification Required ===

The autonomous loop converged the following epics with known unresolved findings.
Each epic's PR has already been merged to $EIGEN_BRANCH (Stage 7.2 of review_swarm_pr).
Do NOT approve this phase until you have manually verified each degraded epic.

<for each degraded epic:>
- P<N>.E<M> — <epic name>
    Reason: <full convergence.reason text>
    Trajectory (last 3 iters): p1=<p1_{N-2}>→<p1_{N-1}>→<p1_N>, p2=<p2_*>→..., p3=<p3_*>→...
    Structured detail: <path to review_convergence_state.json>
    Review reports: eigen_initiative/phases/phase_<N>/epic_<M>/review_report_iteration_*.md
    Recommended check:
      <if CAPPED_BY_OSCILLATION:>      Inspect the oscillating (file, category) pairs and decide whether the architectural alternative is worth a follow-up epic.
      <if P1_REGRESSION_PERSISTENT:>   Read the M1 trajectory in review_convergence_state.json.monotonicity (per-iteration prev_p1/current_p1) AND the m1_firings counter in swarm-manifest.json.monotonicity (the firing count that triggered the cap); assess whether the residual P1 should block phase approval.
      <if DIVERGING_LOOP:>             Read the trajectory; the loop did not converge — confirm the residual findings are acceptable for production.
      <if SWEEP_ABORTED:>              Inspect swarm-manifest.json.p3_sweep.regression_signatures to understand which P3 fix attempts introduced regressions.
</for>

If any degraded epic looks unsafe to ship, refuse this phase's approval (Mode 2 → "No") and either:
  (a) revert the offending PR(s) and re-run /orchestrate_swarm with adjusted scope, or
  (b) accept the residual findings explicitly and re-run /eigen_continue to approve.
```

### 1.4 Generate Testing Recipe

Read `phase_e2e_config.json` to build the recipe:

```
=== Testing Recipe for Phase <N> ===

1. MERGE ALL PRs (in order):
   <list each gh pr merge command>

2. PULL LATEST:
   git checkout $EIGEN_BRANCH
   git pull origin $EIGEN_BRANCH

3. INFRASTRUCTURE SETUP:
   <from phase_e2e_config.infrastructure_requirements>
   - needs_docker: <yes/no> → <setup command if yes>
   - needs_emulator: <yes/no> → <setup instructions if yes>
   - needs_browser_automation: <yes/no> → <setup instructions if yes>
   - services: <list>

4. RUN UNIT/INTEGRATION TESTS:
   <test command from language-profiles skill for detected language>
   All tests should pass — these were verified by the swarm workers.

5. RUN E2E TESTS:
   <e2e_test_command from phase_e2e_config>
   These were written by the E2E Testing epic and should pass.

6. MANUAL VERIFICATION:
   Phase E2E flow: <phase_e2e_test description from manifest>
   Verify manually that:
   <for each phase_e2e_scenario:>
   - <scenario.name>: <scenario.description>
     Acceptance: <scenario.acceptance_criteria>

   <if any epic was classified DEGRADED in 1.3:>
   DEGRADED EPICS — additional checks required (do this before running E2E tests):
   <for each degraded epic:>
   - P<N>.E<M> (<reason_prefix>): <one-line check from the recommended-check table in 1.3.2>
   </for>
   If any degraded check reveals an unacceptable residual, refuse approval in Mode 2.
   <endif>

7. CAPTURE LEARNINGS:
   Review the E2E Testing epic's PR for integration patterns and infrastructure
   gotchas. These findings — from real services, real data, cross-component flows —
   are the most valuable learnings for future phases.

   The review_swarm_pr command has already captured lessons from the E2E epic's review
   (all findings, not just P1). After completing all phases, run /compound_improve to
   feed these lessons back into the command prompts for permanent improvement.

8. CLEANUP (after testing):
   <teardown commands if infrastructure was set up>

When testing is complete, run /eigen_continue again to confirm and start Phase <N+1>.
```

### 1.5 Update Pipeline State

Set the phase review status to `testing` with the generated recipe:
```bash
eigen-squared set-phase-review --phase <N> --status testing --testing-recipe "<generated recipe text>"
eigen-squared commit-state --message "pipeline: phase <N> review — testing"
```

---

## Mode 2: Continue to Next Phase

**Entry condition:** `state.phases[N].phase_review.status == "testing"`

### 2.1 Show Current State

**First, classify the phase**: scan every epic in `state.phases[N].plans` and re-evaluate `convergence.reason` per the 1.3 classification table (including the cap-with-residual reclassification). If ANY epic is degraded, the prompt MUST follow the **degraded path** below; otherwise the **clean path**.

#### Clean path (no degraded epics)

```
Phase <N> is in TESTING status.
Summary was presented at: <summary_presented_at>

Did manual testing pass for Phase <N>?
  1. Yes — testing passed, proceed to Phase <N+1>
  2. No — I need more time to test or fix issues
  3. Show summary again — re-display the Phase <N> summary and testing recipe
```

Default action on plain "Yes": proceed to step 2.2.

#### Degraded path (any epic in this phase is degraded)

Re-render the Degraded Epics block from 1.3.2 at the TOP of the prompt — the user must see the unresolved findings every time they consider approving:

```
=== Phase <N> Degraded Epics — VERIFICATION REQUIRED ===
<Re-render the per-epic degraded block from 1.3.2 here, including
 reason, trajectory, structured detail path, recommended check.>

These epics shipped to $EIGEN_BRANCH with KNOWN UNRESOLVED FINDINGS.
Approving this phase tells the autonomous loop to start Phase <N+1>
with these findings still in the codebase.

To approve: type the literal string  APPROVE-DEGRADED  exactly.
To decline: type anything else (or "No", "Cancel", etc.).
```

The degraded path requires **typed confirmation** — a plain "Yes" / option-1 reflex is rejected. The autonomous watchdog (which auto-launches the next phase as soon as `phase_review.status == approved`) MUST refuse advancement when the phase has degraded epics unless `phase_review.degraded_acknowledged: true` is also set on the pipeline-state record.

### 2.2 Handle User Response

**If "Show summary again"** → read `phase_review.testing_recipe` from pipeline state and re-display it. Re-ask the question.

**If "No"** (or, on degraded path, anything other than literal `APPROVE-DEGRADED`) → Print:
```
Phase <N> remains in 'testing' status.
Run /eigen_continue again when testing is complete.
```
Do NOT update pipeline state. Exit.

**If "Yes"** (clean path) OR `APPROVE-DEGRADED` (degraded path) →

On the degraded path, before continuing, write `phase_review.degraded_acknowledged: true` to the pipeline-state record (alongside the existing `phase_review.status = "approved"` flip). The watchdog uses this to verify acknowledgement; without it, the watchdog will refuse to launch Phase N+1 even if `status == "approved"`.

1. **Capture testing notes** — Ask the user:
   ```
   Before approving, would you like to record testing notes for Phase <N>?
   These notes will be read by Phase <N+1>'s bootstrap as advisory context —
   bug fixes, patterns discovered, gotchas, recommendations.

     1. Yes — I'll write notes (opens file for review)
     2. Auto-generate from git log (commits since phase completed)
     3. Skip — no notes needed
   ```

   **If "Yes"** → Create `$EIGEN_ROOT/eigen_initiative/phases/phase_<N>/testing_notes.md` with this template:
   ```markdown
   # Phase <N> Testing Notes

   ## Bugs Found & Fixed
   - <describe bugs found during testing and how they were fixed>

   ## Patterns Discovered
   - <patterns, conventions, or constraints discovered during testing>

   ## Recommendations for Phase <N+1>
   - <specific advice for the next phase based on testing experience>
   ```
   Present the template to the user and let them fill it in or edit it. Commit the file:
   ```bash
   git add $EIGEN_ROOT/eigen_initiative/phases/phase_<N>/testing_notes.md
   git commit -m "docs: phase <N> testing notes"
   ```

   **If "Auto-generate"** → Run:
   ```bash
   # Get commits since the last epic was converged (approximate: last swarm completion timestamp)
   git log --oneline --since="<last_epic_completed_at>" $EIGEN_BRANCH -- . ':!eigen_initiative'
   ```
   Format the commit list into `testing_notes.md` under a "## Changes During Testing" section. Present to the user for review/editing before saving. Commit as above.

   **If "Skip"** → proceed without creating notes.

2. Update pipeline state via CLI:
   ```bash
   eigen-squared set-phase-review --phase <N> --status approved
   eigen-squared commit-state --message "pipeline: phase <N> review — approved"
   ```

   **Note (2.7):** `set-phase-review --status approved` now verifies
   via `gh pr view --json state` that every epic PR on this phase is
   `MERGED` before accepting the approval. If any PR is still OPEN or
   CLOSED-without-merge, the CLI exits 1 and lists which PRs block the
   approval. This prevents advancing to phase N+1 on an inconsistent
   base (e.g. when a user answers "Yes" while PRs are still pending).

   If the merges were performed out-of-band (e.g. via `git merge` on
   the CLI rather than a PR merge), pass `--force-approve` to bypass
   the check. Use sparingly — the check is your safety net against
   premature approval.

3. Determine next phase:
   - Read `initiative_summary.json` for total phase count
   - If Phase N is the LAST phase → print the completion message
   - If more phases remain → print the continuation message

4. **If `$HUMAN_SWARM_FALLBACK` is NOT `true`** (autonomous mode) — verify the watchdog cron is installed:
   ```bash
   crontab -l 2>/dev/null | grep "eigen-watchdog.*$EIGEN_ROOT"
   ```
   - If found → the watchdog will detect the approval and schedule the next phase automatically.
   - If NOT found → warn and offer to install:
     ```
     WARNING: Watchdog cron not found. The next phase won't start automatically.
     Install it with:
       (crontab -l 2>/dev/null; echo "*/${WATCHDOG_INTERVAL:-10} * * * * ~/.local/bin/eigen-watchdog $EIGEN_ROOT >> $EIGEN_ROOT/.eigen/watchdog.log 2>&1") | crontab -
     ```

   **If `$HUMAN_SWARM_FALLBACK` is `true`** (manual mode) — skip the cron check.

5. Print (if more phases remain):
   If autonomous mode:
   ```
   === Phase <N> Approved — Continuing to Phase <N+1> ===

   Phase <N>: approved at <timestamp>

   The watchdog will schedule the next phase automatically.
   When Phase <N+1> finishes, run /eigen_continue again.
   ```

   If manual mode (`$HUMAN_SWARM_FALLBACK` is `true`):
   ```
   === Phase <N> Approved — Continuing to Phase <N+1> ===

   Phase <N>: approved at <timestamp>

   Run the next command manually:
     eigen-squared status    (to see what's next)
   When Phase <N+1> finishes, run /eigen_continue again.
   ```

   Print (if last phase):
   ```
   === All Phases Complete! ===

   Phase <N>: approved at <timestamp>
   The initiative is complete!

   Remaining actions:
     - Merge any remaining PRs
     - Run /compound_improve to apply lessons learned
     - Archive the eigen_initiative/ directory
   ```

---

## Important Rules

- **This command is interactive** — it always asks the user for input (confirmation, choices).
- **Two modes, same command** — the mode is determined by `phase_review.status` in pipeline state.
- **Never skips user confirmation** — the pipeline MUST NOT cross phase boundaries without human approval.
- **Merge order matters** — PRs should be merged in epic order (E1 first, E2E Testing last).
- **Testing recipe is generated, not hardcoded** — it reads from `phase_e2e_config.json` and the `language-profiles` skill.
- **Pipeline continuation** — after updating pipeline state, the watchdog detects the change and schedules the next command automatically.
- **Degraded convergence is surfaced, not blocked** — the autonomous loop ships epics that converged with `CAPPED_BY_OSCILLATION`, `P1_REGRESSION_PERSISTENT`, `DIVERGING_LOOP`, or `SWEEP_ABORTED` rather than escalating mid-phase. This command is the human gate: classify each epic in Stage 1.3 and surface the degraded ones in Stage 1.3.2 + the testing recipe so the user can refuse approval if any residual finding is unsafe to ship. Never silently treat a degraded reason as clean.
