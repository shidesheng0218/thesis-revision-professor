#!/usr/bin/env python3
"""Run the v3 typed claim-evidence audit."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from thesis_revision_professor.claim_evidence import build_claim_graph
from thesis_revision_professor.document_model import load_document


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("input")
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    graph = build_claim_graph(load_document(args.input))
    graph["unsupported_claim_count"] = graph["unresolved_count"]
    Path(args.out).write_text(json.dumps(graph, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
