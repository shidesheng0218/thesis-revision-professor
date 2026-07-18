"""Deterministic audits that preserve source locations and avoid semantic overclaiming."""

from __future__ import annotations

import re
from collections import Counter

from .claim_evidence import citation_markers
from .document_model import ThesisDocument


REFERENCE_TITLES = {"参考文献", "references", "bibliography"}


def citation_audit(document: ThesisDocument) -> dict:
    paragraphs = list(document.paragraphs)
    reference_index: int | None = None
    for index, paragraph in enumerate(paragraphs):
        normalized = re.sub(r"\s+", "", paragraph.text).lower().rstrip("：:")
        if normalized in REFERENCE_TITLES and paragraph.heading_level is not None:
            reference_index = index
            break
    body = paragraphs if reference_index is None else paragraphs[:reference_index]
    references = [] if reference_index is None else paragraphs[reference_index + 1 :]
    body_markers = [marker for paragraph in body for marker in citation_markers(paragraph.text)]
    cited_numbers: set[str] = set()
    for marker in body_markers:
        cited_numbers.update(re.findall(r"\d+", marker))
    numbered_references: dict[str, str] = {}
    for paragraph in references:
        match = re.match(r"^\s*\[?(\d+)\]?[.、\s]", paragraph.text)
        if match:
            numbered_references[match.group(1)] = paragraph.locator
    reference_numbers = set(numbered_references)
    missing = sorted(cited_numbers - reference_numbers, key=int)
    uncited = sorted(reference_numbers - cited_numbers, key=int)
    risks = []
    if body_markers and reference_index is None:
        risks.append(
            {
                "rule_id": "CIT-REFERENCE-SECTION-MISSING",
                "priority": "P0",
                "message": "检测到正文引用，但未定位到独立的参考文献标题段落。",
                "locator": body[0].locator if body else "",
            }
        )
    if missing:
        risks.append(
            {
                "rule_id": "CIT-MISSING-ENTRY",
                "priority": "P0",
                "message": f"正文引用编号未在参考文献表中出现：{', '.join(missing)}。",
                "locator": "word/document.xml#references",
            }
        )
    if uncited:
        risks.append(
            {
                "rule_id": "CIT-UNCITED-ENTRY",
                "priority": "P2",
                "message": f"参考文献条目未在正文中检测到引用：{', '.join(uncited)}。",
                "locator": "word/document.xml#references",
            }
        )
    return {
        "schema_version": "3.0",
        "reference_heading_locator": paragraphs[reference_index].locator if reference_index is not None else None,
        "citation_count": len(body_markers),
        "reference_count": len(references),
        "numbered_reference_count": len(numbered_references),
        "missing_reference_entries": missing,
        "uncited_reference_entries": uncited,
        "risks": risks,
        "note": "引用标记一致性检查不等于引用真实性或语义支持验证。",
    }


def structure_audit(document: ThesisDocument) -> dict:
    headings = [paragraph for paragraph in document.paragraphs if paragraph.heading_level is not None]
    risks: list[dict] = []
    previous_level = 0
    for heading in headings:
        level = heading.heading_level or 1
        if previous_level and level > previous_level + 1:
            risks.append(
                {
                    "rule_id": "STR-HEADING-JUMP",
                    "priority": "P1",
                    "locator": heading.locator,
                    "message": f"标题层级从 {previous_level} 跳到 {level}。",
                }
            )
        previous_level = level
    normalized = [re.sub(r"\s+", "", item.text).lower() for item in headings]
    expected = {
        "abstract": any(item in {"摘要", "abstract"} for item in normalized),
        "references": any(item in REFERENCE_TITLES for item in normalized),
        "conclusion": any("结论" in item or item == "conclusion" for item in normalized),
    }
    for key, present in expected.items():
        if not present:
            risks.append(
                {
                    "rule_id": f"STR-MISSING-{key.upper()}",
                    "priority": "P1",
                    "locator": "word/document.xml",
                    "message": f"未定位到 {key} 标准章节标题；需结合学校规范人工确认。",
                }
            )
    return {
        "schema_version": "3.0",
        "paragraph_count": len(document.paragraphs),
        "heading_count": len(headings),
        "chapter_count": sum(1 for item in headings if item.heading_level == 1),
        "headings": [
            {"locator": item.locator, "text": item.text, "level": item.heading_level}
            for item in headings
        ],
        "part_counts": {
            "package_parts": len(document.package_parts),
            "media_parts": len(document.media_parts),
        },
        "risks": risks,
    }


def invariant_snapshot(document: ThesisDocument) -> dict:
    text = "\n".join(paragraph.text for paragraph in document.paragraphs)
    return {
        "numbers": Counter(re.findall(r"(?<![A-Za-z])\d+(?:\.\d+)?%?(?![A-Za-z])", text)),
        "years": Counter(re.findall(r"(?:19|20)\d{2}", text)),
        "citations": Counter(citation_markers(text)),
        "media_parts": list(document.media_parts),
        "package_parts": list(document.package_parts),
    }


def _counter_delta(before: Counter, after: Counter) -> tuple[list[str], list[str]]:
    removed = list((before - after).elements())
    added = list((after - before).elements())
    return sorted(removed), sorted(added)


def regression_audit(before: ThesisDocument, after: ThesisDocument, allowed_changes: dict | None = None) -> dict:
    allowed_changes = allowed_changes or {}
    left = invariant_snapshot(before)
    right = invariant_snapshot(after)
    changes = {}
    for key in ("numbers", "years", "citations"):
        removed, added = _counter_delta(left[key], right[key])
        changes[key] = {"removed": removed, "added": added}
    package_removed = sorted(set(left["package_parts"]) - set(right["package_parts"]))
    media_removed = sorted(set(left["media_parts"]) - set(right["media_parts"]))
    violations = []
    for key in ("numbers", "years", "citations"):
        allowed = set(allowed_changes.get(key, []))
        unexpected = [item for item in changes[key]["removed"] + changes[key]["added"] if item not in allowed]
        if unexpected:
            violations.append(f"{key} 出现未授权变化：{', '.join(unexpected)}")
    if package_removed:
        violations.append(f"DOCX 包部件丢失：{', '.join(package_removed)}")
    if media_removed:
        violations.append(f"媒体部件丢失：{', '.join(media_removed)}")
    return {
        "schema_version": "3.0",
        "changes": changes,
        "package_parts_removed": package_removed,
        "media_parts_removed": media_removed,
        "violations": violations,
        "regression_result": "pass" if not violations else "blocked_and_rolled_back",
    }
