# Vulkan diagnostic frame readback crashes

- Status: reproduced in a private Proton fixture; source cause identified; no runtime fix or released resolution.
- Severity: diagnostic-session crash. Normal owner Play is not implicated by this evidence.
- Affected build: USA v33, runtime SHA-256 `1318472f4865e0547ff6d93039600e690d3aab51c4483d476d3999d8edaaa66c`; GE-Proton11-11 with software Vulkan.

## Reproduction and evidence

Enable `JFG_PHASE8_FRAME_CAPTURE` and start a fresh isolated game. Both hidden
and ordinary-window runs fault near VI187â€“188/poll67, before the opening story.
The retained exception is an access violation at module RVA087c0e2e. Matching
PDB symbols resolve the path to `plume::VulkanCommandList::copyTextureRegion`,
`jfg::CaptureContext::draw`, and RT64's presentation thread. Private evidence:
`gh41-opening-skip-20261107/proton-opening-baseline` and `proton-opening-visible`.
No owner save or configuration was used.

## Cause and limits

[CaptureContext](../../../src/renderer/rt64_shell.cpp) requests a texture-to-buffer
copy using a placed-footprint destination. The pinned Plume Vulkan implementation
only distinguishes buffer-to-texture from texture-to-texture; the latter branch
dereferences the null destination texture for this readback request. D3D12's
working capture path does not validate Vulkan readback support. This is separate
from [slow opening skips](cutscene-skip-completion-time.md), which the owner also
observed with logging disabled.

A correct remedy needs a qualified Vulkan image-to-buffer copy, including its
format, row pitch, image layout, synchronization and actual readback validation.
No dependency pin or renderer implementation is changed in this investigation.
Two ordinary no-frame-capture runs (baseline and updated support diagnostics)
complete the opening skip and exit normally under GE-Proton. This confirms the
fixture readback limitation is separate from the slow skip. Do not claim the
optional capture path fixed from that workaround.

## Lesson

Cross-platform diagnostic features require their own GPU-backend checks. A
Windows D3D12 screenshot test is not a Vulkan capture test, and a capture-induced
crash is not evidence of an ordinary gameplay failure.
