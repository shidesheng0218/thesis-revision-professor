# Word output specification

Deliver three `.docx` files:

- `论文修改稿.docx`;
- `修改说明与盲审风险报告.docx`;
- `逐条修改清单.docx`.

## Revision manuscript

Clone the original DOCX package and patch only approved, located plain-text paragraphs. Preserve headings, tables, images, media, formulas, footnotes, fields, headers, footers, numbering, relationships, and package parts. Use Word tracked changes by default.

Do not auto-edit paragraphs containing drawings, objects, fields, footnote/endnote references, or other complex content. Put them in the manual queue.

After every patch, audit numbers, years, citations, media parts, and package parts. When any unapproved change appears, retain the candidate as `论文修改候选稿-回归未通过.docx` and restore the original as `论文修改稿.docx`.

## Reports

The risk report must include overall risk, P0/P1/P2 findings, locators, confidence, evidence rationale, strategy/method confirmation needs, regression result, and next step.

The revision log must include item ID, status, reason, locator, and whether author confirmation is needed.

Render final DOCX files for visual QA when a renderer is available. Verify headings, tables, Chinese glyphs, tracked-change rendering, clipping, and page layout.
# v4 Word output rules

The original package parts, styles, relationships and media are copied before
any edit. Confirmed text replacements use `w:del`/`w:ins` when tracking is
enabled. Manual-only findings may be anchored with `w:commentRangeStart`,
`w:commentRangeEnd` and `w:commentReference`; the corresponding
`word/comments.xml` part and relationship must be present together.

If a paragraph contains drawings, fields, footnotes, endnotes, formulas or
objects, the patcher must leave it unchanged and emit a manual action. A
candidate with a failed regression audit is quarantined and the unchanged
source is delivered as the final manuscript.
