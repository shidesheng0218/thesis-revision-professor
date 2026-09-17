# External feedback import protocol

`thesis-review import-feedback <意见.txt> --review <round-dir> --outdir <dir>`
converts blind-review or advisor opinions into the same finding/plan structure
as internal findings, so external opinions join the controlled revision loop
instead of floating outside it.

## Splitting rules

Heuristic, coarse by design (切不开就整段一条):

1. Numbered items win: lines starting with `第X条`, `N.`/`N、`, or `(N)` split
   the text into items.
2. Otherwise, blank-line-separated paragraphs containing `建议/不足/问题/缺失/补充`
   or strong wording each become one item.
3. Otherwise the whole text is one item.

## Severity and confidence

- P0: contains 必须/错误/严重/不通过/抄袭/造假.
- P1: contains 建议/不足/问题/缺失/补充.
- P2: everything else.
- Confidence is fixed at 0.5; every feedback finding requires author
  confirmation (`evidence_class: EXTERNAL_REVIEW`).

## Locating

Chapter hints (`第X章`, Chinese or Arabic numerals) and section hints
(`3.2节`) are matched against main-document heading paragraphs; the heading
paragraph's locator becomes the finding locator. Anything unmatched (page
numbers, unnamed locations) yields `locator: None` and
`needs_manual_locator: true`.

## Degradation principles

- A finding without a locator never enters automatic patching: it stays on
  the `manual_only` path of the revision plan.
- A located finding enters the `mark_unconfirmed` path and is only patched
  after explicit author confirmation, like any internal item.
- The tool never edits the opinion text, never invents locators, and never
  upgrades severity on its own.

## Mapping table semantics

`feedback_mapping.json` binds each opinion item to its finding id, plan item
id, locator, and status (待定位 / 待作者确认). The《意见—修改对照表.docx》is
written at import time and refreshed automatically by `revise` when the plan
directory contains `feedback_mapping.json`; after revise, statuses become
已修改 / 需作者确认 / 需人工处理 / 待定位. The 不采纳理由 column is left blank
for the author to fill in when an opinion is rejected; the tool does not
decide non-adoption.
