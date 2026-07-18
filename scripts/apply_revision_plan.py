#!/usr/bin/env python3
"""Compatibility wrapper for controlled v3 Word revision."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from thesis_revision_professor.workflow import revise_workflow


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("input")
    parser.add_argument("--plan", required=True)
    parser.add_argument("--state")
    parser.add_argument("--clean-changes", action="store_true")
    parser.add_argument("--outdir", required=True)
    args = parser.parse_args()
    result = revise_workflow(
        args.input,
        args.plan,
        args.outdir,
        state_path=args.state,
        tracked=not args.clean_changes,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
