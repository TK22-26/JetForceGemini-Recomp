# RENDER-018: Dead drone bodies jitter with camera movement

- Status: owner visual pass on the latest route, supported by capture; exact seeded reproduction unverified; not released.
- Severity: visible rendering defect; release qualification follow-up.
- Affected build: v1.3 preview in the Tawfret capture package, launched with standard full-run diagnostics on 2026-10-19. Exact active session metadata is retained privately.
- Report: dead drone bodies lying on the ground appear to miss interpolation, similar in appearance to the earlier glass jitter.
- Reproduction: defeat a drone, leave the body on the ground, then walk or turn the camera while looking at it. The owner explicitly confirmed camera/player movement is the trigger.
- Evidence: owner reports, completed full route and three focused captures on 2026-10-19. The latest candidate has qualified owner visual acceptance; details and limits below.
- Cause: detached body geometry lacked actor ownership; separately, exact zero-scale hidden bones invalidated the entire visible skeleton. Similar appearance did not establish the same cause as glass.
- Remedy: track bounded detached-body vertex ranges and exclude only topology-proven, non-rendering collapsed points from semantic validation; retain visible-geometry safeguards.
- Validation: focused components, actual captured-memory checks and runtime build pass. Owner says the latest route looks good; exact seeded route and broader cutscene coverage are not verified.
- Compatibility lesson: acceptance for live drones and glass does not cover the separate grounded/dead actor state.

Related: [actor interpolation](actor-jitter-edge-culling.md), [boss camera sweep](boss-camera-sweep-pop.md), [v1.3 qualification](../releases-1.3.0-qualification.md).

## Owner clarification and first evidence

The owner locates the report approximately in the second Goldwood room containing drones. Standard capture records repeated groups of 48 invalid semantic samples and 215 missing previous vertices for several actor addresses during combat. Actor addresses must still be correlated to deaths; counts alone are not proof of the cause. A separate severed-limb custom path also exists and needs ownership review. No renderer check has been weakened.

## Targeted capture plan

The owner will finish the long route normally and can start a short second capture. Defeat a drone in early Goldwood, orbit/walk near the body, then close with the body still loaded. The standard recorder already writes final guest RAM at exit. No need to repeat New Game through Vela for this issue.

Static review confirmed behavior 64 (SeveredLimb) draws allocated baked geometry through objPrintSeveredLimb and owns no model instances. Its rigid transform is observed, but current presentation_rigid_key only recognizes model/glass geometry. An older retained combat RAM snapshot contains such an actor with its opaque and transparent display lists. This establishes an unhandled body-part path; it does not yet establish that this is the owner's intact corpse symptom. Existing rejected normal-model samples remain a separate lead. No runtime candidate is installed.

Archive inspection is read-only, not a gameplay replay. A broad archival filename enumeration took about a minute; further inspection uses selected known snapshots only. No game or save was modified.

## Review launcher

A separate **JFG - Drone Body Capture** shortcut records to the private owner-corpse-capture evidence folder. It uses the same runtime and save/profile as the full-run launcher; no candidate change is represented. Start it only after closing the current game and launcher. Standard recording begins on Play. Keep the body loaded when closing so final guest memory can identify the rejected geometry. A short movement/camera orbit is enough.

## Focused owner capture and candidate (2026-10-19)

The owner reproduced the jitter at the very end of the targeted capture and
reported that only some bodies show it. The final room-21 snapshot contains a
grounded behavior-64 SeveredLimb actor near the player, with no model instances.
Its two lists reference three baked vertex batches (18, 24 and 9 vertices).
The other remaining limb has 24, 21 and 3 vertices. Source and snapshot agree:
objPrintSeveredLimb uses the captured rigid transform but independent geometry.

Candidate: bind those exact bounded DMA ranges to the live actor lifetime,
control allocation, vertex allocation and camera. Retain existing exact geometry,
matrix-product, lifetime, ambiguity and cut checks. No guest simulation or geometry
is modified. The normal-model rejection lead was not present for the final body;
it is not the basis of this remedy. Focused tests/build and owner verification
are pending. No claim of a visually verified fix yet.

## Component validation

Synthetic ownership checks pass for body geometry, alternating matrix buffers,
actor deletion/reuse, range boundaries, invalid pointers, unproven branches,
unterminated lists and unrelated behavior. The first test run exposed shared
fixture-state contamination in the new test block, not a runtime crash. Isolating
and restoring that block's RAM fixture fixed it; the full semantic presentation
and RT64 interpolation test executables both pass.

A private read-only C++ check ran the production identity tracker against the
owner's final RAM snapshot. Both remaining limb actors acquire the expected
three ranges (51 and 48 vertices respectively); every recorded batch receives
the correct actor-owned rigid key. This validates the actual captured data layout,
not visual smoothness. No gameplay or replay was run by the agent.

Private evidence: owner-corpse-capture/20261019-044350-
ef63d1ee3fd24843b8fd9641b57d3326 under the Tawfret review evidence root.
No RAM, ROM, save or generated game body is included in public source.

Runtime Release build passed. The candidate is installed in the existing Drone Body Capture preview; saves and configuration were preserved (start muted as requested). Owner visual review remains pending. Runtime SHA-256: 39273f6f7f4e90217b5fa554d436ac4d95f9f9d191bea9381a46dcbec214bd22.

## Owner follow-up: one remaining case in the candidate

The owner reported another jittery body at the end of the candidate capture
(04:55:23 UTC). This capture uses the installed candidate SHA, not the baseline.
At room 16 near the end, the normal BlueAnt actor 0x801c69d0 has 48 invalid
semantic samples across 89 scenes, with the other 215 vertices consequently
unable to retain history. Its detached body-part actors are separately owned.

Retained model-instance memory still contains both palette buffers. Bone 21 has
an exactly zero 3x3 linear transform and finite translation/w=1; neighboring
bones have very small scales. The actor itself has already been freed/reused, so
its final object fields are not treated as reliable evidence. The palette and
model-instance addresses are independently named by the preceding draw log.

New lead: the native death animation collapses a hidden bone to a point.
Our inverse-matrix validation rejects that singular transform and invalidates
the whole actor. A remedy must prove affected triangles have no visible area;
simply weakening inverse validation could create seams. The first candidate is
therefore incomplete, and the issue remains open.

## Second candidate: collapsed hidden bones

The first candidate's final capture has explicit matched rigid ownership for
the surviving detached bodies (private per-actor counts retained). A separate
normal skeleton repeatedly fails inverse validation during its death animation.
The new candidate recognizes only an exact finite affine point collapse and
then checks every incident triangle. Only triangles collapsed to the same world
point with the same actor/model/camera ownership qualify. Their GPU geometry is
unchanged, and their matrices remain at the current native endpoint; interpolation
cannot expand hidden geometry back toward an earlier visible pose.

A collapsed point connected to any visible triangle still invalidates the actor.
Almost-zero scales, unknown ownership, malformed topology and nonfinite matrices
also retain the existing rejection behavior. Focused regression checks cover
both continued interpolation of the visible body and refusal to weaken the seam
safeguard. New semantic-collapsed trace rows identify excluded hidden samples in
the next owner capture. Build and owner review are pending for this candidate.

### Scope of the underlying flaw

The owner correctly identified this as a broader renderer problem. The inverse
validation and per-actor fallback are shared by all skeletal geometry, so the
candidate is intentionally independent of drone type, health, room and animation.
Other invalid samples are not assumed to be the same cause without matrix/topology
evidence. Public regression fixtures use arbitrary identities, not drone assets.
The first compile of the helper exposed an insertion-scope mistake; it was moved
outside the sample structure before component validation. No failed build was
installed or launched.

The earlier full-run log also contains sustained invalid-sample rejections in
behavior-95 cutscene actors, as well as behavior-24 drones. Their exact matrices
were not captured at those times, so this is a broader verification target,
not proof that all those rejections share the zero-scale cause.

Focused semantic and RT64 interpolation checks pass for the generalized candidate.
A standalone C++ check recognizes the recorded bone-21 point collapse in both
retained palette buffers and rejects the neighboring almost-zero scales. That
standalone build caught a missing explicit span header include; it was corrected.
The runtime Release build passed after the header correction. Owner visual
verification remains pending; this is not a released resolution.

Runtime Release build passed. The candidate is installed in the existing Drone Body Capture preview; saves and configuration were preserved (start muted as requested). Owner visual review remains pending. Runtime SHA-256: 31d5c9308ff9043e1022daf9e980a00e2faf34e202d343acd6ae7569fc784dd7.

### Location within the follow-up recording

The sustained normal-skeleton rejection spans about 259.49–262.47 seconds into
the 04:55:23 UTC capture: 90 source scenes, approximately three seconds near its
end. Each scene rejects 48 hidden-bone samples; subsequent scenes lose history
for the remaining 215 vertices. This is separate from the rigid body-part
ownership added by the first candidate.

The generalized candidate is installed and the muted Drone Body Capture launcher
has been reopened. Verify dying intact drones as well as their settled detached
bodies while moving the camera. The next log should show semantic-collapsed rows
instead of the sustained invalid-sample group, with matching visible geometry.
A future full-route review should also revisit opening cutscenes; their prior
invalid groups are not considered resolved without evidence.


## Qualified owner acceptance and latest capture

The owner reports that the second candidate looks good, while explicitly noting
that the exact seeded route was not repeated. Record this as a visual pass for
the tested route, not exhaustive parity or a released resolution.

The 05:11:35 UTC owner capture ran the installed runtime
31d5c9308ff9043e1022daf9e980a00e2faf34e202d343acd6ae7569fc784dd7
and ended normally with final RAM. Its last progress sample records 7,110
retraces, 3,481 game updates, and zero audio-device underruns or overruns.

There are 577 semantic-collapsed events across three actor addresses. Most
exclude the same 48 hidden samples implicated in the prior failing capture;
16 events exclude 15 samples. No invalid-sample rejection is recorded anywhere
in this capture. The affected actors retain matching history for visible geometry.
Some normal cut/missing-history rows remain, so this is not a claim that every
vertex interpolates across every spawn, cut or visibility transition.

Private report: corpse-general-candidate-owner-review.json, derived from
owner-corpse-capture/20261019-051135-970a414dca53482eafde3fa883176490.
The log validates the repaired rejection path during this route; it does not
reconstruct an identical random seed. Earlier cutscene invalid groups still
require separate coverage and are not declared fixed by this capture.

Transferable lesson: validate semantic history against geometry that can actually
render. An exact singular transform can intentionally hide a bone; it should
not spoil unrelated visible geometry when ownership and topology prove that
exclusion is safe. This is a shared renderer correction, not a drone-specific
animation workaround.

## v1.3.0 source availability

The documented change is included in tag v1.3.0 (launcher/source
02be6fa9a4c50f4056f778c5148ca8ac70b0e92b; clean runtime
665596482a7395593e85dbe73f1bd4b016d183d9). See the
[combined release qualification](../releases-1.3.0-qualification.md) for owner
acceptance, source CI, package and publication evidence. Earlier failed attempts
and the scene/device/seed limits above remain part of this record; inclusion
does not turn an unverified broader report into a confirmed resolution.
