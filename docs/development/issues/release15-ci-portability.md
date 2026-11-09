# 1.5.0 CI compile portability

Status: source corrections verified by complete local compiler/test runs.
Final integration checks are tracked on [PR #60](https://github.com/TK22-26/JetForceGemini-Recomp/pull/60).
Severity: release-blocking source build failure, not an observed gameplay defect.

PR #60 at source `37f09fb` exposed two failures in the first required CI run:
GCC 13.3 with AddressSanitizer/UBSan rejected the generated catalog's `consteval`
nullable-pointer test, and ordinary Linux compilation rejected a copying
structured-binding loop in the native ROM DMA regression under warnings-as-errors.
Evidence: [CI run](https://github.com/TK22-26/JetForceGemini-Recomp/actions/runs/42567794764).
The Windows lane independently received HTTP 504 while downloading its pinned
SDL archive; that network failure is not evidence of a compiler defect.

Both source failures reproduce with the same compiler options in isolated local
checks. The catalog's immediate lookup now returns a matching array entry directly
and still rejects unknown revisions during constant evaluation. Runtime nullable
lookup, ROM identities and catalog data remain unchanged. The DMA test binds each
pair by const reference. No warning, sanitizer or required CI check was disabled.

After correction, the catalog consumer and all-three-region descriptor static
assertions compile with both sanitizers; the DMA fixture compiles with the full
warning set. A negative compile confirms unknown revisions are still rejected.
Private evidence: `release15-merge-20261109/before-catalog.log`, `before-dma.log`,
`after-catalog.log`, `after-dma.log`, `after-descriptor.log` and
`unknown-rejected.log`. Full remote CI remains authoritative for the merge.

Lesson: a passing Windows runtime build does not qualify generated constant
expressions for GCC sanitizer builds. Keep compile-time catalog use covered for
every region and preserve strict warning checks in test targets.

## Complete build follow-up

The next CI pass reached a shadowed lambda parameter in the rumble fixture.
A complete local strict GCC build additionally found an implicit unsigned-to-float
conversion and misleading fixture indentation in the existing flight tests.
The candidate renames the fixture parameter, makes the existing numeric conversion
explicit, and separates statements. Flight behavior and the owner's #48 deferral
are unchanged. These are compiler portability corrections, not new gameplay fixes.

The SDL GitHub asset returned HTTP 504 in both CI attempts. The official SDL
release origin supplies the identical 2.26.3 VC archive: its SHA-256 matches the
existing dependency pin. CMake now tries that origin, retaining GitHub as fallback
and keeping hash verification. No dependency version or workflow gate changes.
The complete local strict GCC build, CTest suite (with the existing CI trap-probe
quarantine), and a fresh Windows CMake SDK fetch pass. Full remote CI remains
pending. Private receipts: `linux-build-fixed.log`, `linux-ctest.log`,
`sdl-origin.json` and `sdl-cmake-fetch.log`.

The subsequent sanitizer build exposed one more narrowing warning in the synthetic
resident-memory fixture: two bytes are combined as an `int` and returned as a
16-bit word. The fixture now makes that bounded conversion explicit. The complete
local ASan/UBSan build and enabled CTest suite pass; no production memory behavior
changes. Evidence: `asan-build.log` and `asan-ctest.log` in the same private record.

The CI GCC Debug and Release builds then passed all 121 enabled tests each.
Clang's separate warning lane found implicit signedness conversions in ROM-address
operand composition and exit-level decoding. Explicit unsigned conversions retain
the existing modulo-32-bit signed-immediate behavior and byte-shift result.
The ROM-assets test already checks a negative immediate. The installed local Clang 21 also reports conversions in the CIC nibble mask,
shadow-count result and signed guest-register arguments. These conversions are
now explicit, preserving the nibble mask, nonnegative count and MIPS sign extension.
No warning policy or gameplay behavior changes. The initial local Clang configure
used a distribution without Clang; its failure is preserved. A subsequent build
folder under temporary Linux storage disappeared between calls, so final checks
use persistent private build directories. Complete Clang 21 Release and GCC
ASan/UBSan builds and enabled test suites pass. CI uses Clang 18 independently.
Evidence: `clang-persistent-build.log`, `clang-persistent-ctest.log`,
`asan-persistent-build.log` and `asan-persistent-ctest.log`.
