# Known issues

Current v1.3 status and remaining qualification limits.
The [issue register](development/issues/README.md) links detailed evidence.
Earlier investigation states are preserved in the
[pre-v1.3 notes](development/known-issues-before-1.3.0.md); they are historical,
not the current acceptance checklist.

## v1.3 release qualification

The owner completed the combined New Game-through-Vela review and the targeted
corpse follow-up, and approved release preparation.
The release target is visibly smooth, responsive play with clean audio.
The completed long-route capture has zero audio-device underruns/overruns;
frame timing distributions and limits are recorded in the release checklist. An isolated timing outlier does not automatically block release; recurring
or noticeable stutter, audio gaps and lost input still require attention.
No campaign-wide, every-device or zero-stall guarantee is claimed.

v1.3 includes the owner-accepted ship-cutscene improvements,
high-refresh glass correction, boss camera-sweep interpolation, Reduced blur,
high-drop/ledge camera retention, storage settings and live fog strength.
Native standing-aim movement matches the measured original Expert values
in the qualified owner capture. See the release checklist for build and publication evidence.

A brief Vela-to-first-cut transition dip was previously reported. Ground-shadow
cadence, broader scene/camera coverage and Unlimited/360+ Hz behavior retain
finite validation. Review the new combined route before claiming those
reports resolved. See [performance follow-up](development/issues/1.2.1-session-1.3-followup.md).

## Reporter retests

- [#32: intermittent mouse look and vertical inversion](development/issues/github-mouse-look-and-inversion.md):
  reported on v1.3.0, Windows 11, RTX 5070 Ti and mouse/keyboard. Buttons and menus
  work while camera/aim motion intermittently fails. Inversion reportedly stays
  active with Off selected, including after restart. The reporter withdrew the
  proposed focus-only cause. Neither symptom is reproduced or fixed locally;
  the accepted focus-loss camera reset is not proof of capture recovery here.
- [#33: sideways roll in Modern Controls](development/issues/github-modern-controls-side-roll.md):
  owner reproduces crawling instead of rolling and confirms Original Controls can
  roll. Reviewed Modern mappings omit native lateral actions; unchanged native
  checks confirm analog-to-crawl behavior and a separate simultaneous-entry
  limitation. Original manual/guide identify a shot-evading roll from crouch
  or crawl; Lupus is excluded. Owner selects movement-based rolling without a
  gentle sideways-crawl band for v1, and additionally reports sideways input
  currently produces forward crawling. Roll-only implementation is now authorized
  and in progress; candidate and owner live verification are pending.
  The original report is v1.2.0; owner build is unspecified.
- [#25: Ally X cutscene, reticle and rain](development/issues/github-ally-x-rendering.md):
  reporter confirms missing falling rain and homing/tri-rocket/throwable reticles
  in v1.3 at 1080p/60 with Modern Controls. The earlier desktop mouse/120 FPS
  pass did not resolve this report. The owner reproduced both symptoms on the
  desktop; widescreen and the 60 FPS cap were excluded as sole causes. An
  unreleased output-timestamp correction restores rain/reticles in the owner's
  candidate test. Five archived room entries show a 427-435 ms delay before
  native rain writes, explained by the original fade gate and one initialization
  update. The owner still saw late rain in the first private fade preview. Its
  recording showed no activation: the first candidate supports type-0 opacity
  fades, while the black entry uses type-3 moving geometry. The actual native
  routine reproduces this missed case. A replacement spatial-fade preview now
  passes 1,049 tracked and 30,912 native integration checks plus deployed-launcher
  validation. The owner subsequently approves this replacement as fixing the
  rain delay locally. It remains unreleased; exact onset measurements,
  accumulated streak rounding and pixel-exact original-game comparison are
  unverified. Alternate transitions/projections, dimensions and intervening
  text/window output retain native gating. Reporter/Ally X retest is pending.
  Hardware/driver dependence is unproved.
- [#29: crackling followed by lasting audio delay](development/issues/audio-crackle-persistent-latency.md):
  reported every attempt after several minutes; resetting through the launcher
  reportedly restores sync. Detailed settings or an affected-session support ZIP
  are needed. No new fix is qualified.
- [#30: dual-stick ledge-camera reset](development/issues/controller-ledge-camera-reset.md):
  an unreleased candidate extends retained camera ownership to Modern controller
  ledge climbs. Source regression and native checks pass; owner confirms the ledge fix locally.
  Reporter retest and release remain pending.
- [#31: cutscene skipping](development/issues/optional-cutscene-skipping.md):
  opening story skipping now passes owner review. A further candidate adds
  King Jeff invasion completion after an owner-reported partial skip, and a generated native blue-A button.
  Native/focused checks pass. Owner verified the SS Anubis flashback, Vela rescue,
  Juno departure and Tawfret intro. Broader cutscene coverage remains open;
  unsupported scripts retain normal playback.
- [#19: invasion replay stutter](development/issues/github-invasion-replay-stutter.md):
  the original reporter confirms the latest update resolves the problem and
  requests closure; another affected user also confirms improvement. GitHub
  remains open with an explicit closeout TODO. Exact independent severity/cause
  attribution remains limited; this does not resolve the separate Ally X report.
- [#18: targeting controls](development/issues/github-held-aim-and-diagonal-movement.md):
  the reporter confirms firing no longer cancels held aim in v1.2.0. The separate
  standing-aim diagonal-speed correction is included in v1.3.
- [#4: Windows source setup](development/issues/github-windows-source-setup.md)
  and [#15: Linux source build](development/issues/github-linux-native-build.md):
  prior source remedies are released, while reporter-platform qualification
  remains limited. A packaged Linux AppImage is not qualified.

## Unreleased visual and controller candidates

- [Tawfret sky brightness/fog](development/issues/tawfret-brightness-fog-fidelity.md):
  EmuHawk confirms the old gamma-off correction is intact. A signed fog-gradient
  candidate closely matches complete original graphics tasks at four views;
  owner approved the lighting/fog correction locally; unreleased.
- [Removed controllers moving to later players](development/issues/controller-remove-auto-reassignment.md):
  persistent automatic-assignment exclusions pass core and real UI checks;
  owner approved the removal correction locally; unreleased.

## Original behavior and optional enhancements

[Enemy-clear door indicators](development/issues/door-enemy-lock-distance-darkening.md)
also darken at distance in EmuHawk. Further original-game investigation is
deferred by the owner; the accepted readability workaround remains in v1.3.
This is not evidence of a general transparent-material correction.

The original game deliberately softens some Vela-rescue shots and uses motion
blur in boss encounters. v1.3 offers Off, Reduced and Original blur, with Reduced
as default and a comfort note for Original at high frame rates. The owner
accepted Reduced and verified the original soft shots against N64 footage.

[Ichor detached-head flight](development/issues/ichor-head-flight-locations.md)
was an unconfirmed concern. Bounded original-game and recomp samples found no
out-of-bounds flight; no gameplay patch was justified. Exact random trajectories
and every attack path are not established as identical.

## Settings, controls and mods

- FPS mode, cap and VSync still require stopping/restarting the game.
  [Live switching](development/issues/live-frame-rate-settings.md) is queued.
  Fog strength applies live.
- Game > Settings > Change directory supports movable storage inside the game
  folder. Existing destination files take precedence when copying profiles;
  original files remain. Changing the data folder restarts the launcher and
  is unavailable during gameplay.
- Exit warp bypasses progression only for that explicit mod action. Ordinary
  doors retain native rules. Coverage of every exit remains finite.
- Give all weapons grants the current single-player character's inventory and
  ammo once; saving persists it. It is not unlimited ammunition.
- Modern Controls targets player 1 in single-player. Multiplayer uses Original
  Controller Mapping. Some native menu subpages require keyboard/controller
  navigation. SDL/DualSense rumble, gyro and adaptive triggers are not implemented.
- Camera collision retains native responses for unknown geometry. Broader
  scenery coverage and a complete swept-volume camera rewrite are not claimed.

## Platform and support

The prebuilt release targets Windows x64 and requires a compatible hardware GPU.
No compiler or WSL is required for ordinary ZIP installation. Source compilation
and released portable packages are separate support paths.

The maintainer's campaign completion used optional mods and an unlocked save;
it is not exhaustive unassisted play or original-console fidelity verification.
Support capture is local and best effort; nothing uploads automatically.
Provide the game/runtime version, control mode, location and reproduction steps
using the [playtesting guide](playtesting.md).

## Grounded drone bodies

Detached-body ownership and hidden-bone validation corrections pass focused checks and the latest owner visual review. The latest capture has no invalid-sample rejections or audio underruns; the exact seeded route and earlier cutscene groups remain unverified. See the [issue record](development/issues/dead-drone-camera-jitter.md). Not yet released.

- [SS Anubis ledge-testing stutter](development/issues/tawfret-lighting-preview-stutter.md):
  a short 60 FPS owner run records a several-second delivery slowdown, then
  recovery. The repeat capture has no gameplay presentation intervals over 25 ms
  after loading. Intermittent cause remains unlocalized; unrelated to #30 acceptance.

- [Modern controller high-drop camera reset](development/issues/controller-high-landing-camera-reset.md):
  separate from accepted ledge-climb correction; candidate passes the scoped
  source regression and the owner confirms the landing fix locally; unreleased.

- [Camera reset on window focus loss](development/issues/focus-loss-camera-reset.md):
  late input cleanup loses Modern view identity; candidate passes source regression
  for controller and mouse, with Original exclusion checked. Owner confirms
  fixed in all tested modes; unreleased.

Cutscene-skip preview follow-up: native A sprite draw corrected and styled SKIP label prepared; owner visual review and King Jeff invasion completion remain pending. See [the cutscene-skip record](development/issues/optional-cutscene-skipping.md).

Cutscene skip preview6 now has a candidate for the missing Goldwood forest prompt (native no-control scenery object48). The 25% smaller prompt uses a textured ring. Live verification remains pending; other unsupported scenes are still gated.

Cutscene skip: preview6 did not fix the reported forest sequence. Preview7 targets the captured A holds in the Magnus tutorial (scene199), completing its original399/group1 ->21 return. Health/ammo object classification was blocking eligibility. Candidate passed build and production-function/renderer checks; live verification remains pending.

SS Anubis flashback skip: preview8 candidate admits its native no-control glowing light while retaining movement/event checks. Original route and prompt alignment checks pass; live verification pending.

Owner live verification (2026-10-20): preview8 SS Anubis flashback skip and A-button/ring alignment both confirmed fixed. Owner is continuing the route. This confirms these two fixes only; other untested cutscenes remain open coverage. Not yet released.

Preview8 follow-up: owner cannot skip the Vela rescue cutscene (corrected "can" to "cant"); still playing. Exact scene, eligibility and completion cause under investigation. Preserve active session; no replacement until closed.

Owner confirmed preview8 SS Anubis flashback skip and A-button/ring alignment fixed on2026-10-20; other cutscenes remain under review, unreleased.

New preview8 reports: Vela rescue cannot skip; Juno SS Anubis fly-away cannot skip; brief white flicker on return from SS Anubis to character selection. Owner continues playing; inspect current capture, do not replace active package.

Cutscene skipping preview9 awaits live review of Juno departure. Vela rescue no-prompt and brief white flash after natural SS Anubis departure remain unresolved; targeted input/fade/presentation logging added.

Cutscene skip status, preview10: owner confirms Vela rescue now skips. Juno SS Anubis departure requires retest of revised door eligibility. The repeatable white flash returning to character selection remains under investigation; this preview records a short image window, which adds capture overhead during that transition.

The [character-selection rainbow/white flash](development/issues/character-selection-depth-flash.md) is fixed in the local candidate and owner-confirmed. Workload-aware depth/readback exclusion prevents encoded depth from becoming interpolated output. Vela rescue, Juno departure and Tawfret intro skipping are also owner-confirmed. These changes are not released yet.

A Modern-controller camera snap was reported again on focus return and after a room transition. The room-entry cause is delayed Modern-camera acquisition while input is blocked. The correction passes actual-source regression and owner verification with Modern controller and mouse/keyboard; unreleased. See [CAMERA-009](development/issues/focus-loss-camera-reset.md).

- **Vela rescue skip audio (unreleased):** owner confirms the chopped rumble is fixed. Intermediate skipped shots no longer start effects that would immediately be stopped; ordinary playback and music are preserved. See [native cutscene skipping](development/issues/optional-cutscene-skipping.md).

Minor launcher follow-up: [menu hover and dropdown routing](development/issues/launcher-menu-hover-stuck.md). The first hover candidate broke dropdown selection; the revised input routing passes native UI checks and is owner-confirmed fixed; unreleased.
