"""V3 review and revise workflows used by both CLI and compatibility scripts."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

from .audits import citation_audit, regression_audit, structure_audit
from .claim_evidence import build_claim_graph
from .corpus import derive_patterns, read_manifest, strategy_cards
from .document_model import ThesisDocument, load_document
from .docx_patch import patch_docx
from .docx_report import write_docx
from .review_engine import (
    build_findings,
    build_review,
    merge_semantic_findings,
    semantic_review_request,
    validate_semantic_payload,
)
from .state_machine import advance_state
from .strategy_engine import select_strategy


def write_json(path: str | Path, payload: object) -> None:
    Path(path).write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def read_json(path: str | Path) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _rubric(claim_graph: dict, strategy: dict, citations: dict, structure: dict) -> dict:
    claims = claim_graph.get("claims", [])
    unresolved = claim_graph.get("unresolved_count", 0)
    evidence_score = 5.0 if not claims else max(1.0, 5.0 - 4.0 * unresolved / len(claims))
    coverage = strategy["discipline"].get("coverage", []) + strategy["method"].get("coverage", [])
    present = sum(item["status"] == "present_marker" for item in coverage)
    protocol_score = 3.0 if not coverage else 1.0 + 4.0 * present / len(coverage)
    citation_score = max(1.0, 5.0 - 2.0 * len(citations.get("risks", [])))
    structure_score = max(1.0, 5.0 - 1.0 * len(structure.get("risks", [])))
    question_present = any(item.get("claim_type") in {"research_question", "research_aim"} for item in claims)
    scores = {
        "research_focus": 4.0 if question_present else 2.0,
        "evidence_integrity": round(evidence_score, 2),
        "discipline_method_reporting": round(protocol_score, 2),
        "citation_consistency": round(citation_score, 2),
        "structure": round(structure_score, 2),
    }
    average = round(sum(scores.values()) / len(scores), 2)
    return {
        "schema_version": "3.0",
        "name": "v3-evidence-bound-preflight",
        "scores": scores,
        "average": average,
        "confidence": 0.62,
        "note": "锚定式确定性预检，不以关键词数量冒充最终学术质量评分。",
    }


def _revision_plan(document: ThesisDocument, graph: dict, review: dict) -> dict:
    items = []
    used_locators = set()
    paragraph_map = {item.locator: item for item in document.paragraphs}
    for claim in graph.get("claims", []):
        if claim.get("status") != "unresolved" or claim["locator"] in used_locators:
            continue
        paragraph = paragraph_map.get(claim["locator"])
        if paragraph is None:
            continue
        used_locators.add(claim["locator"])
        items.append(
            {
                "id": f"PLAN-{claim['claim_id']}",
                "fingerprint": f"claim:{claim['claim_id']}:{claim['text_hash'][:12]}",
                "confirmed": False,
                "status": "open",
                "locator": claim["locator"],
                "target_hash": paragraph.text_hash,
                "target_text": claim["text"],
                "problem": f"{claim['claim_type']} 尚未定位到充分证据。",
                "action": "mark_and_request",
                "patch_mode": "mark_unconfirmed",
                "evidence_class": "SOURCE_ORIGINAL",
                "requires_author_confirmation": True,
                "proposed_rewrite": claim["text"],
                "risk": "不得将未验证主张改写成确定事实。",
                "acceptance_test": "作者补充可定位证据或确认降低主张强度。",
                "allowed_changes": {"numbers": [], "years": [], "citations": []},
            }
        )
    for issue in review.get("issues", []):
        if issue.get("claim_ids"):
            continue
        items.append(
            {
                "id": f"PLAN-{issue['id']}",
                "fingerprint": issue["fingerprint"],
                "confirmed": False,
                "status": "open",
                "locator": issue["locator"],
                "target_hash": "",
                "target_text": "",
                "problem": issue["finding"],
                "action": "manual_review",
                "patch_mode": "manual_only",
                "evidence_class": issue.get("evidence_class", "SOURCE_ORIGINAL"),
                "requires_author_confirmation": issue.get("requires_author_confirmation", False),
                "proposed_rewrite": "",
                "risk": issue["rationale"],
                "acceptance_test": issue["acceptance_test"],
                "allowed_changes": {"numbers": [], "years": [], "citations": []},
            }
        )
    return {
        "schema_version": "3.0",
        "plan_id": f"revision-plan-{document.source_hash[:16]}",
        "source": document.source,
        "source_hash": document.source_hash,
        "mode": "staged_confirmation",
        "items": items,
        "instructions": [
            "只有 confirmed=true 且 proposed_rewrite 为具体文本的 replace_text 项可自动改写。",
            "manual_only 项即使确认也不会自动写入 Word。",
            "任何数字、年份或引用变化必须写入 allowed_changes 并通过回归审计。",
        ],
    }


def _markdown_table(headers: list[str], rows: list[list[object]]) -> str:
    clean = [[str(cell).replace("|", "\\|").replace("\n", "<br>") for cell in row] for row in rows]
    output = ["| " + " | ".join(headers) + " |", "| " + " | ".join(["---"] * len(headers)) + " |"]
    output.extend("| " + " | ".join(row) + " |" for row in clean)
    return "\n".join(output)


def _patch_mode_label(mode: str, requires_confirmation: bool) -> str:
    labels = {
        "mark_unconfirmed": "标记待作者确认",
        "replace_text": "确认后替换文本",
        "manual_only": "仅人工处理",
    }
    confirmation = "需确认" if requires_confirmation else "无需确认"
    return f"{labels.get(mode, mode)} / {confirmation}"


def _review_report(review: dict, graph: dict, strategy: dict, rubric: dict, regression: dict | None = None) -> str:
    issues = review.get("issues", [])
    lines = [
        "# 修改说明与盲审风险报告",
        "",
        "## 总体判断",
        "",
        f"- 风险：{review['summary']['risk']}",
        f"- P0/P1/P2：{review['summary']['p0']}/{review['summary']['p1']}/{review['summary']['p2']}",
        f"- 本地预检平均分：{rubric['average']}（置信度 {rubric['confidence']}）",
        f"- 学科协议：{strategy['discipline']['label']}",
        f"- 方法协议：{strategy['method']['label']}（置信度 {strategy['method']['confidence']}）",
        f"- 未解决主张：{graph['unresolved_count']}",
        "",
        "> 本报告区分确定性预检与语义教授评审。低置信度项目必须人工复核。",
        "",
        "## 可追溯问题清单",
        "",
    ]
    if not issues:
        lines.append("未发现结构化问题。")
        lines.append("")
    for item in issues:
        lines.extend(
            [
                f"### {item['priority']} · {item['rule_id']}",
                "",
                f"- 审查者：{item['reviewer']}",
                f"- 定位：{item['locator']}",
                f"- 置信度：{item['confidence']:.2f}",
                f"- 问题：{item['finding']}",
                f"- 依据：{item['rationale']}",
                f"- 建议：{item['recommended_action']}",
                f"- 验收：{item['acceptance_test']}",
                "",
            ]
        )
    lines.extend(
        [
            "## 策略与方法确认",
            "",
            f"- 方法需确认：{'是' if strategy['method']['needs_confirmation'] else '否'}",
            f"- 学科需确认：{'是' if strategy['discipline']['needs_confirmation'] else '否'}",
            "",
        ]
    )
    if regression:
        lines.extend(
            [
                "## 回归门禁",
                "",
                f"- 结果：{regression['regression_result']}",
                f"- 违规：{'; '.join(regression['violations']) if regression['violations'] else '无'}",
                "",
            ]
        )
    lines.extend(
        [
            "## 下一步",
            "",
            "1. 确认学科、方法与所有需作者确认的修改项。",
            "2. 为未解决主张补充可定位证据，或提供具体的限定性改写。",
            "3. 执行 revise 后必须通过数字、年份、引用和 DOCX 部件回归门禁。",
        ]
    )
    return "\n".join(lines)


def _analyze(
    input_path: str | Path,
    *,
    level: str,
    discipline: str,
    method: str,
    stage: str,
    semantic_payload: dict | None = None,
) -> dict:
    document = load_document(input_path)
    graph = build_claim_graph(document)
    citations = citation_audit(document)
    structure = structure_audit(document)
    text = "\n".join(item.text for item in document.paragraphs)
    strategy = select_strategy(text, discipline, method, level, stage)
    deterministic = build_findings(graph, strategy, citations, structure)
    findings = merge_semantic_findings(deterministic, semantic_payload)
    review = build_review(findings, level, strategy["discipline"]["key"], strategy["method"]["key"])
    rubric = _rubric(graph, strategy, citations, structure)
    plan = _revision_plan(document, graph, review)
    plan.update(
        {
            "level": level,
            "discipline": strategy["discipline"]["key"],
            "method": strategy["method"]["key"],
            "stage": stage,
        }
    )
    return {
        "document_object": document,
        "document": document.to_dict(),
        "claim_graph": graph,
        "citations": citations,
        "structure": structure,
        "strategy": strategy,
        "review": review,
        "rubric": rubric,
        "revision_plan": plan,
    }


def review_workflow(
    input_path: str | Path,
    outdir: str | Path,
    *,
    level: str = "master",
    discipline: str = "unknown",
    method: str = "unknown",
    stage: str = "blind-review",
    semantic_findings: str | Path | None = None,
    state_path: str | Path | None = None,
) -> dict:
    outdir = Path(outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    semantic_payload = read_json(semantic_findings) if semantic_findings else None
    if semantic_payload:
        errors = validate_semantic_payload(semantic_payload)
        if errors:
            raise ValueError("Invalid semantic findings: " + "; ".join(errors))
    result = _analyze(
        input_path,
        level=level,
        discipline=discipline,
        method=method,
        stage=stage,
        semantic_payload=semantic_payload,
    )
    document: ThesisDocument = result.pop("document_object")
    artifacts = {
        "document_model": outdir / "document_model.json",
        "claim_graph": outdir / "claim_evidence_graph.json",
        "citation_audit": outdir / "citation_audit.json",
        "structure": outdir / "structure.json",
        "strategy": outdir / "selected_strategy.json",
        "review": outdir / "professor_panel.json",
        "rubric": outdir / "rubric_score.json",
        "revision_plan": outdir / "revision_plan.json",
        "semantic_request": outdir / "semantic_review_request.json",
    }
    result_keys = {
        "document_model": "document",
        "claim_graph": "claim_graph",
        "citation_audit": "citations",
        "structure": "structure",
        "strategy": "strategy",
        "review": "review",
        "rubric": "rubric",
        "revision_plan": "revision_plan",
    }
    for key, path in artifacts.items():
        if key == "semantic_request":
            payload = semantic_review_request(result["document"], result["claim_graph"], result["strategy"], result["review"])
        else:
            payload = result[result_keys[key]]
        write_json(path, payload)
    report_md = _review_report(result["review"], result["claim_graph"], result["strategy"], result["rubric"])
    report_docx = outdir / "修改说明与盲审风险报告.docx"
    log_docx = outdir / "逐条修改清单.docx"
    manuscript = outdir / "论文修改稿.docx"
    write_docx(report_docx, "修改说明与盲审风险报告", report_md)
    log_rows = [
        [
            item["id"],
            item["problem"],
            _patch_mode_label(item["patch_mode"], item["requires_author_confirmation"]),
            item["locator"].replace("word/document.xml#", ""),
        ]
        for item in result["revision_plan"]["items"]
    ]
    write_docx(log_docx, "逐条修改清单", _markdown_table(["ID", "问题", "执行方式", "定位"], log_rows))
    if Path(input_path).suffix.lower() == ".docx":
        shutil.copyfile(input_path, manuscript)
    else:
        write_docx(manuscript, "论文修改稿", Path(input_path).read_text(encoding="utf-8", errors="ignore"))
    convergence = {
        "p0_clear": result["review"]["summary"]["p0"] == 0,
        "p1_verified_or_waived": result["review"]["summary"]["p1"] == 0,
        "evidence_controlled": result["claim_graph"]["unresolved_count"] == 0,
        "regression_passed": False,
        "word_fidelity_checked": False,
    }
    payload = {
        "schema_version": "3.0",
        "input": str(input_path),
        "source_hash": document.source_hash,
        **result,
        "artifacts": {key: str(value) for key, value in artifacts.items()},
        "deliverables": [str(report_docx), str(log_docx), str(manuscript)],
        "convergence": convergence,
    }
    prior_state = read_json(state_path) if state_path and Path(state_path).exists() else None
    state = advance_state(prior_state, payload, phase="revision_plan")
    state_file = outdir / "revision_state.json"
    round_file = outdir / "round_payload.json"
    write_json(state_file, state)
    write_json(round_file, payload)
    return {"outdir": str(outdir), "report": str(report_docx), "state": str(state_file), "semantic_request": str(artifacts["semantic_request"])}


def _allowed_changes(plan: dict) -> dict:
    allowed = {"numbers": [], "years": [], "citations": []}
    for item in plan.get("items", []):
        if not item.get("confirmed"):
            continue
        for key in allowed:
            allowed[key].extend(item.get("allowed_changes", {}).get(key, []))
    return allowed


def revise_workflow(
    input_path: str | Path,
    plan_path: str | Path,
    outdir: str | Path,
    *,
    state_path: str | Path | None = None,
    tracked: bool = True,
) -> dict:
    input_path = Path(input_path)
    outdir = Path(outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    plan = read_json(plan_path)
    before = load_document(input_path)
    if plan.get("source_hash") and plan["source_hash"] != before.source_hash:
        raise ValueError("Revision plan source_hash does not match the input document")
    candidate = outdir / "论文修改候选稿.docx"
    if input_path.suffix.lower() != ".docx":
        raise ValueError("V3 controlled revise currently requires a .docx source")
    patch_log = patch_docx(input_path, candidate, plan, tracked=tracked, mark_unconfirmed=True)
    after = load_document(candidate)
    regression = regression_audit(before, after, _allowed_changes(plan))
    final_docx = outdir / "论文修改稿.docx"
    if regression["regression_result"] == "pass":
        shutil.copyfile(candidate, final_docx)
    else:
        shutil.copyfile(input_path, final_docx)
        blocked_candidate = outdir / "论文修改候选稿-回归未通过.docx"
        shutil.copyfile(candidate, blocked_candidate)
    analysis = _analyze(
        candidate,
        level=plan.get("level", "master"),
        discipline=plan.get("discipline", "unknown"),
        method=plan.get("method", "unknown"),
        stage="regression-review",
    )
    analysis.pop("document_object")
    write_json(outdir / "applied_revision_log.json", patch_log)
    write_json(outdir / "diff_audit.json", regression)
    write_json(outdir / "professor_panel.json", analysis["review"])
    write_json(outdir / "claim_evidence_graph.json", analysis["claim_graph"])
    report_md = _review_report(analysis["review"], analysis["claim_graph"], analysis["strategy"], analysis["rubric"], regression)
    report_docx = outdir / "修改说明与盲审风险报告.docx"
    write_docx(report_docx, "修改说明与盲审风险报告", report_md)
    log_rows = [[item.get("id"), item.get("status"), item.get("reason", ""), item.get("locator", "")] for item in patch_log["items"]]
    log_docx = outdir / "逐条修改清单.docx"
    write_docx(log_docx, "逐条修改清单", _markdown_table(["ID", "状态", "原因", "位置"], log_rows))
    convergence = {
        "p0_clear": analysis["review"]["summary"]["p0"] == 0,
        "p1_verified_or_waived": analysis["review"]["summary"]["p1"] == 0,
        "evidence_controlled": analysis["claim_graph"]["unresolved_count"] == 0 or patch_log["marked_count"] > 0,
        "regression_passed": regression["regression_result"] == "pass",
        "word_fidelity_checked": not regression["package_parts_removed"] and not regression["media_parts_removed"],
    }
    payload = {
        "schema_version": "3.0",
        "input": str(candidate),
        "source_hash": after.source_hash,
        **analysis,
        "revision_plan": plan,
        "regression": regression,
        "patch_log": patch_log,
        "deliverables": [str(final_docx), str(report_docx), str(log_docx)],
        "convergence": convergence,
    }
    prior_state = read_json(state_path) if state_path and Path(state_path).exists() else None
    state = advance_state(prior_state, payload, phase="regression_review")
    write_json(outdir / "revision_state.json", state)
    write_json(outdir / "round_payload.json", payload)
    return {
        "outdir": str(outdir),
        "manuscript": str(final_docx),
        "candidate": str(candidate),
        "regression": regression["regression_result"],
        "state": str(outdir / "revision_state.json"),
    }


def corpus_workflow(corpus_dir: str | Path, out: str | Path, *, rights_manifest: str | Path | None = None) -> dict:
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    patterns = derive_patterns(corpus_dir, read_manifest(rights_manifest))
    pattern_path = out.with_suffix(".patterns.json")
    write_json(pattern_path, patterns)
    out.write_text(strategy_cards(patterns), encoding="utf-8")
    return {"strategy_cards": str(out), "patterns": str(pattern_path), "authorized_documents": patterns["authorized_document_count"]}


def status_summary(state_path: str | Path) -> dict:
    state = read_json(state_path)
    convergence = state.get("convergence", {})
    active = state.get("issues", [])
    return {
        "round": state.get("round"),
        "phase": state.get("phase"),
        "status": state.get("status"),
        "p0_count": sum(item.get("priority") == "P0" and item.get("status") != "resolved" for item in active),
        "p1_count": sum(item.get("priority") == "P1" and item.get("status") != "resolved" for item in active),
        "new_risk_count": len(state.get("new_risks", [])),
        "resolved_count": len(state.get("resolved", [])),
        "confirmation_queue_count": len(state.get("confirmation_queue", [])),
        "stable_rounds": state.get("stable_rounds", 0),
        "convergence": convergence,
        "can_export_final": bool(convergence) and all(convergence.values()),
        "next_step": "补充/确认修改计划后运行 revise。" if state.get("phase") == "revision_plan" else "处理未通过门禁并重新评审。",
    }
