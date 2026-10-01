# Instruction-effect observation: native compiler building block

## Result (2026-09-27)

Patch 0021 implements opt-in offline-C `after_vram` hooks. This addresses one
part of the [device diagnosis's requested observation](autonomy-device-observation.md):
seeing a store or register operation after its effect instead of inferring it
from the next instruction entry. It is **not** a complete game retirement
trace, a qualified cross-engine clock, or a causal repair at update 1909.
The verified selected-state prefix remains 1908, beyond the requested 1291.

For ordinary operations, the hook follows the emitted operation. For control
transfers, it follows condition/target evaluation and architectural link
updates, before executing the delay slot. It does not wait for a generated
callee to return through the host C stack. Untaken branches emit their own
observation; annulled likely slots emit neither entry nor effect events.

Before/after hooks are stored independently. Duplicate hooks of one kind and
invalid after addresses are rejected. The new address field must be nonzero,
aligned, within the named function, and exclusive of `before_vram` in that
configuration entry. Existing hooks and hook-free generation retain their
previous behavior.

ERET, syscall, break, invalid/unsupported CP2 operations, non-C backends and
legacy permanent-pause self loops are explicitly unqualified. A textual hook
after a runtime callback does not establish when a thread-switching or
exception-raising operation completed. The callback must also be host-only
and non-mutating before it can be used as an observer. No game capture uses
these new hooks yet.

## Executable evidence

The original ROM-free fixture and independent expected paths live in
`tests/fixtures/instruction_effects.S` and
`tests/generated_instruction_effects.cpp`. The driver checks 12 cases:
arithmetic/store effects, taken/untaken ordinary and likely branches, direct
and register-indirect calls, indirect tail transfer, and ordinary/likely
conditional links. It checks exact before/effect event order, final results,
store visibility and link visibility. It exercises delay-slot writes that
overwrite an indirect target's source register.

`scripts/test_generated_instruction_effects.py` builds and runs the same
fixture with the previous compiler, the new compiler without hooks, and the
new compiler with hooks. All three runs agree and pass with fatal ASan and
UBSan. Disabled generated C is byte-identical to the previous compiler.
Removing only exact configured hook lines and indentation from the observed
bodies reproduces the control bodies. Nine negative cases reject for the
expected reason: ERET, syscall, break, legacy idle loop, both address fields,
unaligned address, wrong field type, negative address and outside-function
address. Loads, dynamically raised exceptions and whole-game retirement are
not established by these 12 cases.

The final rerun is retained at
`tools/private/generated-instruction-effects-20260927b/result.json`, SHA-256
`2519a98ad6dc4bc13ef85c543991a962cbbc9635644fd108c8cc9747778f670f`.
It preserves all 32 command receipts and their stdout/stderr, generated
controls, observed output and rejected configurations. Its explicit
`game_retirement_qualified` and `parity_verified` fields remain false.

Producer executable SHA-256:

- New isolated compiler:
  `867cbc368244c99efa94a7b0b017740c393e86dd4c45091f9be728c4dea0cd03`.
- Previous control compiler:
  `65979b9a7eb1eaf0fea547bef3c1a2bdc846904892302cb7c1576f55cabc6347`.

The existing game generation configuration was separately rerun with the
new compiler and no new hooks. All **62 files** in
`tools/private/effect-default-gamegen-20260927a/raw` match
`tools/private/execution-root-20260926o/raw` byte for byte, with no added or
missing files. The SHA-256 of the sorted compact JSON relative-path/digest
inventory is `cd188acb122145344ea04f1413db209fb8ace9301c8066c2832a8c923c81d6e0`.
This is unchanged generated-output evidence, not a newly executed game test.

All 21 patches apply through the normal checked applicator to a new clean
checkout at the locked upstream revision. The patchset digest is
`5565be6bb41a7a2d99369010d7fd83c26cd733fa35f67ce4b3aef54761d911b5`.
All five files changed by patch 0021 match the tested prototype after CRLF/LF
normalization; the Windows checkout's raw source bytes are not identical.
The new patch passes publication whitespace checks. The wider patchset
test still reports pre-existing whitespace failures in patches 0016 and
0019; those pinned files were not changed. Earlier signed producer evidence
does not cover this new series.

## Remaining work

The [bounded instruction-effect stream](phase9-instruction-effect-stream.md)
now roundtrips the actual generated fixture hooks under sanitizers, preserving
75 entry/effect pairs and unchanged results. Its Windows/Linux wire bytes
also agree. Subsequent game integration found and fixed a
[continuation hook-boundary defect](phase9-continuation-hook-boundary.md), then
qualified a complete native paired capture with whole observation-off/on
artifact equality. Oracle-side ordinary-effect qualification remains open;
neither fixture nor native stream is a hardware retirement proof.

The [native ERET transport boundary](phase9-eret-transfer-observation.md) now
has a separate runtime observer, opt-in replay artifact and executable tests.
Native observation-off/on game captures now preserve full traces, inputs and
focused RDRAM while recording 308 boundaries. The separate
[oracle ERET/Count observer](phase9-oracle-cpu-boundary-observation.md) now also
passes its bounded game qualification; this does not enable the compiler's
rejected textual ERET hook or align the engines' raw clocks.

1. Define and test actual native exception-return/thread-handoff boundaries;
   do not enable an ERET hook merely after the generated statement.
2. Implement independently checked oracle effect boundaries, including lazy
   Count updates and deferred work. Instruction entries are not completions.
3. Capture the bounded all-thread interval at invocation 1908, preserve raw
   overlay/code identity, and prove observation leaves complete update traces
   and focused RDRAM unchanged before feeding it back into diagnosis.
4. Use that evidence to distinguish the two device-ordering hypotheses, then
   prove and retest a causal repair. No VI insertion, count offset, comparison
   shift or ignored state field is authorized by this work.
