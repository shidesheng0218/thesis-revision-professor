#!/usr/bin/env python3
"""Generate structured multi-role professor panel review issues."""

from __future__ import annotations

import argparse
from pathlib import Path
from thesis_utils import keyword_hits, read_json, read_text, write_json


ROLE_RULES = [
    {
        "role": "chief_reviewer",
        "dimension": "conclusion_boundary",
        "priority": "P0",
        "markers": ["显著提升", "证明", "导致", "决定性", "significantly improves", "proves"],
        "finding": "结论或贡献表达可能过强，需要核对数据、方法和证据边界。",
        "action": "将强因果/强证明表述改为与材料匹配的限定性结论，或要求作者补充证据。",
    },
    {
        "role": "method_professor",
        "dimension": "method",
        "priority": "P0",
        "markers": ["方法", "模型", "实验", "访谈", "案例", "method"],
        "finding": "方法章节需要证明研究设计能够回答研究问题。",
        "action": "补齐对象、样本、流程、变量/概念、分析步骤、可靠性或局限说明。",
    },
    {
        "role": "literature_professor",
        "dimension": "literature_review",
        "priority": "P1",
        "markers": ["文献综述", "已有研究", "研究现状", "literature"],
        "finding": "文献综述应从罗列资料升级为分类、比较、争议和研究空白。",
        "action": "按主题/方法/时间/观点聚类，比较代表研究，并明确本文切入点。",
    },
    {
        "role": "discipline_professor",
        "dimension": "discipline_fit",
        "priority": "P1",
        "markers": ["理论", "框架", "变量", "模型", "案例", "实验"],
        "finding": "需要检查章节结构和论证方式是否符合学科范式。",
        "action": "按学科 profile 调整理论、方法、结果和讨论的比例。",
    },
    {
        "role": "language_professor",
        "dimension": "language",
        "priority": "P2",
        "markers": ["本文认为", "可以看出", "非常", "巨大", "显然"],
        "finding": "语言需要更学术、克制、精确，避免主观或夸张表达。",
        "action": "压缩冗余表达，统一概念，使用证据绑定的限定语。",
    },
    {
        "role": "blind_review_expert",
        "dimension": "blind_review_risk",
        "priority": "P0",
        "markers": ["缺少", "尚未", "未提供", "需作者确认"],
        "finding": "存在可能触发盲审质疑的证据缺口。",
        "action": "将缺口列入作者确认清单，优先补充材料或降低结论强度。",
    },
]


def issue_id(priority: str, role: str, index: int) -> str:
    return f"{priority}-{role.upper().replace('_', '-')}-{index:03d}"


def load_optional(path: str | None) -> dict | None:
    return read_json(path) if path else None


def build_issues(text: str, structure: dict | None, citations: dict | None, evidence: dict | None, rubric: dict | None) -> list[dict]:
    issues: list[dict] = []
    idx = 1
    for rule in ROLE_RULES:
        hits = keyword_hits(text, rule["markers"])
        should_emit = bool(hits)
        priority = rule["priority"]
        evidence_text = f"检测到标记：{', '.join(hits[:8])}" if hits else "基于整体结构启发式检查。"
        if rule["dimension"] == "method" and not hits:
            should_emit = True
            priority = "P0"
            evidence_text = "未检测到明确方法相关标记。"
        if should_emit:
            issues.append(
                {
                    "id": issue_id(priority, rule["role"], idx),
                    "priority": priority,
                    "role": rule["role"],
                    "dimension": rule["dimension"],
                    "finding": rule["finding"],
                    "evidence": evidence_text,
                    "recommended_action": rule["action"],
                    "evidence_class": "SOURCE_ORIGINAL",
                    "requires_author_confirmation": priority == "P0",
                }
            )
            idx += 1

    if structure and structure.get("risks"):
        for risk in structure["risks"]:
            issues.append(
                {
                    "id": issue_id("P1", "structure_professor", idx),
                    "priority": "P1",
                    "role": "structure_professor",
                    "dimension": "structure",
                    "finding": "章节结构存在风险。",
                    "evidence": risk,
                    "recommended_action": "先修正标题层级和章节闭合，再进入语言润色。",
                    "evidence_class": "SOURCE_ORIGINAL",
                    "requires_author_confirmation": False,
                }
            )
            idx += 1
    if citations and citations.get("risks"):
        for risk in citations["risks"]:
            issues.append(
                {
                    "id": issue_id("P0", "literature_professor", idx),
                    "priority": "P0",
                    "role": "literature_professor",
                    "dimension": "citations",
                    "finding": "引用一致性存在风险。",
                    "evidence": risk,
                    "recommended_action": "先修复文内引用与参考文献对应关系，再进行实质性扩写。",
                    "evidence_class": "SOURCE_REFERENCE",
                    "requires_author_confirmation": True,
                }
            )
            idx += 1
    if evidence and evidence.get("unsupported_claim_count", 0) > 0:
        issues.append(
            {
                "id": issue_id("P0", "chief_reviewer", idx),
                "priority": "P0",
                "role": "chief_reviewer",
                "dimension": "evidence",
                "finding": "存在未绑定依据的实质性判断。",
                "evidence": f"{evidence.get('unsupported_claim_count')} 条疑似缺证据断言。",
                "recommended_action": "将这些句子标记为需作者确认，或补充数据/文献/材料。",
                "evidence_class": "SOURCE_ORIGINAL",
                "requires_author_confirmation": True,
            }
        )
        idx += 1
    if rubric and rubric.get("blind_review_risk") in {"major revision", "high risk"}:
        issues.append(
            {
                "id": issue_id("P0", "blind_review_expert", idx),
                "priority": "P0",
                "role": "blind_review_expert",
                "dimension": "overall_risk",
                "finding": "综合评分显示当前版本存在较高盲审风险。",
                "evidence": f"rubric risk={rubric.get('blind_review_risk')}, average={rubric.get('average')}",
                "recommended_action": "优先处理 P0/P1，而不是直接做语言润色。",
                "evidence_class": "SOURCE_FORMAT_RULE",
                "requires_author_confirmation": False,
            }
        )
    return sorted(issues, key=lambda x: ({"P0": 0, "P1": 1, "P2": 2}.get(x["priority"], 9), x["id"]))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("input")
    parser.add_argument("--structure")
    parser.add_argument("--citations")
    parser.add_argument("--evidence")
    parser.add_argument("--rubric")
    parser.add_argument("--discipline", default="unknown")
    parser.add_argument("--level", choices=["master", "doctoral"], default="master")
    parser.add_argument("--out", required=True)
    args = parser.parse_args()

    text = read_text(args.input)
    issues = build_issues(
        text,
        load_optional(args.structure),
        load_optional(args.citations),
        load_optional(args.evidence),
        load_optional(args.rubric),
    )
    data = {
        "source": str(Path(args.input)),
        "level": args.level,
        "discipline": args.discipline,
        "issues": issues,
        "summary": {
            "p0": sum(1 for i in issues if i["priority"] == "P0"),
            "p1": sum(1 for i in issues if i["priority"] == "P1"),
            "p2": sum(1 for i in issues if i["priority"] == "P2"),
        },
    }
    write_json(data, args.out)


if __name__ == "__main__":
    main()
