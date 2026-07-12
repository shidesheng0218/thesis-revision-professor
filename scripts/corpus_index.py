#!/usr/bin/env python3
"""Index a local, legally available thesis corpus without copying source files."""

from __future__ import annotations

import argparse
import hashlib
from pathlib import Path
from thesis_utils import read_docx_paragraphs, write_json


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("corpus_dir")
    parser.add_argument("--out", required=True)
    args = parser.parse_args()

    root = Path(args.corpus_dir)
    entries = []
    for path in sorted(root.rglob("*")):
        if path.suffix.lower() not in {".docx", ".txt", ".md"}:
            continue
        digest = hashlib.sha256(str(path.resolve()).encode("utf-8")).hexdigest()[:16]
        if path.suffix.lower() == ".docx":
            paragraphs = read_docx_paragraphs(path)
            paragraph_count = len(paragraphs)
            title = next((p.text for p in paragraphs if p.text), path.stem)
        else:
            text = path.read_text(encoding="utf-8", errors="ignore")
            paragraph_count = len([p for p in text.splitlines() if p.strip()])
            title = text.splitlines()[0].strip() if text.splitlines() else path.stem
        entries.append(
            {
                "id": digest,
                "path": str(path),
                "title_hint": title[:120],
                "suffix": path.suffix.lower(),
                "paragraph_count": paragraph_count,
                "license_status": "user_provided_local_file_requires_user_authorization",
            }
        )
    write_json({"corpus_dir": str(root), "entry_count": len(entries), "entries": entries}, args.out)


if __name__ == "__main__":
    main()
