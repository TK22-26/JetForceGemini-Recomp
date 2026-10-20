# RENDER-019: Tawfret brightness and distant haze differ from N64 reference

## Status
Reported 2026-10-19. Original-ROM comparison reproduces a fog-dependent rendering difference.
A shader candidate now closely matches the matched original capture. Unreleased;
four original-task viewpoints checked, including explicit native-resolution replay;
owner reports remaining apparent haze difference, with live material verification pending.
Owner supplied a darker scanlined reference and then another reference explicitly
identified as N64. Our screenshot has a brighter gray sky and a relatively distinct
distant boundary. This is a visual-fidelity report, separate from missing rain.

## Reproduction and evidence
Tawfret wet swamp, beside the green barrel, red/white pickups and purple gem on a
tree. Owner screenshot shows Custom output about 120 FPS / 30 scene FPS.
The first reference contains visible scanlines; the later owner-identified N64
reference does not have that same obvious scanline pattern. Camera positions and
weather/lighting phase differ, so still images alone cannot isolate a renderer bug.
Private clipboard artifacts: YgwJIu (first reference), nVY47G (our game), tJLQ6y
(owner-identified N64 reference). Do not publish these or save data automatically.

## Investigation plan
Check the actual active build/profile and fog percentage, native sky/fog/lighting
state and the enhancement path. Distinguish native lightning/weather changes,
fog density/distance, VI/color conversion and reference capture differences.
Do not apply a global brightness reduction based solely on unmatched screenshots.
Owner explicitly authorized a muted EmuHawk lighting comparison and review of the
historical gamma correction on 2026-10-19. Use isolated copied save/configuration;
retain original saves and settings. Other live candidate checks remain owner-led.

## Acceptance and limits
Matched original-RAM/VI rendering and zero/fixed-fog controls now support the
candidate below. Fog 100% retains the native packed coefficients. Broader scene
coverage and owner live verification remain required; not a released resolution.

## Historical gamma review (2026-10-19)

The earlier fix is commit eca79a6a6c41a0d9992761cfcffe1b0daa55944f
(2026-10-02), described in [boot/gameplay notes](../boot-gameplay-fix.md).
osViSetSpecialFeatures previously recorded the request without updating the
renderer VI control bits, leaving gamma enabled when the game requested it off.
The fix remains in both original-OS and named-HLE dispatch paths, using
vi_apply_special_features. RT64 VI::gamma and VideoInterfacePS consume that flag;
the game image does not use the diagnostic-counter overlay's separate constant.

The focused jfg.vi_presentation regression test passed on 2026-10-19.
The isolated original-ROM EmuHawk Ichor save records VI_CONTROL 0x13016
(gamma off), matching the existing gamma-off/divot/dither test case.
This verifies the historical behavior but does not yet settle Tawfret fidelity.
Both owner profiles retain fog 100%; that setting leaves the original packed
fog coefficients unchanged.

Private comparison attempts and limits:
- Both current copied saves resume at MilitaryBase Approach (43), not Tawfret.
  Save hashes and isolated emulator identities are retained privately.
- A private exit-destination fixture loads Swamp (115) via the original transition
  consumer. It changes only the source exit destination/contact and position,
  not lighting, fog, weather or VI values. This is a scene fixture, not an
  unmodified gameplay-route comparison.
- GLideN64 footage from this fixture shows CPU rain over a black scene; it is
  excluded as a usable lighting reference. The observer's cached player address
  also becomes stale at the transition; current actor-table decoding finds the
  new playerGirl actor. Do not interpret that stale pointer as absent gameplay.
- Angrylion/cxd4 subsequently produced usable original-ROM images, as recorded below.
No global gamma/brightness correction has been applied on this evidence.

## Matched original-renderer comparison (2026-10-19)

EmuHawk 2.11.1 with Angrylion and cxd4 RSP renders the original Swamp scene using
the isolated fixture above. Checkpoint 03 at VI frame 3469 has VI_CONTROL
0x13016 (gamma off). Its original RGBA16 color buffer already shows the darker
purple haze before VI processing. Thus the difference is not solely scanlines,
capture display gamma, or VI postprocessing.

A diagnostic extension to phase7_rt64_task_runner accepts the full captured
14-word big-endian VI register file, avoiding its legacy hardcoded gamma-on
defaults. Replaying the captured original graphics task and RAM in current
RT64 with those original registers reproduces the brighter gray sky and more
distinct distant boundary. Original 4 MiB RAM is preserved byte for byte and
zero-extended to the renderer's required 8 MiB storage. The captured task may
precede the final native color buffer by one render update; CPU rain and exact
actor phase are not pixel-parity criteria for this comparison.

A counterfactual gamma-on replay brightens the entire image substantially and
does not resemble the reported localized sky/haze difference. The historical
gamma correction is not a candidate to undo.

Fog isolation:
- Zeroing the original BC000008 fog coefficients at original osSpTaskLoad
  produces a much brighter sky in Angrylion. The same coefficients zeroed in
  RT64 produce a visually similar underlying scene. These are diagnostic
  counterfactuals, not proposed gameplay settings.
- Restoring the native coefficients (5565, -5342) restores the difference.
- Forcing maximum fog in RT64 produces the native fog color (28, 15, 36),
  confirming the fog path and color are active.
- Increasing only the fog offset darkens the image but does not establish the
  correct haze shape or remedy; rejected as sufficient justification for a fix.
- The initial screen-space interpolation probe omitted D3D12's generated shader
  entry points and did not change the measured sky. It is not evidence against
  interpolation being involved.
- Covering both compiled and generated entry points alone still differed from
  the original. Forcing fully opaque fog for behind-camera vertices also failed
  to reproduce the original. Neither partial remedy was retained.

Private evidence: D:/JFG-private/v131-rnd-20261019/tawfret-lighting-angrylion,
tawfret-lighting-angrylion-fog-none and tawfret-renderer-comparison. Original
save hashes remain unchanged. No ROM, save, generated code or screenshots were
published, and no lighting candidate was installed in the owner's preview.

## Shader candidate and first matched validation

The current shader clamps each vertex's fog amount before clipping/interpolation
and uses perspective interpolation for shade alpha. On the original captured
large sky polygons, preserving signed z/w through an affine alpha gradient and
clamping at the pixel shader closely reproduces the original low-level output.

The candidate in [rt64_fog_fidelity.cmake](../../../cmake/rt64_fog_fidelity.cmake):
- preserves the signed fog coordinate through the vertex stage;
- interpolates shade alpha in screen space, independently of existing RGB and UV
  interpolation;
- clamps alpha before the pixel combiner/blender uses it;
- handles a zero fog multiplier without a division, including the 0% preference;
- covers compiled shaders and D3D12's generated shader entry points;
- patches a build-private source view with pinned input hashes, leaving the
  upstream checkout intact.

This is a rendering calculation correction, not a Tawfret-specific multiplier,
gamma change, color override or stronger fog preference. Compatibility limit:
non-fog shade alpha also follows screen-space interpolation, so transparent
materials need live regression review. The original RSP instruction sequence has
not been independently decoded to claim instruction-level fog equivalence.

In the matched top-center sky region (original 320x240 color buffer versus
resampled active RT64 scanout), mean absolute RGB error decreased from 18.91 to
4.45 on a 0-255 scale. Original mean RGB was (102.52,94.71,107.73); candidate
(101.01,93.29,105.76), compared with previous (120.96,114.62,124.84).
The unchanged foreground region remains at 3.90 error. These are image-region
measurements, not a claim of whole-frame or whole-game pixel parity.

Zero-fog and constant-128 controls retain their prior results (sky errors 4.14
and 3.27); this isolates the improvement to the variable fog gradient. Remaining
small differences include native RGBA16 dithering/filtering and neighboring
render-update phase. The gamma-on counterfactual remains excluded.

The diagnostic runner now accepts a captured VI register file for snapshot
replays. Valid captured state renders successfully; a malformed four-byte VI file
is rejected with exit 3; the legacy origin:width interface still renders.

All intermediate probes and failures are preserved privately. No screenshots,
ROM, original/generated game code or personal save data were published.

## Exact task capture and additional views

A later arbitrary-frame snapshot timed out in the standalone replay. Inspection
showed reused command memory being rewritten: one descriptor's recorded end no
longer contained EndDL. This is a diagnostic snapshot limitation, not evidence
that the live game or the new shader hangs. That attempt is preserved and
excluded from candidate acceptance.

The corrected observer records RAM and the task at original osSpTaskLoad, then
the original output buffer before the next main graphics task. It checks EndDL
before replay and uses the task's color target for scanout while retaining the
captured VI settings. Four views use only native controller input between them;
the isolated exit fixture is unchanged. Original title card identifies the
captured Tawfret room as Bog (level 115); older private fixture labels say Swamp.
No lighting/weather/VI game state was patched in these acceptance comparisons.

Both the unmodified pinned shaders and the maintained candidate rendered all
four complete captured tasks successfully. In the broad top-center comparison
region (which includes nearby geometry in some views), mean absolute RGB errors:

| View | Existing shaders | Candidate |
| --- | ---: | ---: |
| 00, affected sky | 10.58 | 4.67 |
| 01 | 3.40 | 3.49 |
| 02 | 3.13 | 3.13 |
| 03 | 3.27 | 3.27 |

These wider-region values are distinct from the smaller sky-region measurement
above. The small 0.09 increase in view 01 is retained in the record; not every
pixel or viewpoint improves. Native dithering, filters and CPU overlay behavior
still differ. The accepted evidence is a close fog-fidelity candidate, not full
RSP/RDP equivalence or a performance qualification.

The 0%-fog test frame is byte-for-byte pixel-identical to the previous shader
output. The patch audit accepts the pinned inputs, is repeatable, rejects a
modified input and confirms the original checkout was unchanged. Native Release
and the diagnostic renderer build successfully; jfg.rt64_f3ddkr_texture and
jfg.vi_presentation pass.

Private evidence: tawfret-lighting-submission and
tawfret-renderer-comparison/exact-tasks below the same investigation directory.
The evidence runner and renderer variants were restored to the maintained
candidate after controls. Owner approved the lighting/fog candidate on 2026-10-19; unreleased.

## Owner follow-up: resolution versus haze (2026-10-19)

Owner reports the lighting preview still appears less foggy than original footage.
They explicitly mean softness from the original lower rendering resolution, not
temporal motion blur. The new screenshot pair differs in camera position and
aspect ratio, so it cannot isolate fog strength. This is unresolved live feedback,
not candidate acceptance.

Owner approved a bounded matched-camera/native-resolution comparison. It reuses
the exact original osSpTaskLoad input/output tasks above, retaining native fog
coefficients and gamma-off VI state. Dedicated private renderer probes force
RT64 Original resolution; production preview settings and source are preserved.
Results and source restoration receipts will be recorded below.


### Native-resolution result

Dedicated private probes explicitly select RT64 Resolution::Original and a
320x240 hidden output window. They replay the same four original complete tasks
with the baseline and candidate shaders, retaining source RAM, matrices, fog and
VI state. The original output and renderer readbacks are decoded identically
from RGBA5551 at 320x240, before display filtering. This avoids treating a
downsampled high-resolution screenshot as a native-rendering test.

For the affected sky patch in view 00 (x130..239, y5..29), average RGB on a 0..255
scale is:

| Renderer | Average R | Average G | Average B | Mean absolute RGB error |
| --- | ---: | ---: | ---: | ---: |
| Original ROM / Angrylion | 102.47 | 94.69 | 107.65 | reference |
| Previous shaders, native resolution | 124.19 | 117.83 | 128.03 | 22.19 |
| Candidate, native resolution | 103.19 | 95.42 | 108.06 | 5.82 |

The candidate's average channel bias is below one level here; individual pixel
errors are larger. Dithering phase, rasterization and CPU rain differ, so this is
not a maximum-error bound or pixel parity claim. The broad top-center candidate
errors across views 00..03 are 5.87 / 4.53 / 4.09 / 4.25. Their baseline errors are
12.53 / 4.45 / 4.09 / 4.25; the small view-01 worsening remains recorded.

The same candidate also rendered at the normal higher resolution. Its native
RGBA16 readback is identical to the explicit native-resolution readback for all
four tasks, while its displayed image has finer edges. RT64 has a native
render-to-RAM path, so identical readbacks do not imply identical high-resolution
GPU surfaces. The resolution-only comparison uses the actual scanouts and
labels its display scaling.

Conclusion: the original bright-sky discrepancy survives at native resolution
with the old shaders and is substantially corrected by the candidate. The
remaining impression of weaker fog in the owner's unmatched screenshots is
consistent with sharper rendering/display filtering. These matched tasks do
not establish a reason to increase fog strength or change gamma. They also do
not rule out every remaining material or view-specific difference.

Private evidence: native-resolution-fog/native-results.json,
comparison-summary.json, matched-native-fog-comparison.png and
resolution-only-comparison.png under the existing R&D evidence directory.
Two comparison images and a short explanatory text were copied to the desktop
for owner review. No color correction was applied to the images.

All probe edits in the worktree and generated renderer were restored byte for
byte, and the maintained diagnostic executable rebuilt. Installed preview
runtime SHA-256 remains
cfac17af630e519c62866ed52de60c8489edd232ddc99fc9f5df260e871ba54d.
No additional production rendering change, fog multiplier, dependency update,
save/settings modification or release was made. This validates the existing
candidate more narrowly; transparent-material live qualification remains open.

## Owner decision, 2026-10-19

Owner approved this candidate for the upcoming update. Automated results and
historical limits remain as recorded; this is local acceptance, not release.
