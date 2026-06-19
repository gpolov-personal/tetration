"""Main argparse dispatcher for the eigen-small CLI.

Thin (~9 verbs) and PERMISSIVE. State writes go through eigen-core's atomic raw
I/O (tmp-file + os.replace). Deliberately absent vs. eigen-squared: the strict
ordering gate, recommendation matrix, findings/signature validation, scheduler/
watchdog, gh-probe guards.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from . import __version__
from .state_small import (
    PLANNING_STAGES,
    VALID_STAGE_STATUS,
    StageMarker,
    Wave,
    SquaredSchemaDetected,
    create_initial_state,
    load_state,
    resolve_state_file,
    save_state,
    validate_state,
)
from .transitions_small import determine_next_small
from .freeze_ledger import Seam, add_seam, load_ledger, resolve_ledger_file, save_ledger


# ── helpers ───────────────────────────────────────────────────────────────

def _eigen_root() -> str:
    return os.environ.get("EIGEN_ROOT") or os.getcwd()


def _state_path(args: argparse.Namespace) -> Path:
    override = getattr(args, "state_file", None)
    return Path(override) if override else resolve_state_file(_eigen_root())


def _ledger_path() -> Path:
    return resolve_ledger_file(_eigen_root())


def _emit(obj: object) -> None:
    print(json.dumps(obj, indent=2))


def _err(msg: str) -> int:
    print(f"ERROR: {msg}", file=sys.stderr)
    return 1


# ── handlers ──────────────────────────────────────────────────────────────

def cmd_init(args: argparse.Namespace) -> int:
    path = _state_path(args)
    if path.exists() and not args.force:
        return _err(f"{path} already exists (use --force to overwrite)")
    state = create_initial_state(args.initiative, phase=args.phase)
    if args.shape:
        state.shape = args.shape
    if args.structure:
        state.dials["structure"] = args.structure
    if args.rigor:
        state.dials["rigor"] = args.rigor
    save_state(state, path)
    _emit({"created": str(path), "phase": state.phase, "shape": state.shape, "dials": state.dials})
    return 0


def cmd_set_shape(args: argparse.Namespace) -> int:
    state = load_state(_state_path(args))
    if state is None:
        return _err("no state file; run `small init` first")
    state.shape = args.shape
    if args.structure:
        state.dials["structure"] = args.structure
    if args.rigor:
        state.dials["rigor"] = args.rigor
    save_state(state, _state_path(args))
    _emit({"shape": state.shape, "dials": state.dials})
    return 0


def cmd_status(args: argparse.Namespace) -> int:
    state = load_state(_state_path(args))
    if state is None:
        _emit({"status": "no_state", "state_file": str(_state_path(args))})
        return 0
    _emit(state.to_dict())
    return 0


def cmd_next(args: argparse.Namespace) -> int:
    state = load_state(_state_path(args))
    if state is None:
        _emit({"next": "small_route", "context": {"step": "triage"}})
        return 0
    nxt = determine_next_small(state.to_dict())
    if nxt is None:
        _emit({"next": None, "done": True, "shape": state.shape})
        return 0
    command, context = nxt
    _emit({"next": command, "context": context})
    return 0


def cmd_set_stage(args: argparse.Namespace) -> int:
    state = load_state(_state_path(args))
    if state is None:
        return _err("no state file; run `small init` first")
    if args.stage not in state.stages:
        return _err(f"unknown stage {args.stage!r} (valid: {', '.join(PLANNING_STAGES)})")
    if args.status not in VALID_STAGE_STATUS:
        return _err(f"invalid status {args.status!r} (valid: {', '.join(sorted(VALID_STAGE_STATUS))})")
    state.stages[args.stage] = StageMarker(status=args.status, path=args.path)
    save_state(state, _state_path(args))
    _emit({"stage": args.stage, "status": args.status, "path": args.path})
    return 0


def cmd_set_waves(args: argparse.Namespace) -> int:
    state = load_state(_state_path(args))
    if state is None:
        return _err("no state file; run `small init` first")
    try:
        waves_raw = json.loads(args.waves_json)
    except json.JSONDecodeError as exc:
        return _err(f"--waves is not valid JSON: {exc}")
    if not isinstance(waves_raw, list):
        return _err("--waves must be a JSON array of wave objects")
    waves: list[Wave] = []
    for w in waves_raw:
        epics = [str(e) for e in (w.get("epics") or [])]
        waves.append(
            Wave(
                id=str(w.get("id", "")),
                epics=epics,
                parallel=bool(w.get("parallel", False)),
                epic_status={e: "pending" for e in epics},
                goal_status={e: "pending" for e in epics},
                review_status="pending",
            )
        )
    state.waves = waves
    save_state(state, _state_path(args))
    _emit({"waves": [w.to_dict() for w in waves]})
    return 0


def cmd_complete_epic(args: argparse.Namespace) -> int:
    state = load_state(_state_path(args))
    if state is None:
        return _err("no state file")
    wave = next((w for w in state.waves if w.id == args.wave), None)
    if wave is None:
        return _err(f"no wave {args.wave!r}")
    if args.epic not in wave.epics:
        return _err(f"epic {args.epic!r} not in wave {args.wave!r}")
    wave.epic_status[args.epic] = "implemented"
    if args.goal_green:
        wave.goal_status[args.epic] = "green"
    save_state(state, _state_path(args))
    _emit(
        {
            "wave": args.wave,
            "epic": args.epic,
            "epic_status": wave.epic_status[args.epic],
            "goal_status": wave.goal_status.get(args.epic),
        }
    )
    return 0


def cmd_set_wave_review(args: argparse.Namespace) -> int:
    state = load_state(_state_path(args))
    if state is None:
        return _err("no state file")
    wave = next((w for w in state.waves if w.id == args.wave), None)
    if wave is None:
        return _err(f"no wave {args.wave!r}")
    wave.review_status = args.status
    save_state(state, _state_path(args))
    _emit({"wave": args.wave, "review_status": wave.review_status})
    return 0


def cmd_validate(args: argparse.Namespace) -> int:
    state = load_state(_state_path(args))
    if state is None:
        return _err("no state file")
    errors = validate_state(state)
    if errors:
        for e in errors:
            print(f"INVALID: {e}", file=sys.stderr)
        return 1
    print("OK")
    return 0


def cmd_commit_state(args: argparse.Namespace) -> int:
    from eigen_core.cli import git_ops

    additional = (
        [p.strip() for p in args.additional_paths.split(",") if p.strip()]
        if args.additional_paths
        else []
    )
    ok = git_ops.commit_state(
        message=args.message,
        eigen_root=_eigen_root(),
        state_file=str(_state_path(args)),
        additional_paths=additional,
        branch=args.branch or "",
    )
    if not ok:
        print(json.dumps({"status": "failed"}), file=sys.stderr)
        return 1
    print(json.dumps({"status": "ok"}))
    return 0


def cmd_freeze_add(args: argparse.Namespace) -> int:
    ledger = load_ledger(_ledger_path())
    consumers = (
        [c.strip() for c in args.consumers.split(",") if c.strip()]
        if args.consumers
        else []
    )
    seam = Seam(
        name=args.name,
        phase=args.phase,
        kind=args.kind,
        signature=args.signature,
        consumers=consumers,
        note=args.note,
    )
    add_seam(ledger, seam)
    save_ledger(ledger, _ledger_path())
    _emit({"frozen": seam.name, "phase": seam.phase, "kind": seam.kind})
    return 0


def cmd_freeze_list(args: argparse.Namespace) -> int:
    ledger = load_ledger(_ledger_path())
    seams = ledger.seams
    if args.phase is not None:
        seams = [s for s in seams if s.phase <= args.phase]
    if args.kind:
        seams = [s for s in seams if s.kind == args.kind]
    _emit({"seams": [s.to_dict() for s in seams], "count": len(seams)})
    return 0


_HANDLERS = {
    "init": cmd_init,
    "set-shape": cmd_set_shape,
    "status": cmd_status,
    "next": cmd_next,
    "set-stage": cmd_set_stage,
    "set-waves": cmd_set_waves,
    "complete-epic": cmd_complete_epic,
    "set-wave-review": cmd_set_wave_review,
    "validate": cmd_validate,
    "commit-state": cmd_commit_state,
    "freeze-add": cmd_freeze_add,
    "freeze-list": cmd_freeze_list,
}


# ── parser ────────────────────────────────────────────────────────────────

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="eigen-small",
        description="Router-driven, artifact-robust, goal-gated pipeline for a "
        "feature or single-phase product (thin, permissive state CLI).",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    parser.add_argument(
        "--state-file",
        dest="state_file",
        help="Override the state path (default: "
        "$EIGEN_ROOT/eigen_initiative/phases/pipeline_state_small.json)",
    )

    sub = parser.add_subparsers(dest="command", help="Available commands")

    p = sub.add_parser("init", help="Create pipeline_state_small.json")
    p.add_argument("--initiative", required=True, help="Feature / product name")
    p.add_argument("--phase", type=int, default=1,
                   help="Phase SLOT this single run occupies (default 1; use 2 to layer "
                        "onto a repo that already ran phase 1 — artifacts go to phases/phase_<N>/)")
    p.add_argument("--shape", choices=["unknown", "direct", "single_phase", "defer_to_squared"])
    p.add_argument("--structure", choices=["unset", "none", "epics", "epics_parallel"])
    p.add_argument("--rigor", choices=["unset", "low", "standard", "high"])
    p.add_argument("--force", action="store_true", help="Overwrite existing state")

    p = sub.add_parser("set-shape", help="Record the triage decision (shape + dials)")
    p.add_argument("--shape", required=True,
                   choices=["direct", "single_phase", "defer_to_squared"])
    p.add_argument("--structure", choices=["none", "epics", "epics_parallel"])
    p.add_argument("--rigor", choices=["low", "standard", "high"])

    p = sub.add_parser("status", help="Show the full state")
    p.add_argument("--json", action="store_true", dest="as_json", help="(no-op; always JSON)")

    p = sub.add_parser("next", help="Permissive next step (never blocks a skip)")
    p.add_argument("--json", action="store_true", dest="as_json", help="(no-op; always JSON)")

    p = sub.add_parser("set-stage", help="Record a planning-stage outcome")
    p.add_argument("stage", choices=list(PLANNING_STAGES))
    p.add_argument("--status", required=True,
                   choices=sorted(VALID_STAGE_STATUS))
    p.add_argument("--path", help="Artifact path produced/reused by this stage")

    p = sub.add_parser("set-waves", help="Set the DAG-ordered wave plan (JSON)")
    p.add_argument("--waves", required=True, dest="waves_json",
                   help='JSON array: [{"id":"a","epics":["E3","E4"],"parallel":true}, ...]')

    p = sub.add_parser("complete-epic", help="Mark an epic implemented (+ goal green)")
    p.add_argument("wave")
    p.add_argument("epic")
    p.add_argument("--goal-green", action="store_true", dest="goal_green",
                   help="Also mark the epic's wave goal green")

    p = sub.add_parser("set-wave-review", help="Set a wave's review status")
    p.add_argument("wave")
    p.add_argument("--status", default="done", choices=["pending", "done"],
                   help="Review status (default: done — the common case)")

    sub.add_parser("validate", help="Validate the state file")

    p = sub.add_parser("commit-state", help="Git add + commit + push the state")
    p.add_argument("--message", required=True)
    p.add_argument("--additional-paths", dest="additional_paths",
                   help="Comma-separated extra paths to stage")
    p.add_argument("--branch", help="Branch to push to (defaults to current)")

    p = sub.add_parser("freeze-add",
                       help="Record a frozen seam / extension hook in the cross-phase freeze ledger")
    p.add_argument("--phase", type=int, required=True)
    p.add_argument("--name", required=True, help="Seam / interface name")
    p.add_argument("--kind", choices=["frozen", "hook"], default="frozen",
                   help="frozen = immutable contract; hook = extension seam left for a later phase")
    p.add_argument("--signature", help="The frozen signature (informational)")
    p.add_argument("--consumers", help="Comma-separated consumer epics/features")
    p.add_argument("--note")

    p = sub.add_parser("freeze-list",
                       help="List frozen seams a later phase must respect")
    p.add_argument("--phase", type=int, help="Only seams frozen at or before phase N")
    p.add_argument("--kind", choices=["frozen", "hook"])
    p.add_argument("--json", action="store_true", dest="as_json", help="(no-op; always JSON)")

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if not args.command:
        parser.print_help()
        return 1
    handler = _HANDLERS.get(args.command)
    if handler is None:  # pragma: no cover — argparse already constrains this
        return _err(f"unknown command {args.command!r}")
    try:
        return handler(args)
    except SquaredSchemaDetected as exc:
        return _err(str(exc))
    except Exception as exc:  # surface clearly, never write torn state
        return _err(f"{type(exc).__name__}: {exc}")
