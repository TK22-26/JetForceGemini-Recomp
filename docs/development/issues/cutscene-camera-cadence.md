# RENDER-CAMERA-CADENCE: Pulsing motion in flight cinematics

- Severity: moderate visual smoothness report.
- Status: resolved locally: camera, ship attachment and startup corrections
  visually verified in normal-launcher review, with two clean repeat captures.
  Unreleased; the earlier isolated hitch remains unlocalized in the history.
- Reported/updated: 2026-10-24 UTC.
- Affected: private candidate `1d631c0`, 120 FPS/VSync, Reduced blur, same
  renderer as v1.4.0. Gameplay reportedly becomes smooth again.

## Symptoms and reproduction

After character selection, Juno's ship leaving the main ship and landing on
Goldwood appear consistently lower cadence. The owner describes repeated
smooth camera motion followed by a small fast jump, and possible independent
ship jitter. Some objects/effects remain smooth. The owner suspects a bug
rather than an unavoidable consequence of 30 Hz native scene updates.

## Evidence, hypotheses and attempts

The closed `flight-shot-capture-20261024` owner session contains gameplay,
interpolation, timing, input and final-memory streams. Review scene-specific
cadence, camera/ship ownership and phase continuity before attributing this
to the native rate. Logging overhead and transitions are confounders.
The 60-native-update proposal is not implemented or performance-qualified.
See also [shot and exit-particle effects](high-refresh-shot-effects.md).

## Resolution and verification limits

The camera improvement has an owner visual pass and native-versus-precision
matrix checks. Original mode retains native table results. Ship-cone ownership
and first-appearance attachment now pass focused tests and real-input replay;
the startup correction also passes replay. Two subsequent normal-launcher live
passes are clean and accepted by the owner. Native
scene updates remain at 30 Hz. Neither these rendering changes nor a shot-effect
fix has been released. Historical attempts and their limits follow below.

## First capture analysis

The output presentation phase advances regularly by half a VI for almost all
frames, and scene data normally arrives at 30 Hz. This does not show a general
collapse of the 120 FPS output. An initial analysis incorrectly treated nominal
120 FPS as exact rather than twice the native VI rate; that diagnostic
classification was corrected without changing runtime timing.

BoyAnimShip has sustained invalid semantic samples in scene 365 (character
selection departure), 93 (Goldwood flight), 15 variant 1 (Walkway departure),
and 102 (Anubis docking). Whole-actor safety consequently holds its animation
at the source endpoint while most scenery camera geometry continues matching.
The precise invalid provenance is still under investigation; do not disable
the safety check. The earlier dead-drone report explicitly left comparable
cutscene actors unverified.

A bounded opt-in matching observer now records invalid model/joint/source
provenance and matrices, plus billboard matching reasons. A copied-save replay
is collecting that evidence. The first probe failed before gameplay because
normal-play optimizations require explicit native-clock/span options in probe
mode; the corrected replay uses those options. No visual fix is accepted yet.
Private analysis: flight-shot-analysis-20261024/coverage-and-actors.json.

## Ship provenance cause and candidate

The invalid samples are separately allocated thruster cones, not singular
bones. US module 73 `animshipDrawThrusters` uses the selected ship instance's
bone palette to draw `fxDrawCone` buffers. Only ordinary model vertex streams
were previously registered, so the cone vertices lacked geometry ownership.
The whole-actor consistency guard consequently held the hull and engines.

The candidate registers the exact bounded `fxAllocateCone` layout for the
live ship actor, control allocation, selected model instance, attachment bone
and both alternating vertex buffers. Logical indices survive buffer parity;
separate engines remain separate, and unknown/malformed/ambiguous data still
holds. It changes presentation metadata only, not simulation or source cadence.
Three focused suites pass, including buffer alternation, wrong bone/actor/
lifetime/instance, allocation limits and malformed layout. A strict-warning
build initially rejected a shadowed variable; it was renamed and the runtime
rebuilt successfully. The private snapshot fixture resolves all 272 combinations
of the captured ship's two engines, two vertex buffers and two palettes.
Full-route candidate replay and owner visual review remain pending.

The candidate replay reached Goldwood and early Anubis, then exited at the
probe-only 24-billion guest-instruction cap (VI 50280, exit 4). This is an
incomplete replay, not a successful full-route test or evidence of a normal
Play crash. The cap remains unchanged. Its interpolation stream preserves
the early ship result; the memory-only gameplay stream was not flushed by
the failure path. The next verification uses a short live copied-save capture.

In the shared VI 23950-24900 ship-flight window, the diagnostic baseline
has 215 sampled frames,
215 with rejection reasons, and
51600 invalid samples. The
candidate has 221 frames,
1 with rejection reasons, and
0 invalid samples. This supports
the ownership correction in that flight; timing offsets and the later
instruction cap prevent claiming exact whole-route state parity.
Private report: flight-shot-analysis-20261024/ship-comparison.json.

## Local review delivery

`JFG - Ship and Effects Preview` opened on 2026-10-24 with a copied save,
120 FPS, Reduced blur and the FPS overlay disabled. The ship ownership
candidate and accepted audio recovery candidate are included. Extra shot
and visible-billboard diagnostics are explicitly enabled by a privately built
launcher helper; ordinary launcher sanitization and release sources remain
unchanged. All three interpolation suites passed again after probe additions.
No visual acceptance, full-route qualification, commit, push or release yet.
Private delivery manifest: flight-shot-analysis-20261024/live-prepared.json.

## Owner review of the ship candidate

The owner reports smoother flight, but remaining microstutters in space and
a jittery camera when switching to Goldwood. This is partial improvement,
not full acceptance. The review capture is closed and preserved under
flight-shot-analysis-20261024/review-analysis/capture-complete.json.
Compare native camera transforms and timing against interpolation holds
before attributing the remaining motion to authored camera rails.

## Remaining camera motion, 2026-10-24

The closed review records a continuous AnimCamera path: 162 actor samples
in space and 814 at Goldwood, with consecutive source updates two VIs apart
after initialization. Camera ownership accepts all 160 subsequent space
frames and all 812 subsequent Goldwood frames. Goldwood scenery has no
coverage holds. This rules out repeated camera-history rejection in these
shots; actor positions alone do not prove the final rendered view is smooth.

Goldwood has eight presentation phase jumps, concentrated near arrival,
with a short run near 12.5 ms per output frame instead of 8.34 ms. Native
camera coordinates still advance each update. Space has one additional
whole-ship hold at VI 92715 when 34 cone vertices first enter history; this
is distinct from the former continuous invalid-cone failure. Neither is
considered resolved. The detailed effect stream produced about 13.4 million
rows, so timing needs a lighter comparison before production pacing changes.

An opt-in read-only camera-emitted-pose observer captures the final view,
projection and emitted fixed matrix on each camera submission. A private
launcher enables it without the detailed comparison/effect streams. This
does not change camera or interpolation behavior. Private evidence is in
flight-shot-analysis-20261024/review-analysis.

## Lightweight final-view capture

Owner confirms the lighter capture looks exactly the same. Its space and
Goldwood display phases advance uniformly by 0.5 VI (636/3244 consecutive
steps, no repeats or skipped phases); median presentation intervals are
8.346/8.341 ms. The earlier timing burst is therefore not necessary for the
visible jitter, and removing logging is not a remedy.

The final view contains angular plateaus and roughly 0.0879-degree steps
while position continues smoothly. Original US camSetProjMtx calls
matrix_XYZ_YPR, which calls Sinf/Cosf. Those original functions index the
floating-point sine table using angle >> 4, discarding four angle bits.
A private reconstruction compares this original table path directly with
the captured actor angles and final view; see camera-analysis/native-trig-correlation.json.
This is a source-level precision lead, distinct from frame pacing and the
one-frame ship topology birth hold. No new camera remedy has been accepted.

## Precision comparison and owner result

The original table reconstruction exactly matches all 978 captured rotation
matrices (163 in space, 815 at Goldwood), with maximum element error zero.
This establishes an original camera-math precision limitation, rather than a
new interpolation-history failure. The owner comparison is consistent with those steps becoming more visible
at higher resolution. It does not explain every isolated hitch.

A private, default-off `JFG_DIAGNOSTIC_CAMERA_PRECISION` comparison interpolates
between adjacent original floating sine-table samples, retaining the four
low angle bits. Admission checks the exact camera view/inverse matrix builders,
return addresses, transform scratch and destination; other game trigonometry
is unchanged. The original call still runs and preserves its timing/register
side effects; only its floating result is replaced, with the host floating
exception environment preserved. Native fast and generated fallback paths
both apply the comparison. The table helper rejects nonfinite input.

The runtime/private launcher build and three focused interpolation suites pass.
Tests cover all 65,536 encoded angles, quadrant boundaries, invalid table values
and camera-call rejection. The copied profile/save is isolated; ordinary
launchers do not enable the experiment. Source: camera_trig_precision.hpp,
native_boot.cpp and semantic_presentation_tests.cpp.

The owner first reported smoother motion, then that the camera jitter appeared
entirely fixed, and clarified that two hiccups remain in the opening space
shot. Therefore camera smoothness passes this local visual comparison;
overall flight cadence remains open. The closed capture independently matches
the higher-precision matrix model in 162/162 space and 813/814 Goldwood samples
with maximum error zero among those matches; one Goldwood sample does not
match the nearest actor samples. Display phases remain uniform (636 and 3244
successive half-VI steps). This is a tested opt-in candidate, not a released
or generally qualified default. Gameplay/Original-mode compatibility and the
two residual space hiccups remain to be resolved.

Private evidence: flight-shot-analysis-20261024/precision-analysis,
precision-live-prepared.json and precision-tests.txt. No commit, push or release
of these rendering changes has occurred in this investigation.

## Residual space hiccup evidence

The precision capture has a 33.054 ms presentation interval at VI 1790,
about 0.08 seconds after scene entry, and a separate whole-ship interpolation
hold at VI 1892, about 1.79 seconds after entry. The latter contains 34 newly
appearing cone endpoints; native ship movement continues. These are two
candidate explanations for the owner's remaining hiccups, not yet correlated
to their observed moments. No blanket history-guard relaxation was applied.
The lightweight stream intentionally omits detailed camera-history rows;
empty rows in that analysis do not prove a matched history count.

The actual captured sine table was independently swept over all 65,536 angles
against mathematical sine. Interpolated error stays below 0.000001 and every
original 16-unit sample boundary remains exact. This numerical check does not
qualify aiming, culling, split screen or Original presentation. A reusable
analysis initially assumed optional camera-history rows were present and
failed with KeyError; the revised parser handles absent diagnostics explicitly.

An inverse-consistency check initially read reused scratch 0x800F2A08, then
misread emitted matrix 0x800FAF38 as floats. Neither attempt is a valid check.
Source identifies mathMtxF2L at 0x80048D84: the stored inverse is N64 split
16.16 fixed point. Correctly decoding it gives view/inverse rotation error
7.49709443e-06; acceptance below 0.0001 is True. This remains a one-snapshot
consistency check, not general gameplay/culling/Original qualification.

The owner says the two proposed hiccup moments sound right. Keep startup
rate acquisition and the new engine-cone history hold as distinct targets.
They approved one additional hour for production integration, compatibility
and those two residual hiccups; the same investigation/counters are retained.

## Normal-mode integration and residual cone candidate

Owner approved one additional hour after the camera pass. The camera precision
path is now selected by the existing high-refresh presentation mode. Original
mode retains native trig; the private precision switch is no longer required.
Three focused suites pass, including disabled-mode and non-camera rejection.
Muted copied-profile replays completed at 120 FPS and Original with exit zero.
The initial Original replay has no camera-pose rows because the diagnostic
observer was coupled to presentation metadata; that observer is now separately
admitted by its diagnostic flag, without enabling precision or identities.

The residual engine candidate observes exact animated-ship bone palette loads,
then lets a newly visible, owned cone use its current local shape at the verified
previous attachment transform. The usual camera, world-motion, cadence and
whole-actor corruption guards still apply. No generic missing-vertex exception
is introduced. Unknown or conflicting parent poses continue to hold. This is
an unverified candidate until its focused tests and replay pass. An initial
build failed because one auto declaration combined const and mutable iterators;
the declarations were separated and the failure remains in private evidence.

The attachment candidate builds and passes all three focused interpolation
suites. New tests keep body/flame attachment aligned at 120/360 output phases
and reject unknown parent identity, stale cadence, zero/nonfinite matrices,
conflicts, camera changes and corrupted body data. Muted real-input replay is
running; no live acceptance of this additional change yet.

Startup investigation shows the first continuous source frame already has
matched transforms but produces one output while the following frame produces
four. RT64 requires the target framebuffer's prior-VI interpolation flag.
A separate candidate permits generating outputs for a proven native 320-wide
RGBA16 color buffer with current continuous history, excluding paused,
offscreen, blur-parent and depth/readback cases. Actual presentation still
selects through the original VI/history path. This candidate requires replay
confirmation and visual review; it is not yet an accepted startup remedy.

The first attachment replay completes with zero noninitial ship rejection rows.
At the former engine birth, 34 vertices use the verified previous attachment
and the whole hull continues interpolating. Original-mode diagnostics now
capture its matrices independently: all 977 sampled flight matrices exactly
match native table math. The 120 FPS run matches the precision model in all
163 space samples and 813/814 Goldwood samples, retaining the previously noted
single actor-sample correspondence limit. A first analysis started before the
Original replay finished; it stopped on the missing completion file and was
repeated only after both replays exited successfully.

Source review caught a selection-order risk in the startup candidate: an
inferred framebuffer could precede a confirmed display buffer in a multi-target
task. Confirmed display targets now always take priority, regardless of scan
order; focused cases cover both orders. No live preview used the intermediate
selection policy. The existing depth-readback and historical-depth exclusions
remain intact.

The final startup bootstrap candidate passed the three focused suites but did not activate in the real-input replay: no bootstrap events, and the first continuous scene still renders once, followed by a 33.614 ms display interval. This falsifies acceptance of the proposed startup remedy. A narrowly scoped target-selection diagnostic is being added to identify the excluded state before deciding whether to revise or remove the candidate. Engine birth remains accepted by replay (34 endpoints, no noninitial ship hold); no live preview of startup changes yet.

The target probe isolates the startup exclusion: at VI1870, source30 with 197 matched transforms selects native color0x135700, but FramebufferManager::find returns null. Its metadata entry is created by the subsequent render, after target selection. This is not merely a stale interpolationEnabled flag. The revised candidate allows an as-yet-unallocated target only through the same current scene/color/cadence/history/depth checks, keeps confirmed-target priority, and leaves actual VI selection unchanged. A fixture reproduces missing manager entry and rejects missing history/rate and depth use. Build/replay/live verification pending.

## Missing first-use framebuffer: candidate verified in replay

The corrected candidate accepts the current workload's proven native color target
before its framebuffer-manager entry exists. Its first continuous source frame
now generates four outputs. Final 120 FPS replay exits zero and activates exactly
one bootstrap in the opening space shot (VI1853, target0x135700). Every measured
subsequent display phase advances 0.5 VI; the former 33ms gap becomes approximately
8.3ms, with no >14ms display intervals across the sampled space shot. The first
frames with no history still correctly remain uninterpolated. This is not a claim
that arbitrary loading stalls or all transition latency can be removed.

The engine birth still uses 34 verified attached endpoints, with no noninitial
whole-ship rejection. All three interpolation suites pass, including the historical
depth/readback exclusion and confirmed-target precedence. Normal launcher preview
uses the latest copied owner save, 120 FPS, Reduced blur, fog100, standard capture
and no FPS overlay. No private camera-precision switch or diagnostic launcher is
needed. Combined owner visual review remains pending; this is not released.

Private evidence: camera-flight-integration-20261024/final-tests.txt,
final-replay-analysis.json, final-display-analysis.json, live-prepared.json.
Transferable lesson: render-target allocation and VI recognition happen later than
interpolation target selection. Prior manager metadata cannot be the sole gate for
first-use color targets; current-workload proof and actual presentation selection
must retain separate responsibilities. The unallocated case must not relax depth,
scene-continuity or confirmed-target priority protections.

Combined normal-launcher live review: owner reports a remaining hiccup after the ship starts rocketing away. Do not mark the visible space-shot issue resolved from the replay improvements. Standard live capture 20261024-190516-7d6cd8a5a0c04d938964cbbfdf2633dc is being examined; gameplay/capture files remain untouched.

## Combined owner acceptance

The owner replayed the space shot two more times and says it now seems fine,
possibly attributing the first isolated hitch to the computer. That explanation
is not independently established. Preserve the earlier report without treating
it as a consistently reproducing candidate failure.

The two repeat captures each contain 640 selected space outputs, zero repeated
or uneven phases, and 0.5-VI phase increments. Median intervals are 8.344/8.345ms;
maxima are 9.765/9.360ms. Each activates the corrected first-use color target and
matches 34 new engine-cone vertices. Only the initial no-history ship frame is
rejected. The first reported-hitch capture also has no repeated/uneven phases
or noninitial ship rejection; its maximum interval is 13.451ms. These measurements
do not establish the subjective cause of that isolated hitch.

A muted replay of the first owner input exits zero. All 162 sampled space camera
matrices exactly match precision math; Goldwood retains the known one-sample
actor/camera correspondence limit (814/815 exact, max0.000450462). No claim of
complete gameplay, aiming or split-screen qualification is made. Original-mode
camera math was separately verified in all 977 prior flight samples.

The candidate is visually accepted locally. It is not committed or released.
Bullet-shot and exit-particle interpolation remain separate unresolved work.
Private repeat evidence: live-captures/20261024-190917-6ac7ceaaf73144bab14dbc1543f1a8b3
and live-captures/20261024-190956-d2fce4097bee445fa56fa4297d21e88d under
camera-flight-integration-20261024. The combined analysis initially mislabeled
the capture-name field with the helper's last actor name; labels were corrected
against the captured file hashes, preserving the original report and metrics.

## Cerulean entrance report (Vela)

The owner reports similar camera cadence on entering Cerulean as Vela during
the skirt review. The running preview profile is set to Original FPS, with the
remembered custom target at120. The precision enhancement intentionally retains
native math in Original FPS. This is not proof that the enhanced path failed,
but neither have all camera paths been audited. No matching capture is available
from this logging-off session. Cerulean high-refresh confirmation remains open;
space/Goldwood acceptance does not establish universal camera coverage.

The owner confirms the Cerulean observation was still Original FPS. The precision enhancement was therefore intentionally inactive. Cerulean high-refresh retesting remains pending; this report is not evidence of a regression in the enabled fix.

Owner then restarted at120FPS and confirms the Cerulean jitter is fixed. This adds an owner-verified high-refresh camera location; native Original-mode stepping remains intentional. No further camera-path change was needed for that report.


## Space backdrop jump report, 2026-10-24

The owner isolated two frames of a jumping skybox in the otherwise smooth main-ship to Goldwood launch. Source video: owner recording `2026-10-24 18-26-21.mkv` (retained privately). This reopens the residual apparent hitch specifically as backdrop motion; the previously accepted ship/camera precision fixes remain in place. The current projectile-motion candidate is still awaiting separate live acceptance. Video timing and the sky draw/history path are under investigation; no cause or remedy is yet verified.

Targeted replay finds three consecutive native sky-transform holds in the continuous space shot (VI2071/2073/2075), each with projected-motion rejection and no surviving geometry anchor. Main scene camera matrices already have identity; the sky actor is allocated separately by initSky and was absent from the ordinary actor identity list. A candidate gives its byte-bound draw transform a separate camera identity, with existing room/lifetime/cadence/motion/projection guards. This is not yet a verified fix. Video background spikes are at6.4167s and7.8500s; replay source intervals are not asserted to be an exact match to the independently recorded session.

First sky candidate failed to eliminate the holds: folding world/view before verifying the native fixed matrix changed floating-point association, so the byte-bound owner was rejected on some frames. The revised candidate preserves native world*(view*projection) operands for validation and uses folded model/view only for the continuity test. It retains independent lifetime, room/camera-mode, motion, projection and ambiguity checks. Replay and live verification pending.

The revised sky replay completed successfully: 161 source frames in the space shot, with all 160 continuous intervals matched and only the first-frame birth held. Both camera owners validated throughout. This is targeted replay verification, not yet owner visual acceptance. The temporary all-mesh backdrop probe was removed from the normal candidate. Tests additionally reject conflicting native pose claims, changed lifetimes and camera cuts even when a separate folded motion representation is present.

The owner confirms the two backdrop jumps are gone in Skybox and LOD Preview, with normal recording and the FPS overlay disabled. This targeted skybox correction is now owner-verified locally and remains unreleased.
