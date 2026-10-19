# v1.3.0 release qualification

Status: clean source, runtime, launcher and package qualified. Source CI passes
all six jobs. The tagged publication workflow and verified public download are
required before merging this final qualification record.

The owner completed New Game through Vela's rescue and the targeted corpse
follow-up, then authorized release and integration.
The owner changed acceptance from absolute zero outliers to visibly smooth,
responsive play with clean audio. Preserve and explain material timing failures.

## Source and build boundary

The active branch contains v1.2.1 and the later reviewed 1.3 performance work.
The owner is testing runtime
09ca8091d720bb2c3f73d935536fc8a2d72df9b0d7bb6288a26b34c2bf1d6ad8,
with Custom 120 FPS, VSync, Reduced blur and 100% fog at capture preparation.
The capture itself records settings at Play and is authoritative if changed.

The release source promotes the same existing optimization selection to
JFG_NATIVE_PLAY_OPTIMIZATIONS. The former JFG_V13_PREVIEW_DEFAULTS remains a
compatibility alias; no selector value or game algorithm changes in that rename.
cmake/native_release.cmake pins native timing/collision, five workload slots,
persistent mapping and bounded upload reservation, and disables automatic
control/blur audit and source-only visual comparison. The existing native
optimization switches remain available for explicit diagnostic comparisons.

The selected source version is 1.3.0. Packaging now requires an explicit
--version, avoiding the old beta default. A clean committed runtime and launcher
build, matching support/launcher identities and the normal package validators
remain required. The tested owner binary is not relabelled as a clean release.

## Acceptance already recorded

- v1.2.1 controls accepted in Vela, Juno and Lupus fights; incorporated here.
- Both reported ship cutscenes accepted with clean audio.
- Breakable glass, boss camera-sweep motion, Reduced blur and high-drop/ledge
  mouse-camera retention accepted in owner play.
- Standing-aim movement matches EmuHawk magnitudes in the qualified runtime trace.
- Directory-picker storage, native window appearance and fog settings accepted.
- Tawfret rain verified in wet gameplay rooms and the opening cutscene.
- The owner cannot reproduce missing reticles with mouse/Modern Controls and
  reports the hut scene smooth. Ask #25 reporter for v1.3/control-mode retest.
- The #18 reporter explicitly acknowledged the aim cancellation resolved in
  v1.2.0, comment 6244055488; movement is the v1.3 correction.

## Required before publication

- [x] Completed owner New Game-to-Vela capture and visual/audio feedback; corpse follow-up accepted with coverage limits.
- [x] Review final audio, output/update timing, scene coverage and log-loss counters.
- [x] Full combined ROM-free/native component and launcher checks.
- [x] Clean source/history policy, including exact UI asset provenance.
- [x] Commit reviewed source with the required maintainer identity.
- [x] Build clean stable runtime/launcher with private diagnostic defaults off.
- [x] Verify allowed ZIP members, hashes, versions and source identities.
- [x] Required source CI, main integration and owner release authorization.
- Publication and public-download verification: enforced before this record merges;
  see the tagged workflow below.
- [ ] Reporter retest requests with the actual v1.3 download link after availability.

A reporter retest is not a confirmed fix. No reply or issue closure is sent
during this preparation. #24/#26 can be resolved with the published functionality;
#25/#19 retain their exact reproduction and hardware limits.

## Source-policy preflight

The first working-tree scan found two private owner paths in new notes, the
unregistered video-icon atlas, and generated-marker false positives in three
small handwritten synthetic compiler fixtures. Paths were removed from public
notes with originals preserved privately. The locally authored SVG/TGA atlas
and three reviewed fixture bodies have exact-hash entries; no suffix-wide or
credential/ROM/archive exemption was added. Modified-body rejection is checked.
The first helper import for that check omitted the repository Python path and
failed before testing; the corrected check passed all eight acceptance/rejection
cases. Full current-tree/history policy results remain recorded separately.

## Grounded drone bodies

Detached-body ownership and hidden-bone validation corrections pass focused checks and the latest owner visual review. The latest capture has no invalid-sample rejections or audio underruns; the exact seeded route and earlier cutscene groups remain unverified. See the [issue record](issues/dead-drone-camera-jitter.md). Not yet released.

## Completed owner route and corpse follow-up

The standard 2026-10-19 full route completed approximately 21.5 minutes, including
menus, the opening sequence, gameplay and room transitions. The last progress
sample records 77,160 retraces, 37,769 game updates and **zero audio device
underruns or overruns**. The event stream extends six updates past that periodic
progress sample.

150,591 successful present-return samples have interval percentiles of 8.340 ms
(p50), 8.501 ms (p95) and 8.783 ms (p99). There are 81 intervals above 33.334 ms,
including room loads and menus; this is not a zero-stall qualification or physical
scanout measurement. Source-update intervals are overwhelmingly two retraces
(37,683 of 37,774 intervals). Seven gaps are more than three seconds from a room
transition: one in the initial menus, one opening-cutscene 50 ms interval, and
five around pause-menu activity. The event correlation is retained privately;
a nearby menu event alone does not prove causality.

Owner's remaining reported visual defect was intermittent grounded drone-body
jitter during camera motion. See RENDER-018. The targeted capture identified
untracked baked body geometry; candidate ownership and component checks now pass.
Owner visual confirmation and final normal-release build/package remain pending.

The owner found one additional corpse case in the first candidate. RENDER-018 now also covers shared skeletal validation of native zero-scale hidden bones. A second candidate passes focused checks and is installed for owner review; corpse/cutscene verification remains open.


## Corpse follow-up acceptance

The owner accepted the second corpse candidate visually for the tested route,
without claiming an identical seeded reproduction. Its approximately two-minute
capture contains 577 proven hidden-geometry exclusions, no invalid-sample
rejections, and zero reported audio-device underruns/overruns. Exact route/seed
parity and the earlier cutscene actor groups are still unverified. Detailed
evidence and the two separate underlying causes are in RENDER-018. These results
do not replace the final clean normal-release build and package qualification.


## Release authorization

The owner approved shipping 1.3.0 after the qualified corpse visual pass.
Issue replies must be drafted for owner review and explicitly approved before
posting. Publication authorization does not authorize posting those comments.
Clean builds, package verification and required CI remain publication gates.

## Open GitHub issue audit before release

Current eight open issues were read from GitHub on 2026-10-19; this audit does
not close them or substitute for reporter-specific reproduction.

| Issue | Addressed in release source / evidence | Remaining limit and reply scope |
|---|---|---|
| #26 fog | Live 0-100% fog strength in Video Settings; owner accepted the controls and effect. | Explain 0 removes fog, 100 preserves native fog; published version needed. |
| #24 portable storage | Directory picker, migration without destination overwrite, relative in-package storage and launcher restart; automated transfer/relocation checks and owner UI review. | Explain selecting a folder inside the game folder and retaining that folder/storage-location.txt when moving or updating. |
| #18 targeting and movement | Reporter confirmed held aim fixed in 1.2.0. Native standing-aim magnitudes restored; owner runtime displacement within 0.00062 units/tick of the measured reference. | Ask movement retest; do not claim every control profile/character trajectory is bit-exact. |
| #21 1.3 rendering/audio follow-up | Cutscene matching, high-resolution blur composition/interpolation, Reduced blur, boss/glass/corpse interpolation, general upload/settings work and unrestricted explicit exit warp; owner route/targeted passes and zero audio underruns in final captures. | Rare transition gaps and wider camera/shadow/Unlimited/high-Hz coverage remain finite. Exact seeded routes not repeated. Keep separate #19 reproduction open. |
| #19 invasion replay | Related opening/cutscene performance improvements included; owner 5090 route did not reproduce the reported 1-2 FPS failure. | Needs reporter retest with Unlimited + VSync and their King Jeff replay. Do not label confirmed fixed. |
| #25 Ally X | Owner verifies rain in native wet rooms/cutscene and smooth hut scene; missing reticle not reproduced with mouse/Modern Controls. | No new rain/reticle patch claimed. Ask 1.3 retest, handheld/controller versus mouse, control mode, weapon and aim/fire bindings; Ally X performance remains unverified. |
| #15 Linux source build | Prior portable noinline, platform I/O and diagnostic boundaries retained; actual GCC translation-unit validation and host CI documented in issue record. | This is a Windows release, not a tested CachyOS/GCC16 AppImage. Keep platform retest open. |
| #4 legacy Windows source setup | Prior firmware/WSL/PowerShell/submodule/short-path remedies retained, with 28 mocked setup checks. Normal release ZIP needs no WSL/compiler. | Fresh Windows10 source install and later optional-tool findings not wholly verified; do not close the whole thread on package availability. |

The owner requires reading and approving each proposed comment before posting.
Draft replies will link the actual published release only after it exists.

## Local develop working-tree reconciliation

All seven uncommitted files in the owner's develop checkout were compared
before publication. The issue18 handoff, PC-controls historical measurement
section and sanitized JSON evidence already match the release source exactly.
The issue record, index and known-issues intent is retained with newer v1.3
status/evidence; old no-fix/undiagnosed statements are not restored over the
verified corrections. Additional community credits were missing and are now
included. Original local files remain preserved until branch integration.

## v1.3.0 build and release identities

Release tag / launcher source: 02be6fa9a4c50f4056f778c5148ca8ac70b0e92b.
Clean runtime source: 665596482a7395593e85dbe73f1bd4b016d183d9. Only release documentation
changed between these revisions; the clean game build is not relabelled.
Both normal-release builds pass, with diagnostic defaults disabled. The standard
package validator verifies ZIP membership, per-file hashes, version and runtime/
launcher source identities. Public symbols, ROMs, saves and generated source are
excluded from the package.

[Source CI](https://github.com/TK22-26/JetForceGemini-Recomp/actions/runs/39205989097)
passes all six jobs, including GCC/Clang, Windows, sanitizers, renderer and launcher.
[Tagged publication](https://github.com/TK22-26/JetForceGemini-Recomp/actions/runs/39207005122)
repeats required checks and independently verifies the uploaded draft before
making [v1.3.0](https://github.com/TK22-26/JetForceGemini-Recomp/releases/tag/v1.3.0)
public. Merging this record additionally requires downloading the public assets
and verifying their hashes, inventory and identities against the staged package.

Issue comments remain drafted and unposted pending the owner reading and
approving them. Source inclusion does not close reporter-specific #19/#25 or
platform-specific #4/#15 validation, or expand the bounded owner evidence.
