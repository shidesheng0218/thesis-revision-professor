#!/usr/bin/env python3
"""Generate markdown strategy cards from aggregate corpus patterns."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("patterns_json")
    parser.add_argument("--out", required=True)
    args = parser.parse_args()

    patterns = json.loads(Path(args.patterns_json).read_text(encoding="utf-8"))
    freq = patterns.get("section_frequency", {})
    doc_count = max(patterns.get("document_count", 0), 1)
    lines = [
        "# Generated strategy cards",
        "",
        "These cards are derived from aggregate structural features only. They do not contain source thesis text.",
        "",
        f"Corpus documents: {patterns.get('document_count', 0)}",
        f"Average citation markers: {patterns.get('average_citation_markers', 0)}",
        "",
    ]
    for section, count in sorted(freq.items()):
        rate = count / doc_count
        lines.extend(
            [
                f"## {section.replace('_', ' ').title()}",
                "",
                f"Observed in {count}/{patterns.get('document_count', 0)} documents.",
                "",
                "- Use this as a structure signal, not as factual evidence.",
                "- Verify against the user's discipline and school requirements.",
                "",
            ]
        )
        if rate < 0.5:
            lines.append("- Treat absence/presence carefully; corpus coverage may be limited.\n")
    Path(args.out).write_text("\n".join(lines), encoding="utf-8")


if __name__ == "__main__":
    main()
