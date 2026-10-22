# Known issues

v1.4.0 includes the owner-reviewed fixes listed below. Reporter-specific retests
and unresolved reports remain open. Public issue replies require separate owner
approval. See the [release qualification](development/releases-1.4.0-qualification.md).

## Open reports and reporter retests

| Report | Current status |
|---|---|
| [#41: cutscene skip completion time](development/issues/cutscene-skip-completion-time.md) | Owner-requested optimization follow-up; affected scenes and delays need measurement. No speed improvement claimed. |
| [#25: Ally X rain, reticles and performance](development/issues/github-ally-x-rendering.md) | Rain/reticle presentation and room-entry rain delay are fixed and owner-approved locally. Reporter/Ally X retest is pending; the separate hut performance report is not resolved by those fixes. |
| [#30: ledge and water camera](development/issues/controller-ledge-camera-reset.md) | Controller ledges, high landings and swimming/re-entry corrections are owner-approved locally; reporter retest after delivery. |
| [#31: cutscene skipping](development/issues/optional-cutscene-skipping.md) | Owner-approved for v1.4.0. Unsupported scripts retain playback. Eleven likely development/setup entries remain documented as diagnostic coverage limits, not passed tests. |
| [#32: intermittent mouse look/inversion](development/issues/github-mouse-look-and-inversion.md) | Intermittent motion loss and reported ineffective inversion Off remain unconfirmed locally. New-profile/reset inversion now defaults Off; existing choices are preserved. Bounded support diagnostics collect evidence without claiming a behavior fix. |
| [#33: Modern side rolls](development/issues/github-modern-controls-side-roll.md) | Roll direction, backward crawling, explicit bindings and automatic-roll preference are owner-approved locally; reporter retest after delivery. |
| [#34: Twin Mantis aiming range](development/issues/github-twin-mantis-aim-range.md) | Native aiming range is restored; five boss fixtures match EmuHawk angle checks and owner Twin Mantis review passed. Broader live/scoped coverage remains finite. |
| [#35: growing audio delay](development/issues/audio-crackle-persistent-latency.md) | Owner cannot reproduce it. Affected-session evidence and settings are needed. #29 crackling was attributed to RTSS by its reporter; no latency fix is claimed. |
| [#36: missing weapon crosshairs](development/issues/github-weapon-crosshairs.md) | Likely covered by the accepted #25 reticle correction; shared cause and reporter resolution need verification after delivery. |
| [#37: Floyd cannot fire](development/issues/github-floyd-cannot-fire.md) | Fully approved locally, including related Modern/Floyd work. Ask the reporter to re-verify v1.4.0; no extra local firing/mission acceptance gate. |
| [#38: Fet-Bubb crash](development/issues/github-fet-bubb-crash.md) | The supplied dump matches VibinToast's v1.1.8, a different project. This port's bounded comparison did not reproduce it. Reporter clarification is needed; no general crash or texture-pack fix is claimed. |
| [#39: Give all weapons](development/issues/github-give-all-weapons.md) | Paused-dialog request expiry is fixed; actual grant acknowledgement and inventory availability are owner-confirmed. Reporter retest after delivery. |
| [#40: Steam Deck/Proton](development/issues/github-steam-deck-proton-startup.md) | Windows-tested window-rendering fallback added for unavailable DirectComposition. Actual Steam Deck startup, helper, gameplay and menus need reporter testing; native Linux port work is deferred. |

The original [#19 reporter](development/issues/github-invasion-replay-stutter.md)
confirms the invasion slowdown is resolved and requests closure. Public closeout
still awaits approval. [#18 targeting](development/issues/github-held-aim-and-diagonal-movement.md)
and the v1.3 movement correction remain included. Portable storage #24 and fog
controls #26 are already implemented; no new response is planned.

## Owner-approved v1.4 corrections

- [Focus and room-entry camera retention](development/issues/focus-loss-camera-reset.md)
  works in the reviewed controller and mouse modes.
- [High-drop controller recovery](development/issues/controller-high-landing-camera-reset.md)
  preserves the chosen angle, matching the mouse correction.
- [Mixed wall/height camera collision](development/issues/modern-mouse-camera-floyd-preview-report.md)
  no longer collapses the camera against Juno in the qualified cases.
- [Controller removal](development/issues/controller-remove-auto-reassignment.md)
  leaves the device unassigned; [port indicators](development/issues/controller-port-indicators-stale.md)
  refresh after saved assignment changes.
- [Tawfret lighting/fog](development/issues/tawfret-brightness-fog-fidelity.md)
  preserves the earlier gamma correction and matches the reviewed EmuHawk comparisons.
- [Quarry atmosphere](development/issues/quarry-atmospheric-transitions.md)
  smooths native fog-distance steps while preserving cycle timing/colours.
  Tribal brightness and the final smoothing candidate are owner-approved;
  the rejected strobing candidate is historical.
- [Character-selection white/rainbow flash](development/issues/character-selection-depth-flash.md),
  chopped Vela skip effects and [menu hover/dropdown routing](development/issues/launcher-menu-hover-stuck.md)
  are owner-confirmed fixed.
- [Mods presentation](development/issues/live-map-mods-layout.md) is owner-approved.
  Runtime acknowledgements determine weapon-grant success, not the button click.
- File verification now has [visible progress](development/issues/launcher-file-verification-feedback.md).
  Native UI tests cover both verification surfaces.

The [cutscene review record](development/issues/cutscene-owner-retest-20261020.md)
preserves failures, retests and the eleven remaining setup/debug classifications.
The private selector is not a release feature. Scene 207's missing-character
prerequisites are repaired only in the diagnostic copied-save path; ordinary
campaign progression is unchanged.

## Performance and coverage

The final v1.4 pass identified [rapid bad-angle camera motion and a floating square in the Tawfret chief cutscene](development/issues/tawfret-chief-camera-and-square.md). The camera-cut correction passed owner review at 120 FPS with logging off. The owner subsequently confirmed the square on original N64 hardware; native resolution had obscured the camera-helper mesh. The owner verified the helper visibility correction in the ordinary 120 FPS launcher: the square is gone and the scene looks correct. Both changes are prepared for v1.4.0, not yet released. See the [findings and lessons](development/tawfret-camera-helper-findings-2026-10-22.md).

The release target is visibly smooth, responsive play with clean audio.
The v1.3 owner route and targeted corpse review passed. The full v1.4 SS Anubis
pass is still pending. No campaign-wide, every-device or zero-stall guarantee
is claimed.

[SS Anubis ledge-testing stutter](development/issues/tawfret-lighting-preview-stutter.md)
was captured once and not reproduced in the repeated route; its intermittent
cause remains unlocalized. The earlier [Vela transition dip and broader performance coverage](development/issues/1.2.1-session-1.3-followup.md)
remain bounded findings. Unlimited/360+ Hz, every scenery collision and every
random encounter have not been exhaustively qualified.

[Grounded drone-body interpolation](development/issues/dead-drone-camera-jitter.md)
is included in v1.3 and passed the latest owner visual review. Exact seeded
route parity is not established.

## Original behavior and optional enhancements

[Enemy-clear door indicators](development/issues/door-enemy-lock-distance-darkening.md)
also darken at distance in EmuHawk. The owner deferred further original-game work;
the accepted readability workaround remains. This is not a general material fix.

Some Vela-rescue shots are intentionally soft, and native boss motion blur can
be uncomfortable at high refresh rates. Off / Reduced / Original remains
available, with Reduced the default and a comfort note for Original.
[Ichor detached-head flight](development/issues/ichor-head-flight-locations.md)
was an unconfirmed concern; bounded comparisons found no out-of-bounds flight
and did not justify a gameplay patch.

## Settings, controls and mods

- Frame rate, cap and VSync changes require stopping/restarting the game.
  [Live switching](development/issues/live-frame-rate-settings.md) is queued;
  fog percentage applies live.
- Modern controls can be selected independently for P1-P4. Some native menu
  subpages still require keyboard/controller navigation. SDL/DualSense rumble,
  gyro and adaptive triggers are not implemented.
- Game > Settings > Change directory copies data without overwriting existing
  destination files. Changing storage restarts the launcher and requires gameplay
  to be stopped. An internal data folder moves with the installation.
- Exit warp bypasses progression only for the explicit mod action. Ordinary
  doors retain native requirements; every exit has not been qualified.
- Give weapons affects the current single-player character once and refills
  existing ammo capacities. Save normally to retain it. It is not infinite ammo.
- Unlock Floyd takes effect in the next room. Mission entry still requires native
  prerequisites, including Mizar tokens. The earlier zero-token test was not a
  failed unlock.
- Rapid duplicate grant clicks before helper feedback and some command-file error
  presentation remain recorded [UI limitations](development/issues/github-give-all-weapons.md).

## Windows 10 setup

The prebuilt Windows x64 package needs no compiler or WSL. Older
[#4 source-setup](development/issues/github-windows-source-setup.md) workarounds
apply to developer builds, not ordinary ZIP installation.
[#15 Linux source-build](development/issues/github-linux-native-build.md)
remedies are recorded, but a native Linux/AppImage release is not qualified.

Developer qualification retains three pre-existing local WSL harness findings
(two sanitizer subtest failures and a tool-pin error); the Windows runtime and
launcher checks pass. See [source validation](development/issues/release-source-validation.md).
Full CI remains a publication gate.

Support collection is local and best effort; nothing uploads automatically.
Include version, control mode, location and reproduction steps using the
[reporting guide](playtesting.md).

Historical evidence remains in the [pre-v1.4 notes](development/known-issues-before-1.4.0.md),
[pre-v1.3 notes](development/known-issues-before-1.3.0.md) and
[issue register](development/issues/README.md).
