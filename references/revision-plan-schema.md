# Revision plan schema

`revision_plan.json` is the contract between diagnosis and controlled rewrite. It prevents uncontrolled thesis rewriting.

## Fields

- `plan_id`: stable plan id for the round.
- `mode`: usually `staged_confirmation`.
- `source`: original thesis path.
- `items`: ordered revision actions.

## Item fields

```json
{
  "id": "P0-EVIDENCE-001",
  "confirmed": false,
  "location_hint": "第五章 结论",
  "target_text": "本文认为教学活动能够促进学习体验提升。",
  "problem": "结论缺少数据支撑",
  "action": "mark_and_request",
  "evidence_class": "SOURCE_ORIGINAL",
  "requires_author_confirmation": true,
  "proposed_rewrite": "基于现有材料，本文可以初步认为教学活动与学习体验改善之间存在关联，但仍需补充数据或访谈证据。",
  "risk": "不得新增未验证结果"
}
```

## Application rules

- Apply only items with `confirmed: true`.
- For unconfirmed P0 evidence gaps, mark the original sentence with `[需作者确认：原因]`.
- Do not add new citations, data, cases, or findings.
- Run regression audit after application.
