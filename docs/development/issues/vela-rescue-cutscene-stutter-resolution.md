# RENDER-011: Vela rescue cutscene stalls and changes apparent resolution

- Follow-up: https://github.com/TK22-26/JetForceGemini-Recomp/issues/21 (1.3, including general performance work).
- Severity: significant visual interruption.
- Status: opt-in GPU composite/history candidate passes scoped boss checks and
  rescue still/reference checks; remaining late updates and moving/live visual review open.
- Reported: 2026-10-18 UTC.
- Affected build: official Windows v1.2.0, Ichor owner capture on the SSD runtime.

## Symptoms and reproduction

The owner observed a large lag spike and sections that suddenly looked very
low resolution when Vela is rescued. This is the rescue cutscene, not Vela's
boss fight. Travel used map warps and health/enemy mods; this is not an
unassisted campaign correctness claim.

## Evidence

Private session: issue20-ichor-controls-20261018/owner-sessions/
20261018-030255-0015cf9d7a56445eaa72c63e1103eb71. Official runtime SHA-256:
72b2844ccaf8c5cc9a93142a7f4b42133b4a33c53ae30ecb31e527fdab40023e.
The executable is on C: SSD; capture files are on D:. Immutable guarded review
steps 220, 222 and 223 read already-recorded data while the owner continued
playing. No concurrent game, build, process-memory probe or runtime change was
used for this review. Private analysis folders are live-rescue-review-01,
live-rescue-detail-02 and live-rescue-sync-03 in that investigation.

The rescue spans approximately 521-595 seconds into the capture. The following
within-shot update gaps exclude the first row after a level/shot change:

| Shot identifier | VI range | Updates | Gaps above 42 ms | Largest gap |
| --- | --- | ---: | ---: | ---: |
| 378 | 30417-31267 | 426 | 0 | below 42 ms |
| 379 | 31281-31933 | 312 | 20 | 115.634 ms |
| 344 | 31950-32575 | 291 | 44 | 51.853 ms |
| 380, first occurrence | 32590-33398 | 324 | 118 | 134.401 ms |
| 345 | 33410-33971 | 282 | 0 | below 42 ms |
| 380, second occurrence | 33983-34749 | 384 | 0 | below 42 ms |

Audio underrun and overrun counters remain zero through this sequence. Larger
transition-spanning maxima in raw stage statistics are not counted as in-shot
stalls. A separate earlier 2.44-second gap is outside the rescue and must be
checked against pause events before being called a runtime performance fault.

## Localized stalls

The first shot 380 has renderer workload waits for presentation of up to
68.693 ms, followed by offscreen submission queue-slot waits up to 65.090 ms.
The latter site's p99 is 31.673 ms. The measured framebuffer GPU fence waits
in the same shot are at most 1.390 ms, and texture-upload waits at most
2.008 ms. This localizes a substantial delay to presentation/queue scheduling;
it does not establish exclusive GPU execution cost or explain every update.
Nested and overlapping waits must not be summed as independent CPU percentages.

The existing 1.3 opening-village investigation has a demonstrated stale
presentation-interval feedback problem and an unreleased queue-ownership
correction. Vela's long waits and expanding 4/6/8/10/12-output sequences are
consistent with that mechanism, but a controlled Vela comparison has not yet
tested that candidate. See [PERF-004](opening-village-and-cutscene-aspect.md).

## Interpolation loss and apparent resolution

Shot 344 presents almost exclusively single-output sequences (583 of 595
observed outputs), with a typical 16.808 ms output interval. Shot 345 presents
282 single-output sequences, typically 33.420 ms apart, despite stable game
updates. Ordinary neighboring shots produce four outputs per source frame.

The trace identifies a second screen-sized pass within the same VI tick:
at VI 33413 a 5,769-vertex scene renders four outputs at source rate 30, then
a scene-classified pass with zero world vertices records source rate zero;
the displayed output uses that latter single-frame sequence. A repeated tick
does not have a positive interpolation interval in PresentationHistory::record.
The current scene classifier admits screen-sized color writes without requiring
world geometry, so such a pass can replace scene history/counters. This is a
concrete lead for the interpolation loss; determine the actual copy/filter/fade
operation before changing classification or skipping any pass. HUDs, CPU
reticles, fades and legitimate 2D scenes must retain their content and ordering.

Those two shots also introduce color target 0x15af40 alongside 0x10ff00 and
0x135700. Native VI width remains 320 throughout; the cinematic mode changes
once at rescue entry and returns at exit, rather than toggling for each shot.
This does not establish the host render-target resolution. The pinned RT64
presenter has a native-resolution RAM fallback, but the current trace does not
record whether it was selected. A framebuffer-copy/effect path is another
possibility. Do not label either as the demonstrated pixel-resolution cause.

## Attempts, validation and next checks

No cutscene runtime change, new build or replay has been made for this report.
The owner recording remains active. Timing/input/interpolation logs are not
a video recording and do not prove the apparent pixel resolution. Preserve
checkpoint saves and observed warp commands for a later targeted reproduction.
After the owner closes the capture, compare the released runtime and existing
1.3 scheduling candidate on the same rescue. Record screen-pass operation,
source/destination targets and actual selected presentation resolution where
current evidence is insufficient. Boss controls remain the 1.2.1 priority.

Detailed gameplay/actor tracing reached its 256 MiB limit at 949.097411 seconds,
after the rescue. Compact game timing, frame/output logs, inputs and renderer
trace continue independently. A read-only live-context observer preserves later
room/control-lock changes for the boss investigation; it does not replace the
missing detailed actor stream. See [PERF-002](frame-diagnostics.md).

## Lessons and compatibility

One logical scene can contain multiple screen-sized graphics passes. Frame
ownership must follow the displayed scene while preserving effects, rather
than treating every full-width color write as an independent animation frame.
Keep scheduling, interpolation and apparent-resolution evidence distinct until
a shared cause is demonstrated. Do not promote partial improvement to a fix.


## Related boss-room rendering report

During the same official capture the owner reports lower apparent resolution
and poor frame rate in the Ichor boss fight (level 181), alongside the modern
controls failure tracked in [INPUT-011](github-ichor-boss-controls.md).
Two supplied screenshots show OUTPUT 47.9 / SCENES 59.9 and OUTPUT 59.8 /
SCENES 59.8. Compact game-update rows still advance by two VI. A screen-sized
zero-world-vertex pass again follows the 3D scene at the same tick and records
source rate zero, replacing the displayed sequence. This is a shared rendering
lead with rescue shots 344/345, not proof of the apparent-resolution cause.
Private evidence: owner-boss-failure-live-01. Keep input and rendering acceptance
separate; neither report is resolved by the unbuilt input candidate.


## Closed capture: motion-blur source and GPU-copy policy

The final boss memory retains the zero-geometry lists at 0x8033c7b0 and
0x8033e7b0. Their commands blend the prior screen in four-row texture strips,
with environment alpha 100, into alternating screen buffers. The pinned blur
overlay's blurUpdate (virtual 0x030000f4, section 47) builds this exact pattern;
blurTask submits its dedicated graphics task. This identifies the extra pass
as the native motion-blur effect, rather than unloaded world geometry.

The released RT64 shell disables framebuffer.copyWithGPU globally for CPU
writeback/shadow-mask compatibility. RT64's texture overlap checks therefore
skip GPU framebuffer tile copies, so this effect loads native-resolution RAM
pixels. This source path explains a concrete mechanism for losing detail;
an A/B image and native rendering validation are still required before claiming
the apparent-resolution report fixed. Re-enabling GPU copies globally would
also bypass CPU-modified masks and overlays, so is not a qualified remedy.

The second full-screen submission also replaces same-tick scene history with
a zero-rate, single-output snapshot. Preserve the original compositing effect,
CPU overlays and offscreen ordering when correcting frame ownership. No blur
removal, resolution patch or interpolation repair has been accepted yet.

Capture is now closed. Final compact play-health reports 10 audio underruns
over the full route, beyond the capped detailed trace. They remain unresolved;
the absence of underruns during the earlier rescue interval is narrower.
Private full-list/route evidence: blur-and-tail-route-review.json.


## Closed-capture rendering follow-up and rejected prototype

Full compact timing and frame logging survive closure. The final health record
contains 10 audio underruns and zero overruns; no individual underrun timestamps
exist in that compact stream. Detailed gameplay tracing capped earlier, so the
underruns cannot all be assigned to specific shots. Sparse room attribution
finds 7,151 two-VI intervals and four three-VI intervals in the late boss section.
Its output intervals have a 17.068 ms median and 35.062 ms 99th percentile.
This is a real output/presentation failure; the scene counter alone is misleading.
Private full review: long-owner-capture-review.json.

The identified 623-command native blur pass samples a 320x240 RGBA16 framebuffer.
Global GPU framebuffer reuse is disabled for CPU-softened shadow compatibility,
so this screen pass also falls back to the low-resolution RAM image. A bounded
opt-in experiment enabled GPU copies only for a fully recognized blur pass.
Both captured lists and 1,246 command mutations pass its recognition checks.
However, native route testing becomes slower and terminates at VI 13603 on the
existing fail-closed guest event-tie check (0x8003f5d8). This experiment fails
qualification and is removed from the hotfix; all source, logs and final memory
are retained privately. No guest timing check was disabled.

A planned grouped-world/blur experiment was not built because its prerequisite
failed. Queue-slot lifetime and compositing still require independent validation.
The focused 1.2.1 preview contains the controls/exit-contact/scene-counter changes,
not GPU-copy or composite-queue experiments. Rendering resolution, 120 FPS
presentation in blur scenes, and the remaining audio events are still open.


## 2026-10-18 hotfix preview follow-up

The owner reports that Vela's selection scene still appears slow and lower
resolution in 1.2.1-beta.1, while boss controls now work. The supplied screenshot
shows output 27.9 FPS, scenes 25.9 FPS, 35.9 ms and a 76.3 ms maximum. This is
reported visual/counter evidence, not a newly qualified timing experiment.
The controls hotfix does not resolve this issue; it remains open for 1.3.

## 1.3 short boss baseline and composite candidate

After merging v1.2.1, a copied Vela save with its native introduction already
seen reaches actual Ichor combat (181). A muted neutral/health-mod capture at
120 FPS keeps all 1,499 measured game intervals at two VI, median 33.431 ms,
maximum 34.268 ms. Actual output averages 31.84 FPS, median 33.382 ms.
The renderer still replaces world sequences with the same-tick blur task.
This establishes an output problem independently of simulation slowdown.
No audio-underrun events occur in the retained short trace. An initial analysis
misread audio-queue's fifth field (device-playing) as an underrun count; that
interpretation is invalid. Longer-route audio qualification remains open.
Private evidence: vela-composite/boss-baseline-review.json.

An opt-in composite candidate retains the world workload and replays world
plus blur together for each output phase. It keeps scene history across the
effect and protects the retained queue slots. Unlike the unbuilt earlier
proposal, the world must match the blur destination: the source is the prior
screen. CPU-texture grouping and GPU-texture grouping have separate modes,
so cadence and image detail can be assessed independently. CPU shadow and
native writeback behavior remain part of required validation. Default mode
is unchanged; no candidate has passed native or visual checks yet.

The first composite build raised output to 119.65 FPS (and 358.96 at 360)
but FAILS image qualification: phases 1/2/3 repeat exactly. Group diagnostics
show every attempted pair remained a single workload. The assumption above
that the parent world matches the blur destination is incorrect: it must match
the sampled source. These figures demonstrate presentation frequency only.
The GPU-copy variant visibly restores detail but still repeats images.
Private evidence: composite-image-review.json and retained phase PNG/PPM files.

The next candidate corrects source matching and seeds every blur output from
the same pre-blend destination image. Recycled interpolation targets otherwise
supply unrelated blend history. Failed pairing falls back to one output instead
of counting repeated blur images as interpolated frames. All variants remain
opt-in pending actual-image, native timing and broader route validation.

### Longer 1.3 composite route: separate settings-I/O hitch

The corrected source-matched/seeded candidate completed ten native exit
transitions, the Ichor introduction and active moving/aiming/firing boss input.
The 262.8-second route is **not clean**: eight audio-underrun events follow a
66.220 ms boss update at VI 14612. host-profile-config records **40.682 ms**
inside the synchronous twelve-file controller settings reload, nested within
40.714 ms of host input. This is concrete blocking host work, not evidence that
the GPU composite itself required 66 ms. A separate four-VI update occurs at
the boss scene entry; two 43?45 ms wall gaps occur in room 119. All remain tracked.

Candidate remedy: read the same bounded per-port settings files on one worker,
publish immutable snapshots, and apply them on the game thread using existing
parsers and reset behavior. Initial settings are loaded before gameplay;
confirmed deletion still disables modern controls, while invalid or unreadable
files retain active settings. Runtime/control-change verification is pending.
Evidence: private vela-composite/long-route-review.json and
long-route-hitch-timeline.json. The Original-mode checks passed their bounded
30 FPS windows; the probe-mode pause fixture did not acknowledge its pause
request and was terminated by its own assertion. Do not count that as a pass.

Test-mode correction: the early direct/long fixtures enabled elapsed host time
in bounded probe mode, but did not enable normal Play's native spans, resident
math, collision traversal, native ROM sample source/completions, or audio
demand scheduling. Their renderer image evidence and measured synchronous
settings-I/O stall remain valid. Their audio underruns are **not proof of a
normal-Play audio regression**, and their timing figures must not be described
as release-equivalent qualification. The next paired route uses the actual
Play entry path with copied saves, recorded input, hidden/muted windows and
owned-window close at the bounded VI endpoint.

A remaining candidate limitation follows from the blend history: interpolating
only the newly rendered world while holding the older image constant produces
a discontinuity at source-frame boundaries. Native output is a blend of two
consecutive world images; both temporal inputs must progress between endpoints.
Private mode 4 tests a GPU interpolation of the two saved older images before
the unchanged native blur draw. Native endpoints and the authored blend factor
are retained. The shader is compiled at build time and its pipeline is created
at render-worker startup. This first diagnostic supports single-sample Windows
targets; other targets retain mode-3 behavior. It remains default-off and must
pass image and performance checks before promotion.

### Normal-Play qualification and evidence corrections

The paired 15,600-VI normal-Play routes before/after background controller
settings reads both completed ten native exits, Ichor's introduction and active
combat without audio underrun/overrun events. Every measured boss interval
advanced two VI. This bounds the result to those routes, not all campaign audio.
The earlier long probe route is retained but is not release-equivalent evidence.
Live settings enable/disable, invalid-file retention, deletion and restoration
also passed; see [PERF-006](controller-settings-io-hitch.md).

The two remaining room-119 gaps are now attributed to live-map geometry JSON
preparation, with independent command-file read stalls also observed.
See [PERF-007](live-map-export-hitch.md).

The first moving-image comparison crossed a four-VI gap: image capture itself
skipped an intermediate source scene. Its larger boundary difference cannot
establish ordinary-Play interpolation jitter. The corrected mode-four candidate
also seeds from the actual native framebuffer, bypassing recycled interpolation
target overrides, and restores the seed on every output phase. All blur modes
remain diagnostic/default-off pending full image and route qualification.

### Scoped compatibility checks after map optimization

The mode-four candidate passes the held shuriken CPU-reticle checks at 120 FPS
(last phase 3/4) and 360 FPS (last phase 11/12), with masks no older than two VI.
The released-aim fixture has no lingering recent overlay. All three report zero
unsupported guest accesses. These are bounded original-OS probe image/mask
checks, not normal-Play performance or full-campaign reticle acceptance.

A deterministic shadow fixture compares modes 0 and 4 in the same executable.
All twelve paired images are pixel-exact, and final logical RDRAM and renderer
snapshot hashes match. This verifies that the recognized-blur path leaves this
ordinary CPU-shadow scene unchanged. The probe's slower source cadence/audio
events must not be reported as normal-Play regressions or performance results:
both runs intentionally use fixed native probe accounting for image parity.

Private evidence: vela-composite/reticle-blur-scope/vi-reticle-regression.json
and shadow-blur-scope/shadow-pixels-comparison.json.

A 320x240 diagnostic capture avoids the high-resolution screenshot disturbance
and records source ticks 4000, 4002 and 4004, with distinct intermediate images.
The first mapping keyed only by scene present ID accidentally labelled every
phase as the final phase. The corrected mapping uses (present ID, phase);
retain both reports. Image continuity is separate from elapsed-time performance.


### Moving boss check at 360 FPS

The normal-Play moving Ichor route with the map/settings I/O optimizations and
mode-four blur candidate completes 7,202 VI, with zero audio underruns/overruns,
zero unsupported accesses and zero dropped diagnostic rows. Four measured boss
windows average 358.95-358.96 successful presents per second. Every game-update
interval in those windows advances two VI; the highest measured update is
34.716 ms. This is a 120-second bounded route, not campaign-wide qualification.

The consecutive low-resolution image samples show distinct phases for both
mode 3 and mode 4. In these separate moving runs, mean boundary image difference
falls from 7.55 to 3.18 intensity levels with history interpolation; median
within-update difference changes from 1.35 to 2.14. This supports improved
continuity but does not establish exact trajectory or pixel parity across runs.
The image capture is excluded from performance claims.

Private evidence: vela-composite/play-moving-blur-360,
small-blur-history-comparison.json and each continuity-review-v2.json.


Owner reaffirmed full-resolution visual fidelity as an explicit acceptance item. The original rescue drops to a visibly lower-detail image, so timing alone cannot qualify the remedy. Separate full-size captures will cover each affected rescue shot and compare scene detail, intended temporal blur, CPU shadows and overlays; screenshot overhead is excluded from performance claims.


### Native endpoint and resize checks

With fixed native probe timing, all three sampled full-game-frame endpoints
at VI 4001, 4003 and 4005 are pixel-exact between fixed and interpolated blur
history (modes 3 and 4). Final logical RDRAM hashes also match. This verifies
the added history interpolation preserves those endpoints; it does not compare
GPU-enhanced detail to the original 320x240 CPU-composited image.

A separate normal-Play moving boss route changes the hidden client from
1164x873 to 800x600, 1280x720 and 640x480. All three changes complete with
normal shutdown, no unsupported guest accesses and no audio underrun/overrun
events. Resizing itself is excluded from steady-state pacing acceptance.
Private evidence: blur-endpoint-equivalence.json and play-moving-blur-resize.


### Full-size rescue capture and remaining timing failure

Separate 1164x873 captures now cover shots 344, 380 and 345 with the old path
(mode 0) and GPU/history candidate (mode 4). Inspection of shot 344 shows
finer stair/cable and actor edges, with the same subtitles and 4:3 letterboxing.
Do not call separate wall-clock runs pixel-identical: shot phase and camera
progress can differ. Lighting, authored blur and the original-ROM reference
remain part of acceptance, not just apparent sharpness.

In shot 380, one old-path intermediate capture after a screenshot-induced
four-VI gap contains black floor/shadow polygons. The preceding old-path
endpoint and intermediate image are intact, and the inspected candidate images
are intact. This is retained as a capture/stall-stress finding, not proof that
ordinary Play displays the defect or that the general shadow problem is solved.
Exact phase identity matters: an intermediate image cannot be treated as the
native endpoint merely because it is the final file captured.

The 12,008-VI normal-Play rescue route has zero audio errors and completes
all six expected shots plus return to gameplay. Every measured same-shot
interval is two VI except transition-adjacent one-VI intervals and one
three-VI, 50.033 ms interval early in shot 344 (VI 3000). This fails the owner's
zero-miss target. The other five shot segments have no gaps above 42 ms.
The simultaneous count of world and blur tasks is not the game-update rate.

Current normal-Play opening controls at 120 and 360 FPS remain audio-clean,
but shot 325 has three three-VI updates at 120 and one at 360. The late updates
spend about 50 ms in update-work; no host-stage span above one millisecond
explains those events. The two existing exact-output shadow/cache leaf
optimizations are being tested for CPU headroom, with presentation and game
timing settings held constant. No zero-slowdown claim is made.

Private evidence: rescue-full-size-image-index.json, rescue-fidelity-plan.json,
rescue-village-wall-review.json, rescue-village-gap-attribution.json,
current-village and rescue-native-cutscene-route.


### Reference-route recovery and renderer compatibility

The first original-ROM rescue reference attempt stopped in the Brig before
the cutscene: a straight-line input planner stalled against the room layout,
about 460 units from the selected exit. This is a failed reference-navigation
fixture, not evidence of a game regression or visual parity. Its observations
and checkpoint history are retained. A corridor-waypoint retry uses ordinary
native input and the same copied save; original save data and game code remain
untouched. Evidence: original-rescue-visual and original-rescue-waypoint-visual.

The renderer shell and F3DDKR texture checks pass with blur diagnostic modes
0 and 4. Earlier interpolation, semantic-presentation and VI-presentation
checks also pass. These establish bounded component compatibility, not full
campaign fidelity or performance acceptance.

The exact-output shadow/cache leaves improve CPU headroom but do not yet
qualify the route. At 120 FPS the opening's shot 325 improves from three late
updates to one, with median active work about 22.19 to 20.96 ms. The remaining
entry update takes 38.88 ms of active work and yields a 51.29 ms game-update
interval; graphics submissions account for about 21.10 ms, including five
small shadow passes. At 360 FPS one late shot-325 interval remains and another
appears in shot 323. The rescue's former shot-344 miss clears, but one 49.91 ms
interval remains in shot 380. All four leaf-enabled routes report zero audio
underruns/overruns. This is partial improvement; the leaves remain opt-in.
A focused submission/wait profile is being used to attribute the remaining
cost before selecting another change.

Private evidence: native-leaf-wall-review.json, current-village-leafs,
rescue-native-leafs and current-village-entry-profile. Full-size screenshots
are fidelity evidence only; their readback overhead excludes them from
performance acceptance.


### Original-ROM image review

The original-ROM reference now completes all six rescue shots and returns to
the Brig. Its 320x240 screenshots are compared visually with the separate
1164x873 candidate captures for shots 344, 380 and 345. The sampled ship/floor
color treatment, scene layout, subtitles and 4:3 letterboxing remain recognizable
and consistent with the original. The candidate retains finer stairs, cables,
character outlines and ship edges; the authored soft star background and
temporal effect have not simply been removed. No obvious new lighting or layout
defect is visible in these inspected stills. Different shot phase, emulator
rendering and output scale prevent a pixel-parity claim; temporal motion and
the owner's full visual pass remain necessary.

Reference scope is deliberately limited. The corridor-waypoint retry reached
the first waypoint, then the cached-interpreter emulator stopped with
"two events of type 0x8 in interrupt queue" during lookahead/checkpoint work.
A subsequent controlled-entry fixture initially wrote the contact at the actor
rather than the actor's control structure and failed to enter the scene; it
produced no accepted reference images. The corrected fixture validates the
native contact-consumer instructions, sets the player position and that control
structure's exit contact/status once, then lets the unmodified original game
run the entire cutscene. It does not patch rendering, AI, cutscene scripts or
timing. This establishes a rendering reference, not navigation/progression
parity. All failed fixture evidence and original saves are preserved.

Private evidence: original-rescue-waypoint-visual, original-rescue-contact-visual,
original-rescue-contact-v2-visual and rescue-full-size-image-index.json.


### Additional fidelity fixture limits

The Original-rate capture attempt reached rescue shot 344 but recorded no
sequence images: Original mode does not publish the interpolation scene tick
used by that screenshot trigger. This is a capture limitation, not a rendering
failure. A swapchain capture using the existing ordinary screenshot path is
being substituted; capture runs remain excluded from performance acceptance.

Clearing only Vela's acquired flag in a copied boss save produced an inconsistent
selection fixture that stopped advancing after entering level 127. It produced
no accepted capsule images. No owner save was changed, and this is not labeled
a runtime regression. The owner's actual hotfix session and initial save have
now been located for state-based reproduction. Failed evidence remains in
rescue-original-rate-shot344-mode0 and vela-locked-capsule-full-size.


### Rescue queue-capacity lead

The latest native 360 FPS rescue controls retain six late shot-344 updates
without texture reuse and four with decoded-only reuse; other rescue shots
are clean at that rate. A 120 FPS control has one 50.203 ms interval in shot
345 despite advancing only two VI. All three normal-Play runs remain audio-clean.
Texture reuse alone does not qualify zero-miss acceptance.

The focused shot-344 profile reproduces four misses. Each missed update's
623-command blur submission waits 10.47-12.50 ms in queue advancement while
its GPU-fence wait is about 0.16-0.17 ms. The preceding deferred world workload
waits roughly 10.94-12.71 ms for a present ID. Those are overlapping producer/
consumer waits, not additive costs. This is stronger evidence for scheduling/
ownership pressure than for texture allocation as the remaining rescue cause.

The pinned queue contains four workloads. A completed blur frame retains both
its world and blur task; the next pair plus the producer's reserved next slot
can exhaust that ring. A private build option now tests six slots while keeping
every existing cursor barrier, resource fence, present dependency and workload
ordering rule. Four remains the default. A complete build-private RT64 source
view supplies the same class layout to every consumer; the pinned dependency
checkout is not modified. Texture-cache retirement ages continue to derive from
the actual queue capacity. Build, state/image, cadence and visual checks are
pending; increased capacity is a candidate, not a declared fix.

Evidence: rescue-resource-comparison-wall-review.json,
rescue344-submission-profile/attribution.json and queue-wait-correlation.json.


### Original-rate and owner-selection fidelity checks

Original-rate swapchain captures now cover rescue shots 344 and 345 with the
old path and GPU/history candidate. The candidate retains finer stairs, cables
and ship edges while keeping the subtitles, 4:3 letterboxing and authored soft
star background. Original mode has interpolation disabled, so the detail gain
does not depend on generating extra frames. These separate wall-clock images
are visual evidence, not exact phase/pixel or performance parity.

The owner capsule screenshot's file-creation time was not its exact gameplay
time. Replaying to that timestamp reached Vela outdoors in level 43; that image
did not validate the closed capsule. Earlier native scene-tick captures now
reproduce the selection room at VI 1400 and the closed capsule at VI 1600.
The inspected old-path and candidate stills retain the same geometry edges,
lighting/fog, character and beam content. This selection state did not show the
rescue's detail improvement; do not describe it as an independently fixed
capsule-resolution bug. Matching image comparisons are retained separately.
Owner motion/visual confirmation remains pending.

Two live-file collection attempts missed their intended early images because
the ordinary capture path refreshes an in-memory frame periodically but writes
its PPM only during shutdown. Buffered gameplay observations also cannot be
treated as a live screenshot clock. The successful captures use the existing
bounded renderer sequence trigger at explicit native scene ticks. Those failed
collection attempts and their final images are retained, not counted as runtime
regressions or successful capsule reproductions.

Private evidence: rescue-original-swapchain-index.json,
owner-selection-scene-phases/index.json and pixel-review.json. Failed/partial
collectors: owner-capsule-visual-replay, owner-capsule-final-anchor-comparison,
owner-selection-transition-images and owner-selection-wall-window.

### Six-slot qualification and remaining entry costs

The six-slot private build passes the 12-image opening shadow comparison:
all pixels and guest/renderer/save hashes match the four-slot control. Native
rescue Play at 120 FPS has no late active cutscene updates, but retains two
47-53 ms Brig-entry intervals. At 360 FPS the repeated mid-shot-344 stalls
disappear in this run; one 51.252 ms shot-entry update and three Brig-entry
misses remain. Both runs have zero audio underruns/overruns, unsupported
accesses or dropped diagnostic rows. Scene-loading gaps remain recorded
separately. This is not zero-miss acceptance or a release-ready default.

The focused six-slot profile reduces queue-advance waits to a maximum of
0.0173 ms in the measured window. Remaining entry stalls have different costs:
one Brig submission waits 14.3652 ms for texture upload, another waits
10.7653 ms for framebuffer upload; the shot-344 entry spends 14.071 ms in
world submission plus blur and shadow work. These are overlapping nested
measurements, not independent costs to sum.

The blur-submit-to-first-display median for shot 344 rises from 10.240 to
16.545 ms; shot 345 changes from 11.6225 to 11.805 ms. This proxy starts later
than input collection and cannot establish input latency by itself. A trace
clock-origin record now allows gameplay and renderer timestamps to be joined
directly instead of treating file-write time as event time.

A moving Ichor image comparison retains identical game/renderer/save state,
but fails strict pixel equality in all 12 images. Differences are confined to
the HUD's animated blue background, bounding box (83,61)-(270,248) in the first
1164x873 image; the world and character pixels are unchanged. Upstream shader
noise depends on rendered-frame count, so a repeated four-slot control is
being collected before classifying the difference. No mask or relaxed
threshold has converted the failed strict comparison into a pass.

Evidence: queue6-shadow-parity/proof.json, queue6-native-rescue-wall-review.json,
queue6-display-age-comparison.json, rescue-queue6-entry-profile/attribution.json,
queue6-blur-motion-proof.json and queue6-image-difference/review.json.

The repeated four-slot control reproduces all 12 images exactly. The six-slot
HUD difference therefore cannot be dismissed as run-to-run nondeterminism.
The upstream raster shader seeds combiner noise from rendered frame count
(RasterPS.hlsl, lines 65/181); changed scheduling can alter its phase. This is
a source-supported explanation, not a fixed-seed proof. Strict full-image
equality remains failed; inspected world/character pixels match without changes.

The renderer's so-called shader uploader is a buffer-copy worker, not the
shader compiler. Additional opt-in worker profiling now separates resource
growth, submission/lock time, mapped buffer copying and completion waits.
It retains all original operations and synchronization. No optimization or
performance acceptance is implied by adding diagnostics.

### Shared-clock latency comparison

The repeated normal-Play four/six-slot comparison now uses a single monotonic
clock origin. From the preceding completed native update to first display,
shot 344's median is 19.258 ms with four slots and 26.7235 ms with six.
Shot 345 is 16.263 versus 17.061 ms. The roughly 7.5 ms increase in the busy
ship shot is not only an artifact of choosing blur-submit as the starting
timestamp. It remains a software-stage proxy, not physical input-to-photon
latency; the native update trace records completion, not entry.

The private six-slot candidate therefore trades recurring in-shot misses for
additional display delay and still leaves entry misses. It is not promoted.
The buffer-worker profile build passes the renderer shell and F3DDKR texture
checks; the clock-origin and recorded-clock mismatch component checks also pass.
Further resource optimization and an owner motion/fidelity pass remain open.

Evidence: queue-capacity-clock-correlation-reviewed.json (corrected timestamp
description), queue6-buffer-profile-build.json and queue4-repeat-noise-control.json.

The first buffer-profile route completed but its nested script rewrite also
changed the profiling insertion needle, so it collected neither buffer-worker
nor detailed submission rows. That run is preserved as a failed diagnostic
fixture, not worker attribution or a like-for-like optimization comparison.
The recovery expands the route first, then sets its environment; it explicitly
requires buffer-copy/submit/wait, texture-stage, submit-sync and function-profile
rows before accepting the capture. Evidence: rescue-queue6-buffer-profile
(failed capture) and rescue-queue6-buffer-pool2-profile (recovered capture).

### Upload mapping lead

The valid raw+decoded-resource profile has one 50.829 ms Brig-entry update.
A 476,928-byte buffer upload occupies 13.3582 ms while using only 246,620
thread cycles; the caller waits 13.1737 ms on the same uploader. This localizes
the wait inside map/copy/unmap, not merely the worker wakeup. The next build
splits those stages. Raw+decoded reuse clears shot 344 in this instrumented
run, but that is not a performance acceptance run.

Pinned upload code maps write-only staging buffers with a null read range.
Microsoft specifies that null means the CPU may read the entire resource,
while an empty range declares no CPU reads. A default-off candidate supplies
the empty range at the verified buffer/texture upload sites; it changes no
readback mapping, copy content, barrier, fence, queue or resource lifetime.
This is a plausible driver/cache optimization, not a proven stall cause yet.

References:
- https://learn.microsoft.com/en-us/windows/win32/api/d3d12/nf-d3d12-id3d12resource-map
- https://learn.microsoft.com/en-us/windows/win32/direct3d12/uploading-resources

The private capacity overlay also stops rewriting its unchanged header on
every configure, avoiding unrelated recompilation without changing its contents.
Evidence: rescue-queue6-buffer-pool1-profile/worker-attribution.json.

### Persistent mapping candidate

The split profile identifies Map itself as the delayed operation: the
write-only-range run spends 11.6183 ms mapping a 476,928-byte upload, with
only 125,780 thread cycles. The whole copy is 11.6668 ms and the game waits
11.5389 ms. Explicit no-read ranges alone do not remove the entry hitch.

A separate private D3D12 candidate maps UPLOAD buffers once after successful
creation, returns that stable pointer for later map calls, and releases the
mapping at resource destruction. Readback/default buffers retain their original
behavior. The pointer is initialized before publication and then immutable;
all existing copies, worker waits, GPU fences and resource ownership remain.
A failed initial map falls back to the original path. Both build support and
runtime activation are off by default. The complete private dependency view
keeps class layout consistent for every consumer, leaving the pin pristine.

Microsoft documents persistent mapping for CPU-accessible heaps provided writes
complete before GPU execution. This candidate follows that existing ordering;
it does not establish a performance fix until measured. Constructor/resource
growth cost stays in the profile, so moving a stall earlier is not a success.
Evidence: rescue-upload-map0-profile and rescue-upload-map1-profile.

### Qualification fixture corrections

The first persistent-map configure failed because its option declaration was
inserted inside the preceding multiline cache declaration. No candidate binary
or replay was produced. The declaration is corrected; the failed build log is
preserved separately from the recovery build.

The write-only-map moving-scene comparison produced no common capture ticks:
the wall-clock file-driven exit warp reached the boss at different native
updates, so game state already differed. This is an invalid equivalence
fixture, not a pixel-regression verdict. Earlier successful comparisons that
actually matched state remain useful, but the asynchronous route cannot be
assumed deterministic. The recovery adds an explicit probe-only Ichor warp at
a selected VI, using the existing validated exit-warp path; normal Play rejects
that fixture option. A separate default-off fixed raster-noise fixture controls
the shader seed for exact-image tests without changing ordinary HUD noise.
Both fixtures must be labeled in results; neither qualifies gameplay timing.

Evidence: steps 542 (unmatched route), 545 (configure failure), and their retained
logs. No failed attempt has been overwritten or reclassified as a pass.

The persistent-mapping build also exposed a composition error: the existing
readback compatibility patch rejected the intentionally transformed private
Plume source. The original pinned source still passes its hash check; the
readback patch now additionally accepts the exact digest exported by that
audited transformation, retaining its own replacement-site check. The failed
configuration and dependent skipped tests are preserved; they ran no game.

### Visual fidelity remains an acceptance requirement

The owner reiterated that the Vela rescue appeared to drop resolution. The
ship-shot comparison was reviewed alongside the original EmuHawk capture:
the candidate retains the scene, colors/effects, text and 4:3 letterboxing,
with clearer cables, stairs and subtitle edges. These separately timed stills
support visual review, not exact-pixel or motion equivalence. The closed
selection capsule remains a separate unresolved report: its ten matched
old/candidate images are identical, so no independent resolution remedy has
been demonstrated there. Final owner motion review is still required.

The upload-mapping build now passes the renderer shell and texture checks.
The remaining configuration mismatch was Windows CRLF output versus the
normalized generated-source digest. Content is verified after normalization
before exporting the actual file digest to the readback compatibility patch;
no source check was removed. Earlier build failures remain preserved.
Performance and mapping image/state comparisons are pending separately.

The persistent-map normal-Play profile retains a 49.173 ms Brig update.
Mapping time moves into resource growth: buffer-resources takes 15.4606 ms,
while the later copy wait is small. It is not a hitch fix. Both off/on runs
have zero audio underruns/overruns, unsupported accesses and dropped rows.
Per-buffer growth/allocation profiling is added to identify the capacity
change before choosing a bounded reservation or reuse strategy. Evidence:
rescue-persistent-map0-profile and rescue-persistent-map1-profile.

The first deterministic Ichor image fixture correctly stopped before warping:
its destination predicate confused resolved level 181 with native transition
code 0xFFB5. Captured room-19 exits show a unique condition-23/0xFFB5 entry;
the fixture now checks that encoded value and still uses the original warp
path. This was a test setup error; no image/state equivalence is claimed from
the failed capture. Normal Play cannot enable this fixture.

### Bounded typed reservation candidate

Per-buffer profiling locates 13.3052 ms in creating/mapping the RDP-parameter
upload buffer, growing from 442,368 bytes to 711,680 bytes for 474,368 bytes
of data. A separate default-off candidate reserves 1 MiB for this explicitly
identified buffer when each workload is first initialized/uploaded. Other
buffers retain their original growth policy; uploads still copy only the
valid range, with the same views, fences and GPU commands. A complete private
dependency view preserves the extended BufferPair layout across consumers.
The reservation adds at most 2 MiB per workload (upload plus default storage)
before accounting for existing storage. Startup cost and memory are tradeoffs;
no measured hitch-removal claim is made yet. Evidence:
rescue-buffer-growth-map1-profile/buffer-growth-attribution.json.

A separate 50.844 ms Brig-entry update spends 7.3084 ms in texture staging
buffer/descriptor growth for a 133-texture batch. Another default-off switch
prepares 256 reusable 4 KiB staging buffers and decode descriptors on the
first texture batch (1 MiB logical staging capacity plus descriptor storage).
It does not load/decode extra textures, change actual batch sizes, or change
fences, barriers, texture content or replacement lookup. Larger batches retain
normal growth. Startup cost is intentional and must remain in the capture;
normal Play/image checks are pending. This switch is separate from the typed
RDP reservation so their costs can be distinguished.

A five-slot private ring is also admitted for qualification. Four slots leave
three usable slots, insufficient for two retained old composite workloads and
two new ones. Five is the smallest ring holding those four without crossing
the protected boundary. It retains every existing barrier/fence and may avoid
the extra backlog allowed by six; reduced display delay is a hypothesis until
measured. The source default remains four. No old failure or latency increase
is reclassified as accepted.

### Mapping/reservation image result and remaining allocation cost

The corrected fixed-VI Ichor fixture passes: all 16 full-size paired images
are pixel-identical with persistent mapping and the typed reservation off/on;
guest RAM, renderer RAM and save hashes match. This uses a fixed raster-noise
seed and fixed-clock probe, so it establishes scoped image/state equivalence,
not normal-Play audio/performance or ordinary noise phase acceptance.
Evidence: reserved-map-pixel-proof.json.

The typed reservation avoids the identified RDP growth but does not qualify
the route: another 206,080-byte upload allocation takes 16.7896 ms, leaving a
49.517 ms Brig-entry update. General bounded upload-storage reuse is the next
candidate; changing only one buffer is insufficient. The first original-ROM
selection captures show the same room/character/effects, but automated confirm
timing did not match the owner capsule closeup. They are retained as partial
reference coverage, not a closed-capsule fidelity verdict.

### Reusing staging independently of destination growth

The broader candidate reserves CPU upload storage for the explicitly listed
DrawBuffers: 512 KiB each, and 1 MiB for RDP parameters, only when first used.
GPU destination buffers retain their original 1.5x growth policy and sizes.
An already large enough staging buffer is retained when its destination grows;
the original code still reuploads the full valid range after destination
recreation. This avoids allocating/mapping another staging resource for each
small increase without enlarging GPU destination storage. It changes no copy
range, descriptor, fence or workload ownership. The static floor is bounded
at 15.5 MiB per fully used DrawBuffers set; actual used sets and resource
counts must be measured. Data exceeding the floor still uses ordinary growth.
With the option off, every growth still recreates staging as before. The
candidate remains private/default-off pending state/image and native Play
checks, including startup cost, memory and late-entry intervals.

An opt-in target-size trace records native framebuffer width, actual GPU
render-target width/height, sample count and composite workload position at
native interpolation endpoints. This supplies resolution evidence for the
Vela capsule independently of authored texture softness or beam/fog effects.
It changes no target, image, resolution policy or gameplay state and is off
by default. Screenshots and this diagnostic are excluded from pacing acceptance.

### Reusable staging: scoped native-Play result

The reusable staging candidate removes the 15-17 ms allocation/map stall from
the profiled resource stage: buffer-resources is 0.414 ms at the late Brig
update. The heavily instrumented run still records one 52.398 ms update; native
work, profiling and map export remain in that observation. It is preserved as
a miss, not silently excluded or relabeled as a clean performance result.

Two subsequent normal-Play rescue runs, each 10,500 VI, pass the active-scene
cadence checks at 120 FPS/VSync and 360 FPS/no VSync. All 2,362 Brig updates in
each run use two VI; maxima are 35.878 and 35.725 ms. Shot 344 has 311 updates
per run, all two VI, maximum 35.547 ms. The other rescue shots remain clean
apart from expected one-VI boundaries. Both runs have zero audio underruns,
overruns, unsupported accesses and dropped log records. Scene-change loading
gaps remain recorded separately; this is not a claim of zero stalls across
loads or acceptance of the whole campaign.

The reusable-upload off/on fixture also has nine exact paired images (one
complete eight-phase cycle plus the next phase), with matching guest RAM,
renderer RAM and save hashes. It uses fixed VI warp, fixed raster-noise seed
and a fixed-clock probe; it does not qualify normal timing or ordinary shader
noise. A separate five/six-slot same-code comparison passes sixteen paired
images and state hashes. Five-slot display delay still needs its own review.

Evidence: reusable-upload-native-rescue-wall-review.json;
rescue-reusable-upload-native-120 and -360; reusable-upload-pixel-proof.json;
five-six-slot-pixel-proof.json; rescue-reusable-upload1-profile.
Measured runtime SHA-256:
68562b8d45f374478f0c04869e72bcac7fbe90b4d8705a3f5cdb85c4252ff83d.

### Capsule resolution observation

The actual owner's Vela-selection route has 47 target-size rows per mode
around VI 1550-1650. Both the original blur path and candidate render the
320-wide guest framebuffer into a 1280x960, one-sample GPU target. Thus this
particular capsule interval does not drop its geometry to native resolution.
The reported soft appearance remains subject to effects/texture and motion
review; this finding is not an independent visual fix or a dismissal of the
owner's report. The ten previously matched old/candidate capsule images were
identical. Original-ROM references have not yet matched the closed capsule
phase: repeated confirmation advances too quickly, and a two-frame one-shot
confirmation failed to leave selection. That failed fixture remains preserved.

Evidence: owner-capsule-target-dimensions/target-dimension-review.json;
original-owner-selection-single-confirm; owner-selection-scene-phases.
Target-diagnostic runtime:
70e559e31ab4971edfaa0e1e9319f3ed296c8a201cfb84f2495063e2835789a1.
The diagnostic is off during pacing qualification. All candidates remain
unreleased, and the owner has not yet reviewed this combined build.

### Explicit owner-preview build policy

A default-off CMake option selects the combined reviewed policy for normal
Play in a private Windows owner-preview executable. Configure requires the
five-slot queue, persistent mapping/reservation support and native Play timing.
The executable fills only missing optimization switches after command-line
validation; explicit comparison overrides win. Probes do not automatically
opt in. No replay, fixed noise, warp, health mod, screenshot, function profiler
or other fixture switch is selected. Launcher environment sanitization remains
unchanged. The build identity includes V13PerformancePreview so the owner
capture can be distinguished from ordinary/default builds. This is packaging
for live qualification, not promotion to the released defaults.

The first no-feature-environment preview capture completed normally with clean
audio/access/drop counters. Its reviewer then failed because it searched the
short support event log for the binary build identity. The corrected review
reuses that capture, checks the embedded preview identity, confirms all nine
feature selectors were absent from the launch environment, and requires native
helper events plus composite-render events. The failed assertion remains
preserved; no game failure or successful rerun is invented. Evidence:
owner-preview-policy-proof.json and preview-policy-rescue-wall-review.json.

### Normal-launcher policy result prevents promotion

The explicit preview policy does activate without inherited candidate switches,
but its normal-Play review finds two isolated three-VI updates: 53.252 ms in
the Brig and 50.805 ms in shot 380. Audio and access counters remain clean.
These misses prevent a zero-dip acceptance claim or owner-preview handoff.
Earlier clean runs remain valid scoped observations; they do not erase this
counterexample. Attribution now compares the saved update/submit/resource
events before choosing another change. The build differs from the earlier
frozen runtime, so neither a regression cause nor an external-load explanation
is assumed.

The separate target-dimension capture confirms 1280x960, one-sample GPU
targets throughout rescue shots 378, 379, 344, 380 and 345. This verifies target
resolution, not exact original-ROM phases or final visual acceptance.
Evidence: preview-policy-missed-update-attribution.json and
rescue-target-dimension-review.json.

The reduced resource-profile attempt 625 rejected startup (exit 3): GPU_COSTS
requires FUNCTION_PROFILE by design. No game measurement was produced. Its
dependent reviewer 626 also failed for the missing interpolation log. Corrected
attempt 627 removes GPU_COSTS and retains the independent buffer/texture stage
timers, avoiding per-function overhead. Both failures remain preserved.

Visual review also includes the retained shot-380 mode-4 frame 2236-0.png and
mode-0 frame 2272-0.png from rescue-full-size-shot380-mode{4,0}/frames.
Both show sharp geometric silhouettes, letterboxing, readable subtitles and
low-detail source textures. These are nearby but different animation phases,
so visual similarity is not an exact image-parity or original-game proof.
No additional resolution fix is inferred from these two images.

## Owner-led blur review, 2026-10-18

The owner changed the workflow: prioritize blur, deliver proposed fixes, and
leave visual/gameplay verification to the owner. Automated gameplay runs stop.
A private 1.3.0-beta.2 launcher uses the existing preview-policy runtime
a9654ea8d161b6906387eb2026ce5ecdb2c2a0b590745bc384a38d9ffa6133e6,
a separate copy of the latest owner profile, and SSD runtime/ROM/profile storage.
This is a baseline for the owner to save immediately before rescuing Vela.
It is not a newly verified blur fix, release package, or zero-stall claim.
Future candidates must preserve that review profile/save. No autoplay, replay,
heavy capture, frame logging or game test is enabled. User visual confirmation
is pending. Private delivery receipt: owner-blur-review-delivery.json.

The breadcrumb-stage diagnostic completed before this workflow change and did
not reproduce the earlier long pauses: no measured breadcrumb call exceeded
1 ms in that run. Earlier pauses coincided with breadcrumb writes, but causation
is still unconfirmed. The existing synchronous support-file code is a follow-up,
not a proven explanation for every missed update.

### Candidate: bind the blur pass to its source world submission

A retained Unlimited/VSync capture records world VI 3030 followed by blur VI
3031; the previous pairing rule requires equal submission VI and falls back to
a one-workload effect with source rate zero. That is a concrete loss of
interpolation ownership, independent of the final target's dimensions. It
does not prove that every reported soft image has the same cause.

The new candidate gives each interpreted full synchronization an identity.
Only a world pass requesting blur, with one unambiguous 320-wide RGBA16 color
source, offers that identity to the immediately following synchronization.
The recognized blur list must name that source. Its presentation tick/rate
then belong to the source world, while the native task retains its actual
submission VI. Queue pairing additionally requires the exact offered identity,
adjacent workload slot, matching source and retained world geometry. Any
intervening or unrecognized work consumes the offer. No game clock, shader,
blur strength, image size, copy range or GPU fence is changed.

This is a new source candidate, not yet built or owner-verified. The running
owner preview a9654ea8 remains unchanged. Per the owner's instruction, no
automated gameplay or visual verification is run. Evidence prompting the change:
preview-policy-missed-update-attribution.json, Unlimited/VSync shot 344.

The source-workload binding candidate compiles successfully. Runtime SHA-256:
01f70f7e591f5c1bd4f4b4776b9580a079f775847fbc25fd7235b8865248711d. No gameplay or visual tests were run; owner review is pending.
The currently open baseline launcher/profile were not replaced.

### Owner baseline visual result, 2026-10-18

The owner reports that the rescue cutscene looked mostly good in the delivered
a9654ea8... preview, with a possible single lower-resolution frame and blur when
the ship flies past at the end. This is partial live improvement, not a clean
pass: both residual symptoms remain open. The prisoner glass is stable; the
breakable glass in the preceding room is a separate defect (RENDER-012).
The source-workload pairing runtime 01f70f7e... had compiled but was not yet
delivered during this review, so the observation cannot validate that change.
Do not assume flyby blur is either an authored effect or a regression without
the owner comparison/original-reference evidence.

The owner confirmed the game closed and the pre-rescue save ready. The existing
desktop Vela Blur Review shortcut now selects source-workload pairing candidate
01f70f7e591f5c1bd4f4b4776b9580a079f775847fbc25fd7235b8865248711d.
Owner profile data/settings were backed up privately and save bytes preserved.
No automatic gameplay was run. This candidate does not contain a glass fix.
Private receipt: owner-blur-pairing-delivery.json. Live result pending.

### Owner identifies three specific soft shots

The owner reports the softness is concentrated in three specific cutscene shots
and supplied the wide docked-ship view with the subtitle "Currently docked at
Ichor Military Base." The other two shots are not yet individually identified.
This follows delivery of the source-workload pairing candidate; no clean
resolution pass is inferred. Screenshot preserved privately as
owner-ichor-docked-soft-shot-20261018.png with a SHA-256 receipt.

Existing geometry/display-list evidence describes real-time rendered rescue
shots and a native framebuffer blur effect, not prerecorded video. The recognized
blur operation samples a 320x240 RGBA16 image in 60 strips. Current candidate
retains high-resolution GPU copies, but remaining softness at these shots must
still be attributed; a large output target or the authored presence of blur is
not proof of high-detail input or correct effect history. The user continues
visual verification; no new game replay/capture was launched.

The owner identifies all three residual soft shots: (1) the first shot of many
drones boarding the ship, (2) the later boarding shot with many drones, and
(3) the large red ship's final flyby directly over the camera. The screenshot
above illustrates the boarding sequence. These exact shots are the next visual
acceptance targets. Do not substitute Vela's capsule or prisoner glass for them.

### Private pre-blend comparison candidate

Add explicit opt-in mode 5 / JFG_V13_BLUR_SOURCE_REVIEW, default off and requiring
the private preview policy. For a proven paired world/blur workload with matching
GPU texture sizes/formats and single-sample targets, display the freshly rendered
source in place of the blend result. This deliberately changes the visual effect
for diagnosis; it is not a fidelity-preserving remedy or a proposed release
default. It does not skip the native task or GPU work and is not a performance
measurement. No sharpening, upscaling inference or texture replacement is added.
The owner will compare the two crowded boarding shots and overhead red-ship
flyby. Clear detail here would isolate the loss to the blend/history path;
continued softness would direct work earlier in rendering/sampling.
Compilation and owner result pending. No agent game run authorized/performed.

The private source-only comparison compiles and is packaged separately as
JFG - Blur Source Comparison, using a copy of the backed-up pre-rescue save.
SHA-256: 7f88e30c9970c670c3d5faef47befb174f661934d582809b245be35fd0401d46. It also includes the intact-glass identity
candidate, unrelated to the three ship shots. The normal blur preview remains
available. No gameplay tests were run; owner visual result is pending.

### Owner source-only comparison result and actor-log follow-up

The owner reports no visible difference from the source-only comparison. Treat
this as a negative visual result, not proof that the blur is innocent: the
diagnostic copy's actual execution still needs confirmation. The owner asks
specifically for actors in the game logging and expects roughly 30, not an
estimate from the screenshot. Historical actor lists and update-count records
were extracted to private rescue-logged-actor-review.json; latest owner preview
did not enable full actor-change logging. No new gameplay was launched.

### Original-rate owner result and v1.1 baseline

Owner reports the same three shots still look low resolution at 30 FPS.
This points to a path shared with Original mode; it does not prove a specific
sampling/blend cause. A newly started logged Original + VSync session confirms
mode=original, target=0, vsync=1 in its runtime header; the report may refer
to the preceding unlogged Original comparison, so do not claim matched shot
telemetry from that header alone. The separate VSync report remains open.

At the owner's request, retrieved the unchanged official v1.1.0 Windows
release for a historical comparison. Archive and all inventory file hashes
were checked. No game was launched or visually tested by the agent. Preparing
a separate copy of the pre-rescue save; v1.1 behavior is not yet verified.
Private receipts: v110-official-release-verified.json and
owner-original-vsync-delivery.json.

The official v1.1.0 baseline is prepared as JFG - v1.1.0 Comparison, using a
separate pre-rescue save and compatible v1.1 controller/audio/experimental
settings. All 54 packaged files match the release inventory; the read-only
frontend protocol query returns jfg-frontend-1. No gameplay was executed.
Runtime SHA-256: fa6e0ec8068a18ae23eaa24eb1a5cb66bbbe4d3a0b6197adda45ff6109a1cd80.
This is the unmodified historical release, including its older controls.
Owner comparison remains pending; this is not verification of current-PC
gameplay or a claim that the blur is absent in v1.1.

Owner explicitly clarifies: **30 FPS motion is correct; all three shots are
still blurry.** This separates the residual visual defect from the apparent
Original/VSync problem. The owner closed the game; the next comparison is
the isolated unmodified v1.1.0 release. No owner v1.1 visual result yet.

The first owner v1.1 comparison could not launch. Its copied keyboard profile
enabled experimental controls before startup, reproducing the known
[NATIVE-002](github-mouse-look-startup.md) trigger (ROM-ready then access
violation). That isolated startup setting is now disabled; renderer and save
are unchanged. Owner retry is pending. This failed launch supplies no v1.1
visual evidence about blur.

### Owner v1.1 comparison result

After the historical keyboard-startup workaround, the owner completes the
comparison and reports that **our current version is sharper than v1.1**.
This is a relative owner observation, not exact-pixel equivalence or proof that
the current three-shot softness is correct. It weakens a new high-refresh
regression explanation, especially given that Original mode also looks soft.
A shared renderer problem and the native effect/source texture limits remain
possible. Before treating the negative source-only experiment as evidence,
confirm whether its guarded copy executed for those shots; it can fall back
silently when pairing or target checks fail.

Private evidence: owner-v110-sharpness-result.json and the retained
v110-owner-successful-comparison support report. No automated gameplay,
screenshots or visual verification was performed.

### Source-only diagnostic execution evidence

Add mode-5-only bounded numeric evidence: recognized native blur passes,
world/blur pairing, source-copy success or exact rejection flags, source and
destination GPU dimensions, GPU tile-copy usage and final presented target
dimensions. Rows stay in memory while playing and are written under the
isolated profile's performance directory after renderer workers join.
Normal mode 4 does not collect the audit. No screenshots, gameplay replay,
pixel readback or per-frame disk writes are added. The copy's eligibility and
rendering behavior remain the same as the prior comparison. Build and owner
review are pending; this instrumentation is not a blur fix.

The first audit build failed for a missing explicit string header; the failed
build log is retained. After adding that include the candidate compiles.
Runtime SHA-256: 693bf257d5dc0e1f697fa6e044b52d0f136a78e718f85646c69154bd89d68938. No gameplay was run; owner review pending.

The audited mode-5 comparison is packaged as JFG - Blur Source Audit at
120 FPS/VSync, muted, counter enabled, copied pre-rescue save. Runtime SHA-256:
693bf257d5dc0e1f697fa6e044b52d0f136a78e718f85646c69154bd89d68938. Logs use the private evidence volume; the bounded
source audit writes on game close. Package/protocol checks pass. Owner live
verification pending; no agent gameplay or visual checks were performed.

### First audit capture failed to persist its data

Owner reports the same blur after the audited comparison. The exact expected
binary launches and exits cleanly, and the frame CSV finishes without dropped
rows. However, no source-audit CSV was saved: the collector was flushed only
from the renderer destructor, while normal native Play explicitly flushes
diagnostics then calls std::_Exit. That bypasses destructors. This is an
instrumentation defect, not evidence that the source copy did or did not run.
The owner pass cannot be cited as proof of source-copy execution.

Correction: attach the collector to the existing explicit successful-exit
flushes; reject further rows and complete in-flight append operations under
a short mutex before writing, with no disk I/O while that mutex is held.
Create a startup marker before rendering starts so collection availability is
visible before another owner route. A standalone no-game fixture will check
concurrent append, explicit finish and immediate process exit before delivery.
Evidence: blur-source-audit-missing-exit.json and owner-blur-audit-first-support.
No image/copy behavior changes. Owner result remains negative and inconclusive
for attribution; no new gameplay or visual testing by the agent.

The standalone no-game audit fixture passes: startup marker survives immediate
exit, 6 concurrent producers preserve all 6,000 rows, explicit finish safely
closes concurrent append, late rows are rejected, and overflow is bounded to
65,536 saved rows with the exact dropped count. Every child calls std::_Exit.
Evidence: audit-exit-fixture/result.json. This validates collector persistence,
not game rendering or the copy path; owner gameplay remains separate.

The explicit-exit audit correction compiles. Runtime SHA-256:
bf34694c847c4af69449cd7f85ced92ebcc90f2952e7f8d982f4f88dd5ee947b. Collector fixture passes; game/copy execution still
requires owner verification. No new gameplay was run.

The corrected diagnostic is packaged and the existing JFG - Blur Source Audit
shortcut now selects runtime bf34694c847c4af69449cd7f85ced92ebcc90f2952e7f8d982f4f88dd5ee947b. The isolated profile
and save are retained; previous package, logs and shortcut are backed up.
No agent gameplay/visual verification. Startup marker will be checked before
the owner repeats the visual route; the prior failed audit remains preserved.

The owner-authorized corrected interactive diagnostic is launched muted.
The startup CSV marker is verified before the repeated route: mode 5, cap 120,
VSync on. Evidence: owner-blur-audit-exit-startup.json. No automated gameplay
or visual verification; full audit persistence and owner visual result remain
pending game close. This corrects instrumentation only, not image quality.

### Owner correlates softness with 30/30 output

Owner reports that all three soft shots show 30 rendered / 30 scene FPS,
returning to 120 / 30 when clear. The corrected capture closes successfully:
36,266 source-audit rows saved, zero dropped; frame log completes with no
queue drops or writer failure. This establishes the capture is usable; causal
interpretation remains under review. Private evidence:
owner-blur-audit-cadence-analysis.json and the original completed CSVs.
No automated game or visual verification was performed.

The completed owner audit identifies 594 native blur passes, all 594 rejected
by world/effect pairing (flag 64); all 594 source-copy attempts are consequently
skipped. Thus the earlier unchanged visual result did not exercise source-only
output. Source confirms failed pairing sets the original interpolation rate to
zero, disabling extra generated frames. The final blur interval measures
29.965 output / 29.965 scene FPS, while selected GPU targets remain 1280x960.
This identifies the output fallback mechanism, not yet the exact pairing check
or the cause of perceived softness. Existing target-size evidence alone is
insufficient. No GPU performance bottleneck is established by this result.

### Candidate: exclude buffer clears from blur source selection

Source review finds the recently added unique-source selection included all
320-wide RGBA16 color writes. The N64 clears depth by temporarily binding it
as a color target, so a normal depth clear plus scene is rejected as two
competing source images. Retained shot-344 display lists contain this exact
sequence. This is a concrete selection defect and a strong explanation for
the new audit rejecting every pair; owner-run confirmation is still required.
The selector now excludes fill-only and recognized depth-clear pairs and
requires RGBA16 drawing. Distinct drawn scene targets remain ambiguous;
serial, adjacency, source address, geometry and lifetime checks remain intact.
Standalone adapter checks cover a depth-clear plus scene, fill-only clear,
multiple distinct scenes, same-target batches, masks and empty output.
The diagnostic now records each world target and exact pairing rejection
bits. It remains a source-only diagnostic, not a released fidelity setting.
Evidence: blur-pair-world-target-command-review.json. Build/test/live pending.

The clear-source candidate builds; the standalone adapter/interpolation
regression checks pass without launching the game. Runtime SHA-256:
982e43fc44aa82bc4645e97780337735e02c33b675426aba9d5261a7021fc025. Owner confirmation of pairing, output cadence and visual
quality remains pending. No automated gameplay or visual verification.

JFG - Blur Source Audit now selects the clear-source candidate, runtime
982e43fc44aa82bc4645e97780337735e02c33b675426aba9d5261a7021fc025. Save, prior package and logs are preserved.
Owner review remains pending: compare the three shots for both sharpness
and 120/30 output; logs now show exact rejection reasons. Muted at startup.
No automated gameplay or visual verification; not a release resolution.

The owner-authorized clear-source candidate is open, muted, using the
unchanged isolated pre-rescue save. The schema-2 startup marker is verified
at 120 FPS/VSync. Evidence: owner-blur-clear-source-startup.json. Owner visual
and output-cadence results, and completed pairing audit, are pending.

### Owner confirms clear 120/30 diagnostic output

Owner reports "we are now at 120/30 and it looks clear" and "no more blurry bad
scenes" with runtime 982e43fc44aa82bc4645e97780337735e02c33b675426aba9d5261a7021fc025.
This accepts the visible result of the corrected source-only diagnostic for
all three reported shots. The old diagnostic copy was blocked by pairing;
excluding depth/fill clears enables a materially different owner result.
This is not normal-effect fidelity acceptance: mode 5 replaces the blur result
with its rendered source. Prepare the same pairing correction with mode 4
restored for owner comparison before choosing a production effect policy.
Completed numeric audit analysis remains pending game close. No automated
visual/gameplay verification. Evidence: owner-blur-clear-source-confirmation.json.

The owner closes the clear-source diagnostic; its completed audit records
592 successful pairs of 594 attempts and 2350 source copies issued.
Audit footer: # complete total=27994 saved=27994 dropped=0.
Frame footer: # completed queue_dropped=0 writer_failed=0.
Private analysis: owner-blur-clear-source-analysis.json. Owner confirms all
three shots clear. Prepare normal-effect mode 4 with the same source selection;
source-only acceptance does not establish authored blur fidelity.

The normal-effect mode-4 version of the same pairing correction builds.
Runtime SHA-256: 821042a28929e3d3ee9e69947388bc63138357e28c61060b278e1c3b37dca663. The source-only copy/audit mode is disabled.
Owner comparison is pending; no automated gameplay or visual verification.

A separate JFG - Blur Normal Effects desktop launcher packages mode 4 with
the same source-selection correction. Source-only preview/profile preserved.
New profile copies the pre-rescue save and controls, starts muted with 120 FPS,
VSync and frame counter/log. Runtime SHA-256: 821042a28929e3d3ee9e69947388bc63138357e28c61060b278e1c3b37dca663.
Owner will compare all three soft shots; gameplay/visual verification pending.
Evidence: owner-blur-normal-effects-delivery.json.

The owner-requested normal-effect preview is open, muted, with FPS logging
verified at Custom 120/VSync. An attempted inherited memory-only gameplay
trace was stripped by the normal launcher sanitization and is NOT active.
The owner was informed; no restart or automated play was performed.
This capture supports frame cadence and owner visuals, not a complete
landing-state trace. Evidence: owner-blur-normal-effects-startup.json.

### Owner normal-effect comparison result

With mode 4 restored, owner reports softness returns, but the scenes hold
120/30 throughout except one transition briefly showing 50/20 and recovering
immediately. Owner conditionally approves the appearance if it is intended.
Do not convert that condition into confirmation of original-game fidelity.
The successful source-only comparison isolates the visible softness to the
effect path, but still cannot distinguish authored strength/history from a
shared renderer error. Interpolation pairing correction has positive owner
acceptance; zero-transition-stall and final effect-fidelity claims remain open.
Private evidence: owner-normal-effects-review.json and completed frame CSV.
No control trace was active, and no automated gameplay/visual checks were run.

### Owner N64 comparison and tentative acceptance, 2026-10-18

The owner checked real N64 footage and reports that the same three shots are
also blurrier there. They consider the new normal-effect code tentatively fixed,
with a later whole-game review still planned. Record this as owner visual
comparison/acceptance, not an automated pixel-equivalence test or release.
The source-only diagnostic remains an investigation aid; normal native effects
remain enabled. The owner locates the brief reported 50/20 dip at the transition
from Vela to the first cut. Timing attribution remains open; do not equate all
gaps in the long owner session with this single cut.
