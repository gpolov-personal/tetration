# eigen-core

Shared utility library for [`eigen-squared`](../eigen-squared/) and `eigen-lite`. **Not a user-facing plugin** — declares no slash commands or skills. Sibling plugins import its modules at runtime.

## Modules

- `eigen_core.cli.git_ops` — git sync/checkout/commit/push primitives, schema-agnostic.
- `eigen_core.cli.scheduler` — claude-tasks API scheduling with retry detection, dedup window, circuit breaker. Skill resolution and task naming injected by callers (no hardcoded mapping).
- `eigen_core.cli.state_io` — raw JSON load/save for pipeline state files; typed wrappers live in consumer plugins.
- `eigen_core.cli.base_models` — primitives shared by every consumer schema: `Convergence`, `FindingsSummary`, `MainCommandState`, `Recommendation`.

## Consumer setup

Consumer plugins inject `plugins/eigen-core/` onto `sys.path` from their own `cli/__init__.py`:

```python
import sys
from pathlib import Path

_core = Path(__file__).resolve().parent.parent.parent / "eigen-core"
if _core.exists() and str(_core) not in sys.path:
    sys.path.insert(0, str(_core))
```

After that, `from eigen_core.cli.git_ops import sync, commit_state` and the rest works directly.

## Tests

```bash
cd plugins/eigen-core
python -m pytest eigen_core/cli/tests/ -q
```
