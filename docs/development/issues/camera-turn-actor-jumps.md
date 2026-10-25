# Actor jumps while rotating the camera

Status: camera-continuity correction owner-verified locally on 2026-10-24; unreleased.

During the travelling-shot diagnostic preview (120 FPS, copied save), the owner reports drones and tribals jumping sideways while the camera spins and a drone begins running. Severity: visible gameplay rendering defect. This is distinct from choppy travelling bullets and grenade shockwaves in the same capture. The preview retains the previously approved camera precision, proximity fade, and ship-light fixes; its only new runtime work is tracer metadata observation, with no projectile interpolation change yet.

Evidence is retained privately in D:/JFG-private/shot-effects-fix-20261024/live-captures/20261024-215441-ac3cc9378a254005b7f372e4c00151f0 (input, actor state, interpolation trace, final RDRAM). No video was automatically recorded. Native simulation displacement, camera/actor history matching and scene holds remain hypotheses, not established causes. Compare actual source motion and presentation before changing global continuity guards. Preserve ordinary actor behavior and invalidate history at real discontinuities.


The earlier actor/LOD ownership fixes remain present (see actor-jitter-edge-culling.md). The new probe finds entire actors absent from the preceding draw, rather than invalid/ambiguous geometry: initial missing-key samples have no old vertices for that lifetime. The existing fallback holds both actor geometry and the camera at the new endpoint while scenery uses an intermediate camera. This can move an otherwise valid actor sideways relative to the room when it becomes visible again. A candidate now holds the actor at its current world pose but retains the verified shared camera interpolation. It does not fabricate an old pose or relax discontinuity/invalid-data guards. Live verification is pending. The private build/replay records also preserve a probe patch anchor failure, UTF-8 BOM correction, diagnostic startup rejection corrected by restoring the required host-clock option, and test variable-shadowing correction.


The completed probe also confirms real detail-model switches: 3,466 sampled missing corners had an existing old joint with a different model/instance identity. The initial actor +0x3A selector remained constant, so it must not be treated as a complete LOD-change detector. Both visibility re-entry and changing mesh topology need independent camera continuity. The candidate explicitly preserves unmatched geometry status and uses zero geometry velocity; it only interpolates a verified continuous shared camera. New invalid samples, conflicting clones, cadence breaks, real motion cuts, camera-generation changes and mixed camera provenance still reject this fallback.


## Owner review, 2026-10-24

The owner reports gameplay looks good and can no longer reproduce the prior travelling-bullet, grenade-shockwave or sideways actor issues. These candidate changes are now visually verified locally, not released. Remaining distinct reports: grenade fire appears to retain native cadence, and the exit marker opening while the camera moves appears to jitter. Muzzle flashing was not separately identified as remaining. Actor detail visibly decreases with distance; the owner requested an Original/High Actor LOD option under Game > Settings. Do not conflate those open paths with the accepted fixes.
