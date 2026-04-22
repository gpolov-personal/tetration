"""Git operations — re-exported from eigen_core for backward compatibility.

The implementation lives in eigen-core; this module preserves the
``cli.git_ops`` import path used by squared subcommands and tests.
"""

from eigen_core.cli.git_ops import (  # noqa: F401
    checkout_branch,
    commit_state,
    current_branch,
    integration_branch_name,
    run_git,
    sync,
)
