"""Institution and style profile loading with safe precedence."""

from __future__ import annotations

import json
from pathlib import Path


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
    return {
        "schema_version": "1.0",
        "profile_id": profile.get("profile_id", "unknown"),
        "source": profile.get("source", "unknown"),
        "version": profile.get("version", "unspecified"),
        "risks": risks,
        "rules_applied": sorted(profile.keys()),
    }
