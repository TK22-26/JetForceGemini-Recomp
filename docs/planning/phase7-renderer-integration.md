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

## Opening asteroid texture corruption (2026-10-08)

Reported and investigated by **Luke Deardoff (@lukedeardoff)** in
[PR #9](https://github.com/TK22-26/JetForceGemini-Recomp/pull/9). His trace of the
incorrect texture addresses was reproduced and guided the diagnosis below.
The final command-boundary reset was implemented independently after checking
the original microcode; Luke's proposed 40-entry cutoff was not incorporated.

The new-game opening cinematic could apply a previous model's texture-offset
table to a later asteroid. The F3DDKR `BF` DMA-base command changes model state;
the original RSP handler also clears the texture-offset enable byte. Our handler
updated the DMA bases but omitted that reset. Reading the next table entry could
then shift the asteroid's texture address into unrelated memory, producing
intermittent colored noise.

Commit `500b2a2` clears `texture_offset`, `texture_shift`, and `texture_count` at
that command boundary. The reset applies regardless of how many textures the
previous model used. The observed 40-entry boundary explains why a fixed cap
can mask this scene's symptom, but the command's reset semantics are the
appropriate rule.

Controlled replays through VI 3150 found 115 nonzero stale image-address shifts
before the correction and none afterward. Some were subsequently undone by
the existing texture-load heuristic, so that count is not a corrupted-frame
count. A separate comparison of 129 consecutive presented frames found 28
affected frames; the corrected frames replace colored noise on a small passing
asteroid with its rock texture. The largest changed area contains 402 pixels
at 640x480. EmuHawk using Ares64 also shows normal rock textures in this sequence;
that reference is an appearance check rather than a pixel-aligned parity claim.

The real command-handler regression covers resetting used and unused tables,
repeated resets, and explicit rearming by a later model. Both
`jfg.rt64_f3ddkr_texture` and `jfg.rt64_shell` pass. The aggregate evidence is
[opening-asteroid-texture-reset.json](../../evidence/opening-asteroid-texture-reset.json).
ROM-derived captures remain private. This verification covers the opening
sequence and reset behavior, not full-campaign renderer equivalence.

The owner replayed the corrected opening cinematic on 2026-10-08 and confirmed
that the asteroids look good. This is additional visual acceptance of this
sequence, not a full-campaign or pixel-exact parity claim.

## Opening lens-flare occlusion (2026-10-09)

The owner compared the opening ship flight with original N64 hardware and
reported that our flare remained visible through the planet and ship. Full
CPU framebuffer writeback was already enabled. A depth-buffer trace adapted
privately from Luke Deardoff's community diagnostic showed that the game was
mostly receiving cleared far-depth values instead of rendered geometry.

F3DDKR counted display lists can submit raw RDP `EF` mode commands. These
update the effective RDP mode without updating RT64's cached RSP mode stack.
`RSP::drawIndexedTri` used that stale stack to decide whether to extend the
framebuffer's depth-write bounds. Geometry could therefore write depth on the
GPU while its depth buffer was omitted from the CPU readback. The game's
original visibility test then treated an obstructed light as unobstructed.

The correction uses the effective RDP depth-write bit, matching the actual
draw call. A hash-pinned CMake patch generates the corrected translation unit
without modifying the pinned dependency checkout. It leaves the game's
visibility routine and framebuffer writeback enabled. No scene-specific
timing, forced flare suppression, or shadow-softening change is involved.

A real CPU command/triangle regression covers all four combinations of RSP
and RDP depth-update state. It fails against unmodified RT64 and passes with
the correction; the F3DDKR texture and renderer-shell regressions also pass.
Matched native captures and an EmuHawk/Ares64 run check the opening flight.

Across 181 consecutive native presents (1210-1390), 50 frames changed
(1217-1266). The candidate suppresses the false flare while the planet blocks
the light and restores it at the planet edge. A separate 246-frame
EmuHawk/Ares64 reference shows the same reveal behavior; this is an appearance
comparison, not pixel-aligned parity.

A follow-up captured 41 consecutive frames of the first, rounded blue Gemini
ship (native presents 1490-1530) and 71 EmuHawk/Ares64 reference frames. Those
native frames are unchanged by the correction. The owner clarified that the
supplied screenshot shows the same Gemini ship later in the cinematic. A later
capture locates that shot (representative native present 1630 and emulator
frame 3060); both show the ship blocking the flare. The owner subsequently
confirmed that the fix works, then reported audio interruptions during later
scenes. The earlier interpretation that this was a different ship is withdrawn.

These checks establish appearance and owner acceptance for the reported
occlusions, not full-campaign or pixel-exact renderer equivalence. ROM-derived
captures remain private; aggregate evidence is in
[opening-lens-flare-depth-bounds.json](../../evidence/opening-lens-flare-depth-bounds.json).

## Opening cutscene audio interruptions (2026-10-09)

The owner heard repeated interruptions while drones attack tribals and a brief
interruption during Juno's ship escape. A normal-launcher replay reproduced two
audio underruns and an approximately 130 ms gap near 157 seconds in actual
Windows output. Generated audio continued across the gap: waveform and
spectrogram comparisons distinguish the playback dropout from intended silence.

Sustained host CPU work was exhausting the pacing margin. When the VI loop gets
more than about 66.7 ms late, it resets its deadline to the current time. The
audio device continues playing during that lost time, so repeated resets drain
the queued samples until playback pauses to refill. A profiled reproduction
discarded 270.077 ms across four resets. Normal-launcher live exports exposed
the overhead that a simpler hidden replay missed. Disabling exports removed
the symptom in a diagnostic run; the implemented fix keeps them enabled.

The renderer now merges changed snapshot bytes in SIMD batches on supported
targets, skips CPU refresh blocks already identical to actual renderer memory,
and validates/copies completed writeback ranges in bulk. Comparing with actual
renderer memory preserves CPU writes when framebuffer storage is reused.
Conflict checks still complete before any write, including unaligned byte
boundaries. The portable scalar path remains available. Full depth and color
writeback, the lens-flare correction, guest audio, buffer thresholds and timing
policy remain unchanged. No scene-specific waits were added.

Across 3,212 graphics tasks in the two busy ranges, mean snapshot-import time
fell from 1,088 to 908 microseconds and its 99th percentile from 2,749 to 1,513.
Mean CPU writeback fell from 52.9 to 6.3 microseconds; its 99th percentile fell
from 471 to 61. The profiled candidate had no deadline resets. Renderer GPU
submission time did not improve; these savings are in host memory handling.

Three clean full-intro replays through VI 12000 passed with live exports on and
other game replays stopped: two at a 1280x845 game viewport and one verified at
1920x1080. All recorded zero audio underruns/overruns and no output-loss
candidates lasting at least 6 ms. Each generated PCM prefix is byte-identical
to the original across 17,615,424 bytes, approximately 200 seconds. Actual
native-process WASAPI recordings were aligned to generated PCM; waveforms,
spectrograms and a known-gap positive control validate the comparison.

At actual 1080p, continuous-frame presentation excess above the guest's VI
cadence peaked at 9.211 ms (99th percentile 3.448 ms). Room changes are retained
separately: at VI 6328 the guest supplies no new picture for 128 VIs, with
17.713 ms additional host delay in that run and 21.116 ms in one normal-size
repeat. These results do not establish perfect display scanout, zero shorter
audio disturbances, or equivalent performance on every machine.

All three renderer regressions pass, including depth-bounds and asteroid
texture tests. Private randomized comparisons cover 192 full-size memory cases
against the previous implementation, plus 192 scalar-fallback checks. Public
regressions cover mixed CPU/GPU bytes, vector/block boundaries, reused storage
and atomic rejection of a late conflict. The clean tested runtime is prepared
for the current normal launcher and `Test Opening Cutscene.cmd`, which uses a
separate fresh save. The owner replayed it and confirmed that it looks good
on 2026-10-09.

The aggregate evidence, exact hashes, thresholds and capture limitations are in
[opening-cutscene-audio-continuity.json](../../evidence/opening-cutscene-audio-continuity.json).
Audio recordings, spectrograms and ROM-derived images remain private.


## Qualification with original guest timing (2026-10-09)

The opening fixes now coexist with the publicly integrated Quarry timing work,
current controls and unified frontend. Earlier results above describe the
previous cooperative runtime. The combined runtime uses the original guest OS
and hardware-clock model; it required removing a per-dispatch environment
lookup during busy polling to retain uninterrupted audio.

Two full opening replays and one Quarry cutscene/gameplay replay from a fresh
ROM-to-build run passed with zero audio underruns/overruns and no detected
Windows output gaps of at least 6 ms. Generated PCM is unchanged. All three
renderer regressions still pass. See the [integration findings](quarry-audio-sync-findings.md#public-unified-runtime-integration---2026-10-09)
and [aggregate evidence](../../evidence/unified-original-timing-validation.json)
for exact hashes, timing results and measurement limits.
