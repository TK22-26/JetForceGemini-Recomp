# Community credits

Git history retains authorship of contributed code. This list also acknowledges
issue reports, playtesting, and investigations that help improve the project,
including work on unresolved issues.
Dependency attribution remains in [third-party notices](THIRD_PARTY_NOTICES.md).

## Luke Deardoff (@lukedeardoff)

- Reported Windows 10 setup failures involving firmware virtualization, WSL,
  PowerShell 5.1, and long submodule paths, with working recovery steps in
  [issue #4](https://github.com/TK22-26/JetForceGemini-Recomp/issues/4).
- Reported and investigated the opening asteroid texture corruption, including
  the stale texture-offset addresses reproduced in [PR #9](https://github.com/TK22-26/JetForceGemini-Recomp/pull/9).
  His trace identified the incorrect texture addresses and guided the correction.
  See [findings](docs/development/boot-gameplay-fix.md#opening-asteroid-textures).
- Reported the fresh-build recovery failure and proposed allowing external build
  caches while retaining restrictions inside the checkout, in his
  [community branch](https://github.com/lukedeardoff/JetForceGemini-Recomp/tree/c8253db8b70c7e2fd166bc9efcd7d101f2d3c819).
  The recovery helper incorporates that output-policy correction with regression
  coverage for external caches, existing files, and checkout boundaries.
- Shared a lens-flare depth-check diagnostic in his community branch. An
  adaptation helped identify missing CPU-visible depth data in the opening
  cinematic; the effective-RDP-state correction was implemented independently.
  See [depth findings](docs/development/boot-gameplay-fix.md#opening-lens-flare-occlusion).

## @ghettowario

- Reported the right-stick camera inversion usability problem and requested a
  configurable vertical direction in
  [issue #13](https://github.com/TK22-26/JetForceGemini-Recomp/issues/13).
- Reported severe slowdown during the opening invasion replay, including the
  affected scene, hardware, and frame-rate settings, in
  [issue #19](https://github.com/TK22-26/JetForceGemini-Recomp/issues/19).

## @GigaWerts

- Reported the Windows 11 startup failure when experimental mouse look was
  enabled before launch, identified a workaround, and supplied a support report
  in [issue #14](https://github.com/TK22-26/JetForceGemini-Recomp/issues/14).

## @Mabec-games

- Reported the Linux AppImage's GCC compilation failure caused by MSVC-only
  `__declspec(noinline)` declarations and supplied a portable correction tested
  on the Linux branch in
  [issue #15](https://github.com/TK22-26/JetForceGemini-Recomp/issues/15).

## @jd002065-del

- Reported held targeting cancelling on fire and the missing aimed diagonal
  movement advantage with keyboard/mouse in
  [issue #18](https://github.com/TK22-26/JetForceGemini-Recomp/issues/18).
  Retested v1.2.0, confirming that targeting cancellation was gone while the
  movement issue remained, and offered further playthrough testing.

## @KongBongo

- Reported controls failing on entry to the Ichor Military Base boss room,
  provided reproduction details across input modes, and attached a support
  report in [issue #20](https://github.com/TK22-26/JetForceGemini-Recomp/issues/20).

## @TK22-26 (maintainer)

- Reported and consolidated cutscene and boss stutter, motion-blur resolution
  loss, and audio interruptions, with captured evidence and follow-up criteria,
  in [issue #21](https://github.com/TK22-26/JetForceGemini-Recomp/issues/21).


## v1.4 community reports and testing

Thank you to the following reporters and testers. These credits acknowledge
feedback, requests and evidence, including reports still under investigation.

- @Tasosgemah - portable storage, skippable cutscenes, ledge camera behavior,
  audio latency, Floyd controls and crosshair follow-up
  ([#24](https://github.com/TK22-26/JetForceGemini-Recomp/issues/24),
  [#30](https://github.com/TK22-26/JetForceGemini-Recomp/issues/30),
  [#31](https://github.com/TK22-26/JetForceGemini-Recomp/issues/31),
  [#35](https://github.com/TK22-26/JetForceGemini-Recomp/issues/35),
  [#37](https://github.com/TK22-26/JetForceGemini-Recomp/issues/37)).
- @duke912 - Ally X performance, rain and weapon-reticle reports
  ([#25](https://github.com/TK22-26/JetForceGemini-Recomp/issues/25)).
- @drencoss - fog controls, portable-storage support and cutscene follow-up
  ([#26](https://github.com/TK22-26/JetForceGemini-Recomp/issues/26),
  [#24](https://github.com/TK22-26/JetForceGemini-Recomp/issues/24),
  [#19](https://github.com/TK22-26/JetForceGemini-Recomp/issues/19)).
- @GsxRoarK4 - additional cutscene performance feedback
  ([#19](https://github.com/TK22-26/JetForceGemini-Recomp/issues/19)).
- @Bighead-SMZ - mouse-look reproduction details, support data and comparison videos
  ([#32](https://github.com/TK22-26/JetForceGemini-Recomp/issues/32)).
- @yodaxy - missing Modern movements and rolling feedback
  ([#33](https://github.com/TK22-26/JetForceGemini-Recomp/issues/33)).
- @impmallet - Twin Mantis aiming-range report and reference
  ([#34](https://github.com/TK22-26/JetForceGemini-Recomp/issues/34)).
- @GenesisEB - missing weapon crosshairs
  ([#36](https://github.com/TK22-26/JetForceGemini-Recomp/issues/36)).
- @azjsales01-stack - Fet-Bubb crash report and diagnostic attachment
  ([#38](https://github.com/TK22-26/JetForceGemini-Recomp/issues/38)).
- @marvin-SL - Give all weapons failure and discoverability feedback
  ([#39](https://github.com/TK22-26/JetForceGemini-Recomp/issues/39)).
- @chaberl-art - Steam Deck/Proton startup report
  ([#40](https://github.com/TK22-26/JetForceGemini-Recomp/issues/40)).
- @EnforcerRidley - community feedback and testing, acknowledged by the maintainer.
