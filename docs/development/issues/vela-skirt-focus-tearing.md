# RENDER-VELA-SKIRT: Focus-dependent skirt separation on slopes

- Status: resolved locally: owner confirms the skirt/focus repair and smooth transparency replacement. Build, component and rendered-replay checks pass; unreleased.
- Severity: moderate visual geometry defect; no gameplay failure reported.
- Reported: 2026-10-24.
- Build: Flight Motion Fix Preview, runtime SHA-256
  `94da3fefbc7ae2327deec3bff2cb8b7f39c30e17eefb4084860d48046d050d2c`,
  based on branch `fix/audio-latency-recovery` at `1d631c0` plus local rendering work.
- Profile: 120 FPS, VSync on, Reduced blur, fog100; copied owner save/settings.

## Reproduction and evidence

Stand Vela on a sloped surface and look upward at a specific camera angle.
Owner screenshot shows an apparent separation/inverted section near the rear
skirt/hip. The circular metal-room screenshot and full latest capture are retained
privately under `vela-skirt-focus-20261024` and the linked source capture.
The reported slope is in room 170.

Owner reports a deterministic stationary comparison: focused game is broken,
unfocused window is correct, and clicking back into the game immediately restores
the defect without moving Vela or the camera. Owner reproduced it with Original FPS after restarting; original-hardware
behavior has not been claimed. Do not assume this is a regression from
the new camera precision change until a controlled comparison supports it.

Source capture:
`camera-flight-integration-20261024/live-captures/20261024-191151-83784760a0114a4b9c5345f3471431ef`.
Owner was asked to close with the affected pose retained for exit RDRAM. No live
profile or save is edited; replay/build work uses copies on D: and remains muted.

## Hypotheses and work

Focus-dependent pausing may switch from interpolated geometry to a native endpoint.
Check mixed ownership, cross-bone triangles, local/world interpolation, culling and
near-plane handling against the same captured state. These are hypotheses, not a
confirmed cause. Prior character seam and dead-body repairs may be relevant:
[character seams](character-seams-lighting.md),
[dead drone jitter](dead-drone-camera-jitter.md), and the newly accepted
[camera/ship candidate](cutscene-camera-cadence.md).

Owner approved one hour. The production guard remains enabled on the original
high-refresh investigation/root with all prior counters preserved. Upstream pinned
reference review/catalog consulted; no upstream update is authorized or planned.
Record attempts, actual cause, tests and live verification here as work proceeds.

## Focus and fade evidence

The long stationary reproduction is in room 170. At VI17628 the additional
Modern proximity fade settles at opacity240 instead of the native255 and
reappears at every recorded focus reacquisition (17963,19902,20274,20361,
20429,20508,23163,25974). The hook at `0x80015E3C` explicitly excludes blocked
input. Thus focus changes the rendered opacity even while the camera stays put.
`pc_camera_player_alpha` starts fading80 units from the upright body. This is a
concrete explanation for the focus correlation; the visual cause still needs
an identical-pose opacity comparison. Partial transparency can expose internal
surfaces without moving vertices. Do not describe that as proved geometry tearing.

The playerGirl semantic history has5381 ordinary room170 scene records with no
reported invalid, cadence, duplicate, missing-endpoint or motion rejection;
the remaining two are room-entry/transition boundaries. Each ordinary scene
has four output phases at120FPS. This weighs against the original mixed-history
hypothesis. Full replay and bounded GPU screenshots are running against copied
save/input; a private opacity-off/material probe is an experiment, not a fix.

Private evidence: `vela-skirt-focus-20261024/focus-fade.json`,
`render-holds.json`, `replay-baseline` and the preserved pre-probe source files.

## Original FPS and controlled opacity comparison

The second capture (20261024-194205) confirms Original FPS, room170 and native
opacity255 reduced to207 for the stationary player. This excludes high-refresh
interpolation as a necessary trigger. The close-camera fade was introduced by
our Modern-camera support, and its blocked-input gate changes appearance on
focus loss. The native opacity return is stored at actor+0x39 and selects the
native transparent model draw path. Internal skirt/body surfaces become visible
through the partially transparent outer mesh; this is not vertex separation.

A controlled replay with the same input and unchanged camera/matching code shows
the skirt intact when only the added fade is disabled, versus exposed overlapping
surfaces when it is enabled. Important limit: live-map warps are absent from that
pad replay, so it reaches room67 rather than the owner's room170. The comparative
images establish the transparency failure in a second pose, not a replay of the
exact slope. The newer owner capture and live retest remain the room170 evidence.
The first comparison executable failed to start because its private runtime was
missing DLLs; adding the same pinned dependencies allowed the replay to finish.

The candidate leaves the native opacity result and depth-writing path intact.
It passes the additional proximity fade as immutable per-task actor metadata to
the renderer. A stable ordered coverage mask is shared across all surfaces of
that player, allowing depth testing to choose the front surface without exposing
internal faces. Focus no longer disables that visual effect. Native aim/death
fades, Original controls, simulation vertices and camera interpolation are not
modified. Coverage ownership includes cloned UV vertices and is reset before
unrelated geometry; shadows and non-scene targets are excluded.

This changes how the added transparency looks and needs owner visual acceptance.
Shader compilation, CPU ownership/clone tests and GPU comparison are pending.
The first build stopped at the existing RT64 source hash guard; the follow-up
accepts the precisely verified generated variant while retaining original pins.
Private evidence: original-capture-summary.json, replay-opaque2, coverage-build*.log.

## Candidate checks

The complete runtime and both Direct3D/Vulkan shader variants built successfully.
All five targeted suites pass: F3DDKR DMA/UV ownership, RT64 interpolation,
semantic presentation, history and Modern controls. New command-handler cases
exercise the fade on Original and interpolated presentation, UV cloning, a
mismatched actor, non-scene targets, and switching to an unrelated matrix. The
RT64 input hash gate accepts both original/candidate LF and CRLF sources and
still rejects a changed source. This is build portability checking, not a live
Vulkan/Proton test.

The preview uses the latest copied profile with Original FPS, Reduced blur,
fog100 and no FPS overlay. The first preparation used the wrong profile root
and stopped before copying a save; it was corrected to userdata/profiles/default.
Source and copied save hashes match. GPU comparison and owner verification remain
pending. Candidate runtime SHA-256:
`eca370274855652dba4a639e940f4a495d69b616c46ed6dcfc178fda54204d8c`.

## Scene-submission handoff correction

The first coverage GPU replay removed the exposed surfaces but also lost the
intended fade. Its metadata required the calculation and task submission to
occur on the same VI. The capture shows the opposite: at VI11199 the prior main
scene is submitted, then the player fade is computed and a tiny shadow task is
submitted; that newly built main scene is submitted at VI11201. The metadata
therefore reached shadows, where it correctly had no effect, but expired before
the actual model draw. This failed candidate was not opened for owner review.

The corrected lifetime uses an unconditional native-update generation, retaining
the metadata through the following update. It still validates actor/control/
header identity and expires after that submission interval. It deliberately does
not use gameplay_trace_updates or completed_game_updates: those existing counters
advance only with particular diagnostic streams, which would recreate a
logging-dependent rendering bug. Additional temporary observers are removed
from the normal preview build after the handoff replay. GPU and live acceptance
of the corrected candidate remain pending.

## Corrected GPU result and normal preview

The generation-bound replay completes successfully and records nonzero fade
values on the main scene's player triangles, with the original opaque depth path.
Its image shows the stable coverage pattern and an intact skirt rather than
internal surfaces blending through it. The previous same-VI candidate recorded
coverage only on offscreen tasks, confirming the handoff failure. The short
comparison is a second room67 pose, not the exact room170 owner slope.

Both temporary handoff/triangle observers were removed and the normal consumers
rebuilt successfully. The owner preview is opened with logging OFF, no diagnostic
arguments and no FPS overlay, with the latest copied save and Original FPS. Its
shared coverage pattern has a visibly different fine dotted appearance at close
range, which still requires owner acceptance along with the exact slope/focus
retest. High-FPS compatibility is covered by CPU ownership tests and the GPU
replay; this does not replace owner Original/120 FPS review.

Clean preview runtime SHA-256: `0773e8ef3147050d8bdcb2f5d5aa8d84d1de1b0931e6906e1a67986738ff5cc1`.
Private evidence: handoff-analysis.json, generation-analysis.json,
replay-generation/frames, clean-build.result.json, live-prepared.json.
No commit, public package, issue reply or release is made by this work.

## Owner verification and fade appearance review

The owner confirms the skirt is fixed in the normal preview. The same review
identifies the ordered coverage mesh as an undesirable visual tradeoff: the
whole nearby character has a visible screen-door pattern. This is deliberate
8x8 Bayer coverage in the candidate shader, not damaged textures or animation.
Geometry/focus correction is locally verified; fade appearance remains open.
The owner approved three hours for code review and improvement on 2026-10-24.
A smooth fade must resolve the nearest player surface before blending, preserve
world occlusion and avoid repeated blending of interior triangles. The follow-up smooth layer implementation and verification are recorded below.

## Smooth layer candidate

The follow-up replaces ordered pixel coverage with a separate color/depth layer.
The added opacity again selects native transparent-object ordering, but does not
blend each player triangle directly. A copy of the current world color/depth
receives the player with opaque output and depth writes, choosing the nearest
surface regardless of internal mesh order. The finished color layer is blended
once at the added opacity; main world depth and native coverage stay unchanged.
Layer allocation is lazy and reused, with separate actor keys and native fades
excluded. The pattern is removed from RasterPS. No image/style acceptance is
claimed until GPU and owner checks pass. This rendering pass has a cost when a
player is faded, which must be measured rather than assumed free.


## Smooth-layer verification and review handoff

The smooth candidate builds with normal and multisampled DXIL/SPIRV shaders.
All five targeted CPU suites pass; actor ownership now includes an explicit
actor key, including Original presentation and UV clones. The bounded additional
ship-light observer also passes the command-handler suite. Its first test-link
command used the wrong project directory; correcting it to tests/ resolves
that build invocation failure.

The first replay's screenshots preceded the close-camera movement, so those
images were not used as fade verification. A second bounded, muted replay
captures the actual fade: the character is smoothly translucent without the
ordered mesh, and the skirt silhouette remains intact in this second room67
pose. This is not a substitute for the owner's exact room170 slope test.
Private evidence: camera-fade-review-20261024/layer-late-gpu.json,
replay-layer-late/frames, tests.log and probe-standard-test.log.

The resource review additionally restricts lazy layer allocation to calls in
the current framebuffer and requires both color and depth targets. Color-only
and unrelated offscreen buffers do not allocate a player layer. Resources are
reused; the normal scene without added player fade does not execute the new
composite. The extra copy/composite cost still needs live timing review.

The owner preview copies the latest save/settings, uses 120 FPS, and enables
explicit state capture with the FPS overlay hidden. The newly requested ship
vertex color/UV/matching observations run only with an interpolation trace;
launcher environment sanitization is preserved. The earlier normal preview did
not capture the owner's short flight; its copied diagnostic-session pointer was
stale. The new profile omits that pointer and will create a fresh session.
No native ROM/save contents are published. Exact-pose and Original-FPS visual
review, plus live Vulkan/Proton/MSAA checks, remain unclaimed.


## Owner acceptance of smooth transparency

On 2026-10-24 the owner reports that transparency looks good in the smooth-fade
preview. This accepts the visible fade replacement while retaining the prior
skirt acceptance. The same capture still reproduces the separate Vela ship-light
cadence issue; no ship-light fix is claimed by this result. Runtime SHA-256:
f02fed538d35a6629f083bc9a8b7eaf30d724a45712f088d35d3d7411a0c936b.


## Resolution scope

The owner requested the confirmed rendering repairs be marked resolved on
2026-10-24. The focus-dependent skirt defect and visible mesh pattern are
resolved locally by the accepted depth-resolved smooth player layer. Original
native fades are excluded; no release or merge is implied by this status.

GitHub #52 separately reports fading during combat with the camera zoomed out.
Improving how an active fade renders does not establish that its activation
distance or combat trigger is correct. That report remains open for its own
reproduction and review.
