#!/usr/bin/env python3
"""Dependency-free v3 acceptance tests."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from thesis_revision_professor.document_model import load_document
from thesis_revision_professor.docx_report import write_docx
from thesis_revision_professor.workflow import corpus_workflow, review_workflow, revise_workflow, status_summary


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
        )
        regression = read(revise_dir / "diff_audit.json")
        assert regression["regression_result"] == "pass"
        assert not regression["media_parts_removed"]
        revised = load_document(revise_dir / "论文修改稿.docx")
        assert "word/media/image1.png" in revised.media_parts
        assert any("需作者确认" in item.text for item in revised.paragraphs)
        state = read(revise_dir / "revision_state.json")
        assert len(state["new_risks"]) == 0
        assert len(state["resolved"]) == 0

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
        subprocess.run([sys.executable, "scripts/release_gate.py"], cwd=ROOT, check=True)
    print("v3 smoke tests passed")


if __name__ == "__main__":
    main()
