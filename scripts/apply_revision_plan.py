#!/usr/bin/env python3
"""Apply confirmed revision plan items and mark unconfirmed evidence gaps."""

from __future__ import annotations

import argparse
from pathlib import Path
from thesis_utils import read_json, read_text, simple_docx, write_json


def apply_plan_to_text(text: str, plan: dict) -> tuple[str, list[dict]]:
    applied = []
    revised = text
    for item in plan.get("items", []):
        target = item.get("target_text") or ""
        if not target:
            continue
        marker = " [需作者确认：缺少支撑材料]"
        if item.get("confirmed"):
            replacement = item.get("proposed_rewrite") or target
            if target in revised:
                revised = revised.replace(target, replacement, 1)
                applied.append({"id": item.get("id"), "status": "applied_confirmed", "action": item.get("action")})
        elif item.get("requires_author_confirmation"):
            if target in revised and marker not in target:
                revised = revised.replace(target, target + marker, 1)
                applied.append({"id": item.get("id"), "status": "marked_unconfirmed", "action": item.get("action")})
    if applied:
        revised += "\n\n修改执行说明\n"
        for item in applied:
            revised += f"- {item['id']}: {item['status']} ({item['action']})\n"
    return revised, applied


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("input")
    parser.add_argument("--plan", required=True)
    parser.add_argument("--outdir", required=True)
    args = parser.parse_args()

    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    plan = read_json(args.plan)
    original = read_text(args.input)
    revised, applied = apply_plan_to_text(original, plan)
    revised_txt = outdir / "论文修改稿.txt"
    revised_docx = outdir / "论文修改稿.docx"
    log_json = outdir / "applied_revision_log.json"
    revised_txt.write_text(revised, encoding="utf-8")
    simple_docx(revised_docx, "论文修改稿", revised)
    write_json({"plan": args.plan, "applied": applied, "output": str(revised_docx)}, log_json)
    print(f"wrote {revised_docx}")


if __name__ == "__main__":
    main()
