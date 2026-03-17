# Skill Index: Orchestrating Swarms

> **Usage**: Before reading the full skill (`SKILL.md`, 1718 lines), check this index to jump directly to the relevant section.
>
> **Format**: Each entry indicates the exact lines to read with `Read(file, offset, limit)`.

---

## By Question / Need

### "What is X?" — Definitions and Concepts

| Question | Section | Lines |
|----------|---------|-------|
| What primitives exist? (Agent, Team, Task, Inbox...) | Primitives | 13–61 |
| What is a Team? A Teammate? A Leader? | Primitives | 13–24 |
| How do the primitives relate to each other? | How They Connect (diagram) | 28–49 |
| What is the lifecycle of a swarm? | Lifecycle + Message Flow | 53–93 |
| What file structure does it use? | File Structure | 126–138 |
| What does a team's config.json look like? | Team Config Structure | 142–172 |

### "How do I create/spawn...?" — Creating Agents

| Question | Section | Lines |
|----------|---------|-------|
| How do I create a simple subagent (no team)? | Method 1: Task Tool | 180–196 |
| How do I create a persistent teammate (with team)? | Method 2: Task + team_name | 199–220 |
| What's the difference between subagent and teammate? | Key Difference (table) | 222–231 |
| How do I create a team? | spawnTeam | 424–438 |

### "What agents can I use?" — Agent Types

| Question | Section | Lines |
|----------|---------|-------|
| What built-in agents exist? | Built-in Agent Types | 234–310 |
| How do I use Bash/Explore/Plan/general-purpose? | Built-in Agent Types | 239–298 |
| What review agents are available? (security, performance...) | Plugin: Review Agents | 316–370 |
| What research agents are available? | Plugin: Research Agents | 372–401 |
| What design/workflow agents are available? | Plugin: Design + Workflow | 403–419 |
| Full list of plugin review agents | All review agents list | 356–370 |
| Full list of plugin research agents | All research agents list | 395–401 |

### "How do I communicate?" — Inter-agent Messaging

| Question | Section | Lines |
|----------|---------|-------|
| How do I send a message to a teammate? | write | 486–496 |
| How do I send a message to everyone? | broadcast | 498–517 |
| When should I use write vs broadcast? | broadcast (when to/not to) | 509–517 |
| What message formats exist? | Message Formats | 686–784 |
| What does a plain text message look like? | Regular Message | 690–698 |
| What does a shutdown_request/approved look like? | Structured: Shutdown | 701–721 |
| What does an idle_notification look like? | Structured: Idle | 723–732 |
| What does a plan_approval_request look like? | Structured: Plan | 747–756 |
| What does a permission_request look like? | Structured: Permission | 768–784 |

### "How do I manage tasks?" — Task System

| Question | Section | Lines |
|----------|---------|-------|
| How do I create tasks? | TaskCreate | 599–606 |
| How do I list tasks? | TaskList | 608–620 |
| How do I get task details? | TaskGet | 622–628 |
| How do I update task status/owner? | TaskUpdate | 630–643 |
| How do I set up task dependencies? | Task Dependencies | 645–664 |
| What does a task JSON file look like? | Task File Structure | 668–683 |
| How do I create an independent task pool? | Pattern 3: Swarm | 873–925 |
| How do I create a sequential task pipeline? | Pattern 2: Pipeline | 835–871 |

### "How do I manage the team?" — Full TeammateTool Reference

| Question | Section | Lines |
|----------|---------|-------|
| Full TeammateTool reference | TeammateTool Operations | 422–593 |
| How do I create a team? | spawnTeam | 424–438 |
| How do I discover existing teams? | discoverTeams | 440–445 |
| How do I request to join a team? | requestJoin | 447–455 |
| How do I approve/reject join requests? | approveJoin / rejectJoin | 457–483 |
| How do I ask a teammate to shut down? | requestShutdown | 519–528 |
| How do I approve/reject a shutdown? | approveShutdown / rejectShutdown | 530–554 |
| How do I approve/reject a plan? | approvePlan / rejectPlan | 556–580 |
| How do I clean up team resources? | cleanup | 582–593 |

### "Which pattern should I use for...?" — Orchestration Patterns

| Question | Section | Lines |
|----------|---------|-------|
| Parallel review with specialists | Pattern 1: Parallel Specialists | 789–831 |
| Sequential pipeline (step by step) | Pattern 2: Pipeline | 835–871 |
| Self-organizing task pool | Pattern 3: Swarm | 873–925 |
| Research first, then implement | Pattern 4: Research + Implementation | 927–951 |
| Require plan approval before implementing | Pattern 5: Plan Approval | 953–987 |
| Coordinated multi-file refactoring | Pattern 6: Coordinated Refactoring | 989–1041 |

### "How do I shut down/clean up?" — Teardown

| Question | Section | Lines |
|----------|---------|-------|
| Correct shutdown sequence | Graceful Shutdown Sequence | 1374–1389 |
| What happens if a teammate crashes? | Handling Crashed Teammates | 1392–1399 |
| Debugging commands | Debugging | 1401–1417 |
| Common errors and solutions | Common Errors (table) | 1361–1371 |

### "Which backend should I use?" — Execution Backends

| Question | Section | Lines |
|----------|---------|-------|
| Backend comparison (table) | Backend Comparison | 1074–1082 |
| Auto-detection logic | Auto-Detection Logic | 1084–1107 |
| in-process details | in-process backend | 1108–1156 |
| tmux details | tmux backend | 1158–1231 |
| iterm2 details | iterm2 backend | 1233–1290 |
| How do I force a specific backend? | Forcing a Backend | 1294–1306 |
| Backend troubleshooting | Troubleshooting Backends | 1328–1356 |

### "How do I do X properly?" — Best Practices

| Question | Section | Lines |
|----------|---------|-------|
| General best practices | Best Practices | 1620–1677 |
| Teammate environment variables | Environment Variables | 1046–1068 |

### Complete Workflows (copy and adapt)

| Workflow | Description | Lines |
|----------|-------------|-------|
| Code review with parallel specialists | Setup → Spawn → Monitor → Synthesize → Cleanup | 1423–1493 |
| Research → Plan → Implement → Test pipeline | Full 5-stage pipeline with specialized workers | 1495–1556 |
| Self-organizing file review swarm | Task pool + workers racing to claim them | 1558–1616 |

### Quick Reference (cheat sheet)

| What | Lines |
|------|-------|
| Spawn subagent without team | 1687–1689 |
| Spawn teammate with team | 1691–1694 |
| Send a message | 1697–1699 |
| Create a task pipeline | 1702–1707 |
| Shut down a team | 1710–1714 |

---

## How to Use This Index

1. Receive a question from the user about swarms
2. Find the closest matching question in this index
3. Read **only** the indicated lines from `SKILL.md` using `Read(file, offset=line, limit=N)`
4. If more context is needed, read adjacent sections
