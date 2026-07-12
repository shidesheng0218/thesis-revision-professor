# Revision loop

Use this loop for substantial thesis work. Keep each round small enough to review safely.

## 1. Baseline Scan

Map the thesis before editing:

- degree level: master or doctoral;
- discipline and methodology family;
- chapter hierarchy;
- research question;
- object of study;
- data/materials;
- method;
- main findings;
- references and citation style;
- target standard: proposal, pre-defense, blind review, final defense, or archive.

Use `scripts/extract_docx_text.py` and `scripts/structure_map.py` when a `.docx` file is available.

## 2. Evidence Audit

Check whether each substantive claim has support. Classify evidence as:

- user original text;
- user data/materials;
- user references;
- corpus-derived structure pattern;
- format or degree standard;
- verified public fact.

Unsupported claims must be marked, not strengthened.

## 3. Corpus Strategy Match

Match the thesis section to strategy cards:

- abstract;
- introduction;
- literature review;
- theory/framework;
- methodology;
- results;
- discussion;
- conclusion;
- innovation statement;
- limitations.

Use corpus strategies only as structural guidance. Do not copy corpus wording.

Use `references/strategy-orchestration.md` to select strategies across degree level, discipline, method family, chapter type, evidence strength, risk priority, corpus match, language operation, and iteration status.

## 4. Professor Panel Review

Run the roles in `professor-panel.md`. Produce short, non-overlapping findings.

## 5. Priority Gate

Classify issues:

- **P0**: likely to block graduation, blind review, defense, or factual integrity.
- **P1**: clearly weakens academic quality.
- **P2**: style, format, readability, and minor consistency.

Handle P0 before P1, and P1 before P2.

## 6. Revision Plan

Before rewriting, produce:

- issue;
- evidence;
- proposed action;
- expected improvement;
- risk;
- required user confirmation or source material.

## 7. Controlled Rewrite

Rewrite only confirmed scope. Preserve:

- facts;
- numbers;
- sample sizes;
- dates;
- cited authors;
- conclusion boundaries;
- discipline-specific terminology.

Mark unverifiable additions as `[需作者确认：原因]`.

## 8. Regression Review

After rewriting, check:

- original issue solved;
- no new unsupported claim;
- no citation mismatch;
- no change to data facts;
- no overclaiming;
- no cross-discipline style mismatch.

When both original and revised files exist, run `scripts/diff_audit.py` to detect risky changes to numbers, years, citations, and strong claims.

## 9. Word Export

Create final `.docx` files according to `word-output-spec.md`.

For a one-command diagnostic round, run:

```bash
python scripts/run_revision_loop.py input.docx --level master --discipline unknown --outdir outputs/round-001
```

## Convergence criteria

Stop a revision round when:

- all P0 issues are removed or explicitly assigned to the author;
- P1 issues are reduced to acceptable risk;
- blind-review risk is small-revision or pass;
- evidence gaps are clearly marked;
- Word deliverables are generated.
