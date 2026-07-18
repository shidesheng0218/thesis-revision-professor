#!/usr/bin/env python3
"""Compatibility wrapper for the v3 review workflow."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from thesis_revision_professor.workflow import review_workflow


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("input")
    parser.add_argument("--level", choices=["master", "doctoral"], default="master")
    parser.add_argument("--discipline", default="unknown")
    parser.add_argument("--method", default="unknown")
    parser.add_argument("--stage", default="blind-review")
    parser.add_argument("--semantic-findings")
    parser.add_argument("--state")
    parser.add_argument("--revised", help="Deprecated: run revise separately so regression can gate the output")
    parser.add_argument("--outdir", required=True)
    args = parser.parse_args()
    result = review_workflow(
        args.input,
        args.outdir,
        level=args.level,
        discipline=args.discipline,
        method=args.method,
        stage=args.stage,
        semantic_findings=args.semantic_findings,
        state_path=args.state,
    )
    if args.revised:
        result["warning"] = "--revised is deprecated; use revise with the generated plan and state."
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
