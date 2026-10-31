# Original FPS simulation parity

Status: open; two causes are isolated by controlled runs: the tested ordinary
Play build keeps host-elapsed simulation timing when Original output is selected,
and its diagnostic instruction clock omits most real RSP/DMA execution time.
Original-ROM task yielding/resumption is now measured. Reference cores fail
published timing expectations, and diagnostic loading audio still underruns.
No Original-mode correction is promoted or claimed hardware-matched.
See the [sanitized research results](../../evidence/original-timing-research-20261028.json)
and [backend review](../../upstream/timing-backend-review-2026-10-28.md).

The owner requires Original FPS to preserve original-ROM behavior; higher
output modes may use qualified improvements. The original N64 image capture
uses a North American cartridge and Expansion Pak. The October 28 five-hour
research renewal retains the same production guard, investigation root and counters.

## Symptoms, cause established so far and scope

The existing Original output setting does not select original simulation timing.
Native Play uses the host clock in both Original and higher output modes.
Measured flying motion previously advanced around 30 updates/second in both,
versus approximately 19-20 in two original-ROM EmuHawk encounters. This mismatch
predates the new elapsed-flight adapter.

The new adapter stabilizes the shared flight/death class around a three-VI
reference in all Native Play modes. Its twelve copied-profile replays and
component checks passed, but that is not a claim of 1:1 original behavior.
Original currently also receives the adapter. Removing it alone restores the
old speed-up; it does not satisfy the owner's requirement.

Investigate mode selection, CPU/OS/device clocks and the available instruction-
timed reference path. Compare original ROM and Original output on matched input
and state. Do not substitute a constant 20 FPS cap or reference speed multiplier
for original timing. Preserve unrelated approved work, original ROMs/saves and
the same production investigation/counters. All work stays local.

## Evidence and validation limits

Prior evidence: [flying-enemy timing](github-flying-enemy-speed.md), including
original live-motion equivalence by update, different elapsed-VI pacing, and
the stable-reference candidate's finite checks. The original-ROM emulator is
EmuHawk 2.11.1 with Angrylion/cxd4, not a physical-hardware measurement.

New private evidence root: original-mode-parity-20261027.
Runtime, phase/cadence comparisons, attempted remedies and failures will be
recorded below. Exact game-wide or physical-hardware parity is not yet established.

## Fresh Original / high-refresh clock comparison

The initial probe phase changed no runtime source or clock policy. Five
instruction-timed native probes completed at 4,500 retraces, and two new
original-ROM EmuHawk captures completed with 600 post-entry retraces.
The first native run reused an earlier input export; the following four use
the new per-poll exports in matched Original/custom-120 pairs.

All 4,939 compared live flight position/velocity states and their relative VI
timings agree exactly between Original and custom 120 when both use the same
instruction-timed reference clock. No elapsed-flight adapter event occurs.
This supports separating presentation rate from simulation; it does not
qualify normal Play, real display smoothness, all actors or audio behavior.

Against Mupen64Plus, all 1,153 common movement states agree exactly by update.
Their elapsed-VI spans do not:

| Scene / actor | Mupen64Plus VI span | Native reference-clock VI span |
| --- | ---: | ---: |
| Tawfret / 801c2d40 | 612 | 653 |
| Tawfret / 801c34a0 | 594 | 637 |
| Tawfret / 801c3c00 | 573 | 616 |
| Goldwood / 801c4710 | 601 | 632 |
| Goldwood / 801c49c0 | 581 | 613 |
| Goldwood / 801c4c70 | 564 | 592 |

Spans cover each actor's common movement sequence, not necessarily the exact
600-VI entry window. The fresh-input rerun reproduces the Tawfret differences;
stale input export alone does not explain them. The native reference spans
are approximately 5-8% longer. There is no justified scalar/cycle retuning from
this comparison alone.

Machine-readable summary:
[clock comparison](../../evidence/original-mode-clock-comparison-20261027.json).
Private evidence: fresh-clock-comparison.json, fresh-clock-results.json,
initial-clock-comparison.json, fixture-alignment.json and original/native
logs under original-mode-parity-20261027. Earlier failed or superseded trials
remain preserved.

## Emulator accuracy and corrected interpretation

Earlier conversational wording called the difference a confirmed original-N64
timing bug. That was too strong: these tests establish a discrepancy with the
specific emulator configuration, not which clock reproduces physical hardware.

EmuHawk is a frontend with multiple N64 cores. Our measured reference uses
Mupen64Plus, not Ares64. The selected accurate graphics/RSP plugins do not
establish cycle-exact CPU, memory, RDP or interrupt scheduling. Mupen's
instruction-cycle model and N64 console-verification history justify treating
it as a repeatable emulator reference with an unmeasured hardware error bound.
Do not label it arbitrary or useless; retain its detailed logical-state
evidence and explicitly identify its core/configuration.

Our instruction-timed path also uses a modeled cost system, including
ares-derived CPU/cache costs in original_timing_fast.h. Its name and passing
selected-state tests do not certify physical hardware timing. Differences
between it and Mupen64Plus are not by themselves a reason to tune either.

Primary references:
- [BizHawk 2.11.1 core selection](https://github.com/TASEmulators/BizHawk/blob/2.11.1/README.md#cores)
- [Mupen64Plus dynarec cycle accounting](https://github.com/mupen64plus/mupen64plus-core/blob/master/doc/new_dynarec.mediawiki#cycle-counting)
- [TASVideos console verification and N64 timing limits](https://tasvideos.org/ConsoleVerification/Legacy/Guide)

The dynarec document describes that implementation's model; its historical
constants are not a measured claim about our installed BizHawk fork.
The TASVideos guide describes verification constraints, not a quantitative
error bound for our JFG captures.

## Hardware follow-up and compatibility decision

The owner has an N64 and North American cartridge, without capture hardware
or a flashcart. Begin with repeatable stock-cartridge footage, optionally
filming the TV at high camera frame rate. This can test the large reported
speed difference; it cannot establish small per-VI or internal cycle equality.
Match scene, character, aspect, enemy starting state and controller activity.
Preserve the original video and real capture rate; repeat the encounter.

If internal timing remains necessary, a USB development flashcart could run
an instrumented local ROM without motherboard probing. Log compact VI/update
counters and selected actor state into a bounded RAM buffer, then retrieve it
after the interval. Measure instrumentation overhead against an unmodified
baseline before drawing conclusions. USB debug capability is documented by
[SummerCart64](https://github.com/Polprzewodnikowy/SummerCart64); no device
purchase, ROM modification, schematic build or hardware test has occurred.

Controller-port capture measures input polls, which are not automatically
physics updates. Direct RDRAM/cartridge bus probing is not a prerequisite for
this gameplay-speed question. Any future electrical schematic must identify
the actual board/device and signal levels before use.

The existing local elapsed-flight candidate remains available with its prior
finite qualification. It is not a solution to the newly stated exact Original
requirement. Neither a default switch to the reference clock nor removal of the adapter
was implemented: the former still lacks hardware/performance/audio qualification,
and the latter restores the earlier emulator mismatch.
Original parity remains open, with no release, closure or hardware-match claim.

Transferable lesson: distinguish logical update equivalence, elapsed guest
retrace timing, displayed frame cadence and physical-hardware timing. A result
in any one category cannot silently certify the others. High-refresh output
can share a simulation clock; separately test its rendered interpolation and
normal Play behavior before changing the default policy.

## Original N64 image capture, 21:27:49

The owner confirmed that this roughly 71-second, 1280x720 Goldwood-combat
capture is from their physical N64 with the North American cartridge and is
timed correctly. It is an original N64 image capture and can be used for
elapsed-event comparison. No new phone capture is required to begin that
analysis. Two further hours were approved for this work.

The file is encoded at 120 FPS; sequential decoding yielded 8,545 images
through timestamp 71.208 seconds. Its recording frame rate does not establish
the game's simulation or rendering rate. After suppressing small compression
changes, whole-image differences yielded approximately 13-20 substantial
changes/second in ten-second windows. This remains an image-change estimate,
not an internal physics-update or VI count.

Use visible flight/death events and elapsed durations, with start/end
uncertainty and matched starting conditions recorded. Camera activity, effects,
frame conversion and repeated images limit exact per-frame conclusions.
The original capture's hardware provenance and correct playback timing are
owner-confirmed; exact runtime timing parity still needs a valid event comparison.

Private evidence: original-mode-parity-20261027/video-review, including the
input hash, timestamped extracts, frame-difference table and updated source
confirmation. Further comparison evidence is under n64-flight-comparison-20261027.
The original image capture is unchanged.

The initial extractor lacked OpenCV; a first isolated installation encountered
the user's pip user-install default. A private D-drive tool directory with pip
isolated/no-user resolved that tooling issue. Both failed receipts are retained;
no product dependency or game installation changed.

## Diagnostic ordinary-Play qualification

A private, explicit JFG_DIAGNOSTIC_REFERENCE_PLAY_CLOCK opt-in now allows
testing the existing instruction-timed CPU/OS/device model through ordinary
Play. Unlike the earlier finite probes, this can exercise live input, ordinary
closing and real audio delivery. It leaves the default clock selection
unchanged and rejects a conflicting host-clock override or use outside Play.
The Release build and bounded ordinary-Play checks below pass. This remains
instrumentation for choosing a proper policy, not a hardware-timing remedy or
a release change.

The first ordinary-Play reference attempts were rejected at startup (exit 3).
Normal Play's entry point independently enables native cache/shadow CPU
shortcuts, which correctly require the native clock. The explicit reference
comparison now omits those default CPU shortcuts, including direct SP access,
while retaining independent presentation upload optimizations. Explicit
conflicting native-cache/shadow overrides still fail validation. Failed runs
are preserved.

### Completed ordinary-Play checks and compatibility limits

The second Release build completed seven bounded copied-profile Play sessions:
five diagnostic-reference runs and two unchanged-default clock controls.
All reached their requested room, rendered, delivered real audio through a
muted device, closed normally and exited zero. These are automated finite
runs, not an owner listening or physical-display smoothness signoff.

For room 24, the reference-clock Original/120 pair matched every one of
1,761 common live flight position/velocity states and relative VI timestamps.
The one-sample length differences arose from closing after a wall-time bound.
The flight adapter was inactive in the reference runs. The native-clock
control still exercised it. This extends the earlier probe result to ordinary
Play without establishing a hardware match.

In room 236, both reference-clock output modes recorded two audio underruns
around the level transition and no further increases during the following
30 seconds. The native-clock control recorded zero. The earlier Tawfret
reference run ended with nine underruns; it did not have time-series audio
logging, so their location is not established. This is a measured reason to
retain the opt-in as diagnostic only. Do not change audio providers or hide
underruns merely to declare the clock qualified.

The opt-in rejects malformed zero/long values, a simultaneous host-clock
request, and non-Play use. The first non-Play negative test used the wrong
CLI spelling and only proved CLI rejection; a corrected test reaches the
runtime validator and exits 3 as expected. Default Play continues using the
existing policy. No owner preview, release executable or package was replaced.

Private evidence: n64-flight-comparison-20261027/runtime-reference-play-v2,
normal-play-v2-results.json, normal-play-qualification.json,
room236-play-results.json, room236-audio-comparison.json, and
reference-flag-validation. Three first-build reference attempts were rejected
before gameplay because of the independently enabled native CPU defaults;
their failures remain preserved.

### Matching the physical capture

The original N64 image capture shows the Goldwood room 236 encounter. Its
vine, crates and terrain match the retained original-ROM scene fixture.
Earlier flying-enemy timing tests used room 24, not this encounter. A fresh
neutral room-236 entry contains ground enemies but does not activate the
flying wave at the starting point. A subsequent ordinary-controller route from
copied-save entrance 1 reached
the vine area and activated 14 Galaxian5 actors. The earlier camera-position
fixture remains visual identification evidence only, not a timing reference.

A visible smoking/tumbling enemy around 40.6-43.0 seconds provides a candidate
event for a bounded elapsed-time comparison. The later fine image review bounds onset and impact below; starting
altitude/velocity and camera motion still need to be accounted for. No exact duration or hardware speed ratio is certified.

The earlier automated death case set health to zero at spawn and the tracked
actor fell about 1,681 world units before removal. It is not equivalent to the
physical capture's airborne-to-floor death. Its roughly 3.9-second lifetime
must not be used as a direct timing match for that image sequence.

The instruction model also uses a corrected-Mupen HLE device profile:
reference_device_timing.hpp explicitly disclaims hardware timing and uses
effective RSP task delays. Ares-derived CPU costs plus that profile do not
form a validated physical-N64 clock. Do not retune costs or impose a 20 Hz
cap to fit the capture. The proper Original-policy gate remains matched
hardware events, guest timing coverage, ordinary-Play audio/performance, and
separate high-refresh presentation validation.

### Matched room-236 encounter and final result

The successful controller route starts from entrance 1 and walks through the
clearing to the vine area. It changes no runtime positions, health, velocities
or instructions. All three ordinary-Play replays used its exported input-poll
sequence and the same copied logical Flash. They reached the scene and exited
zero. Original and custom-120 on the diagnostic reference clock agree in all
6,825 common motion states and their relative VI timestamps across 14 flyers.

The original-ROM run took about 15.57 game updates per 60 VIs while the wave
was active, and 14.80 in the final 600-VI window. That last window contains
140 updates with delta 4 and eight with delta 5. These are emulator-observed
game updates, not a measurement inferred from the physical capture's pictures.
They demonstrate load-dependent pacing in the reference encounter and rule
out a constant 20 Hz correction as proof of universal Original behavior.

After matching spawn name, position/velocity and order, 2,332 initial movement
states agree with the native reference path. Selected sequence lengths differ
in elapsed VIs, and some actor state prefixes diverge later. This is not an
all-state equivalence claim. The source comparison is an equivalent local
fixture and controller route, not a replay of physical-controller inputs.

All eleven second-build Play sessions exited normally: the original seven,
three matched-route runs and one further audio observation. The matched-route
reference pair each reported two transition underruns; the native control
reported zero. Additional PCM/scheduler logging reported four, with source
audio present around the gaps, including one louder interval. The measured
pause/resume gaps in that instrumented run were about 83-268 ms. Extra logging
changed the count, so these timings cannot quantify uninstrumented severity.
The capture records queued PCM before muting, not device-loopback audio.
Audio qualification remains open and the default playback path is unchanged.

The physical image sequence conservatively bounds the first sustained visible
tumble at 40.5-40.8 seconds and impact disappearance at 42.8-42.85 seconds.
Those are image-event bounds, not an exact health-zero/death-initializer time.
The controlled local spawn-kill test remains unsuitable for direct duration
comparison. No scalar was fitted to these images.

Private harness failures are retained: invalid/reused checkpoint tags and a
planner command timeout ended initial navigation attempts; the initial walking
route also stopped at scenery. Those are fixture failures, not established
game crashes. The successful alternate entrance removes those blockers.

Machine-readable finite results:
[ordinary-Play comparison](../../evidence/original-mode-play-comparison-20261027.json).
Private data include matched-route-comparison.json, reference-transition-audio-
analysis.json, the unchanged original image capture, and controller/actor traces.

### Actual reference CPU/device source review

The fixture's Core=1 selects the cached interpreter in
[BizHawk 2.11.1 settings](https://github.com/TASEmulators/BizHawk/blob/2.11.1/src/BizHawk.Emulation.Cores/Consoles/Nintendo/N64/N64SyncSettings.cs).
Its common counter update uses executed PC distance, whereas our reference
path uses ares-derived instruction/cache costs.
[Tagged CPU source](https://github.com/TASEmulators/BizHawk/blob/2.11.1/libmupen64plus/mupen64plus-core/src/r4300/r4300.c#L687).

The tagged device code schedules fixed graphics/audio completion delays after
plugin execution.
[Tagged device source](https://github.com/TASEmulators/BizHawk/blob/2.11.1/libmupen64plus/mupen64plus-core/src/memory/memory.c#L1103).
This explains why selecting a detailed rendering/RSP plugin does not certify
cycle-exact timing. It also establishes that the two clock models differ;
it does not assign every observed VI discrepancy to one causal instruction.
No emulator code was copied into the product or timing constant changed.

The owner-facing summary is retained under the private review artifact
JFG-N64-timing-comparison-2026-10-27.txt. Next acceptance work is a matched
physical event/starting-state comparison and reference-clock normal-Play
performance/audio qualification before any Original-mode policy change.
A new phone capture is optional; the existing original N64 image capture is
usable evidence. Exact hardware parity and issue #48 remain open.

### Loading-performance follow-up

Existing baseline tick timestamps narrow the diagnostic audio problem to a
real-time execution deficit during loading: VIs 1750-1800 take 1.250 seconds
at Original output and 1.296 at 120, compared with about 0.836 seconds at the
otherwise sustained VI pacing. After loading, VIs 2000-2600 take 10.029 seconds
in both. These are measured host durations, separate from the earlier
guest-state/VI comparisons; they do not identify all audio causes or quantify
uninstrumented release performance. The native-clock control's transition is
at different VIs and must not be compared using those numeric windows.

An existing direct-SP device-access optimization was tested explicitly, with
all instruction probes retained and no source/default change. Both output
modes exited normally, and each matched all 6,825 common motion states with
absolute VI timestamps against its baseline. The observed final counters
were 26,000 reads and 43,332 writes. The loading window shortened to 1.194
and 1.186 seconds respectively, but both still reported two underruns.
This is an informative failure to solve audio, not a promoted correction.

One additional bounded function-profile run exited normally and captured a
long loading update from VI 1688 to 1809. The profile is valid with no overflow.
Its largest measured self-CPU costs include original thread dispatch/yield
and asset inflate/Huffman-table work. This identifies concrete optimization
targets, not permission to skip guest instructions or assign guessed timing.
Its roughly 2.545-second wall duration includes waits and observer overhead.
It reported three underruns, so it is not an uninstrumented performance sample.

The earlier direct-MI context-mask optimization had a recorded timing-boundary
rejection in [the village investigation](opening-village-and-cutscene-aspect.md).
It was not enabled or modified here. Its existing rejection must be resolved
with original state/event checks before considering it as a shortcut.

The total is now fourteen normally exited second-build sessions, including
the separate PCM and function-profile observations. Exact Original timing and
diagnostic-clock audio remain open. No new gameplay/default-clock fix or
release qualification is claimed. Private receipts:
reference-clock-wall-pacing.json, direct-sp-clock-comparison.json,
reference-loading-cost-analysis.json and the per-run result/request files.

## October 28 exact-cause continuation

The owner approved eight hours to identify the causal timing mismatch, use
additional decompilation and online tools as needed, and review current
VibinToast work under strict original-matching criteria. The production guard,
investigation root and every prior counter are retained. A fresh source pin
and causal CPU/device/scheduler comparisons are in progress. A visually working
upstream enhancement is not accepted as original timing evidence.

Private evidence root: original-timing-cause-20261028. The preceding finite
results and all informative failures remain preserved. No new fix is yet
claimed, and the prior owner preview and original files remain unchanged.

### Recovery, clock and flight-correction isolation

The owner confirmed an Expansion Pak. New isolated Ares64 interpreter and
Mupen runs use 8 MB; both read osMemSize=0x800000, mmExtendedRam=0 and
mmEndRam=0x80400000 in the target scene. The game retains its 4 MB allocator.
The earlier 4 MB fixture is preserved; memory size is no longer an uncontrolled
difference in the new emulator comparison.

Five ordinary-Play runs used the same copied room-125 save and Mupen input-poll
sequence. Each entered the room and exited zero. Private diagnostic switches
independently disable native_frame_recovery_counter and FlyingMotionScope;
absent switches retain the existing default. The adapter integration test now
also verifies that its explicit diagnostic bypass preserves legacy forces and
displacements. No public launcher/profile setting or default clock changed.

In the final 600-VI window, native default, stock recovery, stock flight and
both stock paths each completed 300 viFrameSync returns. The instruction-model
control completed 192: 168 returned delta 3 and 24 returned delta 4. Restoring
the original recovery rule alone therefore does not restore the original load
cadence in this scene. The host-clock path's faster game-update rate remains
the larger cause of the legacy per-call flight speed change. Changing output
presentation FPS does not select the instruction-model policy.

Ares's raw RDRAM samples are not equivalent to function-entry observations:
dirty cache lines can publish different actor fields on separate VIs. The
new private instruction debugger will read cache-consistent state at original
function boundaries. No precise Ares physics rate is inferred from hybrid
raw actor snapshots, and no scalar or device deadline has been fitted.

Private receipts: original-timing-cause-20261028/causal-first-analysis.json,
causal-motion-prefixes.json, the five run requests/results, and the Ares/Mupen
scope and snapshots. The new debugger is pinned separately; its newer core
must not be mislabeled as the existing BizHawk Ares core. The first debugger
configure failed because Windows backslashes were passed as CMake cache paths.
The corrected separate build uses forward slashes; the failure is retained.

### Instruction-level reference tool qualification

The private headless ares-64 debugger is pinned to
HailToDodongo/ares-64 b4ead632f6a983d2e86546a6bba2b7a5c2ccb6c0.
Its unmodified Angrylion bridge did not boot this original ROM: the first
graphics task reached its completion command, but the bridge consumed RSP
DMEM with the wrong byte order. RSP DMEM is byte-big-endian; Angrylion expects
host-order 32-bit words. E9000000 (SyncFull) was seen as 000000E9, so no DP
interrupt completed the task. Interpreter and JIT boot controls reproduced
the same failure. This was a reference-tool defect, not a game/recomp result.

A private 4 KiB word-order mirror now feeds Angrylion at command submission.
Read-only command scanners use the concrete RSP memory reader instead of a
base-class cast that discarded its byte order. Guest RAM, game instructions
and emulated CPU/device timing are unchanged by that adapter correction.
Both observed and unobserved interpreter runs now enter room 125 and complete
900 further VIs. Their entry/final cache-consistent 4 MiB RAM dumps, entry/final VI
counts and final image hash agree exactly. This qualifies probe neutrality
for that fixture, not the newer core's absolute accuracy against hardware.

The original-ROM scheduler, task starts/completions and cache-consistent actor
states can now be observed at instruction boundaries. Earlier boot failures,
the initially incorrect isolated save destination, and probe-build failures
are retained as non-qualifying attempts. No emulator defect was worked around
by forcing a game interrupt or changing a game timer. The RAM comparison covers
addresses 0x00000000 through 0x003FFFFF; it does not compare all 8 MiB, every
intermediate state, or the entire emulated machine.

Private receipts: original-timing-cause-20261028/debugger-dmem-bridge.json,
headless-observer-dmem-check.json, headless-scheduler-first-analysis.json,
mupen-scheduler-first-analysis.json and headless-motion-prefixes.json.

### Causal graphics-work control and cross-core limits

The cache-consistent original-ROM reference and unadapted native runs share
675 initial enemy position/velocity states across three actors in room 125.
The original Ares model takes 890/869/848 VIs for the three observed prefixes;
native Play takes 462/448/434. The instruction-clock diagnostic takes
798/782/761. This directly separates matching movement math from update
frequency. These are finite prefixes, not whole-game equivalence.

The final 600-VI windows contain 151 updates in the original Ares model,
180 in Mupen, 192 in our instruction-clock diagnostic, and 300 in unadapted
native Play. The independent Mupen scheduler observer preserves entry/final
RAM, actor traces and timestep traces exactly against its unobserved control.

A private causal intervention divides only graphics RSP interpreter clock
charges by three. It changes graphics task durations substantially but gives
152 updates versus 151 in the unmodified control. Graphics work alone is
therefore not the principal cadence limiter in this fixture. This modified
emulator is neither an original reference nor a proposed correction. The
default-after-instrumentation control still matches the prior qualified
entry RAM, final RAM and final image exactly.

The native scheduler's fixed graphics/audio SP completion delays are also
different from the Ares model, but that source difference must not be promoted
to the sole cause after this negative intervention. CPU/workload and scheduler
phase differences remain under investigation. Ares CPU profile units are
93.75 MHz cycles; RSP profile units are 187.5 MHz scheduler clocks, divided
by three for physical RSP pipeline ticks. The corrected private unit receipt
preserves the original raw analysis.

The normal-clock original-ROM room-236 route also completed successfully with
the Expansion Pak setting. Its state-aware controller route reaches the same
encounter waypoints, but analog normalization differs between frontends; it
must not be described as identical recorded input. No game-state writes,
fixed 20 Hz substitution, public clock policy change or hardware-exact claim
was made.

Private receipts: headless-motion-prefixes.json, graphics-clock-isolation.json,
mupen-scheduler-observer-check.json, headless-default-after-causal-gate-check.json,
headless-scheduler-analysis-units.json, frame-phase-analysis.json and the
headless236-entry1-route scope/route/trace/snapshots.

### Cause isolated in ordinary Play

The control variable is the simulation clock, not interpolation output FPS.
With the experimental native-Play build enabled, startup sets
native_preview_play = state.play_mode && !reference_play_clock, independent
of the selected presentation frame rate. HostCountClock advances Count from
host elapsed time and deliberately charges no emulated instruction/cache work.
The original viFrameSync still decides when to return from retrace messages,
but its workload now completes on the PC's timescale. Some original flying
motion, death gravity, damping and spin advance per callback. Executing more
callbacks therefore advances the same motion states in less elapsed time.

Local history identifies commit 5c7df1bdee61778590fb3b7baa281958a9167870
(October 12, 2026) as the verified introduction of native ordinary-Play clock
selection in this checkout. This is not a claim about the first project build.
The subsequent elapsed-flight correction addresses speed stability with a
three-VI compatibility reference; it cannot restore the original variable
load cadence. The five-run clock/recovery/adapter isolation above establishes
why removing either that correction or the recovery override is insufficient.

Relevant implementation:
[native Play policy](../../../src/boot/native_boot.cpp),
[host Count clock](../../../include/jfg/boot/host_count_clock.hpp),
[flight adapter](../../../src/boot/flying_motion.inl), and the pinned decomp's
src/gameVi.c::viFrameSync. The per-update instruction result agrees over
the measured motion prefixes; the time between those results does not.

### CPU-cost observation and frame-boundary sensitivity

A private read-only observer applies our existing instruction/cache cost model
to the exact original-ROM interpreter stream. The final observed window has
943,115,734 actual modeled CPU cycles and 939,162,381 parallel-model cycles,
a ratio of 0.9958082. Entry RAM, final RAM and final image match the unobserved
control exactly. This bounds the cost-formula difference in this workload;
it neither proves physical VR4300 accuracy nor supports arbitrarily retuning
CPU costs to one encounter.

The diagnostic native cache observer also preserves 1,635 common actor
samples, their guest values and absolute VI/update timestamps. An initial
comparison incorrectly included host wall timestamps in the state dictionary;
the corrected qualification excludes those observer-dependent timestamps.
A separate heap comparison initially interpreted one logical big-endian dump
as little endian; the room value failed validation. The corrected reader
verifies room 125 and matching principal overlay/actor-list locations.
Both failed analyses and their corrections are retained.

For 232 matching initial movement states of one actor, elapsed guest time
between sync calls has median 4,874,057 original-model CPU cycles versus 4,669,924 in
the native instruction diagnostic (excluding the first sample). Three NTSC
video intervals are near 4.69 million CPU cycles. A modest work or scheduling
difference can therefore change a three-VI update into four. Matching this
one actor does not imply that all other actors, elapsed timers, random state
or rendering work are identical. The numbers are not a fitted timing rule.

The original-ROM references themselves differ: the final room-125 window has
151 updates in the pinned newer Ares interpreter and 180 in Mupen64Plus, versus
192 in the native instruction diagnostic and 300 in unadapted native Play.
A loaded room-236 route in Ares has 128 updates over 600 VIs, while the earlier
Mupen route has 148. The routes use the same encounter waypoints but different
frontend analog normalization. No core is declared hardware-exact solely
because its output is closer to the recomp.

The native device model currently schedules graphics/audio SP completion at
fixed 1,000/4,000 Count ticks. The original-ROM Ares interpreter executes the
microcode. Private causal task-duration experiments distinguish this source
difference from its measured effect; an early audio intervention failed to
accelerate most audio work because microcode overwrote the DMEM task header.
That negative result is inconclusive and is retained. The corrected experiment
latches task type when the CPU starts it and activates it when SP halt clears.
No experimental emulator timing is a candidate product correction.

Private receipts: instruction-cost-differences.json,
headless-cost-observer-check.json, native-cache-observer-qualification.json,
reference-heap-layouts-corrected.json, matched-motion-work-analysis.json,
rsp-work-causal-analysis.json and the corrected latched-RSP controls under
original-timing-cause-20261028.

### Corrected device intervention and non-idle stage results

The corrected task-type latch materially changes the intended work. Mean audio
task duration falls to 37.17% of control in the audio-only run. Graphics and
combined controls also materially shorten their target tasks. The final
600-VI update counts are 151 unchanged, 150 audio-only, 152 graphics-only,
and 156 combined. Fixed native SP delays remain an approximation, but shortening
RSP work by itself does not account for the diagnostic native clock's 192
updates. These causal emulator modifications are not fixes or timing presets.

The detailed stage observer separates the known CPU idle loop from active
guest work. In the matched first-actor prefix (samples 1 through 199), mean
inclusive non-idle main-update cost is 4,772,164 CPU cycles in Ares and 4,543,451
in the native instruction diagnostic. Idle time is about 1,261,062 versus
759,822 cycles per update. Both active work and scheduling phase therefore
differ; the larger full-update duration is not all active CPU work.

Selected-stage results do not identify a large missing shadow calculation.
Shadow generation is about 143,175 versus 148,154 cycles and its filter about
141,808 versus 144,371. Object-update and track-draw work are higher in the
original-ROM trace, while native graphics submission is higher. Nested
inclusive rows cannot be added together. The compared actor's movement states
and the sampled number of flight/animation-matrix calls match, but other
game state and returned elapsed-VI values differ; this is not a full-world
same-input CPU replay or proof of one missing instruction.

The original observer again preserves the complete captured 4 MiB RAM range
at entry and exit, plus the final image.
The native observer again preserves all 1,635 common actor samples and their
absolute VI/update timestamps. Raw instruction-count distributions from the
earlier stage report must not be compared directly: the native idle optimizer
advances the modeled loop without individually executing every idle instruction.
A parser initially consumed the TSV header as an event; filtering event kinds
before numeric decoding corrected it. No rerun was needed for that analysis
error, and the failed script/log remain preserved.

Private receipts: latched-rsp-causal-analysis.json,
latched-control-qualification.json, stage-detail-analysis.json,
detail-observer-qualification.json and native-detail-observer-qualification.json.
The compact [public evidence summary](../../evidence/original-timing-cause-20261028.json)
contains counts, hashes and qualification limits, without ROM/game assets.

### Compatibility conclusion and remaining acceptance

Original simulation and output presentation need separate explicit policies.
Original must preserve the original update path and a qualified virtual
CPU/device/scheduler clock. Higher presentation rates can interpolate those
same states without changing their VI schedule, as the existing paired
Original/120 probes demonstrate. This conclusion does not require increasing
game simulation to 60 Hz or imposing a universal 20 Hz cap.

The available diagnostic clock is not ready to become the default: it still
differs between reference cores and has measured loading-time audio underruns.
A proper follow-up must qualify its scheduling and host execution performance,
retain original per-call math in Original mode, and compare matched low/high
load routes and transitions. Any high-refresh compatibility timing improvement
must be identified separately from Original fidelity. Matching another
recomp's stable rate is insufficient; see the
[immutable Toast source review](../../upstream/toast-timing-review-2026-10-28.md).
No production clock switch, arbitrary device delay, public preview replacement,
commit, issue reply or release is part of this causal investigation.

### Validation and disposition

The native diagnostic build succeeds. Existing host-clock, reference-event,
original-timing-runtime, original-timing-fast, flight-math and adapter checks
pass after rebuilding their targets. The explicit adapter-bypass integration
check and invalid private-clock option checks also pass. Profile arithmetic
receives its existing focused check after the added diagnostic stage fields.
These are bounded implementation/observer checks, not a final hardware-parity
or release verdict.

The primary ordinary-Play speed-up is explained and reproducible. The separate
instruction-clock approximation still needs qualification and loading-audio
work; it has not been silently selected for the public Original setting.
All earlier results and limitations are retained. Artifacts and copied saves
remain on D:, source changes are local, and no GitHub actions were taken.

## October 28 five-hour research renewal

The owner explicitly renewed research for five hours after the preceding
guarded run closed. The same production investigation, root, accumulated
charges and counters are preserved; one additional bounded job is admitted.
The initial source hashes match the preceding handoff. Existing source,
captures and original saves remain intact, with fresh evidence under
original-timing-research-20261028.

The next phase checks conservation between modeled CPU costs and virtual Count,
then separates equal-input function work from elapsed-VI-dependent world state.
The prior stage averages compare equal selected actor motion, not an identical
whole-machine execution. Neither those averages nor a closer reference rate
justifies a global CPU multiplier. Instruction-clock loading-audio qualification
also remains open. No GitHub posting or default Original-clock switch is
authorized by a successful diagnostic alone.

### Renewed research: conserved clock, causal costs and hardware expectations

The bounded native capture conserves its modeled clock: every observed interval
has twice the Count delta within one CPU cycle of its cost-counter delta, the
expected half-tick rounding. No unknown modeled cache operations appear.
This rules out lost accumulated time in that capture, not missing hardware work.

Applying the native cost formula to the actual original-ROM Ares interpreter
changes the final 600-VI count from 151 to 152 when enabled from boot, and leaves
it at 151 when activated in room 125. The latter preserves 675 initial enemy
motion states, with their spans differing by one VI. Count-flushing instructions
keep their original cost. The unchanged control again matches the captured
4 MiB entry/final RAM and final image. This small formula difference does not
explain the native instruction run's 192 updates.

A separate synthetic conformance probe finds a real accuracy limitation shared
with the Ares-derived model: isolated warm-cache loads/stores are charged two
CPU cycles, whereas the published hardware tests expect one; an independent
instruction after a load is also overcharged. A dependent load/use pair can
agree coincidentally because the model applies the extra charge to every load.
Operand-sensitive floating-point early completion is likewise absent. These
are source-derived hardware expectations, not a new local console measurement
or execution of the complete test ROM. Integer multiply/divide controls agree.
No global timing multiplier or default clock switch follows from this finding.

Reference: [nemu64-test timing tests at the pinned revision](
https://github.com/thelemmy/nemu64-test/blob/9a8b9f7d94ee2f6f57d7feed70c98c22cdc30e6c/src/tests/timing/mod.rs).
Private receipts: clock-cost-conservation.json, cpu-cost-causal-analysis.json,
and timing-model-hardware-cases.json under original-timing-research-20261028.

The first standalone conformance compile lacked the standard declaration for
abort; adding the missing C library include corrected that harness failure.
The failed compile and corrected build are both retained; runtime source and
timing formulas were unchanged by the harness correction.

### Renewed research: guest-thread attribution and RSP saturation

Per-function elapsed measurements included audio and scheduler work that ran
while the game thread was suspended. A read-only owner tracker changes
at original ERET boundaries; after removing other owners, mean main-update
cost over matched enemy states 1–199 is 3,918,692 original-core CPU cycles
versus 3,865,993 native modeled cycles, a 1.35% difference rather than the
earlier inclusive 4.8%. Kernel work preceding ERET is still attributed to
the previous owner in this first measurement. Nested functions are not
additive, and matching one enemy does not assert identical whole-machine
state. The original 4 MiB entry/final RAM and final image remain identical;
1,635 common native actor samples retain state and absolute VI timing.

A stronger private intervention divides RSP compute charge by 64, retaining
fractional remainders, actual microcode execution, CPU timing, and DMA delay
formulas. It changes neither the ROM nor runtime defaults. Graphics-task
mean observed launch-to-SP-interrupt duration falls to 4.34% of control.
Dividing both task classes reduces audio duration to 7.50% and graphics
to 4.36%. Control still has 151 updates in the final 600 VIs; graphics-only
has 160 and both have 162, compared with 192 in the native instruction-clock
diagnostic. Thus RSP work contributes, but even this extreme intervention
does not reproduce the native cadence. This is a causal experiment, not
a proposed hardware model or a fitted task delay. Startup task type zero
is outside the classified steady-state comparisons.

The analysis originally wrote valid measurements and then failed an obsolete
divisor-three assertion key. A separate corrected validation uses the actual
graphics/both cases and preserves that failure. The default private core's
4 MiB entry/final RAM and final image are unchanged.

Private receipts under original-timing-research-20261028:
stage-thread-analysis.json, native-stage-thread-qualification.json,
stage-thread-observer-qualification.json, rsp64-causal-analysis.json,
rsp64-analysis-validation.json, rsp64-default-qualification.json.

### Aligned windows, complete CPU accounting and loading transport

A further observer separates exception entry through ERET as a kernel owner.
All 920 original and 1,266 native frame-sync snapshots conserve the cumulative
CPU clock exactly across the owners. The selected game thread's own mean
main-update cost is 3,882,981 versus 3,837,491 cycles (about 1.17%); audio,
scheduler, other OS threads and idle waiting account for the rest. The
unchanged original 4 MiB RAM/image and 1,635 common native state/VI samples
qualify the observer, not the timing model.

**Comparison-window correction:** the earlier 151-versus-192 final-600-VI
numbers describe each run's own endpoint window. The native capture was longer,
so those are not the same elapsed portion of gameplay and must not be quoted
as a controlled speed ratio. With both anchored to the first matching enemy
state, the complete elapsed-VI window 300-800 contains 125 original-core
updates and 140 native instruction-clock updates. The earlier nominal
300-900 comparison included seven VIs beyond the original capture and is
superseded. The same first 232 motion states take 890 versus 798 VIs;
that matched-state observation is unaffected. Earlier
RSP and CPU interventions remain within-run comparisons with equal duration.

The existing optional fiber transport preserves 4,011 common actor states
and absolute VI timings against OS-thread transport in the copied room-236
loading route; the 120-FPS comparison preserves 3,997 common samples.
Loading VIs 1750–1800 improve from 1.272 seconds to 0.929 (Original) and
0.952 (120 FPS), compared with approximately 0.836 seconds of guest time.
Audio underruns fall from two to one, with no overruns. Adding the existing
direct-SP access option still leaves one underrun in Original and 120.
A separate run with the gameplay trace completely absent also has one
underrun. Logging is not the sole cause. These are finite diagnostic
comparisons, not release performance guarantees or authorization to change
defaults.

The original audio-frame CPU calls are being measured next to distinguish
different sample work from different interrupt/cache scheduling. No arbitrary
CPU multiplier, fixed-rate replacement or default clock/transport change
has been made.

Private receipts: thread-total-analysis.json, stage-kernel-analysis.json,
thread-total-observer-qualification.json, native-thread-total-qualification.json,
aligned-timing-windows.json, loading-transport-analysis.json,
loading-combined-analysis.json, loading-combined-runs.json.

### Equal audio work and causal device-time result

In the fully covered elapsed-VI window 300-800, both the original-ROM core
and native diagnostic call the audio-frame generator 250 times with 736
samples each (184,000 samples), next-frame count two, and DAC rate 2210.
Mean own CPU cost is 348,723 versus 340,805 cycles. Different sample
production is not the cause in this capture. Cache/writeback and interrupt
ordering still differ; these are not sample-for-sample audio-output hashes.

The original-ROM core with the native CPU formula and RSP compute divided
by 64 produces 135 updates in the same window. Also dividing SP-DMA delay
by 64 produces 137. Dividing both compute and DMA delay by 2048 produces
141, compared with control 125 and native 140. Original microcode and DMA
contents still execute. This is a private causal intervention, not a proposed
clock, fitted multiplier or hardware reference. The native runtime currently
completes graphics tasks after 1,000 Count ticks and audio after 4,000, with
DP at the graphics deadline. Omitting most original device execution time
therefore explains a substantial part of the diagnostic cadence discrepancy.
A separate device-only run checks independence from CPU-cost substitution.

The unchanged control again has matching captured 4 MiB entry/final RAM and
final image. The first combined runner omitted the mandatory CPU-cost trace
and correctly aborted before gameplay; its failed files are preserved.
The corrected runner supplies that observer and uses separate directories.

The loading profile with both fiber transport and direct SP access still
contains 80,964,518 guest instructions across main-update VIs 1688-1809.
The observed host duration is 2.131 seconds with instrumentation, compared
with 2.545 in the earlier instrumented OS-thread profile. These are profiling
runs, not release benchmarks; an uninstrumented diagnostic still had one
loading audio underrun. The largest remaining self host-cost entries include
decompression and guest scheduling. No default transport switch is qualified.

### Hardware and upstream implementation limits

The NEC VR4300 manual describes a one-cycle load-use interlock and separate
store/cache-busy interlocks (printed pages 41-42). Thus replacing every
cache-hit charge with zero would be another approximation, not the proper
general repair. The independently published nemu64-test cases above expose
this distinction. Attempts to download the manufacturer's PDF mirrors failed;
the manufacturer's manual text was read through a mirror:
[NEC VR4300 manual, June 1995](https://manuals.plus/m/c715b005609cb524eac30be04209da9e3d2a168bee77d6662b81dc5561e014ce).

The pinned N64Recomp RSP generator intentionally reports DMA as completed
and ignores yielding in its generated COP0 handling:
[RSPRecomp at ffb39cdad1da](https://github.com/N64Recomp/N64Recomp/blob/ffb39cdad1da5de07eaaa48bd1db4a89a7986771/RSPRecomp/src/rsp_recomp.cpp).
Its functional execution facilities do not supply original task timing by
themselves. A proper Original clock must account for actual workload,
DMA/status transitions, yielding, and the original CPU scheduler; importing
that tool alone or assigning one delay per task type would not establish
native parity. No upstream implementation has been copied in this phase.

Private receipts: audio-frame-work-analysis.json,
device-saturation-analysis.json, device-saturation-default-qualification.json,
device-saturation-correction.json, fiber-loading-cost-analysis.json,
rsp-task-workload-analysis.json. Production timing formulas and default
behavior remain unchanged; Original parity remains open.

### Device-only and matched-boot confirmation

With the CPU model unchanged, the near-instant RSP/DMA intervention produces
136 updates versus 125 in the complete elapsed-VI 300-800 window. A second
intervention preserves normal boot and early gameplay, then activates after
absolute VI 2100. Its entry RAM/image match control and every captured enemy
state and absolute VI before that boundary agrees. Its complete 300-800
window has 134 updates (including some pre-intervention time) versus 125.
These controls demonstrate a device-time effect independent of CPU-cost
substitution and changed startup timing; they do not qualify a release fix.

Observed graphics launch-to-SP intervals vary widely: across the bounded
room-125 trace they range from about 20 microseconds to 31.4 milliseconds;
the room-236 route reaches 23.0 milliseconds. Audio duration also varies.
These ranges include distinct tasks, startup/route phases and synchronization,
so they must not become one fitted delay per task type. The private RSP
profile's raw cycle counter uses 187.5 MHz scheduler ticks (three per physical
RSP cycle); the corrected analysis labels this unit and preserves old rows.

The remaining diagnostic loading underrun is actual host-queue starvation:
the fiber/direct-SP capture observes an empty playing queue near VI 1783.
Loading submissions can be about 58 ms apart after earlier work drains the
cushion; a prior queue snapshot can contain only about 33 ms of audio.
This is separate from the equal guest sample production verified above.
It is not evidence of missing music or a new public audio regression.
Default audio behavior is unchanged.

Private receipts: device-only-analysis.json,
delayed-device-boundary-proof.json, delayed-device-qualification.json,
rsp-task-workload-analysis-units-corrected.json,
loading-audio-starvation-analysis.json.

A lifecycle observer edit stopped on a checked ambiguous SP_STATUS anchor:
both read and write handlers matched. No build ran from that partial edit.
The correction targets the unique write-command handler; failure and
correction are retained in task-lifecycle-observer-correction.json.

### Graphics quality and virtual workload boundary under investigation

Source review found that Actor LOD High temporarily changes the native draw
selection and restores its operands afterward. That preserves the surrounding
actor state, but a future instruction/device clock can still count different
rendering work. A bounded copied-profile Original-clock comparison is checking
whether this is observable before any clock-policy promotion. This is a
compatibility qualification of the diagnostic path, not a newly claimed
regression in the approved LOD feature. Production settings remain unchanged.

## October 28 completed causal research and qualification

### Task yielding and actual workload

The unchanged original-ROM reference records 229 successful yield queries in
room 125 and 162 in room 236. This is actual scheduler behavior, not merely
a source-code possibility. Joining the segments by task/command identity and
observed SP signals gives 232 completed main graphics tasks in room 125:
228 resume after audio; four complete in one segment; one further task remains
unfinished at capture end. The median completed task spans 36.440 ms, including
the pause for audio, with 33.432 ms across its running segments.

Room 236 has 425 completed main graphics tasks, 152 with a resumption. Median
wall time is 18.973 ms; running time is 16.926 ms. Ten Clone-pass segments also
yield. These are emulator observations across captured workloads, not universal
per-frame constants or physical-console measurements. Earlier segment durations
must not be mistaken for full task duration.

The native diagnostic schedules graphics SP completion after 1,000 Count ticks
(about 21.3 microseconds) and audio after 4,000 (about 85.3 microseconds), with
DP completion at the graphics deadline. The complete 300-800 elapsed-VI
comparison is 125 original-reference updates versus 140 native diagnostic
updates. Making device execution nearly immediate in the original-ROM core
produces 136 with its CPU model unchanged, or 141 with the native CPU-cost
formula. The matched-boot intervention agrees on all 267 captured actor
states and absolute VIs before VI 2100, then changes subsequent cadence.
This independently isolates missing device time; those experimental divisors
are not a repair proposal.

The old analysis label command_bytes was incorrect for graphics OSTask.data_size:
the game uses non-byte units for some graphics descriptors. Corrected analysis
retains that field raw. RSP profile counts are 187.5 MHz scheduler ticks; physical
RSP cycle equivalents divide by three. Original rows and informative failed
attempts remain preserved.

### Reference accuracy and tool failures

Published synthetic ROMs from the exact reviewed nemu64-test revision complete
on the pinned newer Ares core with all 4,637 functional base tests passing,
but 924/1,604 timing and 9/13 cycle cases failing. Four limited RSP clock/SLL
tests pass. Neither result establishes full hardware timing. The native
instruction-cost component also misses nine of fifteen selected published
expectations despite accounting consistently for its modeled costs.

Both EmuHawk Mupen interpreter modes remain in the public synthetic IPL3's
PI_STATUS busy loop at all sampled frames; the full attempts time out. Its
older Ares64 core exits C0000005 before suite completion. No pass/fail score
is inferred for either unsuccessful attempt, and no synthetic ROM or state
was patched to obtain a score. This does not invalidate the separate successful
JFG state comparisons. Pinned sources, actual run receipts and implementation
limits are linked in the backend review above.

### Graphics-quality control, audio and acceptance

The Actor LOD Original/High copied-profile pair matches all 1,635 common
flying-actor states and every corresponding absolute VI. The repeated Original
control also matches its earlier capture. Both main-thread cycle means are
identical. Exit snapshots show those three flying actors each have only one
model and a zero detail threshold, so this is a negative control, not validation
of real LOD switching under a future workload clock. No LOD regression is claimed.

Normal guest audio production matches across the complete comparison window:
250 tasks of 736 samples each, with the same frame count and DAC rate. The
remaining diagnostic transition underrun instead occurs when host loading
work drains the playback queue before the next submission. Fiber transport
and direct SP access improve the measured host duration but do not eliminate
that underrun. Normal audio defaults are unchanged.

All seven focused component suites pass: host clock, event commitment, Original
runtime/fast timing, flight motion, flight adapter and function profiling.
The new observer controls preserve captured original 4 MiB RAM/images and
native actor states/VI schedules. These checks qualify the observations, not
a release fix.

The proper next implementation is a qualified guest workload clock and timed,
resumable device execution, with explicit Original simulation policy separate
from output FPS. It must preserve original per-call motion and scheduler waits,
keep graphics enhancements from changing canonical timing, and avoid loading
audio starvation. No constant 20 Hz cap, fitted device delay, emulator-specific
speed multiplier or unqualified clock switch was added.

Private receipts: task-lifecycle-analysis-units-corrected.json,
task-resume-analysis.json, hardware-test-roms/ares-test-classification.json,
hardware-test-roms/emuhawk-qualification-limits.json,
lod-clock-analysis-qualified.json and focused-validation.json, alongside the
earlier causal-window, task-observer and audio-starvation records.
