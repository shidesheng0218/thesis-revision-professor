"""Cross-section consistency checks with explicit abstention."""

from __future__ import annotations

import re
from collections import defaultdict

from .document_model import ThesisDocument


SAMPLE_RE = re.compile(r"(?:样本(?:量)?|受试者|参与者|respondents?|participants?)\s*(?:为|是|共|=|:)?\s*(\d+)", re.I)
NUMBER_RE = re.compile(r"(?<![A-Za-z])\d+(?:\.\d+)?%?(?![A-Za-z])")


def _section_key(title: str) -> str:
    value = title.lower()
    if "摘要" in value or value == "abstract":
        return "abstract"
    if "方法" in value or "method" in value:
        return "method"
    if "结果" in value or "result" in value:
        return "results"
    if "结论" in value or "conclusion" in value:
        return "conclusion"
    if "创新" in value or "贡献" in value or "contribution" in value:
        return "contribution"
    if "文献" in value or "literature" in value:
        return "literature"
    if "附录" in value or "appendix" in value:
        return "appendix"
    return "other"


def _facts(document: ThesisDocument) -> dict[str, dict[str, list[dict]]]:
    facts: dict[str, dict[str, list[dict]]] = defaultdict(lambda: defaultdict(list))
    for paragraph in document.paragraphs:
        section = _section_key(paragraph.section_title)
        for match in SAMPLE_RE.finditer(paragraph.text):
            facts[section]["sample_size"].append({"value": match.group(1), "locator": paragraph.locator, "text": paragraph.text})
        for match in NUMBER_RE.finditer(paragraph.text):
            facts[section]["number"].append({"value": match.group(0), "locator": paragraph.locator, "text": paragraph.text})
    return facts


def consistency_audit(document: ThesisDocument, claim_graph: dict | None = None) -> dict:
    facts = _facts(document)
    risks = []
    sample_locations = []
    for section in ("abstract", "method", "results", "conclusion"):
        for item in facts[section].get("sample_size", []):
            sample_locations.append((section, item))
    sample_values = {item["value"] for _, item in sample_locations}
    if len(sample_values) > 1:
        risks.append({
            "rule_id": "CON-SAMPLE-SIZE-CONTRADICTION",
            "type": "CONTRADICTION",
            "priority": "P0",
            "confidence": 0.98,
            "locator": sample_locations[0][1]["locator"],
            "message": "摘要、方法、结果或结论中的样本量出现明确不一致。",
            "evidence": sample_locations,
        })
    result_claims = [item for item in (claim_graph or {}).get("claims", []) if item.get("claim_type") in {"result_claim", "causal_claim", "statistical_claim"}]
    method_present = bool(facts["method"].get("number") or facts["method"].get("sample_size"))
    if result_claims and not method_present:
        risks.append({
            "rule_id": "CON-METHOD-RESULT-MISSING-LINK",
            "type": "MISSING_LINK",
            "priority": "P1",
            "confidence": 0.82,
            "locator": result_claims[0].get("locator", "word/document.xml"),
            "message": "检测到结果/因果主张，但方法章节未定位到可核验的样本或数量信息；需语义复核，不能据此断言方法无效。",
            "evidence": [{"claim_id": result_claims[0].get("claim_id")}],
        })
    conclusion_claims = [item for item in (claim_graph or {}).get("claims", []) if item.get("section_title") and "结论" in item.get("section_title", "") and item.get("claim_type") in {"causal_claim", "result_claim", "general_factual_claim"}]
    result_text = " ".join(item["text"] for item in (claim_graph or {}).get("claims", []) if item.get("claim_type") in {"result_claim", "statistical_claim"})
    if conclusion_claims and not result_text:
        risks.append({
            "rule_id": "CON-CONCLUSION-OVERCLAIM",
            "type": "OVERCLAIM",
            "priority": "P1",
            "confidence": 0.77,
            "locator": conclusion_claims[0].get("locator", "word/document.xml"),
            "message": "结论章节存在结果性主张，但正文结果链未被确定性预检定位；应由作者或语义评审核对。",
            "evidence": [{"claim_id": item.get("claim_id")} for item in conclusion_claims],
        })
    if not facts["abstract"].get("sample_size") and facts["method"].get("sample_size"):
        risks.append({
            "rule_id": "CON-ABSTRACT-MISSING-SAMPLE",
            "type": "MISSING_LINK",
            "priority": "P2",
            "confidence": 0.7,
            "locator": document.paragraphs[0].locator if document.paragraphs else "word/document.xml",
            "message": "方法章节报告样本量，但摘要未定位到样本信息；是否需要补充取决于学校规范。",
            "evidence": facts["method"]["sample_size"],
        })
    return {
        "schema_version": "4.0",
        "facts": {section: dict(values) for section, values in facts.items()},
        "risks": risks,
        "abstentions": ["仅凭关键词无法判断中文摘要与英文摘要的语义等价性；需要语义评审。"],
        "matrix": [
            {"pair": "摘要↔方法", "status": "checked", "rules": ["CON-SAMPLE-SIZE-CONTRADICTION", "CON-ABSTRACT-MISSING-SAMPLE"]},
            {"pair": "方法↔结果", "status": "checked", "rules": ["CON-METHOD-RESULT-MISSING-LINK"]},
            {"pair": "结果↔结论", "status": "checked", "rules": ["CON-CONCLUSION-OVERCLAIM"]},
            {"pair": "中文摘要↔英文摘要", "status": "abstain", "rules": []},
        ],
    }


def compare_documents(before: ThesisDocument, after: ThesisDocument) -> dict:
    left = _facts(before)
    right = _facts(after)
    changes = []
    for section in sorted(set(left) | set(right)):
        before_values = sorted({item["value"] for item in left[section].get("sample_size", [])})
        after_values = sorted({item["value"] for item in right[section].get("sample_size", [])})
        if before_values != after_values:
            changes.append({"section": section, "field": "sample_size", "before": before_values, "after": after_values, "type": "CONTRADICTION"})
    return {"schema_version": "4.0", "changes": changes, "status": "pass" if not changes else "review_required"}
