# RENDER-014: Enemy-clear door indicator darkens with distance

- Status: original-game bug reproduced by owner in EmuHawk; further investigation deferred at owner request. Accepted scoped visibility workaround retained, unreleased.
- Previous status: reported; source investigation open, no delivered fix.
- Severity: visible door/progression-state readability defect.
- Reported: 2026-10-18; affected private v1.3 normal-effect preview.
- Owner evidence: Screenshot 2026-10-18 192145.png and
  Screenshot 2026-10-18 192232.png, retained privately.

## Symptoms and reproduction

The green enemy-clear symbol beside the doorway is bright from nearby and
almost black when viewed farther away in the preceding room. This is a door
indicator, not the weapon lock-on reticle. The owner subsequently isolated camera distance as the trigger and reproduced
the blackout in EmuHawk. This is native behavior, not an established
recomp-only regression.

## Investigation

Check the indicator's native draw/lighting/fade state and renderer handling.
Distinguish native distance fading, translucent render state, depth/LOD and
interpolation ownership before changing alpha or brightness. The owner later reproduced the same blackout in EmuHawk; see the final
native comparison below. Preserve the green/red gameplay
state and other doors. No agent visual/gameplay testing is authorized in the
current owner-led workflow.

## Resolution and limits

Owner reproduced the native blackout in EmuHawk and accepted the scoped opaque-indicator improvement. This intentionally changes native distance fading for completed unlocked markers; it is not a general renderer repair. The exact original translucent-list artifact remains unexplained.
Related: [Vela preview](vela-rescue-cutscene-stutter-resolution.md),
[glass](high-refresh-glass-shaking.md).

## Source finding and candidate

The US behavior-67 doorSwitchControl (80026A50) only changes marked texture
animation frames in the currently selected model, and skips that update when
the logical state has not changed. Selecting a different model with distance
can therefore expose an initial frame. This is a concrete LOD-state coverage
gap; owner screenshots have not yet been tied to captured per-model state.

Candidate publishes the existing native status (0/1) to marked indicator
textures in all validated live models after the native handler. It does not
change enemy count, door eligibility, brightness, geometry or texture assets.
Other behavior IDs and unmarked texture animations remain unchanged.
A memory fixture covers three LODs, state changes, repeated calls, unrelated
textures, unsupported states/behaviors and malformed model counts.
Live near/far verification is still required; no agent gameplay performed.

The synthetic three-model state/texture regression passes. Runtime build and owner near/far comparison remain pending; this is a candidate rather than a demonstrated visual resolution.

## Owner rejection of first candidate, 2026-10-18

Door indicator still blacks out in runtime 669acb5f0cf377a40bd4f57cf7fd907a32890ee9141c01e1f2b7727426c845b2. Component checks did not establish live resolution. Current owner screenshot for the dark indicator: private owner screenshot codex-clipboard-cAYxUe.png. No autonomous visual verification authorized. Source/evidence investigation continues under the owner-approved bounded continuation, preserving all counters.


### Follow-up candidate: retain the base marker while drawing
Offline retained room-42 assets show two-model indicators whose secondary
model has no animated texture array. The first LOD-state synchronization therefore
cannot affect that model; the owner's trace recorded no synchronization changes.
This eliminates the previous claim that successful state propagation was observed.

The new render-only scope prevents native objPrintModelObject from adding a
distance LOD to behavior-67 indicators. It retains the current base model,
texture animation and state, then restores the shared header immediately.
It does not change unlock/progression logic. Component tests require byte-identical
restoration and reject invalid models/indices. A focused door-indicator-draw event
records base model, global LOD request, threshold, logical state and opacity.

This is still a candidate: the retained assets had zero distance thresholds and
the owner's live room has not been inspected. If this does not help, the next
capture distinguishes distance-model selection from texture/depth/lighting causes.

Combined private Motion Clarity Review prepared on 2026-10-18. Runtime SHA-256: 8c81e21948e0af3a269b875dc3147d7f80c46d2a9f1f9e6b98bc955ed3ab80b8. Build and focused navigation, semantic-presentation and 371 PC-input checks pass. Latest owner save/settings copied to an isolated profile, originals unchanged. Muted 120 FPS/VSync with buffered FPS, controls, blur-copy and glass-match evidence. This is not live verification or a release; the owner performs gameplay/visual review.


### Owner rejects detailed-model candidate, 2026-10-18
The owner reports the marker is still black in Motion Clarity Review runtime
8c81e21948e0af3a269b875dc3147d7f80c46d2a9f1f9e6b98bc955ed3ab80b8.
The supplied screenshot again shows the dark center at distance. The candidate
does not establish a fix. Review focused door-indicator-draw records from this
closed capture before attributing the failure to LOD, texture state or depth.
Private evidence image: door-marker-motion-review.png.


The closed owner capture shows every observed door draw requested LOD 0 with a
zero distance threshold; no state-sync corrections occurred. The base model was
already being used. Both speculative mutations and their fixture-only tests have
been removed from the candidate source; failure evidence is retained here.
Opacity does vary during the route. Added material logging records the opaque/
translucent display-list addresses, selected texture frame, animation flags,
actor brightness and per-camera render mode. These distinguish fading/material
state from the now-excluded distance-model switch.


The owner-accepted glass run also retained 712 door-indicator material records.
Texture flags and render mode stayed constant in those observations; animation
state and brightness vary by actor/state. This is diagnostic evidence, not proof
of the dark-indicator cause. Preserve per-actor correlation before changing
materials: aggregate locked/unlocked indicators must not be mistaken for a
distance effect. The ineffective LOD/forced-state mutations remain removed.
Dark door indicator remains open.


### Corrected field interpretation
The captured actor+0x28 word is normalized animation progress, not brightness.
Native objAnimDframe at 8001138C updates/clamps/wraps this value and preserves the
previous phase at +0xAC. Earlier "brightness" labels in the numeric-material
summary were incorrect; they must not be treated as lighting evidence.
The accepted glass capture shows the target door's unlock animation reaching
1.0 and marked texture frame 0x100. Its color/depth correctness remains unproved.
The native ordinary-model path sets primitive RGB to white and alpha from
actor+0x39, selecting the translucent display list whenever alpha is below 255.
Next comparison should inspect the actual live indicator draw at near/far range.

### Owner distance isolation, 2026-10-18 evening

Owner reproduced black indicator in Original mode after restarting; screenshot shows OUTPUT 29.9 / SCENES 29.9 and ORIGINAL PRESENTATION. Rotating the camera closer makes the indicator green; moving it farther makes it black. This reproduces without high-FPS interpolation and prioritizes the native distance-dependent draw/material path. No replacement remedy is yet validated. Evidence: owner screenshot codex-clipboard-OQeCGe.png. Animation progress at actor +0x28 must not be interpreted as brightness.

### Opaque indicator candidate, 2026-10-18 evening

Original-mode owner trace controls-43668-400718031.tsv contains 5,444 target
draws (actor 801bbc80, model 802e2bb0), including long unlocked runs at alpha
247-254 and fully opaque 255. The native function selects model+0x78 for every
alpha below 255, versus +0x74 for 255. This matches the reported camera-distance
boundary, but is not yet proof of the precise GPU defect. The native visibility
function 80015ED8 applies camera-distance fading; unrelated player proximity
fade events belong to actor 801c11b0, not this indicator.

Candidate keeps only a fully unlocked, animation-complete behavior-67 marker
on its opaque draw path while the native draw emits commands. The opacity byte
is restored immediately afterward (also on exception unwinding). Hidden alpha0,
locked/animating markers, special render modes, culling and progression remain
native. This intentionally removes distance fade for this visible status
indicator, not for general actors. It is a scoped presentation candidate,
NOT a confirmed underlying renderer repair. Owner review and potential
distance-boundary popping remain outstanding.

Validation note: runtime compiled successfully; the first new fixture compilation rejected an implicit unsigned-to-byte cast under warnings-as-errors. Added the explicit byte cast in the fixture, rebuilt, and all semantic/door eligibility/restoration checks passed. No production guard changes.

Candidate compiled; exhaustive alpha eligibility/restoration and existing semantic/glass checks pass. Runtime b668ab7dafdd338ae10206d8dc1618e10482fdce114cdfb935420d92a6c340ca. Separate Door Indicator Review profile copies the owner latest save; original preserved. Visual outcome pending owner review. The same preview adds numeric boss-pop diagnostics, without claiming a boss fix.

### Owner accepted, 2026-10-18 evening
Owner reports "visually the door lock is fixed" in Door Indicator Review
(runtime b668ab7dafdd338ae10206d8dc1618e10482fdce114cdfb935420d92a6c340ca).
Screenshot codex-clipboard-8ZqYAF.png shows the green status symbol at the
previously problematic camera distance. This accepts the scoped opaque-marker
remedy in the reported location; the change is unreleased.

Established trigger: native camera-distance fading sends an almost opaque
marker (including alpha254) through the alternate transparent display list.
Keeping a completed unlocked indicator on the opaque path removes the reported
blackout. The exact reason that transparent mesh loses its visible symbol
(depth/self-overlap versus material/blending) remains unproven; do not claim
a general RT64 transparency fix. Normal gameplay state, hidden markers, lock
requirements and culling remain unchanged. Marker distance fade is intentionally
suppressed only during this qualified draw; far-boundary disappearance still
uses native culling. Broad unrelated transparency changes are not warranted.

Transferable lesson: Original-mode reproduction and camera-distance isolation
were more discriminating than an interpolation/LOD hypothesis. An opacity
change from255 to254 can select a completely different native display list,
so compare selected render paths before treating it as simple color dimming.
Actor+0x28 was animation progress, not brightness; that earlier interpretation
must not be reused.

### Scope clarified with owner
Owner asked whether the visible repair is valid or a band-aid. Answer: it is
a targeted workaround that suppresses the unlocked marker's distance fade.
Visual acceptance does not close the underlying transparent-rendering defect.
Keep that investigation OPEN; the final release decision must distinguish the
workaround from a proper transparent-path repair. Investigate draw/depth/material
behavior rather than silently claiming the root cause is solved.


A further private CPU material packet is prepared in source, not yet in the
owner's running Door Indicator Review. It captures both native model display
lists and associated asset/animation bytes, plus emitted outer draw commands,
once per unlocked asset/opacity path (maximum eight packets). Data remains in
the existing buffered trace on D:. No screenshot, GPU readback or per-frame
file write. This is to inspect the actual affected model rather than infer
from unrelated retained switch assets. It does not change draw behavior.

Native parity limitation: Original FPS in this recomp still uses RT64. No owner EmuHawk/N64 same-camera-distance comparison has yet established whether the native transparent switch mesh also blacks out. That comparison remains pending; neither the current workaround nor the Original-FPS reproduction proves a renderer deviation from hardware.


### Owner comparison status ? 2026-10-18 late review

The owner has not yet checked this door at the same distance in EmuHawk or on original hardware. Original-FPS mode in the recomp still uses the recomp renderer; it cannot establish original-game fade parity. The green-at-distance result verifies the scoped opaque workaround only. The native material/depth cause and intended original fade remain open.


### Proper material repair continuation - 2026-10-18 22:04 Eastern

Owner requests returning to the proper door repair and approves two hours.
The opaque workaround is not the final target: inspect the actual captured
native opaque/translucent lists and outer draw state, identify the material or
depth mismatch, and preserve native opacity/fading in a scoped correction.
The previous boss candidate includes the numeric material capture; review its
completed packets before requesting another owner route. No autonomous gameplay
or visual verification; owner reviews builds. All accepted boss/glass/blur/input
changes, saves and investigation counters are preserved.

### Actual unlocked-door material capture, 2026-10-18 late review

Owner completed Door Material Capture with the accepted opaque workaround and
boss candidate, runtime c955a489f9be1e63dded2ba16f2cb4d1205e7519054e91cddd8c8fcd75d56506.
Private evidence: v13-door-material-20261018/owner-preview,
controls-20292-404322406.tsv; decoded packets under door-packets/.
Two packets cover the actual newswitch1 model (802e2bb0), actor 801bbc80,
at native alpha255 and alpha170. The workaround emitted opaque draws in both;
this is not a capture of the unfixed translucent GPU draw.

The stored opaque and translucent native lists each contain 56 commands and
differ only in the OtherMode low word: C8112078 versus C81049D8.
Geometry, combiner and texture loads match. The selected green texture is
present; all pixels in all four selected RGBA16 texture frames have alpha1.
This excludes missing texture alpha and the earlier state/LOD explanations
for this packet. The translucent mode enables alpha blending and disables
depth writes while retaining depth comparison. No general RT64 defect has
yet been established.

Offline mesh inspection is limited: interpreting the post-draw selected
matrix buffer as fixed point produced invalid coordinates, so that result
was rejected. An alternate retained fixed-point buffer provides plausible
geometry, but is not exact-frame evidence. Its sampled center rays show no
broad self-overlap sufficient to explain the entire black center. This does
not exclude scene-depth/order problems or prove GPU correctness.

Owner is now comparing the original game in EmuHawk. It was launched for
manual use; no autonomous emulator gameplay or visual verification performed.
Proper repair remains open; accepted opaque workaround is unchanged.

### Native comparison resolves classification, 2026-10-18 late review

Owner reports: "it does black out in emu" and "it appears to be a game quirk".
This independently reproduces the reported symptom in the original game via
EmuHawk, rather than Original FPS mode in the recomp. The current evidence no
longer supports pursuing this symptom as a recomp-specific renderer defect.
This is an owner visual result, not an automated parity test or a claim about
every emulator/backend/hardware configuration.

Retain the already owner-accepted scoped opacity change as an intentional
readability improvement. A completed unlocked behavior-67 marker remains
opaque while its native draw commands are emitted; its simulation opacity is
restored immediately. Locked/animating, hidden, culled and special-mode actors,
enemy counts and progression are untouched. Native distance fading for this
specific visible marker is intentionally suppressed. It may still disappear
at native culling distance; this is the documented tradeoff.

No general blend/depth changes or speculative material remedies were added.
The exact original-game translucent rendering artifact remains unexplained,
but resolving it is not required to claim the accepted readability improvement.
Do not describe this as a repaired RT64 transparency bug or full native parity.
The previous hypotheses and unsuccessful candidates remain above as history.
Future material work should begin from native comparison before changing
global renderer state. Build/live verification of this retained change is
recorded above; this continuation adds classification/evidence, not a new
runtime candidate. No release or commit has been made for this continuation.

Owner disposition: "this now becomes a bug fix on the original game. so mark it
and ignore for now please." Further material/depth investigation is shelved.
Retain the accepted visibility workaround; do not reopen the native bug without
owner direction. The following GitHub review is a new owner-directed task, not
a continuation of speculative door-material fixes.
