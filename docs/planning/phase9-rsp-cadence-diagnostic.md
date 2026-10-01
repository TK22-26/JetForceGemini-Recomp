# Phase 9 RSP completion cadence diagnostic

## Symptom

Manual testing in the opening forest route reported visible stutter as more
ant actors entered the scene. The host frame and renderer timing trace did not
show a corresponding stall: during the marked interval there were no host
frames over 25 ms, no presentation intervals over 40 ms, and graphics submit
time remained below 4 ms. The process exited normally when the tester closed
the window.

An exact replay from the run's immutable pre-launch Flash and controller-pak
snapshots reproduced the route. Per-retrace actor sampling showed that the
visible discontinuity was simulation cadence rather than presentation
cadence. In the three-ant interval, actor position and animation and controller
polling advanced once every five 60 Hz VI retraces (12 Hz), while RT64
continued presenting on four of those five retraces (48 Hz).

## Root cause

The native runtime queues each graphics RSP task from `osSpTaskStartGo`, but
only submits it and emits its SP/DP completion messages in the outer VI-frame
service loop. The guest cannot issue the next serial graphics task until it
receives those completions, so every task consumes at least one complete VI
interval regardless of its measured host execution time.

The replay produced an exact task-count/cadence relationship across 880
consecutive simulation intervals:

| Graphics tasks per simulation update | VI retraces per update | Effective update rate |
| ---: | ---: | ---: |
| 1 | 2 | 30 Hz |
| 2 | 3 | 20 Hz |
| 4 | 5 | 12 Hz |

Every interval in the final group contained three small actor graphics tasks
and one main scene task. All 659 one-task intervals, 110 two-task intervals,
and 111 four-task intervals followed the relationship
`retrace interval = graphics task count + 1`, with no exceptions. This also
explains why the symptom scaled with visible actors even though total GPU work
was not unusually high.

Controller data was not randomly disconnected or discarded. Controller
polling belongs to the same delayed game loop, however, so sufficiently brief
physical inputs can be missed when the artificial simulation cadence falls to
12 Hz.

## Implementation direction

Graphics task execution and SP/DP completion must no longer be deferred to the
next VI service edge. A task should be prepared, submitted, and completed at a
scheduler-safe point that allows the guest to continue issuing serial RSP
work within the current VI interval. VI framebuffer selection and host
presentation must remain on the 60 Hz service boundary.

The change must preserve:

- SP completion before DP completion;
- fail-closed behavior before either completion is exposed for a rejected
  task;
- task RDRAM snapshot lifetime and retained framebuffer selection;
- deterministic full-render replay and final RDRAM capture;
- audio-task completion behavior;
- window, audio, and input service pacing at VI boundaries.

Acceptance for the fix is an exact replay of the same route in which the
number of graphics tasks no longer adds VI retraces to the simulation update
interval, followed by a paced manual run through the multi-actor scene.

## 2026-08-27 implementation validation

The implementation keeps displayed-framebuffer tasks on the existing VI
completion edge and completes the observed 0x1b-command auxiliary actor tasks
synchronously only after RT64 proves they target a nonzero off-screen color
image. A displayed or missing target fails closed before SP/DP completion.

In the preserved slot-2 manual route, the previously reported multi-ant
stutter was no longer visible. The run then progressed to the next independent
runtime blocker: an invalid `bzero` request for guest destination `0x09b03cd0`
and length `0x1080`. The runtime emitted its controlled first-trap record; the
host process did not produce a Windows crash dump.

## Synthetic-overlay `bzero` follow-up

The preserved full-render replay reproduced the blocker at retrace 42,205 and
identified the caller as `FindBestPathInRegion` in generated section 153
(game overlay 155). The destination is that overlay's BSS at local offset
`0x3cd0`; it is not a corrupt heap or runlink pointer.

Generated overlay-local loads and stores deliberately use normalized synthetic
VRAM addresses. On Windows, `GuestBacking` commits each synthetic overlay at
the corresponding offset used by the generated `MEM_*` helpers. The HLE
`bzero` implementation recognized only cached and uncached RDRAM aliases, so
it rejected a valid write into an active synthetic overlay even though normal
generated memory operations already supported the same window.

The fix resolves `bzero` destinations against either ordinary RDRAM or the
exact extent of a currently published synthetic overlay. Inactive overlays,
gaps, and requests crossing an overlay boundary remain fail-closed. A
full-render replay of the same immutable save and 42,205-retrace controller
stream then reached the requested retrace normally with no unsupported access;
all 9,499 `bzero` calls completed.
