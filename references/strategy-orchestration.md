# Multi-dimensional strategy orchestration

Use this layer to select revision strategies instead of applying generic polishing.

## Dimensions

1. **Degree level**
   - Master's: completeness, method fit, bounded conclusions, format compliance.
   - Doctoral: original contribution, theoretical depth, methodological robustness, field positioning.
2. **Discipline**
   - Use `discipline-profiles.md`; never force one field's structure onto another.
3. **Method family**
   - empirical quantitative, qualitative, mixed methods, design/engineering, theoretical, textual, legal doctrinal, practice-based.
4. **Chapter type**
   - abstract, introduction, literature review, theory, method, results, discussion, conclusion.
5. **Evidence strength**
   - direct data, literature support, case material, public fact, structure pattern only, unsupported.
6. **Risk priority**
   - P0 factual/method/citation integrity; P1 academic quality; P2 expression/format.
7. **Corpus match**
   - domestic CNKI-derived patterns for Chinese degree conventions; global patterns for international thesis conventions.
8. **Language operation**
   - clarify, compress, academicize, hedge, connect, restructure, mark unsupported.
9. **Iteration status**
   - first diagnosis, confirmed rewrite, regression, final export.

## Strategy selection rules

- Select a discipline profile from `references/disciplines/` when the user provides `--discipline`; if the discipline is unknown, use the generic profile and mark the report with a discipline-confirmation note.
- If evidence is weak, choose **mark-and-request** before rewriting.
- If structure is weak but evidence is sufficient, choose **reorder-and-bridge**.
- If method cannot answer the question, choose **scope-reduction** or **method-supplement request**.
- If conclusion exceeds evidence, choose **hedge-and-bound**.
- If literature review is list-like, choose **cluster-compare-gap**.
- If citations are inconsistent, choose **citation-repair before language polish**.
- If Word export is requested, preserve original text traceability and include a revision log.

## Strategy object

```json
{
  "strategy_id": "LR-CLUSTER-COMPARE-GAP",
  "applies_to": ["literature_review"],
  "risk_level": "P1",
  "evidence_requirement": "SOURCE_REFERENCE",
  "action": "Group sources by theme, compare positions, identify gap, and connect to research question.",
  "do_not": "Invent missing literature or claim an uncited gap as fact."
}
```
