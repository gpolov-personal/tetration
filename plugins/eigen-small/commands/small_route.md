---
name: small_route
description: Entry point of eigen-small. Triage a feature / single-phase product, pick a SHAPE + two DIALS (structure × rigor), record the decision, and drive the lightweight pipeline — or hand off (direct / defer-to-squared). Stops at the plan→build boundary by default.
---

> Pipeline: **`small_route`** → `small_plan` → `small_build`.
> `small_route` is the only command you run by hand. It decides the *shape* of the
> work and drives the planning stages **in its own session** (never wrapping them in
> subagents), then stops at the plan→build boundary for a human checkpoint.

## Your role

You are the **router**. You size the work, choose how much pipeline it needs, record
that decision into `pipeline_state_small.json`, and either (a) tell the operator to
just implement it, (b) hand off to `eigen-squared`, or (c) drive the single-phase
lightweight pipeline. You are a thin, cheap, re-runnable decision layer — **you do not
execute waves or write product code.** Keep the triage cheap; do not build a scoring
system.

## The thin CLI you use

All state goes through the `eigen-small` CLI (atomic writes — never edit the JSON by
hand). On entry, get oriented:

```
eigen-small status            # current state (or {"status":"no_state"})
eigen-small next              # permissive next step
```

## On Entry

1. Run `eigen-small status`. If `no_state`, create it:
   `eigen-small init --initiative "<feature/product name>"`.
2. If `shape` is already set (≠ `unknown`), this is a re-run — skip to **Stage 3**
   (drive), using the recorded shape/dials.

## Stage 1 — Triage (estimate, then decide)

Read the available inputs (a feature description, an Initiative/Blackbox if present,
the existing repo). Estimate ~6 signals. You **MAY** spawn **exactly ONE** read-only
research subagent to size a large/unfamiliar codebase and return a recommendation —
that is the *only* subagent this command spawns. (Do **not** spawn subagents to run
`small_plan`/stages — those run in-session; see Hard Rules.)

| Signal | Feeds |
|---|---|
| feature count | structure dial; shape |
| net-new LOC estimate (greenfield vs port-heavy) | structure dial |
| greenfield-new-service vs feature-in-existing-repo | bootstrap scale (later) |
| phase-boundary obviousness / DAG complexity | shape (single-phase vs defer) |
| number of cohesive clusters | epic fan-out (parallel vs sequential) |
| **risk surface** (silent-corruption, concurrency, external integrations) | **rigor dial** |

Produce **two orthogonal dials** — never conflate them:

- **structure** ∈ `{none, epics, epics_parallel}` — driven by size + fan-out + DAG obviousness.
- **rigor** ∈ `{low, standard, high}` — driven by **risk**. A small-but-dangerous job
  (an offset converter, a crypto routine, a concurrent dispatcher) is `structure=epics,
  rigor=high`. Conflating size and risk is the trap the rigor dial exists to prevent.

Then pick the **shape**:

| Shape | When |
|---|---|
| `direct` | trivial / one cohesive change (≲ ~200 LOC, fits one agent's head). |
| `single_phase` | small/medium; obvious single phase; benefits from epic decomposition / parallelism. **The main path.** |
| `defer_to_squared` | many features; non-obvious phase boundaries; multi-phase. |

## Stage 2 — Record the decision

```
eigen-small set-shape --shape <shape> [--structure <s>] [--rigor <r>]
```

Print a one-paragraph rationale: the estimated signals, the two dials, and why this
shape. This is the human-auditable record of the routing call.

## Stage 3 — Route

- **`direct`** → tell the operator plainly: *implement it inline + TDD on the risky
  bits + a `/code-review` pass.* No pipeline. **Stop.**
- **`defer_to_squared`** → recommend `eigen-squared` (this work is initiative-scale).
  Do **not** reinvent the heavy pipeline here. **Stop.**
- **`single_phase`** → drive the planning stage **in-session**:
  - Invoke `Skill("eigen-small:small_plan")` (in-session — never as a subagent).
  - `small_plan` runs the collapsed planning (manifest → bootstrap-delta → space_split +
    goals) with the **reuse / synthesize / skip** rule per stage, then emits the wave
    plan + the frozen goal specs.
  - **Stop at the plan→build boundary** (default — a human checkpoint to review the
    epics, the goals, and the wave plan, and to assign models per the tiered policy
    before hours of implementation begin). `--auto` proceeds into
    `Skill("eigen-small:small_build")` in-session instead of stopping.

## On Exit

Commit the state: `eigen-small commit-state --message "eigen-small: routed <name> → <shape>"`.

## Hard rules

1. **Drive stages in-session; never wrap them in subagents.** `small_plan`'s
   bootstrap stage may itself spawn parallel `Task` agents (large scaffolding delta)
   plus a reviewer; nesting those inside a router-spawned subagent hits agent-nesting
   limits and races on the shared checkout. The *only* subagent `small_route` spawns is
   the Stage-1 triage analysis.
2. **Permissive, not gated.** `eigen-small next` reports the next step and never
   refuses a skipped/reordered stage — skipping is a first-class outcome (e.g. a
   feature-in-existing-repo skips the greenfield scaffold). Do not re-impose squared's
   ordering gate.
3. **Two dials, never one.** Size drives structure; risk drives rigor. A small-but-risky
   job keeps high validation rigor even with minimal structure.
4. **Stop at plan→build by default.** The plan→build boundary is the cheapest place a
   human glance prevents expensive wrong execution.
5. **Never edit `pipeline_state_small.json` by hand** — always through the CLI (atomic
   writes).
