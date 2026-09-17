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

## Locators and namespaces

Paragraph locators are `word/document.xml#para={w14:paraId}`; the enumeration
index is never part of the identity. When a source file lacks `w14:paraId`
attributes, the patcher assigns deterministic unique ones while writing the
candidate, so locators become file-stable from the first controlled patch.
Serialized `word/document.xml` keeps the original namespace prefixes, and every
prefix listed in `mc:Ignorable` must keep its `xmlns` declaration so Word does
not prompt to repair the file.

Paragraphs in other package parts (`word/footnotes.xml`, `word/endnotes.xml`,
`word/header*.xml`, `word/footer*.xml`) are parsed with the same rules and
carry their part name in the locator, e.g. `word/footnotes.xml#para=...`.
Automatic patching is limited to `word/document.xml`: patch requests targeting
any other part are blocked with `unsupported_part_requires_manual_edit` and
stay in the manual queue. Header/footer paragraphs containing field codes
(page numbers) are marked as complex content and are never auto-edited.
