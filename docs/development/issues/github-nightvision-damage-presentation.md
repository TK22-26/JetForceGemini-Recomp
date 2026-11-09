# GH-051: [Playtest] Lupus' Nightvision in Mizar's Palace is pixelated

Status: fixed locally; owner manually tested and approved USA, PAL and JP on November 8, 2026; unreleased.

Source: [[Playtest] Lupus' Nightvision in Mizar's Palace is pixelated](https://github.com/TK22-26/JetForceGemini-Recomp/issues/51). Evidence snapshot retained privately in D:/JFG-private/remaining-gh-issues-20261027/github-issues.json.

## Reported symptoms and reproduction

### Problem type

Graphics

### Launcher and game build

1.4.0 Release build

### Windows version, GPU, and input device

Windows 10, GTX 1080, XBOX Controller

### What happened and how to reproduce it

In Mizar's Palace from the Nightvision part with Lupus, the screen looks pixelated and low resolution, it also looks like the game plays at 30 FPS even if the game is set at high framerates. The same can be observed when the screen turns red after getting hit.

### How often does it happen?

Every attempt

### Support ZIP and additional details

_No response_

## Scope and evidence

Local owner-authorized batch: trace low-resolution/high-refresh postprocessing. Preserve existing approved fixes, user profiles and ROMs. No GitHub posting or issue changes. A reported symptom is not yet a confirmed cause. Attempts, results, final remedy and verification limits will be recorded here.

## October 27 source diagnosis and candidate

The native fxScreenEffect routine emits RGBA16 screen strips for both night vision and the red tint. The recomp globally disables GPU framebuffer reuse to preserve CPU edits to intensity shadow masks. That policy also makes these screen effects sample the native-resolution RAM image. A private fixture executes the actual native function and reproduces both display lists; paired GPU and CPU-owned-mask runs show the resolution difference.

The candidate admits GPU framebuffer copies only for the two exact native screen-effect materials, a 320-wide RGBA16 destination, and an existing 320-wide RGBA16 source framebuffer. Intensity shadow masks remain under CPU ownership and the global policy is unchanged. Render-state checks occur both when a load records its framebuffer copy and when the draw resolves its texture.

GPU and temporal qualification is pending. The earlier fixture accidentally selected the last offscreen shadow target as a screen source, yielding meaningless noise; that failure was discarded and the source is now the last validated full-size world target. Evidence remains private in remaining-gh-issues-20261027/screenfx-gpu-031. No released resolution is claimed.

## October 27 validation update

The configure-first Release build passes renderer checks. With CPU-mask writeback enabled, both screen-effect candidates match the unrestricted high-resolution GPU reference pixel for pixel in the captured scene. Baseline CPU copies retain the reproduced resolution loss. Private evidence: screenfx-gpu-031 and screenfx-gpu-040. The initial rebuild order had configured the private RT64 shader/source view after compiling its library; those builds are not qualification evidence. An explicit configure-first rebuild fixed this, along with normalized line-ending validation for the pinned RT64 state. Temporal qualification and owner review remain pending.

The renderer ownership regression test now also passes using an actual RT64 State/RDP instance: both screen materials are admitted only with an existing RGBA16 color source. Missing sources, reused depth targets, intensity-mask sources, offscreen mask destinations, unrelated RAM and altered materials are rejected. The initial test runner looked in the root Release directory; the built test actually resides in tests/Release and passed when invoked there. Private evidence: screenfx-negative-045-result.json.

## Temporal qualification

A controlled moving world triangle was composited by both actual native screen-effect display lists through the candidate renderer with CPU-mask writeback enabled. At 30 Hz scene input and 120 Hz output, each effect produced four distinct output phases per scene update. All twelve captured phases across three consecutive updates advanced monotonically, approximately 1.33-1.67 output pixels per phase. This verifies that the effect samples the interpolated high-resolution scene rather than repeatedly displaying one RAM snapshot.

The first private fixture had an incorrect VI scanout origin and an unsuitable test material; it showed edge-only pixels and no valid interpolated target. Those frames were rejected. Correcting the fixture to the normal framebuffer origin plus one scanline and an opaque primitive material yielded the qualified result. No production renderer adjustment was made to accommodate the fixture.

Evidence: screenfx-motion-051/motion-result053.json and screenfx-motion-054-verification.json. Resolution, temporal and ownership checks pass locally. Owner review of the actual Lupus route and damage tint remains pending; this is an unreleased candidate.

## Original-ROM effect reference, October 27

Actual EmuHawk/Angrylion now confirms both original effect materials. An ordinary
enemy hit emits the red damage material. For night vision, a copied save selects
Lupus at Dog NVision Pad In (316) and grants the goggles inventory prerequisite;
normal analog movement and A activate the original pad. No live camera, effect,
palette, actor or renderer writes are used. The completed original green
night-vision view and its original screen-strip commands are captured. The
combiner/OtherMode pairs exactly match the candidate's two-material predicate.

The earlier forced-selector fixture identified the night-vision material but
left its palette uninitialized and rendered black; it was not accepted as
visual qualification. The real-pad fixture also corrected two setup mistakes:
the copied flags initially left Juno selectable, and inventory bits use the
opposite order from game flags. Those runs are not night-vision passes. Temporary
entry/return callbacks initially triggered an EmuHawk breakpoint-removal error
during shutdown, after capture; explicit callback cleanup fixed it. The final
pad run exits cleanly.

Private evidence: emuhawk-sanitization-20261027/nightvision-reference-027.json,
emuhawk-lupus-316-025 and emuhawk-screenfx-0-018. The reference is the original
ROM under an emulator, not physical N64 hardware or a complete campaign route.
The synthetic moving-scene GPU tests remain the evidence for 120 Hz temporal
behavior; original hardware has no equivalent high-resolution output mode.
The same logical Flash save and recorded controller-poll route also activate
night vision in the 120 FPS candidate, retain the green overlay/reticle, and
close cleanly. Actual output screenshots show the upscaled scene with the
original effect; this is not a pixel-equality test of different resolutions.
Evidence: native-lupus-120-026 and native-nightvision-028.json. Owner route review remains
pending and no released resolution is claimed.

## November 8 review and regional save preparation

The owner requested review of the existing fix and three regional saves for
manual testing, with a three-hour bounded continuation. GitHub #51 remains open
and has no comments beyond its original 1.4.0 report. No prior owner approval of
this specific night-vision/damage-tint issue was found; Vela rescue blur approval
is a separate effect. The existing exact-material GPU framebuffer remedy and
renderer regression remain in source. The completed checks and delivery below retain regional manual acceptance as
pending. Original saves and #50 acceptance are preserved.

### Current package and regression result

All three current program bundles pass identity verification. Their recorded
build input hashes for `include/jfg/renderer/native_screen_effect.hpp` and
`cmake/renderer/rt64_native_screen_effect.cmake` match the current source exactly.
The GPU framebuffer exception is therefore an existing remedy in the delivered
preview, not a newly added effect workaround. No runtime change or new game
binary was needed for this review.

A fresh compile of the renderer texture regression against the current preview
libraries passes the screen-effect case. The larger executable initially failed
later on a solid-core depth expectation: its synthetic guest fixtures omitted
their qualified regional layout. Passing the existing fixture layout restores
the full texture-test pass; see the [fixture correction](renderer-texture-fixture-layout.md).
The unchanged screen-effect case also passes independently. This fresh check
validates eligibility and exclusions; the October 27 resolution and four-phase
120 Hz captures remain historical evidence, not newly repeated GPU captures.

### Three-region manual test setup

Separate USA, PAL and Japanese profiles now start slot 1 as Lupus at room 316,
Dog NVision Pad In, with goggles item 22. Each starts from its own previously
verified regional save, preserves the remaining slots and normal regional
namespace, and changes copied checkpoint/inventory/story prerequisites only.
Normal saves and the accepted #50 profiles remain unchanged. The archived
normally activated Lupus fixture supplied the shared logical story flags.

Muted launches through the current launcher and native runtime verified all
three: gameplay active in room 316, character 2, goggles present and the actual
NightVisionPad actor present. Copied controller settings were restored after menu
entry. These checks establish the starting point, not regional appearance or
feel acceptance. Desktop shortcuts reset only their separate test saves on each
launch and keep the owner's copied manual audio preferences.

Walk to the pad in the middle of the room and press Interact (copied Modern
bindings: controller X / keyboard E). Move and turn with night vision active;
check that the underlying scene retains the chosen resolution and smooth output.
Then take damage in an enemy area and check the red tint too. Original green
coloring/reticle and red coloring remain intentional. Owner USA/PAL/JP review is
pending; no GitHub closure, commit, push or release was performed.

### Informative setup failures and evidence retention

The minimal copied save entered Lupus's room-66 introduction instead of the pad.
Adding flag 23 alone did not solve that; it is not recorded as the cause/remedy.
Restoring the shared story context from the previously successful fixture allowed
normal checkpoint loading. Individual story gates were not independently isolated.
This is private save preparation, not a campaign progression patch.

The first cleanup helper followed native processes only and missed the launcher's
intermediate setup worker, leaving a test session open. That interfered with a
later launch; complete process-tree cleanup corrected the qualification helper.
The first PAL map lookup searched the USA profile root, while PAL correctly wrote
its state under its revision namespace. Reading that existing capture confirmed
the successful PAL entry; no extra PAL replay was needed. Failed attempts remain
preserved rather than relabeled as passes.

The October 28 storage cleanup archived the old saves under content hashes. The
native and original-ROM fixture Flash files were recovered through their archive
manifests and match SHA-256
`8030ea589ff3b74688b55af95e27d3564e5ffedd0d317ad8bd575a2d0b5bbfad`.
Earlier evidence paths above describe their historical locations; they are not
claims that the original working directories still exist.

Current private receipts: `issue51-review-saves-20261108/`, especially
`github-issue-51.json`, `current-package-identities.json`, `recovered-index.json`,
`renderer-regression/qualified-result.json`, `preparation.json` and
`regional-entry-final-results.json`. ROMs, generated game sources and saves remain
private. Compatibility lesson: qualify the actual character, inventory, pad and
regional namespace; a valid checksum or a room number alone does not prove a
usable manual-test starting point.


### Owner before/after comparison request (November 8)

The owner reports that the current view looks good but requests an earlier build
to establish the comparison. This is not yet final visual acceptance. The
preserved v1.4.0 signoff package is the reported affected release and predates the
October 27 screen-effect remedy. Its manifest file hashes and clean runtime
identity `521f66620e734671a06a07f118e874076f02a133` were verified; that source lacks
the later exact-material framebuffer exception.

A separate USA before-fix shortcut uses the identical prepared Lupus pad save,
120 FPS, matching video settings and copied compatible controls. The v1.4.0 parser
rejects today's version-8 control schema, so the comparison profile uses only its
supported historical fields with the current values. A small executable using
the actual historical parser verifies that Modern controls and X/E Interact load.
Original and current saves/profiles remain unchanged. v1.4.0 has USA support only
and other older behavior; this is a release-to-current comparison, not a build
with only one change toggled. No automated game launch interrupted the owner's
running session. Compare scene sharpness and motion under the green and red
effects at the same window size; manual acceptance remains pending.

Private receipt: `issue51-v140-comparison-20261108/comparison.json`. The same
investigation, remaining attempts and original three-hour approval deadline are
preserved; no allowance or counter was reset.


## Owner acceptance — November 8, 2026

The owner confirmed "fix approved - verified by me" and then clarified:
"all regions are tested but yes they all pass". Record GH-051 as manually
verified and approved for USA, PAL and Japanese gameplay. This supersedes the
earlier pending-review entries and the initially inferred USA-only scope.

The existing screen-effect remedy remains unchanged. The current all-region
test profiles, historical v1.4.0 USA comparison, fresh renderer regression and
regional pad-entry receipts remain the supporting evidence. The owner has now
provided the previously missing visual acceptance; further owner sign-off on
these three regional checks is not requested. No new game session, build or
runtime change was performed while recording this confirmation.

This is local acceptance of #51, not a new release or GitHub issue closure.
The separate renderer test-fixture correction remains uncommitted. Private
acceptance receipt: `issue51-owner-acceptance-20261108/acceptance.json`.
