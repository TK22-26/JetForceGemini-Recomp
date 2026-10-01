# Phase 9: the extra pacing message is already queued

## Measured result (2026-09-26)

The new instruction-point capture qualifies the local US pacing producer at
`0x80054fbc`, called from `0x800457b4` (NOP slot, return `0x800457bc`). At
invocation 1908, **native enters with two messages in queue `0x800feb80`;
the corrected-Mupen reference enters with three**. The producer drains those
messages successfully, exhausts the queue, then performs its separate final
blocking receive. That final receive does not contribute to the saved count.

| Invocation | Shared poll | Queued on entry, native/oracle | Counted successful receives | Return V0 |
| --- | ---: | --- | --- | --- |
| 1907 | 1917 | 2 / 2 | 2 / 2 | 3 / 3 |
| 1908 | 1918 | 2 / 3 | 2 / 3 | 3 / 4 |
| 1909 | 1919 | 2 / 2 | 2 / 2 | 3 / 3 |
| 1910 | 1920 | 2 / 2 | 2 / 2 | 3 / 3 |

Both sides enter with A0=0, the same thread/stack/caller, and equal policy
words at `0x800feca8`, `0x800fecac`, and `0x800feccc`. The three observed policy
branches retain the same settings and take the no-minimum-wait path. S0 follows
each counted receive; saved V1 and returned V0 equal `1 + counted receives`.
This falsifies equal receive histories producing a different count in this
local invocation. The difference exists before the pacing routine starts.
It does **not** identify which earlier CPU/device ordering or work-accounting
difference made the extra reference message available.

The earlier [consumer-entry capture](autonomy-entry-experiment.md) established
delivery of this 3/4 difference in A1 at invocation 1909. Neither observation
authorizes adjusting VI periods, inserting a message, overwriting the step,
shifting comparisons or claiming a causal gameplay repair.

## Implementation and qualification

The replay tools accept repeatable `--point-pc` and `--point-word` options.
They support at most 16 distinct instruction PCs and 16 distinct aligned
canonical 4 MiB KSEG0 words, within a declared focused update window. Both
sides retain all 32 64-bit GPRs, instruction bytes and raw clock labels, with
a 4096-event cap. Native requires the explicit original-OS profile and its
existing execution-instrumented generated root. No generated code regeneration
was required. The default runtime is unchanged.

Native records after any exception resumption and its existing Count charge,
before executing the current guest instruction. BizHawk records its execute
hook before the instruction. Raw CPU Count is deliberately not compared:
the oracle exposes lazily updated core Count. The observer makes no guest
writes and adds no guest timing costs. Runtime address parsing, trace parsing,
overflow, wrong/missing calls, thread/stack correspondence and opcode checks
fail closed. A missing/ambiguous or state-changing observation is not a pass.

`scripts.compare_phase9_point_pacing` is a game-specific analyzer for the
inspected producer. It checks direct-call instruction bytes, focused snapshot
opcodes, complete thread/stack-matched receives, modes/results, counter
increments, count save, final wait, caller return, and input/save/profile pins.
Qualification also requires byte-identical full update traces and **all four
full focused RDRAM snapshots** against each side's pre-probe reference.
All 1984 shared delivered input polls match. Oracle Pak equivalence remains
unverified; global alignment, physical-N64 timing and parity flags remain false.

The source-bound diagnostic build and the paired replay completed. Native
recorded 608 point events, oracle 641. Native reached 4800 consumed VI and
1973 updates in about 69 seconds; oracle reached frame 7200 and 2574 updates.
The strict selected-state checks again pass 1291 and 1908 and first fail at
1909. This is a narrower diagnosis, not another frontier advance.

An initial native attempt also requested unsupported original-OS poll-state
hashes. The process reached its target and retained its point trace, but the
runner rejected the missing poll-state output. That rejected attempt remains
archived and is not used as the qualified capture. The accepted repeat used
the baseline's supported poll-input trace and completed-update options.

## Private evidence

All paths are below `tools/private/`:

- Build: `autonomy/source-point-probe-20260926a/source-build.json`;
  source commit `3e69f04da6278ae0556ca887cf2a56274eff03d8`.
  The private build does not move main HEAD or its index, and is not a hermetic
  dependency-closure attestation or product promotion.
- Native: `point-pacing-native-20260926b`.
  EXE SHA-256: `083475b7320795fef070b689f2e3c311dd3f48e1cd6d3a9758b26b9e9916a4c2`.
- Oracle: `point-pacing-oracle-20260926a`, unchanged corrected-Mupen binary,
  runtime and isolated config pins.
- Both pre-probe references:
  `autonomy/attempts/experiment-capture-410efa3bed9b16fc25fad989/0001/`.
- Comparison: native directory `pacing-comparison.json`, SHA-256
  `aef19c8f95b0d7eb97b10ba163b06ffe2d66c8436e6d84c803b7cbf87e0e7213`.
- The completed bounded diagnostic
  `experiment-feedback-54f2252939dcf2ad22ada3fc` proposed measuring counted
  receive history versus policy/control differences. Its saved diagnosis was
  the basis for this engineering work; it did not authorize a timing fix.

## Verification and next work

The C++ address-parser test passes, as do 6 Python point-capture tests,
8 pacing-analyzer tests, 327 Phase 9.5 tests and all 214 autonomy tests.
`git diff --check` passes. Replay producer inventories include the new Python
parser dependency. Existing dirty work and the separate master-scope edit
are preserved; no main commit/push or candidate promotion was performed.
The ledger audit verifies 102 passed seals among 128 jobs with zero integrity
issues (13 unresolved historical failures/blocks remain). Repository hygiene
still reports the same five pre-existing warnings in the OS-clock document,
PI microtest/trace and task-recovery helper; this work does not waive them.

Next, follow the already captured send/receive points before producer entry
1908 and identify where message availability first splits. If needed, the
new bounded point primitive can observe earlier execution/device boundaries
without another generated-root rebuild. Actual device ordering must be
independently qualified before implementing a repair.

The calibration above was engineered and driven by the root agent. A subsequent
[typed autonomous point experiment](autonomy-point-experiment.md) now completes
model-selected planning, capture, deterministic measurement and follow-up
handoff using the separately bound diagnostic build. It independently confirms
the receive-call difference without changing either full update trace or the
focused RDRAM. It does not complete general proof generation, reviewed repair
integration, whole-game coverage or endurance acceptance. The full
automation-loop goal remains open.
