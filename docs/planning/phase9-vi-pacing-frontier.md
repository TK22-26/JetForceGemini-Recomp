# Phase 9: update-1292 VI pacing frontier

## Current result (2026-09-26)

The opt-in original-OS execution path passes this boundary and matches the
strict oracle prefix through **1300**, repeated twice. At updates 1290–1292,
native and oracle now consume the same retraces: 2940, 2943, 2946. See
[the evidence and remaining limits](phase9-execution-frontier-1300.md).
The older diagnosis below describes the unchanged cooperative control.

## Status (2026-09-24)

Diagnosis, not a runtime fix or parity acceptance. The opt-in SI candidate
and isolated rounding-corrected oracle match semantic completed-update
hashes through update 1291. Update 1292 differs in 17 actor records.
The persistent autonomous goal remains paused.

## Measured sequence

Fresh captures use the same US ROM, input export, initial flash and native
candidate pinned in `phase9-si-completion-timing.md`, and the isolated
corrected oracle in `phase9-oracle-rounding-repair.md`.

| Completed update | Native elapsed VI (0x800a3374) | Oracle elapsed VI |
| --- | --- | --- |
| 1289 | 2 | 2 |
| 1290 | 2 | 2 |
| 1291 | 2 | 3 |
| 1292 | 2 | 3 |
| 1293 | 2 | 3 |

The game pacing routine at 0x80054fbc starts a count at one, drains
0x800feb80, and can change pacing mode byte 0x800fecac from two to three
when the accumulated count reaches three. The oracle watch captures the
mode write at PC 0x800550e8, with 1290 updates completed, poll 1300,
consumed VI 2942. Native retains mode two. The new elapsed-time value is
stored at the end of update 1291 and is available to gameplay on 1292.
This is a concrete upstream discrepancy, not proof that every differing
actor byte has individually been explained.

Queue calls show two successful nonblocking drains on the oracle versus
one on native at this transition (followed by an empty receive).
Oracle queue 0x800fe8a8 receives its completion message at VI 2941;
another VI message is queued at VI 2942 before the drain.

The follow-up entry probe locates that extra VI **before entry** to
0x80054fbc, rather than inside its helper 0x8005539c:

| Update being executed | Native VI at entry | Oracle VI at entry | Controller poll |
| --- | --- | --- | --- |
| 1290 | 2752 | 2939 | 1299 |
| 1291 | 2754 | 2942 | 1300 |
| 1292 | 2756 | 2944 | 1301 |

Oracle `completed_updates` is one less than the update being executed;
native `update_candidate` names the update being executed. Absolute VI
counts already differ earlier; the important measurement is the local
extra VI between corresponding entries, not equality of absolute counters.
The four call arguments match at these entries.

## Native mechanism and limits of the conclusion

`src/boot/native_boot.cpp` charges 64 Count ticks per function dispatch,
regardless of executed instruction work. `service_vi_frame` is called
from the scheduler loop after a quiescent/timeslice outcome. It advances
Count by another 781250 ticks. Dispatch processing services SI deadlines
and timers, but does not independently deliver a VI at an absolute guest
clock deadline. This is not an instruction-accounted clock capable of
faithfully representing a VI interrupt during arbitrary guest work.

This structural gap is relevant to the observed pacing discrepancy.
The captures do **not** yet establish a hardware-qualified CPU cost model,
the exact interrupted instruction, or whether preceding CPU work versus
device timing is responsible for crossing the reference VI boundary.
Changing the dispatch constant until this route matches is not a fix.

A rendering control reran native to target 2800 instead of 3000, placing
the frontier inside the last-240-VI rendered window. Shared update traces
and frontier snapshots remained identical. Update-1292 snapshot SHA-256
on both runs is
`a45c570e3436536c4548d26daadd08ee6f5afbe37a423147600e34679108815e`.
Fast-replay rendering suppression therefore does not explain this local
failure. This does not qualify the entire graphics timing model.

## Artifacts

All directories are under `tools/private/`:

- `vi-frontier1292-native-20260924a`: elapsed-word trace, snapshots, timing.
- `vi-frontier1292-oracle-20260924a`: elapsed-word trace, snapshots, queues.
- `vi-frontier1292-rendered-20260924a`: rendering control.
- `vi-pacing-entry-native-20260924a`: entry arguments/registers, mode watch.
- `vi-pacing-entry-oracle-20260924a`: entry arguments/registers, mode watch,
  queue calls; completed successfully with the same corrected-oracle final
  RDRAM hash as the earlier route capture.

## Implementation gate / next bounded experiment

Do not force mode three, rewrite the elapsed word, inject a VI at update
1291, ignore timing-dependent actor fields, or copy oracle state into native.

Before selecting a replacement timing model, capture guest Count and
interrupt position across the interval from the task-completion return
to pacing entry, on the reference. Account for executed work and device
events separately; function-entry counts alone are not CPU timing.
The required implementation direction is a shared monotonic guest clock
with absolute VI/device deadlines and safe guest preemption points, with
an explicitly qualified execution-cost model. A deadline queue alone
would not supply the missing CPU accounting.

Acceptance must include event ordering across runnable guest work,
blocking waits, multiple deadlines, and no early/duplicate events, then
repeat this unchanged route with same-index comparisons. Preserve the
matching prefix and advance the frontier without route-specific constants.
Hardware timing and oracle timing must remain distinct claims.

## Clock/interrupt experiment: hypothesis supported, repair not qualified

The next bounded experiment completed successfully on both sides. New
`--queue-clock-trace` oracle instrumentation records exposed CP0 Count,
EPC and Cause at selected queue calls, their caller return PCs, the selected
entry PC and the general exception vector. Return-PC hooks identify PC
execution, not a uniquely paired outstanding call; shared return sites can
therefore produce extra observations. The focused window and row/hook limits
bound the capture. Core Count may be updated lazily; its measured intervals
are reference observations, not a hardware cycle calibration.

During update 1291 (completed-update counter 1290):

| Reference event | Consumed VI | Count | Interrupted PC |
| --- | --- | --- | --- |
| Graphics receive caller return, 0x80332240 | 2941 | 0x8b38b186 | n/a |
| Exception entry on the next VI | 2941 | 0x8b3bd454 | 0x80013a80 |
| Game VI queue send | 2942 | 0x8b3bde8a | n/a |
| Pacing entry, 0x80054fbc | 2942 | 0x8b3c30a8 | n/a |

The exception has Cause `0x10000400`. The subsequent VI consumption and
queue send establish the VI association; Cause alone does not distinguish
individual RCP interrupt sources. EPC `0x80013a80` is an ordinary `lh`
instruction in the game routine beginning at `0x80013970`, not a queue wait
or idle loop. The receive-return-to-entry interval is **229154** reference
Count ticks, including intervening interrupt/service work. The interrupt
occurs **205518** ticks after that receive return.

The corresponding native capture records:

- Graphics receive return at Count **2490712168**, consumed VI 2754.
- Pacing entry at Count **2490713576**, still consumed VI 2754.
- Difference: **1408** ticks, exactly 22 fixed 64-tick dispatch charges.

This directly supports the missing execution-time/preemption hypothesis.
It also shows why merely checking VI deadlines at existing dispatch points
is insufficient: native would still undercount this interval substantially.
Do not interpret the ratio as a proposed multiplier; the two intervals also
include differing OS/interrupt work and are not a per-instruction benchmark.

Artifacts:

- `tools/private/vi-pacing-clock-oracle-20260924a/queue-clock.tsv`: 205 rows,
  valid completion footer, replay exit zero.
- `tools/private/vi-pacing-clock-native-20260924a/progress.json.timing.tsv`:
  `guest-clock` observations, replay exit zero.
- Oracle update trace SHA-256 is unchanged from the uninstrumented clock
  control: `2f2867837c3aa1ee5281135f49e8e0c48062fe285acc369a38d21ab1d8f592dc`.
- Native update trace SHA-256 is likewise unchanged:
  `edd1bcca844f8fd2708650d922f829beab673ceffef9911a5275b0edbe0cca8e`.
- Diagnostic native executable SHA-256:
  `e4b17a859ff1d253544b91cad13f53fdbde67e4df722d3a5fbc2cf64d741208b`.
- Native Release build and 26 replay contract tests pass.

No behavior-changing timing repair is accepted or enabled by this experiment.
The remaining implementation gate is now specific: qualify execution-cost
accounting through generated basic blocks/loops and the guest OS work
replaced by HLE, then drive absolute VI/device deadlines from that clock.
Charging only generated instructions while silently omitting HLE work is
not sufficient either. Preserve branch/delay-slot semantics and guest
interrupt masks when adding preemption points. These are runtime/generator
changes, not a local patch to the actor or pacing function.

Stop at this gate rather than tune costs to this replay or claim a fix from
the diagnostic evidence. The matching semantic prefix remains 1291 updates.

Follow-up: the [execution-clock prototype](phase9-execution-clock-implementation.md)
now passes a ROM-free generated-code preemption proof. It is not yet
integrated into the game; CPU/HLE/device timing qualification remains open.

The subsequent [framebuffer writeback experiment](phase9-renderer-cpu-writeback.md)
corrected a CPU-visible depth-buffer discrepancy found by full-game instruction
observation. It preserves the same 1291-update prefix; it does not yet repair
the missing execution-driven VI interruption.
