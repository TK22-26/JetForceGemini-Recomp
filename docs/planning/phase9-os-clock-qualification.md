# OS queue timing qualification (2026-09-26)

Current status: the opt-in execution-driven original-OS path now matches
strictly through update **1300**, repeated twice. See the
[bounded frontier result](phase9-execution-frontier-1300.md) for pins and limits.
No guessed OS-call costs were installed. Earlier 1291-only checkpoints below
are retained as the investigation history, not the current result.

## Why original queue routines cannot simply replace native calls

The native queue implementation initializes the guest waiting-thread list
fields to zero and maintains blocking/wakeup state in `ThreadScheduler`.
The original guest routines follow guest linked thread lists and call guest
context-switch machinery. The original send path dereferences the waiting
list pointer even when only deciding whether there is a waiter. Blindly
executing that routine against native queue state is therefore unsafe.
Running original OS routines requires a compatible guest thread/sentinel
representation and context-switch bridge, not only a dispatch substitution.
Leaf translation routines without that dependency remain separate candidates.

## Reference call tracing

`--queue-clock-trace` now additionally emits `os-call-clock.tsv`. Calls are
paired using the US running-thread pointer at `0x800a9e90`, a per-thread
stack, return PC and restored stack pointer. The trace records initial queue
occupancy/capacity, blocking flag, output-pointer presence, Count interval,
return value, exception epochs, and running-thread-pointer write epochs.
Pointer writes conservatively indicate possible context switches, including
redundant writes. Calls spanning an exception, context switch or an expected
blocking wait are excluded from uninterrupted-cost groups. Their total
duration is not silently treated as CPU execution time.

The parser requires bounded rows, unique call identities, legal pointers,
queue states and a matching footer. Unfinished calls are counted explicitly.
The replay wrapper fails closed if a requested OS call trace is missing or
invalid. Exposed core Count may be lazy; these remain reference observations.

Final-schema capture: `tools/private/os-queue-clock-oracle-20260926b`.
48 completed calls, zero unfinished, 14 excluded intervals. Remaining groups:

| Operation | Observed Count ticks | Samples |
| --- | ---: | ---: |
| Empty nonblocking receive, null output | 80 | 6 |
| Successful nonblocking receive, null output, valid=1 | 120 | 6 |
| Same receive, valid=2 | 120 | 1 |
| Send, nonblocking, initial valid=0 | 132 or 288 | 14 |
| Send, nonblocking, initial valid=1 | 132 | 1 |
| Send with blocking flag but available capacity | 288 | 6 |

Queue occupancy alone does not select the send path: waiting-thread state
also matters. The 288-tick branch is not yet independently qualified as a
general wakeup-cost model. Do not use a mean of these observations.

The final-schema capture's update trace SHA-256 is
`2f2867837c3aa1ee5281135f49e8e0c48062fe285acc369a38d21ab1d8f592dc`,
identical to the prior corrected reference. Earlier `...20260926a` used an
intermediate trace format without the context-switch exclusion; do not use
it for final cost classification. The wrapper was subsequently tightened
to require the sidecar; the b capture was also checked directly with the
new parser, but its saved wrapper result predates that added summary field.

## Independent original-OS microtest

`phase9_cpu_queue_micro.S` is an original test driver, not copied OS code.
The private builder retains original static code from the user's pinned
US ROM and replaces its entry payload with the test. This ROM and its
original routines remain local; no ROM bytes are committed/distributed.
The test disables interrupts, uses a one-slot queue and an explicit empty
thread-list sentinel, and calls the original send/receive routines.

Two fresh Mupen runs produce identical observations:

| Case | Raw Count interval, including measurement boundary | Return | Queue valid count |
| --- | ---: | --- | ---: |
| Original three-instruction test leaf | 12 | 0 | 0 |
| Empty receive | 86 | -1 | 0 |
| Send | 138 | 0 | 1 |
| Receive with output pointer | 140 | 0 | 0 |
| Refill | 138 | 0 | 1 |
| Send to full queue | 96 | -1 | 1 |
| Receive with null output | 126 | 0 | 0 |

The output word is independently checked as 1234. The full send attempts
5678 and is checked to fail without changing queue occupancy. This fixture
does not separately read back the message buffer after that failed send.
The leaf takes six ticks under the previously observed Mupen two-tick
instruction profile; its 12-tick measurement implies six ticks of boundary
overhead in this fixture. Subtracting that boundary yields 80/132/120 for
empty receive/no-wakeup send/discard receive, agreeing with the independently
captured gameplay intervals. Raw measurements are retained; this inference
does not qualify hardware timing or blocked/wakeup paths.

Artifacts under `tools/private`:

- `cpu-queue-os-20260926a`: private payload and ROM.
- `os-queue-micro-mupen-20260926a` and `...b`: repeated microtest results.

Probe ROM SHA-256:
`685e788bf54ce8fc3c5f7d26a51bec1e297b0186238c432109f74e0c2c4bbc8c`.
37 relevant Python trace/parser/replay contract tests pass; `git diff --check`
passes. No native executable behavior was changed in this investigation.

## Next gate

Independently exercise waiter wakeup, full-queue blocking, priority-dependent
rescheduling and interrupt-mask restoration. Account for CPU segments and
device waits separately. Either execute original queue code with a complete
guest-state bridge or implement a qualified path-sensitive replacement;
do not invent a constant cost for a blocked interval or mix incompatible
guest/native scheduler state. Other OS calls and device timing remain open.

## Native queue semantics repair (2026-09-26)

While following the blocking/wakeup gate, native inspection exposed two
concrete gaps: every receiver on a queue was awakened by a send, and a full
queue with `OS_MESG_BLOCK` still trapped instead of parking its sender.
The [SDK messaging contract](https://ultra64.ca/files/documentation/online-manuals/man-v5-1/n64man/os/osSendMesg.htm)
specifies one highest-priority eligible waiter, FIFO among equal-priority
waiters, and suspension until the appropriate queue condition is satisfied.

Implemented in `ThreadScheduler` and the native queue bridge:

- Separate send-space and receive-message wait conditions.
- One-waiter selection by priority and wait insertion order, independent of
  thread creation id. The existing runnable-thread tie-break is unchanged.
- Blocking send/jam retains its payload on the suspended caller's stack,
  retries after wakeup, and enqueues only when space exists.
- Successful receives notify a waiting sender, including the native fast
  receive path. Higher-priority awakened senders run before receive returns.
- The native bridge validates queue state before parking a full-queue sender;
  invalid state or a blocking attempt outside a guest thread still fails closed.

The new regression first failed on the old implementation: one send made
both equal-priority receivers runnable. It passes with the repair. Additional
tests cover priority/FIFO sender selection, nonblocking full rejection,
blocking send versus jam ordering, exact-once payload retention, no busy
spin while blocked, and priority handoff on receipt.

Validation:

- Windows Release build and scheduler/timer/execution-clock CTests pass.
- GCC ASan/UBSan scheduler tests pass; binary artifact
  `tools/private/queue-scheduler-asan-20260926a`.
- 100 consecutive Windows scheduler regression runs pass. These are unit
  runs, not 100 complete gameplay routes.
- Two native runs, `tools/private/queue-scheduler-native-20260926a` and `...b`,
  complete 3000 retraces with 1413 completed updates, 1423 input polls and
  final state hash `bfc381ff27cf56b147fa300d98f04c672316e6ccbf571e9870dbeb096e98e74b`.
- The update trace remains byte-identical to the pre-repair native trace:
  `edd1bcca844f8fd2708650d922f829beab673ceffef9911a5275b0edbe0cca8e`.
  Poll trace hash remains
  `c9d2da0491b089e9910cdd689a71030c03a2d7ea5fa3f6ddbe3ec556accff10f`.
- Same-index comparison through update 1291 passes, recorded in the first
  run's `prefix-comparison.json`.
- Native executable SHA-256:
  `ec414b2ec354327a8a4612848d23e8ed4028ec9acc45b53a9a5f241cac4914df`.

This is a real runtime semantics repair, not the update-1292 timing fix.
No timing constants were added or tuned. Original-OS blocking/wakeup
**timing** qualification, interrupt-mask integration and execution-clock
game integration remain open. The replay does not demonstrate that it
exercised a full-queue blocked send; that new path is covered by the focused
tests. Future native snapshots must preserve wait direction/order and
suspended payloads in addition to RDRAM; no snapshot acceptance is claimed.

## Original-OS threaded handoff experiment (2026-09-26)

The new `queue_threads` private micro-ROM uses the ROM's own `osInitialize`,
`osCreateThread`, `osCreateMesgQueue`, `osStartThread`, `osSetThreadPri`,
send/receive and stop routines. Its original test driver creates two real
guest threads and a one-slot queue through those APIs; it does not fabricate
thread contexts or splice native scheduler state into original OS lists.
The public [thread-start contract](https://ultra64.ca/files/documentation/online-manuals/man/n64man/os/osStartThread.html)
provides the priority-handoff expectation.

Sequence: the worker blocks receiving; the main thread raises its priority
and sends 1111, waking but not running the lower-priority worker. Lowering
the main priority lets the worker consume 1111 and block again. Sending
2222 now hands off immediately; the worker consumes it, fills the queue
with 3333, then blocks sending 4444. Main receives 3333, allowing the
worker's send to finish before main's receive returns, then receives 4444.
Payloads, return values, queue occupancy, lack of premature lower-priority
execution, and restoration of each thread's CP0 Status are checked.

Two fresh corrected-Mupen runs (`os-queue-threads-mupen-20260926b` and `...c`)
exit zero and produce byte-identical traces:

| Operation | Raw Count interval | Interpretation |
| --- | ---: | --- |
| Send waking lower-priority receiver | 294 | uninterrupted OS path |
| Send waking higher-priority receiver | 1268 | includes other thread execution |
| Receive waking higher-priority sender | 1070 | includes other thread execution |
| Final receive with output pointer | 140 | uninterrupted OS path |
| Worker first blocked receive | 1334 | includes suspended interval |
| Worker second blocked receive | 1046 | includes suspended interval |
| Worker fills queue, no waiter | 138 | uninterrupted OS path |
| Worker blocked full-queue send | 1108 | includes suspended interval |

Subtracting the six-tick measurement boundary previously established with
the independent leaf test gives 288 for the lower-priority wakeup send,
132 for the no-waiter send and 134 for the receive with output. The first
two agree with independent gameplay observations. This qualifies those
specific uninterrupted reference paths, not all queue shapes/priorities,
hardware timing, or the CPU portions of suspended calls. In particular,
1268/1070/1334/1046/1108 must **not** become constant HLE execution costs.

Both threads deliberately clear IE at entry; recorded Status is `0x0400ff00`
before and after every measured call, and the exception hook records zero
exceptions. This verifies disabled-state restoration and cooperative OS
handoffs, **not enabled-interrupt delivery or every mask combination**.

The first run (`...a`) produced the same trace but exited abnormally with
Windows status `3221226525` and is rejected. The Lua exception callback
is now unregistered before
emulator shutdown; both subsequent runs exited cleanly. No failing run
was reclassified as accepted.

Accepted trace SHA-256:
`b9258047af77241ae5c646eb117ec9d7df9d51c57d97ecf4f1c3e32c8235a463`.

Build artifact: `tools/private/cpu-queue_threads-os-20260926a`.
Private ROM SHA-256:
`090380a46d5abbcdf94eff7885970ec64c5ffc9e9ed355bfce7c2004195cae7a`.
No ROM bytes are distributed. The generic private builder/runner accepts
`queue_threads`; existing probe choices retain their behavior.

The native scheduler regression now mirrors the same handoff/payload
sequence and passes. Explicit yields model the rescheduling done by the
native guest-call bridge; this is a scheduler test, not a generated-game
integration test. Windows scheduler/timer/clock CTests (3), relevant Python
tests (39), and the scheduler GCC ASan/UBSan run pass.

No shipping timing changes were made. The matched gameplay frontier remains
update 1291. Next work remains separating original OS execution segments
from suspension, covering other OS/device paths, and integrating those
with instruction retirement and independent deadlines.

## Direct guest translation experiment (2026-09-26)

`JFG_PHASE9_GUEST_LEAF_PROBE=1` is an opt-in, **currently rejected** experiment
executing the original generated `osVirtualToPhysical` routine for direct
KSEG0/KSEG1 addresses. It checks the returned physical address and emits
focused instruction observations. It does not install an execution-clock
profile or guess a cost for unsupported paths. All default behavior is
unchanged.

The first two private runs (`execution-leaf-native-20260926a` and `...b`)
stop during startup, before any completed update: caller `0x8009b5c0`
passes `0x00000000`. That requires the original `__osProbeTLB` path, while
the current minimal runtime traps on the needed CP0/TLB operations. The
legacy HLE returns its input for non-KSEG addresses; that is not a validated
replacement for original address translation. Do not bypass this gate or
declare the leaf globally accounted from its KSEG cases alone.

The independent private `translation` micro-ROM now inventories all 32 TLB
entries after boot and invokes the original OS translator for null, KSEG0
and KSEG1 addresses. Two corrected-Mupen runs, `os-translation-mupen-20260926a`
and `...b`, exit zero with identical observations:

| Argument | Result | Count interval including six-tick measurement boundary |
| --- | --- | ---: |
| `0x00000000` | `0xffffffff` | 118 |
| `0x80001234` | `0x00001234` | 42 |
| `0xa0001234` | `0x00001234` | 58 |

All observed boot TLB entry fields are zero. This is **reference boot state**,
not a hardware reset contract. The [NEC VR4300 manual, chapters 5 and 16](https://hack64.net/docs/VR43XX.pdf)
states that relevant reset contents and multiple-match probe behavior are
undefined. A proper implementation therefore needs explicit CP0/TLB state,
architectural lookup/read/write behavior and a separately qualified reference
initialization policy; it must not special-case null to manufacture a pass.
Native TLB support has not been implemented by this experiment.

The subsequent independently authored `Tlb32` storage/probe mechanism in
`include/jfg/boot/tlb.hpp` now covers explicit initialization, indexed access,
all seven legal page masks, ASID/global matching and invalid-page probing.
Its `TlbRegisters32` boundary also implements supported register masking,
indexed read/write and probe-result publication, preserving state on rejected
operations. Unknown registers, reset contents and duplicate matches are not
silently accepted. Random/Wired and instruction hazards remain outside this
mechanism's scope.
It reports unknown or multiply matching entries rather than inventing a
result. ROM-free tests pass with GCC ASan/UBSan. This is **not yet connected
to generated CP0/TLB operations**, does not model 64-bit virtual addressing,
and intentionally supplies no default hardware reset state. The observed
all-zero reference boot entries produce multiple matches for null; selecting
an index for that undefined case still needs explicit reference qualification.
The additional private capture `os-translation-mupen-20260926c` records Index
zero after null translation, with the same results/timings as the previous
two runs. Its ROM is `cpu-translation-os-20260926b/cpu-translation.n64`, SHA-256
`1db47f945a62934cf94f61040d5d97f9123a453a102998e2322101f0b4290ab8`.
This observes one undefined boot case, not every duplicate-tag configuration.
No native translation or update-frontier pass follows from the unit test.

Private build: `cpu-translation-os-20260926a`; ROM SHA-256
`1014070665bd3ca20f0f7bd8630f11cffccedba4074f8ca27bdf0df74c890c30`.
The probe retains original static code only in local derived ROMs. No ROM
bytes are distributed. This microtest does not prove full-game TLB state
equivalence or memory-translation timing on hardware.

Separate reference artifact `execution-leaf-oracle-20260926a` records 810
translation calls around the frontier and preserves the original update
hash digest. Native failed before that window; there is no paired full-game
leaf timing acceptance yet.
All 810 reference calls were uninterrupted and took 36 Count ticks each.

The failed launch also exposed a harness reporting bug: an empty update
stream raised before `native-result.json` was written. The wrapper now
archives trace parsing errors, rejects the run, and does not count a valid
prefix of a malformed stream as complete. Run `...b` demonstrates this
failure artifact; dedicated unit tests cover missing/truncated/valid traces.

The disabled-leaf control `execution-leaf-disabled-native-20260926a` still
finishes 3000 retraces with the writeback candidate's same final state hash.
No rejected leaf experiment was enabled by default or silently skipped.

### CPU operation bridge and reference TLB policy

The expanded original assembly probe now explicitly writes duplicate nonzero
tags (slots 17 then 5), changes ASID/global bits, and tests a 16 KiB page mask
and the next page pair. Two fresh corrected-Mupen runs,
`os-translation-mupen-20260926d` and `...e`, produce identical six probe indices:
`5, 0x80000005, 5, 0x80000005, 17, 0x80000011`. The duplicate chooses the
lowest index, independent of insertion order; misses retain previous low
Index bits. Trace SHA-256:
`d85f592221d6f34efffb366acff2c4376f2521f004a101a377f09e34f1612fbe`.
Private ROM `cpu-translation-os-20260926c/cpu-translation.n64` SHA-256:
`55704f33f16fe8b29bc0eba5892fd8d8559ecf62cf2531e730f151c26be9da6f`.

`TlbRegisters32::observed_mupen_boot()` explicitly selects the observed zero
initialization, lowest-index duplicate policy and retained miss bits. The
ordinary constructor continues to reject unknown state/multiple matches.
The named factory is not a hardware reset promise or a null-address patch.
Unit tests reproduce the independent assembly sequence.

The generated runtime now has an optional, single-owner CPU-operation
binding, separate from function dispatch. Supported MFC0/MTC0/TLB operations
can call the native state model; absent/rejected callbacks retain fatal
traps. Unknown operations, Random/TLBWR, cache operations, ERET and extended
virtual addressing are not implicitly accepted. Ownership cannot be replaced
or released during an active callback, including a reentrant release attempt.
Status retains the existing per-context implementation.

`JFG_PHASE9_GUEST_LEAF_PROBE=1` uses this bridge and the named reference
policy to execute the original translator and original TLB helper. It
remains off by default, and does not yet drive guest deadlines from the
observed instruction count. Its runtime replay validation is recorded below
when completed; unit success alone is not frontier acceptance.

The runtime ABI adds exactly two owner-binding exports. The generator and
synthetic fixture inventories/link-smoke coverage were updated accordingly;
object-shape checking was not disabled. Private observation root
`execution-root-20260926e/root` is regenerated with the new normalizer and
passes the 2935-body observer-only comparison. The intermediate `...d` root
was rejected by incomplete link-smoke coverage and is not accepted evidence.
Changes to the runtime/normalizer invalidate older producer source pins;
Phase 4/6 signing has not been refreshed or asserted by this diagnostic work.
The new public header is included in producer/native source closures.

Bridge ownership and reject-path tests pass on Windows. GCC ASan/UBSan
found a pre-existing test-worker lifetime bug (loop index captured by
reference); capturing it by value fixes the test without changing production
scheduling. The corrected sanitizer executable is
`tools/private/cpu-bridge-tests-20260926b`. Its intentional aborting children
verify that unbound/unsupported CPU operations still fail closed.

### Translation and zeroing replay results

The earlier startup rejection is now resolved by the explicit TLB/CPU bridge,
not by special-casing the null argument. `execution-leaf-native-20260926c`
finishes 3000 retraces with the original translator enabled. The full-game
leaf call sequences are **not** identical: the focused native window has
763 calls (18 instructions each), versus 810 reference calls (36 ticks each).
The strict call comparator rejects this count difference; no index shifting
or claim of complete OS-work equivalence follows from matching leaf costs.

The same opt-in path also runs the original `bzero`, with its existing range
validation preserved. Private generated-code test `generated-bzero-20260926b`
passes 128 alignment/length cases under ASan/UBSan, checking the entire memory
buffer, including bytes outside the requested range. Negative/zero lengths
execute the original early return; they are not charged a guessed constant.
The initial `...a` test build failed on a missing test-driver include and is
not accepted evidence.

Two native runs, `execution-leaf-native-20260926d` and `...e`, finish 3000
retraces / 1413 updates / 1423 controller polls, with identical final state
hash `73df3e2cabae3784cac141a79ad4e16b3c149240012e1e9337ea666b50cd4d9f`.
Executable SHA-256:
`27e41da0cef0fcc1ef570adf34b0c8a83bbd57c92f82b0214cad0b2d032e5eba`.
Their update trace retains the existing digest
`edd1bcca844f8fd2708650d922f829beab673ceffef9911a5275b0edbe0cca8e`.
Strict comparison through update 1292 still finds the first mismatch at
1292 (actors), so the matched prefix remains 1291.

### Original cache-maintenance execution

An independently authored private `cache` micro-ROM exercises all four
original OS cache routines: 192 range calls (three routines, four alignments,
16 lengths spanning negative, zero, line and whole-cache boundaries), plus
the whole-data-cache routine. It measures Count with interrupts disabled
and separately observes cached/uncached data aliases before/after maintenance.
The data aliases are coherent in these reference measurements. This is not
a claim about physical VR4300 caches or arbitrary self-modifying code.

Repeated corrected-Mupen runs `os-cache-mupen-20260926a` and `...b` exit zero
with identical trace SHA-256:
`43ed4742c176a0ad97d0dbfcab9b343ac86db36046f0cbb76a3bd83582d67fe8`.
Private ROM `cpu-cache-os-20260926a/cpu-cache.n64` SHA-256:
`cccde4bdf258a6d6f923e98ea1fc5c0b07380f4d0d6952502ceaec93b00f3773`.
`generated-cache-20260926a` executes the same 193 cases using the private
original generated routines under ASan/UBSan. Every reference interval is
exactly twice the native executed instruction count plus the independently
established six-tick measurement boundary. No fitted cost table is installed.

The optional CPU bridge now accepts these six explicit CACHE selectors under
a named coherent-reference profile. Unknown selectors, nonqualified segments
and invalid address extensions remain fatal. The profile has no dirty CPU
lines to transfer; RT64 framebuffer commit remains a separate operation with
its own conflict checks. Generated code publication remains the existing
validated overlay mechanism, not a new general self-modifying-code facility.
Cache tags, cache/bus latency and hardware cache coherence are not implemented
by this profile. Default runtime behavior remains unchanged.

`execution-cache-native-20260926a` completes the 3000-retrace route with the
same final state and update hashes as the preceding leaf candidate.
Executable SHA-256:
`49f943bd324d697187755351a9a407c7149b8647167349e60ea015a75c1f1e54`.
Windows bridge tests cover accepted operations, rejected/unbound fatal paths,
reentrant ownership protection and invalid addresses. This does not yet fix
the frontier's missing execution-driven VI event.

### Empty-receive execution qualification

`generated-empty-receive-20260926a` executes the original nonblocking empty
receive and its original interrupt-disable/restore helpers in 32 ASan/UBSan
cases. It tests four Status values (IE enabled/disabled), four stack positions,
and both zero and deliberately invalid unused queue-link words. Every call
executes 40 instructions, preserves Status and callee-saved registers, returns
empty, and writes only its frame/caller argument-spill area. This agrees with
the independently measured 80-tick uninterrupted reference empty receive.
It does not exercise blocking waits or wakeups and does not qualify their costs.

`execution-empty-native-20260926a` finishes 3000 retraces with unchanged update
hashes (prefix still 1291). The opt-in path executes original empty receives
only after read-only HLE validation has returned empty; blocking/wakeup paths
remain explicitly unaccounted. Its final whole-state hash differs because
original stack writes and additional legacy dispatch charges are now visible.
Those 64-tick dispatch charges are still the old model, not the observed
40-instruction/80-reference-tick cost, and are not presented as calibrated.

### Correct live Status at thread entry

Native was installing the OS's **saved** thread Status (`0x0400ff03`, EXL set)
directly as the live entry Status. Original `__osDispatchThread` instead enters
the thread through ERET. The [NEC manual's ERET definition](https://hack64.net/docs/VR43XX.pdf)
(chapter 17, page 434) clears EXL when ERL is clear. Leaving EXL set would
permanently suppress a correctly masked interrupt-delivery implementation.

The private original-OS thread fixture now records both threads' Status at
their first instruction, before explicitly disabling interrupts. Repeated
reference runs `os-queue-threads-entry-mupen-20260926a` and `...b` both report
`0x0400ff01` at entry and `0x0400ff00` after disabling IE. All eight queue-call
intervals are unchanged and no exceptions occur. Trace SHA-256:
`b1fcdcb923db14d65192268fdc53330815eb43af6aa1c5e142b537e3eab038f4`.
Private ROM `cpu-queue_threads-os-20260926b/cpu-queue_threads.n64` SHA-256:
`aabebdfe6ddf31998ef59cd42791eee950155218aedef38fde8fe0f802e28407`.

Native thread handoff now applies the architectural Status transition before
calling the entry. This correction is not limited to the diagnostic flag;
the flag only enables entry-Status logging. Unit tests include ERL priority
and preservation of unrelated Status bits. `execution-thread-status-native-20260926a`
logs `0x0400ff01` for ordinary threads and `0x0000ff01` for the non-FR thread,
finishes the 3000-retrace route, and preserves all previous update hashes.
This does not implement general ERET/LLbit/EPC behavior or instruction-time
interrupt delivery. The first divergence is still 1292.

### MI interrupt-mask register and context restoration

The CPU-side MI mask register is no longer treated as plain writable memory
in the guest-leaf diagnostic profile. `MiInterruptMask` independently implements
the public SDK `MI_INTR_MASK_REG` contract: six read bits, six separate set/clear
command pairs on write. Unknown initialization, conflicting pairs and reserved
bits are rejected. 262144 command/initial-mask combinations pass on Windows and
under GCC ASan/UBSan, including atomic rejection. No device interrupt-delivery
or latency model is implied by this register implementation.

The private `mask` micro-ROM calls the original `osSetIntMask` for each of the
64 requested RCP masks, from both all-clear and all-set initial masks. CPU IE
is disabled and the fixture explicitly initializes the public OS global policy.
The return masks, retained CPU Status and MI readback agree in all 128 cases;
Count intervals are 78 or 86 including the six-tick measurement boundary.
Repeated reference runs `os-mask-mupen-20260926a` and `...b` have trace SHA-256
`f53033e610285d83bb51bb924b0a0113951426258bc3ffa142b539fdafd913af`.
ROM `cpu-mask-os-20260926a/cpu-mask.n64` SHA-256:
`9a3148bfdefd405f1a33d7958fdee28487c7059a625793833cf4490490daed43`.

The first game trial, `execution-mask-native-20260926a`, preserved update hashes
but exposed an additional missing OS handoff operation: all 516 focused mask
calls took the all-clear MI path (36 original instructions). The independent
game reference `execution-mask-oracle-20260926a` has 544 calls: 272 at 80 ticks,
271 at 72 ticks, one 738-tick interrupted call. The unequal call counts are
not paired by shifting indices, and the interrupted duration is not a CPU cost.
The native scheduler did not restore a thread's RCP mask on entry/switch.

An extended original-OS two-thread probe initializes both threads normally,
then clears SP only in the worker. It observes MI masks `63,63,63,62,62` for
main entry, worker entry, main after worker blocks, and the worker after its
two blocked receives resume. Repeated runs `os-queue-thread-masks-mupen-20260926a`
and `...b` agree, trace SHA-256:
`5b325d3f6573ccc29c8dad22f1958cdcf10b27b219c0c9023fcbdf2ee4a25a20`.
ROM `cpu-queue_threads-os-20260926c/cpu-queue_threads.n64` SHA-256:
`2916b7403ef25e8add24d93562cd40b3854a9abc033461ff76b47fdf8b54abf4`.
Added observations change suspended wall intervals as expected; uninterrupted
lower-wakeup/final-receive/no-waiter-send costs remain unchanged.

`ThreadScheduler` now offers a pre-run-installed baton hook for saving and
restoring host-owned context state at yield, block, preemption and completion.
The guest-leaf path uses it for per-thread RCP masks, with the observed initial
all-enabled mask. The first implementation accepts only the independently
qualified unrestricted global policy; other global policies fail explicitly
instead of guessing saved/effective-mask handling. These saved masks belong
in future runtime snapshots. ROM-free tests verify exact hook ordering and
independent context preservation. No generated guest context-switch cost or
complete interrupt handler has been supplied by this host-side hook.

The paired full-game trials `execution-mask-thread-native-20260926a` and
`...b` complete 3000 retraces / 1413 updates with identical final-state hash
`851dc9a946ee8cca0fa58c7dae673b1e53995364bd06d8fdd1405a27cdf8cbbe`.
Executable SHA-256:
`ac91ee937bf4f3011ab1a43f955cf0165832412d1112d322e0984efdb68467f9`.
The 516 focused mask calls now split into 258 executions of each path
(40 and 36 instructions), agreeing individually with the reference's 80/72
tick paths. Call totals still differ; this is not full-call-stream acceptance.
Strict comparison in `...b/comparison-1292.json` still rejects update 1292.

### Separate VI service operations and identify RCP sources

Native VI service is split into legacy clock advancement, presentation of
completed work, graphics completion, framebuffer selection, legacy SI
completion, and VI message delivery. The legacy wrapper retains exactly the
old order; no new clock is enabled. `execution-vi-split-native-20260926a`
preserves the preceding whole-state and update hashes. Executable SHA-256:
`60289f94dabde67225ff93b1465f810bb8e8da519b5484b52dafc401e1cdc0ba`.
This makes the individual operations callable from an independent event
dispatcher; it does not by itself supply one.

The read-only oracle queue-clock probe additionally records paired CPU Status,
MI pending/mask, SP status, DP status and VI-current observations. The wrapper
requires the companion trace to be complete, correctly ordered and valid.
`execution-task-oracle-20260926b` has 313 paired observations, including
19 SP, 6 SI, 7 AI, 15 VI and 28 PI exception observations. These are pending
masks at CPU exception entry, **not** exact assertion deadlines or a complete
inventory of device work. No DP-pending exception is observed in this window;
that alone is not proof that no DP work occurred.

RCP trace SHA-256:
`ba85285e9a972f136d95698869ec9950b8f9fe64dc73d92aa8e370a28506b33f`.
Both task captures (`...a`, without companion reads, and `...b`) retain the
reference update hash `2f2867837c3aa1ee5281135f49e8e0c48062fe285acc369a38d21ab1d8f592dc`.
The original SP start takes 48 uninterrupted Count ticks in all 20 focused
calls, with completion interrupts between VIs, not coupled to the next VI.

### SP task-start execution and independent device experiment

`SpStatus` implements the public SDK's SP_STATUS set/clear commands, separate
interrupt state and explicit task completion. Unknown/reserved commands and
conflicting pairs reject atomically. It does not implement DMA, arbitrary RSP
programs, yield/resume, or device timing. 819200 single-bit/old-status cases,
conflicting commands and lifecycle cases pass on Windows and GCC ASan/UBSan.

`generated-sp-start-20260926a` executes the original SP-start routine and its
status helpers in 20 ASan/UBSan cases. Each executes 24 instructions and
preserves its stack/callee-save state. This agrees with the 48-tick full-game
reference interval and the 54-tick private microtest including its independently
established six-tick measurement boundary. The native diagnostic now uses
this original start routine through guarded SP_STATUS MMIO, and updates status
at the existing host task completion. It still uses legacy task timing.
Original `osSpTaskLoad` is **not** executed or charged by this change.

Repeated `execution-sp-start-native-20260926a` / `...b` complete 3000 retraces,
with final-state hash
`a9441f01a121476e3b3e5dad21160fa7ef4cd13caafcd1a2a2767520de2ec05e` and executable
SHA-256 `441d6923ccc78c32cb67c7c5b97c6ca3358efc84ae8d1d5ea8c1ede4a5fe0e11`.
Their update hash is unchanged (`edd1bcca...`): matched prefix still 1291.

The independent `rsp` micro-ROM constructs 16 SDK tasks using the private
original microcode and authored no-op command streams: graphics/audio,
1/8/64/256 no-ops, and DP-wait flag off/on. CPU IE is disabled; the payload
polls SP status directly, avoiding interrupt-handler/wakeup latency. Repeated
`os-rsp-mupen-20260926a` / `...b` agree, trace SHA-256
`0b5539da6396499a3297c6977fbeed8db0e3f2cf1510389f1588507f80e9c188`.
ROM `cpu-rsp-os-20260926a/cpu-rsp.n64` SHA-256:
`d9241bbfbf3e5a35d1596368e9339b16b5cdf506ad16b5e1017da3011e6f2cd4`.
Load/start intervals are 890/54 ticks including measurement boundaries.
Observed completion is 1066 ticks from the pre-start measurement for graphics
and 4062 for audio, including start execution and polling granularity. These
totals are **not** installed as device latencies. The graphics full-sync command
also produces DP pending; audio does not. Both retain the independently pending
VI bit while CPU interrupts remain masked.

### VI period is a separate reference-profile discrepancy

The full-game RCP trace isolates VI exception intervals around 789000 Count
ticks, not the legacy native 781250. An independently authored `vi` micro-ROM
varies V_SYNC across 261, 262, 525, 526, 624 and 625, with H_SYNC 3093/3177.
CPU IE is disabled, the payload polls MI pending and acknowledges via
VI_CURRENT; two transition intervals are discarded after each register change.
No original OS bodies or graphics workload are needed.

`vi-clock-mupen-20260926a` collects five intervals per case; `...b` collects
32 consecutive intervals per case. The latter's totals are within 10 ticks
of `32 * (V_SYNC + 1) * 1500` for all 12 combinations. Polling-loop quantization
is bounded by its seven instructions / 14 reference ticks. This independently
supports the reference period rule, including 789000 for V_SYNC=525, without
fitting the gameplay route. It is not a physical VI timing claim; H_SYNC
insensitivity is a property observed in this reference configuration.
No replacement period or execution-driven game clock is enabled yet.

Private 32-sample ROM `cpu-vi-clock-20260926b/cpu-vi.n64` SHA-256:
`6b7181da321ef27e9148838e43ac96773044a07f0e43dfab610159dbf3da39d9`.

### Remaining original-OS coverage issue

The generated root has `osSpTaskLoad` but not its direct callee
`_VirtualToPhysicalTask` at 0x80098f40. The existing Phase 4 direct-call ledger
already classifies that target as an unresolved candidate. The missing helper
must be recovered through a validated symbol/generation path before substituting
the original load routine. Do not add an untracked body, inflate authoritative
coverage, suppress the lookup failure, or charge a guessed helper cost. This is
in addition to the existing guest queue/thread/context-switch coverage work.

### Effective reference-device timing qualification

The expanded VI sweep repeats exactly in `vi-clock-mupen-20260926b` / `...c`,
trace SHA-256 `372ccf8c6612cd90b8adfdefd40fa43e541ede87a138e342db39fd97afb315d8`.
The 32 consecutive differences telescope to two poll endpoints, not 32
independent accumulated errors. Their 14-tick endpoint bound uniquely selects
an integer period equal to `(V_SYNC + 1) * 1500` in all tested configurations.
The qualifier also rejects individual outliers that cancel in the total.

The revised SP fixture adds eight launch-to-poll phases per task class.
`os-rsp-phases-mupen-20260926b/rsp-deadlines.tsv` records original helper entry,
start-register-write observation, last-running and first-halted Count samples.
Generated original-code test `generated-sp-start-20260926b` independently
establishes the start-register store as instruction 20 of 24, with helper
entry at instruction 18. Exposed reference Count is identical at helper entry
and its delay-slot store (lazy update), 40 ticks after the pre-call measurement.
The store's retirement is at tick 46 including the three measurement/call
instructions, not at the stale exposed Count value.

After this explicit boundary accounting, the intersected completion windows
are `(998,1000]` for graphics and `(3998,4000]` for audio. At the qualified
two-tick observation resolution, these select effective delays of 1000/4000
from store retirement. This is not sub-instruction or physical RSP timing.
Phased ROM SHA-256:
`10bee41e4649995a1976c84a861412d7f741fb1445cf3c04f8d13681c5be73cf`.
Final deadline trace SHA-256:
`8595f1041786e07e8e30a5359e810ceb384f0f976481099a4412887983c47aba`.

`scripts/phase9_reference_device_timing.py` checks these derivations and
rejects incomplete, reordered, ambiguous or altered-boundary evidence.
`include/jfg/boot/reference_device_timing.hpp` exposes a limited named profile:
only the tested VI configurations and the two qualified original task classes.
The executable does **not** use this profile yet. Unit tests exercise the
existing deadline/latch mechanism with these independently selected values,
including SP before VI, no duplicate completion and masked pending delivery.
Windows and GCC ASan/UBSan tests pass. No game-clock acceptance follows.

The current executable with guest-leaf disabled (`execution-leaf-disabled-native-20260926b`)
retains the pre-leaf whole-state hash
`f7d29223aa0a51779cf6b8387621f86aa41ca5362627b2e37da311bde5391be7`.
No progress beyond the 1291 matching prefix is claimed by these controls.

### Recovery experiment for the missing task helper

The original ELF contains the helper's bytes but **no symbol** at its entry.
`phase9_recover_task_helper.py` verifies that the 284-byte gap agrees with the
pinned original ROM, has a completely covered forward integer CFG, seven
calls to the existing translator, one copy call, a unique final return and
the following executable function boundary. The existing original task-load
call is also checked. It then uses binutils to add symbol metadata to a NEW
private ELF; every allocated section's content/address/size/flags is checked
unchanged, and the source ELF is preserved.

`task-helper-recovery-20260926a` produces ELF SHA-256
`fb79011599731c913f6e001f2bac932941acbf623348012d0d277184dd418b92`
from source ELF
`ea06a1f7fd54454fbf65f9dbe0bb6d731d5a44f732c16c8d157b475cb8078f1b`.
The normal context-dump preparation and N64Recomp `--dump-context` then see
3730 executable function symbols and seven inferred size overrides, including
the recovered helper. This is a recovery experiment, **not** an installed
generated root or an accepted Phase 4 artifact. The existing 2905-body model
must be revised transparently to include the additional required body and its
call/return sites; the existing denominator checks have not been disabled.

### Required-body revision and original task-load execution

The metadata recovery was repeated with the allocated-section metadata checks
enabled (`task-helper-recovery-20260926b`), producing the same ELF digest.
The transform and normalizer now explicitly require 2906 authoritative bodies,
3730 executable symbols, seven size recoveries, 14046 direct call candidates
(13858 generated targets, 188 unresolved), and 3621 indirect sites (3416 native
returns, 205 decisions). The 30 support thunks and all relocation denominators
are unchanged. The new transform independently reproduces those counts; none
of the denominator or object-shape gates is disabled. Old inputs deliberately
fail the revised generator's exact counts. **The older Phase 4 manifest is not
acceptance for this new revision; its acceptance/pin refresh remains pending.**

Private `execution-root-20260926g` has 379025 instruction sites. Its pinned
recompiler is `e01d85069df1df0aef8019aa947bb87b75f3f3a41587b8141a75492d5d6135cc`
at `g3-final-n64recomp-8ae15e30/source/build-final/N64Recomp`, not the earlier
combined-v11 binary. Its compatible header retains SHA-256
`85f50a7742573d61fd4ee5a30637ee6300e41c307d7da76361b1b85ce52a1840`.
An attempted root using the upstream header failed its lineage check and is
not used. Merely switching to the new root preserved the previous whole-state
hash (`execution-task-root-native-20260926a`).

`ReferenceSpDma` implements a limited synchronous **reference** task-load
profile. The SDK SP register contract defines direction/fields; the new
read-only reference capture checks the observed completion state. This profile
supports aligned single-block RDRAM-to-SP transfers, preserves the reference's
written address/length/PC values, and rejects block/skip, misalignment, bank
wrap, out-of-range data and unsupported register operations. It is not a
physical DMA timing model, a general RSP engine, or yielded-task support.

`os-rsp-loads-mupen-20260926a` records SP registers, all 64 bytes of task DMEM
and all 384 bytes of boot IMEM at original task-load return, across the 16
independent task cases. Trace SHA-256:
`a4c5cb8db54a6d35944f856a6b8796c06bad824a7ef8ed0fabe6cdf3e172d6c8`.
`generated-sp-load-20260926c` executes the eleven original functions in the
closed call graph under GCC ASan/UBSan. Every task/register/memory comparison
passes. Source selection follows symbol addresses, not generated ordinals.

The opt-in native guest-leaf path now executes original task load as well as
start, through guarded SP DMA/status/PC MMIO. It retains legacy task completion
timing. Repeated `execution-sp-load-native-20260926a` / `...b` finish 3000 VIs,
1413 updates and 1423 polls with whole-state hash
`1b52ce7c019eb66eb25779764fcab2ea0733e7d2ad8aeabf0551bc4eedcfc58f`.
Executable SHA-256:
`65daf23ac300acfd983513efe237f3628c3b9e5f664b51af018b8680d0f7dd25`.
The update hash remains `edd1bcca...`; strict comparison still first differs
at update 1292. This is additional original-OS coverage, **not a frontier pass**.
Windows DMA/status/clock/scheduler tests and GCC ASan/UBSan DMA tests pass.

### Annulled branch-likely slots also consume reference Count

Task-load execution initially measured 439 executed instructions against 890
reference ticks including the six-tick measurement boundary. Three annulled
branch-likely slots account for the six-tick residual, but that explanation
was tested independently before accepting it.

The original `branch` micro-ROM exercises BEQL, BNEL, BLEZL, BGTZL, BLTZL,
BGEZL, plus ordinary BEQ as a control, both taken and untaken, with 16/128
iterations. Skipped slots have zero register effects, as required. Repeated
`branch-clock-mupen-20260926a` / `...b` give 162/1282 ticks for all cases:
this reference charges the annulled slot's two ticks despite not executing it.
The 28-case trace SHA-256 is
`491f08a49ee958fe26aa0e0e3729de7655527f2e0046728d669d70e434360963`.
Private ROM SHA-256:
`62806dfec58df90bff34e2dc8dc04c23fd024ec979ae38a62d56b5199f6d49d0`.

The task-load test requires this independent branch evidence and now agrees
exactly: `(439 executed + 3 annulled) * 2 + 6 = 890`. Start remains
`24 * 2 + 6 = 54`. This is a named-reference accounting rule, not a fitted
task cost or hardware claim. FP/link-likely variants have not been separately
qualified. The game instruction observer still counts entered sites only;
it does not yet charge annulled slots or drive the clock. Future integration
must retain that distinction and per-context branch state.

## Original OS context-switch execution (2026-09-26)

The offline generator previously preserved host call continuations without
writing architectural `$ra` for JAL/JALR. That cannot support the original
OS saving `$ra` as a suspended context's EPC. A ROM-free control fails both
direct and indirect link observations. Patch 0016 adds the explicit,
default-off `emit_guest_link_registers` C-backend profile. Eight cases cover
direct/indirect calls, a delay slot overwriting the indirect target, taken
and untaken ordinary/likely conditional links, and a tail preserving its
incoming link. Fixed-address and relocated tests pass under ASan/UBSan.
The existing producer regression target passes; a clean pinned checkout
successfully applies all sixteen checksum-verified patches. These facts do
not refresh Phase 4 signing or producer acceptance.

Generator SHA-256:
`604addf45ee357e2b347774102972a28047e88c11415712696bc9e44e4f4616a`.
Patch-set SHA-256:
`d88319dce419532a96733c9b4a3103337a10fadd3449e9b9f4ca279979a51cd4`.
Private root `execution-root-20260926h` enables the profile and retains
379025 instruction sites. No Count or device deadlines are enabled by it.

`test_generated_os_threads.py` executes fourteen original OS bodies and the
same independently authored two-thread assembly used by the micro-ROM.
The original dispatcher selects threads and saves/restores their contexts;
the project's baton executor only transports stackful continuations. The
driver validates resumed EPCs against their parked call continuations.
All eight queue results, four payloads, entry Status values, and five RCP
mask observations agree with the oracle. The first timing trial retained
a four-tick excess only on intervals containing two ERETs.

An independent micro-ROM isolates ERET against an otherwise identical NOP
control, over 16/128 iterations. Repeated `eret-clock-mupen-20260926a/b`
observe control 290/2306 and ERET 258/2050: this reference adds no Count
increment for ERET. No OS body, game state, or game timing was used to
derive the rule. It is not a hardware latency assertion. Trace SHA-256:
`151f149378c145f233247ae522fad27d2b2461a3cb341df12d0272a5303c702c`.
Private ROM SHA-256:
`168f96edc7162b9b21e3f70d8ebbc995ee80b14dd8ea1a60cb94148e6db01b1c`.

With this independently qualified rule, `generated-os-threads-20260926c`
matches all eight oracle timing intervals exactly (including suspended
wall time), under ASan/UBSan. Initialization is explicitly untimed fixture
setup; this does not qualify osInitialize, asynchronous interrupt entry,
FP context switching, or full game clock integration. The game frontier
is still 1291 until a strict replay comparison demonstrates otherwise.

The next generator profile stores HI/LO and FP condition/control in the CPU
context. A ROM-free control passes only 4/30 checks; the explicit profile
passes 30/30 under ASan/UBSan, including all eight multiply/divide variants
and cross-function condition/control observations. Arithmetic FP exception
synthesis is not claimed. Patch 0017 requires a matched, rebuilt context ABI.
`generated-os-threads-20260926d` repeats the eight exact queue/thread timing
matches with the new ABI. It also validates the ROM-initialized global mask
at `0x800a9a6c`; an earlier fixture setup wrote an unused address and did not
establish that initialized data itself.

Game trials `execution-guest-links-native-20260926a` (root h) and
`execution-guest-cpu-native-20260926a` (root i) retain the same update trace
SHA-256 `edd1bcca844f8fd2708650d922f829beab673ceffef9911a5275b0edbe0cca8e`.
Both finish 3000 retraces, 1413 updates, 1423 polls, with whole-state hash
`cc7a9f59a6ff903b09a7e0ecc7961381d1a5ffcbd304dfc4b3999ad12d611d2e`.
Strict comparisons still first diverge at 1292. Executable hashes:
root h `de422b749f576e63d32b983be9259a966e1adb15645fad0ab221be00077281ef`;
root i `f78d403d501e738d65536a220cf44ba45a886d92d62f8c25edc0920a709565b5`.

An independent SP interrupt micro-ROM now wakes a higher-priority worker
while main holds live HI/LO, FP registers and the FP condition bit. The first
attempt observed deferred delivery until a branch; a revised probe explicitly
crosses a branch before measuring resumed state. Reference run
`os-interrupt-mupen-20260926c` preserves all state across eight interrupts:
1750 ticks for the first interval (including worker lazy-FPU activation),
then 1366 ticks each. These are observations, not fitted costs to install.
Initial software-interrupt and straight-line SP attempts are retained as
failed qualification artifacts, not accepted results.

The native interrupt test exposed an original OS helper returning via a
saved register rather than `$ra`. The old producer attempts a function lookup
at that return continuation. The ROM-free reproducer aborts in the control;
Patch 0018's guarded incoming-link comparison passes ten fixed/relocated
control-flow cases. Its versioned sidecar explicitly represents the new
bounded union; the old schema cannot silently acquire that permission.
The full native interrupt/timing comparison now matches all eight intervals.

### Qualified interrupt entry and stricter sanitizer gate

Repeated reference `os-interrupt-mupen-20260926c/d` has trace SHA-256
`7e2b266f0514aca2b1b37b45207775f47afb33505630cdf23b796d25a1396544`.
The native test originally entered the handler directly, omitting the four
original instructions installed at the exception vector. Independent vector
capture verifies those instructions match the private ROM preamble. Executing
that original preamble, rather than adding a fitted eight-tick constant, gives
1750/1366 ticks exactly, with eight SP events and two lazy-COP1 exceptions.
Artifacts `generated-os-interrupts-20260926b/c` contain the passing comparisons.
The fixture verifies the vector bytes; its preamble hooks retain the original
source addresses, not a general relocated exception-vector PC model.

**Correction to earlier sanitizer wording:** the earlier link/OS queue tests
used recovering UBSan, so successful exit did not imply a clean sanitizer run.
Their behavioral/timing observations remain valid, but stderr contained signed
LUI-shift violations. The three relevant runners now use
`-fno-sanitize-recover=all`. Patch 0019 forms the LUI bit pattern using an
unsigned 32-bit shift before sign extension. It does not suppress diagnostics.
Clean fatal-sanitizer reruns: fixed/relocated return tests `...20260926c`,
CPU-state `...20260926d`, queue/thread `generated-os-threads-20260926e`, and
the interrupt runs above. Original failed artifacts are retained.

Nineteen-patch clean application succeeds. Patch-set SHA-256:
`9c6f1065f6ea326e9f0eb2bfb76b90a6358f5bbbba45439ab36b1ebf7d8898ec`.
Producer SHA-256:
`c0210858e29b862c3a37ff7045d6de7d73ee942a0e35b4245d09a2e301665e56`.
Private root `execution-root-20260926k` uses that producer. Source preparation
explicitly admits only sidecar schema 2 in addition to schema 1; other semantic
products retain their schema-1 contract. Normalizer decision/member/guard checks
remain required. This is not a refresh of signed Phase 4 acceptance.

`GuestThreadTransport` now extracts the tested stack transport for runtime
integration. It does not select priorities or manufacture thread contexts:
original guest code selects the next OSThread and restores its CPU state.
Continuation PCs must match an observed parked call/interrupt continuation.
The extracted implementation repeats both queue and interrupt timing matches.
The CPU bridge now has an explicit exception-return operation; absent/rejecting
owners retain the fatal trap. Full game integration remains pending, and the
strict matching game prefix remains 1291 until a replay proves otherwise.

### Original initialization closure and diagnostic runtime integration

`osInitialize` had another unresolved local helper at `0x80097788`. Its 120
bytes are a straight-line integer routine with one terminal return, an
original direct caller and an existing next-function boundary. Recovery adds
only symbol metadata (`_ObservedPiHandleInitialize`, a descriptive local name),
and verifies all allocated ELF bytes against the unchanged original. Private
`pi-init-helper-recovery-20260926a` yields ELF SHA-256
`8ad76f859b117e215de989c300976bcefc0f7180fc9e386424fd5aced2445ef4`.

The next explicit inventory revision has 2907 required bodies, 3731 executable
symbols, eight manual sizes, 3622 indirect sites (3417 returns, 205 decisions),
and unchanged 14046 direct sites (13859 generated targets, 187 unresolved).
Aliases (824), support thunks (30), and relocation counts remain unchanged.
The transform independently reproduces these counts. Root
`execution-root-20260926l` has 379055 instrumented instruction sites. Older
roots no longer pass the current normalizer freshness gate; do not re-label
them as freshly accepted products. Signed acceptance remains unrefreshed.

`os-initialization-mupen-20260926b/initialization.tsv` captures original
initialization entry/return CP0, FCR31 and device registers. SHA-256:
`9da1dad637a69c9a4eb20124a35b0a0e8f5a95f374bc78bd7c1d342a7346c3d6`.
Native `generated-os-initialization-20260926b/c` runs the entire 38-body original
initialization/interrupt closure, not the earlier fixture setup. All captured
register transitions and the 1516-tick initialization interval match; the
eight subsequent interrupt timings/state comparisons still match. Absolute
Count origins are deliberately not copied or compared. Fatal ASan/UBSan is
clean. This qualifies that bounded cold-boot profile, not arbitrary PIF or
OS initialization variants.

The opt-in native guest-leaf path now calls original `osInitialize`, with
observed initial Status `0x34000000`, its TLB/cache operations and a guarded
PIF boot-acknowledgement register. PIF command 8 clears; other control commands
and addresses are rejected. The diagnostic boot Cause read is supported only
before OS initialization/scheduling, not as a fake live interrupt register.
This integration still retains the legacy cooperative Count/device clock.
The root-l game trial `execution-os-initialize-native-20260926c` completes
3000 retraces, 1417 updates and 1427 polls without a trap. Same-index comparison
still first differs at update 1292 (17 actor differences); initialization alone
does not fix the pacing frontier. Executable SHA-256:
`ab130c71bd347799bcc815a4e5a6a52919580552847a9bb7334696dfad33f2a5`.
Whole-state hash: `43a1932fdb8a40515e10c7105e2024c8d374e77c48d4fe4947903055d4220f3c`.
The failed `...b` trial exposed an intercepted register helper; the original
initialization closure now dispatches those helpers to generated code. The
earlier `...a` directory accidentally ran the preceding root-k executable while
the new build was still running and is explicitly **not initialization evidence**.

The preceding root-k control replay `execution-guest-returns-native-20260926a`
still matched only through update 1291, with unchanged update/whole-state
hashes, 3000 retraces, 1413 updates and 1423 polls. Executable SHA-256:
`fb3aaf3f13af7d7f77e3e08c126e754c7505efeea572a36284d4f9592c52e853`.

### Independent PI/SI deadline observations

The original DMA micro-ROM sweeps three transfer directions, four PI lengths
and eight launch-to-poll phases. SI is always a fixed 64-byte transaction;
the length column there is only a repeated case label. PI destination data
is independently checked against the cartridge header. Repeated
`dma-clock-mupen-20260926a/b` have identical 96-case trace SHA-256
`02b1e3ef0b0095ee777b7e3a9fe65e7d1b86120b4ba2c92dc08315a0d9939c77`.
ROM SHA-256:
`3501af14b69c04287241d2c34a237b39a331e65c374c3587f0f1ce6636c56a61`.

Intersecting phased polling bounds after store retirement uniquely resolves
2304 ticks for the tested no-command SI write/read transactions, and 128/512
ticks for 1024/4096-byte PI reads, at two-tick resolution. The 16/64-byte PI
reads finish before the first poll: their latency is **not** uniquely
qualified. No general PI formula, command-bearing SI equivalence, device
deadline integration or hardware timing claim follows from this experiment.

### Original VI worker, IPL phase and executable idle loops (September 26)

The next private recovery identifies the thread entry at `0x80098bb8` from the
original `osCreateThread` argument construction, validates its complete loop
CFG and explicitly unreachable suffix, and adds only its 408-byte symbol.
Allocated ELF bytes are unchanged. The resulting inventories are 2908 required,
3732 executable, 9 manual helpers, 14053 direct sites (13964 linked, 89 tails),
13866 generated targets and 187 unresolved targets. Alias/indirect/relocation
denominators are unchanged. Roots m/n use this verified transform. This is
private compiler metadata recovery, not replacement runtime source.

`generated-os-vi-manager-20260926b` executes the 53-body original initialization,
VI worker and scheduling closure. Its 24 messages, 23 consecutive 789000-tick
intervals, and 492-tick worker-to-receive intervals match the oracle. Fatal
ASan/UBSan is clean. Startup origins differ and are retained; only steady-state
behavior is qualified by that fixture.

Independent `vi-phase-mupen-20260926a/b` tests four modes (0, 525, 262, 625),
16 edges and 128 CPU scanline reads. Repeated trace SHA-256 is
`3bf63affefd4f77acb09462603b6bf1fd14aabbd094e83d6010c41fb31ab7c92`.
It supports an initial 500000-tick period with phase 5000, period changes
latched at the following event, and progressive even-field scanlines at 1500
ticks/line. Interlaced behavior is not qualified.

Read-only original-ROM `boot-state-mupen-20260926c/d` captures platform registers,
not player/actor/RNG/save state. Identical trace SHA-256:
`083d08439c4d831c6d8afa541e8c6a0fbca8e0bfc31c79fef050e0ff3042f50b`.
IPL entry Count 14421016 plus 217339 actually interpreted reset instructions
at two ticks gives handoff Count 14855694. This epoch is tied to the exact US
ROM and corrected-Mupen profile, not arbitrary micro-ROMs or physical hardware.
The earlier `...a` timed out before IPL; `...b` mislabeled `0x80000450` as the
handoff and is not reset-handoff evidence. `...e` adds an EPC sidecar without
altering the register capture.

Direct PIF command 8 has a delayed SI interrupt, not merely a cleared control
byte: repeated `dma-pif-mupen-20260926a/b` resolves 2304 ticks at the tested
resolution. Trace SHA-256:
`61d9d9933a20c6865a0871f8ed9b1ac6f00026b2d4e25eac53438baab99afd7a`.
This does not yet qualify all command-bearing controller transactions.

Root n uses the 20-patch producer and executable guest idle loops (379157
instruction hooks). `generated-idle-loops-20260926a` passes eight bounded real
loop executions with fatal ASan/UBSan. Root-m cooperative control
`execution-vi-metadata-native-20260926a` retains the root-l whole-state hash
and strict matching prefix through 1291; first divergence is still 1292.

### Opt-in original-OS native integration: not accepted

`JFG_PHASE9_GUEST_OS_PROBE=1` is separate from the cooperative control. It runs
original OS bodies and lets original scheduling code choose/save/restore
threads; host transport only preserves continuations. It uses real instruction
Count and owned device deadlines, and writes `guest-os-clock.tsv`. Incomplete
devices and an instruction budget fail closed. Its legacy aggregate runtime
hash is not a complete CPU/device snapshot and must not be called accepted.

The first root-m trial `execution-original-os-native-20260926a` reached the PI
wait but exposed the compiler's old permanent idle park. Root-n `...b` executes
idle instructions; its first VI and PIF/SI interrupts match exact reference
Count and EPC after accounting for the original four-instruction vector
preamble. It still exhausted its bounded budget because PI had no owner.

The new independent PI sweeps cover 19 lengths and eight phases. The original
branch-target sweep `pi-timing-mupen-20260926a` trace SHA-256 is
`953ee0bdbaf4289aca89c756b16828bd6f6e74e685cc77582cbcfe819388f6e6`.
Lengths 40 through 262144 support integer length/8 deadlines at two-tick
resolution; shorter deadlines remain observationally bounded, not uniquely
resolved. Direct fallthrough polling confirms device event visibility is
committed at branch boundaries: advancing the deadline at every instruction
would expose completion too early. The same probes observe immediate ROM data
visibility, retained PI addresses/length, busy status 3 and completion status 0.
`pi-alignment-mupen-20260926a` additionally qualifies word-aligned source and
destination addresses; `pi-word-mupen-20260926a` covers lengths 4 modulo 8 and
supports integer truncation of length/8, not rounding the fraction upward.
These are corrected-Mupen observations, not hardware bus timings.

The independently authored `ReferencePiDma` owns these transactions, busy and
interrupt acknowledgement, with bounded buffers and rejected unqualified
directions/ranges. ROM-free Windows tests and fatal Linux ASan/UBSan tests
cover the implementation. Native `...c/d` executes multiple original PI
completions, then stops explicitly at unqualified alignment/length cases;
those rejections prompted the separate probes above, not game-specific fixes.

A pending-interrupt enable fixture `os-mask-enable-mupen-20260926a` proves that
MTC0 Status can deliver an already pending interrupt at the immediately
following instruction, without waiting for a branch. Native
`generated-os-mask-enable-20260926b` matches all eight measured intervals
(1758, then seven times 1374), live register state, and ten exact exception
cause/EPC pairs; fatal ASan/UBSan is clean. Its origin-free fixture excludes
one explicitly retained pre-fixture IPL interrupt from the reference and makes
no full-startup parity claim. The earlier native `...a` passed execution but
its postprocessor rejected that extra startup row; it is not a completed gate.

The strict game frontier is **still 1291**, not improved by these bounded
qualifications alone. PI/SI/Flash/SP/DP/AI ownership, full original-OS runtime
integration and same-index replay remain required. No old signed acceptance
or product projection has been refreshed on the strength of this diagnostic.

### Device integration follow-up (2026-09-26)

Root o adds the privately recovered controller read-packet helper
`0x80097e7c..0x80097f70` (244 bytes). Recovery verifies the original leaf-loop
control flow and unchanged allocated ELF bytes; the independently rerun
transform has 3733 executable symbols, ten manual sizes and 13867 generated
targets. Root o contains 379218 instruction hooks. It is not a signing refresh.

The original-OS path now executes Compare timer deadlines, SI controller
initialization/read transactions and the CIC challenge. SI has 2304-Count
completion events; copies are immediate. Status/button responses are filled
on PIF reads, whereas disconnected-channel flags are already visible after
command writes. `dma-cic-mupen-20260926a` contains 288 SI observations, all
compared byte-for-byte against the independent owner under fatal ASan/UBSan.
It uses `cpu-dma-cic-20260926b`, not the earlier misassembled build a.
The existing independently authored CIC backend is reused, not ROM C source.

`pi-bytes-mupen-20260926b` adds 152 cases covering lengths 1..17, 754 and
65535 at eight phases. Every transferred byte matches ROM, and all sixteen
following sentinel bytes remain unchanged. Byte-observation SHA-256:
`4f20df126adf6e4fdadde9e46214ac7c97d34841b6bb9e83b1200abf4c2d5560`.
Timing trace SHA-256:
`c9ad144d9b02a7edbcfff319f5b1c28aa385737684184b4feb48426d9c11490d`.
Build a's observations incorrectly read the physical cartridge address as a
virtual System Bus address and are not copy-validation evidence. Build b uses
the uncached virtual alias. PI now supports arbitrary bounded byte lengths
with qualified word-aligned endpoints, retaining integer length/8 deadlines.

`rsp-device-events-mupen-20260926b/rsp-boundaries.tsv` proves a significant
ordering detail: SP and DP share the graphics deadline, but the reference
commits only one event at each CPU branch boundary. SP is visible first and
DP at the next boundary. A fitted extra DP delay would be incorrect.
Trace SHA-256:
`2694f93c1c1aeaf46a1c659e903de7d96b8d7d9dec826252c01c452097a55dab`.
`reference_event_commit_tests` simulates all recorded boundaries across sixteen
jobs and matches every MI/SP register observation (24 committed completions).
Windows and fatal ASan/UBSan pass. Unqualified equal-deadline device pairs
are rejected, not assigned guessed priorities.

The opt-in native integration now connects that arbiter to VI, PI, SI,
Compare, SP and DP. Original OS routines continue to own queue/thread state;
host VI/queue observers are read-only. SP/DP integration is not yet accepted
by full-game comparison. Native trial k passed CIC but rejected a 754-byte
PI read; l/m pass that read and stop at an SI transaction under investigation.
These are diagnostic stops, not improvements to the strict 1291 frontier.

Trial n isolates that SI rejection to a valid write/read pair only 264 Count
ticks apart, while the write interrupt is pending. Independent
`si-overlap-mupen-20260926a` tests all four read/write direction pairs and
eight gaps: both copies occur, the first pending SI deadline is retained, and
there is no second interrupt after acknowledging it. Trace SHA-256:
`cfcc34a72b11fe964aa5d2b2b655e660772d1b0db3bda02edac602e08314c33f`.
The owner now coalesces overlapping completions accordingly. Its fatal
ASan/UBSan tests retain all 288 earlier payload comparisons and add 32 overlap
cases. This fixes the device model; it does not bypass an OS wait or alter input.

### FlashRAM, halfword PI and AI follow-up

The isolated FlashRAM command/DMA experiment writes only its disposable
emulator save. `flash-mupen-20260926e` validates 88 CPU-observed command/status
pairs and 40 DMA payload/timing cases, including modifying the source after
DMA but before execute. The reference retains the source address and reads
its bytes on execute; snapshotting at DMA would be wrong. Flash DMA reports
busy=1 and completes 4096 Count ticks after the store-retirement epoch,
unlike ROM PI busy=3 and length/8. IDs are `11118001,00c20000` in this profile.
`ReferenceFlashBus` uses the existing independently authored FlashRamStore
for data and persistence. Windows and fatal ASan/UBSan tests match all rows.
Trace SHA-256: `cf07f7a48f0b19ccad993c3bfcc5e33257273ab98ef302e4d1a7ac34e5b8d353`.
Command SHA-256: `382cf58140d3b325b2e67420126244fcc49983a0556a110ccebcec43d5845a9f`.
Store epochs: `25a38ef67d89808296a0a9054ec8b6a57be9538a20de2a374067d339d622b801`.
Earlier flash a used debugger bus reads rather than CPU reads for status;
b/c lacked the source-mutation test; d redundantly logged loop iterations
as post-store epochs. They are retained, but e is the complete comparison.

Native p reaches 64 consumed VI messages and executes graphics/audio tasks.
Its first thirteen flushed completed-update records match the strict oracle.
The child exits zero, but the legacy parent rejects its empty HLE thread
summary. The new profile therefore has its own explicit diagnostic report
`jfg-phase9-original-os-probe`, with `acceptance:false` and
`runtime_snapshot_complete:false`; no HLE thread evidence is fabricated.
Native q reaches at least 150 retraces, then rejects a halfword-aligned ROM
source. `pi-half-mupen-20260926a` independently validates all halfword endpoint
alignments with byte lengths and unchanged sentinels. PI now permits those
endpoints; odd-byte addresses remain unqualified. Timing trace SHA-256:
`d03dc5117522718bbb04309b203d0fbf48eec8faff71162721d8576462983c5b`.

AI probes `ai-mupen-20260926a` and `ai-fifo-mupen-20260926a` cover three DAC
rates, three lengths, eight phases, and both one/two queued buffers. Fatal
ASan/UBSan matches all 144 rows, including halfway remaining-length reads,
busy/full transitions, sticky IRQ acknowledgement, and both completion windows.
The qualified NTSC profile uses integer frequency `48681812/(DAC+1)` and
duration `length*789000*60/(4*frequency)` in Count ticks; the second buffer is
anchored to the first deadline, not its later interrupt-handler execution.
This is reference behavior, not a physical-hardware frequency assertion.
Trace SHA-256 values:
`d09ec603eca1507879f730deb6b413e62954a02b9eda76970ac0b97a362e8022`,
`114c662309117f1da21faba5322daee9f231ef1c1414627c6d1ac0f0559401b7`.
Native AI integration is still awaiting the longer replay result.

Trial r caught an overly narrow AI acknowledgement check: original OS writes
one, whereas the first microtest wrote zero. `ai-fifo-mupen-20260926b` tests
eight acknowledgement data values (including the high bits and all ones) and
qualifies that the write data is ignored. All 72 FIFO cases again match the
independent owner under Windows and fatal ASan/UBSan. Trace SHA-256:
`a25d0381cc0475dc23518295cdbf3540de8347864ea14287455cf0fc56ef45e1`.

Trial s matches all 687 completed updates before stopping at a zero write to
the FlashRAM status aperture. `flash-mupen-20260926f` tests that write after
all 88 command observations: it has no observable effect in this reference.
The owner now supports that qualified zero write; the expanded payload,
command, epoch and clear checks pass Windows and fatal ASan/UBSan.
Clear trace SHA-256:
`cdaf1dce97c86f0abbb72a61d3a68db8a9a0d8fdfbd2f783936aecbde3a2fb3f`.

Trials t/u then complete 3000 retraces and match the entire available 1300-update
oracle prefix. Their full native update/retrace files are byte-identical.
See the linked frontier result for exact VI-boundary observations and pins.

The latest cooperative control `execution-device-control-native-20260926a`
retains strict prefix 1291, first divergence 1292, and whole-state hash
`43a1932fdb8a40515e10c7105e2024c8d374e77c48d4fe4947903055d4220f3c`.
That is a regression control, not a claim that the requested frontier passed.
