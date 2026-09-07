"""Select discipline and method protocols from packaged strategy profiles."""

from __future__ import annotations

import json
from importlib import resources


def load_profiles() -> dict:
    resource = resources.files("thesis_revision_professor.resources").joinpath("strategy_profiles.json")
    return json.loads(resource.read_text(encoding="utf-8"))


def infer_method(text: str, requested: str = "unknown") -> tuple[str, float, list[str]]:
    profiles = load_profiles()["methods"]
    if requested and requested != "unknown":
        if requested not in profiles:
            return "unknown", 0.0, []
        return requested, 1.0, ["user_selected"]
    ranked: list[tuple[int, str, list[str]]] = []
    lower = text.lower()
    for key, profile in profiles.items():
        if key == "unknown":
            continue
        hits = [marker for marker in profile.get("markers", []) if marker.lower() in lower]
        ranked.append((len(hits), key, hits))
    # 命中数最多者优先；命中数相同时取 key 字典序最小者，保证路由稳定可预期。
    ranked.sort(key=lambda item: (-item[0], item[1]))
    count, key, hits = ranked[0] if ranked else (0, "unknown", [])
    if count == 0:
        return "unknown", 0.0, []
    return key, min(0.9, 0.45 + count * 0.12), hits


def _coverage(text: str, components: dict) -> list[dict]:
    lower = text.lower()
    results = []
    for component, markers in components.items():
        hits = []
        for marker in markers:
            start = lower.find(marker.lower())
            if start < 0:
                continue
            context = lower[max(0, start - 10) : start + len(marker) + 10]
            if any(negation in context for negation in ("未提供", "尚未", "尚待", "没有", "缺少", "不足", "不明", "无法")):
                continue
            hits.append(marker)
        results.append(
            {
                "component": component,
                "status": "present_marker" if hits else "not_located",
                "markers": hits,
                "confidence": 0.75 if hits else 0.55,
            }
        )
    return results


def select_strategy(text: str, discipline: str, method: str, level: str, stage: str) -> dict:
    profiles = load_profiles()
    discipline_key = discipline if discipline in profiles["disciplines"] else "generic"
    method_key, method_confidence, method_evidence = infer_method(text, method)
    discipline_profile = profiles["disciplines"][discipline_key]
    method_profile = profiles["methods"][method_key]
    discipline_coverage = _coverage(text, discipline_profile.get("required_components", {}))
    method_coverage = _coverage(text, method_profile.get("required_components", {}))
    return {
        "schema_version": profiles["schema_version"],
        "precedence": profiles["precedence"],
        "level": level,
        "stage": stage,
        "discipline": {
            "key": discipline_key,
            "label": discipline_profile["label"],
            "requested": discipline,
            "needs_confirmation": discipline_key == "generic" and discipline != "generic",
            "coverage": discipline_coverage,
            "high_risk_questions": discipline_profile.get("high_risk", []),
        },
        "method": {
            "key": method_key,
            "label": method_profile["label"],
            "requested": method,
            "confidence": method_confidence,
            "evidence": method_evidence,
            "needs_confirmation": method_key == "unknown" or method_confidence < 0.65,
            "coverage": method_coverage,
        },
    }
