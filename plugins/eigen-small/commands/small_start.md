---
name: small_start
description: ONE-TIME setup — install the `eigen-small` CLI wrapper on PATH so small_route/small_plan/small_build can call it. Manual-only (no watchdog, no env file). Re-run with --reinstall-cli-only after a version bump.
---

> ONE-TIME setup. Installs the `eigen-small` CLI globally (a thin wrapper in `~/.local/bin`).
> You don't run this again per project — after it, use `/small_route` to start work.
> eigen-small is **manual-only**: no autonomous watchdog and no `.eigen-small/env`. The CLI
> defaults `EIGEN_ROOT` to the current directory, so run the pipeline commands from your
> project root.

## Flag: `--reinstall-cli-only`

If invoked as `/small_start --reinstall-cli-only`, run only **Step 1** (reinstall the CLI
wrapper). Useful after a plugin version bump.

## Step 1 — Install the `eigen-small` CLI wrapper

1. **Resolve the plugin path.** Glob for `cli/__main__.py` under
   `~/.claude/plugins/cache/tetration/eigen-small/<version>/` (installed via the marketplace);
   in local dev use the repo path `…/tetration/plugins/eigen-small`. Store as `PLUGIN_PATH`.
   Read `$PLUGIN_PATH/.claude-plugin/plugin.json` for `version`.

2. **Version check** (idempotent):
   ```bash
   test -x ~/.local/bin/eigen-small && ~/.local/bin/eigen-small --version
   ```
   - Not installed → install.
   - Same version → skip (`eigen-small v<V> already installed`).
   - Different version → ask the user: overwrite or skip.

3. **Write the wrapper.** Uses the **`PYTHONPATH` method** (not `cd`): it must preserve the
   caller's working directory so the CLI's `EIGEN_ROOT` default (= cwd) resolves to the
   project, not the plugin dir.
   ```bash
   mkdir -p ~/.local/bin
   cat > ~/.local/bin/eigen-small <<WRAPPER_EOF
   #!/bin/bash
   # eigen-small CLI v<VERSION> — created by /small_start
   PLUGIN_PATH="<RESOLVED_PLUGIN_PATH>"
   if [ ! -d "$PLUGIN_PATH/cli" ]; then
       echo "ERROR: eigen-small plugin not found at $PLUGIN_PATH"
       echo "Run /small_start --reinstall-cli-only to fix."
       exit 1
   fi
   export PYTHONPATH="$PLUGIN_PATH"
   exec python3 -m cli "\$@"
   WRAPPER_EOF
   chmod +x ~/.local/bin/eigen-small
   ```

4. **Verify:** `eigen-small --version` (expect `eigen-small <VERSION>`). If `~/.local/bin` is
   not on `PATH`, print the fix for the user's `~/.bashrc` / `~/.zshrc`:
   `export PATH="$HOME/.local/bin:$PATH"`.

## Why no watchdog / env file (vs. eigen-squared / eigen-lite)

eigen-squared and eigen-lite also install a cron **watchdog** (autonomous scheduling) and a
project **`.eigen/env`** (`EIGEN_ROOT`/`EIGEN_BRANCH`/tasks-API). eigen-small v1 deliberately
has **neither**: it is manual-only, and the CLI defaults `EIGEN_ROOT` to the current
directory — so there is nothing to schedule and no env file to write. Run `/small_route`,
`/small_plan`, `/small_build` from your project root. (To layer a phase onto a repo whose
root is not your cwd, pass `--state-file <path>` or `export EIGEN_ROOT=<root>` for that run.)

## Next

Run `/small_route` to triage the work and start the pipeline.
