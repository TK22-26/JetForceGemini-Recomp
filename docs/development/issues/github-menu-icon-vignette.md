# GH-057: Menu icons show grey boxes in widescreen; title vignette edge is stepped instead of smooth

Status: local icon and vignette candidates; GPU and actual menu captures verified; owner batch review pending.

Source: [Menu icons show grey boxes in widescreen; title vignette edge is stepped instead of smooth](https://github.com/TK22-26/JetForceGemini-Recomp/issues/57). Evidence snapshot retained privately in D:/JFG-private/remaining-gh-issues-20261027/github-issues.json.

## Reported symptoms and reproduction

### Problem type

Graphics

### Launcher and game build

Source build of main d8e338c (v1.4.0) with only the shadow change from #56 added; built with build_from_rom.py. Grey boxes also seen on earlier versions.

### Windows version, GPU, and input device

Windows 10, NVIDIA RTX 2070 Super (D3D12), PlayStation controller

### What happened and how to reproduce it

**1. Grey boxes around the START / PLAY / MULTI / OPTIONS icons (widescreen)**

Steps: set widescreen on, go to the title menu and look at the menu icons. Expected: no grey box (as on the console). Actual: each icon has an opaque light-grey box/ring around it.

Cause I found: each icon is a 44x44 RGBA16 texture whose 1-px outer ring is grey (156,156,156) at alpha 0. In 4:3 the game draws the icons as unscaled copy-mode texrects, which skip alpha-0 texels. In widescreen they are scaled by 4/3, so the game uses a 1-cycle texrect instead (OtherMode L `0x00552048`: AA_EN, IM_RD, ALPHA_CVG_SEL, no alpha compare; combiner `FC119623 FF2FFFFF`). RT64 only uses texel alpha for coverage when CVG_X_ALPHA is set, so the ring draws as an opaque grey box.

Fix on my community branch: for exactly that 1-cycle texrect mode, set the alpha-compare threshold for the texrect and restore the mode afterwards (`src/renderer/rt64_f3ddkr.cpp`, `texture_rectangle_with_icon_alpha`, on https://github.com/lukedeardoff/JetForceGemini-Recomp/tree/community/on-main). Happy to send it as a focused PR.

**2. Title/menu vignette edge**

On real hardware the round vignette around the title hallway fades smoothly. Here the edge shows visible steps. The vignette is an 80x60 I4 mask (16 alpha levels) drawn as four mirrored ortho quadrants (combiner `FC121624 FF2FFFFF`, OtherMode L `0x00504340`). On the console the 320x240 dither and VI filter smooth those levels out; upscaled, the steps show. I worked around it on my community branch with a replacement texture, so I don't have a code fix for this one yet.

AI-assisted with Claude; tested by me on Windows 10 / RTX 2070 Super.

### How often does it happen?

Every attempt

### Support ZIP and additional details

No support ZIP: this happens on every run, and the cause and render state (from the RT64 inspector) are described above. I will add a screenshot in a comment.

## Scope and evidence

Local owner-authorized batch: verify reported alpha defect and smooth vignette without asset redistribution. Preserve existing approved fixes, user profiles and ROMs. No GitHub posting or issue changes. A reported symptom is not yet a confirmed cause. Attempts, results, final remedy and verification limits will be recorded here.

## October 27 validation update

The reporter's icon diagnosis is confirmed by the decoder and a GPU fixture: transparent border texels no longer cover the background, while opaque interior texels still draw. The correction is narrowed to 44×44 RGBA16 icons, their exact one-cycle mode and combiner; previous blend/mode state is restored. The initial GPU fixture lacked white primitive/environment colors and rendered no visible icon; that fixture was corrected before qualification. Source attribution remains the reporter's issue and community branch.

The authored title vignette is reconstructed in the shader using a small nine-sample floating-point mask filter at upscaled resolution. Only its exact I4 material and 80×60 tile are eligible; high-resolution replacements and native resolution are excluded, and the underlying scene is not filtered. A real runtime trace confirms this material/tile, and paired native menu captures show the smoother edge. The initial exit-RDRAM replay did not retain prior renderer matrices and was discarded for visual comparison; actual frame captures are the evidence. Private evidence: icons-gpu-024, menu-frame-040 and menu-frame-baseline-040. Both shader backends compile. Final owner batch review remains pending.

## Original-ROM comparison, October 27

Pinned EmuHawk 2.11.1 with Angrylion/cxd4 now confirms the menu reference using
the unmodified US ROM. The saved native widescreen option is enabled
(options word D00000E9; bit 40000000 set). A menu checkpoint after ordinary A
input shows transparent outer icon borders, without the recomp's opaque grey
boxes. The actual corrected recomp menu capture has the same transparency
behavior. The N64 VI-filtered vignette is also visually smooth at its native
resolution; the candidate's upscale-only filter preserves that intended effect.

Private evidence: emuhawk-sanitization-20261027/emuhawk-vine-007/session/
checkpoint-d2, scope.json; paired native menu-frame-040 and baseline from the
earlier batch. This is an original-ROM emulator comparison, not new hardware
testing or a pixel-exact comparison of different render resolutions/animation
phases. Owner review of the assembled candidate remains pending.
