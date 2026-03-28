"""Main argparse dispatcher for the eigen-squared CLI."""

from __future__ import annotations

import argparse
import sys

from . import __version__


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="eigen-squared",
        description="Deterministic pipeline state management for eigen-squared",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")

    sub = parser.add_subparsers(dest="command", help="Available commands")

    # ── init ──
    p = sub.add_parser("init", help="Create pipeline_state.json from scratch")
    p.add_argument("--initiative", required=True, help="Initiative name")
    p.add_argument("--phase-count", type=int, required=True, help="Number of phases")
    p.add_argument("--state-file", help="Override state file path")

    # ── status ──
    p = sub.add_parser("status", help="Show pipeline status overview")
    p.add_argument("--json", action="store_true", dest="as_json", help="JSON output")

    # ── next ──
    p = sub.add_parser("next", help="Return the next command to run + context")
    p.add_argument("--json", action="store_true", dest="as_json", help="JSON output")

    # ── get-context ──
    p = sub.add_parser("get-context", help="Return context for a command on entry")
    p.add_argument("target_command", help="Command name (e.g., bootstrap)")
    p.add_argument("--phase", type=int, help="Phase number")
    p.add_argument("--epic", type=int, help="Epic number")
    p.add_argument("--json", action="store_true", dest="as_json", help="JSON output")

    # ── complete ──
    p = sub.add_parser("complete", help="Record command completion")
    p.add_argument("target_command", help="Command that completed")
    p.add_argument("--phase", type=int, help="Phase number")
    p.add_argument("--epic", type=int, help="Epic number")
    p.add_argument("--phase-count", type=int, help="Phase count (time_split only)")
    p.add_argument("--output-path", help="Primary output file path")
    p.add_argument("--output-paths", help="JSON dict of output paths")
    p.add_argument("--feedback-path", help="Feedback file path (deepen commands)")
    p.add_argument("--findings-summary", help="JSON findings summary (deepen commands)")
    p.add_argument("--manifest-path", help="Swarm manifest path")
    p.add_argument("--integration-branch", help="Integration branch name")
    p.add_argument("--pr-url", help="Pull request URL")
    p.add_argument("--pr-number", type=int, help="Pull request number")
    p.add_argument("--report-path", help="Review report path")
    p.add_argument("--epic-manifest", help="Epic manifest path (space_split)")
    p.add_argument("--e2e-config", help="E2E config path (space_split)")
    p.add_argument("--epic-ids", help="JSON list of epic IDs (space_split)")
    p.add_argument("--plan-file", help="Plan file path (plan_epic_converge)")
    p.add_argument("--locked-skills", help="JSON list of locked skill names (deepen commands)")

    # ── mark-converged ──
    p = sub.add_parser("mark-converged", help="Set convergence for a step")
    p.add_argument("target_command", help="Command to converge (e.g., time_split)")
    p.add_argument("--phase", type=int, help="Phase number")
    p.add_argument("--epic", type=int, help="Epic number")
    p.add_argument("--reason", required=True, help="Convergence reason")

    # ── add-recommendation ──
    p = sub.add_parser("add-recommendation", help="Add downstream recommendation")
    p.add_argument("--from-cmd", required=True, dest="from_cmd", help="Source deepen command")
    p.add_argument("--target", required=True, help="Target command")
    p.add_argument("--phase", type=int, help="Phase number")
    p.add_argument("--epic", type=int, help="Epic number")
    p.add_argument("--text", required=True, help="Recommendation text")
    p.add_argument("--iteration", type=int, default=0, help="Source iteration")

    # ── clear-recommendations ──
    p = sub.add_parser("clear-recommendations", help="Clear recommendations from a source")
    p.add_argument("--from-cmd", required=True, dest="from_cmd", help="Source command to clear")

    # ── set-swarm-status ──
    p = sub.add_parser("set-swarm-status", help="Update swarm execution status")
    p.add_argument("status_value", help="Status: not_started|pr_created|iterating|converged")
    p.add_argument("--phase", type=int, required=True)
    p.add_argument("--epic", type=int, required=True)
    p.add_argument("--pr-url", help="Pull request URL")
    p.add_argument("--pr-number", type=int, help="Pull request number")
    p.add_argument("--manifest-path", help="Manifest path")
    p.add_argument("--integration-branch", help="Integration branch")

    # ── add-review-report ──
    p = sub.add_parser("add-review-report", help="Append review report path")
    p.add_argument("--phase", type=int, required=True)
    p.add_argument("--epic", type=int, required=True)
    p.add_argument("--report-path", required=True)

    # ── init-plan ──
    p = sub.add_parser("init-plan", help="Create plans entry for a new epic")
    p.add_argument("--phase", type=int, required=True)
    p.add_argument("--epic", type=int, required=True)

    # ── set-phase-review ──
    p = sub.add_parser("set-phase-review", help="Update phase review status")
    p.add_argument("--phase", type=int, required=True)
    p.add_argument("--status", required=True, dest="review_status",
                   choices=["not_started", "testing", "approved"])
    p.add_argument("--testing-recipe", help="Testing recipe path")

    # ── commit-state ──
    p = sub.add_parser("commit-state", help="Git add + commit + push pipeline state")
    p.add_argument("--message", required=True, help="Commit message")
    p.add_argument("--additional-paths", help="Comma-separated additional paths to stage")
    p.add_argument("--branch", help="Branch to push to")
    p.add_argument("--schedule-next", action="store_true", dest="schedule_next",
                   help="After commit, auto-schedule the next pipeline command")

    # ── sync ──
    p = sub.add_parser("sync", help="Git pull latest from branch")
    p.add_argument("--branch", help="Branch to pull (defaults to $EIGEN_BRANCH)")

    # ── resolve-branch ──
    p = sub.add_parser("resolve-branch", help="Print branch for next command")
    p.add_argument("--json", action="store_true", dest="as_json")

    # ── checkout-branch ──
    p = sub.add_parser("checkout-branch", help="Checkout integration branch")
    p.add_argument("--phase", type=int, required=True)
    p.add_argument("--epic", type=int, required=True)
    p.add_argument("--create", action="store_true", help="Create if doesn't exist")

    # ── schedule-next ──
    p = sub.add_parser("schedule-next", help="Determine + schedule next command")
    p.add_argument("--delay-minutes", type=int, default=3)

    # ── validate ──
    p = sub.add_parser("validate", help="Validate pipeline_state.json")
    p.add_argument("--fix", action="store_true", help="Fix missing fields with defaults")

    # ── install ──
    p = sub.add_parser("install", help="Install pipeline environment in project")
    p.add_argument("--root", required=True, help="Project root path")
    p.add_argument("--branch", required=True, help="Default branch name")
    p.add_argument("--tasks-api", required=True, help="claude-tasks API URL")
    p.add_argument("--telegram", help="Telegram chat ID")
    p.add_argument("--slack", help="Slack webhook URL")
    p.add_argument("--discord", help="Discord webhook URL")

    args = parser.parse_args(argv)

    if not args.command:
        parser.print_help()
        return 1

    # Dispatch to subcommand handlers
    from .subcommands import dispatch
    return dispatch(args)
