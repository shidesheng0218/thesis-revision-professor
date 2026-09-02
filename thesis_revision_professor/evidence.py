"""Evidence-pack manifests and claim--evidence ledger construction.

The ledger is deliberately conservative: an evidence file can be located and
hashed locally, but it is not considered verified until the author explicitly
confirms it.  This keeps the deterministic layer useful without turning a file
name or a citation marker into proof.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path


ALLOWED_TYPES = {
    "SOURCE_USER_DATA",
    "SOURCE_STATISTICS",
    "SOURCE_TABLE_FIGURE",
    "SOURCE_INTERVIEW",
    "SOURCE_CODE_OUTPUT",
    "SOURCE_REFERENCE",
    "SOURCE_LAW_POLICY",
    "SOURCE_DOI_METADATA",
    "SOURCE_AUTHOR_ASSERTION",
}
ALLOWED_RIGHTS = {"user_owned", "licensed", "public_domain", "unknown"}

REQUIRED_TYPE_MAP = {
    "SOURCE_ORIGINAL": {"SOURCE_USER_DATA", "SOURCE_STATISTICS", "SOURCE_TABLE_FIGURE", "SOURCE_INTERVIEW", "SOURCE_CODE_OUTPUT", "SOURCE_AUTHOR_ASSERTION"},
    "METHOD_CAPABILITY": {"SOURCE_USER_DATA", "SOURCE_STATISTICS", "SOURCE_CODE_OUTPUT", "SOURCE_AUTHOR_ASSERTION"},
    "ANALYSIS_TRACE": {"SOURCE_STATISTICS", "SOURCE_CODE_OUTPUT", "SOURCE_TABLE_FIGURE"},
    "SOURCE_USER_DATA": {"SOURCE_USER_DATA", "SOURCE_STATISTICS", "SOURCE_TABLE_FIGURE", "SOURCE_INTERVIEW", "SOURCE_CODE_OUTPUT"},
    "SOURCE_REFERENCE": {"SOURCE_REFERENCE", "SOURCE_DOI_METADATA"},
    "SOURCE_PUBLIC_FACT": {"SOURCE_REFERENCE", "SOURCE_LAW_POLICY", "SOURCE_DOI_METADATA"},
    "ARGUMENT_CHAIN": {"SOURCE_REFERENCE", "SOURCE_USER_DATA", "SOURCE_STATISTICS", "SOURCE_TABLE_FIGURE", "SOURCE_INTERVIEW"},
}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def evidence_template(evidence_dir: str | Path) -> dict:
    return {
        "schema_version": "1.0",
        "evidence_dir": str(Path(evidence_dir)),
        "instructions": "逐条填写证据类型、合法权利、定位和作者核验状态；未知材料不会被当作已证实事实。",
        "items": [],
    }


def read_manifest(path: str | Path | None) -> dict:
    if not path:
        return {"schema_version": "1.0", "items": []}
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or not isinstance(payload.get("items", []), list):
        raise ValueError("evidence manifest must be an object with an items list")
    return payload


def _normalise_item(item: dict, root: Path, index: int) -> dict:
    relative = str(item.get("path", "")).replace("\\", "/")
    path = (root / relative).resolve() if relative else None
    exists = bool(path and path.is_file() and root.resolve() in path.parents)
    evidence_type = str(item.get("type", "SOURCE_AUTHOR_ASSERTION"))
    rights = str(item.get("rights_status", "unknown"))
    return {
        "evidence_id": str(item.get("evidence_id") or f"EV-USER-{index:04d}"),
        "type": evidence_type if evidence_type in ALLOWED_TYPES else "SOURCE_AUTHOR_ASSERTION",
        "path": relative,
        "sha256": _sha256(path) if exists else None,
        "locator": str(item.get("locator", "")),
        "rights_status": rights if rights in ALLOWED_RIGHTS else "unknown",
        "verified_by_author": bool(item.get("verified_by_author", False)),
        "exists": exists,
        "usable": bool(exists and rights in {"user_owned", "licensed", "public_domain"}),
        "note": str(item.get("note", "")),
    }


def normalise_manifest(evidence_dir: str | Path, manifest: dict | None) -> dict:
    root = Path(evidence_dir)
    items = [_normalise_item(item, root, index) for index, item in enumerate((manifest or {}).get("items", []), 1)]
    return {
        "schema_version": "1.0",
        "evidence_dir": str(root),
        "items": items,
        "usable_count": sum(item["usable"] for item in items),
        "unverified_count": sum(not item["verified_by_author"] for item in items),
        "limits": [
            "存在且有权使用不等于内容已经支持某条主张。",
            "只有作者确认后，证据才可用于自动修改的事实授权。",
            "不会把证据文件原文复制到开源产物或策略卡。",
        ],
    }


def build_ledger(claim_graph: dict, evidence_manifest: dict | None = None) -> dict:
    manifest_items = (evidence_manifest or {}).get("items", [])
    usable = [item for item in manifest_items if item.get("usable")]
    by_type: dict[str, list[dict]] = {}
    for item in usable:
        by_type.setdefault(item["type"], []).append(item)
    claims = []
    for claim in claim_graph.get("claims", []):
        required = list(claim.get("required_evidence", []))
        linked = []
        for evidence_type in required:
            accepted_types = REQUIRED_TYPE_MAP.get(evidence_type, {evidence_type})
            for accepted_type in accepted_types:
                linked.extend(by_type.get(accepted_type, []))
        links = [
            {
                "evidence_id": item["evidence_id"],
                "type": item["type"],
                "locator": item.get("locator", ""),
                "strength": "author_verified" if item.get("verified_by_author") else "candidate_only",
            }
            for item in linked[:20]
        ]
        if claim.get("status") == "not_applicable":
            support = "not_applicable"
        elif links and all(item["strength"] == "author_verified" for item in links):
            support = "author_verified_candidate"
        elif links:
            support = "candidate_unverified"
        else:
            support = "unresolved"
        claims.append(
            {
                "claim_id": claim["claim_id"],
                "claim_type": claim["claim_type"],
                "text": claim["text"],
                "locator": claim["locator"],
                "section_title": claim.get("section_title", ""),
                "required_evidence": required,
                "evidence_links": links,
                "support_status": support,
                "counterevidence": [],
                "design_boundary_status": "unassessed",
                "recommended_strength": "maintain" if support in {"not_applicable", "author_verified_candidate"} else "bound_or_abstain",
                "author_confirmation_required": support not in {"not_applicable", "author_verified_candidate"},
            }
        )
    return {
        "schema_version": "4.0",
        "source_hash": claim_graph.get("source_hash"),
        "evidence_count": len(manifest_items),
        "usable_evidence_count": len(usable),
        "claim_count": len(claims),
        "unresolved_claim_count": sum(item["support_status"] == "unresolved" for item in claims),
        "claims": claims,
        "policy": "证据可以支持审查和建议，但不能凭空创造研究事实；作者确认是事实修改的必要条件。",
    }
