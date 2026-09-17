# Loop state schema

`revision_state.json` is the audit memory for cross-round review.

## Issue lifecycle

`open → confirmed → applied → verified → resolved`

Alternate states: `waived` (author accepts documented risk), `blocked` (needs material or complex Word edit), `reopened` (a resolved or waived issue reappears in a later round), and `regressed` (an issue whose status was `applied` reappears in a later round's findings with the same fingerprint — the applied change did not take effect or was reverted).

Every issue uses a stable fingerprint generated from `rule_id` and locator only — the finding text is display data and never feeds the digest, so reviewer wording changes cannot break a resolved/reopened/regressed chain. Do not append duplicate P0/P1/P2 lists each round. The locator is `word/document.xml#para={w14:paraId}` (no enumeration index), so a paragraph's fingerprint stays stable across rounds once its `w14:paraId` exists in the file; documents without paraIds get deterministic ids injected on the first controlled patch. Footnotes, endnotes, headers and footers are parsed too and addressable via their part-prefixed locators (`word/footnotes.xml#para=...`), but only `word/document.xml` locators may drive automatic patching. States written before this decoupling keep wording-dependent fingerprints; on the next `advance_state` they are matched by their stored fingerprint, by the legacy `sha256(rule_id|locator|normalized finding)` value, or by the recomputed current value, and are rewritten onto the current fingerprint.

## Required state fields

- source hash, round, phase, and status;
- active issues, resolved issues, and new risks;
- confirmation queue and selected strategy;
- rubric history and score delta;
- deliverables and regression summary;
- convergence gates and stable-round count;
- compact round history.
- `max_rounds` (default `5`), `loop_trace`, and `manual_review_required` when the limit is exhausted.

## Gates

`p0_clear`, `p1_verified_or_waived`, `evidence_controlled`, `regression_passed`, and `word_fidelity_checked` must all be true before `can_export_final` is true.
