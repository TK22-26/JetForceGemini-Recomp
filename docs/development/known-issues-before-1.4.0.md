# Historical notes before v1.4.0 final review

This preserves the earlier append-only investigation log. Entries may contradict
later owner acceptance. Use [current known issues](../known-issues.md) and the
[individual issue records](issues/README.md) for current status.

# Known issues

> 2026-10-21 owner disposition: **#31 cutscene skipping is approved and unreleased.** Earlier pending acceptance notes are superseded; scene/selector coverage limits remain documented in [ENHANCE-001](issues/optional-cutscene-skipping.md).

## Modern boss aiming range (#34)

The candidate restores the missing native weapon/reticle offset in Modern mouse
and controller aiming. All five boss fixtures, including both Mizar encounters
and upgraded Juno, match EmuHawk's horizontal/vertical limits. Original controls
regression checks pass. The owner approved the fix after live Twin Mantis review,
reporting that it matches the reference video. Broader live/scoped coverage remains
a documented validation limit. #34 stays open for delivery and reporter retest;
the correction is unreleased.
See [GH-034](issues/github-twin-mantis-aim-range.md).

## Mouse inversion default follow-up (2026-10-20)

Modern mouse defaults and reset now use inversion Off in tested local source.
Existing saved choices remain unchanged. This unreleased default correction
does not resolve [#32](issues/github-mouse-look-and-inversion.md)
intermittent mouse look or the report that Off is ineffective. Focused
runtime tests preserve explicit Off through live reload and restart, with
mouse/controller preferences independent. No general ignored-Off defect
was reproduced. The reporter supplied the requested failing support ZIP and
failing/working videos on 2026-10-21. Inspection identifies the official v1.3.0
runtime; the ZIP omits Modern mouse preferences and raw-motion diagnostics.
A focus/raw-delivery hypothesis remains unproved. Bounded mouse diagnostics now
pass native/export tests; a complete package and failing-session live capture
remain pending. No further input behavior correction is claimed.
The owner tested the isolated Mouse Inversion Preview and reports "looks good".
Ask the #32 reporter to retest the updated build when available; reporter
verification remains pending.

## Modern input preview follow-up (2026-10-20)

The new Modern Roll Direction Preview includes tested candidates for fully prone
roll direction, explicit Roll Left/Right bindings, and live P1-P4 assignment
indicators. The owner accepted all preview changes for develop; none is released.
Backward-crawl reversal and controller reassignment are owner-confirmed fixed.
See [GH-033](issues/github-modern-controls-side-roll.md) and
[INPUT-013](issues/controller-port-indicators-stale.md). This update
supersedes the earlier investigation statuses retained below.

Current v1.4.0 candidate status; v1.3.0 remains the published stable release.
The [issue register](issues/README.md) links detailed evidence.
Earlier investigation states are preserved in the
[pre-v1.3 notes](known-issues-before-1.3.0.md); they are historical,
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
reports resolved. See [performance follow-up](issues/1.2.1-session-1.3-followup.md).

## Reporter retests

- [#38: Fet-Bubb crash](issues/github-fet-bubb-crash.md):
  the attached dump exactly matches **VibinToast's v1.1.8**, a separate project,
  by debug identity and crash-site bytes. It does not establish a defect in this
  project's runtime. The immediate fault is an invalid squad-member read; its
  lifecycle cause and texture involvement remain unproved. Reporter clarification/
  routing is needed. This port's official v1.3.0 passed one isolated 6,000-VI
  comparison including 17.875 seconds in the fight, with health override and no
  4K pack; no universal compatibility, fix or closure is claimed here.
- [#39: Give all weapons has no effect](issues/github-give-all-weapons.md):
  reproduced on v1.3.0 when a request expires while the Mods dialog pauses
  gameplay. A candidate applies the grant safely while paused and reports its
  actual result; native, launcher and copied-save runtime checks passed.
  Owner confirms the actual button grant; reporter retest and release remain pending.
- [#40: Steam Deck Proton startup](issues/github-steam-deck-proton-startup.md):
  Windows v1.3.0 reportedly does not start through Proton. Failing stage, error,
  SteamOS/Proton versions and logs are missing. Proton compatibility is unqualified.
  Source review found a mandatory DirectComposition call unsupported in Valve
  Wine. A window-rendering fallback builds and passes normal/failure-injection UI
  checks on Windows; real Proton startup and gameplay remain unqualified. Native port work is deferred.
- [#32: intermittent mouse look and vertical inversion](issues/github-mouse-look-and-inversion.md):
  reported on v1.3.0, Windows 11, RTX 5070 Ti and mouse/keyboard. Buttons and menus
  work while camera/aim motion intermittently fails. Inversion reportedly stays
  active with Off selected, including after restart. The reporter withdrew the
  proposed focus-only cause. Neither symptom is reproduced or fixed locally;
  the accepted focus-loss camera reset is not proof of capture recovery here.
  The 2026-10-21 follow-up supplies a support ZIP and failing/working videos;
  the reporter describes capture and aim buttons working while mouse motion fails.
  Evidence has now been reviewed: official runtime confirmed, but Modern settings
  and raw-motion/focus telemetry are missing. A tested diagnostic candidate now
  retains the preceding minute, but package/live capture remain pending. No new
  inversion result or confirmed motion-loss cause.
- [#33: sideways roll in Modern Controls](issues/github-modern-controls-side-roll.md):
  Follow-up: backward-crawl and prone-roll direction corrections are owner-accepted.
  Explicit roll bindings and the automatic-roll preference are also accepted.
  The following original report and earlier preview status are historical:
  owner reproduces crawling instead of rolling and confirms Original Controls can
  roll. Reviewed Modern mappings omit native lateral actions; unchanged native
  checks confirm analog-to-crawl behavior and a separate simultaneous-entry
  limitation. Original manual/guide identify a shot-evading roll from crouch
  or crawl; Lupus is excluded. Owner selects movement-based rolling without a
  gentle sideways-crawl band for v1, and additionally reports sideways input
  currently produces forward crawling. A roll-only local candidate now passes
  focused native/input tests, an isolated Release build and deployed launcher startup checks;
  the isolated Modern Roll Preview awaits owner gameplay verification.
  The original report is v1.2.0; owner build is unspecified.
- [#25: Ally X cutscene, reticle and rain](issues/github-ally-x-rendering.md):
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
- [#35: growing audio delay](issues/audio-crackle-persistent-latency.md):
  #29 was closed by its reporter after attributing crackling to RTSS. Remaining
  latency is now #35: effects become delayed after several minutes and pause or
  launcher changes temporarily restore sync. The owner cannot reproduce it;
  affected-session evidence and detailed settings are needed. No latency fix is qualified.
- [#36: missing weapon crosshairs](issues/github-weapon-crosshairs.md):
  owner believes the existing accepted #25 reticle correction covers this report;
  treat as likely fixed locally, pending delivery and reporter confirmation.
  A new commenter reports explosives reticles
  disappearing above native FPS, sometimes flashing red for one frame, and
  returning at native FPS. Compare those settings and retest the accepted
  correction after delivery; shared cause and resolution remain unverified.
- [#37: Floyd cannot fire](issues/github-floyd-cannot-fire.md):
  fully owner-approved locally for v1.4.0, including the related Modern/Floyd
  changes. Ask the reporter to re-verify after delivery. Earlier local acceptance
  gates below are historical; no further local firing/mission gate is required.

- [#30: dual-stick ledge-camera reset](issues/controller-ledge-camera-reset.md):
  an unreleased candidate extends retained camera ownership to Modern controller
  ledge climbs. Source regression and native checks pass; owner confirms the ledge fix locally.
  The added water trigger is reproduced in the owner capture. A candidate retains
  Modern mouse/controller view through swimming. The first preview trapped the
  camera near Juno; preview 2 preserves native swimming collision positions and
  passes focused/recorded-point checks. Owner confirms the water camera works.
  The follow-up swimming-to-air/re-entry body-facing fix preserves native facing
  through the whole water-origin jump. Source and recorded-transition checks pass;
  the owner approved the combined preview after an isolated launcher retest.
  Reporter retest and release remain pending.
- [#31: cutscene skipping](issues/optional-cutscene-skipping.md):
  opening story skipping now passes owner review. A further candidate adds
  King Jeff invasion completion after an owner-reported partial skip, and a generated native blue-A button.
  Native/focused checks pass. Owner verified the SS Anubis flashback, Vela rescue,
  Juno departure and Tawfret intro. Broader cutscene coverage remains open;
  unsupported scripts retain normal playback.
- [#19: invasion replay stutter](issues/github-invasion-replay-stutter.md):
  the original reporter confirms the latest update resolves the problem and
  requests closure; another affected user also confirms improvement. GitHub
  remains open with an explicit closeout TODO. Exact independent severity/cause
  attribution remains limited; this does not resolve the separate Ally X report.
- [#18: targeting controls](issues/github-held-aim-and-diagonal-movement.md):
  the reporter confirms firing no longer cancels held aim in v1.2.0. The separate
  standing-aim diagonal-speed correction is included in v1.3.
- [#4: Windows source setup](issues/github-windows-source-setup.md)
  and [#15: Linux source build](issues/github-linux-native-build.md):
  prior source remedies are released, while reporter-platform qualification
  remains limited. A packaged Linux AppImage is not qualified.

## Unreleased visual and controller candidates

- [Tawfret sky brightness/fog](issues/tawfret-brightness-fog-fidelity.md):
  EmuHawk confirms the old gamma-off correction is intact. A signed fog-gradient
  candidate closely matches complete original graphics tasks at four views;
  owner approved the lighting/fog correction locally; unreleased.
- [Removed controllers moving to later players](issues/controller-remove-auto-reassignment.md):
  Follow-up: owner confirms the input-type replacement fix works; unreleased.
  persistent automatic-assignment exclusions pass core and real UI checks;
  owner approved the removal correction locally; unreleased.

## Original behavior and optional enhancements

[Enemy-clear door indicators](issues/door-enemy-lock-distance-darkening.md)
also darken at distance in EmuHawk. Further original-game investigation is
deferred by the owner; the accepted readability workaround remains in v1.3.
This is not evidence of a general transparent-material correction.

The original game deliberately softens some Vela-rescue shots and uses motion
blur in boss encounters. v1.3 offers Off, Reduced and Original blur, with Reduced
as default and a comfort note for Original at high frame rates. The owner
accepted Reduced and verified the original soft shots against N64 footage.

[Ichor detached-head flight](issues/ichor-head-flight-locations.md)
was an unconfirmed concern. Bounded original-game and recomp samples found no
out-of-bounds flight; no gameplay patch was justified. Exact random trajectories
and every attack path are not established as identical.

## Settings, controls and mods

- FPS mode, cap and VSync still require stopping/restarting the game.
  [Live switching](issues/live-frame-rate-settings.md) is queued.
  Fog strength applies live.
- Game > Settings > Change directory supports movable storage inside the game
  folder. Existing destination files take precedence when copying profiles;
  original files remain. Changing the data folder restarts the launcher and
  is unavailable during gameplay.
- Exit warp bypasses progression only for that explicit mod action. Ordinary
  doors retain native rules. Coverage of every exit remains finite.
- Give all weapons grants the current single-player character's inventory and
  ammo once; saving persists it. It is not unlimited ammunition.
  [#39 reports this grant failing on v1.3.0](issues/github-give-all-weapons.md);
  the paused-dialog delivery failure is reproduced and its candidate fix is owner-confirmed; release is pending.
- Modern Controls can be selected independently for P1-P4 in the v1.4 candidate.
  Original Controller Mapping remains available. Some native menu subpages require keyboard/controller
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
using the [playtesting guide](../playtesting.md).

## Grounded drone bodies

Detached-body ownership and hidden-bone validation corrections pass focused checks and the latest owner visual review. The latest capture has no invalid-sample rejections or audio underruns; the exact seeded route and earlier cutscene groups remain unverified. See the [issue record](issues/dead-drone-camera-jitter.md). Not yet released.

- [SS Anubis ledge-testing stutter](issues/tawfret-lighting-preview-stutter.md):
  a short 60 FPS owner run records a several-second delivery slowdown, then
  recovery. The repeat capture has no gameplay presentation intervals over 25 ms
  after loading. Intermittent cause remains unlocalized; unrelated to #30 acceptance.

- [Modern controller high-drop camera reset](issues/controller-high-landing-camera-reset.md):
  separate from accepted ledge-climb correction; candidate passes the scoped
  source regression and the owner confirms the landing fix locally; unreleased.

- [Camera reset on window focus loss](issues/focus-loss-camera-reset.md):
  late input cleanup loses Modern view identity; candidate passes source regression
  for controller and mouse, with Original exclusion checked. Owner confirms
  fixed in all tested modes; unreleased.

Cutscene-skip preview follow-up: native A sprite draw corrected and styled SKIP label prepared; owner visual review and King Jeff invasion completion remain pending. See [the cutscene-skip record](issues/optional-cutscene-skipping.md).

Cutscene skip preview6 now has a candidate for the missing Goldwood forest prompt (native no-control scenery object48). The 25% smaller prompt uses a textured ring. Live verification remains pending; other unsupported scenes are still gated.

Cutscene skip: preview6 did not fix the reported forest sequence. Preview7 targets the captured A holds in the Magnus tutorial (scene199), completing its original399/group1 ->21 return. Health/ammo object classification was blocking eligibility. Candidate passed build and production-function/renderer checks; live verification remains pending.

SS Anubis flashback skip: preview8 candidate admits its native no-control glowing light while retaining movement/event checks. Original route and prompt alignment checks pass; live verification pending.

Owner live verification (2026-10-20): preview8 SS Anubis flashback skip and A-button/ring alignment both confirmed fixed. Owner is continuing the route. This confirms these two fixes only; other untested cutscenes remain open coverage. Not yet released.

Preview8 follow-up: owner cannot skip the Vela rescue cutscene (corrected "can" to "cant"); still playing. Exact scene, eligibility and completion cause under investigation. Preserve active session; no replacement until closed.

Owner confirmed preview8 SS Anubis flashback skip and A-button/ring alignment fixed on2026-10-20; other cutscenes remain under review, unreleased.

New preview8 reports: Vela rescue cannot skip; Juno SS Anubis fly-away cannot skip; brief white flicker on return from SS Anubis to character selection. Owner continues playing; inspect current capture, do not replace active package.

Cutscene skipping preview9 awaits live review of Juno departure. Vela rescue no-prompt and brief white flash after natural SS Anubis departure remain unresolved; targeted input/fade/presentation logging added.

Cutscene skip status, preview10: owner confirms Vela rescue now skips. Juno SS Anubis departure requires retest of revised door eligibility. The repeatable white flash returning to character selection remains under investigation; this preview records a short image window, which adds capture overhead during that transition.

The [character-selection rainbow/white flash](issues/character-selection-depth-flash.md) is fixed in the local candidate and owner-confirmed. Workload-aware depth/readback exclusion prevents encoded depth from becoming interpolated output. Vela rescue, Juno departure and Tawfret intro skipping are also owner-confirmed. These changes are not released yet.

A Modern-controller camera snap was reported again on focus return and after a room transition. The room-entry cause is delayed Modern-camera acquisition while input is blocked. The correction passes actual-source regression and owner verification with Modern controller and mouse/keyboard; unreleased. See [CAMERA-009](issues/focus-loss-camera-reset.md).

- **Vela rescue skip audio (unreleased):** owner confirms the chopped rumble is fixed. Intermediate skipped shots no longer start effects that would immediately be stopped; ordinary playback and music are preserved. See [native cutscene skipping](issues/optional-cutscene-skipping.md).

Minor launcher follow-up: [menu hover and dropdown routing](issues/launcher-menu-hover-stuck.md). The first hover candidate broke dropdown selection; the revised input routing passes native UI checks and is owner-confirmed fixed; unreleased.

- [Player port indicators stay stale](issues/controller-port-indicators-stale.md): idle assignment refresh is owner-accepted in the Modern Roll Direction Preview; unreleased.

Private review tooling: [the cutscene selector process check](issues/cutscene-review-selector-loading.md)
rejected the normal native parent/child pair before issuing any request. The
corrected diagnostic UI passes focused checks and the owner confirms Load scene works.
Remaining scene/character combinations and skip completions are still unverified.

### Quarry day/night atmosphere ? verified in preview

The owner approved the corrected fog smoothing. A complete cycle capture covers
all 12 phases with 2,971 matching environment-fog commands and no colour-match
rejection. The native build and three component suites pass. This smooths the
original game's whole-distance fog steps while retaining cycle timing and colours.
The separate tribal brightness correction remains owner-verified. Both are
unreleased; the earlier strobing candidate is rejected and retained in the
[atmospheric transition record](issues/quarry-atmospheric-transitions.md).

### Cutscene review failures ? unreleased candidate

Owner retest reports scene207/0 stops progressing after skip,235 crashes after playback, and240/variant1 does not allow skipping. These remain open;235 being unused is unconfirmed. BigShip045 remains blocked from unsafe standalone selector entry. See [cutscene review findings](issues/optional-cutscene-skipping.md).

The same review also reports271/variant2 and275/variant1 do nothing. See the [current owner retest table](issues/cutscene-owner-retest-20261020.md); unused/context requirements remain unconfirmed.

Owner also reports308/variant1 and322/variant1 have no visible action, explicitly without freezing. Both remain open in the [current retest record](issues/cutscene-owner-retest-20261020.md).

Scene335/variant1 (Juno, current saved review entry) also still cannot be skipped. The older335/0 note is not cleared by this report; see the [retest record](issues/cutscene-owner-retest-20261020.md).


Cutscene final Juno retest: owner-confirmed checked entries remain passed even when their old notes describe failures. The11 unchecked entries after owner acceptance of405/2,376/0,207/0 and335/0 are tracked in [the current retest record](issues/cutscene-owner-retest-20261020.md). The owner passed batch2 scene376 actor qualification,207 review-save prerequisites and335 focus handoff. The earlier type50 audit used the wrong native dispatch-table index and is superseded by the corrected source audit. Scene207 reaches an original character-selection loop with no eligible character in the incomplete diagnostic save; only that copied review context receives missing character unlocks. The eleven remaining rows are now classified as likely development/setup variants. The original631-exit scan reaches the already-passed378/2,409/1 and410/1 instead of the unchecked variants. Empty scripts and missing departures explain the standalone limitations; universal unreachability is not proved, and the rows remain preserved rather than checked as passes. Selector persistence and explicit context feedback pass isolated checks. The four targeted owner retests are complete; the type 145 qualification audit corrected only an inaccurate source comment. No release or exhaustive campaign coverage is claimed.

## Modern mouse camera follow-up (2026-10-21)

Current disposition: the owner fully approved #37 and the associated Floyd work
for v1.4.0. Earlier preview-specific pending notes below are retained as history,
not outstanding local release gates. Reporter retest remains pending.


Modern M/K can abruptly pull the camera directly against Juno while looking around. The capture and447 production-helper cases confirm a mixed wall/height correction can collapse the distance to4 units. The correction is in preview4; all447 recorded points pass native scene checks in both execution paths. Owner confirms the camera fix. Broader scenery/performance coverage remains pending. See [report](issues/modern-mouse-camera-floyd-preview-report.md).

SS Anubis pad activation requires a Mizar token; the zero-token gate was explained and the owner subsequently entered the mission. Full mission validation remains pending; see [pad access](issues/give-floyd-mission-pad-access.md).

Owner reports Modern M/K Floyd mouse flight feels good in preview5. Preview6 adds A/D lateral flight alongside mouse steering, W thrust and S brake. Runtime, four suites and native velocity/position checks pass; live strafing, firing and mission completion remain pending. See [mission controls](issues/modern-floyd-mission-mouse-flight.md).


Local preview7 adds Modern controller Advanced settings > Invert Floyd flight steering (default On). Automated UI/profile and native steering checks pass; owner approved preview7 on 2026-10-21. Unreleased. See [flight inversion](issues/modern-floyd-controller-flight-inversion.md). Broader Floyd firing/mission completion remains pending.
