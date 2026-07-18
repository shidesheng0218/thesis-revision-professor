# Loop state schema

`revision_state.json` is the audit memory for cross-round review.

## Issue lifecycle

`open → confirmed → applied → verified → resolved`

Alternate states: `waived` (author accepts documented risk), `blocked` (needs material or complex Word edit), `reopened` (resolved issue returns), and `regressed` (a patch creates a new risk).

Every issue uses a stable fingerprint generated from `rule_id`, locator, and normalized finding. Do not append duplicate P0/P1/P2 lists each round.

## Required state fields

- source hash, round, phase, and status;
- active issues, resolved issues, and new risks;
- confirmation queue and selected strategy;
- rubric history and score delta;
- deliverables and regression summary;
- convergence gates and stable-round count;
- compact round history.

## Gates

`p0_clear`, `p1_verified_or_waived`, `evidence_controlled`, `regression_passed`, and `word_fidelity_checked` must all be true before `can_export_final` is true.
