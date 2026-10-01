# Paired reference instruction effects

## Result (2026-09-27)

The reference now supplies the missing counterpart to the
[native effect stream](phase9-instruction-effect-stream.md). A bounded real-game
capture completes **2362960 rows**, with an exact entry/effect pair for every
recorded instruction. Observation off/on preserves all thirteen checked whole
artifacts from the qualified [link-corrected reference](phase9-oracle-link-repair.md).
This is an engineering observation capability, not a causal fix or completed
autonomous repair loop. Selected state still matches through update 1908;
the first actor/camera mismatch remains 1909.

The subsequent [bounded correspondence and jump-table repair](phase9-guest-jump-table-repair.md)
qualifies the copied-vector boundary and identifies a concrete generated GPR
defect. It does not yet establish the cause of the gameplay timing mismatch.

| Effect type at invocation 1908 | Count |
| --- | ---: |
| Instruction entries | 1181480 |
| Ordinary effects | 1051101 |
| Branch decisions/link effects, before the slot | 130308 |
| ERET before subsequent interrupt dispatch | 63 |
| Exception boundaries while an instruction is active | 6 |
| Idle fast-forwards | 2 |

The six exception records are at MTC0 Status, `0x80099d68`, opcode
`0x40886000`. They must not be called six failed ordinary instructions or
silently compared to native ordinary-effect boundaries. Interrupt dispatch
can occur while that interpreter instruction is active.

## Implementation and bounds

`oracle_instruction_effects.c/.h` observes the cached interpreter only.
`oracle_instruction_effects.patch` instruments exact dispatch, jump, ERET,
exception and decoder boundaries in the isolated link-corrected producer.
Decoder metadata retains the instruction word used to populate each cache
entry. Reading current RDRAM again would not establish what an existing cached
entry executes. No guest instruction, register, memory, Count or queue policy
is rewritten by the observer. The added cache metadata changes host structure
layout, so the producer was rebuilt completely and retested with observation
off as well as on.

The binary retains raw guest PC, decoded opcode, thread word, lazy Count and
anchor, Status/Cause/EPC/LLbit, live PC, delay-slot state, device sequence,
branch target/decision, idle ticks and all 32 full-width GPRs. Canonical GPR
deltas and explicit little-endian integers keep the artifact bounded without
discarding register bits. It does not include all FPU/HI/LO or memory effects.

The window is one explicit invocation, at most 4194304 rows and 512 MiB.
Missing/overlapping entries, unsupported delayed transfers, incomplete output,
invalid special boundaries or budget exhaustion reject the capture. A footer
requires entry into the next invocation with no pending effect; process exit
alone cannot certify completion. Ordinary MTC0 Status writes may change EXL;
that architectural write is not by itself an exception observation.

Oracle replay accepts `--instruction-effect-update`, requiring the same
`--cpu-boundary-update`, explicit cached interpreter, focused device capture
and all existing replay checks. The option and specification are recorded in
manifest/result, the reader is exhausted before acceptance, and disabling the
option clears an inherited request. Direct oracle-replay producer inventories
now include the new reader; a dependency test checks propagation. Old job
identities are not rebound to the changed tools.

## Verification

The extracted-body proof compiles the actual patched and prior jump macros,
dispatch wrapper, ERET and general-exception functions with controlled CPU
surroundings. Twelve independent cases pass with identical final results on
the prior producer, new observer-off producer, and observer-on producer under
fatal ASan/UBSan. They include link visibility, annulled slots, slot writes,
out-of-block dispatch, idle fast-forward/fallback, ERET with immediate interrupt
dispatch, a general exception, decode trampolines and MTC0 Status. Four invalid
captures reject. These are extracted-body tests, not complete CPU qualification.

The first proof's expected slot count was wrong: twelve top-level cases execute
four slots, not five. The retained first attempt reports failure. Correcting
that independent inventory yields 16 entries and 16 effects; no implementation
or format gate was changed to turn that test green.

Both real-game runs finish 7200 requested emulator frames and 2574 updates:
`tools/private/oracle-effects-control-20260927a` and
`tools/private/oracle-effects-observed-20260927a`. Whole update/retrace/consumed-VI
traces, point/device/CPU-boundary/checkpoint logs, all four focused RAM images,
final RAM and PNG match the earlier reference exactly. The off-control also
proves an inherited observer flag is cleared. Stream size is 157006777 bytes.

The independent witness binder consumes the full stream and checks **270**
exact device instruction entries, **63** dedicated ERET boundaries and both
Count-observed idle fast-forwards, retaining all available GPR and clock bits.
This does not establish cross-engine Count equivalence or the semantics of
every instruction. There are 52 passing focused reader/replay tests and 383
passing autonomy tests; `git diff --check` passes. Applying the published patch
to a fresh copy reproduces all six modified engine files.

SHA-256 pins (private reports are under `tools/private/`):

- Patch: `70b04e5ece92a7f1b7b079d3682e363f5179855a39d0f98d04345ed55c25c4a6`.
- `oracle-instruction-effects-20260927a/effect-build.json`:
  `614c382f394ed365947c6b3e82b720d625af4300d0350fbf184cdee0f1f18728`.
- Runtime: `663a5c11c8d48c3de0454de9e48de5f1495a4a1ecc85a5e54a059cfd583690f9`.
- Stream: `568d6d864ffef02b245966672646b3496abcdd34cb69385a78e10f3071c7b08c`.
- Observer-on `effect-qualification.json`:
  `2c9c733762d048c21bba9f6a85a052c153e4777463b6c9c4567c03ade86a72c0`.
- Observer-on `witnesses.json`:
  `b0e4d2a3d979537359e9fdfb9b9703d3a4e10f5819b084a4a84c21995cc70454`.
- `oracle-effects-proof-20260927b/result.json`:
  `92f3847c3730feb88583b996af29141b8acc0e50762815ce8c3b43779c7b4c35`.

## First cross-engine diagnostic and remaining acceptance

The two invocation windows do not start at the same instruction. The oracle
increments its marker at `JR ra` entry (`0x80045814`); native increments after
return. The diagnostic explicitly verifies that JR, its NOP slot, its target
`0x80044bf8` and unchanged full GPRs before comparing caller entries. This is
architectural lead-in evidence, not a searched/fitted row or frame offset.

The next **2830 rows** match raw PCs, opcodes and all GPRs. At the first raw
PC-identity boundary native reports `0x80075020` while the oracle executes
`0x80000180`. The pinned native source explicitly invokes the source copy of
the installed exception vector and checks its first sixteen bytes. All eight
focused snapshots confirm those four source/vector words agree. The diagnostic
stops there; it does not normalize addresses or label this a semantic bug.
Its `window-diagnostic.json` SHA-256 is
`e7cedbd5ceafc8f42467c3d22b592a30020c5dbaf7ba66e352c0be68d816ff45`.

Next qualify explicit code-identity and boundary correspondence, including
copied vector code, overlays, exception timing and idle spans. Then expose the
bounded all-thread result through a typed autonomous observation/research job.
Do not compare raw lazy Count to native pre-instruction Count as a shared clock,
discard special effects, or change gameplay to force equal traces. General
proof construction, reviewed integration, corpus expansion, recovery/endurance
and the full automation-loop objective remain unfinished.
