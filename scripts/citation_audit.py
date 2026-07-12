#!/usr/bin/env python3
"""Audit simple in-text citation and reference consistency."""

from __future__ import annotations

import argparse
import re
from thesis_utils import citation_patterns, read_text, write_json


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("input", help=".docx, .txt, .md, or extracted JSON")
    parser.add_argument("--out", required=True)
    args = parser.parse_args()

    text = read_text(args.input)
    citations = citation_patterns(text)
    refs_start = max(text.rfind("参考文献"), text.lower().rfind("references"))
    references_text = text[refs_start:] if refs_start >= 0 else ""
    numbered_refs = re.findall(r"^\s*\[?(\d+)\]?", references_text, flags=re.M)
    cited_numbers = set()
    for cite in citations:
        for n in re.findall(r"\d+", cite):
            cited_numbers.add(n)
    reference_numbers = set(numbered_refs)
    data = {
        "citation_count": len(citations),
        "reference_count": len(reference_numbers),
        "citations_sample": citations[:50],
        "missing_reference_entries": sorted(cited_numbers - reference_numbers, key=lambda x: int(x) if x.isdigit() else x),
        "uncited_reference_entries": sorted(reference_numbers - cited_numbers, key=lambda x: int(x) if x.isdigit() else x),
        "risks": [],
    }
    if citations and not reference_numbers:
        data["risks"].append("检测到文内引用，但未识别到参考文献表。")
    if data["missing_reference_entries"]:
        data["risks"].append("存在文内引用编号未在参考文献表中出现。")
    if data["uncited_reference_entries"]:
        data["risks"].append("存在参考文献条目未被文内引用。")
    write_json(data, args.out)


if __name__ == "__main__":
    main()
