#!/usr/bin/env python3
"""Produce a heuristic thesis risk score for triage."""

from __future__ import annotations

import argparse
from pathlib import Path
from thesis_utils import citation_patterns, keyword_hits, read_json, read_text, write_json


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


def default_rubric_path(level: str) -> Path:
    root = Path(__file__).resolve().parents[1]
    return root / "references" / "rubrics" / ("doctoral-cn.json" if level == "doctoral" else "master-cn.json")


def score_with_config(text: str, rubric: dict) -> dict:
    dimensions = rubric.get("dimensions", [])
    scores = {}
    issues = []
    total = 0.0
    weight_sum = 0.0
    for dim in dimensions:
        key = dim["key"]
        weight = float(dim.get("weight", 1))
        markers = dim.get("positive_markers", [])
        p0 = keyword_hits(text, dim.get("p0_markers", []))
        p1 = keyword_hits(text, dim.get("p1_markers", []))
        hits = keyword_hits(text, markers)
        score = min(5, max(1, 1 + len(hits) * 2))
        if p0:
            score = min(score, 1)
            issues.append({"priority": "P0", "dimension": key, "markers": p0, "action": dim.get("recommended_action", "")})
        elif p1:
            score = min(score, 2)
            issues.append({"priority": "P1", "dimension": key, "markers": p1, "action": dim.get("recommended_action", "")})
        scores[key] = score
        total += score * weight
        weight_sum += weight
    avg = total / weight_sum if weight_sum else 0
    p0_count = sum(1 for i in issues if i["priority"] == "P0")
    p1_count = sum(1 for i in issues if i["priority"] == "P1")
    risk = "pass"
    if p0_count or avg < 2.5:
        risk = "high risk"
    elif p1_count >= 3 or avg < 3.2:
        risk = "major revision"
    elif p1_count or avg < 4:
        risk = "minor revision"
    return {
        "rubric": rubric.get("name", "custom"),
        "scores": scores,
        "weighted_average": round(avg, 2),
        "average": round(avg, 2),
        "issues": issues,
        "p0_dimensions": [i["dimension"] for i in issues if i["priority"] == "P0"],
        "p1_dimensions": [i["dimension"] for i in issues if i["priority"] == "P1"],
        "blind_review_risk": risk,
        "note": "Configurable heuristic triage; professor review must verify evidence.",
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("input")
    parser.add_argument("--level", choices=["master", "doctoral"], default="master")
    parser.add_argument("--rubric", help="Optional rubric JSON path")
    parser.add_argument("--out", required=True)
    args = parser.parse_args()

    text = read_text(args.input)
    rubric_path = Path(args.rubric) if args.rubric else default_rubric_path(args.level)
    if rubric_path.exists():
        data = score_with_config(text, read_json(rubric_path))
        data["level"] = args.level
        data["rubric_path"] = str(rubric_path)
        write_json(data, args.out)
        return
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
