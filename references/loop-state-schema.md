# Loop state schema

The loop state is the memory layer for multi-round thesis revision. It prevents repeated advice, tracks evidence gaps, and makes convergence auditable.

## Top-level fields

- `round`: current loop round.
- `phase`: current phase, one of `baseline_scan`, `revision_plan`, `controlled_rewrite`, `regression_review`, `word_export`.
- `baseline`: thesis metadata and structure summary.
- `scores`: chronological rubric scores.
- `p0`, `p1`, `p2`: open issues by priority.
- `resolved`: issues solved in prior rounds.
- `new_risks`: risks introduced by edits.
- `evidence_gaps`: claims or sections requiring author confirmation.
- `confirmation_queue`: items the author must confirm before rewriting.
- `strategy_matches`: corpus or rule strategy cards selected for the current thesis.
- `deliverables`: generated files.
- `convergence`: boolean gates.
- `user_preferences`: durable preferences such as conservative style or staged confirmation.
- `history`: round-level payloads.

## Issue object

```json
{
  "id": "P0-METHOD-001",
  "priority": "P0",
  "role": "method_professor",
  "dimension": "method",
  "finding": "The method cannot support the claimed causal conclusion.",
  "evidence": "Conclusion uses causal language but methodology describes interviews only.",
  "recommended_action": "Bound the conclusion or add confirmed causal evidence.",
  "evidence_class": "SOURCE_ORIGINAL",
  "requires_author_confirmation": true
}
```

## Convergence gates

- `p0_clear`: all P0 issues solved or assigned to author.
- `p1_acceptable`: remaining P1 issues do not block the target milestone.
- `risk_minor_or_pass`: blind-review risk is `minor revision` or `pass`.
- `evidence_gaps_marked`: unsupported content is marked.
- `word_deliverables_generated`: required `.docx` files exist.

Do not claim convergence unless all gates are true.
