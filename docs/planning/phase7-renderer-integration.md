# Phase 7 renderer integration

## Current result

The project now builds a static shell against the exact RT64 revision
`5473732a822a4423b5696e7cb18fecc425a59875`. CMake rejects an absent or
different checkout. RT64 is opt-in and remains outside the normal ROM-free
build.

The shell owns its 8 MiB RDRAM snapshot and converts canonical big-endian
captures to RT64's host word-swapped layout. RT64 never receives the live
simulation buffer. Its internal SP interrupt callback is isolated; only the
project-owned graphics bridge may commit externally visible completion, after
the bounded parser and independent output oracle accept the task.

`RendererCallbackRuntime` enforces registration and one-submit/one-present
lifecycle rules. `Rt64RendererCallbacks` binds that lifecycle to the existing
`GraphicsTaskBridge`, the bounded custom-family parser, the caller's independent
oracle, the caller's completion sink, and RT64 presentation.

## F3DDKR/JFG path

The project-owned RT64 binding installs a fail-closed F3D base map plus the
reviewed JFG handlers for DMA matrices, texture offset, the 10-byte vertex
variant, triangle batches with per-corner texture coordinates, counted RDP DMA
lists, DMA offsets, billboard state, and matrix selection. Unknown commands
terminate the submission. The implementation now follows JFG's command macros
for its direct encoded vertex count, encoded destination start, DMA source
alignment, complete-MVP matrix slot and multiply flag, append cursor and
triangle reset, indexed triangles, culling, and clip-space billboard anchoring.

The first unclassified ignored capture remains recorded as an integration
smoke in `evidence/phase7-rt64-task-smoke.json`.

The boot/title scene has a timing-correct capture at the exact
`osSpTaskStartGo` submission boundary. The capture waits for the later VI
double-buffer swap before recording its oracle. Its independently generated
semantic stream contains 732 parsed commands; the RT64 binding handled 66
custom/control commands, rejected none, and committed completion only after
the exact semantic match. RT64 read back a 640x480 frame for the 320x240 VI
source. Three separate runs were byte-identical and each passed the fixed pixel
thresholds, with worst-case SSIM 910,110 millionths, foreground IoU 838,980
millionths, and mean absolute error 43,152 millionths. The public-safe aggregate
is `evidence/phase7-boot-title.json`.

The representative gameplay task contains 3,261 parsed commands, including
124 matrix commands, 441 vertex batches, 338 triangle batches, and 2,764 drawn
triangles. All commands are supported. Three independent 640x480 GPU readbacks
were byte-identical and passed with worst-case SSIM 821,580 millionths,
foreground IoU 970,458 millionths, and mean absolute error 50,134 millionths.
The scene aggregate is `evidence/phase7-gameplay.json`.

## Reproduction with private inputs

Configure with `JFG_ENABLE_RT64=ON`, the exact `JFG_RT64_ROOT`, and
`JFG_BUILD_PHASE7_RT64_RUNNER=ON`. Then run `jfg-phase7-rt64-task` with the
ignored capture directory and the independent semantic-oracle file. The runner
prints aggregate counts only; it never prints command bodies or private paths.

## Simulation isolation and completion

Both captured scene states were hashed in renderer-disabled, bounded-semantic,
and fully presented RT64 modes. Each scene's three hashes matched exactly, and
the enabled paths verified that their source snapshots remained unchanged.
All Phase 7 gates are closed; `evidence/phase7-completion.json` contains the
public-safe aggregate.
