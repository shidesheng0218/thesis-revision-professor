# Discipline profiles

Use the closest profile. If uncertain, ask for the user's discipline and school requirements.

## Computer science

Expect clear problem definition, method/algorithm/system design, experiments or evaluation, baselines, metrics, limitations, and reproducibility notes.

## Engineering

Expect design constraints, technical route, experiments/simulation, performance indicators, failure analysis, and application boundary.

## Management and economics

Expect theory/model, variables, data source, empirical method or case design, robustness/validity discussion, and practical implications.

## Education

Expect educational problem, literature and policy context, participants/materials, intervention or survey design, analysis, and ethical limits.

## Humanities

Expect concept clarity, textual/material basis, argument structure, literature debate, close analysis, and cautious claims.

## Law

Expect legal issue, normative framework, statutes/cases/policies, doctrinal analysis, comparative analysis when relevant, and bounded recommendations.

## Medicine and life sciences

Expect ethics, sample, protocol, statistical method, data limits, clinical/biological significance, and cautious causal language.

## Arts

Expect creative/problem context, work or case analysis, method of practice/research, aesthetic or design rationale, and documentation of process.

## Interdisciplinary

State the primary evaluation lens first, then map secondary fields. Avoid applying one discipline's rubric blindly to another.

## Institution profile layout fields

An institution profile JSON may declare layout requirements alongside
`required_sections`:

- `font.eastAsia`: required default East Asian font name, compared against
  `word/styles.xml` `w:docDefaults` `w:rFonts/@w:eastAsia`;
- `font.body_pt`: required default body size in points, compared against
  `w:docDefaults/w:sz` (half-points, divided by two);
- `margins_mm`: per-side page margins in millimetres (`top`, `right`,
  `bottom`, `left`), compared against every `w:sectPr/w:pgMar` (twips,
  1 mm ≈ 56.6929 twips) with a ±1 mm tolerance.

A mismatch raises a P2 `PROF-LAYOUT-FONT` / `PROF-LAYOUT-MARGINS` finding that
requires author confirmation; final layout authority stays with the school
regulations and human typesetting. Fields that are absent from the profile are
not checked, and layout facts missing from the document (no styles part, no
section margins) are treated as unknown rather than non-compliant.
