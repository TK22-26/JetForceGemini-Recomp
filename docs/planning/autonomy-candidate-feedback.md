# Candidate replay feedback (2026-09-26)

## Missing transition now implemented

The [first real repair cycle](autonomy-proven-repair-cycle.md) proved that a
qualified local fix can leave the gameplay divergence unchanged. Previously
the finite case driver returned that result and stopped; the scheduler did
not automatically hand its negative evidence to a new investigation.

`scripts/autonomy/candidate_feedback.py` now connects any sealed candidate
native retest to one bounded read-only diagnostic. The normal scheduler places
this transition before another frontier search. It does not depend on the
REGIMM Count policy, manually prepared diagnostic packets, or a manual game run.

| Measured candidate outcome | Follow-up task |
| --- | --- |
| Input mismatch | Investigate delivered-input equivalence before game-code conclusions. |
| Earlier state mismatch | Explain the regression and specify the missing regression test. |
| Unchanged first mismatch | Preserve any independently proved local fix; distinguish remaining causes instead of blindly retrying it. |
| Later first mismatch | Identify integration/corpus/alignment gaps; do not promote a diagnostic to parity. |

The intake checks the ledger seal, packet identity, approved review and
implementation lineage, original baseline, trace/report hashes, comparison
scope, input report and derived disposition. Historical results do not require
the current producer script to have identical bytes, but their sealed evidence
must remain intact. Changed or contradictory supporting evidence fails closed.

The diagnostic gets twelve pinned evidence files, including measured facts,
the original implementation packet and patch, both native traces, the oracle
trace, comparisons and input report. Whole-trace identity is measured explicitly:
the same first mismatch alone does not establish equal traces. Update indices
are not retrace indices, and alignment/parity remain unverified.

One stable successor ID is derived from each retest. Restarting cannot enqueue
another successor for the same result, including a failed or blocked successor.
An interruption after writing the facts but before queue insertion resumes
with the same facts. No code is promoted, no implementation is blindly retried,
and no model-authored command is executed by this transition. Existing worker
timeout, process containment, authentication, retry and pause controls still
apply. The continuous supervisor retains its daily-attempt cap; explicit
single-job commands do not acquire that service-level cap. A diagnostic's
prose is not a proof or an executable task.

## Bounded entry command

```powershell
python -m scripts.autonomy.candidate_feedback `
  --retest re-44ed500a0c32-native-retest `
  --agent (Get-Command codex.cmd).Source --execute
```

Without `--execute`, this only queues the investigation. With it, only that
specific queued job is dispatched; unrelated backlog is not consumed. An
already running or completed job is not relaunched. The ordinary continuous
scheduler can also queue and run these successors within its existing limits.

## Live evidence and remaining work

The real Count candidate produced successor
`candidate-feedback-126df228845178d443e38892`. Its immutable facts report
`retained-no-frontier-gain`, 1984 matching consumed input polls, byte-identical
native update traces and the unchanged first selected-state mismatch at 1909.
The worker completed its investigation but its first final report was rejected:
the proposed `next_test` exceeded the runtime validator's 1000-character limit,
which the legacy JSON Schema had not declared. The blocked job and its entire
output remain intact. This was a schema/validator mismatch, not a gameplay fix
or a requirement to relax the validator.

New diagnostic packets now pin `diagnosis.bounded-v2.schema.json`, including
the existing text/evidence bounds. The legacy schema file is unchanged, so old
seals retain their identity. Supervision and expired-attempt recovery select
the schema from the packet's pinned contract. Current comparison, update,
VI-boundary, poll-cadence and candidate-feedback producers all use the new
contract for newly queued diagnoses. The runtime validation limits are unchanged.

For this exact legacy length failure, one 120-second format-only successor is
allowed; it does not re-investigate or rerun an experiment. A new-schema failure
or another failure reason is not eligible. The successor
`candidate-feedback-126df228845178d443e38892-format-v2` passed. Its hypothesis is
862 characters and next test 818; all original evidence strings, classification,
alignment, retrace claim and confidence were verified unchanged. The recorded
agent event stream contains zero command executions. Future format packets pin
the original report explicitly, and both normal sealing and recovery enforce
that those fields remain unchanged. The live run predated that extra field;
its preservation was checked independently afterward.

Repeating the command returns the passed successor without launching anything.
The ledger audit now has 118 jobs and 93 verified passed seals, zero integrity
issues and no active jobs. The original format failure remains among the 11
blocked jobs; two failed and twelve queued jobs also remain.

The diagnostic proposes checking the queue-derived elapsed-step word
`0x800a3374` before the actor/camera mismatch, and identifies its later use as
a routine argument. It is still a hypothesis, not implementation authority.
The [older 1909 focused capture](phase9-execution-frontier-1909.md) already
observed the 3/4 word difference on an earlier pinned binary. That evidence
was not attached to this diagnostic's frozen-build packet. The next experiment
stage must reconcile/reuse it, establish any needed source/runtime linkage,
and focus on the upstream execution/device cause, not blindly repeat a known
observation. The worker's request for separate capture authorization describes
its read-only role; it is not a new user-approval blocker for ordinary in-scope
bounded capture work.

Tests cover the four dispositions, changed evidence/lineage, contradictory
disposition, read-only packet contents, restart duplicate suppression, simulated
interruption between publication and enqueue, immutable facts, pause/budgets,
and scheduler priority. These are separate from the prior real supervisor
hard-kill test; the publication interruption here is simulated.
The full updated autonomy suite passes **164 tests**. Contract/format tests
cover exact length boundaries, legacy identity, pinned-schema mutation,
preservation of evidence/certainty, worker schema selection, and one-shot
format recovery. `git diff --check` passes. The repository hygiene scan still
reports five existing warnings in
`phase9-os-clock-qualification.md`, `phase9_cpu_pi_timing_micro.S`,
`phase9_cpu_pi_timing_trace.py` and `phase9_recover_task_helper.py`; they are
not waived. Machine-specific paths were removed from the new runbook examples.

Follow-up: the [bounded state-word experiment](autonomy-state-word-experiment.md)
now carries this saved diagnosis through a typed plan, a frozen-build paired
capture and a sealed observation. It independently reproduced the 1908 word
difference without advancing the gameplay frontier. Its 175-test suite and
live reuse check supersede the earlier test/audit counts above.

The entire autonomy objective remains open. In particular, arbitrary research
proposal still needs a general, independently reviewed experiment/proof
production path, then protected red/green validation and bounded repair
selection. Automatic candidate integration, complete dependency closure,
broader regression/exploration coverage and multi-day acceptance also remain.
This feedback transition removes a manual handoff; it is not proof that the
system can already invent and safely execute every next experiment unaided.
