---
name: unsupervised-multiphase
description: "The eigen-small driver doctrine for `small_build --unsupervised` — the unattended, in-session, sequential multi-phase build. Load ONLY when small_build is invoked with --unsupervised (multi-phase work planned by small_plan_horizon and approved by small_review). Defines the precondition gate (all phases human-approved), the per-phase build loop over an isolated per-phase state file, the bounded goal-retry circuit-breaker, halt-and-surface on failure, and what it deliberately does NOT do (no watchdog/cron)."
---

# Unsupervised multi-phase driver

This is loaded **only** when `small_build --unsupervised` runs. It is a **single in-session
sequential driver** — there is **no watchdog, no cron, no claude-tasks, no `.eigen` env**. It runs
the planned phases (from `small_plan_horizon`) one after another, unattended, **after a human has
approved every phase in `small_review`**, and **halts** the moment a phase can't reach its goal.

The safety model: the human checkpoint is **front-loaded** (every phase's specs + goals validated in
`small_review` before any build), so each frozen goal is a trusted oracle. The driver then just runs
the already-validated plans and stops on the first thing the goals can't certify.

## Precondition gate (refuse to run otherwise)

1. **Discover the phases by disk** — glob `eigen_initiative/phases/phase_*/` with an
   `epic_manifest.json`. Order ascending. This is the set of phases to build.
2. **Require ≥2 phases.** A single phase is not an unsupervised job — fall back to supervised
   `small_build` (or `--auto`). Say so and stop.
3. **Require EVERY discovered phase `approved`** — `eigen-small review-list`. If any phase is
   `pending` or has no entry, **STOP**: "run `small_review` and approve every phase before an
   unattended build." This approval is the load-bearing front-loaded gate; never bypass it.
4. **If 3 phases, emit the experimental warning** (`small_plan_horizon`'s warning) before starting.

## Per-phase build loop

For each phase N in ascending order:

1. **Isolated per-phase state file.** Use `--state-file
   eigen_initiative/phases/phase_<N>/pipeline_state_small.json` for **every** `eigen-small` call in
   this phase. This sidesteps the single-phase main state cleanly — each phase keeps its own
   wave/goal/review record, so the run is resumable and phases never overwrite each other.
   - If that per-phase state already shows all waves green + reviewed (a resumed run), **skip to the
     next phase**.
   - Otherwise initialize it: `eigen-small --state-file <p> init --initiative "<name>" --phase <N> --shape single_phase`,
     mark the planning stages resolved (`set-stage manifest|bootstrap|space_split --status done`),
     and load this phase's wave plan: `set-waves --waves "$(cat phases/phase_<N>/wave_plan.json)"`.
2. **Run the standard `small_build` per-wave loop** (Stages 1–3 of `small_build`) for phase N, against
   `phases/phase_<N>/` artifacts and `feat/P<N>.E<M>` / `wt-P<N>.E<M>` branches+worktrees. All the
   normal rules apply: orchestrator runs each goal as the oracle, strict file-ownership, explicit
   `git worktree add` for parallel epics, per-wave `/code-review` + risk reviewers, the goal+suite
   regression gate.
3. **Earlier phases' seams are read-only** — `eigen-small freeze-list --phase <N-1>`. Build against
   them; never mutate one. (They were frozen upfront by `small_plan_horizon`.)
4. **The last wave is the cumulative E2E gate** (phase N covers 1..N, per `phase_e2e_config.json`) —
   the only oracle for cross-phase integration.
5. **Bounded goal-retry circuit-breaker** (the Paso-0 rule): `--max-attempts N` (default 3)
   implementer round-trips per epic, feeding the failing assertions back each time. Count each
   still-red round-trip with `eigen-small --state-file <per-phase> record-goal-attempt <wave> <epic>`
   so the bound **survives a resume** — on re-entry, read the counter and do not re-loop past N (a
   human resets it with `--reset` to grant a fresh budget). On the Nth still-red attempt → **halt**
   (next section).
6. On phase N **fully green** (all waves' goals green + reviews done): `commit-state`, optionally
   write `phases/phase_<N>/build_notes.md` (gotchas worth a human's eye — advisory, not consumed by
   planning), then advance to phase N+1.

## Halt-and-surface (never push past a red goal)

If any epic's goal is still red after `--max-attempts N`, or a wave review's blocking findings can't
be cleared: **STOP the entire driver. Do not advance to phase N+1.** Report precisely: the phase, the
epic, the failing goal assertions, attempts made, and what was tried. Leave the per-phase state at the
red point (resumable once a human intervenes). Compounding a wrong phase into the next is the exact
failure this halt prevents.

## What this driver deliberately does NOT do

- **No watchdog / cron / claude-tasks / `.eigen` env.** It is one in-session sequential loop. (This
  is the line eigen-small holds vs eigen-squared; even squared keeps phase transitions human-gated.)
- **No re-planning, no re-opening goals.** Goals are frozen; the plan was approved in `small_review`.
- **No auto-approval.** Approval happened in `small_review`; this driver only consumes it.
- **No crossing a phase boundary on a red goal.** Sequential + halt-on-failure, always.

## Hard rules

1. **Refuse unless every discovered phase is `approved`** (`review-list`) and there are ≥2 phases.
2. **One isolated state file per phase** (`--state-file phases/phase_<N>/…`) — never re-point or
   overwrite a single shared state across phases.
3. **Halt on the first unreachable goal** (after `--max-attempts N`); never advance past it.
4. **Frozen seams + goal assertions are read-only**; the per-wave regression gate still applies.
5. **In-session only — no watchdog/daemon.** If you find yourself wanting cron, the work is
   eigen-squared-shaped.
