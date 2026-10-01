# Phase 9: bounded device-event observation

## Result (2026-09-27)

The requested update-1291 boundary is passed. A fresh instrumented pair
reproduces **1908 consecutive matching selected states**; camera and 18 actor
records first differ at 1909. Consumed-VI accounting first differs at 1908.
This remains the opt-in original-OS / corrected-Mupen compatibility profile,
not full-memory, physical-N64, default-runtime or campaign parity.

The observer records instruction entries, their next observed instruction,
running-thread-word changes, device dispatch, interrupt state and CPU
interrupt acceptance. Records preserve raw PC/opcode, previous PC, all 32
64-bit GPRs, Status/Cause, MI pending/mask, thread word and optional deadline.
The shared C/C++ writer is `include/jfg/boot/device_event_probe.h`; its strict
bounded reader is `scripts/phase9_device_events.py`. Native hooks are in
`src/boot/native_boot.cpp`; the independently authored oracle adapter and
patch are `scripts/oracle_device_events.{c,h,patch}`. Both replay wrappers
require explicit `--device-events`, focused points and a supported engine.

Raw native pre-instruction Count and oracle lazy Count are **not declared
aligned**. An instruction successor is not retirement proof. A changed
running-thread word is not itself a CPU context switch. Dispatch,
post-dispatch state and acceptance are distinct observations, not an exact
hardware assertion-cycle measurement. Synthetic overlay PCs and raw return
registers are retained without aliases. No guest input or timing policy was
changed to obtain these results.

## Evidence

Paths below are relative to `tools/private/`. The uninstrumented controls are
`autonomy/attempts/experiment-capture-410efa3bed9b16fc25fad989/0001/{native,oracle}`.

| Check | Native | Oracle |
| --- | --- | --- |
| Successful capture | `device-events-native-20260927b` | `device-events-oracle-20260927a` |
| Bounded completion | 4800 consumed VI / 1973 updates | 7200 emulator frames / 2574 updates |
| Complete update trace unchanged from control | Yes | Yes |
| Full 4-MiB snapshots at 1907-1910 unchanged | All four | All four |
| Instruction events matching independent point capture | 1324 / 1324 | 1406 / 1406 |
| Total device-event records | 3266 | 3524 |

Instruction checks compare order, invocation, opcode, all GPR words and the
thread word exactly; they do not shift either stream. All 1984 shared
delivered-input polls match the selected route and each other. Initial flash
matches on both sides; oracle controller-pak equivalence remains unverified.
Native `comparison-1908.json` and `input-poll-comparison.json` preserve the
prefix and delivered-input checks. This proves bounded non-perturbation of
the observed traces and snapshots, not equality of every execution effect.

Pins:

- Native source snapshot: `12ca800b3fd5554dd5574c2a1dd4c6f85df24772`.
  Build receipt: `autonomy/source-device-events-20260927b/source-build.json`.
  EXE: `c11c234fd13fbf7aace6b791054434b71630c4e820632e4ee694281c6eda6fb8`.
  Runtime: `6677b08492f0aa59f09e2251ae83c28c4d502fe0c86b45db32ce57f6d9c46a17`.
- Oracle build: `oracle-device-events-20260927b`; cached interpreter Core 1,
  the same engine as the pinned control.
  DLL: `3e1619c5ee5f93279b134c591682a96f6622ce87ac6b26451d1cd5cab204d54f`.
  Runtime: `aeed86fd43d8c52bf1b0c09e42c8f278c355233ffd478b0baefd9cc8535c9bf7`.
- Complete native update trace:
  `45ee833c282ef24bd4e07f8377e0528a73aed58148b5f6d1059ea7edcac88f86`.
  Complete oracle update trace:
  `3437cf759d969a6c524cd28e65d94e1f0cd0e9f268ae940c362f225534d0f31b`.
- Native result: `68be4139130e14115da23e94509df2d52bcd8ea039c733607bf075c26739043f`.
  Oracle result: `9284d00469eebceb54eea769ecaa6b8d9c0dced2947e8e94f31506da6b3e3445`.

Previously pinned runtimes were not overwritten. Build receipts do not claim
a completely verified dependency closure or product promotion.

## Preserved failures and implementation corrections

Native build A failed warnings-as-errors for a shadowed local name. Build B
uses distinct names and reports Cause with CPU-visible timer/MI pending bits,
not merely the software latch. Its frozen source and failed predecessor
remain available. Oracle build A instrumented only the pure interpreter;
it was not used for qualification. Build B also instruments cached dispatch,
excluding decode/block trampolines to prevent duplicate instruction entries.

Native capture A reached its target normally but the wrapper rejected the
additional poll-semantic-hash request: that observer is implemented only in
the cooperative controller HLE, which original-OS execution does not call.
The failed capture remains failed. The wrapper now rejects that unsupported
option before process launch, with test coverage, rather than producing a
header-only stream or silently dropping the request. Successful capture B
requests the established original-OS contract: completed-update hashes and
delivered-input tracing, plus the new bounded event/point observations.
Implementing an original-OS poll-state observer remains separate future work.

The focused Python suite passes 36 tests; the complete autonomy suite passes
341 tests (86.116 seconds). Both C and C++ writer tests pass under CTest, and
`git diff --check` passes.

## Next acceptance work

The subsequent [autonomous device-observation lane](autonomy-device-observation.md)
now implements source/runtime registration, deterministic qualification,
ledger execution and research routing. Its live verification status is recorded
there; implementation alone is not a passed observation or causal repair.

Bind runtime/source pins and the exact capture contract into an independently
revalidated autonomous measurement producer. This diagnostic is not yet that
producer, a causal repair, or proof of globally aligned clocks/retirement.
Test a falsifiable explanation of the pre-1908 message-availability split;
do not adjust VI counts, ignore fields or shift comparison boundaries.
General proof construction, reviewed repair integration and full-route
coverage remain open. The 1291 request is achieved; the entire automation
loop is not complete.
