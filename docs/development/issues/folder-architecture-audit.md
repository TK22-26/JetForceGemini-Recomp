# ARCH-20261031: Repository organization and documentation consolidation

- Severity: medium for misleading instructions and the obsolete packaging contract; low for folder layout and caches.
- Status: implemented and validated locally on `develop`; no release or remote issue change.
- Reported/updated: 2026-10-31 UTC. The owner approved the complete reorganization, documentation and commit within one two-hour allowance.
- Audited baseline: `db9ea90b41b9bf14d806ab6aea1aefbddbb80efa`, with the owner's existing NTSC/PAL correction preserved.
- Scope: every tracked file plus the physical checkout inventory; remove by default unless a current consumer, unique knowledge, evidence contract or distribution obligation justifies retention.

## What was wrong

The repository accumulated flat tool/test directories, duplicated status pages and release
procedures, and long feature pages mixing current instructions with dated investigation notes.
The source audit reproduced these specific defects:

- The Quarry desktop command referenced a missing private script and a machine-specific interpreter.
- The dashboard still described v1.3.0 while the source and retained qualification recorded v1.4.0.
- The launcher-only packager expected 117 receipt inputs while the builder declared 140. Its exact-set
  contract could not accept that builder. The playable release workflow already used a different packager.
- One archived known-issues snapshot had 35 broken relative links after an earlier move.
- Root CMake declared the same experimental timing option twice. Generic and Xbox controller artwork
  were byte-identical 2,458,924-byte payloads embedded separately.
- Twelve lines in five Markdown files contained malformed punctuation/encoding. Several guides still
  described merged changes as separate branches or repeated superseded pending states.

The actual maintenance cause was competing ownership and duplicated contracts, not a demonstrated
new gameplay defect. The remedy assigns canonical homes, removes the obsolete implementations and
updates every known import/build/receipt/documentation consumer together.

## Audit coverage and retention

The initial inventory covered 26,663 regular files: 1,589 tracked, 18,694 ignored and 6,380 root Git
metadata files. All 1,558 tracked text files were indexed (319,498 lines); 31 tracked binaries were
hashed. The content scan hashed 19,048 non-Git files without read errors or concurrent changes.
The external production-ledger junction was recorded as a boundary, not traversed for cleanup.

[File dispositions](../repository-audit.csv) record every baseline tracked file and new canonical
entry. [Repository layout](../repository-layout.md) explains the ownership and retention rules.
This is file/content/dependency coverage, not line-by-line certification of all gameplay semantics.
Reference searches are supporting evidence; dynamically selected probe families cannot be declared
dead solely because a literal filename search finds no caller.

All 936 audited, unchanged Python cache files were removed (16,676,755 bytes). The last six belonged
to deliberately retired packager sources and were removed only after checking their original hashes.
Downloaded dependencies, build outputs, private evidence, ROMs, saves, upstream Git repositories and
the operational ledger remain outside source cleanup. Distinct distribution licenses and the
separate baseline/patch link fixtures remain even where content matches.

## Implemented organization and removals

- Tools now live in build, release, validation, evidence, diagnostics, exploration and verification
  domains. The existing `scripts.<tool>` import API remains available; seven small root CLI entries
  preserve published setup workflows. Dynamic autonomy tool identities include their package support.
- Python and C++ tests are grouped by responsibility. Package-aware discovery retains every current
  test; eight checks specific to the removed launcher-only packaging/publishing path were retired.
- Windows frontend and video settings source now live with their owner in `launcher/native`; its
  three C++ test files live in `launcher/native/tests`. Public source snapshots include that domain.
- Renderer CMake helpers and targets live under `cmake/renderer`; generated/native targets live in
  `cmake/NativeTargets.cmake`, and test groups in `tests/cmake`. The duplicate option was removed
  without changing its default.
- Removed `Play Quarry Cutscene.cmd`, the launcher-only packager/publisher, and three unreferenced
  legacy Phase 9 PowerShell workflows tied to an absent Phase 8 build layout. Shared version/tag/source
  checks now live in `scripts/release/release_metadata.py`; playable packaging remains authoritative.
- Generic controller art now aliases the Xbox resource. Resource 215 stays reserved, so later IDs
  do not shift; the standalone UI preview materializes the alias in its build output.

## Documentation and original-game findings

The main README, documentation/development indexes, status, known issues, controls and release
procedure were rewritten or consolidated. Runtime implementation notes, maintainer procedures and
version qualification have separate homes. Redundant dashboard/release guides and known-issues
snapshots were removed; useful Tawfret, weapon-grant, combat and high-refresh findings were merged
into their existing issue records. Obsolete beta instructions became a focused release-history
record preserving the missing-runtime and software-GPU failures. The issue index now links every
record without repeating a chronology of contradictory preview statuses. Historical research remains
in canonical issue records and immutable Git links.

The [original N64 catalog](../../original-game/README.md) records the physical-hardware Tawfret
camera-helper bug and its intentional v1.4.0 correction. It separately records NTSC Walkway silence
on hardware and PAL music in EmuHawk. PAL hardware and Japanese behavior are untested; the regional
code/asset cause is unknown. The US music insertion remains pending a separate removal/validation,
and PAL/JP recomp support remains separate future work. No gameplay change was made by this reorganization.
The Audio Settings replacement remains owner-accepted locally, with the original delay cause unknown.

## Attempts, failures and final validation

Initial migration checks exposed real path/contract failures: imports resolved the compatibility
wrapper instead of the domain implementation; moved test fixtures still staged the old hierarchy;
C++ tests had old relative headers; a dynamic CMake test path still named the former folder; and CI's
policy validator expected the old discovery command. Those consumers were updated, not disabled.
A conservative import-consolidation pass rejected inconsistent indentation before writing that file;
the corrected pass used actual AST indentation. An early documentation newline conversion expanded
paragraph spacing; original paragraph boundaries were restored from the retained baseline.

Historical Phase 4 fixtures initially tried to replay the current tree as the old archive layout.
The historical archive names and pins were restored; a mocked context-failure test now uses a synthetic
legacy-layout closure. Phase 5's signed record still authenticates, while the changed current source
set is explicitly reported as drift. Signed milestones were not rewritten to make this tree appear
historically qualified. Two exact hygiene fixture hashes were updated only after confirming their
hex literals were unchanged; no scanner exemptions were broadened.

| Final check | Result and limit |
|---|---|
| Python discovery and suite | 1,819 discovered cases; 1,801 tests reported, including 49 documented/environment skips; passing. Baseline discovery was 1,827, with only eight retired packager tests removed. |
| Windows MSVC native Release | Build passes; all 118 CTest cases pass, including synthetic generated-code rejection/build fixtures. |
| Pinned RT64 integration | Build passes; all four renderer CI suites pass. The upstream checkout is unchanged. |
| Launcher | Actual executable builds; 690 managed, 28 setup, six graphics-adapter and 23 storage checks pass, plus viewport cases. |
| Native UI | 1,015 Modern controls, 305 controller-mapping, 104 menu-input and 64 Audio checks pass; isolated profiles/desktops avoid owner input. |
| Project validation and entry points | Schema/policy/hygiene validation and root/domain CLI checks are recorded in the implementation receipt. |
| Candidate branch history | Isolated baseline develop history plus the identical staged candidate passes the history scan; retained local archive/stash objects remain a separately recorded limitation. |
| Preserved evidence | All 96 protected contract/evidence files match their pre-migration hashes. Existing user edits were backed up before changes. |

Private audit ID: `folder-architecture-audit-20261031`; implementation ID:
`reorganization-implementation-20261031`. These retain the original inventories and per-file report,
backup/bundle/hashes, guarded step scripts, failed and passing logs, cache-removal receipt and final
validation. The production guard remained enabled under the same investigation and all earlier
charges; this work does not reset or reopen its budget.

The full local-object history scan additionally found retained archive/unreachable objects and
stash timestamp metadata outside the baseline `develop` history and proposed index. Those findings
are recorded separately in [repository history hygiene](repository-history-hygiene.md); the
current-source hygiene gate passes. History was preserved and scanner rules were not weakened.
The first staged whitespace check also caught three truncated CSV descriptions ending with a
space; the descriptions were trimmed before the final staged check.

## Compatibility limits and follow-up

This validates the reorganized Windows source, launcher and renderer. It does not claim a new Linux
build, full private ROM-to-game regeneration, gameplay playthrough or release qualification. Old
private scripts with retired physical paths need migration; the seven published root entry points
and established Python module API are preserved. Historical signed evidence applies to its named
source; fresh current-source milestone qualification would require new evidence.

The large native runtime remains a deliberate follow-up: splitting state, thread ownership,
callbacks and generated ABI needs semantic review and private-runtime validation. Moving files is
not proof that this deeper refactoring is complete. Future changes should give each contract one
owner, migrate consumers atomically, check links from their actual parent, preserve resource IDs,
and distinguish hardware evidence, emulator evidence, tested changes and live acceptance.
