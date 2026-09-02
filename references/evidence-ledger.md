# Evidence ledger protocol

The ledger is the source-of-truth boundary for substantive revision.

## Required properties

- Every evidence item has an `evidence_id`, type, relative path, SHA-256 hash,
  rights status and a human-readable locator.
- `usable` means the file exists and the author has a permitted rights status;
  it does not mean that the file semantically proves a claim.
- `verified_by_author=true` is required before a fact can authorize an
  automatic replacement of a number, date, citation, result or conclusion.
- Missing or contradictory evidence produces a finding or a request for
  author confirmation; it never produces invented content.

## Supported material boundary

The default local adapter accepts DOCX, Markdown, plain text, JSON and CSV
materials. Other formats must be converted by the user or handled by an
explicit optional adapter. The repository stores schemas and synthetic
fixtures only, never thesis full text from CNKI, Wanfang, ProQuest or similar
services.
