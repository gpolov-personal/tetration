"""Main argparse dispatcher for the eigen-lite CLI."""

from __future__ import annotations

import argparse

from . import __version__
from . import plumbing  # noqa: F401 — imports for side-effect: registers handlers
from .subcommands import dispatch


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="eigen-lite",
        description="Destilated eigen pipeline for small single-phase initiatives.",
    )
    parser.add_argument(
        "--version", action="version", version=f"%(prog)s {__version__}"
    )
    parser.add_argument(
        "--state-file",
        help="Override pipeline_state_lite.json path "
             "(default: $EIGEN_ROOT/eigen_initiative/phases/pipeline_state_lite.json)",
    )

    sub = parser.add_subparsers(dest="command", help="Available commands")

    # ── init ──
    p = sub.add_parser("init", help="Create pipeline_state_lite.json from scratch")
    p.add_argument("--feature-set", required=True, dest="feature_set",
                   help="Name of the feature set / initiative")
    p.add_argument("--epic-count", type=int, default=0, dest="epic_count",
                   help="Known epic count; typically 0 until lite_plan Stage D runs")
    p.add_argument("--force", action="store_true",
                   help="Overwrite existing state file")

    # ── status ──
    p = sub.add_parser("status", help="Show pipeline status overview")
    p.add_argument("--json", action="store_true", dest="as_json",
                   help="JSON output")

    # ── next ──
    p = sub.add_parser("next", help="Return the next command to run + context")
    p.add_argument("--json", action="store_true", dest="as_json")

    # ── get-context ──
    p = sub.add_parser("get-context",
                       help="Return context for a command on entry")
    p.add_argument("target_command",
                   choices=["lite_plan", "lite_swarm", "lite_review"])
    p.add_argument("--epic", type=int, help="Epic number (required for swarm/review)")
    # --json is a no-op (output is always JSON) — accepted for symmetry with
    # `next --json` so command docs can use a uniform form.
    p.add_argument("--json", action="store_true", dest="as_json",
                   help="(no-op) output is always JSON")

    # ── complete ──
    p = sub.add_parser("complete", help="Record command completion")
    p.add_argument("target_command",
                   choices=["lite_plan", "lite_swarm", "lite_review"])
    p.add_argument("--epic", type=int)
    p.add_argument("--stage", help="Stage marker to append (lite_plan)")
    p.add_argument("--output-paths", dest="output_paths",
                   help="JSON dict of output paths (lite_plan)")
    p.add_argument("--converged", action="store_true",
                   help="Mark command converged (lite_plan)")
    p.add_argument("--decided-by", dest="decided_by")
    p.add_argument("--reason")
    p.add_argument("--pr-url", dest="pr_url", help="Pull request URL (lite_swarm)")
    p.add_argument("--pr-number", type=int, dest="pr_number",
                   help="Pull request number (lite_swarm)")
    p.add_argument("--integration-branch", dest="integration_branch",
                   help="Integration branch name (lite_swarm)")
    p.add_argument("--report-path", dest="report_path",
                   help="Review report path (lite_review)")
    p.add_argument("--findings-summary", dest="findings_summary",
                   help="JSON priority-shape dict (lite_review)")

    # ── mark-converged ──
    p = sub.add_parser("mark-converged", help="Force convergence on a step")
    p.add_argument("target_command",
                   choices=["lite_plan", "lite_swarm", "lite_review"])
    p.add_argument("--epic", type=int)
    p.add_argument("--reason", required=True)

    # ── set-swarm-status ──
    p = sub.add_parser("set-swarm-status", help="Update swarm execution status")
    p.add_argument("status_value",
                   help="not_started|pr_created|iterating|converged")
    p.add_argument("--epic", type=int, required=True)
    p.add_argument("--pr-url", dest="pr_url")
    p.add_argument("--pr-number", type=int, dest="pr_number")
    p.add_argument("--integration-branch", dest="integration_branch")

    # ── add-review-report ──
    p = sub.add_parser("add-review-report", help="Append review report path")
    p.add_argument("--epic", type=int, required=True)
    p.add_argument("--report-path", required=True, dest="report_path")

    # ── init-epics ──
    p = sub.add_parser("init-epics",
                       help="Lazy-init state.epics after lite_plan Stage D")
    p.add_argument("--epics", required=True, dest="epics_json",
                   help="JSON list: [{\"epic\": 1, \"is_e2e_epic\": false}, ...]")

    # ── validate ──
    sub.add_parser("validate", help="Validate pipeline_state_lite.json")

    # ── sync ──
    p = sub.add_parser("sync", help="Git pull latest from branch")
    p.add_argument("--branch", help="Branch (defaults to $EIGEN_BRANCH)")

    # ── commit-state ──
    p = sub.add_parser("commit-state",
                       help="Git add + commit + push pipeline state")
    p.add_argument("--message", required=True)
    p.add_argument("--additional-paths", dest="additional_paths",
                   help="Comma-separated additional paths to stage")
    p.add_argument("--branch", help="Branch to push to")

    # ── resolve-branch ──
    p = sub.add_parser("resolve-branch",
                       help="Print branch for the next command")
    p.add_argument("--json", action="store_true", dest="as_json")

    # ── checkout-branch ──
    p = sub.add_parser("checkout-branch", help="Checkout integration branch")
    p.add_argument("--epic", type=int, required=True)
    p.add_argument("--create", action="store_true",
                   help="Create the branch if it doesn't exist")

    # ── write-env ──
    sub.add_parser("write-env",
                   help="Regenerate .eigen-lite/env from current process env")

    # ── install ──
    p = sub.add_parser("install", help="Create .eigen-lite/ with env file")
    p.add_argument("--root", required=True)
    p.add_argument("--branch", required=True)
    p.add_argument("--tasks-api", required=True, dest="tasks_api")
    p.add_argument("--telegram")
    p.add_argument("--slack")
    p.add_argument("--discord")

    # ── schedule-next ──
    p = sub.add_parser("schedule-next",
                       help="Determine + schedule the next command")
    p.add_argument("--delay-minutes", type=int, default=1,
                   dest="delay_minutes")
    p.add_argument("--extra-prompt", default="", dest="extra_prompt")

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if not args.command:
        parser.print_help()
        return 1

    return dispatch(args)
