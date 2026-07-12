# thesis-revision-professor

中文 | An evidence-bound thesis revision skill and CLI for master's and doctoral dissertations.

`thesis-revision-professor` helps Codex and command-line users review, plan, and safely revise thesis drafts. It focuses on professor-style diagnosis, evidence auditing, staged revision, corpus-derived writing strategies, and Word `.docx` outputs.

It does **not** fabricate data, citations, experiments, interviews, cases, or conclusions. It does **not** include CNKI, Wanfang, ProQuest, or other copyrighted thesis full text.

## 30-second quick start

```bash
git clone https://github.com/shidesheng0218/thesis-revision-professor.git
cd thesis-revision-professor
python -m thesis_revision_professor review assets/examples/fake_thesis_sample.docx \
  --level master \
  --discipline education \
  --outdir outputs/round-001
```

Generated files:

- `outputs/round-001/修改说明与盲审风险报告.docx`
- `outputs/round-001/逐条修改清单.docx`
- `outputs/round-001/论文修改稿.docx`
- `outputs/round-001/revision_plan.json`
- `outputs/round-001/revision_state.json`

## Install as a Codex skill

```bash
mkdir -p ~/.codex/skills
git clone https://github.com/shidesheng0218/thesis-revision-professor.git ~/.codex/skills/thesis-revision-professor
```

Restart Codex, then ask:

```text
Use thesis-revision-professor to review my master's thesis:
/path/to/thesis.docx

First produce a blind-review risk assessment, P0/P1/P2 issues, and an evidence-bound revision plan.
Do not fabricate data, citations, or conclusions. Export Word .docx reports.
```

## Optional CLI install

```bash
pip install -e .
thesis-review review assets/examples/fake_thesis_sample.docx --level master --discipline education --outdir outputs/round-001
thesis-review status outputs/round-001/revision_state.json
```

## Main commands

```bash
python -m thesis_revision_professor review thesis.docx --level master --discipline education --outdir outputs/round-001
python -m thesis_revision_professor revise thesis.docx --plan outputs/round-001/revision_plan.json --outdir outputs/round-002
python -m thesis_revision_professor corpus ./legal-corpus --out outputs/strategy_cards.md
python -m thesis_revision_professor status outputs/round-001/revision_state.json
python -m thesis_revision_professor demo
```

## What the loop does

1. Baseline scan.
2. Evidence audit.
3. Citation audit.
4. Configurable rubric scoring.
5. Multi-role professor panel review.
6. Revision plan generation.
7. Controlled rewrite after confirmation.
8. Regression audit.
9. Word export.

## Academic integrity and copyright

- Use only thesis corpora you can lawfully access.
- Do not upload CNKI/Wanfang/ProQuest thesis full text into this repository.
- Corpus mining stores aggregate structure and strategy patterns, not source paragraphs.
- The tool does not guarantee graduation, defense success, blind-review success, publication, or plagiarism-check outcomes.
- Unsupported claims are marked as `[需作者确认]` rather than invented.

## Validation

```bash
python tests/run_smoke.py
python scripts/release_gate.py
```
