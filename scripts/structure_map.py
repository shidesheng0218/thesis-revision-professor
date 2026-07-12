#!/usr/bin/env python3
"""Build a simple thesis chapter/heading structure map."""

from __future__ import annotations

import argparse
from pathlib import Path
from thesis_utils import read_docx_paragraphs, write_json


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("input", help=".docx file")
    parser.add_argument("--out", required=True)
    args = parser.parse_args()

    paragraphs = read_docx_paragraphs(args.input)
    headings = [
        {"index": p.index, "level": p.level, "text": p.text}
        for p in paragraphs
        if p.level is not None
    ]
    first_level = [h for h in headings if h["level"] == 1]
    data = {
        "source": str(Path(args.input)),
        "paragraph_count": len(paragraphs),
        "heading_count": len(headings),
        "chapter_count": len(first_level),
        "headings": headings,
        "risks": [],
    }
    if not first_level:
        data["risks"].append("未识别到一级章节标题，可能存在标题样式或章节结构问题。")
    if len(first_level) < 4:
        data["risks"].append("一级章节数量偏少，需确认是否包含摘要、引言、方法、结果/分析、结论等必要部分。")
    write_json(data, args.out)


if __name__ == "__main__":
    main()
