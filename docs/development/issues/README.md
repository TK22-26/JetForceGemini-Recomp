# Issue investigations and resolutions

Keep an issue record from the first reproducible report through its final verified
resolution. This is the persistent engineering history for bugs, regressions and
significant limitations. It complements [known issues](../../known-issues.md), the
[runtime fix log](../boot-gameplay-fix.md), and feature implementation notes; link
those sources rather than copying conflicting accounts.

Original-hardware defects also belong in the [N64 catalog](../../original-game/README.md). Keep emulator evidence and regional differences separate.

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

## Published delivery

[v1.4.0 qualification](../../releases/qualification-1.4.0.md) records the published package,
checks and issue delivery. The individual records retain reporter-specific retests and redirected
reports; a closed GitHub issue is not proof of universal parity. No fresh remote issue audit is
implied by this index. [Comment punctuation](github-comment-punctuation.md) and
[merge metadata](github-merge-metadata.md) retain the publication-process findings.

## Active and historical issue index

The historical rows below index existing evidence; they do not claim a new retest.
Detailed per-issue records are added as those issues receive further work.

| ID | Issue | Current recorded status | Investigation / resolution |
|---|---|---|---|
| TEST-RENDERER-LAYOUT-20261108 | Renderer texture fixtures omit their regional layout | Explicit fixture layout restores full texture regression pass; no runtime change; uncommitted | [Report](renderer-texture-fixture-layout.md) |
| UI-LAYOUT-20261107 | ROM buttons and Video search field sizing | Distinct ROM IDs and text/search layout corrected; Windows/Proton checks pass; owner review pending | [Report](launcher-rom-and-search-layout.md) |
| AUDIO-OPENING-20261107 | Audible opening Invasion glitch on Bazzite | Owner reports audible interruption; cause and saved Linux logs pending | [Report](opening-invasion-audio-proton.md) |
| UI-ABOUT-WINDOW-20261107 | About remains an embedded dialog | Dedicated native About window and official GitHub mark pass Windows/Proton checks; delivered for owner review | [Report](launcher-about-separate-window.md) |
| UI-ABOUT-20261107 | About window opens slowly | Delay not reproduced in Windows/Proton checks; timing logging delivered; cause remains open | [Report](launcher-about-window-delay.md) |
| N64-002 | Goldwood starting-bridge texture wash (NTSC) | Owner-reported native behavior; screenshots preserved, cause unknown; intentionally preserved, no fix requested | [Record](goldwood-starting-bridge-texture-wash.md) |
| AUDIO-SUPPORT-20261104 | Support ZIP removes audio recovery events | Bounded audio-event export fixed in 067f9a8; production logger-to-ZIP and malformed-field checks pass; unreleased | [Report](audio-recovery-support-export.md) |
| BUILD-AUDIT-MEMORY-20261102 | MSVC blur-audit buffer initialization | Isolated compiler, fixed-capacity export and all three enhanced native builds verified; public-default build remains unverified | [Report](build-blur-audit-compiler-memory.md) |
| AUTONOMY-CHILD-CONTAINMENT-20261102 | Packaged Python native children escape the process job | Verified by Windows regressions and actual native compiler containment; unreleased | [Report](windows-packaged-python-child-containment.md) |
| TOOLING-SESSION-20261101 | Retained Codex process blocks session resume | Recurring lock contention recovered locally; history preserved; lifecycle cause and owner resume verification pending | [Report](codex-session-writer-lock.md) |
| FLASH-CONTRACT-20261101 | FlashRAM sector and command semantics | Shared device, normal new-slot/reload, checksum menus and exact-path write-failure/retry verified on all three; campaign durability and hardware timing pending | [Report](flashram-device-contract.md) |
| LAUNCHER-EXPLORER-SHUTDOWN-20261101 | Map explorer worker outlives window close | Bounded worker completion passes actual-window regression; live verification pending | [Report](launcher-explorer-shutdown.md) |
| ARCH-NATIVE-20261101 | Native runtime modularization | Implemented module ownership; Windows build, 118 CTests and scoped native replays pass; shared State and Linux live limitations recorded; unreleased | [Report](native-runtime-modularization.md) |
| TOOLING-HISTORY-20261031 | Local history hygiene | Resolved locally after verified external preservation of all objects and six stashes; actual full-history gate passes; main/develop/tag identities preserved | [Report](repository-history-hygiene.md) |
| ARCH-20261031 | Folder architecture, stale documentation and legacy tooling | Implemented locally: domain layout, obsolete tooling removal and documentation consolidation; Windows/Python/renderer/UI checks pass; unreleased | [Report](folder-architecture-audit.md) |
| VERIFY-EMU-20261027 | Original-ROM reference qualification of local batch | Scoped original-ROM comparisons and full available regression checks complete; limits recorded | [Matrix and limits](emuhawk-reference-verification-20261027.md) |
| SUPPORT-ZIP-20261027 | Added presentation diagnostics and upload sanitization | Final rebuilt exporter passes actual ZIP privacy/bounds checks; unreleased | [Report](support-zip-presentation-sanitization.md) |
| TOOLING-PORTABILITY-20261027 | Local batch GCC warnings and updated WSL trust-boundary fixture | GCC Release build and 108 tests pass; pinned WSL sanitizer coverage unavailable | [Report](local-batch-portability-validation.md) |
| SDK-PRINTF-20261027 | Missing original SDK formatting functions crash sound warnings | Original-byte metadata recovery, actual formatting and final native replays pass; unreleased | [Report](sdk-printf-field-metadata.md) |
| ORIGINAL-TIMING-20261027 | Original FPS does not select original simulation timing | Open: host-clock and omitted device-time causes isolated; yielding measured; reference timing and diagnostic loading audio remain unqualified | [Report](original-mode-simulation-parity.md) |
| GH-048 | [Playtest] In high framerates flying enemies move faster | Deferred for this version by owner Nov 8; unresolved, not accepted as fixed; existing candidate and timing evidence retained | [Report](github-flying-enemy-speed.md) |
| GH-049 | [Playtest] With Modern Controls can't view objectives during Floyd Challanges | Fixed in develop; owner confirmed Nov 8; configured Fire cycles paused Floyd objective pages; unreleased | [Report](github-floyd-objectives-controls.md) |
| GH-050 | [Playtest] With Modern Controls can't use trap items in Jeff's Arcade race | Fixed locally; owner manually tested and approved USA/PAL/JP Nov 8; uncommitted/unreleased | [Report](github-arcade-trap-controls.md) |
| GH-051 | [Playtest] Lupus' Nightvision in Mizar's Palace is pixelated | Fixed locally; owner manually tested and approved USA/PAL/JP Nov 8; unreleased | [Report](github-nightvision-damage-presentation.md) |
| PREVIEW-SAVE-IDENTITY | Closer-camera preview rejects save identity after text newline conversion | Repaired locally; shipped USA/PAL/JP storage validation passes; owner retry pending | [Report](preview-save-identity-newlines.md) |
| GH-052 | [Playtest] With Modern Controls the character turns transparent during combat | Resolved locally: owner approved the 180-unit closer-camera build; regional/device coverage unspecified; unreleased | [Report](github-combat-player-transparency.md) |
| GH-053 | [Proposal] With Modern Controls a toggle for free movement (like with Classic) with a button press | Owner confirms already tested and approved as an optional Advanced control action; regional/device coverage unspecified; unreleased. | [Report](github-modern-free-movement.md) |
| GH-054 | Erro open app driver video intel | Owner directs closure as another project/version; no local defect established. Recorded for closure; no GitHub change performed. | [Report](github-intel-launch-version-mismatch.md) |
| GH-055 | [proposal] Question for camera control | Owner confirms already tested and approved as an optional Advanced control setting; regional/device coverage unspecified; unreleased. | [Report](github-modern-free-camera.md) |
| GH-057 | Menu icons show grey boxes in widescreen; title vignette edge is stepped instead of smooth | Current local fixes reverified with renderer checks and USA widescreen captures; owner visual acceptance pending; unreleased. | [Report](github-menu-icon-vignette.md) |
| GH-058 | [Playtest] Game starts but only shows black screen | Cause unverified; requested/selected game API and bounded presentation diagnostics implemented and locally tested, with persisted Auto/D3D12/Vulkan selection and a validated standalone comparison. Affected Windows 10 retest pending. | [Report](github-black-screen-audio.md) |
| RENDER-VELA-SKIRT | Vela skirt transparency artifact on slopes | Resolved locally: skirt/focus repair and smooth transparency owner-verified; unreleased | [Report](vela-skirt-focus-tearing.md) |
| RENDER-CAMERA-CADENCE | Pulsing flight camera and ship motion | Camera/ship/startup corrections owner-verified locally; separate skybox correction passes replay and owner review | [Report](cutscene-camera-cadence.md) |
| AUDIO-VOLUME-EMPTY | In-place volume-file rewrite can publish an empty snapshot | Candidate verified in repeated focused runs and the full 111-test host suite; unreleased | [Report](async-volume-empty-snapshot.md) |
| UI-AUDIO-SETTINGS | Audio Settings opens as an old modal with about 20 seconds delay | Resolved locally: owner confirms immediate opening; original delay cause unknown; unreleased | [Report](audio-settings-window-delay.md) |
| NAV-EXIT-SENTINEL | Exit destination high-byte sentinel | Original-source cause and both-memory-layout regressions verified; all-three native builds pass; live-route acceptance pending | [Report](navigation-exit-destination-sentinel.md) |
| ROM-PACKAGE-VERIFY | Regional package verifier format mismatch | Schema-2 producer/verifier roundtrips and rejection cases pass; all 38 release tests pass; unreleased | [Report](regional-package-verifier.md) |
| ROM-SUPPORT-IDENTITY | Regional program identity omitted from support ZIP | Synthetic and actual all-three native-session ZIP identity/privacy checks pass in committed launcher; unreleased | [Report](regional-support-identity.md) |
| ANIM-PAL-BACKWARD-20261102 | Modern backward movement tilts Juno on PAL | Owner confirms v31 body-tilt correction fixed; accepted locally, unreleased | [Report](pal-modern-backward-body-tilt.md) |
| MENU-KEY-CADENCE-20261102 | Name-entry keyboard keys appear to animate at native frame rate | Owner confirms v31 keyboard fixed; all-region replay coverage retained; accepted locally, unreleased | [Report](name-entry-key-animation-cadence.md) |
| MODERN-AIM-RELEASE-20261102 | Modern Aim release snaps the camera instead of sweeping back | owner confirms smooth scope-out and natural scope-in on PAL/controller; USA/JP manual testing pending; US/PAL/JP native regressions pass; local v33, unreleased | [Report](modern-aim-release-camera-snap.md) |
| LAUNCHER-NOTIFICATIONS | Bottom-left notices queue instead of stacking | Implemented; native UI regressions pass; owner visual acceptance pending; local v35, unreleased | [Report](launcher-notification-stack.md) |
| LAUNCHER-ROM-REGIONS | Main-screen regional ROM selection | Implemented; native UI, all-region CLI and restart checks pass; owner review pending; local v34, unreleased | [Report](launcher-regional-rom-selection.md) |
| ROM-REGIONS | PAL and Japanese support | All-three enhanced handoff, saves/fault recovery, Modern slice and 15-minute Play verified; public-default resource-bounded build and owner acceptance remain open | [Report](regional-rom-support.md) |
| ROM-OVERLAY-OWNERS | Regional overlay identity | Typed owners, record members and packed schemas qualified for all three; bounded enhanced Play passes; full feature acceptance open | [Record](regional-overlay-ownership.md) |
| AUDIO-FLIGHT-045 | Missing music in specific flight transitions | Owner-confirmed native NTSC issue; different correction deferred to a separate general native-bug-fixes update; Walkway hardware evidence established, Vela routes individually unverified | [Report](flight-transition-missing-music.md) |
| RENDER-SHOT-001 | Low-FPS effects at high output rates | Ship beams, travelling shots and grenade shockwaves owner-verified locally; opening marker and fire owner-verified locally; unreleased | [Report](high-refresh-shot-effects.md) |
| GH-047 | [Playtest] In high framerates the floor reflections are animated in lower frames | Fixed in develop; reflected geometry and motion corrections owner-approved, reaffirmed Nov 8; unreleased | [Report](floor-reflection-geometry.md) |
| GH-046 | [Playtest] In high framerate character shadows jitter while moving | Solved in develop; updated/modern Enhanced Shadows option added, Original retained; owner acceptance reaffirmed Nov 8; unreleased | [Report](github-character-shadow-jitter.md) |
| RENDER-020 | Bridge environmental shadow and Enhanced scope | Classified: dark strip is pre-existing ground vertex shading; bridge has no projected-shadow control; environment replacement is separate work | [Evidence and compatibility](enhanced-shadow-environment-scope.md) |
| META-001 | GitHub merge identity differs from local no-reply/UTC policy | PR #42 server metadata observed; owner informed; history preserved; publication commit/tag identity checked locally | [Report](github-merge-metadata.md) |
| BUILD-V14 | Clean CI: GCC rain initializer and RT64 checkout line endings | All supported-platform and merged-main CI jobs pass; included in v1.4.0 | [Report](v14-clean-ci-portability.md) |
| RENDER-CHIEF | Tawfret chief cutscene camera motion and floating square | Both corrections owner-verified; original N64 helper artifact removed in v1.4.0 | [Report](tawfret-chief-camera-and-square.md) |
| PROTON-MOUSE-20261107 | Hidden gameplay pointer escapes and stops at monitor edges | Owner manually confirms fully working on Bazzite Nov 8; accepted locally, cause unconfirmed, unreleased | [Report](proton-mouse-confinement.md) |
| GH-041 | [Enhancement] Reduce cutscene skip completion time | Native ROM protocol overhead isolated; all three regions checked; owner confirms opening skip works on Proton, unreleased | [Report](cutscene-skip-completion-time.md) |
| VULKAN-CAPTURE | Diagnostic frame readback | Reproduced private Vulkan capture crash; missing image-to-buffer branch identified; no fix yet | [Report](vulkan-diagnostic-frame-readback.md) |
| UI-009 | Live map Mods redesign disabled/focus states | Owner-approved 2026-10-21; visible badges and reference padlock accepted locally; 973 native checks pass; included in v1.4.0 | [Review](live-map-mods-layout.md) |
| GH-040 | Does not run through Proton on the Steam Deck | Owner reports Bazzite looks good except skips; current-build logs received with newer USA session; Deck verification pending | [Report](github-steam-deck-proton-startup.md) |
| GH-039 | Give all weapons leaves inventory unchanged (#39) | Reproduced: paused Mods dialog expires requests. Candidate processes grants while paused and confirms application; native/runtime/launcher checks passed and owner confirms actual UI grant; released in v1.4.0; #39 closed with reporter retest requested | [Report](github-give-all-weapons.md) |
| GH-038 | Fet-Bubb crashes shortly after attacking (#38) | Dump exactly matches VibinToast v1.1.8, a different project; our v1.3.0 passes bounded boss comparison; local defect unestablished; #38 closed and reporter redirected | [Report](github-fet-bubb-crash.md) |
| GH-037 | Floyd cannot fire (#37) | Fully approved locally by owner for v1.4.0; reporter re-verification after delivery pending | [Report](github-floyd-cannot-fire.md) |
| GH-036 | Missing weapon crosshairs (#36) | Owner believes existing accepted reticle correction covers it; likely fixed locally, delivered in v1.4.0; #36 closed with reporter retest requested | [Report](github-weapon-crosshairs.md) |
| GH-034 | Modern boss aim range, including both Mizar fights (#34) | Owner-approved after live Twin Mantis review; five boss fixtures match EmuHawk in both Modern paths; included in v1.4.0; reporter retest after delivery | [Report](github-twin-mantis-aim-range.md) |
| DIAG-003 | Cutscene selector rejects a running game | Normal native parent/child pair miscounted as two games; corrected detection owner-confirmed; character ID swap corrected awaiting review; room45 direct-entry crash and stale-request startup open | [Report](cutscene-review-selector-loading.md) |
| UI-008 | Launcher menu hover remains highlighted over game | Initial hover fix regressed dropdown selection; corrected routing passes 55 menu and 790 controls checks; owner confirms fixed; included in v1.4.0 | [Report](launcher-menu-hover-stuck.md) |
| GH-032 | [Playtest] Mouselook not working. | Four v1.4.0 captures analyzed: failing sessions have zero accepted motion; develop delivery candidate and inversion direction still need affected-user verification | [Report](github-mouse-look-and-inversion.md) |
| GH-033 | Modern Controls missing sideways roll (#33) | Roll bindings, automatic-roll setting, prone direction and backward-crawl fixes owner-accepted; included in v1.4.0 | [Cause, evidence and selected policy](github-modern-controls-side-roll.md) |
| PERF-005 | SS Anubis ledge-testing stutter in Lighting Preview | Earlier gaps measured; repeat Anubis capture steady, intermittent cause open | [Report](tawfret-lighting-preview-stutter.md) |
| RENDER-019 | Tawfret brightness and distant haze differ from N64 | Fog candidate checked against original tasks; owner approved locally; included in v1.4.0 | [Report](tawfret-brightness-fog-fidelity.md) |
| INPUT-012 | Removing a controller moves it to another player | Explicit Remove and input-type replacement fixes owner-confirmed; included in v1.4.0 | [Report](controller-remove-auto-reassignment.md) |
| INPUT-013 | Player port indicators stay stale | Idle assignment indicator refresh owner-accepted; included in v1.4.0 | [Report](controller-port-indicators-stale.md) |
| AUDIO-004 | Crackling and persistent audio delay (#29/#35) | #29 closed; #35 open. November 1 logs identify released build and pause-like gap but no queue timing; develop recovery has owner regression acceptance, affected-user retest pending | [Report](audio-crackle-persistent-latency.md) |
| CAMERA-009 | Focus-loss camera reset | Room-entry/focus-return correction passes actual-source tests and owner review with Modern controller and mouse/keyboard; included in v1.4.0 | [Report](focus-loss-camera-reset.md) |
| CAMERA-008 | Modern controller high-drop camera reset | Owner confirmed locally; 486 scoped assertions and native checks pass; included in v1.4.0 | [Report](controller-high-landing-camera-reset.md) |
| CAMERA-007 | Modern ledge/water camera reset and water-air facing (#30) | Ledge/water camera and water-air body-facing fix owner-approved after isolated retest; included in v1.4.0, reporter retest pending | [Report](controller-ledge-camera-reset.md) |
| ENHANCE-001 | Optional cutscene skipping (#31) | Owner-approved 2026-10-21; final four targeted Juno retests pass; eleven debug/context entries retain documented coverage limits; included in v1.4.0 | [Scope](optional-cutscene-skipping.md) |
| RENDER-018 | Dead drone bodies jitter with camera movement | Included in v1.3; owner visual pass and capture validation, exact seed/cutscene coverage unverified | [Investigation and validation](dead-drone-camera-jitter.md) |
| NATIVE-003 | Ichor detached-head flight locations after body destruction | EmuHawk plus idle/moving Vela comparison: no sampled out-of-bounds flight; broader parity unconfirmed | [Report and comparison plan](ichor-head-flight-locations.md) |
| MOD-001 | Exit warp stops at the door | Native contact fix in 1.2.1; 1.3 progression bypass and exact overlapping-exit handoff pass focused/native checks | [Report and source review](map-exit-warp-transition.md) |
| RENDER-012 | Breakable glass before Vela shakes at high refresh | Included in v1.3: production overlay translation, component checks and owner live verification passed | [Report](high-refresh-glass-shaking.md) |
| RENDER-015 | Boss motion blur causes discomfort despite 120/30 | Included in v1.3; Off/Reduced owner-accepted and three-mode preference component-tested | [Report](boss-motion-blur-discomfort.md) |
| RENDER-016 | GitHub #25 Ally X cutscenes, homing reticle and rain | Original reporter confirms all reported bugs fixed in v1.4.0 and reports 120 FPS on Ally X; remains closed | [Report](github-ally-x-rendering.md) |
| RENDER-014 | Enemy-clear door indicator darkens with distance | ORIGINAL-GAME BUG confirmed in EmuHawk; further investigation deferred by owner; accepted visibility workaround included in v1.3 | [Report](door-enemy-lock-distance-darkening.md) |
| RENDER-013 | Original appears to follow VSync/display refresh | Not reproduced after restart; owner confirms 30 FPS motion, earlier session unlogged | [Investigation](original-vsync-rate-selection.md) |
| RENDER-011 | Vela rescue cutscene stalls / appears low resolution | Owner accepts v31 regional rescue-blur correction; command-list regression passes; local, unreleased | [Report and evidence](vela-rescue-cutscene-stutter-resolution.md) |
| INPUT-011 | GitHub #20 Ichor boss-room controls stop responding | Released in v1.2.1; owner confirms three bosses; reporter retest pending | [Cause and verification](github-ichor-boss-controls.md) |
| BUILD-003 | Release source policy and compiler portability | v1.4 Windows candidate checks pass; clean-history/package/public-download verification passed; existing WSL harness limitation retained | [Release validation](release-source-validation.md) |
| NATIVE-002 | GitHub #14 mouse-look startup access violation | Reproduced startup cause resolved in v1.2.0; current enabled startup passes | [Startup report](github-mouse-look-startup.md) |
| BUILD-002 | GitHub #15 GCC native build failure | Portable source released in v1.2.0; actual GCC source verified, AppImage not qualified | [Linux build review](github-linux-native-build.md) |
| INPUT-010 | GitHub #13 controller camera inversion | GUI toggle released in v1.2.0; persistence/deltas verified, reporter retest pending | [Controls review](github-controller-vertical-inversion.md) |
| SETUP-001 | GitHub #4 Windows 10 source setup | Fixes released in v1.2.0; 28 checks pass, fresh Windows 10 retest pending | [Setup review](github-windows-source-setup.md) |
| GH-018 | Held aim cancels on firing; diagonal movement differs while aiming | Owner relays reporter acknowledgement: held aim fixed in v1.2. Standing-aim correction included in v1.3 and matches native measurements; reporter retest pending | [Investigation](github-held-aim-and-diagonal-movement.md), [handoff](../runtime/issue18-native-controls-handoff-2026-10-17.md) |
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
| STORAGE-001 | Historical diagnostics fill the working volume | October 28 bulk cleanup verified (~299.5 GB freed); current timing set retained; three small policy-blocked leftovers | [Cause, retention and cleanup](diagnostic-storage-exhaustion.md) |
| PERF-005 | GitHub #19 invasion replay at 1-2 FPS | Original reporter confirms resolved and requests closure; explicit closeout TODO; GitHub still open | [Report and comparisons](github-invasion-replay-stutter.md) |
| PERF-004 / DISPLAY-002 | Opening village cadence / cutscenes ignore 4:3 option | Combined private candidate passes active-shot cadence at 120/360; aspect checks pass; loading, presentation and live review remain separate | [Evidence and progress](opening-village-and-cutscene-aspect.md) |
| AUDIO-003 | Ship-cutscene stutter and Goldwood exit audio | Included in v1.3; both ship scenes owner-accepted and final route has zero audio underruns | [Exit investigation](goldwood-exit-audio.md) |
| AUDIO-002 | Frequent audio interruptions during walking/combat | Native playback remedy delivered; final default replays clean; one long-stall control underrun and owner listening check remain open | [Report and investigation](walking-audio-interruptions.md) |
| AUDIO-001 | Intermittent background-music crackle | Verified in tests and owner live verification; local preview only | [Investigation](intermittent-music-crackle.md) |
| DIAG-002 | Reference owner capture inherited debug gameplay overrides and classic controls | Setup defect confirmed; correction prepared; further reference testing stopped at owner request | [Audit and correction](reference-owner-capture-contamination.md) |
| DIAG-001 | Bounded replay misses final image capture | Verified in hidden replays; unchanged final reference RAM | [Cause and verification](final-probe-frame-capture.md) |
| CAMERA-006 | Mouse camera resets after landing or ledge climb | Fixed in local candidate; component checks and owner confirmation cover high-drop landing and ledge climb; included in v1.4.0 | [Report](mouse-camera-high-landing-reset.md) |
| CAMERA-005 | Modern camera jumps upward over terrain / apparent pond-lip contact | Actual pond regression reproduced and corrected in tests; revised preview installed, owner live check pending | [Report and investigation](camera-collision-bounce.md) |
| CAMERA-003 | Modern area entry faces the exit | Verified in focused tests and owner live play; local preview | [Reproduction and work](modern-controller-state-transitions.md) |
| MOVE-003 | Dual-stick jump loses direction and air steering | Verified in focused tests and owner live play; local preview | [Reproduction and work](modern-controller-state-transitions.md) |
| CAMERA-004 | Focus loss lowers camera angle | Verified in focused tests and owner live play; local preview | [Reproduction and work](modern-controller-state-transitions.md) |
| CAMERA-001 | Small repeated forward camera steps | Verified in isolated replay; delivered preview, live verification pending | [Fixed modern camera boom](https://github.com/TK22-26/JetForceGemini-Recomp/blob/db9ea90b41b9bf14d806ab6aea1aefbddbb80efa/docs/features/pc-controls.md#2026-10-11-goldwood-capture-camera-stepping-and-native-pause-save) |
| CAMERA-002 | Large scenery-driven camera pull-ins | Open; targeted response correction in CAMERA-005, broader scenery coverage pending | [Capture findings](https://github.com/TK22-26/JetForceGemini-Recomp/blob/db9ea90b41b9bf14d806ab6aea1aefbddbb80efa/docs/features/pc-controls.md#2026-10-11-goldwood-capture-camera-stepping-and-native-pause-save), [candidate and limits](camera-collision-bounce.md) |
| INPUT-001 | Main-menu clicks eaten; resize cursor remains in client | Corrected and regression-tested; physical focus verification remains | [Win32 activation/cursor cause and fix](https://github.com/TK22-26/JetForceGemini-Recomp/blob/db9ea90b41b9bf14d806ab6aea1aefbddbb80efa/docs/features/pc-controls.md#live-menu-click-and-cursor-correction-2026-10-10) |
| INPUT-002 | Hover traverses intermediate save slots | Corrected with semantic native selection; tested | [Pointer audit](https://github.com/TK22-26/JetForceGemini-Recomp/blob/db9ea90b41b9bf14d806ab6aea1aefbddbb80efa/docs/features/pc-controls.md#modern-shoulder-camera-and-mouse-audit-2026-10-10) |
| INPUT-003 | Fire drops mouse aim; aim entry snaps view | Corrected and tested; broader live coverage remains | [Capture ownership and camera handoff](https://github.com/TK22-26/JetForceGemini-Recomp/blob/db9ea90b41b9bf14d806ab6aea1aefbddbb80efa/docs/features/pc-controls.md#modern-shoulder-camera-and-mouse-audit-2026-10-10) |
| INPUT-004 | Missing pause mouse targets / modern Save | Submenu navigation, contextual Back and sounds verified in tests; live check pending | [Current report and investigation](modern-pause-navigation.md) |
| INPUT-006 | Modern aiming prevents jumping | Native jump-from-aim verified for all characters; live check pending | [Investigation](modern-pause-navigation.md) |
| LAUNCHER-004 | GitHub #24 portable user data | Released in v1.3; owner accepted, user confirms working; GitHub closed | [Report](portable-user-data.md) |
| LAUNCHER-005 | Native windows use light title bars unlike Scooby | Included in v1.3; native caption checks pass and owner accepted | [Report](native-window-chrome.md) |
| RENDER-017 | GitHub #26 optional distance-fog removal | Released in v1.3; owner accepted, requester acknowledged; GitHub closed | [Report](optional-fog-removal.md) |
| LAUNCHER-002 | Controller window opens off-center | Owner-centered placement verified in hidden windows; live check pending | [Investigation](modern-pause-navigation.md) |
| MOVE-001 | Upward view moves idle character | Reproduced; corrected and zero-displacement replay verified | [Camera translation cause](https://github.com/TK22-26/JetForceGemini-Recomp/blob/db9ea90b41b9bf14d806ab6aea1aefbddbb80efa/docs/features/pc-controls.md#upward-camera-running-speed-and-scripted-input-follow-up-2026-10-10) |
| MOVE-002 | Modern movement 23.08% too fast | Native axis scaling/cap restored and tested | [Movement cap cause and fix](https://github.com/TK22-26/JetForceGemini-Recomp/blob/db9ea90b41b9bf14d806ab6aea1aefbddbb80efa/docs/features/pc-controls.md#upward-camera-running-speed-and-scripted-input-follow-up-2026-10-10) |
| INPUT-005 | Mouse ownership during pickups/cutscenes | Shared lock fix tested; exact shotgun chest awaits live verification | [Input-lock audit](https://github.com/TK22-26/JetForceGemini-Recomp/blob/db9ea90b41b9bf14d806ab6aea1aefbddbb80efa/docs/features/pc-controls.md#upward-camera-running-speed-and-scripted-input-follow-up-2026-10-10) |
| ANIM-001 | Backward movement uses wrong clip and leans | Prior fix regressed during regional conversion; see [current correction](pal-modern-backward-body-tilt.md) | [Animation cause and fix](https://github.com/TK22-26/JetForceGemini-Recomp/blob/db9ea90b41b9bf14d806ab6aea1aefbddbb80efa/docs/features/pc-controls.md#native-backward-and-directional-locomotion-2026-10-10) |
| ANIM-002 | Stationary turning has no planted-foot pivot | Open research; no confirmed reusable pivot or installed asset | [Feasibility findings](https://github.com/TK22-26/JetForceGemini-Recomp/blob/db9ea90b41b9bf14d806ab6aea1aefbddbb80efa/docs/features/pc-controls.md#stationary-pivot-feasibility-review-2026-10-11) |

## Additional investigation records

These records supply their own current status and evidence limits. This complete directory index
also includes release audits, original-behavior comparisons and resolved supporting investigations.

| Investigation |
|---|
| [1.2.1 session follow-up for 1.3](1.2.1-session-1.3-followup.md) |
| [Actor LOD option](actor-lod-option.md) |
| [Boss briefly pops during camera sweeps](boss-camera-sweep-pop.md) |
| [Actor jumps while rotating the camera](camera-turn-actor-jumps.md) |
| [Character-selection rainbow/white flash after SS Anubis](character-selection-depth-flash.md) |
| [Cutscene owner retest - 2026-10-20 Eastern](cutscene-owner-retest-20261020.md) |
| [Drone buried beside a broken hut](drone-buried-after-hut-collision.md) |
| [Exit marker and grenade fire cadence](exit-marker-fire-cadence.md) |
| [Floyd reticle and ammo HUD layering](floyd-reticle-ammo-hud-layering.md) |
| [Floyd widescreen aiming bounds](floyd-widescreen-aim-bounds.md) |
| [Open GitHub issue review before a full update (2026-10-16)](github-release-readiness-20261016.md) |
| [Give Floyd: SS Anubis mission pad cannot be activated](give-floyd-mission-pad-access.md) |
| [Launcher file verification has no visible progress](launcher-file-verification-feedback.md) |
| [Live frame-rate settings](live-frame-rate-settings.md) |
| [Modern controls unavailable for Players 2-4](modern-controls-secondary-players.md) |
| [Modern Floyd controller diagonal range](modern-floyd-controller-diagonal-range.md) |
| [Modern controller Floyd flight inversion](modern-floyd-controller-flight-inversion.md) |
| [Modern mouse/keyboard Floyd mission flight controls](modern-floyd-mission-mouse-flight.md) |
| [Modern Floyd vertical aiming reversed with inversion Off](modern-floyd-vertical-inversion.md) |
| [Modern mouse camera report during Floyd preview3](modern-mouse-camera-floyd-preview-report.md) |
| [Quarry atmospheric day/night transition jumps](quarry-atmospheric-transitions.md) |
| [Gems visible through hanging vine textures](vine-gem-occlusion.md) |

For earlier runtime defects, use the [runtime fix log](../boot-gameplay-fix.md).
The [pre-reorganization index](https://github.com/TK22-26/JetForceGemini-Recomp/blob/db9ea90b41b9bf14d806ab6aea1aefbddbb80efa/docs/development/issues/README.md)
retains the old chronological preview summaries. Their failures and final outcomes belong in the
linked issue records; old pending states do not override those records or release qualification.
