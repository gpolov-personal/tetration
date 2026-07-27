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

Load `Skill("eigen-small:language-profiles")` for toolchain detection (package
manager, linter, type checker, test runner, structural patterns per language). It is
read-only knowledge; you still own every decision.

Load `Skill("eigen-small:goal-authoring")` before Stage S step 2 — the doctrine for the
per-epic goal specs (independent · strong-model + adversarial · real-boundary · golden-manifest ·
frozen oracle). It is the keystone that makes direct per-epic build safe.

## The unifying rule for every stage

> **reuse-if-present · synthesize-if-missing · skip-if-not-needed** — decided per stage
> from `state.dials` + on-disk detection. A stage marked `skipped` is a first-class,
> resolved outcome (e.g. a feature on an existing repo skips the greenfield scaffold).

After each stage, record it: `eigen-small set-stage <stage> --status <s> [--path <p>]`.

## On Entry

> **Phase slot (N).** Read `phase` from `eigen-small status` (or `next`'s `context.phase`; default 1). Every `phases/phase_<N>/…` path below uses that N — a phase-2 run (`init --phase 2`) reads/writes `phases/phase_2/…` and reuses the existing `phase_2_manifest.md`, never colliding with a `phase_1/` from an earlier (e.g. squared) run.

1. `eigen-small status`. **STOP** unless `shape == single_phase` — print: "run
   `small_route` first (shape must be single_phase)."
2. `eigen-small next` → its `context.next_stage` tells you where to resume (stages are
   idempotent: a stage already in a resolved status is skipped on a re-run).
3. Read the Initiative + Blackbox (or the feature description) and the existing repo
   conventions (CodeGraph/Read/Grep directly; you MAY fan out read-only research
   `Task` agents for a large/unfamiliar repo).
4. **Read the cross-phase freeze ledger** — the seams this phase must respect:
   `eigen-small freeze-list --phase <N-1>`. Every listed seam is **read-only** — build
   against it, never mutate it. If phase N's design would require **mutating** a frozen
   seam, that is a cross-cutting contradiction: STOP and reconcile (re-shape phase N, or
   surface that the earlier freeze was wrong) before proceeding.

## Stage M — Phase manifest

Goal: ensure a usable `phases/phase_<N>_manifest.md` exists.

- **Reuse** — if `eigen_initiative/phases/phase_<N>_manifest.md` exists (e.g. eigen-squared
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

- **Reuse** — if `phases/phase_<N>/bootstrap-report.json` exists, use it →
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
   - `phases/phase_<N>/epic_manifest.json` — `epics[]{id, features[], risk (concurrency|silent_corruption|external_integration|none), interfaces_provided[]
     {interface_name, consumer_epics[], contract, concrete_files[]}, validation_summary}`,
     `execution_order[]` (E2E last), `phase_e2e_test`.
   - `phases/phase_<N>/epic_<M>/epic.md` per epic — features table, **frozen interface
     signatures**, verbatim Blackbox specs, validation_summary, bootstrap context.
   - `phases/phase_<N>/phase_e2e_config.json`.
   - **Invariant #1:** every manifest feature lands in exactly one epic.
   - **Invariant #2:** every `concrete_files[]` path appears in
     `bootstrap-report.json.entities_created[].path` (populate from real stubs, or only
     reference paths confirmed to exist).
   - **Invariant #3 (AC→goal coverage):** every acceptance criterion in an epic's Blackbox spec
     maps to ≥1 assertion in that epic's goal (Step 2) — no AC left un-asserted. An orphan AC is a
     silent "passes-but-is-wrong" gap. Authored in Step 2, verified at On Exit.
2. **Emit the goal specs**, one per epic under `test/waves/<id>/`, **per the goal-authoring
   doctrine** (`Skill("eigen-small:goal-authoring")`, loaded above). Derive each from the epic's
   `validation_summary` + Blackbox ACs; validate against a **real boundary**; author it
   **independently** with a stronger model + an adversarial mandate; freeze it **read-only** to
   `small_build`'s implementers (golden manifest for deterministic seams). This is a fixed policy
   — the rigor dial tunes only corpus *breadth* and review depth, never whether the goal is
   independent/adversarial. See the skill for the full rationale.
3. **Emit the wave plan.** Group epics into waves by the DAG — **only mutually-independent
   epics share a wave** (parallel); everything downstream is sequential. The E2E gate is
   the last (solo) wave.
   `eigen-small set-waves --waves '[{"id":"a","epics":["E3","E4","E5"],"parallel":true}, {"id":"b","epics":["E6"],"parallel":false}, {"id":"c","epics":["E7"],"parallel":false}]'`
4. **Emit the per-run model plan** — `phases/phase_<N>/model_plan.yaml`, the **live, editable**
   knob the human tunes at the plan→build STOP and `small_build` reads before spawning each
   implementer. Pre-populate it with the **default tiering** (below), one row per epic, so the
   human only adjusts values:
   ```yaml
   # Edit during the plan→build checkpoint. small_build reads this before spawning each
   # implementer; if this file is absent it falls back to the same defaults by risk tag.
   defaults: { strong: <strongest available>, cheap: <cheaper> }
   goal_authoring: <strongest available>      # always strong — see the goal-authoring doctrine
   epics:
     E3: { model: <cheap>,  why: "spec-transcription / mechanical" }
     E4: { model: <strong>, why: "risk: concurrency — integration heart" }
     # ...one row per epic
   ```
   **Default tiering policy** (the basis for the pre-fill, and `small_build`'s fallback when the
   file is missing): **goal authoring** + the **riskiest epic** (`risk` ∈ {concurrency,
   silent_corruption, external_integration}) + the **integration-heart** (orchestration/wiring)
   epic + the **greenfield bootstrap gate** → **strongest** available model; mechanical /
   spec-transcription epics → a **cheaper** model. The frozen real-boundary goal is what makes a
   cheaper implementer safe. This file is the **only** place tiering is tuned per run — it lives
   under `EIGEN_ROOT` (the project), **not** in the plugin, so changing it never needs a reinstall.
5. **Cross-cutting critique — ONE adversarial pass, before you freeze anything.** Assume the
   decomposition is wrong and hunt the highest-severity contradiction. (This is the *one* job
   of the old convergence loop worth keeping — distilled to a single pass, **NOT a loop**.)
   - Do any two epics' to-be-frozen contracts / ACs **contradict** each other?
   - Would any contract you're about to **freeze need to mutate in a later phase**? (the
     `JUDGE_PII_PSEUDONYMISATION_ENABLED` boolean→set class — reshape it **now**, before the
     freeze, so the future phase plugs in additively.)
   - Does every manifest feature land in **exactly one** epic, every `concrete_files[]`
     resolve, and every AC map to ≥1 goal assertion (the three invariants — feature coverage +
     concrete-files resolution + AC→goal coverage, defined in Stage S)?
   Fix what you find by re-shaping the epics/contracts; only then freeze. One pass — if nothing
   high-severity surfaces, move on (**do not iterate**).
6. **Record this phase's freezes** so phase N+1 inherits them: for each interface/seam this
   phase freezes, `eigen-small freeze-add --phase <N> --name <seam> --kind frozen
   [--signature "<sig>"] [--consumers <csv>]`; for each seam deliberately left as an
   **extension hook** for a future phase, use `--kind hook` (the SVC-01 no-op-hooks pattern).
7. Record the stage done: `eigen-small set-stage space_split --status done --path phases/phase_<N>/epic_manifest.json`.

## On Exit

1. **Epic-readiness check** (one pass — the mini Handoff Test; "execute directly against epics"
   is only as good as the epics). Per epic confirm: clear, testable ACs; **frozen interface
   signatures** named; a **real-boundary goal spec** under `test/waves/<id>/`; a `risk` tag set;
   a unique feature→epic mapping (Invariant #1 — feature coverage); and that **every AC maps to ≥1
   goal assertion — flag orphan ACs** (Invariant #3 — AC→goal coverage). Fix gaps now — one pass, not an iterative gate.
2. `eigen-small validate` (state must be internally consistent).
3. `eigen-small commit-state --message "small_plan: planned <name> (<E> epics, <W> waves)" --additional-paths eigen_initiative/phases/,test/waves/`.
4. **STOP at the plan→build boundary** (default — a human checkpoint to review the epics,
   the goal specs, and the wave plan, and to **review/edit `phases/phase_<N>/model_plan.yaml`**
   — pre-filled with the default tiering — before hours of implementation begin). Print
   `eigen-small next` (→ `small_build`, wave a).
   If `small_route` was invoked with `--auto`, proceed into `Skill("eigen-small:small_build")`
   in-session instead of stopping.

## Hard rules

1. **The three invariants are non-negotiable** — feature coverage (every feature in exactly
   one epic), concrete-files resolution (every `concrete_files[]` ⊆ `entities_created[].path`),
   and AC→goal coverage (every AC asserted by ≥1 goal — no orphan ACs). They hold no matter which
   stages were reused/synthesized/skipped.
2. **reuse / synthesize / skip** per stage — never redo a present artifact; never block on
   a legitimately-absent one.
3. **Goal authoring is independent + strong-model + adversarial, always** (not dial-gated).
4. **Frozen interfaces are the contract** — once written in bootstrap/space-split, they are
   read-only to implementers; an additive change re-checks the consuming epics.
5. **Do not invoke eigen-squared's CLI-coupled converge commands**, do not micro-slice into
   swarm tasks, do not run convergence loops. Decompose inline; one agent, one pass.
6. **Never edit `pipeline_state_small.json` by hand** — always via the CLI (atomic writes).
