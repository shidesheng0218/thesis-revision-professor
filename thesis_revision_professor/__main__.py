#!/usr/bin/env python3
"""Product CLI for thesis-revision-professor v4."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from .corpus import rights_template
from .docx_report import write_docx
from .llm_review import LlmReviewError, run_llm_review
from .workflow import (
    consistency_workflow,
    corpus_workflow,
    defense_workflow,
    deep_review_workflow,
    disclosure_workflow,
    evidence_template_workflow,
    import_feedback_workflow,
    merge_semantic_workflow,
    review_workflow,
    revise_workflow,
    status_summary,
    write_json,
)


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
            profile_path=args.profile,
            evidence_dir=args.evidence_dir,
            evidence_manifest_path=args.evidence_manifest,
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
            comments=args.comments,
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


def cmd_deep_review(args: argparse.Namespace) -> None:
    print_result(deep_review_workflow(args.input, args.outdir, level=args.level, discipline=args.discipline, method=args.method, stage=args.stage, profile_path=args.profile, evidence_dir=args.evidence_dir, evidence_manifest_path=args.evidence_manifest))


def cmd_merge_semantic(args: argparse.Namespace) -> None:
    print_result(merge_semantic_workflow(args.review, args.findings, args.outdir))


def cmd_evidence_template(args: argparse.Namespace) -> None:
    print_result(evidence_template_workflow(args.evidence_dir, args.out))


def cmd_consistency(args: argparse.Namespace) -> None:
    print_result(consistency_workflow(args.before, args.after, args.out))


def cmd_defense(args: argparse.Namespace) -> None:
    print_result(defense_workflow(args.review, args.outdir))


def cmd_disclosure(args: argparse.Namespace) -> None:
    print_result(disclosure_workflow(args.review, args.outdir))


def cmd_import_feedback(args: argparse.Namespace) -> None:
    print_result(import_feedback_workflow(args.text, args.review, args.outdir))


def cmd_llm_review(args: argparse.Namespace) -> None:
    try:
        print_result(run_llm_review(args.request, args.out))
    except LlmReviewError as error:
        raise SystemExit(f"llm-review 失败:{error}")


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
    review.add_argument("--profile", help="User-provided institution/style profile JSON")
    review.add_argument("--evidence-dir", help="Directory containing user-authorized evidence")
    review.add_argument("--evidence-manifest", help="Evidence manifest JSON")
    review.add_argument("--outdir", required=True)
    review.set_defaults(func=cmd_review)

    revise = sub.add_parser("revise", help="Patch confirmed items, audit regressions, and re-review")
    revise.add_argument("input")
    revise.add_argument("--plan", required=True)
    revise.add_argument("--state", help="Previous revision_state.json")
    changes = revise.add_mutually_exclusive_group()
    changes.add_argument("--clean-changes", action="store_true", help="Write clean replacements instead of Word tracked changes")
    changes.add_argument("--tracked", action="store_true", help="Write Word tracked changes (default)")
    revise.add_argument("--comments", action="store_true", help="Add Word comments for manual and applied findings")
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

    deep = sub.add_parser("deep-review", help="Prepare a five-round evidence-grounded review war room")
    deep.add_argument("input")
    deep.add_argument("--level", choices=["master", "doctoral"], default="master")
    deep.add_argument("--discipline", default="unknown")
    deep.add_argument("--method", default="unknown")
    deep.add_argument("--stage", default="blind-review")
    deep.add_argument("--profile")
    deep.add_argument("--evidence-dir")
    deep.add_argument("--evidence-manifest")
    deep.add_argument("--outdir", required=True)
    deep.set_defaults(func=cmd_deep_review)

    merge = sub.add_parser("merge-semantic", help="Merge Codex semantic findings into a review round")
    merge.add_argument("--review", required=True)
    merge.add_argument("--findings", required=True)
    merge.add_argument("--outdir", required=True)
    merge.set_defaults(func=cmd_merge_semantic)

    evidence = sub.add_parser("evidence-template", help="Create an evidence manifest template")
    evidence.add_argument("evidence_dir")
    evidence.add_argument("--out", required=True)
    evidence.set_defaults(func=cmd_evidence_template)

    consistency = sub.add_parser("consistency", help="Compare two document models for cross-section changes")
    consistency.add_argument("--before", required=True)
    consistency.add_argument("--after", required=True)
    consistency.add_argument("--out", required=True)
    consistency.set_defaults(func=cmd_consistency)

    defense = sub.add_parser("defense", help="Generate evidence-bound blind-review and defense questions")
    defense.add_argument("--review", required=True)
    defense.add_argument("--outdir", required=True)
    defense.set_defaults(func=cmd_defense)

    disclosure = sub.add_parser("disclosure", help="Export the machine-generated AI-assisted-content disclosure")
    disclosure.add_argument("--review", required=True, help="Round directory containing revision_state.json / revision_plan.json")
    disclosure.add_argument("--outdir", required=True)
    disclosure.set_defaults(func=cmd_disclosure)

    feedback = sub.add_parser("import-feedback", help="Import external blind-review/advisor feedback into a controlled revision round")
    feedback.add_argument("text", help="Opinion text file (.txt/.md, utf-8)")
    feedback.add_argument("--review", required=True, help="Round directory containing round_payload.json")
    feedback.add_argument("--outdir", required=True)
    feedback.set_defaults(func=cmd_import_feedback)

    llm = sub.add_parser("llm-review", help="Generate semantic_findings.json via an OpenAI-compatible API (optional)")
    llm.add_argument("--request", required=True, help="semantic_review_request.json from a review round")
    llm.add_argument("--out", required=True, help="Output semantic_findings.json")
    llm.set_defaults(func=cmd_llm_review)

    demo = sub.add_parser("demo", help="Generate a synthetic, copyright-safe v4 demo")
    demo.add_argument("--outdir")
    demo.set_defaults(func=cmd_demo)
    return parser


def main(argv: list[str] | None = None) -> None:
    args = build_parser().parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
