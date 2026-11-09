# v1.5.0 source qualification

Status: source prepared for the owner-authorized develop-to-main merge on
2026-11-09. This record does not establish a published tag or downloadable package.

The [changelog](../../CHANGELOG.md) describes the combined regional architecture,
launcher, controls, renderer and Proton changes. The
[issue index](../development/issues/README.md) preserves individual evidence,
failed attempts and manual acceptance. USA/PAL/Japanese Arcade controls (#50) and
night-vision/damage presentation (#51) passed owner testing in all three regions.
Modern combat camera distance (#52) and optional advanced controls (#53/#55)
carry the owner's recorded approval without inventing additional route coverage.

The graphics API selector has Windows normal-Play checks across all three
regions and APIs, actual Windows/Proton settings checks and bounded diagnostic
coverage. Its final hint is "Auto chooses a compatible renderer." The reported
Windows black screen (#58) still needs affected-machine evidence; the selector
and logging are investigation tools, not a claimed remedy for that report.

## Remaining scope

- #45 is a native NTSC behavior reserved for a separate native-bug-fixes update.
- #48 is deferred by the owner for this version.
- #57 has automated/captured-menu verification; owner visual acceptance is pending.
- Bazzite PC acceptance does not establish Steam Deck or every Proton configuration.
- Original-game timing and broader campaign coverage retain their documented limits.

## Integration and packaging

The merge must pass the repository's normal required CI checks. Local validation
receipts are retained privately under `release15-merge-20261109`; earlier renderer
qualification remains under `renderer-api-20261109`, `renderer-api-combobox-20261109`
and `renderer-api-copy-20261109`. Existing owner profiles and previews are preserved.

The checked-in main-push workflow runs ROM-free CI. The release workflow is
tag/manual-triggered and validates prebuilt assets already attached to a draft
release; a main merge alone does not create an installation package. No release
tag, uploaded asset or publication is authorized by this source-merge record.
See [release procedure](../maintenance/releases.md). Source merges must not include
ROMs, generated game code, private logs or personal saves.

## Local integration checks

The 1.5.0 source passes full-history repository hygiene, project/schema validation,
release metadata and packaging fixture tests, the rebuilt launcher checks and
the Video Settings UI regression suite. These are source-integration checks;
they do not manufacture fresh hardware acceptance or a distributable runtime.
The required GitHub PR checks remain the merge gate.
