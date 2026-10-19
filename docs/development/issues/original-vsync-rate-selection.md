# Original frame rate appears to follow VSync refresh

- **ID:** RENDER-013
- **Status:** Reported; source path reviewed, live behavior not yet established.
- **Severity:** Medium; undermines native-versus-interpolated visual comparisons.
- **Affected:** Owner's v1.3.0-beta.2 private Vela source-only comparison.
- **Reported:** 2026-10-18. Owner selected Original and reports that enabling
  VSync appears to select screen refresh instead of native presentation.

## Reproduction and evidence

Compare Original with VSync on/off after restarting the game, in the same
pre-rescue scene. Owner is performing all gameplay and visual verification.
No agent game runs were started. Private original-vsync-review.json records
the settings observed during review; the saved file at that instant contains
Original, retained custom FPS 120, VSync off. The retained custom value is not
used in Original mode. Runtime settings are initialized when a game starts.

The observation remains open. Owner says the counter was off but movement was
noticeably smoother than 30 FPS. This is a visual report, not a counter-only
observation; actual intermediate-frame generation still needs checking.

## Source review

src/boot/native_boot.cpp disables presentation identities for Original and
passes zero experimental FPS to Rt64Shell. rt64_shell.cpp enables Manual
refresh and SkipBuffering only for Custom/Unlimited; RT64 defaults to Original.
rt64_f3ddkr.cpp skips prepare_interpolation when disabled. The pinned RT64
Original branch sets targetRate zero, which disables generated intermediate
frames. presentation_policy.hpp clamps a requested custom rate to display
refresh with VSync; it does not raise an ordinary requested rate.

The presentation counter counts swapchain submissions. Native VI changes and
CPU overlays can present separately from a new 3D scene, and native menus or
cutscenes are not necessarily fixed to 30 FPS. Do not impose an unconditional
30 FPS cap as a speculative remedy. Confirm actual runtime mode and generated
frame count before changing timing or presentation.

## Validation and remaining work

No fix or released resolution is claimed. Determine active configuration,
interpolation count and the owner's observed behavior with VSync on/off.
Preserve the independent [Vela blur investigation](vela-rescue-cutscene-stutter-resolution.md).

## Owner verification setup

Prepared JFG - Vela Original FPS with an isolated copy of the backed-up
pre-rescue save: Original, VSync on, frame counter and log on, audio muted.
The runtime is the normal blur-source pairing candidate, SHA-256
01f70f7e591f5c1bd4f4b4776b9580a079f775847fbc25fd7235b8865248711d;
the private mode-5 source-only experiment is not used for this check.
Existing owner profiles and saves remain untouched. Runtime frame-log headers
record the resolved mode/target/VSync used at startup. Performance evidence is
redirected to the private evidence volume; gameplay remains owner-driven.
No new runtime fix is claimed. Owner result pending.

## Owner clarification after Original comparison

Owner confirms that 30 FPS motion is correct and suspects the earlier result
was still using the previous 120-FPS mode before a restart. The three blurry
cutscene shots remain blurry; this does not close the separate blur report.
The two completed counter captures are reviewed in private
owner-original-fps-result.json, including runtime mode/target/VSync headers.
No timing or frame-rate code was changed. The suspected VSync override is
not reproduced in this owner follow-up; restart timing is a likely explanation,
not a proven reconstruction of the earlier unlogged session.
