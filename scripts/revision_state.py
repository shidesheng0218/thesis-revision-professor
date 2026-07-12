#!/usr/bin/env python3
"""Create and update revision loop state."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from thesis_utils import write_json


def initial_state() -> dict:
    return {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "round": 0,
        "status": "initialized",
        "p0": [],
        "p1": [],
        "p2": [],
        "resolved": [],
        "evidence_gaps": [],
        "user_preferences": {"confirmation_mode": "staged"},
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
    add.add_argument("--out", required=True)
    args = parser.parse_args()

    if args.command == "init":
        write_json(initial_state(), args.out)
        return
    state = json.loads(Path(args.state).read_text(encoding="utf-8"))
    state["round"] = int(state.get("round", 0)) + 1
    state["history"].append({"round": state["round"], "summary": args.summary})
    state["status"] = "in_progress"
    write_json(state, args.out)


if __name__ == "__main__":
    main()
