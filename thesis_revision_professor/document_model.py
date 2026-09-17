"""Stable, evidence-oriented representation of thesis source documents."""

from __future__ import annotations

import hashlib
import json
import re
import zipfile
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterator
from xml.etree import ElementTree as ET


W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
W14_NS = "http://schemas.microsoft.com/office/word/2010/wordml"
W = f"{{{W_NS}}}"
W14 = f"{{{W14_NS}}}"


def text_hash(text: str) -> str:
    normalized = re.sub(r"\s+", " ", text).strip()
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def fallback_paragraph_id(index: int, scope: str = "") -> str:
    """Deterministic paraId for paragraphs lacking w14:paraId.

    Derived from the enumeration index only (never from text, which patches
    modify), and matches the value docx_patch injects on write-back for the
    main document part, so a paragraph keeps the same locator identity across
    the review → revise round. Non-main parts pass a scope prefix so their
    fallback ids never collide with document.xml ids.
    """
    return hashlib.sha256(f"{scope}p{index}|0|".encode("utf-8")).hexdigest()[:8].upper()


def heading_level(text: str, style: str = "") -> int | None:
    match = re.search(r"heading\s*([1-6])", style, flags=re.I)
    if match:
        return int(match.group(1))
    if re.match(r"^第[一二三四五六七八九十百\d]+[章节篇]\s*", text):
        return 1
    numeric = re.match(r"^(\d+(?:\.\d+){0,5})[、.\s]", text)
    if numeric:
        return min(numeric.group(1).count(".") + 1, 6)
    canonical = text.strip().lower()
    if canonical in {
        "摘要",
        "abstract",
        "参考文献",
        "references",
        "致谢",
        "acknowledgements",
        "附录",
        "appendix",
    }:
        return 1
    return None


def paragraph_text(node: ET.Element) -> str:
    return "".join(child.text or "" for child in node.iter(f"{W}t")).strip()


def paragraph_style(node: ET.Element) -> str:
    ppr = node.find(f"{W}pPr")
    if ppr is None:
        return ""
    pstyle = ppr.find(f"{W}pStyle")
    return pstyle.attrib.get(f"{W}val", "") if pstyle is not None else ""


def has_complex_content(node: ET.Element) -> bool:
    guarded = {
        f"{W}drawing",
        f"{W}object",
        f"{W}fldChar",
        f"{W}instrText",
        f"{W}footnoteReference",
        f"{W}endnoteReference",
    }
    return any(child.tag in guarded for child in node.iter())


def iter_paragraph_nodes(root: ET.Element) -> Iterator[tuple[ET.Element, str, bool]]:
    """Yield paragraphs in document order with an OOXML path and table flag."""

    def walk(node: ET.Element, path: str, in_table: bool) -> Iterator[tuple[ET.Element, str, bool]]:
        for index, child in enumerate(list(node)):
            child_path = f"{path}/{index}"
            child_in_table = in_table or child.tag == f"{W}tbl"
            if child.tag == f"{W}p":
                yield child, child_path, child_in_table
                continue
            yield from walk(child, child_path, child_in_table)

    yield from walk(root, "", False)


@dataclass(frozen=True)
class DocumentParagraph:
    index: int
    locator: str
    paragraph_id: str
    ooxml_path: str
    text: str
    text_hash: str
    style: str
    heading_level: int | None
    section_title: str
    in_table: bool
    has_complex_content: bool
    has_stable_locator: bool


@dataclass(frozen=True)
class ThesisDocument:
    source: str
    source_hash: str
    format: str
    paragraphs: tuple[DocumentParagraph, ...]
    package_parts: tuple[str, ...]
    media_parts: tuple[str, ...]
    layout: dict

    def to_dict(self) -> dict:
        return {
            "schema_version": "4.0",
            "source": self.source,
            "source_hash": self.source_hash,
            "format": self.format,
            "paragraph_count": len(self.paragraphs),
            "package_parts": list(self.package_parts),
            "media_parts": list(self.media_parts),
            "layout": self.layout,
            "paragraphs": [asdict(item) for item in self.paragraphs],
        }

    def paragraph_by_locator(self, locator: str) -> DocumentParagraph | None:
        return next((item for item in self.paragraphs if item.locator == locator), None)


def _source_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_docx(path: str | Path) -> ThesisDocument:
    source = Path(path)
    aux_part_re = re.compile(r"^word/(footnotes|endnotes)\.xml$|^word/(header|footer)\d*\.xml$")
    with zipfile.ZipFile(source) as archive:
        names = archive.namelist()
        xml_parts = {"word/document.xml": archive.read("word/document.xml")}
        for name in sorted(names):
            if name != "word/document.xml" and aux_part_re.match(name):
                xml_parts[name] = archive.read(name)
        parts = tuple(sorted(names))
        styles_xml = archive.read("word/styles.xml") if "word/styles.xml" in names else None
    layout = _extract_layout(ET.fromstring(xml_parts["word/document.xml"]), styles_xml)
    paragraphs: list[DocumentParagraph] = []
    for part_name in sorted(xml_parts, key=lambda item: (item != "word/document.xml", item)):
        root = ET.fromstring(xml_parts[part_name])
        is_main = part_name == "word/document.xml"
        scope = "" if is_main else part_name
        active_section = ""
        for index, (node, ooxml_path, in_table) in enumerate(iter_paragraph_nodes(root)):
            text = paragraph_text(node)
            if not text:
                continue
            style = paragraph_style(node)
            level = heading_level(text, style) if is_main else None
            if is_main and level is not None:
                active_section = text
            para_id = node.attrib.get(f"{W14}paraId")
            has_stable_locator = para_id is not None
            if not para_id:
                para_id = fallback_paragraph_id(index, scope)
            paragraphs.append(
                DocumentParagraph(
                    index=index,
                    locator=f"{part_name}#para={para_id}",
                    paragraph_id=para_id,
                    ooxml_path=ooxml_path,
                    text=text,
                    text_hash=text_hash(text),
                    style=style,
                    heading_level=level,
                    section_title=active_section,
                    in_table=in_table,
                    has_complex_content=has_complex_content(node),
                    has_stable_locator=has_stable_locator,
                )
            )
    return ThesisDocument(
        source=str(source),
        source_hash=_source_hash(source),
        format="docx",
        paragraphs=tuple(paragraphs),
        package_parts=parts,
        media_parts=tuple(name for name in parts if name.startswith("word/media/")),
        layout=layout,
    )


def _extract_layout(document_root: ET.Element, styles_xml: bytes | None) -> dict:
    """Pull default font/size from styles.xml docDefaults and per-section margins."""

    layout: dict = {
        "default_east_asia_font": None,
        "default_size_pt": None,
        "section_margins_twips": [],
    }
    if styles_xml:
        try:
            styles_root = ET.fromstring(styles_xml)
        except ET.ParseError:
            styles_root = None
        if styles_root is not None:
            rpr = styles_root.find(f"{W}docDefaults/{W}rPrDefault/{W}rPr")
            if rpr is not None:
                rfonts = rpr.find(f"{W}rFonts")
                if rfonts is not None:
                    layout["default_east_asia_font"] = rfonts.attrib.get(f"{W}eastAsia") or None
                size = rpr.find(f"{W}sz")
                value = size.attrib.get(f"{W}val", "") if size is not None else ""
                if value.isdigit():
                    layout["default_size_pt"] = int(value) / 2
    for sect in document_root.iter(f"{W}sectPr"):
        pgmar = sect.find(f"{W}pgMar")
        if pgmar is None:
            continue
        margins = {}
        for side in ("top", "right", "bottom", "left"):
            value = pgmar.attrib.get(f"{W}{side}", "")
            if value.lstrip("-").isdigit():
                margins[side] = int(value)
        layout["section_margins_twips"].append(margins)
    return layout


def load_text(path: str | Path) -> ThesisDocument:
    source = Path(path)
    text = source.read_text(encoding="utf-8", errors="ignore")
    paragraphs: list[DocumentParagraph] = []
    active_section = ""
    for index, raw in enumerate(text.splitlines()):
        value = raw.strip()
        if not value:
            continue
        level = heading_level(value)
        if level is not None:
            active_section = value
        digest = text_hash(value)
        paragraphs.append(
            DocumentParagraph(
                index=index,
                locator=f"text#paragraph={index};hash={digest[:8]}",
                paragraph_id=f"text-{index}",
                ooxml_path="",
                text=value,
                text_hash=digest,
                style="",
                heading_level=level,
                section_title=active_section,
                in_table=False,
                has_complex_content=False,
                has_stable_locator=False,
            )
        )
    return ThesisDocument(
        source=str(source),
        source_hash=_source_hash(source),
        format=source.suffix.lower().lstrip(".") or "text",
        paragraphs=tuple(paragraphs),
        package_parts=(),
        media_parts=(),
        layout={"default_east_asia_font": None, "default_size_pt": None, "section_margins_twips": []},
    )


def load_document(path: str | Path) -> ThesisDocument:
    source = Path(path)
    if source.suffix.lower() == ".docx":
        return load_docx(source)
    if source.suffix.lower() == ".json":
        payload = json.loads(source.read_text(encoding="utf-8"))
        if isinstance(payload, dict) and payload.get("source"):
            candidate = Path(payload["source"])
            if candidate.exists():
                return load_document(candidate)
    return load_text(source)
