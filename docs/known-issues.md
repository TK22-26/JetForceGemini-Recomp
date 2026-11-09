# Known issues

Reviewed 2026-11-09. The published v1.4.0 bundle and the current `develop` source have different
validation status. A tested local candidate is not automatically released or accepted by its reporter.
Use the [issue index](development/issues/README.md) for full reproduction, attempts, causes and evidence;
[project status](status.md) and the [changelog](../CHANGELOG.md) describe delivered features.

## Open problems and verification still needed

| Problem | Current evidence and limit |
|---|---|
| [Private preview save identity](development/issues/preview-save-identity-newlines.md) | Closer-camera preview marker repaired after LF-to-CRLF staging conversion; shipped USA/PAL/JP storage checks pass, saves unchanged. Owner retry pending. |
| [Combat transparency / #52](development/issues/github-combat-player-transparency.md) | Resolved locally: owner approved the 180-unit closer-camera build after the preview marker repair. Regional/device coverage was not specified; unreleased. |
| [Stacked launcher notices](development/issues/launcher-notification-stack.md) | Local v35 stacks notices with independent animation and expiry; native UI checks pass. Owner visual acceptance remains pending. |
| [Regional ROM selector](development/issues/launcher-regional-rom-selection.md) | Local v34 has cartridge selection, remembered region and `--region`; native UI, CLI and restart checks pass. Physical-pointer owner review remains pending. |
| [Modern Aim release](development/issues/modern-aim-release-camera-snap.md) | v33 passes targeted native checks in all three versions and is owner-approved on PAL/controller. USA/JP manual testing remains pending; unreleased. |
| [Original FPS simulation parity](development/issues/original-mode-simulation-parity.md) | Ordinary Play uses a host-clock policy; Original output does not restore the N64 simulation clock. Matching motion states does not prove matching elapsed time. Open. |
| [Flying-enemy speed #48](development/issues/github-flying-enemy-speed.md) | Deferred for this version by the owner on November 8; removed from the current test queue, not marked fixed. The elapsed-VI candidate and its finite checks remain recorded; exact Original timing and broader qualification remain unresolved for future work. |
| [Intermittent mouse look #32](development/issues/github-mouse-look-and-inversion.md) | Four released-v1.4.0 captures distinguish zero accepted motion in failing sessions from working delivery. Develop fixes a reproduced hosted-window delivery gap; exact reporter trigger, current-build retest and inversion direction remain unverified. |
| [Stepwise audio delay #35](development/issues/audio-crackle-persistent-latency.md) | Develop host-queue recovery has component verification and owner regression-listening acceptance. New November 1 logs contain no audio queue/device timing; the trigger and affected-user current-build result remain unknown. RTSS crackling is separate. |
| [Audio recovery support export](development/issues/audio-recovery-support-export.md) | Fixed in develop commit 067f9a8 with bounded event grammar and actual ZIP regressions. Diagnostic transport is verified; this does not establish the remaining #35 audible-delay cause. |
| [Steam Deck / Proton #40](development/issues/github-steam-deck-proton-startup.md) | Fallback now presents menus in an owned popup while keeping the game visible. Windows/Proton integration checks pass; owner reports positive Bazzite UI results and later accepts the mouse behavior. Steam Deck reporter verification remains pending. |
| [ROM-button and search-field layout](development/issues/launcher-rom-and-search-layout.md) | Main/menu ROM IDs and styles separated; label alignment and search height corrected. Windows/Proton checks and scoped visual inspection pass; owner acceptance pending. |
| [Opening Invasion audio on Bazzite](development/issues/opening-invasion-audio-proton.md) | Owner reports audible glitch and awkward opening skip; saved Linux evidence and exact cause pending. |
| [About is not a separate window](development/issues/launcher-about-separate-window.md) | Dedicated native About window now passes Windows/Proton UI and process checks. Updated Windows and USB builds delivered; owner acceptance pending. |
| [About-window opening delay](development/issues/launcher-about-window-delay.md) | Controlled Windows/Proton opens do not reproduce the delay. Bounded timing logging delivered; owner capture, cause and remedy remain open. |
| [Windows 10 black screen #58](development/issues/github-black-screen-audio.md) | Cause unverified; requested/selected game API and bounded presentation diagnostics implemented and locally tested, with persisted Auto/D3D12/Vulkan selection and a validated standalone comparison. Affected Windows 10 retest pending. |
| [Menu icons and vignette #57](development/issues/github-menu-icon-vignette.md) | Current renderer checks and actual USA widescreen captures verify the local corrections. Owner visual acceptance and release remain pending; PAL/JP were not freshly captured. |
| [Cutscene skip completion #41](development/issues/cutscene-skip-completion-time.md) | Thousands of emulated ROM transfers cause the long opening skip. Checked native SDK completion improves local timings while retaining all nine scenes; USA/PAL/JP tests pass. Owner confirms the opening skip works on Proton; the supplied USA capture measures 1.828 seconds. Wider manual coverage remains unrecorded. |
| [Vulkan diagnostic frame readback](development/issues/vulkan-diagnostic-frame-readback.md) | Screenshot capture can crash in the pinned Vulkan image-copy path. Normal no-screenshot Proton Play passes; capture remains unfixed. |
| [Gems through vines](development/issues/vine-gem-occlusion.md) | A candidate adds depth for fully opaque foliage pixels while preserving holes/blending. Component, GPU replay and normal-game checks pass; owner batch review remains pending. Original-ROM EmuHawk also shows the overlap. |
| [Buried Goldwood drone](development/issues/drone-buried-after-hut-collision.md) | The captured actor is below the floor. The collision sequence and original-game parity remain unconfirmed. |
| [Intermittent ledge-route stutter](development/issues/tawfret-lighting-preview-stutter.md) | Captured once and not reproduced on repeated routes; cause remains unlocalized. |

Report [#38](development/issues/github-fet-bubb-crash.md) concerns another project's build and retains its recorded clarification status. The owner confirms [#54](development/issues/github-intel-launch-version-mismatch.md) is not this project's version and directs closure; no further clarification is required for #54.

## Accepted locally, not yet released

| Change | Acceptance and remaining limits |
|---|---|
| [Night vision and damage tint #51](development/issues/github-nightvision-damage-presentation.md) | Fixed locally; owner manually tested and approved USA, PAL and JP on November 8. Existing screen-effect remedy and fresh renderer regression pass; unreleased. |
| [Proton mouse confinement](development/issues/proton-mouse-confinement.md) | Owner manually confirms the current build is fully working on Bazzite on November 8. Prior failed capture is preserved; precise cause remains unconfirmed. No separate Steam Deck or regional acceptance inferred. |
| [Name-entry keyboard](development/issues/name-entry-key-animation-cadence.md), [backward body tilt](development/issues/pal-modern-backward-body-tilt.md), and [regional rescue blur](development/issues/vela-rescue-cutscene-stutter-resolution.md) | Owner confirms these three fixes in the v31 retest on November 3. The owner identifies the retest as PAL with a controller; separate US/JP visual qualification is not inferred. |
| [Audio settings window](development/issues/audio-settings-window-delay.md) | Owner confirms the replacement separate window opens immediately. The old approximately 20-second delay's cause remains unknown. Restart an existing launcher to use the new route. |
| [Enhanced Shadows / #46](development/issues/github-character-shadow-jitter.md) | Solved in develop; owner reaffirmed acceptance November 8. Video Settings offers updated/modern Enhanced shadows alongside Original. Focused combat/chief/cinematic checks pass; this is not an exhaustive campaign/performance claim. |
| [Shot effects](development/issues/high-refresh-shot-effects.md) and [actor camera motion](development/issues/camera-turn-actor-jumps.md) | Travelling tracers, grenade shockwaves/fire, opening sparkle and Vela ship-beam corrections have their recorded owner acceptance. Suspected muzzle-flash jitter remains unconfirmed. |
| [Flight camera / skybox cadence](development/issues/cutscene-camera-cadence.md) | Owner accepts two normal live repeats and confirms space-departure jumps are gone. One earlier isolated hitch remains unexplained; Original retains its policy. |
| [Vela skirt fade](development/issues/vela-skirt-focus-tearing.md) | Owner accepts the smooth-layer repair; native checks and replay pass. |
| [Floor reflections / #47](development/issues/floor-reflection-geometry.md) | Fixed in develop; owner reaffirmed acceptance November 8. Mirrored culling and separate reflected skeletal history correct geometry and motion; checks and replays pass. Release/reporter follow-up is separate from the accepted fix. |
| [Floyd objective pages / #49](development/issues/github-floyd-objectives-controls.md) | Fixed in develop; owner confirmed November 8. Configured Fire cycles the paused objective pages with Modern controls; native-handler and remapping checks pass. No additional device/region coverage inferred. |
| [Actor LOD](development/issues/actor-lod-option.md) | Owner verified live Original/High behavior in Video > Enhancements. Default remains Original. |

[Arcade traps / #50](development/issues/github-arcade-trap-controls.md) are fixed
locally and owner-approved after manual USA, PAL and JP testing on November 8.
The corrected original race module ID and fixed-camera input gates restore
Modern race actions. The earlier failed automated oil fixture remains in the
issue history; the change is included in the 1.5.0 source and remains unreleased.

The October 27 batch also contains controls/UI candidates for combat transparency,
free movement and menu/title presentation.
Their individual [issue records](development/issues/README.md) retain owner-review status.
[Batch portability validation](development/issues/local-batch-portability-validation.md) records the
unavailable pinned local WSL sanitizer boundary and the existing Linux quarantine.

## Original game and regional behavior

The owner reports a [texture wash over Goldwood's starting bridge](development/issues/goldwood-starting-bridge-texture-wash.md)
in native NTSC and requests that it be documented and preserved. Both screenshots
are retained; cause and capture setup are unspecified, and PAL/JP were not compared.
No fix is planned.

Leaving Walkway has **no music on the owner's NTSC N64** and **does have music in PAL EmuHawk**.
Only this departure was rechecked; the two Vela routes remain unverified. The US insertion candidate
has been removed from current source and rebuilt with scoped replay checks. Older preview packages
still contain the superseded insertion.
[Issue #45's record](development/issues/flight-transition-missing-music.md) retains that correction.
On November 8 the owner classified #45 as a native NTSC bug and deferred a different remedy to
a separate general native-bug-fixes update. It is outside the current manual-test queue; no new
fix or release is claimed. [N64-003](original-game/bugs.md#n64-003-missing-flight-transition-music-on-ntsc-45)
records the decision and the limited route evidence.
PAL hardware and Japanese behavior are untested; [PAL/JP recomp support](development/issues/regional-rom-support.md)
now uses one generation/runtime architecture and admits all three exact revisions for local
builds. Final native candidates pass fresh save/reload probes and bounded enhanced
Goldwood Play. The committed launcher passes actual import/setup/direct Play, clean
exit, save isolation and support exports for all three. Additional normal-Play
save creation/reload, checksum validation, exact-path write-failure recovery and
15-minute sessions pass. Sparse audio underrun counters in other runs remain
unexplained; the owner will report any audible problems during manual testing.
These observations do not block the handoff.
A separate public-default source-build test reaches its 8 GiB memory ceiling;
its complete compile/link qualification remains open. Campaign, feature, language,
hardware and release acceptance remain open;
published v1.4.0 packages support their pinned US ROM. The regional issue retains historical
failures, exact build identities and the current acceptance matrix.
[Named overlay owners](development/issues/regional-overlay-ownership.md) and
shared navigation bindings are implemented, with qualified record layouts and live
regional features still awaiting qualification.

The [native N64 catalog](original-game/README.md) distinguishes confirmed hardware bugs from emulator
observations and regional differences. Tawfret's camera-helper square is hardware-confirmed and was
intentionally corrected in v1.4.0; its separate camera-cut interpolation issue was recomp-specific.
[Enemy-clear door indicators](development/issues/door-enemy-lock-distance-darkening.md) also darken at
distance in EmuHawk; further original-game work is deferred and the accepted readability workaround remains.
[Ichor head flight](development/issues/ichor-head-flight-locations.md) was an unconfirmed concern and did
not justify a gameplay patch. These emulator observations are not new hardware-bug confirmations.

## Settings, controls and mods

- FPS, cap and VSync changes require stopping/restarting the game; [live switching](development/issues/live-frame-rate-settings.md)
  is future work. Fog percentage applies live. Unlimited/360+ Hz and every encounter are not exhaustively qualified.
- Modern controls support P1-P4, but some native menu subpages require keyboard/controller navigation.
  SDL/DualSense rumble, gyro and adaptive triggers are unimplemented. See [controls](features/pc-controls.md).
- Storage changes copy without overwriting destination files and restart the launcher; stop gameplay first.
  Keep the selected data directory and `storage-location.txt` with a portable installation.
- Exit warp deliberately bypasses progression for that mod action. Ordinary doors keep native requirements;
  every exit has not been qualified. Give weapons affects the current character once, not infinite ammo.
- Unlock Floyd takes effect in the next room and does not supply mission tokens. Save normally to retain
  inventory changes. Rapid duplicate grants and some command-error presentation remain documented UI limits.
- Motion blur offers Off / Reduced / Original, with Reduced the default. Some original cinematic shots are
  intentionally soft; native boss blur can be uncomfortable at high refresh rates.

## Released corrections and coverage

v1.4.0 includes the reviewed camera, roll, boss-aiming, Floyd, rain/reticle, cutscene, Mods and launcher
corrections recorded in its [qualification](releases/qualification-1.4.0.md). The Ally X reporter confirms
the originally reported bugs fixed and 120 FPS on their setup; that is not a universal performance guarantee.
Invasion slowdown also has reporter confirmation. A closed issue retains its finite verification scope;
weapon-crosshair shared cause and several reporter-specific retests remain distinct from owner acceptance.

The retained campaign run used testing mods and an unlocked-Tribals save. A separate full v1.4 SS Anubis
pass was not recorded as completed. No campaign-wide, every-device or zero-stall guarantee is claimed.
Historical private captures may have been retired under the October 28 storage cleanup; their written
findings and acceptance limits remain in the issue records, with the latest enemy-timing set excepted.

## Windows 10 setup

The prebuilt Windows x64 bundle needs no compiler or WSL. Old [source-setup workarounds](development/issues/github-windows-source-setup.md)
apply to developer builds. Linux source-build remedies are released, but a native Linux/AppImage release
is not qualified. Historical local WSL findings remain in [source validation](development/issues/release-source-validation.md);
required source/tagged-release CI later passed.

Support collection is local and best effort; nothing uploads automatically. Include version, control mode,
location and reproduction steps using the [reporting guide](playtesting.md).

FlashRAM has a shared-device candidate with passing sector, program-buffer,
bitwise-write and command-deadline tests. Final native integration, fresh slots
and separate reloads pass for each region in original-OS probes and normal
enhanced Play. Full-size checksum/padding menus and controlled failed atomic
replacement followed by an exact-path retry also pass on all three. Broader
campaign durability, power loss and hardware timing remain open; see the
[FlashRAM record](development/issues/flashram-device-contract.md).

### PAL presentation cadence (regional source candidate)

Exact VI intervals and the VI clock now reach shared history, world/blur
pairing and RT64 output scheduling, including PAL intervals such as three or
four VIs. Component tests and final native interpolation traces pass. Requested
output rate remains distinct from measured presentation performance; broader
regional motion, display and hardware acceptance remain open. See the
[regional implementation record](development/issues/regional-rom-support.md#five-hour-continuation--current-checkpoint).

### Windows automation containment

Guarded Windows work now requires unpackaged Python and uses suspended launch
before job assignment. Store Python allowed native compiler children to escape
the job despite Python itself being assigned. The 507 affected tests and actual
native compiler containment checks pass; earlier
receipts are not retroactive proof of child containment. See the
[containment issue](development/issues/windows-packaged-python-child-containment.md)
for current verification and compatibility limits.

### Modern Aim release camera transition

The owner reports that releasing Aim in Modern controls snaps the camera back
instead of sweeping into normal view. A shared source candidate preserves the
actual aimed position through the collision solver; focused components pass.
The compiler-memory blocker is corrected and all three v31 test runtimes now
contain this candidate. On November 3, the owner retested it and reported that
release remains instant. The ownership observer was attached to the normal-camera
path that ground Aim bypasses. The replacement observes the actual Aim camera
and passes two emitted-view returns in each region, plus PAL mouse/quick re-aim.
The owner rejected v32: a large initial step and stale collision recovery produce
a jagged scope-out. v33 addresses both and passes the final native checks in all three regions.
The owner approves PAL/controller. USA/JP manual testing remains pending.
The local v33 build is unreleased. Scope-in retains its native implementation.
See the [issue record](development/issues/modern-aim-release-camera-snap.md).

### Owner review dispositions, November 8

#53 and #55 are already owner-tested and approved optional Advanced control
options; no repeat acceptance is requested. The owner directs #54 be noted for
closure because the report concerns another project/version. GitHub closure
has not been performed. Current #57 verification and #58 evidence review are
recorded in their linked issue records.
