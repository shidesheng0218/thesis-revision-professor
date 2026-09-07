#!/usr/bin/env python3
"""Dependency-free v3 acceptance tests."""

from __future__ import annotations

import json
import re
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from thesis_revision_professor.document_model import W14_NS, W_NS, load_document
from thesis_revision_professor.docx_patch import patch_docx
from thesis_revision_professor.docx_report import write_docx
from thesis_revision_professor.profiles import load_profile, profile_audit
from thesis_revision_professor.state_machine import advance_state
from thesis_revision_professor.workflow import corpus_workflow, defense_workflow, deep_review_workflow, review_workflow, revise_workflow, status_summary


MC_NS = "http://schemas.openxmlformats.org/markup-compatibility/2006"


SAMPLE = """# 摘要

本文旨在分析某类教学活动与学生学习体验之间的关系。

# 第一章 绪论

本文试图回答：某类教学活动如何影响学生学习体验。

# 第二章 文献综述

已有研究表明，教学设计与学生参与度相关[1]。

# 第三章 研究方法

本研究采用访谈和案例分析，研究对象和编码流程尚待补充。

# 第四章 结果

本文认为该活动显著提升学习体验，但尚未提供数据表或访谈证据。

# 第五章 结论

现有材料不足以支持普遍性结论。

# 参考文献

[1] 张三. 教学设计研究[J]. 教育研究, 2024(1): 1-10.
"""


def add_media_part(path: Path) -> None:
    with zipfile.ZipFile(path, "a", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("word/media/image1.png", b"synthetic-media-fixture")


def read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> None:
    with tempfile.TemporaryDirectory() as temp_dir:
        temp = Path(temp_dir)
        source = temp / "source.docx"
        write_docx(source, "伪论文", SAMPLE)
        add_media_part(source)
        with zipfile.ZipFile(source) as archive:
            assert "word/styles.xml" in archive.namelist()
            assert "Songti SC" in archive.read("word/styles.xml").decode("utf-8")

        review_dir = temp / "review"
        review_workflow(source, review_dir, level="master", discipline="education", method="qualitative")
        assert (review_dir / "claim_evidence_ledger.json").exists()
        assert (review_dir / "consistency_matrix.json").exists()
        deep_dir = temp / "deep"
        deep = deep_review_workflow(source, deep_dir, level="master", discipline="education", method="qualitative")
        assert deep["status"] == "awaiting_semantic_review"
        assert read(deep_dir / "loop_trace.json")["max_rounds"] == 5
        graph = read(review_dir / "claim_evidence_graph.json")
        questions = [item for item in graph["claims"] if item["claim_type"] in {"research_question", "research_aim"}]
        assert questions and all(item["status"] == "not_applicable" for item in questions)
        statistical = [item for item in graph["claims"] if item["claim_type"] == "statistical_claim"]
        assert statistical and statistical[0]["status"] == "unresolved"

        citations = read(review_dir / "citation_audit.json")
        assert citations["citation_count"] == 1
        assert citations["numbered_reference_count"] == 1
        assert not citations["risks"]

        strategy = read(review_dir / "selected_strategy.json")
        assert strategy["discipline"]["key"] == "education"
        assert strategy["method"]["key"] == "qualitative"
        cs_dir = temp / "computer-science-review"
        review_workflow(source, cs_dir, discipline="computer-science", method="machine-learning")
        cs_rules = {item["rule_id"] for item in read(cs_dir / "professor_panel.json")["issues"]}
        education_rules = {item["rule_id"] for item in read(review_dir / "professor_panel.json")["issues"]}
        assert cs_rules != education_rules
        with zipfile.ZipFile(review_dir / "修改说明与盲审风险报告.docx") as archive:
            report_xml = archive.read("word/document.xml").decode("utf-8")
        assert "统计性结果主张" in report_xml

        assert source.read_bytes() == (review_dir / "论文修改稿.docx").read_bytes()

        revise_dir = temp / "revise"
        revise_workflow(
            source,
            review_dir / "revision_plan.json",
            revise_dir,
            state_path=review_dir / "revision_state.json",
            comments=True,
        )
        regression = read(revise_dir / "diff_audit.json")
        assert regression["regression_result"] == "pass"
        assert not regression["media_parts_removed"]
        revised = load_document(revise_dir / "论文修改稿.docx")
        assert "word/media/image1.png" in revised.media_parts
        assert any("需作者确认" in item.text for item in revised.paragraphs)
        with zipfile.ZipFile(revise_dir / "论文修改稿.docx") as archive:
            assert "word/comments.xml" in archive.namelist()
            assert "commentReference" in archive.read("word/document.xml").decode("utf-8")
        state = read(revise_dir / "revision_state.json")
        assert len(state["new_risks"]) == 0
        assert len(state["resolved"]) == 0

        defense_dir = temp / "defense"
        defense = defense_workflow(review_dir, defense_dir)
        assert defense["question_count"] > 0
        assert (defense_dir / "答辩问题库与应答准备.docx").exists()

        plan = read(review_dir / "revision_plan.json")
        evidence_item = next(item for item in plan["items"] if item["patch_mode"] == "mark_unconfirmed")
        evidence_item["confirmed"] = True
        evidence_item["patch_mode"] = "replace_text"
        evidence_item["proposed_rewrite"] = "样本数据显示学习体验提升了99%。"
        unsafe_plan = temp / "unsafe-plan.json"
        unsafe_plan.write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding="utf-8")
        rollback_dir = temp / "rollback"
        revise_workflow(source, unsafe_plan, rollback_dir)
        rollback = read(rollback_dir / "diff_audit.json")
        assert rollback["regression_result"] == "blocked_and_rolled_back"
        assert source.read_bytes() == (rollback_dir / "论文修改稿.docx").read_bytes()
        assert (rollback_dir / "论文修改候选稿-回归未通过.docx").exists()

        corpus_dir = temp / "corpus"
        corpus_dir.mkdir()
        (corpus_dir / "authorized.md").write_text(SAMPLE, encoding="utf-8")
        (corpus_dir / "unverified.md").write_text(SAMPLE, encoding="utf-8")
        rights = temp / "rights.json"
        rights.write_text(
            json.dumps(
                {
                    "files": [
                        {
                            "relative_path": "authorized.md",
                            "allow_derived_strategy": True,
                            "discipline": "education",
                            "level": "master",
                            "method": "qualitative",
                            "quality_basis": "synthetic_fixture",
                        }
                    ]
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        cards = temp / "cards.md"
        corpus_workflow(corpus_dir, cards, rights_manifest=rights)
        patterns = read(cards.with_suffix(".patterns.json"))
        assert patterns["authorized_document_count"] == 1
        assert patterns["rejected_unverified_count"] == 1
        serialized = json.dumps(patterns, ensure_ascii=False)
        assert str(corpus_dir) not in serialized
        assert "authorized.md" not in serialized

        summary = status_summary(revise_dir / "revision_state.json")
        assert summary["round"] == 2

        check_layout_audit(temp, source)
        check_regressed_state()
        check_locator_stability(temp)
        check_paragraph_id_injection(temp)
        check_namespace_preservation(temp)

        subprocess.run([sys.executable, "scripts/release_gate.py"], cwd=ROOT, check=True)
    print("v4 smoke tests passed")


def check_layout_audit(temp: Path, source: Path) -> None:
    document = load_document(source)
    layout_profile = temp / "layout-profile.json"
    layout_profile.write_text(
        json.dumps(
            {
                "profile_id": "layout-check",
                "required_sections": [],
                "font": {"eastAsia": "宋体", "body_pt": 12},
                "margins_mm": {"top": 25, "right": 25, "bottom": 25, "left": 30},
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    audit = profile_audit(document, load_profile(layout_profile))
    layout_rules = {risk["rule_id"] for risk in audit["risks"]}
    assert "PROF-LAYOUT-FONT" in layout_rules
    assert "PROF-LAYOUT-MARGINS" in layout_rules
    font_finding = next(risk for risk in audit["risks"] if risk["rule_id"] == "PROF-LAYOUT-FONT")
    assert font_finding["priority"] == "P2"
    assert font_finding["requires_author_confirmation"] is True
    # 与文档实际版式一致的 profile 不应产生版式 finding(write_docx 默认 Songti SC 11pt、四边 25.4mm)
    matching_profile = temp / "matching-layout-profile.json"
    matching_profile.write_text(
        json.dumps(
            {
                "profile_id": "layout-match",
                "required_sections": [],
                "font": {"eastAsia": "Songti SC", "body_pt": 11},
                "margins_mm": {"top": 25.4, "right": 25.4, "bottom": 25.4, "left": 25.4},
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    matching_audit = profile_audit(document, load_profile(matching_profile))
    assert not [risk for risk in matching_audit["risks"] if risk["rule_id"].startswith("PROF-LAYOUT")]
    # 未配置版式字段的 profile 行为不变
    default_audit = profile_audit(document, load_profile(None))
    assert not [risk for risk in default_audit["risks"] if risk["rule_id"].startswith("PROF-LAYOUT")]
    # findings 作为纯数据流入 review_engine
    layout_review = temp / "layout-review"
    review_workflow(source, layout_review, profile_path=layout_profile)
    panel_rules = {item["rule_id"] for item in read(layout_review / "professor_panel.json")["issues"]}
    assert "PROF-LAYOUT-FONT" in panel_rules
    assert "PROF-LAYOUT-MARGINS" in panel_rules


def check_regressed_state() -> None:
    def issue(fingerprint: str) -> dict:
        return {
            "id": f"P1-T-{fingerprint}",
            "fingerprint": fingerprint,
            "rule_id": "T-RULE",
            "priority": "P1",
            "status": "open",
        }

    first = advance_state(
        None,
        {"review": {"issues": [issue("fp-applied"), issue("fp-resolved")]}},
        phase="baseline_scan",
    )
    by_fp = {item["fingerprint"]: item for item in first["issues"]}
    by_fp["fp-applied"]["status"] = "applied"
    by_fp["fp-resolved"]["status"] = "resolved"
    second = advance_state(
        first,
        {"review": {"issues": [issue("fp-applied"), issue("fp-resolved")]}},
        phase="regression_review",
    )
    statuses = {item["fingerprint"]: item["status"] for item in second["issues"]}
    assert statuses["fp-applied"] == "regressed"
    assert statuses["fp-resolved"] == "reopened"


def check_locator_stability(temp: Path) -> None:
    stable_source = temp / "stable.docx"
    write_docx(stable_source, "定位测试", "前置段落。\n\n第二章 稳定定位测试目标段落。")
    with zipfile.ZipFile(stable_source) as archive:
        parts = {name: archive.read(name) for name in archive.namelist()}
    xml = parts["word/document.xml"].decode("utf-8")
    xml = xml.replace(
        f'<w:document xmlns:w="{W_NS}">',
        f'<w:document xmlns:w="{W_NS}" xmlns:mc="{MC_NS}" xmlns:w14="{W14_NS}" mc:Ignorable="w14">',
        1,
    )
    serial = iter(range(0x2000, 0x2100))

    def add_para_id(match: re.Match) -> str:
        return f'<w:p w14:paraId="{next(serial):08X}">'

    xml = re.sub(r"<w:p>", add_para_id, xml)

    def rewrite(path: Path, document_xml: str) -> None:
        with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for name, data in parts.items():
                archive.writestr(name, document_xml.encode("utf-8") if name == "word/document.xml" else data)

    rewrite(stable_source, xml)
    before = load_document(stable_source)
    target = next(item for item in before.paragraphs if "稳定定位测试目标" in item.text)
    assert target.has_stable_locator
    assert ";index=" not in target.locator
    rewrite(stable_source, xml.replace("<w:body>", "<w:body><w:p/>", 1))
    after = load_document(stable_source)
    shifted = next(item for item in after.paragraphs if "稳定定位测试目标" in item.text)
    assert shifted.index != target.index
    assert shifted.locator == target.locator


def check_paragraph_id_injection(temp: Path) -> None:
    plain = temp / "plain.docx"
    write_docx(plain, "注入测试", "没有任何 paraId 的段落。")
    patched = temp / "patched.docx"
    log = patch_docx(plain, patched, {"items": []})
    assert log["paragraph_ids_injected"] > 0
    with zipfile.ZipFile(patched) as archive:
        patched_xml = archive.read("word/document.xml").decode("utf-8")
    paragraph_count = len(re.findall(r"<w:p[ >]", patched_xml))
    assert paragraph_count > 0
    assert patched_xml.count("w14:paraId=") == paragraph_count
    assert "xmlns:w14=" in patched_xml
    assert 'mc:Ignorable="w14"' in patched_xml
    reparsed = load_document(patched)
    assert all(item.has_stable_locator for item in reparsed.paragraphs)
    assert [item.locator for item in reparsed.paragraphs if item.text == "没有任何 paraId 的段落。"]
    # 幂等:已带 paraId 的文件再次 patch 不再注入
    repatched = temp / "repatched.docx"
    second_log = patch_docx(patched, repatched, {"items": []})
    assert second_log["paragraph_ids_injected"] == 0


def check_namespace_preservation(temp: Path) -> None:
    ns_source = temp / "ns.docx"
    write_docx(ns_source, "ns", "命名空间保留测试。")
    with zipfile.ZipFile(ns_source) as archive:
        parts = {name: archive.read(name) for name in archive.namelist()}
    ns_xml = parts["word/document.xml"].decode("utf-8")
    ns_xml = ns_xml.replace(
        f'<w:document xmlns:w="{W_NS}">',
        f'<w:document xmlns:w="{W_NS}" xmlns:mc="{MC_NS}" xmlns:w14="{W14_NS}" '
        'xmlns:v="urn:schemas-microsoft-com:vml" '
        'xmlns:wps="http://schemas.microsoft.com/office/word/2010/wordprocessingShape" '
        'xmlns:wp14="http://schemas.microsoft.com/office/word/2010/wordprocessingDrawing" '
        'mc:Ignorable="w14 wps wp14">',
        1,
    )
    ns_xml = ns_xml.replace("</w:t></w:r></w:p>", '</w:t></w:r><v:shape id="s1"/><wps:wsp/></w:p>', 1)
    with zipfile.ZipFile(ns_source, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, data in parts.items():
            archive.writestr(name, ns_xml.encode("utf-8") if name == "word/document.xml" else data)
    ns_out = temp / "ns-out.docx"
    patch_docx(ns_source, ns_out, {"items": []})
    with zipfile.ZipFile(ns_out) as archive:
        out_xml = archive.read("word/document.xml").decode("utf-8")
    assert "ns0" not in out_xml
    for prefix in ("w", "w14", "mc", "v", "wps", "wp14"):
        assert f"xmlns:{prefix}=" in out_xml
    assert 'mc:Ignorable="w14 wps wp14"' in out_xml
    # 幂等:重复 patch 不累积重复声明
    ns_out2 = temp / "ns-out2.docx"
    patch_docx(ns_out, ns_out2, {"items": []})
    with zipfile.ZipFile(ns_out2) as archive:
        out_xml2 = archive.read("word/document.xml").decode("utf-8")
    assert "ns0" not in out_xml2
    assert out_xml2.count("xmlns:wp14=") == 1
    assert out_xml2.count("xmlns:wps=") == 1


if __name__ == "__main__":
    main()
