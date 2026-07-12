#!/usr/bin/env python3
"""Audit risky changes between an original and revised thesis draft."""

from __future__ import annotations

import argparse
from thesis_utils import citation_patterns, extract_numbers, extract_years, read_text, split_sentences, write_json


def missing_items(before: list[str], after: list[str]) -> list[str]:
    after_set = set(after)
    return sorted({item for item in before if item not in after_set})


def added_items(before: list[str], after: list[str]) -> list[str]:
    before_set = set(before)
    return sorted({item for item in after if item not in before_set})


def new_claim_like_sentences(before_text: str, after_text: str) -> list[str]:
    before_sent = set(split_sentences(before_text))
    markers = ["表明", "证明", "导致", "显著", "促进", "shows", "proves", "significant", "causes"]
    out = []
    for sent in split_sentences(after_text):
        if sent in before_sent:
            continue
        if any(m in sent for m in markers):
            out.append(sent)
    return out[:100]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("original")
    parser.add_argument("revised")
    parser.add_argument("--out", required=True)
    args = parser.parse_args()

    before = read_text(args.original)
    after = read_text(args.revised)
    before_numbers = extract_numbers(before)
    after_numbers = extract_numbers(after)
    before_cites = citation_patterns(before)
    after_cites = citation_patterns(after)
    before_years = extract_years(before)
    after_years = extract_years(after)
    new_claims = new_claim_like_sentences(before, after)
    risks = []
    if missing_items(before_numbers, after_numbers) or added_items(before_numbers, after_numbers):
        risks.append("数字、比例、样本量或年份类信息发生变化，需作者确认。")
    if missing_items(before_cites, after_cites) or added_items(before_cites, after_cites):
        risks.append("引用标记发生变化，需检查参考文献一致性。")
    if new_claims:
        risks.append("修改稿新增强断言，需核对证据。")
    data = {
        "number_removed": missing_items(before_numbers, after_numbers),
        "number_added": added_items(before_numbers, after_numbers),
        "year_removed": missing_items(before_years, after_years),
        "year_added": added_items(before_years, after_years),
        "citation_removed": missing_items(before_cites, after_cites),
        "citation_added": added_items(before_cites, after_cites),
        "new_claim_like_sentences": new_claims,
        "risks": risks,
        "regression_result": "needs_author_review" if risks else "no_obvious_regression",
    }
    write_json(data, args.out)


if __name__ == "__main__":
    main()
