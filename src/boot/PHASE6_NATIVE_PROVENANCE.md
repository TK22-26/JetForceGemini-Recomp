# Phase 6 native-entry provenance

| Module | Owner role | Public contract | Independent validation |
| --- | --- | --- | --- |
| `hle` | libultra boundary owner | Reached queue, event, thread, priority, PI DMA, cache, interrupt-mask, controller/SI, and VI operations over checked guest state | ROM-free ABI/layout/error tests and guarded native execution |
| `thread_scheduler` / `executor` | scheduling owner | Deterministic priority scheduling and bounded stackful guest execution | ROM-free scheduler/executor tests and repeated native records |
| `reset_handoff` | reset owner | Checked reset subset, delay slots, and transfer from `0x80000400` | Synthetic clear-loop, transfer, fault, and budget tests |
| `native_boot` | native M2 adapter owner | Validated load, guest aliases, exact-ROM overlay data, guarded MMIO register pages, generated dispatch, internal VI-manager bridge, watchdog, state/journal hashes, and exact success/trap schemas | Private native repetitions, original-entry AddressSanitizer run, and BizHawk queue-ring checkpoint |
| dispatch-table helper | private mapping boundary owner | Strict identification JSON validation and build-local C++ include generation | Synthetic schema and rejection tests |
| native verifier | evidence owner | ROM identity, exact output, state/journal determinism with first divergence, invalid-ROM, MMIO ledger, sanitizer, complete producer provenance, and emulator/native parity gates | Python contract tests and private M2 CTest |

The emulator was used only as a black box: the private probe observed public
guest memory state and frame progression. ROM bytes, generated bodies,
identification mappings, and raw checkpoints remain ignored. The public
artifacts contain hashes and high-level facts only. Generated declarations are
consumed through their generated ABI.

Every module above is independently authored. **No third-party implementation
source was copied, transcribed, adapted, or relabeled.** No source from
BizHawk, librecomp, N64ModernRuntime, or the Jet Force Gemini decomp was used
as implementation text.
