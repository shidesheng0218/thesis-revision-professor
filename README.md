# thesis-revision-professor

An open-source Codex skill for evidence-bound master's and doctoral thesis revision, professor-style review, corpus-derived writing strategy mining, and final Word `.docx` export.

This repository does not include CNKI, Wanfang, ProQuest, university repository, or other real copyrighted thesis full text. Users must provide and use corpus files only when they have lawful access and permission.

## What it does

- Reviews thesis structure, evidence, citations, language, and blind-review risk.
- Runs a staged revision loop: diagnose → plan → confirm → rewrite → regress → export.
- Provides a one-command diagnostic loop engine that creates structured JSON and Word reports.
- Extracts non-verbatim writing strategies from legally available local corpora.
- Produces Word `.docx` deliverables for the revised thesis, review report, and revision log.

## Academic integrity

The skill is for revision, review, and research-expression improvement. It must not be used to fabricate data, citations, experiments, interviews, policy facts, or conclusions. It does not guarantee graduation, blind-review acceptance, publication, or plagiarism-check results.

## Quick validation

```bash
python scripts/export_docx.py --title "测试报告" --body tests/fixtures/sample_report.md --out /tmp/test_report.docx
python scripts/extract_docx_text.py assets/examples/fake_thesis_sample.docx --out /tmp/extracted.json
python scripts/rubric_score.py assets/examples/fake_thesis_sample.docx --level master --out /tmp/score.json
python tests/run_smoke.py
```

## One-command loop

```bash
python scripts/run_revision_loop.py assets/examples/fake_thesis_sample.docx \
  --level master \
  --discipline education \
  --outdir outputs/round-001
```

The command generates:

- `extracted.json`
- `structure.json`
- `citation_audit.json`
- `evidence_audit.json`
- `rubric_score.json`
- `professor_panel.json`
- `round_payload.json`
- `revision_state.json`
- `论文修改稿.docx`
- `修改说明与盲审风险报告.docx`
- `逐条修改清单.docx`
