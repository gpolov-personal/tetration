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
small_route   triage → shape + two dials → drives planning in-session → stops at the plan→build boundary
small_plan    collapsed planning: manifest → bootstrap-delta → space_split + goals (reuse / synthesize / skip)   [forthcoming]
small_build   wave executor: per-epic implementers (worktrees) → goal-gate stop-condition → per-wave review     [forthcoming]
```

## State CLI (thin, ~9 permissive verbs)

A thin CLI over `eigen-core`'s atomic raw I/O. **Permissive** — `next` reports the
next actionable step and never refuses a skipped or reordered stage (the opposite of
squared's hard ordering gate). State lives at
`eigen_initiative/phases/pipeline_state_small.json`.

```
small init --initiative <name> [--shape ...] [--structure ...] [--rigor ...]
small set-shape --shape single_phase --structure epics_parallel --rigor high
small status
small next                                  # permissive: next stage/wave or "done"
small set-stage manifest --status synthesized [--path ...]
small set-waves --waves '[{"id":"a","epics":["E3","E4","E5"],"parallel":true}, ...]'
small complete-epic a E4 --goal-green
small set-wave-review a --status done
small validate
small commit-state --message "..."
```

Deliberately absent (the squared ceremony shed): the strict ordering gate, the
recommendation matrix, findings/signature validation, the scheduler/watchdog, and
the `gh`-probe guards.

## Architecture notes

- **Reuses `eigen-core`** (vendored into `_vendored/eigen_core/` by
  `tools/vendor-core.sh`): atomic state I/O + base models. A CLI is *required*, not
  optional — a markdown command can only get atomic writes by shelling out to a
  Python entry point.
- **Declares `dependencies: ["eigen-squared"]`** so it can reuse read-only skills
  (e.g. `language-profiles` for toolchain detection) via cross-plugin `Skill(...)`.
- **Own flat state** (`pipeline_state_small.json`) with a `SquaredSchemaDetected`
  guard so it can never clobber a squared/lite state file.

## Status

v1, in progress. Built so far: the plugin scaffold + thin CLI + `small_route`.
`small_plan` and `small_build` are the next increments.
