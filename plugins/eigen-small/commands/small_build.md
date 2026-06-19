---
name: small_build
description: Wave executor for eigen-small. Walks the DAG-ordered wave plan; per wave, builds each epic DIRECTLY from its epic.md (one focused implementer per epic, parallel epics in explicit git worktrees), gated by its frozen real-boundary goal as the stop-condition, then runs a lightweight per-wave code-review with a goal+suite regression gate. Resumable per wave. The last wave is the E2E phase gate.
---

> Pipeline: `small_route` → `small_plan` → **`small_build`**.
> **Separate from the router by design.** Invoked **in-session** (so per-epic
> implementers spawn from the top level — never wrap this in a router subagent, or the
> implementers' own spawns hit nesting limits). **Resumable per wave** — re-running
> picks up at the first unfinished wave via `eigen-small next`.

## Your role

You are the **orchestrator**, not an implementer. You spawn one focused implementer per
epic, **confirm each epic's goal green yourself** (the goal is an independent oracle — do
not trust an implementer's self-report), merge, run a lightweight per-wave review, and
record progress. You write no product code.

## The CLI you use

```
eigen-small status                       # current waves + per-epic goal status
eigen-small next                         # which wave / pending epics is next
eigen-small complete-epic <wave> <epic> --goal-green
eigen-small set-wave-review <wave>              # --status defaults to done
eigen-small commit-state --message "..."
```

## On Entry

1. `eigen-small status`. **STOP** if there are no `waves` — run `small_plan` first.
2. `eigen-small next` → `context.wave` + `context.pending_epics` (or `step: review`) is the
   wave to work. Walk waves in the order `next` reports them; do not skip ahead.

## Per-wave loop

### Stage 1 — Implement

One focused implementer per epic. Build **directly from `phases/phase_1/epic_<M>/epic.md`**
(its frozen interface signatures, verbatim Blackbox specs, validation_summary). TDD on the
risky features; keep frozen signatures; honour logging/secret guardrails.

- **Parallel wave** (`context.parallel == true` — mutually-independent epics): for each epic,
  create an **explicit git worktree** and spawn one implementer there:
  ```
  git worktree add ../wt-P1.E<M> -b feat/P1.E<M> <integration-branch>
  ```
  Spawn the implementer (Agent tool) with `cwd` = that worktree. **Use explicit
  `git worktree add` — NOT `isolation:"worktree"`** (verified: it does not isolate parallel
  background agents; they share the main checkout and race on branch checkouts). Each
  implementer touches **only its own subpackage + its own test file**; `contracts/`/`config/`
  and other epics' packages are read-only; it commits **only its own files**. (Strict
  file-ownership is the load-bearing safety margin under any residual sharing.)
- **Sequential wave** (`parallel == false`): one implementer on `feat/P1.E<M>`. The
  integration-heart epic (orchestration / wiring) goes to the **strongest available model**
  plus a **targeted concurrency review** in Stage 3 — it is where late integration + races +
  light review coincide.
- **Tiered models:** the riskiest epic (and goal authoring, already done in `small_plan`) →
  strongest model; mechanical/spec-transcription epics → a cheaper model. The frozen
  real-boundary goal is what makes a cheaper implementer safe.

**Implementer brief (per epic):**
```
Read:    phases/phase_1/epic_<M>/epic.md (the contract — read fully)
GOAL (stop): test/waves/<id>/ — do NOT return success until your goal runs GREEN
You own: <epic subpackage> + test/unit/.../test_<pkg>.py   (+ may EXTEND test/waves/<id>/, never weaken frozen assertions)
Read-only: contracts/, config/, other epics' packages, the frozen goal assertions
Do:   TDD from the epic ACs → implement → keep frozen signatures → make the §goal green against its real boundary
Don't: change frozen ABC signatures, touch other subpackages, weaken the goal, edit pipeline_state_small.json
```

### Stage 2 — Goal gate (the stop-condition)

For each epic, **the orchestrator runs the epic's `test/waves/<id>/` goal itself** against
its **real boundary** (real broker / object store / record-replay stub — fake only what the
wave doesn't own). The implementer's self-report is not sufficient — the goal is the
independent oracle. Only when it is **actually green**:
```
eigen-small complete-epic <wave> <epic> --goal-green
```
If a goal is red, send the implementer back (do not mark green, do not advance).

### Stage 3 — Merge + per-wave code-review

1. Merge the wave's epic branches into the integration branch (file-disjoint ownership →
   clean merges). Run the unit suite on the integrated tree.
2. **Lightweight review:** `/code-review` on the wave diff (+ a targeted reviewer on the
   high-risk epics, e.g. a concurrency review on the orchestration epic). Not the 8-agent ×
   3-iteration swarm; no P3 sweeps.
3. **Triage → fix → regression-gate:** fix the blocking / cheap-isolated findings in-wave;
   **a fix is not done until its affected `test/waves/<id>/` goal AND the unit suite are green
   again**; re-`/code-review` the fix diff if non-trivial; record the rest as documented
   follow-ups. Then:
```
eigen-small set-wave-review <wave>              # --status defaults to done
```
4. Clean up worktrees (`git worktree remove ../wt-P1.E<M>`). `eigen-small next` → the next wave.

### Last wave — the E2E phase gate

The final wave's epic is the phase gate (no new product code): bring up the containerized
stack and run the phase-success scenarios green (equivalence / fail-open / extractability /
backpressure, per `phase_e2e_config.json`). Its goal accessory **is** the gate.

## On Exit

`eigen-small commit-state --message "small_build: wave <id> complete"` after each wave, and
once `eigen-small next` reports `done`, a final `--message "small_build: all waves green"`.
Report the wave summary + any recorded follow-ups.

## Hard rules

1. **Explicit `git worktree add` for parallel epics — never `isolation:"worktree"`** (it does
   not isolate; agents race on the shared checkout). Sequential waves are unaffected.
2. **The orchestrator confirms each goal green** by running it against the real boundary —
   never on the implementer's self-report. The goal is the independent oracle.
3. **A fix is not done until its goal + the unit suite are green again** (the regression gate).
4. **Frozen signatures are read-only** to implementers; goal assertions are read-only (extend,
   never weaken).
5. **Invoked in-session, never wrapped in a router subagent** — implementers must spawn from
   the top level.
6. **Strict file-ownership** per epic (only its subpackage + its test file) — the safety margin
   that keeps merges clean and survives any residual checkout sharing.
7. **Never edit `pipeline_state_small.json` by hand** — always via the CLI.
