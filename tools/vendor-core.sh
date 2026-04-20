#!/usr/bin/env bash
# Vendor plugins/eigen-core/eigen_core/ into each consumer plugin's _vendored/
# directory. Runs from pre-commit and from CI drift check. Idempotent.
#
# Why: plugin caches under ~/.claude/plugins/cache/<marketplace>/<plugin>/<version>/
# only contain the plugin's own subtree — cross-plugin path traversal does not
# survive install. Each consumer must bundle its own copy of eigen_core.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SOURCE="$REPO_ROOT/plugins/eigen-core/eigen_core"
CONSUMERS=("eigen-squared" "eigen-lite")

if [[ ! -d "$SOURCE" ]]; then
  echo "ERROR: source $SOURCE not found" >&2
  exit 1
fi

for consumer in "${CONSUMERS[@]}"; do
  target_parent="$REPO_ROOT/plugins/$consumer/_vendored"
  target="$target_parent/eigen_core"

  if [[ ! -d "$REPO_ROOT/plugins/$consumer" ]]; then
    echo "skip: plugins/$consumer not present"
    continue
  fi

  mkdir -p "$target_parent"
  rm -rf "$target"
  cp -R "$SOURCE" "$target"

  # Strip test files from the vendored copy — consumers test their own shims
  # and eigen-core ships its own tests at its plugin root.
  find "$target" -type d -name tests -prune -exec rm -rf {} +
  find "$target" -type d -name __pycache__ -prune -exec rm -rf {} +

  echo "vendored: $consumer/_vendored/eigen_core"
done
