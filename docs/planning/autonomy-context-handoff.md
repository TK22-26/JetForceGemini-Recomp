# Reuse a freshly validated context within one call

## Change (2026-09-27)

Every `state_word_experiment.diagnosis_context` used to call
`candidate_feedback.checked_outcome`, which fully validates the candidate's
review/baseline, discard that returned context, then call `verified_context`
again to recover it. Recursive history verification magnified this duplicate
work. The earlier whole-plan profile recorded 106 review-context verifications
for 53 state-word plan contexts.

`candidate_feedback.checked_outcome_context` now returns the same facts,
implementation packet and evidence plus its freshly validated review context.
The original three-value `checked_outcome` interface remains available and
returns identical data. `diagnosis_context` consumes the expanded result
without walking the same review/baseline again merely to retrieve it.

This is **not a cache**. Each call still validates the ledger seal, packet,
review/build/source/runtime lineage, supporting files, comparison scope,
input-prefix report and disposition. A later call rechecks changed evidence.
The independent before/after checks around measurement remain unchanged.
The helper is included in the state-word producer digest, which now flows
through entry and point producer digests and the existing interval closure.
This is not a claim that every historical dependency closure is complete.

## Evidence and limits

On the saved diagnosis `experiment-feedback-ef23e04b636937c192656e3a`, one
read-only before/after check measured:

| | Review validations | Wall seconds |
| --- | ---: | ---: |
| Before | 2 | 1.0868874 |
| After | 1 | 0.6065971 |

The complete sorted-JSON context, with filesystem paths rendered as strings,
has the same SHA-256 before and after:
`ee2a57715ac63e617e17fdfa7ebcbae92749cf75fd992b22ff74f46093235462`.
This is a single diagnostic-context check, not a controlled whole-loop speedup
claim. Recursive observation validation remains expensive.

All 325 autonomy tests pass. Added tests cover exact legacy projection,
one review validation per invocation, fresh checking after supporting-file
mutation, diagnosis/baseline binding, and helper changes propagating to all
four measurement producer identities. `git diff --check` passes. A separate
read-only full recomputation of `interval-observe-c2ea167fbedae4d4081e7f09`
completed in 227.412 seconds, including both before/after checks and 106
review verifications across its history. It reproduced the sealed result
exactly: SHA-256
`d373c954fd24cb739274d3ae310d7aade4be4f3c7d210110ad7e063b92382ae2`,
qualification passed, prediction false. This concurrent run has no matched
whole-result timing control and is not a speedup benchmark.

No capture, model result, input, comparison field, runtime code or reference
was changed by this optimization. General proof construction, reviewed repair
integration, gameplay coverage and recovery/endurance acceptance remain open.
