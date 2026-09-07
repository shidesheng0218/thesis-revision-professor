"""Build a conservative, traceable claim-evidence graph for thesis review."""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from typing import Iterable

from .document_model import DocumentParagraph, ThesisDocument


CITATION_PATTERNS = (
    re.compile(r"\[[0-9,\-–—\s]+\]"),
    re.compile(r"（[^）]{1,60}[，,]\s*(?:19|20)\d{2}[a-z]?）"),
    re.compile(r"\([A-Z][A-Za-z'\-]+(?:\s+et al\.)?,\s*(?:19|20)\d{2}[a-z]?\)"),
)
INTERNAL_EVIDENCE = re.compile(
    r"(?:见|如|根据)?(?:表|图|附录)\s*[A-Za-z一二三四五六七八九十\d]+"
    r"|(?:访谈|编码|实验|调查|问卷|样本|数据|统计|模型|案例|档案|史料)(?:结果|材料|记录|显示|表明)?"
)
STATISTICAL = re.compile(
    r"\b(?:p\s*[<=>]\s*0?\.\d+|t\s*=|F\s*=|χ²|R²|CI\b|OR\b)"
    r"|\d+(?:\.\d+)?%|显著(?:性)?"
)
CAUSAL = re.compile(r"导致|造成|使得|促进|抑制|决定|因果|effect of|causes?|leads? to|results? in", re.I)
RESULT = re.compile(r"结果表明|研究发现|结果显示|分析发现|实验表明|本研究发现|results? (?:show|indicate)", re.I)
SOURCE_CLAIM = re.compile(r"已有研究|学者认为|文献表明|研究指出|研究显示|according to|previous studies", re.I)
POLICY_LEGAL = re.compile(r"法律|法规|条例|政策|规范性文件|司法解释|法条|policy|regulation|statute", re.I)
CONTRIBUTION = re.compile(r"创新|贡献|首次|填补|突破|novel|contribution|first to", re.I)
RESEARCH_QUESTION = re.compile(r"研究问题|试图回答|拟回答|问题是|research question|asks? whether", re.I)
RESEARCH_AIM = re.compile(r"本文旨在|本研究旨在|研究目的|拟探讨|旨在分析|aims? to|purpose of this", re.I)
METHOD_STATEMENT = re.compile(
    r"采用|运用|选取|收集|编码|抽样|访谈了|调查了|实验设计|研究方法|数据来源|we (?:use|employ|collect)",
    re.I,
)
INTERPRETATION = re.compile(r"这意味着|可以解释为|可能表明|本文认为|由此可见|suggests? that|may indicate", re.I)


@dataclass(frozen=True)
class EvidenceLink:
    evidence_id: str
    evidence_type: str
    locator: str
    marker: str
    strength: str


@dataclass(frozen=True)
class ClaimNode:
    claim_id: str
    claim_type: str
    locator: str
    paragraph_id: str
    section_title: str
    text: str
    text_hash: str
    required_evidence: tuple[str, ...]
    evidence_links: tuple[EvidenceLink, ...]
    status: str
    confidence: float
    rationale: str
    severity_hint: str

    def to_dict(self) -> dict:
        payload = asdict(self)
        payload["required_evidence"] = list(self.required_evidence)
        payload["evidence_links"] = [asdict(item) for item in self.evidence_links]
        return payload


def citation_markers(text: str) -> list[str]:
    markers: list[str] = []
    for pattern in CITATION_PATTERNS:
        markers.extend(match.group(0) for match in pattern.finditer(text))
    return markers


def classify_claim(text: str, section_title: str = "") -> tuple[str, tuple[str, ...], str, float]:
    """Classify a sentence without treating every long sentence as a claim."""

    if RESEARCH_QUESTION.search(text):
        return "research_question", (), "P2", 0.96
    if RESEARCH_AIM.search(text):
        return "research_aim", (), "P2", 0.94
    if METHOD_STATEMENT.search(text) and not RESULT.search(text):
        return "method_statement", ("SOURCE_ORIGINAL",), "P1", 0.83
    if CAUSAL.search(text):
        return "causal_claim", ("SOURCE_USER_DATA", "METHOD_CAPABILITY"), "P0", 0.92
    if STATISTICAL.search(text):
        return "statistical_claim", ("SOURCE_USER_DATA", "ANALYSIS_TRACE"), "P0", 0.9
    if RESULT.search(text):
        return "result_claim", ("SOURCE_USER_DATA",), "P0", 0.9
    if SOURCE_CLAIM.search(text):
        return "literature_claim", ("SOURCE_REFERENCE",), "P1", 0.9
    if POLICY_LEGAL.search(text):
        return "policy_legal_claim", ("SOURCE_REFERENCE", "SOURCE_PUBLIC_FACT"), "P1", 0.78
    if CONTRIBUTION.search(text):
        return "contribution_claim", ("ARGUMENT_CHAIN",), "P1", 0.85
    if INTERPRETATION.search(text):
        return "interpretive_claim", ("SOURCE_ORIGINAL", "SOURCE_USER_DATA"), "P1", 0.74
    if re.search(r"表明|说明|证明|发现|影响|相关|高于|低于|增加|降低", text):
        return "general_factual_claim", ("SOURCE_REFERENCE", "SOURCE_USER_DATA"), "P1", 0.7
    return "non_claim", (), "P2", 0.9


def _links(paragraph: DocumentParagraph) -> tuple[EvidenceLink, ...]:
    links: list[EvidenceLink] = []
    for index, marker in enumerate(citation_markers(paragraph.text), start=1):
        links.append(
            EvidenceLink(
                evidence_id=f"EV-{paragraph.paragraph_id}-REF-{index}",
                evidence_type="SOURCE_REFERENCE",
                locator=paragraph.locator,
                marker=marker,
                strength="marker_only",
            )
        )
    for index, match in enumerate(INTERNAL_EVIDENCE.finditer(paragraph.text), start=1):
        context = paragraph.text[max(0, match.start() - 10) : min(len(paragraph.text), match.end() + 8)]
        if re.search(r"未提供|尚未|尚待|没有|缺少|不足|无法", context):
            continue
        links.append(
            EvidenceLink(
                evidence_id=f"EV-{paragraph.paragraph_id}-INT-{index}",
                evidence_type="SOURCE_USER_DATA",
                locator=paragraph.locator,
                marker=match.group(0),
                strength="candidate_internal",
            )
        )
    return tuple(links)


def _support_status(
    claim_type: str,
    required: tuple[str, ...],
    links: tuple[EvidenceLink, ...],
) -> tuple[str, str]:
    if not required:
        return "not_applicable", "研究问题或研究目的本身通常不要求句内引用。"
    present = {link.evidence_type for link in links}
    if claim_type == "method_statement":
        return "supported_by_original", "方法陈述由作者原文承载，仍需在方法完整性审查中核验。"
    if claim_type in {"causal_claim", "statistical_claim"}:
        if "SOURCE_USER_DATA" in present:
            return "partially_supported", "检测到内部证据标记，但仍需核验研究设计或分析过程。"
        return "unresolved", "强结果或因果主张未定位到数据、表图或分析链。"
    if present.intersection(required):
        return "partially_supported", "检测到候选证据标记；引用存在不代表内容已经支持该主张。"
    return "unresolved", "未在该主张附近定位到所需证据标记。"


def split_sentences(text: str) -> Iterable[str]:
    for sentence in re.split(r"(?<=[。！？!?；;])\s*", text):
        value = sentence.strip()
        if value:
            yield value


def build_claim_graph(document: ThesisDocument) -> dict:
    claims: list[ClaimNode] = []
    claim_index = 1
    for paragraph in document.paragraphs:
        if paragraph.heading_level is not None:
            continue
        links = _links(paragraph)
        for sentence in split_sentences(paragraph.text):
            claim_type, required, severity, confidence = classify_claim(sentence, paragraph.section_title)
            if claim_type == "non_claim":
                continue
            status, rationale = _support_status(claim_type, required, links)
            claims.append(
                ClaimNode(
                    claim_id=f"CLM-{claim_index:05d}",
                    claim_type=claim_type,
                    locator=paragraph.locator,
                    paragraph_id=paragraph.paragraph_id,
                    section_title=paragraph.section_title,
                    text=sentence,
                    text_hash=paragraph.text_hash,
                    required_evidence=required,
                    evidence_links=links,
                    status=status,
                    confidence=confidence,
                    rationale=rationale,
                    severity_hint=severity,
                )
            )
            claim_index += 1
    unresolved = [item for item in claims if item.status == "unresolved"]
    return {
        "schema_version": "4.0",
        "source": document.source,
        "source_hash": document.source_hash,
        "claim_count": len(claims),
        "unresolved_count": len(unresolved),
        "claims": [item.to_dict() for item in claims],
        "limits": [
            "本地图谱只确认候选证据是否可定位，不声称引用内容已与主张语义一致。",
            "因果、统计、法律和医学主张必须由方法专家或语义评审再次核验。",
        ],
    }
