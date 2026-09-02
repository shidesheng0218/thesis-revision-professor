"""Loss-minimizing DOCX patches with stable locators and optional tracked changes."""

from __future__ import annotations

import copy
import datetime as dt
import io
import re
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

from .document_model import W, W14, has_complex_content, iter_paragraph_nodes, paragraph_text, text_hash


REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"
CT_NS = "http://schemas.openxmlformats.org/package/2006/content-types"
XML_NS = "http://www.w3.org/XML/1998/namespace"

ET.register_namespace("w", W.removeprefix("{").removesuffix("}"))
ET.register_namespace("w14", W14.removeprefix("{").removesuffix("}"))


def _paragraph_map(root: ET.Element) -> tuple[dict[str, ET.Element], dict[str, ET.Element], dict[str, list[ET.Element]]]:
    by_locator: dict[str, ET.Element] = {}
    by_hash: dict[str, list[ET.Element]] = {}
    by_text: dict[str, list[ET.Element]] = {}
    for index, (node, _path, _in_table) in enumerate(iter_paragraph_nodes(root)):
        text = paragraph_text(node)
        if not text:
            continue
        para_id = node.attrib.get(f"{W14}paraId") or f"p{index:06d}"
        locator = f"word/document.xml#para={para_id};index={index}"
        by_locator[locator] = node
        by_hash.setdefault(text_hash(text), []).append(node)
        by_text.setdefault(text, []).append(node)
    return by_locator, by_hash, by_text


def _first_run_properties(node: ET.Element) -> ET.Element | None:
    run = node.find(f"{W}r")
    if run is None:
        return None
    rpr = run.find(f"{W}rPr")
    return copy.deepcopy(rpr) if rpr is not None else None


def _clear_content(node: ET.Element) -> None:
    ppr = node.find(f"{W}pPr")
    for child in list(node):
        if child is not ppr:
            node.remove(child)


def _run(text: str, rpr: ET.Element | None, deletion: bool = False) -> ET.Element:
    run = ET.Element(f"{W}r")
    if rpr is not None:
        run.append(copy.deepcopy(rpr))
    tag = f"{W}delText" if deletion else f"{W}t"
    value = ET.SubElement(run, tag)
    if text.startswith(" ") or text.endswith(" "):
        value.set(f"{{{XML_NS}}}space", "preserve")
    value.text = text
    return run


def _replace_paragraph(node: ET.Element, replacement: str, tracked: bool, change_id: int) -> None:
    original = paragraph_text(node)
    rpr = _first_run_properties(node)
    _clear_content(node)
    if not tracked:
        node.append(_run(replacement, rpr))
        return
    timestamp = dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    deletion = ET.SubElement(
        node,
        f"{W}del",
        {f"{W}id": str(change_id), f"{W}author": "thesis-revision-professor", f"{W}date": timestamp},
    )
    deletion.append(_run(original, rpr, deletion=True))
    insertion = ET.SubElement(
        node,
        f"{W}ins",
        {f"{W}id": str(change_id + 1), f"{W}author": "thesis-revision-professor", f"{W}date": timestamp},
    )
    insertion.append(_run(replacement, rpr))


def _comment_text(item: dict) -> str:
    parts = [str(item.get("problem", "需要作者复核。"))]
    if item.get("risk"):
        parts.append(f"风险：{item['risk']}")
    if item.get("acceptance_test"):
        parts.append(f"验收：{item['acceptance_test']}")
    if item.get("evidence_ids"):
        parts.append("证据：" + ", ".join(map(str, item["evidence_ids"])))
    return "\n".join(parts)


def _add_comment_part(parts: dict[str, bytes], comment_id: int, text: str) -> None:
    comments_name = "word/comments.xml"
    if comments_name in parts:
        root = ET.fromstring(parts[comments_name])
    else:
        root = ET.Element(f"{W}comments")
    timestamp = dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    comment = ET.SubElement(root, f"{W}comment", {f"{W}id": str(comment_id), f"{W}author": "thesis-revision-professor", f"{W}date": timestamp})
    paragraph = ET.SubElement(comment, f"{W}p")
    paragraph.append(_run(text, None))
    parts[comments_name] = ET.tostring(root, encoding="utf-8", xml_declaration=True)


def _enable_comments(parts: dict[str, bytes]) -> None:
    content_types = ET.fromstring(parts["[Content_Types].xml"])
    if not any(node.attrib.get("PartName") == "/word/comments.xml" for node in content_types.findall(f"{{{CT_NS}}}Override")):
        ET.SubElement(content_types, f"{{{CT_NS}}}Override", {"PartName": "/word/comments.xml", "ContentType": "application/vnd.openxmlformats-officedocument.wordprocessingml.comments+xml"})
        parts["[Content_Types].xml"] = ET.tostring(content_types, encoding="utf-8", xml_declaration=True)
    rel_name = "word/_rels/document.xml.rels"
    rels = ET.fromstring(parts[rel_name])
    comments_type = "http://schemas.openxmlformats.org/officeDocument/2006/relationships/comments"
    if not any(node.attrib.get("Type") == comments_type for node in rels.findall(f"{{{REL_NS}}}Relationship")):
        used_ids = {node.attrib.get("Id") for node in rels.findall(f"{{{REL_NS}}}Relationship")}
        index = 1
        while f"rId{index}" in used_ids:
            index += 1
        ET.SubElement(rels, f"{{{REL_NS}}}Relationship", {"Id": f"rId{index}", "Type": comments_type, "Target": "comments.xml"})
        parts[rel_name] = ET.tostring(rels, encoding="utf-8", xml_declaration=True)


def _next_comment_id(root: ET.Element) -> int:
    values = []
    for node in root.iter(f"{W}commentRangeStart"):
        value = node.attrib.get(f"{W}id", "")
        if value.isdigit():
            values.append(int(value))
    return max(values, default=-1) + 1


def _annotate_paragraph(node: ET.Element, comment_id: int) -> None:
    ppr = node.find(f"{W}pPr")
    children = [child for child in list(node) if child is not ppr]
    for child in children:
        node.remove(child)
    start = ET.Element(f"{W}commentRangeStart", {f"{W}id": str(comment_id)})
    end = ET.Element(f"{W}commentRangeEnd", {f"{W}id": str(comment_id)})
    reference = ET.Element(f"{W}r")
    reference.append(ET.Element(f"{W}commentReference", {f"{W}id": str(comment_id)}))
    if ppr is not None:
        node.append(ppr)
    node.append(start)
    for child in children:
        node.append(child)
    node.append(end)
    node.append(reference)


def _resolve_node(
    item: dict,
    by_locator: dict[str, ET.Element],
    by_hash: dict[str, list[ET.Element]],
    by_text: dict[str, list[ET.Element]],
) -> tuple[ET.Element | None, str]:
    locator = item.get("locator") or item.get("location_hint")
    if locator in by_locator:
        return by_locator[locator], "locator"
    target_hash = item.get("target_hash")
    if target_hash and len(by_hash.get(target_hash, [])) == 1:
        return by_hash[target_hash][0], "hash"
    target = item.get("target_text", "")
    if target and len(by_text.get(target, [])) == 1:
        return by_text[target][0], "exact_text"
    containing = [node for text, nodes in by_text.items() if target and target in text for node in nodes]
    if len(containing) == 1:
        return containing[0], "unique_substring"
    return None, "not_unique_or_missing"


def _next_change_id(root: ET.Element) -> int:
    ids = []
    for tag in (f"{W}ins", f"{W}del"):
        for node in root.iter(tag):
            value = node.attrib.get(f"{W}id", "")
            if value.isdigit():
                ids.append(int(value))
    value = max(ids, default=0) + 1
    return value if value % 2 else value + 1


def _enable_tracking(parts: dict[str, bytes]) -> None:
    settings_name = "word/settings.xml"
    if settings_name in parts:
        root = ET.fromstring(parts[settings_name])
    else:
        root = ET.Element(f"{W}settings")
    if root.find(f"{W}trackRevisions") is None:
        root.insert(0, ET.Element(f"{W}trackRevisions"))
    parts[settings_name] = ET.tostring(root, encoding="utf-8", xml_declaration=True)

    content_types = ET.fromstring(parts["[Content_Types].xml"])
    override_exists = any(
        node.attrib.get("PartName") == "/word/settings.xml" for node in content_types.findall(f"{{{CT_NS}}}Override")
    )
    if not override_exists:
        ET.SubElement(
            content_types,
            f"{{{CT_NS}}}Override",
            {
                "PartName": "/word/settings.xml",
                "ContentType": "application/vnd.openxmlformats-officedocument.wordprocessingml.settings+xml",
            },
        )
        parts["[Content_Types].xml"] = ET.tostring(content_types, encoding="utf-8", xml_declaration=True)

    rel_name = "word/_rels/document.xml.rels"
    if rel_name in parts:
        rels = ET.fromstring(parts[rel_name])
    else:
        rels = ET.Element(f"{{{REL_NS}}}Relationships")
    settings_type = "http://schemas.openxmlformats.org/officeDocument/2006/relationships/settings"
    if not any(node.attrib.get("Type") == settings_type for node in rels.findall(f"{{{REL_NS}}}Relationship")):
        used_ids = {node.attrib.get("Id") for node in rels.findall(f"{{{REL_NS}}}Relationship")}
        index = 1
        while f"rId{index}" in used_ids:
            index += 1
        ET.SubElement(
            rels,
            f"{{{REL_NS}}}Relationship",
            {"Id": f"rId{index}", "Type": settings_type, "Target": "settings.xml"},
        )
        parts[rel_name] = ET.tostring(rels, encoding="utf-8", xml_declaration=True)


def patch_docx(
    source: str | Path,
    output: str | Path,
    plan: dict,
    *,
    tracked: bool = True,
    mark_unconfirmed: bool = True,
    comments: bool = False,
) -> dict:
    source = Path(source)
    output = Path(output)
    with zipfile.ZipFile(source) as archive:
        parts = {name: archive.read(name) for name in archive.namelist()}
    document_root = ET.fromstring(parts["word/document.xml"])
    by_locator, by_hash, by_text = _paragraph_map(document_root)
    next_id = _next_change_id(document_root)
    next_comment_id = _next_comment_id(document_root)
    comments_added = 0
    results = []
    changed_nodes: set[int] = set()
    marker = " [需作者确认：缺少支撑材料]"
    for item in plan.get("items", []):
        patch_mode = item.get("patch_mode", "manual_only")
        should_patch = bool(item.get("confirmed")) or (mark_unconfirmed and patch_mode == "mark_unconfirmed")
        if not should_patch or patch_mode == "manual_only":
            if comments and patch_mode == "manual_only":
                node, resolution = _resolve_node(item, by_locator, by_hash, by_text)
                if node is not None and not has_complex_content(node):
                    _annotate_paragraph(node, next_comment_id)
                    _add_comment_part(parts, next_comment_id, _comment_text(item))
                    next_comment_id += 1
                    comments_added += 1
                    results.append({"id": item.get("id"), "status": "comment_added", "resolution": resolution, "locator": item.get("locator")})
                    continue
            results.append({"id": item.get("id"), "status": "not_applied", "reason": "manual_or_unconfirmed"})
            continue
        node, resolution = _resolve_node(item, by_locator, by_hash, by_text)
        if node is None:
            results.append({"id": item.get("id"), "status": "blocked", "reason": resolution})
            continue
        if id(node) in changed_nodes:
            results.append({"id": item.get("id"), "status": "blocked", "reason": "paragraph_already_changed"})
            continue
        if has_complex_content(node):
            results.append({"id": item.get("id"), "status": "blocked", "reason": "complex_paragraph_requires_manual_edit"})
            continue
        current = paragraph_text(node)
        target = item.get("target_text", "")
        if target and target not in current:
            results.append({"id": item.get("id"), "status": "blocked", "reason": "target_text_mismatch"})
            continue
        if item.get("confirmed"):
            proposed = item.get("proposed_rewrite", "")
            if not proposed or proposed == target:
                results.append({"id": item.get("id"), "status": "blocked", "reason": "no_concrete_rewrite"})
                continue
            replacement = current.replace(target, proposed, 1) if target else proposed
            status = "applied_confirmed"
        else:
            if marker in current:
                results.append({"id": item.get("id"), "status": "not_applied", "reason": "marker_already_present"})
                continue
            replacement = current.replace(target, target + marker, 1) if target else current + marker
            status = "marked_unconfirmed"
        _replace_paragraph(node, replacement, tracked, next_id)
        if comments:
            _annotate_paragraph(node, next_comment_id)
            _add_comment_part(parts, next_comment_id, _comment_text(item))
            next_comment_id += 1
            comments_added += 1
        next_id += 2
        changed_nodes.add(id(node))
        results.append({"id": item.get("id"), "status": status, "resolution": resolution, "locator": item.get("locator")})
    parts["word/document.xml"] = ET.tostring(document_root, encoding="utf-8", xml_declaration=True)
    if tracked and any(item["status"] in {"applied_confirmed", "marked_unconfirmed"} for item in results):
        _enable_tracking(parts)
    if comments_added:
        _enable_comments(parts)
    output.parent.mkdir(parents=True, exist_ok=True)
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, payload in parts.items():
            archive.writestr(name, payload)
    output.write_bytes(buffer.getvalue())
    return {
        "source": str(source),
        "output": str(output),
        "tracked_changes": tracked,
        "applied_count": sum(item["status"] == "applied_confirmed" for item in results),
        "marked_count": sum(item["status"] == "marked_unconfirmed" for item in results),
        "comments_added": comments_added,
        "blocked_count": sum(item["status"] == "blocked" for item in results),
        "items": results,
    }
