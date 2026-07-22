<div align="center">

# ⚡ tetration

### Automation that compounds on itself.

**A [Claude Code](https://claude.com/claude-code) plugin marketplace for autonomous, convergence-driven software delivery.**

Hand it a spec. Walk away. Come back to reviewed, tested, merged code.

![Claude Code](https://img.shields.io/badge/Claude_Code-plugin_marketplace-6E56CF)
![Plugins](https://img.shields.io/badge/plugins-2-blue)
![eigen--squared](https://img.shields.io/badge/eigen--squared-v3.9.0-brightgreen)
![CLI tests](https://img.shields.io/badge/CLI_tests-153_passing-success)
![Language agnostic](https://img.shields.io/badge/languages-Python_·_TS_·_Go_·_Rust_·_C%23_·_Kotlin_·_Swift-orange)

</div>

---

> The agentic wave gave everyone an agent that can write a function.
> **tetration gives that agent a pipeline** — one that decomposes a 150-feature initiative into shippable code, runs a *swarm* of specialists to build it, reviews its own work until the findings hit zero, and hardens its own prompts from what it learned.

*Tetration* is the mathematical operation one level above exponentiation — repeated exponentiation. That's the whole idea: automation that doesn't just repeat, it **compounds recursively on itself**. Each stage feeds the next, each review tightens the last, and the system edits its own instructions from production defects. This repo is the marketplace that ships it.

---

## 📦 What's inside

| Plugin | Version | For | In one line |
|--------|---------|-----|-------------|
| **[`eigen-squared`](plugins/eigen-squared/)** | `3.9.0` | Large, greenfield or multi-phase initiatives (10–150+ features) | The full autonomous pipeline: initiative → phases → epics → plans → tasks → parallel swarms → review → merge, self-scheduling across phases and stopping only for a human checkpoint. |
| **[`eigen-lite`](plugins/eigen-lite/)** | `0.9.0` · beta | Small deltas on an existing repo (2–5 features) | A distilled, single-phase variant. Four commands (`lite_start`, `lite_plan`, `lite_swarm`, `lite_review`) collapse squared's seven-stage planner into a single-pass plan with parallel analyst subagents — then reuses `eigen-squared`'s workers via cross-plugin skill referencing. |

**Rule of thumb:** ≥6 features / greenfield / needs phase-splitting → **eigen-squared**. A handful of endpoints on a repo you already have → **eigen-lite**.

---

## 🧠 The idea in five moves

tetration isn't "an agent that codes." It's an **engineering process**, encoded so agents can execute it deterministically.

### 1. Spec-driven, not vibe-driven
You don't prompt it feature-by-feature. You give it **documents**:

- **Initiative** — a Feature Summary Table: IDs, dependencies, priorities, domains.
- **Blackbox Requirements** — per-feature specs: inputs, outputs, behavior, acceptance criteria.
- **Whitebox Reference** *(optional)* — implementation patterns from a system you trust.

The pipeline treats these as the contract. Ambiguity is surfaced and escalated, not guessed.

### 2. Decomposition along two axes
Big things become small things until a swarm can grab each piece:

```
Initiative  ──time_split──▶  Phases  ──space_split_converge──▶  Epics  ──plan_epic_converge──▶  Tasks
   (150 features)          (shippable,           (sequential units      (file-scoped work
                            E2E-testable)         of work)               for parallel workers)
```

`time_split` slices **across time** (sequential, independently shippable phases). `space_split_converge` slices **within a phase** (ordered epics — the last is always the E2E Testing epic).

### 3. Swarms build it — in parallel, with TDD, on real dependencies
Each epic is handed to `orchestrate_swarm`, a **swarm leader** that spawns worker teammates. Every worker follows strict **test-driven development**:

> **design validation tests → write code → verify green.**

Tests run against **real dependencies** — a real database, a real message bus, real infrastructure — *not* mocks. Mocks hide the exact class of defect (wrong API identifiers, wrong method names, wrong model IDs) that specs get wrong. Workers own disjoint file sets, so they never collide; they coordinate through messages, not merge conflicts.

### 4. Convergence — it reviews itself until findings hit zero
This is the "eigen" in **eigen-squared**. An *eigenvector* is a vector that maps back onto itself under a transformation; apply the transform enough times and it **converges** to a stable point. Every stage here works the same way:

- **Planning stages** (`time_split`, `bootstrap_converge`, `space_split_converge`, `plan_epic_converge`) are **self-converging single sessions** — they draft, run an *executed* verification gate (real builds, real consistency checks), critique against fixed checklists, and revise.
- **Implementation** runs the one cross-command loop, `orchestrate_swarm ↔ review_swarm_pr`: a review swarm of specialists finds issues, workers fix them, bounded to ≤3 rounds, then merges with any residuals openly disclosed at the human checkpoint.

Findings are triaged P1/P2/P3. Nothing merges dirty and silent.

### 5. It improves *its own source*
Reviewer agents log real production defects as structured `lessons/` (root cause + the exact prompt section to fix). `compound_improve` reads them and **rewrites the plugin's own command prompts** to bake the fix in permanently. The pipeline gets better at its job every time it runs. *That's the compounding.*

---

## 🖥️ Watch the swarm work — live

Because tetration runs on Claude Code **agent teams** with `teammateMode: tmux`, the swarm isn't a black box. Each teammate gets its own **visible pane**. You literally watch the leader dispatch waves and the workers build in parallel, side by side:

```
┌──────────────────────────────┬──────────────────────────────┐
│  🧭 orchestrate_swarm (lead)  │  👷 worker · P1.E2.T1         │
│  wave 2/3 · 4 workers live    │  design tests → code → ✅ green│
│  coordinating shared files…   │  auth service                 │
├──────────────────────────────┼──────────────────────────────┤
│  👷 worker · P1.E2.T2         │  🔍 review_swarm_pr           │
│  writing migration tests…     │  security · arch · perf ·     │
│  green: 6/9                   │  simplicity · testing → P2×1  │
└──────────────────────────────┴──────────────────────────────┘
```

No dashboard to build, no logs to tail — the terminal *is* the observability layer.

---

## 🤖 The cast: specialist agents + a skills library

**Reviewer & researcher subagents** (`agents/`) — each a focused persona the swarm spawns for scope-aware review:

`security-sentinel` · `architecture-strategist` · `performance-oracle` · `code-simplicity-reviewer` · `data-integrity-guardian` · `pattern-recognition-specialist` · `best-practices-researcher` · `framework-docs-researcher` · `repo-research-analyst` · `git-history-analyzer` · `test-practices-researcher` · `vs-python-reviewer`

**A 30+ skill library** (`skills/`) the agents draw on, spanning:

- **eigen-native plumbing** — `pipeline-state-schema`, `language-profiles`, `orchestrating-swarms`, `compound-docs`, `codegraph`.
- **the agent-native philosophy** — `agent-native-architecture` (a full essay-length skill with 14 reference docs on building software where agents are first-class citizens with UI parity, atomic tools, and emergent capability).
- **curated best-practice packs** — React/Next & React Native (Vercel), security (per-framework), Rust, Go, Java, Kotlin, Node, Python, C#, senior-architect, web-design-guidelines, and more.

---

## ⚙️ Deterministic where it counts

LLMs are creative; state machines shouldn't be. tetration draws a hard line between them.

All pipeline state lives in one JSON document managed **exclusively** by a Python CLI (`eigen-squared`). Command prompts *never* touch `pipeline_state.json` directly — they call the CLI on entry (`get-context`) and exit (`complete`). Every transition, convergence decision, retry, and branch resolution is typed, pure, side-effect-free Python — backed by **153 passing tests**. This eliminated what was documented as the *#1 source of bugs*: an LLM misreading JSON schema or forgetting to flip a cross-flag.

```bash
eigen-squared next --json          # what should run next?
eigen-squared get-context <cmd>    # sync git, auto-detect phase/epic, run guards
eigen-squared complete <cmd> ...   # record completion atomically
eigen-squared status               # human-readable pipeline overview
```

### Autonomy via claude-tasks
In autonomous mode, a cron **watchdog** (`eigen-watchdog`) polls every N minutes, asks the CLI what's next, and schedules it through [**claude-tasks**](https://github.com/kylemclaren/claude-tasks) — an external server that runs Claude Code sessions on a schedule or in response to events. Commands *never* schedule their own successors; the watchdog owns all scheduling, so there's no "forgot to schedule / scheduled twice" failure mode. The pipeline drives itself phase after phase, pausing only at the human checkpoint (`eigen_continue`). In **manual mode**, drop claude-tasks entirely and run each stage yourself.

---

## 🚀 Quick start

```bash
# In any Claude Code session:
/plugin marketplace add ggpolovera/tetration
/plugin install eigen-squared@tetration      # or: eigen-lite@tetration

# Then, in your project:
cd /path/to/your/project
claude
/eigen_start        # interactive setup: env, mode, CLI install, pipeline init
```

`eigen_start` runs in two passes (with a Claude Code restart between them) to configure `.claude/settings.json`, install the CLI globally, and — in autonomous mode — set up the watchdog cron. Drop your initiative documents in `eigen_initiative/`, and you're off.

> Full setup, pipeline stages, CLI reference, and file layout live in the plugin's own guide:
> **📖 [`plugins/eigen-squared/README.md`](plugins/eigen-squared/README.md)** · lite: **[`plugins/eigen-lite/README.md`](plugins/eigen-lite/README.md)**

### Requirements
- **Claude Code** with agent teams enabled (`CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1`, `teammateMode=tmux`) — `eigen_start` writes these for you.
- **Python 3.10+** for the CLI.
- **tmux** for the live swarm panes.
- *(autonomous only)* **[claude-tasks](https://github.com/kylemclaren/claude-tasks)** running locally.
- *(optional)* **[CodeGraph](https://github.com/colbymchenry/codegraph)** — a local code-intelligence graph agents query instead of grep when a project is indexed. Never required; degrades silently to grep/Read.

---

## 🗺️ Repo layout

```
tetration/
├── .claude-plugin/
│   └── marketplace.json          # the marketplace manifest (lists both plugins)
├── plugins/
│   ├── eigen-squared/            # the flagship pipeline
│   │   ├── cli/                  # the deterministic "brain" — 153 tests
│   │   ├── commands/             # 14 pipeline stage prompts
│   │   ├── agents/               # 12 specialist reviewer/researcher subagents
│   │   ├── skills/               # 30+ skills (eigen-native + curated packs)
│   │   └── lessons/              # self-improvement corpus for compound_improve
│   └── eigen-lite/               # the distilled variant for small initiatives
└── docs/                         # design notes & explorations
```

---

## ✨ Why it's different

- **Spec → shipped, not prompt → snippet.** It executes an engineering *process*, end to end.
- **Real-dependency TDD.** Tests hit real infra, so specs that lie about external APIs get caught — not papered over by mocks.
- **Convergence, not one-shot.** Every stage reviews itself to a fixed point before advancing.
- **Deterministic spine.** A 153-test Python state machine owns all state; the LLM never bookkeeps.
- **Observable by construction.** The swarm works in visible tmux panes.
- **Self-improving.** It rewrites its own prompts from what breaks in production.
- **Language- & project-agnostic.** Web APIs, mobile apps, CLIs, libraries, ML pipelines — Python, TypeScript, Go, Rust, C#/.NET, Kotlin, Swift, Flutter, React Native, and more.

---

## 📛 The names

- **tetration** — repeated exponentiation; the marketplace's promise of automation that *compounds* rather than merely repeats.
- **eigen-squared** — *eigen* (self / fixed-point, as in eigenvector) *squared* (self-applied, nested): a system that repeatedly applies processes to their own output until they **converge**.
- **eigen-lite** — the same self-referential machine, distilled to its smallest useful form.

---

<div align="center">

**Built by [G.Polo.V](https://github.com/ggpolovera)** · eigen-lite by Diego San Cristobal
Requires [Claude Code](https://claude.com/claude-code) · Made for the agentic era.

</div>
