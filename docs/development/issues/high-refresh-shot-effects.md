# RENDER-SHOT-001: Bullet effects appear low FPS at high output rates

- Severity: moderate visual smoothness issue.
- Status: Vela ship beams, travelling bullets and grenade shockwaves owner-verified locally; unreleased. Grenade fire/opening-marker reports remain open. Muzzle-flash jitter was not isolated or confirmed fixed.
- Reported/updated: 2026-10-24 UTC.
- Affected: audio candidate `1d631c0`, 120 FPS with VSync and Reduced blur;
  native executable SHA-256 `726946fc5583617d4625ed0dfe4455045459fa096f89aebe42739afe3b102626`.

## Symptoms and reproduction

During the SS Anubis audio pass the owner reported that enemy bullet/shot
effects look low FPS, possibly also the player's shots. The owner clarified
that the report concerns shot effects, not necessarily enemy character models.
Exact weapon, projectile type, room and distinction between muzzle flash,
travel and impact remain unconfirmed. The owner additionally reports general
slight choppiness and asks whether 60 native scene updates could help.

## Evidence and hypotheses

Possible missing projectile/billboard ownership, intentionally discrete texture
animation, or uneven output timing need separate measurements. Existing
renderer code interpolates owned billboard transforms while retaining authored
texture cadence; that is not proof these particular effects are covered.
An output frame rate alone does not establish smoothness or guest update rate.
Do not raise native simulation speed as a presumed rendering fix.

## Attempts and results

2026-10-24: separate copied-profile capture prepared with existing gameplay,
actor, input, timing and interpolation streams. Private evidence root:
`flight-shot-capture-20261024`. Same executable and settings as the owner's
clean audio pass; no runtime changes. Native 60 Hz operation is not enabled
or qualified by this work.

## Actual resolution and verification limits

None yet. Capture enemy shots and player shots with the camera still, then
repeat with camera movement. Distinguish travel, flash and impact effects.
Compare scene updates, transform matching and output timing before changing
interpolation. Keep any gameplay-speed claim separate from visual cadence;
[GitHub #48](https://github.com/TK22-26/JetForceGemini-Recomp/issues/48) is a
separate unverified report of faster flying enemies. Existing high-refresh
tests do not establish coverage of every effect.

### Completed capture and expanded owner report

The owner completed the diagnostic capture on 2026-10-24. Exit-door sparkle
effects also look lower cadence when the camera moves; their expanded
particles otherwise appear smooth. This adds a camera-relative particle test,
not proof of projectile or particle identity failure. Private
`flight-shot-capture-20261024/capture-complete.json` seals the closed session.

## First matching evidence

The closed capture contains many identified billboard draws with no matched
previous transform in gameplay (including the Goldwood landing room). This is
a concrete interpolation lead, but aggregate counts do not identify whether
the failing objects are exit sparkles, shots or other sprites. The opt-in
matching observer adds actor/particle allocation, asset and rejection reason
so that texture animation, spawn/retirement and camera-relative motion can be
separated. No rendering-policy change or visual acceptance yet.

## Refined evidence

The initial high rejection counts in Goldwood were dominated by particles
behind the camera. Nine exact old/current matrix and quad samples were all
behind both view endpoints, so those rejections do not establish a visible
interpolation defect. The diagnostic is refined to collect visible failures
and correlate the custom muzzle-transform draw path with actual renderer
matches. `camPushMuzzleMtx` is separate from the normal actor billboard path;
its lack of a dedicated owner is a lead, not a confirmed cause. Current
renderer policy for shots/particles remains unchanged.

Dedicated shot-draw/matrix probes are now available in the same copied-save
preview. This is a diagnostic delivery, not a shot/particle rendering fix.
It records custom muzzle matrices and small-mesh matching, while sampling
visible billboard motion rejections. Owner is asked to capture travelling
shots versus muzzle flashes and exit sparkles, then close the game.

## Vela flight underside lights (2026-10-24)

Owner additionally reports that the underside lights in Vela ship-exit flight do not interpolate to higher FPS. Screenshot is retained privately as vela-skirt-focus-20261024/owner-vela-flight-lights.png. Same normal Flight Motion Fix Preview runtime94da3fef; capture20261024-191151 contains the route. Separate geometry/camera motion from authored beam brightness/UV/color updates before proposing a remedy. Cause unconfirmed; no fix claimed. The deterministic Vela skirt focus regression is currently first priority.

The same capture records room88 (ship exit) and368 (flight). In room88 the
identified LightBeam objects usually interpolate all54 emitted vertex samples,
with approximately20-22 held source intervals each from motion rejection.
The GirlAnimShip hull/effect group is otherwise matched through ordinary flight;
room368 also records one34-vertex engine birth. These are different draw paths:
the screenshot alone does not identify which produces the underside streaks.
Do not claim the entire beam or ship stays at30FPS; distinguish occasional
motion guards from un-interpolated color/texture changes with a matching draw.

Owner repeats the underside-light report for Vela first ship exit, screenshot20261024 PgAWKa. The short4:38-4:41PM session used the logging-off skirt preview and saved no new gameplay capture; its copied diagnostics-session pointer refers to3:42PM and is stale. Prepare an explicitly captured follow-up with overlay hidden and additional color/UV/match observations. Do not misattribute the stale path to this reproduction.


## Captured follow-up for Vela ship underside lights

The normal fade preview's short owner session had logging disabled; its copied
diagnostic-session pointer named an older capture. No new flight evidence was
claimed from that pointer. The smooth-fade preview now uses an explicit fresh
capture at 120 FPS with the on-screen FPS box hidden, and the owner is asked to
replay Vela's first ship exit without skipping.

A bounded observer records semantic beam/cone identity, vertex RGBA, UV,
UV velocity and endpoint matching only while interpolation tracing is active
and an animated ship is present. No simulation, camera, opacity or matching
behavior depends on this observer. The launcher continues to strip inherited
JFG environment flags; explicit diagnostic launch creates the trace.
The light effect remains unresolved pending that capture. This is not a fix
for muzzle flashes or exit-door particles either.


## Light capture evidence and scroll candidate

The completed smooth-fade capture identifies eight LightBeam actors in room88
(Vela ship exit). Their sampled RGBA values are constant. Their animated
T coordinates advance by 0.125 texel each native scene and wrap at32 texels,
while tcVel remains zero. Their geometry usually matches; roughly20-22 intervals
per beam are rejected separately. Ship cone texture motion also has zero UV
velocity but is a distinct effect and is not included in this first correction.

The supported US beamScroll at0x04C0096C updates only triangle-corner T values,
using a phase masked to0x3ff in s10.5 coordinates. The candidate supplies the
short wrapped UV delta to the existing raster interpolation path. Actor lifetime,
control/shape, camera, logical vertex and exact triangle corner own history;
a corner key preserves different UV seams on the same vertex. It consumes the
existing geometry/cadence decision and changes neither native scroll speed nor
simulation memory. Original FPS is unchanged. Build/replay/live verification
remain pending; no visual ship-light fix is claimed yet.


The geometry holds are concentrated near first appearance and while the beam
endpoints cross the camera, rather than throughout the whole shot. The captured
reject reason is motion (one or two endpoints), with no duplicate or invalid
vertex errors. The beam path already captures and verifies its rigid native
model/view/projection, but semantic continuity only submitted those operands
for bridges. The follow-up candidate also supplies them for beams and uses the
existing bounded world-motion test when projected motion is unreliable.
Real camera/model cuts, large deformation and actor replacement remain excluded.
The near-plane/camera-cut/deformation regression cases now exercise both types.
This remedy still requires controlled scene evidence and owner acceptance.

The first new UV test build stopped because a local test variable shadowed an
existing variable under warnings-as-errors. Renaming it resolves the build;
the two targeted suites pass. The input-only baseline and UV replays omit map
warps and reach room67, so their images cannot validate room88 lights. A separate
hidden, muted review-session fixture selects room88 through the existing
cutscene-review protocol using only copied saves; it does not alter ordinary
campaign loading or the review eligibility checks.


## Controlled beam comparison and visual-review candidate

The final controlled baseline/candidate pair enters room88 from room67 on the
same VI2325 through the existing private scene-review request. Both runs exit
cleanly and observe the same eight beams over2323 beam-source intervals. The
baseline holds167 intervals; the combined candidate holds8, exactly the first
appearance of each beam. There are no later beam motion rejections in this
sample. Sampled nonzero UV velocities increase from0 to9260. Rendered candidate
frames show the matching underside view and intact beam geometry.

The renderer and native executable build successfully. Both targeted CTest
suites pass, including wrapped scroll, UV seams, actor replacement, geometry
holds, cadence gaps and near-plane rigid motion versus real discontinuities.
The private receipt is camera-fade-review-20261024/controlled-beam-comparison.json;
the candidate runtime SHA256 is
b9beb4f289b6af228d193470cedbdf07da67083fe1afd2512b72336042ad5235.

Earlier controlled-fixture attempts failed because the progress-file watcher did
not tolerate Windows sharing violations; the watcher now retries those reads.
A later forced shutdown left buffered gameplay logs unflushed, so that run was
not used for comparison. The final pair closes through the private process's
normal window-close path and preserves the complete logs. No ordinary campaign
or save-loading behavior was changed to construct this comparison.

The copied-save Vela Ship Light Fix Preview uses120FPS, capture enabled and
the FPS overlay hidden. It retains the owner-approved smooth proximity fade.
Status: component checks and controlled rendering evidence pass; owner visual
verification of the lights is pending. This does not resolve the separate
shot/exit-sparkle report or establish that all animated ship-cone textures
interpolate.


## Owner verification and local resolution

On 2026-10-24 the owner reports the Vela Ship Light Fix Preview is fixed.
The closed capture is preserved as
camera-fade-review-20261024/ship-live-captures/20261024-212435-69639eae0bc6414f82b161247ccfe2f9;
ship-live-accepted.json seals its input, state and trace files and the preview
runtime b9beb4f289b6af228d193470cedbdf07da67083fe1afd2512b72336042ad5235.

The demonstrated cause was two missing presentation operations: native beam
texture scrolling had no interpolated UV velocity, and beams did not use their
verified rigid pose to handle continuous motion near the camera. The fix adds
wrapped T-scroll history and the bounded rigid-motion path for LightBeam.
Native animation speed, original scene updates and Original FPS remain unchanged.
Targeted tests, controlled same-scene comparison and owner visual review now
pass. The ship-light subissue is resolved in the local development candidate;
it is not yet merged or released.

This acceptance does not resolve bullet/muzzle effects, exit-door sparkles,
all ship-cone texture animation, character shadows (#46) or floor reflections
(#47). Those are separate draw paths and retain their own verification needs.

## Travelling-projectile follow-up

The owner clarified that the low-FPS symptom is bullets moving through the air,
not muzzle flashes, and approved two hours on2026-10-24. The initial instruction
extract used a module ID as a normalized file index; generated indices differ.
That failed lookup is corrected by matching the actual entry PC.

The native objDrawTracer path builds a fresh four-vertex view-space quad from
the projectile endpoints, then draws with a projection-only matrix. These
positions change outside ordinary rigid actor and billboard ownership. This is
a concrete candidate for missing vertex interpolation; it is not yet a measured
cause in the owner's visible shots.

A byte-bound draw observer now records the exact transient quad from the two
verified projectile callers in objPrintCustomObject, retaining its live actor,
control allocation, camera and view/projection operands. It adds bounded
diagnostic rows but does not yet change tracer presentation. Birth, retirement,
buffer reuse and camera changes must remain distinct in any eventual fix.


### Travelling-shot capture and expanded owner report (2026-10-24)

The owner clarified that the low-rate shots are bullets travelling through the air. A copied-profile 120 FPS capture reproduced them while moving the camera, plus grenade shockwave jitter, running drone/tribal sideways jumps during camera rotation, and possible muzzle-flash jitter. These are separate open symptoms; the travelling-shot candidate does not establish a fix for the other paths. The capture is sealed privately under shot-effects-fix-20261024/baseline-capture-seal.json. The owner approved another hour; existing guard lineage and counters remain preserved.

The initial tracer observer confirms thousands of changing native view-space projectile vertices with zero presentation velocity. The ordinary model/sprite ownership paths do not cover this custom four-corner draw. A candidate will bind native tracer corners to their actor lifetime and captured camera, preserving original simulation and draw endpoints. It is not yet live verified.


### Candidate replay findings

The tracer path is established in the new capture: 8,952 initial observed vertices included 7,772 changing native positions across nearby scenes and zero presentation X velocity. Two candidate input replays validate all captured tracer camera/projection bindings and produce moving vertex history. The first replay has 983/1,568 tracer scene matches; the remaining holds comprise 167 births and 418 projected-motion rejections. A second replay has 890/1,265 matches (109 births, 266 motion holds). The native routes/counts differ between runs, so these are coverage observations, not an exact paired performance comparison.

A follow-up candidate uses the verified tracer camera operands and a bounded world-space continuity check, as for the accepted near-plane beam path. This avoids rejecting valid fast screen motion merely because a bullet approaches or crosses the camera plane; real camera cuts and large world displacement remain guarded. Births still have no invented previous projectile.

Grenade shockwaves use behavior 40 / shockwaveDraw at 0x80029688. Their twenty local vertices alternate between control+0 and control+200, selected at control+0x1DA; expansion previously had no semantic identity. The candidate binds this exact live allocation to its captured rigid camera/model pose. A replay records 13,200 matched of 14,280 expanded vertices, with 13,044 moving samples. Texture/colour animation keeps its native cadence. Both component and decoder suites pass. None of these observations is owner visual acceptance yet.


### Normal visual-review candidate

Prepared and opened JFG - Projectile Motion Fix Preview at 120 FPS, with diagnostic recording and FPS overlay OFF, using a copied save. Runtime SHA-256: 79dc9b329817d674338e4befc8d13c844714bf92d7d03696b346f69c8eedfb94. The combined hidden replay and four focused test suites pass (semantic presentation, decoder textures, renderer interpolation integration, interpolation history). The temporary missing-key provenance probe has been removed from the normal build. Exact counts and replay/build receipts are retained privately in shot-effects-fix-20261024. Source save hash is unchanged. Travelling shots, grenade shockwaves and actor camera continuity remain candidates pending owner review; the suspected muzzle flash is not claimed fixed.


The final combined replay reaches VI 15,000 normally. All 1,435 tracer camera bindings validate: 1,286 scenes interpolate, 141 are new-history/birth holds and eight retain the world-motion guard. Thus 1,286/1,294 non-birth scenes interpolate in this replay. Shockwaves match 83,520/85,320 vertex samples; 76,233 move. The shared-camera fallback is used for 264 actor frames / 117,990 vertex samples. These are recorded renderer outcomes, not a guarantee that every effect or physical display frame is smooth.

Muzzle-flash review: the owner described this symptom as uncertain. The native draw at 0x8000C0B8 attaches short-lived textured geometry through a parent model/bone and its matrix stack; it is separate from objDrawTracer and shockwaveDraw. This candidate does not alter its authored flashing/texture cadence or claim a fix. The owner is asked to flag any remaining visible muzzle-specific defect during normal testing.


## Owner review, 2026-10-24

The owner reports gameplay looks good and can no longer reproduce the prior travelling-bullet, grenade-shockwave or sideways actor issues. These candidate changes are now visually verified locally, not released. Remaining distinct reports: grenade fire appears to retain native cadence, and the exit marker opening while the camera moves appears to jitter. Muzzle flashing was not separately identified as remaining. Actor detail visibly decreases with distance; the owner requested an Original/High Actor LOD option under Game > Settings. Do not conflate those open paths with the accepted fixes.


## Final development status, 2026-10-25

Ship lights, travelling bullets and grenade shockwaves are owner-verified locally.
The later [exit-marker investigation](exit-marker-fire-cadence.md) also ends in
owner acceptance after persistent sparkle-slot identity was restored. Grenade
fire improved when animated sprite topology stopped invalidating its transform
history, but full fire confirmation remains open. The earlier pending statuses
above record the progression of the investigation, not the final result.
No release containing this batch is claimed. Muzzle-flash animation, character
shadows and floor reflections are separate paths, not verified fixes here.
