"""Deterministic audits that preserve source locations and avoid semantic overclaiming."""

from __future__ import annotations

import re
from collections import Counter

from .claim_evidence import citation_markers
from .document_model import ThesisDocument


REFERENCE_TITLES = {"参考文献", "references", "bibliography"}

# 确认标记统一在此定义：docx_patch 生成标记、回归审计剥离标记都引用同一处，
# 避免两处正则漂移。剥离时连同标记前的空白一起移除。
CONFIRMATION_MARKER_PREFIX = "[需作者确认:"
CONFIRMATION_MARKER_RE = re.compile(r"\s*" + re.escape(CONFIRMATION_MARKER_PREFIX) + r"[^\[\]]*\]")


def confirmation_marker(reason: str) -> str:
    return f" {CONFIRMATION_MARKER_PREFIX}{reason}]"


def strip_confirmation_markers(text: str) -> str:
    return CONFIRMATION_MARKER_RE.sub("", text)


# 数值 invariant：支持负号、千分位(1,247)、小数(3.14)与百分号(-2.3%)。
# 取向是"宁可少报、不可误报"：token 内部不允许字母/下划线/小数点拼接
# (如 v1.2、GB_7714 不整体入表)，后续紧跟字母或数字的匹配被丢弃，
# 版本号、编号类内容因此不易被误当数值变化。
NUMBER_TOKEN_RE = re.compile(r"(?<![A-Za-z0-9_.])(?:-?(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?%?)(?![A-Za-z0-9])")
# 年份 invariant：合理的四位年份范围取 1600-2099(学位论文引文罕见更早)，
# 两侧加数字边界，避免从更长数字串中误切。
YEAR_TOKEN_RE = re.compile(r"(?<!\d)(?:1[6-9]\d{2}|20\d{2})(?!\d)")


def citation_audit(document: ThesisDocument) -> dict:
    # 章节结构只认主文档；脚注/尾注计入正文引用网络；页眉页脚不参与引用审计。
    main_paragraphs = [p for p in document.paragraphs if p.locator.startswith("word/document.xml#")]
    note_paragraphs = [p for p in document.paragraphs if p.locator.startswith(("word/footnotes.xml#", "word/endnotes.xml#"))]
    paragraphs = main_paragraphs
    reference_index: int | None = None
    for index, paragraph in enumerate(paragraphs):
        normalized = re.sub(r"\s+", "", paragraph.text).lower().rstrip("：:")
        if normalized in REFERENCE_TITLES and paragraph.heading_level is not None:
            reference_index = index
            break
    body = (paragraphs if reference_index is None else paragraphs[:reference_index]) + note_paragraphs
    references = [] if reference_index is None else paragraphs[reference_index + 1 :]
    body_markers = [marker for paragraph in body for marker in citation_markers(paragraph.text)]
    cited_numbers: set[str] = set()
    for marker in body_markers:
        cited_numbers.update(re.findall(r"\d+", marker))
    numbered_references: dict[str, str] = {}
    entries: list[dict] = []
    for paragraph in references:
        match = re.match(r"^\s*\[?(\d+)\]?[.、\s]", paragraph.text)
        if not match:
            continue
        entry = _parse_reference_entry(match.group(1), paragraph.text, paragraph.locator)
        entries.append(entry)
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
    risks.extend(_reference_structure_risks(entries, numbered_references))
    return {
        "schema_version": "4.0",
        "reference_heading_locator": paragraphs[reference_index].locator if reference_index is not None else None,
        "citation_count": len(body_markers),
        "reference_count": len(references),
        "numbered_reference_count": len(numbered_references),
        "missing_reference_entries": missing,
        "uncited_reference_entries": uncited,
        "reference_entries": entries,
        "risks": risks,
        "note": "引用标记一致性检查不等于引用真实性或语义支持验证。",
    }


# GB/T 7714 类型标识(半角),全角括号单独提示。
_TYPE_MARKER_RE = re.compile(r"\[([A-Za-z]{1,3})\]")
_FULLWIDTH_MARKER_RE = re.compile(r"【([A-Za-z]{1,3})】")


def _parse_reference_entry(number: str, text: str, locator: str) -> dict:
    """粗解析文献表条目要素；只做结构抽取，不判断文献真实性。"""
    marker = _TYPE_MARKER_RE.search(text)
    fullwidth = _FULLWIDTH_MARKER_RE.search(text)
    year = re.search(r"(?<!\d)(?:1[6-9]\d{2}|20\d{2})(?!\d)", text)
    segments = [segment.strip() for segment in re.split(r"[.．]", text)]
    segments = [segment for segment in segments if segment]
    author = segments[0] if len(segments) >= 2 else ""
    title = segments[1] if len(segments) >= 3 else ""
    return {
        "number": number,
        "locator": locator,
        "text": text,
        "has_author": bool(author),
        "has_title": bool(title),
        "has_year": year is not None,
        "type_marker": marker.group(1) if marker else None,
        "fullwidth_marker": fullwidth.group(1) if fullwidth else None,
    }


def _reference_structure_risks(entries: list[dict], numbered_references: dict[str, str]) -> list[dict]:
    """CIT-REF-* 结构审计:编号连续性/重复与 GB/T 7714 要素完整性。

    只做结构匹配；文献是否真实存在、内容是否语义支持主张,属于证据层。
    """
    if not entries:
        return []
    risks = []
    numbers = [int(entry["number"]) for entry in entries]
    duplicates = sorted({number for number in numbers if numbers.count(number) > 1})
    gaps = sorted(set(range(1, max(numbers) + 1)) - set(numbers)) if numbers else []
    if duplicates or gaps:
        parts = []
        if duplicates:
            parts.append(f"重复编号 {', '.join(map(str, duplicates))}")
        if gaps:
            parts.append(f"缺号 {', '.join(map(str, gaps))}")
        risks.append(
            {
                "rule_id": "CIT-REF-NUMBERING",
                "priority": "P1",
                "message": f"参考文献编号不连续或重复：{'；'.join(parts)}。",
                "locator": "word/document.xml#references",
                "confidence": 0.9,
                "requires_confirmation": True,
                "rationale": "仅核对编号结构,不判断条目内容真实性。",
            }
        )
    for entry in entries:
        missing_fields = [label for key, label in (("has_author", "作者"), ("has_title", "题名"), ("has_year", "年份")) if not entry[key]]
        if missing_fields or not entry["type_marker"]:
            problems = []
            if missing_fields:
                problems.append(f"缺 {'/'.join(missing_fields)}")
            if not entry["type_marker"]:
                problems.append("缺类型标识(如 [J]/[M]/[D]/[C])")
            risks.append(
                {
                    "rule_id": "CIT-REF-FIELDS",
                    "priority": "P1",
                    "message": f"参考文献 [{entry['number']}] {'；'.join(problems)}。",
                    "locator": entry["locator"],
                    "confidence": 0.9,
                    "requires_confirmation": True,
                    "rationale": "仅按 GB/T 7714 要素完整性做结构检查,不判断文献真实存在或语义支持。",
                }
            )
        if entry["fullwidth_marker"]:
            risks.append(
                {
                    "rule_id": "CIT-REF-FULLWIDTH-MARKER",
                    "priority": "P2",
                    "message": f"参考文献 [{entry['number']}] 使用全角类型标识【{entry['fullwidth_marker']}】,建议改为半角 [{entry['fullwidth_marker']}]。",
                    "locator": entry["locator"],
                    "confidence": 0.9,
                    "requires_confirmation": True,
                    "rationale": "版式规范提示,不影响文献内容判定。",
                }
            )
    return risks


def structure_audit(document: ThesisDocument) -> dict:
    headings = [paragraph for paragraph in document.paragraphs if paragraph.heading_level is not None and paragraph.locator.startswith("word/document.xml#")]
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
        "schema_version": "4.0",
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
    # 先剥离作者确认标记：标记文本(及其未来可能出现的数字)不参与数字/年份/citation 比对。
    text = "\n".join(strip_confirmation_markers(paragraph.text) for paragraph in document.paragraphs)
    return {
        # 四位年份由 years 类别单独登记，不再重复计入 numbers，避免同一变化双报。
        "numbers": Counter(token for token in NUMBER_TOKEN_RE.findall(text) if not YEAR_TOKEN_RE.fullmatch(token)),
        "years": Counter(YEAR_TOKEN_RE.findall(text)),
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
        "schema_version": "4.0",
        "changes": changes,
        "package_parts_removed": package_removed,
        "media_parts_removed": media_removed,
        "violations": violations,
        "regression_result": "pass" if not violations else "blocked_and_rolled_back",
    }
