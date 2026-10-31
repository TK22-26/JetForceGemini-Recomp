# Runtime reference

Start with [architecture](../architecture.md) for the build pipeline and subsystem boundaries.
These pages explain implementation choices; [issue records](../issues/README.md) own current
bugs, attempts and acceptance. Historical checks apply to their named source and inputs.

| Area | Reference |
|---|---|
| Native playback and host buffering | [Audio](native-audio-playback.md) |
| Collision work and compatibility | [Collision](native-collision.md) |
| Host replacement of resident math | [Resident math](native-resident-math.md) |
| Reading ROM assets | [ROM loading](native-rom-loading.md) |
| Controls and camera integration history | [Modern controls](modern-controls.md) |
| Original-ROM Normal/Expert comparison | [Issue 18 controls comparison](issue18-native-controls-handoff-2026-10-17.md) |
| Renderer cache identity | [Draw-call keys](renderer-draw-call-keys.md) |
| Optional performance instrumentation | [Function profiling](function-profiling.md) |

Normal Play's host clock and Original video presentation are distinct. See the
[open simulation-parity investigation](../issues/original-mode-simulation-parity.md)
before interpreting equal frame rates as original-console timing.
