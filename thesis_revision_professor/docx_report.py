"""Dependency-free, Chinese-capable DOCX report writer."""

from __future__ import annotations

import html
import re
import zipfile
from pathlib import Path


W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
TOTAL_WIDTH = 9360


def _run(text: str, *, bold: bool = False) -> str:
    properties = (
        '<w:rPr><w:rFonts w:ascii="Arial" w:hAnsi="Arial" w:eastAsia="Songti SC" w:cs="Arial"/>'
        '<w:lang w:val="en-US" w:eastAsia="zh-CN"/>'
        f"{'<w:b/>' if bold else ''}</w:rPr>"
    )
    space = ' xml:space="preserve"' if text.startswith(" ") or text.endswith(" ") else ""
    return f"<w:r>{properties}<w:t{space}>{html.escape(text)}</w:t></w:r>"


def _paragraph(text: str, style: str = "", *, bold: bool = False) -> str:
    ppr = f'<w:pPr><w:pStyle w:val="{style}"/></w:pPr>' if style else ""
    return f"<w:p>{ppr}{_run(text, bold=bold)}</w:p>"


def _column_widths(count: int) -> list[int]:
    presets = {
        1: [TOTAL_WIDTH],
        2: [2700, 6660],
        3: [1800, 3000, 4560],
        4: [1700, 2700, 1900, 3060],
        5: [1450, 2500, 1550, 2900, 960],
        6: [1100, 1500, 1500, 2100, 1500, 1660],
    }
    if count in presets:
        return presets[count]
    width = TOTAL_WIDTH // max(count, 1)
    return [width] * count


def _table(rows: list[list[str]]) -> str:
    widths = _column_widths(max((len(row) for row in rows), default=1))
    xml_rows = []
    for row_index, row in enumerate(rows):
        cells = []
        for index, cell in enumerate(row):
            width = widths[min(index, len(widths) - 1)]
            shading = '<w:shd w:val="clear" w:fill="D9EAF7"/>' if row_index == 0 else ""
            tc_pr = (
                f'<w:tcPr><w:tcW w:w="{width}" w:type="dxa"/>'
                '<w:tcMar><w:top w:w="80" w:type="dxa"/><w:left w:w="100" w:type="dxa"/>'
                '<w:bottom w:w="80" w:type="dxa"/><w:right w:w="100" w:type="dxa"/></w:tcMar>'
                f"{shading}</w:tcPr>"
            )
            cells.append(f"<w:tc>{tc_pr}{_paragraph(str(cell), bold=row_index == 0)}</w:tc>")
        xml_rows.append("<w:tr>" + "".join(cells) + "</w:tr>")
    borders = "".join(f'<w:{side} w:val="single" w:sz="4" w:color="B7C9D6"/>' for side in ("top", "left", "bottom", "right", "insideH", "insideV"))
    grid = "".join(f'<w:gridCol w:w="{width}"/>' for width in widths)
    return (
        '<w:tbl><w:tblPr><w:tblW w:w="9360" w:type="dxa"/><w:tblLayout w:type="fixed"/>'
        f"<w:tblBorders>{borders}</w:tblBorders></w:tblPr><w:tblGrid>{grid}</w:tblGrid>{''.join(xml_rows)}</w:tbl>"
    )


def markdown_to_body(title: str, body: str) -> str:
    output = [_paragraph(title, "Title")]
    lines = body.splitlines()
    index = 0
    while index < len(lines):
        line = lines[index].rstrip()
        if not line:
            index += 1
            continue
        if line.startswith("|") and index + 1 < len(lines) and set(lines[index + 1].replace("|", "").replace(" ", "")) <= {"-", ":"}:
            rows = []
            while index < len(lines) and lines[index].startswith("|"):
                if "---" not in lines[index]:
                    rows.append([cell.strip() for cell in lines[index].strip("|").split("|")])
                index += 1
            output.append(_table(rows))
            continue
        if line.startswith("### "):
            output.append(_paragraph(line[4:], "Heading3"))
        elif line.startswith("## "):
            output.append(_paragraph(line[3:], "Heading2"))
        elif line.startswith("# "):
            output.append(_paragraph(line[2:], "Heading1"))
        elif line.startswith("- "):
            output.append(_paragraph("• " + line[2:]))
        elif re.match(r"^\d+\.\s", line):
            output.append(_paragraph(line))
        elif line.startswith("> "):
            output.append(_paragraph(line[2:], "Quote"))
        else:
            output.append(_paragraph(line))
        index += 1
    return "".join(output)


def _styles_xml() -> str:
    return f'''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:styles xmlns:w="{W_NS}">
  <w:docDefaults><w:rPrDefault><w:rPr><w:rFonts w:ascii="Arial" w:hAnsi="Arial" w:eastAsia="Songti SC" w:cs="Arial"/><w:lang w:val="en-US" w:eastAsia="zh-CN"/><w:sz w:val="22"/></w:rPr></w:rPrDefault><w:pPrDefault><w:pPr><w:spacing w:after="120" w:line="360" w:lineRule="auto"/></w:pPr></w:pPrDefault></w:docDefaults>
  <w:style w:type="paragraph" w:default="1" w:styleId="Normal"><w:name w:val="Normal"/></w:style>
  <w:style w:type="paragraph" w:styleId="Title"><w:name w:val="Title"/><w:basedOn w:val="Normal"/><w:pPr><w:jc w:val="center"/><w:spacing w:after="360"/></w:pPr><w:rPr><w:b/><w:sz w:val="36"/><w:rFonts w:ascii="Arial" w:hAnsi="Arial" w:eastAsia="STHeiti"/></w:rPr></w:style>
  <w:style w:type="paragraph" w:styleId="Heading1"><w:name w:val="heading 1"/><w:basedOn w:val="Normal"/><w:pPr><w:spacing w:before="300" w:after="180"/></w:pPr><w:rPr><w:b/><w:sz w:val="30"/><w:rFonts w:eastAsia="STHeiti"/></w:rPr></w:style>
  <w:style w:type="paragraph" w:styleId="Heading2"><w:name w:val="heading 2"/><w:basedOn w:val="Normal"/><w:pPr><w:spacing w:before="240" w:after="120"/></w:pPr><w:rPr><w:b/><w:sz w:val="26"/><w:rFonts w:eastAsia="STHeiti"/></w:rPr></w:style>
  <w:style w:type="paragraph" w:styleId="Heading3"><w:name w:val="heading 3"/><w:basedOn w:val="Normal"/><w:pPr><w:spacing w:before="180" w:after="90"/></w:pPr><w:rPr><w:b/><w:sz w:val="24"/><w:rFonts w:eastAsia="STHeiti"/></w:rPr></w:style>
  <w:style w:type="paragraph" w:styleId="Quote"><w:name w:val="Quote"/><w:basedOn w:val="Normal"/><w:pPr><w:ind w:left="480"/><w:spacing w:before="80" w:after="120"/></w:pPr><w:rPr><w:color w:val="5B6573"/></w:rPr></w:style>
</w:styles>'''


def write_docx(path: str | Path, title: str, body: str) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    document = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        f'<w:document xmlns:w="{W_NS}">'
        f'<w:body>{markdown_to_body(title, body)}<w:sectPr><w:pgSz w:w="11906" w:h="16838"/>'
        '<w:pgMar w:top="1440" w:right="1440" w:bottom="1440" w:left="1440"/></w:sectPr></w:body></w:document>'
    )
    content_types = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
        '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
        '<Default Extension="xml" ContentType="application/xml"/>'
        '<Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>'
        '<Override PartName="/word/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.styles+xml"/>'
        "</Types>"
    )
    root_rels = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>'
        "</Relationships>"
    )
    document_rels = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>'
        "</Relationships>"
    )
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", content_types)
        archive.writestr("_rels/.rels", root_rels)
        archive.writestr("word/document.xml", document)
        archive.writestr("word/styles.xml", _styles_xml())
        archive.writestr("word/_rels/document.xml.rels", document_rels)
