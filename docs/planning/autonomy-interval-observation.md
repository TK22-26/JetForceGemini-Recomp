# Retained planner history and cross-thread interval observation

## Result (2026-09-27)

The latest point planner had received an empty instruction inventory even
though its independently checked history contained two valid caller anchors.
Inventory discovery had searched only addresses in the latest diagnosis.
The planner now receives compact, pinned prior measurements and the already
recomputed runtime calibration. Qualified prior entry addresses also seed
instruction discovery, which still checks every focused native/reference
snapshot. Historical execution qualification does not automatically qualify
a new call or a different interval.

The live history refresh restored these two direct JAL/NOP candidates:

| Caller | Entry | Return |
| --- | --- | --- |
| `0x80045248` | `0x80043130` | `0x80045250` |
| `0x800457b4` | `0x80054fbc` | `0x800457bc` |

The old inventory and results are unchanged. A separate `-history-v2`
inventory and one successor planner are allowed only when the newly checked
facts add an instruction candidate. New prose, renamed measurements, unchanged
candidate sets, supported plans, or another history-v2 result cannot trigger
this refresh. Consumers independently reconstruct the facts and compare their
bytes, rather than trusting a newly pinned summary alone.

The live job `point-plan-fc11205d03db6b5e0e95748a-history-v2` passed, using
no tools, and correctly returned `needs-instrumentation`. It recognized the
previously established entry occupancy/count/result differences and declined
another measurement of them. The remaining limitation is real: the original
point primitive measures one thread *inside* one call; the question concerns
events before entry and on scheduler/device threads. This run repairs a
context-loss bug but does not claim that context alone resolves that limitation.

## New observation foundation

`scripts.autonomy.point_interval_observation` measures a selected instruction
hook, filtered by one GPR low word, between the previous qualified caller
return and the next callee entry. It includes all threads in that interval.
It requires unique correctly ordered call anchors, stable boundary thread and
stack, corresponding return addresses, and matching boundary input-poll labels.
It retains raw selected events, including addresses and clock labels. It does
not match arbitrary calls by ordinal or normalize overlay return addresses.

The engineering adapter reuses the existing registered point calibration.
It revalidates the source-bound runtime, both complete update traces, all four
full focused RDRAM snapshots per side, instruction bytes, raw trace hashes,
and delivered input before and after measurement. All 1984 shared delivered
polls match; reference Pak equivalence remains unverified. No new game replay,
generated-root rebuild, game fix, or timing adjustment was required.

The qualified measurement selects send entry `0x80096f20`, with A0 low word
`0x800feb80`:

| Next pacing invocation | Native send-entry hits | Reference send-entry hits |
| --- | ---: | ---: |
| 1908 | 2 | 3 |
| 1909 | 2 | 2 |
| 1910 | 2 | 2 |

This establishes an additional observed reference send-call entry in the
pre-producer interval. It does **not** establish a successful enqueue, device
completion time, global state alignment, or the cause of the extra call.
In particular, the capture has no return hook for the preceding graphics
completion receive; it cannot yet distinguish blocking/resumption from extra
work after that receive. Native/reference overlay return values remain raw
and different, not silently translated or paired as equivalent calls.

## Evidence and reproduction

Private evidence under `tools/private/autonomy/`:

- Old inventory: `point-anchors/entry-plan-74bef6aeeed1c7736091b78e.json`.
- New inventory: the same stem with `-history-v2.json`.
- Planner: `attempts/point-plan-fc11205d03db6b5e0e95748a-history-v2/0001/`.
  Final message SHA-256:
  `763b9a0e44de8fa0f8c6b5b8f9299f613bd66da67fa02771282e30cf0971eeac`.
- Interval report:
  `interval-calibration/c1c514b73e286462f3cddcab89c80d0d7d632c244e9f3ad60991f5eef69e8c95.json`.
  Its filename is its content SHA-256. It pins the consumed planner result,
  runtime registration, calibration, point traces and interval analyzer.

```powershell
python -m scripts.autonomy.point_interval_observation --plan point-plan-fc11205d03db6b5e0e95748a-history-v2 --pc 0x80096f20 --register 4 --value-lo 0x800feb80
```

Publication is content-addressed and does not overwrite previous evidence.
This command is an engineering qualification adapter, **not yet a typed
autonomous interval-plan/capture/feedback lane**. Its report explicitly says
`autonomous_plan_executed: false`; it cannot authorize a repair or product
promotion.

Follow-up: the [typed interval adapter](autonomy-interval-experiment.md) now
connects model-selected intervals to capture reuse/new capture, independent
measurement and diagnostic feedback. The engineering command/report above
remains separate and is not relabeled as an autonomous run.

## Verification and next work

Tests cover recovered history, unqualified probes, changed instructions,
candidate-based refresh eligibility, immutable old facts, consumer-side
recomputation, one-time dispatch, interval boundaries, cross-thread filtering,
unchanged raw overlay addresses, and capture/runtime mutation rejection.
All 270 autonomy tests pass; `git diff --check` passes.
The ledger audit verifies 113 passed seals among 139 jobs with zero integrity
issues; 14 historical failed/blocked jobs remain. No main commit/push or
candidate promotion occurred.

Next, expose the interval primitive as a typed, bounded planner operation
and qualify receive return/queue mutation observations where needed. Keep the
existing measured send counts visible so that the next experiment distinguishes
new explanations rather than repeating them. Full independent proof production,
reviewed repair integration/continuation, campaign coverage and restart/endurance
acceptance remain open. Selected game-state comparison still matches through
1908 and first differs at 1909; this work does not advance that frontier.
