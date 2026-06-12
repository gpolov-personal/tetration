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
- Loop continues until all P1 and P2 findings are resolved (`CLEAN`) or a hard cap of 3 review iterations is reached (`CAP_REACHED_WITH_RESIDUAL`, merged as degraded with residuals documented). Residual P3 findings do not block convergence — they are recorded in `pipeline_state.json` for downstream visibility.

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

Load the prior **convergence state ledger** at `eigen_initiative/phases/phase_<phase>/epic_<epic>/review_convergence_state.json` (default `{ "epic_id": "P<N>.E<M>", "iterations": [] }` if absent). Each entry has the structure:

```json
{
  "iteration": <int>,
  "agents_used": ["<agent_id>", "..."],
  "findings": [
    {
      "id": "F<n>",
      "sig": "<sha1 of normalized_file|category|normalized_title>",
      "file": "<path>",
      "symbol": "<symbol or '<file-level>'>",
      "category": "<category>",
      "severity": "P1|P2|P3",
      "title": "<finding title>"
    }
  ]
}
```

The `sig` formula does NOT include `symbol`. Sig stability across iterations is load-bearing for Stage 2.2's set operations (Persistent / Regressed / New) — adding `symbol` to the sig would invalidate every cross-iteration comparison. `symbol` is a separate human-readable grouping field on each entry.

This ledger is the source of truth for cross-iteration finding tracking. Stage 2.2's set operations read from it; Stage 2.4 appends to it. `findings_history` (the CLI mirror in `pipeline_state.json`) is still populated every iteration — `compound_improve`'s cross-epic aggregator depends on it.

If a previous review report exists (`review_report_iteration_<review_iteration - 1>.md`), read it for human-readable cross-iteration narrative — but the **machine-readable** comparison is computed from `review_convergence_state.json`, not from re-parsing the markdown.

### Convergence Decision (after collecting findings, Stage 3)

This loop used to carry an elaborate anti-oscillation state machine (a `(file, symbol, category)` oscillation circuit-breaker, monotonicity rules M1/M1-stale/M2, and a one-shot P3 sweep with auto-revert). That machinery was insurance against **weak models that ping-ponged findings**; a strong model (Opus-class) fixes findings correctly, so a hard `<= 3`-iteration cap with residual disclosure is sufficient and far cheaper. All of it is gone — replaced by the simple bounded loop below.

`CAP = 3`. Evaluate the rules below **in order**, stopping at the first match (`p1`, `p2`, `p3` are this iteration's kept-finding counts from Stage 2.1):

1. **If `p1 == 0` AND `p2 == 0` → CONVERGED**, reason `"CLEAN"`.
   - Any residual P3 findings are **disclosed** in the PR review and the report but do NOT block convergence.
   - Skip Stage 4 (no fixup tasks). Merge in Stage 7.2 with the residual P3 list surfaced.

2. **Else if `review_iteration >= CAP` (CAP = 3) → CONVERGED**, reason `"CAP_REACHED_WITH_RESIDUAL"`.
   - The residual P1/P2/P3 counts are disclosed in the PR body, the report, and the lessons.
   - Skip Stage 4 (more fixups will not help within the cap). Merge in Stage 7.2 with residuals documented.
   - This is a **degraded** convergence — `eigen_continue.md` recognizes `CAP_REACHED_WITH_RESIDUAL` and requires the human to type `APPROVE-DEGRADED` at the phase checkpoint. Reuse this exact reason string so that gate keeps working unchanged.

3. **Else (`p1 > 0` OR `p2 > 0`, and `review_iteration < CAP`) → CONTINUE**, status `"iterating"`.
   - Stage 4 generates fixup tasks for the **P1 + P2 findings only**.
   - P3 findings ride along as disclosed `residual_p3` (file/severity/category/title in `swarm-manifest.json.residual_p3`) — they are **never** fixed in a dedicated sweep.
   - Hand back to `orchestrate_swarm` via the manifest; finalize the iteration as `iterating`.
   - Rationale: "<p1+p2> blocking findings remain (P1: <p1>, P2: <p2>); <p3> P3 carried as residual."

The convergence-reason vocabulary is intentionally minimal: `"CLEAN"` (case 1) and `"CAP_REACHED_WITH_RESIDUAL"` (case 2). No other reason strings are produced.

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
3. Build `scope_files` as an **immutable iter-0 snapshot** — union of:
   - `files_owned` and `test_files_owned` of the **original T-tasks only** (tasks whose `id` matches `P<N>.E<M>.T<K>` — exclude R-tasks and the integration task),
   - `shared_files`,
   - `e2e_config.e2e_test_dir` files.

   On iteration 0, write `scope_files` to `swarm-manifest.json.scope_files_snapshot` (a frozen array). On iteration ≥ 1, recompute `scope_files` the same way (from the same T-tasks) and check it against the snapshot UNIONED with `swarm-manifest.json.scope_expansion_log[].file` (entries written by leader-approved expansions — see Tier-3 ownership audit and Stage 4.0 regression gate). The check semantics:
   - If `recomputed ⊆ snapshot ∪ logged_expansions` → OK. Use `recomputed` as `scope_files` for this iteration's filtering.
   - If `recomputed` includes a file in NEITHER `snapshot` NOR `logged_expansions` → **STOP** with `ERROR: scope_files drift detected at iteration <N> — file <X> appeared in T-task ownership but has no expansion ledger entry.` This catches T-task ownership mutations that bypassed the leader's approval ladder; legitimate Tier-3 expansions are recorded in `scope_expansion_log[]` and flow through cleanly.

   `scope_expansion_log[]` is append-only. Each entry: `{iteration: <int>, file: "<POSIX-relative>", reason: "ownership_audit_inline|regression_gate_expansion|...", decided_by: "leader_autonomous|user", decided_at: "<ISO 8601>"}`. Written by `orchestrate_swarm`'s APPROVE INLINE / APPROVE EXPANSION / mvf_scope_expansion handlers in the same atomic save as the corresponding `task.files_owned` mutation. Decoupling the expansion ledger from the snapshot is what lets Tier-1's iter-0 lock and Tier-2/3's mid-iteration expansion paths coexist without deadlock.

4. **Load prior out-of-scope discards** (iteration ≥ 1 only). Read `eigen_initiative/phases/phase_<phase>/epic_<epic>/review_discards.json` if it exists. The file lists every finding previously dropped as out-of-scope, with the iteration that dropped it. These are re-applied deterministically in Stage 2.1.

### 0.3 Read Epic and Plan Context

1. Read the epic file — title, description, acceptance criteria.
2. Read the plan file for architectural context.
3. List existing task files to detect previous review tasks (avoid duplicates).

### 0.4 Detect Tech Stack

1. Detect project languages using the `language-profiles` skill.
2. Look up relevant review skills from the Stack-Specific Skills table.
3. Set `<frontend_in_scope>` — true iff `scope_files` (§0.2) contains any `*.tsx`, `*.jsx`, `*.vue`, `*.svelte`, `*.astro`, `*.html`, or `*.css` file, or any `*.ts`/`*.js` file under a `components/`, `pages/`, `views/`, or `ui/` directory. False otherwise.
4. Set `<impeccable_available>` and `<impeccable_detect_path>` — best-effort probe for the **optional, external** impeccable design skill. It is available only if its detector entry script resolves at one of `~/.claude/skills/impeccable/scripts/detect.mjs` or `.claude/skills/impeccable/scripts/detect.mjs` (or the path reported for an installed `impeccable` skill) AND `node` is on PATH. If it does not resolve, set `<impeccable_available>` false and continue. **impeccable is never required — never STOP on its absence, and never reference its non-detector (interactive) flows.**
5. Set `<codegraph_available>` — best-effort probe for the **optional, external** CodeGraph index (code-intelligence; see `skills/codegraph/SKILL.md`). True iff `codegraph` is on PATH and `$EIGEN_ROOT/.codegraph/` exists (`codegraph status -j` → `"initialized": true`). If it does not resolve, set false and continue. **Never required — never STOP on its absence.**

### 0.5 Fetch PR Diff

1. Fetch: `gh pr diff <pr_number> --color never`
2. Filter to scope files only. If scoped diff is empty → **STOP.**

### 0.5.5 Refresh CodeGraph Index (optional)

Skip entirely if `<codegraph_available>` is false. Otherwise ensure the index reflects the merged code now on the integration branch before §0.6 / §1.2 query it for impact analysis. This command runs as a fresh session, so CodeGraph's connect-time catch-up normally reconciles the index automatically — just run `codegraph status "$EIGEN_ROOT"` and, **only if** it reports a `Pending sync` section (the watcher was off during the swarm — headless / `CODEGRAPH_NO_DAEMON` / WSL2 `/mnt`), run `codegraph sync "$EIGEN_ROOT"`. Do not sync otherwise — over-syncing is wasted work. See `skills/codegraph/SKILL.md`.

### 0.6 Build Scope Context Document

Assemble for all review agents:
- Epic context and acceptance criteria
- What each task built (id, summary, files)
- Files in scope, shared files
- PR metadata
- **CRITICAL: What is OUT OF SCOPE** — files not listed, missing functionality not in acceptance criteria
- **CodeGraph blast-radius summary (only if `<codegraph_available>`):** for the symbols changed in the scoped diff, precompute a dependency summary with `codegraph_impact` (blast radius) and `codegraph_callers`/`codegraph_callees` (out-of-diff dependents), and include it here once so every reviewer sees who the change can break without re-deriving it via grep. Omit this bullet entirely when CodeGraph is absent. See `skills/codegraph/SKILL.md`.
- **Previously-raised findings — DO NOT re-raise unless the fix is demonstrably wrong** (iteration ≥ 1 only). Populate from `review_convergence_state.json`. **Bounded inline list** — without a cap, this section grew linearly with iteration count (~20 findings/iter × 5 iterations = 100+ bullets in every reviewer prompt by iter 5). Apply two caps in order:

  1. **Per-signature cap of K=2 entries**: for each unique signature, include only the most-recent 2 occurrences. Older occurrences are still in `review_convergence_state.json` and reachable via the read-the-ledger fallback below.
  2. **Total inline cap of 50 lines**: after the per-signature cap, if the bullet list still exceeds 50 lines, truncate to the most-recent 50 (sorted descending by `last_seen_iteration`, then by severity).

  **Priority ordering — high-priority context emitted FIRST**: before the bounded prior-finding list, emit the current `review_iteration` and the cap (3), so reviewers know how many passes remain before a `CAP_REACHED_WITH_RESIDUAL` merge. This guarantees the load-bearing context is at the top of the prompt where it cannot be truncated by downstream prompt-size limits.

  Findings dropped by the inline caps are recorded in `review_convergence_state.json.prior_findings_overflow` (per-iteration count) for observability — `<count> additional prior findings filtered out — see review_convergence_state.json`.

  For every finding INCLUDED in the inline list:
  ```
  - id: <last-seen iteration>.<F-id>   signature: <sha1>
    severity: <P1|P2|P3>   file: <path>   category: <category>
    title: <title>
    last_seen_iteration: <iteration>   status: <addressed | persistent | regressed>
  ```
  Status is computed by Stage 2.2's set operations once findings are collected; for the **context document** (which is built before findings are collected), include only `last_seen_iteration` and let Stage 2.2 update the status downstream.

  Agents reviewing this PR are instructed:

  > A finding listed above was raised in a prior review pass. Do **not** re-raise the same signature unless the fix is demonstrably wrong (i.e. the fix is wrong on its own merits, not just incomplete). If you re-raise:
  > 1. **Cite the prior ID** explicitly in your in-scope justification (e.g., `re-raising iter1.F3 — the fix introduced a new SQL injection vector via OFFSET parameters`).
  > 2. **Articulate why the prior fix is wrong**, not just "this still seems risky".
  > 3. If you cannot articulate (1) and (2), **downgrade the finding to P3** — the existence of a prior fix is itself evidence the maintainers considered the issue, so weak re-raises do not warrant blocking severity.
  >
  > The convergence loop is bounded at 3 iterations (Convergence Protocol). A weak re-raise that keeps P1/P2 non-zero pushes the epic toward a `CAP_REACHED_WITH_RESIDUAL` merge of unresolved findings. Re-raise judiciously.

  If `review_convergence_state.json` is missing or its `iterations` array is empty (e.g., epic started before Step 4 landed, or this is iteration 0), this section is omitted. Stage 2.2 falls back to "all findings are New".

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
  - `design-critique` — **only if `<frontend_in_scope>` AND `<impeccable_available>` (both from §0.4)**. A detector-backed UI reviewer (mechanism in §1.2 "Design / UI checks") that runs impeccable's anti-pattern detector over the in-scope frontend files. If either gate is false, omit it silently — it is an optional enhancement, never required, and its absence must not change any other behavior. Because the roster is locked at iteration 0, this decision is frozen for the epic: absent at iteration 0 → never added later; present → reused verbatim even if impeccable later disappears (the §1.2 checklist makes that case a no-op).

  Persist the resolved roster to the iteration-0 review report's YAML front-matter (Stage 5.2) under the `agents_used` key so subsequent iterations can read it back verbatim.

**If `review_iteration >= 1`** — reuse the iter-0 roster:

  Read `eigen_initiative/phases/phase_<phase>/epic_<epic>/review_report_iteration_0.md` from the integration branch and parse its YAML front-matter. Use `agents_used` verbatim. Ignore the conditional triggers (diff size, performance-mention) entirely — even if the diff has grown past 500 lines or new acceptance criteria mention performance, **do not add agents**.

  If the iter-0 report is missing or its front-matter does not contain an `agents_used` list, **STOP** with:

  ```
  ERROR: review_report_iteration_0.md not found on integration branch (or missing agents_used front-matter) — agent roster cannot be reconstructed for iteration <N>.
  ```

  Do not silently recompute the roster. A missing iter-0 report indicates a force-push regression of the integration branch and must be surfaced to the operator.

### 1.2 Spawn All in Parallel

Each agent receives the scope context and scoped diff. Each returns findings with: severity, category, **symbol** (the specific declaration the finding targets — the type / function / class / method / route name; for findings that span the whole file or target non-code artifacts like `eslint.config.mjs`, JSON config, package.json, or markdown, use the literal string `"<file-level>"`; never omit this field, never emit `null`), in-scope justification, location, proposed fix, effort.

**Symbol convention**: use the bare declaration name (`SchemaEnum`, `executeSql`); for methods, use `Class.method` (`BackendProvider.executeSql`); never include parameter lists, signatures, or modifiers; if a finding genuinely spans multiple declarations, pick the most specific one and mention the others in `title`.

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

**Design / UI checks** (only the gated `design-critique` reviewer, when present in the roster):
- Mechanism is **deterministic and non-interactive**: run impeccable's detector over the in-scope frontend files only — `node <impeccable_detect_path> --json <frontend scope_files>` (source mode: no network, no dev server, no browser). Do **NOT** invoke impeccable's interactive flows (`init`, the `PRODUCT.md` setup gate, `live` mode) — they stall headless swarm runs. [D1]
- Report **only detector-anchored, objective findings**: accessibility and WCAG contrast failures, missing semantic HTML / skipped heading levels, broken or placeholder images, and the detector's documented anti-patterns — each with a concrete `file:line`. Map each hit to the standard finding schema (§1.2); use the offending element/selector as `symbol`, or `"<file-level>"` when the hit spans the file. [D2]
- Severity mapping (conservative, so design findings never block on taste): accessibility / contrast / broken-image hits → **P2**; all other anti-pattern (slop/quality) hits → **P3**. Never emit P1 from this reviewer. [D3]
- **Do NOT raise subjective polish** ("too bland", "make it bolder", "add personality"). Subjective findings have no stable pass condition and would keep P1/P2 non-zero across iterations, pushing the epic toward a `CAP_REACHED_WITH_RESIDUAL` merge. Objective, location-anchored findings only. [D4]
- If the detector is missing at spawn time, errors, or returns no hits, contribute **zero findings** and do not block — the reviewer degrades cleanly to a no-op. [D5]

**Impact & dependency checks** (all reviewers, only when `<codegraph_available>` — augments, never replaces, normal review):
- For each symbol changed in the scoped diff, use `codegraph_impact` (blast radius) and `codegraph_callers` to find **out-of-diff** dependents the change could break, instead of reasoning about ripple effects from grep alone. This is most valuable for `security-sentinel`, `architecture-strategist`, and `data-integrity-guardian`. The §0.6 scope doc already carries a precomputed summary — deepen it per finding rather than re-deriving it. [C1]
- Trust CodeGraph results (full AST parse) — do not re-verify them with grep. Treat returned source as already read. Do NOT run `codegraph sync` (handled in §0.5.5). [C2]
- If `<codegraph_available>` is false, this block is a **no-op** — review proceeds exactly as before with grep/Read. [C3]

Wait for ALL agents.

### 1.3 Deterministic Type-Escape Detector

Run alongside the agents (synchronously in main thread — it's a regex scan, not an agent). The detector synthesizes findings that join the agent pool before Stage 2.1 dedup, so they participate in scope filtering, signature dedup, and the ledger like any other finding.

#### Why deterministic

Type escapes (`as any`, `@ts-ignore`, bare `# type: ignore`) are a common source of cross-iteration P1/P2 churn in real codebases (per the leader's `type_escape_needed` rationale at `orchestrate_swarm.md`). A regex catches them with zero false negatives on the unambiguous patterns and runs in milliseconds — strictly better than waiting for an agent to maybe spot them.

#### Scan window

Only scan **added** lines in the iteration's diff (lines starting with a single `+`, ignoring `+++` headers). Pre-existing escapes in unmodified code are NOT flagged — this avoids flooding day-1 reviews with backlog work.

```bash
# Iteration boundary: the prior review report's addition commit (or merge-base on iter 0).
prior_report="eigen_initiative/phases/phase_<phase>/epic_<epic>/review_report_iteration_<N-1>.md"
if [ -f "$prior_report" ]; then
    iter_base=$(git log -1 --diff-filter=A --format=%H -- "$prior_report")
else
    iter_base=$(git merge-base "$EIGEN_BRANCH" HEAD)
fi

# Scan added lines only, with file + line context. Restrict to scope_files.
git diff -U0 "${iter_base}..HEAD" -- '*.ts' '*.tsx' '*.js' '*.jsx' '*.py' '*.pyi' '*.go'
```

Parse the unified diff: track the current file and post-image line number from each `@@ ... +<n>,<count> @@` hunk header; for each `+` line (non-header), test against the pattern set below.

#### Pattern set (high-signal, low false-positive)

| Language | Pattern (regex, applied to the line content with leading `+` stripped) | Title |
|---|---|---|
| TS / JS | `\bas\s+any\b` | Unauthorized type escape: `as any` |
| TS / JS | `\bas\s+unknown\s+as\s+\w` | Unauthorized type escape: `as unknown as <T>` chained cast |
| TS / JS | `(?://\|/\*)\s*@ts-ignore\b` | Unauthorized type escape: `@ts-ignore` |
| TS / JS | `(?://\|/\*)\s*@ts-expect-error\b` | Unauthorized type escape: `@ts-expect-error` |
| TS / JS | `(?://\|/\*)\s*@ts-nocheck\b` | Unauthorized type escape: `@ts-nocheck` |
| Python | `\btyping\.cast\(\s*Any\b` | Unauthorized type escape: `typing.cast(Any, ...)` |
| Python | `#\s*type:\s*ignore\s*$` (no `[error_code]` suffix) | Unauthorized type escape: bare `# type: ignore` (no error-code suffix) |
| Python | `#\s*pyright:\s*ignore\s*(?:$\|#)` (no `[rule]` suffix) | Unauthorized type escape: bare `# pyright: ignore` (no rule suffix) |

Patterns deliberately **excluded** (high false-positive rate without AST analysis): broad Python `Any` parameter types, Go `interface{}` parameters, `getattr` private access, monkey-patching detection. Those remain enforceable via worker discipline (the rules in `orchestrate_swarm` worker spawn) and review-agent judgment.

#### Allowlist — leader-approved escapes

Skip a match when the line **immediately above** (within 3 lines, after stripping diff metadata) contains the literal `REVIEWER: type-escape approved` substring. This is the convention the leader's `type_escape_needed` autonomous handler instructs the worker to write. Format: `// REVIEWER: type-escape approved by leader, see [DECISION-<id>]` (or `# REVIEWER: ...` for Python).

For each unauthorized match, synthesize a finding with the existing scope-context structure:

```json
{
  "file": "<path>",
  "line": <post-image line number>,
  "symbol": "<file-level>",
  "category": "type-safety",
  "severity": "P1",
  "agent": "type-escape-detector",
  "title": "<title from pattern table>",
  "in_scope_justification": "Type-safety hard rule (orchestrate_swarm spawn prompt); unauthorized escape introduced in this iteration's diff.",
  "proposed_fix": "Refactor the surrounding code so the type checker is satisfied legitimately, or raise [QUESTION] type: type_escape_needed to team-lead and obtain a [DECISION-AUTONOMOUS] referenced by an inline `// REVIEWER: type-escape approved` comment.",
  "effort": "minutes-to-hours"
}
```

The detector emits `symbol: "<file-level>"` because the regex operates on diff lines without AST context — it has no access to the enclosing declaration's name.

Append the synthesized findings to the agent results pool **before** Stage 2.1 begins. Stage 2.1's scope filter, signature computation, prior-discard match, and dedup apply unchanged — the detector's findings are just one more "agent's" input. The signature scheme produces deterministic IDs across iterations, so a re-introduced same-line escape is a Persistent finding.

#### What the detector does NOT do

- It does not reject the diff or block the loop — it only adds findings. Convergence still depends on Stage 3's case dispatch.
- It does not heuristically classify "good" vs "bad" uses of an escape. The regex is the policy. To allow an escape, the leader must say so via the inline comment.
- It does not run on synthetic or generated code (file globs above are deliberately conservative). Build outputs, vendored dependencies, and lockfiles are out of scope by `scope_files` enforcement in Stage 2.1.

---

## Stage 2: Collect, Filter, and Triage

### 2.1 Scope Filter

For each finding, in order:

1. **Compute the signature (algorithm v2).** The signature is `sha1("<normalized_file_path>|<category>|<normalized_title>")` (hex digest), where:
   - `normalized_file_path` is the POSIX-style relative path with case preserved,
   - `category` is the lowercase short category (`security`, `data-integrity`, `test-quality`, ...),
   - `normalized_title` is the title under v2 normalization (rules below).

   The pre-signature triple `(normalized_file_path, category, normalized_title)` is also the **match_key** used by the prior-discard rule below. The same scheme is used by `swarm_execution.findings_history` — both artifacts agree iteration-for-iteration.

   **v2 title normalization** (apply in order):
   1. Casefold (Unicode-safe lowercase via `str.casefold()`, not `str.lower()`).
   2. Strip leading/trailing whitespace and trailing punctuation (`.,;:!?`).
   3. Collapse internal whitespace runs to a single space.
   4. Tokenize on whitespace, drop tokens in the stopword set: `{is, are, was, were, be, the, a, an, of, for, in, on, at, to, with, without, missing, present}` — chosen because they appear in title paraphrases without changing the finding's meaning.
   5. Re-join survivors with a single space.

   **Token order is preserved.** Sorting tokens alphabetically would collapse semantically distinct titles (e.g., "deletion auth required" vs. "auth deletion required"); the dedup-quality gain is modest, the false-merge risk is real.

   **Signature versioning.** `pipeline_state.json.swarm_execution.signature_version` (default `2`) records the algorithm in use. Loaders that encounter `signature_version < 2` (legacy state from before this step landed) re-compute every entry's signature under v2 rules on the next read and write back. The pre-v2 signature is preserved in a `legacy_signatures: ["<old_sig>", ...]` array on each finding entry so retroactive comparisons against old reports still match. Migration is idempotent — safe to re-run.

2. **Regression-gate skip-list (iteration ≥ 1)**: load the union of (a) `swarm-manifest.json.tasks[].full_suite_regressions` (per-worker gate, Step 5) and (b) `swarm-manifest.json.iterations[<prev>].integration_regressions` (Stage 4.0 pre-final-push gate). Mark each signature in this union as `skipped_by_regression_gate` for THIS finding pass: such signatures are **excluded** from the P1/P2 counts that drive the Stage 3 convergence decision (they do not block or extend the loop). The findings themselves are still reported in the per-iteration report (Stage 5.1) as informational, with a `[gated-by: full-suite]` prefix, so reviewers can audit; they just do not contribute to convergence-loop math because the regression gate already handled them in-iteration. Surface a `regression_gate_skipped: <count>` line in the Stage 5.1 review comment for observability.

3. **Scope membership**: file in `scope_files`? If not → drop with reason `file not in scope_files (T-task ownership)`. Scope membership is evaluated **before** the prior-discard rule below; without this ordering, a finding discarded at iter 1 because its file was momentarily out of scope would silently drop at iter 5 even if the user has since explicitly expanded scope.

4. **Prior-discard match (iteration ≥ 1)**: if the finding's match_key matches any entry in `review_discards.json` from a prior iteration AND the file is still out of `scope_files` (i.e. the discard reason still applies), **drop** the finding with reason `previously discarded in iter <K> (<original_reason>)`. If the file is now back in scope (because step 3 admitted it via the expansion log), do NOT sticky-drop — re-evaluate the finding under the current rules. Surface a `discards_suppressed_this_iteration: <count>` line in the Stage 5.1 review comment for observability (count of findings whose match_key was in `review_discards.json` but whose scope is now re-admitted, so the user can see the dedup churn).

   **v2 migration extends to match_key.** When `swarm-manifest.json.review_discards.json` is loaded with `signature_version < 2` (or absent), the v2 normalization rules ALSO rewrite each entry's `match_key` under the same algorithm; the original string is preserved in `legacy_match_key` for audit. This keeps discards sticky across the migration boundary — without it, a v1 match_key would silently fail to match v2 finding signatures and the discard would un-stick.

5. **Justification quality**: in-scope justification references a real acceptance criterion? If vague → downgrade to P3 (do not drop).

6. **Deduplicate** across agents — **by signature**, not by free-text title. Findings sharing a signature are merged (keep the highest severity; concatenate the agent list).

Every finding dropped by rules 1 or 2 is appended (with its match key, severity, category, agent, title, reason, and current `iteration`) to a sidecar:

```
eigen_initiative/phases/phase_<phase>/epic_<epic>/review_discards.json
```

Schema:

```json
{
  "epic_id": "P<N>.E<M>",
  "discards": [
    {
      "iteration": 0,
      "file": "server/ai/tool-dispatcher.ts",
      "severity": "P3",
      "category": "performance",
      "agent": "performance-oracle",
      "title": "default 10s timeout vs 60s confirmation",
      "match_key": "<normalized_file>|<category>|<normalized_title>",
      "reason": "file not in scope_files (T-task ownership)"
    }
  ]
}
```

Append-only — never rewrite existing entries. The file is committed to the integration branch in Stage 4.6 (Continue case, alongside the new fixup tasks) or, on any CONVERGED case, in Stage 5.2 alongside the report.

### 2.2 Cross-Iteration Comparison (iteration 1+)

Compute signature-set differences against `review_convergence_state.json`. Let:
- `current` = set of signatures kept after Stage 2.1 (this iteration).
- `prev` = set of signatures from the most recent prior `iterations[]` entry (empty on iter 0 / first run).
- `ever_seen_pre_prev` = union of signatures across all `iterations[]` entries strictly before the immediately-prior one.

Then:
- **Addressed**: `prev \ current` — present in prior iteration, gone now.
- **Persistent**: `prev ∩ current` — present in both.
- **Regressed**: `(ever_seen_pre_prev \ prev) ∩ current` — fixed at some earlier point, then reappeared.
- **New**: `current \ (prev ∪ ever_seen_pre_prev)` — never seen before this iteration.

For the report (Stage 5.2) and the PR comment (Stage 5.1), each bucket lists **finding IDs from the iteration where the signature was last seen** alongside the current iteration's IDs (e.g., `Persistent: [iter1.F3 → iter2.F2]`). This lets a human reader trace the trajectory of a single finding across iterations without re-parsing markdown.

If `review_convergence_state.json.iterations` is empty (first review), this stage is a no-op except for setting all current findings as "New".

### 2.3 Triage Summary

Print:
```
Review Findings (Iteration <N>):
  Total raw: <N>, After scope filter: <M>
  P1: <x>, P2: <y>, P3: <z>
  <if iteration 1+:>
  vs. Previous: <addressed> fixed, <persistent> remaining, <regressed> regressed, <new> new
  Signature trajectory: <persistent_count> signatures shared with iter <N-1>; <regressed_count> regressed from earlier iterations.
```

### 2.4 Append to Convergence State Ledger

After Stage 2.2 has computed buckets, append the current iteration to `review_convergence_state.json`:

```json
{
  "iteration": <current_iteration>,
  "agents_used": [<from Stage 1.1's resolved roster>],
  "findings": [
    { "id": "F<n>", "sig": "<sha1>", "file": "<path>", "symbol": "<symbol or '<file-level>'>", "category": "<category>", "severity": "P1|P2|P3", "title": "<title>" }
  ]
}
```

`F<n>` (in `findings`) is a 1-indexed local ID assigned in stable order (e.g., by signature lex order so iter-N's F1 is reproducible). Persist the **kept** post-filter findings only; discards live in `review_discards.json` instead.

The file is committed to the integration branch:
- In the Continue case: in Stage 4.6 alongside the new fixup tasks.
- In any CONVERGED case (`CLEAN` / `CAP_REACHED_WITH_RESIDUAL`): in Stage 5.2 alongside the report.

Append-only — never rewrite existing iteration entries (idempotent retry replaces only the entry for the current iteration, mirroring the CLI's `findings_history` semantics).

---

## Stage 3: Convergence Decision

Apply the bounded loop in the Convergence Protocol section against the just-collected findings and `review_iteration`.

The decision dispatches Stage 4's behavior:

| Case | Decision | Stage 4 behavior |
|---|---|---|
| **Clean** (`p1 == 0` AND `p2 == 0`) | **CONVERGED — `CLEAN`** | Skip Stage 4 entirely; proceed to Stage 5. Residual P3 (if any) disclosed, not blocking. |
| **Cap reached** (`p1 > 0 OR p2 > 0`, and `review_iteration >= 3`) | **CONVERGED — `CAP_REACHED_WITH_RESIDUAL`** | Skip Stage 4; proceed to Stage 5. Residual P1/P2/P3 counts disclosed; merges as degraded convergence. |
| **Continue** (`p1 > 0 OR p2 > 0`, and `review_iteration < 3`) | **CONTINUE — iterating** | Stage 4 generates fixup tasks for P1+P2 only. P3s recorded in `residual_p3`. |

`CAP = 3`. P3 findings never produce fixup tasks — they ride along as disclosed residuals.

---

## Stage 4: Create Fixup Tasks (only if not converged)

Stage 4 runs only in the **Continue** case (`p1 > 0 OR p2 > 0`, `review_iteration < 3`). Run Stage 4.1–4.7 over **P1 + P2 findings only**. Record P3s in `residual_p3` (they never produce a fixup task).

### 4.1 Derive File Ownership

For each selected P1/P2 finding:
- Look up which manifest task owns the finding's file → `original_task_id`
- Determine `files_owned` and `test_files_owned` for the fix
- If file is in `shared_files` → integration finding (final wave)

### 4.2 Build Dependency Graph and Assign Waves

- Serialize findings that need the same file
- **If `<codegraph_available>`**: also serialize findings whose files sit in each other's blast radius (caller↔callee per `codegraph_impact`/`codegraph_callees`), not just findings touching the identical file — this catches cross-file fixup collisions the file-overlap heuristic misses. Fall back to file-overlap only when CodeGraph is absent. See `skills/codegraph/SKILL.md`.
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
3. Append new execution waves with `"type": "review-fixup"`.
4. Update `e2e_config.e2e_scenarios` for P1 findings.
5. Refresh `swarm-manifest.json.residual_p3` with the current P3 findings (replace, don't append) so downstream consumers see the live residual list.

### 4.6 Commit and Push

The `git add` covers the fixup task files, the manifest update, `review_discards.json` (any new discards appended in Stage 2.1), and `review_convergence_state.json` (the iteration entry appended in Stage 2.4).

```bash
git add eigen_initiative/phases/phase_N/epic_M/
git commit -m "chore: review iteration <N> — <M> fixup tasks for P<N>.E<M>"
git push origin feat/P<N>.E<M>
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

The review body must include:
- **Findings table** — every finding raised this iteration (P1, P2, P3). Show in-line locations.
- **Residual P3 list** — the live `swarm-manifest.json.residual_p3` array, regardless of which case fired. P3 findings are always disclosed even when no fixup task is created for them.
- **Convergence status** — CONVERGED / CONTINUE — with the reason: `CLEAN` (converged clean), `CAP_REACHED_WITH_RESIDUAL` (converged at the cap with residual P1/P2/P3), or `iterating` (Continue).
- **Residual disclosure line** (only when converging with `CAP_REACHED_WITH_RESIDUAL`):
  - `CAP_REACHED_WITH_RESIDUAL: max review iterations (3) reached — residual P1: <x>, P2: <y>, P3: <z> merged and documented. Requires APPROVE-DEGRADED at the phase checkpoint.`
- **Next steps** — directives for the watchdog: "run /orchestrate_swarm" (Continue) or "merging now" (CONVERGED, either reason).

Use `event: "COMMENT"`.

If no findings (converged clean, `CLEAN`): post a simple approval comment.

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
- **Discards summary** — count of findings dropped by Stage 2.1 in this iteration, broken down by reason (`previously discarded in iter K` vs. `file not in scope_files`). Reference `review_discards.json` for the full list.
- Cross-iteration comparison (if iteration 2+)
- Convergence status (`CLEAN`, `CAP_REACHED_WITH_RESIDUAL`, or `iterating`)
- Manifest update summary
- **Residual disclosure** (only when converging with `CAP_REACHED_WITH_RESIDUAL`): the residual P1/P2/P3 counts merged at the cap, noting the epic requires `APPROVE-DEGRADED` at the phase checkpoint.

If `review_discards.json` or `review_convergence_state.json` was modified this iteration and has not yet been committed (any CONVERGED case, where Stage 4 is skipped), include them in the same `git add` as the report so the ledgers never lag behind the report.

Commit:
```bash
git add eigen_initiative/phases/phase_N/epic_M/review_report_iteration_*.md
git commit -m "chore: review report iteration <N> for P<N>.E<M>"
git push origin feat/P<N>.E<M>
```

---

## Stage 6: Lesson Extraction

### 6.1 Determine Lesson Scope

Check the cases in this order; the first matching rule wins:

- **If the convergence reason is `CAP_REACHED_WITH_RESIDUAL`** (the degraded reason): create lessons for **every finding present in the final iteration, regardless of severity**. These are the highest-value learning signals in the entire pipeline — they're the exact vectors that the convergence loop could not resolve within the cap. Skipping a P3 here because it's "low severity" loses the signal `compound_improve` needs to fix the upstream prompt that produced the failure mode. Cap-with-residual epics ship findings to production with no autonomous-loop recourse, and the lessons file is the only place that information lands. Non-degraded findings from the same iteration follow the regular-epic / E2E rules below.

- **If E2E Testing epic** (read `epic_manifest.json` — the E2E epic has `name == "E2E Testing"` and `features == []`): create lessons for **ALL findings (P1, P2, and P3)**. The E2E Testing epic is the most critical learning opportunity in each phase — every finding here (infrastructure failures, cross-component bugs, integration patterns) is a systemic insight that improves future phases. Do not skip any severity.

- **If regular feature epic**: create lessons for **P1 and P2 findings**. P3s are excluded by default (volume — feature epics typically generate many low-severity stylistic findings that drown out the architectural signal). High-value P3s are still captured via the `CAP_REACHED_WITH_RESIDUAL` promotion rule above when the epic caps out with them as residuals.

  **Why include P2 (changed in Tier 2 Step 4):** P2 findings on feature epics are usually architectural — JSON.parse without try/catch, missing transaction boundaries, contract drift between services, ad-hoc retry logic without backoff. Excluding them was a Tier 1 carry-over from before signature dedup landed (`a8f2b98`), when there was a real risk of lesson-file sprawl from the same P2 surfacing in multiple iterations. With Tier 1's signature scheme, same-(file, category, normalized_title) P2s across iterations collapse to one lesson automatically (Stage 6.3 Deduplicate and Write enforces this), so the volume risk is gone and `compound_improve`'s next-project loop gets a richer architectural signal.

### 6.2 Generate Lessons

For each finding in scope (determined by 6.1), create a lesson JSON. For `CAP_REACHED_WITH_RESIDUAL` lessons, include the per-iteration finding history from `review_convergence_state.json` (the signatures that persisted across iterations and their fix attempts) so `compound_improve` can identify which prompt or worker behavior left the vector unresolved within the cap.

### 6.3 Deduplicate and Write

Write to `$EIGEN_ROOT/eigen_initiative/eigen_lessons/review_swarm_pr/`.

---

## Stage 7: Update Pipeline State and Report

### 7.1 Update Pipeline State

Use the CLI to update pipeline state. The exact call depends on the Stage 3 case. `swarm_status` is set to `"iterating"` for the Continue case (fixup tasks created) and to `"converged"` for either terminal case (`CLEAN` or `CAP_REACHED_WITH_RESIDUAL`).

The `--reason` string MUST mention the residual P1/P2/P3 counts when converging with `CAP_REACHED_WITH_RESIDUAL` and the residual P3 count when `p3 > 0`, so downstream commands (`eigen_continue` degraded-convergence gate, the PR-comment renderer) can parse/display it.

**`--findings-detail` is required on every case.** Before running the CLI, write a per-iteration detail file. The file MUST include `entries[]` with one self-describing payload per kept finding so downstream consumers (`compound_improve` cross-epic aggregator) do not have to round-trip through the sidecar:

```bash
cat > /tmp/eigen_findings_iter_<N>.json <<EOF
{
  "iteration": <N>,
  "p1": <x>, "p2": <y>, "p3": <z>,
  "signatures": [<sigs from Stage 2.4>],
  "entries": [
    {
      "signature": "<sha1 from Stage 2.1>",
      "severity": "P1",
      "file": "<POSIX-relative file>",
      "category": "<lowercase short category>",
      "threat_class": "<one of the closed enum>",
      "title_normalized": "<v2-normalized title>"
    }
    /* one entry per kept finding */
  ]
}
EOF
```

`<N>` is the iteration just completed (the same number used in `review_report_iteration_<N>.md`); `signatures` is the array of every kept finding's signature from Stage 2.4. `entries[]` MUST contain one object per signature with required fields `signature`, `severity` (`P1|P2|P3`), `file`, `category`, `threat_class`. The `threat_class` MUST be one of the closed enum (`auth-bypass`, `injection`, `data-loss`, `race-condition`, `type-escape`, `permissions`, `concurrency`, `secrets-exposure`, `path-traversal`, `denial-of-service`, `crypto-misuse`, `input-validation`, `error-handling`, `resource-leak`, `other`). The CLI rejects unknown threat_class values with a non-zero exit. The CLI also validates `iteration` matches `swarm_execution.review_iteration - 1` after the bump and refuses on mismatch — this catches stale or skewed detail files.

All cases below use the **`finalize-iteration` atomic verb**: a single CLI call performs both the iteration-completion mutation and the convergence/status update under one state lock + one `save_state`. A SIGKILL between the legacy paired `complete` + `mark-converged` / `set-swarm-status` calls used to leave partial state on disk; `finalize-iteration` eliminates that window. The legacy verbs remain available for non-hot-path callers but should not be used in the convergence loop.

**Case CLEAN — converged with `p1=0 AND p2=0` (residual P3 allowed):**
```bash
# <z> is the residual P3 count (0 when fully clean). Recorded as-is; P3 never blocks.
eigen-squared finalize-iteration --phase <phase> --epic <epic> --status converged --reason "CLEAN: all P1/P2 findings resolved.<if z>0: ' <z> P3 carried as residual (non-blocking).'>" --report-path <report_path> --findings-summary '{"p1": 0, "p2": 0, "p3": <z>}' --findings-detail /tmp/eigen_findings_iter_<N>.json
eigen-squared commit-state --message "pipeline: review P<phase>.E<epic> — CONVERGED (CLEAN)" --additional-paths eigen_initiative/phases/phase_<phase>/epic_<epic>/
```

**Case CAP_REACHED_WITH_RESIDUAL — converged at the cap (`p1>0 OR p2>0`, `review_iteration >= 3`):**
```bash
# <x>, <y>, <z> are this iteration's counts — recorded as-is so findings_history captures the final (capped) iteration. eigen_continue treats this reason as degraded and requires APPROVE-DEGRADED.
eigen-squared finalize-iteration --phase <phase> --epic <epic> --status converged --reason "CAP_REACHED_WITH_RESIDUAL: max review iterations (3) reached with residual P1: <x>, P2: <y>, P3: <z>; merging with residuals documented. Logged to compound_improve." --report-path <report_path> --findings-summary '{"p1": <x>, "p2": <y>, "p3": <z>}' --findings-detail /tmp/eigen_findings_iter_<N>.json
eigen-squared commit-state --message "pipeline: review P<phase>.E<epic> — CONVERGED (CAP_REACHED_WITH_RESIDUAL)" --additional-paths eigen_initiative/phases/phase_<phase>/epic_<epic>/
```

**Case Continue — iterating (`p1>0 OR p2>0`, `review_iteration < 3`):**
```bash
eigen-squared finalize-iteration --phase <phase> --epic <epic> --status iterating --report-path <report_path> --findings-summary '{"p1": <x>, "p2": <y>, "p3": <z>}' --findings-detail /tmp/eigen_findings_iter_<N>.json
eigen-squared commit-state --message "pipeline: review P<phase>.E<epic> — iteration <N>, CONTINUE" --additional-paths eigen_initiative/phases/phase_<phase>/epic_<epic>/
```

When converging with `CAP_REACHED_WITH_RESIDUAL`, also write a lesson per finding to `eigen_initiative/eigen_lessons/review_swarm_pr/` (per Stage 6.1's degraded-reason rule) capturing the residual vectors. This is consumed by `compound_improve` on its next pass and is the only persistent record of the cap-out outside of `swarm-manifest.json` and `review_convergence_state.json`.

### 7.1.5 Refresh PR Body (every iteration, including pre-convergence)

After Stage 7.1's `commit-state` succeeds, refresh the PR body so a human reviewer can read the cumulative trajectory without parsing each `review_report_iteration_<N>.md` separately.

**Preserve user-edited content.** Do NOT overwrite the entire PR body. Manage a fenced section bounded by `<!-- eigen-managed:start -->` and `<!-- eigen-managed:end -->`. On first run (no fence present), append the fenced block to the existing body. On subsequent runs, replace only the content between the fences. Hand-edits above or below the fence survive untouched.

```bash
# 1. Fetch current PR body.
current_body=$(gh pr view <pr_number> --json body -q .body 2>/dev/null) || {
    echo "WARNING: gh pr view failed for PR #<pr_number>; skipping PR-body refresh."
    # Best-effort — record the failure and proceed. Do NOT block convergence.
    # Append to swarm-manifest.json:
    #   pr_body_update_failed: { iteration: <N>, error: "<gh exit code or message>" }
    skip_pr_body_update=1
}

if [ -z "$skip_pr_body_update" ]; then
    # 2. Build new managed-section content from findings_history + convergence reason.
    new_section=$(cat <<EOF
<!-- eigen-managed:start -->
## Convergence summary

**Status:** <converged-with-reason | iterating>
**Iteration:** <N> / 3 (cap)
**Convergence reason:** <CLEAN | CAP_REACHED_WITH_RESIDUAL | "—">

### Iteration history

| Iter | P1 | P2 | P3 | Report |
|------|----|----|----|--------|
<one row per iterations[] entry, with link to review_report_iteration_<i>.md>

### Convergence trajectory

- Resolved this iteration: <count>
- Newly introduced this iteration: <count>
- Persistent across iterations: <count>
- Residual P3 (non-blocking): <count>

_Last updated: <ISO 8601>_
<!-- eigen-managed:end -->
EOF
)

    # 3. Validate fence pairing BEFORE splicing.
    start_count=$(echo "$current_body" | grep -c "<!-- eigen-managed:start -->" || true)
    end_count=$(echo "$current_body"   | grep -c "<!-- eigen-managed:end -->" || true)
    if [ "$start_count" -gt 1 ] || [ "$end_count" -gt 1 ] || [ "$start_count" != "$end_count" ]; then
        # Malformed fence (duplicate markers from a pasted-in old PR body, or a
        # half-edited fence where the user removed only one marker, or a fence
        # accidentally embedded inside a code block). Fail-soft: log and append
        # a fresh fenced section at the bottom rather than risk corrupting the
        # body.
        # Record in swarm-manifest.json:
        #   pr_body_fence_malformed: [{iteration: <N>, start_count: $start_count, end_count: $end_count, at: "<ISO 8601>"}]
        echo "WARNING: malformed eigen-managed fence in PR body (start=$start_count, end=$end_count); appending fresh section."
        new_body="${current_body}

${new_section}"
    elif [ "$start_count" = "1" ] && [ "$end_count" = "1" ]; then
        # Exactly one well-formed fence. Replace it.
        new_body=$(echo "$current_body" | awk -v new="$new_section" '
            BEGIN { skip=0 }
            /<!-- eigen-managed:start -->/ { print new; skip=1; next }
            /<!-- eigen-managed:end -->/   { skip=0; next }
            !skip { print }
        ')
    else
        # No fence yet (start_count=0, end_count=0). Append.
        new_body="${current_body}

${new_section}"
    fi

    # 4. Push back. Best-effort — record failure but do not block.
    gh pr edit <pr_number> --body "$new_body" || {
        echo "WARNING: gh pr edit failed; PR body not refreshed for iteration <N>."
        # Record pr_body_update_failed in swarm-manifest.json as above.
    }
fi
```

**Failure mode is best-effort.** If `gh` is unavailable (network, auth, rate limit), record a `pr_body_update_failed` entry in `swarm-manifest.json` and continue. The convergence loop must not block on PR cosmetics.

### 7.1.6 Capture last-green baseline (fully-clean convergence only)

**Skip this section unless** the iteration converged with a genuinely clean state: reason `CLEAN` AND `p1=p2=p3=0` (no residual). Degraded convergence (`CAP_REACHED_WITH_RESIDUAL`) and a `CLEAN` convergence that still carries residual P3 MUST NOT update the baseline — using an iteration with unresolved findings as baseline would taint the next epic's gate.

Write `swarm-manifest.json.last_green_baseline`:

```json
"last_green_baseline": {
  "commit_sha": "<git rev-parse HEAD on the integration branch>",
  "suite_result_hash": "<sha256 of the per-test pass/fail manifest from the gate run>",
  "captured_at": "<ISO 8601>",
  "captured_at_iteration": <N>,
  "convergence_reason": "<reason that triggered capture, e.g. 'All findings resolved'>"
}
```

`commit_sha` is the SHA on the integration branch immediately after Stage 7.1's commit-state lands (so future epics' Stage 4.0 gate can `git diff` against this baseline). `suite_result_hash` is the deterministic hash of the most-recent green run's per-test manifest; consumers compare against it before each new gate run to short-circuit identical re-runs.

If the field already exists from a prior CONVERGED-clean iteration of this same epic, **overwrite** it (the more recent green is the better baseline). The field is not append-only — only one baseline per epic.

This baseline is consumed by `orchestrate_swarm` Stage 4.0 and per-worker full-suite gates: any test signature that fails in `last_green_baseline.suite_result_hash`'s manifest is treated as "already failing pre-iteration" and excluded from the regression count, so workers are never blamed for breakage they inherited.

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
  <if iteration 1+:>
  vs Previous: <addressed> fixed, <persistent> remaining, <regressed> regressed, <new> new
  <if z > 0:>
  Residual (non-blocking): P3 × <z> — recorded in swarm-manifest.json.residual_p3 and pipeline_state.json
  <if CAP_REACHED_WITH_RESIDUAL:>
  Cap reached at iteration 3 with residual P1: <x>, P2: <y>, P3: <z> — merged and documented. Requires APPROVE-DEGRADED at the phase checkpoint.

Iteration: <N> / 3 (cap)

Convergence: <CONVERGED — CLEAN | CONVERGED — CAP_REACHED_WITH_RESIDUAL | CONTINUE — iterating>

Next steps:
  Continue (iterating):
    Stay on this branch and run /orchestrate_swarm.
    The manifest has been updated — only new review tasks will execute (P1+P2 fixups).
    After fixups complete, run /review_swarm_pr again (iteration <N+1>).
  CONVERGED (CLEAN or CAP_REACHED_WITH_RESIDUAL):
    PR #<pr_number> merged to $EIGEN_BRANCH. Branch feat/P<N>.E<M> deleted.
    Now on $EIGEN_BRANCH with latest changes.
    If more epics remain in this phase: proceeding to next epic.
    If all epics are complete: run /eigen_continue to review and approve the phase (CAP_REACHED_WITH_RESIDUAL requires APPROVE-DEGRADED).
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
- **Convergence**: all P1 and P2 findings must be resolved. Residual P3 findings are allowed and recorded in `pipeline_state.json` (`swarm_execution.findings_summary.p3` and `swarm_execution.convergence.reason`) and in `swarm-manifest.json.residual_p3`. The loop is a **simple bounded loop** with a hard cap of 3 iterations (`CAP = 3`), evaluated in order each iteration:
  1. `p1 == 0 AND p2 == 0` → CONVERGED with reason `CLEAN` (residual P3 disclosed, non-blocking).
  2. else if `review_iteration >= 3` → CONVERGED with reason `CAP_REACHED_WITH_RESIDUAL` (residual P1/P2/P3 merged and documented; `eigen_continue` requires `APPROVE-DEGRADED` at the phase checkpoint).
  3. else → CONTINUE: create P1+P2 fixup tasks; P3 ride along as disclosed residuals.

  The elaborate anti-oscillation machinery (oscillation circuit-breaker, monotonicity M1/M1-stale/M2, P3 sweep with auto-revert) was insurance against weak-model ping-ponging and has been removed: a strong model fixes correctly, so a hard `<= 3`-iteration cap with residual disclosure is sufficient and far cheaper.
- **Deterministic type-escape detector (Stage 1.3)**: project-wide, runs alongside review agents, regex-scans the iteration's added diff lines for unambiguous escape patterns (`as any`, `as unknown as <T>`, `@ts-ignore`/`@ts-expect-error`/`@ts-nocheck`, `typing.cast(Any, ...)`, bare `# type: ignore` / `# pyright: ignore`). Synthesizes P1 findings with `category: type-safety` and `agent: type-escape-detector`. Allowlist via inline `// REVIEWER: type-escape approved by leader, see [DECISION-<id>]` comment within 3 lines above the escape — the same convention the leader's `type_escape_needed` autonomous handler in `orchestrate_swarm.md` instructs workers to write. Pre-existing escapes in unmodified code are NOT flagged (only added lines). Findings flow through normal Stage 2 triage (scope filter, signature dedup, ledger).
- **P3 fixup policy**: P3 findings **never** trigger fixup tasks. They ride along as disclosed residuals in `swarm-manifest.json.residual_p3` and the PR review, and do not block convergence (`CLEAN` converges with residual P3 present).
- **Push after every commit**: the PR updates automatically when the branch is pushed.
- **Merge is automatic on convergence**: when converged, the command merges the PR via `gh pr merge --squash --delete-branch`, checks out `$EIGEN_BRANCH`, pulls, and deletes the local branch. No manual step needed.
- **Post-merge state**: after auto-merge, the working directory is on `$EIGEN_BRANCH` with all epic artifacts (code, tasks, manifest, pipeline_state, reports) merged in.
- **Testing philosophy**: when evaluating tests, prefer real dependencies over mocks. Flag tests that mock where real infrastructure is available.
- **Agent roster is locked at iteration 0**: the set of review agents spawned for an epic's PR is computed once on iteration 0 and persisted to that iteration's report front-matter. Iterations ≥ 1 reuse the iter-0 roster verbatim. Conditional triggers (diff size, performance-mention) are evaluated only on iteration 0. Any new reviewer type only takes effect starting from the next epic. This guarantees that growth in apparent finding count across iterations of the same epic reflects genuine new regressions, not late-discovered latent issues from an expanded roster.
- **Scope is locked at iteration 0**: `scope_files` is computed once from the **original T-tasks'** `files_owned` and `test_files_owned` (plus `shared_files` and `e2e_config`) and is invariant across iterations of the same epic. R-task ownership is a subset by construction and never expands scope. Out-of-scope findings discarded in iteration K are persisted in `review_discards.json` and re-applied as discards in all subsequent iterations — promoting a previously-discarded finding requires an explicit promotion step (Tier 2 enhancement), not a silent re-admission.
- **Findings are tracked by signature, not by free-text title**: every kept finding has `sig = sha1("<normalized_file_path>|<category>|<normalized_title>")`. Cross-iteration comparison (Stage 2.2) and `swarm_execution.findings_history` use the same scheme so they agree iteration-for-iteration. The full per-iteration ledger lives in `review_convergence_state.json` (next to the report) with `{file, symbol, category, severity, title}` for human readers; the CLI mirror in `findings_history` keeps just `{iteration, p1, p2, p3, signatures}` for downstream consumers (`compound_improve`'s cross-epic aggregator depends on it). The `symbol` field on each ledger entry is human-readable grouping metadata only — it is **not** part of the signature, so adding/changing/inferring a symbol after the fact does not break cross-iteration sig comparisons.

