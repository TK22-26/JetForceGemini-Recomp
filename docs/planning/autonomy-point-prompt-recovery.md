# Lossless point-planner prompt and preflight recovery

## Failure and correction (2026-09-27)

`point-plan-87785a7ef633b3b334481983` was blocked before launching a model:
its prompt contained 20,709 characters, over the unchanged 20,000-character
limit. The ledger has one blocked attempt and its directory contains only
the preflight failure receipt. No worktree, guard record, transcript or model
output exists for that attempt. The failed packet and ledger entry are kept.

Point prompts now compact JSON whitespace and represent repeated homogeneous
objects as explicit column/row tables. Decoding all four payload sections
reproduces every original field and value, including raw clocks/return
addresses, null predictions, qualification limits and all historical rows.
This is not an excerpt or an evidence summary. The original full history facts
remain separately pinned and independently recomputed by consumers.

The retained prompt becomes **18,152 characters**. No prompt limit, comparison
field, runtime behavior or research-round allowance changes. New point plans
are fully validated before packet publication and lease consumption.

## Bounded recovery

The base point planner may have one `-prompt-v1` successor only when the
predecessor is an exact, single-attempt prompt-limit preflight failure. Recovery
checks the ledger, immutable packet digest, source/input pins, failure receipt,
absence of worker activity and all normal packet validation except the original
oversized prompt. It independently revalidates the complete entry-plan ancestry,
runtime and retained facts before enqueueing the replacement.

The replacement preserves the original contract, sources, prerequisites,
read-only authority and zero retry budget. It adds pins for the old packet and
failure receipt. The failed predecessor is not promoted or made a prerequisite
that would need to pass. The supervisor checks recovery again before launch;
point-plan consumers recheck it as well. Changed evidence, unknown failure,
worker activity, a second attempt or a failed replacement cannot authorize
another model run. Existing queued/running/terminal successors are not relaunched.

## Verification and limits

The complete 341-test autonomy suite passes (85.562 seconds), including a
real-subprocess integration test: oversized preflight starts no
worker; the lossless successor starts exactly one read-only typed worker and
seals its result, leaving the original blocked packet unchanged. Focused tests
cover lossless nested tables, heterogeneous rows, qualification/clock retention,
reserved-field rejection, packet/input/receipt tampering, evidence recomputation,
pause, single-successor routing, producer identity coverage and rejection before
publication. Tests also cover normal bounded plan publication and routing a
completed recovery into the interval lane. Interval
intake now uses the same preferred-point
selector as the research driver, so it recognizes the recovered plan and cannot
fork from the old blocked predecessor.

The live research driver has resumed from
`interval-observe-c2ea167fbedae4d4081e7f09` with a two-job budget. It completed
`point-plan-87785a7ef633b3b334481983-prompt-v1` in exactly one attempt; the result
seal SHA-256 is
`20a9647ff6da51fff448b2b3b60ee10ec68e85a52fc8aa3fc06ef71c16d17bd3`.
The model reports `needs-instrumentation`: neither available call anchor
supplies the required all-thread retirement and source-tagged device ordering
before the producer entry. Already measured queue values and counts are not
new causal evidence. The original driver finished with one dispatch and
`paused-or-unsupported`: it had imported the older interval selector before
that code was updated. After this confirmed terminal exit, a new one-job
driver resumed the same observation with the corrected selector. It is
revalidating the completed point result, not rerunning its model. The
ledger audit verifies 127 passed seals among 155 jobs with zero integrity issues;
16 historical failures/blocks remain, including the preserved oversized packet.

This removes a mechanical research handoff failure. It does not fix update
1909, establish device causality, implement general proof construction or
complete the automation loop. The selected-state frontier remains 1908.

The next substantive implementation is an execution/device-event observer,
not another repeat of the already measured queue counts. Local source reads
identify native device selection/assertion and exception acceptance in
`src/boot/native_boot.cpp`, and oracle `check_interupt`, `gen_interupt` and
`update_count` in the retained corrected-Mupen source. Oracle Count is updated
lazily, so sampling its register at arbitrary instruction hooks cannot be
presented as committed engine time. A new observer must distinguish event
deadline, pending-bit assertion and CPU acceptance, preserve raw PC/thread/
return/input context, and prove full-trace/focused-RDRAM non-perturbation on
both sides before its output can justify any repair. This observer is not yet
implemented or accepted at that checkpoint. The subsequent
[device-event observation](phase9-device-event-observation.md) implements the
bounded raw observer and records its qualification; global retirement,
clock alignment and repair acceptance remain unproved.
