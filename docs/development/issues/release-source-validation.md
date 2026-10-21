# BUILD-003: Release source validation

Status: resolved for the v1.2.0 release source/build qualification; original failures and platform limits retained below.

Release validation found unregistered controller-prototype rasterizations and launcher screenshots, numeric opcode/section identifiers mistaken for hex payloads, synthetic compiler fixtures mistaken for generated game code, and a repeatedly mis-encoded prototype filename inflating one feature-note line beyond 3 MB. These block publication, not gameplay.

The filename is repaired in the current document; historical evidence remains intact. Exact SHA-256 and Git blob records in `scripts/reviewed_hygiene_bodies.json` document the inspected assets and narrowly scoped historical false positives. No suffix-wide binary exemption or credential/ROM/archive exemption is introduced. Mutated fixtures and artwork must fail again. The controller artwork originates in the owner-provided editable prototype documented beside its SVGs; screenshots show the project launcher/settings.

The all-object local history scan additionally sees private stash objects that are never part of a pushed release. Qualification will scan a clean isolated clone of the committed release history, preserving the local stash and all original counters. No history rewrite is performed. Initial failed policy logs remain in the private release qualification directory.

Lesson: register exact UI asset provenance when adding rasterizations, and keep generated game bodies out of public fixtures. Preserve UTF-8 explicitly when updating documents. Release-history scans must be performed on the actual publishable clone, not confused with private local stash objects.

## Verified candidate scope

Current policy, exact-body mutation regression tests and schema validation pass. The external-output launcher test harness is corrected; the first link probe was missing input_stick.cpp and its corrected link passes. The complete published-history clone remains a pre-push check.

## Full CI portability follow-up

The first release PR CI found LP64 narrowing in the randomized runlink fixture:
std::mt19937 produces 32-bit values but exposes unsigned long on GCC/Linux. The
fixture now explicitly obtains uint32_t words. GCC also requires explicit default
initialization for omitted aggregate pose members; they now have `{}` initializers,
preserving the previous value-initialization behavior. These are compile defects,
not observed gameplay regressions. The initial failed CI run is retained as
38977882410. Full host GCC/CTest qualification is required before the follow-up push.

The follow-up CI passed GCC Debug and Release (99 tests each), then caught signed
fixture indexing under Clang and promoted byte-expression narrowing under the
sanitizer compiler. The fixture explicitly validates/casts nonnegative indices;
the bounded two-byte read explicitly narrows its combined result. The byte values
and camera/reticle behavior are unchanged. Failed run 38978308958 is retained.
Full Clang and sanitizer build/test coverage is required before the next push.

The full local AddressSanitizer + undefined-behavior build passes all 84 tests
in the CI scope (the existing isolated trap-probe quarantine is unchanged).
Clang is not installed in this WSL distribution, so its configuration failed
before compilation. Clang validation remains a required GitHub CI job; no compiler
warning, required check or production guard is disabled to work around that absence.

The next CI run (38979091192) passed policy, both Windows builds, RT64,
launcher and sanitizers; Clang found three further signed controller-fixture
indices. The test already asserts the slot equals 5 before indexing, and now
casts that checked value explicitly. The complete local build then found one
unsigned iterator distance in billboard history; its existing bounds check
remains intact and the distance now uses the vector iterator difference type. A private official Ubuntu Clang 18.1.3
toolchain, downloaded and extracted without installing system packages, then
built the complete host target set with warnings as errors: **100/100 tests
passed** locally. The complete ASan/UBSan scope passed 84/84. No warning or CI
gate was disabled. Final CI and publication remain independent release gates.

Transferable lesson: GCC, Clang and MSVC differ in aggregate and signedness
diagnostics. Run each supported compiler over all fixtures before publication;
checking only the native game translation unit cannot validate the host suite.

## Published release verification

Available in [v1.2.0](https://github.com/TK22-26/JetForceGemini-Recomp/releases/tag/v1.2.0), built from `f56cd94c4bd7583bceee201eb3f229f744216bc1` after
[PR #16](https://github.com/TK22-26/JetForceGemini-Recomp/pull/16) merged. The
[tagged-release workflow](https://github.com/TK22-26/JetForceGemini-Recomp/actions/runs/38981221560) passed its full checks, verified the prebuilt
Windows bundle and published it. The public download was downloaded again and
its ZIP, per-member hashes, package inventory and clean runtime identity verified.
This release includes the remedy and finite verification described above; it
does not expand the recorded hardware, Linux, campaign or fresh-install coverage.

The final desktop verification initially expected a four-component version
string. The native launcher correctly reports `1.2.0`; its numeric PE fields are
1, 2, 0, 0. The check now verifies those fields and the preserved shortcut
arguments, without changing the published package. Original failure retained
in the private publication receipts.


## v1.2.1 publication record

Tagged-source CI and the prebuilt publication workflow pass; the downloaded public assets match the staged hashes and bundle manifest. The issue index accidentally replaced INPUT-011's link cell with a status sentence during release preparation. This documentation-only follow-up restores the link and records actual publication/reporter-retest status; the published tag and binaries remain unchanged. See [boss-control release evidence](github-ichor-boss-controls.md).

## v1.3 preparation

The current source-policy preflight found two owner-specific paths in new issue notes, a new unregistered project UI icon atlas, and generated-marker matches in three small handwritten synthetic compiler fixtures. Public notes now use private artifact names; exact-body reviews cover the atlas/fixtures with mutation rejection intact. No generated game body, ROM, save or capture is added. Final current-tree/history, compiler, package and CI qualification remain pending in [the v1.3 checklist](../releases-1.3.0-qualification.md).

## v1.3 release CI: randomized fixture width

The first v1.3 PR run fails Linux compilation in semantic_presentation_tests:
mt19937::result_type is unsigned long on LP64, so randomized fixture addresses
narrow implicitly to uint32_t under warnings-as-errors. Windows uses a 32-bit
unsigned long and did not expose the problem. Explicitly convert the generator's
specified 32-bit output at the fixture boundary; retain its seed, sequence,
assertions and all warnings. No runtime/game code changes. GCC/Clang checks and
fresh CI are required before publication. Original failed CI is retained in PR #27.

The corrected randomized fixture compiles and passes under host GCC and Clang.
The Windows renderer CI also rejected the pinned timer source because its hash
was taken before CRLF normalization. Hash the canonical LF text, as the other
strict dependency patches do. LF and CRLF copies produce identical patched units;
a changed source is still rejected. The dependency revision and timer behavior
are unchanged. An initial fixture configure could not locate Ninja; the standard
Visual Studio generator completed all three checks. The authenticated fatal-bridge
test passes locally with Clang; its initial CI failure remains recorded and
requires a fresh full CI result. No authentication assertion or CI gate is relaxed.

The final v1.3 source CI run 39205989097 passes all six jobs. The unchanged
authenticated fatal-bridge test passes in the complete CI suite as well as the
focused host Clang run; no root cause was established for its first-run failure.
That failure remains an intermittent validation observation, not a claimed game
fix. Canonical timer hashing and explicit random-output widths are verified on
both supported host platforms without relaxing compiler warnings or source pins.

## v1.4 final-pass candidate

Five worktrees are reconciled into develop without dropping unique paths or
commits. The combined Release runtime and all 123 native/renderer CTest suites
pass; managed/native launcher checks also pass. See the
[v1.4 qualification](../releases-1.4.0-qualification.md) for counts and limits.

The 1,807-test local Python run retains the same two sanitizer subtest failures
and one WSL trust-anchor error documented for v1.2. The installed Microsoft-signed
WSL 10.0.26100.8737 differs from the repository pin; the harness/test source is
unchanged. No trust boundary was repinned or bypassed. Affected-host harness
qualification and full CI remain separate from the Windows final-pass package.

Source-policy review registered exact owner-generated skip artwork and removed
personal video directories from current notes. Existing public historical notes
have exact-body path-only exceptions. Private unreachable/archive objects are
preserved locally and excluded from the clean public-history fetch, not added to
public exceptions. Native game source, ROMs, saves and captures remain excluded.
