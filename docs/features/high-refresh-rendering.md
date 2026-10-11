# Experimental high-refresh rendering

The research branch now contains a working, opt-in presentation interpolation
prototype. Automated gameplay replays demonstrate approximately 60 and 240
presentations per second in a moving-camera scene while preserving the original
guest execution and memory. This is an unreleased candidate, with owner playtesting
and broader visual qualification still pending.

## Try it

Build the live RT64 runtime normally, then set `JFG_EXPERIMENTAL_RENDER_FPS` to
`60`, `120`, `240`, `360` or another integer from 60 through 1000. Unset
or `0` selects the original mode. Invalid values are rejected.

The [preview helper](../../scripts/play_high_refresh.ps1) copies saves and selected
settings into a new directory for each run:

```powershell
.\scripts\play_high_refresh.ps1 -Runtime C:\JFG-build\Release\jfg-native-boot.exe -Rom C:\Games\jfg.z64 -Save C:\Games\jfg.flash -Fps 60
```

Use `-ProfileDirectory` for existing controller, modern-control, PC-input and
audio configuration files. `-ControllerPak` optionally supplies a pak copy.
The helper prints the new save directory. A new invocation begins from the
supplied source save; progress remains in the printed preview directory.

The locally qualified build is `C:\JFG-builds\high-refresh-20261011\Release\jfg-native-boot.exe`.
Sibling `Play-60-FPS.cmd`, `Play-360-FPS.cmd` and `Play-0-FPS.cmd` launch it
with isolated copies of the retained profile/save. These machine-local helpers
and game inputs are not part of the source repository.

RT64 currently limits a manual target to detected display refresh. A 360 request
on the tested 240 Hz display therefore runs with a 240 target. Neither 360 nor
above-360 delivered FPS has been qualified.

## What was implemented

- Each graphics task carries its guest VI timestamp into the decoder.
- Unique, unchanged mesh geometry identifies candidate transforms between scenes.
  Previous matrices are copied into immutable host metadata owned by the queued
  workload. No history pointers refer to recycled guest or renderer buffers.
- The renderer linearly interpolates the combined matrices for presentation.
  Authored transforms and RT64's native-resolution feedback path are preserved.
- Offscreen shadow submissions preserve scene history, presentation counters and
  source cadence. Irregular cadence, ambiguous geometry, camera-plane crossings
  and large projected motion fall back to current transforms.
- The experimental path enables manual refresh and SkipBuffering. Default
  Original/Console behavior remains available.

The [DK64 and other port comparison](../upstream/high-refresh-reference-review-2026-10-11.md)
informed the design. No upstream game patches were imported. Dependency changes
are generated into the build tree from exact hash-checked RT64 sources.

## Measured candidate

Implementation source: local commit `8d8f09701cc50d3a5b03eafd90ff5a41d3aeb3e9`.

Hardware: RTX 5090, Ryzen 7 5800X, RT64-detected 240 Hz display; captured output
640 by 480. Three identical-input replays ended at VI 4100 in 70.16-70.33 seconds.
The original, 60-target and 360-target runs have byte-identical 4 MiB guest RAM,
8 MiB renderer snapshots, recorded input and saves, plus the same probe state hash.
Instruction, controller-sample, graphics-task and decoded-audio-task counts also
agree. This does not establish audio-device underrun behavior or full resumable
snapshot equivalence.

| Requested FPS | Effective target | Camera-window presents/s | Median / p95 / p99 interval (ms) |
|---:|---:|---:|---|
| 60 | 60 | 59.98 | 16.672 / 16.738 / 16.755 |
| 360 | 240 | 239.81 | 4.170 / 4.303 / 4.411 |

Rates and interval percentiles cover the approximately 1.6-second moving-camera
window at VI 4000-4098, excluding screenshot readback. That window rendered two
or eight presentation states per authored 30 Hz scene. The full replays include
loading and static/menu sections; these numbers are not a whole-game benchmark.

The 60 and 360 requested modes respectively logged 1,344 and 9,357 intermediate
frames with changing matched transforms. Separate bounded screenshot replays
capture actual swapchain images from the same presentation group, verify distinct
pixels and retain matching guest RAM. The sampled HUD, character and reflection
are visible; this is not acceptance of all overlays or scenes.

Release build and five focused tests pass: interpolation history, RT64 matrix
adapter, shell/memory, F3DDKR texture handling and depth bounds. The probe retains
`acceptance=false` and `runtime_snapshot_complete=false`, accurately reflecting
its limited coverage. See [RENDER-001](../development/issues/high-refresh-rendering.md)
for attempts, hashes and private evidence locations.

## Remaining visual and performance work

Exact geometry matching is a conservative prototype, not semantic actor identity.
Repeated models, changing topology and some animation/effects use endpoints.
Actor reuse, small camera cuts, fast rotations, changing viewports, pause/resume,
cutscenes, menus and multiplayer still need explicit coverage. Simple coefficient
interpolation is not rotation decomposition and can distort some motion.

SkipBuffering may display a scene before a CPU-composited overlay has been applied.
The sampled HUD remains visible, but general CPU-overlay ownership is unqualified.
Mixed scene/offscreen workloads, resize and loading transitions also need testing.

Longer frame-time runs, GPU timings, memory growth, 360+ Hz output hardware and
owner playtesting remain open. Interpolation does not repair the separate
[combat simulation-cadence issue](../development/issues/goldwood-combat-slowdown.md).

## Diagnostics

`JFG_RT64_INTERPOLATION_TRACE` writes TSV rows with event, steady-clock
microseconds, guest VI tick (render) or present ID (present), source rate,
effective target, frame index/count, interpolation weight and matched/moving
transform counts. Extra presentation calls alone are not evidence of extra motion.

For image qualification, create an empty directory and set
`JFG_RT64_FRAME_SEQUENCE` to it plus `JFG_RT64_CAPTURE_FROM` to a present ID
from the trace. This captures at most four present IDs and sixteen frames per ID
as PPM files. GPU readback disturbs pacing; do not benchmark a capture run.

Keep the production guard enabled and retain the existing
`high-refresh-rendering-20261011` ledger lineage for autonomous continuation.
