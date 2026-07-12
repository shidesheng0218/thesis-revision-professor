#!/usr/bin/env python3
"""Extract paragraphs and heading metadata from a .docx file."""

from __future__ import annotations

import argparse
from pathlib import Path
from thesis_utils import paragraphs_to_json, read_docx_paragraphs, write_json


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("input", help="Input .docx file")
    parser.add_argument("--out", required=True, help="Output JSON path")
    args = parser.parse_args()
    paragraphs = read_docx_paragraphs(args.input)
    data = paragraphs_to_json(paragraphs)
    data["source"] = str(Path(args.input))
    write_json(data, args.out)


if __name__ == "__main__":
    main()
