---
name: codegraph
description: "Optional, external code-intelligence reference for eigen-squared. Load when a command's agent needs to explore existing code structure, trace call flows, or compute change impact (callers/callees/blast radius) more cheaply than grep/Read. CodeGraph is a local tree-sitter knowledge graph exposed over MCP + CLI; it is NEVER required — commands must degrade silently to grep/Glob/Read when it is absent."
---

# CodeGraph — Optional Code-Intelligence Reference

Single source of truth for how eigen-squared commands use **CodeGraph** (https://github.com/colbymchenry/codegraph): a local, language-agnostic knowledge graph (tree-sitter → SQLite) of every symbol, edge, and file. Structural reads are sub-millisecond and return what grep cannot (callers, callees, blast radius, cross-file/cross-language call paths).

**CodeGraph is OPTIONAL and EXTERNAL.** It is not bundled with this plugin and may not be installed. Every command that uses it MUST existence-check first and **fall back to grep/Glob/Read when it is absent — never STOP, never block, never ask the user to install it mid-run.** Recommending installation belongs only in `eigen_start`.

> Name collision: an unrelated MCP server `code-review-graph` (tools `get_*_tool`) exists in some environments. Target CodeGraph specifically — the `codegraph` CLI, the `.codegraph/` index dir, and `codegraph_*` base tool names.

---

## Existence gate (run once per command, in Stage 0)

```
Set <codegraph_available> and <codegraph_root> — best-effort probe.
1. <codegraph_root> = `git rev-parse --show-toplevel` (else $EIGEN_ROOT / cwd).
2. Available iff ALL hold:
   - `command -v codegraph` succeeds (CLI on PATH), AND
   - `<codegraph_root>/.codegraph/` exists AT that working-tree root (test the dir directly —
     do NOT accept a parent tree's index), AND
   - `codegraph status -j <codegraph_root>` reports `"initialized": true`.
   If any check fails → <codegraph_available> = false, continue with grep/Read.
```

`codegraph status` exits 0 even when uninitialized, so gate on the `.codegraph/` dir + the `initialized` field, NOT on exit code. Testing the dir *at the working-tree root* also guards against a git worktree silently borrowing another branch's index (fails closed → grep/Read).

## Tool-by-intent (when `<codegraph_available>`)

Prefer these over grep/Read for **structural** questions; use native grep/Read only for literal text (string/comment/log contents) or a file you already have open. Tools are exposed under this runtime's MCP prefix (`mcp__codegraph__codegraph_*` on Claude Code; the runtime's own convention elsewhere) — gate on the CLI/`.codegraph` probe, never on a hardcoded prefix string.

| Question | Tool |
|---|---|
| "Where is X defined?" / "Find symbol X" | `codegraph_search` |
| "What calls Y?" | `codegraph_callers` |
| "What does Y call?" | `codegraph_callees` |
| "How does X reach Y? / trace the flow" | `codegraph_trace` (one call = whole path, incl. dynamic/callback/JSX hops) |
| "What breaks if I change Z?" (blast radius) | `codegraph_impact` |
| "Show Y's signature / source / docstring" | `codegraph_node` |
| "Focused context for an area/task" | `codegraph_context` |
| "Several related symbols' source at once" | `codegraph_explore` |
| "What files exist under path/" | `codegraph_files` |
| "Which test files does this change affect" | CLI `codegraph affected <files…> --stdin` |
| "Is the index healthy / what's pending?" | `codegraph_status` |

Rules of thumb: **trust results** (full AST parse — don't re-verify with grep); answer architecture questions in 2-3 calls (`codegraph_context`, then ONE `codegraph_explore`) instead of spawning a file-reading sub-agent or a grep+read loop; don't chain `search`+`node` when `context` is one call; treat returned source as already read.

## What CodeGraph does NOT cover (keep on grep/Read)

- **Third-party deps** (`node_modules`, `.venv`, `vendor`) are excluded — installed-SDK-source lookups must stay on Read.
- **Non-code artifacts** (YAML/compose, JSON config, Dockerfiles, markdown, live processes) are not indexed.
- **Code that does not exist yet** — greenfield files a plan describes but no one has written. CodeGraph only graphs what is on disk.

---

## Sync / freshness protocol

**Default: RELY ON auto-sync. Do NOT run `codegraph sync`.** When the MCP server runs, three layers keep the index fresh: a debounced OS file-watcher; a per-file `⚠️` staleness banner during the debounce window (Read those specific files directly — they are pending; files not in the banner are authoritative); and connect-time `(size,mtime)+hash` catch-up before the first query of every new session. Over-syncing (after each edit, before each query, inside a worker loop) is a latency anti-pattern for zero correctness gain.

Run `codegraph sync <codegraph_root>` (optionally first `codegraph status <codegraph_root>` to confirm a `Pending sync` section) **only** when one of:

- **(a) Watcher is off** — sandboxed env, `CODEGRAPH_NO_DAEMON=1`, `serve --mcp --no-watch`, or an index/worktree on WSL2 `/mnt` or a network share (WAL + watcher degrade there).
- **(b) Same-session write-then-query** — a single command/session that writes files and then queries the index *in the same run* before any new MCP connect (connect-time catch-up has not fired yet).

Calibration for eigen-squared's execution model (cron **watchdog** → short headless `claude -p` sessions; swarm workers share **one** working tree on the integration branch via file-ownership, **no worktrees**):

| Scenario | Action |
|---|---|
| Headless watchdog → new `claude -p` session | **No sync** — connect-time catch-up reconciles before the first query. |
| Swarm TDD workers (shared tree, parallel writers) | **No sync** — one running watcher debounces all workers' edits; the `⚠️` banner covers the debounce window. Per-edit/per-query sync is the anti-pattern. |
| Post-bootstrap / post-wave, querying in the SAME session as the writes | One `codegraph sync <root>` (case b). If the next consumer is a NEW session → no sync. |
| Pre-review on the integration branch (review_swarm_pr) | `codegraph status`; `sync` only if it reports pending. With the watcher off (headless), sync once so impact/caller queries reflect the merged code. |
| Watcher off (case a) at a wave / integration boundary | Leader runs `codegraph sync <root>` once at the boundary — never inside the per-worker loop. |

## Initialization (producer)

The index must exist before any consumer can query it. `codegraph init -i` initializes **and** runs a full index (`-i` = `--index`, not interactive). This belongs at boundaries that create code:

- **`eigen_start`** offers it once for the project (and recommends installing the CLI).
- **`bootstrap_converge`** ensures it after the foundation is created (init if `.codegraph/` is absent; otherwise rely on auto-sync, or `sync` only when the watcher is off).

Execution/review commands must **never** `init` — they only existence-check and consume.
