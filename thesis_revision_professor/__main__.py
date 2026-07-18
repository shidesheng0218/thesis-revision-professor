#!/usr/bin/env python3
"""Product CLI for thesis-revision-professor v3."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from .corpus import rights_template
from .docx_report import write_docx
from .workflow import corpus_workflow, review_workflow, revise_workflow, status_summary, write_json


def print_result(payload: dict) -> None:
    print(json.dumps(payload, ensure_ascii=False, indent=2))


def cmd_review(args: argparse.Namespace) -> None:
    print_result(
        review_workflow(
            args.input,
            args.outdir,
            level=args.level,
            discipline=args.discipline,
            method=args.method,
            stage=args.stage,
            semantic_findings=args.semantic_findings,
            state_path=args.state,
        )
    )


def cmd_revise(args: argparse.Namespace) -> None:
    print_result(
        revise_workflow(
            args.input,
            args.plan,
            args.outdir,
            state_path=args.state,
            tracked=not args.clean_changes,
        )
    )


def cmd_corpus(args: argparse.Namespace) -> None:
    print_result(corpus_workflow(args.corpus_dir, args.out, rights_manifest=args.rights_manifest))


def cmd_rights_template(args: argparse.Namespace) -> None:
    payload = rights_template(args.corpus_dir)
    write_json(args.out, payload)
    print_result({"rights_manifest_template": str(args.out)})


def cmd_status(args: argparse.Namespace) -> None:
    print_result(status_summary(args.state))


def cmd_demo(args: argparse.Namespace) -> None:
    outdir = Path(args.outdir or "demo-output")
    outdir.mkdir(parents=True, exist_ok=True)
    source = outdir / "fake_thesis_sample.docx"
    body = """# 摘要

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
    write_docx(source, "伪论文样例", body)
    result = review_workflow(source, outdir, level="master", discipline="education", method="qualitative")
    print_result(result)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="thesis-review")
    sub = parser.add_subparsers(dest="command", required=True)

    review = sub.add_parser("review", help="Run evidence-bound deterministic and optional semantic review")
    review.add_argument("input")
    review.add_argument("--level", choices=["master", "doctoral"], default="master")
    review.add_argument("--discipline", default="unknown")
    review.add_argument("--method", default="unknown")
    review.add_argument("--stage", default="blind-review")
    review.add_argument("--semantic-findings", help="Validated findings returned by Codex or another semantic reviewer")
    review.add_argument("--state", help="Previous revision_state.json")
    review.add_argument("--outdir", required=True)
    review.set_defaults(func=cmd_review)

    revise = sub.add_parser("revise", help="Patch confirmed items, audit regressions, and re-review")
    revise.add_argument("input")
    revise.add_argument("--plan", required=True)
    revise.add_argument("--state", help="Previous revision_state.json")
    revise.add_argument("--clean-changes", action="store_true", help="Write clean replacements instead of Word tracked changes")
    revise.add_argument("--outdir", required=True)
    revise.set_defaults(func=cmd_revise)

    corpus = sub.add_parser("corpus", help="Mine non-verbatim patterns from rights-approved local files")
    corpus.add_argument("corpus_dir")
    corpus.add_argument("--rights-manifest", required=True)
    corpus.add_argument("--out", required=True)
    corpus.set_defaults(func=cmd_corpus)

    rights = sub.add_parser("rights-template", help="Create a corpus rights-manifest template")
    rights.add_argument("corpus_dir")
    rights.add_argument("--out", required=True)
    rights.set_defaults(func=cmd_rights_template)

    status = sub.add_parser("status", help="Summarize issue lifecycle and convergence gates")
    status.add_argument("state")
    status.set_defaults(func=cmd_status)

    demo = sub.add_parser("demo", help="Generate a synthetic, copyright-safe v3 demo")
    demo.add_argument("--outdir")
    demo.set_defaults(func=cmd_demo)
    return parser


def main(argv: list[str] | None = None) -> None:
    args = build_parser().parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
