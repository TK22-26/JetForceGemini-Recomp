# ROM and game-asset handling policy

- Status: Mandatory Phase 0 policy
- Last reviewed: 2026-08-03
- Approval authority: Human maintainers

This policy is an engineering control, not legal advice. It intentionally uses
a conservative default while permissions and distribution questions remain
under human review.

## Core rule

Users must supply their own lawfully obtained supported ROM. The project does
not provide, locate, download, transmit, or bundle ROMs or game assets.

No ROM-derived expressive data may be stored in Git or any GitHub feature,
including a private repository. Private repository visibility does not make
such material acceptable.

## Material prohibited from Git and GitHub

The following MUST NOT appear in commits, branches, tags, stashes submitted for
review, issues, discussions, pull requests, comments, snippets, Actions logs,
job summaries, artifacts, caches, releases, packages, container images, or
attestations:

- Complete ROMs, partial ROM ranges, patches containing recoverable ROM bytes,
  byte dumps, or encoded/compressed/encrypted equivalents.
- Extracted textures, models, animations, level data, fonts, text, video,
  music, sound effects, or other game assets.
- Screenshots, framebuffers, PCM captures, display lists, RSP/RDP buffers, or
  memory snapshots.
- Emulator save states or save files containing copied game data.
- Generated C, disassembly, decompiled source, or other expressive output
  derived from ROM code pending an approved distribution decision.
- Unlicensed upstream source, headers, or exported symbol files.
- Crash dumps, evidence bundles, or logs containing any of the above.

The prohibition applies even when data is transformed, truncated, encrypted,
base64 encoded, placed in Git LFS, or hidden inside a binary archive.

## Permitted tracked information

After review, the repository may track:

- The published cryptographic hash, byte order, and size of a supported ROM.
- Validation code that reads a user-selected local file without uploading it.
- Project-authored schemas, synthetic fixtures, and non-expressive test input.
- Repository URLs, commit IDs, tool versions, aggregate counts, and
  project-assigned opaque IDs when they do not reproduce protected content.
- Under the current conservative boundary, new feasibility artifacts do not
  add target-specific ROM, VRAM, section, entrypoint, or table coordinates;
  those regeneration inputs remain local. A human must separately audit
  reachable history before authorizing any future public publication.
- Scripts that regenerate private material locally from the user's ROM.

A hash or structural fact being permitted does not authorize publishing its
underlying data.

## Local storage

ROMs and derived data belong only in ignored local storage such as:

- `roms/`
- `extracted/`
- `assets/private/`
- `generated/`
- `src/generated/`
- `corpus/private/`
- `captures/private/`
- `artifacts/private/`

Private inputs SHOULD be stored outside the checkout where practical and
mounted read-only for tests. Tools MUST avoid printing absolute paths,
directory listings, file contents, or environment details involving these
locations.

The project MUST NOT silently search broad filesystem locations for ROMs. A
user supplies an explicit path or selects a file through the application.

## Runtime and packaging behavior

- The application validates the supported ROM locally before extraction or
  execution.
- Unsupported inputs fail with a non-identifying error containing expected and
  observed public-safe metadata only.
- Temporary decrypted or extracted material uses a private local directory and
  is deleted on successful shutdown where practical.
- Crash reporting is opt-in and redacts paths, memory, ROM bytes, save content,
  and personal or machine identifiers before transmission.
- Release packages contain no ROM, extracted asset, private test body, or
  unapproved generated output.

## Automated enforcement

Before ROM-backed development is accepted, the repository requires:

1. Ignore rules for every private directory.
2. A tracked-path check that fails if a private path is committed.
3. Content scanning for known ROM hashes, N64 ROM headers and byte-order
   variants, high-risk archive types, private corpus signatures, and generated
   output markers.
4. A test suite containing harmless canaries for every detection rule.
5. A release scan of source, binaries, debug symbols, archives, installer
   payloads, logs, notices, and SBOM inputs.

Scanners supplement human review and may not independently classify material
as legally distributable.

## Incident response

If prohibited material reaches Git or GitHub:

1. Stop affected workflows and block further distribution.
2. Notify maintainers through the private security-reporting process.
3. Restrict access to affected branches, artifacts, caches, packages, and
   releases.
4. Preserve only non-expressive incident metadata needed for response.
5. Remove hosted artifacts and coordinate any necessary history cleanup with
   GitHub and human maintainers.
6. Rotate credentials if the incident could also have exposed secrets.
7. Verify removal with a complete repository and hosted-artifact scan before
   work resumes.

Do not copy the prohibited bytes into the incident ticket as evidence.

## Human-only decisions

Only a human maintainer, with legal guidance where appropriate, may propose a
future change to the generated-code or protected-data policies, reuse of
unlicensed upstream material, a public repository, or a release. The current
policy does not authorize publishing ROM-derived expressive data in Git or
GitHub.
