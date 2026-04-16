---
name: code_from_validation_tests_swarm
description: Step B of the eigen-squared worker swarm — implement code to make the validation tests pass (TDD), after Step A has produced the tests. Use when a parent orchestrator (e.g. orchestrate_swarm) delegates the implementation step of a worker's TDD cycle. This is a **skill bridge**: the operational content lives in the corresponding command file at `.opencode/commands/code_from_validation_tests_swarm.md` (the skill redirects to it so that runtimes without a unified skills/commands model — like OpenCode — can still honor `Skill("code_from_validation_tests_swarm")` invocations).
---

# code_from_validation_tests_swarm (skill bridge)

This skill exists so that a parent command can invoke it via the `skill` / `Skill` tool even on runtimes (like OpenCode) whose skill-lookup does not cover the `commands/` directory. The operational content is the command file:

```
.opencode/commands/code_from_validation_tests_swarm.md
```

## Instructions for the invoking agent

1. Open the command file above using the `read` tool.
2. Execute its instructions literally, top to bottom, as if the command had been invoked directly (e.g. via `/code_from_validation_tests_swarm <task_id>` in Claude Code).
3. The caller typically supplies a task ID along with the invocation (in Claude Code: `Skill("code_from_validation_tests_swarm", args: "<task_id>")`). On OpenCode the `skill` tool takes only a `name` parameter, so the task ID will have been mentioned in the caller's turn right before invoking this skill. Extract the task ID from the surrounding context and use it everywhere the command expects `$ARGUMENTS` or `$1`.
4. If you are running on OpenCode with a non-Anthropic model (GPT, Codex, MiniMax, Qwen, DeepSeek, Gemini), also apply the tool-name translation layer documented in the `orchestrating-swarms-opencode` skill when following the command.

## Why this bridge exists

Claude Code treats skills and slash commands as a unified discovery space: `Skill("foo")` finds both `.claude/skills/foo/SKILL.md` and `.claude/commands/foo.md`. OpenCode's `skill` tool only searches `.opencode/skills/**/SKILL.md`. To keep a single source of truth for the worker's operational content (the command file), this skill is an intentional thin redirect rather than a duplicate of the command body.
