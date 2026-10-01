# Typed autonomous cross-thread interval experiments

## Capability

The [engineering interval observer](autonomy-interval-observation.md) now has
a typed planner/capture/measurement adapter. The research driver and normal
scheduler can advance an unsupported point plan into `plan-interval`, then
consume an independently recomputed `interval-experiment` observation through
the existing diagnostic feedback loop. This is still research, not automatic
repair authorization or parity acceptance.

The model may choose a direct JAL/NOP anchor, at most 16 instruction PCs and
16 aligned RDRAM words, and one instruction/GPR-low-word event filter. The
interval is strictly between the previous caller return and the next callee
entry. All threads are included. Predictions can compare filtered event counts
or a register/word at one selected occurrence. A maximum of three interval
rounds is allowed on a lineage; unsupported proposals stop without retries of
the same evidence. The bounded source-context successor below is a new plan,
not a retry or an additional measurement round.

The executor validates unique call boundaries, caller/thread/stack/input-poll
correspondence, instruction bytes, capture completeness and input provenance.
Value comparisons additionally require identical selected-event prefixes in
PC, running-thread word, SP/RA low words and controller poll. Raw overlay return
addresses are not translated. Different prefixes, missing occurrences or
changed capture state yield an inconclusive prediction, not a proven mismatch.
Entering a send/receive routine is not proof that the queue operation completed.

Before planning, the executor computes the available A0-filtered interval
counts from the registered capture and provides them as checked context.
Requesting one of those counts again is rejected. Prior measurements and
qualified caller candidates remain visible. Historical unsupported point plans
do not fork new interval lanes after a newer point-context refresh exists.

If the requested anchor/PCs/words are already captured, the executor reuses
the registered evidence. Otherwise it invokes the existing source-bound point
capture with its fixed CLI, exclusive emulator lease and 300-second limit per
side. New captures must reproduce both complete update traces and every full
focused RDRAM snapshot. Both paths revalidate their complete plan/runtime/capture
lineage after measurement. Local qualification does not resolve reference Pak
equivalence or establish physical-N64 timing truth.

Measurements run in a guarded, read-only child with a 600-second wall limit,
process containment, bounded logs and periodic lease heartbeats. This avoids
allowing long evidence validation to expire an otherwise active analysis lease.
The resulting report is sealed separately from the model's hypothesis. Later
consumers recompute it and reject altered measurement/qualification/parity claims.

## First live plan (2026-09-27)

Parent: `point-plan-fc11205d03db6b5e0e95748a-history-v2`.

The first packet, `interval-plan-44fd61e1d22e9010d0cc513e`, failed before any
model process started: its 25,679-character prompt duplicated the full retained
count inventory and exceeded the 20,000-character limit. The failed packet and
attempt remain intact. The adapter now validates packets before enqueueing and
uses a compact projection without discarding the full pinned facts. Context
format v2 has a separate deterministic identity; it is not a retry of a model
experiment or a larger execution budget.

`interval-plan-v2-44fd61e1d22e9010d0cc513e` passed with a 12,230-character
prompt. It selected a genuinely new value observation from retained captures:

- Anchor: entry `0x80054fbc`, caller `0x800457b4`, return `0x800457bc`.
- Interval ending at pacing invocation 1908, not completed update 1908.
- Select send-entry `0x80096f20` with A0 low word `0x800feb80`.
- Compare word `0x800feb88` at the second selected event.
- Prediction: native/reference differ, conditional on matching selected-call
  prefixes and capture qualification.

This plan requires no new game replay and does not repeat the known 2/3 send
count. Its measurement job is `interval-observe-8452523d416da9c0aeb97b0f`.

That measurement passed qualification using the registered capture. Word
`0x800feb88` equals `0x00000001` on both sides at the second selected send
entry in each interval ending at invocation 1908, 1909 and 1910. The predicted
difference is therefore **falsified**, not inconclusive. The already known
later 2/3 entry occupancy difference is not present at this earlier matched
event. This does not prove which later queue/device/work event causes it.

Result SHA-256:
`3ac7ebe72c75907b665ae5d0bd429d9e88379bb19f5407e08831a8b25b8cbad9`.
The result includes raw evidence, the local qualification, capture reuse mode,
and independent source/runtime/reference/plan pins. The research driver was
then resumed directly from this observation to pass negative evidence into
the next bounded diagnostic.

The driver independently revalidated that sealed result, queued
`experiment-feedback-ef23e04b636937c192656e3a`, and launched it. That diagnostic
completed successfully with `insufficient_evidence`, unvalidated alignment and
no supported divergent retrace. Its structured diagnosis SHA-256 is
`9162e83580971ffee273837cd0815424fc8390b99585e66cd891bb8e9fd2304b`.
It distinguishes two still-unproved explanations: an earlier VI event versus
a delayed graphics-queue receive/continuation. It requests receive-path and
event-timing observations, not another completed-update word comparison.
No subsequent causal repair is claimed. The bounded continuation command is:

```powershell
python -m scripts.autonomy.research_cycle --observation interval-observe-8452523d416da9c0aeb97b0f --agent (Get-Command codex.cmd).Source --max-jobs 1 --execute
```

The initial handoff after the successful diagnostic failed before enqueueing
the next state-word planner: its history prompt embedded the interval's raw
selected events and boundary register dumps, exceeding 20,000 characters.
The state-word adapter now projects the checked prediction, measured values,
anchor/filter and qualification/claim limits into the prompt; complete original
observations remain pinned as evidence. It preserves false and inconclusive
outcomes and validates the prompt before enqueueing. It neither raises the
prompt budget nor rewrites any existing packet, result or measurement.

Live handoff verification then independently revalidated the same sealed
diagnostic and full measured lineage and queued
`experiment-plan-4239ff8597f4d69da16c3faf` with an 8,812-character prompt and
nine evidence-file pins. This check used the driver without `--execute`:
the successor is queued, not executed, and the successful diagnostic was not
rerun. The updated autonomy suite passes 290 tests; `git diff --check` passes.
The ledger audit verifies 116 passed seals among 144 jobs with zero integrity
issues and 15 preserved historical failures/blocks. No worker remains live
from these bounded commands.

The earlier checkpoint test suite passed 287 autonomy tests and `git diff --check`.
Its ledger audit verified 115 passed seals among 143 jobs with no integrity
issues; 15 historical failures/blocks included the preserved oversized
pre-launch packet. At that checkpoint the diagnostic was still running and
was not counted as a passed result.

The first live measurement completed normally under process containment with
active lease heartbeats. The adapter now also supplies an explicit guard-record
path for future interval measurements; that argument is covered by the ledger
test, not a new live kill/restart drill. Historical output is not rewritten to
claim a guard artifact that the first invocation did not record.

## Source-backed operand-context successor (2026-09-27)

`instruction_context` derives a small static instruction inventory from every
retained native/oracle RDRAM snapshot in the validated focus window. It looks
for a word load feeding a zero-test branch after a direct call to a bounded
linear leaf which does not overwrite RA. The call corridor, callee and return
delay-slot bytes must agree in every snapshot. Unknown instructions, intervening
control flow or RA writes reject the candidate. Targets, sites, lookback,
callee length and focus window are bounded. Snapshot hashes and decoded
instructions remain in the full facts; the planner sees a compact projection.

These are **conditional normal-path register effects**, not observed execution,
retirement, caller equivalence or timing. Traps and interrupts are not excluded
by the decoder. In particular, a predicted internal RA is never substituted
for a captured raw RA.

An unsupported base interval plan can gain exactly one `-operands-v1` successor
when this inventory supplies new nonempty context and the existing three-round
measurement budget has room. The previous plan, result and original facts are
preserved and pinned as prerequisites/evidence. Failed or active successors
are not retried; newer point-context plans, pause, empty inventories and
exhausted rounds prevent the refresh. Merely changing diagnosis prose does not
authorize a successor. The planner may choose a narrower falsifiable operand
test without pretending to settle the entire device-causality question.

Consumers fully validate the point ancestry once, then independently recompute
both old and new interval facts against that same freshly checked parent.
Re-pinning a fabricated instruction fact cannot satisfy that recomputation.
The existing raw selected-prefix, complete trace, full focused-RDRAM and input
qualification remains unchanged. No new comparison aliases or gameplay fixes
are introduced. The research-tail dispatcher prefers the durable successor,
including failed/running states, so restarting the driver cannot relaunch it.

## Remaining acceptance

Tests exercise schema/round bounds, repeat rejection, context size validation,
capture reuse versus new capture, inconclusive caller/occurrence mismatches,
consumer routing, measured-result feedback, immutable observations, and guarded
sealing with a real ledger. This is not a multi-day or live hard-kill acceptance.

The complete objective still requires general independent proof construction,
reviewed repair integration and continuation, broader gameplay coverage, and
restart/endurance acceptance. The selected-state frontier remains 1908; no game
timing, gameplay code, comparison index or golden state is changed by this lane.
