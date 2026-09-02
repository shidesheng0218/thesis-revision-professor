"""Evidence-bound blind-review and defense preparation artifacts."""

from __future__ import annotations

import json
from pathlib import Path

from .docx_report import write_docx


def build_defense_package(review_dir: str | Path, outdir: str | Path) -> dict:
    review_dir = Path(review_dir)
    outdir = Path(outdir)
    outdir.mkdir(parents=True, exist_ok=True)

    def read(name: str, default: dict) -> dict:
        path = review_dir / name
        return json.loads(path.read_text(encoding="utf-8")) if path.exists() else default

    review = read("professor_panel.json", {"issues": []})
    graph = read("claim_evidence_graph.json", {"claims": []})
    issues = review.get("issues", [])
    questions = []
    for index, issue in enumerate(issues, 1):
        questions.append({
            "question_id": f"DEF-{index:04d}",
            "category": _category(issue.get("rule_id", "")),
            "question": _question(issue),
            "locator": issue.get("locator", ""),
            "claim_ids": issue.get("claim_ids", []),
            "evidence_ids": issue.get("evidence_ids", []),
            "answer_boundary": "只能依据论文原文和作者已核验材料回答；没有材料时明确说明尚未核验。",
            "severity": issue.get("priority", "P2"),
        })
    for claim in graph.get("claims", []):
        if claim.get("status") == "unresolved" and len(questions) < 60:
            questions.append({
                "question_id": f"DEF-CLAIM-{claim['claim_id']}",
                "category": "evidence",
                "question": f"请说明“{claim['text']}”由哪一项数据、文献或分析过程支持？",
                "locator": claim.get("locator", ""),
                "claim_ids": [claim.get("claim_id")],
                "evidence_ids": [item.get("evidence_id") for item in claim.get("evidence_links", [])],
                "answer_boundary": "不能现场补造证据；若证据尚未整理，应说明限制并提出补充计划。",
                "severity": claim.get("severity_hint", "P1"),
            })
    payload = {
        "schema_version": "4.0",
        "source_review": str(review_dir),
        "questions": questions,
        "principle": "问题来自可定位风险和未解决主张，不生成论文中不存在的事实。",
    }
    (outdir / "defense_question_bank.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    evidence_map = {
        "schema_version": "4.0",
        "items": [{"question_id": item["question_id"], "locator": item["locator"], "claim_ids": item["claim_ids"], "evidence_ids": item["evidence_ids"]} for item in questions],
    }
    (outdir / "defense_evidence_map.json").write_text(json.dumps(evidence_map, ensure_ascii=False, indent=2), encoding="utf-8")
    lines = ["# 答辩问题库与应答准备", "", "> 下列问题只根据审查中已定位的问题生成；回答必须回到论文和已核验材料。", ""]
    for item in questions:
        lines.extend([f"## {item['question_id']} · {item['category']}", "", item["question"], "", f"- 定位：{item['locator']}", f"- 风险级别：{item['severity']}", f"- 应答边界：{item['answer_boundary']}", ""])
    docx = outdir / "答辩问题库与应答准备.docx"
    write_docx(docx, "答辩问题库与应答准备", "\n".join(lines))
    return {"question_bank": str(outdir / "defense_question_bank.json"), "evidence_map": str(outdir / "defense_evidence_map.json"), "docx": str(docx), "question_count": len(questions)}


def _category(rule_id: str) -> str:
    if "CIT" in rule_id:
        return "citation"
    if "CON" in rule_id or "EVI" in rule_id:
        return "evidence"
    if "PRO" in rule_id or "METHOD" in rule_id:
        return "method"
    if "STR" in rule_id or "PROF" in rule_id:
        return "structure"
    return "blind_review" 


def _question(issue: dict) -> str:
    finding = issue.get("finding", "该问题")
    action = issue.get("recommended_action", "请依据原始材料说明处理方案")
    return f"评审意见指出：{finding}。请说明依据是什么，以及你将如何处理：{action}"
