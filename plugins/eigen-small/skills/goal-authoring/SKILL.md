---
name: goal-authoring
description: "The eigen-small doctrine for authoring per-epic goal specs as independent real-boundary oracles. Load when small_plan authors the test/waves/<id>/ goal specs, or when small_build runs/enforces them as the stop-condition. Defines what makes a goal a valid oracle: independent, strong-model + adversarial, real-boundary, golden-manifest for deterministic seams, frozen read-only."
---

# Goal Authoring — the independent real-boundary oracle

This is the **keystone** of eigen-small. Each epic's goal spec (under `test/waves/<id>/`) is
the **independent oracle** that decides whether the epic is done. It is what lets eigen-small
build each epic **directly** — one focused implementer, no swarm TDD-A/B ceremony — and still
be safe: the goal, not the implementer's self-report, is the source of truth. `small_plan`
**authors** these specs; `small_build` **runs** them as the per-epic stop-condition and the
post-fix regression gate.

A goal is a valid oracle only if it satisfies all five properties below.

## 1. Independent of the implementer

The goal is authored **separately from** (and **before**) the code that will satisfy it, and is
**read-only** to the implementer. An implementer may *extend* the accessory (add cases) but may
**never weaken** a frozen assertion. The orchestrator — not the implementer — runs the goal and
confirms it green; an implementer's "it passes" is never sufficient evidence.

## 2. Strong-model + adversarial — always (not dial-gated)

Author the goal *WHAT* with a **stronger model than the implementer**, under an explicit
adversarial mandate: **"design the goal to break a plausible-but-wrong implementation."** This is
a **fixed policy**, independent of the rigor dial. The rigor dial tunes only the corpus *breadth*
and the review depth — it never decides whether the goal is adversarial or independent. (See the
model tiering for *which* model is "stronger" on a given run; goal authoring is always at the top
tier.)

## 3. Real-boundary

Validate against the **real boundary** the epic integrates with — the real broker / object store
/ database, or a record-replay stub of it — **faking only what the wave does not own**. A goal
that passes against an in-process mock of the very seam under test is not an oracle. This is also
the economic linchpin: *the frozen real-boundary goal is what makes a cheaper implementer safe*,
because a wrong implementation fails against the real boundary regardless of who wrote it.

## 4. Golden manifest for deterministic seams

For deterministic transforms (offset converters, serializers, pure pipelines), prefer an
**independently-authored golden manifest** — the expected outputs fixed *externally*, not derived
from the implementation. The implementation must match the manifest; the manifest never bends to
the implementation.

## 5. Frozen oracle

Once authored, the goal's assertions are **frozen and read-only** to `small_build`'s implementers
(extend the accessory, never weaken the assertions) and the orchestrator runs them verbatim as:
- the **per-epic stop-condition** (Stage 2 goal gate — green against the real boundary, or the
  implementer goes back); and
- the **regression gate** after any review fix (a fix is not done until its affected goal AND the
  unit suite are green again).

---

**One-line invariant:** the goal is authored independently, by a stronger model, adversarially,
against the real boundary, and is frozen — so passing it is genuine evidence of correctness, not
a self-graded claim.
