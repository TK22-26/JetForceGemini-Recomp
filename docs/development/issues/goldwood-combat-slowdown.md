# PERF-001: Goldwood combat slows game updates

- **Severity: critical. Status: open; diagnostic candidate partly improves timing.**
- Reported: 2026-10-11 UTC. Last status cross-reference: 2026-10-13 UTC.
- Affected: modern-controls v1.1 local preview with original instruction-clock runtime;
  source capture runtime SHA-256 `de2737396c3f840291de8a9155eaed415f6076beaf4d27200be6505cde11c538`.
- [Implementation investigation and research](../../features/pc-controls.md#2026-10-11-critical-goldwood-timing-investigation).
- Related: CAMERA-001 small boom-distance steps; CAMERA-002 large collision pull-ins.

## Symptoms and reproduction

The owner reported lag while fighting Goldwood drones and crossing the bridge after
the first enemy section. Rapid mouse turns made the issue noticeable. The worst
combat window in capture `20261011-011404-f9cc9def804541998e2a5fa4d250df0b` is
approximately 190-210 seconds. The late bridge segment is approximately 237-268
seconds. A steady 30 Hz camera has inherent latency, but it cannot explain the
measured combat collapse to roughly 15 game updates per second.

## Evidence and cause

Host VI ticks continue near 16.7 ms while game updates reach about 67 ms median,
with 85-98 ms gaps in the source capture. CPU graphics submission is about 2.6-3 ms;
this is not GPU completion time and does not rule out all graphics bottlenecks.

The current execution policy charges Count for modeled N64 instruction and cache
costs, then paces the host to that timeline. It therefore reproduces the modeled
console CPU throughput limit and also spends host CPU time evaluating that model.
A light-trace run measured about 62.3 ms modeled non-idle work per update in the
worst window. This is a demonstrated contributor. It does not by itself explain
all residual host execution or scheduling costs.

Actor trace rows are changes, not complete snapshots. Reconstruct by slot and
apply removals. Corrected source combat counts are 44-58 total table entries and
1-7 enemy entries; these are not visible-on-screen counts. Earlier counts derived
from individual delta rows are invalid.

## Attempts and results

| Experiment / hypothesis | Result | Decision |
|---|---|---|
| Fixed modern desired camera distance | Removed 186 unobstructed fixed-angle relative steps over five units in comparable replay pairs | Separate camera fix delivered; does not repair combat update rate |
| Full versus light capture logging, same runtime/input | Slowdown remains; final RDRAM identical (`757b7094a9d6fabd671e4c90ba7d50e54a52741d3e7ff3ffb57df3f062b93d99`) | Logging is not the sole cause |
| Extra modern camera visibility-query cost | About 0.14 ms modeled / 0.52 ms host per traced invocation | Too small to explain the measured deficit |
| Replace modeled CPU clock with elapsed host clock | Removes modeled per-instruction/cache charges, preserves guest OS/device deadlines | Promising diagnostic candidate, default off |
| Replay old recording strictly by poll number | Different clock changes real input durations | Invalid performance acceptance comparison |
| Replay by absolute recorded VI | Startup menu readiness differs | Invalid route comparison |
| Anchor timed replay at first gameplay pose | Start matches, long open-loop route later diverges into a different level | Do not claim the full-route FPS comparison as Goldwood proof |
| Load the same Goldwood checkpoint saved by the game | Same initial pose, 47 actor entries, two enemy entries, 27 shots each; median 49.96 to 33.61 ms across movement/firing, candidate p95 50.19 ms | Improvement, residual slow intervals remain |
| Change clock only after identical combat prefix | Full RDRAM, Count, VI and input poll identical at boundary; both remain level 21 | Stronger comparison below; still below target |
| Instrument native idle deadlines and wake-up times | Ordinary sleeps overshot by 1.247 ms median / 1.890 ms p95 over 1,868 observed gameplay waits; run then trapped | Scheduling cost demonstrated; incomplete run is not acceptance |
| High-resolution Windows waitable timer | Built after correcting Windows header-order macro pollution; native run trapped at VI 4098 on equal PI/SP/DP deadlines | Timer candidate remains diagnostic; event-order qualification is required |
| Inline native ordinary-instruction bookkeeping | Original 250,000-transition regression plus native no-time-charge / bounded-safepoint / hardware-exception boundary checks passed; runtime rebuild in progress | Avoid a full C++ callback per ordinary native instruction without dropping clock safepoints |

For seconds 1-21 after the identical combat boundary, reference median/p95 are
**67.88/97.78 ms**; candidate median/p95 are
**49.89/51.82 ms**. Median enemy-table count is seven in both.
Later state can diverge as changed cadence changes sampling; identical initial
memory does not imply identical future AI or frame-by-frame behavior.

## Actual resolution

**No final resolution yet.** `HostCountClock` in
[`include/jfg/boot/host_count_clock.hpp`](../../../include/jfg/boot/host_count_clock.hpp)
and its integration in [`native_boot.cpp`](../../../src/boot/native_boot.cpp) are a
private diagnostic candidate in the original combat investigation, enabled there
by `JFG_DIAGNOSTIC_HOST_CLOCK=1`. On 2026-10-12, the separate high-refresh preview
enables elapsed timing during play and qualifies a lighter bridge route; see
[PERF-002](frame-diagnostics.md#local-preview-delivery-2026-10-12). That local
delivery does not qualify this heavier fight or reopen the shelved PC/audio
investigation. No combat resolution or public release is claimed.

The candidate uses a steady clock at 46.875 MHz, preserves fractional timer units,
handles guest wrap with a 64-bit count, excludes frontend pauses, and services
normal hardware/OS deadlines. It retains game simulation and actor processing.
It does not multiply world speed, skip actors, or conceal drops with smoothing.

## Verification and open acceptance

- 148 clock checks and 18 recorded-input timeline checks passed; the nine targeted
  timing/input test executables passed together.
- Controlled movement is identical under both clocks: 243.04 world units/second
  forward/back and both strafe directions in the tested fixture.
- Held aim survives firing; shot counts agree in movement and Goldwood fixtures.
- Native Save changes only a copied test save; reload restores the saved 95-round
  pistol state. Source/live saves remain unchanged.
- Default reference-clock replay remains byte-identical to the retained baseline.
- Still required: consistent combat cadence, startup/cutscene/audio timing,
  overload and stall recovery, broader controller/input coverage, frontend pause
  and physical focus behavior, and owner verification of the fight and bridge.
- Large collision-driven camera pull-ins and unqualified pivot animations remain
  separate issues. A passed timing test does not resolve them.

Private artifact root: `combat-critical-evidence-20261011`, within the existing
`pc-input-aiming-20261008` guarded investigation. Preserve scripts, runtime hashes,
input/profile provenance and reports; do not publish ROM or personal save data.

## Lessons for other recomp projects and future 60+ FPS work

Distinguish elapsed real time, guest timer units, guest simulation ticks, VI,
rendered frames and presentation. An emulated CPU/cache cost model is a valuable
deterministic reference, but retaining its throughput ceiling as the native game
clock can preserve original slowdown despite abundant host performance.

A host-time clock is compatible with future higher-refresh rendering, but does
**not** itself make the simulation run correctly at 60+ Hz. Keep the game-speed
contract independent of render/present rate. Audit movement, animation, weapon
cadence, AI, audio and input for per-update assumptions before changing simulation
frequency. A possible later design renders interpolated transforms between fixed
simulation steps; camera collision, input latency, discontinuities and state
ownership still require their own design and tests. Do not blindly double ticks
or halve deltas. No interpolation or 60 Hz simulation is implemented here.

Use bounded catch-up and explicit pause/stall policy, not an unbounded backlog.
Timing-policy changes also invalidate poll-count-based real-time comparisons;
use matched checkpoints, time-based input with conserved mouse displacement and
short button edges, and report route divergence. Measure presentation/GPU and
actual update cadence independently; an FPS counter alone does not locate a cause.

Primary architectural references: [N64ModernRuntime timer](https://github.com/N64Recomp/N64ModernRuntime/blob/cdf5abbd5026fef5c364c676e4667c45e42b6863/ultramodern/src/timer.cpp),
[VI scheduler](https://github.com/N64Recomp/N64ModernRuntime/blob/cdf5abbd5026fef5c364c676e4667c45e42b6863/ultramodern/src/events.cpp),
[Perfect Dark timing](https://github.com/perfect-dark-pc-port/perfect_dark/blob/32a1cb9f268dd3ac73016801025c6bbbfa20130f/src/game/timing.c),
and [Fix Your Timestep](https://gafferongames.com/post/fix_your_timestep/).
These guide architecture; they are not drop-in fixes for this runtime.


### Follow-up: simultaneous device events and timer precision

The high-resolution wait run stopped at VI 4098: PI, SP and DP all had absolute
Count deadline 3243790045; current Count was 3243822106. This is an exact deadline
tie, not merely several different deadlines becoming overdue. The original
reference selector only qualifies SP-before-DP ties and deliberately rejects
other simultaneous-source combinations. The failure check remains in place.
Changing clock sampling exposes a native-runtime scheduling requirement that
must be resolved with an explicit, validated event contract. Arbitrary priority
changes or offsetting one deadline to avoid a tie would conceal the issue.

The Windows wait candidate uses a high-resolution one-shot waitable timer,
rounds the relative timeout up to 100 ns units, rechecks steady time after wake,
and keeps the original device deadline. It does not busy-spin or change game
speed. The API requires Windows 10 version 1803 or newer; unsupported creation
currently fails the diagnostic mode rather than silently claiming high precision.
See [CreateWaitableTimerExW](https://learn.microsoft.com/en-us/windows/win32/api/synchapi/nf-synchapi-createwaitabletimerexw)
and [SetWaitableTimerEx](https://learn.microsoft.com/en-us/windows/win32/api/synchapi/nf-synchapi-setwaitabletimerex).
Both recorded wait probes stopped before the route finished. Their partial
observations cannot qualify either a final performance improvement or a release.

The generated native inline rebuild did not complete within this build step; continuation required. Its focused tests passed; this
is not a performance acceptance result. The installed runtime hash was checked
and remains unchanged. Additional owner-approved work continues under the same
production guard and investigation with all prior charges retained.


### Continuation: native scheduling qualification

The owner approved two additional hours in the same investigation, preserving
all guard counters. The first generated inline rebuild exceeded its eight-minute
command budget. The continuation rebuild has its own bounded command inside the
same guarded investigation; this is not a new investigation or a counter reset.

The native event candidate commits all independent device completions sharing the
earliest due timestamp before the guest CPU observes an interrupt. Guest PI/SI
transfers already make their data visible at launch in the retained device
profile; their completion changes status/interrupt state. SP completion finishes
its owned task before the CPU runs again. The original reference policy remains
unchanged, including its rejection of unqualified ties. This is a separate native
elapsed-time contract, not a new claim of cycle-exact N64 timing parity.

Tests cover all nonempty device subsets and their input permutations, duplicate
sources, future/earlier deadlines, integer limits, actual PI/SI/SP completions in
all 24 orders, interrupt masking/acknowledgement, and unchanged reference tie
rejection. Integration and performance outcomes follow below.

- `finish-native-inline-runtime-build`: process exit 127 (zero alone does not establish performance acceptance).

- `native-inline-clock-goldwood-before-batch`: process exit 125 (zero alone does not establish performance acceptance).

- `native-event-batch-candidate`: process exit 125 (zero alone does not establish performance acceptance).

- `native-event-batch-test-build`: process exit 125 (zero alone does not establish performance acceptance).

- `native-event-batch-tests`: process exit 125 (zero alone does not establish performance acceptance).

- `native-event-batch-runtime-build`: process exit 125 (zero alone does not establish performance acceptance).

- `native-event-batch-goldwood-checkpoint`: process exit 125 (zero alone does not establish performance acceptance).

- `native-event-batch-combat-boundary`: process exit 125 (zero alone does not establish performance acceptance).

- `reference-event-batch-combat-boundary`: process exit 125 (zero alone does not establish performance acceptance).

- `compare-event-batch-combat-boundary`: process exit 125 (zero alone does not establish performance acceptance).

No completed matched combat comparison for this revision; acceptance remains pending.


### CPU versus GPU work

RT64 already renders on the GPU. The diagnosed clock charges, ordinary instruction
callbacks and device waits are CPU-side work. Moving AI/physics to GPU compute
would require data/layout and synchronization changes; it is not a demonstrated
remedy for this timing defect. Graphics submission timings do not establish GPU
completion latency. If residual stalls implicate rendering, measure GPU timestamps,
queue/fence waits and presentation separately before proposing further offload.

The guest stack transport also uses parked host OS threads with a single execution
baton. Context-switch overhead is a possible additional cost, not a confirmed
bottleneck in this recording. Do not replace it merely because fibers might be
faster; quantify the cost and preserve context, exceptions, sanitizer support,
thread-local state and guest scheduler behavior before changing the transport.


### Completed scheduling replay pass

The incremental build completed after the command timeout; completed objects
were retained and no original/generated game bodies were changed. The native
inline build without the event batch reproduced an exact PI/SP/DP deadline tie
at VI 3816. After adding the explicit native event batch, its 41,370 focused
checks passed and the saved Goldwood movement/firing replay completed.

Matched combat prefix memory, Count, VI and poll equality: **True**.

- Reference seconds 1-21: update median **67.79 ms**, p95 **98.69 ms**; final audio counters [19124224, 19117568, 8, 0] (queued/consumed/underflows/overflows).

- Native seconds 1-21: update median **50.01 ms**, p95 **54.91 ms**; final audio counters [19124224, 19113728, 2, 0] (queued/consumed/underflows/overflows).

Windows timer deadline/reuse/lifetime check process exit: 0.


The owner approved six additional hours on the same investigation. This does not
reset counters, disable the production guard or change the installed preview.
Critical acceptance remains open until residual costs and the listed regressions
are qualified. Supporting replays alone are not a release claim.

## High-refresh visibility preview combat follow-up (2026-10-13)

The owner frequently sees 20-25 SCENES while fighting Goldwood drones despite
120 OUTPUT in visibility preview `c9189c1` (runtime SHA-256
`cb3de8f6593fa2abb0a12e7a2ea7f98ecf23ea817ad247505c1338a39dcd2292`). Drones and gems
now look good, but this scene-cadence drop destroys the smooth result. Critical
combat acceptance remains open. This report is in the current elapsed-clock
high-refresh build, so the original modeled-clock contributor alone cannot
explain it. Measure host work, renderer waits and the game's 31-update recovery
rule without forcing simulation speed or hiding drops in the counter.

One owner-approved guarded continuation in the existing high-refresh investigation
runs within the prior deadline. This does not reopen the PC/audio investigation.
Current before/after evidence will be recorded here; no new fix is yet claimed.

The normal 120-cap copied-checkpoint combat replay reproduces 19.8-22.1 scenes/s
through the fight. Diagnostic elapsed-clock samples show repeated genuine fast
frames while the guest remains in its 31-fast-frame recovery hold. Candidate:
seed only the native 20-Hz recovery counter to its threshold before viFrameSync;
the original late-frame test, VI waits and returned elapsed interval stay intact.
This allows the next genuinely fast update to restore 30 Hz and still preserves
real overload. Reference instruction-clock execution remains unchanged.

The first CPU-cost wrapper incorrectly combined the diagnostic option with Play,
which the runtime rejects (exit 3). Its ownership assertion masked that status;
a repaired wrapper recorded it. The corrected finite native-clock diagnostic
omits screenshot/memory captures. These failed requests are retained, not passes.


The recovery-only ordinary Play replay improves the four measured windows from
19.8/19.8/22.1/19.6 to 27.4/26.9/23.9/25.2 scenes/s, with zero audio underruns.
This is a partial improvement, not sustained-30 completion. Source diagnostics
also observe roughly 4,600-6,000 full CPU/device probes per update because native
elapsed time is sampled every 128 ordinary guest instructions. A controlled
candidate tests a 512-instruction quantum. Per-instruction IO revision, exception,
interrupt and deadline checks remain; no modeled clock or guest timestep is
changed. Reference-mode and both sampling-boundary policies need qualification.


The clean recovery/particle runtime with the existing 128-instruction quantum
measures 29.47/29.78/29.83/27.31 scenes/s across the same four windows. The 512
experiment measures 29.38/23.49/24.78/28.01; it does not establish a benefit and
is rejected. Host-load/route variability limits attribution. Restore 128 for
delivery; retain the boundary tests and failed-hypothesis evidence. Do not claim
that reducing clock polling fixed combat. Real overload and full-game live
acceptance remain open, even though removing the sticky recovery helps.


## Retained correction and final qualification (2026-10-13 UTC)

Native elapsed play now primes only the 20-Hz recovery counter before the
supported US viFrameSync function. The original function still measures queued
VIs, rejects late work, waits for its deadline and returns real elapsed time.
The 31-consecutive-fast-frame hold was a demonstrated contributor to prolonged
20-Hz episodes. This does not force 30 Hz or accelerate the simulation clock.
The original instruction-clock reference path is unchanged. Genuine overload
remains visible. The 512-instruction sampling experiment was rejected; 128 stays.

Final runtime `14746717614559b93fa535f9caf0a02fce50f23d2df3ab23aa6e9302607f30aa`. Ordinary muted Play at Custom 120/VSync:

| VI window | Before SCENES/s | Final SCENES/s | Final OUTPUT/s |
|---|---:|---:|---:|
| 4000-4500 | 19.83 | 26.79 | 117.92 |
| 4500-4800 | 19.79 | 25.18 | 117.32 |
| 4800-5400 | 22.14 | 23.98 | 112.34 |
| 5400-5800 | 19.62 | 24.33 | 111.61 |

These bounded copied-checkpoint results are not a sustained-30 guarantee or
full-combat acceptance. Different native timings can affect an open-loop fight,
and host-load variation was significant. Nine focused C++ suites pass. Final
Original guest/renderer/save state matches exactly, native timing begins after
an identical reference prefix, and a deliberate 250-ms overload remains visible.
Pause/resume is qualified. Normal final audio underruns (120/360): 8/62.

The first recovery test build stopped on narrowing warnings; explicit bounded
casts corrected the test. A particle build stopped on local shadowing and was
corrected. A restored-source executable hash assertion also stopped a request;
no binary identity was assumed afterwards: all final replays identify the actual
rebuilt artifact. These informative failures remain in the private manifest.

Transferable lesson: distinguish mandatory elapsed-time handling from historical
console recovery hysteresis. Raising OUTPUT cannot compensate for delayed scene
production, and dropping polling frequency is not a demonstrated optimization.
**Status remains critical/open, partial correction qualified; owner live review
and further genuine host-cost work remain.** No public release.
See [qualification](../../../evidence/combat-particles.json) and
[particle issue](pickup-particle-desync.md). Large private evidence stays on D:.


### Performance acceptance remains open

The final combat runs record **8 audio underruns at 120 and 62 at a 360 target**.
These are observed failures of sustained smooth playback, not passing performance
acceptance. The earlier recovery runs had zero; the initial old preview had five.
A separate modern-controls-camera-collision runtime was observed active at
10:46-10:47 UTC. Earlier overlap was not fully recorded, so its contribution to
all timing samples is unproven. No owner process was stopped. A controlled
single-runtime comparison remains necessary before attributing the late audio
difference to this change or claiming sustained 30/360 performance.

Functional/state/pixel checks pass, while combat remains critical/open and this
preview is a partial correction. Preserve both successful and failed measurements.


## Delivery held for performance verification

The implementation is ready for review, but the desktop shortcut and installed
visibility preview remain unchanged. Final combat has real drops and 8/62 audio
underruns at 120/360; late concurrent-runtime load prevents clean attribution.
The post-pause trace has 988 samples, no repeats/rewinds, and three skipped phase
steps. Functional/state/pixel verification does not establish smooth performance.
Do not replace the working preview or call combat fixed until a controlled
single-runtime comparison resolves this. Both candidate sources and all evidence
are preserved. The next bounded run should first coordinate exclusive runtime
testing, compare unchanged/candidate builds on the same copied checkpoint, then
profile remaining host execution/renderer costs if genuine drops persist.
