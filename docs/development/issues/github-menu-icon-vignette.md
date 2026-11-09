# GH-057: Menu icons show grey boxes in widescreen; title vignette edge is stepped instead of smooth

Status: Current local fixes reverified with renderer checks and USA widescreen captures; owner visual acceptance pending; unreleased.

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

The reporter's icon diagnosis is confirmed by the decoder and a GPU fixture: transparent border texels no longer cover the background, while opaque interior texels still draw. The correction is narrowed to 44Ãƒâ€”44 RGBA16 icons, their exact one-cycle mode and combiner; previous blend/mode state is restored. The initial GPU fixture lacked white primitive/environment colors and rendered no visible icon; that fixture was corrected before qualification. Source attribution remains the reporter's issue and community branch.

The authored title vignette is reconstructed in the shader using a small nine-sample floating-point mask filter at upscaled resolution. Only its exact I4 material and 80Ãƒâ€”60 tile are eligible; high-resolution replacements and native resolution are excluded, and the underlying scene is not filtered. A real runtime trace confirms this material/tile, and paired native menu captures show the smoother edge. The initial exit-RDRAM replay did not retain prior renderer matrices and was discarded for visual comparison; actual frame captures are the evidence. Private evidence: icons-gpu-024, menu-frame-040 and menu-frame-baseline-040. Both shader backends compile. Final owner batch review remains pending.

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

## November 8 current-build review

The owner authorized fresh verification of #57 and review of #58. Live GitHub
body/comments were captured privately; #57 has one screenshot comment, while
#58 has no comments or attached failing-session support ZIP. Current validation
results and their limits will be added below. Private evidence: `issue57-58-review-20261108/`.

### Fresh verification result

The current renderer texture fixture was rebuilt against the same renderer
libraries used by the delivered regional build and passes. It checks normal and
flipped qualifying icon rectangles, a nonqualifying tile, the owned nonzero alpha
threshold, command advancement and restoration of previous blend/mode state.
The current decoder and vignette-patch hashes match the delivered native build's
input receipt. The generated shaders in the USA, PAL and JP build caches contain
the exact material, upscale-only and high-resolution-replacement exclusions.

Actual muted USA sessions using the current Issue52 Camera Test package captured
the START screen and the PLAY/MULTI/OPTIONS menu in widescreen (320x180 display
canvas). Visual inspection finds no opaque grey outer icon boxes and a smooth
vignette transition. The authored blue icon frames remain. These are real native
frames, not reconstructed exit-memory replays. Two navigation captures landed
on the animated title and save-selection screens; retained as navigation evidence,
not substituted for the main-menu capture. All four sessions exited normally.

Private evidence: `issue57-58-review-20261108/renderer-regression/result.json`,
`current-source-pins.json`, `current-menu-us/final.png`,
`current-main-menu-us/final.png`, and the corresponding input, identity and run
records. Earlier October 27 evidence remains historical; its original private
directory was unavailable during this review and was not represented as freshly
reopened. Fresh visual capture covers USA, not PAL/JP or the reporter's GPU.

Owner check: use the current launcher, enable widescreen in the original in-game
options, then inspect START and PLAY/MULTI/OPTIONS at an enlarged window size.
Confirm no grey outer square and no hard vignette steps, unwanted halo or scene
blur; compare with widescreen off. No owner acceptance or release is inferred
from these automated checks.
