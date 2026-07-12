#!/usr/bin/env python3
"""Build markdown and Word reports from loop JSON outputs."""

from __future__ import annotations

import argparse
from pathlib import Path
from thesis_utils import markdown_table, read_json, simple_docx


def load(path: Path, default: object) -> object:
    return read_json(path) if path.exists() else default


def build_markdown(loop_dir: Path, title: str) -> str:
    structure = load(loop_dir / "structure.json", {})
    citations = load(loop_dir / "citation_audit.json", {})
    evidence = load(loop_dir / "evidence_audit.json", {})
    rubric = load(loop_dir / "rubric_score.json", {})
    panel = load(loop_dir / "professor_panel.json", {"issues": [], "summary": {}})
    plan = load(loop_dir / "revision_plan.json", {"items": []})
    diff = load(loop_dir / "diff_audit.json", {})
    issues = panel.get("issues", []) if isinstance(panel, dict) else []
    rows = [
        [
            i.get("id", ""),
            i.get("priority", ""),
            i.get("role", ""),
            i.get("dimension", ""),
            i.get("finding", ""),
            i.get("recommended_action", ""),
            "是" if i.get("requires_author_confirmation") else "否",
        ]
        for i in issues
    ]
    md = [
        f"# {title}",
        "",
        "## 总体判断",
        "",
        f"- 盲审风险：{rubric.get('blind_review_risk', 'unknown') if isinstance(rubric, dict) else 'unknown'}",
        f"- Rubric 平均分：{rubric.get('average', 'unknown') if isinstance(rubric, dict) else 'unknown'}",
        f"- 章节数：{structure.get('chapter_count', 'unknown') if isinstance(structure, dict) else 'unknown'}",
        f"- 引用标记数：{citations.get('citation_count', 'unknown') if isinstance(citations, dict) else 'unknown'}",
        f"- 疑似缺证据断言：{evidence.get('unsupported_claim_count', 'unknown') if isinstance(evidence, dict) else 'unknown'}",
        "",
        "## P0/P1/P2 问题清单",
        "",
        markdown_table(["ID", "优先级", "角色", "维度", "问题", "建议动作", "需确认"], rows) if rows else "暂无结构化问题。",
        "",
        "## 证据不足清单",
        "",
    ]
    md.extend(["", "## 修改计划摘要", ""])
    plan_items = plan.get("items", []) if isinstance(plan, dict) else []
    if plan_items:
        md.append(markdown_table(["ID", "动作", "需确认", "问题", "拟处理"], [[i.get("id", ""), i.get("action", ""), "是" if i.get("requires_author_confirmation") else "否", i.get("problem", ""), i.get("proposed_rewrite", "")] for i in plan_items[:30]]))
    else:
        md.append("尚未生成 revision_plan.json。")
    md.extend(["", "## 证据不足清单", ""])
    claims = evidence.get("claims", []) if isinstance(evidence, dict) else []
    unsupported = [c for c in claims if c.get("risk") == "needs_evidence"][:20]
    if unsupported:
        md.append(markdown_table(["句子序号", "内容", "处理"], [[c["index"], c["text"], "[需作者确认：缺少支撑材料]"] for c in unsupported]))
    else:
        md.append("未检测到明显缺证据断言。")
    md.extend(["", "## 回归审计", ""])
    if diff:
        md.extend(
            [
                f"- 结果：{diff.get('regression_result')}",
                f"- 风险：{'; '.join(diff.get('risks', [])) if diff.get('risks') else '未检测到明显回归风险'}",
            ]
        )
    else:
        md.append("未提供修改稿，跳过 diff 回归审计。")
    md.extend(
        [
            "",
            "## 下一轮建议",
            "",
            "1. 先处理 P0 问题和证据不足项。",
            "2. 经作者确认后再进入 Controlled Rewrite。",
            "3. 修改后运行 Regression Review，确认未改变事实、数字、引用和结论边界。",
        ]
    )
    return "\n".join(md)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("loop_dir")
    parser.add_argument("--title", default="修改说明与盲审风险报告")
    parser.add_argument("--markdown-out", required=True)
    parser.add_argument("--docx-out", required=True)
    args = parser.parse_args()

    md = build_markdown(Path(args.loop_dir), args.title)
    Path(args.markdown_out).write_text(md, encoding="utf-8")
    simple_docx(args.docx_out, args.title, md)


if __name__ == "__main__":
    main()
