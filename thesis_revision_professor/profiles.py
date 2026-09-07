"""Institution and style profile loading with safe precedence."""

from __future__ import annotations

import json
from pathlib import Path


TWIPS_PER_MM = 56.6929
MARGIN_TOLERANCE_MM = 1.0


def load_profile(path: str | Path | None) -> dict:
    if not path:
        return {"schema_version": "1.0", "profile_id": "default-safe", "required_sections": [], "source": "built-in-safe-default"}
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("profile must be a JSON object")
    payload.setdefault("schema_version", "1.0")
    payload.setdefault("profile_id", Path(path).stem)
    payload.setdefault("required_sections", [])
    payload.setdefault("source", "user-provided")
    return payload


def _layout_findings(document, profile: dict) -> list[dict]:
    font_cfg = profile.get("font") or {}
    margins_cfg = profile.get("margins_mm") or {}
    layout = getattr(document, "layout", None) or {}
    findings = []
    font_problems = []
    expected_font = font_cfg.get("eastAsia")
    actual_font = layout.get("default_east_asia_font")
    if expected_font and actual_font and actual_font.strip() != str(expected_font).strip():
        font_problems.append(f"默认中文字体为 {actual_font}，规范要求 {expected_font}")
    body_pt = font_cfg.get("body_pt")
    actual_pt = layout.get("default_size_pt")
    if body_pt is not None and actual_pt is not None and abs(actual_pt - float(body_pt)) > 0.01:
        font_problems.append(f"默认字号为 {actual_pt:g}pt，规范要求 {float(body_pt):g}pt")
    if font_problems:
        findings.append(
            {
                "rule_id": "PROF-LAYOUT-FONT",
                "priority": "P2",
                "locator": "word/styles.xml",
                "message": "版式与规范不符：" + "；".join(font_problems) + "。",
                "rationale": "仅从文档默认样式读取版式，未核对显式设置段落；最终版式以学校规范与人工排版为准。",
                "action": "对照学校版式规范调整默认字体与字号，或记录豁免。",
                "acceptance_test": "作者确认版式符合学校规范，或提供规范豁免说明。",
                "requires_author_confirmation": True,
            }
        )
    if margins_cfg:
        for position, section in enumerate(layout.get("section_margins_twips") or [], start=1):
            mismatches = []
            for side in ("top", "right", "bottom", "left"):
                expected = margins_cfg.get(side)
                actual = section.get(side)
                if expected is None or actual is None:
                    continue
                actual_mm = actual / TWIPS_PER_MM
                if abs(actual_mm - float(expected)) > MARGIN_TOLERANCE_MM:
                    mismatches.append(f"{side} 实际约 {actual_mm:.1f}mm / 要求 {float(expected):g}mm")
            if mismatches:
                findings.append(
                    {
                        "rule_id": "PROF-LAYOUT-MARGINS",
                        "priority": "P2",
                        "locator": "word/document.xml",
                        "message": f"第 {position} 节页边距与规范不符（容差 ±{MARGIN_TOLERANCE_MM:g}mm）：" + "；".join(mismatches) + "。",
                        "rationale": "页边距按 sectPr/w:pgMar 读取（1mm≈56.6929 twips）；以学校规范与最终排版为准。",
                        "action": "对照学校版式规范调整页边距，或记录豁免。",
                        "acceptance_test": "作者确认页边距符合学校规范，或提供规范豁免说明。",
                        "requires_author_confirmation": True,
                    }
                )
    return findings


def profile_audit(document, profile: dict) -> dict:
    headings = [item.text.strip().lower() for item in document.paragraphs if item.heading_level is not None]
    risks = []
    for required in profile.get("required_sections", []):
        aliases = required if isinstance(required, list) else [required]
        if not any(any(str(alias).lower() in heading for heading in headings) for alias in aliases):
            risks.append({
                "rule_id": "PROF-MISSING-SECTION",
                "priority": "P1",
                "locator": "word/document.xml",
                "message": f"规范 profile 要求章节未定位：{' / '.join(map(str, aliases))}。",
            })
    risks.extend(_layout_findings(document, profile))
    return {
        "schema_version": "1.0",
        "profile_id": profile.get("profile_id", "unknown"),
        "source": profile.get("source", "unknown"),
        "version": profile.get("version", "unspecified"),
        "risks": risks,
        "rules_applied": sorted(profile.keys()),
    }
