"""Traceable deterministic preflight plus a schema for semantic professor review."""

from __future__ import annotations

import hashlib
import json
import re
from typing import Iterable


LABELS = {
    "causal_claim": "因果主张",
    "statistical_claim": "统计性结果主张",
    "result_claim": "研究结果主张",
    "literature_claim": "文献事实主张",
    "general_factual_claim": "实质性事实主张",
    "ethics": "研究伦理",
    "instrument": "研究工具",
    "procedure": "研究实施流程",
    "participants": "研究对象/参与者",
    "sampling": "抽样与研究对象",
    "coding": "编码或分析过程",
    "trustworthiness": "质性研究可信度",
    "baseline": "基线或对比方法",
    "metrics": "评价指标",
    "data": "数据集或数据来源",
    "reproducibility": "可复现信息",
    "identification": "识别策略",
    "variables": "变量定义",
    "robustness": "稳健性检验",
    "authority": "法律依据",
    "interpretation": "解释方法",
}


def display_label(value: str) -> str:
    return LABELS.get(value, value)


def issue_fingerprint(rule_id: str, locator: str, finding: str = "") -> str:
    """Stable identity: wording-independent, so reviewer phrasing never breaks chains.

    Only `rule_id` and `locator` feed the digest; `finding` is accepted for
    backward compatibility and ignored. Use `legacy_fingerprint` when matching
    states written by older versions.
    """
    raw = f"{rule_id}|{locator}".encode("utf-8")
    return hashlib.sha256(raw).hexdigest()[:20]


def legacy_fingerprint(rule_id: str, locator: str, finding: str) -> str:
    """Pre-decoupling fingerprint (rule_id | locator | normalized finding)."""
    normalized = re.sub(r"\s+", " ", finding).strip().lower()
    raw = f"{rule_id}|{locator}|{normalized}".encode("utf-8")
    return hashlib.sha256(raw).hexdigest()[:20]


def _issue(
    *,
    rule_id: str,
    reviewer: str,
    locator: str,
    finding: str,
    severity: str,
    rationale: str,
    action: str,
    acceptance_test: str,
    claim_ids: Iterable[str] = (),
    evidence_ids: Iterable[str] = (),
    confidence: float = 0.7,
    requires_confirmation: bool = False,
) -> dict:
    fingerprint = issue_fingerprint(rule_id, locator, finding)
    return {
        "id": f"{severity}-{rule_id}-{fingerprint[:8]}",
        "fingerprint": fingerprint,
        "rule_id": rule_id,
        "reviewer": reviewer,
        "role": reviewer,
        "locator": locator,
        "claim_ids": list(claim_ids),
        "evidence_ids": list(evidence_ids),
        "priority": severity,
        "severity": severity,
        "likelihood": round(confidence, 2),
        "impact": {"P0": 0.95, "P1": 0.7, "P2": 0.35}.get(severity, 0.5),
        "confidence": round(confidence, 2),
        "finding": finding,
        "rationale": rationale,
        "counterevidence": "未进行外部文献内容核验；作者材料可能提供反证。",
        "recommended_action": action,
        "acceptance_test": acceptance_test,
        "evidence_class": "SOURCE_ORIGINAL",
        "requires_author_confirmation": requires_confirmation,
        "status": "open",
        "source_engine": "deterministic_preflight",
    }


def build_findings(claim_graph: dict, strategy: dict, citations: dict, structure: dict) -> list[dict]:
    findings: list[dict] = []
    for claim in claim_graph.get("claims", []):
        if claim.get("status") != "unresolved":
            continue
        claim_type = claim.get("claim_type")
        severity = claim.get("severity_hint", "P1")
        rule_id = {
            "causal_claim": "EVI-CAUSAL-UNRESOLVED",
            "statistical_claim": "EVI-STATISTICAL-UNRESOLVED",
            "result_claim": "EVI-RESULT-UNRESOLVED",
            "literature_claim": "EVI-LITERATURE-UNRESOLVED",
        }.get(claim_type, "EVI-CLAIM-UNRESOLVED")
        findings.append(
            _issue(
                rule_id=rule_id,
                reviewer="evidence_reviewer",
                locator=claim["locator"],
                finding=f"{display_label(claim_type)}尚未定位到充分证据。",
                severity=severity,
                rationale=f"原句：{claim['text']}；{claim['rationale']}",
                action="补充可定位的数据、表图、分析或文献；无法补充时降低主张强度。",
                acceptance_test="主张关联到可核验依据，或明确标记为未解决且不写成确定性结论。",
                claim_ids=[claim["claim_id"]],
                evidence_ids=[item["evidence_id"] for item in claim.get("evidence_links", [])],
                confidence=float(claim.get("confidence", 0.7)),
                requires_confirmation=True,
            )
        )
    for risk in citations.get("risks", []):
        findings.append(
            _issue(
                rule_id=risk["rule_id"],
                reviewer="citation_reviewer",
                locator=risk.get("locator", "word/document.xml#references"),
                finding=risk["message"],
                severity=risk["priority"],
                rationale="正文区与参考文献区已分离后执行编号一致性检查。",
                action="核对原文与参考文献表，不自动生成或猜测文献。",
                acceptance_test="正文引用与文后条目一一对应，且作者确认文献真实存在。",
                confidence=0.92,
                requires_confirmation=risk["priority"] == "P0",
            )
        )
    for risk in structure.get("risks", []):
        findings.append(
            _issue(
                rule_id=risk["rule_id"],
                reviewer="structure_reviewer",
                locator=risk["locator"],
                finding=risk["message"],
                severity=risk["priority"],
                rationale="依据可定位的 Word 标题层级执行结构预检。",
                action="结合学校模板确认并修正标题层级或必要章节。",
                acceptance_test="标题层级连续且满足用户提供的学校规范。",
                confidence=0.75,
            )
        )
    for scope in (strategy["discipline"], strategy["method"]):
        for component in scope.get("coverage", []):
            if component["status"] != "not_located":
                continue
            key = scope["key"].upper().replace("-", "_")
            findings.append(
                _issue(
                    rule_id=f"PRO-{key}-{component['component'].upper()}",
                    reviewer="discipline_method_reviewer",
                    locator="word/document.xml",
                    finding=f"在{scope['label']}协议中未定位到组件：{display_label(component['component'])}。",
                    severity="P1",
                    rationale="本地预检未发现配置中的报告标记；这不是缺失事实的最终判定。",
                    action="由语义评审在相关章节复核；若确实缺失，再要求作者补充。",
                    acceptance_test=f"定位并核验{display_label(component['component'])}，或记录不适用理由。",
                    confidence=float(component["confidence"]),
                    requires_confirmation=False,
                )
            )
    deduplicated = {item["fingerprint"]: item for item in findings}
    return sorted(
        deduplicated.values(),
        key=lambda item: ({"P0": 0, "P1": 1, "P2": 2}.get(item["priority"], 9), item["id"]),
    )


def merge_semantic_findings_with_rejections(deterministic: list[dict], semantic_payload: dict | None) -> tuple[list[dict], list[dict]]:
    """Merge accepted semantic findings; rejected ones are returned with reasons."""
    if not semantic_payload:
        return deterministic, []
    accepted, rejected = partition_semantic_findings(semantic_payload)
    merged = {item["fingerprint"]: item for item in deterministic}
    for raw in accepted:
        item = _issue(
            rule_id=str(raw["rule_id"]),
            reviewer=str(raw["reviewer"]),
            locator=str(raw["locator"]),
            finding=str(raw["finding"]),
            severity=str(raw["severity"]),
            rationale=str(raw["rationale"]),
            action=str(raw["recommended_action"]),
            acceptance_test=str(raw["acceptance_test"]),
            claim_ids=raw.get("claim_ids", []),
            evidence_ids=raw.get("evidence_ids", []),
            confidence=float(raw.get("confidence", 0.7)),
            requires_confirmation=bool(raw.get("requires_author_confirmation", False)),
        )
        item["source_engine"] = "semantic_professor_review"
        item["counterevidence"] = str(raw.get("counterevidence", item["counterevidence"]))
        merged[item["fingerprint"]] = item
    return sorted(merged.values(), key=lambda item: ({"P0": 0, "P1": 1, "P2": 2}.get(item["priority"], 9), item["id"])), rejected


def merge_semantic_findings(deterministic: list[dict], semantic_payload: dict | None) -> list[dict]:
    merged, _rejected = merge_semantic_findings_with_rejections(deterministic, semantic_payload)
    return merged


def build_review(findings: list[dict], level: str, discipline: str, method: str) -> dict:
    counts = {priority: sum(1 for item in findings if item["priority"] == priority) for priority in ("P0", "P1", "P2")}
    risk = "pass"
    if counts["P0"]:
        risk = "high risk"
    elif counts["P1"] >= 4:
        risk = "major revision"
    elif counts["P1"] or counts["P2"]:
        risk = "minor revision"
    return {
        "schema_version": "4.0",
        "level": level,
        "discipline": discipline,
        "method": method,
        "issues": findings,
        "summary": {"p0": counts["P0"], "p1": counts["P1"], "p2": counts["P2"], "risk": risk},
        "calibration_note": "确定性结果是可解释预检；教授级最终判断需要独立语义评审或人工导师复核。",
    }


def semantic_review_request(document: dict, claim_graph: dict, strategy: dict, review: dict, *, ledger: dict | None = None, consistency: dict | None = None, profile: dict | None = None) -> dict:
    return {
        "schema_version": "4.0",
        "task": "independent_semantic_professor_review",
        "instructions": [
            "只依据定位到的原文与用户材料审查，不补造数据、引用或结论。",
            "逐项检查反证；低置信度时 abstain。",
            "每条 finding 必须给 locator、rule_id、rationale、confidence 和 acceptance_test。",
            "不要重复确定性预检意见，除非能提供更具体的语义依据。",
        ],
        "reviewer_roles": [
            "chief_argument_reviewer",
            "discipline_expert",
            "method_expert",
            "evidence_auditor",
            "citation_norms_expert",
            "integrity_ethics_expert",
            "adversarial_blind_reviewer",
        ],
        "loop_rounds": {
            "max_rounds": 5,
            "round_2": "independent role reviews",
            "round_3": "adversarial counterevidence and contradiction search",
            "round_5": "regression and convergence review",
        },
        "document": document,
        "claim_graph": claim_graph,
        "selected_strategy": strategy,
        "deterministic_review": review,
        "claim_evidence_ledger": ledger or {},
        "consistency_matrix": consistency or {},
        "profile_audit": profile or {},
        "output_schema": {
            "findings": [
                {
                    "rule_id": "string",
                    "reviewer": "string",
                    "locator": "string",
                    "claim_ids": ["string"],
                    "evidence_ids": ["string"],
                    "severity": "P0|P1|P2",
                    "confidence": "0..1",
                    "finding": "string",
                    "rationale": "string",
                    "counterevidence": "string",
                    "recommended_action": "string",
                    "acceptance_test": "string",
                    "requires_author_confirmation": "boolean"
                }
            ]
        },
    }


SEMANTIC_REQUIRED_FIELDS = ("rule_id", "reviewer", "locator", "severity", "confidence", "finding", "rationale", "recommended_action", "acceptance_test")
SEMANTIC_OPTIONAL_FIELDS = ("claim_ids", "evidence_ids", "counterevidence", "requires_author_confirmation")
# 语义 finding 必须锚定到段落 locator;兼容历史 ;index= 形式。
SEMANTIC_LOCATOR_RE = re.compile(r"^word/document\.xml#para=\S+$")
SEMANTIC_SEVERITIES = {"P0", "P1", "P2"}


def validate_semantic_finding(item: object) -> list[str]:
    """Per-finding validation; returns human-readable rejection reasons."""
    if not isinstance(item, dict):
        return ["finding must be a JSON object"]
    reasons = []
    for field in SEMANTIC_REQUIRED_FIELDS:
        value = item.get(field)
        if value is None or (isinstance(value, str) and not value.strip()):
            reasons.append(f"missing required field: {field}")
    severity = item.get("severity")
    if severity is not None and severity not in SEMANTIC_SEVERITIES:
        reasons.append(f"severity must be one of P0/P1/P2, got {severity!r}")
    confidence = item.get("confidence")
    if confidence is not None and (
        isinstance(confidence, bool) or not isinstance(confidence, (int, float)) or not 0 <= confidence <= 1
    ):
        reasons.append(f"confidence must be a number between 0 and 1, got {confidence!r}")
    locator = item.get("locator")
    if locator is not None and (not isinstance(locator, str) or not SEMANTIC_LOCATOR_RE.match(locator)):
        reasons.append(f"locator must look like word/document.xml#para=..., got {locator!r}")
    return reasons


def partition_semantic_findings(payload: dict | None) -> tuple[list[dict], list[dict]]:
    """Split payload findings into accepted raw findings and rejected diagnostics."""
    accepted: list[dict] = []
    rejected: list[dict] = []
    for index, item in enumerate((payload or {}).get("findings", [])):
        reasons = validate_semantic_finding(item)
        if reasons:
            rejected.append({"index": index, "reasons": reasons, "finding": item if isinstance(item, dict) else repr(item)})
        else:
            accepted.append(item)
    return accepted, rejected


def validate_semantic_payload(payload: dict) -> list[str]:
    """Structural errors that invalidate the whole payload.

    Per-finding problems do not fail the review; they are rejected individually
    and surfaced through `partition_semantic_findings` / merge diagnostics.
    """
    if not isinstance(payload, dict):
        return ["payload must be a JSON object"]
    errors = []
    if not isinstance(payload.get("findings"), list):
        errors.append("findings must be a list")
    return errors


def reviewer_disagreements(semantic_payload: dict | None) -> dict:
    """Preserve independent reviewer conflicts instead of silently choosing one."""
    groups: dict[str, list[dict]] = {}
    for item in (semantic_payload or {}).get("findings", []):
        locator = str(item.get("locator", "word/document.xml"))
        groups.setdefault(locator, []).append(item)
    conflicts = []
    for locator, items in groups.items():
        reviewers = {str(item.get("reviewer", "unknown")) for item in items}
        findings = {str(item.get("finding", "")).strip() for item in items}
        severities = {str(item.get("severity", "P2")) for item in items}
        if len(reviewers) > 1 and (len(findings) > 1 or len(severities) > 1):
            conflicts.append({
                "locator": locator,
                "reviewers": sorted(reviewers),
                "positions": [
                    {"reviewer": item.get("reviewer"), "severity": item.get("severity"), "confidence": item.get("confidence", 0.7), "finding": item.get("finding", ""), "rationale": item.get("rationale", "")}
                    for item in items
                ],
                "chief_adjudication_required": True,
                "status": "open",
            })
    return {"schema_version": "4.0", "conflicts": conflicts, "count": len(conflicts)}
