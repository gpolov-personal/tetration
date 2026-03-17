# Understanding: Orchestrating Swarms Skill

## Purpose

This skill is a comprehensive reference guide for orchestrating **multi-agent swarms** using Claude Code's `TeammateTool` and `Task` system. It activates when coordinating multiple agents working in parallel, running simultaneous code reviews, building pipelines with dependencies, or any task that benefits from divide-and-conquer patterns.

---

## Core Concepts (Primitives)

The system is built on 7 key primitives:

| Primitive | Description |
|-----------|-------------|
| **Agent** | A Claude instance that can use tools |
| **Team** | A named group of agents. One leader + multiple teammates |
| **Teammate** | An agent that joined a team. Has a name, color, and inbox |
| **Leader** | The agent that created the team. Receives messages and approves plans/shutdowns |
| **Task** | A work unit with subject, description, status, owner, and dependencies |
| **Inbox** | JSON file where an agent receives messages from others |
| **Message** | JSON object sent between agents (plain text or structured) |

### Execution Backends

There are 3 backends that determine how teammates run:

- **in-process**: Same Node.js process. Fastest but invisible. Default outside tmux.
- **tmux**: Separate tmux panes. Visible and persistent.
- **iterm2**: Split panes in iTerm2 (macOS only).

Auto-detected based on environment (`$TMUX`, `$TERM_PROGRAM`, availability of `tmux`/`it2`).

---

## Two Ways to Create Agents

### 1. Task Tool (Subagents) — Ephemeral

```javascript
Task({
  subagent_type: "Explore",
  description: "Find auth files",
  prompt: "Find all authentication-related files",
  model: "haiku"
})
```

- Runs synchronously (or async with `run_in_background: true`)
- Returns result directly
- **No team required**
- Ideal for: searches, analysis, one-off research

### 2. Task + team_name + name (Teammates) — Persistent

```javascript
Task({
  team_name: "my-project",
  name: "security-reviewer",
  subagent_type: "security-sentinel",
  prompt: "Review auth code...",
  run_in_background: true
})
```

- Joins the team, appears in `config.json`
- Communicates via inbox messages
- Can claim tasks from the shared task list
- Persists until shutdown is requested
- Ideal for: parallel work, ongoing collaboration, pipeline stages

**Key difference**: Subagents are "fire-and-forget" with direct results. Teammates are persistent with inbox-based communication.

---

## Available Agent Types

### Built-in (always available)

| Type | Tools | Best for |
|------|-------|----------|
| `Bash` | Bash only | Git operations, system commands |
| `Explore` | Read-only | Code exploration, searches (optimized with haiku) |
| `Plan` | Read-only | Architecture design, planning |
| `general-purpose` | All (*) | Multi-step tasks, research + implementation |
| `claude-code-guide` | Read + Web | Questions about Claude Code |
| `statusline-setup` | Read + Edit | Configure status line |

### Plugin (compound-engineering)

Organized by category:

- **Review agents** (15+): security-sentinel, performance-oracle, architecture-strategist, code-simplicity-reviewer, pattern-recognition-specialist, etc.
- **Research agents** (5): best-practices-researcher, framework-docs-researcher, git-history-analyzer, repo-research-analyst, learnings-researcher
- **Design agents**: figma-design-sync
- **Workflow agents**: bug-reproduction-validator

Referenced with prefix: `compound-engineering:review:security-sentinel`

---

## TeammateTool Operations

The full lifecycle is managed with these 13 operations:

### Team Management
1. **spawnTeam** — Create a team (you become the leader)
2. **discoverTeams** — List available teams
3. **cleanup** — Remove team resources (requires all teammates to be shut down)

### Membership
4. **requestJoin** — Request to join a team
5. **approveJoin** — Accept a join request (leader only)
6. **rejectJoin** — Reject a join request (leader only)

### Communication
7. **write** — Send a message to a specific teammate
8. **broadcast** — Send a message to ALL teammates (expensive, avoid if possible)

### Lifecycle
9. **requestShutdown** — Ask a teammate to exit (leader only)
10. **approveShutdown** — Accept shutdown (teammate only)
11. **rejectShutdown** — Reject shutdown (teammate only)

### Plans
12. **approvePlan** — Approve a teammate's plan (leader only)
13. **rejectPlan** — Reject a plan with feedback (leader only)

---

## Task System

Tasks are the team's shared work queue:

- **TaskCreate** — Create tasks with subject, description, and activeForm
- **TaskList** — View all tasks and their status
- **TaskGet** — Get details of a specific task
- **TaskUpdate** — Update status, owner, or dependencies

### Dependencies

Managed with `addBlockedBy`. When a blocking task completes, blocked tasks are automatically unblocked:

```javascript
TaskUpdate({ taskId: "2", addBlockedBy: ["1"] })  // #2 waits for #1
// When #1 completes → #2 is automatically unblocked
```

### File Structure

```
~/.claude/teams/{team-name}/
├── config.json              # Team metadata and members
└── inboxes/
    ├── team-lead.json       # Leader's inbox
    └── worker-1.json        # Worker's inbox

~/.claude/tasks/{team-name}/
├── 1.json                   # Task #1
└── 2.json                   # Task #2
```

---

## Orchestration Patterns

The skill documents 6 main patterns:

### 1. Parallel Specialists (Leader Pattern)
Multiple specialists review code simultaneously. The leader creates the team, spawns reviewers in parallel, collects results, and synthesizes findings.

### 2. Pipeline (Sequential Dependencies)
Sequential stages with dependencies: Research → Plan → Implement → Test → Review. Each stage unblocks when the previous one completes.

### 3. Swarm (Self-Organizing)
Generic workers that grab tasks from a pool. They race to claim tasks and naturally load-balance. Ideal for many independent tasks.

### 4. Research + Implementation
Research first (synchronous), then implement using the research results as context.

### 5. Plan Approval Workflow
Requires leader approval before implementation. Uses `mode: "plan"` and the `plan_approval_request` flow.

### 6. Coordinated Multi-File Refactoring
Workers with clear file boundaries, with dependencies for coordination (e.g., specs depend on refactors completing).

---

## Message Formats

Messages can be:

- **Plain text**: `{ "from": "...", "text": "...", "read": false }`
- **Structured** (JSON in the text field):
  - `shutdown_request` / `shutdown_approved`
  - `idle_notification`
  - `task_completed`
  - `plan_approval_request`
  - `join_request`
  - `permission_request`

---

## Error Handling and Shutdown

### Correct shutdown sequence:
1. `requestShutdown` all teammates
2. Wait for `shutdown_approved` from each one
3. Verify no active members remain
4. Call `cleanup`

### Crashed teammates:
- 5-minute heartbeat timeout
- Automatically marked as inactive
- Their tasks can be claimed by others
- Cleanup works after timeout expires

---

## Best Practices

1. **Always cleanup** — Don't leave orphaned teams
2. **Meaningful names** — `security-reviewer` > `worker-1`
3. **Clear prompts** — Step-by-step instructions, not "review the code"
4. **Use task dependencies** — Let the system manage unblocking
5. **Prefer write over broadcast** — broadcast is expensive (N messages)
6. **Match agent type to task** — Explore for searches, general-purpose for implementation
7. **Handle failures** — Workers have a 5-min timeout, build retry logic

---

## Technical Notes

- Based on Claude Code v2.1.19
- Teammates automatically receive environment variables: `CLAUDE_CODE_TEAM_NAME`, `CLAUDE_CODE_AGENT_NAME`, etc.
- Backend can be forced with `CLAUDE_CODE_SPAWN_BACKEND=in-process|tmux`
- Backend type is recorded per teammate in `config.json`
- A teammate's text output is NOT visible to the team — it MUST use `write` to communicate
