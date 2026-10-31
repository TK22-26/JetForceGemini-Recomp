# GH-051: [Playtest] Lupus' Nightvision in Mizar's Palace is pixelated

Status: local resolution and temporal candidate verified; owner route review pending.

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
