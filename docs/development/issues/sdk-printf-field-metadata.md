# Missing SDK printf field metadata

Status: local candidate; fresh generation, contract tests and actual formatter execution pass. Final native gameplay qualification passes. Discovered
during the flying-enemy timing qualification on 2026-10-27. No release claim.

## Symptoms and evidence

Two copied-profile Tawfret death replays exited at unresolved guest address
0x8009BE20 after the flyers had died. The final stack identified the original
Sound state allocate failed - sndId %d warning. Another candidate replay and
the paired previous executable completed. This does not establish that the
movement change causes the sound-state shortage.

Private artifact ID: flying-timing-fix-20261027, including
print-stack-analysis.json, printf-field-disassembly.txt and the two failed
replays. ROM, generated code, RAM and personal saves remain private.

## Cause and remedy

The pinned upstream ELF omits FUNC metadata for static libultra _Putfld,
although _Printf calls its original ROM body. The output callback repair
already present in the host cannot handle a failure earlier in the formatter.

Extend the existing SDK metadata recovery pipeline with the exact original
function boundary. Check the pinned ROM body and complete switch table,
direct branches, allowed callees and original caller. Add only ELF function
metadata, proving that all allocated bytes remain unchanged, then regenerate
normally. Do not suppress the sound warning or replace its formatting logic.

## Validation and limits

ROM-free negative boundary/call/table tests added. Fresh generation, native
replay and warning formatting checks pending. The sound-allocation warning is
a separate condition; restoring its formatter must not be reported as fixing
the audio pool. A complete game-function catalog needs static-local helpers as
well as externally named functions.

The transitive formatter audit also found missing static _Genld metadata in
the floating conversion path. Recover that original body too, with its checked
memcpy calls and explicit unreachable return suffix. Both restored bodies have
unchanged ROM instructions. Inventory increases by two functions, ten direct
calls, three returns and one switch; two existing unresolved calls now resolve.
Older acceptance manifests remain historical evidence for their original roots.

The first floating-helper boundary check rejected a branch into a delay slot.
Disassembly confirms a legal shared SLTI instruction, reached both normally and
by the general-format branch. The checker now permits only that explicitly
qualified slot for this pinned body, with a separate negative test. The default
boundary policy remains strict; no unchecked branch or changed instruction is
admitted.

## Generation and focused execution checks

Both recovered functions regenerate successfully through the normal context,
transform and normalization stages. The current inventory contains 2,911
authoritative bodies and 3,628 indirect-transfer sites. All six SDK helper
recoveries remain required for a fresh ROM build. No old acceptance manifest is
relabelled as acceptance of this new inventory.

A private execution probe compiles the actual regenerated formatter and its
14-function direct-call closure against original RAM constants. Five cases pass:
the reproduced sound warning, signed/unsigned/hex integers, strings/characters/
percent, fixed/scientific floating point, and general-format floating point.
Returned character counts and all output bytes match the expected strings,
including Rare's terminating NUL. The general-format case exercises the
explicitly qualified shared delay-slot entry.

The first probe attempts had harness setup failures: a forced timing-header
include preceded declarations, the resident section base was uninitialized, and
the floating-point odd-register pointer was missing. These were corrected to
match the native runtime's existing initialization. They are not game regressions.
Private probe histories are preserved. The five relevant Python generation
contract suites pass; the helper suite has 17 tests, with two platform-specific
cases skipped on Windows. Final native warning-path replays remain pending.

An optional ASan/UBSan optimized build of the private formatter probe exceeded
its 120-second compile limit; it is not counted as a sanitizer pass. Its owned
compiler was checked/cleaned up. The ordinary five-case execution test passes.
The earlier diagnostic sanitizer run identified the harness's unset FP pointer,
not an access fault in the normal initialized game runtime.

## Private build preparation failure and correction

The first final optimized-runtime build stopped at the existing collision-source
digest check. The fresh normalized root had instruction timing hooks but omitted
the separate native-span preparation required by this private optimized build
configuration. Applying the existing finish_native_spans step restores the
previously qualified collision, shadow-filter and cache-helper source hashes
exactly. No source digest, extraction rule or game instruction was relaxed.

The failed build receipt is retained. Rebuild and gameplay qualification must
finish before handoff. Fresh ordinary generation and private optimized generation
have distinct preparation requirements; reuse the exact selected configuration
when replacing a generated root. This was an orchestration error, not evidence
of a collision or flight-physics regression.

## Final native qualification

The prepared final runtime completes all twelve flight/death/control replays and
an ordinary hosted-launcher Play/close check. The replay set records 21 guest
print-sink callback calls without an unresolved-target failure. This count does
not identify every printed message; the focused five-case formatter probe is
the exact warning-text/format validation. The native sound-pool limit itself is
not changed or claimed fixed. Source qualifications remain unchanged after the
required private span preparation. This repair remains unreleased.
