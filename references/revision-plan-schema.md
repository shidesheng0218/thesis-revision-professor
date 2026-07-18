# Revision plan schema

`revision_plan.json` is a source-hash-bound contract between diagnosis and controlled rewrite.

## Plan fields

- `source_hash`, `level`, `discipline`, `method`, and stage;
- `mode: staged_confirmation`;
- item-level stable locator, paragraph hash, target text, risk, acceptance test, and allowed invariant changes.

## Item modes

- `mark_unconfirmed`: preserve the claim and append an author-confirmation marker; never treat it as repaired evidence.
- `replace_text`: apply only when `confirmed: true`, the locator and target hash match, and `proposed_rewrite` is concrete.
- `manual_only`: never auto-edit; used for restructuring, source repair, complex OOXML, or missing research material.

```json
{
  "id": "PLAN-CLM-00021",
  "confirmed": false,
  "locator": "word/document.xml#para=00A1;index=48",
  "target_hash": "...",
  "target_text": "本文证明……",
  "patch_mode": "mark_unconfirmed",
  "evidence_class": "SOURCE_ORIGINAL",
  "requires_author_confirmation": true,
  "proposed_rewrite": "本文证明……",
  "allowed_changes": {"numbers": [], "years": [], "citations": []},
  "acceptance_test": "补充可定位证据或降低强断言。"
}
```

Reject a plan if its `source_hash` does not match the input. Any unlisted number, year, citation, media, or package-part change fails regression and rolls back the final manuscript.
