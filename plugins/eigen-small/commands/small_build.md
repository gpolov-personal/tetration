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

## Mode: supervised (default) vs `--unsupervised`

**Default — supervised, single phase.** Everything below is the supervised hot path: build the
current phase's waves, stop. This is the common case — keep reading.

**`--unsupervised` — multi-phase sequential driver.** If invoked with `--unsupervised`, you are
instead driving an *unattended sequential build across all planned phases* (planned by
`small_plan_horizon`, approved by `small_review`). **Do not follow the single-phase flow below.**
Load `Skill("eigen-small:unsupervised-multiphase")` and follow it — that doctrine is kept out of
this hot path **on purpose** (progressive disclosure), so a supervised single-phase run never
carries multi-phase instructions it doesn't need. The driver reuses the per-wave loop below, once
per phase, against a per-phase state file.

## The CLI you use

```
eigen-small status                       # current waves + per-epic goal status
eigen-small next                         # which wave / pending epics is next
eigen-small complete-epic <wave> <epic> --goal-green
eigen-small set-wave-review <wave>              # --status defaults to done
eigen-small commit-state --message "..."
```

## On Entry

> **Phase slot (N).** Read `phase` from `eigen-small status` (or `next`'s `context.phase`). All `phases/phase_<N>/…` paths and the `feat/P<N>.E<M>` / `wt-P<N>.E<M>` branch + worktree names below use that N (a phase-2 run uses `phases/phase_2/`, `feat/P2.E<M>`).

1. `eigen-small status`. **STOP** if there are no `waves` — run `small_plan` first.
2. `eigen-small next` → `context.wave` + `context.pending_epics` (or `step: review`) is the
   wave to work. Walk waves in the order `next` reports them; do not skip ahead.

## Per-wave loop

### Stage 1 — Implement

One focused implementer per epic. Build **directly from `phases/phase_<N>/epic_<M>/epic.md`**
(its frozen interface signatures, verbatim Blackbox specs, validation_summary). TDD on the
risky features; keep frozen signatures; honour logging/secret guardrails.

- **Parallel wave** (`context.parallel == true` — mutually-independent epics): for each epic,
  create an **explicit git worktree** and spawn one implementer there:
  ```
  git worktree add ../wt-P<N>.E<M> -b feat/P<N>.E<M> <integration-branch>
  ```
  Spawn the implementer (Agent tool) with `cwd` = that worktree. **Use explicit
  `git worktree add` — NOT `isolation:"worktree"`** (verified: it does not isolate parallel
  background agents; they share the main checkout and race on branch checkouts). Each
  implementer touches **only its own subpackage + its own test file**; `contracts/`/`config/`
  and other epics' packages are read-only; it commits **only its own files**. (Strict
  file-ownership is the load-bearing safety margin under any residual sharing.)
- **Sequential wave** (`parallel == false`): one implementer on `feat/P<N>.E<M>`. The
  integration-heart epic (orchestration / wiring) also gets a **targeted concurrency review** in
  Stage 3 — it is where late integration + races + light review coincide.
- **Model assignment:** read `phases/phase_<N>/model_plan.yaml` (emitted by `small_plan`, possibly
  hand-tuned at the STOP) and spawn each epic's implementer with the model it names. **If the file
  is absent, fall back to the default tiering:** the riskiest epic (and goal authoring, already
  done in `small_plan`) + the integration-heart epic → strongest model; mechanical /
  spec-transcription epics → a cheaper model. The frozen real-boundary goal is what makes a
  cheaper implementer safe.

**Implementer brief (per epic):**
```
Read:    phases/phase_<N>/epic_<M>/epic.md (the contract — read fully)
GOAL (stop): test/waves/<id>/ — do NOT return success until your goal runs GREEN
You own: <epic subpackage> + test/unit/.../test_<pkg>.py   (+ may EXTEND test/waves/<id>/, never weaken frozen assertions)
Read-only: contracts/, config/, other epics' packages, the frozen goal assertions
Secure-by-default: when the epic touches inputs, auth, secrets, or external I/O, load
      `Skill("eigen-small:security-best-practices")` for the detected language (python/js/ts/go)
Do:   TDD from the epic ACs → implement → keep frozen signatures → make the §goal green against its real boundary
Don't: change frozen ABC signatures, touch other subpackages, weaken the goal, edit pipeline_state_small.json
```

### Stage 2 — Goal gate (the stop-condition)

For each epic, **the orchestrator runs the epic's `test/waves/<id>/` goal itself** against
its **real boundary** (real broker / object store / record-replay stub — fake only what the
wave doesn't own). The implementer's self-report is not sufficient — the goal is the
independent oracle (the why, and the extend-never-weaken rule, are the goal-authoring doctrine:
`Skill("eigen-small:goal-authoring")`). Only when it is **actually green**:
```
eigen-small complete-epic <wave> <epic> --goal-green
```
If a goal is red, send the implementer back **with the failing assertions as feedback** (do not
mark green, do not advance). **Bound this loop with `--max-attempts N` (default N=3) round-trips
per epic:** on the Nth still-red attempt, **STOP and surface** — report the epic, the
persistently-failing assertions, and what was tried, then hand back to the human. Never silently
loop past N. (You MAY escalate the implementer's model on a retry via `model_plan.yaml`.) The bound
turns the implicit "iterate until green" into "iterate until green *or* fail loudly".

### Stage 3 — Merge + per-wave code-review

1. Merge the wave's epic branches into the integration branch (file-disjoint ownership →
   clean merges). Run the unit suite on the integrated tree.
2. **Lightweight review:** `/code-review` on the wave diff. Then, for each epic carrying a
   `risk` tag in the epic_manifest, spawn the matching **bundled** specialist reviewer
   (Agent tool, `subagent_type`) on that epic's diff:
   - `risk: silent_corruption` → `eigen-small:data-integrity-guardian`
   - `risk: external_integration` → `eigen-small:security-sentinel`
   - `risk: concurrency` → `eigen-small:architecture-strategist`
   Not the 8-agent × 3-iteration swarm; no P3 sweeps.
3. **Triage → fix → regression-gate:** fix the blocking / cheap-isolated findings in-wave;
   **a fix is not done until its affected `test/waves/<id>/` goal AND the unit suite are green
   again**; re-`/code-review` the fix diff if non-trivial; record the rest as documented
   follow-ups. Then:
```
eigen-small set-wave-review <wave>              # --status defaults to done
```
4. Clean up worktrees (`git worktree remove ../wt-P<N>.E<M>`). `eigen-small next` → the next wave.

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
4. **Frozen signatures are read-only** to implementers — including every seam in the
   cross-phase freeze ledger (`eigen-small freeze-list`); goal assertions are read-only
   (extend, never weaken).
5. **Invoked in-session, never wrapped in a router subagent** — implementers must spawn from
   the top level.
6. **Strict file-ownership** per epic (only its subpackage + its test file) — the safety margin
   that keeps merges clean and survives any residual checkout sharing.
7. **Never edit `pipeline_state_small.json` by hand** — always via the CLI.
8. **Bound the goal-retry loop** — `--max-attempts N` (default 3) round-trips per epic; on the Nth
   still-red attempt STOP and surface to the human, never loop silently. The goal stays the oracle;
   the bound is the circuit-breaker.
9. **`--unsupervised` is multi-phase-only and gated.** It runs only after `small_review` approved
   **every** discovered phase, builds phases sequentially in-session (no watchdog/cron), and halts
   on a goal still red after `--max-attempts N` without crossing to the next phase. On a single
   phase it degenerates to `--auto`. The driver doctrine lives in
   `Skill("eigen-small:unsupervised-multiphase")`, loaded only when the flag is set.
