# Gems visible through hanging vine textures

Status: candidate verified in renderer tests and captured-frame GPU comparisons; awaiting owner batch review. Owner reported October 27, 2026. Unreleased Enhanced Shadows preview v26 at 120 FPS.

## Symptom and reproduction

In a forest room, purple gems remain visible through apparently opaque brown/green portions of a hanging vine cutout texture. Owner provided two screenshots and closed the captured game with the vine visible. The same session's shadows are visually approved; this is a separate material/depth question.

Private evidence: D:/JFG-private/enhanced-shadow-bridge-20261026/owner-captures/20261027-040742-c6ccd8b2cd3b4885bf84b537aa44ae61, including final 4 MiB RAM, input, draw/interpolation logs and final frame. Runtime SHA-256 c33abc0393a1c6927dd37e5833245e9e7cbb930aef66b8990a46bf92235d6416.

Severity: visible occlusion defect, no progression failure reported.

## Investigation

Unproven possibilities: vine depth writing, gem depth comparison, alpha/material classification or native draw ordering. No hardware parity or exact cause established yet. Preserve cutout holes and approved character transparency/shadows; do not globally force transparent surfaces to write depth.

## Verification and limits

Owner evidence and native draw-state analysis establish the reported occlusion failure. The candidate and its verification are recorded below.

## Captured cause and candidate, October 27

The final state is level 236. The vine uses level textures 21/22/23/30 (RGBA32 with fully transparent holes, partially transparent edges and fully opaque texels). Its native blended level mode is C8104A50: depth comparison enabled, depth writing disabled. Subsequent health-gem billboard draws use C8104B50, also without depth writing. The game therefore never records the vine's solid pixels as occluders before drawing those pickups.

These are original emitted game modes; a native rendering limitation is strongly indicated. No same-view hardware/EmuHawk comparison has yet been made, so hardware reproduction is not claimed.

The candidate preserves the native blended colour pass and follows it with an exact-alpha solid-core pass. Only alpha 1 contributes depth; holes and soft edges retain native blending. A validated current-level face-range table identifies eligible RGBA32 level materials with at least one fully opaque texel. The adapter additionally pins the observed native level combiner and render mode. It does not apply to actors, sprites, HUD, shadow receivers or arbitrary blended geometry. Both RSP/RDP mode state and blend threshold are restored after each contribution.

This is not general order-independent transparency: partially transparent overlap still uses the original ordering. No global transparent depth-write change or per-room/per-character patch is made.

Early validation corrections: split a mixed-type auto declaration rejected by MSVC; enable the existing optional snapshot runner in the private build; use RT64's actual reversed combiner word layout in the material predicate. No failed build was installed in the owner package. Runtime and GPU qualification remain pending.

## Qualified candidate

Build and renderer component tests pass. Integration tests exercise the actual native level material, unrelated geometry with identical render modes, invalid ranges, fully translucent textures and restoration of both RSP/RDP state and blend threshold. The integration test exposed that native EF commands update RDP mode independently of the RSP shadow; the correction uses the effective RDP material and restores each original state separately.

An actual GPU replay of the owner's final room/camera reproduces the three visible gems through the vine. Enabling the candidate changes only pixels inside X392..423/Y84..103 of the 640x480 output, hiding those gems. Two further isolated GPU fixtures move all six gems toward the camera, or reduce the vine's alpha to partial transparency. Both remain pixel-identical to native rendering. Fully opaque occlusion, foreground visibility and deliberate transparency are therefore distinguished.

The static replay omits the HUD tail and lacks Enhanced shadow presentation metadata; its unchanged black native shadow patch is not a live-game regression or shadow qualification. All comparisons use the same replay input apart from the explicitly recorded material/position fixture changes.

A normal-Play copied-save combat replay reaches room27 and closes normally after approximately 61 seconds. All 314,889 shadow replacement draws match submitted draws with zero missing geometry or mismatched output phases. The script's older rooms convenience array reads a descriptor column; actual live.json level27 is the room proof.

Private receipts and PNG comparisons: D:/JFG-private/vine-gem-occlusion-20261027/gpu-comparison.json, gpu-regression.json, qualification.json. The early regression fixture recognized only one vertex-DMA alignment encoding; it was corrected to recognize all six one-vertex anchor commands. No fixture writes affect personal saves or game simulation.

Compatibility lesson: blended opaque texture interiors need an occlusion contribution even when their soft borders retain transparency. Preserve provenance and independent command-state stores; enabling depth writes on every blended pixel would incorrectly block through holes and translucent content. This is deliberately not a general transparency sorting replacement.

Owner requested final review after the remaining GitHub batch, so no replacement launcher was opened. The runtime is staged privately and unreleased.

## Original-ROM EmuHawk reproduction, October 27

The pinned US ROM under EmuHawk 2.11.1 / Angrylion / cxd4 also draws the three
gems through the opaque green portion of this vine. The reference uses the
same room 236 and its original, unchanged pickup placements and materials.
Only a private camera fixture places the player and camera at the owner's
recorded viewpoint; the original ROM performs the culling, display-list
generation, RSP work and RDP rendering. No texture alpha, gem depth, render
mode or draw-order changes are applied in the reference.

The first camera fixture updated the visible view too late to match culling
and showed only sky. Applying the pose after the original player controller
returns preserves coherent camera/culling state and yields the expected view.
Only that completed capture is reproduction evidence.

Private evidence: emuhawk-sanitization-20261027/emuhawk-vine-return-016,
checkpoint-ef.png/.rdram/.State, scope.json, and vine-poses-012.json.
This confirms an original-ROM rendering limitation in the emulator, rather
than only an inference from the recomp's emitted modes. It is not a new
physical-console test. The existing candidate's opaque-core depth correction,
foreground-gem and partial-alpha regression results remain the remedy and
validation; final owner review is still pending.
