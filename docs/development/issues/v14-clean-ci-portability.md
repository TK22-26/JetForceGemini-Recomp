# v1.4.0 clean CI portability checks

- Status: two build corrections applied; clean CI rerun pending. Publication blocked until checks pass.
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
