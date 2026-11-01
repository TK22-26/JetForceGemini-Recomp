# Known issues

Reviewed 2026-11-01. The published v1.4.0 bundle and the current `develop` source have different
validation status. A tested local candidate is not automatically released or accepted by its reporter.
Use the [issue index](development/issues/README.md) for full reproduction, attempts, causes and evidence;
[project status](status.md) and the [changelog](../CHANGELOG.md) describe delivered features.

## Open problems and verification still needed

| Problem | Current evidence and limit |
|---|---|
| [Original FPS simulation parity](development/issues/original-mode-simulation-parity.md) | Ordinary Play uses a host-clock policy; Original output does not restore the N64 simulation clock. Matching motion states does not prove matching elapsed time. Open. |
| [Flying-enemy speed #48](development/issues/github-flying-enemy-speed.md) | An elapsed-VI movement candidate passes portable checks and twelve native replays. Its stable three-VI reference does not reproduce every loaded N64 cadence; owner review and the Original timing policy remain open. |
| [Intermittent mouse look #32](development/issues/github-mouse-look-and-inversion.md) | A local candidate fixes reproduced raw-mouse delivery loss across the hosted process boundary. Two-process checks pass; reporter and inversion-Off retests remain pending. |
| [Stepwise audio delay #35](development/issues/audio-crackle-persistent-latency.md) | Unreleased host-queue recovery passes component, fault-recovery, sanitizer and native audio checks. Owner listening found no regression; the reporter's trigger is unknown and affected-user retest is pending. RTSS-related crackling is a separate report. |
| [Steam Deck / Proton #40](development/issues/github-steam-deck-proton-startup.md) | An unreleased HWND fallback corrects the invisible menu input shield. Windows and actual GE-Proton menu/input/pixel checks pass; Steam Deck hardware remains unverified. |
| [Windows 10 black screen #58](development/issues/github-black-screen-audio.md) | Cause requires reporter evidence. A local candidate adds bounded presentation diagnostics; its support ZIP has privacy and size checks. |
| [Cutscene skip completion #41](development/issues/cutscene-skip-completion-time.md) | Qualified outgoing fades are shorter in a tested local candidate; three native routes complete. Owner batch review remains pending. Unsupported scripts retain ordinary playback. |
| [Gems through vines](development/issues/vine-gem-occlusion.md) | A candidate adds depth for fully opaque foliage pixels while preserving holes/blending. Component, GPU replay and normal-game checks pass; owner batch review remains pending. Original-ROM EmuHawk also shows the overlap. |
| [Buried Goldwood drone](development/issues/drone-buried-after-hut-collision.md) | The captured actor is below the floor. The collision sequence and original-game parity remain unconfirmed. |
| [Intermittent ledge-route stutter](development/issues/tawfret-lighting-preview-stutter.md) | Captured once and not reproduced on repeated routes; cause remains unlocalized. |

Reports [#38](development/issues/github-fet-bubb-crash.md) and #54 identify another project's builds;
they require reporter clarification, not a claim that this port has fixed those symptoms.

## Accepted locally, not yet released

| Change | Acceptance and remaining limits |
|---|---|
| [Audio settings window](development/issues/audio-settings-window-delay.md) | Owner confirms the replacement separate window opens immediately. The old approximately 20-second delay's cause remains unknown. Restart an existing launcher to use the new route. |
| [Enhanced Shadows](development/issues/github-character-shadow-jitter.md) | Owner approved v26 visually; focused combat/chief/cinematic checks pass. Broader campaign/performance qualification remains pending. Original mode keeps native silhouettes. |
| [Shot effects](development/issues/high-refresh-shot-effects.md) and [actor camera motion](development/issues/camera-turn-actor-jumps.md) | Travelling tracers, grenade shockwaves/fire, opening sparkle and Vela ship-beam corrections have their recorded owner acceptance. Suspected muzzle-flash jitter remains unconfirmed. |
| [Flight camera / skybox cadence](development/issues/cutscene-camera-cadence.md) | Owner accepts two normal live repeats and confirms space-departure jumps are gone. One earlier isolated hitch remains unexplained; Original retains its policy. |
| [Vela skirt fade](development/issues/vela-skirt-focus-tearing.md) | Owner accepts the smooth-layer repair; native checks and replay pass. |
| [Floor reflections](development/issues/floor-reflection-geometry.md) | Mirrored culling and skeletal interpolation pass checks, replays and owner review; original reporter retest remains pending. |
| [Actor LOD](development/issues/actor-lod-option.md) | Owner verified live Original/High behavior in Video > Enhancements. Default remains Original. |

The October 27 batch also contains controls/UI candidates for Floyd objectives, arcade traps,
combat transparency, free movement, high-resolution screen effects and menu/title presentation.
Their individual [issue records](development/issues/README.md) retain owner-review status.
[Batch portability validation](development/issues/local-batch-portability-validation.md) records the
unavailable pinned local WSL sanitizer boundary and the existing Linux quarantine.

## Original game and regional behavior

Leaving Walkway has **no music on the owner's NTSC N64** and **does have music in PAL EmuHawk**.
Only this departure was rechecked; the two Vela routes remain unverified. The US insertion candidate
has been removed from current source and rebuilt with scoped replay checks. Older preview packages
still contain the superseded insertion.
[Issue #45's record](development/issues/flight-transition-missing-music.md) retains that correction.
PAL hardware and Japanese behavior are untested; [PAL/JP recomp support](development/issues/regional-rom-support.md)
now uses one generation/runtime architecture and admits all three exact revisions for local
builds. All three original-OS candidates create/reload saves, and later enhanced candidates pass
native builds and bounded Goldwood Play. The latest source is in final native/product
qualification. Campaign, feature, language, hardware and release acceptance remain open;
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
bitwise-write and command-deadline tests. Native integration and valid in-game
save/reload checks for each region remain open; see the
[FlashRAM record](development/issues/flashram-device-contract.md).

### PAL presentation cadence (regional source candidate)

The current shared history holds endpoints for PAL intervals that do not divide
50 Hz (for example, three VIs). Exact fractional duration still needs to reach
world/blur pairing and output scheduling. The 50/60 Hz clock correction does not
complete that enhancement. See the [regional implementation record](development/issues/regional-rom-support.md#remaining-pal-interpolation-duration-contract).
