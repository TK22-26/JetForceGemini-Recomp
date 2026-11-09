# TOOLING-PORTABILITY-20261027: Local batch validation limits

- Severity: build/test portability; no observed gameplay regression.
- Status: GCC Release build and 108 tests pass; WSL boundary suite passes with explicit integration skips.
- Reported and updated: 2026-10-27 UTC.
- Affected: unpublished local rendering batch, GCC 13 warning-as-error builds;
  Windows production-evidence integration tests on an updated WSL executable.

## Evidence and cause

The Windows Release build and its CTest suite passed. Linux Release compilation
reported misleading indentation in the new actor-LOD, shadow settings and shadow
capture headers, a shadowed test-local variable, and an omitted optional camera
aggregate initializer. They are compiler portability defects, not new runtime
behavior discoveries.

The complete Python suite ran 1,807 tests with 48 skips and failed two sanitizer
subtests plus one WSL boundary test. The installed Windows WSL executable differs
from the production evidence harness's repository hash pin. That rejection is
correct; it must not silently repin a system tool or weaken production checks.

## Local remedy and validation

Separate the misleading statements, name the test address clearly, and explicitly
initialize the already-empty optional camera motion pose. These preserve behavior.
The WSL unit test now injects a known test payload and test-only pin while still
checking the fixed executable path and rejecting a mutated private execution copy.
The sanitizer integration test explicitly skips if its exact production WSL
boundary is unavailable, before attempting its build. Production pins and execution
policy are unchanged. This skip is a validation limit, not sanitizer success.

Private evidence: remaining-gh-issues-20261027/final-checks-060.json,
final-linux-061.json and the corresponding logs. The corrected Linux Release build passes, as do all 108 non-quarantined CTest cases. The WSL boundary suite passes 29 tests with three explicit environment/toolchain skips, including the unavailable pinned WSL sanitizer integration. Private rerun evidence: portability-checks-066.json. After the Floyd remapping correction, all 115 Windows Release tests pass; the Linux rebuild and affected control tests pass. The full Python suite passes 1,807 tests with 49 environment/platform skips. The native renderer/runtime and RT64 texture tests also pass. The existing Linux G2 trap-probe quarantine is retained, not relabeled as tested. Final repository hygiene, schema validation and whitespace checks pass.

## Compatibility lesson

Compile portable headers with GCC's warning-as-error policy as well as MSVC.
A trust-boundary unit fixture should not depend on a serviced OS binary hash;
real pinned-tool integration coverage must report an unavailable boundary honestly.
