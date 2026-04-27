# Tier 4 — PR #32 Review-Response Plan

## Premise

The PR #32 deep review surfaced 27 findings (5 BLOCKERs, 14 HIGHs, 8 critical MEDIUMs). Verification against `dev` confirmed 23 VALID, 4 PARTIAL, 0 INVALID. This plan addresses each finding with the smallest reasonable change, one commit per change, in the order that respects internal dependencies (schema → CLI → docs → cross-tier reconciliation).

The cross-cutting pattern across the findings is **inter-tier integration drift**: Tiers 1, 2, 3 each shipped clean as units, but the boundaries between them were never re-walked end-to-end. This plan re-walks them.

## Status table

| ID  | Severity | Subject                                                                          | Status | Commit |
|-----|----------|----------------------------------------------------------------------------------|--------|--------|
| B1  | BLOCKER  | Implement signature v2 migration in SwarmExecution model                         | ✅     | `58c63c1` |
| B5+M1 | BLOCKER+MEDIUM | Define threat_class enum; extend findings_history entries                  | ✅     | `1525e3a` |
| H10 | HIGH     | Add finalize-iteration parity flags                                              | ✅     | `ddb3705` |
| H9  | HIGH     | Tests for finalize-iteration verb                                                | ✅     | `1151c18` |
| B2  | BLOCKER  | Add Stage 7.1.6 baseline-capture and Stage 2.1 skip-list to review_swarm_pr.md   | ✅     | `a5ea8ad` |
| H3  | HIGH     | Promote Stage 4.0 to a real section heading                                      | ✅     | `b616a60` |
| H4  | HIGH     | M1 R-tasks set architectural_escalation flag                                     | ✅     | `728c486` |
| H1  | HIGH     | Decouple scope_files snapshot from scope_expansion_log                           | ✅     | `4fb7031` |
| H2  | HIGH     | REASSIGN re-spawns owner in current iteration                                    | ✅     | `321c8b4` |
| H5  | HIGH     | Reorder discard rules and surface count                                          | ✅     | `5c9d10d` |
| H6  | HIGH     | Reclassify Maximum review iterations as degraded when residual                   | ✅     | `50a8341` |
| H7  | HIGH     | Mode 2 typed confirmation for degraded phases                                    | ✅     | `944afa9` |
| H8  | HIGH     | Split eigen_continue M1 reference between manifest and convergence-state        | ✅     | `f9c8885` |
| H11 | HIGH     | Add M1-stale rule and document convergence ordering                              | ✅     | `19936b1` |
| H12 | HIGH     | Partition prior-iteration context for Step A vs Step B                           | ✅     | `b2fdd3c` |
| H13 | HIGH     | Add cross-worker regression handling subsection in Step B                        | ✅     | `b6aebb7` |
| H14 | HIGH     | Atomic write and schema_version for cross_epic_patterns.json                     | ✅     | `da171a5` |
| B3  | BLOCKER  | Carry forward promoted_to_prompt fields in Stage 1.6.4                           | ✅     | `3baa71f` |
| B4  | BLOCKER  | Tighten cross-epic bucket key and threshold                                      | ✅     | `ba4fc6e` |
| M3  | MEDIUM   | PR body fence pairing validation                                                 | ✅     | `b182b31` |
| M4  | MEDIUM   | Cap Stage 0.6 prior-iteration bullets                                            | ✅     | `439d40c` |
| M5  | MEDIUM   | Iter-0 file_iteration_counts initialized to 0                                    | ✅     | `c5e7ee1` |
| M6  | MEDIUM   | Mirror type-escape ban into Step A Stage 3                                       | ✅     | `f02b8c8` |
| M7  | MEDIUM   | Apply ownership audit to integrator commits                                      | ✅     | `3ca4fd2` |
| M8  | MEDIUM   | Capture project-bootstrap baseline                                               | ✅     | `0f02fce` |
| M2  | MEDIUM   | Document schema authority canonicalization                                       | ✅     | `cfc602c` |
| —   | release  | Bump plugin + CLI to 3.7.0                                                       | 🟦     | (this commit) |

Legend: ⬜ pending — 🟦 in_progress — ✅ committed — ⏸ deferred

---

## Step B1 — Signature v2 migration in SwarmExecution

**Severity:** BLOCKER. Documentation claims an idempotent v1→v2 migration; no code exists.

**Files:**
- `plugins/eigen-squared/cli/models.py` — add `signature_version: int = 2`, `legacy_signatures: dict = field(default_factory=dict)` to `SwarmExecution`; update `to_dict`/`from_dict`.
- `plugins/eigen-squared/cli/subcommands/__init__.py` — at `from_dict`-load time, if `signature_version` missing or `< 2`, recompute each `findings_history[].signatures` under v2 normalization, store originals in `legacy_signatures[<sig_v2>] = <sig_v1>`, set `signature_version = 2`. Save state once after load.
- `plugins/eigen-squared/cli/tests/test_integration.py` — load fixture with v1 state, assert v2 signatures + `legacy_signatures` populated; re-load to assert idempotent.

**Success criteria:** new test green; v1 fixture round-trips to v2 state with `legacy_signatures` populated; second load is a no-op.

**Rollback:** revert commit; loaders treat missing `signature_version` as legacy (current behavior).

---

## Step B5+M1 — threat_class enum + extended findings_history entries

**Severity:** BLOCKER (B5) + MEDIUM (M1). `threat_class` is a bucket key with no defined enum. `findings_history` entries lack the fields the cross-epic aggregator filters on.

**Files:**
- `plugins/eigen-squared/skills/pipeline-state-schema/SKILL.md` — define `THREAT_CLASS_ENUM` (closed set of ~12 values, e.g. `auth-bypass`, `injection`, `data-loss`, `race-condition`, `type-escape`, `permissions`, `concurrency`, `secrets-exposure`, `path-traversal`, `denial-of-service`, `crypto-misuse`, `other`); extend `findings_history[]` schema to `{iteration, p1, p2, p3, signatures, signature_version, entries: [{signature, category, threat_class, title_normalized}]}`.
- `plugins/eigen-squared/cli/main.py` — add `--findings-detail` JSON entries to require `category` and `threat_class` (validated against the enum).
- `plugins/eigen-squared/cli/subcommands/__init__.py` — `_ingest_findings_detail` validates threat_class; writes `entries` array.
- `plugins/eigen-squared/commands/review_swarm_pr.md` — Stage 1 review-finding template requires `threat_class: <one-of-enum>`.
- `plugins/eigen-squared/commands/compound_improve.md` — Stage 1.6 reads `entries[].threat_class` directly from `findings_history` (no longer relies on free-text title regex).

**Success criteria:** invalid threat_class rejected by CLI with non-zero exit; cross-epic aggregator finds `threat_class` on every entry; legacy entries (no `entries` array) are skipped, not crash.

**Rollback:** revert; aggregator falls back to category-only bucketing.

---

## Step H10 — finalize-iteration parity flags

**Severity:** HIGH. `cmd_finalize_iteration` lacks `--pr-url`, `--pr-number`, `--manifest-path`, `--integration-branch`. Callers needing those fields silently lose them.

**Files:**
- `plugins/eigen-squared/cli/main.py` — add the four flags to the `finalize-iteration` parser.
- `plugins/eigen-squared/cli/subcommands/__init__.py` — `cmd_finalize_iteration` propagates them in the iterating branch (mirrors `cmd_set_swarm_status`).

**Success criteria:** `finalize-iteration --status iterating --pr-url X --pr-number 1 --manifest-path Y --integration-branch Z` writes all four fields under one save.

---

## Step H9 — finalize-iteration tests

**Severity:** HIGH. Zero coverage on the central correctness claim of Tier 3.

**Files:**
- `plugins/eigen-squared/cli/tests/test_integration.py` — add 5 cases:
  1. `--status converged --reason X` flips both `sw.status` and `sw.convergence.converged` in one save.
  2. `--status iterating` only flips `sw.status`.
  3. `--status converged` without `--reason` fails before mutation.
  4. Re-run after convergence returns `EXIT_IDEMPOTENT_NOOP` without bumping `review_iteration`.
  5. With `--findings-detail` payload writing `findings_history` and `entries[]`.

---

## Step B2 — Stage 7.1.6 baseline-capture + Stage 2.1 skip-list

**Severity:** BLOCKER. `orchestrate_swarm.md` advertises behavior `review_swarm_pr.md` does not implement.

**Files:**
- `plugins/eigen-squared/commands/review_swarm_pr.md`:
  - Add `### 7.1.6 Capture last-green baseline` between `7.1.5` and `7.2`. Body: on Cases 1.1 / 2.1 only, write `swarm-manifest.json.last_green_baseline = {commit_sha, suite_result_hash, captured_at}`.
  - Add Stage 2.1 step: load `tasks[].full_suite_regressions` ∪ `iterations[].integration_regressions`; intersect signatures with `current_iteration.signatures`; mark intersected signatures as `skipped_by_regression_gate` and exclude from `current_p1` for M1 evaluation.

**Success criteria:** `grep last_green_baseline review_swarm_pr.md` returns ≥ 1 hit in Stage 7.1.6; Stage 2.1 has explicit skip-list step preceding M1 evaluation.

---

## Step H3 — Promote Stage 4.0 to a real section

**Severity:** HIGH. "Stage 4.0" is prose inside a Stage 3 message handler.

**Files:**
- `plugins/eigen-squared/commands/orchestrate_swarm.md` — add `## Stage 4.0 — Pre-final-push regression gate` heading between Stage 3 and Stage 4.1; move the existing prose into it; add Quality Checklist reference.

---

## Step H4 — M1 R-tasks set architectural_escalation flag

**Severity:** HIGH. M1 R-tasks fall through to the generic `design_decision` handler.

**Files:**
- `plugins/eigen-squared/commands/review_swarm_pr.md` Case M1 — when emitting R-tasks, also set `architectural_escalation: true` on the task entry. Add explicit autonomous-decision sub-case in `orchestrate_swarm.md` keyed on `monotonicity_violation: true` requiring ≥1 alternative and incrementing `monotonicity.m1_firings`.

---

## Step H1 — Decouple scope_files snapshot from scope_expansion_log

**Severity:** HIGH. Iter-0 lock and Tier-2/3 expansion paths deadlock.

**Files:**
- `plugins/eigen-squared/skills/pipeline-state-schema/SKILL.md` — add `scope_expansion_log[]` to swarm-manifest schema (entries: `{iteration, file, reason, decided_by, decided_at}`).
- `plugins/eigen-squared/commands/review_swarm_pr.md` Stage 0.2 — recompute `scope_files`, then UNION in all `scope_expansion_log[].file`; only fail on drift if recomputed-set ∪ log differs from snapshot.
- `plugins/eigen-squared/commands/orchestrate_swarm.md` — APPROVE INLINE / APPROVE EXPANSION write to `scope_expansion_log[]` (in addition to `task.files_owned`).

---

## Step H2 — REASSIGN re-spawns owner in current iteration

**Severity:** HIGH. REASSIGN punts to next iteration, defeating Step 5's stated purpose.

**Files:**
- `plugins/eigen-squared/commands/orchestrate_swarm.md` — change REASSIGN flow: spawn the actual owner with a fixup `[WORK]` task **in the current iteration**, run their gate, integrate. Only fall back to next-iteration queue if owner's worker budget is exhausted.

---

## Step H5 — Reorder discard rules; surface count; migrate match_key

**Files:**
- `plugins/eigen-squared/commands/review_swarm_pr.md` Stage 2.1 — apply scope-membership BEFORE sticky-discard; sticky-discard only when file also out of scope. Add `discards_suppressed_this_iteration` count to Stage 5.1 review comment.
- `plugins/eigen-squared/cli/models.py` + migration — extend v2 migration to rewrite `review_discards.json[].match_key`, preserving original in `legacy_match_key`.

---

## Step H6 — Reclassify cap-with-residual as degraded

**Files:**
- `plugins/eigen-squared/commands/eigen_continue.md` 1.3 classification table — when reason is `Maximum review iterations` AND `findings_history[-1].p1 + p2 + p3 > 0`, classify as `degraded` with reason `CAP_REACHED_WITH_RESIDUAL`. Add to Stage 6.1's "always promote to lessons" list.

---

## Step H7 — Mode 2 typed confirmation for degraded phases

**Files:**
- `plugins/eigen-squared/commands/eigen_continue.md` Stage 2.1–2.2 — when any epic in phase is degraded:
  - re-show degraded-epics block at top of prompt.
  - require typed `APPROVE-DEGRADED` confirmation (else abort).
  - record `phase_review.degraded_acknowledged: true` to pipeline state.
- Watchdog refuses advancement without the flag.

---

## Step H8 — Split eigen_continue M1 reference

**Files:**
- `plugins/eigen-squared/commands/eigen_continue.md` 1.3 / 1.3.2 — split: "trajectory in `review_convergence_state.json.monotonicity`; firing counter in `swarm-manifest.json.monotonicity.m1_firings`."

---

## Step H11 — M1-stale rule + ordering rationale

**Files:**
- `plugins/eigen-squared/commands/review_swarm_pr.md` Convergence Protocol — add explicit M1-stale rule: `m1_firings >= 2 AND p1 > 0 AND iteration >= 2` → converge with `P1_REGRESSION_PERSISTENT`, regardless of growth this iteration. Add documentation block "Rule ordering rationale" explaining why oscillation precedes M1 precedes M1-stale precedes M2.

---

## Step H12 — Partition prior-iteration context

**Files:**
- `plugins/eigen-squared/commands/orchestrate_swarm.md` Worker-spawn block at lines 441–502 — split into `PRIOR REVIEW CONTEXT (HEADERS ONLY)` and `PRIOR REVIEW CONTEXT (DETAIL)`. Step A (`design_validation_tests_swarm.md`) consumes only headers; Step B (`code_from_validation_tests_swarm.md`) consumes both.
- Add "Prior context partition" subsection in `design_validation_tests_swarm.md` Stage 2 explaining why.

---

## Step H13 — Cross-worker regression handling in Step B

**Files:**
- `plugins/eigen-squared/commands/code_from_validation_tests_swarm.md` — add Step B Stage 4 subsection:
  - `[QUESTION] type: scope_expansion` template (cross-worker regression).
  - Three terminal states: `inline_fix` / `reassigned` / `full_suite_regression_unresolved`.
  - Post-audit recovery instructions (`revert_modified` rolled files back).
- Rename worker-side `[BLOCKER] type: ownership_violation` → `[QUESTION] type: mvf_scope_expansion` to match leader's autonomous-decision key.

---

## Step H14 — Atomic write + schema_version for cross_epic_patterns.json

**Files:**
- `plugins/eigen-squared/commands/compound_improve.md` Stage 1.6/1.7 — wrap reads/writes transactionally:
  - Stage 1.6.4 writes via `tempfile + fsync + rename`.
  - Stage 1.7.4 writes back-pending FIRST (`promoted_to_prompt: false, pending_promotion: true`); applies edits; clears `pending_promotion: false, promoted_to_prompt: true` on success.
  - Add `schema_version: 1` to artifact root.
- `plugins/eigen-squared/skills/pipeline-state-schema/SKILL.md` — document the atomic-write contract.

---

## Step B3 — Carry forward promoted_to_prompt in Stage 1.6.4

**Files:**
- `plugins/eigen-squared/commands/compound_improve.md` Stage 1.6.4 — before writing, read existing `cross_epic_patterns.json`; for each new pattern whose composite key (`kind`, `category`, `threat_class`, `path_basename`, `escape_pattern`) matches an existing pattern, copy `promoted_to_prompt`, `promoted_at`, `promoted_in_version`.

---

## Step B4 — Tighten cross-epic bucket key + threshold

**Files:**
- `plugins/eigen-squared/commands/compound_improve.md` Stage 1.6.2 — bucket key uses `(category, parent_dir + basename)` (≥1 path segment). 1.6.3 promotion gate: `len(unique supporting_epics) >= 3` AND `occurrences >= 5`. Exclude epics with `convergence.reason == "CAPPED_BY_OSCILLATION"` from supporting_epics.

---

## Step M3 — Fence pairing validation

**Files:**
- `plugins/eigen-squared/commands/review_swarm_pr.md` Stage 7.1.5 — count `<!-- eigen-managed:start -->` and `<!-- eigen-managed:end -->` markers; if not exactly 0 or 1 of each, log `pr_body_fence_malformed` warning to manifest and append fresh fenced section at bottom.

---

## Step M4 — Cap Stage 0.6 prior-iteration bullets

**Files:**
- `plugins/eigen-squared/commands/review_swarm_pr.md` Stage 0.6 — cap inline list at last K=2 entries per signature AND total cap of 50 lines. Overflow stored in `review_convergence_state.json.prior_findings_overflow`. High-priority context (M1 status, escalation files, oscillation pairs) emitted BEFORE the historical list.

---

## Step M5 — Iter-0 file_iteration_counts initialized to 0

**Files:**
- `plugins/eigen-squared/commands/review_swarm_pr.md` Stage 4.1.a — initialize `file_iteration_counts` to all-zeros at iter 0 (counts review-fixup cycles only, not initial T-task commits). Document: "consecutive iterations" excludes iter-0 baseline.

---

## Step M6 — Type-escape ban in Step A Stage 3

**Files:**
- `plugins/eigen-squared/commands/design_validation_tests_swarm.md` Stage 3 — add type-escape ban block (mirrors `code_from_validation_tests_swarm.md:496-501`).
- Add `[QUESTION] type: type_escape_needed` template for Step A.

---

## Step M7 — Integrator ownership audit

**Files:**
- `plugins/eigen-squared/commands/orchestrate_swarm.md` Stage 4.5 — after integrator finishes, run `git diff --name-only HEAD~<n>..HEAD` against `shared_files` set. On out-of-scope, `revert_modified` before PR creation.

---

## Step M8 — Project-bootstrap baseline

**Files:**
- `plugins/eigen-squared/commands/bootstrap_converge.md` — capture initial green baseline at end of bootstrap (commit_sha, suite_result_hash). Write to project-level state.
- `plugins/eigen-squared/commands/orchestrate_swarm.md` — epic iter-0 inherits baseline from project-bootstrap if no prior epic CONVERGED clean baseline exists. Document the two sources.

---

## Step M2 — Schema authority canonicalization

**Files:**
- `plugins/eigen-squared/skills/pipeline-state-schema/SKILL.md` — add top-level "Schema authority" section declaring `pipeline_state.json` is the only typed file (governed by `cli/models.py`); `swarm-manifest.json`, `cross_epic_patterns.json`, `review_convergence_state.json`, `review_discards.json`, `findings_history` sidecars are loose-JSON governed by prose in this SKILL. Cross-reference each.

---

## Cross-cutting concerns

- **Version bump:** all schema additions remain backwards-compatible (legacy entries skipped, not crash). Bump to `3.7.0` (minor) at the end.
- **Test execution:** run `cli/tests/test_integration.py` after every CLI-touching commit.
- **Doc-only commits:** acceptable to commit without test runs but flag in commit body.

## Dependencies

- B5+M1 depends on B1 (signature_version field must land first).
- H10 depends on B5+M1 (parity flags are written under same atomic save).
- H9 depends on H10 (tests cover the new flags).
- B2 must land before H6/H7 (degraded surfacing relies on baseline-skip-list integration).
- H8 / H11 are independent.
- B3 depends on B4 (composite key must be tightened first).
- M3 / M4 / M5 / M6 / M7 / M8 / M2 are independent.

## Out of scope

- Full implementation of Tier 3 Step 7 (auto-revert on M1) — still deferred per Tier 3 plan.
- Refactor of `cli/subcommands/__init__.py` to extract shared finalize/complete logic (acceptable duplication; safer to inline).
- Adding dataclasses for `swarm-manifest.json` / `cross_epic_patterns.json` — explicitly opted-out via M2 (declare prose-governed).
