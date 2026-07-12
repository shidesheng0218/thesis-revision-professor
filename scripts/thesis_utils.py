#!/usr/bin/env python3
"""Shared utilities for thesis-revision-professor scripts."""

from __future__ import annotations

import json
import re
import zipfile
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Iterable
from xml.etree import ElementTree as ET

W_NS = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"


@dataclass
class Paragraph:
    index: int
    text: str
    style: str = ""
    level: int | None = None


def read_text(path: str | Path) -> str:
    path = Path(path)
    suffix = path.suffix.lower()
    if suffix == ".docx":
        return "\n".join(p.text for p in read_docx_paragraphs(path) if p.text)
    if suffix == ".json":
        data = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(data, dict) and "paragraphs" in data:
            return "\n".join(p.get("text", "") for p in data["paragraphs"])
        return json.dumps(data, ensure_ascii=False, indent=2)
    return path.read_text(encoding="utf-8")


def read_docx_paragraphs(path: str | Path) -> list[Paragraph]:
    path = Path(path)
    with zipfile.ZipFile(path) as zf:
        xml = zf.read("word/document.xml")
    root = ET.fromstring(xml)
    paragraphs: list[Paragraph] = []
    for idx, node in enumerate(root.iter(f"{W_NS}p")):
        texts = [t.text or "" for t in node.iter(f"{W_NS}t")]
        text = "".join(texts).strip()
        if not text:
            continue
        style = ""
        ppr = node.find(f"{W_NS}pPr")
        if ppr is not None:
            pstyle = ppr.find(f"{W_NS}pStyle")
            if pstyle is not None:
                style = pstyle.attrib.get(f"{W_NS}val", "")
        level = heading_level(text, style)
        paragraphs.append(Paragraph(index=len(paragraphs), text=text, style=style, level=level))
    return paragraphs


def heading_level(text: str, style: str = "") -> int | None:
    style_lower = style.lower()
    m = re.search(r"heading([1-6])", style_lower)
    if m:
        return int(m.group(1))
    cn = re.match(r"^第[一二三四五六七八九十百\d]+[章节篇]\s*", text)
    if cn:
        return 1
    numeric = re.match(r"^(\d+(?:\.\d+){0,5})[、.\s]", text)
    if numeric:
        return min(numeric.group(1).count(".") + 1, 6)
    return None


def paragraphs_to_json(paragraphs: Iterable[Paragraph]) -> dict:
    return {"paragraphs": [asdict(p) for p in paragraphs]}


def write_json(data: object, path: str | Path) -> None:
    Path(path).write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def split_sentences(text: str) -> list[str]:
    parts = re.split(r"(?<=[。！？!?；;])\s*|\n+", text)
    return [p.strip() for p in parts if p.strip()]


def read_json(path: str | Path) -> object:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def looks_like_claim(sentence: str) -> bool:
    markers = [
        "表明", "说明", "证明", "发现", "认为", "因此", "显著", "影响", "促进", "导致",
        "shows", "indicates", "demonstrates", "proves", "therefore", "significant", "impact",
    ]
    return any(m in sentence for m in markers) or len(sentence) > 80


def extract_numbers(text: str) -> list[str]:
    return re.findall(r"(?<![A-Za-z])(?:\d{4}年|\d+(?:\.\d+)?%?|\d+人|\d+份|\d+次|\d+个)(?![A-Za-z])", text)


def extract_years(text: str) -> list[str]:
    return re.findall(r"(?:19|20)\d{2}", text)


def keyword_hits(text: str, markers: list[str]) -> list[str]:
    lower = text.lower()
    return [m for m in markers if m.lower() in lower or m in text]


def priority_rank(priority: str) -> int:
    return {"P0": 0, "P1": 1, "P2": 2}.get(priority, 3)


def risk_rank(risk: str) -> int:
    order = {"pass": 0, "minor revision": 1, "major revision": 2, "high risk": 3}
    return order.get(risk, 9)


def markdown_table(headers: list[str], rows: list[list[object]]) -> str:
    escaped = []
    for row in rows:
        escaped.append([str(cell).replace("\n", "<br>").replace("|", "\\|") for cell in row])
    out = ["| " + " | ".join(headers) + " |", "| " + " | ".join(["---"] * len(headers)) + " |"]
    out.extend("| " + " | ".join(row) + " |" for row in escaped)
    return "\n".join(out)


def citation_patterns(text: str) -> list[str]:
    patterns = []
    patterns.extend(re.findall(r"\[[0-9,\-\s]+\]", text))
    patterns.extend(re.findall(r"（[^）]{1,40}，\s*\d{4}）", text))
    patterns.extend(re.findall(r"\([A-Z][A-Za-z\-]+(?:\s+et al\.)?,\s*\d{4}\)", text))
    return patterns


def _paragraph_xml(text: str, style_name: str = "") -> str:
    escaped = (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )
    style = f'<w:pPr><w:pStyle w:val="{style_name}"/></w:pPr>' if style_name else ""
    return f"<w:p>{style}<w:r><w:t>{escaped}</w:t></w:r></w:p>"


def _table_xml(rows: list[list[str]]) -> str:
    cells = []
    for row in rows:
        tcells = []
        for cell in row:
            tcells.append(f"<w:tc><w:tcPr><w:tcW w:w=\"2400\" w:type=\"dxa\"/></w:tcPr>{_paragraph_xml(str(cell))}</w:tc>")
        cells.append("<w:tr>" + "".join(tcells) + "</w:tr>")
    return "<w:tbl><w:tblPr><w:tblBorders><w:top w:val=\"single\" w:sz=\"4\"/><w:left w:val=\"single\" w:sz=\"4\"/><w:bottom w:val=\"single\" w:sz=\"4\"/><w:right w:val=\"single\" w:sz=\"4\"/><w:insideH w:val=\"single\" w:sz=\"4\"/><w:insideV w:val=\"single\" w:sz=\"4\"/></w:tblBorders></w:tblPr>" + "".join(cells) + "</w:tbl>"


def _markdown_blocks_to_docx_xml(title: str, body: str) -> str:
    document_body = [_paragraph_xml(title, "Title")]
    lines = body.splitlines()
    i = 0
    while i < len(lines):
        line = lines[i].rstrip()
        if not line:
            i += 1
            continue
        if line.startswith("|") and i + 1 < len(lines) and set(lines[i + 1].replace("|", "").replace(" ", "")) <= {"-", ":"}:
            table_rows = []
            while i < len(lines) and lines[i].startswith("|"):
                if "---" not in lines[i]:
                    table_rows.append([c.strip() for c in lines[i].strip("|").split("|")])
                i += 1
            document_body.append(_table_xml(table_rows))
            continue
        if line.startswith("### "):
            document_body.append(_paragraph_xml(line[4:], "Heading3"))
        elif line.startswith("## "):
            document_body.append(_paragraph_xml(line[3:], "Heading2"))
        elif line.startswith("# "):
            document_body.append(_paragraph_xml(line[2:], "Heading1"))
        elif line.startswith("- "):
            document_body.append(_paragraph_xml("• " + line[2:]))
        elif re.match(r"^\d+\.\s", line):
            document_body.append(_paragraph_xml(line))
        else:
            document_body.append(_paragraph_xml(line))
        i += 1
    return "".join(document_body)


def simple_docx(path: str | Path, title: str, body: str) -> None:
    """Create a valid dependency-free DOCX with basic headings and tables."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    document_body = _markdown_blocks_to_docx_xml(title, body)
    document_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
        f"<w:body>{document_body}<w:sectPr/></w:body></w:document>"
    )
    content_types = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
        '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
        '<Default Extension="xml" ContentType="application/xml"/>'
        '<Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>'
        "</Types>"
    )
    rels = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>'
        "</Relationships>"
    )
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("[Content_Types].xml", content_types)
        zf.writestr("_rels/.rels", rels)
        zf.writestr("word/document.xml", document_xml)
