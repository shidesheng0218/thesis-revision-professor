#!/usr/bin/env python3
"""Export markdown/plain text content to a minimal Word .docx file."""

from __future__ import annotations

import argparse
from pathlib import Path
from thesis_utils import simple_docx


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--title", required=True)
    parser.add_argument("--body", required=True, help="Markdown/text file or literal body text")
    parser.add_argument("--out", required=True)
    args = parser.parse_args()

    body_path = Path(args.body)
    body = body_path.read_text(encoding="utf-8") if body_path.exists() else args.body
    simple_docx(args.out, args.title, body)


if __name__ == "__main__":
    main()
