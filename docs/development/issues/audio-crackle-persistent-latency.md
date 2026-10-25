# AUDIO-004: Persistent audio latency (#35); earlier crackling report #29 closed

## Delivery and issue status — 2026-10-22 UTC

On October 22, the #35 reporter supplied six logs from v1.4.0 and confirmed that latency still increases in sudden steps, sometimes repeatedly. Pause/unpause restores synchronization. Device and display settings are now supplied, but the cause remains unlocalized and no latency fix is claimed. #35 stays open. The separate RTSS finding for #29 is retained.

[Release v1.4.0](https://github.com/TK22-26/JetForceGemini-Recomp/releases/tag/v1.4.0); [verified issue action](https://github.com/TK22-26/JetForceGemini-Recomp/issues/35#issuecomment-6332075095).
October 24: `fix/audio-latency-recovery` contains an unreleased host-queue
recovery candidate. Component parity, fault-recovery and sanitizer checks pass;
native build passes; owner listening is still pending. The actual #35 trigger is
still unknown. See the candidate results at the end of this report.

Earlier entries below preserve their original investigation and verification scope.

### Affected v1.4.0 session reviewed October 23 UTC

The [October 22 reporter follow-up](https://github.com/TK22-26/JetForceGemini-Recomp/issues/35#issuecomment-6334947549)
explicitly distinguishes sudden latency increases from continuous gradual
drift. Another event can add further delay. They used pause/unpause to recover
shortly before quitting the attached session.

Reported settings: 240 Hz VRR display, usually 120 FPS; also reproduced at
60 FPS, 240 FPS and unlocked. VSync is forced through the NVIDIA driver. Audio
device is an Audigy 2. These details identify the affected configuration, not
a diagnosed driver or hardware cause. The earlier report identifies Windows 10
and an RTX 5060 Ti. Do not conflate this with #29's RTSS crackling resolution.

The six supplied files are breadcrumbs.log, build.log, controller.log,
launcher.log, mouse.log and native.log. Build and launcher identities match
v1.4.0 (launcher source 5ec705f7, runtime source 521f6662); the session closes
with exit code zero. The native log lists startup/audio-path markers but no
audio queue duration, device-consumption timing or underrun/overrun timeline.
Breadcrumbs and mouse records cannot establish the audio backlog or its cause.
The supplied evidence is therefore useful but insufficient for a root-cause
claim. Do not request the same basic settings again.

The next investigation should correlate a sudden delay event and pause recovery
with queued samples, audio-device consumption and host/game clock timing. The
existing queue/reanchor observations below and upstream catalog entry
JFG-UP-024 remain hypotheses to test. No code, replay or new diagnostic capture
was run in this review; the existing production guard allowance is exhausted.

Private evidence: `post-v14-issue-review-20261023/issue-35.json`, the six original
attachments under `issue35-attachments`, and URL/SHA-256 receipts in
`attachment-receipt.json`. A response acknowledging the logs and the remaining
failure is drafted for owner review only; no response or closure was posted.

### Owner follow-up: hold reply; prioritize the backlog hypothesis

The owner asked for concrete leads and explicitly withheld a #35 response.
Read-only source reinspection confirms a useful first hypothesis: audio output
temporarily falls behind while samples continue to be produced, leaving an
excess queue that normal playback does not remove. A later event could add
another step. This is consistent with the report, not a reproduction or a
confirmed trigger.

Evidence supporting this priority:

- `settle_startup_queue` drains excess queued sound toward the
  configured 100 ms prebuffer. Frontend pause/resume clears the host anchor,
  allowing this drain on the next VI. There is therefore an explicit code path
  that could explain why pause repairs accumulated software-queue latency.
- The audio device's `update_metrics` counts queues over two seconds but does not
  correct them. The normal host-paced gameplay path does not use the separate
  200 ms queue throttle. A persistent offset can therefore exist without
  ordinary playback bringing it back to the starting latency.
- The newer report describes steps rather than continuous drift; prioritize
  temporary output/clock disruptions over a steady sample-rate mismatch.

Distinguish a software backlog from downstream device buffering with queue age,
production/consumption rates and clock/pause markers across the event. An
isolated delayed-consumption test could establish whether our current recovery
policy retains excess latency, but would not by itself identify the reporter's
trigger. If the software queue remains near its baseline while audible latency
increases, investigate downstream device timing or source-event timing instead.
Do not apply periodic audio flushing or blame the Audigy without that evidence.
No execution or new fix was attempted; the existing guarded allowance remains
exhausted and the requested continuation has not yet been granted.

- Status: #29 closed by its reporter after attributing crackling to RTSS. Remaining latency reported separately as #35; owner cannot reproduce; awaiting affected-session evidence, no qualified latency fix.
- Severity: high; sound effects reportedly remain 1-2 seconds behind gameplay.
- Report: [GitHub #29](https://github.com/TK22-26/JetForceGemini-Recomp/issues/29), 2026-10-19.
- Reporter: Windows 10, RTX 5060 Ti, Xbox One controller.

## Symptoms and reproduction

Play for several minutes. Crackling lasts several seconds, then sound effects
remain delayed. Reported every attempt, during cutscenes and gameplay. Changing
something through the launcher or using its pause option reportedly restores
synchronization. The exact setting change and device configuration are unknown.
No reporter support ZIP or timing capture is attached as of this review.

## Source review and hypotheses

[src/boot/native_boot.cpp](../../../src/boot/native_boot.cpp) opens SDL queued
audio at the guest frequency. Normal interactive play disables the additional
200 ms audio-queue throttle because the game already follows its VI clock.
The overrun threshold is two seconds; crossing it increments a counter but
does not recover latency. Startup/host-clock reanchoring can drain the queue
to 100 ms. These are source facts, not proof that this reporter has a long SDL
queue. Driver buffering, resampling and source/event timing remain alternatives.

A previous clean owner route and zero underruns do not disprove latency.
Queue depth/age and audible delay are separate acceptance criteria.
The pinned upstream audio reference JFG-UP-024 was consulted; no dependency
or clock changes are justified by this report alone.

## Next evidence and validation

Owner expects an affected-session support ZIP, or at minimum detailed settings:
FPS mode/cap, VSync, audio preferences, output device/connection, approximate
onset time and location. Public requests wait for owner approval after review.

When a failing capture is available, correlate queued minus consumed bytes,
sample frequency, underruns/overruns, host pause/resume/reanchor and game time.
An ordinary support ZIP identifies the setup but may not contain the sample
timeline; do not claim it provides detailed audio profiling.

No audio flushing, timer changes, device changes or gameplay tests were performed
for this review. A future remedy must bound audible latency without discarding
normal game events, changing game speed or creating new crackles.

## Related evidence and lesson

[Earlier source crackle](intermittent-music-crackle.md),
[playback starvation](walking-audio-interruptions.md), and
[v1.3 qualification](../releases-1.3.0-qualification.md) describe distinct prior
faults and bounded checks. Private source-review logs: v131-rnd-20261019.
Do not label a new delay report as the old underrun fault without measurement.

## Existing long-run queue comparison and pause path (2026-10-19)

Reanalyzed the owner's historical 1.3 preview full-run capture
20261019-042137-86ff999db64d4a8fb6e578e62ead461e, rather than treating zero
underrun/overrun counters as a latency measurement. Its 38,666 audio-queue
observations span 1,291 seconds. After the first 10 seconds, queued audio has
median 117.0 ms, p99 131.2 ms and maximum 137.4 ms. Minute medians remain
114-121 ms; no one-second backlog appears. Startup reached 401.2 ms before
playback started and the explicit startup drain reduced it to 98.9 ms.
The shorter known-good wet-room capture stayed below 155.6 ms after startup.
These are software-queue observations, not speaker latency or a reproduction
of the reporter's machine. Capture/runtime identity remains in the prior
private launch receipt; this is not a new run of the final release.

Source confirms the reported pause recovery has a plausible local mechanism:
service_live_window resumes SDL audio and clears original_os_host_anchor_ready;
the next VI calls settle_startup_queue before reanchoring playback. That
method waits for excess queued audio to drain to approximately 100 ms.
This supports the backlog hypothesis, but neither establishes its trigger nor
excludes downstream device/driver latency.

The official v1.3.0 package contains SDL 2.26.3 (verified DLL version).
No specific SDL defect has been tied to #29. Source lacks selected audio
backend/device identity and an ongoing queue-age history in ordinary support
breadcrumbs. Existing optional gameplay tracing already records current
queue bytes, cumulative queued/consumed bytes, sample rate and playback state.
Use those observations in an affected capture; ask separately for the actual
output device/connection and Windows audio format if the support ZIP lacks them.

Private analysis: D:/JFG-private/v131-rnd-20261019/historical-audio-queue-analysis.json,
with bounded analyzer step 021. Source review steps 015-019 cover the queue,
pause and clock paths. No audio throttling, sample dropping, reset policy or
dependency update has been applied.


## Reusable offline analysis

Added [analyze_runtime_effects.py](../../../scripts/analyze_runtime_effects.py)
to summarize actual changed-pixel calls and software audio queue age from an
existing closed gameplay.tsv. Example:

    python scripts/analyze_runtime_effects.py <closed-session>/gameplay.tsv

It excludes the first ten seconds by default; use --from-seconds 0 for startup.
It keeps paused/prebuffer audio separate from active playback, validates sample
rates and cumulative/current byte consistency, and reports missing probes
without treating them as a clean pass. It cannot prove visible output, speaker
latency or complete trace delivery.

Five focused unit tests pass, including zero-write reticle calls, a persistent
1.2-second backlog without any underrun event, changing cumulative byte totals,
startup/paused buffers, and malformed evidence. Applying it to the historical
full-run and wet-room captures reproduces the source-review measurements.
No game executable or active user profile was modified.


### Limits of the v1.3 support ZIP

The current SupportSession.SafeLine export grammar accepts original controller
fields, GPU driver IDs and basic build/progress records. It does not accept
video FPS/VSync/blur/fog fields, Modern Controls fields, audio endpoint/backend
identity or the runtime's audio-mode support_event strings. A v1.3 ZIP is useful
for build/GPU identification but cannot replace a separate settings report or
the detailed gameplay/audio trace. Do not promise that it contains those
missing fields. Improving this diagnostic coverage is a follow-up limitation;
no support exporter behavior was changed during this R&D pass.

Owner cannot reproduce the audio delay and agrees more reporter information is needed. Keep this open; no speculative audio correction is approved as a resolution.


## Reporter split and owner status (2026-10-21 UTC audit)

On 2026-10-20 the reporter [closed #29](https://github.com/TK22-26/JetForceGemini-Recomp/issues/29#issuecomment-6299179314),
explaining that RTSS caused the crackling. The reporter then opened
[#35](https://github.com/TK22-26/JetForceGemini-Recomp/issues/35) for growing audio
latency on v1.3.0, Windows 10, RTX 5060 Ti and an Xbox One controller. After several
minutes, effects reportedly lag by one or two seconds and worsen over time;
launcher setting changes or pause temporarily restore synchronization. No support
ZIP or further comments accompany #35 at this audit.

The owner again reports inability to reproduce. Track the latency work under #35;
retain this record's prior source and queue observations as evidence, not a
reproduced cause. No new audio remedy or gameplay experiment was attempted.
Request an affected-session report and exact settings/device/connection/onset
information when following up. The RTSS explanation applies to the reporter's
crackling; it does not establish the cause of #35 latency or every audio fault.


## Guarded audio-backlog fault injection, October 23 UTC

The owner explicitly approved up to one hour for this targeted experiment.
The existing `high-refresh-rendering-20261011` investigation was continued with
one bounded attempt and unchanged root/counters; the production guard remained
enabled. Execution used its supervised child process tree. No game, ROM, save,
release executable or GitHub issue was modified. Public responses remain held.

**Result: a persistent software-queue backlog and pause recovery are reproduced
under controlled faults in the released audio-device component. The trigger
on the reporter's machine and a production remedy are still unverified.**

### Method and identity

The fixture extracts `HostAudioDevice` verbatim from `native_boot.cpp`, then
checks it against the v1.4.0 tag. It uses the production playback-buffer helper,
master-volume implementation and low-queue demand helper. The SDL 2.26.3 DLL
has the same SHA-256 as the current released package. Real-backend tests use
WASAPI on the owner's PC with silent synthetic stereo PCM at 22,018 Hz.

The controlled producer emits nominal two-retrace audio chunks, using absolute
60 Hz deadlines; this is a component harness, not the guest audio-manager/game
execution. Trace/file-watcher dependencies are inert fixture substitutes.
There is also a deterministic SDL-consumption substitute to check queue math
without OS scheduling variation. Faults are introduced only by the fixture;
the extracted production class is unchanged.

### Measured results

Numbers below are software queue durations, not measured speaker latency.
Real-backend final medians use the last two seconds of each 15-second run.

| Controlled case | Result |
|---|---|
| Normal playback | 121 ms final median; no underrun or overrun |
| Consumer stopped for one second, then resumed | 1133 ms final median; excess persists after consumption returns; zero overrun count |
| Two one-second consumer stops | 2131 ms median after the second stop |
| Pause/resume and the existing anchor drain after those stops | 109 ms final median |
| Six separate 150 ms consumer stops | 989 ms final median; zero underruns and zero overruns |
| Producer stopped for one second while output kept consuming | One underrun, then recovery to 114 ms final median |
| One second of extra PCM submitted as a burst; consumer never stopped | 1119 ms final median; zero overrun count |

The deterministic counterpart starts near 108 ms and retains exactly one or
two additional seconds after the respective consumer faults. Pause recovery
returns to the same baseline. Its normal pause control does not accumulate
delay, and a one-percent consumption-rate mismatch produces gradual growth
instead of discrete steps. Eight deterministic scenarios and six real-backend
scenarios completed with their targeted comparisons passing.

### Interpretation and remaining work

Once excess audio exists, ordinary playback produces and consumes at roughly
the same rate, retaining the offset. The low-queue demand helper can accelerate
production below its target but does not remove excess above it. Counting only
queues over two seconds misses clearly excessive one-second backlogs. Existing
pause/resume recovery drains queued sound toward 100 ms, reproducing the
reporter's stated recovery pattern without a full game restart.

This establishes a recovery gap under a controlled fault, not that the Audigy,
its driver, NVIDIA VSync or any particular game scene caused #35. The burst
control deliberately produces the same symptom with uninterrupted consumption:
the next affected-session capture must distinguish a production burst from an
output-consumption stall, rather than assuming hardware caused it. A baseline
pass on another PC and zero overrun/underrun counts do not exclude this fault.

Next evidence should include selected backend/device and format, current queue
milliseconds, submitted/consumed deltas against monotonic time, host/VI clock
events and pause/reanchor markers around a queue increase. Ordinary support logs
currently omit those observations. If the software queue stays normal during
audible delay, downstream buffering or source-event timing remains a separate
path. The synthetic tests do not establish the full game's response to the
fault or end-to-end audible latency.

No production patch is applied. A fix must bound excess latency while preserving
guest/game timing and avoiding audible discontinuities. Re-enabling the old
second pacing loop would need care because it was removed to avoid frame
hitches; periodically flushing audio without identifying the event is not a
qualified remedy. Keep #35 open and do not claim a released resolution.

Private evidence on D: `audio-backlog-test-20261023/authorization.json`,
`process-guard.json`, hashed step requests/results and the fixture directory.
The latter retains raw per-frame CSVs, source/DLL identity receipts,
`fake-analysis.json`, `real-results.json`, `production-burst-result.json`,
`verified-summary.json` and build logs. No copyrighted game data is involved.

## Host queue recovery candidate, October 24 UTC

Owner authorized five hours and a dedicated branch, `fix/audio-latency-recovery`.
The production guard continues the existing investigation/root/counters. This
is an unverified candidate, not a released fix or confirmation of #35's trigger.

The candidate retains the original synth rate, PCM conversion/volume, AI DMA,
VI/game pacing and ordinary SDL submissions. Native interactive playback alone
can recover after the queue stays over 250 ms for a second, with consumption
progress, following a one-second warmup. Startup/resume anchors, pause, loading,
cutscene completion, reference timing, fast replay and null sinks are excluded.
A service gap re-arms the detector; a recovery has a five-second cooldown.

Recovery pauses the device briefly, retains the newest 100 ms from bounded
post-volume PCM history, and blends its first 5 ms from the old pending head.
For faults longer than the four-second history it fades in instead. Unavoidably,
stale sound is discarded during this exceptional resynchronization; this cannot
guarantee an inaudible transition. Submitted, consumed and discarded bytes stay
separate; demand uses the actual remaining queue. SDL replacement failure follows
the existing queue-failure contract rather than silently continuing without sound.
An ordinary support-log recovery record does not require diagnostic capture.

Validation in progress: pure policy/PCM tests, unchanged-path component parity,
controlled fault recovery on simulated and real WASAPI consumption, native build,
then owner listening. Full-game and reporter-machine verification remain pending.
Private evidence: `D:/JFG-private/audio-latency-fix-20261024`. The initial branch
preflight rejected a whitespace-stripped porcelain status; it made no edits.
The corrected check preserved all pre-existing documentation and created the
branch. No main/develop merge, release or GitHub response is authorized here.

### Component validation results

- MSVC `/W4 /WX`: the policy/PCM suite passes at 8,000, 22,018, 32,000,
  44,100, 48,000 and 96,000 Hz. An hour of simulated normal buffering at each
  rate produces no recovery. It also covers stalled consumption, transient
  spikes, warmup/cooldown, exclusions, clock discontinuities, ring wrapping,
  stereo signed samples, unchanged tail samples and long-fault fade-in.
- A verbatim old/new `HostAudioDevice` fixture passes **48 baseline/candidate
  comparisons** (three rates, four service frequencies and normal/pause/
  producer-starvation/excluded contexts). Submitted PCM hashes and SDL queue/
  playback-control operations match exactly; no recoveries/discards occur.
  This proves the tested paths, not every hardware backend or full gameplay.
- The deterministic fault cases retain 1,099/2,099/999/1,099/6,099 ms in the old
  component after one stall, two stalls, six short stalls, an extra-production
  burst and a six-second stall respectively. All settle to 117 ms with the
  candidate. Recovery leaves emulated DMA state and original submission counts
  unchanged, separates discarded bytes from consumption, and tests failed SDL
  replacement with the device paused and the existing error path returned.
- With the released SDL DLL and real **WASAPI**, normal baseline is 121 ms;
  the released component retains 1,133 ms after a one-second consumption stop.
  Candidate final medians are 108 ms after one stop, 120 ms after two,
  111 ms after repeated short stops and 116 ms after extra production. These
  successful fault runs have no underruns. Normal/pause/producer-starvation
  controls trigger no latency recovery; the deliberate one-second producer
  starvation produces one expected underrun and returns to 109 ms.
- The first repeated-stall real run did record two underruns. Raw timestamps
  put both after roughly 268 ms producer-observation gaps exceeding the queued
  cushion, including one before any injected fault/recovery. That failed check
  is retained, not relabeled a clean pass. A subsequent run of the same case
  records no underruns. Its cause outside the component was not established.
- GCC with AddressSanitizer/UndefinedBehaviorSanitizer and strict conversion
  warnings passes. The initial Clang attempt could not run because clang++ is
  not installed in Ubuntu-24.04; GCC supplied the sanitizer check instead.

Private evidence: `component/source-receipt.json`, `005-component-ab.request.log`,
`component/real-results.json`, `component/real-twice-underrun-analysis.json`,
`component/real-continuation.json`, and `010-sanitize-gcc.request.log` beneath
the October 24 evidence root. Silent PCM tests measure software queue duration,
not speaker latency or subjective continuity. No game saves were used.

The remaining release gate is unchanged: listen to normal gameplay, cutscene
skips, focus/pause transitions and a long session in an isolated candidate,
then obtain an affected-machine retest. A normal software queue with delayed
audible output would require a different investigation. Keep #35 open.

Transferable lesson: count queued latency and discarded audio separately from
underruns and bytes played. A healthy producer/consumer rate after a temporary
disruption does not restore their earlier phase. Recovery must not introduce
a second clock controlling gameplay or alter sound for healthy queues.


Final source review caught a telemetry-only error: `support_event` deliberately
rejects spaces, whereas the first fixture substituted a stdout logger. Recovery
metrics now use its accepted slash-separated category format. The component
suite was rerun against the actual production logger, and all eight expected
success/failure records were verified on disk. PCM/SDL parity and fault results
remain unchanged. Original fixture evidence is preserved; the corrected receipt
is `component-v2/support-validation.json`. This illustrates why a diagnostic stub
does not establish that ordinary packaged support logging works.

The full native build started before this string-only correction. Its source
consistency check will intentionally reject that changed input; final native
qualification must rebuild/check the current source and identity afterward.


The final normal-path refinement reuses the measurement already taken by
`service()`/`queue()` rather than polling SDL again. The 48 comparison pairs now
also verify every SDL queue-size read, alongside PCM and playback-control calls;
all match the baseline. Repeated real WASAPI normal/one-stall/two-stall checks
use the actual production support logger. `component-v3` retains these exact
source, operation-trace and support-log results. This avoids shifting the
healthy path's cached demand observation just to evaluate recovery.

### Native build and review package

Fresh CPU/RSP generation from the supported local ROM completed and verified
the matching ROM checksum. The current Windows native Release build passes,
as do all eight registered audio suites: latency recovery, playback buffer,
master volume, native event/demand timing, native audio source, DMA broker,
audio task bridge and cutscene audio. The earlier in-flight build was rejected
by its source-consistency check after the support-message correction; the final
pass rebuilt/checked the exact current inputs and their hashes. Project
validation, repository hygiene and whitespace checks also passed.

The isolated `D:/JFG-previews/audio-latency-recovery-20261024` package uses the
released launcher and a copied save/profile, keeps the owner's 120 FPS and
audio/control settings, and has diagnostics/FPS overlay disabled. Its package
hashes and source/runtime identity are checked. The released folder and save
remain unchanged. Private `native-qualification.json` and `preview-ready.json`
record the final input hashes and package identity.

Status: implemented on `fix/audio-latency-recovery`, built and component-tested;
owner listening and affected-reporter verification pending. Not merged into
main/develop, published, posted to GitHub or claimed as a released #35 fix.

### Owner regression pass, 2026-10-24

The owner ran the SS Anubis audio pass with diagnostics disabled on the
`1d631c0` candidate and reported **no audio regression**. The owner did not
previously experience #35's persistent delay, so this is listening acceptance
for the exercised route, not verification on the affected machine. The
reporter's retest remains pending; no release, merge or GitHub reply follows
from this pass. A subsequent capture covers separate flight-music and shot
effect reports.

## Background replay audio report, 2026-10-24

The owner heard a brief audio tear after closing the visual review capture,
then clarified only menu music was audible and no game window was visible.
An agent-started hidden camera replay was running at that time. Its requested
NULL_AUDIO flag did not silence this native-clock configuration, so the test
was stopped immediately. Treat this as an unqualified background-test symptom,
not regression acceptance or failure of the owner's earlier gameplay pass.
The completed visible review reports zero host underruns/overruns; that does
not rule out an audible defect. Any further hidden audio-capable fixture must
use an explicit muted copied audio profile. Private stop receipt:
flight-shot-analysis-20261024/camera-replay-stopped.json.


## Retest delivery note

On 2026-10-24 the owner requests that #35 be carried as a changelog retest
request for the affected user. The Unreleased changelog now states that scope.
The ordinary SS Anubis listening pass remains accepted; this does not establish
resolution on the affected machine, close #35 or authorize a GitHub reply.
