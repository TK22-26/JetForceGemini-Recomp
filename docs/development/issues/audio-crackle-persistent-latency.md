# AUDIO-004: Persistent audio latency (#35); earlier crackling report #29 closed

## Delivery and issue status — 2026-10-22 UTC

The owner-approved reply requests a v1.4.0 affected-session support ZIP, audio device/connection and FPS/VSync settings. #35 stays open; growing audio delay remains unlocalized and is not claimed fixed. The separate RTSS finding for #29 is retained.

[Release v1.4.0](https://github.com/TK22-26/JetForceGemini-Recomp/releases/tag/v1.4.0); [verified issue action](https://github.com/TK22-26/JetForceGemini-Recomp/issues/35#issuecomment-6332075095).
Earlier entries below preserve their original investigation and verification scope.

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
