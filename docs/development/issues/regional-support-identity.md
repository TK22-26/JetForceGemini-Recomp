# Regional identity omitted from support reports

- ID: ROM-SUPPORT-IDENTITY.
- Status: candidate passes actual support-ZIP export tests in the rebuilt launcher; native-session report check pending; unreleased.
- Affected: development launcher support reports for all three regional runtimes.
- Severity: diagnostic limitation; does not itself change gameplay.

## Cause and remedy

The regional launch paths wrote `rom_revision`, but the support sanitizer did
not admit that field. The report silently dropped the selected revision. The
native program's build, model and generation identities were also absent.

The sanitizer now derives permitted revision IDs from the shared ROM catalog
and admits only three fixed-size program hash fields. Both launch paths record
the identity from their existing verified program lease. No extra runtime query,
ROM path, game data or save contents are included. Validation completes before
writing any identity field.

## Validation and limits

Synthetic all-three export tests exercise the actual support ZIP writer, exact
revision and hash retention, malformed/private canary rejection and invalid
identity rejection without partial output. All 748 launcher checks, 28 setup
checks, graphics/viewport tests and 23 storage checks pass in the v29 launcher
build. The actual regional native-session report checks are still pending.
Release availability remains separate.

## Lesson

Adding a producer log line does not update a sanitized diagnostic contract.
Test the exported report as well as the producer and preserve the same verified
session identity through selection, launch and support collection.
