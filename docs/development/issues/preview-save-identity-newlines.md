# PREVIEW-SAVE-IDENTITY: Closer-camera preview rejects its USA save folder

- Severity: blocks launching the selected USA ROM in the private preview.
- Status: repaired locally; shipped launcher storage validator passes; owner retry pending.
- Reported: November 8, 2026 (owner local date); verified November 9 UTC.
- Affected: private issue52-combat-camera-closer-20261108 preview on Windows.
- Evidence: owner screenshot; private issue52-marker-repair-20261108 receipts.

## Symptoms and cause

Play reports that the save folder belongs to another ROM revision or has an
invalid identity. The preview-copy step decoded and rewrote all top-level text
files to relocate paths. Python's Windows newline conversion changed the
`rom-revision.txt` protocol from LF to CRLF, although it contains no paths.
`RegionalStorage.Prepare` in `launcher/windows/RegionalRom.cs` deliberately
checks its exact bytes and correctly rejected it. The existing regional-storage
tests already cover rejection of newline-normalized markers. Runtime-package
validation alone did not check this copied profile, so the prior handoff's
package checks missed the launch blocker. This is a staging error, not an N64 bug.

## Repair and verification

The original marker was first checked against the selected ROM's canonical
SHA-1 and backed up alongside the malformed file. Restored the verified marker
with a byte write. No identity check was disabled and no save was relabeled or
converted. All FlashRAM and controller-pak files retain their pre-repair hashes.

Invoked the actual shipped helper's `RegionalStorage.Prepare`: the original
CRLF marker was rejected before repair; USA, PAL and JP storage were accepted
afterward. The empty PAL namespace received its normal marker through the
production method. No game session was started; owner will retry Play and
perform the requested camera checks. The 180-unit camera build is unchanged.

Two verification harness failures are retained: the native launcher executable
is not a managed assembly (the validator lives in JFG-Setup.exe), and PowerShell
needed the concatenated profile path parenthesized in the reflection argument
array. Neither failure changed the save files. The corrected harness passed.

A corrected successor staging template is retained privately; it excludes
`rom-revision.txt` from path-text rewriting. The signed failed step is preserved.
No commit or release is claimed. Related: [combat transparency](github-combat-player-transparency.md).

## Lessons

Treat identity sidecars as byte protocols. Copy them unchanged; rewrite only
known path-bearing fields. Check the actual selected profile through the
launcher storage validator as well as checking executable/package manifests.
