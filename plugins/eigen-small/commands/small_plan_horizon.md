---
name: small_plan_horizon
description: Long-horizon planner for eigen-small — the multi-phase sibling of small_plan. Cuts the work into up to 3 SEQUENTIAL phases (warns recommending a max of 2), then plans each phase by REUSING small_plan's per-phase doctrine, freezing cross-phase seams UPFRONT in-session so a later phase plans against an earlier phase's frozen contracts. Single-pass — the human review (small_review) is the critic, not a convergence loop. Emits per-phase artifacts + a per-phase wave_plan.json on disk, discovered later by small_build --unsupervised. STOPS at the plan→build boundary.
---

> Pipeline (multi-phase): `small_route` → **`small_plan_horizon`** → `small_review` → `small_build --unsupervised`.
> Invoked **in-session**. Use this **only** when the work is genuinely multi-phase (2–3 phases) and
> you intend the unattended sequential build. For a single phase, use `small_plan`.

## Your role

You are the **long-horizon planner**. You hold up to three phases in context, cut them, and plan
each one — but you do **not** invent new planning machinery: per phase you **reuse `small_plan`'s
doctrine verbatim** (`Skill("eigen-small:small_plan")` Stages M/B/S + `Skill("eigen-small:goal-authoring")`).
What is *new* here is only: the **phase cut**, **freezing cross-phase seams upfront** and feeding
them forward in-session, and **cumulative E2E gates**. You plan in **one pass** — the human is the
critic at `small_review`, which replaces squared's plan-convergence loop (eigen-small's "one pass,
no convergence loops" creed holds).

## The horizon — and the hard warning

- **Cut at most 3 phases.** If the work needs **≥4 phases**, STOP and recommend **eigen-squared**
  (`time_split`) — that is its job, with the convergence hardening multi-phase decomposition needs.
- **2 phases is the safe ceiling.** When you cut **3**, emit a clear **WARNING**: *3-phase planning
  in eigen-small is experimental — the cross-phase blast-radius grows non-linearly and the only
  critic is the single human review pass. Strongly consider 2 phases, or eigen-squared.*
- The work must be **predictable enough to plan entirely upfront.** Planning all phases before
  building any **forecloses the "build phase 1, learn, then plan phase 2" loop** (the reason
  eigen-small's two-manual-runs model exists). Say this plainly: choosing this path asserts the
  work is well-understood. If it is exploratory, prefer two manual `small_plan` runs.

## On Entry

1. `eigen-small status` — expect `shape` routed here for multi-phase (small_route). Read the
   Initiative + Blackbox (or the feature description) and the repo conventions.
2. `eigen-small freeze-list` — any seams already frozen by a prior run are read-only inputs.

## Stage H — Cut the phases (the only genuinely new planning step)

A `time_split`-lite, single pass:

1. Build the dependency DAG from the feature set (backward-only edges — a phase may depend on
   earlier phases, never later).
2. **Phase 1 = the foundation**: infra + critical-path roots + a minimal input→…→output slice
   (+ containerization if deployment is in scope). Layer remaining features by topological order;
   **keep cohesion clusters atomic** (never split a cluster across phases).
3. Each phase must be **cumulatively E2E-testable** — phase N's E2E gate covers phases 1..N, not
   just N in isolation. This is the oracle for cross-phase integration the single-phase goals miss.
4. Apply the **horizon warning** above (≤2 recommended, 3 experimental, ≥4 → defer to squared).

## Stage P — Plan each phase (reuse small_plan, freeze forward)

For each phase N in ascending order, plan it into `phases/phase_<N>/` by **reusing small_plan's
Stages M/B/S** (manifest → bootstrap-delta → space-split + goals), with two cross-phase rules:

1. **Plan against earlier phases' FROZEN contracts, in-session.** Phase 2 is planned before phase 1
   is built, so it plans against phase 1's **frozen** seams (not a realized ledger). Treat every
   seam this run already froze (Stage P of an earlier phase, below) as read-only — build against it.
2. **Freeze this phase's cross-phase seams UPFRONT**, immediately after space-split, so the next
   phase inherits them: `eigen-small freeze-add --phase <N> --name <seam> --kind frozen|hook
   [--signature ...] [--consumers ...]`. This is the load-bearing mechanism — an implementer in
   `small_build` may never deviate from a frozen seam, so freezing upfront is what makes planning
   later phases against not-yet-built contracts safe.
3. Emit the same **invariant artifacts** small_plan does, under `phases/phase_<N>/`:
   `epic_manifest.json`, `epic_<M>/epic.md`, `phase_e2e_config.json` (cumulative — covers 1..N),
   goals under `test/waves/<id>/`, and a **`phases/phase_<N>/wave_plan.json`** (the DAG-ordered wave
   grouping for this phase, same shape as `set-waves` takes — `small_build --unsupervised` loads it
   per phase). The **three invariants hold per phase** (feature coverage, concrete-files resolution,
   **AC→goal coverage** — no orphan ACs).
4. **One cross-cutting critique pass** — per phase AND across phases: do any two phases' to-be-frozen
   contracts contradict? Would a phase-1 freeze need to mutate in phase 2 (reshape it **now**, before
   freezing)? One pass, no loop — the deep critique is the human's at `small_review`.

> **State note:** `small_plan_horizon` writes **disk artifacts + the freeze ledger**, not the
> single-phase `pipeline_state_small.json` waves (which holds one active phase). `small_build
> --unsupervised` discovers the phases by disk and points the live state at each phase as it
> advances. So `eigen-small next` stays single-phase-oriented; the multi-phase flow is driven by
> `small_review` → `small_build --unsupervised`, not by `next`.

## On Exit

1. Confirm per phase: the three invariants hold; frozen seams recorded (`freeze-list`); a cumulative
   E2E config; a `wave_plan.json`. Fix gaps now — one pass.
2. `eigen-small commit-state --message "small_plan_horizon: planned <name> (<K> phases)" --additional-paths eigen_initiative/phases/,test/waves/`.
3. **STOP at the plan→build boundary.** Point the human to **`small_review`** — it walks every phase's
   specs + goals, runs the mechanical AC→goal coverage check, and records the per-phase approvals
   that gate `small_build --unsupervised`. Nothing builds until every phase is approved there.

## Hard rules

1. **Reuse small_plan's per-phase doctrine — do not fork it.** Only the phase cut, upfront
   forward-freezing, and cumulative E2E are new here.
2. **Freeze cross-phase seams UPFRONT and feed them forward** in the same session — later phases plan
   against frozen (not realized) contracts; that is what makes upfront multi-phase planning safe.
3. **One pass, no convergence loop.** The critic is the human at `small_review`. (eigen-small's "one
   pass" creed.)
4. **≤2 phases recommended, 3 experimental (warn), ≥4 → defer to eigen-squared.**
5. **Cumulative E2E per phase** (phase N covers 1..N) — the only oracle for cross-phase integration.
6. **Do not auto-advance phases.** This command only *plans*. Sequencing the builds is
   `small_build --unsupervised`, and only after `small_review` approves every phase.
7. **Never edit `pipeline_state_small.json` by hand** — always via the CLI.
