# ADR 0001: Project, upstream, and protected-data boundaries

- Status: Accepted for Phase 0
- Date: 2026-08-03
- Decision owners: Human maintainers
- Supersedes: None

## Context

The project needs information from a user-supplied Jet Force Gemini ROM, an
unlicensed matching-decompilation repository, and several independently
licensed recompilation projects. Some useful build outputs and test captures
may reproduce expressive game data. A private GitHub repository is still a
distribution and collaboration system; repository visibility does not grant a
right to copy or redistribute third-party material.

The project also needs a boundary between project-owned automation, external
tools, and private local inputs. Without that boundary, a normal Git command,
CI artifact upload, cache, or agent evidence bundle could disclose material
that must remain local.

## Decision

### Repository purpose

This repository owns only the independently authored native-port work:

- Architecture and governance documents.
- Build orchestration that does not embed protected inputs.
- Runtime adapters and project-authored patches once their dependency and
  licensing basis is approved.
- Synthetic tests and public-safe test manifests.
- Packaging metadata that contains no game assets.

The repository does not become a fork of the matching decompilation. The
decompilation remains an external, local research/build input until written
permission and human legal review authorize a different relationship.

### Repository visibility

The GitHub repository MUST remain private. Making it public, publishing a
release, enabling a public package, or mirroring it to another host is a human
gate requiring all of the following:

1. An approved dependency and license inventory.
2. An approved generated-code and symbol-distribution decision.
3. A clean protected-data scan of the complete Git history and release inputs.
4. A documented project-license decision.
5. Human release approval.

Private visibility does not relax any content rule in this ADR.

### Filesystem and Git boundaries

The following are separate data classes:

| Location | Purpose | Git policy |
|---|---|---|
| `scripts/` or `devtools/` | Project-authored automation | Tracked after review |
| `tools/` | Cloned upstream repositories and downloaded tools | Entire tree ignored |
| `roms/` | User-supplied ROMs | Entire tree ignored; never uploaded |
| `extracted/`, `assets/private/` | Extracted or converted game data | Ignored; never uploaded |
| `corpus/private/`, `captures/private/` | ROM-backed test bodies and captures | Ignored; never uploaded |
| `generated/`, `src/generated/` | Locally generated output pending policy decision | Entire trees ignored; never uploaded |
| `artifacts/private/`, `test-results/` | Local private results | Ignored; never uploaded |

External repositories MUST be cloned under `tools/` and pinned by a
project-owned lock or provenance document. They MUST NOT be added as Git
submodules, subtrees, vendored source, release assets, packages, Actions
artifacts, or caches until their use and license are approved.

Private data SHOULD live outside the repository checkout when practical. The
ignore file is defense in depth, not an authorization or security boundary.

### Unlicensed upstream material

Pending written permission, the project MUST NOT copy into Git or GitHub:

- Source or headers from the JFG matching decompilation.
- Source or headers from RecompFrontend.
- Exported symbol files or symbol repositories derived from unlicensed work.
- Matching-source excerpts in issues, pull requests, agent evidence, or docs.
- Generated C or other expressive output derived from the ROM.

Locally cloning and inspecting an upstream repository does not authorize
redistribution. Project documentation may record non-expressive facts needed
for provenance, such as repository URL, commit ID, tool version, file hash,
section address, or a project-assigned opaque identifier, subject to human
review.

### Generated output and symbols

All generated code, exported symbols, disassembly, memory snapshots, display
lists, audio captures, images, and extracted assets are presumed private until
classified under the legal policies. `generated/` remains ignored until a
human-approved ADR changes this default.

There will be one authoritative symbol model if symbol distribution is later
approved. Human-readable names and tool-specific TOML files will be generated
views, not independent sources of truth.

### Enforcement

The project MUST implement the following before accepting ROM-backed work:

- A pre-commit and CI denylist scanner for ROM files, ROM byte signatures,
  extracted assets, private corpus formats, generated expressive output, and
  forbidden paths.
- A tracked-file check equivalent to `git ls-files` that fails if any ignored
  private or external-tool path is tracked.
- Full-length commit pinning for third-party GitHub Actions.
- CODEOWNERS or equivalent mandatory review for workflows, legal policies,
  dependency locks, goldens, and protected-data scanners.
- A release scan covering the entire Git history, source archive, binaries,
  debug symbols, installer, SBOM, and notices.

No automation may make a legal classification merely because a scanner passes.

## Human-only gates

Only a human maintainer may approve:

- A change in repository visibility.
- The project license or a dependency-license interpretation.
- Copying unlicensed upstream material.
- Committing or distributing generated code or symbol exports.
- Proposing a future policy change concerning screenshots, audio, video,
  display lists, or memory-derived data. The current policy forbids placing
  ROM-derived expressive data in Git or GitHub.
- A release, package, or public mod SDK.

## Consequences

- Contributor setup is less convenient because upstream tools and private
  inputs must be acquired locally.
- Public CI initially tests only project-owned code and synthetic fixtures.
- ROM-backed validation requires a separate trusted execution boundary.
- Provenance and regeneration automation become first-class deliverables.
- The design leaves room to relax a boundary later, but only through a new ADR
  with written evidence and human approval.

## Acceptance criteria

This ADR is operational when:

1. All external repositories are under ignored `tools/` paths.
2. No private/protected path is tracked.
3. A clean clone can run public-safe checks without a ROM or unlicensed source.
4. The protected-data scanner fails on test canaries for each forbidden class.
5. Repository visibility is private and public publishing is human-gated.
