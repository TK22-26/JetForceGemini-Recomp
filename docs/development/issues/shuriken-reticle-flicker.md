# RENDER-008: Shuriken reticle flickers and disappears

Status: owner reported during longer acceptance capture; cause and remedy unverified. Severity: visible aiming feedback failure. Affected: local draw-key preview, 120 FPS, VSync On, modern mouse/keyboard, runtime source 27ddef0a5ed4afd1f1f9c26a5590b590cda5fe8e (SHA-256 db65b460f399b550ca8a3ad0d98f5374d5e00a95dc4a7073edfa2649fa6772c6).

## Symptoms and reproduction
The owner reports that the shuriken reticle flickers and eventually disappears altogether while continuing the tutorial capture. The owner explicitly confirms this occurs both with Aim held and without Aim. Exact first affected frame, weapon ammo/state and native no-Aim visibility rules are not yet established; do not infer the original game always draws a hip-fire reticle.

Report marker: 2026-10-16 13:43:01 UTC, about 429 seconds after the session's 13:35:52 start. This is when the report was recorded, not an exact glitch onset timestamp. Private evidence: final-measurement-20261016/session 20261016-133552-e6cd10c21fef4225a62f3f7b22eaadfa. Inputs, timing, interpolation and gameplay streams continue. Preserve startup/idle and input timestamps in raw evidence.

## Initial investigation and hypotheses
Historical commit f53dea1dcd64262c4b90e45864b0f33d87908863 preserved CPU framebuffer effects for software-drawn crosshairs and rain through color readback, CPU-edit import and game-selected buffer presentation. It is an ancestor of the active build. The remedy was not simply omitted by the develop merge.

Potential causes include loss/overwrite of CPU-drawn reticle pixels during interpolated presentation, wrong framebuffer ownership/lifetime, or guest weapon/aim-state gating. These are hypotheses; none is established by the live report. The existing airborne-aim adapters and tests cover pistol/sniper, not all shuriken states. Owner reports both aiming modes, so do not restrict reproduction to airborne aim.

No experiment, rebuild, runtime change or claimed fix accompanies this initial source review while the owner is measuring performance. After the run, correlate recorded inputs/weapon state and inspect framebuffer changes/presentation ownership, using a copied save and muted bounded replay if the existing guard scope permits. Preserve every failed or inconclusive result.

## Compatibility and acceptance
Reticle pixels may be CPU framebuffer edits rather than ordinary graphics batches. Verify real final presentation and the selected guest buffer; smooth actor interpolation does not prove software effects survive. Require stable shuriken visibility across sustained aim, throws, movement and mode transitions, with native visibility expectations checked. See [continuous airborne aim](widescreen-pointer-and-airborne-aim.md) and [high-refresh rendering](high-refresh-rendering.md).
