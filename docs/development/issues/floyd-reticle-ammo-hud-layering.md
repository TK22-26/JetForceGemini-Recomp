# Floyd reticle and ammo HUD layering

- Status: reported layering reproduced in original EmuHawk Angrylion/LLE; original behavior, no rendering correction indicated.
- Severity: original visual quirk; no aiming defect established by this overlap.
- Affected observation: Modern Players and Floyd preview3, Modern mouse/keyboard, runtime `126b960c5fe0298d2f2498abed25b6a153bdef2d7bf9dd396ac16a7629129dd2`.
- Reproduction: join P2 Floyd, move reticle toward the upper-left ammo display. Owner screenshot shows filled crosshair triangles obscured by the HUD while thin strokes remain above it.

Owner also reports mouse feels unchanged after preview3. That candidate changes only controller diagonal shaping; mouse and original outer bounds are intentionally unchanged. Physical-controller acceptance remains pending.

The prior bounds comparison establishes native reticle limits, not this compositing order. Hypotheses: original CPU-line/GPU-triangle drawing order, or a CPU-mask presentation regression. Existing shuriken retention work makes the latter worth checking but does not establish a shared defect. Compare unmodified original EmuHawk at overlapping positions in both 4:3 and widescreen, preserving existing saved states and owner profile. No intended-design claim from the screenshot alone.

Private evidence: `floyd-bounds-20261021/hud-overlap-review`, owner screenshot and fresh sealed original checkpoints. Related: [aim bounds](floyd-widescreen-aim-bounds.md), [controller diagonals](modern-floyd-controller-diagonal-range.md), [software reticle retention](shuriken-reticle-flicker.md). Source review/replay and final results pending.

Initial original screenshots reproduce triangle occlusion in both modes, but omit the thin strokes; the emulator template disables GLideN64 copy-color-from-RDRAM. This limits that visual comparison and is not evidence of a preview bug. Repeating from startup with that option enabled in a fresh private emulator copy, original save/ROM and ordinary input unchanged; no checkpoint identity bypass.

GLideN64 with copy-from-RDRAM enabled still omits the thin strokes in this fixture, so that repeat is inconclusive for line/HUD order. Next bounded comparison uses original EmuHawk Angrylion with its required LLE RSP, fresh startup (no cross-renderer savestate import). Plugin enum and LLE routing verified against [BizHawk 2.11.1 settings](https://github.com/TASEmulators/BizHawk/blob/2.11.1/src/BizHawk.Emulation.Cores/Consoles/Nintendo/N64/N64SyncSettings.cs) and [core](https://github.com/TASEmulators/BizHawk/blob/2.11.1/src/BizHawk.Emulation.Cores/Consoles/Nintendo/N64/N64.cs). Private copies only.

## Original rendering result

EmuHawk 2.11.1 with Angrylion and its LLE RSP reproduces both components in the original widescreen scene: filled reticle triangles are covered by the ammo panel, while the thin green strokes cross the blue HUD border. Two positions near the ammo display were inspected in raw screenshots and nearest-neighbor detail crops. This agrees with the owner's preview3 screenshot. It is observed original behavior, not a claim about undocumented artistic intent. No product rendering change is warranted for this report.

The comparison starts the original supported USA ROM from a private copied save, uses ordinary P2 input and leaves gameplay RAM unmodified. It does not import state from the other renderer. The original screenshots and all GLideN64 attempts are retained privately. GLideN64's missing software strokes made those initial comparisons inconclusive for line order, even with color-from-RDRAM enabled. Their coordinate/triangle observations remain useful; do not use them to claim missing native lines.

Evidence: `hud-overlap-review/original-angrylion/session/checkpoint-a1.png` and `checkpoint-a2.png`, corresponding sealed checkpoint manifests, `original-angrylion-hud-detail.png`, `original-angrylion-near-detail.png`, and `summary.json`. No new source fix, commit or release. Transferable lesson: qualify CPU framebuffer effects in the reference emulator before treating its screenshot as a rendering oracle.
