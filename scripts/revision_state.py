#!/usr/bin/env python3
"""Create and update revision loop state."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
from pathlib import Path
from thesis_utils import read_json, write_json


def initial_state() -> dict:
    return {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "round": 0,
        "status": "initialized",
        "phase": "baseline_scan",
        "baseline": {},
        "scores": [],
        "p0": [],
        "p1": [],
        "p2": [],
        "resolved": [],
        "new_risks": [],
        "evidence_gaps": [],
        "confirmation_queue": [],
        "strategy_matches": [],
        "deliverables": [],
        "convergence": {
            "p0_clear": False,
            "p1_acceptable": False,
            "risk_minor_or_pass": False,
            "evidence_gaps_marked": False,
            "word_deliverables_generated": False,
        },
        "user_preferences": {"confirmation_mode": "staged", "rewrite_scope": "confirmed_only"},
        "history": [],
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    init = sub.add_parser("init")
    init.add_argument("--out", required=True)
    add = sub.add_parser("add-round")
    add.add_argument("state")
    add.add_argument("--summary", required=True)
    add.add_argument("--round-json")
    add.add_argument("--out", required=True)
    args = parser.parse_args()

    if args.command == "init":
        write_json(initial_state(), args.out)
        return
    state = read_json(args.state)
    state["round"] = int(state.get("round", 0)) + 1
    event = {
        "round": state["round"],
        "summary": args.summary,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    if args.round_json:
        payload = read_json(args.round_json)
        event["payload"] = payload
        state["scores"].append(payload.get("rubric_score", {}))
        for issue in payload.get("professor_panel", {}).get("issues", []):
            bucket = issue.get("priority", "P2").lower()
            if bucket in {"p0", "p1", "p2"}:
                state[bucket].append(issue)
        state["evidence_gaps"].extend(payload.get("evidence_audit", {}).get("claims", []))
        state["deliverables"].extend(payload.get("deliverables", []))
        state["phase"] = payload.get("next_phase", "revision_plan")
        state["convergence"] = payload.get("convergence", state["convergence"])
    else:
        state["phase"] = "revision_plan"
    state["history"].append(event)
    state["status"] = "in_progress"
    write_json(state, args.out)


if __name__ == "__main__":
    main()
