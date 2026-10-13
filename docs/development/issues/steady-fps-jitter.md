# RENDER-003: Jitter with steady 120 OUTPUT / 30 SCENES

Status: capped presentation-window correction verified in bounded tests and delivered locally; owner visual verification pending. Source-workload and Unlimited limits remain open.
Severity: high; smooth high-refresh rendering remains incomplete.

## Report and reproduction

The owner reports visible jitter even in a quiet scene while the counter holds
120 OUTPUT / 30 SCENES with no visible dips. It occurs both without input and
during motion, but is most obvious while moving Juno and turning the camera
together. The reported profile requests Custom 120 with VSync on. The affected desktop
preview was `high-refresh-native-timing-preview-20261012`, implementation
`5c7df1bdee61778590fb3b7baa281958a9167870`, runtime SHA-256
`a14d9d77fc98ef6be1999a3ea9492d60467a4b107e376c66d431fbfd70231259`.
Confirm the running executable separately; the owner report is not an automated
reproduction. The owner explicitly requests interpolation around stable actor,
skeleton/joint and camera identities, beyond matching graphics batches.

## Existing evidence and hypotheses

- [PERF-002](frame-diagnostics.md) corrects the reproduced capped-play bridge's
  source-clock fallback. That does not establish visually continuous motion.
- OUTPUT counts successful present returns, including repetitions; SCENES counts
  new submissions. Neither establishes unique images, physical scanout or smooth
  camera/animation progression. A stable average can conceal uneven intervals.
- [Presentation history](../../../include/jfg/renderer/interpolation_history.hpp)
  matches exact geometry and blends combined transforms. Unmatched/ambiguous
  geometry falls back to endpoints; animated geometry need not retain its key.
- Incomplete animation coverage, camera/player phase mismatch, coefficient
  blending and presentation/display pacing are competing hypotheses, not a
  diagnosed cause. The 30-Hz source rate alone does not make jitter inevitable.
- Combined movement and camera rotation need the same presentation timestamp.
  Stable semantic identities must include lifetime/reset handling so reused
  actors, camera cuts, teleports and mode transitions do not blend unrelated data.

## Planned validation and acceptance

Compare stationary, movement-only, camera-only and simultaneous-motion fixtures
using copied profiles/saves and muted, owned hidden windows. Measure per-frame
spacing and actual intermediate camera/body motion, not counters alone. Keep
heavy GPU screenshot captures separate from pacing benchmarks. Preserve the
original-clock reference and guest update/movement rules. Test actor reuse and
animation boundaries before claiming complete coverage. Native monitor/focus
behavior and owner visual confirmation remain necessary where hidden tests cannot
establish them. Do not infer that this report shares the heavier combat cause.

## Modern-engine references

Fixed simulation with interpolated rendering is a standard design:
[Godot's interpolation overview](https://docs.godotengine.org/en/stable/tutorials/physics/interpolation/physics_interpolation_introduction.html).
Camera handling can combine an interpolated follow target with per-render mouse
rotation; camera and target sampling must agree:
[Godot camera guidance](https://docs.godotengine.org/en/stable/tutorials/physics/interpolation/advanced_physics_interpolation.html).
These are design references, not evidence of implementation parity in JFG.

## Resolution and compatibility

The changing-geometry history gap is established and addressed by semantic
vertex ownership. It is not established as the sole cause of all reported jitter.
The candidate preserves gameplay state and the terrain correction. See the
qualification below and its later delivery record for the tested artifact. The
same guarded investigation retains all charges; unrelated PC/audio work is
unchanged. Never feed interpolated visual positions back into simulation.

## Diagnostic interruption and storage recovery

The identity diagnostic was interrupted by a full C: drive before runtime source edits or a game run. The guard retained the failed charge and stopped at 18 attempts. The owner explicitly approved one additional guarded retry within the existing five-hour deadline, preserving all counters and the investigation root.

Large private captures were moved to `D:/JFG-private/high-refresh-20261011` with SHA-256 verification of every file before removing the original copies; directory junctions preserve existing evidence references. New large outputs use D:. The production ledger and source checkout remain in place. The private relocation receipt records 16 directories, 6612 files and 8036767841 bytes.

Informative setup failures: the inventory initially used Path.is_junction, unavailable in the installed Python; Windows reparse attributes replaced it. The first cleanup script encountered PowerShell array wrapping before deleting anything; direct JSON array assignment corrected it. An automatic command review had rejected the combined relocation command without a specific reason; copying/hash verification and path-checked cleanup were subsequently separated. These failures establish no rendering result.

## Semantic interpolation candidate

The bounded identity trace ties animated matrix DMA addresses to two alternating
palettes owned by a model instance, with a stable bone index. Exact-shape matching
had left changing body geometry without history. The candidate carries actor
lifetimes and camera ownership with each immutable graphics task, and matches
logical model vertices by actor lifetime, instance, model, camera and joint.
Free requests, missing actors, level/model/camera changes and discontinuities
invalidate history. UV clones retain their original logical vertex identity.

Character vertex endpoints interpolate in world space before applying the same
camera phase. This avoids separately blending deforming local positions and
joint transforms, which can pull shared edges apart. It is presentation-only:
guest simulation and input timing are unchanged. It is not a reconstructed local
skeletal hierarchy with quaternion blending or per-render mouse look. Unsupported
draw paths retain the previous conservative matcher.

Six focused identity/interpolation/clock tests pass. The first muted moving-route
run matched 517,189 of 524,527 tagged vertices (98.6%); that is coverage evidence,
not visual acceptance. The same run averaged 119.22 output FPS and 27.29 scenes/s
in VI 4000-4400, including a 33.104-ms output interval. Pacing therefore remains a
qualification concern, and the installed preview has not been replaced. Paired
runs of the accepted runtime and candidate, without interpolation trace output,
are retained in private artifact `semantic-interpolation-v1/pacing-comparison.json`.

Implementation setup failures: a patch selector initially matched both a real
task and a skipped-task placeholder; it was narrowed before building. The first
build used RT64 interop matrix member syntax on an hlslpp matrix; row indexing
and explicit construction corrected it. Subsequent review guarded live-only
identity state for non-live builds, removed a per-UV-clone context mutex lookup,
cached joint inverse validation per DMA and inverses per transform, and skipped
semantic vertex collection for offscreen masks. The refined binary passed the route qualification below. Final review bounded
byte-swapped reads for truncated RAM spans, rejected signed-negative bone counts,
and kept unknown-camera paths on the existing conservative matcher.


## Bounded qualification (2026-10-13 UTC)

Seven focused tests pass, including retirement/address reuse, missing actors,
level/camera changes, stale buffers, ambiguous UV duplicates, actor-wide fallback,
and coincident shared-edge vertices under different joint rotations and camera
motion at five interpolation weights. F3DDKR texture tests cover the modified UV
clone path. These checks preserve endpoints; they do not establish raster coverage
of every reported thigh pose.

Without detailed interpolation tracing, the initial paired route averaged
119.85 OUTPUT / 29.78 SCENES for the candidate versus 119.90 / 29.79 for the
installed build. Refined idle, movement-only and camera-only cases held roughly
120 output FPS and 29.6-29.8 scenes/s. Combined movement/camera input was verified
in guest position/yaw samples, not merely assumed from the replay file.

The combined route exposed the same 31-update three-VI recovery episode in both
old and new builds: about 119.5-119.6 output FPS / 27.5 scenes/s over VI 4000-4400.
This remains an open source-cadence limitation. Custom 360 averaged 350.1 output
FPS / 27.4 scenes/s and included a 41.5-ms output interval. Neither observation
supports a claim of completely stable 30-Hz scenes or steady 360-FPS output.
All six normal-play cases recorded zero audio underruns and dropped log rows,
and preserved the copied save. The hidden-window tests measure successful present
returns; they do not qualify physical VSync/monitor delivery.

The original-clock reference retained exact guest/RT64 memory and copied-save
hashes. Paired original-clock visual runs likewise retained identical final
guest and RT64 memory. The first selected screenshot window was after movement
had stopped and was inconclusive for animation. A second bounded window targets
active simultaneous movement. Swapchain readback captures deliberately stall
rendering and are excluded from performance claims. Capture counts and hashes,
tested runtime identities and route results are in
[qualification](../../../evidence/semantic-interpolation.json).

In the active window, the baseline repeated one complete image across six
subframes, while the candidate produced six different images and changed dark
blue character pixels in each adjacent pair. The capture start can land on a
different presented group, so this is sampled motion evidence, not an exact
paired per-frame trajectory or proof that every output image is unique. Visual
inspection shows the walking pose progressing; the automated body mask excludes
the surrounding bright water but is not a complete character segmentation.

The remedy is host presentation metadata and world-space vertex interpolation;
it does not increase simulation/input frequency, reconstruct a local skeleton
hierarchy, interpolate lighting attributes, or implement per-render mouse look.
Unsupported paths keep conservative transform matching. Teleports and large
projected discontinuities hold an endpoint; every small cinematic cut and model
variant is not yet covered. Reported Original-mode thigh gaps, delayed lighting,
combat slowdown, Unlimited saturation and long-session/audio behavior remain
separate open work. Owner live confirmation is required before resolving this
jitter report.

Transferable lesson: constant output counters do not establish unique, coherent
animation samples. Carry stable ownership with the immutable render task, make
all parts of an actor share the same fallback decision, and measure screenshot
motion separately from timing to avoid diagnosing readback overhead as normal
play stutter. Large evidence remains on D: with verified stable references.


## Local preview delivery (2026-10-13 UTC)

Implementation commit `01a35a13539a89e8842b8491eb37565d42b03de8` is packaged as
`high-refresh-semantic-20261013` on D:. The existing **JFG - High Refresh Preview**
desktop shortcut now selects that package. Close an older launcher and reopen
the shortcut to test walking while turning the camera. Your existing profile,
save and settings were preserved; all 14 package manifest entries and launcher
initialization passed. F8 and **JFG - Performance Logs** remain available.
No public release or push was made.

The exact delivered runtime SHA-256 is `71f59d66fc20e62f85cc3c2c280e72a85b02aee61e0de5a87adf45fe80f906b4`.
Final combined-motion qualification averaged 119.87 output FPS /
27.49 scenes/s at Custom 120 with requested VSync, and
345.38 / 27.44 at Custom 360 with VSync off.
Output p99/max intervals were 8.637/10.200 ms and
4.228/42.520 ms respectively.
Both normal-play runs recorded zero audio underruns/dropped log rows; the exact
original-clock memory/save reference still matches. The existing three-VI
recovery episode remains visible; these are not steady-30/steady-360 claims.
Detailed results are in the qualification JSON. Owner visual review, full-game
coverage, physical monitor pacing and the separate seams/lighting issues remain
open. The previous package is retained for comparison.


## Owner-approved continuation (2026-10-13 UTC)

The owner approved five further hours to continue the open pacing, thigh-gap and
delayed-lighting issues after local semantic-interpolation delivery. The same
production guard remains enabled, retaining 19 attempts, 18 activities and
33222.14147090912 seconds before the new lease. One additional guarded session
is authorized until 05:29:07 UTC; no counters or roots are reset. New large
artifacts use private storage on D:. Tests remain muted with owned hidden windows
and copied profiles/saves. The installed semantic preview remains the comparison
baseline until a new candidate is independently qualified.

First step: correlate retained present intervals, guest update work and graphics
submission waits around the combined-motion three-VI recovery episode. Reuse
existing seam/lighting captures to define an exact pixel or spatial boundary;
avoid repeating broad captures without a new discriminating measurement.


The first new pacing fixture exited at startup: it requested CPU-cost diagnostics
with --play, which the runtime deliberately rejects. The wrapper then reported
a dead-window ownership assertion while the process was closing. No gameplay or
pacing evidence came from that run. Corrected tests keep CPU-cost sampling on
the supported finite native-clock probe; ordinary play uses the existing light
trace/counter only. The failed fixture and its environment are retained.

Owner follow-up after reopening the semantic preview: "No seems at 120". Record
this as live confirmation that the reported thigh lines are absent at 120 FPS
in that test, not acceptance of every pose, frame-rate mode or lighting state.


### Owner follow-up: stationary camera spin (2026-10-13 UTC)

The owner reports only movement/camera jitter remains in the delivered semantic
preview at 120 FPS. The thigh lines and delayed lighting are absent in that
live check; this is scoped owner confirmation, not a claim of all-scene parity.
A more precise jitter reproduction is to stand still and rotate the camera in a
full circle. The view jumps and looks blurred despite a steady 120 OUTPUT /
30 SCENES counter. Present frequency alone is therefore insufficient acceptance:
measure the camera/geometry displacement of consecutive presented images.

Current hypotheses include camera/terrain history falling back as visibility
changes, skipped or repeated interpolation samples, and camera sampling phase.
Separate the broad 20-Hz recovery event from this stable-counter reproduction.


### Capped sequence truncation candidate

The stationary-spin trace confirms nonuniform displayed interpolation progress
even though the output and source counters remain approximately 120/30. The
finite-rate workload loop treats the next queued shadow-only task as a new scene
and abandons remaining intermediate frames. This priority test already filters
shadow tasks in Unlimited mode; capped modes had retained the broader test.

Candidate: apply the same scene-aware queue check at capped rates. A real next
scene or unknown workload still preempts; the existing time budget still sheds
work on overloaded machines. Record actual displayed scene/alpha identities
through the optional trace, and separately measure ordinary uncaptured play.
This is a candidate until paired spin and combined-motion tests pass.


The first instrumented spin held 119.74 output / 29.78 scenes per second, but
162 of 743 displayed samples repeated their predecessor's interpolation phase.
All 185 measured camera cohorts matched: scenery history loss did not explain
that interval. The optional output trace captures source tick and alpha alongside
the actual selected target before its GPU read, rather than inferring motion
from the render queue or FPS counter.

The scene-aware queue check alone still leaves duplicates. A second cause is the
completed-sequence VI path: it schedules another entire source-frame window of
identical endpoint images. That can hold an endpoint for 33 ms and defer the next
scene, while the output counter continues to report 120. Candidate correction:
acknowledge an already-consumed finite scene immediately and let the next source
scene own its output window. Original mode, paused debugger work and Unlimited's
stream handling retain their own paths. Qualification is still pending.


The second candidate produces 740 strictly advancing samples (every step 0.5 VI)
across 185 scenes in the original camera-pan fixture, with zero repeats or
backward samples. The wider nominal-circle fixture traversed only 314.3 degrees:
its real applied look samples, rather than intended input rows, exposed incomplete
coverage. The first qualification script correctly stopped before broader tests.
Increase the turn rate and verify actual accumulated yaw exceeds 360 degrees.
The wider trace crossed a normal 30-to-20 Hz recovery interval; phase analysis
must use each scene's actual source interval, not assume two VIs for every scene.
Earlier repeat counts are unaffected, but the reported step-size anomalies at
20 Hz were an analysis error and are superseded by interval-aware analysis.
The retained pre-fix wide sweep also had eight audio underruns during its warmup;
it is not clean audio acceptance. Muted normal-play qualification remains pending.

Optional screenshots can now select a bounded source-scene interval, with a hard
64-image limit. Scene selection requires the optional output trace, which supplies
the image's source identity. Readback timings are never used as a benchmark.


### Capture regression caught before delivery

Eight ordinary-play mode/pause fixtures completed, but the final finite reference
probe failed closed with renderer `present-10` (frame capture failed). The new
duplicate-VI skip had also skipped a specifically armed diagnostic screenshot.
Its renderer RAM still matched the reference, but the early trap invalidated
the final guest-state check. No parity pass is claimed for that failed run.
Dependent qualification/commit preparation stopped without edits.

Correction: the single active capture owner exposes an atomic pending flag,
set when armed and cleared on completion, exception or deactivation. A requested
capture presents one latest image even for a consumed scene; ordinary duplicate
VIs still yield immediately. Explicit CPU framebuffer operations also preserve
their existing presentation path. Re-run the exact reference and camera-phase
checks before local delivery. Preserve the failed probe and all step receipts.


## Confirmed cause and qualified correction (2026-10-13 UTC)

Two queue policies prevented uniform presentation progress. Shadow-only jobs
could truncate a capped scene before all intermediate images were generated.
Separately, an extra VI referring to a consumed scene scheduled a full second
window of its final image. The next scene then arrived visually late despite a
steady present counter. Both policies are corrected in
[the RT64 queue adapter](../../../cmake/rt64_video_settings.cmake).

A muted stationary pan changes from 162 repeated phases in 743 displayed
samples to 740 samples with 739 equal 0.5-VI steps and no repeats or rewinds.
The corrected full-circle fixture verifies 419.0625 degrees of actual applied
camera yaw and 1,702 displayed samples with 1,701 equal steps, including the
31-update 20-Hz recovery interval. All 410 measured scenery camera cohorts
remain matched. Separate screenshots of actual swapchain images demonstrate
intermediate scenery motion; they are not a timing benchmark.

Normal hidden play results over VI 4000-4400 follow. These measure successful
present returns, not physical scanout. The pause case intentionally includes
a 1.25-second pause and must not be compared as ordinary pacing. The reference
case uses the retained diagnostic clock and is for exact state comparison.

| Fixture | Output FPS | Scenes/s | p99 ms | Maximum ms | Audio underruns |
|---|---:|---:|---:|---:|---:|
| normal-circle-120 | 119.68 | 29.77 | 9.000 | 10.298 | 0 |
| normal-combined-360 | 335.83 | 27.44 | 9.496 | 34.097 | 0 |
| normal-circle-144 | 143.85 | 29.82 | 7.278 | 8.066 | 1 |
| normal-circle-60 | 59.82 | 29.84 | 17.583 | 18.187 | 0 |
| normal-circle-480 | 458.79 | 29.78 | 3.851 | 16.875 | 0 |
| normal-circle-unlimited | 1274.77 | 19.13 | 3.071 | 5.427 | 413 |
| normal-original | 27.89 | 27.59 | 51.511 | 52.271 | 0 |
| pause-120 | 100.73 | 25.09 | 9.215 | 1260.765 | 0 |
| reference-state | 119.65 | 24.56 | 8.974 | 15.801 | 0 |

The finite reference run retains the exact guest RAM, renderer RAM and copied
save hashes. Focused timing, interpolation, texture and video-setting tests
pass. Full measurements, source/runtime identities, artifact hashes and limits
are in [qualification](../../../evidence/presentation-pacing.json).

Transferable lesson: qualify monotonic source-time progress and actual images,
not just output/submission rates. An already-consumed VI does not authorize a
second animation interval. Small offscreen tasks must preserve the owning
scene's interpolation window; new scenes and actual overload still take priority.

This verifies the reproduced duplicate-window defect. Native workload spikes,
physical display smoothness, Unlimited saturation, the heavier combat report
and complete scene/animation coverage remain separate limits.


The source-controlled [trace analyzer](../../../scripts/analyze_presentation_trace.py)
reproduces these phase counts. Four regression tests cover mixed 30/20-Hz source
intervals, steady-timestamp freezes/jumps, backward samples and invalid input.
For example, after capturing the optional TSV, run:

```text
python scripts/analyze_presentation_trace.py interpolation.tsv --from-vi 3900 --to-vi 4750 --expected-fps 120
```

Use the effective output cap after VSync; omit the expected rate for Unlimited.
The display row records source VI, source rate, requested target, render index,
sequence length, alpha, present ID and target slot after its monotonic timestamp.
A uniform phase does not establish physical scanout or unique pixels: retain
camera-coverage and actual-image checks alongside it.


The capture-compatible build now passes the specifically armed final screenshot
and exact guest/renderer/save hashes. A fresh full-circle trace still advances
strictly at the expected phase with no repeats or rewinds. Normal combined
360-cap play was repeated separately. The final compatibility proof and runtime
identity are in qualification; the earlier failed capture remains preserved.
One 144-cap fixture reported one audio underrun, and Unlimited reported 413 with
about 19 scenes/s under saturation. Those are limitations, not audio acceptance;
the 120-cap and capped combined-motion audio results are recorded separately.


## Local delivery

Implementation commit `b9c1aeee7d259f358a5a76ac22b9ba6c9b7644d6` is committed on the
research branch. The desktop **JFG - High Refresh Preview** shortcut now targets
`high-refresh-pacing-20261013` on D:. Close the game and launcher before reopening.
The delivered runtime SHA-256 is `8bd6b7635ec71a70c735055af97df5119df9f8a0b00d942825b226259ffe9cf7`.
All 14 package entries verify, an isolated launcher-init fixture resolves that
exact runtime, and the owner's profile/settings/save hashes are unchanged. The
older semantic package is retained. This is a local preview, not a release.

The exact delivered binary passed nine focused C++ checks, four analyzer checks,
the corrected full-circle trace (1,700 samples / 1,699 uniform steps), fresh
combined 360-cap play, and the armed screenshot / exact reference-state test.
The latest combined-motion run averaged 351.62 output FPS over its active
window, with the existing 31-update source-cadence recovery still present.
No audio underruns were recorded in those final circle/combined replays.
The rebuilt committed executable is byte-identical to that qualified binary.

The owner has been asked to retest a stationary full-circle camera rotation at
Custom 120 / VSync on. Monitor scanout and owner visual acceptance are pending;
this record does not mark all high-refresh limitations resolved.

## Completed CPU-write windows (2026-10-13)

The expanded owner route exposes another completed-sequence case: framebuffer
writes bypass the earlier empty-operation skip and repeat one endpoint for a
full finite interval. The correction displays that completed endpoint once,
without discarding CPU writes or changing game timing. Bounded repeated phases
fall from 995 to 35 with no backward phases. Pause and final captures pass.
The base/interpolated CPU-write target mismatch remains a separate limitation.
See [the route review](tutorial-late-object-jitter.md#review-qualification-2026-10-13)
and [qualification](../../../evidence/high-refresh-route-review.json).
This does not establish a fix for the owner's exact late light/bridge jitter.
