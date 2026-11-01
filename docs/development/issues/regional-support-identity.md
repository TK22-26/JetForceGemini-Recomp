# Regional identity omitted from support reports

- ID: ROM-SUPPORT-IDENTITY.
- Status: candidate passes synthetic and actual all-three native-session support-ZIP exports in the committed launcher; unreleased.
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
build. Implementation commit: `5bac0c896c3e4a47456b2973994bbe7151062e77`.

The final v30 launcher was built from that commit. After actual installed-bundle
Play for each region, the installed setup assembly exported each native session
through its real support ZIP writer. All three archives retain the exact
revision, source commit and program hashes. Each contains the 11 allowed text
members, bounded sanitized logs and no private paths, ROMs or save data.
Private receipt: `regional-architecture-20261101-owner5h/actual-support-exports-v30.result.json`.
The exporter was invoked locally without UI interaction or upload. This
qualifies report contents, not every support-dialog interaction or release
availability.

## Lesson

Adding a producer log line does not update a sanitized diagnostic contract.
Test the exported report as well as the producer and preserve the same verified
session identity through selection, launch and support collection.
