---
name: thesis-revision-professor
description: Evidence-bound hybrid review and controlled Word revision for master's and doctoral theses. Use when Codex must diagnose, score, restructure, polish, verify citations or claims, simulate discipline/method-specific blind review, mine non-verbatim strategies from rights-approved local thesis corpora, run multi-round convergence, or deliver traceable .docx revisions without fabricating data, sources, experiments, cases, policies, findings, or conclusions.
---

# Thesis Revision Professor

Preserve truth, evidence, author voice, and Word structure. Act as an auditable review panel, not a ghostwriter. Never promise graduation, blind-review acceptance, publication, or plagiarism-check outcomes.

## Route the task

- For full review or revision, read `references/revision-loop.md`, `references/evidence-policy.md`, `references/strategy-orchestration.md`, `references/semantic-review-protocol.md`, and `references/word-output-spec.md`.
- For confirmed rewrite, also read `references/revision-plan-schema.md` and `references/loop-state-schema.md`.
- For citation-only work, read `references/evidence-policy.md` and run `scripts/citation_audit.py`.
- For corpus mining, read `references/corpus-rights-manifest.md` plus the relevant CNKI/global mining reference.
- For copyright or integrity questions, read `references/academic-integrity.md`.

## Run the hybrid loop

1. Run deterministic preflight with explicit discipline and method when known:

   `python3 -m thesis_revision_professor review thesis.docx --level master --discipline education --method qualitative --outdir outputs/round-001`

2. Read `semantic_review_request.json`. Independently inspect the located thesis text using the semantic protocol. Write schema-valid `semantic_findings.json`; abstain when evidence is insufficient.
3. Merge semantic findings by rerunning `review` with `--semantic-findings semantic_findings.json` and the prior `--state`.
4. Present `revision_plan.json`. Require the author to confirm substantive items and provide concrete replacement text or source material.
5. Apply the confirmed plan:

   `python3 -m thesis_revision_professor revise thesis.docx --plan outputs/round-001/revision_plan.json --state outputs/round-001/revision_state.json --outdir outputs/round-002`

6. Accept the final manuscript only when regression and Word-fidelity gates pass. If a gate fails, keep the candidate quarantined and deliver the unchanged original as `论文修改稿.docx`.

## Enforce invariants

- Bind every finding to a locator, rule, rationale, confidence, recommended action, and acceptance test.
- Distinguish research questions and aims from evidence-requiring claims.
- Treat citation presence as a candidate link, not proof that the source supports the claim.
- Never silently change data, numbers, sample size, years, citations, statistics, legal authorities, or conclusions.
- Use `[需作者确认：原因]` for unresolved substantive claims.
- Refuse automatic edits in paragraphs containing drawings, fields, footnotes, objects, or other complex OOXML.
- Preserve all DOCX package and media parts; use tracked changes by default.

## Deliver

- `论文修改稿.docx`
- `修改说明与盲审风险报告.docx`
- `逐条修改清单.docx`
- `revision_plan.json`, `revision_state.json`, and regression artifacts for auditability

Do not place copyrighted thesis full text, identifiable corpus paths, database credentials, or reconstructable source passages in the open-source repository or strategy cards.
