# Execution-driven clock prototype (2026-09-24)

Current status (2026-09-26): integrated as an opt-in original-OS execution
diagnostic. It now matches the strict oracle prefix through **update 1300**
in two repeated runs. See [the result and limits](phase9-execution-frontier-1300.md).
The default cooperative runtime and signed acceptance remain unchanged.
The prototype descriptions below preserve the implementation history.

## Implemented

`include/jfg/boot/execution_clock.hpp` provides:

- Monotonic 64-bit virtual time, explicit absolute device deadlines,
  one outstanding event per source, cancellation, and stable source-id
  ordering for simultaneous deadlines.
- Periodic events anchored to the previous deadline, not time of service.
  Missed periods remain observable. Overflow is rejected or explicitly
  reported; wrapping is never silent.
- Idle advance directly to the next event. The caller must establish that
  no guest thread is runnable; the clock does not inspect the scheduler.
- A separate interrupt latch: masking/global-disable/exception-level/unsafe
  boundaries defer delivery without stopping time or losing pending sources.
  Acknowledgement clears only the selected source bits.
- Instruction retirement that charges already executed work. At each
  instrumented boundary: retire the previous operation, drain events,
  preempt if permitted, then start the next operation after resumption.
  Retirement state belongs to each guest context, not a shared in-flight
  instruction across threads. Device callbacks and mask translation remain
  caller responsibilities.

The clock accepts supplied costs; it does not pretend to derive hardware
costs from the number of host instructions or function calls. Atomic work
may cross a deadline; returned events retain their original timestamps.
It is not yet a general instruction/cache/bus/device timing model.

## Actual generated-code proof

`tests/fixtures/execution_clock.S` is original ROM-free MIPS assembly with
a loop, ordinary branch delay slots, an annulled/taken branch-likely slot,
and a nested call/return. `scripts/test_generated_execution_clock.py`:

1. Assembles and links the fixture with the installed MIPS tools.
2. Uses N64Recomp's instruction hooks for all 17 instruction sites; it does
   not insert accounting by rewriting generated C comments.
3. Compiles the real generated output and links it to this project's clock
   and stackful scheduler.
4. Runs 90 cases, checking exact executed instruction totals, register
   results, mid-function preemption without OS calls, correct resumption,
   delay-slot-safe delivery, and mask deferral.

This fixture deliberately uses **one synthetic tick per instruction**.
Its success is mechanism validation, not N64 timing qualification. The
prototype treats branch/delay-slot pairs as non-preemptible; it does not
claim exact architectural exception EPC/BD handling inside a delay slot.
General game instrumentation, overlays, MMIO boundaries, guest mask
translation, and guest OS/HLE timing are not covered by this small fixture.

Reproduce from WSL, with a new output directory each time:

```sh
python3 scripts/test_generated_execution_clock.py \
  tools/private/execution-clock-check-NEW \
  --recompiler tools/build/n64recomp-ffb39cda/N64Recomp \
  --include tools/upstream/N64Recomp/include --sanitize
```

The tool never edits signed/generated game roots. It emits a private
non-acceptance manifest pinning the recompiler. Recompiler SHA-256:
`34958d6ae8c047adb772090c75fdcc051036646a1db58595694f814c3a4a09b6`.

## Timing qualification experiment

The private CPU micro-ROM measures Count around 100- and 1000-iteration
loops. Each loop iteration has four instructions. Three workloads replace
the first instruction with an integer add, a repeated cached load, or a
repeated uncached load. Interrupts are disabled. Its IPL is taken only
from the user's pinned local ROM; generated ROM bytes remain private.

| Workload | Mupen delta for 3600 extra instructions | Ares delta |
| --- | ---: | ---: |
| Integer add loop | 7200 | 1728 |
| Cached-load loop | 7200 | 2249 |
| Uncached-load loop | 7200 | 2226 |

Mupen produced 802/8002 ticks for every 100/1000 pair, identical on two
fresh runs. Ares produced 298/2026, 277/2526, and 301/2527 respectively.
These are aggregate observations, including core timing behavior and
measurement overhead; they are not measured individual instruction
latencies. Neither emulator result is asserted to be hardware truth.

This supports two ticks per instruction for **these Mupen workloads**. It
does not qualify all instructions, cache states, interrupt overhead, or HLE
calls, and must not become an unlabeled default hardware timing model.
The micro-ROM runner's default rounding probe remains backward-compatible;
`--probe clock` selects the new independent measurement and strict parser.

Artifacts under `tools/private`:

- `execution-clock-micro-final-20260924a`: final generated-code ASan/UBSan run.
- `cpu-clock-execution-20260924a`: private assembled payload and ROM.
- `execution-clock-mupen-20260924a` and `...b`: repeated corrected-Mupen results.
- `execution-clock-ares-20260924a`: alternate-core observations.

Probe ROM SHA-256:
`cf7e4e4b6d4926a350d8442bee732cfd15c1f496104060fe5f13fccf0cb04c45`.

## Validation and remaining gate

- Windows Release execution-clock, timer and scheduler CTests pass.
- Generated fixture passes 90 cases with GCC ASan and UBSan.
- 32 Python clock/rounding/replay contract tests pass.

Do not run the game under a nominally instruction-accounted profile while
its HLE calls still consume arbitrary or zero time. The unresolved gate is
coverage of guest OS execution and independently timed SI/PI/SP/DP/AI work,
plus qualification of a named reference CPU timing profile on held-out
instruction workloads. Existing VI service also combines host presentation
and device completion; it must be separated before becoming a generic event
dispatcher. Those are still required implementation tasks, not completed
features of this header.

The first game trial must use a separately instrumented private root and a
named opt-in profile, retain the old path as a control, preserve the matching
prefix, and extend it without route-specific constants or copied game state.
No claim of a game fix or whole-scope completion follows from these tests.

Follow-up: [OS queue timing qualification](phase9-os-clock-qualification.md)
now has paired per-thread reference measurements and repeated independent
original-OS microtests for nonblocking paths and real guest-thread handoffs.
The uninterrupted lower-priority wakeup path agrees with gameplay timing;
blocked durations remain explicitly separated from CPU-cost qualification.
Wakeup/blocking timing integration and other OS/device timing are still open.

September 26 update: an opt-in original-OS native diagnostic now executes real
initialization, scheduling, exception handlers, cartridge DMA, timer waits and
controller initialization. Independently probed PI/SI/Compare device models
replace the corresponding unowned registers in that diagnostic. This is not
the default cooperative runtime or an accepted snapshot/clock profile; device
coverage and renderer integration remain incomplete. The control replay still
matches strictly through update 1291 and first differs at 1292. Current detail
and limitations are in the linked OS-clock qualification log.
