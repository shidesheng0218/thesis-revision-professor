"""External blind-review / advisor feedback import: split, locate, map, report.

Feedback findings are heuristic and low-confidence by design; they never enter
automatic patching without author confirmation, and items whose locator cannot
be resolved stay on the manual path.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from .docx_report import write_docx
from .document_model import ThesisDocument
from .review_engine import issue_fingerprint


ITEM_START_RE = re.compile(r"^\s*(?:第\s*([一二三四五六七八九十百\d]+)\s*条|(\d+)\s*[.、．)）]|[（(]\s*(\d+)\s*[)）])", re.M)
SEVERITY_P0_RE = re.compile(r"必须|错误|严重|不通过|不合格|抄袭|造假")
SEVERITY_P1_RE = re.compile(r"建议|不足|问题|缺失|欠缺|应当|需要修改|补充")
CHAPTER_RE = re.compile(r"第\s*([一二三四五六七八九十百\d]+)\s*章")
SECTION_RE = re.compile(r"(?<![\d.])(\d+(?:\.\d+){0,3})\s*节")

_CN_DIGITS = {"一": 1, "二": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7, "八": 8, "九": 9}


def _cn_number(text: str) -> int | None:
    text = text.strip()
    if text.isdigit():
        return int(text)
    if text in _CN_DIGITS:
        return _CN_DIGITS[text]
    if text == "十":
        return 10
    if text.startswith("十") and text[1:] in _CN_DIGITS:
        return 10 + _CN_DIGITS[text[1:]]
    if text.endswith("十") and text[:-1] in _CN_DIGITS:
        return _CN_DIGITS[text[:-1]] * 10
    match = re.fullmatch(r"([一二三四五六七八九])十([一二三四五六七八九])", text)
    if match:
        return _CN_DIGITS[match.group(1)] * 10 + _CN_DIGITS[match.group(2)]
    return None


def split_feedback(text: str) -> list[str]:
    """启发式切分外部意见:编号/第X条优先,其次关键词段落,切不开则整段一条。"""
    matches = list(ITEM_START_RE.finditer(text))
    if len(matches) >= 2:
        items = []
        for index, match in enumerate(matches):
            end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
            body = text[match.start() : end].strip()
            if body:
                items.append(body)
        return items
    paragraphs = [part.strip() for part in re.split(r"\n\s*\n", text) if part.strip()]
    keyword_paragraphs = [part for part in paragraphs if SEVERITY_P1_RE.search(part) or SEVERITY_P0_RE.search(part)]
    if keyword_paragraphs:
        return keyword_paragraphs
    stripped = text.strip()
    return [stripped] if stripped else []


def locate_feedback(text: str, document: ThesisDocument) -> str | None:
    """从意见中的章节/小节线索定位到主文档标题段落;匹配不到返回 None。"""
    headings = [
        paragraph
        for paragraph in document.paragraphs
        if paragraph.heading_level is not None and paragraph.locator.startswith("word/document.xml#")
    ]

    def find_heading(prefix: str) -> str | None:
        for paragraph in headings:
            normalized = re.sub(r"\s+", "", paragraph.text)
            if normalized.startswith(prefix):
                return paragraph.locator
        return None

    chapter = CHAPTER_RE.search(text)
    if chapter:
        number = _cn_number(chapter.group(1))
        if number is not None:
            for candidate in (f"第{number}章", f"第{chapter.group(1)}章"):
                locator = find_heading(candidate)
                if locator:
                    return locator
        locator = find_heading(f"第{chapter.group(1)}章")
        if locator:
            return locator
    section = SECTION_RE.search(text)
    if section:
        prefix = section.group(1)
        for paragraph in headings:
            normalized = re.sub(r"\s+", "", paragraph.text)
            if normalized.startswith(prefix) and not (len(normalized) > len(prefix) and normalized[len(prefix)].isdigit()):
                return paragraph.locator
    return None


def feedback_findings(text: str, document: ThesisDocument) -> list[dict]:
    findings = []
    for index, raw in enumerate(split_feedback(text), start=1):
        locator = locate_feedback(raw, document)
        severity = "P0" if SEVERITY_P0_RE.search(raw) else ("P1" if SEVERITY_P1_RE.search(raw) else "P2")
        rule_id = f"FB-{index:03d}"
        findings.append(
            {
                "id": f"{severity}-{rule_id}-{issue_fingerprint(rule_id, locator or '')[:8]}",
                "fingerprint": issue_fingerprint(rule_id, locator or ""),
                "rule_id": rule_id,
                "reviewer": "external_reviewer",
                "role": "external_reviewer",
                "locator": locator,
                "claim_ids": [],
                "evidence_ids": [],
                "priority": severity,
                "severity": severity,
                "likelihood": 0.5,
                "impact": {"P0": 0.95, "P1": 0.7, "P2": 0.35}[severity],
                "confidence": 0.5,
                "finding": raw,
                "rationale": "外部评审意见导入，按启发式规则切分与定位，置信度固定较低；需作者逐条确认。",
                "counterevidence": "外部意见可能与学校规范或论文实际不符；以导师与学校要求为准。",
                "recommended_action": "作者逐条确认意见，确认后纳入受控修改。",
                "acceptance_test": "作者确认采纳或不采纳并给出理由。",
                "evidence_class": "EXTERNAL_REVIEW",
                "requires_author_confirmation": True,
                "needs_manual_locator": locator is None,
                "status": "open",
                "source_engine": "external_feedback",
            }
        )
    return findings


def build_feedback_mapping(findings: list[dict], plan_items: list[dict]) -> list[dict]:
    by_fingerprint = {item.get("fingerprint"): item for item in plan_items}
    mapping = []
    for finding in findings:
        item = by_fingerprint.get(finding["fingerprint"], {})
        mapping.append(
            {
                "feedback_id": finding["rule_id"],
                "finding_id": finding["id"],
                "raw_text": finding["finding"],
                "locator": finding["locator"],
                "needs_manual_locator": finding["needs_manual_locator"],
                "plan_item_id": item.get("id"),
                "status": "待定位" if finding["locator"] is None else "待作者确认",
            }
        )
    return mapping


def build_feedback_report(mapping: list[dict], plan_items: list[dict], *, patch_log: dict | None = None, out_docx: str | Path | None = None) -> str:
    """《意见—修改对照表》:每条外部意见绑定计划项与当前状态。"""
    plan_by_id = {item.get("id"): item for item in plan_items}
    patch_by_id = {item.get("id"): item for item in (patch_log or {}).get("items", [])}
    lines = [
        "# 意见—修改对照表",
        "",
        "> 外部意见经启发式切分导入,状态随受控修改流程更新;不采纳须填写理由。",
        "",
        "| 意见 | 意见摘要 | 状态 | 计划项 | 定位 | 不采纳理由 |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for entry in mapping:
        plan_item = plan_by_id.get(entry.get("plan_item_id"), {})
        patch_item = patch_by_id.get(entry.get("plan_item_id"))
        if patch_item is not None:
            status = {
                "applied_confirmed": "已修改",
                "marked_unconfirmed": "需作者确认",
                "comment_added": "已批注待人工",
                "not_applied": "需人工处理",
                "blocked": "需人工处理",
            }.get(patch_item.get("status"), patch_item.get("status", ""))
        elif entry.get("needs_manual_locator"):
            status = "待定位"
        elif plan_item.get("confirmed"):
            status = "已确认待执行"
        else:
            status = entry.get("status", "待作者确认")
        summary = re.sub(r"\s+", " ", str(entry.get("raw_text", ""))).strip()
        if len(summary) > 60:
            summary = summary[:60] + "…"
        lines.append(
            "| " + " | ".join(
                [
                    str(entry.get("feedback_id", "")),
                    summary.replace("|", "\\|"),
                    status,
                    str(entry.get("plan_item_id") or "—"),
                    str(entry.get("locator") or "—"),
                    "",
                ]
            ) + " |"
        )
    body = "\n".join(lines)
    if out_docx is not None:
        write_docx(out_docx, "意见—修改对照表", body)
    return body
