#!/usr/bin/env python3
"""Run the v3 body/reference-separated citation consistency audit."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from thesis_revision_professor.audits import citation_audit
from thesis_revision_professor.document_model import load_document


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("input")
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    Path(args.out).write_text(
        json.dumps(citation_audit(load_document(args.input)), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
