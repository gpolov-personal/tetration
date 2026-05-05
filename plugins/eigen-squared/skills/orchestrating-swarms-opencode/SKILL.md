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
| `Agent({..., isolation: "worktree"})` | `team_spawn({..., worktree: false})` **for eigen-squared swarms** (see note below) | Ensemble's default is `worktree: true`, but eigen-squared's `orchestrate_swarm` and related commands deliberately **avoid git worktrees** — see the "Worktree policy" section. Only pass `worktree: true` if a command explicitly requests git-isolated parallel edits. |
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

## `Skill(...)` invocations in eigen-squared commands

Eigen-squared's `orchestrate_swarm` delegates the two TDD steps to worker skills using Claude Code's `Skill(...)` tool:

```
Skill("eigen-squared:design_validation_tests_swarm", args: "<task.id>")
Skill("eigen-squared:code_from_validation_tests_swarm", args: "<task.id>")
```

Two translation rules for OpenCode:

1. **Drop the `eigen-squared:` namespace prefix.** OpenCode's `skill` tool takes a plain `name`. Call `skill({name: "design_validation_tests_swarm"})`, not `skill({name: "eigen-squared:design_validation_tests_swarm"})`.

2. **OpenCode's `skill` tool has no `args` parameter.** If the original call passes `args: "<value>"`, state the value explicitly in your turn **before** invoking the skill, so it is available in the context the skill will read. Example: say "I am invoking the design-validation skill for task `task_abc123`." then call `skill({name: "design_validation_tests_swarm"})`. The skill's bridge instructions tell the invoked agent to extract the task ID from the immediate context and use it wherever the target command expects `$ARGUMENTS`.

The bridge skills (`design_validation_tests_swarm` and `code_from_validation_tests_swarm`) redirect to the corresponding command file under `.opencode/commands/`. You will typically need to `read` the command file yourself after the `skill` call, because the bridge content only points to the command.

---

## Slash-command vs Read distinction

If the daemon-injected prompt instructs the **lead** session to read a command file (e.g. "Read `.opencode/commands/orchestrate_swarm.md` and execute it"), that is a bug in the prompt-composition layer, not a workflow you should follow. The daemon is supposed to invoke commands via `opencode run --command <name>`, which lets OpenCode handle frontmatter, hooks, and `$ARGUMENTS` substitution natively. Inlining the command body via `Read` produces neither.

When you see this on the lead, do **not** silently work around it by reading the file. Fail loudly with a single tool call (e.g. a `Bash` echoing the diagnosis) so the operator notices the daemon-side regression and re-runs `eigen-squared sync-opencode` / upgrades claude-tasks.

**Note**: this rule is for the **lead** session under `opencode run --command …`. Teammates spawned via the bridge skills (`design_validation_tests_swarm`, `code_from_validation_tests_swarm`) intentionally `read` the target command file inline because they cannot invoke `opencode run` from inside their own session — that path is documented in the "Skill(...) invocations" section above.

---

## Model selection rule for team_spawn

Eigen-squared command prose often instructs the lead to spawn a teammate "using model **X**". On Claude Code that maps to `Agent({ model: X })` and inheritance from the lead is also possible. **On OpenCode + ensemble there is no inheritance from the lead.** `team_spawn` resolves the worker model via:

```
explicit `model` arg
  → ensemble.json `modelsByAgent[<agent>]`
  → ensemble.json `modelAssignment` pool (rotate / random)
  → ensemble.json `defaultModel`
  → undefined (hard fail at spawn time)
```

The lead's own model is never consulted. Two rules to translate the prose correctly:

1. **Literal model names** (e.g. "using model `opus`", `sonnet`, `haiku`, `gpt-5`): **omit** the `model` param in `team_spawn`. The eigen-squared sync (`sync-opencode`) writes `.opencode/ensemble.json` with `defaultModel = <profile-model>` matching whatever runner the daemon chose. Inheritance happens through `defaultModel`, not through the lead. Per-agent overrides go in `runners.yaml.models_by_agent` → `ensemble.json.modelsByAgent`, not in the spawn call.

2. **Variable model names** (e.g. `<worker_model>`, `${WORKER_MODEL}`, anything wrapped in `<…>` or `${…}`): **respect** the variable as an explicit selection and pass it through: `team_spawn({ …, model: "<worker_model_value>" })`. The variable was filled in by the daemon at spawn time precisely because that decision is intentional, not boilerplate.

If a `team_spawn` fails with `spawn:model:invalid`, the most common cause is `defaultModel` lacking a `provider/` prefix in `ensemble.json` — see Troubleshooting.

---

## Agent ID resolution

On Claude Code, agent definitions live under `<plugin>/agents/<id>.md` and are resolved via the plugin loader. On OpenCode, `team_spawn({ agent: "<id>" })` requires the definition to be visible at one of:

- `.opencode/agent/<id>.md`
- `.opencode/agents/<id>.md`

Both paths are first-class — the OpenCode loader globs `{agent,agents}/**/*.md`. The eigen-squared sync writes the **plural** form (`.opencode/agents/`) for consistency with `commands/` and `skills/`.

If a `team_spawn` fails with `agent not found`, the cause is almost always a missing or stale sync. Escalate via `team_message({ to: "lead", text: "FAIL: agent <id> not found — run \`eigen-squared sync-opencode\` from the project root" })` rather than substituting a different agent.

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

2. **Worktree isolation is default-on in ensemble, but eigen-squared swarms disable it**: ensemble's default is `worktree: true` (each teammate in `~/.local/share/opencode/worktree/<project-id>/ensemble-<team>-<member>/`). **For eigen-squared swarm commands (`orchestrate_swarm`, `code_from_validation_tests_swarm`, etc.), always pass `worktree: false`** when translating an `Agent(...)` call into `team_spawn(...)`. Eigen-squared coordinates concurrent edits through **declared file ownership** (`files_owned` / `test_files_owned` in the swarm manifest) rather than through git-level isolation. All teammates share the lead's working directory and integrate continuously, so worktrees would break the design. See the dedicated section below.

3. **State layout is SQLite, global**: teams, members, tasks, and messages live in `~/.config/opencode/ensemble.db`. Not filesystem-per-team like Claude Code. `team_id` is generated internally; you work with the `name` you passed to `team_create`.

4. **Messaging is async, best-effort**: `team_message` writes to the DB and fires `promptAsync` at the recipient session. If the recipient is idle, the idle-wake hook delivers on next turn. If the plugin crashes mid-delivery, messages older than 5s are retried on restart. Do not assume immediate synchronous delivery — after sending, do a short wait or check `team_status` / `team_results` before blocking on a response.

5. **Message size cap**: 10 KB per message (`team_message`, `team_broadcast`). Batch larger payloads by writing to a file in the shared worktree and messaging the path.

6. **Ergonomic helpers not in Claude Code**: `team_status`, `team_view`, `team_merge`, `team_results` have no direct CC equivalents. Use them; they simplify lead-side orchestration.

7. **`team_results` is authoritative for full message text**: messages delivered to the lead via the system-prompt injection are truncated. When a teammate reports a long result, the lead should call `team_results({from: <name>})` to retrieve the full body.

8. **No auto-restart after crash**: if OpenCode restarts mid-swarm, stale busy members are marked as errored, orphaned sessions aborted, undelivered messages re-delivered. Teammates themselves do **not** auto-restart. The lead must re-spawn them if the swarm should continue.

9. **Shell env vars injected into teammates**: each teammate's shell gets `ENSEMBLE_TEAM`, `ENSEMBLE_MEMBER`, `ENSEMBLE_ROLE`, `ENSEMBLE_BRANCH`. Useful for identifying self in bash commands.

---

## Single-turn polling pattern (critical on `opencode run`)

`opencode run` is a **single-turn** invocation: the lead session terminates the instant its turn ends with prose. When the lead terminates, **all teammates spawned during that turn are killed mid-work** — their processes die, their `busy` status goes stale in the DB, and pending file writes are lost.

This constraint does not exist in Claude Code (where the TUI keeps the session alive across turns). On OpenCode, it forces a specific orchestration shape: **from the first `team_spawn` until `team_cleanup`, the lead must not emit prose.** Every turn between those two points must end with a tool call that schedules the next turn.

### The monolithic polling loop

Use this structure in any orchestrator command (equivalent of `orchestrate_swarm`, `plan_epic_converge`, `create_issues_from_plan_swarm`, etc.) that spawns teammates on OpenCode:

```
1. setup (team_create, team_tasks_add, etc.)   ← prose OK here
2. spawn first wave  (team_spawn x N in a single response)
3. loop (tool calls ONLY, no prose between iterations):
   a. Bash({command: "sleep 15"})              ← keeps runtime alive ~15s
   b. team_tasks_list
   c. DECIDE (no prose; your next tool call is exactly one of):
      - if any task just transitioned blocked→pending and has no
        assignee yet  →  team_spawn that task's worker (joins the swarm)
      - else if every task is status=completed  →  exit loop
      - else  →  go back to (a), another sleep
4. team_cleanup
5. final prose summary                         ← prose allowed again here
```

One loop, one exit condition ("all tasks completed"). Dependency gating is automatic: downstream waves stay `blocked` in the DB until prereqs complete, and the loop spawns them on the iteration they unblock. No wave-boundary prose, no "Wave N complete — moving on" acknowledgments.

### What breaks the lead's survival

- **Prose acknowledgements between waves** (e.g. "Wave 1 complete — proceeding to Wave 2."). Don't emit them even if the command template suggests structured per-wave reporting. All acknowledgement happens AFTER `team_cleanup`.
- **Progress narratives** ("I'll now wait for teammates", "teammates are running", "all 3 are busy"). Same failure mode — any narrative ends the turn.
- **`team_message` to the user mid-loop**. Reserve user-facing messages for the final summary.
- **Conditional branches expressed as prose** ("If not all completed, I'll sleep again"). Express them as the decision in step 3c via the choice of next tool call, not as narrated intent.

### What is safe inside the loop

- `Bash` (including `sleep`, `python`, `git`, filesystem inspection).
- Any `team_*` tool (`team_status`, `team_view`, `team_results`, `team_spawn`, `team_message` between teammates).
- `read`, `write`, `edit`, `grep`, `glob` if the lead needs to consult a file mid-orchestration.
- A single final prose summary AFTER `team_cleanup`, consolidating per-task outcomes.

### Timeout and partial-failure handling

Cap the loop at ~80 iterations (~20 minutes). If the cap is hit, the correct final sequence is still pure tool calls: `team_status` → `team_cleanup` → one prose summary with partial results. Do NOT narrate the timeout mid-loop.

---

## Worktree policy for eigen-squared swarms

Eigen-squared's orchestration model (`orchestrate_swarm` and the `*_swarm` family) predates ensemble's worktree feature and was designed for a single shared filesystem. Its coordination primitive is **file ownership**: each task in the swarm manifest declares `files_owned: [...]` and `test_files_owned: [...]`, and teammates are disciplined to only edit files in their declared ownership set. This lets multiple teammates work in parallel in the same branch without conflicts.

If you enable ensemble worktrees (`worktree: true`) when translating an eigen-squared `Agent(...)` call, you break several assumptions:

- Teammates won't see each other's writes in real time.
- The integration step (which expects all ownership sets to coexist on one branch) breaks, because each teammate's edits live in a separate branch.
- File-ownership conflicts — which the manifest prevents by construction — become invisible to the ownership guardrails.
- Crash recovery in eigen-squared uses branch state as the source of truth and assumes a single branch per phase/epic; parallel branches would confuse it.

**Rule**: when the command you are executing was written for eigen-squared (identifiable by `[WAVE-STATUS]`/`[INTEGRATION-REQUEST]` task prefixes, `swarm-manifest.json`, or explicit mention of file ownership), **always translate `Agent(...)` to `team_spawn({..., worktree: false, ...})`**, regardless of what the Agent call looks like in the command prose.

If a non-eigen-squared command (e.g. a personal experiment or a review flow where agents should not see each other's edits) wants isolation, pass `worktree: true` explicitly. Default when unsure: `worktree: false`.

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

If you are on OpenCode with a non-Anthropic model, **every tool call that mentions `Task`, `Agent`, `SendMessage`, `TaskCreate`, `TaskList`, `TaskUpdate`, `TeamCreate`, or `TeamDelete` is a bug**. Translate it before emitting the call. And from the first `team_spawn` until `team_cleanup`, **no prose** — only tool calls, or the swarm dies.
