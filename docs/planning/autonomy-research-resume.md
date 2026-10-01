# Resume the durable research tail without repeated dispatch validation

## Measured problem (2026-09-27)

The interval follow-up diagnosis passed. The state-word planner
`experiment-plan-4239ff8597f4d69da16c3faf` and entry planner
`entry-plan-d31b18fdf8ca2936643953c3` both correctly returned
`needs-instrumentation`: completed-update words and function-entry registers
alone cannot distinguish VI-event ordering from a delayed graphics-queue
receive/continuation. These are unsupported-method results, not new gameplay
measurements or fixes.

Resuming the chain exposed costly repeated ancestry walks before dispatch.
A read-only `cProfile` run of the saved word plan's full `plan_context` took
170.039 seconds (including profiler overhead), with 53 word-plan contexts,
106 review-context checks, 1,875 subprocess calls and 750 runtime digests.
The old dispatcher invoked these full validators again at each earlier lane
just to locate the next unfinished stage. Internal recursive validation is
still expensive; eliminating repeated dispatch walks is not a claim that all
of that cost has been removed.

## Change and integrity boundary

`scripts.autonomy.research_cycle` now discovers the deepest existing typed
plan using deterministic IDs and ledger states. A passed plan supplies only
a routing hint after checking its seal, packet, schema and output digests.
The selected executor still validates its complete ancestry before queueing
new work. No cached context, timestamp-only trust, skipped measurement check,
changed comparison or larger model budget is introduced.

Existing queued/running/failed plans are returned without relaunching them.
A completed observation goes through the normal independently recomputed
feedback path. A terminal unsupported report requires full plan validation;
the routing hint's reason is not accepted as the final result. Historical
point plans retain their bounded anchor-refresh path. User pause and dispatch
budgets remain enforced by the outer driver and executors.

Caller discovery also searches the exact big-endian JAL/NOP byte patterns for
the already bounded target set, instead of decoding every RDRAM word in
Python. Every snapshot's call, delay slot and entry bytes are still checked.
Alignment, ordering, the candidate limit and the prior trailing boundary are
preserved. No evidence cache is used. On the eight retained 4 MiB snapshots
for updates 1907-1910 and 15 target addresses, the old decoder and new search
returned exactly the same two candidates. The measured scan time was 0.16835
versus 0.06085 seconds, about 2.77x for this scan alone, not the whole workflow.
Forty seeded synthetic image sets also match the independent exhaustive decoder.

## Controlled handoff

The old dispatcher (PID 6284, started 01:30:53 local) was deliberately stopped
at 01:48:10 after checking that the ledger had no active job and the completed
word/entry plans were sealed. This was an implementation upgrade, not a
timeout retry. Its results were preserved. The updated dispatcher resumed
the same interval observation with a two-job budget; it must not repeat either
completed planner or restart a live worker because an observation times out.

The upgraded dispatcher started at 01:48:11 and launched
`point-plan-678334c526b05d2c5ff88756` at 01:50:28, about 137 seconds later,
without relaunching the word or entry planners. This is a live handoff check,
not a matched whole-workflow benchmark or a claim that the remaining internal
recursive checks are cheap. The point worker subsequently sealed a
`needs-instrumentation` result: the distinguishing interval is before the
producer entry and crosses threads, outside the point primitive's scope. Its
19,515-character prompt stayed within the existing limit. The same dispatcher
then launched `interval-plan-v2-cdd6ed1023e44dea328eabcd` without restarting
any completed worker. That planner also sealed `needs-instrumentation`:
entry-hook counts do not prove completed queue operations or device timing,
and comparisons at the intervening receive entry cannot silently equate the
different raw overlay return addresses. No new capture or repair was authorized
by these planner results. The dispatcher completed full validation and returned
the terminal unsupported-method report with exactly two dispatched jobs and
`parity_verified: false`. All three new typed planners have exactly one attempt.
No worker from these commands remains live.

All 303 autonomy tests pass, including routing-hint tampering, full-executor
rejection, terminal full validation, historical refresh behavior, active-job
idempotence and equivalence to the exhaustive anchor decoder. The ledger audit
after the two planner completions verified 120 passed seals among 147 jobs with
no integrity issues and 15 preserved historical failures/blocks.
`git diff --check` passes.

## Next distinguishing observation, not a proven fix

A subsequent source inspection identifies a narrower readiness test that may
avoid the receive-entry overlay-link ambiguity without translating addresses.
The receive routine's call at `0x80096928` writes an internal return link to
`0x80096930`; its interrupt-disable callee does not overwrite that register.
The later branch at `0x8009693c` consumes register 15, loaded from queue+8;
register 14 identifies that queue. These instruction bytes match in all eight
retained native/oracle snapshots for updates 1907-1910, and the registered
generated source already has a hook at the branch.

A candidate test would filter that branch for register 14 low word
`0x800fe8a8` and measure its queue-readiness operand before the pacing call,
while requiring actual raw caller/thread/stack/input prefixes to match. This
could test an earlier readiness split, not establish complete receive-path
equivalence or decide every VI-device cause. Expected static register effects
were proposal evidence only at this checkpoint: the branch had not yet been
captured or qualified, and the outer overlay continuation was not proved equivalent. Do not
overwrite the unsupported plans or relax their comparison checks.

The [operand-context successor](autonomy-interval-experiment.md#source-backed-operand-context-successor-2026-09-27)
now supplies these independently derived facts to bounded experiment selection.
The full autonomy suite passes 321 tests. The resumed live chain revalidated
the old observation and plan lineage, then completed
`interval-plan-v2-cdd6ed1023e44dea328eabcd-operands-v1` in one attempt. Its
17,436-character prompt pins eight evidence files and keeps the old unsupported
plan intact. The model selected register 15 at occurrence 1 of branch
`0x8009693c`, filtered by register 14 low word `0x800fe8a8`, in the interval
ending at invocation 1908. It predicts a difference but explicitly permits
falsification or an inconclusive result. This is not a preselected human probe
packet or a causal fix.

The same driver fully validated that typed plan and automatically queued
`point-capture-c2ea167fbedae4d4081e7f09`. The bounded continuation executed it
in one attempt. Both sides ended normally (native 1973 completed updates,
oracle 2574), and the paired capture is sealed. Its result SHA-256 is
`5dcdb6a98f9801daf724d2e62e7653e2a6f8994f20a6605eb90b7be4bef1703e`.
The full update traces and all eight focused RDRAM snapshots are unchanged
from the unprobed reference pair, and delivered inputs match.

A read-only engineering check of the completed capture passes the existing
interval qualification. At the predicted first branch occurrence, register 15
is zero on both sides for invocations 1908-1910. Across all three selected
occurrences in each interval, the queue-readiness operands are 0, 1, 1 on
both sides; the selected raw PC/thread/SP/RA/input prefixes match. Actual RA
at these hooks is `ffffffff:80096930` on both sides, without translation.
This does not prove equivalence of the outer overlay continuation, blocked
duration, completed queue operations or VI causality.

The autonomous job `interval-observe-c2ea167fbedae4d4081e7f09` subsequently
completed its full before/after lineage and measurement verification. Its
sealed result SHA-256 is
`d373c954fd24cb739274d3ae310d7aade4be4f3c7d210110ad7e063b92382ae2`.
Qualification passes with no reasons, and the predicted difference at selected
occurrence 1 is **falsified** in the sealed measurement, not just in the
engineering check. No completed-queue, causal-fix or parity claim is made.

The driver independently revalidated this new observation, queued
`experiment-feedback-39191c234b66695beba63c33`, and completed its first attempt.
The diagnosis SHA-256 is
`d9a0f618f8ab9966f3043f5a72cdd5e15411100da61c552438d65f521dd904ca`.
It reports insufficient evidence and unvalidated alignment, with no claimed
divergent retrace. Both counters read VI 4591 at the third graphics-readiness
hook, but the reference then samples thread `0x80105410` before additional
scheduler hooks and the extra VI. This narrows the requested event-order
observation; it does not identify the originating interrupt or prove a fix.
The next requested trace spans the third readiness hook through producer
entry and includes dequeue/sender wakeup, Status restoration, raw return
execution and source-tagged device assertion/acceptance.

The three-job driver completed normally after automatically queueing
`experiment-plan-1d077adf9cc140cfc8ec88a8` (9,562 prompt characters, ten evidence
pins). A new bounded driver resumed directly from the new observation with
a four-job budget. That word plan and `entry-plan-4319e1269e3f29a58b5e74ac`
completed in one attempt each; both report that their primitive cannot order
the requested events. The driver subsequently queued
`point-plan-87785a7ef633b3b334481983`, which was blocked with
`prompt must be 1..20000 characters`. The driver has exited normally after
three dispatches; it is not still running. No completed worker was relaunched.
The audit before that final dispatch verified 126 passed
seals among 153 jobs with zero integrity issues and 15 preserved historical
failures/blocks. These are unsupported-method reports, not new captures. The subsequent
[fresh-context handoff](autonomy-context-handoff.md) reduces duplicate review
validation in future passes without weakening the evidence checks.

The gameplay frontier remains 1908 matching selected-state updates, with the
first actor/camera mismatch at 1909. General independent proof construction,
reviewed repair integration/continuation, broader gameplay coverage and
restart/endurance acceptance remain required for the entire automation goal.

Read-only revalidation on 2026-09-27 independently recomputed the comparisons
from both the longer and focused saved native/oracle update traces. Both pairs
pass prefixes 1292 and 1908 and fail at 1909 with camera and 18 actor-record
differences. At 1292 both sides report controller poll 1301 and consumed VI
2946. This reconfirms the requested passage beyond 1291; it is not a new
runtime fix, full-state parity, or default-runtime promotion. The prompt-size
failure belongs to the later research chain and does not invalidate this
already captured result.
