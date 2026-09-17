#!/usr/bin/env python3
"""Dependency-free v3 acceptance tests."""

from __future__ import annotations

import http.server
import json
import os
import re
import subprocess
import sys
import tempfile
import threading
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from thesis_revision_professor.audits import citation_audit, regression_audit, strip_confirmation_markers
from thesis_revision_professor.document_model import W14_NS, W_NS, load_document
from thesis_revision_professor.docx_patch import patch_docx
from thesis_revision_professor.docx_report import write_docx
from thesis_revision_professor.llm_review import LlmReviewError, run_llm_review
from thesis_revision_professor.profiles import load_profile, profile_audit
from thesis_revision_professor.review_engine import issue_fingerprint, legacy_fingerprint
from thesis_revision_professor.state_machine import advance_state
from thesis_revision_professor.workflow import corpus_workflow, defense_workflow, deep_review_workflow, disclosure_workflow, import_feedback_workflow, review_workflow, revise_workflow, status_summary


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
        check_fingerprint_migration()
        check_regression_invariants(temp)
        check_marker_decoupling(temp)
        check_semantic_rejections(temp, source)
        check_disclosure(temp, source)
        check_llm_review(temp)
        check_feedback(temp, source)
        check_cit_ref_audit(temp)
        check_footnote_coverage(temp)

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


def check_fingerprint_migration() -> None:
    locator = "word/document.xml#para=ABC12345"
    # 措辞无关：同一 rule_id+locator 不同 finding 文本指纹相同；legacy 算法可区分
    assert issue_fingerprint("EVI-X", locator, "甲措辞") == issue_fingerprint("EVI-X", locator, "乙措辞")
    assert issue_fingerprint("EVI-X", locator) != issue_fingerprint("EVI-X", "word/document.xml#para=OTHER")
    assert legacy_fingerprint("EVI-X", locator, "  Some  Text ") == legacy_fingerprint("EVI-X", locator, "some text")
    assert legacy_fingerprint("EVI-X", locator, "甲措辞") != issue_fingerprint("EVI-X", locator)

    def old_issue(rule_id: str, finding: str, status: str) -> dict:
        return {
            "id": f"P1-{rule_id}-old",
            "fingerprint": legacy_fingerprint(rule_id, locator, finding),
            "rule_id": rule_id,
            "locator": locator,
            "finding": finding,
            "priority": "P1",
            "status": status,
        }

    # 模拟旧版本写出的 revision_state.json(措辞相关 fingerprint)
    prior = {
        "schema_version": "4.0",
        "round": 1,
        "max_rounds": 5,
        "stable_rounds": 0,
        "issues": [
            old_issue("EVI-OLD-RESOLVED", "旧措辞A", "resolved"),
            old_issue("EVI-OLD-APPLIED", "旧措辞B", "applied"),
            old_issue("EVI-OLD-GONE", "旧措辞C", "confirmed"),
        ],
        "resolved": [],
        "scores": [],
        "history": [],
    }

    def new_finding(rule_id: str) -> dict:
        return {
            "id": f"P1-{rule_id}-new",
            "fingerprint": issue_fingerprint(rule_id, locator),
            "rule_id": rule_id,
            "locator": locator,
            "finding": "语义层完全不同的新措辞",
            "priority": "P1",
            "status": "open",
        }

    migrated = advance_state(
        prior,
        {"review": {"issues": [new_finding("EVI-OLD-RESOLVED"), new_finding("EVI-OLD-APPLIED")]}},
        phase="regression_review",
    )
    by_rule = {item["rule_id"]: item for item in migrated["issues"]}
    # 旧 fingerprint 的 issue 历史不丢：resolved→reopened,applied→regressed
    assert by_rule["EVI-OLD-RESOLVED"]["status"] == "reopened"
    assert by_rule["EVI-OLD-APPLIED"]["status"] == "regressed"
    # 重写后统一为新指纹
    assert by_rule["EVI-OLD-RESOLVED"]["fingerprint"] == issue_fingerprint("EVI-OLD-RESOLVED", locator)
    assert by_rule["EVI-OLD-APPLIED"]["fingerprint"] == issue_fingerprint("EVI-OLD-APPLIED", locator)
    # 消失的 legacy issue 以新指纹记入 resolved
    resolved_rules = {item["rule_id"] for item in migrated["resolved"]}
    assert "EVI-OLD-GONE" in resolved_rules
    gone = next(item for item in migrated["resolved"] if item["rule_id"] == "EVI-OLD-GONE")
    assert gone["fingerprint"] == issue_fingerprint("EVI-OLD-GONE", locator)


def check_regression_invariants(temp: Path) -> None:
    before = temp / "inv-before.md"
    before.write_text("样本量 1,247 人，下降 -2.3%，始于 1875 年。\n", encoding="utf-8")
    after = temp / "inv-after.md"
    after.write_text("样本量 1,248 人，下降 -2.4%，始于 1876 年，含圆周率 3.14。\n", encoding="utf-8")
    left = load_document(before)
    right = load_document(after)
    # 正例：千分位、负数百分比、小数、非 19/20 开头年份的未授权变化全部被检出
    audit = regression_audit(left, right)
    assert audit["regression_result"] == "blocked_and_rolled_back"
    numbers = audit["changes"]["numbers"]
    assert "1,247" in numbers["removed"] and "1,248" in numbers["added"]
    assert "-2.3%" in numbers["removed"] and "-2.4%" in numbers["added"]
    assert "3.14" in numbers["added"]
    years = audit["changes"]["years"]
    assert "1875" in years["removed"] and "1876" in years["added"]
    # 负例：授权白名单内的同样变化不报
    allowed = regression_audit(
        left,
        right,
        {"numbers": ["1,247", "1,248", "-2.3%", "-2.4%", "3.14"], "years": ["1875", "1876"], "citations": []},
    )
    assert allowed["regression_result"] == "pass"
    # 负例：完全相同的文本(含版本号样式 1.2.3)不产生任何变化
    same = temp / "inv-same.md"
    same.write_text("使用版本 1.2.3 的统计口径与编号 GB/T 7714。\n", encoding="utf-8")
    unchanged = regression_audit(load_document(same), load_document(same))
    assert unchanged["regression_result"] == "pass"
    assert unchanged["changes"]["numbers"]["added"] == []
    assert unchanged["changes"]["years"]["added"] == []


def check_marker_decoupling(temp: Path) -> None:
    assert strip_confirmation_markers("结果显示提升 42%。 [需作者确认:99 处待补]") == "结果显示提升 42%。"
    plain = temp / "marker-before.docx"
    write_docx(plain, "标记解耦", "结果显示提升 42%。")
    before = load_document(plain)
    # 正例：未确认项走标记路径，标记文本(即使含数字)不进入数字/年份比对
    mark_plan = {
        "items": [
            {
                "id": "PLAN-MARK",
                "patch_mode": "mark_unconfirmed",
                "confirmed": False,
                "locator": "",
                "target_text": "结果显示提升 42%。",
                "target_hash": "",
                "problem": "需要作者确认",
                "requires_author_confirmation": True,
            }
        ]
    }
    candidate = temp / "marker-candidate.docx"
    log = patch_docx(plain, candidate, mark_plan)
    assert log["marked_count"] == 1
    audit = regression_audit(before, load_document(candidate))
    assert audit["changes"]["numbers"]["added"] == []
    assert audit["changes"]["numbers"]["removed"] == []
    assert audit["changes"]["years"]["added"] == []
    assert audit["regression_result"] == "pass"
    # 对照：已确认替换若引入未授权数字变化仍被检出
    replace_plan = {
        "items": [
            {
                "id": "PLAN-REPLACE",
                "patch_mode": "replace_text",
                "confirmed": True,
                "locator": "",
                "target_text": "42%",
                "target_hash": "",
                "proposed_rewrite": "43%",
                "problem": "改写",
                "requires_author_confirmation": False,
            }
        ]
    }
    candidate2 = temp / "marker-candidate2.docx"
    patch_docx(plain, candidate2, replace_plan)
    audit2 = regression_audit(before, load_document(candidate2))
    assert "43%" in audit2["changes"]["numbers"]["added"]
    assert "42%" in audit2["changes"]["numbers"]["removed"]
    assert audit2["regression_result"] == "blocked_and_rolled_back"


def check_semantic_rejections(temp: Path, source: Path) -> None:
    def finding(rule_id: str, **overrides: object) -> dict:
        base = {
            "rule_id": rule_id,
            "reviewer": "chief_argument_reviewer",
            "locator": "word/document.xml#para=ABC12345",
            "severity": "P1",
            "confidence": 0.8,
            "finding": "语义发现",
            "rationale": "依据",
            "recommended_action": "动作",
            "acceptance_test": "验收",
        }
        base.update(overrides)
        return base

    payload = {
        "findings": [
            finding("SEM-VALID"),
            finding("SEM-BAD-SEVERITY", severity="P3"),
            finding("SEM-MISSING-FIELDS", rationale="", recommended_action=""),
            finding("SEM-BAD-LOCATOR", locator="word/document.xml", confidence=1.5),
            finding("SEM-LEGACY-LOCATOR", locator="word/document.xml#para=00A1;index=48"),
        ]
    }
    payload_path = temp / "semantic-findings.json"
    payload_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    out = temp / "semantic-review"
    # 个别 finding 非法不导致工作流失败
    review_workflow(source, out, semantic_findings=payload_path)
    rejections = read(out / "semantic_rejections.json")
    assert len(rejections) == 3
    reasons_blob = json.dumps(rejections, ensure_ascii=False)
    assert "severity" in reasons_blob
    assert "missing required field" in reasons_blob
    assert "locator" in reasons_blob
    assert "confidence" in reasons_blob
    rejected_ids = {entry["finding"]["rule_id"] for entry in rejections}
    assert rejected_ids == {"SEM-BAD-SEVERITY", "SEM-MISSING-FIELDS", "SEM-BAD-LOCATOR"}
    # 合法 finding(含历史 ;index= locator)正常合并
    panel = read(out / "professor_panel.json")
    panel_rules = {item["rule_id"] for item in panel["issues"]}
    assert "SEM-VALID" in panel_rules
    assert "SEM-LEGACY-LOCATOR" in panel_rules
    # 结构级错误仍整体拒绝
    bad_path = temp / "semantic-bad.json"
    bad_path.write_text(json.dumps({"findings": "not-a-list"}), encoding="utf-8")
    try:
        review_workflow(source, temp / "semantic-bad-out", semantic_findings=bad_path)
    except ValueError:
        pass
    else:
        raise AssertionError("structurally invalid semantic payload must raise ValueError")


def check_disclosure(temp: Path, source: Path) -> None:
    review_dir = temp / "disclosure-review"
    review_workflow(source, review_dir, level="master", discipline="education", method="qualitative")
    out = temp / "disclosure-out"
    result = disclosure_workflow(review_dir, out)
    md = (out / "AI辅助内容清单.md").read_text(encoding="utf-8")
    assert "审查过程" in md
    assert "修改计划项" in md
    assert "待作者确认项" in md
    assert "未采纳的语义审查意见" in md
    assert "产物完整性" in md
    # 未确认项有体现(plan 中 requires_author_confirmation 且未确认的项)
    assert "待确认" in md
    payload = read(out / "AI辅助内容清单.json")
    assert payload["plan_items"] > 0
    assert payload["pending_confirmation"] > 0
    # docx 生成且可重新 load
    docx_path = Path(result["docx"])
    assert docx_path.exists()
    reloaded = load_document(docx_path)
    assert any("辅助内容清单" in item.text for item in reloaded.paragraphs)
    # 降级:产物缺失的目录不崩,且如实注明缺失
    empty = temp / "disclosure-empty"
    empty.mkdir()
    disclosure_workflow(empty, temp / "disclosure-degraded")
    degraded_md = (temp / "disclosure-degraded" / "AI辅助内容清单.md").read_text(encoding="utf-8")
    assert "缺失" in degraded_md
    assert "无修改计划产物" in degraded_md


def check_llm_review(temp: Path) -> None:
    valid_finding = {
        "rule_id": "SEM-LLM-VALID",
        "reviewer": "chief_argument_reviewer",
        "locator": "word/document.xml#para=ABC12345",
        "severity": "P1",
        "confidence": 0.8,
        "finding": "模型发现的合法问题",
        "rationale": "依据",
        "counterevidence": "反证",
        "recommended_action": "动作",
        "acceptance_test": "验收",
    }
    bad_finding = {
        "rule_id": "SEM-LLM-BAD",
        "reviewer": "method_expert",
        "locator": "word/document.xml#para=ABC12345",
        "severity": "P9",
        "confidence": 0.8,
        "finding": "非法 severity",
        "rationale": "依据",
        "recommended_action": "动作",
        "acceptance_test": "验收",
    }
    captured: dict = {}

    class Handler(http.server.BaseHTTPRequestHandler):
        def do_POST(self) -> None:
            length = int(self.headers.get("Content-Length", 0))
            captured["path"] = self.path
            captured["body"] = json.loads(self.rfile.read(length))
            content = json.dumps({"findings": [valid_finding, bad_finding]}, ensure_ascii=False)
            response = json.dumps({"choices": [{"message": {"role": "assistant", "content": content}}]}).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(response)

        def log_message(self, *_args: object) -> None:
            return

    server = http.server.HTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    request_path = temp / "llm-request.json"
    request_path.write_text(
        json.dumps(
            {
                "task": "independent_semantic_professor_review",
                "reviewer_roles": ["chief_argument_reviewer"],
                "output_schema": {"findings": []},
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    out_path = temp / "llm-out" / "semantic_findings.json"
    try:
        os.environ["THESIS_REVIEW_API_BASE"] = f"http://127.0.0.1:{server.server_port}/v1"
        os.environ["THESIS_REVIEW_API_KEY"] = "test-key"
        os.environ["THESIS_REVIEW_MODEL"] = "fake-model"
        result = run_llm_review(request_path, out_path)
        # 请求拼装正确:OpenAI 兼容路径、模型、system+user 消息、Bearer 头
        assert captured["path"].endswith("/chat/completions")
        assert captured["body"]["model"] == "fake-model"
        assert [message["role"] for message in captured["body"]["messages"]] == ["system", "user"]
        # 响应解析 + 字段校验接入:合法 finding 保留,非法 severity 被拒
        payload = read(out_path)
        assert [item["rule_id"] for item in payload["findings"]] == ["SEM-LLM-VALID"]
        assert len(payload["rejected_findings"]) == 1
        assert payload["rejected_findings"][0]["finding"]["rule_id"] == "SEM-LLM-BAD"
        assert result["roles_ok"] == 1 and result["partial"] is False
    finally:
        server.shutdown()
        server.server_close()
        for variable in ("THESIS_REVIEW_API_BASE", "THESIS_REVIEW_API_KEY", "THESIS_REVIEW_MODEL"):
            os.environ.pop(variable, None)
    # 无 key 时清晰报错(非零退出路径由 CLI SystemExit 承担)
    try:
        run_llm_review(request_path, temp / "llm-out2" / "semantic_findings.json")
    except LlmReviewError:
        pass
    else:
        raise AssertionError("缺少 THESIS_REVIEW_API_KEY 时 llm-review 必须报错")


def check_feedback(temp: Path, source: Path) -> None:
    review_dir = temp / "feedback-review"
    review_workflow(source, review_dir, level="master", discipline="education", method="qualitative")
    opinion = temp / "盲审意见.txt"
    opinion.write_text(
        "盲审专家意见\n"
        "1. 第三章研究方法的样本量描述不足，建议补充说明。\n"
        "2. 第四章结果存在严重错误，必须修改统计口径。\n"
        "3. 第二章文献综述建议补充近两年文献。\n"
        "4. 语言表达需要润色，个别段落不通顺。\n",
        encoding="utf-8",
    )
    out = temp / "feedback-round"
    result = import_feedback_workflow(opinion, review_dir, out)
    assert result["feedback_count"] == 4
    assert result["unlocated_count"] == 1
    plan = read(out / "revision_plan.json")
    feedback_items = [item for item in plan["items"] if item.get("source") == "external_feedback"]
    assert len(feedback_items) == 4
    located = [item for item in feedback_items if item.get("locator")]
    unlocated = [item for item in feedback_items if not item.get("locator")]
    assert len(located) == 3 and len(unlocated) == 1
    # 可定位项走标记路径;不可定位项保持 manual_only,绝不进自动 patch
    assert all(item["patch_mode"] == "mark_unconfirmed" for item in located)
    assert unlocated[0]["patch_mode"] == "manual_only"
    assert any(item["locator"].startswith("word/document.xml#para=") for item in located)
    # severity 启发式:严重/必须 → P0;建议/不足 → P1
    panel = read(out / "professor_panel.json")
    by_rule = {item["rule_id"]: item for item in panel["issues"] if item.get("rule_id", "").startswith("FB-")}
    assert by_rule["FB-001"]["priority"] == "P1"
    assert by_rule["FB-002"]["priority"] == "P0"
    assert by_rule["FB-004"]["needs_manual_locator"] is True
    mapping = read(out / "feedback_mapping.json")
    assert len(mapping["items"]) == 4
    statuses = {item["feedback_id"]: item["status"] for item in mapping["items"]}
    assert statuses["FB-004"] == "待定位"
    # 对照表 docx 生成且可打开
    report = load_document(Path(result["report"]))
    assert any("意见—修改对照表" in item.text for item in report.paragraphs)
    # revise 检测到 feedback_mapping.json 时自动刷新对照表
    revise_dir = temp / "feedback-revise"
    revise_workflow(source, out / "revision_plan.json", revise_dir)
    revise_report = revise_dir / "意见—修改对照表.docx"
    assert revise_report.exists()
    revised_mapping_doc = load_document(revise_report)
    assert any("已修改" in item.text or "需作者确认" in item.text for item in revised_mapping_doc.paragraphs)


def check_cit_ref_audit(temp: Path) -> None:
    flawed = temp / "cit-ref-flawed.docx"
    write_docx(
        flawed,
        "文献审计",
        "正文引用[1]。\n\n# 参考文献\n\n"
        "[1] 张三. 教学设计研究[J]. 教育研究, 2024(1): 1-10.\n"
        "[2] 李四. 学习体验调查\n"
        "[2] 王五. 重复编号研究[J]. 教育研究, 2023(2): 5-6.\n"
        "[4] 赵六【M】. 某专著. 2020.",
    )
    audit = citation_audit(load_document(flawed))
    rules = {risk["rule_id"] for risk in audit["risks"]}
    assert "CIT-REF-NUMBERING" in rules
    assert "CIT-REF-FIELDS" in rules
    assert "CIT-REF-FULLWIDTH-MARKER" in rules
    numbering = next(risk for risk in audit["risks"] if risk["rule_id"] == "CIT-REF-NUMBERING")
    assert "重复编号 2" in numbering["message"] and "缺号 3" in numbering["message"]
    assert numbering["priority"] == "P1"
    fullwidth = next(risk for risk in audit["risks"] if risk["rule_id"] == "CIT-REF-FULLWIDTH-MARKER")
    assert fullwidth["priority"] == "P2"
    fields = [risk for risk in audit["risks"] if risk["rule_id"] == "CIT-REF-FIELDS"]
    assert any("[2]" in risk["message"] for risk in fields)
    assert any("[4]" in risk["message"] and "缺类型标识" in risk["message"] for risk in fields)
    # 负例:合规文献表不产生 CIT-REF-* finding
    clean = temp / "cit-ref-clean.docx"
    write_docx(clean, "文献审计", "正文引用[1]。\n\n# 参考文献\n\n[1] 张三. 教学设计研究[J]. 教育研究, 2024(1): 1-10.")
    clean_audit = citation_audit(load_document(clean))
    assert not [risk for risk in clean_audit["risks"] if risk["rule_id"].startswith("CIT-REF-")]
    # 负例:无参考文献章节且无引用时静默跳过
    no_refs = temp / "cit-ref-none.docx"
    write_docx(no_refs, "文献审计", "没有任何引用的正文。")
    none_audit = citation_audit(load_document(no_refs))
    assert not [risk for risk in none_audit["risks"] if risk["rule_id"].startswith("CIT-REF-")]


def check_footnote_coverage(temp: Path) -> None:
    base = temp / "footnote-base.docx"
    write_docx(base, "脚注覆盖", "正文没有引用，详见脚注。\n\n# 参考文献\n\n[1] 张三. 教学设计研究[J]. 教育研究, 2024(1): 1-10.")
    with zipfile.ZipFile(base) as archive:
        parts = {name: archive.read(name) for name in archive.namelist()}
    footnotes = (
        f'<w:footnotes xmlns:w="{W_NS}"><w:footnote w:id="2"><w:p><w:r>'
        "<w:t>该结论参见文献[1]的复现研究。</w:t></w:r></w:p></w:footnote></w:footnotes>"
    )
    header = (
        f'<w:hdr xmlns:w="{W_NS}"><w:p><w:r><w:t>第</w:t></w:r>'
        '<w:r><w:fldChar w:fldCharType="begin"/></w:r>'
        '<w:r><w:instrText xml:space="preserve"> PAGE </w:instrText></w:r>'
        '<w:r><w:fldChar w:fldCharType="end"/></w:r></w:p></w:hdr>'
    )
    covered = temp / "footnote-covered.docx"
    with zipfile.ZipFile(covered, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, data in parts.items():
            archive.writestr(name, data)
        archive.writestr("word/footnotes.xml", footnotes)
        archive.writestr("word/header1.xml", header)
    document = load_document(covered)
    note_paragraphs = [item for item in document.paragraphs if item.locator.startswith("word/footnotes.xml#")]
    header_paragraphs = [item for item in document.paragraphs if item.locator.startswith("word/header1.xml#")]
    assert len(note_paragraphs) == 1 and "[1]" in note_paragraphs[0].text
    assert len(header_paragraphs) == 1
    # 页码域沿用复杂内容标记,避免误改
    assert header_paragraphs[0].has_complex_content is True
    # 脚注引用计入正文引用网络
    audit = citation_audit(document)
    assert audit["citation_count"] == 1
    assert audit["missing_reference_entries"] == []
    # 对脚注部件段落的 patch 请求被 blocked
    blocked_plan = {
        "items": [
            {
                "id": "PLAN-NOTE",
                "patch_mode": "replace_text",
                "confirmed": True,
                "locator": note_paragraphs[0].locator,
                "target_text": "该结论参见文献[1]的复现研究。",
                "target_hash": "",
                "proposed_rewrite": "改写脚注。",
            }
        ]
    }
    candidate = temp / "footnote-candidate.docx"
    log = patch_docx(covered, candidate, blocked_plan)
    assert log["items"][0]["status"] == "blocked"
    assert log["items"][0]["reason"] == "unsupported_part_requires_manual_edit"
    # 空计划 patch 后包部件回归仍 pass
    clean_candidate = temp / "footnote-clean-candidate.docx"
    patch_docx(covered, clean_candidate, {"items": []})
    regression = regression_audit(load_document(covered), load_document(clean_candidate))
    assert regression["regression_result"] == "pass"
    assert not regression["package_parts_removed"]


if __name__ == "__main__":
    main()
