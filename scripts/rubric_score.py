#!/usr/bin/env python3
"""Produce a heuristic thesis risk score for triage."""

from __future__ import annotations

import argparse
from thesis_utils import citation_patterns, read_text, write_json


DIMENSIONS = [
    "topic_value",
    "research_question",
    "literature_review",
    "method",
    "data_materials",
    "analysis",
    "findings",
    "innovation",
    "language",
    "format",
    "citations",
]


def score_dimension(text: str, dim: str) -> int:
    lower = text.lower()
    checks = {
        "research_question": ["研究问题", "research question", "本文旨在", "本文试图"],
        "literature_review": ["文献综述", "已有研究", "literature"],
        "method": ["方法", "模型", "实验", "访谈", "案例", "method"],
        "data_materials": ["数据", "样本", "材料", "dataset", "sample"],
        "analysis": ["分析", "结果", "检验", "analysis", "result"],
        "findings": ["发现", "结论", "finding", "conclusion"],
        "innovation": ["创新", "贡献", "contribution"],
        "format": ["摘要", "关键词", "参考文献"],
    }
    if dim == "citations":
        return min(5, max(1, len(citation_patterns(text)) // 3))
    if dim == "language":
        return 3 if len(text) > 1000 else 2
    if dim == "topic_value":
        return 3 if len(text) > 500 else 2
    hits = sum(1 for marker in checks.get(dim, []) if marker in lower or marker in text)
    return min(5, 1 + hits * 2)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("input")
    parser.add_argument("--level", choices=["master", "doctoral"], default="master")
    parser.add_argument("--out", required=True)
    args = parser.parse_args()

    text = read_text(args.input)
    scores = {dim: score_dimension(text, dim) for dim in DIMENSIONS}
    avg = sum(scores.values()) / len(scores)
    p0 = [dim for dim, score in scores.items() if score <= 1]
    p1 = [dim for dim, score in scores.items() if score == 2]
    risk = "pass"
    if p0 or avg < 2.5:
        risk = "high risk"
    elif len(p1) >= 4 or avg < 3.2:
        risk = "major revision"
    elif p1 or avg < 4.0:
        risk = "minor revision"
    data = {
        "level": args.level,
        "scores": scores,
        "average": round(avg, 2),
        "p0_dimensions": p0,
        "p1_dimensions": p1,
        "blind_review_risk": risk,
        "note": "Heuristic triage only; professor-style review must verify against the thesis and rubric.",
    }
    write_json(data, args.out)


if __name__ == "__main__":
    main()
