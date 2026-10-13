# RENDER-007: Ground-shadow cadence at high refresh

Status: owner-reported sluggish shadow motion; source-level interpolation gap
identified, visible lag magnitude and correction not yet verified.
Severity: medium visual smoothness limitation; separate from combat FPS loss.

The owner noticed Juno's ground shadow looking less smooth than the character
in the expanded tutorial capture, while acknowledging uncertainty. Affected
preview is the develop-merged high-refresh runtime used by capture
20261013-172104. That recording has timings and a final image, not a continuous
video of the shadow; it cannot establish the shadow's exact visual delay.

The renderer interpolates owned character vertices and camera/model transforms.
Small intensity shadow-mask passes are excluded from scene interpolation, and
the original game reads them back for CPU blur/attenuation before sampling them.
Those textures and projected texture coordinates do not currently receive
caster-owned interpolation at each output phase. Thus 120 OUTPUT does not mean
120 newly animated shadow masks. A moving character can have smoother animation
than its shadow even with steady output. Texture and mask cadence is distinct
from a demonstrated temporal lag in the reported scene.

Source: rt64_f3ddkr.cpp semantic-target selection/prepare_interpolation,
rt64_interpolation_adapter.hpp apply_presentation_interpolation, and
rt64_shell.cpp CPU mask writeback. The pinned decomp shadowGenerate and shadow
projection routines establish the CPU-authored receiver/mask path. No mask
readback or CPU processing was removed to make a performance counter rise.

Next verification needs a fixed-route sequence of actual presented frames with
visible feet and shadow, compared at equal camera/body phase. A remedy should
bind the projected shadow to its caster/receiver and preserve original lighting,
CPU mask edits and clipping. Simply shifting receiver geometry or crossfading
textures can introduce floating shadows or ghosting and is not an accepted fix.

Related: [late tutorial jitter](tutorial-late-object-jitter.md),
[combat cadence](goldwood-combat-slowdown.md), and
[seams/lighting](character-seams-lighting.md). No released resolution is claimed.

## Bounded frame review (2026-10-13)

The final Original/Custom comparison preserves every non-framebuffer guest byte
and the save. The custom eight-frame capture shows Juno beside a wall, without
a clearly measurable ground shadow, so it cannot establish the reported lag or
validate a remedy. Readback probes have 2/3 audio underruns, unlike zero in the
separate native Play tests; do not use them as performance acceptance.

RT64 already supports texture-coordinate velocity and generic tile interpolation.
The missing part identified here is explicit caster/receiver ownership and
phase handling in this game's shadow path, not a claim that RT64 lacks UV
interpolation. No shadow correction is included in this review. Keep RENDER-007
open and require visible shadow/body comparisons before declaring a fix.
