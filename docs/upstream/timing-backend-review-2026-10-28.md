# Timing backend reference review

This is an architecture/source review for the [Original timing issue](../development/issues/original-mode-simulation-parity.md).
No upstream runtime was imported and no production dependency pin changed.
Source snapshots and licenses are retained privately with immutable revisions.

| Reference | Reviewed revision | Useful behavior and limit |
| --- | --- | --- |
| [N64Recomp](https://github.com/N64Recomp/N64Recomp/tree/ffb39cdad1da5de07eaaa48bd1db4a89a7986771) | ffb39cdad1da | Generated RSP code executes microcode, but its COP0 handling reports DMA as complete and ignores yield-status writes. Overlay resumption is not general timed preemption. |
| [Ares debugger fork](https://github.com/HailToDodongo/ares-64/tree/b4ead632f6a983d2e86546a6bba2b7a5c2ccb6c0) | b4ead632f6a9 | RSP instruction pipeline, issue/stall accounting and scheduled SP DMA provide a useful workload reference. RDP FullSync raises DP immediately when processed; functional rendering and a running DPC clock do not establish hardware rasterization time. |
| [CEN64](https://github.com/n64dev/cen64/tree/e0641c8452a3ae8edcd2bf4e46794bb4eaafc076) | e0641c8452a3 | Explicit RSP pipeline and fixed CPU/RCP clock relationship are useful architecture references. Its inspected SP DMA routines copy data synchronously and DMA busy/full reads return zero. It is not a complete ready-made timing solution for our requirement. |
| [paraLLEl-RSP](https://github.com/libretro/parallel-rsp/tree/9ab776a2ce28899769c4f911403234cac62fc799) | 9ab776a2ce28 | Useful functional execution. The inspected plugin entry runs until halt/IRQ and returns its supplied cycle argument; that return is not a measured task duration. |

Specific implementation references:
[N64Recomp COP0](https://github.com/N64Recomp/N64Recomp/blob/ffb39cdad1da5de07eaaa48bd1db4a89a7986771/RSPRecomp/src/rsp_recomp.cpp),
[CEN64 pipeline](https://github.com/n64dev/cen64/blob/e0641c8452a3ae8edcd2bf4e46794bb4eaafc076/rsp/pipeline.c),
[CEN64 DMA/status](https://github.com/n64dev/cen64/blob/e0641c8452a3ae8edcd2bf4e46794bb4eaafc076/rsp/cp0.c),
[CEN64 transfers](https://github.com/n64dev/cen64/blob/e0641c8452a3ae8edcd2bf4e46794bb4eaafc076/rsp/interface.c),
[paraLLEl-RSP entry](https://github.com/libretro/parallel-rsp/blob/9ab776a2ce28899769c4f911403234cac62fc799/parallel.cpp).

The paraLLEl-RDP project's own [synchronization description](https://github.com/ares-emu/parallel-rdp#synchronization)
also leaves CPU/GPU synchronization policy to the integrating emulator. Pixel
accuracy is not a substitute for guest device timing. The [Toast review](toast-timing-review-2026-10-28.md)
separately identifies useful native enhancement ideas without claiming they
restore Original pacing.

## Actual reference qualification

The published [nemu64-test revision](https://github.com/thelemmy/nemu64-test/tree/9a8b9f7d94ee2f6f57d7feed70c98c22cdc30e6c)
has downloadable CI ROMs from [run 34256763312](https://github.com/thelemmy/nemu64-test/actions/runs/34256763312).
Both archive digests were checked before using those unmodified synthetic ROMs.
They are not proprietary game code and were not run on the owner's console.

With private observers/interventions disabled, our pinned newer Ares interpreter
passes all 4,637 base tests. Its extended run fails 924 of 1,604 timing cases and
9 of 13 cycle cases. Failures include CPU dependency/exception timing, FPU timing,
cached and uncached memory behavior, and cache-related cycle cases. The four
passing RSP timing tests cover clocks and scalar SLL only. They do not qualify
vector issue, DMA contention, full task timing or RDP rasterization time.

EmuHawk's Mupen64Plus cached and pure interpreters both remain in the synthetic
ROM's public IPL3 PI_STATUS-busy loop at the observed PC A40001C4. The two full
attempts time out, so no suite score is assigned. EmuHawk's older Ares64 core
also fails to complete this suite, exiting with C0000005 after a last captured
frame of 361. These are reference-tool limits, not failures of the game build.
Successful original-ROM gameplay comparisons remain useful within their scope.

The existing native instruction model independently matches only 6 of 15 selected
published warm-cache/instruction expectations. Its cost conservation checks pass,
which establishes that modeled work is charged consistently, not that the model
is hardware-accurate. The manufacturer manual's load-use and cache-busy rules
remain relevant; removing all cache-hit charges would not be a general solution.

## Implementation implications

A proper Original policy needs a guest clock independent of host speed and
presentation FPS; original per-call simulation; workload-dependent CPU and
device timing; and actual task/status/interrupt ordering. JFG yields graphics,
runs audio, then resumes the same graphics task. Small Clone passes can yield too.
A fixed delay by task type cannot represent that behavior.

A candidate must keep host rendering enhancements separate from the canonical
guest workload, preserve native RDRAM/writeback ownership, and qualify audio
during loading. The single-model flying-actor LOD control did not change timing,
but does not exercise real detail switching. Do not silently turn unqualified
settings into a runtime fallback or change the owner's approved enhancement
behavior to hide this boundary.

Required acceptance is matched-state and matched-VI replay in both light and
loaded scenes, task yield/resume and DMA/status checks, unchanged logical states
when only output FPS changes, and normal-Play transition/audio validation.
Physical-console comparisons must retain their measured scope; no emulator or
static source description supplies a universal hardware guarantee.

[Sanitized measured evidence](../evidence/original-timing-research-20261028.json).
