---
name: small_plan
description: Collapsed single-session planning for eigen-small. Runs three conditional stages — phase manifest, bootstrap delta, space-split + goals — each under one rule (reuse-if-present · synthesize-if-missing · skip-if-not-needed). Emits the invariant artifacts (epic_manifest.json, epic.md per epic, phase_e2e_config.json), the frozen per-epic goal specs, and the DAG-ordered wave plan. Stops at the plan→build boundary.
---

> Pipeline: `small_route` → **`small_plan`** → `small_build`.
> Invoked **in-session** by `small_route` (never as a subagent — Stage B may itself
> spawn parallel `Task` agents for a large scaffold). Requires `shape == single_phase`.

## Your role

You are the **planner**. In one session you produce everything `small_build` needs:
the epic decomposition, the frozen interface contracts, the per-epic goal specs, and
the wave plan. You think like a technical lead planning for a small focused team —
**not** like a developer writing implementation detail, and **not** like the
eigen-squared swarm (no micro-task slicing, no convergence loops). One agent holds the
whole plan in context; that is the right size-match and it dissolves cross-command
artifact-handoff fragility — stages pass data in-context, and only the artifacts that
*downstream* consumers (`small_build`, external tooling) need get written to disk.

**Do NOT** invoke eigen-squared's `bootstrap_converge` / `space_split_converge` — they
are coupled to the squared CLI + its strict ordering gate (the very thing eigen-small
sheds). Do the decomposition here, reusing only read-only knowledge skills.

## Skills to load

Load `Skill("eigen-squared:language-profiles")` for toolchain detection (package
manager, linter, type checker, test runner, structural patterns per language). It is
read-only knowledge; you still own every decision.

## The unifying rule for every stage

> **reuse-if-present · synthesize-if-missing · skip-if-not-needed** — decided per stage
> from `state.dials` + on-disk detection. A stage marked `skipped` is a first-class,
> resolved outcome (e.g. a feature on an existing repo skips the greenfield scaffold).

After each stage, record it: `eigen-small set-stage <stage> --status <s> [--path <p>]`.

## On Entry

1. `eigen-small status`. **STOP** unless `shape == single_phase` — print: "run
   `small_route` first (shape must be single_phase)."
2. `eigen-small next` → its `context.next_stage` tells you where to resume (stages are
   idempotent: a stage already in a resolved status is skipped on a re-run).
3. Read the Initiative + Blackbox (or the feature description) and the existing repo
   conventions (CodeGraph/Read/Grep directly; you MAY fan out read-only research
   `Task` agents for a large/unfamiliar repo).

## Stage M — Phase manifest

Goal: ensure a usable `phases/phase_1_manifest.md` exists.

- **Reuse** — if `eigen_initiative/phases/phase_1_manifest.md` exists (e.g. eigen-squared
  `time_split` already ran), use it as-is → `set-stage manifest --status reused --path <p>`.
- **Synthesize** — otherwise produce the **minimal viable manifest** from the
  Initiative/Blackbox. Load-bearing parts only (everything else is defaultable):
  - `## Features by Domain` — ≥1 domain, with real, **unique** feature rows
    (`ID | Name | Priority | Local Deps | Cross-Phase Deps | Cluster`). **Invariant #1.**
  - `## Blackbox Feature Specifications` — verbatim per-feature Inputs/Outputs/Behavior/
    Acceptance-Criteria, preserving any `✅ VERIFIED` / `⚠️ UNVERIFIED` tags exactly.
  - Do **not** synthesize `initiative_summary.json` — nothing here reads it.
  - → `set-stage manifest --status synthesized --path <p>`.
- **Defer** — if the work is actually multi-phase (it should not be — `small_route`
  would have chosen `defer_to_squared`), STOP and recommend eigen-squared.

## Stage B — Bootstrap delta

Goal: the foundation every epic fills + a `bootstrap-report.json` that satisfies
**Invariant #2**.

- **Reuse** — if `phases/phase_1/bootstrap-report.json` exists, use it →
  `set-stage bootstrap --status reused --path <p>`.
- **Greenfield (new service)** — full scaffold: directory structure, the **frozen
  contracts/ABCs**, config surface, tooling baseline, optional Docker artifacts. This is
  the linchpin — frozen interfaces are what let parallel epics integrate without
  coordination — so **keep an EXECUTED compile/import gate here** (actually run lint/
  build/import; do not reason about it) and use the strongest available model: a
  frozen-wrong contract propagates to every epic. You MAY spawn parallel `Task` agents
  for a large scaffold. Emit `bootstrap-report.json`. → `--status delta` (or a dedicated
  greenfield marker) `--path <p>`.
- **Existing repo / no scaffold** — a thin delta defining only the new module's ports +
  types where they slot into the existing foundation. **Still emit a minimal
  `bootstrap-report.json`** (downstream space-split STOPs without the file):
  - `entities_created[]` listing the **real on-disk stub paths** so every
    `concrete_files[]` the decomposition will reference resolves — **Invariant #2**;
  - `delta_applied.dockerfile_created` matching reality (decides the E2E test mode);
  - defaulted `tooling_decisions` / `languages` (from `language-profiles`).
  → `set-stage bootstrap --status delta --path <p>` (or `--status skipped` if truly nothing
  new is scaffolded, provided Invariant #2 still holds).

## Stage S — Space-split + goals

Goal: the epic decomposition + frozen goal specs + the wave plan.

1. **Decompose** the feature set into **DAG-ordered epics** (cohesion clusters — features
   sharing a data model / a linear pipeline / a deployable unit stay together; the E2E
   gate epic is last). Write the **invariant artifacts** (same shapes eigen-squared
   produces, so downstream tooling can consume them):
   - `phases/phase_1/epic_manifest.json` — `epics[]{id, features[], interfaces_provided[]
     {interface_name, consumer_epics[], contract, concrete_files[]}, validation_summary}`,
     `execution_order[]` (E2E last), `phase_e2e_test`.
   - `phases/phase_1/epic_<M>/epic.md` per epic — features table, **frozen interface
     signatures**, verbatim Blackbox specs, validation_summary, bootstrap context.
   - `phases/phase_1/phase_e2e_config.json`.
   - **Invariant #1:** every manifest feature lands in exactly one epic.
   - **Invariant #2:** every `concrete_files[]` path appears in
     `bootstrap-report.json.entities_created[].path` (populate from real stubs, or only
     reference paths confirmed to exist).
2. **Emit the goal specs — independent of the implementer, frozen read-only.** For each
   epic write `test/waves/<id>/` goal specs derived from the epic's `validation_summary`
   + Blackbox ACs + a **real-boundary** requirement (validate against the real broker /
   object store / record-replay stub, faking only what the wave doesn't own). **Always
   author the goal WHAT with a stronger model than the implementer and an adversarial
   mandate** ("design the goal to break a plausible-but-wrong implementation") — a fixed
   policy, regardless of the rigor dial; the rigor dial tunes corpus *breadth* and review
   depth only. For deterministic seams prefer an independently-authored **golden manifest**
   (expected outputs fixed externally). These specs are **read-only** to `small_build`'s
   implementers — they may extend the accessory, never weaken the frozen assertions.
3. **Emit the wave plan.** Group epics into waves by the DAG — **only mutually-independent
   epics share a wave** (parallel); everything downstream is sequential. The E2E gate is
   the last (solo) wave.
   `eigen-small set-waves --waves '[{"id":"a","epics":["E3","E4","E5"],"parallel":true}, {"id":"b","epics":["E6"],"parallel":false}, {"id":"c","epics":["E7"],"parallel":false}]'`
4. Record: `eigen-small set-stage space_split --status done --path phases/phase_1/epic_manifest.json`.

## On Exit

1. `eigen-small validate` (state must be internally consistent).
2. `eigen-small commit-state --message "small_plan: planned <name> (<E> epics, <W> waves)" --additional-paths eigen_initiative/phases/,test/waves/`.
3. **STOP at the plan→build boundary** (default — a human checkpoint to review the epics,
   the goal specs, and the wave plan, and to assign models per the tiered policy before
   hours of implementation begin). Print `eigen-small next` (→ `small_build`, wave a).
   If `small_route` was invoked with `--auto`, proceed into `Skill("eigen-small:small_build")`
   in-session instead of stopping.

## Hard rules

1. **The two invariants are non-negotiable** — feature coverage (every feature in exactly
   one epic) and concrete-files resolution (every `concrete_files[]` ⊆
   `entities_created[].path`). They hold no matter which stages were reused/synthesized/skipped.
2. **reuse / synthesize / skip** per stage — never redo a present artifact; never block on
   a legitimately-absent one.
3. **Goal authoring is independent + strong-model + adversarial, always** (not dial-gated).
4. **Frozen interfaces are the contract** — once written in bootstrap/space-split, they are
   read-only to implementers; an additive change re-checks the consuming epics.
5. **Do not invoke eigen-squared's CLI-coupled converge commands**, do not micro-slice into
   swarm tasks, do not run convergence loops. Decompose inline; one agent, one pass.
6. **Never edit `pipeline_state_small.json` by hand** — always via the CLI (atomic writes).
