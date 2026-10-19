# Known issues

Current status for 1.2.1 and the unreleased 1.3 development branch. The [issue register](development/issues/README.md)
contains causes, attempted remedies and evidence. Earlier candidate statuses are
preserved in the [historical notes](development/known-issues-before-1.2.0.md).

## High-refresh rendering and performance

The Vela rescue pairing correction restores 120/30 output in owner testing.
Bypassing blur makes all three shots clear; restoring normal effects brings
softness back. The owner conditionally accepts it if intended; original-effect
fidelity is still unverified. One transition briefly drops to about 50/20,
then recovers. This is not a zero-stall qualification.

[High-landing and ledge-climb mouse-camera resets](development/issues/mouse-camera-high-landing-reset.md)
are corrected in the local v1.3 candidate; component checks and owner live
confirmation cover both reported transitions.

The [Vela rescue cutscene](development/issues/vela-rescue-cutscene-stutter-resolution.md)
has confirmed update stalls and shot-specific interpolation loss in v1.2.0.
A private composite/staging-reuse candidate passed scoped image/state checks
and initial active-shot rescue cadence runs at 120/360 FPS. Later normal-Play
captures exposed isolated 50 ms / three-VI updates in Brig and rescue shots 344
and 380. These counterexamples block delivery; resource-wait attribution is in
progress. All measured rescue targets, including the capsule, remain 1280x960.
This does not resolve the reported soft appearance: original-phase fidelity,
presentation delay and owner visual acceptance remain open.

Owner testing reports no perceptible gameplay slowdown and resolution of the
reported shuriken reticle, resting-shuriken jitter and crouch-inversion problems.
Character seams, drone/gem flashing, bending bridges, audio sample delivery and
combat CPU/cache behavior have received tested corrections. This does not certify
every level, display or PC at 30 game updates or 360 presentations per second.

- [GitHub #19](development/issues/github-invasion-replay-stutter.md) reports severe invasion replay stuttering in v1.2.0 with Unlimited/VSync on an RTX 5090; reproduction and cause remain open.
- [Breakable glass before Vela shakes at high refresh](development/issues/high-refresh-glass-shaking.md): an intact-pane identity candidate compiles, but its visual effect remains unverified. The owner confirms prisoner glass is stable; these are separate surfaces.
- Unlimited pacing/audio and physical 360+ Hz display qualification remain limited.
- Ground-shadow cadence and broad late-object/camera coverage remain incomplete.
- The beta.1 owner pass confirms both reported ship cutscenes are smooth with
  clean audio. The draw-matching correction is still unreleased in stable 1.3;
  see the [cutscene investigation](development/issues/goldwood-exit-audio.md).
- The combined private candidate passes active opening-shot cadence at 120/360
  FPS. Startup/scene loading gaps and rendered presentation remain separate.
  The cutscene canvas follows the saved widescreen option in tests/native replay;
  owner visual review is pending. See [PERF-004 / DISPLAY-002](development/issues/opening-village-and-cutscene-aspect.md).
- The reported Original/VSync override was not reproduced after restarting; the owner confirms correct 30 FPS motion. The earlier unlogged result may have retained the previous mode. See [RENDER-013](development/issues/original-vsync-rate-selection.md).
- Original is the default rendering mode. F8 shows OUTPUT and SCENES separately;
  interpolation does not create extra simulation steps or guarantee monitor scanout.

See [performance](development/issues/goldwood-combat-slowdown.md),
[shadow cadence](development/issues/shadow-cadence.md),
[late objects](development/issues/tutorial-late-object-jitter.md) and
[diagnostic coverage](development/issues/frame-diagnostics.md).

## Controls and camera

[GH-018](development/issues/github-held-aim-and-diagonal-movement.md):
the owner relays the reporter's acknowledgement that firing no longer cancels
held aim in v1.2. The separate v1.3 standing-aim movement correction now matches
the EmuHawk Expert measurements in both component checks and captured gameplay:
4.0625 forward, 2.5 sideways and 4.77010548 diagonal units per native tick.
Observed runtime displacement differs by less than 0.00062 units/tick in the
qualified samples. This is scoped movement verification, not every state or
Original Normal-preset behavior.

[GitHub #20: Ichor boss controls](development/issues/github-ichor-boss-controls.md)
is corrected in 1.2.1. The native boss actor was mistaken for an input lock.
Unit/captured-state tests and native effective-input routes cover mouse,
controller and original mapping. The owner confirms controls in Vela/Ichor,
Juno and Lupus fights. Mizar and a full physical-device matrix were not tested.

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

[Ichor's detached-head flight locations](development/issues/ichor-head-flight-locations.md)
remain an **unconfirmed** owner concern. Scoped original-game/EmuHawk destination
and trajectory samples bound the captured port positions; no flight patch was
justified. Full trajectory/RNG correspondence and owner visual coverage remain
limited. This is not a confirmed pathfinding or arena-boundary defect.


[Exit warp](development/issues/map-exit-warp-transition.md) in 1.2.1 requests
the eligible native transition instead of stopping at the door. The 1.3 candidate
also bypasses progression requirements for the explicit mod command, as requested;
ordinary doors retain their native rules. Scoped transition and boss-entry checks
pass, but manual coverage of every launcher exit is incomplete.

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


The failed experimental GPU-blur change is excluded; cutscene/boss blur quality
and output pacing remain under investigation.

### Boss-controls verification (2026-10-18)

The owner confirms Vela/Ichor, Juno and Lupus controls in 1.2.1-beta.1; the focused stable 1.2.1 release is approved. This preview does not resolve [Vela cutscene stalls/resolution](development/issues/vela-rescue-cutscene-stutter-resolution.md). See [INPUT-011](development/issues/github-ichor-boss-controls.md).

The remaining session findings and ongoing general performance work are tracked for 1.3 in [issue #21](https://github.com/TK22-26/JetForceGemini-Recomp/issues/21). Controls acceptance does not close the blur, presentation or audio reports.
\n- 1.3 investigation: live-map geometry JSON preparation can add about 9 ms to a game update. An output-preserving formatting candidate is under qualification; command-file I/O remains separate. See [PERF-007](development/issues/live-map-export-hitch.md).\n
- [Enemy-clear door indicator darkens with distance](development/issues/door-enemy-lock-distance-darkening.md): owner reproduced the blackout in EmuHawk; native bug investigation deferred. Accepted opaque-indicator readability workaround retained, unreleased.

Vela cutscene follow-up (2026-10-18): owner N64 footage comparison confirms soft shots are present there too; normal-effect candidate tentatively accepted at 120/30. One brief Vela-to-first-cut dip and broader review remain.

- v1.3 owner control candidates: standing-aim forward/strafe components now
  match the recorded Expert baseline; high-land recovery retains the existing
  mouse camera while native actions stay locked. Component and live qualification
  are recorded in GH-018 and CAMERA-006; no release claim.


### 2026-10-18 owner follow-up
- Breakable glass still shook after the first identity-only candidate. The revised
  reflection-UV candidate passes component checks; owner verification remains open.
- The door indicator still darkened after state synchronization. A render-only
  detailed-model candidate and focused logging are prepared; cause is not confirmed.
- Mouse ledge-climb view retention joins the high-landing candidate; both require
  owner acceptance.
- Vela boss movement causes severe blur/discomfort despite mostly stable 120/30.
  A private native-composite bypass is prepared. The earlier capture lacks full
  effect recognition; the next preview records it. This does not change the
  previous owner observation that some rescue shots are soft on original N64.
See the [issue index](development/issues/README.md) for evidence and current status.

Owner follow-up: breakable glass also remains shaky with the reflection-UV candidate in Motion Clarity Review. Awaiting finalized focused capture; it is not fixed.


Current v1.3 owner preview: the breakable-glass overlay-address translation now has a passing production-translator regression and a rebuilt candidate, pending owner verification. The distant door indicator remains open after both earlier candidates were rejected. Reduced is the approved default for the planned Off / Reduced / Original blur control; that control is not implemented in this preview.


Owner follow-up: the glass overlay-address candidate fixes the reported shaking in the pre-Vela room. Component checks and owner live verification passed; unreleased. The dark door indicator and full three-mode blur setting remain open.


The three-mode blur control is implemented in the current private v1.3 preview, with Reduced as the default and a high-FPS Original comfort note. Component checks pass; Reduced strength and mode comparisons still await owner visual review. The dark door indicator remains open. Glass and ledge fixes retain prior owner acceptance.

- v1.3 owner review: Reduced blur appearance accepted. A separate [boss camera-sweep pop](development/issues/boss-camera-sweep-pop.md) remains open. [Door-indicator darkening](development/issues/door-enemy-lock-distance-darkening.md) also reproduces in EmuHawk; original-game bug, deferred at owner request with the accepted readability workaround retained.

Door Indicator Review: unlocked-indicator opaque draw candidate is built and component-tested, awaiting owner visual review. Boss camera-sweep pop remains open; targeted buffered logging is now included. Reduced blur appearance is owner-accepted and its actual alpha adjustment is confirmed in the completed capture (native100 to applied216, 3,130 command observations across two runs).

Owner confirmed the enemy-clear indicator remains green at the problematic distance in Door Indicator Review. The qualified unlocked-marker opaque draw remedy is unreleased; this does not claim a general transparent-material fix. The separate boss camera-sweep pop remains open.

Clarification: the door indicator remedy is an owner-observed visual workaround, not a resolved general rendering defect. It suppresses the unlocked marker distance fade. The underlying transparent-path blackout remains OPEN for diagnosis.

Boss camera sweep - current status: the owner confirms the boss now looks and feels good in Boss Camera Review. Component tests pass, and the complete owner audit confirms 140 boss source scenes keep interpolating where the old projected-motion check would reject them. This is an owner-verified local v1.3 correction, not a release or zero-hitch performance qualification; five isolated shared-camera fallback updates and timing outliers remain documented in [the issue record](development/issues/boss-camera-sweep-pop.md).

- GitHub [#24 portable storage](development/issues/portable-user-data.md): Game > Settings portability candidate passes local storage/window/restart qualification; owner review and v1.3 release pending.
- GitHub [#25 Ally X report](development/issues/github-ally-x-rendering.md): homing-missile/other weapon reticles and hut cutscene performance remain open. The owner verified Tawfret rain at 120 FPS and in its opening cutscene; the playable landing/maze are dry in the original room data. No rain patch was needed for that reproduction. Ask the reporter to recheck on v1.3; their hardware/build remains independently unverified.

- **v1.3 settings candidates:** directory-picker storage migration and Windows
  dark title bars pass isolated native checks; revised owner UI review is pending
  ([LAUNCHER-004](development/issues/portable-user-data.md),
  [LAUNCHER-005](development/issues/native-window-chrome.md)).
  The new tabbed Video Settings includes optional distance-fog removal; this
  visual enhancement still needs owner validation
  ([RENDER-017 / #26](development/issues/optional-fog-removal.md)).


### Current owner acceptance and v1.3 release target (2026-10-19)

- High-drop mouse-camera and ledge-climb resets are owner-confirmed fixed.
- Held-aim cancellation is acknowledged fixed in v1.2, as relayed by the owner.
- The owner cannot reproduce missing weapon reticles with mouse/Modern Controls;
  the hut scene is smooth and Tawfret gameplay/cutscene rain is visible.
  Ask the #25 reporter to recheck v1.3 and specify device/control mode.
- The owner is undertaking New Game through Vela's rescue on the combined build.
  Release acceptance prioritizes visibly smooth, responsive play and clean audio.
  The owner's latest clarification relaxes the earlier absolute zero-outlier
  requirement: isolated timing outliers alone do not automatically block release.
  Review their context and visible/audio/control effect; do not hide missed updates,
  recurring stalls, or data loss behind averages.
- Final route review and packaging remain pending. No release is approved by an
  unfinished run, and local acceptance does not establish every-device parity.
