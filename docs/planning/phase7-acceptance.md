# Phase 7 / M3 acceptance contract

Phase 7 is the first rendered-frame milestone. It is not satisfied by the
existing semantic graphics fallback, by a synthetic image, or by one isolated
real graphics task.

The machine-readable contract is
[`config/phase7-acceptance.json`](../../config/phase7-acceptance.json). Every
gate is now supported by current evidence, and the public-safe aggregate in
`evidence/phase7-completion.json` is reconciled by the Phase 7 validator.

## Required proof

1. The renderer is the RT64 commit pinned in `dependencies.lock.json`.
2. The project registers a fail-closed renderer callback path and supports the
   reviewed `F3DDKR`/JFG command family.
3. At least one real task from the boot/title scene and one real task from a
   representative gameplay scene reach the renderer.
4. Framebuffer dimensions and addresses, RSP/RDP completion ordering, command
   logging, and unknown-command rejection are executable checks.
5. Each scene is captured at least three times on the reference runner and is
   compared with an independently captured emulator oracle.
6. Renderer-disabled and renderer-enabled runs produce identical simulation
   hashes. Every supported renderer backend also produces the same simulation
   hash.
7. Developer builds expose the RT64 frame debugger.

Pixel comparison is performed by
`scripts/compare_phase7_frames.py`. The emulator oracle is scaled uniformly
to fit the RT64 output and centered on black. Raw RGB error and foreground
coverage remain unfiltered. Before 8x8 SSIM, both luminance planes receive the
same separable Gaussian prefilter with a sigma of one emulator-oracle pixel;
this prevents subpixel texture-sampling differences between the independent
rasterizers from masquerading as scene-structure failures. Every accepted
repetition must meet all three fixed thresholds: 8x8 SSIM at least 800,000 millionths,
foreground intersection-over-union at least 800,000 millionths, and mean
absolute RGB error at most 60,000 millionths. These values are part of the
machine-readable contract and cannot be relaxed by a completion producer.

## Evidence boundary

ROM bytes, task bodies, command bodies, RDRAM snapshots, and image bodies stay
under ignored private directories. The tracked completion summary may contain
only pins, producer provenance, aggregate counts, dimensions, comparison
results, and gate booleans. It must not contain private paths, addresses,
command values, image bodies, or ROM-derived identifiers.

The validator is run with:

```text
python scripts/validate_phase7_acceptance.py
```
