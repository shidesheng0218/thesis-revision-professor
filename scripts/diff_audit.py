#!/usr/bin/env python3
"""Run the v3 fact and DOCX-package regression audit."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from thesis_revision_professor.audits import regression_audit
from thesis_revision_professor.document_model import load_document


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("original")
    parser.add_argument("revised")
    parser.add_argument("--allowed-changes", help="Optional JSON with numbers/years/citations arrays")
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    allowed = json.loads(Path(args.allowed_changes).read_text(encoding="utf-8")) if args.allowed_changes else None
    payload = regression_audit(load_document(args.original), load_document(args.revised), allowed)
    Path(args.out).write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
