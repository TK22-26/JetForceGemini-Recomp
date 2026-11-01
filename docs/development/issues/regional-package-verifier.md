# Regional package verifier format mismatch

- ID: ROM-PACKAGE-VERIFY.
- Status: corrected locally; all 38 release tests pass; unreleased.
- Affected: development regional package builder and draft-release verifier.
- Severity: blocks verification/publication of a correctly built regional archive.

## Symptoms and reproduction

The package builder emits a schema-2 package index with revision directories,
per-revision program manifests and runtime source identities. The release
verifier still requires schema 1, root-level game binaries and a single runtime
source. A valid regional archive therefore fails the publication verification
gate. No release was attempted or published during this investigation.

Run the release verification tests against a schema-2 bundle. The old fixture
also omits the now-required program manifest, so its setup must move onto the
shared synthetic regional bundle contract before it can test the actual gate.

## Cause, remedy and validation

Confirmed source cause: package generation migrated without its downstream
release verifier. The correction must validate every declared revision, exact
manifest and member digest, revision identity, complete runtime libraries and
clean build receipt. It must reject duplicate, mismatched, unsafe, missing or
extra data while retaining release-tag and checksum checks. Original game
bytes and private saves are never valid package inputs.

The verifier now consumes schema 2 and validates each exact regional program
manifest, full runtime inventory, clean support identity and source inventory.
All 38 release tests pass, including each single-revision package and one
three-revision producer-to-verifier roundtrip. Negative cases cover wrong
revision, duplicate entry, stale manifest hash, missing CRT, undeclared runtime,
dirty receipt, mismatched source inventory and unsafe paths.

The baseline had seven fixture setup errors because it lacked program
manifests. The first corrected release-suite run also exposed an old stable
package test reusing an existing archive path; a separate fixture destination
now reaches the intended dirty-source rejection. Both failures are retained in
private evidence (`regional-release-baseline`, `regional-release-v28`).

A passing archive check
does not authorize publication or establish regional gameplay acceptance.

## Lesson

Treat package producers, installed-package readers and publication verifiers
as consumers of one versioned artifact contract. Exercise the real producer to
verifier path, including all three revisions and single-revision packages.
