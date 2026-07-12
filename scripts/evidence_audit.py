#!/usr/bin/env python3
"""Flag substantive claims that appear to need evidence."""

from __future__ import annotations

import argparse
from thesis_utils import citation_patterns, looks_like_claim, read_text, split_sentences, write_json


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("input", help=".docx, .txt, .md, or extracted JSON")
    parser.add_argument("--out", required=True)
    args = parser.parse_args()

    sentences = split_sentences(read_text(args.input))
    claims = []
    for i, sentence in enumerate(sentences):
        if looks_like_claim(sentence):
            cites = citation_patterns(sentence)
            claims.append(
                {
                    "index": i,
                    "text": sentence,
                    "citation_count": len(cites),
                    "risk": "needs_evidence" if not cites else "has_citation_marker",
                }
            )
    data = {
        "claim_count": len(claims),
        "unsupported_claim_count": sum(1 for c in claims if c["risk"] == "needs_evidence"),
        "claims": claims[:200],
        "instruction": "人工复核这些句子；没有引用标记不必然错误，但重要事实、因果、发现、政策判断必须有依据。",
    }
    write_json(data, args.out)


if __name__ == "__main__":
    main()
