# Runtime research summary

This page separates bounded engineering results from the playable preview's
[current capabilities](../dashboard.md). Historical comparisons apply to their
recorded revisions and profiles; they are not acceptance of the latest launcher.

Some specialized diagnostics require maintainer-local inputs. Use
[ROM build setup](rom-bootstrap.md) for the supported public build workflow.

## Recorded comparison boundary

The September 2026 original-OS experiment matched 1,908 consecutive selected
actor/camera update states. The first selected-state mismatch was update 1,909;
consumed-VI timing already differed at 1,908. This was selected-state agreement,
not full-RDRAM equality, physical-console timing proof, or campaign completion.
See the retained [boundary record](../planning/phase9-execution-frontier-1909.md).

Qualified observations found the extra pacing message already queued on producer
entry. Word, entry, interval, instruction-effect, and device-event observations
narrowed hypotheses, but did not establish a causal repair of that boundary.
Do not shift comparisons, insert a VI, remove fields, or treat observed timing
constants as a fix. The production ledger determines whether more work is admitted.

## Runtime contracts

| Area | Current reference |
|---|---|
| Absolute deadlines, retirement, interrupt delivery | [Execution clock](../planning/phase9-execution-clock-implementation.md) |
| Guest OS state and reference timing | [OS timing](../planning/phase9-os-clock-qualification.md) |
| Serial-interface completion | [SI timing](../planning/phase9-si-completion-timing.md) |
| GPU results visible to guest CPU | [Framebuffer writeback](../planning/phase9-renderer-cpu-writeback.md) |
| Before/after compiler hooks | [Instruction effects](../planning/phase9-instruction-effect-observation.md) |
| Source attribution and implementation boundaries | [Boot provenance](../../src/boot/PROVENANCE.md) |

The timing notes retain their source-linked paths. Flags and experiments are
not new default behavior from this cleanup. Source tests and current build
configuration determine what is enabled.

## Automated gameplay

Earlier exploration demonstrated startup, checkpoint restoration, generated
navigation, selected destinations, and bounded combat/death/retry cases.
Ten completed seeded jobs varied objectives; they did not prove general
varied-path exploration or complete native parity. A hundred startup repetitions
did not certify a hundred complete campaign slices.

Remaining work includes complete progression coverage, combined recovery,
varied routes, failure minimization with sanitizer replay, and native snapshots.
See the [exploration requirements](../planning/phase9-5-autonomous-exploration.md)
and [slice acceptance tracker](../planning/phase9-acceptance.md).

## Finding earlier results

[Git history](../history.md) retains the detailed run journals, hashes, failed
attempts, and source revisions. Operational evidence and ledgers remain in their
existing local locations. Cleanup does not delete them, change signed results,
or reopen any investigation.
