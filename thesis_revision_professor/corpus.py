"""Copyright-aware, non-verbatim corpus strategy extraction."""

from __future__ import annotations

import hashlib
import json
import statistics
from collections import Counter
from pathlib import Path

from .claim_evidence import citation_markers
from .document_model import load_document


SECTION_MOVES = {
    "abstract": ("摘要", "abstract"),
    "introduction": ("绪论", "引言", "introduction"),
    "literature_review": ("文献综述", "研究现状", "literature review"),
    "theory": ("理论", "概念框架", "theoretical framework"),
    "method": ("研究方法", "方法", "methodology", "methods"),
    "results": ("研究结果", "结果", "results"),
    "discussion": ("讨论", "discussion"),
    "limitations": ("局限", "不足", "limitations"),
    "conclusion": ("结论", "conclusion"),
    "references": ("参考文献", "references", "bibliography"),
}


def rights_template(corpus_dir: str | Path) -> dict:
    return {
        "schema_version": "1.0",
        "corpus_dir": str(Path(corpus_dir)),
        "instructions": "逐文件确认合法权限。只有 allow_derived_strategy=true 的文件会进入聚合分析。",
        "files": [],
    }


def _rights_map(manifest: dict | None) -> dict[str, dict]:
    if not manifest:
        return {}
    return {str(item.get("relative_path")): item for item in manifest.get("files", [])}


def derive_patterns(corpus_dir: str | Path, manifest: dict | None) -> dict:
    root = Path(corpus_dir)
    rights = _rights_map(manifest)
    documents = []
    rejected = 0
    for path in sorted(root.rglob("*")):
        if path.suffix.lower() not in {".docx", ".txt", ".md"}:
            continue
        relative = path.relative_to(root).as_posix()
        permission = rights.get(relative, {})
        if not permission.get("allow_derived_strategy"):
            rejected += 1
            continue
        document = load_document(path)
        heading_text = [item.text.lower() for item in document.paragraphs if item.heading_level is not None]
        moves = []
        for heading in heading_text:
            for move, markers in SECTION_MOVES.items():
                if any(marker in heading for marker in markers) and move not in moves:
                    moves.append(move)
                    break
        text = "\n".join(item.text for item in document.paragraphs)
        documents.append(
            {
                "anonymous_id": hashlib.sha256((relative + document.source_hash).encode("utf-8")).hexdigest()[:16],
                "moves": moves,
                "paragraph_count": len(document.paragraphs),
                "citation_marker_count": len(citation_markers(text)),
                "discipline": permission.get("discipline", "unknown"),
                "level": permission.get("level", "unknown"),
                "method": permission.get("method", "unknown"),
                "year_band": permission.get("year_band", "unknown"),
                "quality_basis": permission.get("quality_basis", "unverified"),
            }
        )
    frequencies = Counter(move for document in documents for move in document["moves"])
    transitions = Counter(
        f"{left}->{right}"
        for document in documents
        for left, right in zip(document["moves"], document["moves"][1:])
    )
    citation_counts = [item["citation_marker_count"] for item in documents]
    paragraph_counts = [item["paragraph_count"] for item in documents]
    return {
        "schema_version": "3.0",
        "authorized_document_count": len(documents),
        "rejected_unverified_count": rejected,
        "section_frequency": dict(frequencies),
        "move_transitions": dict(transitions),
        "citation_marker_distribution": {
            "median": statistics.median(citation_counts) if citation_counts else 0,
            "min": min(citation_counts, default=0),
            "max": max(citation_counts, default=0),
        },
        "paragraph_count_distribution": {
            "median": statistics.median(paragraph_counts) if paragraph_counts else 0,
            "min": min(paragraph_counts, default=0),
            "max": max(paragraph_counts, default=0),
        },
        "strata": dict(Counter(f"{item['discipline']}|{item['level']}|{item['method']}" for item in documents)),
        "documents": documents,
        "privacy_note": "不保留标题、作者、绝对路径或原文片段；匿名 ID 不可用于重建原文。",
    }


def strategy_cards(patterns: dict, *, minimum_group: int = 10) -> str:
    count = patterns.get("authorized_document_count", 0)
    lines = [
        "# Corpus-derived strategy cards",
        "",
        "这些卡片仅表示合法语料中的非逐字聚合模式，不是事实证据，也不自动代表优秀写法。",
        "",
        f"- 已授权文档：{count}",
        f"- 未授权或未确认文档：{patterns.get('rejected_unverified_count', 0)}",
        f"- 最小公开分组：k ≥ {minimum_group}",
        "",
    ]
    if count < minimum_group:
        lines.extend(["## 发布门禁", "", "样本量不足，不发布可泛化策略；请补充合法授权语料。", ""])
        return "\n".join(lines)
    for move, value in sorted(patterns.get("section_frequency", {}).items()):
        rate = value / count
        lines.extend(
            [
                f"## MOVE-{move.upper()}",
                "",
                f"- support_n: {value}",
                f"- observed_rate: {rate:.3f}",
                "- evidence_class: SOURCE_CORPUS_PATTERN",
                "- action: 仅用于检查章节功能是否完整，不复制语料措辞。",
                "- limitation: 频率不等于质量，必须结合学科、方法和学校规范。",
                "",
            ]
        )
    return "\n".join(lines)


def read_manifest(path: str | Path | None) -> dict | None:
    return json.loads(Path(path).read_text(encoding="utf-8")) if path else None
