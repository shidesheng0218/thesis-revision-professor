#!/usr/bin/env python3
"""Standard-library smoke tests for environments without pytest."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PY = sys.executable


def run(*args: str) -> None:
    subprocess.run(args, cwd=ROOT, text=True, capture_output=True, check=True)


def main() -> None:
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        docx = tmp / "report.docx"
        extracted = tmp / "extracted.json"
        run(PY, "scripts/export_docx.py", "--title", "测试报告", "--body", "tests/fixtures/sample_report.md", "--out", str(docx))
        run(PY, "scripts/extract_docx_text.py", str(docx), "--out", str(extracted))
        assert json.loads(extracted.read_text(encoding="utf-8"))["paragraphs"]

        score = tmp / "score.json"
        src = tmp / "sample.md"
        src.write_text("摘要\n本文研究问题明确。方法包括访谈和案例分析。参考文献\n[1] 张三. 测试文献.", encoding="utf-8")
        run(PY, "scripts/rubric_score.py", str(src), "--level", "master", "--out", str(score))
        assert "blind_review_risk" in json.loads(score.read_text(encoding="utf-8"))

        corpus = tmp / "corpus"
        corpus.mkdir()
        (corpus / "fake.md").write_text("摘要\n引言\n文献综述\n方法\n结果\n结论\n参考文献\n[1] A.", encoding="utf-8")
        index = tmp / "index.json"
        patterns = tmp / "patterns.json"
        cards = tmp / "cards.md"
        run(PY, "scripts/corpus_index.py", str(corpus), "--out", str(index))
        run(PY, "scripts/extract_thesis_patterns.py", str(index), "--out", str(patterns))
        run(PY, "scripts/generate_strategy_cards.py", str(patterns), "--out", str(cards))
        assert "Generated strategy cards" in cards.read_text(encoding="utf-8")
    print("smoke tests passed")


if __name__ == "__main__":
    main()
