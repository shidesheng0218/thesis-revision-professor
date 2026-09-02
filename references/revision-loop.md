# Hybrid revision loop

Use a two-layer, five-round war-room loop. The deterministic layer protects facts and Word fidelity; the Codex semantic layer performs independent professor-style reasoning.

## Outer loop

1. **Parse and baseline**: create `document_model.json` with source hash, stable locators, headings, media parts, and paragraph hashes.
2. **Typed claim—evidence audit**: classify claims as research aim/question, method statement, literature, result, causal, statistical, legal/policy, contribution, interpretation, or general factual claim. Research questions and aims are normally `not_applicable`, not missing evidence.
3. **Strategy route**: combine academic-integrity rules, school rules, degree level, discipline, method family, thesis stage, and language conventions. Confirm low-confidence discipline or method inference.
4. **Deterministic preflight**: run citation, structure, claim, and DOCX package checks. Mark low-confidence absence as `needs_review`, never as a fabricated hard fact.
5. **Independent semantic panel**: use `semantic_review_request.json` and `semantic-review-protocol.md`. Include evidence and counterevidence; abstain where verification is impossible.
6. **Adversarial review**: actively search for contradictions, overclaiming, scope drift, and method-result mismatch; preserve reviewer disagreement.
7. **Adjudication and plan**: deduplicate by stable fingerprint, prioritize dependencies, generate located `revision_plan.json`, then obtain author confirmation.
8. **Controlled Word patch**: change only confirmed, concrete, located text. Preserve package parts. Use tracked changes for approved rewrites and comments for manual-only findings.
9. **Regression and re-review**: audit numbers, years, citations, media/package parts, cross-section consistency, and re-run review on the candidate.
10. **State transition**: record open, confirmed, applied, verified, resolved, waived, blocked, reopened, or regressed issues.

## Inner patch loop

For one atomic patch: propose → check evidence/invariants → author confirms → patch → regression audit → accept or roll back.

## Stop conditions

Converge only when all are true:

- no open P0;
- remaining P1 items are verified, waived with rationale, or explicitly assigned to the author;
- unresolved material claims are controlled and not expressed as facts;
- all accepted patches pass regression and Word-fidelity gates;
- no new P0/P1 risk appears in the final independent review.

Stop and request author material after two low-improvement rounds or five total rounds by default. If five rounds are exhausted without passing the gates, set `manual_review_required`. Never keep generating cosmetic advice to simulate progress.
