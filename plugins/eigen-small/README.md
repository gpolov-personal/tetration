# eigen-small

A **router-driven, artifact-robust, goal-gated** pipeline for small/medium work —
a feature or a single-phase product (roughly ≤ ~1,500–2,000 net-new LOC, often on
an existing codebase) where the full `eigen-squared` apparatus is over-scaled and
`eigen-lite`'s swarm-worker execution is not the model you want.

Full design: [`../../docs/eigen_small_design.md`](../../docs/eigen_small_design.md).

## What it is (and isn't)

| | scope | execution model | router? | artifact-robust? |
|---|---|---|---|---|
| `eigen-squared` | 10–150+ features, multi-phase | swarm TDD-A/B workers + 8-agent review + watchdog | no | no (strict ordering gate) |
| `eigen-lite` | 2–5 features, single-phase | still the squared TDD-A/B swarm workers | no | partial (skip-if-output-exists) |
| **`eigen-small`** | a feature / single-phase product | **direct build per epic + goal-as-stop-condition + lightweight review** | **yes** | **yes (reuse / synthesize / skip)** |

eigen-small's three genuinely-new contributions over the siblings: (1) a **router/triage**
front-end that sizes the work and prunes/synthesizes stages; (2) **artifact-robustness** —
run a stage even when its upstream was skipped, by synthesizing the minimal viable
artifact; (3) **goal-gate direct-build** — each epic is built straight from its
`epic.md`, gated by an executable real-boundary goal as its stop-condition, instead
of the swarm-worker decomposition.

## Commands

```
small_start   ONE-TIME setup: install the eigen-small CLI wrapper on PATH (manual-only; --reinstall-cli-only)
small_route   triage → shape + two dials → drives planning in-session → stops at the plan→build boundary
small_plan    collapsed planning: manifest → bootstrap-delta → space_split + goals (reuse / synthesize / skip)
small_build   wave executor: per-epic implementers (worktrees) → goal-gate stop-condition → per-wave review
```

## State CLI (thin, ~9 permissive verbs)

A thin CLI over `eigen-core`'s atomic raw I/O. **Permissive** — `next` reports the
next actionable step and never refuses a skipped or reordered stage (the opposite of
squared's hard ordering gate). State lives at
`eigen_initiative/phases/pipeline_state_small.json`.

```
small init --initiative <name> [--phase N] [--shape ...] [--structure ...] [--rigor ...]
small set-shape --shape single_phase --structure epics_parallel --rigor high
small status
small next                                  # permissive: next stage/wave or "done"
small set-stage manifest --status synthesized [--path ...]
small set-waves --waves '[{"id":"a","epics":["E3","E4","E5"],"parallel":true}, ...]'
small complete-epic a E4 --goal-green
small set-wave-review a --status done
small validate
small commit-state --message "..."
small freeze-add --phase 1 --name <seam> --kind frozen|hook [--signature ...] [--consumers ...]
small freeze-list [--phase N] [--kind frozen|hook]    # the cross-phase contract a later phase must respect
```

**Cross-phase freeze ledger** (`eigen_initiative/phases/freeze_ledger.json`): `small_plan`
records each phase's **frozen** seams (immutable contracts) and **hooks** (extension seams
left for a later phase). A phase-N run reads `freeze-list --phase <N-1>`, treats those as
read-only, and flags any design that would mutate one — this is the cross-phase verification
that makes the two-runs multi-phase approach safe.

Deliberately absent (the squared ceremony shed): the strict ordering gate, the
recommendation matrix, findings/signature validation, the scheduler/watchdog, and
the `gh`-probe guards.

## Architecture notes

- **Reuses `eigen-core`** (vendored into `_vendored/eigen_core/` by
  `tools/vendor-core.sh`): atomic state I/O + base models. A CLI is *required*, not
  optional — a markdown command can only get atomic writes by shelling out to a
  Python entry point.
- **Self-contained — no plugin dependencies.** Bundles its own read-only skills
  (`language-profiles` for toolchain detection, `security-best-practices` for secure-by-default
  coding/review) and review agents (`data-integrity-guardian`, `security-sentinel`,
  `architecture-strategist`, mapped from epic `risk` tags). These were vendored from
  eigen-squared so eigen-small stands alone.
- **Own flat state** (`pipeline_state_small.json`) with a `SquaredSchemaDetected`
  guard so it can never clobber a squared/lite state file.

## Two phases on one repo (run twice)

eigen-small is single-phase, but a 2-phase product (MVP → extensions) is supported as **two
runs**: do phase 1, then run again with `init --phase 2`. The phase-2 run slots its artifacts
into `phases/phase_2/`, **reuses** the existing `phase_2_manifest.md`, and builds on phase 1's
**frozen extension seams** (the no-op hooks pattern). It does **not** auto-plan both phases —
you sequence them (trivial for 2). **≥3 phases → use eigen-squared** (the router answers
`defer_to_squared`).

## Status

v1 complete: scaffold + thin CLI + `small_start` (CLI install) + the three pipeline
commands (`small_route` · `small_plan` · `small_build`). Registered in `marketplace.json`
(v0.4.0). Validated end-to-end via a `kvstore` dry-run. Supports a phase slot
(`init --phase N`) so a single run can layer as phase 2 onto an existing repo, plus the
§15 lean-philosophy refinements: a **cross-phase freeze ledger** (`freeze-add`/`freeze-list`),
a **one-pass cross-cutting critique** in `small_plan`, and **epic `risk` tags** driving
targeted review. As of v0.4.0: **self-contained** (no eigen-squared dependency — review agents
and reference skills vendored).
**Install with `/small_start`** (manual-only — no watchdog/env). Remaining hardening:
exercise the parallel-worktree fan-out and the manifest *reuse* path on a real project.
