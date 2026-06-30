---
name: small_review
description: Interactive comprehension + validation gate for eigen-small. Walks a human phase by phase through the specs (Blackbox features, epic.md) and the per-epic GOAL specs, SYNTHESIZED for fast understanding (layered disclosure — drill into the real artifact on demand), with a MECHANICAL AC→goal coverage check (no orphan ACs). Records a per-phase review approval. Run it at the plan→build boundary; approving every phase is the precondition for `small_build --unsupervised`.
---

> Pipeline: `small_route` → `small_plan`(`_horizon`) → **`small_review`** → `small_build`.
> Run **in-session** at the plan→build STOP. It is **read-only over the planning artifacts** —
> it writes nothing but a per-phase review approval. It does **not** re-plan and does **not**
> auto-review code; it helps a *human* understand and sign off the specs + goals fast.

## Your role

You are the **explainer + validator's assistant**, not a reviewer. Your job is to let a human
grasp, in minutes and without reading every line, *what each phase builds* and *what its GOAL must
prove for `small_build` to call the phase done* — and to confirm two things per phase: the specs
are well-conceived, and the GOAL aggregates **all** the ACs it must verify. You synthesize; the
human decides and approves.

## The CLI you use

```
eigen-small review-list                 # current per-phase approvals
eigen-small set-review --phase N --status approved [--note "..."]
eigen-small freeze-list --phase N       # the frozen cross-phase seams (surface these first)
```

## On Entry

1. **Discover the phases by disk**: glob `eigen_initiative/phases/phase_*/`. Each `phase_<N>/` with
   an `epic_manifest.json` is a reviewable phase. Works whether there is **one** phase (today's
   `small_plan`) or **several** (`small_plan_horizon`). Walk them in ascending phase order.
2. `eigen-small review-list` → which phases are already approved (idempotent: re-running re-walks
   only what you want; an approved phase can be re-reviewed and re-approved).
3. If no `phase_*/` exists → STOP: "run `small_plan` (or `small_plan_horizon`) first."

## Per-phase walkthrough

For each phase N, read its artifacts read-only — `phase_<N>_manifest.md` (`## Blackbox Feature
Specifications`), each `phase_<N>/epic_<M>/epic.md`, each goal under `test/waves/<id>/`, and
`eigen-small freeze-list --phase <N>` — then present it under this **synthesis contract**:

1. **Surface by risk, not by order.** Lead with the **frozen cross-phase seams** this phase
   exposes (what a later phase will inherit read-only) and the phase's E2E gate. These are the
   highest-blast-radius items; the human must see them first.
2. **Synthesize, with layered disclosure.** Give a tight plain-language summary per epic: *what it
   builds, its frozen interface, and the one-line "this epic is done when…"* derived from its GOAL.
   Offer to **drill into the real artifact** (the verbatim AC, the actual goal assertion) on
   request. The synthesis **indexes** the artifacts — it never replaces them, and the human can
   always open the real thing.
3. **Run the AC→goal coverage check MECHANICALLY, do not narrate it.** Compute the map: every
   acceptance criterion in the phase's Blackbox specs → the goal assertion(s) under
   `test/waves/<id>/` that exercise it. **Print the orphan ACs explicitly** (ACs asserted by no
   goal — Invariant #3). Do not say "coverage looks good"; show the mapping and the orphans (if any).
   An orphan AC is a silent "passes-but-is-wrong" gap and must be fixed in `small_plan` before approval.
4. **Ask the two validation questions** (use AskUserQuestion):
   - *Are this phase's specs well-conceived* (scope, the frozen seams, no contradiction)?
   - *Does the GOAL aggregate all the ACs* (zero orphans, real-boundary, the right stop-condition)?
5. **Record the verdict:**
   - Approved → `eigen-small set-review --phase <N> --status approved [--note "<what the human flagged>"]`.
   - Not approved → leave it `pending` and report precisely what to fix in `small_plan`
     (`small_plan_horizon`) — do **not** edit the plan here.

## On Exit

1. `eigen-small review-list` → the approval summary across phases.
2. Route the human:
   - **All discovered phases approved AND ≥2 phases** → `small_build --unsupervised` is now
     unlocked (sequential unattended build, gated by these approvals). Print the suggestion.
   - **Single phase approved** → normal `small_build` (supervised) — print `eigen-small next`.
   - **Any phase pending** → name the gaps; nothing downstream should run until they're resolved.

## Hard rules

1. **Read-only over planning artifacts.** `small_review` writes nothing but the per-phase review
   approval (via `set-review`). It never edits the manifest, epics, goals, or
   `pipeline_state_small.json`. Gaps are fixed by re-running `small_plan`, not here.
2. **Synthesis indexes, never replaces.** Always offer drill-down to the verbatim AC / goal
   assertion. The human must be able to validate the real artifact, not just your summary.
3. **The AC→goal coverage check is MECHANICAL, not narrated.** Show the AC→assertion mapping and
   print orphan ACs; never assert "covered" without the evidence.
4. **Surface highest-blast-radius first** — frozen cross-phase seams and the E2E gate before
   per-epic detail.
5. **Approval is the unsupervised precondition.** `small_build --unsupervised` requires **every
   discovered phase** approved here. A single un-approved phase blocks the unattended run.
