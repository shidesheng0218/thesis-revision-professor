#!/usr/bin/env python3
"""Product CLI for thesis-revision-professor."""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PY = sys.executable


def run_script(script: str, *args: str) -> None:
    subprocess.run([PY, str(ROOT / "scripts" / script), *args], cwd=ROOT, check=True)


def cmd_review(args: argparse.Namespace) -> None:
    run_script(
        "run_revision_loop.py",
        args.input,
        "--level",
        args.level,
        "--discipline",
        args.discipline,
        "--outdir",
        args.outdir,
        *(["--revised", args.revised] if args.revised else []),
    )


def cmd_revise(args: argparse.Namespace) -> None:
    run_script("apply_revision_plan.py", args.input, "--plan", args.plan, "--outdir", args.outdir)


def cmd_corpus(args: argparse.Namespace) -> None:
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    tmp_index = out.with_suffix(".index.json")
    tmp_patterns = out.with_suffix(".patterns.json")
    run_script("corpus_index.py", args.corpus_dir, "--out", str(tmp_index))
    run_script("extract_thesis_patterns.py", str(tmp_index), "--out", str(tmp_patterns))
    run_script("generate_strategy_cards.py", str(tmp_patterns), "--out", str(out))
    print(json.dumps({"strategy_cards": str(out), "index": str(tmp_index), "patterns": str(tmp_patterns)}, ensure_ascii=False, indent=2))


def cmd_status(args: argparse.Namespace) -> None:
    state = json.loads(Path(args.state).read_text(encoding="utf-8"))
    latest = state.get("scores", [{}])[-1] if state.get("scores") else {}
    convergence = state.get("convergence", {})
    summary = {
        "round": state.get("round"),
        "phase": state.get("phase"),
        "risk": latest.get("blind_review_risk", "unknown"),
        "p0_count": len(state.get("p0", [])),
        "p1_count": len(state.get("p1", [])),
        "p2_count": len(state.get("p2", [])),
        "can_enter_controlled_rewrite": state.get("phase") in {"controlled_rewrite", "revision_plan"},
        "word_export_gate": convergence.get("word_deliverables_generated", False),
        "next_step": "确认 revision_plan.json 中的修改项，然后运行 thesis-review revise。" if state.get("phase") == "revision_plan" else "继续下一轮 review 或导出。",
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))


def cmd_demo(args: argparse.Namespace) -> None:
    demo_out = ROOT / "demo" / "output"
    demo_out.mkdir(parents=True, exist_ok=True)
    input_docx = ROOT / "assets" / "examples" / "fake_thesis_sample.docx"
    demo_input = ROOT / "demo" / "input" / "fake_thesis_sample.docx"
    demo_input.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(input_docx, demo_input)
    run_script("run_revision_loop.py", str(demo_input), "--level", "master", "--discipline", "education", "--outdir", str(demo_out))
    print(json.dumps({"demo_output": str(demo_out)}, ensure_ascii=False, indent=2))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="thesis-review")
    sub = parser.add_subparsers(dest="command", required=True)
    review = sub.add_parser("review", help="Run diagnostic professor-review loop")
    review.add_argument("input")
    review.add_argument("--level", choices=["master", "doctoral"], default="master")
    review.add_argument("--discipline", default="unknown")
    review.add_argument("--outdir", required=True)
    review.add_argument("--revised")
    review.set_defaults(func=cmd_review)

    revise = sub.add_parser("revise", help="Apply confirmed revision plan items")
    revise.add_argument("input")
    revise.add_argument("--plan", required=True)
    revise.add_argument("--outdir", required=True)
    revise.set_defaults(func=cmd_revise)

    corpus = sub.add_parser("corpus", help="Extract non-verbatim strategy cards from a legal local corpus")
    corpus.add_argument("corpus_dir")
    corpus.add_argument("--out", required=True)
    corpus.set_defaults(func=cmd_corpus)

    status = sub.add_parser("status", help="Summarize revision state")
    status.add_argument("state")
    status.set_defaults(func=cmd_status)

    demo = sub.add_parser("demo", help="Generate demo outputs")
    demo.set_defaults(func=cmd_demo)
    return parser


def main(argv: list[str] | None = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
