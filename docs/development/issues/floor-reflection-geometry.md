# GH-047: Floor reflection cadence and missing reflected geometry

- Status: owner-approved local reflected geometry and motion corrections; unreleased.
- Report: [GitHub #47](https://github.com/TK22-26/JetForceGemini-Recomp/issues/47).
- Owner follow-up: 2026-10-25, after development commit d98d7fc.
- Severity: visible rendering defect; no gameplay failure reported.

## Symptoms and reproduction

The owner believes reflected motion may already run at 60 FPS, but reports
persistent missing regions of reflected character models: apparent missing
vertices/triangles and see-through areas resembling the earlier skirt defect.
The defect is reportedly always visible. The first area offers easy access to
reflective surfaces. The supplied capture is Juno in Goldwood room 92, using a copied profile at 120 FPS.

## Evidence and hypotheses

Separate geometry visibility, winding/culling, depth/alpha behavior and native
reflection updates from interpolation. Similar appearance does not establish
the same cause as the accepted proximity-fade repair; that correction concerns
the added Modern close-camera fade. Do not change global culling, depth or alpha
rules without matching the reflected draw and native behavior.

No remedy or verification is claimed at intake. Preserve the working geometry,
camera, light, fire and marker changes. Use copied profiles/saves, muted hidden
replays and the existing guarded investigation with all counters preserved.
The owner approved up to three hours. No GitHub response is authorized.

## Tracker intake

The #47 reporter uses v1.4.0 on Windows 10, GTX 1080 and an Xbox controller.
They report lower-rate character reflections at high output rates, while flying
enemy debris reflects smoothly. Their suggested location is the beginning of
Mizar's Palace with Juno or Vela; it happens every attempt. No comments or support
capture are attached at intake. The owner's missing-geometry symptom is additional
to that original cadence report; investigate whether the causes are related.

## October 25 capture and first hypothesis

The owner completed the copied-profile, 120 FPS capture in Goldwood's first
reflective room. The snapshot, controller input and render traces are retained
privately on D:. A muted replay reproduced the final pose. The original capture
is unchanged. Its neutral disconnected controller samples retained Modern mode
5, which the replay parser rejects; a private replay copy canonicalized only
those otherwise-zero disconnected samples to mode 0. This recording/reader
mismatch is a diagnostic tooling limitation, not evidence of a gameplay fault.

The original `realReflectPrint` brackets its mirrored draws with native
`G_SETGEOMETRYMODE(0x1000)` / `G_CLEARGEOMETRYMODE(0x1000)`. Our DMA triangle
handler overwrites culling from triangle flags and viewport sign alone. The
first candidate retains the guest mode separately and applies its winding
reversal, preserving native double-sided triangles and restoring ordinary
culling after the pass. This is a candidate pending replay and live verification.
The consulted GLideN64 DMA triangle handler has the same overwrite; it does not
independently establish correct JFG reflection behavior.

Animation cadence remains a separate investigation: mirrored skeletal draws
use a temporary adjusted camera matrix outside the regular camera registry.
No cadence resolution is claimed yet.

## Confirmed causes and candidate remedy

There are two independent presentation faults:

1. **Face winding.** The reflected world transform reverses handedness. The
   native pass explicitly requests front-face culling, but the HLE DMA triangle
   handler discarded that request. It drew the reflected model's inner/back
   surfaces, producing apparent holes rather than missing source vertices.
   Retain guest geometry state separately from RT64's per-triangle state, apply
   the requested reversal, keep double-sided flags, and honor the native clear
   at the end of the pass. This applies in Original and interpolated modes.
2. **Skeletal motion ownership.** The native reflection routine emits an
   actor-specific adjusted camera matrix, outside the normal camera registry.
   The skeletal palette therefore had no matched reflection animation history.
   Observe that exact native conversion and retain its inverse-actor, mirrored
   actor, view and projection operands. Accept only unchanged matrix bytes and
   the same live actor/model allocations. Validate the operands against the
   decoded matrix, fold the mirror into the bone's world transform, and use the
   ordinary camera for presentation. A separate reflection history namespace
   prevents reflection birth/death from blocking the direct model's animation.

This does not replace the native reflection system, increase simulation speed,
change the water's opacity, or remove model faces. Native scene cuts, invalid
matrices, freed actors, overwritten buffers and stale records still reject
history. No floating camera guess or position-only identity is used.

### Validation and remaining limits

- Native F3DDKR, semantic presentation, interpolation history and RT64
  interpolation suites pass. Checks cover normal/mirrored and negative-viewport
  culling, double-sided triangles, restoring ordinary culling, buffer reuse,
  actor retirement, room changes, and independent reflection birth/death.
- The copied-input Goldwood replay completes at 120 FPS and Original FPS. The
  source save hash remains unchanged. Comparison images show the corrected
  reflected outer surfaces. These are same-route comparisons, not claims of
  bit-identical timing: startup pacing and scene counts vary between runs.
- The final 120 FPS replay accepts all 924 observed reflection matrix bindings.
  It matches 1,382,130 of 1,386,456 reflected vertex samples across the route;
  only three reflection draws lack history (initial cadence and newly appearing
  reflected geometry), with no conflicting or invalid samples. In the final
  continuous scenes, all 1,506 reflected samples match, increasing total matched
  semantic samples from 3,312 to 4,818.
- Original FPS completes the route without semantic reflection interpolation,
  as intended. The interpolation screenshot helper produces no Original-mode
  images; its post-run image assertion failed after the successful game exit.
  Do not count that helper failure as a game failure or claim Original screenshots.
- The owner preview is 120 FPS with the FPS box hidden and a separate copied save.
  Owner visual acceptance and the reporter's Mizar's Palace/Juno/Vela retest
  remain pending. No public issue reply, release, or closure is authorized.

Private evidence: `D:/JFG-private/reflection-geometry-20261025/`, including the
sealed baseline, original inputs, private input normalization receipt,
`replay-validation.json`, native test/build results, and the preview receipt.
Initial compiler attempts exposed incorrect opcode macro names and a missing
matrix-conversion forward declaration; corrected builds and tests passed. A
source edit attempted during compilation was refused by Windows; no preview
binary was replaced while running.

### Transferable lessons

Keep guest rendering state separate from host-derived per-primitive state.
A mirrored model needs reversed winding and independently owned motion history.
Shared source vertices and bone palettes do not make the ordinary and reflected
passes interchangeable. Capture native transform provenance before temporary
stack/matrix storage is reused, and make reflection visibility independent of
ordinary actor interpolation.

Source: [F3DDKR adapter](../../../src/renderer/rt64_f3ddkr.cpp),
[presentation identity](../../../include/jfg/renderer/presentation_identity.hpp),
[native conversion observer](../../../src/boot/native/guest_execution.cpp). Related:
[Vela proximity fade](vela-skirt-focus-tearing.md),
[actor history fallback](camera-turn-actor-jumps.md).

## Owner acceptance, October 25

The owner approved the reflection fix after two checks. They did not specify
those checks' exact characters or locations, so no additional route coverage is
claimed. Both corrections are accepted locally and remain unreleased. Their
newly reported laggy shadow is separate work under GH-046; it does not revoke
reflection acceptance. The original #47 reporter has not yet retested this build.

## October 27 local batch audit

Status: owner-approved local reflected geometry and motion corrections; unreleased.

Correct mirrored face culling and keep mirrored skeletal presentation history separate from ordinary actor draws.

Verification: Recorded Original/120 native and Goldwood replays passed; Owner approved after two checks; unspecified additional route coverage is not assumed. No GitHub action was performed.
