# PERF-002: Frame diagnostics and reported stutter

Status: native scene timing and present logging verified in bounded capped-play tests; local preview delivered, owner verification pending. Unlimited throughput and broader audio remain open.
Severity: high owner-reported stutter; presentation defects reproduced and corrected in the candidate.
Owner reports slowdowns while testing the high-refresh preview but has no visible
counter or convenient frame log. Slowdown cause and location remain unconfirmed.
The separate combat slowdown record is PERF-001; do not assume the same cause.

Candidate: F8 toggles a swapchain-only counter and asynchronous per-render CSV.
Count render intervals and screen-scene submissions separately, excluding small
offscreen shadow tasks. The observer never writes simulation memory. Disk writes
run on a separate thread; an 8192-entry bounded queue counts overflow rather than
blocking rendering. Four rotating 16 MiB files bound each session's storage.
Local preview defaults can be enabled through performance.ini next to video.ini.
Tests must start muted and use copied profiles/saves. No slowdown fix claimed.


Initial build caught a misspelled configuration field, corrected before replay.
The first enabled replay failed before gameplay with 0xc0000409 in NVIDIA's
nvwgf2umx.dll (Windows Application events 1000/1001, retained crash dump).
The large glyph rectangle batch is a candidate trigger. The next candidate
limits clear calls to sixteen rectangles and keeps non-Windows renderer builds
behind a no-op diagnostics adapter. Failed run remains preserved; no delivery.


The bounded rectangle batches pass subsequent Original and Custom 360/VSync
replays. The initial driver failure did not recur in these checks; the exact
driver-internal failure is not diagnosed. The counter is Windows-only; other
renderer builds receive a no-op adapter rather than Windows dependencies.

Validation: three muted 4,500-VI modern-route runs (Original diagnostics on,
Custom 360/VSync on, Custom 360/VSync off) preserve exactly the same guest RDRAM,
renderer snapshot and save as the prior clean fixture. CSV frame numbers and
timestamps are monotonic, queue drops are zero, and Custom records intermediate
output frames rather than merely counting game submissions. The disabled run
writes no frame log. A screenshot verifies counter text and placement. F8 uses
foreground game-window ownership and rising-edge detection; physical-key/live
fullscreen verification remains for owner testing. Automated tests never take
desktop focus. Rotation/error paths were reviewed, not disk-exhaustion tested.

FPS measures swapchain render-hook cadence, not physical monitor scanout. GAME
counts screen-scene submissions, not every guest simulation tick; 64x64 shadow
tasks are excluded. MS is the last half-second's mean render interval; MAX is
its worst interval. Logging records each raw interval and the latest scene/VI
counters. Pausing, minimizing, loading and diagnostics toggling can introduce
gaps; these must be distinguished from gameplay stalls. GPU utilization and a
precise slowdown cause are not inferred from these counters alone.

Delivery uses the same preview profile and saves in a new immutable package.
The preview defaults to diagnostics enabled through `performance.ini`, with
F8 toggling the counter and recording for the current game session. CSV files
are under `performance` beside `video.ini`; a desktop **JFG - Performance Logs**
shortcut opens that directory. Stop the game to finish the capture, then share
the CSV files with the same session prefix. Four rotating 16 MiB segments retain
bounded recent history per session; old sessions are retained until removed by
the owner. Files contain timing/counter data, not game memory, ROMs or saves.
The observation tool has some rendering cost; compare with F8 off when needed.

Private evidence: `fps-logging-qualification-v2/result.json` and per-mode CSV,
frame captures, stdout/stderr; initial failed run and build receipts retained.
This adds observability and does not claim to fix the newly reported slowdown.


Implementation commit: `930c57517f31f624d2a05527cdcc1b5264ff4c72`.
Machine-local package: `C:/JFG-builds/high-refresh-diagnostics-preview-20261012`.
The existing preview shortcut now targets this package with the same profile;
the new Performance Logs shortcut opens that profile's `performance` folder.
All fourteen manifest entries and isolated launcher package resolution passed.
Runtime SHA-256: `9fc3233e51b0436f2675362bf9c803a81ee0a94a5a43cd1d9ee68612e2caa0f4`.
Old package and shortcut backup remain available; no public release was made.

The Original run recorded 3,218 render rows and Custom recorded 16,132, with
2,056 scene submissions in each. Custom diagnostics-on/off took 76.829/76.812
seconds in this capped replay; this does not establish overhead at unlimited
FPS, different hardware or long sessions. [Aggregate evidence](../../../evidence/frame-diagnostics.json)
links the observations to the qualified runtime. Implementation:
[counter and bounded writer](../../../src/renderer/frame_diagnostics.hpp),
[scene counters](../../../include/jfg/renderer/frame_diagnostics_state.hpp).


## Owner live regression, 2026-10-12

Owner reports stutter only with the newly delivered diagnostic build, with
GAME showing 20 while output shows 120 (Custom 120, VSync on). This supersedes
the narrow muted replay qualification as evidence of live usability. Severity:
high, reported regression plus misleading counter labels; the timing causes require comparison.
Affected runtime: `9fc3233e51b0436f2675362bf9c803a81ee0a94a5a43cd1d9ee68612e2caa0f4`.
Private owner timing capture: `frames-20261012-062848-6524-0.csv`; summarized
in `fps-regression-owner-capture.json`. No reproduction or fix is claimed yet.

Suspects: the overlay emits many rectangle-clear commands every output frame;
we must compare this separately from asynchronous logging. The GAME counter is
actually screen-scene submission cadence, not a verified simulation counter.
The output counter includes interpolated and repeated frames and cannot establish
120 unique game poses or smooth delivery. Original 30 versus observed 20 requires
comparison with the pre-diagnostics runtime and scheduling evidence.

Approved bounded work retains the production guard, investigation root and all
existing counters. Automated tests remain muted and use isolated copied saves.


### Owner F8 comparison and cadence-transition candidate

Owner confirms the stutter continues with F8 off. The raw comparison repeats
a large output gap at scene VI 4113 with legacy/cached/log-only instrumentation.
Pre-diagnostics RT64 trace has four interpolated frames at VI 4110, a single
unmatched scene at 4113 (source_rate=0), then six matched frames at 4116 (20 Hz).
The history policy invalidates every change between two- and three-VI intervals;
normal 30/20 Hz transitions therefore disable interpolation despite valid motion.
This is a specific presentation defect distinct from source simulation slowdown.

Candidate allows ordinary two/three-VI transitions to use their actual source
interval and existing motion/geometry continuity checks. Camera jumps, unsafe
mixed-transform geometry, long gaps and other cadence changes retain their
existing rejection. Focused transition tests and muted native comparisons are
pending. This candidate does not change guest timers or force 30 Hz simulation.


### Completed-sequence replay candidate

The cadence candidate restores six moving intermediates at VI 4113 and retains
the same guest/renderer/save hashes, but a roughly 33 ms output gap remains.
Do not credit it with eliminating the reported timing stutter.

A separate capped-rate defect is visible in the baseline and candidate trace:
VI 4498 is rendered once into four intermediates, then present events 3216,
3217 and 3218 each present the entire 0..3 sequence again without a new scene.
That replays motion backward at the start of each duplicate group. The previous
repeat-latest guard applied only to Unlimited. Finite counters also count extra
targets while their count includes the base frame, so completion was not marked
as the complete sequence.

Candidate marks completion after the final output and extends repeat-latest to
completed capped sequences, with finite-array versus unlimited-ring indexing.
No source updates or scene timing change. Native trace/pixel verification and
regression checks are pending; this candidate is not yet delivered.


### Capped streaming experiment

The completed-sequence correction verifies 505 repeat groups with at most one
output each and preserves all fixture hashes. It removes sequence rewind, but
the fixed-batch 120 FPS moving-window p99 worsens from roughly 10 to 25 ms.
This is not an accepted final performance fix and has not been delivered.

Next candidate reuses the existing two-target, time-sampled producer/consumer
ring for capped interpolation as well as Unlimited. The consumer still enforces
the requested cap and VSync; the producer uses elapsed source-frame time and
yields to new scene work. This avoids finite-batch restart and rate-transition
phase resets without changing guest simulation. Tests and measurements pending.


The initial capped-streaming replay preserves hashes and avoids sequence rewind,
but its moving-window p99 is about 23 ms. Source review also identifies a capped
producer/consumer mismatch: an unpaced producer can fill the ring with multiple
nearly identical early-time poses before the capped consumer displays them.
The next bounded variant paces pose sampling to the cap while retaining the
existing presentation cap and yielding at source-window end/new scene work.
No streaming variant is qualified or delivered yet.


### Separate capped-sequence buffers

The paced streaming variant reduces the moving-window maximum to 10.9 ms, but
replay duration grows from about 76.8 to 81 seconds and wall-time scene cadence
falls. Rejected: smoothing output by making the game wait violates the task.
Neither capped streaming variant will be delivered in this form.

Next candidate restores finite interpolation and gives consecutive sequences
separate alternating target banks. The old shared target array forced the
producer to wait for the previous sequence's consumer, then reduced/skipped
frames because that intentional ownership wait counted against its render
time budget. Two banks avoid cross-sequence overwrite/wait while existing
present-ID ordering protects bank reuse. Unlimited retains its two-slot ring.
Completion/repeat-latest and normal 30/20 Hz transition corrections remain.
Build, replay, memory/scene-speed and presentation checks are pending.


The first two-bank replay preserves baseline wall time/state and holds about
60 outputs/second with a moving-window maximum of 19.6 ms. Its 120/VSync request
was actually clamped to 60: the desktop now exposes one 1920x1080 display and
RT64 reports 60 Hz, whereas earlier runs detected 240 Hz. The test's obsolete
assumption of more than 100 duplicate groups failed (74 actual groups); this
is not a 120 Hz performance pass. Preserve that failed assertion and evidence.

Subsequent qualification will use explicit effective-rate checks: VSync-on at
the currently reported 60 Hz and capped 120/360 with VSync off, without changing
the owner's desktop settings. The old delivered runtime is rerun under those
same current conditions. Target-bank allocation and consumer lookup share a
mutex so vector growth during cadence transitions does not race presentation.


The two-bank candidate alone fails qualification: 120/VSync-off moving-window
p99 is 25.05 ms versus the delivered build's 9.82 ms. Unlimited also fails
the scene-progression gate. No desktop update was made. Actual swapchain
readback proves the previous runtime replays the same four distinct images
for consecutive VI presentations; the candidate holds only the final image.
The next experiment preserves a finite repeat output window while repeating
that final image, so removing rewinds does not introduce idle present gaps.
Readback runs are visual evidence, not timing benchmarks.


## Qualified correction, 2026-10-12

The owner's F8-off comparison confirms that disabling the counter does not stop
stutter. The retained pre-logging runtime also produces 20 Hz source scenes on
this route. Do not call that counter reading an invented conversion, force the
guest simulation to 30 Hz, or confuse 120 outputs with 120 unique authored poses.

Three defects are addressed in the final candidate:

- The bitmap counter emitted hundreds of tiny rectangle clears each output.
  It now uses one cached texture draw, uploaded when displayed text changes
  (normally twice per second). Labels read OUTPUT and SCENES, with an explicit
  INTERPOLATED / REPEATED line. Neither counts physical monitor scanout or
  simulation ticks. `overlay=0` in performance.ini enables log-only isolation.
- Ordinary two-to-three-VI scene intervals (30/20 Hz) invalidated interpolation
  for one frame. These transitions now retain valid transform history; the
  existing geometry, shared-matrix, projected-jump and other cadence rejection
  checks remain. VI 4113 now has six moving intermediates at 120 and eighteen
  at 360, rather than a single unmatched endpoint.
- A later VI restarted an already completed finite interpolation sequence.
  Actual GPU readback shows the old runtime displaying the same four distinct
  images again. The correction repeats its latest image through the paced
  output window. Presenting only one repeat per VI was rejected because it
  introduced idle gaps. Alternating finite GPU target banks prevent the next
  producer sequence from overwriting a target still being presented. Their
  vector allocation/lookup is synchronized; intermediate-target storage is
  roughly doubled. Unlimited retains its bounded two-target ring.

The 120/VSync-off moving window changes from 119.43
outputs/s, p99 9.823 ms and maximum
29.735 ms to 120.00, p99
9.725 ms and maximum 10.892 ms. At 360 the candidate
measures 359.80 outputs/s, p99 3.494 ms and maximum
7.110 ms. These are bounded fixture observations, not a claim that
all owner-visible stutter is fixed.

Original, VSync (currently detected 60 Hz), 120, 360, log-only, 1000 and Unlimited
runs preserve the expected guest RAM, renderer snapshot and save hashes, with
2,056 source scenes and zero CSV queue drops. Capped replay duration and source
progression match the baseline. Unlimited's strict near-30-Hz progression gate
failed in both old and new traced builds; compare its no-trace results separately.
Its high output count does not establish full-speed gameplay under saturation.
No game clock/input/audio scheduling change is made. Focused interpolation-history
and RT64 interpolation tests pass. Test windows are hidden and muted; automated
checks never take desktop focus. Current 60-Hz desktop VSync is not evidence of
physical 120/360-Hz scanout; those rates were tested with VSync off.

Actual swapchain readback verifies completed groups contain only repeated latest
pixels. Readback is excluded from timing benchmarks. Source/aggregate evidence:
[comparison receipt](../../../evidence/frame-diagnostics-regression.json),
[history](../../../include/jfg/renderer/interpolation_history.hpp),
[presentation adapters](../../../cmake/rt64_video_settings.cmake),
[counter](../../../src/renderer/frame_diagnostics.hpp). Private attempts and
failed gates remain under `fps-regression-*`; no ROM, generated code or save is
published. Dependency inputs remain pinned, with patches in build-tree copies.

The local preview remains experimental. Owner live testing, other scenes,
fullscreen/high-refresh display behavior and long sessions remain outstanding.
Original-mode joints/lighting and conservative actor interpolation remain in
[RENDER-002](character-seams-lighting.md); combat throughput remains PERF-001.
The original logging-build claim is not treated as proof that instrumentation
alone caused every hitch. No public release or blanket stutter resolution.

Transferable lessons: a steady FPS counter can conceal backward animation;
validate image order as well as timing. Identical guest memory does not prove
wall-time speed. Check source-scene throughput, compare observation on/off,
verify effective VSync targets, and retain failed candidates and their costs.


### Local delivery receipt

Implementation commit: `19fde3c7c0d5b102e4dd2c2d1fa6e0c9af4fbd67`.
Runtime SHA-256: `b3e871f0cde15a90263f5e691932cf026e6cef182c42f3592ca86023e3fa3a50`.
Package: `C:/JFG-builds/high-refresh-diagnostics-v2-preview-20261012`.
All 14 manifest file sizes/hashes and isolated managed
launcher resolution passed. The existing desktop **JFG - High Refresh Preview**
shortcut targets the new package with its original arguments/profile. The previous
package and shortcut backup remain available. Audio, video, controller, modern
controls, diagnostics preference and save hashes were unchanged by delivery.
Close the existing launcher and reopen the desktop shortcut to load the candidate.
No public release, push, owner desktop input or game launch occurred during
handoff. The tests were muted; owner live acceptance remains pending.


## Source scene-rate investigation, owner approved 2026-10-12

The owner explicitly asks to fix the remaining 20-Hz scene-update drop, with up
to five hours and commits of this work. All prior HFR changes are already committed
(implementation 19fde3c, delivery notes 0fac3b6); this research worktree starts
clean. The existing high-refresh investigation/root and guard retain every charge.
The unrelated main checkout has uncommitted timing/audio/control work and is
preserved. The older PC/audio investigation is shelved and is not resumed here.
Its retained source/evidence can inform this narrow scene-cadence investigation.

Reproduction: the existing muted copied-save Goldwood bridge fixture changes
from two to three VI intervals during movement (30 to 20 screen scenes/sec),
including VI 4113 and following scenes. This occurs before logging was added and
with Original presentation. Presentation-only fixes do not restore source cadence.
Investigate modeled CPU Count cost, real host work/scheduling and explicit guest
frame-selection behavior. Preserve elapsed movement/animation/weapon timing,
input, audio deadlines and save correctness; do not accelerate game speed merely
to raise the counter. Related prior combat work: [PERF-001](goldwood-combat-slowdown.md).
All experiments use muted isolated profiles and guarded execution; no owner input.


The original-policy bridge replay with low-volume update/cost tracing and input
recording retains the exact baseline RAM/renderer/save hashes and 2,056 scenes.
A second recorded-poll replay also preserves them. The next comparison switches
only clock policy after an identical VI-3900 prefix; this is a diagnostic, not
a delivered change. Retained source/evidence paths are recorded privately in
`scene-rate-retained-timing.json`; no unrelated main files are changed.


The baseline charges about 34.1 ms median modeled non-idle CPU work in the
20-Hz bridge interval, crossing a 33.4 ms frame budget. Retained guest source
`gameVi.c::viFrameSync` sets LOGIC_20FPS after a late frame and waits for more
than 30 faster updates before restoring LOGIC_30FPS. The native elapsed-clock
comparison starts from identical VI/poll/Count/RAM at VI 3900 and keeps two-VI
updates (33.44 ms median) through that interval. It is an existing clock policy,
not a guest frame-rate patch or forced time multiplier.

The diagnostic native process reaches VI 4500 cleanly, but its final presentation
is too old for the existing optional renderer snapshot, so the wrapper fails on
missing rdram.bin.rt64. This is a capture limitation, not a qualified full pass;
retain it and compare boundary/trace evidence separately.

Candidate: opt-in native elapsed timing for interactive preview; finite reference
probes keep the original instruction clock. Reuse the existing independently
unit-tested periodic deadline/scanline phase helper to coalesce overdue video
interrupts after a host stall without accelerating catch-up. Add bounded offline
stall and pause observations for qualification. No guest frame-rate clamp, CPU
span generation, unrelated main edits or audio DSP changes are imported.

The first policy-check wrapper incorrectly expected a plain-text `retraces=4500` marker in JSON output. Its reference process exited normally and preserved all three reference hashes. Correct the parser in a new retained step; this is a harness failure, not a runtime failure.



Qualification harness failures retained: the live trace-tail reader attempted to parse a partially flushed hexadecimal field; its hidden play child was stopped by the guarded worker. The follow-on analysis could not find the unfinished play window. The first startup probe requested an incompatible realtime flag and was rejected before starting. Fix the wrappers and rerun; these are not passing runtime checks. The interpolation-trace run overlapped the failed play child and cannot be used as an uncontended performance benchmark.

Native timing restores about 29.8 screen scenes/s in the boundary replay, but the 120-FPS candidate has recurring ~16-ms output gaps. The 360-FPS candidate reaches ~354.6 output FPS with one ~25.9-ms gap. Treat presentation pacing as an unresolved candidate regression and investigate before delivery. Detailed qualification is retained in scene-rate-policy-analysis.json.

The paired stage trace explains the apparent 120-FPS regression: draw-hook
intervals reached 16.4 ms, while actual present-return intervals stayed near
8.34 ms (p99 8.62, maximum 9.14 in that diagnostic interval). The counter sampled
before RT64's limiter, so it measured preparation scheduling, not output pacing.
This diagnostic overlapped a failed wrapper's hidden child and is not a final
performance benchmark. Candidate correction: sample successful swapchain returns,
keep the cached overlay drawing separate, and label CSV schema 2 explicitly.
Monitor scanout/visible fluidity still require owner verification.

The first final play wrapper successfully paused/resumed and requested close, but checked window ownership again after the runtime destroyed its window. That harness assertion terminated the waiting outer process before a complete receipt. Correct the closed-window polling condition in a new immutable wrapper and rerun. The initial startup play attempt shares that wrapper flaw; keep its evidence separate from successful tests.

Unlimited qualification with the new timing boundary stops producing frames at
VI 3900 and reaches the wall-clock watchdog (exit 4). Preserve the failed run:
`scene-rate-final-compatibility/native-unlimited`. Capped modes complete this
boundary. The unlimited ring waits for a free target/previous consumer without
a deadline, despite checking scene expiry only after waking. Candidate: bound
that wait by the existing scene time window, then mark generation complete and
wake the consumer. This imposes no numeric FPS cap and does not overwrite an
occupied target. The candidate needs replay qualification before delivery.

The normal --play path with native timing from boot still has recurring long updates and audio starvation, unlike the identical-prefix boundary replay. The 1.25-second pause itself freezes Count correctly, but this candidate does not yet fix normal-play scene cadence. Startup audio qualification also fails its no-underrun requirement. Do not ship the boundary result as a completed fix; compare the normal-play stalls and preserve scene-rate-live-stall-analysis.json.

The normal-play comparison enabled JFG_PHASE8_FRAME_CAPTURE. In --play this
forces a synchronous GPU readback every 60 submitted presentations, waiting for
the whole presentation queue to idle. The long trace gaps end in present(),
not CPU computation or idle timer oversleep. Ordinary launcher Play strips this
option; it belongs to the explicit heavy diagnostic capture. Correct the timing
fixture to omit periodic screenshots in --play, preserving lightweight CSV and
muted PCM recording. Do not treat screenshot-enabled results as ordinary-play
performance or import unrelated CPU optimizations to compensate for readback.
Heavy capture remains a documented source of stalls and audio starvation.

Bounding the Unlimited wait removes the watchdog, but Unlimited still spends
up to 33 ms inside scene full-sync submission, drops to 20-Hz updates and starves
audio while emitting about 1,390 output frames/s. Candidate: give each in-flight
sequence its own two-slot ring (four targets total), as finite sequences already
have separate banks. Remove the previous sequence's target-reuse wait while
retaining the current ring's slot ownership and deadline. This is bounded GPU
storage, not a numeric FPS limit. Validate before retaining or delivering.

The separate Unlimited banks did not recover source cadence (~19 scenes/s) or
audio continuity; revert that experiment and its extra allocation. The renderer
still ignores queued off-screen shadow passes until the old scene's time window
ends. Those passes can contain CPU-visible readback, so queued work can hold up
the next game update. Candidate: yield Unlimited interpolation to any queued
workload, preserving the bounded slot wait and original two-target ring. There
is still no numeric FPS cap. Check both scene rate and output spacing rather
than crediting a high repeated-frame count.


### Accepted implementation and remaining limits

The private build enables JFG_EXPERIMENTAL_NATIVE_PLAY_TIMING for --play.
Elapsed steady time drives Count at 46.875 MHz; guest viFrameSync, update steps,
movement scaling and save logic remain unchanged. Finite reference probes and
other builds retain the original instruction clock by default. The native policy
removes modeled CPU penalties as the trigger for the reproduced bridge's 20-Hz
fallback when the host has enough time. The game's real-overload fallback and
31-update recovery rule remain intact.

Keep the original two-target Unlimited ring with a bounded scene-window wait,
which fixes the transition watchdog. Extra banks did not recover cadence and are
reverted. Eagerly yielding to all queued work recovered 30 scenes/s but produced
~145 output FPS with ~41-ms gaps, so that experiment is reverted too. Unlimited
can still delay game-dependent rendering and reduce source updates to ~20 Hz.
Use Custom for this scene-rate correction; rates above 360 remain hardware and
workload dependent. Neither rejected change is in the accepted source.

CSV schema 2 measures successful present returns after pacing, retaining its
columns. OUTPUT includes interpolated/repeated images; SCENES counts submissions.
Neither measures monitor scanout. The cached overlay remains one texture draw.
Normal 120-FPS play without periodic screenshots holds two-VI updates (~33.4 ms)
and records zero audio underruns on the bridge. The 1.25-second frontend pause
freezes Count and resumes without catch-up. Boundary comparisons preserve the
route endpoints and copied save. Original-clock probes retain exact RAM/renderer/
save hashes; native final RAM differs and is not claimed as reference parity.

A 200-second startup comparison produces ~200.46 seconds of PCM in the reference
and ~200.51 in native play, with ~98.8% nonzero samples. Native reports three
underruns/one empty pause versus zero in this reference. This fails the strict
zero-underrun startup gate; broad audio continuity and audible quality remain
open. Explicit diagnostic screenshots impose synchronous GPU waits and must not
be used as ordinary-play performance benchmarks. No audio DSP changes or CPU
span optimizations were imported; the shelved audio investigation stays shelved.

Other levels, combat, long sessions, full actor interpolation and reported seams/
lighting remain outside this demonstrated correction. Tests were muted, hidden,
and used copied saves. Every failed wrapper/candidate is retained privately.


### Committed runtime qualification

Implementation `5c7df1bdee61778590fb3b7baa281958a9167870`; rebuilt runtime SHA-256 `a14d9d77fc98ef6be1999a3ea9492d60467a4b107e376c66d431fbfd70231259`.

| Normal play setting | Output FPS | New scenes/s | Update median ms | Output p99 ms | Output max ms |
|---|---:|---:|---:|---:|---:|
| play-120-vsync | 119.66 | 29.76 | 33.428 | 9.019 | 9.534 |
| play-360 | 351.99 | 29.78 | 33.451 | 3.157 | 28.819 |

These are hidden, muted, copied-save tests at 1600x900. The VSync row records the
requested setting; it is not monitor-scanout verification. Both normal-play
runs record zero audio underruns and CSV queue drops. Original-clock replay
retains all three reference hashes. Five focused clock/scheduler/interpolation
tests pass. The longer startup/audio and Unlimited limits above remain open.
[Aggregate qualification](../../../evidence/native-scene-timing.json) records
artifact identities and distinguishes checks made on earlier binaries from the
final runtime. No full-game parity or blanket stutter resolution is claimed.


### Local preview delivery (2026-10-12)

The desktop **JFG - High Refresh Preview** shortcut now selects
`C:\JFG-builds\high-refresh-native-timing-preview-20261012\JFG-Launcher.exe`.
Close the old launcher and reopen that shortcut. Use a Custom cap for this
scene-rate correction; F8 toggles the counter/log, and **JFG - Performance Logs**
opens the existing log folder. The launcher initialization check selected the
new runtime, all 14 manifest entries passed hash/size verification, and the
existing profile/save/settings hashes were unchanged. The old package remains
available. This is a local preview, not a public release.

The implementation commit and exact delivered runtime are recorded above and
in the qualification JSON. Owner live confirmation of the bridge and overall
stutter remains pending. Unlimited source cadence, startup audio continuity,
combat, other levels, seams and lighting are not declared resolved.

## Hidden controller replay fractional-motion regression (2026-10-13)

The extended owner route exposed a replay limitation: physical focus gating
cleared precise stick/scope fractional motion even when the recorded input path
correctly bypassed the physical gate. Hidden replays could therefore diverge
from focused live input. Candidate uses the already computed effective input
block state for both suspension and fractional resets; live focus loss and
explicit diagnostic replay suspension still reset. A fractional slow-stick
regression check is added. Build and owner-route correspondence are pending;
this is not presented as a damage-hitch or scenery-jitter fix.

The hidden fractional-motion correction now passes focused input and replay
checks: recorded low-rate input retains its accumulated fraction while live
focus loss and explicit replay suspension still clear it. This removes one
source of replay divergence; it does not restore full owner-route equivalence.
Final native Play compares log-only and expanded tracing at 120/30 with 18
actual damage events and no diagnostic drops. The owner's damage-correlated
source-rate loss remains open. See [route qualification](tutorial-late-object-jitter.md#review-qualification-2026-10-13).
