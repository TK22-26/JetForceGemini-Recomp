# Changelog

## Unreleased

- Split native startup from private guest memory, host audio/window input, overlays,
  saves, task submission, diagnostics and guest execution modules. Preserve single
  timing/cache ownership and the generated ABI. The Windows host rebuild and scoped
  replays pass; shared state and regional host assumptions remain documented limits.
  [Runtime validation](docs/development/issues/native-runtime-modularization.md).
- Build a shared US/PAL/Japanese program architecture: exact original reconstruction,
  common CPU/audio generation, typed resident/overlay/member bindings, strict native
  bundle identity and revision save storage. Earlier original-OS builds create saves
  and reload into Goldwood on all three revisions. Enhanced runtime, residual binary
  schemas, product admission and campaign acceptance remain in qualification.
  [Regional implementation and evidence](docs/development/issues/regional-rom-support.md).
- Finish owner-approved local Git cleanup after verifying an independent retained
  database of all original objects and six stashes. Keep main/develop and public
  commit/tag identities; the actual checkout's full history hygiene check passes.
  [Recovery and scope](docs/development/issues/repository-history-hygiene.md).

- Reorganize build/release/validation/diagnostic tools, tests, native launcher source
  and CMake targets by responsibility. Preserve published setup entry points and
  shared Python imports; remove the broken Quarry shortcut, obsolete launcher-only
  packaging and stale manual workflows. Consolidate duplicate controller artwork.
- Rewrite and consolidate project, player and maintainer documentation, with a
  complete file-disposition audit and one durable record per investigation. Add an
  original N64 bugs catalog, keeping hardware-confirmed Tawfret behavior separate
  from the NTSC/PAL Walkway music difference and future regional support.
  [Audit, validation and remaining limits](docs/development/issues/folder-architecture-audit.md).

- Fix Audio Settings opening as an inline modal: use a separate native window
  with live volume/mute controls. Focused UI and menu-route tests pass; on
  October 31 the owner confirms immediate opening and accepts the fix. The
  original delay's cause remains unknown.
  [Record](docs/development/issues/audio-settings-window-delay.md).

- Add a local candidate for flying-enemy timing (#48): advance the shared flight
  and falling movement by elapsed game time, using a three-VI reference measured
  across two original-ROM encounters. Keep output FPS independent, preserve
  native velocity units and leave existing elapsed-time AI/animation clocks
  unchanged. Finite native replay checks pass; owner visual review is pending.
  Follow-up found variable pacing in a matched loaded encounter, so this does
  not satisfy exact Original FPS timing. Controlled tests isolate the native
  host-clock policy, which also applies to Original output; removing the flight
  correction alone restores the old speed-up. The separate diagnostic clock remains
  unqualified for default use: it also omits workload-dependent RSP/DMA time
  and still has loading-time audio gaps. Controlled original-ROM interventions
  isolate the device-time effect; reference-core timing tests prevent treating
  emulator agreement as hardware qualification.
  [Original timing follow-up](docs/development/issues/original-mode-simulation-parity.md).
  [Reference, implementation and limits](docs/development/issues/github-flying-enemy-speed.md).
- Recover omitted original SDK formatting functions in the generation pipeline.
  A sound-allocation warning exposed the missing integer-field helper; the
  transitive audit also recovered its floating conversion dependency. Loaded
  game bytes remain unchanged. Formatter execution and final native replays pass.
  [Cause and recovery](docs/development/issues/sdk-printf-field-metadata.md).

- Local review candidates for the remaining issue batch: restore Floyd objective
  cycling and Jeff's Arcade trap controls in Modern mode; add optional free
  movement and combat transparency settings; correct Proton fallback menu
  visibility and hosted mouse delivery. Defaults preserve existing behavior.
- Shorten qualified cutscene-skip fade waits while retaining native scene
  completion, loading and video-readiness checks. Three-part flight timing
  improves in normal Play; final owner review is pending.
- Preserve high-resolution screen sampling for native night vision and damage
  tint while keeping CPU shadow-mask ownership. Captured-frame GPU comparison,
  four-phase motion and ownership checks pass; owner route review is pending.
- Remove transparent icon borders in widescreen menus and smooth the authored
  title vignette without replacing game assets. Decoder/GPU and actual menu
  captures pass; owner batch review is pending.
- Include bounded launcher presentation details in support reports for black
  video with working audio. The reported Windows 10 failure remains unverified.
  Actual support-ZIP exports pass real-session and contaminated-file privacy
  checks. Keep each sanitized log within 64 KiB even when the input ends in a
  valid unterminated line at the exact limit.

- Prevent gems from drawing through fully opaque vine pixels while preserving
  transparent gaps and blended edges. Captured-frame GPU, material-state and
  normal-game checks pass; owner batch review is pending.
  [Cause and verification](docs/development/issues/vine-gem-occlusion.md).

- Add Actor LOD Original/High under Video Settings > Enhancements. High retains
  detailed actor models at a distance and applies live when saved. Original
  remains the default; Apply/Cancel, persistence and aligned help text are covered
  by launcher checks. High may increase rendering cost in crowded scenes.
  [Implementation and review](docs/development/issues/actor-lod-option.md).
- Smooth high-refresh cinematic camera motion by retaining the low angle bits
  lost by the original camera trigonometry. Preserve native results in Original
  FPS mode and for non-camera calls. Owner review confirms the space/Goldwood
  improvement and smooth Cerulean entry at 120 FPS.
- Preserve ship interpolation when attached engine geometry appears, and allow
  the first continuous scene to use its verified framebuffer/history before the
  display target has a prior-frame entry. Keep camera-cut, lifetime and target
  selection checks. Two repeated owner flight reviews passed.
- Correct the two mid-flight space-backdrop jumps during Goldwood departure by
  tracking the sky actor's camera transform separately from ordinary actors.
  The final operand order preserves native matrix validation; targeted replay
  and owner review pass. [Camera and flight findings](docs/development/issues/cutscene-camera-cadence.md).
- Correct Vela's apparent skirt separation on slopes during close-camera fading,
  including Original FPS. Resolve the nearest player surface into a separate
  layer and blend it once, preventing overlapping internal surfaces from showing
  through. Keep the fade consistent across focus changes and replace the initial
  screen-door pattern with smooth transparency. Native aim/death fades keep their
  existing path. [Cause and accepted remedy](docs/development/issues/vela-skirt-focus-tearing.md).
- Interpolate Vela's ship-underside light-beam motion and wrapped texture scrolling
  at high output rates. Preserve native animation speed and actual camera cuts.
  Targeted checks, controlled rendering comparison and owner review pass.
- Smooth travelling bullets and expanding grenade shockwaves by tracking their
  custom vertex buffers with the actual live projectile/effect and camera.
  Valid motion near the camera no longer fails solely because its projected
  screen displacement is large; real discontinuities still reject history.
  [Effect evidence and limits](docs/development/issues/high-refresh-shot-effects.md).
- Prevent drones and tribals from jumping sideways during camera turns when they
  reappear or change detail models. Unmatched geometry retains its current world
  pose while following the verified interpolated camera, without inventing an
  earlier pose. [Owner-verified correction](docs/development/issues/camera-turn-actor-jumps.md).
- Improve grenade-fire motion by keeping known sprite-transform identity stable
  when animated local mesh topology changes. Native texture/shape frame cadence
  is unchanged. The owner subsequently confirmed grenade fire visually; resolved
  locally and unreleased.
- Smooth opening exit-marker sparkles while turning the camera. The native marker
  sorts 20 persistent sparkles by camera distance and draws them through temporary
  transforms; tracking their logical slots prevents draw order from breaking
  interpolation. Owner review passed at 120 FPS. The cone's geometry was already
  interpolating. [Investigation and lessons](docs/development/issues/exit-marker-fire-cadence.md).
- Recover from a sustained host audio backlog after a temporary output stall
  while preserving normal buffering behavior. Component parity/fault checks,
  native audio suites and the owner's SS Anubis listening pass found no regression.
  The affected user on [#35](https://github.com/TK22-26/JetForceGemini-Recomp/issues/35)
  should retest when this change is available; affected-machine verification and
  the original trigger remain open.

- Correct reflected-model face culling and track mirrored skeletal poses separately
  from normal actor draws. Native checks and Goldwood replays pass at 120 FPS and
  Original FPS, and owner visual review passed. [Reflection findings](docs/development/issues/floor-reflection-geometry.md).

- Add Original/Enhanced Shadows under Video Settings > Enhancements. Enhanced
  uses filtered 512x512 maps from interpolated actor poses and authored light
  directions at each output frame. Shared pose bounds, sprite/detached-body
  casters and actual receiving geometry prevent the reproduced clipping, combat
  crash and double-shadow defects. It has no automatic Original fallback.
  Original remains the default and retains native silhouette cadence. The owner
  approved v26 visually; broader campaign/performance coverage remains open.
  [Evidence and limits](docs/development/issues/github-character-shadow-jitter.md).

### Findings and remaining verification

- The Goldwood wooden bridge’s dark ground strip is built into level vertex shading,
  using the same texture as brighter adjacent ground. The bridge has no native
  projected-shadow component; Enhanced actor shadows do not replace that static
  environmental shading. [Evidence and scope](docs/development/issues/enhanced-shadow-environment-scope.md).

- Correct the #45 assessment after the owner's October 31 NTSC hardware recheck:
  leaving Walkway also lacks music in the original. The local Walkway insertion
  is removed from current source, with scoped normal/skip and exit-chain replay checks.
  Older preview packages still contain the superseded insertion.
  The owner subsequently confirms music in PAL EmuHawk, establishing a regional
  difference for this route. PAL/Japanese native integration remains open;
  the two Vela routes remain
  unverified. Existing candidate tests prove the insertion, not its correctness
  relative to hardware. #45 remains open; no release is claimed.
  [Comparison record](docs/development/issues/flight-transition-missing-music.md).
- The #25 reporter confirms their rain, reticle and performance complaints are
  resolved in v1.4.0. The #40 reporter confirms Proton startup now works, but
  launcher menus remain blank; local Proton reproduction and a fix are still open.
  [Ally X retest](docs/development/issues/github-ally-x-rendering.md),
  [Proton follow-up](docs/development/issues/github-steam-deck-proton-startup.md).
- A Goldwood drone was observed below the floor near a broken hut. Saved actor
  state supports a native position/collision displacement, but the collision
  sequence and any difference from the original game remain unproved. No collision
  patch is included. [Evidence](docs/development/issues/drone-buried-after-hut-collision.md).
- Suspected muzzle-flash jitter, character shadows (#46),
  and the separate camera-fade activation report (#52)
  are not claimed resolved by these rendering fixes. See the
  [issue index](docs/development/issues/README.md) and [known issues](docs/known-issues.md).

## 1.4.0 - 2026-10-22

- Prevent scenery from interpolating through cinematic camera cuts when a distant
  shape incorrectly anchors the shared transform. Tawfret chief camera changes
  passed owner review at 120 FPS with logging off.

- Prevent cinematic camera-helper models from appearing as floating squares.
  This corrects an original-game artifact while retaining camera paths and
  scene state. Owner verified all three Tawfret chief shots at 120 FPS with
  diagnostics and FPS logging disabled. See the
  [investigation write-up](docs/development/issues/tawfret-chief-camera-and-square.md).

- Enable independent Modern controls for P1-P4 and correct Floyd co-op/mission
  fire routing, vertical direction and controller diagonal reach.
- Add mouse-steered Floyd flight with W thrust, S brake and A/D strafe, plus a
  separate controller flight-inversion option. Floyd changes are owner-approved
  locally; ask the original reporter to verify the delivered version.
- Prevent mixed wall/height collision corrections from collapsing the Modern
  mouse camera against the character.
- Smooth Quarry day/night fog-distance steps while retaining original cycle
  timing and colours; restore consistent tribal brightness.
- Complete the owner-reviewed cutscene skip batch, preserving native completion
  behavior. Keep unsafe/debug-only scene-selector entries out of normal gameplay;
  their diagnostic limitations remain documented.
- Process Give weapons requests safely while the Mods window pauses gameplay,
  and show actual grant acknowledgement instead of submission-only feedback.
- Refresh Live map Mods with separate toggles/actions, status feedback, accessible
  disabled/focus states and scalable local icon artwork.
- Show progress while verifying game files in both launcher surfaces.
- Add a conventional window-swapchain fallback when DirectComposition setup
  fails. Windows checks pass; Steam Deck/Proton verification still needs the reporter.
- Include bounded mouse input diagnostics in support reports for #32; this is
  evidence collection, not a claimed fix for intermittent mouse input.
- Update community credits and release documentation.

- Preserve Modern swimming camera orientation and native collision clearance,
  including overhead views. Keep native body facing through water-origin jumps
  to avoid snapping on surface departures and re-entry; owner-approved locally.

- Restore the original boss aiming range for Modern mouse and controllers,
  including both Mizar encounters. All five boss fixtures match EmuHawk in
  automated angle checks; owner-approved after live Twin Mantis review.

- Default Modern mouse vertical inversion to Off for new profiles and resets.
  Preserve existing saved choices and controller settings. This does not
  resolve the separate intermittent mouse-look/ineffective-Off report (#32).

- Restore Modern crouch/prone side rolls and correct backward-crawl reversal
  and diagonal motion during prone rolls. Preserve native roll speed and easing.
- Add bindable Roll Left/Right actions for Modern keyboard/mouse and controllers,
  plus an Advanced automatic movement rolling switch shared per player.
  New roll bindings default to unbound; automatic rolling remains enabled.
- Preserve removed-controller exclusions when changing input type and refresh
  idle P1-P4 indicators after saved controller changes. Owner preview review passed.
  Newly saved Modern profiles use schema 7; older versions require separate profiles.


- Prevent chopped sound-effect fragments while skipping Vela's rescue by omitting
  effect starts from intermediate shots in a confirmed skip chain. Preserve
  native cleanup, music and normal playback. Owner listening review passed.
- Clear launcher menu hover when entering the game while preserving dropdown
  selection across the child input window. Native UI checks and owner review passed.

- Show rain through supported room-entry fades instead of waiting for the fade
  to finish. Preserve fade masking and native gating for unsupported cases.
  Native/regression checks and owner visual review passed; reporter retest remains.

- Prevent depth-buffer readback from appearing as white/rainbow geometry in
  interpolated character-selection frames after the Vela/SS Anubis cinematics.
  Renderer regression checks and owner visual verification passed.
- Add an in-game cutscene skip prompt: A, B or Start reveals it; hold A for one
  second to confirm. Reviewed cinematics use explicit native completion and
  scene transitions, preserving progression and required music changes.
  Owner verified the SS Anubis flashback, Vela rescue, Juno departure and
  Tawfret introduction; unsupported scripts remain ineligible.
- Retain the Modern controller camera angle during ledge grabs, climbs and
  high-drop landing recovery, extending the existing mouse corrections.
  Automated checks and owner verification passed (#30).
- Preserve Modern view identity while neutralizing input during focus loss.
  The earlier correction passed owner testing. A follow-up initializes the new
  room camera while the map has focus, avoiding delayed takeover on clicking
  back. Controller/mouse regression checks and owner verification passed.
- Correct rain and software-drawn reticles disappearing during normal high-refresh
  Play because required output-frame timestamps depended on diagnostic logging.
  Regression checks pass with logging disabled; owner verified both effects.
- Keep removed controllers unassigned instead of automatically moving them to
  later player slots. Automated mapping/UI checks and owner review passed.
- Correct the fog gradient on large sky polygons, bringing Tawfret's sky and haze
  closer to matched original-game rendering. Preserve the gamma correction and
  fog percentage controls. Original-task comparisons and owner review passed.

## 1.3.0 - 2026-10-19

- Improve ship, village and Vela-rescue cutscene presentation and boss motion.
  Reduce redundant draw matching, upload allocation work, synchronous settings
  reads and live-map serialization stalls. Preserve the original game timing.
- Retain high-resolution scene images and interpolation through native blur
  effects. Add Off / Reduced / Original blur; Reduced is the default.
- Fix breakable-glass shaking and boss animation stepping during camera sweeps.
  Keep cutscene framing aligned with the game's saved widescreen option.
- Improve camera-relative interpolation of detached drone bodies and death
  animations with intentionally hidden bones.
- Preserve the mouse camera angle after high landings and ledge climbs.
  Restore the measured native standing-aim forward/strafe/diagonal speeds.
- Add Game > Settings > Change directory for portable saves, settings and
  imported ROM storage. Paths inside the game folder remain valid when it moves.
- Refresh Video Settings with tabs and add live fog strength from 0% to 100%.
  Update native window title bars to follow the Windows dark appearance.
- Let the exit-warp mod enter the next room regardless of progression gates.
  Add Map > Settings > Mods > Give all weapons as a one-click inventory/ammo grant.
- Retain the v1.2.1 boss-controls and source-scene FPS counter corrections.

Owner route and targeted visual review are complete; exact seeded parity is not
claimed. See the [release qualification](docs/releases/qualification-1.3.0.md)
for validation evidence and limits.
Reporter-specific reticle/hut behavior and the exact invasion-replay report
await v1.3 retests; see [known issues](docs/known-issues.md).

## 1.2.1 - 2026-10-18

- Fixed modern boss controls losing movement, strafing and separate mouse/controller aiming. Playable boss combat and jumps now retain their configured actions; actual cutscene, pause and death ownership remain intact. Owner playtests passed Vela/Ichor, Juno and Lupus.
- Fixed map exit warps stopping at a door: eligible warps now enter the next room through the native transition, preserving progression requirements.
- Corrected the scene FPS counter counting a second full-screen blur pass at the same source tick. Output FPS is still measured separately.
- Cutscene/boss motion-blur resolution loss, presentation stalls and the earlier long-route audio underruns remain open for 1.3. The controls hotfix includes no experimental rendering changes. See [the 1.3 follow-up](https://github.com/TK22-26/JetForceGemini-Recomp/issues/21).

## 1.2.0 - 2026-10-16

- Added smooth high-refresh rendering with VSync, Custom FPS and Unlimited in
  native Video Settings. Game timing remains independent of presentation rate.
  Character, camera, scenery, pickup and bridge interpolation are improved.
- Reduced combat CPU work and renderer cache stalls; improved audio delivery and
  ROM sample loading. Owner playtesting reports stable gameplay. Unlimited pacing,
  exhaustive no-dip coverage and the reported Goldwood exit-cutscene audio hitch
  remain under investigation; a high output counter is not a game-update guarantee.
- Added the full Modern Controls editor, mouse look and dual-stick aiming, shared
  action bindings, visible menu/dialogue bindings and independent inversion settings.
  Corrected crouch mouse inversion, shuriken reticle loss and resting shuriken jitter.
- Fixed the experimental keyboard/mouse startup crash by initializing game memory
  before controller discovery. The v1.1.0 crash is reproduced with keyboard selected.
- Made native execution-probe declarations and volume-file reads portable to GCC.
- Improved legacy Windows source setup: detect disabled firmware virtualization,
  refresh old WSL distribution support, and distinguish installer failures from
  actual restart requests. Normal ZIP installation still requires no build tools.
- Added an amber update banner below Play when GitHub has a newer stable release.
  **What's new** opens the project page; **Update now** opens the release/download
  page. Checks run in the background and never install updates automatically.

Extract the complete Windows x64 ZIP into a new folder. Existing saves and settings
remain in your profile. Modern gameplay and high-refresh rendering remain opt-in.
See [known issues](docs/known-issues.md) for compatibility and qualification limits.

- Added background stable-release checks, a persistent home-screen update notice,
  and **Help > Check for updatesâ€¦** with installed/latest versions and a release link.
  Offline checks leave gameplay available; downloads are never installed automatically.
- Refreshed the README and rebuilt the project dashboard around the fully playable
  v1 game, with modern-controls highlights, AI assistance credit and a startup image.

## 1.1.0 â€” 2026-10-09

- Fixed the embedded game's aspect ratio. Gameplay stays in a centered 4:3
  display area when the launcher is wide, resized, maximized, or fullscreen.
  Cutscenes retain their own top and bottom bars instead of expanding across
  the launcher window. The original game's graphics and widescreen option
  are unchanged.
- Added one-time ROM import. Select a supported ROM once; the launcher verifies
  and copies it into the local game profile. Future launches use that copy,
  so the original file can be moved or deleted. Invalid imports preserve the
  previous copy. Existing valid ROM selections are imported on upgrade.
- Removed the central ROM card after a successful import. **Game > Select ROMâ€¦**
  remains available to select another file.
- Replaced the first-run local build with a prebuilt Windows x64 game bundle.
  Players no longer need Git, Python, Visual Studio Build Tools, WSL, or a
  first-run compilation. Required Microsoft runtime DLLs are included.
- Added a clear message when only software graphics are available, avoiding
  the stalled startup and excessive memory use observed in the test VM.
- Added package integrity checks, a ROM-import regression test, and viewport
  coverage for 4:3, 16:9, ultrawide, portrait, and odd-sized windows.

Download and extract the complete v1.1.0 ZIP into a new folder. Open
`JFG-Launcher.exe`, use **Select ROMâ€¦** if prompted, and click **Play**. Existing
saves and settings remain in the same profile. The ZIP contains the compiled
program and its runtime libraries; **no ROM or game assets are included**.

The simplified installation approach was inspired by the
[Zelda64Recomp team and its plug-and-play model](https://github.com/Zelda64Recomp/Zelda64Recomp#plug-and-play).
This is an independent implementation.

## 1.0.0 â€” 2026-10-09

Initial stable release with the unified launcher, configurable controllers,
live map and inventory, and the recorded rendering and audio fixes. The v1.0.0
installer built the game locally from the player's ROM and required developer
tools. See the [v1.0.0 release](https://github.com/TK22-26/JetForceGemini-Recomp/releases/tag/v1.0.0).

Owner review on October 27: Enhanced Shadows preview v26 visually approved ("shadows look good now"); unreleased. See [shadow investigation](docs/development/issues/github-character-shadow-jitter.md).
