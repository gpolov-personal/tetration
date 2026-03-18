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

3. Verify `$EIGEN_ROOT/eigen_initiative/phases/pipeline_state.json` exists. If not → **STOP.** Print:
   ```
   ERROR: No pipeline_state.json found.
   The pipeline hasn't started yet. Run /eigen_start first.
   ```

4. Load the `pipeline-state-schema` skill to understand the pipeline state format.

---

## Phase Detection

Read `$EIGEN_ROOT/eigen_initiative/phases/pipeline_state.json`.

### Find the Completed Phase

Scan `state.phases` in numeric order (phase "1", "2", etc.). For each phase N:

1. Check if `phase_review` exists for this phase:
   - If `phase_review.status == "testing"` → this phase is awaiting user confirmation → **go to Mode 2**
   - If `phase_review.status == "approved"` → this phase is done, continue scanning

2. If no `phase_review` or `phase_review.status == "not_started"`:
   - Read `$EIGEN_ROOT/eigen_initiative/phases/phase_N/epic_dag.json`
   - Check ALL epics in `epics[]` — for each epic M, check `state.phases[N].plans[M].swarm_execution.status`
   - If ALL epics have `swarm_execution.status == "converged"` (including the E2E Testing epic) → this phase just completed → **go to Mode 1**
   - If NOT all converged → skip this phase (still in progress)

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

7. CLEANUP (after testing):
   <teardown commands if infrastructure was set up>

When testing is complete, run /eigen_continue again to confirm and start Phase <N+1>.
```

### 1.5 Update Pipeline State

Update `$EIGEN_ROOT/eigen_initiative/phases/pipeline_state.json`:

Add to `state.phases[N]`:
```json
"phase_review": {
  "status": "testing",
  "summary_presented_at": "<ISO 8601>",
  "approved_at": null,
  "testing_recipe": "<generated recipe text>"
}
```

Set `updated_at` to current timestamp.

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

1. Update pipeline state:
   ```json
   "phase_review": {
     "status": "approved",
     "summary_presented_at": "<existing>",
     "approved_at": "<ISO 8601>",
     "testing_recipe": "<existing>"
   }
   ```

2. Determine next phase:
   - Read `initiative_summary.json` for total phase count
   - If Phase N is the LAST phase → **STOP.** Print:
     ```
     === All Phases Complete ===

     Phase <N> was the final phase. The initiative is complete!

     Remaining actions:
       - Merge any remaining PRs
       - Run /compound_improve to apply lessons learned
       - Archive the eigen_initiative/ directory
     ```

   - If more phases remain → schedule next phase's `/time_split`:

3. Schedule next phase via claude-tasks (if `$CLAUDE_TASKS_API` is set):
   ```bash
   NEXT_RUN=$(date -u -d '+5 minutes' +%Y-%m-%dT%H:%M:%SZ)

   # Only include telegram_webhook if $EIGEN_TELEGRAM_CHAT_ID is set and non-empty.
   curl -s -X POST $CLAUDE_TASKS_API/api/v1/tasks \
     -H "Content-Type: application/json" \
     -d '{
       "name": "eigen: time_split (Phase <N+1>)",
       "prompt": "Use the Skill tool to invoke Skill(\"eigen-squared:time_split\"). Follow all its instructions completely.",
       "cron_expr": "",
       "scheduled_at": "'$NEXT_RUN'",
       "working_dir": "'$EIGEN_ROOT'",
       "enabled": true,
       "telegram_webhook": "'$EIGEN_TELEGRAM_CHAT_ID'"
     }'
   ```

4. Print:
   ```
   === Phase <N> Approved — Continuing to Phase <N+1> ===

   Phase <N>: approved at <timestamp>
   Phase <N+1>: /time_split scheduled in 5 minutes

   The autonomous pipeline will resume and run Phase <N+1> to completion.
   When Phase <N+1> finishes, run /eigen_continue again.
   ```

   If `$CLAUDE_TASKS_API` is NOT set:
   ```
   === Phase <N> Approved ===

   Phase <N>: approved at <timestamp>

   To start Phase <N+1> manually:
     Run /time_split (it will auto-detect Phase <N+1>)

   Or set $CLAUDE_TASKS_API and run /eigen_continue again to schedule it automatically.
   ```

---

## Important Rules

- **This command is interactive** — it always asks the user for input (confirmation, choices).
- **Two modes, same command** — the mode is determined by `phase_review.status` in pipeline state.
- **Never skips user confirmation** — the pipeline MUST NOT cross phase boundaries without human approval.
- **Merge order matters** — PRs should be merged in epic wave order (Wave 1 first, E2E Testing last).
- **Testing recipe is generated, not hardcoded** — it reads from `phase_e2e_config.json` and the `language-profiles` skill.
- **5-minute delay for next phase** (not 3) — gives more time after a phase transition than between pipeline steps.
- **Works without claude-tasks** — if `$CLAUDE_TASKS_API` is not set, it still approves the phase and tells the user to run `/time_split` manually.
