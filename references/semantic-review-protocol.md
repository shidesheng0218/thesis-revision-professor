# Semantic professor review protocol

Use this protocol after deterministic preflight creates `semantic_review_request.json`.

## Independent review

1. Read only the located source text, claim graph, selected discipline/method protocol, and user-provided evidence.
2. Select reviewers dynamically: chief argument reviewer, discipline expert, method expert, citation expert, integrity/ethics expert, adversarial blind reviewer, and Word editor only when relevant.
3. Check the claim against supporting and counter-evidence. Citation presence alone is not support.
4. Abstain when the source is unavailable, the method cannot be inferred, or evidence cannot be verified.
5. Do not repeat deterministic findings unless semantic analysis adds a specific rationale or counterexample.

## Required finding

Every finding must contain `rule_id`, `reviewer`, `locator`, `claim_ids`, `evidence_ids`, `severity`, `confidence`, `finding`, `rationale`, `counterevidence`, `recommended_action`, `acceptance_test`, and `requires_author_confirmation`.

Use P0 only for clear integrity, method-validity, unsupported strong-result, or citation-correspondence failures. Use P1 for material academic-quality weaknesses. Use P2 for expression and presentation.

## Validation

`rule_id`, `reviewer`, `locator`, `severity`, `confidence`, `finding`, `rationale`, `recommended_action`, and `acceptance_test` are required and must be non-empty; `severity` must be `P0`/`P1`/`P2`; `confidence` must be a number in `[0, 1]`; `locator` must look like `word/document.xml#para=...` (the historical `;index=` form is still accepted). `claim_ids`, `evidence_ids`, `counterevidence`, and `requires_author_confirmation` are optional and fall back to defaults.

Findings failing these checks are rejected individually — the review run continues and records each rejection with its reasons in `semantic_rejections.json`, so nothing is silently dropped. A structurally invalid payload (not a JSON object, or `findings` not a list) fails the whole run with an error.

Return `{"findings": [...]}` and validate it by passing the file to `review --semantic-findings`.
