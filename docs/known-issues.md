# Known issues

Current status for 1.2.0. The [issue register](development/issues/README.md)
contains causes, attempted remedies and evidence. Earlier candidate statuses are
preserved in the [historical notes](development/known-issues-before-1.2.0.md).

## High-refresh rendering and performance

Owner testing reports no perceptible gameplay slowdown and resolution of the
reported shuriken reticle, resting-shuriken jitter and crouch-inversion problems.
Character seams, drone/gem flashing, bending bridges, audio sample delivery and
combat CPU/cache behavior have received tested corrections. This does not certify
every level, display or PC at 30 game updates or 360 presentations per second.

- Unlimited pacing/audio and physical 360+ Hz display qualification remain limited.
- Ground-shadow cadence and broad late-object/camera coverage remain incomplete.
- The owner reported Goldwood exit-cutscene choppiness/audio interruptions. The
  earlier detailed trace capped before the exit, so it cannot clear that report.
- Original is the default rendering mode. F8 shows OUTPUT and SCENES separately;
  interpolation does not create extra simulation steps or guarantee monitor scanout.

See [performance](development/issues/goldwood-combat-slowdown.md),
[shadow cadence](development/issues/shadow-cadence.md),
[late objects](development/issues/tutorial-late-object-jitter.md) and
[diagnostic coverage](development/issues/frame-diagnostics.md).

## Controls and camera

Modern Controls is opt-in for player 1 in single-player. Original multiplayer uses
Controller Mapping. Compatible SDL controllers and Xbox/PlayStation layouts are
available; XInput rumble works, while native SDL/DualSense rumble, gyro and adaptive
triggers are not implemented. Some menu subpages still need keyboard/controller
navigation. Devices, weapons, characters and unusual states have finite coverage.

Controller vertical inversion is available in Modern Controls > Sensitivity &
behavior. The keyboard/mouse startup crash was reproduced in v1.1.0 and its early
game-memory initialization remedy is included. The [GitHub review](development/issues/github-release-readiness-20261016.md)
records exact verification scope and remaining reporter-machine checks.

Camera terrain/pond corrections retain native responses for unknown geometry;
this is not a complete swept-volume camera rewrite. See
[camera coverage](development/issues/camera-collision-bounce.md).

## Platform and setup

The release package is Windows x64. Linux native-source portability corrections
are included; this does not claim a packaged/tested Linux AppImage. Normal ZIP
installation imports your ROM and needs no compiler or WSL.

Legacy Windows source setup now diagnoses disabled firmware virtualization,
updates old WSL support and distinguishes installation failure from a requested
restart. Automated setup fixtures pass; a fresh Windows 10 reporter-machine
installation is still pending. See [setup](development/issues/github-windows-source-setup.md)
and [Linux build](development/issues/github-linux-native-build.md).

## Gameplay, tools and support

The maintainer confirms the campaign, original multiplayer and optional content
are playable. The retained completion run used optional infinite-health/enemy
auto-kill mods and an unlocked save; it is not an exhaustive unassisted hardware
test. Original-console accuracy remains under validation. Player-shadow checks
cover Juno; his water splash remains untested.

The optional navigation mod has not established autonomous campaign completion.
Lupus hover, moving platforms, crawling, combat gates and unsupported scripted
traversal still need manual play. Normal gameplay leaves the mod off.

Support capture is best effort and may be partial after forced termination or
early crashes. Nothing uploads automatically. Include the launcher/game version,
location and reproduction steps using the [playtesting guide](playtesting.md).
