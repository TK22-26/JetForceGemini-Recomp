# Documentation

Choose the guide for what you want to do. [Project status](status.md) distinguishes published behavior, local changes and future work.

| Task | Start here |
|---|---|
| Install and play | [Getting started](getting-started.md), [launcher, settings and saves](development/launcher.md) |
| Set up controls | [PC controls](features/pc-controls.md) |
| Use optional tools | [Live map and navigation](features/navigation-mod.md), [frontend and inventory](features/frontend.md) |
| Report or investigate a problem | [Known issues](known-issues.md), [reporting guide](playtesting.md), [issue records](development/issues/README.md) |
| Compare with the original game | [Original N64 bugs and regional differences](original-game/README.md) |
| Build or change the project | [Development](development/README.md), [repository layout](development/repository-layout.md) |
| Maintain a release or automated work | [Maintainer guide](maintenance/README.md) |
| Understand future work | [Roadmap and acceptance contracts](planning/README.md) |

## Reference and evidence

[Architecture decisions](adr/), [upstream references](upstream/reference-review-2026-10-01.md),
[feasibility](feasibility/README.md), [completion evidence](../evidence/README.md),
[release records](releases/), [third-party notices](../THIRD_PARTY_NOTICES.md),
[dependency inventory](legal/dependency-license-inventory.md),
[ROM and asset policy](legal/rom-and-assets-policy.md), and [test corpus policy](legal/test-corpus-policy.md).

<a id="where-documents-belong"></a>

## Documentation ownership

Player instructions live in this directory and `features/`. Build and runtime reference lives in
`development/`; each bug has one durable record in `development/issues/`. Release procedures and
guarded automation live in `maintenance/`; version-specific qualification belongs in `releases/`.
`original-game/` catalogs hardware-confirmed native bugs separately from emulator observations and
regional differences. `planning/` describes future gates, not completed features.

Update the canonical page and link it elsewhere. Remove a superseded page after preserving its unique
findings in the appropriate issue or reference. Keep failures, evidence identities and acceptance limits.
The [file audit](development/repository-audit.csv) records every baseline tracked file's disposition, including documentation; new entries identify added ownership and reference files.

## Historical material

Historical snapshots and removed duplicate reports remain in Git. Use `git log --all -- path`
to find their revisions and `git show <commit>:path` to read the original record. References to
older results retain their source identities and acceptance limits; they are not new validation.

## Fixed paths and immutable evidence

Signed evidence pins the bytes of Phase 5/6 contracts and ADR 0003; these also name the Phase 4
contract and dependency inventory. Do not edit or move those records. Boot provenance pins
`development/boot-gameplay-fix.md` and the four `planning/phase9-*` timing notes. The production guard
and roadmap paths remain fixed. Phase 1/3 aggregate paths are part of their schemas.

Published launchers and ZIPs link `getting-started.md`, `known-issues.md`,
`development/launcher.md` and `development/rom-bootstrap.md`. Keep those paths stable; the two
bundled guides use absolute links. Historical results apply only to their recorded revision and inputs.
They do not certify a later build or reopen a stopped investigation.
