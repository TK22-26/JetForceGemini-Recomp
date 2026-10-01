# Phase 6 native-ROM boot completion ledger

This ledger preserves the former native-boot gap and records its disposition.
The strict M2 exit gate is complete locally: the supported original entry path
reaches stable, repeatable VI/scheduler activity with exact cross-process
output identity, emulator checkpoint parity, invalid-ROM safety, and zero
unsupported accesses on the accepted path.

## Closed native-gate work

1. **libultra C-ABI bridge:** reached thread, priority, queue, event, PI, and
   VI operations are independently implemented and bound to the deterministic
   scheduler.
2. **Reset vector and IPL handoff:** the checked reset subset establishes the
   observed 4 MiB memory state and transfers from `0x80000400` into generated
   code.
3. **Direct hardware and dispatch:** cached/uncached RDRAM aliases are mapped;
   reached RCP pages use guarded per-instruction access instrumentation and a
   public-register whitelist. Unresolved dispatch, HLE, register, and access
   boundaries trap instead of silently continuing.
4. **Initial title execution:** the real generated entry creates and starts
   title threads, registers VI events, and reaches the title VI queue.
5. **Emulator/native parity:** a private BizHawk 2.11.1 black-box checkpoint
   proves three actual queue-ring advances and consumed VI messages; three
   native runs agree at canonical-output, state-hash, and journal-hash levels.
   The public summary binds the private record and all producer inputs by
   SHA-256.
6. **Sanitizer:** a separately identified AddressSanitizer executable runs the
   same original-entry checkpoint and invalid-ROM rejection path and must match
   the ordinary build's semantic state, journal, and MMIO trace.

The earlier facts-only identification found 47 of 55 boot-critical libultra
functions, but M2 implements only the surface actually reached before the
stable-VI checkpoint. Any later call outside that surface retains the explicit
fail-closed disposition in `evidence/phase6-native-stub-ledger.json`.

## Work intentionally beyond Phase 6

- Rendering, F3DDKR resolution, and production RSP graphics handling are
  Phase 7 work.
- Gameplay-complete SDK/MMIO coverage is not asserted by the M2 checkpoint.
- Distribution remains prohibited until the maintainer records the human
  legal/license decision required by `phase6-acceptance.md`.

## Status

- Phase 6 deterministic infrastructure: complete.
- Phase 6 native-ROM boot to stable VI/scheduler activity (M2): complete
  locally and signed.
- Remaining Phase 6 unsupported entries at the accepted checkpoint: zero.
