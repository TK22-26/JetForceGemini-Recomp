# PERF-001: Goldwood combat slows game updates

- **Severity: critical. Status: open; bounded local previews qualified, but the owner full-tutorial capture still has source-cadence drops. Combined develop/high-refresh bounded qualification passed and the local preview is delivered; full-route acceptance remains open.**
- Reported: 2026-10-11 UTC. Last updated: 2026-10-13 UTC.
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

The reference execution policy charges Count for modeled N64 instruction and cache
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

**No final resolution yet.** The local Modern Controls Preview now uses the
qualified native elapsed-time clock and contiguous instruction spans. Its v1.1
launcher and saved profile are unchanged. See the [final candidate measurements
and acceptance](#contiguous-candidate-qualification-and-handoff) below.

`HostCountClock` in
[`include/jfg/boot/host_count_clock.hpp`](../../../include/jfg/boot/host_count_clock.hpp)
and its integration in [`native_boot.cpp`](../../../src/boot/native_boot.cpp)
remove modeled console CPU/cache costs from the private interactive build's
timeline. The explicit `JFG_EXPERIMENTAL_NATIVE_PLAY_TIMING` build option remains
off by default; reference probes retain their deterministic instruction clock.
No release or fix commit is claimed. Residual slow updates and live acceptance
remain open.

The separate high-refresh preview first enabled elapsed timing during play on
2026-10-12; see [PERF-002](frame-diagnostics.md#local-preview-delivery-2026-10-12).
Historical results below identify their specific build/profile. They do not
prove a full-tutorial fix or reopen a shelved investigation.

The candidate uses a steady clock at 46.875 MHz, preserves fractional timer units,
handles guest wrap with a 64-bit count, excludes frontend pauses, and services
normal hardware/OS deadlines. It retains game simulation and actor processing.
It does not multiply world speed, skip actors, or conceal drops with smoothing.

## Initial verification and acceptance history

These initial results and outstanding checks describe the first clock candidate.
Later sections record subsequent checks, failures and current acceptance.

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

Implementation commit: 83cd8af0bad951d27939adadb74f374840d1303d. The committed build retains
qualified runtime 14746717614559b93fa535f9caf0a02fce50f23d2df3ab23aa6e9302607f30aa.
A copy is retained in the private D: evidence directory. Desktop delivery is
held pending the controlled performance comparison above; no release was made.

## Three-hour combat continuation (2026-10-13 11:47 UTC)

Owner approved three hours to fix combat drops. Same production investigation,
root and accumulated charges retained, guard enabled. Candidate 83cd8af remains
held for performance acceptance. First compare installed preview and candidate
with no other JFG runtime, monitoring process overlap throughout. Large evidence:
D:/JFG-private/high-refresh-20261011/combat-isolated-20261013. Tests muted, hidden,
1600x900, copied Goldwood save and identical input/settings. This records work in
progress, not a completed fix or delivered result.

First isolated runs: installed preview 24.74/29.27/29.84/25.01 and
27.97/26.66/29.86/27.43 SCENES/s; held candidate 29.77/29.46/29.71/29.63.
All had zero audio underruns. The fourth comparison overlaps a separate
modern-controls-camera-clearance runtime and is excluded from performance
acceptance. No foreign process was stopped. Dependent requests stopped on the
failed isolation prerequisite; no source import or build ran. Resume source
integration using the three valid runs, repeat performance after isolation.

Ported CPU eligibility caching, bounded native instruction spans and exact
clock transcript support from develop 9a6e6781975610ef59811f29355eba01d2d07d19. All original guest
operations and 128-instruction clock safepoints remain. This is a candidate;
the new integration still requires differential tests and replay qualification.
The import script assumed a blank line after the final CMake test target and
stopped after writing source; a follow-up added the target using its actual EOF.
No partial import was built. Dependent builds correctly stopped. Entry-offset
lookup metadata remains a separately measured optimization to consider.

The full CPU rebuild was canceled before its resource limit. A frozen copy of
the prior completed archive supplied 2,909 unchanged generated bodies, after
matching generated source/header text, recorded compiler flags/toolchain and
dependency ages. Wrappers/runtime use this checkout; normal object-shape and
link audits stay enabled. First cache scripts stopped on a concurrently changed
project, path-comparison error, replaced wrapper log, then an MSBuild output-log
filename variation. No failed cache request counted as validation. The repaired
build and two focused timing suites pass; game/performance validation follows.

## Native CPU candidate qualification

The imported cache/span optimization removes repeated host bookkeeping around
ordinary generated instructions. Groups contain at most 16 safe operations;
dynamic RAM checks, branches, device accesses and observers retain the checked
fallback. All guest operations and the 128-instruction clock sampling quantum
remain. The 31-fast-frame recovery correction and particle identities are kept.
This is a CPU optimization, not a forced game timestep or changed FPS counter.

Ten focused C++ suites pass, as do six generator tests including 4,096 compiled
RAM/MMIO pairs. Original guest/renderer/save state matches the reference exactly.
Native transcript replay matches 2,606,049 clock observations and the final
guest/renderer/save state exactly, with 145,817,191 instructions using spans.
Those transcript runs are not performance evidence; recording adds overhead
and the replay deliberately follows recorded time rather than wall time.
Pause/resume preserves the clock boundary, and injected 250-ms overload remains
visible. The post-pause trace has 1,000 samples, no repeats, backward phases or
uneven phase steps. These are bounded software checks, not monitor scanout.

The MSVC generator-test fixture initially failed Windows batch quoting after
its source edit; the repaired invocation ran all six tests without skips.
An initial performance preflight treated idle MSBuild node-reuse helpers as
active load. Its owned waiting process was canceled before any benchmark.
The replacement blocks actual compiler/linker/game processes and retains all
guard charges. A read-only job-accounting query reports the current innermost
Windows job; it is not proof of the supervisor's aggregate remaining allowance.

**Candidate functionally qualified; isolated performance, delivery and owner
live acceptance remain pending.** A separate controls task is running replays;
no foreign process was stopped. See [candidate evidence](../../../evidence/combat-native-spans.json).
Keep the production guard enabled and retain the same investigation/root and
counters on handoff. Large private artifacts stay on D:.

Build compatibility: native preview builds now require a generated span root;
ordinary/reference builds retain their default behavior. After fresh private
normalization and original timing setup, call
scripts.original_timing_generation.finish_native_spans(root) once before
building with JFG_EXPERIMENTAL_NATIVE_PLAY_TIMING=ON. Never apply it twice or
copy a header over stale generated bodies. Frozen-object reuse here separately
verified all 2,909 body sources, their included headers, compiler flags/toolchain
and dependency ages; fresh wrappers/support and normal object audits were kept.
Transferable lesson: separate game-state/clock equivalence from performance,
and never compare frame rates while another game or compiler is competing.

## Controlled combat qualification and local delivery

| Run | SCENES/s by combat window | OUTPUT/s by combat window | Audio underruns | Median update wall time excluding clock wait |
|---|---|---|---:|---:|
| prespan-120-a | 29.83 / 29.78 / 29.84 / 29.77 | 119.67 / 119.94 / 119.88 / 119.68 | 0 | 22.522 ms |
| spans-120-clean-a | 29.82 / 29.79 / 29.83 / 29.75 | 119.76 / 119.95 / 119.83 / 119.60 | 0 | 21.945 ms |
| spans-120-clean-b | 29.83 / 29.79 / 29.84 / 29.80 | 119.91 / 119.95 / 119.87 / 119.65 | 0 | 21.442 ms |
| spans-360-clean | 29.80 / 29.73 / 29.81 / 29.68 | 358.13 / 359.55 / 355.88 / 352.77 | 0 | 22.058 ms |

Controlled performance qualification completed after the competing controls
tests ended. Two clean 120/VSync runs and one 360/no-VSync run each maintained
29.68-29.84 SCENES/s across the measured combat windows, with zero audio
underruns. Output was 119.60-119.95 at the 120 target and 352.77-359.55 at the
360 target. One 3-VI update occurred in the first 120 run and one in the 360
run; all other measured updates used 2 VIs. No sustained 20-25-Hz episode
recurred. This qualifies bounded local combat cadence, not perfect pacing,
physical scanout, all computers, every encounter or sustained exact 360 FPS.

The original installed preview's valid comparison windows ranged from 24.74
to 29.86 SCENES/s. The recovery-only build already held about 29.8 in its clean
repeat. Native span batching reduced median update wall time excluding explicit
clock wait from 22.522 ms there to 21.945 / 21.442 ms in the two 120 runs.
That is modest observed headroom, not a claim that batching alone removed the
20-Hz hold. These times also include renderer/OS work; open-loop fights can
diverge with native timings. The demonstrated recovery hysteresis fix is the
main explanation for avoiding prolonged 20-Hz episodes.

The first new-CPU comparison overlapped another controls replay and was excluded,
even though its audio counter was zero. Its process evidence and result remain.
Two-minute quiet preflight and continuous JFG/compiler/linker process sampling
qualified the final three runs; this is not whole-system load control.

Delivered locally as high-refresh-combat-spans-20261013 on D: through **JFG - High Refresh Preview**.
Implementation a93faa5ef61b86536327ffa83d48fc95835a21ff; runtime e7e3af29fd9aeec9e037da93a27d0e50272ba7bbb6b4ac77eb5f6536dd2d6fc5.
All 14 manifest files and isolated muted launcher initialization verify.
The existing owner save/settings and shortcut arguments are preserved. Tests
were muted and used copied saves. The earlier pickup-particle correction is
included. No public release. **Owner live verification and broader combat/game
coverage remain open.** See [qualification](../../../evidence/combat-native-spans.json).

## Owner tutorial capture after delivery

The 2026-10-13 manual log-only Custom 120/VSync run still contains genuine scene
cadence drops: 20.16 submissions/s over elapsed 7:15-7:35, and 21.61 then 24.85
over 10:45-10:50 and 10:50-10:55. Output averages 110.05, 116.45 and 114.85
respectively. The owner reports jitter on crates, an exit light and a bridge
in the later cave/bridge area; exact room-to-log timing is unavailable.
The qualified short combat comparisons are not withdrawn, but they do not
generalize to this route. No new cause or remedy has been established.
See [RENDER-006](tutorial-late-object-jitter.md) for evidence, limits and the
unchanged production guard state. This review ran no new gameplay experiments.

The separate entry-offset optimization is now imported from 9a6e6781975610ef59811f29355eba01d2d07d19.
The controls investigation measured 666,854 lookup probes and 2.661 ms per
combat update before its remedy, falling to 57 probes and 0.0028 ms there.
Those are prior measurements, not new high-refresh performance results. Here,
three dispatch paths now use offsets published with the same function pointer
and overlay lifetime, instead of scanning preceding instructions. Fresh private
normalization and unchanged game-body verification precede build acceptance.

## Controls investigation history imported from develop

The following measurements belong to the separate controls investigation and
its documented fixtures; they are not qualification of the combined build.

### Instruction-call overhead and GPU measurement audit

The first scheduling revision completed both Goldwood tests. The simpler fixture
held roughly 33.3 ms per frame body, but the matched fight still had a 50.01 ms
median / 54.91 ms p95 update interval (reference 67.79 / 98.69 ms). About 13.0% of
the measured combat wall-time window was spent inside graphics submission; its
full-sync portion was about 6.5%. Those nested values must not be added together.

An opt-in CPU-cost trace then measured 56.74% of guest instructions entering an
out-of-line runtime callback, while only 0.80% entered the full clock/device
handler. Most of those calls therefore performed ordinary instruction bookkeeping.
These are instruction fractions, not fractions of runtime. Whole-process CPU
time includes renderer/helper threads and is quantized; use aggregate values.

The instrumented run itself had a 33.87 ms median / 50.54 ms p95 interval. This
variation from the preceding uninstrumented run means a single favorable replay
cannot prove a performance fix. Compare independent runs with matched initial
state, and compare uninstrumented behavior with instrumented behavior.

The ordinary RT64 workload-profiler snapshot returned no available samples.
Missing samples are not zero GPU cost. The synchronous framebuffer render-to-RAM
path has a separate graphics worker; the regular workload profiler is insufficient
to characterize it. Direct measurement must put timestamps on that worker and
resolve them after its existing fence, without adding another GPU wait.
CPU full-sync timing includes submission, synchronization and readback and is
not interchangeable with GPU execution duration.

The next native candidate inlines the compact bookkeeping path in large generated
functions as well as small ones. It retains the same bounded host-clock sampling,
hardware revision, interrupt, exception, observer and instruction-budget checks.
It does not omit guest instructions or actor work. The original cache/Count model
and its selector remain available for reference comparison.

The new path passed 65,536 differential native transitions alongside the 250,000
reference transitions. A warnings-as-errors failure for a shadowed variable in
the new test was corrected before the runtime rebuild was admitted. The generated
support-header and previous executable hashes were archived; game code bodies
were not edited.

All compared combat prefixes equal: **True**.

- native-event-batch-boundary: median 50.01 ms, p95 54.91 ms, 335 updates over 40 ms / 430 samples.

- native-cpu-gpu-cost-boundary: median 33.87 ms, p95 50.54 ms, 206 updates over 40 ms / 497 samples.

- native-all-inline-boundary: median 50.13 ms, p95 54.16 ms, 398 updates over 40 ms / 399 samples.

- native-all-inline-cost-boundary: median 50.14 ms, p95 54.02 ms, 395 updates over 40 ms / 402 samples.

Reference full-replay RDRAM SHA-256: `757b7094a9d6fabd671e4c90ba7d50e54a52741d3e7ff3ffb57df3f062b93d99`.

The critical issue remains open; installed preview unchanged. Pause/stall, audio, startup/cutscene, movement, Save/reload and owner live verification remain part of promotion acceptance.


### Scheduling phase handoff and bridge comparison

The all-function inline candidate reduced out-of-line instruction callbacks from 56.74% to 0.924%, but both new combat replays remained near 50.1 ms per update (about 20 Hz). It did not solve the remaining slowdown. Reduced callback count is not a demonstrated performance improvement. Preserve the result and measure remaining handler, renderer and execution costs before choosing the next remedy.

Hidden runs so far used a 640x480 surface. The owner recording ended at 1164x873; subsequent GPU comparisons must match that size. Hidden rendering still does not qualify visible presentation/VSync latency.
The late-bridge comparison did not complete; preserve the failed/skipped command outcomes and do not claim acceptance.

The installed preview hash remains `059328317aeedccf1342156b884a6b8221573acd7f669636744649d8669f3cdd`. The native timing policy is diagnostic and default off. The next authorized phase measures the synchronous GPU framebuffer queue and validates pause/resume and host stalls before any promotion. The critical issue remains open.


### Hidden pause fixture correction

The first hidden pause attempt received no acknowledgement: the ordinary non-play probe does not service frontend window commands. This is a harness limitation, not evidence of a broken interactive pause. The existing hidden real-time replay flag was restricted to the older cooperative runtime. Its validation now also admits the unified guest OS when that runtime owns pacing; the shared window service returns before the cooperative frame pacer, preventing double pacing. The corrected bounded fixture remains hidden and uses copied saves, without foreground or physical input changes. Acceptance awaits the corrected run.

The reference bridge replay reached its requested ending, then failed at `guest-capture/final-image`; the paired comparison was skipped. This diagnostic capture failure is retained and not counted as gameplay/timing acceptance.


### Direct GPU measurements and timing qualification

The direct synchronous framebuffer GPU measurement returned valid timestamps:
1,195 submissions over 19.98 seconds occupied 42.37 ms of GPU execution in total
(0.21% of wall time), averaging 0.0355 ms per submission. The remaining combat
update interval was 50.14 ms median / 54.23 ms p95. This rules out that measured
GPU command interval as the dominant cost; it does not measure the separate
regular workload/presentation queue. CPU graphics submission, including its
existing waits, remained about 5.59 ms per update. The native clock/device handler
prefix contributed about 2.68 ms per update after excluding measured waits and
graphics submission. These nested measurements must not be added indiscriminately.

The corrected hidden real-time pause fixture held the guest clock at the same VI
for a 1.263-second frontend pause (four Count ticks of measurement separation),
then resumed at 30 updates in the first second. Held aim survived firing five
shots; saving modified only the copied fixture. Reload is checked separately.

Injected 250 ms and 2,000 ms host stalls exposed overdue video-interrupt delivery
in a burst: respectively 74 and 179 VI events in the following second, with many
within the first millisecond. Gameplay completed without a fatal error, but this
is not acceptable missed-deadline qualification. Native timing remains default
off until the overdue-event policy is corrected and rechecked.

The first capture-size tests stopped before gameplay because Windows produced a
1160x863 client rectangle from an estimated 1164x873 request. The harness now
corrects dimensions using the measured owned hidden window rectangle, without
showing/focusing it. Failed cases remain archived; only a confirmed final surface
size will count as a size-matched GPU comparison.

Source inspection found three dispatch paths that scan every preceding instruction
address to identify a generated relocation's alternate entry point. Per-call
lookup cost is being measured before selecting a remedy. Generated lookup tables
change at overlay lifecycle boundaries, so any cached resolution must preserve
publication, rebasing and invalidation semantics; a blind address cache is unsafe.


### Generated entry lookup cost and remedy

Diagnostic-only measurements found a median 666,854 table probes across 54
relocation-entry resolutions per combat update, costing 2.661 ms (5.3% of the
20-second measured wall-time window). Each dispatch searched every preceding
instruction address to discover whether its target was an alternate entry into
a generated function. The generator already knows that identity.

The candidate now emits each continuation offset with its function-table entry.
That offset is published, rebased, invalidated and collision-selected together
with the corresponding function pointer. Dispatch retrieves the metadata instead
of searching prior addresses. This removes repeated work without changing guest
code, instruction costs, timers or actor simulation. It is one measured overhead,
not a complete explanation of the remaining 50 ms update interval.

The compiled synthetic test exercises normal and alternate entry execution,
1,000 rebase/unload cycles, exact address collisions, misses and reload. It and
the 17 existing generator tests passed. The stale-normalizer build check first
rejected an incomplete incremental support update. Full regeneration then used
the original qualified recompiler header; 5,821 game and shared-header files
were verified byte identical before support/inventory synchronization. The
normalizer revision check remains enabled. Matched performance and full reference
RAM parity checks are separate acceptance requirements.

The pause Save reload also passed: all 250 observed post-load weapon states
retained the saved 95-round count; the source save remained unchanged.

The second surface-size attempt was still one pixel short because the inspecting
process used a different DPI-awareness context from the owned runtime window.
The revised fixture uses that window's DPI context for both sizing and
measurement. These failed size checks did not count as GPU evidence.


### Entry metadata validation, CPU samples and missed video deadlines

The entry metadata remedy passed the full 17,000-VI reference replay with the
same final 4 MiB RAM hash as the earlier reference:
`757b7094a9d6fabd671e4c90ba7d50e54a52741d3e7ff3ffb57df3f062b93d99`.
Candidate executable: `266aa9d0b459e80b36c73bc550877fd2b304490134d146c5cb044b9d03b5e67f`.
Median resolution cost fell from 2.6605 ms / 666,854 probes per update to
0.0028 ms / 57 probes. The combat update median still measured 49.991 ms
(p95 51.308 ms); this is a verified local optimization, not resolution of PERF-001.
Both comparisons began with the same RAM hash at the clock switch. Subsequent
native-time trajectories may differ, so later work totals are not identical inputs.

The generator's object-shape audit initially rejected two exported functions in
one support object. The compatibility lookup wrapper now occupies its own
support source/object; the entry table has one exported metadata accessor.
The audit accepts only the specifically named new accessor in addition to the
two existing lookup roles, while retaining the one-function-per-object rule.
Synthetic tests cover both old and new inventories and reject unrelated extras.
The stale-normalizer, header-lineage, line-ending and object-shape failures are
retained as evidence; no qualification check was bypassed to obtain a build.

The corrected DPI fixture confirmed a 1164x873 hidden client surface and final
capture. Native synchronous framebuffer GPU work occupied 44.91 ms over 19.969 s
(0.225% of wall time; 0.0351 ms/submission). Reference was 27.95 ms over 19.949 s
(0.140%; 0.0348 ms/submission). These measure that command list only. Regular
rendering/presentation GPU cost and visible VSync latency remain separate.

Owned-process CPU sampling collected 1,089 passes over 18 seconds without a
failed sample. On the hottest game thread, 248 of 298 samples attributed to
generated source landed on instruction timing hooks (83.2%). The thread used
6.531 s of user CPU and 0.344 s of kernel CPU. Waiting samples are not CPU cost;
optimized PDB attribution and sampling cadence can bias source attribution.
This is evidence to investigate per-instruction bookkeeping, not proof that
83% of whole-process time is spent there. GPU offloading is not indicated by
these CPU bookkeeping measurements.

The next candidate caches the metadata-independent eligibility predicate at
the full timing handler. Every instruction still checks live CPU Status,
hardware revision, bounded poll budget, FPU availability and metadata boundaries.
CPU register writes and ERET explicitly invalidate it; instruction-limit
remaining allowance caps the next poll budget. It keeps instruction/branch
accounting and the reference cache model, and never skips game logic. Differential
tests, full reference parity and matched combat measurements are required before
calling it a performance improvement.

Native periodic VI scheduling now latches one pending video interrupt and
advances its next deadline over all elapsed edges while preserving phase. It
does not advance Count, replay missed game updates or change reference timing.
VI_CURRENT uses bounded periodic phase even before an overdue event is serviced.
88,126 unit checks passed, including overflow, phase, missed periods and the
existing equal-time event-batch checks. These rules also avoid a burst of old
video messages after a future higher-render-rate build stalls; they do not
implement 60 Hz game simulation or interpolate animation/camera poses.

Private evidence: `native-coalesced-stall-250`; verification result remains in the guarded command spool.

Private evidence: `native-coalesced-stall-2000`; verification result remains in the guarded command spool.

Both injected stalls passed: 250 ms resumed with 60 video events in the next
second; 2,000 ms resumed with 61, compared with 74 and 179 before the fix.
Each had one video event within the first 2 ms. Count continued to track actual
elapsed time to within 0.002 ms of the logged wall interval. The 2-second fixture
is allowed to underflow audio while the entire host thread is deliberately
stopped; this is not a claim of uninterrupted audio through a frozen process.

All fixtures used copied profiles/saves and hidden owned windows. The installed
preview remains unchanged and native timing remains diagnostic/default off.
PERF-001 remains CRITICAL OPEN; final controls, startup/audio, pause/save,
stall regressions and owner live verification are still required for promotion.


### Cached eligibility qualification and rejected Count-store experiment

The cached eligibility candidate built and passed 250,000 reference and 65,536
native transition checks, including Status/I/O invalidation, FPU and metadata
boundaries, bounded clock sampling and instruction-limit refusal. Its full
17,000-VI reference replay still produced RAM SHA-256
`757b7094a9d6fabd671e4c90ba7d50e54a52741d3e7ff3ffb57df3f062b93d99`.
Runtime SHA-256: `2e52d24adc2e5f5707b06d13e66059e757bc20dd97ea71bb7172f9420c478fcb`.

This change did **not** resolve the remaining combat slowdown. The unprofiled
matched-boundary run measured 50.115 ms median / 54.590 ms p95, with 382 of 408
updates exceeding 40 ms. The instrumented sibling measured 49.094 / 53.829 ms.
Both began with the qualified identical combat prefix. Two- and three-VI update
intervals remain; later native-time AI/input trajectories can diverge.

Two Clang synthetic benchmarks had substantially different results: a 32-hook
same-translation-unit body improved about 1%, while a 1,024-hook body with state
and fallbacks compiled separately improved about 73.5%. Both body size and
compilation boundaries changed, and the actual runtime uses MSVC. Those figures
are not gameplay speedup evidence. The actual replay result takes precedence.

A separate, isolated MSVC /O2 experiment compared the current native helper with
removing its redundant Count mirror write. Across eight alternating pairs of
64 million synthetic hooks, medians were 227.563 ms and 229.964 ms (candidate
1.01 times baseline). There was no demonstrated benefit; the runtime source
retains that write. Do not convert a plausible optimization into an accepted fix
without relevant measurements.

The 200-second cold-start/title/attract fixtures completed under both clocks.
Both produced nonzero 22,018 Hz PCM, no recorded host-audio underruns or empty
queue pauses, and preserved the source save. Native PCM duration was 200.446 s;
reference was 200.463 s. This verifies delivery/content presence, not audible
quality or visually judged cutscene synchronization.

Next diagnostics distinguish the generated-dispatch prefix, repeated overlay
inventory validation and regular GPU workload from the previously measured
synchronous framebuffer GPU queue. Regular-workload observations read RT64's
existing timestamp results after its existing fence on the owning worker;
a synchronized snapshot avoids racing its profiler. No extra GPU wait or guest
workload is introduced. Prefix measurements are nested and must not be summed
as independent costs. The separately recorded final-image probe failure is
[DIAG-001](final-probe-frame-capture.md).

PERF-001 remains **CRITICAL OPEN**. The installed preview is unchanged and the
native timing policy remains diagnostic/default off. Hidden qualification does
not replace the owner's reserved physical-input/focus and fight/bridge checks.


### Separate regular GPU and dispatch observations

Runtime `00c1dfaeae5d2f4e12242a69326c531df5edadb010127d5a461d9506a4318434`
measured both existing GPU command intervals. Over the matched 20-second combat
window, 981 synchronous-framebuffer submissions totaled 32.790 ms (0.164% of
wall time), and 650 regular workloads totaled 16.189 ms (0.081%). Mean command
intervals were 0.0334 and 0.0249 ms. These measurements do not include the wait
before a GPU's first marker, visible VSync or desktop presentation latency.
They provide no reason to move CPU bookkeeping to the GPU.

Generated-dispatch prefix timing measured 3.309 ms median per update across
16,756.5 calls. Overlay-inventory validation is nested within that prefix:
0.769 ms and 3,640 checks. Never add those nested measurements. Instrumentation
and host scheduling affect this run, which measured 64.64 ms median updates;
unprofiled repeats take precedence for gameplay-cost claims. The next unprofiled
run measured 45.860 ms median / 54.338 ms p95, with 256 of 470 updates above 40 ms.
The matched reference sibling measured 67.883 / 98.999 ms, with all 267 updates
over 60 ms. Later native/reference actor and RNG paths can differ. This remains
partial improvement, not a fixed 30 Hz combat update rate.

Private evidence: `native-remaining-costs-boundary-detailed-costs.json`,
`certified-combat-comparison.json`, and `certified-bridge-comparison.json`.
The final-image failure is independently verified under [DIAG-001](final-probe-frame-capture.md).

### Control verification corrections and bounded native span candidate

Initial qualification checks made two invalid assumptions: positive expected yaw
for rightward stick input (the implementation uses negative yaw), and that VI
messages delivered by an update's completion equal the movement time consumed
inside that update. Both clocks had the same turn sign. Completion can straddle
an asynchronous video interrupt, and elapsed video edges can be coalesced.
Preserve those failed checks as test defects, not evidence of changed speed.
The trace now records the actual tick argument consumed by `controlPlayer`.
Replacement checks fit displacement and turn angle against accumulated movement
ticks, while separately reporting wall-time and delivered-VI rates. Save/reload
qualification previously skipped because of the failed prerequisite; it must
actually run and pass before being claimed.

The next candidate consolidates native timing bookkeeping across at most sixteen
straight-line instructions. Every guest operation and every original timing hook
remain in generated source; the reference path uses its original hook sequence.
Native admission reserves the full span within the existing sampling quantum.
Branches, labels/alternate entries, CPU register operations, callbacks, observers,
CACHE and exception boundaries end a span. Each memory operation dynamically
checks the full-width address, cached RDRAM extent and alignment. MMIO, uncached
aliases or other addresses first commit the executed prefix, then use individual
hooks before the access, preserving trap PC/Count/branch metadata. Hardware I/O
revision changes originate in that guarded MMIO path, not asynchronous render
callbacks. FPU admission retains the live availability check.

This is an internal opt-in experiment, requiring both native timing and generated
span support; release generation and the preview do not enable it. Synthetic
helper and compiled RAM/MMIO fallback equivalence, original hooks/labels inventory,
full reference RAM parity and same-binary alternating combat runs are required.
Building it is not proof of a performance gain. No actor, collision, animation,
movement or camera work is skipped. Future 60+ Hz rendering still needs separate
simulation/interpolation work; bounded instruction safepoints remain required.


### Conditional native-span qualification (2026-10-11)

Candidate runtime `43e65779b7cbd5da3dbcb5d61f392b57d0675dcd69165c473d08bb63f2f65b2b`
passed the complete 17,000-VI reference replay with unchanged final RAM
`757b7094a9d6fabd671e4c90ba7d50e54a52741d3e7ff3ffb57df3f062b93d99`.
Generated spans retained all 424,827 original hooks and existing labels;
46,829 spans grouped 237,742 instructions with 110,267 dynamic memory guards.

Same-executable ABBA combat measurements, over 20 seconds after the identical
qualified initial state:

| Spans | Updates | Median ms | p95 ms | Updates over 40 ms |
| --- | ---: | ---: | ---: | ---: |
| Off | 466 | 49.427 | 53.759 | 267 |
| On | 557 | 33.585 | 50.287 | 83 |
| On | 502 | 34.001 | 50.515 | 193 |
| Off | 454 | 49.825 | 53.094 | 289 |

The optimization reduces repeated host bookkeeping; no game work is skipped.
About 56.6% of executed combat instructions used admitted spans. Results remain
variable: the repeated enabled run still spent part of combat near 50 ms per
update. The median is not an average frame rate. Changed clock cadence can
alter later input sampling, AI and RNG; these are performance comparisons, not
proof of identical later gameplay state. PERF-001 remains **CRITICAL OPEN**.

A qualification instrumentation error was also caught: the first replacement
movement checks expected a fifteenth trace field that an earlier build did not
actually emit. The source edit had been appended to a private installer after
it ran. Those checks failed and dependent save/reload checks skipped. This
candidate actually includes the consumed movement-tick field; its replacement
checks must pass independently. Failed attempts remain in the private evidence.

A diagnostic clock transcript records exact native-clock observations keyed by
instruction ordinal, PC/opcode and idle deadline. Replaying the transcript with
spans enabled must consume every observation and produce identical final RAM,
Count, instruction total and save. Replay rejects mismatched keys, truncation,
backward time and unused tail records. Transcript replay skips host idle waits
and must never be reported as a performance measurement. The utility is opt-in
and restricted to finite recorded-input probes; it does not change play timing.

Private evidence: `span-qualified-combat-comparison.json`,
`span-qualified-reference-parity`, and the guarded qualification spool.
Installed preview unchanged; no live verification or release claimed.


The native transcript comparison passed: 8,589,363 clock observations were
consumed exactly, with identical final Count (10,200,870,393), instruction total
(11,629,409,591), save and RAM
`98e92f42129b1b7f6f8dd14b1b84280bfecf8814d94ef4efc0045b99153f2331`.
The optimized execution included 508,191,887 grouped instructions. This proves
that recorded sequence, not arbitrary gameplay or a performance claim.

The source audit checked all 115,571 eligible memory expressions against their
decoded base register and signed offset, with no mismatches. Its initial parser
flagged 84 zero-register forms incorrectly; the corrected audit and initial
report are both preserved. The next generator also rejects mismatched,
relocated, compound or unknown operands conservatively instead of assuming
its decoded address matches emitted C. Compiled fallback tests cover a base
register changing between accesses, including RAM-to-MMIO and MMIO-to-RAM.

Dual-stick/reference/native movement qualification and KBM aiming, frontend
pause, native Save and reload all passed. Movement remained 4.0625 world units
per consumed game tick in all four directions; half-stick yaw was -128/+128
angle units per tick. Firing retained aim, and the saved 95-round ammunition
state reloaded. A 1.262-second frontend pause advanced Count by only 0.0006 ms,
kept VI unchanged, and resumed with 29 updates in the next second. These hidden
fixtures do not replace the owner's physical-input/focus verification.

With actor logging disabled, the 20-second comparison completed 480 updates
without spans and 562 with spans; medians were 37.968 and 33.507 ms, and p95
remained 50.699 and 50.205 ms. The residual slowdown is not explained by actor
logging alone. Private evidence: `span-light-combat-comparison.json`,
`native-span-transcript-parity.json`, `native-span-memory-expression-audit.json`
and the `span-tick-*` fixtures.


### Contiguous native instruction candidate

The next candidate keeps admitted native operations together in generated code,
followed by the exact original fallback sequence. Unsafe memory access commits
the executed prefix and jumps to that instruction's original hook. This removes
per-instruction fast/fallback joins from the admitted block and lets the compiler
optimize consecutive operations without repeated opaque observer checks. Every
original operation, hook and alternate-entry label remains. No enemy, collision,
animation or input work is omitted.

The stricter generator proves each allowed memory expression has the decoded
base/offset and access width. Unknown expressions end a span. All 46,829 spans,
237,742 grouped instructions and 110,267 memory guards survived this stricter
classification. Six generator tests passed, including compiled RAM/MMIO
transitions and rejection of changed base, offset, width and relocation forms.
A quoting error in the newly added test initially stopped installation before
compilation. The failed command and skipped dependencies were retained; the
corrected tests passed before generation resumed under the same guard.

A default-off `JFG_EXPERIMENTAL_NATIVE_PLAY_TIMING` CMake option makes an explicit
private interactive preview use native elapsed timing and batching without
inherited environment flags. It requires the live runtime and a span-generated
root, identifies itself as `NativeTimingPreview`, and emits a support-log policy
marker. Finite reference probes keep original timing unless explicitly requested
otherwise. This engine policy applies to both control styles; it is not a new
controller setting or a released default.

This build must still pass full reference RAM parity, the existing exact-clock
transcript, same-binary alternating combat measurements, movement/aiming,
pause/Save/reload, bridge, audio and stall checks. An owned hidden interactive
startup must confirm activation without diagnostic clock environment variables.
Physical input/focus and visible/audible verification remain reserved for the
owner. A successful compile does not resolve PERF-001.

Candidate binary SHA-256: `251700d98118a137fdcbae8af50bdc4351c0276e9c4d0d1c525a65a18505f554`. Installed preview unchanged at build completion.


### Contiguous candidate qualification and handoff

Runtime SHA-256: `251700d98118a137fdcbae8af50bdc4351c0276e9c4d0d1c525a65a18505f554`.

The complete reference replay retains RAM SHA-256
`757b7094a9d6fabd671e4c90ba7d50e54a52741d3e7ff3ffb57df3f062b93d99`.
The previously recorded 8,589,363 native-clock observations replayed exactly
across the changed binary, ending with identical RAM, Count, instruction total
and save. This isolates code-generation semantics from host scheduling changes.

Same-binary alternating combat results (20-second qualified window):

| Spans | Updates | Median ms | p95 ms | Updates over 40 ms |
| --- | ---: | ---: | ---: | ---: |
| Off | 503 | 33.840 | 50.593 | 192 |
| On | 553 | 33.533 | 50.295 | 93 |
| Off | 476 | 46.798 | 50.626 | 247 |
| On | 594 | 33.440 | 37.513 | 12 |

The qualified bridge window measured 33.448 ms median / 33.865 ms p95 across 594 updates.
Its initial memory, Count and input poll match the previously qualified reference.
Later trajectories can diverge as cadence changes; the clock transcript supplies
the separate exact-state proof. Median update time is not average frame rate.

The interim analysis wrapper initially rejected a UTF-8 byte-order mark before
launching the second enabled replay. That failed command is retained. Reading
its source as UTF-8 with BOM support fixed the wrapper; the four completed runs
were executed off/on/off/on. No runtime replay failure was hidden or discarded.

Dual-stick movement/turning, KBM aiming/fire, frontend pause, native Save and
reload passed. The new binary preserved movement per consumed game tick and
reloaded the 95-round ammunition state. Source saves stayed unchanged.
The frontend pause lasted 1.260 seconds, advanced Count by 0.000085 ms,
and resumed with 30 updates in the next second.
A deliberate two-second host stall resumed with 61 video events in the next second
and 1 within the first 2 ms, preserving the no-catch-up-burst contract.

The native startup/attract fixture delivered the expected nonzero PCM duration
without reported underruns or empty-queue pauses. Its reference comparison used
the previously qualified reference binary, explicitly recorded in the evidence.
Both produced 200.463 seconds of PCM at 22,018 Hz. The longest interval between
queue submissions was 384.694 ms for this candidate versus 192.072 ms for the
reference fixture; there were no recorded underruns or empty-queue pauses.
These counters do not establish audible quality or visible cutscene sync.
An owned hidden interactive window also started with the preview policy without
diagnostic timing environment variables and closed cleanly through its window.
No desktop focus, global mouse/keyboard input or user window was changed by these
checks. They do not verify audible quality, visible latency or physical devices.

**PERF-001 remains CRITICAL OPEN, with the candidate verified in the stated hidden
fixtures and owner live verification pending.** Remaining slow updates are not
a claimed stable 30 Hz result. This work does not provide 60+ Hz simulation or
animation/camera interpolation. It removes modeled CPU cost from native elapsed
timing and reduces host bookkeeping without skipping simulation work.

For future recomp implementations: keep hardware time separate from host
instruction throughput, retain bounded safepoints and forced hardware boundaries,
preserve phase while coalescing a pending periodic interrupt after a host stall,
and use an exact clock transcript for optimizer parity. Prove effective memory
operands before bypassing per-instruction observers; uncertain forms must fall
back. A faster binary or completed replay alone is not acceptance evidence.

Diagnostic limit: ordinary live captures retain inputs and timing traces, but
do not record the exact Count transcript. Native elapsed-time runs can therefore
diverge on replay even with identical input recordings. The exact transcript
utility remains restricted to finite offline probes; RAM alone is not a complete
CPU/scheduler snapshot. Future deterministic live replay needs an explicit,
bounded clock-recording design rather than assuming input records are sufficient.

Private evidence: `native-preview-qualification.json`,
`contiguous-combat-comparison.json`, `contiguous-native-span-transcript-parity.json`,
`contiguous-bridge-comparison.json`, and the linked qualification fixtures.

The local Modern Controls Preview now uses this verified runtime with the
existing v1.1 launcher. Its previous runtime is backed up, package file hashes
were verified, and profile/settings/save hashes are unchanged. No public release
or Git commit is claimed. The desktop preview and capture shortcuts retain their
existing targets. Owner acceptance remains the drone fight, bridge, physical
KBM/XInput and focus, and audible/visible timing checks.


### Remaining costs in the final candidate

The final candidate received a separate CPU sampling and detailed timing pass
from the same qualified combat boundary. Profiling suspends/resumes owned
process threads and adds counters; these timings locate remaining costs and
are **not** performance acceptance measurements. Parked-thread samples are not
CPU usage, and nested counters must not be added together.

| Instrumented host work | Median per update (ms) | p95 (ms) |
| --- | ---: | ---: |
| Generated dispatch prefix | 1.887 | 2.339 |
| Overlay inventory (inside dispatch prefix) | 0.502 | 0.679 |
| Native handler prefix | 2.671 | 3.302 |
| CPU graphics submission | 5.343 | 6.820 |
| Explicit idle waits | 6.874 | 20.514 |

| Existing GPU timestamp interval | Completed submissions | Total GPU ms | Fraction of measured wall interval |
| --- | ---: | ---: | ---: |
| Framebuffer work | 1704 | 58.956 | 0.295% |
| Regular graphics work | 1123 | 28.337 | 0.142% |

These GPU queries reuse completed timestamps and add no new GPU wait. They do
not measure visible presentation/VSync latency or queue delay before the first
GPU marker. Rendering already runs on the GPU; these measurements do not justify
moving game logic, input or scheduler bookkeeping to GPU compute.

The owned-thread sampler completed 1,085 passes with no failed samples. It
recorded 109 instruction-pointer samples in `memcmp`, but flat samples do not
identify its callers or establish that these comparisons caused slow updates.
Before optimizing that work, attribute call sites and distinguish required
code/overlay integrity checks from avoidable repetition. Do not remove checks
or cache guest memory without a complete invalidation/lifetime contract.

The remaining work is to locate the CPU execution and scheduling boundaries in
slow updates on the final candidate, while retaining the same correctness
contracts. Broader pure-operation span eligibility is one possible experiment,
but excluded helpers must first be proven free of hardware callbacks and other
observable effects. It is not an implemented fix or a measured explanation.
Do not trade deadline checks, collision tests, actors or animation updates for
a higher reported frame rate.

Private evidence: `contiguous-remaining-costs-detailed-costs.json` and
`contiguous-remaining-costs-cpu-sampling.json`. The latter retains source locations
and owned-thread CPU accounting for subsequent investigation.


### Owner live feedback after native preview

The owner reports very smooth gameplay on 2026-10-11, but intermittent crackle
in background music. This is encouraging gameplay feedback, not a blanket timing
acceptance. Track the audible problem as [AUDIO-001](intermittent-music-crackle.md).

## Develop integration (2026-10-13, qualification pending)

Owner requested merging develop `63e49a7a71c3a914d2adc1d91fdcf00bef30d38e`
into high-refresh checkpoint `60cb549bceb023d416dc7721793e809d33ac0699`.
The merge preserves the high-refresh recovery policy, semantic/rigid identities,
video dialog and render diagnostics alongside develop camera, controls, native
audio sample source, profiling and render-viewport fixes. The newer diagnostic
clock-stall environment name accepts the previous high-refresh name as a fallback;
existing high-refresh trace event names remain stable. Both issue histories are
retained. Build and replay results must be recorded before delivery; a successful
merge alone does not establish late-cave or full-tutorial acceptance.

## Develop merge qualification (2026-10-13)

Develop `63e49a7a71c3a914d2adc1d91fdcf00bef30d38e` is integrated with the
high-refresh candidate. Fresh generation has identical game files, and 25
Python checks, 13 focused C++ suites, viewport tests, 120 video RmlUi checks and
546 modern-controls UI checks pass. Original/Custom preserve every non-render-
buffer guest byte. A new native-clock recording with the native audio source
replays exactly. Older pre-merge raw hashes differ after the imported behavior
changes; no claim of cross-revision bitwise equivalence is made.

Review caught a real message-number collision missed by the initial non-live
dialog test. The new live test reproduces swallowed widescreen relayout before
the fix, then passes after the video-state query moves to its own message.
Apply, pause/resume and aspect changes are checked on an isolated desktop.

merged-combat-120-a: 119.7/29.81, 120.0/29.79, 119.8/29.84, 119.6/29.80 OUTPUT/SCENES; merged-combat-120-final-b: 119.7/29.85, 119.9/29.74, 119.9/29.84, 119.8/29.80 OUTPUT/SCENES; merged-combat-360: 352.0/29.79, 356.4/29.75, 357.3/29.83, 352.1/29.76 OUTPUT/SCENES. All three clean combat runs have zero audio underruns and
no foreign compiler/game overlap. Pause/resume also passes. The full-circle
trace has no backward presentation phases, and the reconstructed area-47 pond
retains full north-facing camera distance. These are bounded muted tests,
not a full tutorial or physical-display acceptance.

The owner-reported later-cave objects and full-route cadence drops remain open.
Rigid identity is qualified as a candidate; no visual remedy for that exact
unreproduced report is claimed. The rejected projection rule remains absent.
See [merge qualification](../../../evidence/high-refresh-develop-merge.json)
for rates, phase counts, provenance and limits. Preview packaging follows.

## Local merged-preview delivery (2026-10-13)

The qualified combined runtime/launcher is delivered as
`high-refresh-develop-merged-20261013`. The existing desktop **JFG - High Refresh
Preview** shortcut now selects it; close and reopen an older launcher to use
the new package. Existing save, video/audio/control settings and log-only
performance preferences are preserved byte-for-byte. Package validation and
isolated setup initialization pass. Source merge: `f70b513c896df107163f2d72abed344a87dc2517`.
Runtime SHA-256: `1381e018fa2ec2cc8cc0e9c64c785753485b4068a81a08b7f29f8ca0cee2e4f8`.

This is a local preview, not a public release. Full-tutorial performance and
the exact later-cave crates/exit-light/bridge jitter still require live coverage;
their issue records remain open. All runtime tests were muted. Large private
evidence and the new package stay on D:. The production guard remained enabled
under the same investigation and counters throughout.

## Expanded route: damage-correlated drops (2026-10-13)

The owner reports about a second of lag on damage. In capture 20261013-172104,
health drops near VI 3742-3912 (session 64-67 seconds) coincide with roughly
20-22 new scenes/s while output remains about 111-114/s. This is a real source
cadence reduction, not just counter text. The window includes dense combat and
expanded synchronous tracing; damage is correlated, not yet a proved cause.
The later light/bridge segment mostly has even presentation phases, so its
object matching failures must be considered separately. Initial menu/idle time
is excluded from active-route summaries; raw timestamps are retained.

The full owner route has not yet replayed faithfully using elapsed-VI input
scheduling; the replay remains in the first room. Hidden recorded precise-stick
fraction accumulation had a real focus-reset bug and now passes targeted input
tests, but that change alone did not restore route correspondence. Do not infer
a full-route fix from these partial replays.

## Damage comparison qualification (2026-10-13)

The final candidate corrects redundant completed framebuffer-write holds, and
preserves non-render-buffer game state in Original/Custom comparison. A bounded
Goldwood native Play fixture with 18 actual damage events maintains about
120 OUTPUT / 29.8 SCENES with both light and expanded logging, no audio underruns
and no diagnostic queue drops. Logging alone does not explain a slowdown in
that fixture. 360-cap output averages 350-355 with about 29.8 SCENES, not a
sustained 360. Deliberate pause/readback probes are reported separately.

The owner's 20-22 SCENES damage-correlated window remains real and unexplained
in the exact route. Replaying available inputs does not preserve the full
route under timing changes, so unmatched baseline/candidate routes cannot
prove a whole-route performance improvement. Keep PERF-001 open. See
[review findings](tutorial-late-object-jitter.md#review-qualification-2026-10-13)
and [aggregate qualification](../../../evidence/high-refresh-route-review.json).

The continuation audits pure relocation-address arithmetic inside native timing
spans. The two relocation macros read the host section table and have no device
callbacks; calls that can alter that table remain boundaries. Relocated memory
operands are still excluded unless their actual address is proved. The candidate
preserves every guest operation and the 128-instruction clock quantum. The new
eligibility regression fails before and passes after; compiled differential
cases exercise relocation-table changes between invocations alongside RAM/MMIO
and clock-boundary fallback. Runtime replay/performance qualification is pending.

The pure-arithmetic change preserves every replayed guest byte, save, instruction
count and logical matching decision, but live dense combat still reaches 24-27
SCENES/s. No combat resolution is claimed. A follow-up candidate validates the
actual signed relocated memory address before batching; it never substitutes the
unrelocated ROM immediate. Unknown expressions, MMIO and unaligned accesses keep
the precise fallback. The compiled differential test includes relocated loads
and stores, changing section tables, RAM/MMIO and all nearby poll boundaries.
Runtime qualification follows.

A second CPU candidate checks the existing pending-device certificate after
each normal 128-instruction Count sample. If no device deadline has arrived and
Status/I/O revision are unchanged, it avoids rewalking every inactive device.
The Count sample, instruction boundary, guest operation and deadline remain
identical. CP0/CACHE, idle/park sites, observers, device errors, flash mutations
and invalidated certificates keep the complete handler. This is a candidate
until exact recorded-clock state and native Play comparisons pass. A duplicated
certificate refresh left by integration is also removed.

Test review found that the first randomized relocated-memory fixture combined
its section stride and base-selection parity so relocated cached-RAM cases were
always misaligned. The test is corrected to exercise both admitted and rejected
relocated accesses, with explicit minimum hit counts for each and all 4,096
original/optimized architectural comparisons. The earlier eight-test pass alone
did not establish that admitted branch; this limitation is recorded explicitly.

A dense recorded-clock fixture now contains 1.50-1.70 million instructions per
update, with about 3.8-4.3 ms in interpolation preparation. A storage candidate
replaces ordered semantic-vertex lookup with full-key hashed lookup, avoids
allocation for repeated UV clones, and records corrupt owners in the existing
first pass. Identity equality, duplicate rejection, whole-character decisions,
cut handling and endpoint arithmetic remain unchanged. A private 180-frame,
7,200-sample differential harness compares every output field to the previous
algorithm; full real-scene replay and native performance qualification follow.

Review caught a NaN/culling edge case in the first-pass corruption audit: the old
second pass rejects even a unique NaN endpoint because its copy compares unequal.
A new regression removes that corrupt vertex in the following scene and requires
all remaining actor parts to hold. It fails before the correction and passes
afterward; the differential harness also includes this sequence. The initial
private benchmark launch failed to locate the compiler by bare filename; using
its explicit developer-environment path corrected setup before any game launch.

## Continuation outcome, 2026-10-13

The selected CPU changes admit proven relocation arithmetic and actual signed
relocated RAM operands into existing bounded instruction spans, and reuse an
unchanged pending-device certificate after the normal Count sample. The
128-instruction clock quantum, maximum 16-instruction span, device deadlines,
MMIO/alignment rejection, CP0/CACHE/observer paths and guest operations remain.
Quiet and dense recorded-clock comparisons preserve every guest byte, save and
guest instruction count.

Semantic history uses full-key hashed lookup and avoids duplicate UV-clone
allocation while preserving whole-actor corruption rejection. The dense
same-workload comparison reduces median history cost from 3.90/4.09 ms to
3.34/3.59 ms in the two busy windows. The NaN-then-culling regression and 4,096
compiled RAM/MMIO/relocation/clock-boundary comparisons pass. One generic test
invocation lacked a compiler on PATH and skipped that integration test; the
developer-environment rerun executes all eight tests without skips.

Native combat still has real scene-rate drops. Different native timing paths
do not prove an end-to-end FPS uplift, and the owner's damage-correlated
20-25 FPS full-route slowdown remains open. Unlimited's additional queue-window
delay is measured in PERF-002; its candidate was rejected for worse presentation.
It is not the sole cause of capped combat load. Final rates, audio and source identities are in
[aggregate qualification](../../../evidence/high-refresh-route-fix.json).

## Unlimited scene-age candidate rejected, 2026-10-13

The final native review rejects the prepared-scene-age candidate. It reduces
queue delays and audio underruns (368 in the preceding native sample to 2 in the
candidate sample), and the identical-clock busiest update falls from 49.0 to
39.0 ms with identical guest memory, save and instruction counts. However its
Unlimited presentation p99 expands from about 2.75 ms to 31.0 ms, with output
bursts separated by long gaps. Those native paths are not workload-equivalent,
but the rendering regression is sufficient to reject the scheduling change.
Preserve all evidence. Do not accept lower CPU cost or fewer audio errors alone
as proof of smooth rendering.

All four scene-age source edits are reverted to the tested pre-candidate source.
The selected binary is the queue-observer build 1b0bdd0f, whose exact-clock
guest bytes, save, instruction counts and logical matching equal its preceding
1609c019 build. All original resource waits remain. Unlimited's existing
starvation/pacing issue stays open. No prepared-age correction is delivered.

## Five-hour guarded continuation, 2026-10-14 UTC

Owner approved five hours after the route-fix preview. The same operational
investigation/root and all prior charges are retained; the guard stays enabled.
Selected baseline is implementation aaae085 with documentation e51b0af and runtime
1b0bdd0f. Work prioritizes actual combat source-rate cost and a visibly qualified
late-room fixture. Preserve original game timing, muted owned tests, copied saves,
and raw evidence on D:. The scene-age, direct-camera and secondary subset
experiments remain rejected unless new evidence supports a distinct correction.
No bounded replay, synthetic match or build alone closes the owner's reports.

The new dense-stage observer preserves all guest bytes, instructions and matching
decisions. Semantic history is the largest measured preparation stage (1.51 ms
median), followed by geometry-key construction (0.81 ms). A candidate reuses the
continuity result for exactly equal UV-cloned vertices while retaining full-key
identity, conflicting/invalid actor-wide rejection and NaN/culling behavior.
The old algorithm is the differential oracle; real replay and native checks
remain required. This does not change game timing or count extra simulation.

The initial 2026-10-14 stage/alias renderer builds retained stale generated
layout code. Their visual/performance acceptance is invalid and is being rerun;
see [BUILD-001](stale-generated-renderer.md). Guest-state equality alone did not
detect this private build error. The delivered preview is unaffected.

A diagnostic-only replay-prefix release is being added to establish identical
combat starting state before real native timing measurements. At a complete
update boundary it fingerprints RAM, Count, input and instruction ordinals,
then releases the checked Count transcript and reanchors only the host clock.
It requires finite non-Play replay with an explicit boundary before the probe
end; normal replay still requires EOF. This is test infrastructure, not a
performance fix, and does not change the launcher or default gameplay policy.

Coherent renderer requalification preserves guest state and logical matching.
The alias reuse lowers dense history preparation by roughly 0.2-0.3 ms, while
busy updates still exceed 33 ms. The current semantic stage alone is 1.26 ms
median. A further candidate retains two contiguous endpoint tables, with full-key
collision checks and unchanged invalid-owner rejection, instead of allocating
individual hash nodes every scene. It must pass the prior implementation oracle,
real-state replay and native-prefix performance review before selection.

The flat-table candidate preserves the dense replay byte-for-byte and all
matching decisions. Dense semantic cost falls from about 1.26 to 0.97 ms.
One native-prefix comparison improves the busy window from 23.3 to 28.6 source
FPS; later paths differ, so this is encouraging rather than isolated causal
proof or a stable-30 guarantee. Detailed CPU profiling itself adds cost, but
its disabled control still reproduces the real slowdown.

A preparation candidate reserves mesh storage from actual per-matrix vertex
counts, and binds the F3DDKR context only for the owning synchronous interpreter
call. The latter replaces repeated global mutex/map lookup while keeping the
fallback registry for other states/threads and restoring the binding on return
or exception. Neither change alters geometry, identities or GPU resource waits.
State, rendering and native timing qualification follow.

A concrete CPU omission is found in the span generator: MUL_S and MUL_D expand
to plain multiplication in the pinned generated header, but were absent from
the pure-helper allowlist. Matrix loops therefore fragment around each multiply.
The candidate adds only those two macros; it keeps the original arithmetic,
FPU/Status checks, 16-instruction maximum, 128-instruction clock quantum, MMIO
fallback and all control/callback boundaries. The added eligibility regression
fails before and passes after. The compiled 4,096-case differential now also
compares float/double output bits and FP exceptions in four rounding modes,
including signed zero, subnormal, overflow and infinity inputs. Exact recorded
clock and native performance qualification remain required.

The multiplication-span candidate passes exact-clock dense replay with unchanged
guest bytes, save, instruction totals and logical matching. In a combined
comparison against the delivered 1b0bdd0f runtime, the busiest median update falls
from 37.872 to 35.626 ms and history preparation from 3.735 to 2.633 ms. The
earlier busy window changes only 32.915 to 32.730 ms. These are profiled,
identical-workload costs, not native FPS promises. Native released-prefix
measurements still include sub-30 source rates; the combat report remains open.

Another measured hypothesis concerns the generated function table: multiplying
an aligned address then masking only its low bits does not mix overlay/section
bits. A probe model and compiled original-versus-mixed benchmark use the actual
inventory while checking identical function/continuation resolution. This is
distinct from the already removed continuation metadata scan. No lookup change
is selected until semantic, lifecycle and native-game checks qualify it.

The actual-inventory compiled lookup benchmark preserves every queried function,
continuation and miss. Mixing the whole 32-bit address reduces lookup time by
about 33-51% in resident, sampled-hot-section and all-section models. This saves
nanoseconds per call and does not explain the full combat deficit. The generator
candidate retains full-address equality, first-published collision precedence,
lazy rebuilds and lifecycle invalidation. Existing compiled rebase/unload/reload
and generator checks pass; regenerated game bodies and headers are byte-exact.
Native replay qualification is still required before delivery.

A foreground process-status check at 03:01 UTC found a concurrent
Scooby-Doo diagnostic plus unrelated host activity. The owner was asked to pause
its game tests. The later lookup native comparison is not accepted as isolated
FPS evidence; earlier native runs without a full process-load monitor also
cannot rule out this contention. Exact recorded-state and Original reference
comparisons remain valid for correctness, not uncontended performance.

The older 512-instruction poll candidate remains rejected. A distinct private
experiment will compare 128 versus 256 only after releasing the identical
recorded combat prefix; ordinary Play and the entire prefix retain 128.
Repeated reversed-order runs with host-load monitoring are required before
considering a policy change. No default clock or game-speed change is selected.

## Monitored polling comparison, 2026-10-14 UTC

After the owner paused the other task and its diagnostic exited, four reversed-
order 128/256/256/128 runs began at the same recorded combat RAM/Count/input/
instruction boundary. No foreign game or compiler was observed by the two-second
monitor. Source windows ranged 29.21-29.92 updates/s with 128 and 29.52-29.91
with 256. The later native paths differ and the effect is small; these observations
do not justify changing the established clock policy. The private 256 probe is
not selected. Ordinary Play retains 128 and the existing 16-instruction spans.
Both earlier attempts that detected the open foreign process deferred without
launching a game. Evidence: combat-focus-20261014/poll-clear-abba-review.json,
its per-run host-load records and poll-decision.json.

A second monitored reversed-order comparison uses the pre-flat-table baseline
and the qualified CPU/matrix/lookup candidate, with identical recorded release
state in all four runs and no observed foreign game/build activity. The busiest
window is about 28.51 updates/s in both baseline runs; the candidate produces
29.62 in one run and 28.51 in the other. Early active work is slightly lower,
but changing later instruction workloads and run variability prevent a stable
30-FPS guarantee. Select the exact-state-preserving CPU reductions for measured
work savings; keep PERF-001 open. Evidence: cpu-clear-abba-review.json and its
host-load records. Neither the 256-instruction probe nor scene-age scheduling
experiment is included.

## Severe 360-FPS qualification hitch remains under review

The selected equal-slot candidate's later normal Play run completes and drains
its logs, but VI 4000-4800 averages only about 11 scene updates/s and 181-189
presentations/s, with 34 audio underruns. This is a failed performance check,
despite successful state/phase/completion checks. Earlier same-runtime dual-policy
captures were substantially smoother, so neither a new rendering regression nor
external host contention is ruled out. Do not deliver based on a generic
"completed successfully" assertion. The actual work/submit/history costs and a
monitored identical-prefix old/new comparison are required. Evidence:
shared-native-play-review.json and 360-slow-run-cost-review.json.

The subsequent monitored 360-FPS before/after/after/before comparison preserves
all four release RAM/Count/input/instruction/tape boundaries and observes no
foreign game/build activity. It does not reproduce the 11-FPS collapse or audio
underruns. Both versions still reach approximately 26-27 scene updates/s in
combat windows. Per-process CPU deltas are retained; changing native paths
prevent attributing the previous severe hitch or claiming a stable-30 remedy.
Evidence: shared360-abba-review.json and its four host-load records.

A static 32-versus-16-instruction span model reduces span count by only about
5.3%, with 0.11% more instructions covered. The sampled dense runtime averages
about 5.7 guest instructions per span commit. No 32-span runtime is selected
or benchmarked; the established 16-instruction bound and 128-instruction polling
quantum remain unchanged. Evidence: span-length-potential.json.

## Measuring host-thread transport separately

Function self time includes scheduling latency and cannot identify how much CPU
is spent switching guest stacks. An opt-in CPU-cost diagnostic now measures
baton publication-to-receipt latency on each side of a transfer; it excludes
execution of the intervening guest slice. Ordinary transport remains unmeasured.
Per-update counts/totals and the cumulative maximum accompany the existing
instruction/handler/graphics counters. This is observation only: the scheduler,
context-transfer rules, thread implementation and game timing are unchanged.
A transport optimization requires measured cost and exact-state qualification.


The measured baton wake totals are approximately 0.31-0.39 ms median per update
in four dense-route windows, about 1% of active update wall time. The larger
__osEnqueueAndYield self-time label includes other work and is not evidence that
thread switching causes the combat deficit. No scheduler replacement is selected.
A second same-clock capture disables the extra comparison histories and actor
trace while keeping cost counters; its RAM/save/instruction equality passes.
This separates ordinary history work from expensive diagnostic comparison passes.
These instrumented captures are cost observations, not uncontended FPS acceptance.
Evidence: transport-timing-review.json and single-policy-cost-review.json.


## Checked overlay-identity index candidate

The single-policy capture attributes about 0.58-0.66 ms per busy update to repeated
157-record overlay identity scans. A private byte-checked index passes 18,004
oracle checks (duplicates, changed identities, absent values, moved tables and
invalid extents) and reduces lookup time about 35-40% in reversed-order synthetic
workloads. It compares the complete validated inventory bytes on every call,
rebuilds on any difference, resolves hash collisions with the full identity and
rejects duplicates. Allocation bases are still read live; guest load/resume,
publication and lifecycle handling are unchanged. No unchecked lifetime cache
is introduced. This is a small CPU-work candidate, not a combat-FPS resolution.
Actual replay and native comparison are required before selection. Evidence:
overlay-inventory-cost-review.json and inventory-index-prototype/result.json.


The byte-checked overlay index passes the dense recorded combat replay and full
17,000-VI Original replay: RAM, save, complete instruction trace and reference
framebuffer agree. Profiled busy-update inventory work changes from 0.656 to
0.526 ms median, a small saving. The 120/360 native comparisons were interrupted
by foreign compiler activity and are not accepted as FPS qualification. Keep the
candidate separate from any stable-30 claim. Evidence: inventory-index-dense,
inventory-index-full-original-review.json, indexed-inventory-cost-review.json,
inventory-native120-review.json and inventory-native360-review.json.

A private compiler prototype added restricted aliases only inside admitted
16-instruction spans, leaving all hook and fallback boundaries intact. Its real
matrix leaf differential failed byte-exact RAM equality on synthetic edge cases.
It is rejected before changing the generator or rebuilding game functions;
normal generated code is unchanged. Preserve span-alias-prototype/decision.json
and mismatch-details.log. Compiler hints require state-level differential proof,
even when a pointer-separation argument appears sound.


The rejected restricted-alias leaf's first difference is a NaN representation
at RAM offset 0x32c: baseline 0xffc00000 versus candidate 0x7fc00001. CPU snapshot
equality alone would miss this memory-result difference. The prototype remains
unselected; the production generator has no restricted-alias change.

The owner authorized continuing under the existing unrelated host load. The
new inventory-loaded120/360 reversed-order runs therefore retain all process
observations instead of stopping when another compiler appears. They are loaded
host observations, not isolated performance acceptance or proof that a slowdown
is caused by this candidate. Exact release state is checked independently.


The corrected 360 FPS comparison verifies saved `fps=360` and VSync disabled.
Both runs share the exact release point; output averages roughly 354-359 FPS,
while combat scene windows still vary around 25-30 FPS. This single native pair
does not establish stable 30 FPS or a general gameplay speedup. The indexed
inventory remains a small CPU-cost reduction supported by exact replay, not a
resolution of PERF-001. Incorrectly labelled private runs are documented in
[frame diagnostics](frame-diagnostics.md); their raw evidence is retained.

A temporary full-sync stage probe passes the same dense exact-state checks and
is removed/rebuilt afterward. In the busy window, texture upload wait is about
0.34 ms per scene, GPU fence wait 0.70 ms, queue wait 0.006 ms, and history 2.68 ms.
Other renderer work is distributed across several stages. No dominant queue
wait was found, and synchronization is retained. Evidence: sync-stage-probe-normalized.


## Post-lifetime-correction native observations, 2026-10-15 UTC

The non-observer candidate completes the extended owner-input route at both
120/VSync and 360/no-VSync without crashes, invalid accesses or audio underruns.
Reviewed combat windows run near 119.9 output/29.8 scenes at 120, and 358-360
output/29.2-29.8 scenes at 360. Longer individual updates still occur. Four
minimal/expanded-capture observations do not reproduce a consistent large
logging penalty. These are current-build observations under the allowed host
load, not a controlled causal speedup or stable-30 guarantee. The captured
path-cache lifetime fix addresses memory corruption; PERF-001 remains open.
Evidence: overlay-cold-native120/360, overlay-lifetime-cadence-review and
capture-overhead-native-review. Preserve source-update intervals alongside
output averages; level/mode stability alone cannot identify damage events.


## Replay coverage and health-event qualification, 2026-10-15 UTC

A private transition-call observer resolves the long native replay gap: the
original mainRestartAfterDeath routine at 0x80046378 executes at VI 7155. Juno's
sampled health reaches zero at VI 6933 and resets at VI 7250; the largest update
interval is 1,139.504 ms across VIs 7182-7250. After entering Goldwood, this replay
stays in level 21. Therefore the extended native input replays do not reproduce
the owner's later-cave route. Earlier references to an extended owner-input
route describe replay duration/input provenance, not complete location coverage.
The observer is removed and normal source rebuilt before further qualification.

The owner's retained recording instead has approximately 104 ms update intervals
near nonfatal health losses in levels 21 and 16. A new 120-FPS native capture has
a largest interval of 48.616 ms in its sampled nonfatal-loss windows. These are
different paths and events, not a matched A/B or a damage-hitch resolution. Health
is sampled from playerBoy properties+6; actor initialization and lifetime changes
must be distinguished from damage. Windows overlap and are not independent trials.
The misleading hitPlayer symbol is a proximity query, not an actual damage hook.

Evidence: transition-call-native-review.json, recorded-player-health-v2-review.json
and health-window-cadence-review.json. PERF-001 remains open. Transferable lesson:
record actual location, transition identity and health state before attributing
a long update interval to combat or accepting a nominal full-length input replay.
