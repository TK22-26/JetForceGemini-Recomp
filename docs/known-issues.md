# Known issues

See the [issue investigation register](development/issues/README.md) for evidence,
attempted remedies and verified resolutions.

Check this page before opening a report. It lists confirmed open limitations;
[GitHub issues](https://github.com/TK22-26/JetForceGemini-Recomp/issues)
hold the ongoing discussion, and fixed problems are recorded in the
[runtime fix log](development/boot-gameplay-fix.md).

## Critical: Goldwood combat slowdown

The owner's recorded drone fight drops to approximately 15 game updates per
second in its busiest section. This is an actual update-cadence deficit, separate
from the fixed modern camera-distance stepping. Detailed logging alone does not
explain it. A native clock replacement is under qualification and is not installed
in the delivered preview. See the [timing investigation](features/pc-controls.md#2026-10-11-critical-goldwood-timing-investigation)
for measurements, experiments and the remaining acceptance work.

## Character seams and lighting

The local high-refresh candidate corrects reproduced terrain cracks caused by
inconsistent interpolation of batches sharing a transform. Owner confirmation
and broader character coverage are pending. The Original-mode joint and incorrect
delayed lighting recovery reports remain open. A controlled return across the
bridge matches the reference's visible lighting pattern, but the intermittent
extra delay has not been isolated. Dense modern-route checks found no separating
shared thigh vertices in 215 observed body frames; the specific see-through
line still needs a marked current-build reproduction. This does not rule out
raster coverage or other poses. See
[RENDER-002](development/issues/character-seams-lighting.md).

## High-refresh rendering

The [high-refresh candidate](features/high-refresh-rendering.md) has RmlUi
Video Settings in a separate Windows window with VSync, a Custom FPS target and Unlimited. A short replay
exceeds 360 presentations/s while preserving guest state. Unlimited pacing remains
uneven, and its full replay took about 2% longer than Original. Sustained performance,
semantic object identity, animation/effects, CPU overlays, transitions, audio-device
behavior and physical 360+ Hz display qualification are incomplete. Original remains
the default. Video Settings positioning, dropdown text alignment, simplified chrome and continuous FPS preset borders are tested; owner confirmation remains pending. See [RENDER-001](development/issues/high-refresh-rendering.md).

## Windows 10 setup

**v1.1.0 uses a prebuilt game and one-time ROM import.** The WSL/developer-tool
setup problems below concern the old v1.0-and-earlier local-build installer or
source builds; ordinary v1.1.0 installation no longer requires those steps.

[Issue 4](https://github.com/TK22-26/JetForceGemini-Recomp/issues/4) reports
setup failures on Windows 10 with Windows PowerShell 5.1:

- Disabled firmware virtualization can cause repeated restart instructions.
- Older WSL installations may reject the requested Ubuntu distribution.
- Missing Linux packages can stop setup at the package check.
- Long RT64 dependency paths could fail checkout, and a retry could skip
  incomplete submodules.

Since 0.4.0-preview.2, setup uses short build and dependency cache paths,
enables Git long paths for dependency downloads, retries submodule
initialization and preserves native stderr and exit codes under PowerShell 5.1.
These changes have automated coverage, but the reporter's full Windows 10
sequence still needs a retest. Firmware-virtualization detection, older WSL
distributions and prerequisite probes such as `Test-LinuxPackages` remain open,
so repeated restarts alone will not fix every failure. If you are comfortable
installing prerequisites yourself, use [manual build setup](development/rom-bootstrap.md).

## Release and source versions

v1.1.0 ships a prebuilt game from its recorded source revision. Current source
and development builds can contain newer features, including the controls
overhaul and launcher update checker, which are not yet in that published ZIP.
Include your launcher version and game build when reporting. The new checker's
availability and validation are recorded in [LAUNCHER-001](development/issues/launcher-update-discovery.md).
[Getting started](getting-started.md) explains release and source-build setup.

## Controllers

The v1.1.0 release supports keyboard and Xbox/XInput controllers. The current
controls overhaul adds compatible SDL gamepad discovery and Xbox/PlayStation
layouts. XInput rumble is available; native SDL/DualSense rumble, gyro and
adaptive triggers are not implemented. Original local multiplayer is working
per maintainer confirmation; coverage of every device/adapter combination remains open.

[Experimental PC controls](features/pc-controls.md) are opt-in and
single-player only. Steep camera angles near scenery can hide part of the
player, pointer targets on pause subpages remain incomplete, and coverage across
weapons, characters and modes is incomplete. The start/save-selection screens and
main pause page have mouse targets in the current modern-controls preview.

## Gameplay and rendering coverage

The maintainer completed the campaign with optional infinite-health and enemy
auto-kill mods and a save with all Tribals unlocked; saving and loading are
verified. The maintainer confirms the full game, original multiplayer and
optional content are playable. The retained assisted run is not an exhaustive
unassisted or hardware-compatibility test; original-console accuracy remains under validation. Player-shadow processing
is verified for Juno only, and Juno's water splash is untested. Report a
specific failure with its location and steps using the [playtesting guide](playtesting.md).

## Support reports

Native crash stacks and freeze capture require a game built by 0.4.0-preview.2
or later. Capture is best effort: forced termination, early startup failures,
corrupted stacks or access restrictions can leave partial logs. Reports are
text stack snapshots, not memory dumps, and nothing uploads automatically.

## Navigation mod

The opt-in [navigation mod](features/navigation-mod.md) can walk, jump, open
chests, collect NPC rewards and cross exits, but autonomous campaign
completion is not established. Lupus hover, moving platforms, crawling,
shooting and explosive gates and unsupported scripted traversal still need
manual play. Normal gameplay leaves the mod off.


## Slowdown capture

The high-refresh preview has an F8 counter and asynchronous CSV logs. The revised
counter labels OUTPUT and SCENES separately and uses one cached texture draw.
Completed interpolation sequences no longer restart old motion, and ordinary
30/20-Hz source transitions retain valid interpolation. Muted 120/360 fixture
pacing improves with matching game progression and memory, but the owner's
reported stutter awaits live confirmation. Native timing restores 30-Hz scene
updates in the measured capped-play bridge. Unlimited can still reduce source
cadence; use Custom for this fix. Longer native startup testing records three
audio underruns, so broad audio continuity remains unverified. Schema 2 logs
successful present returns after pacing; heavy screenshots can introduce stalls.
A high output counter does not establish unique game poses or monitor scanout.
See [PERF-002](development/issues/frame-diagnostics.md) for remaining limits.
