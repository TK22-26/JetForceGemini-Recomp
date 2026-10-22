# Issue investigations and resolutions

Keep an issue record from the first reproducible report through its final verified
resolution. This is the persistent engineering history for bugs, regressions and
significant limitations. It complements [known issues](../../known-issues.md), the
[runtime fix log](../boot-gameplay-fix.md), and feature implementation notes; link
those sources rather than copying conflicting accounts.

## Recording policy

- Start or update a record while investigating, not only after success. Use the
  [template](template.md). Give the issue a stable descriptive filename and ID.
- Record symptoms and reproduction, affected version/profile/platform, severity,
  evidence provenance, observed facts, hypotheses, attempts and their results.
- Retain failed or inconclusive attempts when they explain a decision. Correct
  invalid evidence explicitly; do not silently promote a hypothesis to a cause.
- Record the actual final code/behavior change, why it fixes the demonstrated
  cause, regression checks, remaining gaps, and where it is available. A patch,
  successful build, or completed replay alone is not a verified resolution.
- Separate **reported**, **reproduced**, **candidate**, **verified in tests**,
  **awaiting live verification**, and **resolved/released**. State the specific
  scope of a pass. Record a commit/release only once one actually exists.
- Keep public records free of ROMs, generated game code, personal save data and
  identifying machine paths. Reference private artifact IDs and hashes as needed.
- Preserve useful findings from older feature/fix logs through links. Historical
  tests apply to their recorded build, not automatically to the current tree.

This practice applies to future work throughout the repository, including
launcher/UI, controls, runtime, rendering, audio, setup and tooling. Documentation
does not authorize reopening an exhausted investigation or reset guard budgets.

## Active and historical issue index

The historical rows below index existing evidence; they do not claim a new retest.
Detailed per-issue records are added as those issues receive further work.

| ID | Issue | Current recorded status | Investigation / resolution |
|---|---|---|---|
| BUILD-V14 | Clean CI: GCC rain initializer and RT64 checkout line endings | Build corrections applied; CI rerun pending | [Report](v14-clean-ci-portability.md) |
| RENDER-CHIEF | Tawfret chief cutscene camera motion and floating square | Both corrections owner-verified; original N64 helper artifact removed; unreleased | [Report](tawfret-chief-camera-and-square.md) |
| GH-041 | Cutscene skip completion time (#41) | Owner requests faster completion for some scenes; measurement and optimization pending | [Follow-up](cutscene-skip-completion-time.md) |
| UI-009 | Live map Mods redesign disabled/focus states | Owner-approved 2026-10-21; visible badges and reference padlock accepted locally; 973 native checks pass; unreleased | [Review](live-map-mods-layout.md) |
| GH-040 | Windows release fails to start through Steam Deck Proton (#40) | Mandatory DirectComposition conflicts with Valve Wine; HWND candidate built; normal/failure-injection UI checks passed. Proton/Deck validation pending; native port deferred | [Report](github-steam-deck-proton-startup.md) |
| GH-039 | Give all weapons leaves inventory unchanged (#39) | Reproduced: paused Mods dialog expires requests. Candidate processes grants while paused and confirms application; native/runtime/launcher checks passed and owner confirms actual UI grant; reporter retest/release pending | [Report](github-give-all-weapons.md) |
| GH-038 | Fet-Bubb crashes shortly after attacking (#38) | Dump exactly matches VibinToast v1.1.8, a different project; our v1.3.0 passes bounded boss comparison; local defect unestablished, reporter routing/clarification needed | [Report](github-fet-bubb-crash.md) |
| GH-037 | Floyd cannot fire (#37) | Fully approved locally by owner for v1.4.0; reporter re-verification after delivery pending | [Report](github-floyd-cannot-fire.md) |
| GH-036 | Missing weapon crosshairs (#36) | Owner believes existing accepted reticle correction covers it; likely fixed locally, delivery/reporter confirmation pending | [Report](github-weapon-crosshairs.md) |
| GH-034 | Modern boss aim range, including both Mizar fights (#34) | Owner-approved after live Twin Mantis review; five boss fixtures match EmuHawk in both Modern paths; unreleased; reporter retest after delivery | [Report](github-twin-mantis-aim-range.md) |
| DIAG-003 | Cutscene selector rejects a running game | Normal native parent/child pair miscounted as two games; corrected detection owner-confirmed; character ID swap corrected awaiting review; room45 direct-entry crash and stale-request startup open | [Report](cutscene-review-selector-loading.md) |
| UI-008 | Launcher menu hover remains highlighted over game | Initial hover fix regressed dropdown selection; corrected routing passes 55 menu and 790 controls checks; owner confirms fixed; unreleased | [Report](launcher-menu-hover-stuck.md) |
| GH-032 | Intermittent mouse look and ineffective vertical inversion (#32) | Official v1.3.0 verified; cause unproved; bounded mouse diagnostics implemented and tested, package/live capture pending; default/reset-Off separately accepted, unreleased | [Report and review](github-mouse-look-and-inversion.md) |
| GH-033 | Modern Controls missing sideways roll (#33) | Roll bindings, automatic-roll setting, prone direction and backward-crawl fixes owner-accepted; unreleased | [Cause, evidence and selected policy](github-modern-controls-side-roll.md) |
| PERF-005 | SS Anubis ledge-testing stutter in Lighting Preview | Earlier gaps measured; repeat Anubis capture steady, intermittent cause open | [Report](tawfret-lighting-preview-stutter.md) |
| RENDER-019 | Tawfret brightness and distant haze differ from N64 | Fog candidate checked against original tasks; owner approved locally; unreleased | [Report](tawfret-brightness-fog-fidelity.md) |
| INPUT-012 | Removing a controller moves it to another player | Explicit Remove and input-type replacement fixes owner-confirmed; unreleased | [Report](controller-remove-auto-reassignment.md) |
| INPUT-013 | Player port indicators stay stale | Idle assignment indicator refresh owner-accepted; unreleased | [Report](controller-port-indicators-stale.md) |
| AUDIO-004 | Persistent audio delay (#35); earlier #29 closed | Reporter attributes #29 crackling to RTSS; #35 latency not reproduced by owner, affected-session evidence needed | [Report](audio-crackle-persistent-latency.md) |
| CAMERA-009 | Focus-loss camera reset | Room-entry/focus-return correction passes actual-source tests and owner review with Modern controller and mouse/keyboard; unreleased | [Report](focus-loss-camera-reset.md) |
| CAMERA-008 | Modern controller high-drop camera reset | Owner confirmed locally; 486 scoped assertions and native checks pass; unreleased | [Report](controller-high-landing-camera-reset.md) |
| CAMERA-007 | Modern ledge/water camera reset and water-air facing (#30) | Ledge/water camera and water-air body-facing fix owner-approved after isolated retest; unreleased, reporter retest pending | [Report](controller-ledge-camera-reset.md) |
| ENHANCE-001 | Optional cutscene skipping (#31) | Owner-approved 2026-10-21; final four targeted Juno retests pass; eleven debug/context entries retain documented coverage limits; unreleased | [Scope](optional-cutscene-skipping.md) |
| RENDER-018 | Dead drone bodies jitter with camera movement | Included in v1.3; owner visual pass and capture validation, exact seed/cutscene coverage unverified | [Investigation and validation](dead-drone-camera-jitter.md) |
| NATIVE-003 | Ichor detached-head flight locations after body destruction | EmuHawk plus idle/moving Vela comparison: no sampled out-of-bounds flight; broader parity unconfirmed | [Report and comparison plan](ichor-head-flight-locations.md) |
| MOD-001 | Exit warp stops at the door | Native contact fix in 1.2.1; 1.3 progression bypass and exact overlapping-exit handoff pass focused/native checks | [Report and source review](map-exit-warp-transition.md) |
| RENDER-012 | Breakable glass before Vela shakes at high refresh | Included in v1.3: production overlay translation, component checks and owner live verification passed | [Report](high-refresh-glass-shaking.md) |
| RENDER-015 | Boss motion blur causes discomfort despite 120/30 | Included in v1.3; Off/Reduced owner-accepted and three-mode preference component-tested | [Report](boss-motion-blur-discomfort.md) |
| RENDER-016 | GitHub #25 Ally X cutscenes, homing reticle and rain | Timestamp and spatial rain-delay fixes owner-confirmed locally; unreleased; reporter/Ally X retest and hut performance open | [Report](github-ally-x-rendering.md) |
| RENDER-014 | Enemy-clear door indicator darkens with distance | ORIGINAL-GAME BUG confirmed in EmuHawk; further investigation deferred by owner; accepted visibility workaround included in v1.3 | [Report](door-enemy-lock-distance-darkening.md) |
| RENDER-013 | Original appears to follow VSync/display refresh | Not reproduced after restart; owner confirms 30 FPS motion, earlier session unlogged | [Investigation](original-vsync-rate-selection.md) |
| RENDER-011 | Vela rescue cutscene stalls / appears low resolution | Tentatively accepted by owner at 120/30 after N64 footage confirms soft shots; brief Vela-to-first-cut dip and broader review remain | [Report and evidence](vela-rescue-cutscene-stutter-resolution.md) |
| INPUT-011 | GitHub #20 Ichor boss-room controls stop responding | Released in v1.2.1; owner confirms three bosses; reporter retest pending | [Cause and verification](github-ichor-boss-controls.md) |
| BUILD-003 | Release source policy and compiler portability | v1.4 Windows candidate checks pass; clean-history/package verification pending; existing WSL harness limitation retained | [Release validation](release-source-validation.md) |
| NATIVE-002 | GitHub #14 mouse-look startup access violation | Reproduced startup cause resolved in v1.2.0; current enabled startup passes | [Startup report](github-mouse-look-startup.md) |
| BUILD-002 | GitHub #15 GCC native build failure | Portable source released in v1.2.0; actual GCC source verified, AppImage not qualified | [Linux build review](github-linux-native-build.md) |
| INPUT-010 | GitHub #13 controller camera inversion | GUI toggle released in v1.2.0; persistence/deltas verified, reporter retest pending | [Controls review](github-controller-vertical-inversion.md) |
| SETUP-001 | GitHub #4 Windows 10 source setup | Fixes released in v1.2.0; 28 checks pass, fresh Windows 10 retest pending | [Setup review](github-windows-source-setup.md) |
| GH-018 | Held aim cancels on firing; diagonal movement differs while aiming | Owner relays reporter acknowledgement: held aim fixed in v1.2. Standing-aim correction included in v1.3 and matches native measurements; reporter retest pending | [Investigation](github-held-aim-and-diagonal-movement.md), [handoff](../issue18-native-controls-handoff-2026-10-17.md) |
| DISPLAY-001 | Widescreen viewport and pointer alignment | Verified in tests; preview installed, live check pending | [Investigation](widescreen-pointer-and-airborne-aim.md) |
| INPUT-008 | Menu bindings save but are hidden; retained mouse preference | Unified Keys, no arrows and shared E verified and delivered locally; owner check pending | [Profile/default review](modern-capture-profile-defaults.md) |
| RENDER-008 | Shuriken reticle flickers and disappears | Released in v1.2.0 after tests and owner live acceptance | [Report and investigation](shuriken-reticle-flicker.md) |
| INPUT-009 | Mouse pitch reverses while crouching | Released in v1.2.0 after tests and owner live acceptance | [Investigation](crouch-mouse-inversion.md) |
| RENDER-009 | Ground shurikens jitter | Released in v1.2.0 after tests and owner live acceptance | [Investigation](ground-shuriken-jitter.md) |
| INPUT-007 | Keep aiming active throughout modern jumps | Verified in tests; preview installed, live check pending | [Investigation](widescreen-pointer-and-airborne-aim.md) |
| LAUNCHER-001 | No launcher update discovery; stale release description | Released in v1.2.0; owner-approved layout, UI and live updater verified | [Cause, implementation and checks](launcher-update-discovery.md) |
| RENDER-001 | Smooth 60-360+ FPS presentation | Presentation pacing and FPS preset corrections tested; owner visual confirmation pending | [Evidence and plan](high-refresh-rendering.md) |
| RENDER-002 | Juno joint/terrain seams and incorrect dark lighting | Owner reports thigh gaps and delayed lighting absent at 120 FPS in semantic preview; broader coverage remains | [Report and evidence](character-seams-lighting.md) |
| RENDER-003 | Jitter despite steady 120 OUTPUT / 30 SCENES | Bounded holds corrected; finite-clock/shadow-scene queue cause captured; private ownership candidate and live verification pending | [Report and investigation](steady-fps-jitter.md) |
| RENDER-004 | Gems/enemies shake or flash; level culls at camera edge | Owner confirms gems/drones good; pickup particles and combat cadence remain open | [Report and investigation](actor-jitter-edge-culling.md) |
| RENDER-005 | Pickup particles desynchronize from gems | Lifetime/shape correction tested and delivered locally; owner live confirmation pending | [Report and investigation](pickup-particle-desync.md) |
| RENDER-006 | Late tutorial crates, exit light and bridge jitter | Deforming bridge correction delivered locally after tests; original physics correct; owner visual and broader object acceptance pending | [Live capture review](tutorial-late-object-jitter.md) |
| RENDER-007 | Ground shadow appears less smooth than Juno | Clipped receiver/mask gap investigated; no qualified shadow fix | [Shadow cadence](shadow-cadence.md) |
| PERF-007 | Live-map JSON preparation stalls gameplay | Included in v1.3; faster serialization/background reads verified in scoped normal Play | [Cause and checks](live-map-export-hitch.md) |
| PERF-006 | Synchronous controller settings polling stalls input/game update | Included in v1.3; background snapshot reader verified in focused and normal Play checks | [Cause and limits](controller-settings-io-hitch.md) |
| PERF-003 | Late renderer cache-key hitch | Stable keys and empty-cache fast path delivered after tests/native replays; live acceptance pending | [Cause and checks](renderer-cache-key-instability.md) |
| PERF-001 | Goldwood drone-combat update slowdown | Native ROM loading improvement delivered; tested combat holds two-VI updates; later renderer/load gaps and owner acceptance remain open | [Evidence and attempts](goldwood-combat-slowdown.md) |
| PERF-002 | Frame diagnostics and attribution | Long-capture coverage and screenshot-induced hitches corrected and delivered locally; new route verification pending | [Evidence and limits](frame-diagnostics.md) |
| AUTO-002 | Parallel admission reaches shared attempt ceiling before peer finishes | Original safe stop retained; renewed private admission headroom passes four completion-order fixtures | [Cause and stop evidence](parallel-investigation-admission.md) |
| AUTO-001 | Pending request withdrawal aborts a worker | Cached withdrawals survive live recovery; successor resume handling passes isolated corruption/cancellation fixtures | [Cause and recovery](high-refresh-queue-cancellation.md) |
| NATIVE-001 | Access violation during extended native Play replay | Fresh overlay reset fixes captured stale path-cache write; targeted return/native respawn tests pass; local preview installed, live verification pending | [Crash evidence](native-play-access-violation.md) |
| BUILD-001 | Restored source and stale generated renderer disagree | Coherent rebuild qualified in exact-state replay with sane renderer rates; desktop baseline unaffected | [Cause and safeguards](stale-generated-renderer.md) |
| STORAGE-001 | Historical diagnostics fill the working volume | Local recovery; retention policy open | [Cause and verified archive](diagnostic-storage-exhaustion.md) |
| PERF-005 | GitHub #19 invasion replay at 1-2 FPS | Original reporter confirms resolved and requests closure; explicit closeout TODO; GitHub still open | [Report and comparisons](github-invasion-replay-stutter.md) |
| PERF-004 / DISPLAY-002 | Opening village cadence / cutscenes ignore 4:3 option | Combined private candidate passes active-shot cadence at 120/360; aspect checks pass; loading, presentation and live review remain separate | [Evidence and progress](opening-village-and-cutscene-aspect.md) |
| AUDIO-003 | Ship-cutscene stutter and Goldwood exit audio | Included in v1.3; both ship scenes owner-accepted and final route has zero audio underruns | [Exit investigation](goldwood-exit-audio.md) |
| AUDIO-002 | Frequent audio interruptions during walking/combat | Native playback remedy delivered; final default replays clean; one long-stall control underrun and owner listening check remain open | [Report and investigation](walking-audio-interruptions.md) |
| AUDIO-001 | Intermittent background-music crackle | Verified in tests and owner live verification; local preview only | [Investigation](intermittent-music-crackle.md) |
| DIAG-002 | Reference owner capture inherited debug gameplay overrides and classic controls | Setup defect confirmed; correction prepared; further reference testing stopped at owner request | [Audit and correction](reference-owner-capture-contamination.md) |
| DIAG-001 | Bounded replay misses final image capture | Verified in hidden replays; unchanged final reference RAM | [Cause and verification](final-probe-frame-capture.md) |
| CAMERA-006 | Mouse camera resets after landing or ledge climb | Fixed in local candidate; component checks and owner confirmation cover high-drop landing and ledge climb; unreleased | [Report](mouse-camera-high-landing-reset.md) |
| CAMERA-005 | Modern camera jumps upward over terrain / apparent pond-lip contact | Actual pond regression reproduced and corrected in tests; revised preview installed, owner live check pending | [Report and investigation](camera-collision-bounce.md) |
| CAMERA-003 | Modern area entry faces the exit | Verified in focused tests and owner live play; local preview | [Reproduction and work](modern-controller-state-transitions.md) |
| MOVE-003 | Dual-stick jump loses direction and air steering | Verified in focused tests and owner live play; local preview | [Reproduction and work](modern-controller-state-transitions.md) |
| CAMERA-004 | Focus loss lowers camera angle | Verified in focused tests and owner live play; local preview | [Reproduction and work](modern-controller-state-transitions.md) |
| CAMERA-001 | Small repeated forward camera steps | Verified in isolated replay; delivered preview, live verification pending | [Fixed modern camera boom](../../features/pc-controls.md#2026-10-11-goldwood-capture-camera-stepping-and-native-pause-save) |
| CAMERA-002 | Large scenery-driven camera pull-ins | Open; targeted response correction in CAMERA-005, broader scenery coverage pending | [Capture findings](../../features/pc-controls.md#2026-10-11-goldwood-capture-camera-stepping-and-native-pause-save), [candidate and limits](camera-collision-bounce.md) |
| INPUT-001 | Main-menu clicks eaten; resize cursor remains in client | Corrected and regression-tested; physical focus verification remains | [Win32 activation/cursor cause and fix](../../features/pc-controls.md#live-menu-click-and-cursor-correction-2026-10-10) |
| INPUT-002 | Hover traverses intermediate save slots | Corrected with semantic native selection; tested | [Pointer audit](../../features/pc-controls.md#modern-shoulder-camera-and-mouse-audit-2026-10-10) |
| INPUT-003 | Fire drops mouse aim; aim entry snaps view | Corrected and tested; broader live coverage remains | [Capture ownership and camera handoff](../../features/pc-controls.md#modern-shoulder-camera-and-mouse-audit-2026-10-10) |
| INPUT-004 | Missing pause mouse targets / modern Save | Submenu navigation, contextual Back and sounds verified in tests; live check pending | [Current report and investigation](modern-pause-navigation.md) |
| INPUT-006 | Modern aiming prevents jumping | Native jump-from-aim verified for all characters; live check pending | [Investigation](modern-pause-navigation.md) |
| LAUNCHER-004 | GitHub #24 portable user data | Released in v1.3; owner accepted, user confirms working; GitHub closed | [Report](portable-user-data.md) |
| LAUNCHER-005 | Native windows use light title bars unlike Scooby | Included in v1.3; native caption checks pass and owner accepted | [Report](native-window-chrome.md) |
| RENDER-017 | GitHub #26 optional distance-fog removal | Released in v1.3; owner accepted, requester acknowledged; GitHub closed | [Report](optional-fog-removal.md) |
| LAUNCHER-002 | Controller window opens off-center | Owner-centered placement verified in hidden windows; live check pending | [Investigation](modern-pause-navigation.md) |
| MOVE-001 | Upward view moves idle character | Reproduced; corrected and zero-displacement replay verified | [Camera translation cause](../../features/pc-controls.md#upward-camera-running-speed-and-scripted-input-follow-up-2026-10-10) |
| MOVE-002 | Modern movement 23.08% too fast | Native axis scaling/cap restored and tested | [Movement cap cause and fix](../../features/pc-controls.md#upward-camera-running-speed-and-scripted-input-follow-up-2026-10-10) |
| INPUT-005 | Mouse ownership during pickups/cutscenes | Shared lock fix tested; exact shotgun chest awaits live verification | [Input-lock audit](../../features/pc-controls.md#upward-camera-running-speed-and-scripted-input-follow-up-2026-10-10) |
| ANIM-001 | Backward movement uses wrong clip and leans | Native selector inputs corrected and tested | [Animation cause and fix](../../features/pc-controls.md#native-backward-and-directional-locomotion-2026-10-10) |
| ANIM-002 | Stationary turning has no planted-foot pivot | Open research; no confirmed reusable pivot or installed asset | [Feasibility findings](../../features/pc-controls.md#stationary-pivot-feasibility-review-2026-10-11) |

For earlier runtime defects, retain the [existing fix log](../boot-gameplay-fix.md).
Other currently reported limitations remain in [known issues](../../known-issues.md).


[2026-10-16 GitHub release-readiness audit](github-release-readiness-20261016.md): four open reports reviewed; a full update is not yet qualified.

- [BUILD-003: Release source validation](release-source-validation.md) - candidate remediation and qualification for 1.2.0.

[1.2.1 session findings targeted for 1.3](1.2.1-session-1.3-followup.md) collects the unresolved blur, slowdown and audio evidence with the general performance backlog.

- [Boss camera sweep pop](boss-camera-sweep-pop.md): camera-aware correction component-tested and owner-verified in Boss Camera Review; completed audit confirms 140 old projected-motion rejections avoided. Isolated shared-camera fallbacks and broader performance qualification remain documented; unreleased.

- [Live frame-rate settings](live-frame-rate-settings.md): queued enhancement; FPS mode/cap/VSync currently require game restart.

[v1.3.0 release qualification](../releases-1.3.0-qualification.md) tracks the combined owner pass, source/package checks and reporter retests; publication is pending.

[v1.3 qualification and release identities](../releases-1.3.0-qualification.md)
record the combined route, clean builds and publication gates. Historical rows
retain their original evidence limits; source inclusion is not exhaustive parity.

Cutscene skip (#31): latest candidate corrects the missing native A texture and updates the SKIP lettering. Invasion completion is still owner-untested; see [the active record](optional-cutscene-skipping.md).

Cutscene skip preview6: Goldwood forest scenery qualification candidate plus smaller, centered prompt with a smooth native IA8 ring; build/component/GPU checks passed, owner approval pending.

Cutscene skip preview7: capture identifies Magnus tutorial199 as the blocked sequence, before return shot399. Candidate corrects health physics-pointer classification and admits health/ammo demonstration objects only without native players; native route and safety checks passed, owner verification pending. Final A pop removed.

Cutscene skip preview8: SS Anubis flashback type65 glowing-light classification corrected; original three-shot return validated in completion-function tests. Prompt raster alignment corrected. Owner live review pending. Forest tutorial return now confirmed in preview7 trace; visual acceptance still pending.

Owner live verification (2026-10-20): preview8 SS Anubis flashback skip and A-button/ring alignment both confirmed fixed. Owner is continuing the route. This confirms these two fixes only; other untested cutscenes remain open coverage. Not yet released.

Preview8 follow-up: owner cannot skip the Vela rescue cutscene (corrected "can" to "cant"); still playing. Exact scene, eligibility and completion cause under investigation. Preserve active session; no replacement until closed.

Owner confirmed preview8 SS Anubis flashback skip and A-button/ring alignment fixed on2026-10-20; other cutscenes remain under review, unreleased.

New preview8 reports: Vela rescue cannot skip; Juno SS Anubis fly-away cannot skip; brief white flicker on return from SS Anubis to character selection. Owner continues playing; inspect current capture, do not replace active package.

Cutscene preview9: accepted preview8 flashback/alignment retained. Juno departure candidate preserves native disabled-door semantics and flag96; 4,136 completion checks pass. Vela no-prompt input and natural departure white flash remain open with targeted capture logging; owner review pending.

Cutscene preview10: Vela rescue now owner-confirmed working. Juno departure remains open after preview9 failed; revised cinematic-door eligibility passes native checks and awaits owner review. Repeated white flash remains open with bounded transition image capture.

- [Character-selection rainbow/white flash](character-selection-depth-flash.md): workload-aware depth/readback correction passed renderer checks and owner visual review in preview13; unreleased.

Current cutscene status: owner confirmed preview13 Tawfret intro, Vela rescue and Juno departure skipping. Earlier preview notes above preserve historical failures and superseded pending states; see [the current record](optional-cutscene-skipping.md).

2026-10-20 cutscene review: [optional skipping](optional-cutscene-skipping.md) now records the owner checklist failures, separate direct-entry limitations, Quarry tribal flashing, and source-tested completion candidates. These candidates are not yet owner-verified or released. [Selector loading](cutscene-review-selector-loading.md) records the session replay and character mapping candidates.

- [Launcher file verification feedback](launcher-file-verification-feedback.md): open owner report; both Verify files actions lack a visible working state (2026-10-20).


2026-10-20 checklist completion candidate: linked texture-actor segments,
native credits exit and selector cleanup, and reachable ending departure are
source/component-tested and installed for targeted owner retest.
[File verification feedback](launcher-file-verification-feedback.md) adds
visible activity to both verification views;81 native UI checks pass.
The full owner checklist is preserved; unresolved diagnostic contexts and
Quarry tribal flashing are not marked resolved.


2026-10-20 follow-up: Quarry tribals brighten/darken after both282/0 and411/0,
including the owner's restarted Original-FPS comparison. Native EmuHawk
brightness comparison is in progress. The private selector's classified
catalog and BigShip direct-entry rejection pass isolated persistence checks
and62 native entry checks; these changes are staged, not installed/released.


Quarry follow-up: original-ROM EmuHawk also visibly pulses. The exact earlier
day/night lighting repair was located; a scoped restoration is built and
installed for owner review, with the live outcome still pending. See the
[cutscene issue](optional-cutscene-skipping.md) for cause, comparison evidence,
source scope and limitations. No released-resolution claim.

- [Quarry atmospheric day/night transition jumps](quarry-atmospheric-transitions.md): owner-approved corrected smoothing; all 12 phases captured with 2,971 matching fog commands and zero colour-match rejection. Original integer-distance steps and rejected strobing candidate documented. Unreleased; actor fix remains accepted.

- [Modern controls on P2-P4](modern-controls-secondary-players.md): confirmed setup/runtime restriction; UI tests pass, per-port runtime candidate under validation.

- 2026-10-21 review follow-up: [BigShip selector entry](cutscene-review-selector-loading.md) no longer crashes but does not start. Current validator deliberately rejects the unsafe standalone entry; safe entry and clear selector feedback remain unresolved. Not a verified skip pass.

- 2026-10-21 owner cutscene retest: [scene207](optional-cutscene-skipping.md) shows the skip prompt but reportedly crashes after skipping. High-severity completion failure remains open; prompt visibility is not successful skip verification.

- 2026-10-21 ongoing [cutscene pass](optional-cutscene-skipping.md):207/0 stalls after skip (owner clarification);235 reportedly crashes after playback, unused status unconfirmed;240/1 does not allow skip. All remain open, separate from accepted Quarry lighting/fog fixes.

- [Current cutscene owner retest](cutscene-owner-retest-20261020.md): ongoing045/207/235/240/271/275 findings, with crashes, stalled completion, unavailable skip and no visible action kept distinct. Unresolved; accepted Quarry fog is separate.

- Final [Juno cutscene retest](cutscene-owner-retest-20261020.md): owner confirms remaining failures are valid; Juno-only investigation active, including376,378/1 and corrected380/1. Superseded by the owner clarification below: checked Juno entries are passes even when older failure notes remain.

- [Modern Floyd vertical inversion](modern-floyd-vertical-inversion.md): owner reproduced reversed mouse aim with P2 inversion Off; adapter correction passes native tests and preview 2 is owner-confirmed.

- Owner clarified final Juno checkbox semantics: checked means passed, even with an older failure note. Only unchecked entries remain in the [active cutscene retest scope](cutscene-owner-retest-20261020.md).

- Juno final cutscene pass: [current owner retest](cutscene-owner-retest-20261020.md), All four targeted fixes are owner-confirmed. The11 remaining unchecked entries are classified as likely development/setup variants after the original631-exit and animation-script scans; no exact unresolved variant was linked by those exits. Classification limits are recorded; the type 145 audit is complete with a source-comment correction and no runtime change. [Selector record](cutscene-review-selector-loading.md) covers mode recovery, focus handoff, explicit blocked-entry feedback and the corrected note-row event ordering. Checked owner entries remain passed.

- [Floyd widescreen bounds](floyd-widescreen-aim-bounds.md): original limits confirmed in EmuHawk at4:3/widescreen; mouse matches, no bounds change.

- [Modern Floyd controller diagonal range](modern-floyd-controller-diagonal-range.md): correction in preview3;64 native cases and four suites pass; owner controller test pending; original outer bounds intact.

- [Floyd reticle/ammo HUD layering](floyd-reticle-ammo-hud-layering.md): original triangle/line layering reproduced in EmuHawk Angrylion; no correction indicated.

- [Modern M/K camera during Floyd preview3](modern-mouse-camera-floyd-preview-report.md): mixed-contact distance correction in preview4;447 recorded points qualified in both native execution paths; owner confirms camera fixed; unreleased.

- [Floyd mission pad access after Give Floyd](give-floyd-mission-pad-access.md): SS Anubis pad requires a Mizar token; zero-token gate explained. Owner subsequently entered the mission; firing/completion validation remains open.

- [Modern M/K Floyd mission steering](modern-floyd-mission-mouse-flight.md): Owner reports preview5 flight feels good; preview6 adds A/D strafing. Runtime/four suites and native velocity checks pass; owner strafe/fire/completion validation pending.

- [Modern controller Floyd flight inversion](modern-floyd-controller-flight-inversion.md): separate default-On flight option in preview7; automated checks pass and owner approved; unreleased.
