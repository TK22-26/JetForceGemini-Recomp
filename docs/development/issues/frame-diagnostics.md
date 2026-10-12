# PERF-002: Frame diagnostics and reported stutter

Status: counter/presentation corrections verified in muted tests; local preview delivered, owner live confirmation pending (2026-10-12).
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
