from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PY = sys.executable


def run(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, cwd=ROOT, text=True, capture_output=True, check=True)


def test_export_and_extract_docx(tmp_path: Path) -> None:
    docx = tmp_path / "report.docx"
    extracted = tmp_path / "extracted.json"
    run(PY, "scripts/export_docx.py", "--title", "测试报告", "--body", "tests/fixtures/sample_report.md", "--out", str(docx))
    assert docx.exists()
    run(PY, "scripts/extract_docx_text.py", str(docx), "--out", str(extracted))
    data = json.loads(extracted.read_text(encoding="utf-8"))
    assert data["paragraphs"]


def test_rubric_score(tmp_path: Path) -> None:
    src = tmp_path / "sample.md"
    out = tmp_path / "score.json"
    src.write_text("摘要\n本文研究问题明确。方法包括访谈和案例分析。参考文献\n[1] 张三. 测试文献.", encoding="utf-8")
    run(PY, "scripts/rubric_score.py", str(src), "--level", "master", "--out", str(out))
    data = json.loads(out.read_text(encoding="utf-8"))
    assert "blind_review_risk" in data


def test_corpus_strategy_pipeline(tmp_path: Path) -> None:
    corpus = tmp_path / "corpus"
    corpus.mkdir()
    (corpus / "fake.md").write_text("摘要\n引言\n文献综述\n方法\n结果\n结论\n参考文献\n[1] A.", encoding="utf-8")
    index = tmp_path / "index.json"
    patterns = tmp_path / "patterns.json"
    cards = tmp_path / "cards.md"
    run(PY, "scripts/corpus_index.py", str(corpus), "--out", str(index))
    run(PY, "scripts/extract_thesis_patterns.py", str(index), "--out", str(patterns))
    run(PY, "scripts/generate_strategy_cards.py", str(patterns), "--out", str(cards))
    assert "Generated strategy cards" in cards.read_text(encoding="utf-8")


def test_run_revision_loop(tmp_path: Path) -> None:
    out = tmp_path / "loop"
    run(PY, "scripts/run_revision_loop.py", "assets/examples/fake_thesis_sample.docx", "--level", "master", "--discipline", "education", "--outdir", str(out))
    assert (out / "修改说明与盲审风险报告.docx").exists()
    assert (out / "round_payload.json").exists()
    assert (out / "revision_plan.json").exists()


def test_apply_revision_plan_marks_unconfirmed(tmp_path: Path) -> None:
    loop = tmp_path / "loop"
    revised = tmp_path / "revised"
    run(PY, "scripts/run_revision_loop.py", "assets/examples/fake_thesis_sample.docx", "--level", "master", "--discipline", "education", "--outdir", str(loop))
    run(PY, "scripts/apply_revision_plan.py", "assets/examples/fake_thesis_sample.docx", "--plan", str(loop / "revision_plan.json"), "--outdir", str(revised))
    text = (revised / "论文修改稿.txt").read_text(encoding="utf-8")
    assert "需作者确认" in text


def test_cli_review_status(tmp_path: Path) -> None:
    out = tmp_path / "cli"
    run(PY, "-m", "thesis_revision_professor", "review", "assets/examples/fake_thesis_sample.docx", "--level", "master", "--discipline", "education", "--outdir", str(out))
    assert (out / "revision_state.json").exists()
    run(PY, "-m", "thesis_revision_professor", "status", str(out / "revision_state.json"))
