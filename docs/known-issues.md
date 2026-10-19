# Known issues

Current status for released v1.2.1 and the unreleased v1.3 candidate.
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

The v1.3 candidate includes the owner-accepted ship-cutscene improvements,
high-refresh glass correction, boss camera-sweep interpolation, Reduced blur,
high-drop/ledge camera retention, storage settings and live fog strength.
Native standing-aim movement matches the measured original Expert values
in the qualified owner capture. These changes are local and unreleased.

A brief Vela-to-first-cut transition dip was previously reported. Ground-shadow
cadence, broader scene/camera coverage and Unlimited/360+ Hz behavior retain
finite validation. Review the new combined route before claiming those
reports resolved. See [performance follow-up](development/issues/1.2.1-session-1.3-followup.md).

## Reporter retests

- [#25: Ally X cutscene, reticle and rain](development/issues/github-ally-x-rendering.md):
  the owner sees rain in the appropriate Tawfret rooms and opening cutscene,
  reports a smooth hut scene, and cannot reproduce missing weapon reticles using
  mouse/Modern Controls. Ask the reporter to retest v1.3 and identify device,
  Modern Controls versus Original Mapping, weapon and aim/fire bindings.
  Deliberately dry landing/maze rooms match the original data. No rain or reticle
  patch was justified by this owner reproduction.
- [#19: invasion replay stutter](development/issues/github-invasion-replay-stutter.md):
  related opening scenes improve in measured comparisons, but the exact reported
  King Jeff replay and reporter settings remain independently unverified.
- [#18: targeting controls](development/issues/github-held-aim-and-diagonal-movement.md):
  the reporter confirms firing no longer cancels held aim in v1.2.0. The separate
  standing-aim diagonal-speed correction is included locally for v1.3.
- [#4: Windows source setup](development/issues/github-windows-source-setup.md)
  and [#15: Linux source build](development/issues/github-linux-native-build.md):
  prior source remedies are released, while reporter-platform qualification
  remains limited. A packaged Linux AppImage is not qualified.

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
