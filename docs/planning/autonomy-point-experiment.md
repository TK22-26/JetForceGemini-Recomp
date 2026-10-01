# Autonomous instruction-point experiments

## Live result, 2026-09-26

The measured-result driver now completes diagnosis -> typed instruction-point
plan -> source-bound native/BizHawk capture -> independently recomputed
observation -> next investigation. The model selected the probe PCs and
prediction; the root agent did not write its capture packet. The native run
took about 70 seconds and retained 391 events; the reference retained 413.

The qualified measurement counts calls to `0x80096910` within the pacing
producer `0x80054fbc`, called by the direct JAL at `0x800457b4`:

| Invocation | Native receive calls | Reference receive calls |
| ---: | ---: | ---: |
| 1907 | 4 | 4 |
| 1908 | 4 | 5 |
| 1909 | 4 | 4 |
| 1910 | 4 | 4 |

These are all receive calls in the anchored invocation, including the empty
nonblocking attempt and separate final blocking wait, not just successful
counted receives. The earlier, root-driven
[pacing analysis](phase9-pacing-receive-observation.md) established the queue
already differed on entry (2/3) and both sides counted correctly. This new run
proves an autonomous measurement handoff; it does not discover a new gameplay
frontier or prove which upstream timing behavior is wrong.

Both full update traces and all four full focused RDRAM snapshots per side
are unchanged against the original unprobed reference. The same-index
selected-state prefix still passes through 1908, including the requested 1291
target, and first differs at 1909. Reference results remain corrected-Mupen
compatibility evidence, not physical-N64 timing truth or product acceptance.

## Bounded contract and qualification

`point_plan.py` and its JSON schema accept only `point-state` or explicit
`needs-instrumentation`. A supported plan chooses at most 16 aligned canonical
RDRAM PCs and 16 words, a direct JAL/NOP caller/entry anchor, and one event-count,
register-value or word-value prediction. The fixed focused window, runtime,
input and replay bounds belong to the supervisor. Model output cannot supply
commands, writes, timing changes or dynamic device reads. Three point rounds
are allowed per lineage; changing a prediction label, update, register or an
irrelevant PC does not make an already captured observation new evidence.

The observer retains raw events and clocks, then requires unique entry/return
anchors with the expected RA, matching thread/stack and corresponding input
polls. Instructions must match retained snapshots and remain stable across
the focused captures. Internal value comparisons additionally require equal
observed hook prefixes through the chosen occurrence. Unique entry/return
values may be compared despite differing internal event counts. This is local
hook correspondence, not proof of whole-path or global event alignment.
Missing or ambiguous correspondence and changed game state are inconclusive;
malformed traces or inconsistent opcode evidence fail closed. Alignment,
causal-fix and parity flags remain false.

The original frozen native binary predates point instrumentation. A separate
immutable `point_runtime` registry therefore binds the diagnostic build to a
source-build record and independently recomputed calibration against the
original reference. It does not relabel that build as the original baseline,
promote it, or attest a hermetic dependency closure. Every new capture must
again prove unchanged update traces and focused RDRAM.

An initial point proposal correctly refused because the saved diagnosis did
not explicitly supply a qualified callsite candidate. `point_anchors.py` now
derives stable direct JAL/NOP candidates from retained RDRAM snapshots on both
sides and supplies them as pinned instruction evidence. They are not declared
executed calls until capture qualifies them. One versioned evidence refresh
was allowed for that older unsupported proposal. The subsequent
[history-aware inventory](autonomy-interval-observation.md) also allows one
versioned refresh when independently checked prior observations add an actual
instruction candidate omitted by the diagnosis-only inventory. A proposal is
never retried merely because it says unsupported or receives different prose.

Capture uses the existing exclusive emulator lease, process guards, pause
checks and 300-second per-side limits. Trace declarations, completion, event
counts and hashes are checked when sealing and recovering. Deterministic
observation recomputes the evidence and rechecks plan/runtime/capture pins.
No new paid API dependency was introduced.

A profiling pass found repeated focused-record extraction rescanning entire
update prefixes. The shared reader now batches each requested window into a
single validated prefix scan, retaining only requested records. There is no
cross-call cache: subsequent evidence rechecks reread the files. On the same
sealed observation, profiled end-to-end revalidation fell from 63.25 to 39.74
seconds and reproduced the exact saved result. This is a local validation
cost measurement, not a promised whole-loop speedup.

## Private evidence and operation

The following IDs are in `tools/private/autonomy/`:

- Typed proposal: `point-plan-6a6d08ac1d15f2dbec600adf-anchors-v1`.
- Paired capture: `point-capture-e8aea779b55c3e9d7be4f817`.
- Qualified observation: `point-observe-e8aea779b55c3e9d7be4f817`.
  Result SHA-256:
  `90e21755999a1cc43e6fb3f67d871baad4a19442933d916d3f2e91c77e11358d`.
- Automatically queued follow-up:
  `experiment-feedback-569bb45c7b8220f004d58ee6`.
- Runtime registration:
  `point-runtimes/execution-update-f6b6450b3b760d121bfbea0e.json`.
  Diagnostic source commit: `3e69f04da6278ae0556ca887cf2a56274eff03d8`.

The bounded command used was:

```powershell
python -m scripts.autonomy.research_cycle --observation experiment-observe-410efa3bed9b16fc25fad989 --agent (Get-Command codex.cmd).Source --max-jobs 3 --execute
```

It completed the refreshed plan, capture and observation, then stopped at its
three-job budget with the next investigation queued. A resume can start from
the latest observation ID to avoid walking already completed stages. This
command is not an unbounded service and does not drain unrelated backlog.

The follow-up was subsequently executed, but exhausted its 480-second attempt
without a final diagnosis. Its recorded error was `cannot capture tracked
patch within limits`: the supervisor attempted final snapshot collection
against the already exhausted deadline, obscuring the original stop. The
isolated worktree is clean, both process guards finished, and the transcript
survives. The attempt remains failed/blocked evidence, not an accepted
diagnosis. It was not automatically rerun or given a larger research budget.

The supervisor now preserves the primary failure and records a separate
candidate-snapshot error; it does not launch snapshot collection after an
already failed attempt exhausts its deadline. Otherwise-successful attempts
still require a valid snapshot. Existing failure artifacts are not rewritten.
The next investigation should be narrowed using retained evidence rather than
repeating the same broad research packet. This is an unresolved research step,
not loss of the successfully sealed capture or observation.

Follow-up, 2026-09-27: [bounded research completion](autonomy-research-completion.md)
now handles this missing-result case with one tool-free synthesis step. Its
live result passed and fed the next typed planner. The original failed attempt
remains unchanged; the upstream cause and unsupported event observations still
need evidence.

The subsequent [history/interval work](autonomy-interval-observation.md) fixes
loss of prior qualified anchors in planner context. Its live planner still
correctly requests cross-thread pre-entry observations. An engineering interval
analyzer now qualifies 2 native / 3 reference send-call entries before pacing
invocation 1908, using retained captures. It is not yet exposed as a typed
autonomous interval lane and does not establish a successful enqueue or cause.

## Verification and remaining work

All 236 autonomy tests pass, including schema bounds, mixed history, immutable
trace seals, instruction/anchor qualification, fixed capture CLI, read-only
planner execution, pause handling and follow-up dispatch. Recovery validation
also accepted the actual completed capture with a mocked ledger and rejected
an injected point-trace digest mismatch. That read-only recovery check is not
a new live hard-kill/restart drill.

Six additional batched-reader tests cover single-scan behavior, malformed
intermediate records, missing updates, changed evidence between calls,
requested-prefix termination and invalid requests. The focused reader,
pacing, point, entry and word suites pass together (48 tests).
Three additional supervisor regressions cover timeout reporting, secondary
snapshot failure and mandatory snapshot validation on the success path.

The final ledger audit verifies 108 passed seals among 134 jobs with zero
integrity issues. Fourteen unresolved historical failures/blocks include the
new timed-out investigation. Repository hygiene still reports the same five
pre-existing findings in the OS-clock document, PI microtest/trace and
task-recovery helper; those findings are not waived. `git diff --check` passes.

General independent proof construction, reviewed repair integration,
whole-game coverage and endurance acceptance remain open. No timing patch,
main-branch commit/push or candidate promotion accompanies this observation.
The full automation-loop objective remains active and unfinished.
