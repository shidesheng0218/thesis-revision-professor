"""Machine-generated AI-assisted-content disclosure for thesis revision rounds."""

from __future__ import annotations

import json
from pathlib import Path

from .docx_report import write_docx


ARTIFACTS = ("revision_state.json", "loop_trace.json", "revision_plan.json", "professor_panel.json", "semantic_rejections.json")


def _read(path: Path) -> object | None:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError):
        return None


def build_disclosure_package(review_dir: str | Path, outdir: str | Path) -> dict:
    """Summarize what the tool did into a《AI 辅助内容清单》.

    Only facts already present in machine artifacts are reported; anything
    missing is stated as missing instead of being reconstructed.
    """
    review_dir = Path(review_dir)
    outdir = Path(outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    state = _read(review_dir / "revision_state.json")
    trace = _read(review_dir / "loop_trace.json")
    plan = _read(review_dir / "revision_plan.json")
    panel = _read(review_dir / "professor_panel.json")
    rejections = _read(review_dir / "semantic_rejections.json")
    state = state if isinstance(state, dict) else None
    trace = trace if isinstance(trace, dict) else None
    plan = plan if isinstance(plan, dict) else None
    panel = panel if isinstance(panel, dict) else None

    missing = [
        name
        for name, payload in (
            ("revision_state.json", state),
            ("loop_trace.json", trace),
            ("revision_plan.json", plan),
            ("professor_panel.json", panel),
            ("semantic_rejections.json", rejections),
        )
        if payload is None
    ]

    rounds = state.get("history", []) if state else []
    roles = sorted({str(issue.get("role", issue.get("reviewer", "unknown"))) for issue in (panel or {}).get("issues", [])})
    stages = trace.get("stages", []) if trace else []
    strategy = (state.get("strategy_matches") or [{}])[-1] if state else {}
    items = (plan or {}).get("items", [])
    pending = [item for item in items if item.get("requires_author_confirmation") and not item.get("confirmed")]
    if isinstance(rejections, list):
        rejected_findings = rejections
    elif isinstance(rejections, dict):
        rejected_findings = rejections.get("rejected_findings", rejections.get("rejected", []))
    else:
        rejected_findings = []

    lines = [
        "# AI 辅助内容清单",
        "",
        "> 本清单由 thesis-revision-professor 依据审查产物自动生成，只汇总机器记录中已有的事实，不评价论文内容本身，也不新增未报告的信息。",
        "",
        "## 审查过程",
        "",
        f"- 已记录审查轮次：{len(rounds)}",
    ]
    for entry in rounds:
        lines.append(f"- 第 {entry.get('round')} 轮：阶段 {entry.get('phase')}，新增风险 {entry.get('new_risk_count')}，解决 {entry.get('resolved_count')}")
    if trace:
        lines.append(f"- 深度审查计划：最多 {trace.get('max_rounds')} 轮，当前状态 {trace.get('status')}")
        for stage in stages:
            lines.append(f"  - {stage.get('name')}：{stage.get('status')}")
    else:
        lines.append("- 深度审查计划：无该产物（未运行 deep-review）。")
    if strategy:
        discipline = strategy.get("discipline", {})
        method = strategy.get("method", {})
        lines.append(f"- 选用协议：学科 {discipline.get('key', 'unknown')}，方法 {method.get('key', 'unknown')}")
    if roles:
        lines.append(f"- 参与审查角色：{', '.join(roles)}")
    lines.extend(["", "## 修改计划项", ""])
    if items:
        lines.append("| ID | 执行方式 | 证据来源 | 作者确认 | 定位 |")
        lines.append("| --- | --- | --- | --- | --- |")
        for item in items:
            confirmed = "已确认" if item.get("confirmed") else ("待确认" if item.get("requires_author_confirmation") else "不涉及")
            lines.append(
                "| " + " | ".join(
                    [
                        str(item.get("id", "")),
                        str(item.get("patch_mode", "")),
                        str(item.get("evidence_class", "")),
                        confirmed,
                        str(item.get("locator", "")).replace("|", "\\|"),
                    ]
                ) + " |"
            )
    else:
        lines.append("无修改计划产物。")
    lines.extend(["", "## 待作者确认项", ""])
    if pending:
        for item in pending:
            lines.append(f"- {item.get('id', '')}：{item.get('problem', '')}（定位：{item.get('locator', '')}）")
    else:
        lines.append("无待确认项。")
    lines.extend(["", "## 未采纳的语义审查意见", ""])
    if rejected_findings:
        for entry in rejected_findings:
            finding = entry.get("finding", {})
            label = finding.get("rule_id", f"第 {entry.get('index', '?')} 条") if isinstance(finding, dict) else str(finding)
            lines.append(f"- {label}：{'; '.join(entry.get('reasons', []))}")
    else:
        lines.append("无被拒收的语义审查 finding。")
    lines.extend(["", "## 产物完整性", ""])
    for name in ARTIFACTS:
        lines.append(f"- {name}：{'正常' if name not in missing else '缺失（清单相应内容已降级说明）'}")
    body = "\n".join(lines)

    md_path = outdir / "AI辅助内容清单.md"
    md_path.write_text(body, encoding="utf-8")
    docx_path = outdir / "AI辅助内容清单.docx"
    write_docx(docx_path, "AI 辅助内容清单", body)
    payload = {
        "schema_version": "4.0",
        "source_review": str(review_dir),
        "rounds_recorded": len(rounds),
        "plan_items": len(items),
        "pending_confirmation": len(pending),
        "rejected_findings": len(rejected_findings),
        "missing_artifacts": missing,
        "principle": "清单仅汇总机器产物中已有的事实；缺失产物如实注明，不补造内容。",
    }
    (outdir / "AI辅助内容清单.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"markdown": str(md_path), "docx": str(docx_path), "payload": str(outdir / "AI辅助内容清单.json"), "plan_items": len(items), "pending_confirmation": len(pending)}
