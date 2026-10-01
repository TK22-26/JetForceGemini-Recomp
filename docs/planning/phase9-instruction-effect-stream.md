# Bounded native instruction-effect stream

## Implemented building block (2026-09-27)

The [compiler's after-effect hooks](phase9-instruction-effect-observation.md)
and [pre-handoff ERET observer](phase9-eret-transfer-observation.md) need one
bounded artifact that preserves instruction order and raw register contexts.
`InstructionEffectTrace` and its streaming Python reader now implement that
format. The game generator, runtime wiring and explicit replay opt-in are now
implemented. The first observer-on capture correctly rejected a continuation
hook-placement defect. After the separately proved compiler correction,
**the bounded native game capture now passes**, including complete strict
pairing and whole-artifact observation-off/on equality. The subsequent
[oracle stream](phase9-oracle-instruction-effects.md) also passes bounded
capture and local-witness checks; cross-engine all-thread comparison remains
open. See the
[continuation boundary repair](phase9-continuation-hook-boundary.md).

The format has three explicit phases: instruction entry, ordinary effect,
and ERET before host handoff. Every effect must complete the immediately
pending entry at the same section, raw PC, opcode and host guest-owner.
An ERET cannot masquerade as an ordinary textual after-hook. Its selected
owner, target PC, thread word and cleared EXL/ERL must be valid. Missing,
duplicate, mismatched or still-pending effects prevent successful completion.
This pairing requirement is a qualification gate to test on the actual
runtime, not an assumption that every unqualified callback completes inline.

Records retain section identity, raw PC/opcode, guest-owner, running-thread
word, native Count, Status/Cause, ERET target/selected owner, latest device
sequence and all 32 full-width GPRs. Wire integers are explicitly little
endian, independent of RDRAM's layout. The first record stores every GPR;
later records store a canonical change mask and only changed 64-bit values.
The reader reconstructs every GPR without aliasing addresses or dropping
upper bits. It rejects altered schemas, malformed deltas, device-order
reversal, alignment violations, nonzero r0 and malformed transfers.

Limits are one explicit invocation, at most 4194304 records and 512 MiB.
The writer reserves room for its footer before each row. It finishes only
when an observed invocation advances beyond the target, with a nonempty
stream and no pending entry. Shutdown by itself does not complete a capture.
I/O errors, budget exhaustion or invalid boundaries permanently fail that
writer instance. No guest state, clock, event queue or thread is modified.

`scripts/phase9_instruction_effect_trace.py` validates incrementally; callers
must exhaust `records()` to validate its footer. `summary()` does so. This
avoids retaining millions of reconstructed contexts in memory just to validate
a stream. FPU/HI/LO, memory contents, hardware retirement and common-clock
alignment are deliberately not claimed by this format.

## Executable verification

`tests/instruction_effect_trace_tests.cpp` exercises four valid records,
Count wrap and ERET ownership, and thirteen rejection cases. Its distinct
high/low register patterns check all GPR positions, not just r2/r31.
Nine Python tests cover complete reconstruction, every possible truncation of
the fixture stream, trailing bytes, mismatched pairs/owners, bad transfer
state, invalid windows/budgets, redundant masks and changed/unchanged bits.

`scripts.test_instruction_effect_trace` compiles the writer under fatal
ASan/UBSan, reruns the existing compiler-effect proof, then wraps that proof's
actual generated hooks with the new writer. The original independent fixture
still verifies the expected instruction paths, link/store effects and final
results. All twelve cases pass with the writer off and on, with identical
stdout/final results. The strict reader recovers all **75 entries and 75
effects** and checks the captured operand/high-register bits. The wrapper's
owner, invocation and Count fields are synthetic; they do not qualify real
game scheduling or Count accounting. ERET is covered separately by the writer
fixture, not by those generated ordinary-instruction cases.

The retained sanitizer report is
`tools/private/instruction-effect-trace-proof-20260927b/result.json`, SHA-256
`23fa55273b92a522e27603f50014ac50dd85f98fb25d6f7084f738b5a969421b`.
Generated trace SHA-256:
`294ac7c49f3266e77ac20ec26a423631d53574de3c20f0303a2d956136815258`.

MSVC also builds the writer tests with C++20, `/W4 /WX`, and passes all four
valid records and thirteen rejections. Its binary trace is byte-identical
to the Linux sanitizer build's output. The retained Windows report is
`tools/private/instruction-effect-trace-msvc-20260927b/result.json`, SHA-256
`8184b9efd9c1788e6f607f70df241de428d9cca863f4283d796edc6e0d9025da`.
This is local compiler/format evidence, not a hermetic build attestation.
The combined effect/Count/ERET/device reader suite passes 42 tests.

## Game integration and retained first failure

`scripts.phase9_instruction_effect_root` generates a separate private root,
preserving the existing execution hook before each new entry observer. Thus
an interrupt handler and actual exception resumption precede the interrupted
instruction's entry record. Ordinary effects use the compiler boundary;
ERET uses the validated transport callback before host handoff. Executed
unqualified callbacks or incomplete/mismatched pairs reject a capture.

The real generation at `tools/private/instruction-effect-root-20260927a`
passes a comparison of all **2939 normalized generated bodies**: removing
only the new entry/effect lines and indentation reproduces the previous
instruction-observation bodies. It covers 379218 sites: 377429 ordinary
effect hooks, one dedicated ERET site and 1788 explicitly unqualified sites.
Their full section/PC/opcode inventory remains private and pinned. The
manifest SHA-256 is
`e8552c020176fed42ea85fcd170ede2bcd26d72774f4168fea59a9ba3e0f83ae`.
This is a generation check, not evidence that every path is reachable or
that an unqualified operation may be ignored during capture.

Native replay now accepts `--instruction-effect-update`, requiring original
OS execution, bounded device capture and ERET capture. It clears inherited
flags, records the explicit request, checks the completed binary stream and
preserves parse failures in the run result. Raw generated section/PC/opcode
identity is retained; resident-code/overlay correspondence is not inferred.
The writer fixture is also a normal CMake/CTest target. The focused generator,
reader/configuration, ERET, replay-profile and failure-reader group passes
29 tests. The detached source-bound build from snapshot
`1f5b181873a8fe905af1fbe6500e80235b935be7` completed; no main branch or control
build was replaced. All three native CTest targets pass. Its observer-off
capture completes 1973 updates at 4800 consumed VI, preserving all eleven
whole control files (update/retrace traces, input, polls, point/device/ERET
traces and four focused RDRAM snapshots) byte for byte.

The first observer-on run rejects at invocation 1908 with
`instruction-effect-probe / pair-boundary-or-budget`, target `0x02f0030c`.
The retained 8127607-byte partial stream has 159139 readable diagnostic rows,
but no completion footer; it is not accepted evidence. Actual generated code
shows continuation dispatch observing the skipped function-start instruction
and bypassing the resumed instruction's before hook. The strict reader/writer
gate is unchanged. A six-test witness binder now cross-checks accepted streams
against exact local device sequences and dedicated ERET boundaries; it does
not turn this incomplete capture into a qualified one.

The separate corrected root at
`tools/private/instruction-effect-root-20260927b` again passes all 2939 body
comparisons against its corrected before-only root, with the same site counts.
Its manifest SHA-256 is
`1ba56846d3b9577af10d44fbea4c5d064336403438a5a01c6875ac8da474ac0c`.
The new compiler changes an existing boundary, so candidate-versus-old-runtime
retesting must remain separate from observer-on/off non-perturbation testing.

## Qualified corrected-runtime capture

The new source-bound build completed (33.703 seconds configure, 423.734
seconds build); all three native trace/transport CTest targets pass.
`instruction-effects-control-20260927b` and
`instruction-effects-observed-20260927b` both complete 4800 consumed VI,
1973 updates and 1984 controller polls (76.734 and 87.547 seconds).
All eleven whole control artifacts match byte for byte between these two
runs, including the four complete focused RDRAM snapshots. The off-control
again proves the replay option clears an inherited observer flag.

The strict reader consumes **2354642 rows**, comprising **1177321 entries**,
1177261 ordinary effects and 60 dedicated pre-handoff ERET effects. It reaches
the valid footer with no pending pair. The 119094987-byte stream retains six
guest-owner identities. Exact independent local observers bind all 256 device
instruction witnesses and all 60 ERET transfers, including full-width GPRs.
No row budget, pair requirement or comparison field was relaxed.

The source-build receipt is
`autonomy/source-instruction-effects-20260927b/source-build.json`, SHA-256
`8715c540cd94f5efbd4a2681990dd0faf75a6d38fba8c1a806f5737f4cbfdd2c`.
Executable: `ca050eb84be2df3a4cc5af2d9438872fb5d10382bd5edee73a8171150e182dcd`.
EXE/DLL runtime: `04b53ae3c6fe2c47e4a19949de1e674e43446d4ad685f6a9733a1ab8edc1477a`.
Instruction stream: `fef47176b96f5f8834c8919782f148dbfad4c4353ef02e5d74cda83a65192890`.
The observed `nonperturbation.json` SHA-256 is
`b8b56020987635584da0815136d0ed6f226982e1c0a0f4f6cfe7a4048e27be99`.
This is local engineering qualification, not an autonomous ledger observation,
hermetic build attestation, or promotion of this compiler/runtime candidate.

The compiler correction preserves whole selected-update/retrace traces and
delivered inputs against the older runtime, but changes CPU traces and small
parts of focused RDRAM. Those changes are recorded separately in the
[candidate retest](phase9-continuation-hook-boundary.md), not waived as observer
non-perturbation. The fresh oracle comparison still passes through 1908 and
first differs at 1909.

## Next acceptance

The preliminary [reference link-register repair](phase9-oracle-link-repair.md)
now passes twelve independent cases in both Mupen interpreters and agrees
with Ares. Two whole-game-prefix replays preserve thirteen checked artifacts
from the old oracle, so it does not explain the 1909 divergence. It remains
an isolated reference candidate, not a silently replaced historical baseline.

The [oracle effect stream](phase9-oracle-instruction-effects.md) now passes its
bounded game capture, off/on non-perturbation and independent local witnesses.
It explicitly distinguishes branches, ERET, exceptions and idle fast-forwards.
Count mutations and instruction entries alone are not substitutes. Preserve
raw overlay/code identity and qualify the bounded all-thread comparison
before using it to test a causal repair. Do not subtract raw native Count
from oracle lazy Count or tune either clock to make traces match.

The active goal remains the entire automation loop. This prototype does not
close general instrumentation/proof construction, reviewed integration,
broader gameplay coverage or recovery/endurance acceptance. The selected-state
frontier remains update 1908/1909.
