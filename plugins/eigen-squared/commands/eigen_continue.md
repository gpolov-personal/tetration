---
name: eigen_continue
description: Phase transition checkpoint — summarize completed phase, provide testing recipe, and launch the next phase after user confirmation
---

# Eigen Continue — Phase Transition Checkpoint

## Your Role

You are the **phase reviewer and transition manager**. After the autonomous pipeline completes a phase (all epics including E2E Testing have converged), you:

1. Present what was built — epics, tasks, PRs, test results
2. Generate a testing recipe — how the user should manually test the phase
3. Wait for the user to confirm testing passed
4. Schedule the next phase's `/time_split` to continue the pipeline

This command has **two modes** based on the current `phase_review` state:
- **Mode 1 (Summary)**: present what was built + testing recipe → set status to `"testing"`
- **Mode 2 (Continue)**: ask if testing passed → if yes, schedule next phase → set status to `"approved"`

---

## Environment Validation

1. Read `$EIGEN_ROOT`. If not set → **STOP.** Print:
   ```
   ERROR: $EIGEN_ROOT is not set.
   Ensure .claude/settings.json has the env vars configured.
   Run /eigen_start for first-time setup.
   ```

2. Read `$EIGEN_BRANCH`. If not set → **STOP** with same pattern.

3. Verify the pipeline state is accessible via CLI:
   ```bash
   eigen-squared status --json
   ```
   If it fails or returns no state → **STOP.** Print:
   ```
   ERROR: No pipeline state found.
   The pipeline hasn't started yet. Run /eigen_start first.
   ```

---

## Phase Detection

Use the CLI to detect the next actionable phase:
```bash
eigen-squared next --json
```

### Find the Completed Phase

Parse the CLI output to determine the phase and its review status:

1. If the output indicates a phase N with `phase_review.status == "testing"` → **go to Mode 2**

2. If the output indicates a phase N that is completed (all epics converged) with `phase_review.status == "not_started"` or no `phase_review`:
   - Read `$EIGEN_ROOT/eigen_initiative/phases/phase_N/epic_dag.json` to confirm all epics are converged
   - **go to Mode 1**

3. If no phase is found → **STOP.** Print:
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
- `$EIGEN_ROOT/eigen_initiative/phases/phase_N/epic_dag.json` — all epics, execution waves
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

  Merge in epic order (Wave 1 first, E2E Testing last).
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
eigen-squared set-phase-review --phase <N> --status testing --testing-recipe "<generated recipe text or path>"
```

Then commit the state change:
```bash
eigen-squared commit-state --message "pipeline: phase <N> review — testing"
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
   ```

   Then commit the state change:
   ```bash
   eigen-squared commit-state --message "pipeline: phase <N> review — approved"
   ```

2. Determine next phase:
   - Read `initiative_summary.json` for total phase count
   - If Phase N is the LAST phase → print the completion message
   - If more phases remain → print the continuation message

3. Print (if more phases remain):
   ```
   === Phase <N> Approved — Continuing to Phase <N+1> ===

   Phase <N>: approved at <timestamp>

   The `eigen-squared schedule-next` hook will schedule the next phase
   automatically when this session ends. The autonomous pipeline will
   resume and run Phase <N+1> to completion.

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
- **Merge order matters** — PRs should be merged in epic wave order (Wave 1 first, E2E Testing last).
- **Testing recipe is generated, not hardcoded** — it reads from `phase_e2e_config.json` and the `language-profiles` skill.
- **Pipeline continuation** — the `eigen-squared schedule-next` hook fires when this session ends. It reads the pipeline state (updated by the CLI) and schedules the next command automatically. You do not need to schedule anything.
