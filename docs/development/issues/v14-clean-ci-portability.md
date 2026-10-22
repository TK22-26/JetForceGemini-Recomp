# v1.4.0 clean CI portability checks

- Status: supported-platform CI passed for the corrected source; release preparation complete subject to final source checks and owner signoff. Unreleased.
- Discovered: 2026-10-22, release PR #42, initial CI run 39709407647.
- Severity: release build gate; no observed gameplay regression.

The first all-platform run rejected omitted `Fade::spatial` initialization under
GCC's missing-field-initializers warning in the Linux and sanitizer jobs. MSVC
accepted the same aggregate. An explicit default member initializer preserves
the existing zero/default spatial state and makes the intent portable; warning
levels and warnings-as-errors are retained. Existing rain-fade tests cover the
behavior and are rerun in CI.

The clean Windows renderer job also rejected the pinned RT64 render-target
source because it checked raw file bytes. The local upstream file used LF;
the Windows runner checked out CRLF. The source pin now normalizes CRLF to LF
before hashing, matching the project's existing pin policy. The expected source
digest is unchanged. A local CMake fixture runs the actual pin block against
the original LF and CRLF inputs and a content mutation: both encodings pass,
and the mutation is rejected. No dependency revision or pin is relaxed.

The reviewed gameplay candidate was preserved. Packaging was stopped before
the obsolete source could be called release-ready. Initial CI logs, fixture
outputs and exact build identities are retained privately under
`v14-final-release-20261022`; replacement artifacts must identify the corrected
clean source. Full CI is required before the owner's final publication signoff.


The second CI run (39710195968) passes all 107 GCC Debug tests, all 107 GCC
Release tests and the sanitizer lane. Clang then rejects a signed char-to-unsigned
conversion in the new camera-helper test fixture. The fixture now explicitly
converts the ASCII name byte to uint8_t before writing it, matching the guest
byte representation. This changes test construction only, not runtime code.
Warning strictness is retained; a fresh complete CI run is required.


The third run (39710786459) passes GCC Debug/Release and sanitizers but reaches
three additional Clang signedness warnings in cutscene code: an int row used as
an array index and a promoted uint16_t command byte passed as unsigned. Explicit
size_t/unsigned conversions preserve their already-bounded positive values.
A local complete Clang build is used to collect further diagnostics together;
no compiler warnings are disabled. This is separate from the recorded WSL
trust-anchor limitation in the private sanitizer harness; those pins stay intact.


The local WSL compiler is Clang 21.1.8, newer than CI's Clang 18. The full
keep-going build compiles all changed cutscene/rain/helper tests and reports
one unrelated warning in the unchanged CIC implementation's integer promotion.
That newer-compiler limitation is retained, not silently treated as a passed
whole build. Five focused cutscene, rain and fog suites pass locally. The helper test
compiles but cannot link because its runtime library depends on that unchanged
CIC object; its local Not Run result is retained, with full execution left to CI.
The existing CIC source and warnings-as-errors are unchanged; CI's supported
compiler remains the full-build gate.


## Final supported-platform verification

[CI run 39711677000](https://github.com/TK22-26/JetForceGemini-Recomp/actions/runs/39711677000)
passes all six jobs on `521f66620e734671a06a07f118e874076f02a133`: Linux
GCC Debug/Release and Clang, Windows Debug/Release, Linux sanitizers, the Windows
RT64 renderer, launcher, and policy/schema/Python checks. The clean native Windows
Release build and cutscene/helper/rain suites also pass locally. No warning,
source pin or test assertion was disabled to obtain those results.

The local Clang 21 CIC warning remains a documented newer-toolchain limitation;
it does not apply to the supported Clang 18 CI result. The final documentation
commit receives its own PR checks before signoff. Main merge and publication
remain unapproved.
