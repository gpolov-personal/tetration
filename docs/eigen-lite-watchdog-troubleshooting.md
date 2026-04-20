# eigen-lite-watchdog — troubleshooting

How to diagnose the most common failure modes. Each section lists the log line you'll see, what it means, and the minimum action to recover.

## Where to look first

- **Watchdog log:** `<project>/.eigen-lite/watchdog.log` — one line per cron tick. Timestamped.
- **Hook log:** `<project>/.eigen-lite/hook_log.jsonl` — per-call scheduling decisions (pending, confirmed, failed, stalled, deduplicated). Richer than the watchdog log.
- **Env file:** `<project>/.eigen-lite/env` — must define `EIGEN_ROOT`, `EIGEN_BRANCH`, `CLAUDE_TASKS_API`.

## Symptom index

### `ERROR: env file not found at <path>/.eigen-lite/env`

The watchdog can't find the env file it sources on every tick. Cause: you haven't run `eigen-lite install` in this project, or somebody deleted `.eigen-lite/`.

**Recover:**
```bash
eigen-lite install --root "$(pwd)" --branch main --tasks-api http://localhost:8080
```
`install` only writes the env file — it does not schedule work. The next cron tick will pick things up.

### `ERROR: EIGEN_ROOT is empty in <env file>` (or `CLAUDE_TASKS_API`)

Env file exists but a required variable is blank. Either the file was hand-edited and lost a value, or `install` was run with an empty flag.

**Recover:** re-run `eigen-lite install` with the correct flags, or edit the env file directly and make sure every line is `KEY="value"` (no stray whitespace).

### `WARN: .eigen-lite/env is older than .claude/settings.json`

You changed settings (e.g., a new Telegram chat ID or API URL) but the env file still has the old values. The watchdog is still running fine; it's just telling you the env is stale.

**Recover:**
```bash
cd <project>
eigen-lite write-env
```
`write-env` regenerates the env from the current process environment, so make sure the variables you want are exported in the shell you run it from.

### `WARN: claude-tasks API unreachable at <url>`

The watchdog tried to GET `/api/v1/tasks` and curl failed. Either the service is down, the URL is wrong, or a firewall/proxy is blocking the request.

**Recover:**
```bash
# Confirm the server is actually answering:
curl -sf "$CLAUDE_TASKS_API/api/v1/tasks" | head
```
If that curl fails from your shell too, fix the server (or the URL) — the watchdog will resume on the next tick once the endpoint responds.

### Watchdog exits silently (exit 0) and nothing was scheduled

Three innocent causes, all normal:
1. **Another watchdog instance holds the lock.** `flock -n` on `<project>/.eigen-lite/watchdog.lock` ensures one run at a time. The overlapping tick just exits.
2. **A task is already `running` in claude-tasks for this project.** The watchdog waits for it to finish before scheduling the next one.
3. **Pipeline is complete.** `eigen-lite next --json` returned `{"command": null}`. There's nothing more to do.

Distinguish them from the hook log — on case 2 or 3 there's no new entry; on case 1 there's no new entry either but `lsof .eigen-lite/watchdog.lock` will show the other holder.

### `STALLED: pipeline stalled after max retries for <task name>`

Scheduler saw the same command+context fail four times in a row, or the POST to `/api/v1/tasks` failed ten times. It gives up to prevent infinite cron loops.

**Recover:**
1. Inspect `.eigen-lite/hook_log.jsonl` — the last few entries show whether the failure was scheduling (couldn't reach the API) or execution (the command itself failed).
2. If execution kept failing, read the task's working notes (under `swarm_working_notes/` for lite_swarm/lite_review, or the last lite_plan output) and fix whatever's broken.
3. Reset the stall by forcing a new context key — e.g., mark the current step converged with `eigen-lite mark-converged <command> --epic N --reason "manual intervention"` and let the watchdog pick up whatever comes next.

To resume without changing state, just delete the last few failed entries from `.eigen-lite/hook_log.jsonl` and the next tick will retry from scratch. The hook log is a tail-read cache, not authoritative state — it's safe to trim.

### `INFO: retry detected for <task name> (last task name matches)`

Not a failure — the watchdog noticed the most recent task has the same name as the next one it's about to schedule, so it appends a RE-RUN warning to the prompt. The executing command can then notice the warning, read working notes, and avoid redoing prior partial work.

Only worry if this message appears more than 2–3 ticks in a row for the same task — that's close to the stall threshold.

## Lock file is stuck (rare)

`flock -n` releases the lock when the script exits, even on crash. If a lock-file remains as a zero-byte file but no process holds it (confirm with `lsof <project>/.eigen-lite/watchdog.lock`), you can safely remove it:
```bash
rm <project>/.eigen-lite/watchdog.lock
```
The next tick will recreate it. Do not delete the lock file while a watchdog is running — you'll get concurrent scheduling, which is what the lock is there to prevent.

## Coexistence with eigen-squared

Each plugin has its own `.eigen/` or `.eigen-lite/` directory, so their locks, env files, and hook logs never collide. If you ever run both in the same project (discouraged; see `plugins/eigen-lite/README.md`), the only shared state is `phases/phase_1/epic_*/` artifacts under `eigen_initiative/` — the pipeline state files themselves (`pipeline_state.json` vs `pipeline_state_lite.json`) are separate.
