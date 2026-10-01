# Native ERET transfer boundary

## Implemented (2026-09-27)

The [instruction-effect hook prototype](phase9-instruction-effect-observation.md)
correctly rejects ERET: code after `cop0_eret()` can execute much later, when
the parked host stack is resumed, or never execute before shutdown. It is not
the point at which the original ERET selected another guest thread.

`GuestThreadTransport` now accepts an optional const-context observer. It
emits the current host guest-owner, selected guest-owner and target PC after
validating the transport continuation, before copying/yielding to the next
participant. Same-thread returns emit before returning directly. Rejected
owners, missing parked continuations and wrong known-target continuations
emit no event. Scheduler and post-resume continuation guards remain active.
Known-target validation now also occurs before yielding, so a rejected
transfer cannot publish a successful observation first.

The original-OS native CPU bridge already commits the profile's EXL transition
and exception-boundary flags before calling the transport. The new observer
reads those results there. It verifies the ERET opcode, cleared EXL/ERL, EPC
and pending ERET-boundary flag. It does not run after the suspended C call
returns, alter CPU Count, modify guest state or select a thread itself.
This does not qualify a complete hardware ERET model, LLbit behavior or ERL
returns, which are outside this bounded native profile.

## Opt-in replay interface

`scripts.phase95_native_replay` accepts `--eret-transfers` together with
`--device-events`, focused updates, instruction points and the explicit
`original-os-probe` execution profile. The setting is off by default and the
wrapper clears an inherited `JFG_PHASE9_ERET_TRANSFERS` before applying the
explicit choice. An incompatible engine or missing device capture rejects.

`eret-transfers.tsv` contains a versioned header, bounded invocation window,
sequence, raw ERET PC/opcode, old/new transport owner, target PC, post-transition
Status, raw native Count and all 32 full-width GPRs. It is a separate artifact;
old instruction-entry/device events are not relabeled or given new meanings.
No overlay address or register is normalized.

The writer has a 65536-row limit and finishes only when an observed instruction
entry advances beyond the requested window. Shutdown by itself does not write
a successful footer. Output/order/boundary failures stop the native run. The
reader rejects malformed columns, ordering, addresses, widths, zero-register
violations, invalid Status/opcode and missing or incorrect footers. An empty
but completed window reports zero observations, not a successful retirement
measurement. Replay records the declaration, completion, row counts and file
digest, and rejects a requested capture that did not complete.

## Verification so far

- MSVC Release builds and all three focused CTest targets pass: existing guest
  transport, new ERET observation, and the new trace writer.
- `scripts.test_guest_eret_observation` compiles and runs those three targets
  under fatal ASan/UBSan, then parses the writer's real output with the Python
  reader. Controls and observed runs have identical execution, repair counts
  and handoff counts. The expected timeline proves five observations precede
  the associated entry/resume, including bootstrap and same-thread returns.
  Five invalid/out-of-execution transfer attempts are rejected without an
  observation or transport/context mutation.
- The trace roundtrip preserves full-width return addresses and raw Count
  wraparound. Writer tests reject invalid opcode/Status/zero register/target
  and misalignment, reversed invocation order, bad output and invalid windows.
- Six reader/configuration tests pass, covering raw fields, same-thread
  counting, malformed/torn files, boundary/order violations, empty completed
  windows and inherited-flag removal. The combined reader/device/profile/
  failure-trace group passes 21 tests. The complete autonomy suite passes
  362 tests in 97.664 seconds.

The retained sanitizer report is
`tools/private/eret-transfer-proof-20260927a/result.json`, SHA-256
`9c18b008ac50f9ec4aeb28c5a03a7ab7f9d1e99601c933115edf2956a167396c`.
It pins the tested sources and retains the six compiler/execution command
receipts and outputs. Its game non-perturbation and oracle qualification
flags are false: ROM-free transport tests alone cannot establish either.

## Live native qualification

A fresh detached source snapshot and guarded CMake build completed successfully:

- Source commit: `4230cd0724111adca93d1ae1f888bdb7e7eb899b`.
- Source-build receipt:
  `tools/private/autonomy/source-eret-transfers-20260927a/source-build.json`,
  SHA-256 `eba449fa1790f1cc0d1a3833e9d4ab41cf981c635a253a552e55740580655274`.
- Executable: `tools/private/aert1909ab/Release/jfg-native-boot.exe`,
  SHA-256 `7e49a14a23bf529e64381364bc3f534d0b9e141cfb6eac391d0f1940ec515c60`.
- EXE/DLL runtime digest:
  `43927562b53aa18525302e25b5247a4b090b291344d3bd3bd9da83a1bded1b85`.

The build's own two new CTest targets also pass. This is source-bound local
build evidence, not a hermetic dependency/toolchain attestation; the existing
receipt's `build_closure_verified` remains false. No main branch was moved
and no control executable was replaced.

`eret-transfers-control-20260927a` and
`eret-transfers-observed-20260927a`, under `tools/private/`, both completed
4800 VI, 1973 updates and 1984 controller polls normally. They use the same
new executable, original-OS profile, initial saves, recorded input and
1907-1910 focused update range. The control explicitly disables the new
observer even with its environment variable inherited as `1`; no ERET file
is created. The other capture requests `eret_transfers=True` through replay.

The **entire** update and retrace files, controller input and delivered-poll
log, point and device traces, and four full 4-MiB focused RDRAM images match
byte-for-byte across both captures and the retained
`device-events-native-20260927b` control: ten files per capture. Full update
parsing, actor/snapshot binding, completion/profile/input declarations and
source/runtime pins were checked; backing file hashes were rechecked after
measurement. No ignored fields or comparison shifts were used.

The bounded 1906-1911 ERET file contains **308** transfer boundaries, including
15 same-thread returns. Per-invocation counts are 56/44/60/48/52/48. The captured
ERET opcode matches the instruction bytes in all four retained RDRAM images.
The trace digest is
`596df696e88ce8f8cf38dbde3df2ff86ca4365803f6f918e102de2e2ccab2d42`.
The engineering measurement and all evidence pins are retained at observed
`nonperturbation.json`, SHA-256
`988a01c38b976faeedcedeef79b8d3b0eea716606d93cd3c6415075cfecd756f`.
This establishes native non-perturbation on this retained prefix and focus,
not a universal observer guarantee or a newly accepted autonomous ledger job.

## Remaining acceptance

The [oracle ERET and Count-mutation observer](phase9-oracle-cpu-boundary-observation.md)
now passes compiled-body sanitizer tests and observation-off/on game
qualification. At invocation 1908 it records 63 ERET boundaries and 130970
Count mutations, with twelve entire artifacts unchanged from the controls.
This does not independently align those events with native transfers.
Deferred-work/anchor accounting, ordinary instruction effects and raw
code/overlay identity are still required before qualifying an all-thread
interval and feeding it into automated causal diagnosis. The boundaries
alone do not distinguish the two current device-ordering hypotheses.

This is not yet an all-instruction completion trace, causal repair or a
completed autonomous loop. General proof construction,
reviewed repair integration, wider gameplay and restart/endurance acceptance
remain part of the unchanged goal. The selected-state frontier remains 1908/1909.
