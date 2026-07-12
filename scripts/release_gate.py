#!/usr/bin/env python3
"""Release gate for open-source safety and basic deliverable quality."""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TEXT_SUFFIXES = {".md", ".py", ".yaml", ".yml", ".json", ".txt", ".toml"}
SENSITIVE_PATTERNS = [
    re.compile(r"ghp_[A-Za-z0-9_]{20,}"),
    re.compile(r"github_pat_[A-Za-z0-9_]{20,}"),
    re.compile(r"Sds990218", re.I),
    re.compile(r"670258236@qq\.com", re.I),
]
DANGEROUS_PROMISES = ["保证毕业", "保证盲审通过", "保证通过查重", "guarantee graduation", "guarantee blind-review"]
COPYRIGHT_RISK = ["CNKI论文全文", "知网论文全文", "ProQuest thesis full text bundled"]


def tracked_files() -> list[Path]:
    proc = subprocess.run(["git", "ls-files"], cwd=ROOT, text=True, capture_output=True, check=True)
    return [ROOT / line.strip() for line in proc.stdout.splitlines() if line.strip()]


def check_text_files(files: list[Path]) -> list[str]:
    errors = []
    for path in files:
        if path.relative_to(ROOT).as_posix() == "scripts/release_gate.py":
            continue
        if path.suffix not in TEXT_SUFFIXES:
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        for pattern in SENSITIVE_PATTERNS:
            if pattern.search(text):
                errors.append(f"sensitive pattern in {path.relative_to(ROOT)}")
        for phrase in DANGEROUS_PROMISES + COPYRIGHT_RISK:
            if phrase in text:
                idx = text.find(phrase)
                context = text[max(0, idx - 30): idx + len(phrase) + 30].lower()
                if "does not " in context or "不" in context or "不能" in context:
                    continue
                errors.append(f"unsafe phrase `{phrase}` in {path.relative_to(ROOT)}")
    return errors


def check_demo() -> list[str]:
    required = [
        ROOT / "assets" / "examples" / "fake_thesis_sample.docx",
        ROOT / "assets" / "word_templates" / "review_report_template.docx",
    ]
    return [f"missing required demo/template file: {path.relative_to(ROOT)}" for path in required if not path.exists()]


def main() -> None:
    files = tracked_files()
    errors = check_text_files(files) + check_demo()
    if errors:
        for error in errors:
            print(f"release gate failed: {error}", file=sys.stderr)
        raise SystemExit(1)
    print("release gate passed")


if __name__ == "__main__":
    main()
