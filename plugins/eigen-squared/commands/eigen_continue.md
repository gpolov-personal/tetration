---
name: eigen_continue
description: Phase transition checkpoint — summarize completed phase, provide testing recipe, and launch the next phase after user confirmation
---

# Eigen Continue — Phase Transition Checkpoint

## Pipeline Context

```
eigen_start → space_split → plan_epic_converge → create_issues_from_plan_swarm
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
  - `state.phases[N].plans[M].swarm_execution` — PR url, PR number, review iterations
  - `$EIGEN_ROOT/eigen_initiative/phases/phase_N/epic_M/epic.md` — epic name, features
  - Latest review report (if exists): `$EIGEN_ROOT/eigen_initiative/phases/phase_N/epic_M/review_report_iteration_*.md`

### 1.2 Fetch PR Status

For each epic with a `swarm_execution.pr_url`, fetch current PR status:
```bash
gh pr view <pr_number> --json state,title,additions,deletions,changedFiles,mergedAt
```

### 1.3 Present Phase Summary

```
=== Phase <N> Complete — Summary ===

Phase: <N> — <phase_e2e_summary from manifest>
Status: All epics converged (including E2E Testing)

Epics Completed:
  | Epic | Name | Features | PR | Review Iterations | Status |
  |------|------|----------|----|-------------------|--------|
  | P<N>.E1 | <name> | <count> | #<pr> | <iterations> | converged |
  | P<N>.E2 | <name> | <count> | #<pr> | <iterations> | converged |
  | P<N>.E<last> | E2E Testing | 0 | #<pr> | <iterations> | converged |

PRs to Review and Merge (in order):
  1. gh pr merge <pr_1> --squash   # P<N>.E1 — <name>
  2. gh pr merge <pr_2> --squash   # P<N>.E2 — <name>
  ...
  <last>. gh pr merge <pr_last> --squash   # P<N>.E<last> — E2E Testing

  Merge in epic order (E1 first, E2E Testing last).
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
eigen-squared commit-state --message "pipeline: phase <N> review — testing" --schedule-next
```

---

## Mode 2: Continue to Next Phase

**Entry condition:** `state.phases[N].phase_review.status == "testing"`

### 2.1 Show Current State

```
Phase <N> is in TESTING status.
Summary was presented at: <summary_presented_at>

Did manual testing pass for Phase <N>?
  1. Yes — testing passed, proceed to Phase <N+1>
  2. No — I need more time to test or fix issues
  3. Show summary again — re-display the Phase <N> summary and testing recipe
```

### 2.2 Handle User Response

**If "Show summary again"** → read `phase_review.testing_recipe` from pipeline state and re-display it. Re-ask the question.

**If "No"** → Print:
```
Phase <N> remains in 'testing' status.
Run /eigen_continue again when testing is complete.
```
Do NOT update pipeline state. Exit.

**If "Yes"** →

1. Update pipeline state via CLI:
   ```bash
   eigen-squared set-phase-review --phase <N> --status approved
   eigen-squared commit-state --message "pipeline: phase <N> review — approved" --schedule-next
   ```

2. Determine next phase:
   - Read `initiative_summary.json` for total phase count
   - If Phase N is the LAST phase → print the completion message
   - If more phases remain → print the continuation message

3. Print (if more phases remain):
   ```
   === Phase <N> Approved — Continuing to Phase <N+1> ===

   Phase <N>: approved at <timestamp>

   If AUTOCHAIN=true, `eigen-squared schedule-next` has scheduled the next phase.
   The autonomous pipeline will resume and run Phase <N+1> to completion.
   If AUTOCHAIN is not enabled, run `eigen-squared schedule-next` manually to continue.

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
- **Pipeline continuation** — after updating pipeline state, `eigen-squared schedule-next` is called to schedule the next command (only when `AUTOCHAIN=true`). It reads the pipeline state (updated by the CLI) and schedules the next command automatically. If `AUTOCHAIN` is not enabled, the pipeline stops and requires manual invocation.
