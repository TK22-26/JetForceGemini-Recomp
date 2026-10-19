# Opening village cadence and cinematic aspect

## Reports (2026-10-17)

- **PERF-004**, moderate: the first new-game village opening cinematic is a
  little choppy in 1.3.0-beta.1. Audio is fine. The owner confirms both ship
  departure and Goldwood ending are now fixed.
- **DISPLAY-002**, moderate: with the original-game widescreen option off,
  gameplay stays 4:3 but cutscenes expand to 16:9. The owner requests restoring
  the chosen aspect now and deferring a video-settings override.
- Status: combined private candidate passes scoped active-shot cadence at 120/360 FPS; aspect passes focused tests/native replay. Loading gaps, presentation and owner visual acceptance remain separate. Neither follow-up is released.

## Evidence and reproduction

Start a new game using the local 1.3.0-beta.1 full-pass capture, leave widescreen
off in the game's Options, and watch the opening village section plus the
transitions between gameplay and cinematics. The completed owner recording
`20261017-172209-eb88b969e7974108b2ed47740d3a8589` and review
`beta1-capture-review/report.json` remain private on the data volume. Runtime
SHA-256: `9b0fd3b1c3572650882e52c74363c6af2cd46bac9daf7ff95647aec5d6de3f98`.
The source is commit `a8144269f86e094426e09ce63af050e2ac4c4b42`.

## Initial hypotheses and limits

The launcher canvas currently follows the runtime resolution byte at
`0x800FECA8`, while the renderer and pointer mapping follow the displayed VI.
A cinematic may temporarily select a resolution independently of the user's
option; this is a hypothesis requiring guest-code and capture verification.
See the earlier [DISPLAY-001 fix](widescreen-pointer-and-airborne-aim.md).
Do not globally suppress genuine user widescreen changes or confuse cinematic
letterboxing with a stretched image. Cadence requires separate timing and
interpolation evidence; a smooth ship test does not verify the village.

No timing change, stable publication, or new video override is authorized by
this record. Preserve original saves, previous builds, production guard and
all investigation counters. Automated tests stay muted and evidence stays on
the data volume.

## Confirmed aspect cause and candidate

The owner's trace switches the launcher canvas to 320x180 at VI 1707 when
the new-game opening starts and back to 320x240 at VI 10642. The same unwanted
change occurs on ship departure at VI 11619 and returns at VI 13594.
The runtime read `sResolutionIndex`, which the game overrides for cinematic
video modes. It is not the saved user preference. The native menu's
`frontGetScreenMode` at `0x8005A804` instead reads bit 30 of the options word at
`0x800FF384`; its paired setter preserves this in frontend settings.

The candidate uses that same saved option for the launcher canvas. The VI and
pointer mapping remain tied to the image the game actually displays, retaining
cinematic letterboxing within the selected canvas. Higher-resolution bit 29
and unrelated flags cannot change the aspect. Focused regression checks cover
each independent settings bit and the observed cinematic VI. Focused tests and full-opening native replay now pass; owner verification is pending; no new aspect override is added.

The completed owner capture has zero audio underruns, overruns, queue recoveries
or dropped frame records. Detailed trace did not hit its cap. Village intervals
5800–6500 and 7800–8800 contain renderer queue waits up to 64–65 ms; surrounding
ship scenes have near-zero queue waits. The cause of those waits remains under
profiling and is separate from the aspect selection defect.

## Village presentation-wait candidate

The baseline muted replay reproduces 103.08 rendered / 15.21 scene FPS at
VI 5800–6500 and 105.65 / 17.48 at VI 7800–8700. The owned-process profile
has no sampling failures and shows the renderer mostly waiting, not executing
the ship's previously expensive draw matcher. GPU workload durations are short.

A concrete timeline shows scene VI 6199 retaining a 10 Hz estimate from its
previous six-VI interval. It emits twelve outputs at 120 Hz. The next authored
scene is already submitted at VI 6202, but preceding shadow workloads wait
77.5 ms on queued presentation events until that old sequence finishes. This
feeds another late interval into the scheduler. Private artifacts:
`village-profile-review.json`, `village-wait-timeline.json`.

The candidate gives a newer authored scene ownership at its actual forward VI
boundary, instead of finishing an obsolete backward interval estimate. Finite
sequences may retire remaining outputs only after that boundary and after at
least one output. Every guest update and graphics workload still executes;
shadow-only submissions, duplicate ticks, paused/captured output and the
unlimited ring cannot trigger this retirement. Timing ownership works with
logging disabled. Native comparisons and correctness checks are pending.

## First candidate result and remaining shadow dependency

The first handoff candidate improved the two troublesome windows from
103.08/15.21 and 105.65/17.48 rendered/scene FPS to 113.31/25.86 and
114.37/25.56. This is not full acceptance. Audio remained clean. The runtime
finished normally; a missing Python `__file__` broke only postprocessing,
which was recovered from retained evidence without repeating the game run.

The remaining dependency also gates small shadow workloads on a later CPU
present event. These already have separate color lists and frame counters.
A second candidate exempts only known non-scene, unpaused 64-pixel shadow
targets without depth access, framebuffer discards or operations involving
another framebuffer. Resource mutexes, GPU fences and scene dependencies
remain in force. Unknown or mixed workloads retain the original wait.
Validation is pending; this is not a released resolution.

## Residual cost and profiling limits

The independent-shadow candidate removes the large presentation gate (the
traced problem windows now have 3.3/5.7 ms maximum workload wait). It still
averages 26.94/27.27 scene FPS; disabling detailed interpolation tracing does
not remove the missed deadlines (24.84/26.56 in that comparison). Thus neither
candidate is accepted as a complete village fix. Ordinary busy updates spend
roughly 31-33 ms outside explicitly measured idle waits.

Function profiling localizes most wall time to graphics task submission and
completion, including seven small shadow passes per update. Preparation of a
typical shadow spends about 0.266 ms copying RAM, 0.102 ms materializing graphics
overlays and only 0.025 ms on presentation identities. The separate renderer
RAM import averages roughly 0.4 ms per submission. Shadow processing guest
leaves are also measured; no speculative gameplay optimization is selected.

An external sampler attempt failed on a Python local-name collision, while
its runtime/function trace completed and remains usable. A later preparation
profile was correctly rejected at startup because full profiling requires
memory-buffered tracing; the corrected run enabled it and watched the separate
progress file for completion. These failures are retained, not counted as
successful performance comparisons. Evidence: `village-residual-profile-review`,
`village-submit-breakdown`, `village-prepare-costs`, `village-leaf-profile-summary`.

## Bounded offscreen CPU optimization

Caller sampling confirms repeated renderer RAM imports and producer snapshots
are significant remaining costs; no unsafe snapshot aliasing was adopted.
An additional candidate avoids rebuilding unused scene-interpolation metadata
for non-scene workloads and avoids UV vertex clones when an offscreen vertex's
UV and texture-generation state are unchanged. Main-scene topology is preserved
because it contributes to interpolation identity. Tests exercise repeated
triangles, changed UVs, and generated-coordinate changes through the real
decoder. The independent shadow gate now additionally requires 64-pixel I8
masks and rejects unknown framebuffer operations.

Four targeted test groups pass. The unprofiled full-opening comparison and
audio health are retained in `village-shadow-cpu-comparison.json`; further
correctness and visual acceptance remain separate gates. Sampling helper
failures (nested quoting and Windows mapping-format assumptions) were recovered
without modifying runtime behavior, with their failed receipts retained.

## Remaining ordinary-play cost and snapshot candidate

FPS-only native comparison confirms a real remaining slowdown: beta.1 averages
16.34/18.81 scene FPS in the two problem windows; the queue/offscreen candidate
averages 26.22/27.26. Audio and frame logging stay clean. Removing unused texture
coordinates only for flat I8 masks averages 27.07/27.08; it is not a complete fix.
The real decoder regression also switches the mask back to textured drawing and
checks that UV ownership resumes. Main-scene topology is unchanged.

The next candidate reuses the changed ranges already found while preparing a
snapshot, avoiding a second complete RAM comparison at import. A pooled image
carries the exact renderer generation it came from. Other imports, presentation,
unknown/new images, or a different pool generation force a full import. Every
GPU-written extent is restored regardless of whether CPU bytes compare equal;
overlay extents and translated display-list writes are explicitly included.
No live guest memory is borrowed. Unit cases cover generation mismatch, first
use, same-value CPU writes after GPU changes, page boundaries, and atomic
rejection of malformed ranges. Build, exact-state and native performance
qualification are pending; this candidate is private and unreleased.


## Final candidate verification and remaining limits (2026-10-17)

Documentation qualification first encountered a mixed UTF-8/Windows-1252 issue
in the newly written notes. Invalid legacy bytes were decoded without changing
valid UTF-8 text, then the notes were saved as UTF-8. The failed receipt is
retained; no runtime change or replay was needed for this documentation failure.

The queue ownership correction removes the long feedback wait, but alone does
not meet the game-update deadline. The subsequent CPU changes retain scene
geometry and skip unused offscreen interpolation/UV work. Snapshot generations
reuse producer dirty ranges at renderer import; all GPU-written extents and
translated display-list writes remain included. Active overlay text is restored
from its immutable image, while current DATA/BSS comes from live overlay memory;
avoiding an intermediate ROM-data restore keeps unchanged pages clean. Unknown
generations still take the full import path. No game or audio clock was changed.

Five focused test groups cover the decoder, snapshot import, interpolation,
workload classification and saved-aspect selection. The final native runtime
passes exact reference correspondence for 2,687 Custom and 1,875 Original
updates: inputs, final game/save/renderer memory and instruction counts match.
Custom interpolation decisions match, and both runs have zero unsupported
accesses. The separate ship-departure native replay remains above 115 rendered
and 29 scene FPS, with zero audio underruns/overruns and frame-record drops.

The final full-capture replay at 120 FPS/VSync measures 119.31/29.76 and
118.18/29.41 rendered/scene FPS in village VI windows 5800-6500 and 7800-8700.
These windows contain respectively two and thirteen three-VI game-update
intervals; quiet windows retain two-VI cadence. Audio underruns, overruns and
dropped records are zero. This is a substantial improvement over beta.1's
15-19 scene FPS, but it does not satisfy the owner's no-20-FPS-dips goal.

The final FPS-only 120/VSync replay measures 119.47/29.80, 118.72/29.63
rendered/scene FPS in the same two windows. At 360 FPS/VSync off, the ordinary
1164x873 replay measures 284.74/17.25, 294.99/17.72, despite quiet intervals near
359/30. The 640x480 comparison measures 284.49/18.59, 298.80/18.93. Resolution scaling
is a diagnostic comparison, not a replacement for the requested presentation
rate or proof that one CPU/GPU stage is the entire remaining bottleneck.

Large scene-transition presentation gaps are also retained in
`village-transition-gaps.json`, rather than hidden by the selected busy-scene
windows. Their cause and visible effect require separate attribution. Zero
audio counters do not imply uninterrupted video. No full-route owner acceptance,
360 Hz display qualification or stable 1.3 release is claimed. The existing
beta.1 launcher is not replaced by this partially accepted source candidate.

Private evidence (same retained investigation directory):
`active-delta-reference.json`, `active-delta-ship-native-check.json`,
`village-active-delta-owner-review.json`, `village-active-final-120.json`,
`village-active-delta-360.json`, `village-active-final-360-small.json`, and
`village-transition-gaps.json`. The tested runtime SHA-256 is
`9713edb70231371ab68049b4e31148e9c42eda4b80512bab39d8bd7a9facd4b5`.
It was built from the candidate working tree; the source qualification receipt
records the subsequent commit. Original saves, binaries and failed experiment
receipts are retained. A first flat-mask reference review failed only because
its expected level was beyond the tested VI endpoint; retained state comparison
already passed, and corrected review recovered the result without a replay.

### Transferable lessons and next discriminating checks

- A cinematic's temporary resolution mode is not the player's saved preference.
  Canvas selection must use the saved bit without altering the actual VI or
  pointer mapping. Test both independent options and cinematic transitions.
- A backward frame-interval estimate can block the next authored scene and
  reinforce a lower cadence. New scene ownership must be explicit; offscreen,
  paused, captured and unlimited submissions require their existing fences.
- Small offscreen targets still pay large host RAM-copy and overlay costs.
  Reusing dirty ranges requires exact snapshot provenance and GPU-writeback
  restoration, including same-value CPU writes. Never alias mutable guest RAM.
- Average rendered FPS is insufficient. Keep scene cadence, actual update VI
  intervals, transition gaps and audio health separately visible. Fixed-clock
  state equivalence establishes correctness, not native performance.
- Remaining work: profile the ordinary-play 360 FPS village producer, GPU waits
  and present scheduling together; distinguish render-rate contention from
  residual CPU preparation. Investigate transition gaps independently. OS dirty
  page tracking could reduce the remaining producer RAM scan, but is only a
  lead and needs explicit materializer/GPU-writeback ownership tests first.

The documentation retry also normalized mixed line endings before exact text replacement; failed queue receipts remain retained. No runtime tests were repeated for that correction.


## Source qualification receipt

Implementation commit: `b9152eb012a9b96fa5f8af8fb4b0eea9ad00ae14` on `fix/goldwood-exit-audio-1.3`.
Current-source hygiene, project validation and isolated single-branch history
qualification pass. Unrelated retained stash objects remain unchanged and are
absent from this candidate ancestry. A further native Original-mode performance
comparison was withdrawn before execution to remain within the guarded window;
the completed Original fixed-clock state-equivalence check remains valid.

The reduced-resolution 360 FPS test still averages only 18.59/18.93 scene FPS
in the two problem windows. This does not isolate the final CPU/GPU cause, but
it rules out a simple assumption that fewer pixels alone resolves this case.
Next work should correlate presentation-rate CPU work and GPU waits with the
producer deadline. Transition-gap attribution remains separate. No new preview
package, full-route owner acceptance or stable release is claimed.

Source: [snapshot ownership](../../../src/renderer/rt64_shell.cpp),
[task preparation and saved aspect](../../../src/boot/native_boot.cpp),
[presentation queue integration](../../../cmake/rt64_video_settings.cmake), and
[offscreen decoder work](../../../src/renderer/rt64_f3ddkr.cpp).


## Owner-authorized pacing continuation (2026-10-17)

The owner approved five more hours to finish the remaining smoothness work,
including additional profiling if needed. The existing production investigation
was continued with its guard enabled, 43 prior attempts, 40 supporting activities
and all elapsed charges preserved. No counter or root was reset. The initial
comparison uses the retained qualified candidate and recorded route at 120 and
360 FPS, measuring synchronous submission waits, GPU durations, preparation and
game-update work. Native Original-mode pacing is a separate control. All tests
remain hidden and muted, with copied profiles and private evidence on the data
volume. This is continued open work, not a resolution or new public release.


### Rate-dependent queue contention candidate

The first 360 FPS detailed profile measures synchronous queue-slot waits up to
47 ms while individual measured GPU draw durations stay below 0.2 ms. Profiling
adds overhead and this run has one audio underrun, so it is diagnostic evidence,
not clean-play acceptance. The pinned WorkloadQueue and PresentQueue producers
both busy-spin, repeatedly taking the cursor mutex until a consumer releases a
slot. That contends with the thread required to make progress.

The candidate replaces those busy loops with predicate condition-variable waits
on the same cursor mutex, and notifies when a barrier advances. Queue ownership,
ordering, GPU fences and guest clocks stay intact. Existing shutdown notification
also releases waiting producers. Native performance/correctness validation is
pending; no physical smoothness or audio acceptance is claimed.


### CPU shadow queue elision candidate

Replacing queue busy-spins alone did not resolve the native 360 FPS deficit:
the busy windows remained around 16.9/18.7 authored scenes per second, with two
audio underruns in that run. The timeline shows seven tiny shadow workloads per
update waiting behind a scene's interpolation outputs. Each shadow already
completed native GPU readback before entering that high-resolution queue.

The next candidate omits only that redundant second submission for a known,
single 64x64 I8 offscreen mask, after synchronous render-to-RAM completes and
only with GPU framebuffer copies disabled. Native rendering, readback, CPU blur,
texture import, guest clocks, interrupts and full-sync cleanup remain active.
Unknown targets, external operations, tile copies, depth, developer mode and
paused rendering retain the original queue path. This is not yet qualified.


### Shadow elision validation and remaining work

Native ordinary 360 FPS playback improves the two busy windows from 16.90 and
18.69 scene FPS with the queue-wait-only candidate to 28.71 and 29.59 with the
duplicate shadow submission removed. Output averages 349.70 and 355.77 FPS;
audio underruns/overruns and dropped logger records are zero. At 120 FPS the
same candidate measures 118.96/29.68 and 118.06/29.40 output/scene FPS, also with
clean audio. Isolated late intervals remain, so this is not final acceptance.

All six focused renderer tests pass. Fixed-clock comparisons match Custom's
2,687 and Original's 1,875 updates exactly for inputs, game RAM, renderer RAM,
save bytes and instruction counts; Custom interpolation decisions also match.
Twelve matched swapchain captures spanning two busy village updates and all
six interpolation phases are pixel-for-pixel identical to the prior candidate.
These screenshot/fixed-clock runs are correctness tests, not audio/performance
benchmarks. Their intentional overhead is retained in the private results.

Private evidence is in `village-pacing-20261017`: `cpu-shadow-reference.json`,
`shadow-pixels-comparison.json`, `shadow-coverage-evidence.json`, and the two
`cpu-shadow-queue-*-review.json` ordinary playback receipts. Profiling of the
remaining deadline misses continues. Owner visual review is still pending.


### Cached overlay restoration candidate

After shadow queue elision, measured queue waits are negligible (maximum
0.032 ms in the profiled busy section), but 27 of 336 update intervals still
take three VIs. Preparation scans cost roughly 2.04 ms per update for base RAM
plus 1.05 ms for overlay materialization; submission import adds 1.18 ms.
The main scene decode also remains significant. Windows write-watch is not a
drop-in option because guest RAM uses two mapped aliases, so no such memory
mapping change is being attempted.

The next candidate tracks ranges changed in each cached expanded overlay
snapshot. It restores only those ranges of immutable TEXT/inactive modules,
and carries active DATA/BSS ownership forward even when values stay unchanged.
Current live DATA/BSS and pointer translation still run for every task. Fresh
cache entries use the existing complete initialization path. Focused tests
cover unchanged active data, module unload, and invalid-range atomic rejection;
native replay and exact-state qualification are pending.


Overlay-range correctness matches all 2,687 Custom and 1,875 Original samples,
including RAM, inputs, saves, instruction counts and Custom interpolation
decisions. Its first native 360 FPS run measures 29.32/29.49 scene FPS with
clean audio. However, the 120 FPS run regresses to 16.11/26.75 scene FPS in the
busy windows. This candidate is not accepted. Controlled repeat comparisons
against the retained shadow-elision binary will distinguish reproducibility
before any further optimization is layered on it. The failed performance
receipt is retained as `overlay-ranges-120-review.json`.


### Bounded VI import candidate

The native VI path copied all 4 MiB of guest RAM into a staging image, scanned
all 8 MiB into RT64, and invalidated the pooled task generation every refresh.
The pinned `State::updateScreen` reads only the selected VI image and its known
framebuffer's RAM extent. This repeated full import also forced a subsequent
task to scan all 8 MiB again.

The candidate imports the union of those validated framebuffer extents. It
tracks every imported byte range alongside device-write ownership, so a later
CPU edit back to the cached value still overwrites the private renderer RAM.
Known normal VI consumers preserve snapshot generation; unknown/debug consumers
refresh all supplied CPU RAM and retain conservative invalidation. No mutable
guest pointer is retained. CPU overlay retention, framebuffer hashes and VI
presentation operations still execute. Focused tests cover range limits,
overlap merging and the same-value reversion case. Qualification is pending.


The bounded-import trial's first build rejected implicit `size_t` narrowing in
its optional trace fields. The retry casts only after the existing 8 MiB range
validation. The failed build and dependent unexecuted replay receipts remain
retained. Screenshot capture is armed after validation, avoiding a pending
capture flag on an invalid import. No runtime qualification is claimed yet.


### Controlled repeats and measurement limits

The retained shadow-elision control also loses some cadence in the repeat
session. Overlay-cache repeats recover from 27.75/28.36 to 29.25/29.03 scene
FPS, while the control measures 29.16/28.50. All three have clean audio. System
CPU usage falls from 36.5% to 29.7% across these sequential runs. A subsequent
diagnostic records a separate Scooby game test plus other host work; these
measurements are not isolated and do not attribute the first 16 FPS result
uniquely to source changes. No unrelated processes were terminated.

Measured overlay preparation falls from 0.129 to 0.068 ms per submission in
the two detailed 120 FPS comparisons. Exact-state checks remain clean. The
bounded VI import also passes all 2,687 Custom and 1,875 Original exact samples,
including renderer input RAM and interpolation decisions. Full-opening native
play, actual-pixel equality and real-weapon reticle checks are recorded separately
from these fixed-clock correctness runs; fixed-clock audio counters do not
qualify native playback. Large scene-transition gaps remain explicitly separated
from the busy-window averages pending attribution.


### Strict missed-deadline continuation

The owner explicitly rejected accepting even one late update in the 798 busy
intervals. Preview handoff is held while that deadline miss is attributed and
addressed. No beta.2 package or commit was produced by the queued preparation.
The following repeated trace was labelled 360 but its nested test-template
replacement did not match: its recorded configuration is actually Custom 120
with VSync, stopping near 9,000 VI. It is retained as a second 120 FPS run, not
360 evidence. It reproduces 131 three-VI busy-window intervals and one audio
underrun, and correctly blocks the proposed qualification and dependent jobs.
The much worse repeat requires investigation; the clean first run is not enough
to accept the candidate. Failed test-harness/qualification receipts are retained.


The isolated missed update contains a cold section-8 reload and about 2.93 million
instructions, versus 1.53 million immediately before it. This is a correlation,
not proof that the small host overlay publication itself dominates. Deep function
profiling identifies the repeated integer shadow filter as the largest ordinary
guest CPU leaf (about 0.8 ms/update averaged, 1.98 ms in the cold update). An opt-in
candidate executes the same pinned generated integer leaf without per-instruction
bookkeeping, with a validated 4 KiB cached-RAM image, nonaliasing pointer field,
unchanged registers/memory and elapsed-clock refresh at return. Original timing,
recorded-clock replay, detailed instruction observers and unknown inputs retain
the generated path. Private differential and native timing qualification are
required before enabling it; this is not a game-clock or FPS-counter adjustment.


The opt-in filter passes 2,048 randomized/boundary original-C comparisons for
the complete CPU context and all 4 MiB of RAM, plus 11 rejection cases without
mutation. The fixture measures about 9.7 times less execution time; it does not
establish a game FPS result. Source extraction is digest-pinned and rejects even
known external callees, with synthetic guard tests. The first fixture command
failed before compilation because of developer-environment quoting; a separate
checked command file corrected it. All failed receipts remain preserved.


The four controlled native-elapsed filter trials all complete with zero audio
underruns/overruns and no dropped trace rows. The enabled 120 FPS run has 10 late
updates in the two busy windows (versus 72 for its preceding control); the 360
run has 29 late updates (versus 25 for its following control). Host load varies,
so the differential leaf speedup is established but these runs do not prove a
uniform frame-rate improvement or meet the owner's zero-miss criterion. The
preview remains held and the filter remains opt-in.

A detailed enabled-filter trace attributes late updates to approximately
15-22 ms of synchronous graphics submission, plus 2-5 ms of snapshot copying.
The asynchronous semantic-history join is usually below 0.02 ms; a blanket
thread-pool replacement is not supported by this evidence. The memory-only
gameplay trace reserves its entire bounded buffer before play, ruling out
vector growth during the route. An external call-stack sample is being used
to attribute the remaining renderer copy/submit cost; its own suspension overhead
disqualifies that sample as an FPS benchmark. Evidence is retained under
`village-pacing-20261017/native-filter-residual-misses.json` and
`residual-attribution-review.json` on the private data volume.


External call stacks identify repeated Windows guard-page/single-step exceptions
and VirtualProtect calls in SP task setup, alongside actual graphics work. An
opt-in direct-SP candidate retains all six pinned generated routines' instruction
probes, branches, registers and RAM operations, but routes their qualified SP
register words through the same existing device helpers used by the exception
handler. It preserves the I/O revision, SP launch/interrupt effects and MMIO
journal. Unknown addresses/operations fall back to guarded memory. It does not
disable page guards or the production investigation guard. Fixed-clock state and
event parity plus native timing qualification are pending; default remains off.


The direct-SP trial passes 2,687 Custom and 1,875 Original fixed-clock samples:
inputs, CPU RAM, renderer RAM, save data and instruction counts are identical;
Custom interpolation decisions also match. The trials cover 163,304 and 64,974
direct device accesses, with no unsupported accesses. Nine focused renderer,
SP device and event-batching tests also pass. These establish bounded correctness,
not native pacing qualification. The private receipt is
`village-pacing-20261017/direct-sp-reference.json`.

The first quiet-host preflight incorrectly treated idle reusable MSBuild servers
as active compilation. Its own waiting helper was cancelled without touching
those servers or the production supervisor, and the failed receipt is retained.
The replacement checks actual CPU activity; the other game's diagnostic had
closed before the comparison started. No guard state or counters were reset.


The direct-SP native comparison improves ordinary active update time but still
misses the strict deadline criterion: two three-VI intervals at 120 FPS and one
at 360 FPS in the busy windows. Both rates have zero audio underruns/overruns,
zero unsupported accesses and no trace loss. The repeated section-8 cold update
remains late; the 120 run also has an independent late update near VI 8609.
This is partial improvement, not a resolved issue or a qualified preview.
Evidence: `direct-sp-comparison.json` and `direct-sp-cold-attribution.json`.


Thread-transport profiling measures roughly 2-3 ms in recipient wake latency
across 94-174 transfers in sampled late updates. A separate opt-in candidate
polls the published baton recipient for at most 50 microseconds before taking
the original mutex and condition-variable wait. Scheduler order, one-runner
ownership and cooperative shutdown remain unchanged; no GPU wait or game tick
is skipped. It can trade some CPU time for lower short-handoff latency and must
pass exact-state and native performance comparisons before any default change.


The first bounded-spin build caught a missing forwarding method on the guest
transport wrapper before any replay ran. The checked recovery adds that method;
the compile failure and dependent nonexecuted replay receipts are retained.


### Eight-hour continuation: cooperative stack transport candidate

The bounded 50 us spin trial failed native qualification: at 120 FPS the late
7800-8700 VI window had four three-VI updates; at 360 FPS the two busy windows
had four and nine respectively. Audio underruns and trace drops remained zero.
It remains opt-in and is rejected as the pacing fix. Evidence is retained in
`D:/JFG-private/goldwood-exit-1.3-20261017/village-pacing-20261017/baton-spin-comparison.json`.

The owner approved eight additional hours at 23:01 UTC October 17, through
07:01 UTC October 18. The prior guarded session was independently graded and
charged; the same investigation was continued with no counter/root reset.
Zero late visible updates remains the qualification requirement.

A default-off Windows fiber transport now prototypes the same guest-directed
stack handoffs on one OS thread. This removes parked-thread wakeups without
parallelizing guest execution or changing game timing. Overlay invocation
leases, pending generated dispatch, collision recursion and function-profile
stacks use explicit execution-local contexts. Context caches invalidate on
every switch and lifetime transition. Renderer dispatch and submission TLS,
RSP broker TLS, presentation sampling, and single-step SEH state remain TLS:
those scopes never yield a guest continuation. Floating-point state is saved
on each Windows fiber switch; stacks inherit the executable's stack reserve.
Shutdown unwinds each parked stack before deleting it. ASan and non-Windows
builds retain OS threads. This is an unvalidated candidate, not a completed fix.


Prototype build checks found two setup faults before any replay: source reads
initially used the Windows code page instead of UTF-8, then generic storage in
the minimal generated bridge introduced extra externally emitted symbols.
The bridge audit was retained unchanged. Call-path review established that its
pending one-shot target is consumed and cleared before callback dispatch can
yield; that field remains ordinary TLS and the bridge source is byte-for-byte
identical to HEAD. The other suspended-call state still uses per-stack storage.
This corrects the broader initial TLS inventory above. Failed build and dependent
nonexecuted replay receipts are retained.


The first cooperative-transport build passes four focused tests, including
deterministic scheduling, isolated stack state, FP rounding, exception transfer,
cross-thread rejection and stack unwinding. Its fixed-clock Custom 2,687 and
Original 1,875 samples exactly retain inputs, RAM, save, renderer RAM and guest
instruction counts; Custom interpolation decisions also match.

Native 120 FPS has zero late updates across the three measured village windows,
with zero audio underruns/overruns and trace loss. Native 360 FPS has one late
update at poll 3027 / VI 6387, containing the section-8 cold load: 49.312 ms wall,
15.686 ms explicit wait and 33.626 ms active. A separate Scooby diagnostic was
running during this comparison; neither the miss nor the improvement is being
attributed solely to that load. The candidate remains unqualified. Current
evidence: `fiber-reference.json`, `fiber-comparison.json`, `fiber-cold-functions.json`
and `fiber-cold-stages.json` in the retained private pacing directory.
Deep function instrumentation is attribution evidence, not an FPS test. With
the fiber backend, raw Windows thread-cycle counters include all guest stacks
on that host thread; they must not be interpreted as exclusive per-guest cycles.


The fiber attribution follow-up now samples logical participant cycles: measured
switches accumulate each participant's running cycles and exclude parked time.
Function and update-cycle events use a high-bit participant ID for fibers;
submission/OS-thread events retain real Windows thread IDs. Normal unprofiled
execution performs no added cycle queries. Tests distinguish a parked stack from
another stack doing substantial CPU work. An empty pre-start backend selection
can also return to OS threads without leaving the executor cancelled.
These changes need build, replay and pacing revalidation before qualification.


Next opt-in candidate: the pinned whole-cache maintenance routine walks 512
cache lines per call, often eight calls per update. Our existing explicit
coherent-memory model validates these operations without moving RAM. The new
private generated variant retains all register effects, inlines the identical
validation, and removes per-instruction bookkeeping only under the same native
elapsed-time admission used by other qualified leaves. Recorded-clock and
detailed instruction observers retain the original routine; GPU readback and
memory ownership are unchanged. This optimization is invalid for a future
dirty-line/tag cache model and must not silently carry over to one. Source pins,
full CPU/RAM differential tests and native replay are required before acceptance.


The first cache-walk native replay deliberately rejected its own qualification:
the activation counter was zero. The helper was attached to ordinary game
dispatch, but this SDK entry uses the separate mapped-OS dispatch path. That
run still had zero late 120 FPS updates, but supplies no evidence for cache
acceleration. The remedy moves the same guarded helper to its actual SDK call
site; the original mapped body must still exist and remains the fallback.
The failed activation assertion, unstarted harness withdrawal and replay are
preserved in `cache-all-admission-review.json` and the guarded step receipts.


The corrected mapped cache path activates (18,924 calls in its first 120 FPS
run), but the first native comparison records additional late updates, including
a 123 ms active interval without an overlay-cold event. It is not accepted as a
fix. The two-VI requirement is retained; follow-up attribution separates actual
CPU work, synchronous submissions, explicit waits and scene events. Evidence:
`cache-all-mapped-comparison.json` and `cache-all-late-attribution.json`.
The earlier nonactivated run remains a separate control and must not be labelled
as a cache-optimization result.


The mapped-cache follow-up holds the output target at 120 FPS and crosses
cache acceleration with VSync enabled/disabled. Runtime/profile are held fixed;
lightweight process CPU observations accompany each run. This distinguishes
the two variables conflated by earlier 120/VSync versus 360/no-VSync captures.
Per-run results, including every late update, are retained in
`cache-vsync-factorial.json` and `cache-vsync-attribution.json`; this experiment
alone does not establish full-route qualification.

The first four-way report parser expected optional detailed submission
stages in lean captures and rejected their absence. The corrected report
marks these costs unmeasured rather than zero. Dependent build/replay steps
refused execution. No failed executable or capture was delivered.


After the owner confirmed the other diagnostic would remain paused, the
next full opening replay removes broad process enumeration and optional
per-fiber cycle queries. It retains the in-memory update/submit timing trace
and ordinary FPS log, uses copied profiles, and runs muted at 120/VSync and
360/no-VSync. This is a new qualification attempt, not a reinterpretation of
the earlier misses. Evidence: `quiet-fiber-full-comparison.json`.


The longer lean capture still has isolated stalls and audio interruptions.
A private diagnostic now samples Windows context-switch counts, dispatch wait
reasons, host-thread CPU/cycles and process-wide page faults around root updates,
plus submission waits and snapshot stages. Fiber host samples include all guest
stacks executing on that host thread; they are not exclusive root CPU costs.
Only the root interval reads/reset dispatch wait bits, avoiding nested-reader
loss. Page faults are process-wide correlations, not proof of root ownership.
Source and ordinary runtime are restored after freezing the private build;
this instrumentation is not enabled in the preview or FPS qualification.
Evidence: `host-dispatch-diagnostic` and subsequent private captures.

The private scheduling build passes exact retained Custom/Original replay
comparison before native collection. Per-update host dispatch samples are
joined by VI/poll and timestamp; missing or invalid rows reject attribution.
The detailed native results are retained in `host-dispatch-attribution.json`.
These measurements remain separate from ordinary frame-rate qualification.


Owner clarified that equivalent output permits changing the underlying code,
including algorithmic and data-structure replacements. Private candidates have
not passed zero-miss qualification; the desktop beta.1 remains unchanged.
Instrumented host scheduling captures are attribution evidence, not a delivered
regression or acceptable performance comparison. The next work targets repeated
CPU graphics processing and allocation, retaining full output comparisons and
ordinary, uninstrumented performance qualification.


A code optimization candidate reuses per-interpreter semantic input/output,
geometry, local-index, count and inverse-transform scratch. Shape history also
retains each entry's key allocation instead of destroying all keys per scene.
All logical lengths, flags and ownership are reset; published render frames
remain immutable and separately owned. Semantic work is joined before scratch
reuse, including future destruction on exceptions. Matching rules and floating
point calculations are unchanged. Focused history/semantic tests pass, including
stale-output reset, growth/shrink, empty/offscreen scenes and identity reuse.
Exact retained replay and native performance comparisons remain pending.
Evidence: `interpolation-scratch` and frozen `interpolation-scratch-runtime`.

The scratch candidate passes the retained Custom/Original output comparison
before an alternating ordinary native comparison against the frozen prior
candidate at 120 and 360 FPS. Both binaries use identical optimization flags;
per-function and host-dispatch instrumentation are absent. Native comparisons
retain update timing in memory and audio/drop counters. Results are preserved
in `interpolation-scratch-reference.json` and `interpolation-scratch-comparison.json`;
a completed run is not itself a zero-miss qualification.


A separate algorithmic candidate resolves model/palette identities once per
F3DDKR vertex batch, then intersects contiguous source ranges with model
ranges. The scalar implementation remains as an independent definition and
fallback for oversized/wrapped batches. Deterministic differential tests cover
overlapping geometry, ambiguous palettes, model order, empty ranges, source
alignment and uint32 range overflow. This removes repeated full model-list
scans per vertex while retaining the first-owner and ambiguity policy exactly.
Full replay and performance verification remain pending. Evidence: `batch-identities`.

A separate component benchmark compares retained original history classes
and scalar lookup with the new code, alternating order over six repetitions.
It checks matching output checksums and counts allocations/bytes after warmup.
This measures the specific eliminated work independently of native scene timing;
it is not a substitute for FPS qualification. Evidence: `optimization-components`.


Owner confirmed all other work on this PC is paused during this continuation.
Exclusive machine use is a measurement condition, not a product requirement.
The scratch comparison does not qualify: 120 FPS candidate has five audio
underruns and eleven late updates in selected windows; 360 FPS candidate has
two underruns and twenty-nine late updates. The prior 360 FPS control also
has two underruns and worse long stalls. No external workload is established
as the cause, and none is being used to dismiss these failures. Both ordinary
controls and candidates remain unqualified; the desktop preview is unchanged.
A bounded stack sample of the current optimized runtime will locate remaining
CPU and synchronization work. It is attribution-only, separate from native FPS
measurements and the component benchmark. All comparisons retain failures.


New [PERF-005 / GitHub #19](github-invasion-replay-stutter.md) reports a severe
invasion replay collapse on the same GPU model in v1.2.0, using Unlimited with
VSync. This expands configuration/entry-route coverage; existing capped
new-game comparisons do not independently reproduce the reported tribal replay.
The finite display-rate path applies with VSync, not the uncapped ring.


The current bounded stack profile contains 1,003 samples at the performance
counter under RT64 preciseSleepUntil on the presenter, plus other polling
samples. These are sampled wall-stack observations, not a whole-process CPU
percentage. The pinned implementation estimates short sleeps then busy-polls
until its deadline. A private, default-off candidate uses the existing Windows
high-resolution timer for the bulk wait and polls only the final 100 us. It
preserves the original target timestamp, never treats an early wake as due,
and falls back to the pinned implementation if the timer is unavailable.
Concurrent deadline checks pass. Native pacing, CPU and exact-output
qualification remain pending. This is not yet a cause or fix claim for #19.
Evidence: batch-identities-stack-review.json, presentation-timer.

The timer component comparison alternates original/candidate order at 120,
240, 360 and 1000 Hz. It records actual thread CPU time and deadline overshoot,
rejecting early completion. This isolates pacing cost but does not qualify
game simulation or monitor scanout. Evidence: presentation-timer-component.


## Quiet-PC optimization results (2026-10-18 UTC)

Retained Custom and Original comparisons for scratch reuse and batched
identity lookup preserve RAM, saves, renderer RAM, instructions and available
interpolation decisions exactly. Scalar/batch differential tests also pass.
The component benchmark measures identity lookup at about 10.95 times faster
(106.84 versus 9.75 ms for the selected workload). Semantic output allocation
falls from 164,035,500 to 176,000 bytes over 500 benchmark frames. These are
component results, not total-game speedups.

- control120: 0 late updates across the four selected windows; 0 audio underruns.
- native120: 3 late updates across the four selected windows; 0 audio underruns.
- native360: 0 late updates across the four selected windows; 0 audio underruns.
- control360: 1 late updates across the four selected windows; 0 audio underruns.

The optimized 360 run is clean in these windows, while the optimized 120 run
still has three late updates (VI 6152, 8319, 8322), without cold publications.
This remains a failed zero-miss qualification. Other parts of the full opening
contain long scene-transition gaps whose visibility/expected timing still
need classification; selected windows do not certify the entire route.
Evidence: batch-identities-comparison.json, optimization-components/summary.json.


The stack sample also locates duplicate framebuffer hashing on the guest
thread. The preliminary CPU-mask pass hashed every screen/depth target, then
the immediately following checkRDRAM hashed them again. Its only consumed
results were I8 color masks. The candidate checks those masks directly and
reuses their first hash, preserving map-key/addressStart behavior, dirty flags,
read heights and the following all-framebuffer check. No framebuffer upload,
CPU overlay or ownership decision is removed. Shell checks pass; exact RAM,
reticle pixels and native performance qualification remain pending.
Evidence: mask-hash-filter.


The fixed-100-us presentation timer candidate FAILED native output pacing:
120 FPS output fell to approximately 116 FPS despite unchanged simulation.
It remains disabled. The isolated component comparison also ran without the
application timer environment or warmup, so its original-timer coarse sleeps
cannot support a production CPU-ratio claim. Native comparisons are authoritative.
A revised default-off candidate observes actual timer wake overshoot and keeps
a bounded 0.5-2 ms polling margin (starts at 0.75 ms, rises immediately, decays
1 us/wake). It retains the exact original deadline and checks it after waking.
Repeated concurrent deadline tests pass; native pacing/CPU qualification is
pending. Evidence: presentation-timer-comparison.json, presentation-adaptive.

Current ordinary native comparisons retain every update interval greater
than two VI, including intervals outside selected visible-scene windows.
A separate analysis joins existing lightweight submit/RAM-check/full-sync
counters by timestamp without rerunning or instrumenting the game. It retains
long transition gaps for visual classification; none are silently discarded.
Evidence: current-native-late-attribution.json. Qualification remains open.


## Wall-clock acceptance and remaining device-trap attribution

Ordinary mask-comparison controls contain 84-172 ms active host stalls even
where adjacent game-update VI values still differ by two. VI coalescing means
zero three-VI intervals alone cannot qualify a run. Acceptance must additionally
check wall-clock game-update intervals, actual presentation intervals and audio
counters. Historical zero-VI-miss statements retain their stated metric and
must not be promoted to zero wall-clock stalls. The latest controls fail.

A private default-off MMIO profile counts actual guarded device accesses by
hardware page and spans handler/single-step wall time. Direct SP accesses do
not enter these counters. It also records cumulative root-thread CPU time and
cycles; quantized thread times need aggregation. No device values, interrupt
order, memory protection or guest timing change. Handler spans include host
preemption and exclude kernel dispatch before handler entry, so they are not
pure CPU percentages. No per-function instrumentation or stack suspension is
required. Exact reference and native attribution are pending. Evidence:
mmio-attribution; performance acceptance remains open.

The diagnostic runtime copies were launched from a SATA HDD (D:), while C:
is NVMe. A same-binary paired comparison moves only verified runtime files to
C: and retains profiles/traces/evidence on D:. All optimization/pacing settings
remain identical, with the timer experiment disabled. No caches are flushed;
byte verification itself reads the files, so placement results alone do not
prove cold image paging as the cause. Runtime storage is a hypothesis for
isolated host stalls, not an explanation for the released sustained slow scene.
Evidence: runtime-storage-comparison/identity.json and results.json.

Wall-clock qualification review now includes every source-update interval,
source-scene delivery change and present-return interval in the four retained
visible windows, plus the largest full-route gaps. It explicitly retains long
host gaps hidden by two-VI counter deltas. The 42 ms review threshold flags a
substantial excursion from the normal approximately 33.4 ms game interval;
it does not claim smaller fluctuations are absent. No qualification is inferred
from a completed harness or a zero VI-only count. MMIO attribution separately
aggregates handler wall spans and cumulative host CPU times by hardware page.
Evidence: wall-clock-qualification-review.json, mmio-attribution-review.json.


Storage experiment correction: C:/JFG-builds/high-refresh-20261011 is
a retained junction to D:/JFG-builds/high-refresh-20261011. Consequently the
runtime-storage-comparison cases are all on the HDD; its SSD identity claim is
incorrect and those results cannot compare physical drives. The original
evidence is preserved. A replacement uses C:/JFG-qualification-runtimes outside
that junction and checks resolved drive identity before copying and testing.
Evidence: runtime-physical-storage-comparison. Ordinary timing measurements
from the earlier run remain usable with both locations correctly labelled D:.

The diagnostic runtime copies were launched from a SATA HDD (D:), while C:
is NVMe. A same-binary paired comparison moves only verified runtime files to
C: and retains profiles/traces/evidence on D:. All optimization/pacing settings
remain identical, with the timer experiment disabled. No caches are flushed;
byte verification itself reads the files, so placement results alone do not
prove cold image paging as the cause. Runtime storage is a hypothesis for
isolated host stalls, not an explanation for the released sustained slow scene.
Evidence: runtime-physical-storage-comparison/identity.json and results.json.

This follow-up retains every wall-clock update interval above 42 ms, including
coalesced two-VI gaps, including intervals outside selected visible-scene windows.
A separate analysis joins existing lightweight submit/RAM-check/full-sync
counters by timestamp without rerunning or instrumenting the game. It retains
long transition gaps for visual classification; none are silently discarded.
Evidence: coalesced-gap-attribution.json. Qualification remains open.

This follow-up retains every wall-clock update interval above 42 ms and
adds the separately measured host-present call duration, including intervals outside selected visible-scene windows.
A separate analysis joins existing lightweight submit/RAM-check/full-sync
counters by timestamp without rerunning or instrumenting the game. It retains
long transition gaps for visual classification; none are silently discarded.
Evidence: gap-present-attribution.json. Qualification remains open.


## Context-switch interrupt-mask access candidate

The new trap profile identifies the MI register page as a substantial remaining
exception source. Three pinned context-save/restore instruction sites now have
a private, default-off variant that calls the existing qualified MI-mask
bridge. This retains probes, span guards, fallback access, journals, device
revision and interrupt semantics; the interrupt-entry variant also preserves
the prior direct-SP changes. Original generated files are untouched. Existing
mask-command qualification is reused; full state and native performance checks
are pending. Evidence: context-mask-access, context-mask-runtime.

The first context-mask wrapper stopped before compilation: its negative
fixture changed the first matching instruction word, which belonged to an
earlier timing-span commit rather than the execution hook it intended to test.
The production generator still checks the complete pinned source hash. The
corrected fixture targets the exact PC/word execution-hook pair; no rejection
rule is removed. Dependent exact/native jobs stopped at their prerequisites
and performed no replay. All failed receipts remain preserved.

The MMIO attribution captures large wall-clock pauses with little root-thread
CPU consumption and less than 2 ms in measured device handlers. Controller
configuration currently reopens up to twelve profile files synchronously every
250 ms on the game thread. This is a concrete blocking-I/O hypothesis, not yet
the proven cause. A separate default-off host-stage profile measures config,
input, device discovery, audio, window, VI and overall video servicing with
wall time and same-thread cycles, retaining only calls above 1 ms. Nested
spans overlap and must not be summed. Evidence: host-stage-attribution.


### Current merged 1.3 normal-Play control

The merged candidate with background settings/map reads and opt-in blur mode 4
completes normal Play at 120/VSync and 360/no-VSync without audio errors.
The opening still fails zero-miss acceptance: shot 325 contains three late
three-VI updates at 120 FPS and one at 360 FPS. Recorded wall gaps are
49.668-51.326 ms; host I/O spans do not explain them. Other native fast-path
experiments remain disabled in these controls. See vela-composite/current-village
and rescue-village-wall-review.json. Exact-output shadow/cache leaves are the
next isolated CPU-headroom comparison; no timing or fidelity acceptance yet.


### Texture-upload worker attribution

A focused entry profile reproduces the late shot-325 update. The world
submission takes 12.15 ms, with 5.55 ms waiting for texture uploads; individual
measured framebuffer GPU submissions remain below 0.13 ms in that run.
The five subsequent shadow submissions total about 8.05 ms. These are nested
wall spans, not additive GPU percentages. A private, default-off worker profile
now separates upload-buffer/descriptor allocation, TMEM resource construction,
decoded-resource setup, replacement lookup, command recording, fence completion
and cache publication. Same-thread CPU-cycle deltas accompany wall time.
Every original queue operation, wait and resource lifetime remains intact.
Performance and output are not changed by this instrumentation when disabled;
build and recorded-route verification are pending.

The first profile-analysis pass accidentally interleaved VI ticks with game
updates, hiding long game-update intervals. The corrected analysis selects
game updates only; both artifacts remain retained. Evidence:
current-village-entry-profile/attribution-v2.json. This profile is attribution,
not a zero-slowdown qualification.


The worker profile isolates a 126-texture batch with 6.24 ms total work:
2.54 ms constructing TMEM resources and 2.83 ms preparing decoded textures,
versus 0.24 ms for final GPU submission/completion. The CPU-cycle samples
support resource preparation as real CPU work, not merely an idle fence.
The repeated profiled run happens to avoid the prior missed-update threshold;
that does not establish a fix or invalidate the earlier miss.

An opt-in resource-recycling candidate now reuses only texture resources that
RT64 was about to delete at its existing zero-lock retirement boundary. Exact
TMEM length, dimensions, format and decoding mode must match; replacements
and mipmapped resources are rejected. Every byte upload, decode, descriptor
update, cache version, barrier and fence remains unchanged. Free resources are
bounded to 256 entries and an estimated 64 MiB; ownership is per texture-cache
instance and destroyed with it. The purpose is less driver resource creation,
not lower texture detail. Build, pixel/RAM equivalence, reuse counts and native
pacing checks are pending. The candidate remains disabled by default.

Evidence: current-village-entry-texture-profile/texture-upload-review.json.


The first recycling build rejected a defaulted comparison operator because the
pinned RT64 target uses C++17. Replacing it with the equivalent explicit member
comparison preserves that target's language level. The dependent replay stopped
at the failed-build prerequisite and performed no game run. Failed build logs
remain retained; no parity or pacing result is claimed from that attempt.


The recycling candidate now builds with the pinned C++17 target, and renderer
shell/texture checks pass. With the same executable and fixed guest-clock input,
all twelve paired shadow-scene images are pixel-exact with reuse off/on. Final
logical RAM, renderer RAM and FlashRAM hashes also match. The route exercises
3,039 recycled allocations (949 misses); free-resource retention peaks at
41,418,752 estimated bytes and remains within both bounds. These are image/state
checks, not elapsed-time performance evidence: the deliberately fixed-clock
probe's slower cadence/audio events cannot establish a normal-Play regression.
The ordinary 120/360 FPS comparison is separate and still pending.

Private evidence: texture-recycling-pixel-parity-v2/proof.json and
shadow-pixels-comparison.json; runtime c77ef02cf32a858f6be393565388b2ef72afe0708d0110e96b4d0cd010b4dee4.


### Recycling queue-ownership correction

Source review found a compatibility gap despite passing pixels: the pinned
Plume D3D12 copy command list deliberately skips transition barriers. A reused
TMEM texture was still in a shader-read state from a direct queue. Before a
new copy queue upload, it must transition to COMMON on a direct queue and
complete that handoff. See Microsoft's
[resource-state contract](https://learn.microsoft.com/en-us/windows/win32/api/d3d12/ne-d3d12-d3d12_resource_states)
and [promotion/decay rules](https://learn.microsoft.com/en-us/windows/win32/direct3d12/using-resource-barriers-to-synchronize-resource-states-in-direct3d-12).

The corrected candidate batches those retired TMEM transitions on the existing
direct worker and waits for completion before submitting copies. Fresh resources
retain their original path. Every previous wait remains. Prior pixel and timing
results describe the pre-handoff candidate and do not qualify this correction.
This was found in the private default-off experiment; no public release uses it.
A pending capsule capture using that old experimental runtime was withdrawn.
The corrected candidate requires a fresh build, image/RAM comparison and native
timing review. Handoff duration is recorded separately when tracing is enabled.

The earlier normal-Play comparison was also mixed: candidate 360 FPS had no
late active-shot intervals, while candidate 120 retained one 52.026 ms entry
interval. Controls had zero late active-shot intervals at 120 and two at 360.
All four were audio-clean. Resource reuse is therefore not yet a qualified
zero-miss fix, even apart from the queue-ownership correction.


### Corrected handoff qualification and decoded-only alternative

The corrected full-resource reuse path passes a new 12-frame full-size pixel
comparison, with identical CPU RAM, renderer RAM and save hashes (step 476,
runtime 08e25fcc195069fb6f562f3c00ac304cc3374b58389d248f98b597fd7b56ae52).
The fixed-clock probe is not native timing/audio acceptance.

Combined with the exact-output shadow/cache leaves and direct SP access,
normal Play at 120 FPS/VSync has no late active-shot intervals. At 360 FPS,
shot 325 still has three three-VI intervals at VI 6513, 6516 and 6519,
49.638-51.235 ms. All earlier selected windows pass, demonstrating why the full
shot must be checked rather than only those windows. Audio and access counters
are clean in both runs. Menu/scene-loading gaps remain recorded separately.
This fails zero-miss acceptance. Evidence: texture-recycling-handoff-direct-sp.

A private mode-2 alternative now recycles only decoded RGBA textures after
the same completed-GPU/zero-lock retirement boundary. Every TMEM resource is
fresh, so copy-queue ownership retains the original path without an added
handoff. Reused decoded resources remain on direct queues and use the existing
shader-read-to-UAV transition before full re-decoding. Keys retain exact RGBA
dimensions/format; all byte uploads, descriptors, cache versions and fences
remain intact. Mode 1 is retained solely as the bounded comparison. Both
remain disabled by default. New build, pixel/state and timing checks are pending.

Selection captures at VI 1300 and 1360 show the native camera approach and
Vela stepping out; they do not reproduce the owner's closed green capsule
screenshot. Held-selection images likewise do not qualify that reported state.
Private evidence: vela-selection-confirmation-safe-1300 and -1360. A copied-save
closed-capsule fixture and Original-rate rescue checks are pending.


### Decoded-resource correctness checkpoint

The mode-2 decoded-only recycler builds successfully and passes the new
12-frame, 1164x873 pixel comparison with exact CPU RAM, renderer RAM and save
equality. The pool is exercised by 3,039 hits; retained estimated GPU storage
peaks at 24,641,536 bytes. No TMEM handoff events occur, as required by this
variant's queue contract. Runtime: 8812fa614cca783905094f460e383fe4f8c22945213df6524f7fe23706ef946d.
Evidence: texture-decoded-reuse-parity/proof.json, steps 485 and 486a.
An unexecuted first parity wrapper used an incorrect template substitution;
its immutable request/source were withdrawn and retained before execution.

The MI context-mask experiment was previously built but its exact/native
continuations were withdrawn when hotfix work took priority. A fixed-clock
probe alone cannot qualify its accelerated path: the device bridge requires
native elapsed time. A new native-clock recording/control-replay/candidate-replay
comparison explicitly checks matching state/instructions and nonzero direct
read/write counters. Component bridge fallback/lifetime tests are also retained.
This path remains opt-in; no outcome is inferred before its actual proof.

This local checkpoint retains private defaults: blur composites/history and
both texture-reuse modes are disabled in the ordinary launcher. It is neither
a 1.3 release nor a declaration of zero missed updates. Native timing and moving
visual acceptance remain required; no owner profile or public release changed.


The first MI recorded-clock attempt stopped at the existing 16-million-sample
recording limit around VI 4000, before either replay. Its 512,000,016-byte file
and failure receipt are retained; no correctness or performance acceptance is
claimed. The focused replacement keeps the original deterministic prefix and
starts elapsed-time recording at VI 5500, covering the remaining busy interval
to VI 6600 within the unchanged recording cap. The production investigation,
its limits and counters are unchanged.


### MI replay rejection and diagnostic follow-up

The focused clock record and unchanged control replay finish with identical
CPU RAM, renderer RAM, save hashes and instruction samples. The direct MI-mask
candidate stops at the native-clock guard at 0x800756a0 just as elapsed timing
begins. It does not qualify. Dependent performance requests 499/500 were
withdrawn before execution; no default or public runtime changed.

The former error text used "non-monotonic-time" for both actual backward Count
and a mismatching recorded instruction boundary. Failure-only diagnostics now
retain expected/observed instruction, PC/opcode, idle deadline and Count to
distinguish those cases without changing acceptance, clocks or recording limits.
The 512,000,016-byte prior file contains 16 million 32-byte records plus its
header; the earlier note's 32-million sample count was incorrect and is corrected.
The production investigation and counters remain unchanged.

Evidence: context-mask-focused-clock, guarded steps 494, 499/500 withdrawal
receipts and the forthcoming failure-diagnostic replay. This remains open work.


The diagnostic build distinguishes the candidate failure as a recorded sample
boundary mismatch, rather than an actual backward host clock. The first detailed
rejection exited before the async trace writer drained its final record; the
error label was preserved but the expected/observed row was absent. The fatal
diagnostic path now drains that writer before exiting. Sampling and acceptance
remain unchanged, and no native performance run is authorized by this result.


### Native opening comparison with decoded-only reuse

Four normal-Play opening runs (reuse off/on at 120 FPS/VSync and 360 FPS/no
VSync) have no same-shot gaps above 42 ms in shots 322, 324, 323, 325 and 326.
All are audio-clean, with no unsupported accesses or dropped log rows. The
controls passing too prevents crediting resource reuse alone for that result.
Menu/loading gaps remain recorded separately, and earlier misses remain valid
evidence. The rescue comparison still fails zero-miss acceptance.

Evidence: texture-decoded-reuse-wall-review.json and
rescue-resource-comparison-wall-review.json, runtime 8812fa614cca783905094f460e383fe4f8c22945213df6524f7fe23706ef946d.


### Combined upload candidate qualification (2026-10-18)

The combined native helper, texture reuse, five-slot composite queue and
reusable upload-storage candidate completes two muted normal-Play opening
runs, each 9,000 VI, at 120/VSync and 360/no VSync. Active cinematic shots
322, 324, 323, 325 and 326 contain no three-VI updates or intervals above
42 ms. Their measured maxima are 35.661 ms at 120 and 35.514 ms at 360;
one-VI boundaries remain visible. Both runs have zero audio underruns,
overruns, unsupported accesses and dropped log records.

This does not exclude startup/title or scene-change loading gaps: level 0
retains 133.482/167.244 ms gaps, and a later scene transition takes about
two seconds. Those remain in the raw and reviewed data. Rendered spacing,
visual fidelity and owner live review are separate acceptance requirements.
The opening source-update result is not a global zero-stall claim.

Private evidence: reusable-upload-opening/fps120 and fps360;
reusable-upload-opening-wall-review.json in vela-composite (see retained
step 602 for the exact review artifact name). Runtime SHA-256:
70e559e31ab4971edfaa0e1e9319f3ed296c8a201cfb84f2495063e2835789a1.
See [RENDER-011](vela-rescue-cutscene-stutter-resolution.md) for the allocation
cause, staging reuse and independent image/state checks.
