#!/usr/bin/env python3
"""Run the multi-dimensional thesis revision loop through diagnostic/report phase."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from thesis_utils import read_json, simple_docx, write_json


ROOT = Path(__file__).resolve().parents[1]
PY = sys.executable


def run(args: list[str]) -> None:
    subprocess.run([PY, *args], cwd=ROOT, check=True)


def convergence(rubric: dict, panel: dict, evidence: dict, report_docx: Path) -> dict:
    p0 = panel.get("summary", {}).get("p0", 0)
    p1 = panel.get("summary", {}).get("p1", 0)
    risk = rubric.get("blind_review_risk", "unknown")
    gaps = evidence.get("unsupported_claim_count", 0)
    return {
        "p0_clear": p0 == 0,
        "p1_acceptable": p1 <= 2,
        "risk_minor_or_pass": risk in {"minor revision", "pass"},
        "evidence_gaps_marked": gaps >= 0,
        "word_deliverables_generated": report_docx.exists(),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("input", help="Original thesis .docx/.md/.txt")
    parser.add_argument("--revised", help="Optional revised draft for regression diff audit")
    parser.add_argument("--level", choices=["master", "doctoral"], default="master")
    parser.add_argument("--discipline", default="unknown")
    parser.add_argument("--outdir", required=True)
    parser.add_argument("--state", help="Existing revision_state.json")
    args = parser.parse_args()

    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    input_path = Path(args.input)

    extracted = outdir / "extracted.json"
    structure = outdir / "structure.json"
    citations = outdir / "citation_audit.json"
    evidence = outdir / "evidence_audit.json"
    rubric = outdir / "rubric_score.json"
    panel = outdir / "professor_panel.json"
    revision_plan = outdir / "revision_plan.json"
    diff = outdir / "diff_audit.json"
    report_md = outdir / "修改说明与盲审风险报告.md"
    report_docx = outdir / "修改说明与盲审风险报告.docx"
    revision_log_docx = outdir / "逐条修改清单.docx"
    manuscript_docx = outdir / "论文修改稿.docx"
    state_json = outdir / "revision_state.json"
    round_json = outdir / "round_payload.json"

    if input_path.suffix.lower() == ".docx":
        run(["scripts/extract_docx_text.py", str(input_path), "--out", str(extracted)])
        run(["scripts/structure_map.py", str(input_path), "--out", str(structure)])
    else:
        write_json({"source": str(input_path), "note": "Non-docx input; extraction skipped."}, extracted)
        write_json({"source": str(input_path), "paragraph_count": 0, "heading_count": 0, "chapter_count": 0, "headings": [], "risks": ["非 Word 输入，未执行章节样式识别。"]}, structure)
    run(["scripts/citation_audit.py", str(input_path), "--out", str(citations)])
    run(["scripts/evidence_audit.py", str(input_path), "--out", str(evidence)])
    run(["scripts/rubric_score.py", str(input_path), "--level", args.level, "--out", str(rubric)])
    run(
        [
            "scripts/professor_panel_review.py",
            str(input_path),
            "--structure",
            str(structure),
            "--citations",
            str(citations),
            "--evidence",
            str(evidence),
            "--rubric",
            str(rubric),
            "--discipline",
            args.discipline,
            "--level",
            args.level,
            "--out",
            str(panel),
        ]
    )
    run(["scripts/build_revision_plan.py", "--source", str(input_path), "--panel", str(panel), "--evidence", str(evidence), "--out", str(revision_plan)])
    if args.revised:
        run(["scripts/diff_audit.py", str(input_path), args.revised, "--out", str(diff)])
    run(["scripts/build_revision_report.py", str(outdir), "--markdown-out", str(report_md), "--docx-out", str(report_docx)])

    panel_data = read_json(panel)
    issue_rows = []
    for issue in panel_data.get("issues", []):
        issue_rows.append(f"{issue['id']} | {issue['priority']} | {issue['role']} | {issue['finding']} | {issue['recommended_action']}")
    simple_docx(revision_log_docx, "逐条修改清单", "\n".join(issue_rows) or "暂无结构化问题。")
    simple_docx(
        manuscript_docx,
        "论文修改稿",
        "当前 loop 处于诊断与计划阶段。为避免无依据改写，正文修改需作者确认 Revision Plan 后执行。\n\n"
        f"原始文件：{input_path}\n"
        "请根据《修改说明与盲审风险报告.docx》确认 P0/P1 修改范围。",
    )

    rubric_data = read_json(rubric)
    evidence_data = read_json(evidence)
    conv = convergence(rubric_data, panel_data, evidence_data, report_docx)
    payload = {
        "input": str(input_path),
        "level": args.level,
        "discipline": args.discipline,
        "artifacts": {
            "extracted": str(extracted),
            "structure": str(structure),
            "citation_audit": str(citations),
            "evidence_audit": str(evidence),
            "rubric_score": str(rubric),
            "professor_panel": str(panel),
            "revision_plan": str(revision_plan),
            "diff_audit": str(diff) if args.revised else None,
        },
        "rubric_score": rubric_data,
        "evidence_audit": evidence_data,
        "professor_panel": panel_data,
        "deliverables": [str(report_docx), str(revision_log_docx), str(manuscript_docx)],
        "revision_plan": read_json(revision_plan),
        "convergence": conv,
        "next_phase": "revision_plan" if not conv["p0_clear"] else "controlled_rewrite",
    }
    write_json(payload, round_json)
    if args.state and Path(args.state).exists():
        run(["scripts/revision_state.py", "add-round", args.state, "--summary", "run_revision_loop diagnostic round", "--round-json", str(round_json), "--out", str(state_json)])
    else:
        run(["scripts/revision_state.py", "init", "--out", str(state_json)])
        run(["scripts/revision_state.py", "add-round", str(state_json), "--summary", "run_revision_loop diagnostic round", "--round-json", str(round_json), "--out", str(state_json)])
    print(json.dumps({"outdir": str(outdir), "report": str(report_docx), "state": str(state_json)}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
