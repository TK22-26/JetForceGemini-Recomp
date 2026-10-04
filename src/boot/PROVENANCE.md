# Boot runtime authorship provenance (Phase 6)

Per the binding independent-authorship rules in
`docs/planning/phase6-acceptance.md`, every runtime bridge module carries a
provenance record attesting independent authorship. This file is that record
for the Phase 6 boot runtime.

## Attestation

- Owner role: Runtime
- Author: this project (independently authored)
- No source from N64ModernRuntime/librecomp, RecompFrontend, or any other
  third-party runtime was copied, transcribed, machine-translated, or
  minimally adapted into these modules.
- The implementation targets the **public libultra / N64 SDK contract**
  (documented function semantics and ABI). Implementing that contract is
  independent authorship; the contract itself is the platform specification,
  not any project's expression of it.
- Validation is by **black-box behavioral comparison** only. Where an oracle
  is used, observable behavior (inputs, outputs, memory/register state, event
  order) is compared; internal structure is never reproduced.

## Modules covered

| Module | Contract implemented | Oracle used for validation |
|---|---|---|
| `include/jfg/boot/runtime.hpp`, `src/boot/runtime.cpp` | osCreateThread/osStartThread, osCreateMesgQueue/osSendMesg/osJamMesg/osRecvMesg, osSetEventMesg (VI), osSetTimer, osPiStartDma, osViSwapBuffer, osSpTaskStartGo | representative-boot self-consistency + pinned checkpoint; emulator oracle for the native lane (research-only, black-box) |
| `include/jfg/boot/representative.hpp` | a synthetic boot exercising the above; ROM-free | n/a (test fixture) |
| `include/jfg/boot/driver.hpp` | reset-to-entry sequencing, invalid-ROM safety | n/a |
| `include/jfg/boot/executor.hpp`, `src/boot/executor.cpp` | bounded stackful transfer between generated guest functions and scheduler/HLE boundaries | ROM-free executor tests plus native state/journal repetition |
| `include/jfg/boot/thread_scheduler.hpp`, `src/boot/thread_scheduler.cpp` | priority-ordered guest thread lifecycle, queue blocking/wakeup, pause, and deterministic virtual VI events | ROM-free scheduler tests plus three original-entry processes |
| `include/jfg/boot/hle.hpp`, `src/boot/hle.cpp` | reached libultra thread/queue/event/PI DMA/cache/interrupt/controller ABI | ROM-free ABI/error-path tests and guarded native execution |
| `include/jfg/boot/reset_handoff.hpp`, `src/boot/reset_handoff.cpp` | checked reset subset and delay-slot transfer from `0x80000400` | synthetic reset/fault/budget tests and original-entry execution |
| `src/boot/native_boot.cpp` | validated image load, guest aliases, exact-ROM overlay data, fail-closed generated dispatch, guarded MMIO register model, VI-manager bridge, watchdog, state hash, and ordered journal | repeated native run, AddressSanitizer run, invalid-ROM run, and BizHawk queue-ring observation |
| `src/runtime/recomp_support/minimal_runtime.cpp` | generated-code register helpers and scheduler handoff for generated pause-self boundaries | generated link/object audits and original-entry execution |

## Modeling notes (disclosed, not hidden)

- Queue waiter selection and full-queue blocking send/jam were independently
  implemented from the SDK's documented messaging contract: one highest-
  priority eligible waiter, FIFO ties, separate empty/full conditions, and
  resumption when space/message becomes available. No oracle/decomp scheduler
  implementation was copied. Tests cover stack-preserved payload and ordering;
  two native replays preserve the prior trace. This is a semantics repair,
  not qualification of OS execution costs or whole-runtime cycle accuracy.
  See `docs/planning/phase9-os-clock-qualification.md` for evidence and limits.

- `include/jfg/boot/execution_clock.hpp` is an independently authored
  deadline clock, interrupt latch and instruction-retirement mechanism.
  No emulator or third-party runtime implementation was copied. Its
  instruction-cost and device-period inputs are explicit model parameters,
  not claimed hardware timings. ROM-free tests use original MIPS assembly
  recompiled with N64Recomp and the project's own scheduler. This prototype
  is not yet integrated into the game runner or a parity-accepted profile.
  See `docs/planning/phase9-execution-clock-implementation.md`.

- `include/jfg/boot/si_deadline.hpp` is an independently authored single-flight
  deadline primitive. The opt-in `JFG_PHASE9_SI_COUNT_PROBE` integration uses
  an observed 2,568-tick oracle DMA-return-to-ack interval solely as a causal
  experiment. It is not calibrated N64 hardware timing and is disabled by
  default. No emulator implementation was copied. Payload processing remains
  at the existing HLE transfer boundary; this experiment changes completion
  scheduling, not the whole SI/PIF implementation. Pending completion, its
  queue/message, deadline, and timing profile must be included in any future
  runtime snapshot. See `docs/planning/phase9-si-completion-timing.md`.

- `include/jfg/boot/timers.hpp` is an independently authored native timer
  service using the public SDK `osSetTimer`/`osStopTimer` contract:
  https://ultra64.ca/files/documentation/online-manuals/man-v5-1/n64man/os/osSetTimer.htm.
  It implements countdown/interval expiry, nonblocking queue notification,
  cancellation and monotonic 64-bit Count deadlines. ROM-free tests cover
  queue loss and scheduler wakeup in both guest memory layouts. The runtime
  services deadlines at dispatch boundaries and between virtual VI events;
  these are deterministic model timings, not cycle-accurate hardware claims.
  The timer's public interval/value/queue/message storage is initialized in
  guest memory, but OS-private linked-list bookkeeping is host-owned. Native
  snapshot support must serialize this list and its ordering counter; an
  RDRAM-only snapshot cannot restore pending timers. Exact internal libultra
  memory layout parity and periodic-interrupt oracle qualification remain
  separate acceptance work.

- The thread model is **cooperative and step-based**, not host-preemptive.
  This is the deterministic boot profile the acceptance contract requires; it
  is an intentional, original design, not a port of any runtime's scheduler.
- Message/queue/event/timer/DMA/VI semantics follow the libultra contract's
  observable behavior. Latencies (VI period, DMA latency) are deterministic
  virtual-time constants chosen by this project, not values copied from
  hardware timing tables or another implementation.
- Native VI messages originate from deterministic virtual-frame events. The
  internal VI manager consumes the event and sends its configured message;
  the title-side receive counts a retrace only after consuming that message.
- Native MMIO pages are guarded and every reached aligned register access is
  recorded against an explicit public-register whitelist. Unknown offsets
  fail the M2 gate rather than inheriting an uninstrumented memory default.

- The opt-in framebuffer CPU-writeback bridge is independently authored
  client code using RT64's public framebuffer timestamps/ranges and existing
  render-to-RAM output. It copies only task-owned ranges after validating
  against the submitted snapshot, rejecting CPU conflicts atomically. No
  emulator implementation was copied. This is memory-result integration,
  not RSP/DP timing qualification. See
  `docs/planning/phase9-renderer-cpu-writeback.md` for proof and limitations.

- `include/jfg/boot/tlb.hpp` is independently authored from NEC's VR4300
  manual U10504EJ7V0UM00, chapters 5 and 16:
  https://hack64.net/docs/VR43XX.pdf. It is a 32-bit TLB storage/probe
  mechanism, not an emulator-derived implementation or a complete MMU.
  Unknown reset state and architecturally undefined multiple matches remain
  explicit errors in its default policy. The opt-in native CPU-operation
  bridge now connects it to original generated guest routines. A separately
  named reference policy supplies independently observed boot contents and
  duplicate/miss handling; it is not a hardware reset promise. CP0/TLB state
  and the selected policy must be serialized in any runtime snapshot.

- `include/jfg/runtime/cpu_operation_bridge.h` and its single-owner runtime
  implementation are original code. Active callbacks prevent owner teardown;
  unbound/unsupported operations retain fatal traps. The original translator,
  zeroing and cache-maintenance bodies are recompiled from the user's private
  ROM, not copied from an emulator/decomp implementation. Their CPU work is
  observed but does not yet drive the native event clock.

- `include/jfg/boot/reference_cache.hpp` is an explicit coherent-reference
  operation policy, independently authored using CACHE selector meanings in
  the NEC manual and original private microtests. It is not a physical cache
  implementation and does not promise arbitrary self-modifying-code support.
  Existing validated generated-overlay publication owns executable code;
  RT64 owns its separately committed framebuffer output. Unsupported cache
  selectors/address modes fail closed. See the OS-clock qualification document
  for the independent 193-case timing and data-alias evidence.

- `include/jfg/boot/cpu_status.hpp` implements only ERET's documented Status
  transition from NEC's manual (chapter 17, page 434). Native thread entry
  uses it because the HLE handoff replaces the OS exception-return boundary.
  Independent original-OS thread probes verify the entry value. General ERET,
  EPC/ErrorEPC and LLbit handling are not supplied by this small helper.

- `include/jfg/boot/mi_interrupt_mask.hpp` is independently authored against
  the public SDK RCP register definitions (`PR/rcp.h`, MI_INTR_MASK_REG), not
  copied from an emulator. Original private-ROM microtests validate set/clear
  readback through all 64 requested masks. The diagnostic native MMIO provider
  and scheduler baton hook preserve per-thread RCP masks, independently checked
  with an original-OS two-thread fixture. Only its unrestricted global-policy
  case is currently qualified. No emulator scheduling structure was reproduced;
  the project's existing stackful executor remains responsible for handoffs.
  The register and saved thread masks must be included in runtime snapshots.

- `include/jfg/boot/sp_status.hpp` is independently authored from the public
  SDK's SP_STATUS register definitions, with the SDK task signal names used
  for explicit host-owned task preparation/completion. Original private-ROM
  task-start tests verify register transitions and instruction counts; no
  emulator implementation was read or reproduced. DMA, arbitrary RSP code,
  yield/resume and completion latency are not supplied by this register model.
  Its status/pending state belongs in runtime snapshots. The diagnostic uses
  original task-start bodies, while the existing host task engine still owns
  completion and acknowledgement at its legacy service boundary.

- `include/jfg/boot/reference_device_timing.hpp` is an independently measured
  and deliberately restricted corrected-Mupen profile, not a hardware model.
  Authored micro-ROMs sweep VI configuration and SP polling phases, and the
  derivation separates CPU store retirement from lazy exposed Count. No
  emulator implementation was copied. These period/latency queries are not
  yet used by the native game clock; qualification and limits are recorded in
  `docs/planning/phase9-os-clock-qualification.md`.
### Original task load and synchronous reference SP DMA (2026-09-26)

`include/jfg/boot/reference_sp_dma.hpp`, its guarded native MMIO integration,
and the ROM-free task/DMA test drivers were independently authored here from
the SDK SP register interface and black-box observations. No third-party
runtime/emulator implementation was copied or translated. The SDK's memory
and alignment contract is also documented in the
[N64 Programming Manual, memory issues](https://ultra64.ca/files/documentation/online-manuals/man/pro-man/pro03/03-06.html).
The intentionally limited synchronous behavior is a named reference profile,
not a hardware DMA latency or RSP execution claim.

Original OS bodies and boot microcode are compiled/copied only from the
user's pinned private ROM/ELF into ignored local artifacts. The missing task
helper was recovered as verified symbol metadata with unchanged loaded code,
then admitted as an additional required generated body, not a handwritten
replacement. Its eleven-function load/start closure is sanitizer-tested
against sixteen independent reference task cases. The independent branch
micro-ROM establishes the reference's annulled-slot timing separately from
the game; no replay-specific cost is inserted. Full guest OS/context-switch
coverage and the execution-driven game clock remain unimplemented.

### Original OS stackful handoff qualification (2026-09-26)

`tests/generated_os_threads.cpp` is an independently authored CPU/transport
driver. It executes private original OS bodies; it does not transcribe an
OS implementation. The documented exception-return transition and the
project's existing baton executor transport contexts selected by original
guest code. The independently authored micro-ROM and black-box emulator
outputs qualify queue behavior, thread masks, and measured Count intervals.
Initialization is explicitly untimed fixture setup, not a substituted
osInitialize implementation. No third-party runtime implementation was read
or copied to author this driver. The accompanying generic N64Recomp patches
retain the upstream MIT license and are not claimed as independent-runtime
source. The independent ERET micro-ROM distinguishes this reference core's
Count accounting from physical hardware timing.

`include/jfg/boot/guest_thread_transport.hpp` extracts this independently
authored stack transport. It validates observed continuations and uses the
existing baton executor; all OS scheduling/context decisions remain in the
private original program. The original-SP/lazy-COP1 microtest validates ten
exception entries, eight wakeups, preserved integer/FP state and exact measured
reference timing. No third-party runtime source was used. This diagnostic
qualification is not a shipping-runtime acceptance claim.

`reference_pif_boot.hpp` and its native guarded-MMIO use are independently
authored from black-box boot observations: the qualified control write is
the boot acknowledgement command 8; reads return cleared control state.
Controller commands, reset/CIC protocols and arbitrary PIF accesses are not
implemented by that small model. Original `osInitialize`, including its
recovered private PI-handle helper, is executed locally without substituting
OS code. The independent initialization/interrupt microtest compares its
register transitions and exact Count interval under fatal ASan/UBSan.

### Execution-driven diagnostic devices (2026-09-26)

`reference_pi_dma.hpp`, `reference_si_dma.hpp`, and `reference_compare.hpp`
are independently authored from public register contracts and independently
written black-box micro-ROM experiments, without reading/copying another
emulator's runtime implementation. They are limited corrected-Mupen reference
profiles, not assertions of physical N64 timing. Their tested ranges and
unsupported cases are explicit. See `phase9-os-clock-qualification.md` for
artifacts, bounded timing observations and the unchanged gameplay frontier.

The opt-in native CPU path executes original OS initialization, thread,
interrupt, timer and controller routines from the user's private ROM. The
host supplies architectural/device state and stack transport, not rewritten
OS algorithms or guessed HLE CPU costs. The IPL Count/Status/MI initialization
is a read-only, ROM-pinned hardware-register capture; no oracle actor/player,
RNG, camera, gameplay RAM or save state is injected by this profile. The
initial save remains the explicitly selected replay input.

Additional function discoveries are validated private symbol metadata only:
the VI worker and controller read-packet leaf have closed original control
flow and verified caller references. Their loaded ELF bytes remain unchanged.
They do not constitute independently authored copies of original runtime
source. Compiler patches retain their upstream MIT license. Neither these
private tests nor the opt-in native integration refresh existing signed
acceptance evidence or establish full gameplay parity.

`reference_event_commit.hpp` is independently authored from branch-boundary
SP/DP observations: one event per commit, chronological deadlines, and the
observed SP-before-DP tie. It does not copy another runtime's event queue.
Other tied-source orders remain explicitly unqualified. Byte-length PI and
SI/CIC payload probes are private isolated-device experiments, not injected
gameplay state. The original OS native integration remains diagnostic.

`reference_flash_bus.hpp` and `reference_ai_dma.hpp` are independently authored
from isolated CPU/MMIO observations. Flash wraps the pre-existing save store;
its DMA source sampling, command results and device deadlines are separately
tested. AI has an owned two-buffer FIFO and reference-clock deadlines, not
host-audio-driven interrupts. Neither implementation reads another emulator's
source. Their new tests and integration do not refresh signed acceptance.


### Retained cartridge boot state (2026-10-02)

`ipl_handoff.hpp` is an independently authored adapter for the supported
CIC-6105 cartridge-entry profile. Local generated RAM-check bodies identify
the three retained memory words; their corresponding bytes are copied from
the user's verified ROM at runtime. The adapter also supplies `osCicId`.
No IPL3 bytes or upstream implementation are redistributed. Synthetic bounds
tests and the private idle replay validate this limited correction. See
`docs/development/boot-gameplay-fix.md` for the health/ammo regression and limits.

The US retail synchronous-print sink is independently authored from its local
ROM-observed ABI: three argument-home stores and a non-null return, with no
output buffer access. The dispatch adapter validates the loaded instruction
identity and guest stack range before applying this behavior. No upstream
implementation source was copied.

The US sound-player empty-queue recovery is independently authored from local
recorded behavior and the supported ROM's event ABI. A full 200-node pool drops
its periodic event, then the sound player spins on an empty queue. The adapter
qualifies the sound-player identity, empty result, prior overflow and interval,
then delivers a periodic event with a positive delay. Original queue links,
event ordering and accounting are untouched. No upstream code or ROM payload
is included; only private reproductions and synthetic fixtures were used.


### Opt-in box-jump prototype (2026-10-04)

The controller and movement telemetry are independently authored from local
position/input observations and synthetic fixtures. They use ordinary input
commands with room/generation binding, bounded trials and manual cancellation.
No game source, assets or upstream traversal implementation are redistributed.
Player movement state and animation telemetry use signature-qualified local
ROM observations. The incorrect ledge-trial assumption was removed: the
recorded intermediate stop is supported on a gently tilted box top.
Live tests confirmed ordinary jumps through the five SS Anubis platforms;
automatic whole-route discovery and item interaction require separate evidence.
