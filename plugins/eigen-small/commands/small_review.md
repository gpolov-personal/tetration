---
name: small_review
description: Interactive comprehension + validation gate for eigen-small. Per phase it FIRST generates a derived Gherkin view of the specs (review_specs.gherkin.md) and GATES on the human reading it; then walks the human through the specs (Blackbox features, epic.md) and the per-epic GOAL specs, SYNTHESIZED for fast understanding (layered disclosure — drill into the real artifact on demand), with a MECHANICAL AC→goal coverage check (no orphan ACs). Records a per-phase review approval. Run it at the plan→build boundary; approving every phase is the precondition for `small_build --unsupervised`.
---

> Pipeline: `small_route` → `small_plan`(`_horizon`) → **`small_review`** → `small_build`.
> Run **in-session** at the plan→build STOP. It is **read-only over the planning artifacts** —
> it writes nothing but a per-phase review approval and the derived Gherkin review aid
> (a regenerated VIEW, never a source). It does **not** re-plan and does **not**
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
`eigen-small freeze-list --phase <N>` — then:

0. **FIRST: generate the Gherkin review aid and GATE on the human reading it.** Write
   `eigen_initiative/phases/phase_<N>/review_specs.gherkin.md` per the format in *"The Gherkin
   review aid"* below — regenerated from scratch on every run (never read or patch a previous
   copy). Tell the human the path and give a one-paragraph orientation: features/scenario
   counts, the epics they map to, and — quoted verbatim — any `# ⚠ ORPHAN` evidence lines.
   Then **STOP and wait**: ask (AskUserQuestion) whether they have reviewed the file —
   *"Reviewed — all clear"* / *"I have questions"* / *"Something looks wrong"*. Answer questions
   by drilling into the scenario **alongside** the verbatim AC and the goal assertion it
   renders; re-ask until they confirm. Do NOT start the synthesis walkthrough (steps 1–5)
   before that confirmation. If something looks wrong, capture it precisely — it feeds the
   step-5 verdict (a spec defect routes back to `small_plan`, like any other).

Then present the phase under this **synthesis contract**:

1. **Surface by risk, not by order.** Lead with the **frozen cross-phase seams** this phase
   exposes (what a later phase will inherit read-only) and the phase's E2E gate. These are the
   highest-blast-radius items; the human must see them first.
2. **Synthesize, with layered disclosure.** Give a tight plain-language summary per epic: *what it
   builds, its frozen interface, and the one-line "this epic is done when…"* derived from its GOAL.
   Offer to **drill into the real artifact** (the verbatim AC, the actual goal assertion, or its
   Gherkin scenario — tagged `@F<i>-AC<j>` in the review aid) on
   request. The synthesis **indexes** the artifacts — it never replaces them, and the human can
   always open the real thing.
3. **Run the AC→goal coverage check MECHANICALLY, do not narrate it.** Compute the map: every
   acceptance criterion in the phase's Blackbox specs → the goal assertion(s) under
   `test/waves/<id>/` that exercise it. **Print the orphan ACs explicitly** (ACs asserted by no
   goal — Invariant #3). Do not say "coverage looks good"; show the mapping and the orphans (if any).
   An orphan AC is a silent "passes-but-is-wrong" gap and must be fixed in `small_plan` before approval.
   The review aid's `# goal:` / `# ⚠ ORPHAN` evidence lines are this same mapping made visible —
   they MUST agree with what you print here; if they do not, the aid was generated wrong:
   regenerate it (the mapping you compute is the truth, the file is its rendering).
4. **Ask the two validation questions** (use AskUserQuestion):
   - *Are this phase's specs well-conceived* (scope, the frozen seams, no contradiction)?
   - *Does the GOAL aggregate all the ACs* (zero orphans, real-boundary, the right stop-condition)?
5. **Record the verdict:**
   - Approved → `eigen-small set-review --phase <N> --status approved [--note "<what the human flagged>"]`.
   - Not approved → leave it `pending` and report precisely what to fix in `small_plan`
     (`small_plan_horizon`) — do **not** edit the plan here.

## The Gherkin review aid (step 0's artifact)

**Path:** `eigen_initiative/phases/phase_<N>/review_specs.gherkin.md` — one per phase,
**overwritten on every run**, generated ONLY from `phase_<N>_manifest.md` + the frozen goals
under `test/waves/*` (never from its own previous version).

**It is a VIEW, not a source.** The file MUST open with this header (adapted to the phase):

> **DERIVED VIEW — non-normative.** Regenerated by `small_review` on every run from
> `phase_<N>_manifest.md` + `test/waves/*`. On any conflict, the manifest ACs and the frozen
> goals win. Never hand-edit. NOT an input to `small_plan` or `small_build`.

**Format.** One ```` ```gherkin ```` block per Blackbox feature, in F-order:

- `Feature: F<i> — <feature name>`, with the manifest's one-line purpose as the description.
- One `Scenario:` per AC, tagged `@F<i>-AC<j> @epic-<id>`.
- Directly under the Scenario title, the AC's **verbatim text as `#` comments** — the fidelity
  anchor that lets the human audit the rendering against the real AC without leaving the file.
- `Given`/`When`/`Then` derived from the AC **and** its goal assertion(s) — prefer the goal's
  concrete observables (golden hashes, exact byte counts, key shapes, ordered events) in the
  `Then`: they make the scenario sharper than the prose.
- Close every scenario with exactly ONE evidence line:
  - `# goal: <pytest node id(s)>` — the assertion(s) that exercise it;
  - `# regression: <command>` — for ACs the manifest maps to a regression command, not a goal;
  - `# ⚠ ORPHAN — no goal assertion` — must match what step 3 prints.

**Translation rules.**

- Behavioral ACs → straight Given/When/Then.
- Structural/static ACs (frozen signature pins, banned imports, packaging/policy posture) →
  inspection form: `Given <the artifact/source tree> / When <what is inspected> / Then <the
  pinned fact>`. Never contort a static pin into fake behavior.
- If an AC cannot be rendered faithfully, transcribe it verbatim inside the Scenario as
  comments and mark it `# rendered-as-is` — a wrong-but-pretty scenario is worse than none.
- Invent NOTHING: every Given/When/Then clause must trace to the AC text or to a goal
  assertion. The aid may only ever *restate*, never *extend*, the spec.

**Canonical example** (shape to imitate — a behavioral AC with a golden pin):

```gherkin
@F1-AC2 @epic-P2E1
Scenario: Comm container is byte-pinned to the spec manifest
  # AC (verbatim): "golden bytes — encoding the frozen fixture (seeded vectors +
  # fixed chunks) yields the pinned sha256 and byte length."
  Given the frozen comm fixture (3 chunks, seeded vectors, real offsets 0/120/480)
  When it is encoded with encode_comm_object
  Then the container is exactly 9760 bytes
  And its sha256 equals the golden manifest's pinned hash
  # goal: test/waves/P2E1/test_goal_storage.py::TestCommCodec::test_golden_bytes
```

## On Exit

1. `eigen-small review-list` → the approval summary across phases.
2. Route the human:
   - **All discovered phases approved AND ≥2 phases** → `small_build --unsupervised` is now
     unlocked (sequential unattended build, gated by these approvals). Print the suggestion.
   - **Single phase approved** → normal `small_build` (supervised) — print `eigen-small next`.
   - **Any phase pending** → name the gaps; nothing downstream should run until they're resolved.

## Hard rules

1. **Read-only over planning artifacts.** `small_review` writes nothing but the per-phase review
   approval (via `set-review`) and the derived Gherkin review aid
   (`review_specs.gherkin.md`, regenerated every run). It never edits the manifest, epics,
   goals, or `pipeline_state_small.json`. Gaps are fixed by re-running `small_plan`, not here.
2. **Synthesis indexes, never replaces.** Always offer drill-down to the verbatim AC / goal
   assertion. The human must be able to validate the real artifact, not just your summary.
3. **The AC→goal coverage check is MECHANICAL, not narrated.** Show the AC→assertion mapping and
   print orphan ACs; never assert "covered" without the evidence.
4. **Surface highest-blast-radius first** — frozen cross-phase seams and the E2E gate before
   per-epic detail.
5. **Approval is the unsupervised precondition.** `small_build --unsupervised` requires **every
   discovered phase** approved here. A single un-approved phase blocks the unattended run.
6. **The Gherkin gate blocks the walkthrough.** Per phase, the review aid is generated FIRST and
   the human's explicit confirmation that they reviewed it is required before any synthesis or
   validation question. No confirmation, no walkthrough.
7. **The Gherkin aid is a VIEW, never a source.** Regenerated from the manifest + frozen goals on
   every run; never hand-edited, never read back as input, never consumed by `small_plan` or
   `small_build`. On any conflict, the manifest AC and the frozen goal win — fix the rendering,
   never the spec, from here.
