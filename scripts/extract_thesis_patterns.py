#!/usr/bin/env python3
"""Extract non-verbatim structural patterns from an indexed corpus."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from thesis_utils import citation_patterns, read_text, write_json


KEYWORDS = {
    "abstract": ["摘要", "abstract"],
    "introduction": ["引言", "绪论", "introduction"],
    "literature_review": ["文献综述", "已有研究", "literature"],
    "method": ["方法", "模型", "实验", "method"],
    "results": ["结果", "分析", "result"],
    "conclusion": ["结论", "conclusion"],
    "references": ["参考文献", "references"],
}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("corpus_index")
    parser.add_argument("--out", required=True)
    args = parser.parse_args()

    index = json.loads(Path(args.corpus_index).read_text(encoding="utf-8"))
    aggregate = {k: 0 for k in KEYWORDS}
    citation_counts = []
    docs = []
    for entry in index.get("entries", []):
        text = read_text(entry["path"])
        present = []
        for key, markers in KEYWORDS.items():
            if any(m.lower() in text.lower() for m in markers):
                aggregate[key] += 1
                present.append(key)
        citation_counts.append(len(citation_patterns(text)))
        docs.append({"id": entry["id"], "sections_detected": present, "citation_count": citation_counts[-1]})
    data = {
        "document_count": len(docs),
        "section_frequency": aggregate,
        "average_citation_markers": round(sum(citation_counts) / len(citation_counts), 2) if citation_counts else 0,
        "documents": docs,
        "copyright_safe_note": "Only aggregate structural features are stored; no source paragraphs are retained.",
    }
    write_json(data, args.out)


if __name__ == "__main__":
    main()
