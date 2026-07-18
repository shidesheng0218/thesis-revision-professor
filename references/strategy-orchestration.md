# Strategy orchestration

Select a strategy by composition, not by a generic writing checklist.

## Precedence

`academic integrity > school rules > method validity > degree level > discipline convention > corpus pattern > language style`

## Routing dimensions

- degree: master's or doctoral;
- discipline: education, computer science, engineering, economics, management, law, medicine, humanities, arts, or generic;
- method: quantitative, qualitative, mixed methods, experiment, machine learning, engineering design, legal doctrinal, or textual/historical;
- stage: proposal, pre-defense, blind review, final defense, archive;
- chapter function and claim type;
- evidence strength and P0/P1/P2 priority.

Use the packaged `strategy_profiles.json` for deterministic preflight. If a profile component is not located, emit a P1 `needs_review` item with low confidence; do not assert that the component is absent until semantic review verifies it.

## Executable strategy object

Every strategy must declare:

- applicable and excluded conditions;
- evidence requirement and severity;
- operation and prohibited operation;
- facts/formatting that must remain invariant;
- expected benefit and possible side effect;
- acceptance test;
- source, support count, and limitations if derived from corpus data.

Use corpus patterns only for rhetorical or structural guidance. Frequency is not proof of excellence or factual truth.
