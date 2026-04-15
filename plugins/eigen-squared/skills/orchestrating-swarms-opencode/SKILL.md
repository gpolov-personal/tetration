---
name: orchestrating-swarms-opencode
description: This skill should be used when orchestrating multi-agent swarms on OpenCode with non-Anthropic models (GPT, Codex, MiniMax, Qwen, DeepSeek, Gemini, Nemotron, etc.). It replaces the `orchestrating-swarms` skill when Claude Code's native agent-team tools (`Agent`, `SendMessage`, `TaskCreate`, `TeamCreate`) are NOT available and the runtime exposes the `team_*` tools from the `@hueyexe/opencode-ensemble` plugin instead. Provides the Claude-Code → OpenCode tool-name translation layer, argument mappings, semantic deviations, and swarm orchestration patterns re-expressed with ensemble's primitives.
---

# OpenCode Swarm Orchestration

This skill is the **OpenCode-native sibling** of `orchestrating-swarms`. When you are running on OpenCode with a non-Anthropic model, Claude Code's agent-team tools (`Task`, `Agent`, `SendMessage`, `TaskCreate`, `TaskList`, `TaskUpdate`, `TeamCreate`, etc.) **do not exist in your tool list**. Calling them will fail. Use the `team_*` tools from the `@hueyexe/opencode-ensemble` plugin instead, following the translation layer below.

---

## When to use this skill

Use this skill (and NOT `orchestrating-swarms`) when **all** of the following are true:

1. You are running on **OpenCode** (binary `opencode`, not Claude Code).
2. The active model is **not** an Anthropic Claude model (i.e., you are on GPT-5, Codex, MiniMax, Qwen, DeepSeek, Gemini, Nemotron, or similar).
3. Your tool list contains tools starting with `team_` (e.g., `team_create`, `team_spawn`, `team_message`). If it does **not**, the ensemble plugin is not installed — stop and report this.

If the tool list contains `Task`, `Agent`, `SendMessage`, `TaskCreate` (Claude Code native), use the `orchestrating-swarms` skill instead — **not this one**.

---

## Prerequisites

The host project must have `@hueyexe/opencode-ensemble` installed and enabled. Typically in `opencode.json`:

```json
{
  "plugin": ["@hueyexe/opencode-ensemble@0.12.1"],
  "permission": {
    "external_directory": {
      "~/.local/share/opencode/worktree/**": "allow"
    }
  }
}
```

Verify by checking that `team_create`, `team_spawn`, `team_message` appear in your available tools. If they don't, the commands invoking this skill **will fail** — surface the problem to the user immediately; do not attempt workarounds.

---

## The translation directive (read this before anything else)

**NEVER** call any of these Claude Code tools on OpenCode. They do not exist:

```
Task, Agent, SendMessage, TaskCreate, TaskList, TaskUpdate, TaskGet,
TaskComplete, TaskOutput, TaskStop, TeamCreate, TeamDelete,
EnterWorktree, ExitWorktree
```

Instead, call the corresponding `team_*` tool from the mapping table. If a command body references any of the forbidden names above, **translate at call time** — do not copy-paste the call.

---

## Tool name mapping (Claude Code → OpenCode)

| Claude Code tool | OpenCode tool | Notes |
|---|---|---|
| `Task({subagent_type, prompt})` — plain subagent, no team | OpenCode native `task({subagent_type, prompt, description})` | Blocking child session. Same semantics. Not a teammate. |
| `Agent({subagent_type, name, prompt, team_name})` — teammate spawn | `team_spawn({name, agent: subagent_type, prompt})` | Teammate in the active team. `team_name` is ignored; OpenCode has one active team per lead session. |
| `Agent({..., run_in_background: true})` | `team_spawn({...})` | `team_spawn` is fire-and-forget by default. |
| `Agent({..., isolation: "worktree"})` | `team_spawn({..., worktree: true})` | Default is `true`. Pass `worktree: false` for read-only agents that share the parent workspace. |
| `SendMessage({to, message})` | `team_message({to, text: message})` | `to` = teammate name. |
| `SendMessage({to, message: {plan_approved: true}})` | `team_message({to, approve: true, text})` | Structured plan-approval variant. |
| `SendMessage({to, message: {plan_rejected: reason}})` | `team_message({to, reject: reason})` | |
| `SendMessage({broadcast: true, message})` | `team_broadcast({text: message})` | Sends to all teammates. |
| `TeamCreate({team_name})` or `TeamCreate({name})` | `team_create({name})` | Caller becomes the lead. |
| `TeamDelete()` / cleanup | `team_cleanup({})` | Shuts down remaining teammates and removes team state. |
| `TaskCreate({title, description, dependencies, owner})` | `team_tasks_add({tasks: [{content: title, priority, depends_on}]})` | Arg is an **array** — `team_tasks_add` accepts batch. |
| `TaskList()` | `team_tasks_list({})` | Returns all tasks with status + assignee. |
| `TaskGet({id})` | `team_tasks_list({})` then filter | No single-task getter; list and filter. |
| `TaskUpdate({id, status: "completed"})` | `team_tasks_complete({task_id: id})` | |
| `TaskUpdate({id, owner: X})` — self-claim | `team_claim({task_id: id})` | Atomic claim; caller's teammate name is implicit. |
| `TaskOutput({id})` | `team_results({from?})` | Retrieves full message content including task results. Messages to lead are truncated on delivery; use `team_results` for full text. |
| `TaskStop({id})` | No direct equivalent | Manually `team_message` the owner to abandon, or use `team_shutdown` for the owner teammate. |
| Check team state | `team_status({})` | Snapshot: members, statuses, task counts. Not in Claude Code. |
| Switch view to a teammate's session | `team_view({member})` | TUI-only; useful when the lead wants the user to see a specific teammate's chat. |
| Shut down a single teammate | `team_shutdown({member, force?})` | Graceful by default; `force: true` aborts. |
| Merge a teammate's worktree branch | `team_merge({member})` | Squash-merges unstaged into lead's working directory. `team_cleanup` does this automatically for remaining branches. |

---

## Argument rename cheat sheet

When translating call sites, adjust arg names too:

| Claude Code arg | OpenCode arg |
|---|---|
| `message` | `text` (for `team_message`, `team_broadcast`) |
| `subagent_type` | `agent` (in `team_spawn`) |
| `title` | `content` (in `team_tasks_add`) |
| `id` (task) | `task_id` |
| `dependencies` | `depends_on` |
| `owner` (on TaskCreate) | Not set at creation; claim afterwards via `team_claim` |
| `team_name` | **drop** — not needed on OpenCode |
| `name` (teammate) | `name` (same; used as `to` in messaging and `member` in lifecycle ops) |

---

## Semantic deviations you must know

These are places where `team_*` tools behave differently from their Claude Code counterparts. Adjust orchestration accordingly.

1. **Teammates have a restricted toolset**: on spawn, teammates get `edit` (in their worktree), `bash`, and the 6 team communication tools (`team_message`, `team_broadcast`, `team_tasks_*`, `team_claim`). They **cannot** spawn further teammates (no nested teams). Sub-subagents via the OpenCode `task` tool are allowed.

2. **Worktree isolation is default-on**: every teammate runs in its own git worktree at `~/.local/share/opencode/worktree/<project-id>/ensemble-<team>-<member>/`. File edits stay isolated until merge. If two teammates must see each other's files live, pass `worktree: false` on spawn (and accept the risk of conflicting edits).

3. **State layout is SQLite, global**: teams, members, tasks, and messages live in `~/.config/opencode/ensemble.db`. Not filesystem-per-team like Claude Code. `team_id` is generated internally; you work with the `name` you passed to `team_create`.

4. **Messaging is async, best-effort**: `team_message` writes to the DB and fires `promptAsync` at the recipient session. If the recipient is idle, the idle-wake hook delivers on next turn. If the plugin crashes mid-delivery, messages older than 5s are retried on restart. Do not assume immediate synchronous delivery — after sending, do a short wait or check `team_status` / `team_results` before blocking on a response.

5. **Message size cap**: 10 KB per message (`team_message`, `team_broadcast`). Batch larger payloads by writing to a file in the shared worktree and messaging the path.

6. **Ergonomic helpers not in Claude Code**: `team_status`, `team_view`, `team_merge`, `team_results` have no direct CC equivalents. Use them; they simplify lead-side orchestration.

7. **`team_results` is authoritative for full message text**: messages delivered to the lead via the system-prompt injection are truncated. When a teammate reports a long result, the lead should call `team_results({from: <name>})` to retrieve the full body.

8. **No auto-restart after crash**: if OpenCode restarts mid-swarm, stale busy members are marked as errored, orphaned sessions aborted, undelivered messages re-delivered. Teammates themselves do **not** auto-restart. The lead must re-spawn them if the swarm should continue.

9. **Shell env vars injected into teammates**: each teammate's shell gets `ENSEMBLE_TEAM`, `ENSEMBLE_MEMBER`, `ENSEMBLE_ROLE`, `ENSEMBLE_BRANCH`. Useful for identifying self in bash commands.

---

## Core patterns (translated)

### Pattern 1 — Parallel specialists

Use when several independent, read-only analyses can run in parallel and you want to merge results.

```text
Step 1: team_create({ name: "review" })
Step 2: team_spawn({ name: "security",     agent: "security-sentinel",         prompt: "<role-specific brief>" })
        team_spawn({ name: "performance",  agent: "performance-oracle",        prompt: "<role-specific brief>" })
        team_spawn({ name: "patterns",     agent: "pattern-recognition-specialist", prompt: "<role-specific brief>" })
Step 3: Wait for teammate results to arrive via system-prompt injection.
        If a result is truncated, call team_results({ from: <name> }) for the full body.
Step 4: team_status({}) — confirm all three reached idle.
Step 5: Synthesize findings. Report to user.
Step 6: team_cleanup({})
```

### Pattern 2 — Pipeline with dependencies

Sequential stages where each step needs the previous one's output.

```text
Step 1: team_create({ name: "pipeline" })
Step 2: team_tasks_add({ tasks: [
          { content: "Research:  identify candidate libraries",       priority: "high" },
          { content: "Plan:      write integration design",           priority: "high", depends_on: ["<task-1-id>"] },
          { content: "Implement: apply the plan",                     priority: "medium", depends_on: ["<task-2-id>"] },
          { content: "Test:      add coverage for new code",          priority: "medium", depends_on: ["<task-3-id>"] },
        ]})
Step 3: Spawn specialists:
        team_spawn({ name: "researcher", agent: "repo-research-analyst", prompt: "Claim pending tasks via team_claim; work only on tasks whose dependencies are completed." })
        team_spawn({ name: "planner",    agent: "architecture-strategist", prompt: "..." })
        team_spawn({ name: "impl",       agent: "general",                prompt: "..." })
        team_spawn({ name: "qa",         agent: "test-practices-researcher-no-vs", prompt: "..." })
Step 4: Monitor via team_status + team_tasks_list. Intervene only if a teammate stalls.
Step 5: Final synthesis + team_cleanup.
```

Each teammate's prompt must include the claim-loop pattern:

```text
1. team_tasks_list({}) — find a pending task whose dependencies are all completed.
2. team_claim({ task_id }) — atomic claim. If it fails, another teammate got it; retry step 1.
3. Do the work. Edit files in YOUR worktree only.
4. team_message({ to: "lead", text: "<result summary>" }) — report results.
5. team_tasks_complete({ task_id }) — mark done; unblocks dependents.
6. Repeat from step 1. Stop when no claimable tasks remain.
```

### Pattern 3 — Self-organizing swarm (independent task pool)

Many independent tasks, N workers racing to claim them.

```text
Step 1: team_create({ name: "swarm" })
Step 2: team_tasks_add({ tasks: [<one task per file/module/check, no dependencies>] })
Step 3: team_spawn N workers with identical prompts ("claim and execute tasks from the board").
Step 4: Workers race through team_claim. One message to lead per completion.
Step 5: Lead monitors with team_status + team_tasks_list. All tasks complete → cleanup.
```

### Pattern 4 — Research → implement handoff

Research teammate completes first, then an implementer starts working from the research output.

```text
Step 1: team_create + team_tasks_add([
          { content: "Research how to integrate X", priority: "high" },
          { content: "Implement based on research", priority: "high", depends_on: ["<research-task-id>"] },
        ])
Step 2: team_spawn({ name: "researcher", agent: "framework-docs-researcher", prompt: "..." })
Step 3: Wait for researcher to complete task 1 (team_tasks_list shows status=completed).
Step 4: team_spawn({ name: "impl", agent: "general", prompt: "Read team_results from researcher; claim task 2; implement." })
Step 5: Wait, synthesize, cleanup.
```

---

## For patterns not covered here

The companion skill `orchestrating-swarms` documents additional patterns (plan-approval flows, coordinated refactoring, crash recovery variations). You **may** read it for the orchestration *logic*, **but you MUST substitute tool names per the mapping table above on every call site**. Never call the CC-native tools directly — only use `team_*` tools.

If in doubt about a tool call: look up the tool in the mapping table. If it is not there, it probably does not have a direct equivalent; improvise using `team_message` + `team_tasks_*` or ask the user.

---

## Troubleshooting

| Error or symptom | Cause | Fix |
|---|---|---|
| "Tool not found: SendMessage / Task / TaskCreate / Agent" | You called a Claude Code name. | Translate via mapping table. |
| `spawn:workspace:failed` in logs | Non-blocking ensemble warning about a deprecated workspace feature. | Ignore — teammate still spawns in worktree and runs. |
| `spawn:model:invalid` fallback | `defaultModel` in `.opencode/ensemble.json` missing `provider/` prefix. | Use `"defaultModel": "openai/gpt-5.4-mini-fast"` (with provider prefix). |
| Teammate spawn hangs | `permission.external_directory` for `~/.local/share/opencode/worktree/**` not set → opencode prompts on every file op. | Add the allow rule in `opencode.json`. |
| Lead never receives teammate's response | Teammate errored silently. Check `team_status` — if status shows `error`, that teammate needs re-spawn. | `team_shutdown({member, force: true})` then `team_spawn` fresh. |
| Message truncated in lead system prompt | Normal — lead sees summary only. | Call `team_results({from: <name>})` for full text. |
| Two teammates race-claim the same task | Normal if `team_claim` races; it is atomic but needs retry. | Teammate prompt must handle claim failure by listing again. |
| Plugin not loading / `team_*` tools absent | Plugin not in `opencode.json` or version cache stale. | `rm -rf ~/.cache/opencode/packages/@hueyexe` and restart opencode. |

---

## Quick cheat sheet

```text
# Team lifecycle
team_create({ name })
team_cleanup({})
team_status({})

# Spawn / shutdown
team_spawn({ name, agent, prompt })               # default: worktree=true
team_shutdown({ member, force? })
team_merge({ member })                             # unstage into lead workdir

# Messaging
team_message({ to, text })                         # peer or to lead
team_broadcast({ text })                           # everyone
team_results({ from? })                            # full content

# Tasks
team_tasks_add({ tasks: [{ content, priority, depends_on? }] })
team_tasks_list({})
team_claim({ task_id })
team_tasks_complete({ task_id })

# TUI
team_view({ member })                              # switch user's view
```

---

## One-line invariant

If you are on OpenCode with a non-Anthropic model, **every tool call that mentions `Task`, `Agent`, `SendMessage`, `TaskCreate`, `TaskList`, `TaskUpdate`, `TeamCreate`, or `TeamDelete` is a bug**. Translate it before emitting the call.
