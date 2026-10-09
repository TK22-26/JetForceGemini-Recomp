# Quarry cutscene audio timing findings

Current performance status (2026-10-08): Selected runtime passes the controlled Quarry cutscene, gameplay, window-stall, packaged-launch and visible-window checks with zero audio underruns. See the final guarded performance result below. Public unified-frontend source integration remains pending.


Status: the owner accepted the cutscene timing on 2026-10-08. The subsequent
performance candidate passed the controlled cutscene and gameplay checks with
zero underruns and is selected in both launchers. Campaign-wide coverage and
integration into the unified frontend source remain open.

## Current checkout and replay

Use the current `JetForceGemini-Recomp` checkout.
Run `Play Quarry Cutscene.cmd` in its root. It automatically advances through
the menus into the Quarry entry cutscene, using fresh copies of a separate seed
save. It never opens the owner's normal campaign profile. Controls are replayed,
so close the game window after watching.

This is a dedicated timing test runtime, not yet an integration into the unified
frontend. The seed save alone is not a guaranteed Quarry resume point: the
test launcher also redirects the initial level request and selects Lupus before
allowing the original cutscene to execute. Its only ROM input is the owner's
existing USA ROM; no ROM is bundled.

Earlier evidence and the production investigation ledger remain in the old
`Jet Force Gemini Recomp` directory. Moving the working checkout did not reset
the investigation or its counters. The enabled supervisor admitted the owner's
new three-hour extension with a fixed deadline of 2026-10-08 23:55:02 UTC.
The incomplete replay interrupted by the CLI restart remains recorded as failed.

## Confirmed permanent-delay regression on 2026-10-08

The owner reported that the entire scene's sound was roughly one second behind
the picture in candidate `fa8068d6afb9...`, worse than the previous Mizar-only
complaint. The retained manual run began at 20:55:07 UTC.

The trace shows a 1.227-second host stall around title-screen VI 80. Audio
ran dry once. After playback resumed, the fixed host VI wall-clock origin was
still in the past. The game caught up quickly, producing audio faster than the
device could play it. Its queue then stayed near 1.23 seconds for the rest of
the run. This explains the persistent delay and why hidden replays without
that interruption looked healthy. The owner thinks the window was moved or
resized near startup; that trigger is plausible, rather than proved by the trace.

A zero overrun count did not rule out this failure: the overrun threshold was
two seconds, above the damaging queue depth.

## Recovery change and validation

The new `ViPlaybackClock` moves the host VI deadline origin forward when a new
audio underrun invalidates the old origin. Ordinary late frames still catch up
while audio remains continuous. The change does not alter guest Count, the
original device event ordering, music sequence timing, or PCM samples. It adds
no scene-specific waits and drops no audio.

Two private test builds received the same 1.2-second producer stall. After
VI 600, the old clock retained a median 1,222 ms queue; the recovery clock had
a median 92 ms queue and a maximum 108 ms queue. Both retained identical
guest-clock traces, final RAM, and PCM. Each intentionally forced stall caused
one underrun: this test proves recovery, not prevention of the interruption.

The uninstrumented recovery candidate also completed the full 9,000-VI Quarry
replay with zero underruns, overruns, or unsupported accesses. Its complete CPU
report, final RAM, PCM, and guest-clock trace matched the previous control.
Unit checks cover repeated independent underruns, unchanged pacing while
audio continues, and reinitializing the clock.

The owner test packages now use `06d5ef6843bd7efc58809f5b96562245b5242537f2dd09f2d54fc44d2299df5f`.
The injected-stall code is absent from that runtime.

Local evidence:
- `tools/private/quarry-recovery-20261008/recovery-qualification.json`
- `tools/private/quarry-recovery-20261008/test-package-recovery-activation.json`
- The old checkout's `tools/private/quarry-loader-clock-20261008/owner-regression-20261008`

## Earlier mechanisms and remaining limits

Earlier controlled work identified several independent contributors:
- HLE shortcuts skipped original CPU/cache/OS work while music continued.
  The original-OS timing candidate restores modeled instruction, cache, and
  device costs and paces the host against the original VI clock.
- Excess audio queued during renderer startup could persist as an output
  phase offset. Initial playback now drains to the existing startup cushion
  before establishing the host wall-clock origin.
- Synchronous recording, status, map, and volume-file work could block the
  game thread. The candidate uses bounded background writers/readers.
- The new manual run exposed the missing recovery after a later host stall,
  which the one-time startup correction did not address.

The N64 recording uses an original cartridge and upgraded Lupus. Its video is
20 fps, so sampled camera boundaries have 50 ms resolution. Previous process
loopback measurements found smaller remaining late-scene offsets and occasional
presentation spikes. Those findings do not override the owner's manual reports.
The cache/device model still has bounded approximations, and broad campaign,
frontend, and controller integration needs separate validation. Preventing the
window-handling stall and finishing current-source integration remain open.


## Owner confirmation — 2026-10-08

The owner approved the starvation-recovery test: the Quarry cutscene was perfect or close enough that they could not tell. They reported one tiny audio underrun as gameplay resumed. Cutscene timing is accepted for this test; the gameplay transition remains under investigation and overall smoothness is not yet declared fixed. The tested runtime SHA-256 is 06d5ef6843bd7efc58809f5b96562245b5242537f2dd09f2d54fc44d2299df5f. Evidence: tools/private/quarry-recovery-20261008/owner-recovery-confirmation.json.

## Follow-up on the small gameplay underrun

The owner confirmed they did **not** touch the game window after the cutscene.
Their accepted session logged two post-cutscene underruns, at retraces 8726
and 9353. Both overlap time inside the scheduler's Windows message pump:
119.849 ms and 80.505 ms. These are measured wall times; the old log does not
identify the message or distinguish message work from host preemption. Do not
attribute these events to a user moving or resizing the window.

A private candidate gives the window its own thread and transfers keyboard
and close requests through a short, synchronized mailbox. In controlled desktop
replays, two deliberately blocked window messages (1.2 seconds each) caused two
underruns in the control and zero in this candidate. A 9000-retrace comparison
also preserved the complete PCM, final RAM, CPU report and guest-clock trace
byte for byte. However, that heavier diagnostic replay recorded one underrun.
The window candidate remains unselected pending resolution of the residual
timing concern.

Two further CPU experiments were also left out of the launchers. Skipping
unnecessary fixture/observer checks recorded three diagnostic underruns and
three in its desktop stress replay. Separating the common instruction handler
from its large rare-path stack frame reduced the common frame from 688 to
32 bytes, but its diagnostic run still recorded four underruns (the desktop
stress replay recorded zero). These are failed acceptance checks, not fixes.
A contemporaneous profile of the approved baseline also recorded underruns;
raw counts across these runs do not establish that either edit caused a
regression. The baseline already contains targeted guest-thread wakeups, so
another proposed executor change was stopped before compilation as redundant.

The selected executable remains the owner-approved starvation-recovery build,
SHA-256 06d5ef6843bd7efc58809f5b96562245b5242537f2dd09f2d54fc44d2299df5f.
The standard Start Beta Test.cmd launcher in the older desktop directory now
uses this same approved executable; its prior v2 executable is backed up.
The isolated Quarry replay in the current checkout retains that approved build.
No campaign saves were changed. The experimental window and CPU changes were
not activated, and public unified-frontend source integration remains pending.

Detailed evidence and exact source candidates are retained in
tools/private/quarry-recovery-20261008/owner-acceptance-followup-findings.json.
The owner-approved cutscene timing is preserved. Overall zero-underrun gameplay
is still an open requirement.

## Gameplay performance follow-up - 2026-10-08, 22:59 UTC

The owner renewed guarded work for two hours. The operational guard remains
enabled, with the same investigation and all prior charges retained. This
section records investigation evidence before selecting another runtime.

Profiling separated two problems. Windows message handling can block the
emulation thread; the independent-window candidate removes that dependency.
The demanding part of the cutscene also leaves little CPU margin. A paired
memory profile measured approximately 0.57 ms importing each tiny graphics
task and 0.34 ms returning a full scene's GPU output to game RAM.

The memory candidate copies aligned writeback spans in bulk, while still
validating every owned range before changing any live byte. It compares
current snapshot bytes with the actual destination before skipping a copy.
It does not restore the broken GPU framebuffer reuse behavior or ignore CPU
edits to shadows. The existing renderer tests, additional snapshot boundary
cases, and 256 writeback equivalence cases passed. In the paired playback,
full-scene writeback fell to about 0.035 ms. The memory-only candidate passed
one desktop and one diagnostic replay with zero underruns, but combining it
with the window change did not reliably meet the acceptance requirement.

Native CPU samples identified the per-instruction timing callback as the
largest sampled native function. Two further changes reduce host overhead:
the common instruction path avoids the rare handler's large stack frame,
and immutable instruction properties are decoded at build time. Interrupt
eligibility, event deadlines, branch-delay bookkeeping, cache transitions
and the modeled N64 costs still run as before. No game instructions or
timing constants are changed.

The predecoded candidate checked all 428,937 generated hook sites against an
independent C++ decoder. Another 250,000 adversarial instruction/cache cases,
including dirty writebacks, idle transitions and counter wrap, matched the
old model. Its 9000-retrace replay preserved the complete PCM, final RAM,
CPU report and guest-clock trace byte for byte. That run recorded zero
underruns, overruns and unsupported accesses. After the first 300 video
intervals, the maximum excess in host presentation-call intervals relative to the original
video clock was 10.843 ms; the 99th percentile was 3.604 ms. No measured
host interval excess exceeded one original video interval. These are host
submission timestamps, not direct measurements of display scanout.

The following desktop run is **not an isolated performance result**. Another
`unified-frontend-20261008` native instance started about 95 seconds into it.
The run then logged audio gaps at 110.467 and 112.568 seconds and a roughly
one-second presentation pause. This overlap is recorded, without claiming
that it proves the cause of every pause. No other agent's or owner's process
was changed. The private test runners now detect other native game instances,
record them and close only their own replay if overlap occurs.

The new candidate SHA-256 is
`f350bab9d7e38282d5e453b4ff4d9aa2227ed57f4cf045dd0cce3baaadca97c2`.
It remains unselected pending uncontested desktop, active-gameplay and window
stress checks. Both existing launcher packages retain the owner-approved
`06d5ef6843bd7efc58809f5b96562245b5242537f2dd09f2d54fc44d2299df5f`
runtime. The deliberate 1.2-second sleeps exist only in separate stress-test
executables; they are never added to launcher builds or cutscene timing.

Evidence remains under `tools/private/quarry-recovery-20261008/`, including
`graphics-memory-phase-breakdown.json`, `bulk-memory-results.json`,
`cpu-hotspot-results.json`, `predecoded-initial-qualification.json`,
`predecoded-candidate/metadata-transformation.json` and
`peer-interference-evidence.json`.

The accompanying [source review patch](quarry-performance-candidate.patch)
shows the handwritten changes against the previously approved private
runtime, with private include paths normalized. It contains no generated
game code or ROM data. It is a review artifact, not a patch to apply blindly
over the current unified frontend. That source integration remains pending;
the other agent's current frontend/controller changes have been preserved.


## Follow-up validation limits - 2026-10-08

The additional peer-detection run predecoded-quiet-desktop-v2 found three
queue underruns at 66.443, 66.815 and 67.163 seconds (retraces 3863, 3881 and
3897). The other native game was first detected at 76.906 seconds. Its overlap
invalidates the complete run, but cannot explain those earlier gaps by itself.
The candidate is therefore not considered a reliable zero-underrun fix.
predecoded-gap-source-audit.json preserves the event order.

A separate host-layout experiment groups the per-instruction execution fields
into a compact, aligned part of the private C++ State object. Its game-memory
layout, instruction stream and modeled clock are unchanged. This experiment
requires its own complete replay and performance qualification before use.

The current public runtime source also differs substantially from the approved
private original-OS build. Neither the existing cutscene timing fixes nor these
performance experiments should be assumed present in the other agent's
unified-frontend build. predecoded-gap-source-audit.json records the source
hash observed during this review. Preserve the frontend/controller changes
when performing that integration.

The host-layout microbenchmark kept identical Count and instruction totals.
Its median improvement was 0.78%, insufficient evidence to select another
runtime. The compact layout remains an unselected experiment; see
hot-state-cpu-benchmarks.json and hot-state-benchmark-decision.json.

## Final guarded performance result - 2026-10-08

Selected runtime passes the controlled Quarry cutscene, gameplay, window-stall, packaged-launch and visible-window checks with zero audio underruns.

The three uncontested desktop runs had no overlapping native game processes.
Both deliberate 1.2-second window stalls were acknowledged and completed.
The 9000-retrace diagnostic retained identical PCM, RAM, CPU report and
guest-clock trace. The instruction metadata, window mailbox and byte-copy
equivalence tests are described above.

| Run | Audio underruns | Maximum host interval excess (ms) | Excess over one VI |
| --- | ---: | ---: | ---: |
| predecoded-9000 | 0 | 10.843 | 0 |
| predecoded-clear-desktop | 0 | 12.744 | 0 |
| predecoded-clear-stress | 0 | 10.125 | 0 |
| predecoded-clear-gameplay | 0 | 9.032 | 0 |

The frame figures exclude the initial 300 retraces and measure host
presentation-call intervals relative to the original VI clock, not monitor
scanout. They do not establish perfect pacing throughout the entire campaign.

The selected executable is f350bab9d7e38282d5e453b4ff4d9aa2227ed57f4cf045dd0cce3baaadca97c2. Both the requested
Start Beta Test.cmd in the older desktop folder and Play Quarry Cutscene.cmd
in the current checkout use it. All three package checks pass; the previous
owner-approved executable and metadata are backed up. No campaign saves were
changed. No scene-specific waits, audio padding, audio drops or guest-clock
changes were added by these performance fixes. The injected sleeps exist
only in the separate stress-test executable.

The tested runtime sources and build recipe remain in the current checkout
under tools/private/quarry-recovery-20261008. The review patch records the
handwritten delta. Integration into the public unified-frontend source tree
remains pending; the other agent's edits have been preserved.

Evidence: predecoded-qualification.json, performance-package-verification.json,
performance-visible-gameplay-qualification.json, performance-runtime-activation.json,
and gameplay-performance-final-findings.json in that private evidence directory.

## Public unified-runtime integration - 2026-10-09

The accepted Quarry work is now integrated into the public ROM-to-build recipe
and the unified launcher runtime. This supersedes the integration-pending notes
above; those entries preserve the investigation history.

Fresh generation instruments the original OS and game instructions with the
qualified cache/device clock model. The original OS owns interrupt, queue and
thread behavior. The AI and PI models, paired-FPR handling and starvation-aware
host playback clock are included. The renderer retains the asteroid, depth
occlusion, CPU framebuffer-edit and SIMD memory-copy corrections.

Host window messages run on the window-owning thread with an input mailbox.
Volume reads, diagnostic output and map snapshots no longer block the guest
execution path. Cooperative executor wakeups target the next participant.
All default unified-frontend exports and current controller features remain on.

The first combined build still underran in the opening cinematic. Profiling
found CPU saturation during original guest polling loops: the function
dispatcher queried a test-only environment variable on every call. Reading
that immutable option once at startup removed the reproduced audio gaps.
Instruction fast paths and compile-time OS observer lookup preserve the same
guest costs, interrupt boundaries and original routine bodies. Generated PCM
remains byte-identical to the corresponding pre-optimization replay.

Original OS execution also exposed two controller polls in a single retrace.
Recorded-poll replay now preserves both samples; ordinary retrace replay still
rejects ambiguous overlapping intervals. Backward and nonidentical overlapping
records remain rejected atomically. Automated aim, movement, firing, camera,
stock-mode and record/replay checks pass; physical multiplayer is not asserted.

A fresh build from the owner's ROM, without prebuilt game objects, passed two
full opening runs and one Quarry cutscene/gameplay run at a verified 1920x1080
game viewport. No other native game overlapped these captures. The 81 ROM-free
C++ tests, three renderer regressions, schema checks and Linux Python suite pass.
The local Windows Python run retains three pre-existing Phase 4 harness failures:
this PC's WSL binary differs from that historical audit's pinned hash. The
unchanged base revision reproduces them; the pin was not weakened or replaced.
The fresh generation exposed duplicate inclusion of the timing ABI header;
the corrected include boundary was rebuilt through the public, manifest-checked
native resume command. No generated game files were edited to make it compile.

| Run | Audio underruns | Output gaps >=6 ms | Maximum host interval excess (ms) |
| --- | ---: | ---: | ---: |
| intro-final | 0 | 0 | 13.388 |
| quarry-final | 0 | 0 | 9.725 |
| intro-final-repeat | 0 | 0 | 15.475 |

These are native-process WASAPI output comparisons and host presentation-call
timestamps, not direct speaker/monitor measurements or whole-campaign parity.
No measured interval excess exceeded one original video interval in these
qualified runs. No scene waits, audio padding, audio drops or scene-specific
clock changes were added. Actual recordings, spectrograms and ROM-derived
inputs remain private. Exact executable identity and aggregate checks are in
[unified-original-timing-validation.json](../../evidence/unified-original-timing-validation.json).
