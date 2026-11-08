# GH-046: Character shadows jitter at high frame rates

- Status: owner-approved local Enhanced Shadows v26; unreleased.
- Severity: moderate visual smoothness issue.
- Report: [GitHub #46](https://github.com/TK22-26/JetForceGemini-Recomp/issues/46).
- Intake: 2026-10-24.
- Affected report: v1.4.0, Windows10, GTX1080, Xbox controller; high frame rate,
  exact target not specified.

## Symptoms and reproduction

The reporter says character shadows do not follow movement smoothly at high
frame rates, reproducible whenever running. No support ZIP, location, character,
video or subsequent comment was supplied at intake.

## Intake evidence and initial hypothesis

This is distinct from the accepted flight-camera, ship-beam and smooth-player
fade corrections. Those tests do not cover the projected ground-shadow path.
At intake, a shadow updating only at native scene cadence while the character
interpolates was a hypothesis. The investigation below compares the moving
player and shadow at Original and 120 FPS, then correlates shadow ownership
and transform endpoints before selecting an interpolation policy.

At intake, no patch, runtime test, GitHub reply or closure had been performed for #46.

## Owner reproduction and active investigation, October 25

The owner approved the reflection fixes after two checks, then confirmed visible
shadow lag/jitter in the same 120 FPS preview. The captured route is preserved;
no second capture is required for initial analysis. Two hours are approved on
the existing guarded high-refresh investigation, with all counters preserved.
The investigation initially separated mask animation, ground projection,
camera motion and simulation updates; the candidate findings follow below.

The latest reflection-preview session contains only the title/intro corridor
actors and neutral input, so it cannot establish moving-player shadow cadence.
Use the earlier recorded reflection gameplay route for the initial diagnostic
replay; preserve the owner report separately from that evidence. Native shadow
projection writes transient, clipped world-space vertices, outside skeletal
model ownership. Those writes and their renderer correspondence supplied the evidence for
the candidate below.

## Candidate under test

The native producer rebuilds floor-clipped shadow polygons into alternating
shared buffers. These vertices previously had no actor/receiver ownership. The
candidate records the original receiver triangle and projector boundaries,
identifies surviving corners by those boundaries, and presents shadow position
and UV coordinates with the same camera phase. Newly exposed or ambiguous
geometry retains the endpoint; unrelated corners are never matched by draw order.
Separate shadow history groups preserve the directly drawn actor and scenery.
The CPU-filtered shadow mask and game simulation remain native.

Initial build found two test-only warnings (narrowed byte index and a shadowed
local name); those are corrected. Final automated results are recorded below;
owner visual approval remains pending.

## Replay findings and compatibility

The first candidate matched cinematic shadows but not the playable character.
The player geometry was correctly identified; its draw used a copied camera
matrix in materialized overlay storage, so the camera-address lookup found no
owner. The revised candidate accepts a copied matrix only when its complete
product matches one unambiguous, captured view/projection pose. Two identical
copies of that pose qualify; conflicting cameras, stale bytes and mismatched
products do not. This is restricted to proven projected-shadow vertex ranges.

The 120 FPS gameplay replay of Juno in the reflective Goldwood starting area
completed successfully. The camera-alias candidate matched 17,400 of 18,279
player shadow samples across 871 scene draws. During the 240 sampled updates
with player movement, 4,671 of 5,316 samples matched. Newly exposed/clipped
receiver corners are held or receive camera-only motion rather than borrowing
another corner. This is partial automated coverage, not owner visual approval.

The four existing renderer/semantic/history test executables passed. Additional
coverage checks original receiver vertices, projector corners, floor/clip-edge
intersections, alternating buffers, actor retirement, room changes, stale vertex
bytes, copied camera matrices, conflicting cameras, and clamped shadow UVs.
The final bounded-lookup revision passes all four suites. Both the 120 FPS and
Original FPS replays complete successfully (4,560 VI retraces each).

The CPU-rendered/softened shadow mask keeps its original image and authored
silhouette cadence. The candidate corrects projection geometry, sliding UVs and
camera phase; it does not invent interpolated texture silhouettes. Static floor
receiver identity is proven by its source plane and original X/Z triangle.
Changing receivers or ambiguous clipping intersections deliberately lose history.
Moving/dynamic receiver coverage and the reporter's exact setup remain untested.

Private evidence: `D:/JFG-private/shadow-cadence-20261025/`, including the native
producer trace, failed first ownership attempt, copied-camera diagnostics,
component test results, immutable runtime copies and paired replay records.
No ROM, generated game source, personal save or raw capture is published.

Transferable lesson: procedural decals need both geometry and texture-coordinate
history. Match the meanings of clipped corners, not allocator addresses or list
order, and validate camera operands even when the game keeps equivalent copies.
Keep decal eligibility separate from the actor and static room so a new clipped
polygon cannot freeze unrelated animation or camera motion.

Final-check failures were confined to helper/test integration: the public identity
header now uses its explicit matrix array type, and the copied-camera test uses
a valid perspective projection. Its initial identity/orthographic projection was
correctly rejected by the existing guard; that rejection remains a negative test.

The isolated **JFG - Shadow Motion Fix Preview** was opened at 120 FPS, with a copied
save and hidden FPS overlay. It retains the owner-approved reflection correction.
Runtime SHA-256: `cecdf6cfe9f4b94fcf0f66f51288ae0fb6a2fb0090ad055cefaa7f06d7aa9a91`.
Owner review and the original reporter's retest are still pending; nothing is
released, posted to GitHub, committed or pushed by this investigation.

## Owner rejection and renewed investigation, October 25

The owner reports blocky shadows, flicker and continued unsmooth motion in the
120 FPS shadow preview. The capture is closed. The first candidate is rejected;
automated vertex correspondence and successful replay exits did not establish
visual correctness. One further guarded hour is approved with existing counters
preserved. The reflection remedy remains owner approved. No shadow resolution
is claimed. Investigate projection/UV coherence and the CPU-generated mask
before another candidate; preserve the rejected capture and runtime.

Private replay harness correction: its mute file initially used the wrong field
order and was rejected by the strict audio-settings parser. The next replay
uses `version`, `volume`, then `muted`, with zero gain and mute enabled. This
was a harness configuration error, not a change to game audio behavior.

The follow-up capture's active input spans VI 1,222,352 to 1,227,403 after a long
neutral title session. The owner confirms the defect is during gameplay.
The original recording is preserved. A reconstructed replay that removed too
much boot/title lead-in stayed in character selection; it is not gameplay
validation. The next comparison preserves a full minute of title lead-in.

Source review identified another candidate defect: shadows can recognize a
copied ordinary camera by its complete operands, while static receiver meshes
only recognized its original allocation address. The resulting precise and
fixed-point projections can disagree in depth. A restricted full-operand camera
lookup is being tested for those receiver meshes too. This is a hypothesis until
the paired render comparison and owner review establish the visual result.

## Coplanar projection defect isolated

The camera-ownership-only comparison was insufficient: the ordinary scenery
history still presents the emitted fixed-point camera products. The rejected
shadow binding instead recomputed `view * projection` from floating-point
operands. Thus the decal and its receiver could have different clip-space depth,
even with the same identified camera and at the native endpoint. This is a
concrete discrepancy in the first candidate, consistent with coplanar flicker;
its visible effect remains subject to the revised render/owner comparison.

The revised binding retains operand validation and uses the exact emitted
camera product for shadow presentation. The broader scenery-ownership change
was removed. A shared tested shadow-binding helper now checks that a quantized
camera is preserved exactly, distinct from its floating-point source; invalid
matrices, unknown vertex offsets and nonfinite positions remain ineligible.
Clipping identities, CPU mask generation and the approved reflection fix are
unchanged. Build/replay and live verification of this revision are pending.

The revised depth-binding build and all four existing component suites pass,
including the new exact-emitted-camera regression test. The gameplay and
Original FPS replays are running before the copied-profile preview is opened.
The first candidate remains rejected; this revision is not yet visually verified.
Private follow-up evidence: `D:/JFG-private/shadow-cadence-followup-20261025/`.

The rejected binding also supplied a different matrix for the same ordinary
camera identity than the directly drawn actors. The semantic camera collector
correctly treated those claims as conflicting and removed the shared camera
history. Both the rejected replay and the insufficient ownership-only trial
recorded zero camera-only birth samples in the sampled gameplay interval.
The exact-emitted-camera revision records 26,940 matched shadow vertices plus
5,229 camera-only samples (all of its 32,169 samples); it restores a common
camera phase for newly clipped geometry without inventing prior corners.
These route reconstructions differ slightly in exact scene timing/poses, so the
counts establish exercised paths rather than an identical-frame performance
or visual comparison. Frame captures are retained privately. Owner confirmation
is still required for blockiness/flicker and motion smoothness.

The revised candidate passes all four component suites, a reconstructed 120 FPS
gameplay replay (9,200 VI), and Original FPS compatibility (4,560 VI).
**JFG - Shadow Flicker Preview** is open for owner review, with a copied save
and the FPS box hidden. Runtime SHA-256: `91c44aecb9eb86c8bba2f6ea820f84c153db6cca9bc79a1ac4d86b4bbe0145b8`.
The reflection remedy is retained; shadow visual acceptance is pending.

## Owner confirmation and remaining cadence, October 25

The owner confirms blockiness and jitter are gone in the exact-emitted-camera
preview, but reports that shadow motion now feels slower than 30 FPS. Preserve
the accepted depth/camera correction. The full #46 cadence problem is not
resolved. Continued investigation is authorized under the remaining guarded
allowance; separate mask refresh cadence from projector/UV interpolation holds.

## Clipped-corner texture-motion candidate

The owner says both silhouette change and movement across the floor feel slow.
The closed capture shows native CPU mask work on every two VI retraces (30 FPS)
through the sampled gameplay interval; it does not yet establish how often the
mask pixels themselves change. Of 20,346 shadow vertex samples, 16,422 retained
geometric history. New clip topology correctly used camera-only motion, but its
texture coordinates held at the current endpoint, visibly limiting motion.

The next candidate records the native unquantized X/Z points used for UV
projection. For a camera-only corner on the same live receiver/projector, it
evaluates the previous affine UV projection at that current floor point. It
keeps geometry on its current floor and never borrows another clipped vertex.
A fit must agree with all native UV samples within two 1/32-texel steps; gaps,
receiver/actor retirement, conflicting UVs, degenerate fits, projector jumps and
extrapolation that magnifies quantization are rejected. The original matched
corner path is preserved. New tests cover changed clip topology, large jumps,
cadence breaks, conflicts, lifecycle changes and poorly conditioned old clips.
This candidate is under automated review, not visually accepted. It does not
add new intermediate silhouette images; mask cadence remains separate work.

Automated validation of the bounded projector revision passes all six build
targets and four component suites, a 9,200-VI 120 FPS gameplay replay and a
4,560-VI Original FPS replay. The sampled 600 gameplay scene rows contain
12,654 shadow vertices, including 1,175 camera-only corners with nonzero
projector UV motion. This establishes that the new path is exercised, not
visual smoothness or a silhouette fix. Private records: `clip-bound-validation.json`
and `clip-uv-coverage.json` in the follow-up evidence directory.
Runtime SHA-256: `5c62abb9efc54fd9ee86d575c33725a8c5458766cabd0026ea826eb626c67209`.
Owner review of this motion revision remains pending.

## Shadow border and idle-pose report, October 25

The owner reports a fuzzy, unstable outer shadow border and shadow jumps during
Juno's idle animation; low mask resolution versus interpolation is not yet
distinguished. One additional guarded hour is approved, including extra logging.
The prepared clipped-corner motion candidate has not received visual approval.
Keep the accepted depth/camera and reflection remedies. Record mask pixel changes,
projection endpoints and presentation history before attributing the symptom.

The first diagnostic build was rejected by MSVC's deprecated `getenv` warning.
The opt-in mask capture now uses the Windows Unicode environment/path APIs;
this diagnostic-only integration failure changed no runtime under review.

The owner also ran the prepared motion shortcut independently. Its completed
session `20261025-230711-5880eda6b317485f9bdfd54c3e66392c` is preserved under
the previous work directory's `motion-preview-captures`; the border/idle report
therefore supersedes the earlier pending-review status for that candidate.
It is not approved as a full shadow fix.

The first opt-in pixel build succeeds and its 11,000-VI replay completes.
Before the native softening/filter pass, the sampled masks contain only 0 and
142; afterward the stored values span 0 through 8. Mask contents usually
change every two VI retraces. This establishes coarse silhouette sampling,
not proof that all reported jumps are native or that projection is correct.

The owner capture saved input, timings and final RAM, but the launcher correctly
removed inherited diagnostic environment flags, so its new mask-pixel stream
was absent. A private replay of the full recorded input applies those flags
directly with copied initial profile data. This is a harness setup failure;
no extra owner capture is required for that replay.

## Fractional receiver candidate

The first diagnostic replay has 379 stationary-player updates with one actor
position but 21 distinct packed shadow footprints. The producer calculates
fractional clipped coordinates and then truncates them to signed integers.
Interpolating these rounded endpoints retains holds and one-unit steps.
The new candidate retains the original fractional point plus the native vertical
lift, only when it reproduces every emitted signed coordinate exactly and the
lift safely separates the decal from its receiver. Unknown, out-of-range,
nonfinite, stale or insufficiently lifted points retain the native endpoint.
The emitted camera product and the original CPU mask/filter remain intact.
This is a motion candidate, not an interpolated silhouette or resolution fix.
Component tests and gameplay/Original compatibility review are pending.

The full owner-input replay completes successfully in 408.7 seconds. Its
stationary Juno window spans VI 20,335 to 22,787: 1,227 mask updates include
1,123 changed images. The mask centroid can move over one texel between
adjacent updates while the actor's root position is unchanged. The native
mask draw requests antialiasing off (`otherMode.L = 0x0F0A4000`), consistent
with the binary pre-filter image. This is direct evidence of native coarse
mask sampling and a separate silhouette-cadence limit; it is not a pixel
comparison against original hardware. See `owner-idle-mask-analysis.json`.

Source review caught a candidate integration error before its first replay:
semantic history used fractional points while the uploaded current endpoint
still used integers. The corrected candidate uploads the same validated
current point used by history, preserving the common emitted camera matrix.
The superseded build was never installed into the owner preview.

The corrected fractional-coordinate candidate passes all six build targets and
four component suites. Muted 120 FPS (11,000 VI) and Original FPS (4,560 VI)
replays complete successfully. Original FPS bypasses the presentation change.
The 120 FPS idle interval records 6624 fractional samples
out of 6624 shadow vertices, establishing actual runtime coverage.
These diagnostic replays do not establish performance or owner acceptance.
Runtime SHA-256: `6172e151469414651415444363372904d575fa7f0e583b8b051a28cd5f61dd7d`.

## Optional Enhanced shadows requested, October 25

The owner reports the fractional-coordinate preview still has blocky silhouettes
and visible jumps as Juno sways his arms. It is not accepted as a complete fix.
The owner suspects the remaining appearance is inherent to the original shadow
calculation and requests an optional Video setting, Original / Enhanced, with
a replacement shadow-generation path. Pixel evidence supports coarse native
mask sampling; original-hardware parity is still not established by those logs.
Original remains the default. A three-hour guarded implementation/research
window is approved, using the same investigation and counters. Modern shadow
techniques will be researched before selecting the renderer integration.
No enhanced runtime exists or is validated at this point.

### Enhanced design and references (implementation in progress)

Research reviewed Microsoft's [shadow depth-map artifact guide](https://learn.microsoft.com/en-us/windows/win32/dxtecharts/common-techniques-to-improve-shadow-depth-maps),
NVIDIA's [shadow-map antialiasing chapter](https://developer.nvidia.com/gpugems/gpugems/part-ii-lighting-and-shadows/chapter-11-shadow-map-antialiasing),
and Epic's [virtual shadow map documentation](https://dev.epicgames.com/documentation/en-us/unreal-engine/virtual-shadow-maps-in-unreal-engine?application_version=5.6).
The transferable choices are geometry-based maps, stable light-space sampling,
comparison filtering and explicit performance bounds. Virtual page allocation
and whole-world light reconstruction are not needed for this first actor-shadow
implementation and are not claimed.

The selected prototype generates a 512-square, light-projected height/depth map per
actor/projector on the GPU at each displayed interpolation phase. It uses the
same validated world-space pose endpoints as the visible actor. Native clipped
floor receiver geometry and native opacity retain level boundaries and authored
visibility. A comparison filter will soften map edges, with a bounded increase
in softness for greater caster-to-floor separation. No mask readback or
crossfade of old silhouette images is introduced by this path.

Original remains the persisted default. The owner subsequently requires Enhanced never to fall back. Unowned/mixed
geometry or unavailable caster data is an implementation/validation blocker;
Original may only be selected explicitly. Reflections and unrelated effects
cannot become shadow casters through address guessing. Compatibility at Original
FPS, split-screen, scene changes and visual/performance acceptance remain open.

### First Enhanced integration checks

The GPU and settings implementation now compiles. The first muted 11,000-VI
replay completed but did **not** exercise the new shadow draw: collection read
RT64's GameCall::meshDesc.faceIndicesStart before State::fullSync finalized
those ranges. Its zero Enhanced draw counts invalidate that replay as shadow
verification. The corrected collector derives indexed ranges in the same
framebuffer/projection/call order, skips raw projections, and has a regression
fixture with deliberately uninitialized/stale meshDesc values.

The receiver's native depth lift is now recorded separately from physical
floor height. The visible decal retains the exact native depth/camera path;
height comparisons remove each endpoint's lift so low body geometry can still
cast onto the actual floor. Component checks cover pose endpoints, reflection
exclusion, camera/receiver ownership, stable map extent, physical floor height,
and blocking incomplete geometry. Missing geometry is not an Original-mode
fallback. GPU coverage, visual output, performance, and owner review remain
pending; this feature is not a released or completed shadow fix.

Build portability findings: RT64's C++17 target cannot use map::contains;
the shared shadow geometry helper also needed a name other than Windows'
near macro. Both were corrected without changing the geometric test.

### Enhanced coverage corrections and current qualification

The first actual GPU replay exercised four displayed phases (0.25, 0.5, 0.75,
1.0) per game scene. It then blocked at a camera transition: the receiver had
exact native producer ownership but no matching semantic camera history. Those
are separate facts. Enhanced now takes actor, projector, floor position and
depth lift from the producer packet; actual workload view indices identify the
view. Optional preceding-frame history is used only for motion. The corrected
11,000-VI gameplay replay completed.

A subsequent complete owner-route replay reached VI 23,814 and exited
abnormally. Its asynchronous trace ended before the failing operation; there
was no durable final cause. This is an open qualification failure, not a passed
route. The next candidate drains diagnostic evidence on an Enhanced contract
failure so an exception cannot erase the relevant receiver/caster row.

The replacement also consumes the native light yaw/elevation, distinct light
projector identities, and authored receiver fading. Light and opacity endpoints
are carried through presentation history. Native packet ownership is retained
even when clipped-corner matching is unavailable; Original interpolation still
requires its existing corner proof. The collector no longer imposes arbitrary
actor-count or receiver-index caps that could silently leave old draws behind.
A matched receiver cannot bypass replacement through the vertex-depth-test
eligibility condition. Unsupported geometry remains a qualification blocker,
not an automatic change of shadow quality.

The launcher Rendering card and its actual UI tests pass for Original default,
Enhanced selection, Apply/persistence and Cancel. Component fixtures cover
projection direction, physical floor height, opacity endpoints, camera cuts,
reflection exclusion and retained producer ownership without corner history.
The first authored-light integration build caught use of a nonexistent RT64
color-float field; receiver alpha now reads the real normalized color-byte
stream. Rebuilding and broader runtime/visual qualification remain in progress.
There is no owner acceptance or release claim for Enhanced yet.

### Complete-route blocker isolated; replacement coverage measured

The complete Original-quality replay on the same binary completed 24,240 VI.
Enhanced completed the shorter 11,000-VI route at both 120 FPS and Original
FPS, but the longer Enhanced replay reproducibly stopped. A private SIGABRT
capture with matching executable/PDB resolved that stop to the explicit
EnhancedShadowRenderer::prepare incomplete-geometry check. This is not
evidence of a GPU/device failure.

The first attempt to preserve the exact reason still linked an older renderer
object. Force-rebuilding the generated RT64 integration units made the failure
durable: at VI 23,333 the visible floor shadow belonged to actor 0x801BD150,
but the collector had no eligible caster for its view. The same scene still
contained 1,506 reflected actor samples. Whether normal geometry is absent or
incorrectly partitioned by view is under investigation. Reflected screen-space
geometry must not be used as if it were the actual unmirrored caster.

Actual submission tracing on the shorter route records 1,092,512 expected
receiver draws and 1,092,512 Enhanced replacements across 19,885 output phases,
with zero mismatched output phases and zero scissor-only discards. This checks
the submission path, not merely preparation of unused maps. A two-light fixture
also verifies separate maps and complete caster geometry for each projector.

These checks do not qualify the longer route, split-screen, performance or the
visual appearance. Enhanced remains unreleased and is not handed over while
the known complete-route failure remains. No Original-mask fallback was added.

### Camera-independent caster ownership candidate

The expanded inventory resolves the failure: the task contains only the
reflected model's geometry, plus the ordinary floor shadow. All 1,506 model
samples have reflection lifetimes. The missing caster is not caused by an
incorrect receiver view index.

Enhanced now captures a separate canonical model sample from the original
palette matrix before applying a reflection adjustment. Its actor lifetime,
model instance, joint and logical vertex own world-pose history; the camera
view and reflection presentation lifetime do not. This is the same model
geometry transformed into its real world pose, not a mirrored silhouette or a
native-mask substitution. Duplicate triangles from multiple visible passes
are deduplicated by their logical vertices; conflicting canonical world
positions block qualification. Native receiver/view/projector ownership is
still checked separately.

The normal actor/reflection interpolation histories remain unchanged. New
component cases verify the unmirrored palette transform, camera-independent
world-pose history, a receiver with only a reflected visible draw, and rejection
of invalid canonical geometry. The revised renderer and component suite build
and pass; complete-route replay and owner visual verification are pending.

The canonical-caster candidate completes the full 24,240-VI owner route
(exit 0, 409.53 seconds). Its trace accounts for 2,104,203 expected receiver
draws and exactly 2,104,203 replacements across 44,237 output phases, with
zero missing-caster rows and zero submission mismatches. The formerly failing
reflection-only transition completes. A subsequent build adds explicit task
reset of caster-matrix validity and motion-coverage diagnostics; its replay
and Original-FPS compatibility check are running. These are correctness
replays with diagnostics, not representative performance measurements.

Qualification scope correction: the full owner recording contains a long
title-screen lead-in. Room logs confirm the complete runs reach the flight,
Goldwood introduction and first gameplay room (US rooms 0x16D, 0x5D and 0x5C).
The first final-build 11,000-VI Original-FPS check ends in title room 0x181;
it verifies startup/title compatibility only, not gameplay. Its screenshot
caught this limit. Both frame-rate modes are being checked again using the
previously validated shorter input lead-in. Renderer submission totals include
title/character-screen shadows and must not be described as millions of
gameplay-only draws.

The final-build full recording completes with 2,078,562 replacements for
2,078,562 expected receivers, zero missing-caster rows and zero mismatched
output phases. Canonical history records 42,559,236 moving samples and
2,681,262 samples from the original palettes of reflected draws. This proves
the new path receives moving poses; perceived smoothness and outline quality
still require owner review.

### Qualified preview handed to owner; visual acceptance pending

The corrected shorter recording reaches Goldwood in both final-build modes.
Original FPS completes 11,000 VI (exit 0, 187.35 seconds), with 97,025 expected
and submitted replacement draws. Custom 120 FPS completes 11,000 VI (exit 0,
185.87 seconds), with 733,693 expected and submitted draws. Both have zero
submission mismatches and confirmed room coverage 0x181, 0, 0x16D, 0x5D and
0x5C. These checks use normal renderer code paths without the private native
optimization/host-timing overrides. Gameplay frames were inspected with the
new ground shadow and reflected character visible.

Runtime SHA-256: 4415f6f4b9599b6166903ce2c2fd3e28ae5e2dc902e3b9b03c384cc7ae4d9c96.
The isolated Enhanced Shadows Preview uses a copied save/profile, 120 FPS,
muted audio, hidden FPS overlay and standard diagnostic recording. Its package
manifest was rehashed and verified; support identity names the matching runtime
and private symbols. The owner is asked to inspect idle arm sway, walking and
camera turns. No owner acceptance, broad campaign coverage, split-screen
qualification, other-GPU performance, commit or release is claimed.

### October 25 owner refinement review: crash and receiver overlap

The owner reported a Goldwood cinematic crash with Enhanced enabled, a hard shadow edge, and a shadow appearing on both a raised object and the lower floor. These are open candidate regressions; earlier route qualification did not cover every actor type. Capture D:/JFG-private/enhanced-shadows-20261025/owner-captures/20261026-030734-dee1b5bdb16043359c5e9d7a3394029b ends at scene VI 80237 in room 199 with 14 missing-caster receiver draws belonging to five HealthPowerup actors. No native fallback occurred: the incomplete-caster check stopped the renderer. The exact caster-path omission and receiver overlap cause remain under investigation. The owner approved one hour, preserving the production guard and all existing counters. Actor LOD and Shadows are moving to Video > Enhancements, including dirty state and search categorization. A replacement requires crash qualification before live review.

Candidate changes under qualification: rigid model casters now use captured native model/view/projection operands, validated against the emitted matrix and the exact live model vertex allocation. The native mask is not sampled. A second per-projector GPU height pass identifies the highest receiving surface below the caster, so lower overlapping surfaces do not receive the same silhouette. Receiver plane correction avoids self-rejection on slopes. Softness is expressed in world units and increases with blocker separation, using deterministic comparison filtering. Neither the crash remedy nor receiver overlap is marked resolved until actual-scene and owner verification. UI checks passed after moving LOD/Shadows and their dirty indicators to Enhancements.

### October 26 sprite-caster crash diagnosis

The direct room-199 fixture reproduces the owner crash with both the handed-over
runtime (4415f6f4...) and the first refinement candidate (3952b575...).
The attempted rigid-model support did not fix it. The failing HealthPowerup
objects are sprites: native object dispatch reads header byte +0x1E as 1 and
calls the sprite renderer (US 0x8000DEA0..0x8000DED8). Their +0x6C asset table
does not contain model instances. Treating those bytes as a skeletal or rigid
model would be incorrect.

The exit RDRAM is canonical big-endian. It identifies all five objects and their
authored static-shadow controls: bit 4 at control+0xC and scale 1.6. Native shadowProject multiplies the scale by 10 to form the horizontal
projection extent (US 0x8001E288..0x8001E2AC). These actors intentionally use
projected sprite shadows in the original game. The original 64x64 I4 image was
inspected as evidence; Enhanced does not sample or copy it.

The new candidate gives this explicitly identified sprite class an analytic
sphere caster, centered on the native sprite origin, sized from its authored
horizontal projection footprint and attached to the live actor lifetime. The GPU solves the light ray intersection to obtain caster
height and uses the same receiver-occlusion and soft-edge path as mesh casters.
Separate presentation history interpolates its position and dimensions. This is
a defined sprite rendering path, not a substitution selected when mesh capture
fails. Unknown or malformed caster geometry still fails qualification; it never
switches quality or reuses the Original mask.

Analytic shadow proxies are an established rendering technique; for comparison,
[Unreal's capsule shadow documentation](https://dev.epicgames.com/documentation/en-us/unreal-engine/capsule-shadows-overview-in-unreal-engine)
describes sphere/capsule representations for soft shadows. This implementation
uses a spherical approximation for sprite casters and does not import that engine.
It does not claim a physical 3D mesh exists inside a billboard.

Evidence remains private under
D:/JFG-private/enhanced-shadow-refinement-20261025/before-room199 and after-room199.
The current guarded work is D:/JFG-private/enhanced-shadow-sprites-20261026,
authorized for three additional hours with the same investigation and counters.
Component checks, direct-scene replay and owner review are pending for this
sprite candidate. The Goldwood crash is not yet marked resolved.

Compatibility lesson: native receiver ownership does not imply a skeletal mesh.
Handle the native drawable class explicitly; do not reinterpret sprite assets as
models or silently replace unidentified actors with a generic blob.

The first sprite candidate (v16) still failed the exact scene. Runtime evidence
corrected the initial height-field interpretation: header+0x6C/+0x6E are -100/+10
receiver-search limits for these objects, not caster dimensions. The earlier
24/0 interpretation was wrong. The revised explicit sprite path uses the authored
horizontal footprint as a spherical proxy radius at the native sprite origin;
it does not infer volume from receiver search bounds. The producer fixture now
uses the actual -100/+10 case and verifies those unrelated fields cannot make the
proxy invalid. This remains an approximation appropriate to a billboard with no
3D mesh, selected by drawable class, never as fallback for a missing model.

Sprite pose history is bound only to receiver packets used by the current
workload. Retained alternating buffers cannot overwrite the current position.

### Corrected sprite candidate: scene qualification and owner handoff

Runtime 30147ae9342fd215d161891a2390195f258bd0628ac0c533ebb305d1159d6721 (private v17) completes the direct Forest Intro
room-199 fixture at both frame rates. Custom 120 FPS: exit 0 in
111.23 seconds, 188,201 expected and
submitted replacement draws across 4,359 output phases.
Original FPS: exit 0 in 110.32 seconds,
94,015 expected and submitted draws across
2,162 phases. Both have zero missing-caster rows and
zero per-phase submission mismatches. These counts include title/flight and
other rooms on the test route; they are not all gameplay-only draws.

Both runs enter room 199, continue for 25 seconds and close normally. Captured
frames confirm the Forest Intro is rendered. This tests the formerly failing
scene through a direct review request, not a complete natural campaign route.
The final component suites (renderer geometry, presentation identity and video
settings) pass; actual launcher UI tests passed the Enhancements move earlier.
The first added producer test needed its halfword writer corrected before it
compiled; that fixture error is preserved in the private build2 log.

The owner preview now contains this exact runtime and the tested launcher.
All 14 package-manifest files were rehashed and
verified. The copied save is byte-identical to the pre-update backup; controls
are preserved. It is set to Enhanced, 120 FPS, muted audio, hidden FPS overlay
and standard diagnostics. The desktop shortcut targets the new capture root.

The reproducible crash passes the automated scene test. Softer edges, raised
receiver occlusion and normal camera/idle motion remain pending owner visual
verification. Full-campaign coverage, split-screen and other-GPU performance
are still unqualified. No automatic Original fallback, commit or release.

### October 26 bridge review: visual refinement rejected

The owner stopped the v17 capture with Juno standing on the edge of a raised
bridge/object. Screenshot codex-clipboard-ryZhp2.png shows malformed/abrupt shadow
coverage beside the object; the owner also reports excessive softness together
with intermittent blocky edges. These are open visual failures, not accepted
results. Automated Forest Intro crash qualification remains separate.

Evidence: D:/JFG-private/enhanced-shadow-sprites-20261026/owner-captures/
20261026-042904-ca8a72a65f1340b4a8d965e14c6cc354, including the final RAM snapshot.
The recording ran for many hours; its interpolation trace is about 27 GB.
Investigation will use bounded sections and the exit state rather than assuming
a short recording. The owner approved three hours on October 26, preserving the
production guard, the same investigation and all counters. Receiver depth
selection and the sparse contact-hardening filter are hypotheses to test.
The tested v17 preview remains intact until a replacement qualifies.

### October 26/27 bridge and filter candidate

The final v17 input/collision snapshot places Juno at approximately
(9.04, 4.76, 1137.47), level 92, on the raised object. Its final presentation
trace contains all four 120 FPS interpolation phases. This evidence does not
support describing the bridge defect as simply a return to native shadow cadence.

The input recording spent about 20.7 hours at the title screen before the active
route. A private replay removed that idle interval while preserving active input
samples and order. Its first attempt was rejected because normalized sample
timestamps overlapped; correcting the ordering allowed a clean run. However, the
shortened replay ended near the first portal, not at the captured bridge position.
It is a useful first-room compatibility check, **not an exact reproduction** of
the bridge defect. No owner bridge fix is claimed from that replay.

Code review identified three concrete limitations in the previous candidate:

- Receiver visibility was selected from one nearest texel in a second height
  texture. That quantizes the boundary between the raised object and the ground.
- PCF samples all compared against the center point's floor height. A sloped
  receiver needs a different comparison height at each displaced sample.
- A sparse, regularly spaced filter and hard blocker membership could produce
  isolated coverage patches and abrupt softness changes near an animated edge.

The new candidate removes the receiver height texture/pass. Each projector
retains its exact physical receiver triangles and both presentation endpoints.
The shader intersects those triangles along the authored light direction, finding
the next surface above the current receiving point. Contributions blocked by that
surface do not darken the lower surface again. Receiver sets stay separate for
different authored lights, even when they share a caster actor.

The filter corrects receiver-plane height per sample, bilinearly weights blocker
membership, and distributes 32 PCF taps over a disk rather than stretching a 5x5
grid. The contact radius and angular growth are reduced to retain more silhouette
detail. These are presentation changes; native physics, actor geometry and game
update frequency are unchanged. Enhanced still never selects Original as fallback.

The per-sample plane correction follows the technique described in
[Microsoft's Cascaded Shadow Maps documentation](https://learn.microsoft.com/en-us/windows/desktop/DxTechArts/cascaded-shadow-maps).
The contact-hardening design is informed by
[NVIDIA's PCSS description](https://developer.download.nvidia.com/shaderlibrary/docs/shadow_PCSS.pdf);
the implementation uses the project's actor height maps and receiver geometry,
not an imported engine or full-scene shadow system.

Validation so far:

- Renderer/texture ownership, semantic presentation and video setting component
  suites pass. The additional multi-light test checks that different physical
  receiving surfaces cannot leak into another projector's visibility set.
- The reusable [shader qualification](../../../scripts/verification/test_enhanced_shadow_shader.py)
  compiles the production HLSL and executes 48 analytic cases using D3D12 WARP.
  Cases cover moving platform boundaries at three interpolation phases, stacked
  and sloped receivers, oblique light, bilinear edge coverage and blocker weights.
  All pass. WARP validates shader calculations; it is not hardware performance
  qualification. The initial private harness invocation failed because of command
  quoting; the corrected reusable runner passes.
- The unchanged render candidate v19 completes the direct Forest Intro fixture
  at both Original and 120 FPS, without the prior sprite-caster crash.
  Custom: 375,829 replacement draws in 8,649 output phases.
  Original: 94,067 draws in 2,174 phases.
  Both have zero missing geometry and zero expected/submitted draw mismatches.
  These totals include the preceding title/flight route and are not a benchmark.
  The 120 FPS trace includes 0.25, 0.5, 0.75 and 1.0 pose phases.
- Both DXIL and SPIR-V compile. Runtime review here uses D3D12; Vulkan execution,
  split-screen, broader campaign coverage and other-GPU performance remain open.

A bounded diagnostic snapshot now retains one immutable Enhanced shadow scene
and writes its exact caster/receiver geometry at shutdown. Ordinary Play does
not enable it. The explicit diagnostic drain is required because the native
runtime uses _Exit; relying on a C++ destructor alone would lose this evidence.
The capture performs no periodic filesystem writes during owner presentation.

The source and evidence are retained privately in
D:/JFG-private/enhanced-shadow-bridge-20261026. The final capture build is being
qualified before owner handoff. Bridge coverage, softness and idle motion remain
**pending owner visual verification**. No commit, publication or release.

Transferable lesson: filtering a shadow map does not fix receiving-surface
ownership. Treat geometric visibility and filter continuity separately; preserve
fractional surfaces and correct plane height at each filtering sample. A shortened
input replay must not be described as exact when it reaches a different position.

#### Final capture build and owner handoff

Private v20, runtime SHA-256 7059397cfc98bfaa329a46a0bbf7c7ee30e058f8b91c093fbb004c840124e4b5, passes the
same Forest Intro fixture at 120 FPS after the shutdown-capture integration:
377,523 expected/submitted draws across 8,731
output phases, zero missing geometry or submission mismatches. It closes
normally and writes the bounded 49,236-byte geometry snapshot
at tick 6570, proving the explicit drain works with _Exit.
The renderer geometry and interpolation component suites pass again after that
integration. The previous v19 rendering checks at Original FPS remain applicable;
v20 changes diagnostic snapshot lifetime, not the rendering equations.

The existing Enhanced Shadows desktop shortcut now opens that qualified runtime.
All 14 package entries were rehashed and
verified. The copied save and controller configuration remain byte-identical to
their pre-update backup. Preview settings are Enhanced, 120 FPS, muted, with the
FPS overlay hidden. The prior package was stopped before replacement.

Owner review was requested for the raised bridge edge and Juno's idle silhouette.
Visual acceptance remains pending; this is a candidate, not a released resolution.
The reused documentation update encountered a Windows default-encoding error
while reading CHANGELOG.md; the remaining edit was completed with explicit UTF-8.
No runtime or owner files were affected by that documentation error.

#### Owner review: positive appearance, broader crash pass underway

The owner reports that v20 "looks much better" and "looks really good", and is
continuing through the game to look for crashes. Record this as positive initial
visual review, not completed campaign/stability qualification. The running
preview must remain unchanged while that review continues.

Scope clarification: Enhanced replaces the native projected actor-shadow draws.
This includes character/enemy/tribal mesh casters and explicitly identified
sprite-object casters such as pickups. It is not a full-scene environmental
lighting replacement. Level texture shading, vertex lighting and other static
authored darkening are not regenerated by this system. A character's shadow
received by the bridge uses Enhanced; the bridge's own apparent ground shadow
is not automatically regenerated. The owner's suggestion that the bridge shadow
is baked into the environment is plausible but not verified for that asset.
No new environmental-shadow implementation was requested or attempted.

#### New owner report: tribal chief shadow clips to a square

After positive Juno review, the owner reports a new defect on the tribal chief:
parts of the shadow pop into view and clip out at a rectangular boundary.
Screenshot codex-clipboard-EQ4iOq.png shows the hard cutoff. The owner closed the
v20 capture and asks to prioritize the chief at its end; the bridge material
classification is deferred. This is an open Enhanced-shadow geometry/coverage
regression, not a rejection of Juno's improved appearance. The captured native
receiver footprint is the first hypothesis to verify. Evidence remains in the
20261027-021111 owner capture under enhanced-shadow-bridge-20261026.

#### Chief clipping: confirmed receiver footprint mismatch (candidate v21)

The v20 exit snapshot identifies KingBear and confirms the hard cutoff in
receiver geometry, not the soft filter or map texture. Its projected mesh spans
Z=28.35..84.78, whereas the native emitted receiving patch spans
Z=48.22..82.22. Nearly 20 world units are missing at one end. Juno's mesh fits
inside his larger original receiving patch. This explains why the player looked
correct while the chief showed a rectangular boundary.

The candidate derives the skeletal caster footprint from the actual model's
vertex groups and both fixed-point bone-palette banks, then projects them over
the native receiver height interval using the same light shear as Enhanced.
It includes the maximum filter radius and packed-coordinate allowance.
Before shadowProject performs its receiver broadphase and polygon clipping,
the pinned rectangle-bounds call receives the union of that required footprint
and the original polygon. Sufficient original polygons stay byte-identical.
Only render scratch coordinates change; actor collision, animation, native
Original mode and the sprite caster definition are unchanged. This is not a
chief-specific multiplier or an attempt to stretch a cut-off shadow texture.

Private captured-RAM execution of the production helper passes: the chief's new
rectangle covers X=132..175 and Z=25..88; Juno's existing rectangle is unchanged.
The initial model inspection incorrectly treated flagged metadata/helper batches
as skeletal groups, yielding invalid bone/offset values. They carry 0xC00 flags
and degenerate helper faces and are excluded from mesh bounds. The initial
compile also found an unavailable matrix alias; the helper now uses an explicit
16-float array. Neither exploratory error was installed in the owner preview.

Focused tests cover two animation poses, oblique light/receiver heights,
metadata exclusion, invalid joint indices, caller pinning, Original-mode
byte identity and restoration of the guest floating-point environment.
Build, scene compatibility and owner visual verification are still pending.
The helper is qualified for valid skeletal model palettes; it does not invent a
pose for unrelated rigid/sprite formats or silently switch to Original shadows.

Transferable lesson: modernizing shadow generation must also modernize the
geometry receiving it. A correctly filtered, complete shadow map can still be
cut off by an inherited receiver-query rectangle. Finite texture/query bounds
are necessary, but their extent must follow the caster and light rather than an
old texture scale. Bridge environmental-material classification remains deferred.

#### Chief native-room qualification and final triangle reference refinement

The v21 production build and semantic suite pass. Forest Intro runs pass at
120 FPS (376,565 draws / 8,655 output phases) and Original FPS
(94,057 / 2,162), with no missing geometry or draw-count mismatch.

A native-exit fixture now reaches the actual chief hut (room48). Its shutdown
geometry confirms the caster occupies X=162.44..197.77, Z=19.87..67.66 while
the receiving surface covers X=159..203, Z=15..75. The replacement survives the
native broadphase, clipping and GPU submission. This run completes normally
with 444,111 expected/submitted shadow draws over 9,892 output phases and no
missing geometry. This qualifies actual coverage; visual owner review is pending.

Two preliminary route fixtures did not preserve the desired endpoint. Directly
selecting the introduction returned to the borrowed source room rather than
carrying the normal entrance destination. The first native-exit run then walked
back out because its reused input tape contained later movement. The corrected
fixture retains the title input, becomes neutral, uses the normal village/hut
exits and requires a stable room48 endpoint. These are test-fixture limitations,
not game crash or transition regressions.

Final candidate v22 determines contributing vertices from nondegenerate native
triangle references instead of using batch flags as a proxy. Helper/attachment
entries have repeated vertex indices and are excluded before interpreting their
metadata as joint groups. This avoids assuming that individual material bits
mean invisible geometry; it also retains seven additional Juno model vertices
that the preliminary broad flag check omitted. Chief captured bounds and Juno's
unchanged receiving rectangle still pass the production helper probe.
A warnings-as-errors check caught a shadowed local name during this refinement;
it was renamed before the final build. Final build/room qualification is pending.

Scope remains projected skeletal actor receiver sizing. No claim is made that
the bridge's separate environmental darkening has been classified or replaced.

#### Final v22 qualification; owner acceptance pending

Runtime SHA-256 c36f64551ea9cdaa0dfeaa520ae2b24fa1c39a394f8716dbee8efd1827e5592b passes the build and semantic suite.
The stationary native-exit fixture reaches room48 and completes normally:
450,163 expected/submitted replacement draws in
9,986 output phases, with no missing geometry or mismatches.
The final captured chief receiver surrounds the full caster bounds on both axes.
Forest Intro passes at 120 FPS (377,467 draws /
8,663 phases) and Original FPS
(94,003 / 2,158); both have zero
missing geometry and draw-count mismatches. The shader/filter remains the
previously qualified v20 implementation. These checks establish geometry and
submission correctness, not owner visual acceptance or a full campaign pass.

The separately requested bridge inspection is now complete. Its dark ground
strip is pre-existing level vertex shading, sharing its texture with brighter
adjacent ground. The bridge actor has no projected-shadow control. See
[environment shadow scope](enhanced-shadow-environment-scope.md).
The chief correction is ready for a copied-save, muted 120 FPS preview.
No commit, push, issue posting or release was performed.

#### Owner regression: drone shadow remains clipped in v22

The owner reports a hard cutoff on a blue drone, screenshot
codex-clipboard-7sEGZe.png, and correctly challenges actor-by-actor patching.
The v22 capture is closed and preserved. Chief-room geometry qualification did
not establish complete caster-format/receiver-path coverage. Do not mark the
shared clipping defect resolved or infer chief visual acceptance from that test.
Investigate all captured caster formats and their rejected receiver-bound
queries; do not add a drone-name/behavior-specific size multiplier.
Evidence: 20261027-031349 owner capture, under enhanced-shadow-bridge-20261026.

#### v23 diagnostic capture crash under investigation

Owner reports crash in the short follow-up drone capture. Support log records native_exit=0xc0000409 around 51 seconds. Geometry/input traces survived; shutdown RDRAM did not. The launcher correctly strips inherited JFG variables, so the newly requested query-snapshot variable did not reach the game. The extra bounded snapshot path therefore was inactive. Do not attribute the crash to logging or to a specific shadow change without replay evidence. A private replay enables query snapshots and abort evidence directly with copied save data.

#### Shared drone sizing cause and detached-body crash (2026-10-27)

The original owner shutdown RAM contains valid packed matrices and the v22
helper expands both blue-drone bounds offline. That was insufficient evidence:
the live receiver query runs before deferred matrix conversion. A normal-Play
reconstruction reaches the owner's room27 combat and captures the query state.
Both blue-drone active palettes are float 4x3 matrices, with unspecified fourth
column padding, while their other banks are packed N64 matrices. The existing
helper rejected the float bank, leaving the original small receiver polygon.

The native camConvertMatrixList at 80042470 queues palette/bone-count entries
at 800FA658, counted by 800A2ED0; camTick at 800424A0 converts them later.
Candidate sizing consults that exact queue before decoding each bank. Queued
matrices use the twelve defined floats and implicit affine fourth column;
unqueued matrices use the packed representation. No behavior/name-specific
radius or arbitrary multiplier is introduced. Simulation memory changes remain
restricted to the temporary receiver polygon in Enhanced mode.

An intermediate private v24 attempt inferred the representation from homogeneous
matrix values. This was wrong: native float padding may contain stale values,
and newly allocated identity matrices are not prepared render poses. It still
rejected the drones and expanded a fresh Juno query toward the origin; the chief
route then crashed in native receiver traversal. That candidate was NOT installed
for owner review. The queue-based candidate replaces this inference entirely.
Tests cover mixed/pending formats, undefined NaN padding, finite coordinate
validation, and rejection of unqueued initialization identities.

The owner's v23 crash also reproduces in normal Play at approximately 52 seconds.
The Enhanced renderer reports a missing caster for SeveredLimb 801C4660,
behavior64, which has baked vertex allocations and no ModelInstance. Existing
rigid interpolation already identifies its exact DMA ranges. The candidate now
uses those same lifetime/control/allocation/range checks to supply the detached
mesh to the modern caster renderer. It does not substitute a blob or Original
shadow. Tests cover transformed body geometry, gaps, lifetime reuse and ambiguous
ownership. Build and replay qualification are pending; owner acceptance remains
pending. The crash should not be described as caused by recording.

Earlier probe-mode input replays remained in menus or followed the wrong route;
they do not qualify the owner failure. The normal-Play fixture reproduces the
room27 detached-body crash and preserves its RAM, host abort stack and rejected
actor. Evidence is retained under enhanced-shadow-bridge-20261026, including
owner-play-replay-v23, drone-shadow-clipping and the isolated candidate fixtures.

The queue-based v25 candidate passes chief-room and Original-FPS Forest Intro runs. Two combat runs also complete without missing caster/receiver draws; however, both shutdown geometry snapshots omit the transient detached limb. The assertion requiring that actor at shutdown therefore fails and is retained as a fixture limitation, not treated as proof of live detached geometry. A bounded per-caster trace is added to record actual detached mesh collection while it is visible, independently of the exit snapshot.

#### Final queue-based candidate qualified; owner visual review pending

The build, semantic tests and renderer tests pass. The normal-Play combat
reconstruction now completes with 301,221 expected/submitted
replacement draws over 4,245 output phases, zero missing geometry
and zero draw-count mismatches. The new per-caster evidence records the exact
previously failing detached actor 801C4660 as a 48-vertex mesh in four consecutive
scenes. Its approximately 0.13-second visible interval explains why the earlier
shutdown snapshots missed it. This establishes actual collection of the supported
detached geometry, not merely absence of a repeat crash.

The same functional candidate reaches the native chief hut (room48), completes
normally and submits 712,642 matching replacement draws over
9,950 phases. Chief caster X=116.78..183.61, Z=31.27..72.07 is
contained by receiver X=114..188, Z=28..75. Original-FPS Forest Intro also completes:
161,296 matching draws over 2,176 phases.
Both have zero missing geometry/mismatches. The final v26 differs from v25 only
by the explicit transient-caster trace and passes its own full combat replay.

Actual combat geometry also verifies the shared drone correction: one blue drone
caster X=1062.96..1135.61, Z=-1190.21..-1111.08 is covered by receiver
X=1059..1139, Z=-1194..-1108. Other captured blue-drone and TribalBoy models
also receive expanded coverage. Their sizes come from model/pose data and the
native conversion queue, not per-character values.

Final runtime SHA-256: c33abc0393a1c6927dd37e5833245e9e7cbb930aef66b8990a46bf92235d6416.
The copied-save owner preview uses Enhanced shadows at 120 FPS, muted, with
the FPS overlay hidden. Final drone/chief visual acceptance and broader campaign
qualification remain pending. No commit, push, issue post or release occurred.

Compatibility lessons: deferred-conversion queues are authoritative format
provenance; unused float padding and allocation-initialization identities are
not. A shutdown snapshot can show a different representation from the producer
that failed. Detached custom geometry must reuse its proven live allocation
ownership rather than assuming every actor has a ModelInstance. Explicit owner
capture now retains bounded query snapshots after launcher sanitization; normal
Play without an explicit RDRAM capture does not enable them.

### Owner acceptance, October 27, 2026

After reviewing preview v26, the owner confirmed "shadows look good now". The shared caster bounds and detached-body rendering candidate is visually approved, in addition to the recorded automated qualifications. This is an unreleased resolution; broad campaign/performance qualification is not implied. The newly reported vine/gem occlusion is tracked separately in [vine-gem-occlusion](vine-gem-occlusion.md).

## October 27 local batch audit

Status: owner-approved local Enhanced Shadows v26; unreleased.

Use stable high-resolution, pose-driven Enhanced shadows with actual caster/receiver geometry, shared actor bounds and detached-limb provenance. No silent Original fallback.

Verification: Owner: shadows look good now; Preserved v26 caster/receiver and native combat qualification; Vine candidate combat: 314889 Enhanced draws across 4305 phases, zero missing casters. No GitHub action was performed.

## Open PR #56 review, 2026-11-04 UTC

The owner requested a complete open-issue/PR status report. Static review of
[PR #56](https://github.com/TK22-26/JetForceGemini-Recomp/pull/56), head
`0302fc52061135baf2491beb4483ccc33aac5dfd`, compared all six changed files with
`develop` at `ed5f7c79e02040d8277dcf04434e0b08b7c97952`. No PR build, experiment,
gameplay run, merge, remote review or contributor message was performed.

This is a different GPU-mask approach from the accepted Enhanced v26 path.
The owner liked an earlier community implementation after the October 9 opacity
correction; that historical comparison does not accept this exact PR head.
GitHub reports mergeable against main but blocked, with no submitted review or
reported checks. The precise branch-rule reason for the block was not established.

Source-review concerns apply to the unmerged proposal, not a demonstrated
regression in current develop:

- `gpu_shadow_framebuffer()` selects every framebuffer narrower than 128 pixels
  without format or proven caster ownership. Its import/writeback exceptions
  need narrower ownership and reused-memory qualification.
- GPU mode still skips CPU mask processing when the custom pipeline is absent
  or blur is disabled. The 8/14 opacity conversion is in that custom shader;
  standard reinterpretation is therefore not equivalent to restoring CPU
  opacity. Too-dark/raw-mask output is a static failure-path concern, without
  a fresh driver-failure or blur-Off reproduction.
- Globally enabling GPU copies conflicts with the newer architecture's deliberate
  CPU-mask policy and narrowly qualified screen-effect exceptions. Current
  generated RT64 shader-library modifications also serve camera fading. Integration
  must preserve those modifications rather than replace their generated units.

Recommendation: do not merge unchanged. Prefer explaining the newer accepted
Enhanced implementation with contributor credit, or request a separate integrated
option with ownership, opacity/fallback, high-refresh, lifecycle and performance
coverage. The PR author reports Windows/RTX 2070 Super testing at 60 Hz, not
high-refresh/Unlimited or regional qualification. This review changes neither
v26 owner acceptance nor the existing release status; no PR disposition was sent.
