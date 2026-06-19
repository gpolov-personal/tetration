# eigen-small — Design Document

**Status:** proposed (design only — no plugin files yet)
**Date:** 2026-06-18
**Build decision (recorded):** fresh sibling plugin `eigen-small` (not a fork of `eigen-lite`); reuse the `eigen-core` vendored primitives + the eigen-lite *scaffolding pattern*, but a genuinely different execution philosophy.
**Command surface (recorded):** three commands — `small_route`, `small_plan`, `small_build`. No mirror of squared's many planning commands; no `small_time_split`.

> **Location note:** this doc lives in the tetration repo (where the plugin will live), not in the judge service repo where it was drafted. Move it if you prefer it co-located with the experiment.

---

## 1. Purpose & positioning

`eigen-small` is a **router-driven, artifact-robust, goal-gated** pipeline for small/medium work (a feature or a single-phase product, roughly ≤ ~1,500–2,000 net-new LOC, often on an existing codebase) where the full eigen-squared apparatus is over-scaled.

It is the codification of an execution model proven in practice on the LLM-as-Judge Phase 1 (`docs/llm_judge/phase1_lightweight_build_plan.md` in the judge repo): keep the cheap high-value upstream artifacts (the epic DAG + the WHAT-only `epic.md` specs + the frozen interfaces), drop the heavy coordination machinery (`create_issues` micro-tasking, `orchestrate_swarm` TDD-A/B fan-out, the 8-agent × 3-iteration `review_swarm_pr`), and replace the swarm's safety net with **per-seam executable goals against real boundaries as hard stop-conditions**, plus a lightweight per-wave code-review.

### What makes it distinct from the siblings

| Plugin | Scope | Execution model | Has a router? | Artifact-robust? |
|---|---|---|---|---|
| `eigen-squared` | 10–150+ features, multi-phase, autonomous | swarm: TDD-A/B workers + 8-agent review, convergence loops, watchdog | no (human flowchart) | no — hard stage-ordering gate |
| `eigen-lite` | 2–5 features, single-phase | still the squared TDD-A/B swarm workers (via `lite_swarm`) | no | partial (skip-if-output-exists) |
| **`eigen-small`** | a feature / single-phase product | **direct build per epic + goal-as-stop-condition + lightweight review** | **yes (`small_route`)** | **yes (reuse / synthesize / skip)** |

`eigen-lite` already collapsed planning into one command and reuses workers — so eigen-small is **not** "a smaller pipeline" (lite already is that). Its genuinely new contributions are three: (1) the **router/triage** front-end that sizes the work and prunes/synthesizes stages; (2) **artifact-robustness** as a first-class principle (run a stage even when its upstream was skipped, by synthesizing the minimal viable artifact); (3) the **goal-gate direct-build** execution model instead of the swarm-worker TDD-A/B decomposition.

---

## 2. Core philosophy (five principles)

1. **Scaffolding is inversely proportional to implementer strength.** The two things that actually matter are *frozen contracts* (coordination) and an *independent oracle* (validation). Keep exactly those; drop task-slicing and multi-agent review ceremony.
2. **The goal is the definition of done.** Each epic's stop-condition is an executable accessory that validates the seam against its **real boundary** (real broker / real object store / real record-replay stub) — an oracle the implementing agent cannot fake. "Done" = the goal runs green, not "my tests pass + someone reviews later."
3. **Two orthogonal dials, never conflated:** *structural decomposition* (driven by size + fan-out) and *validation rigor* (driven by risk). A small-but-dangerous job = minimal structure + maximal validation.
4. **Reuse / synthesize / skip.** Every planning stage is conditional: reuse the artifact if it exists, synthesize the minimal viable version if it's missing, skip it entirely if the work doesn't need it.
5. **The router decides and sequences; it does not execute.** Triage + planning orchestration is a cheap, re-runnable decision layer. Wave execution is a separate, heavier, resumable engine.

---

## 3. Relationship to existing plugins (what to reuse, what to avoid)

**Reuse (`eigen-core`, vendored):** the atomic state I/O (`save_raw_state`/`load_raw_state` — tmp-file + `os.replace`, no torn writes) and the base models (`MainCommandState`, `Convergence`, `Recommendation`). Vendor it the same way lite/squared do (`tools/vendor-core.sh` → `_vendored/eigen_core/`, `cli/__init__.py` injects `_vendored/` onto `sys.path`).

**Reuse the eigen-lite *pattern*:** flat per-plugin state, own thin state surface, own state file (`pipeline_state_small.json` / `.eigen-small/`), a `SquaredSchemaDetected`-style guard so it can never clobber squared/lite state. **Reuse `Skill("eigen-squared:language-profiles")`** for toolchain detection (package manager, linter, test runner, structural patterns per language) — recorded decision. Declare `"dependencies": ["eigen-squared"]` in the manifest (as eigen-lite does); it is read-only knowledge with no execution coupling.

**Do NOT reuse the squared `cli/` (the 22-verb CLI).** Verified: its `determine_next` + `get-context` **hard-block out-of-order execution** ("Next command is X, not Y", non-zero exit) and **refuse to skip `time_split`** — there is no `--force-stage`. That ordering gate is exactly what eigen-small must relax. Wrapping that CLI would drag in the strict gate, the nested phase/epic schema, the `gh`-probe guards, and the recommendation matrix — all the ceremony we're shedding.

**Do NOT reuse the swarm workers for execution.** `eigen-lite` reuses `design_validation_tests_swarm` + `code_from_validation_tests_swarm`; eigen-small deliberately does not — the goal-gate direct build is the whole point of divergence.

---

## 4. State model

A minimal flat JSON state, written through a **thin CLI (~6–7 verbs)** that wraps eigen-core's atomic I/O. There **is** a CLI — but not squared's 22-verb surface, and crucially **no strict ordering gate**: `small next` is *permissive* (computes the next stage/wave from the shape, never refuses a skip or reorder). A CLI is required, not optional: `eigen-core` is a Python library, so a markdown command can only get atomic writes (tmp + `os.replace`) and a deterministic `next`/`status` by shelling out to a Python entry point — managing the JSON with `jq`/`cat >` from a prompt would be the non-atomic, torn-write failure mode eigen-core exists to prevent.

**CLI surface (deliberately thin):**

```
small init                       create .eigen-small/state.json (shape + dials)
small status [--json]            render current state
small next   [--json]            PERMISSIVE transition: next stage/wave (or "done"); never blocks a skip
small set-stage <s> --status reused|synthesized|delta|skipped|done [--path ...]
small complete-epic <wave> <epic> [--goal-green]
small commit-state --message ... [--additional-paths ...]
```

Deliberately absent (the squared ceremony we shed): the strict ordering gate, recommendation matrix, findings/signature validation, scheduler/watchdog (v1), gh-probe guards. Concurrency: prefer a **single-writer** model (the `small_build` parent records epic outcomes after each implementer returns), so atomic writes suffice; eigen-core's `flock` is available (vendored, free) if implementers ever write their own status.

```jsonc
// eigen_initiative/phases/pipeline_state_small.json   (ecosystem-consistent with lite/squared; guarded: refuse to operate on a squared/lite schema)
{
  "schema": "eigen-small/1",
  "initiative": "<name>",
  "shape": "direct | single_phase | defer_to_squared",
  "dials": { "structure": "none|epics|epics_parallel", "rigor": "low|standard|high" },
  "stages": {
    "manifest":  { "status": "reused|synthesized|skipped", "path": "..." },
    "bootstrap": { "status": "reused|delta|synthesized|skipped", "report_path": "..." },
    "space_split": { "status": "done", "epic_manifest": "...", "epics": ["E3","E4","E5","E6","E7"] }
  },
  "waves": [
    { "id": "a", "epics": ["E3","E4","E5"], "parallel": true,
      "epic_status": {"E3":"pending","E4":"pending","E5":"pending"},
      "goal_status": {"E3":"pending","E4":"pending","E5":"pending"},
      "review_status": "pending" },
    { "id": "b", "epics": ["E6"], "parallel": false, "goal_status": {"E6":"pending"}, "review_status": "pending" },
    { "id": "c", "epics": ["E7"], "parallel": false, "goal_status": {"E7":"pending"}, "review_status": "pending" }
  ],
  "updated_at": "<ISO>"
}
```

Convergence loops are *not* modelled — eigen-small is single-pass by design (the goal gate is the convergence). The state exists for resumability (which wave/epic is done) and to carry the router's decision into `small_build`.

---

## 5. Command surface

```
small_route   triage → shape + dials → drives the planning stages in-session → emits the wave plan
small_plan    collapsed planning: manifest → bootstrap-delta → space_split + goals (each stage: reuse/synthesize/skip)
small_build   wave executor: per-wave implementers (worktrees) → goal-gate stop-condition → per-wave code-review
```

Three commands, invoked in sequence. `small_route` is the entry point and the only thing the user runs by hand; it drives `small_plan` in-session, then hands off to `small_build` (in-session or as the operator's next explicit step).

---

## 6. `small_route` — the router / triage

**Job:** size the work, pick a shape + the two dials, then drive the planning stages. It is cheap and re-runnable.

### 6.1 Triage (may be a subagent that returns a recommendation)

Estimate a handful of signals from the Initiative/Blackbox (or a feature description):

| Signal | Feeds |
|---|---|
| feature count | structure dial; shape |
| net-new LOC estimate (greenfield vs port-heavy) | structure dial |
| greenfield-new-service **vs** feature-in-existing-repo | bootstrap scale |
| phase-boundary obviousness / DAG complexity | shape (single-phase vs defer-to-squared) |
| number of cohesive clusters | epic fan-out (parallel vs sequential) |
| **risk surface** (silent-corruption, concurrency, external integrations) | **rigor dial** (independent of size) |

The triage is the one piece that may run as a subagent (bounded analysis → returns a recommendation). Keep it cheap — a short prompt estimating ~6 signals and picking among named outputs. *Do not* build an elaborate scoring system; the irony of a heavyweight router to avoid heavyweight pipelines is the failure mode to avoid.

### 6.2 The two dials (orthogonal)

- **Structure** ∈ `{none, epics, epics_parallel}` — driven by size + fan-out + DAG obviousness.
- **Rigor** ∈ `{low, standard, high}` — driven by risk. Controls: goal corpus breadth / adversarial coverage, code-review depth, and whether the riskiest *implementation* epic goes to the strongest model. (Independent goal-authoring by a **strong model** is **always on** — a fixed policy, not a dial; see §9.)

A small-but-risky job (an offset converter, a crypto routine, a concurrent dispatcher) → `structure=epics, rigor=high`. Conflating the two is the trap.

### 6.3 The three shapes

| Shape | When | What the router does |
|---|---|---|
| **0 — Direct** | trivial / one cohesive change (≲ ~200 LOC, fits one agent's head) | No pipeline. Emit guidance: "implement + TDD on risky bits + `/code-review`." Stop. |
| **1 — Single-phase + epics** | small/medium; obvious (single) phase; benefits from epic decomposition / parallelism | Drive `small_plan` (manifest → bootstrap-delta → space_split + goals), then `small_build`. **The main path.** |
| **2 — Defer to eigen-squared** | many features; non-obvious phase boundaries; multi-phase | Stop and recommend `eigen-squared` (do not reinvent the heavy pipeline). |

### 6.4 How it drives (critical mechanics)

- The router **invokes the planning stages in its own session, in dependency order** — it does **not** wrap them in subagents. Verified reason: `small_plan`'s bootstrap stage may itself spawn parallel `Task` agents for a large scaffolding delta plus a reviewer; nesting those inside a router-spawned subagent hits agent-nesting limits and races on the shared checkout.
- The only subagent the router spawns is the **triage**.
- It **stops after planning by default** (a human checkpoint at the plan→build boundary — review the epics, goals, and wave plan, and assign models before hours of implementation begin). `--auto` proceeds into `small_build` in-session. Either way, `small_build`'s per-epic implementers spawn from the top level (never wrapped in a router subagent).

---

## 7. `small_plan` — collapsed planning (reuse / synthesize / skip)

One command, internal conditional stages. Collapsing planning (the eigen-lite precedent) is deliberate: a single agent holding the whole plan in context is the right size-match, **and it largely dissolves the "robust to missing artifacts" problem** — there is no cross-command file handoff to break; stages pass data in-context and only the artifacts that *downstream* consumers (`small_build`, external tooling) need get written.

### 7.1 The unifying rule for every stage

> **reuse-if-present · synthesize-if-missing · skip-if-not-needed** — driven by the router's shape/dials + on-disk detection.

This single rule covers two concerns at once: *robustness to a skipped upstream* **and** *not redoing work already done* (e.g., the judge case, where eigen-squared's `time_split` + `space_split` had already run — `small_plan` detects and reuses them).

### 7.2 Stage M — Phase manifest

- **Reuse:** if `phases/phase_N_manifest.md` exists, use it.
- **Synthesize (single-phase):** otherwise produce the **minimal viable manifest** from the Initiative/Blackbox. Verified load-bearing parts only: the **`## Features by Domain` table** (≥1 domain, real+unique feature rows with ID/Name/Priority/Deps/Cluster/Domain) and the **`## Blackbox Feature Specifications`** (verbatim per-feature Inputs/Outputs/Behavior/AC). Everything else (e2e_summary, clusters_included, priority_distribution, cross-phase deps, downstream notes) is defaultable/ignorable.
- **Do not synthesize `initiative_summary.json`** — verified: `bootstrap_converge` never reads it; it is CLI/state bookkeeping, not a planning input.
- **Defer:** if the router said Shape 2, hand to eigen-squared's real `time_split` instead.

### 7.3 Stage B — Bootstrap delta

- **Reuse:** if `phases/phase_N/bootstrap-report.json` exists, use it.
- **Greenfield:** full scaffold (directory structure, frozen contracts/ABCs, config, tooling baseline, optional Docker) — the foundation every epic fills. **This is the linchpin** (frozen interfaces are what let parallel epics integrate without coordination), so even at low rigor, keep an **executed compile/import gate** here and put it on the strongest model — a frozen-wrong contract is the most expensive error class (it propagates to every epic).
- **Existing repo / `--no-scaffold`:** thin "define the new module's ports + types" delta, **but still emit a minimal `bootstrap-report.json`**. Verified hard requirement: `space_split` STOPs if the report file is absent. Minimal viable contents:
  - `entities_created[]` listing the **real on-disk stub paths** (so every `concrete_files[]` the decomposition references resolves — see §10, invariant #2),
  - `delta_applied.dockerfile_created` matching reality (decides the E2E test mode),
  - defaulted `tooling_decisions` / `languages`. Everything else empty/zero.
- **May fan out:** for a large greenfield delta, this stage may spawn parallel `Task` agents for scaffolding (this is why the router must not wrap `small_plan` in a subagent).

### 7.4 Stage S — Space split + goals

- Decompose the feature set into DAG-ordered epics (reuse the cluster column / natural clusters), writing the invariant artifacts (`epic_manifest.json`, per-epic `epic.md`, `phase_e2e_config.json`). Epics are cohesion units; the E2E gate epic is last.
- **Emit the goal specs here, independent of the implementer** (see §9). Derive each goal from the epic's `validation_summary` + Blackbox ACs + the real-boundary requirement; write to `test/waves/<id>/` as a **frozen, read-only** spec (assertions + golden manifest where applicable). **Always** author goals with a **stronger model** than the implementer and an adversarial mandate — a fixed policy, not dial-gated (recorded decision).
- **Emit the wave plan** into state: group epics into waves by the DAG. Only mutually-independent epics share a wave (parallel); everything downstream is sequential.

---

## 8. `small_build` — wave executor (separate from the router)

**Why a separate command, not "inside the router":**
1. **Lifecycle:** triage is seconds; wave execution is hours. Coupling kills the router as a cheap re-runnable decision point.
2. **Parallelism + worktrees:** Wave A spawns one implementer per independent epic in **explicit `git worktree add` dirs** — heavy orchestration the router shouldn't carry, and the exact place the worktree race bit before (see §12).
3. **Resumability:** per-wave resume (crash mid-Wave-B → resume from the incomplete wave) wants its own wave-state.
4. **Nesting:** implementers spawn from the top level so they can in turn spawn a reviewer / read fixtures; `small_build` is invoked in-session, never wrapped by the router as a subagent.

### 8.1 Per-wave loop (DAG order)

For each wave:

1. **Implement.** One focused agent per epic.
   - **Parallel wave (independent epics):** each implementer in its **own `git worktree add` directory** + its own branch. Strict file-ownership (touches only its subpackage + its own test file; contracts/config are read-only).
   - **Sequential wave (e.g. E6 orchestration, E7 gate):** one implementer.
   - Each implementer builds **directly from `epic.md`** (TDD on the risky features), keeps frozen signatures, follows logging/secret guardrails.
2. **Goal gate (the stop-condition).** The implementer **does not close** until its `test/waves/<id>/` goal accessory runs **green against the real boundary** (broker / object store / record-replay stub — fake only what the wave doesn't own). The implementer may *extend* the accessory with more cases but **never weaken the frozen assertions**.
3. **Code-review (per-wave gate, lightweight).** After goals green + merge: a `/code-review` pass on the diff (+ one targeted reviewer on the high-risk epics). **Triage findings → fix blocking / cheap-isolated in-wave → re-run the affected goal + unit suite as the regression gate (a fix is not done until its goal is green again) → re-review the fix diff if non-trivial → wave done.** Record the rest as documented follow-ups.

### 8.2 Model assignment (the tiered model)

- **Goal authoring + the riskiest epic (typically E6 orchestration: async fan-out, fail-open ordering, breaker under load) → the strongest model**, plus a **targeted concurrency review** even in the lightweight regime. These are "get-it-right-once" linchpins; their failure mode (a frozen-wrong contract, a silent race) is the most expensive.
- **Implementation volume (mechanical/spec-transcription epics) → a cheaper / open-weight model.** The real-boundary goal is the guardrail that makes this safe — the agent can't ship confidently-wrong code past an oracle it can't fake.

---

## 9. Goal authoring — independent and frozen

The goal accessory is the independent oracle, so its *definition* must not be authored by the agent that implements the epic (they'd share a blind spot).

- **Separate the WHAT, not necessarily the HOW.** The success criteria + coverage (which cases, which assertions, the golden manifest) are authored in `small_plan`'s Stage S — derived from the already-converged `epic.md` `validation_summary` + Blackbox ACs — and **frozen read-only** (extend the "never alter frozen signatures" rule to "never weaken frozen goal assertions"). The implementer may write the driver mechanics and add cases.
- **The real boundary is the first line of independence** (reality doesn't share the agent's blind spot — e.g., a real S3 `GetObject` catching a prefix-stripped-key bug that all-local tests passed). Independent authoring is the **second** line, and it pays off most exactly where the boundary is a weak oracle: **coverage decisions** and **non-deterministic concurrency**.
- For deterministic seams, the strongest form is an **independently-authored golden manifest** (expected outputs fixed externally) — the implementer literally cannot pass without correct behavior.
- **Always (fixed policy, recorded decision):** the goal WHAT is authored by a **stronger model** than the implementer, with an adversarial mandate ("design the goal to break a plausible-but-wrong implementation"), independent of the epic's implementer — regardless of the rigor dial. The rigor dial tunes corpus *breadth* and review depth, **not** whether the author is independent/strong.

---

## 10. The two non-negotiable invariants

From the verified artifact-contract map, two cross-artifact invariants must hold no matter which stages were synthesized vs reused:

1. **Feature coverage:** every feature in the manifest's `## Features by Domain` table is real and unique, and lands in exactly one epic. (Downstream coverage gate.)
2. **Concrete-files resolution:** every `concrete_files[]` path that the epic decomposition references appears in `bootstrap-report.json.entities_created[].path`. (Downstream verification gate — failure is always high-severity.) Two safe strategies: populate `entities_created` from the real on-disk stubs, **or** have the decomposition emit only paths confirmed to exist.

Everything else in the handoff artifacts is defaultable or ignorable (per the contract map), which is *why* the synthesize shims are small.

---

## 11. Plugin file structure (fresh, mirroring the eigen-lite pattern)

```
plugins/eigen-small/
├── .claude-plugin/
│   └── plugin.json                 # { name, version, description, dependencies:["eigen-squared"], keywords, homepage }
├── commands/
│   ├── small_route.md              # router / triage
│   ├── small_plan.md               # collapsed planning (reuse/synthesize/skip)
│   └── small_build.md              # wave executor + goal-gate + per-wave review
├── cli/                            # thin CLI (~6–7 verbs) — see §4 for the surface
│   ├── __init__.py                 # sets __version__, injects _vendored on sys.path
│   ├── __main__.py                 # `python3 -m cli`
│   ├── main.py                     # argparse dispatch (init/status/next/set-stage/complete-epic/commit-state)
│   ├── state_small.py              # flat Lite-style state model over eigen-core MainCommandState
│   ├── transitions_small.py        # PERMISSIVE next (no ordering gate)
│   └── tests/test_version_sync.py  # CI guard: plugin.json.version == cli/__init__.py:__version__
├── _vendored/eigen_core/           # vendored copy of eigen-core (atomic I/O + base models)
└── README.md
```

Manifest auto-discovers `commands/*.md` (no explicit registration). Install via the same bash-wrapper pattern as lite/squared (`~/.local/bin/eigen-small` → `python3 -m cli`). Register in `tetration/.claude-plugin/marketplace.json` only when ready to ship. CI guard: `plugin.json.version == cli/__init__.py:__version__`.

---

## 12. Honest caveats (carried from the proven Wave-A run)

- **Worktree isolation is not free.** `isolation:"worktree"` did **not** isolate parallel background agents — they shared the main checkout and raced on branch checkouts; the run survived only because each agent committed strictly its own files. `small_build` MUST use explicit `git worktree add` dirs for parallel waves (or serialize). Sequential waves (B/C) are unaffected.
- **A goal is only as strong as its corpus.** The real boundary stops faking, but coverage (did the corpus include the surrogate edge?) is an authoring decision — hence independent goal-authoring + the Blackbox coverage ACs. Review the goal's *coverage*, not just its green status.
- **Integration risk concentrates in the orchestration wave.** Cross-seam invariants (e.g. "the object read must not hold a Bedrock slot under real concurrency") are first exercised only when the wiring epic runs. Treat that wave's goal as the highest-risk and add a concurrency review.
- **Lightweight review surfaces fewer findings** than an 8-agent swarm review. Accept it deliberately; the goal gates + the phase-gate epic are the backstop. Don't let `rigor=low` silently skip validation on a risky-but-small job — that's what the rigor dial is for.

---

## 13. Out of scope for v1 (deliberate)

- **Autonomous watchdog / `CLAUDE_TASKS_API` scheduling.** v1 is manual / in-session driver. (Add later if wanted.)
- **Multi-phase orchestration (a built-in phase splitter / N-phase sequencing + phase gates).** That's Shape `defer_to_squared`. **Exception (Level 0):** a 2-phase product (MVP → extensions) is supported as **two single-phase runs** — run again with `init --phase 2`, which slots artifacts into `phases/phase_2/` and reuses phase 1's frozen contracts/hooks. The router does **not** auto-plan the two phases; you sequence them (the boundary is trivial for 2). ≥3 phases → defer to eigen-squared.
- **Convergence loops** (main↔deepen, multi-iteration review). The goal gate replaces them.
- **Reusing squared's swarm workers** for execution. The goal-gate direct build is the divergence.
- **Squared's 22-verb CLI + nested phase/epic state + strict ordering gate.** eigen-small has a *thin* CLI (~6–7 permissive verbs, §4) over flat state — not the absence of a CLI, and not squared's surface.

---

## 14. Open decisions to settle before building

1. ~~**State plumbing:** router-managed JSON vs. a thin CLI?~~ **RESOLVED → thin CLI** (~6–7 permissive verbs over eigen-core atomic I/O; see §4). Atomic writes from a markdown command require a Python entry point, so a CLI is required, not optional.
2. ~~**Goal-author model policy.**~~ **RESOLVED → always independent + always a strong model + adversarial mandate**, regardless of the rigor dial. The rigor dial tunes corpus breadth/review depth only (§6.2, §8.2, §9).
3. ~~**Cross-plugin reuse.**~~ **RESOLVED → reuse `Skill("eigen-squared:language-profiles")`**; declare `dependencies:["eigen-squared"]` in the manifest (§3, §11).
4. ~~**`small_route` ↔ `small_build` handoff.**~~ **RESOLVED → stop after planning by default** (human checkpoint); `--auto` flag proceeds in-session (§6.4).
5. ~~**First build increment.**~~ **RESOLVED → scaffold (manifest + vendored eigen-core + thin CLI + state) + `small_route` first**, then `small_plan`, then `small_build` — each increment independently testable.
