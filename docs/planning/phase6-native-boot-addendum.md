# Phase 6 native M2 record

The private-gated `jfg-native-boot` executable now clears the local Phase 6
M2 gate. It validates the supported original image, establishes the reset/IPL
state at `0x80000400`, transfers into the real generated entry path, and
reaches three delivered VI retraces through the title's message queue and the
project scheduler. Three verifier-controlled processes produce the same
canonical record, full RDRAM/state hash, ordered journal hash, and explicit
MMIO trace. The record also embeds the compiler/build and sanitizer identity;
the public summary publishes stable fields and cryptographic bindings instead
of copying a large private trace.

```json
{"kind":"jfg-phase6-native-boot","status":"stable-vi","sanitizer":"none","vi_retraces":3,"vi_frames":3,"vi_interrupts":3,"vi_messages_delivered":3,"threads_created":6,"rdram_bytes":4194304,"mmio_accesses":22,"unsupported_accesses":0,"state_hash":"...","journal_hash":"..."}
```

The runner models the observed 4 MiB RDRAM configuration, cached/uncached
guest aliases, the reset subset, instrumented reached RCP register pages, reached libultra
queue/thread/priority/event/PI/VI calls, and the internal VI-manager boundary.
Generated guest threads execute through the deterministic stackful scheduler.
The internal VI manager is an independently authored behavioral bridge because
that internal entry is not present in the generated registry. Deterministic
virtual frames raise the registered VI event; the manager consumes that event
and delivers its configured message to the title queue. The gate increments
only when the title actually consumes a delivered message. It does not inject
a message from the blocking title receive.

Unsupported generated dispatch and HLE/MMIO boundaries remain fail-closed.
The parent process accepts only the exact authenticated child success or trap
schema, has a bounded watchdog, and treats access violations or malformed
output as failure. The accepted M2 run has zero unsupported accesses. The
explicit disposition is recorded in
`evidence/phase6-native-stub-ledger.json`.

The independent black-box checkpoint was captured with BizHawk 2.11.1. Its Lua
probe observed the title queue's `first` ring index advance 0 → 1 → 2 → 3 on
frames 31, 32, and 33 and read the same VI message from each consumed ring
slot. The private evidence binds the checkpoint, exact Lua probe, BizHawk
executable, generated-corpus inventory, identification report, native and ASan
executables, source closure, and clean producer revision. Raw emulator/native
evidence remains ignored; `evidence/phase6-native-boot-summary.json` publishes
only safe counts, hashes, comparison results, and the private-body digest.

Usage is `jfg-native-boot --rom <path> [--watchdog-ms <1..300000>]`. Probe
watchdogs default to the greater of 30 seconds or 20 milliseconds per requested
retrace. Exit 64 is
usage failure, 2 rejects the image silently, 3 is setup/execution failure, and
4 is a canonical fail-closed boundary trap. Success is exit 0 with exactly the
record above.

This milestone is boot/scheduler/VI activity, not gameplay or rendering.
Phase 7 still owns renderer integration and real captured RSP task handling.
The result is local research only and does not authorize distribution; the
human legal/distribution checkpoint in the acceptance contract remains open.
