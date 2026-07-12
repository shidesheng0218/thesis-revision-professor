#!/usr/bin/env python3
"""Build a staged revision_plan.json from loop outputs."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
from pathlib import Path
from thesis_utils import read_json, write_json


def action_for_issue(issue: dict) -> str:
    dim = issue.get("dimension", "")
    if dim in {"evidence", "conclusion_boundary", "overall_risk"}:
        return "mark_and_request"
    if dim == "literature_review":
        return "cluster_compare_gap"
    if dim == "method":
        return "method_completion_request"
    if dim == "language":
        return "academicize_and_compress"
    if dim == "citations":
        return "citation_repair_request"
    return "restructure_or_clarify"


def proposed_rewrite(issue: dict, target_text: str | None = None) -> str:
    action = action_for_issue(issue)
    if action == "mark_and_request":
        base = target_text or issue.get("finding", "")
        return f"{base} [需作者确认：该判断需要补充数据、文献或材料依据]"
    if action == "academicize_and_compress":
        return "将主观、夸张或口语化表达改为克制、证据绑定的学术表达。"
    if action == "cluster_compare_gap":
        return "按主题/方法/观点分类已有研究，比较差异，最后明确本文研究空白。"
    if action == "method_completion_request":
        return "补充研究对象、数据来源、样本/材料、分析流程、可靠性与局限说明。"
    if action == "citation_repair_request":
        return "核对文内引用与参考文献表，补齐缺失条目或删除未引用条目。"
    return issue.get("recommended_action", "调整结构并增强论证连接。")


def build_items(source: str, panel: dict, evidence: dict) -> list[dict]:
    items = []
    idx = 1
    claims = evidence.get("claims", []) if isinstance(evidence, dict) else []
    unsupported = [c for c in claims if c.get("risk") == "needs_evidence"][:20]
    for claim in unsupported:
        item_id = f"P0-EVIDENCE-{idx:03d}"
        items.append(
            {
                "id": item_id,
                "confirmed": False,
                "location_hint": f"句子序号 {claim.get('index')}",
                "target_text": claim.get("text", ""),
                "problem": "疑似缺少证据支撑的实质性判断",
                "action": "mark_and_request",
                "evidence_class": "SOURCE_ORIGINAL",
                "requires_author_confirmation": True,
                "proposed_rewrite": proposed_rewrite({"dimension": "evidence", "finding": "缺少证据"}, claim.get("text", "")),
                "risk": "不得将未验证判断写成确定性结论",
            }
        )
        idx += 1
    for issue in panel.get("issues", []):
        item_id = issue.get("id", f"{issue.get('priority', 'P2')}-ISSUE-{idx:03d}")
        action = action_for_issue(issue)
        requires_confirmation = bool(issue.get("requires_author_confirmation")) or issue.get("priority") == "P0"
        items.append(
            {
                "id": item_id,
                "confirmed": not requires_confirmation and issue.get("priority") == "P2",
                "location_hint": issue.get("dimension", "unknown"),
                "target_text": "",
                "problem": issue.get("finding", ""),
                "action": action,
                "evidence_class": issue.get("evidence_class", "SOURCE_ORIGINAL"),
                "requires_author_confirmation": requires_confirmation,
                "proposed_rewrite": proposed_rewrite(issue),
                "risk": issue.get("recommended_action", "需按证据边界修改"),
            }
        )
        idx += 1
    return items


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", required=True)
    parser.add_argument("--panel", required=True)
    parser.add_argument("--evidence", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()

    panel = read_json(args.panel)
    evidence = read_json(args.evidence)
    plan = {
        "plan_id": f"revision-plan-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "mode": "staged_confirmation",
        "source": args.source,
        "items": build_items(args.source, panel, evidence),
        "note": "Only confirmed items are applied. Unconfirmed P0 evidence gaps are marked for author confirmation.",
    }
    write_json(plan, args.out)


if __name__ == "__main__":
    main()
