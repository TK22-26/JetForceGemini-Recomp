# PERF-005: SS Anubis ledge-testing stutter in Lighting Preview

- Status: measured, unresolved; no cause or fix qualified.
- Severity: visible short gameplay interruption.
- Reported: owner, 2026-10-19 evening after accepting #30.
- Build: private Tawfret Lighting Preview, runtime cfac17af630e519c62866ed52de60c8489edd232ddc99fc9f5df260e871ba54d.
- Profile: Custom 60 FPS, VSync on, Reduced blur, fog 100%; runtime/profile on C: SSD.

## Recorded evidence

The preview saved successful-present timings and scene counts, not video or
input/CPU/GPU phase timings. Latest file: frames-20261020-013503-40644-0.csv,
1.69?62.42 seconds after runtime start. Copies, support logs, settings and
analysis are retained in D:/JFG-private/v131-rnd-20261019/lighting-lag.

There are 3,452 presented-frame rows. At 30?35 seconds, the log contains 221
rendered outputs and 95 distinct scene submissions: about 44.2/19.0 FPS across
that interval. At 35?40 seconds it recovers to 284/135; 40?55 seconds is near
60/30. Present gaps in the first burst reach 425 ms; scene gaps reach 338 ms.
These are actual delivery gaps, not a mislabeled FPS counter.

Earlier isolated stalls at startup/roughly 18, 21, 24 and 27 seconds also occur
in the separately accepted ledge run, suggesting common startup/menu/loading
events; without input/transition markers they are not assigned to gameplay.
Across the entire lighting session, including those events, 43 present
intervals exceed 25 ms and 23 exceed 40 ms. The logging writer reports no
queue drops or failure. The process exits normally.

The previous longer lighting run has substantially steadier cadence outside
isolated gaps. The ledge run has 144-ish output/30 scenes once playing; it is
not a controlled same-settings comparison with the 60 FPS lighting run.
Both contain the same fog candidate, so timing alone does not identify fog
as the cause.

## Hypotheses and next discrimination

Possible room/resource/shader first-use work or a scene-specific execution
bottleneck remains unlocalized. No CPU-vs-GPU attribution can be recovered
from the frame CSV. The support breadcrumbs confirm fewer completed updates
during the burst but contain no per-stage costs. Ask whether it occurred on
room entry or throughout movement. A short staged-timing capture on the same
profile is the next evidence needed if reproducible; do not treat a build or
the successful ledge fix as a performance correction.

## Limits and lesson

No gameplay was launched by the agent for this review. No guarantee of audio
continuity is inferred from a normally closed process; this session does not
record audio counters. Keep startup/loading pauses, game-update cadence,
output cadence and subjective motion smoothness distinct.

## Owner location clarification

The owner identifies SS Anubis while testing ledge grabbing. Tawfret was the
preview name, not the location of the slowdown. The new isolated desktop
Anubis Ledge Timing Capture preserves that profile at 60 FPS/VSync and adds
standard phase/input/renderer logging, with the accepted controller ledge fix.
It starts muted; no game was launched by the agent. Capture/reproduction pending.


## Follow-up capture: not reproduced

The owner repeated the SS Anubis ledge movement and could not reproduce the lag.
Capture 20261020-014541-483e7dd0ea0f4e20b1e6773fb031e984 confirms level 35
after loading and records 277 retained ledge-view updates. Every complete
five-second bucket from 30 seconds onward has 149-150 native updates.
Runtime progress reports zero audio underruns/overruns and no host pause/resume.
Longer startup/menu/loading updates are recorded separately. Camera body
clearance peaks at 3.489 ms. The normal approximately 33 ms full update
measurement includes pacing waits; it is not all CPU computation.

This does not reproduce the earlier multi-second gameplay slowdown. The runtime
has the controller ledge correction, but this is not a controlled same-input A/B.
Keep the intermittent report open; do not credit the camera fix with resolving it.
The owner also found the separate controller landing reset (CAMERA-008), then
confirmed its fix in a later preview.

Post-30-second summary (microseconds): {"after_30sec_output_rows": 6038, "max_present_us": 18248, "present_over_25ms": 0, "present_over_40ms": 0, "max_scene_us": 36172, "scene_over_42ms": 0, "multi_scene_steps": 0}.
