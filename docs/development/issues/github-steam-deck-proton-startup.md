# GH-040: Windows release does not start through Steam Deck Proton

## Candidate correction delivered for retest - 2026-11-07

Status: corrected source with Windows/Proton integration verification; owner
Bazzite/NVIDIA and Steam Deck acceptance pending. Unreleased and uncommitted.
Updated private package: `E:/JFG-Issue-40-Bazzite-20261107`, with `E:/handoff.md`.
Launcher SHA-256: `a5fe71ccc1a1989ca2f377f556c31a4d7c0ea4d7411459e74a9f6bfd2cd04dfc`. Base develop `067f9a8` plus local UI changes;
`game/launcher-build.json` pins the exact input hashes. Regional runtimes unchanged.

The actual source cause was fallback capture explicitly hiding the hosted game
viewport. An opaque root HWND swap chain could not provide the intended overlay.
[`fallback_overlay.hpp`](../../../launcher/ui/fallback_overlay.hpp) now presents
the panel rectangle in an owned, nonactivating popup with its own HWND swap chain
on the UI device. The viewport remains visible; root capture and coordinate
forwarding handle popup clicks. Cancel/deactivation releases capture and dismisses
dropdowns. The default DirectComposition route remains in use where available.

Final checks: 116 Windows composition and 165 fallback menu checks; 165 actual
GE-Proton11-11 checks; 70 ROM-library and 247 Video checks on both platforms.
The fixture asserts hosted-game visibility, bounded popup coverage, actual popup
swap-chain HWND, forwarded selection, cancellation and existing resize/input
behavior. The actual final launcher naturally selected the window backend under
Proton, initialized its helper and exited cleanly. Also passed: 778 managed,
28 mocked setup, graphics/viewport/storage checks. Windows ROM/search framebuffer
images were inspected at representative 100/125/150 percent scales.

Proton environment: WSL2 Ubuntu24.04, GE-Proton11-11 x64, umu1.4.4, steamrt4
4.0.20261021.265997, DXVK3.1.1 and llvmpipe25.2.8 software Vulkan. These are
integration checks with synthetic hosted windows, not actual Bazzite/RTX4070
game pixels, physical-pointer or Steam Deck acceptance. Fullscreen/focus and
normal gameplay retests remain in the owner checklist.

The updater preserves saves/settings/runtimes/notes and backs up replaced files.
Before replacement it copies existing results archives and collects current logs
back to USB. Repeated Linux fixture updates and corrupt-payload refusal pass;
USB payload hashes and unchanged original ROM/other files are verified. Old
launcher files are in `previous-build/`. No owner logs were present on E: during
this review, so the opening [skip](cutscene-skip-completion-time.md) and
[audio](opening-invasion-audio-proton.md) reports remain unlocalized.

Private evidence: `gh40-ui-fixes-20261107`. A first layout candidate collapsed the
button text and was rejected on framebuffer review; a final capture-cancellation
edge was corrected and retested. One orchestration assertion failed after partial
edits; follow-up steps verified the resulting source. These are retained attempts,
not hidden clean-run claims. The production guard remained enabled on the same
investigation with counters preserved. No commit, push or public issue action.

Lesson: testing menu pixels alone missed the simultaneous gameplay requirement.
Assert both window visibility and presentation ownership, then obtain actual
hardware acceptance. The earlier sections below describe superseded checkpoints.


## Owner retest: menus render but hide gameplay - 2026-11-07

**Status: incomplete; owner reports a remaining Proton presentation defect.**
After the Bazzite handoff, the owner reports that opening a dropdown hides the
game and blacks out the rest of the window, leaving only the menu visible. The
launcher start screen is not hidden by the same action. The owner identifies
this as the platform-specific finding; the separately reported ROM-button/search
layout and About-opening delay also affect Windows.

The test context is the supplied private bundle for Bazzite x64 with an RTX 4070,
launcher source `067f9a8` and v33 game runtimes. Exact installed Proton version,
in-game location, capture settings and repetition counts were not supplied in
this feedback. The menu screenshot shows readable entries over the start screen;
the gameplay blackout is described by the owner, not independently replayed here.

The source directly explains the difference. In
[`sync_ui_capture_windows`](../../../launcher/native/ui_capture_windows.hpp),
the non-composited backend shows the hosted viewport only when `!capturing`.
[`syncUiCapture`](../../../launcher/native/frontend_win32.cpp) includes ordinary
dropdown capture in that flag. The start screen belongs to the launcher's own
surface; gameplay belongs to a separate hosted child window. Hiding that child
therefore removes the game, while an opaque fallback swap chain cannot expose it
through the transparent playing background.

The prior correction fixed missing menu contents, but did not provide an overlay
over visible gameplay. The existing menu fixture explicitly expects the fallback
to hide the viewport during capture; its 105 passing checks accepted this
limitation. They must not be cited as verification that gameplay stays visible
behind menus. The earlier source/Proton results remain valid for their narrower
menu-content and input checks. No full owner acceptance or #40 closure is claimed.

Required correction: present usable menus above the hosted game while retaining
the game outside the menu bounds, including dismissal, focus, resize and
fullscreen transitions. Simply keeping the child visible under the root's
opaque swap chain would reintroduce clipping; the presentation arrangement needs
to support both surfaces. Add a regression that asserts visible gameplay outside
the open dropdown, not just rendered text in the menu buffer. No implementation
or new execution has occurred for this report; the production guard remains
enabled and shelved after the completed handoff scope.

Evidence: owner feedback and three screenshots retained in private artifact
`gh40-owner-feedback-20261107`; hashes and shared UI findings are in
[launcher layout](launcher-rom-and-search-layout.md) and
[About-window delay](launcher-about-window-delay.md). The USB handoff and binary
hashes are preserved as the tested baseline; no updated USB build is claimed.

## Current qualification and owner handoff - 2026-11-07

The known blank-menu defect is fixed in current source and freshly verified in
the launcher built from `067f9a898ceff90b789e0af779693f6cdc64a300`. The correction
was consolidated in `279fce1`: the HWND backend hides the invisible input shield
and routes input through the root window; DirectComposition retains its overlay
shield. The added November 7 audio-support exporter fix is also in this launcher.
No additional runtime or launcher code change was required for this handoff.

Fresh Windows verification passed 778 managed checks, 28 mocked setup checks,
graphics/viewport/storage checks, 104 composition menu checks and 105 fallback
menu checks. Actual GE-Proton11-11 x86_64, umu 1.4.4 and steamrt4
4.0.20261021.265997 on WSL2 Ubuntu 24.04 passed all 105 fallback UI checks,
including rendered menu text, selection, resize and repeated viewport/input
transitions. That fixture forces unavailable composition. A separate probe of
the actual production launcher naturally selected `backend=window` with
`composition_hresult=0x80004001`, initialized its real helper and exited cleanly.
The shipped helper's init, USA ROM import and complete runtime verification also
passed under Proton. No full-game Linux session or Bazzite/NVIDIA hardware pass
is inferred from those checks.

The owner identified an available **Bazzite x64 PC with an RTX 4070**. A private
test bundle, pinned Proton archive, integrity manifest, setup/log-collection
scripts and `handoff.md` were copied to the requested E: drive and hash-verified.
It contains the current launcher plus the verified v33 USA/PAL/JP runtimes used
in v35, with fresh profile creation and no copied personal saves. The existing
USA ROM on the drive was verified and preserved. Owner gameplay/menu/settings,
save/restart and input testing on Bazzite is pending; Steam Deck reporter
verification remains separate. No GitHub reply, closure or release occurred.

The first UI fixture invocation rejected an existing output directory before
testing; fresh-directory execution passed. Initial Linux staging stopped because
WSL did not mount removable E:, corrected by private staging of the verified ROM.
The test's accessibility/D-Bus services briefly held the private image mount;
only services carrying that exact test home/runtime environment were stopped,
and unmount succeeded. These were test-harness issues, not game regressions.

Evidence: private artifact `gh40-bazzite-handoff-20261107`, including
`package-verification.json`, `proton-result.json`, `proton-menu-result/result.json`,
`production-launcher-result/result.json`, `linux-cleanup.json` and
`delivery-result.json`. The E: bundle includes compact verification receipts.
The production guard remained enabled with the same investigation/root and all
prior counters, under the explicitly approved 60-minute/three-attempt scope.

Earlier dated sections below retain historical status and verification limits.


## Delivery and issue status â€” 2026-10-22 UTC

The Windows-tested launcher fallback ships in v1.4.0. On October 22, the reporter confirmed that the latest Windows release now boots through Proton on Steam Deck and displays gameplay. Launcher menus still replace gameplay with a blank background; toggling the menu returns to gameplay. #40 remains open for this unresolved menu rendering failure. Full Deck compatibility and a native Linux release are not claimed.

[Release v1.4.0](https://github.com/TK22-26/JetForceGemini-Recomp/releases/tag/v1.4.0); [verified issue action](https://github.com/TK22-26/JetForceGemini-Recomp/issues/40#issuecomment-6332078795).
Earlier entries below preserve their original investigation and verification scope.

### Reporter retest and local feasibility review, October 23 UTC

[@chaberl-art's October 22 report](https://github.com/TK22-26/JetForceGemini-Recomp/issues/40#issuecomment-6349698249)
narrows the failure from startup to launcher menu contents. Clicking a top menu
shows a solid grey/blue menu background, and clicking again restores gameplay.
SteamOS version, Proton version, Gaming/Desktop Mode and a Proton log are still
unspecified. Severity remains high because launcher settings are inaccessible.
No local Proton reproduction or new rendering remedy is verified.

The existing HWND fallback hides the hosted game window while showing opaque
launcher UI. The reported hide/restore behavior makes this presentation boundary
a useful investigation target, but does not establish which backend ran or why
the menu contents disappeared. Passing Windows fallback tests did not qualify
the actual Wine renderer. Capture the backend/HRESULT and Proton output before
attributing the failure to a specific draw or compositor operation.

Read-only host inventory found Windows 11 Pro, an RTX 5090, a running hypervisor,
installed Hyper-V tools and running Hyper-V services. Both Get-VM and Get-VMHost
returned a permission error, so available VMs and their graphics capabilities
could not be inventoried. Three existing Ubuntu WSL2 distributions were stopped.
No VM/distro was started, no package installed and no Proton test performed.

Microsoft does not support Hyper-V DDA/GPU-P on Windows 11 client hosts; this is
an official support limitation, not proof that every community configuration is
impossible. The game's D3D12 path also needs the Vulkan features required by
vkd3d-proton. A Linux VM or WSLg may still help isolate launcher behavior, but
guest graphics support must be measured before drawing game compatibility or
performance conclusions. WSLg's documented accelerated OpenGL support alone
does not establish the required Vulkan support.

References: [Microsoft Hyper-V GPU support](https://learn.microsoft.com/en-us/troubleshoot/windows-server/virtualization/troubleshoot-hyper-v-gpu-assignment-partitioning-passthrough-issues),
[WSLg graphics prerequisites](https://learn.microsoft.com/en-us/windows/wsl/tutorials/gui-apps),
[vkd3d-proton driver requirements](https://github.com/HansKristian-Work/vkd3d-proton#drivers).

Further execution requires an owner-authorized continuation of the existing
guarded investigation; the production guard is enabled and the prior allowance
is exhausted/shelved. Preserve its counters. Keep any new VM disks, prefixes,
downloads and evidence on D:. The next bounded task is to establish an accessible
Linux graphics environment, record exact versions/capabilities, and attempt the
released launcher/menu sequence with an isolated profile. A successful local
test would still need reporter verification on Steam Deck.

Private evidence: `post-v14-issue-review-20261023/issue-40.json`. A reply requesting
the missing platform details and a menu-opening Proton log is prepared for
owner review. No GitHub response, title change or closure was made.

The owner subsequently requested local fix work before replying to #40. Hold
the proposed information request; no response is authorized. The local test
plan and its access/guard blockers above remain in effect.

- Severity: high for the reported platform; launch is blocked.
- Status: local candidate; Windows and actual Proton UI verified; Steam Deck reporter review pending.
- Reported and reviewed: 2026-10-21 UTC.
- Source: [GitHub #40](https://github.com/TK22-26/JetForceGemini-Recomp/issues/40),
  by @chaberl-art, created 17:18 UTC.
- Reported build/profile: v1.3.0 Windows release on Steam Deck through Proton.
  SteamOS version, Proton version, Deck model and launch configuration unspecified.

## Symptoms and reproduction

The Windows release does not run on Steam Deck using Proton, on every attempt.
The report does not say whether the launcher fails to open, ROM import fails,
Play fails, or a game window opens and exits. No error, support ZIP or Proton log
is attached. No local Proton launch attempt was made in this review.

## Evidence and hypotheses

Private issue/comment snapshot:
`github-follow-up-review-20261021T204709Z/github-issues.json`.

The [published package targets Windows x64](../../known-issues.md#open-problems-and-verification-still-needed).
Proton compatibility is unqualified. This is distinct from
[#15's native Linux/GCC source-build failure](github-linux-native-build.md);
the released compiler corrections do not establish Windows-package compatibility
under Proton or a supported AppImage. No particular dependency, graphics backend
or Proton version is established as the cause.

## Attempts and results

| Date | Action | Result |
|---|---|---|
| 2026-10-21 | Read the report and compare recorded platform qualification | Recorded Proton startup separately from native Linux build status; no compatibility experiment or workaround claimed |

## Actual resolution

Pending. No fix, tested workaround, compatible Proton version or release is claimed.

## Verification and remaining limits

Before selecting a guarded reproduction, collect the failing stage, exact error,
SteamOS/Proton versions, package/launcher identity, launch command or Steam shortcut
target and working directory. A Proton log and support ZIP, if the launcher opens,
would supply evidence. Record Desktop versus Gaming mode and confirm that the
whole package was extracted. Any changes should be tested with copied data and a
separate compatibility prefix; preserve existing imported ROMs and saves privately.

Do not promise a Linux release or speculative compatibility override. Any future
experiment must use the production supervisor and its existing admission limits.

## Lessons for future changes

Separate native compilation, packaged Windows execution and Proton compatibility.
Identify the failing startup stage before assigning a cause or proposing fixes.

## October 21 source review and native Linux alternative

The owner asked whether a native Steam Deck build could bypass Proton. A native
Linux x86-64 game would remove the Windows compatibility layer, but current
develop cannot produce the current playable release through a build-option
change alone.

The v1.3.0 source was inspected at commit
635d9652e0a1aaf8a00247ddf4160cc23a21171b. The launcher has a native Win32/D3D11 UI
and embeds a .NET Framework helper compiled by Framework64/v4.0.30319/csc.exe.
It extracts that helper and starts it as a separate process for setup and Play.
Graphics enumeration, profile creation, helper launch and the native game's
startup are distinct failure stages. These are compatibility boundaries to
diagnose, **not established causes of #40**. No Proton execution was performed.

Current develop still has Windows-specific live runtime integration and a
non-Windows native-runner exit reporting process isolation unavailable. The
existing Ubuntu CI host-library checks do not establish a playable Linux build.

An earlier Linux implementation is recoverable from the #15 reporter's fork:

- [Compiler fix 2a117d8](https://github.com/Mabec-games/JetForceGemini-Recomp/commit/2a117d8f230c092160e51f4274f658274b37ba83),
  whose parent is original Linux commit 8b6837d685f12efcd22339c757cb8e8d22480da6.
- Its Linux documentation/source includes POSIX memory mapping, device-trap
  signal handling, process isolation, SDL window/input/audio and RT64 Vulkan.
- The #15 reporter claims gameplay with audio after the compiler fix. That is
  external owner evidence, not a local or Steam Deck verification.
- Its AppImage contains source and compiles on the user's machine on first run.
  It is not a ready-to-play prebuilt equivalent of our Windows release.
- Its launcher, live map and inventory windows remain Windows-only.

The useful implementation path is to recover and audit that platform layer,
integrate it with current controls, timing and rendering fixes in an isolated
checkout, build a precompiled Linux runtime with a portable ROM-import entry,
and verify gameplay/save/load/audio/input on Deck. Launcher feature parity is
additional work. A native preview can be a separate deliverable; the Proton
report remains open until a reproduced fix or reporter-tested alternative.

Local WSL inventory lists Ubuntu, Ubuntu-22.04 and Ubuntu-24.04. Only environment
inventory was read; no Linux build, dependency installation, port integration
or hardware test was run. Private pinned evidence is in
gh40-proton-review-20261021/fork-source-identity.json and source-review.json.

Valve recommends Vulkan for Deck graphics and identifies platform-specific
launcher frameworks as a compatibility concern:
[Steam hardware recommendations](https://partner.steamgames.com/doc/steamhardware/recommendations).
This supports the proposed platform direction but does not prove our performance.

The original missing-evidence request remains useful for #40: exact failing
stage, SteamOS/Proton versions, launch target, visible error and a Proton log.
Valve documents PROTON_LOG=1 and its default home-directory steam-APPID.log:
[Proton runtime options](https://github.com/ValveSoftware/Proton#runtime-config-options).
No GitHub reply, closure or release promise has been sent.

## October 21 Proton-first candidate

The owner deferred native Linux work after finding that a fork already pursued it.
Only Windows-package Proton compatibility is in scope for this continuation.
No native port, package, dependency installation or Linux build was started.

A concrete launcher incompatibility was found before the managed helper starts:
published v1.3.0 requires DirectComposition in FrontendUiInit; failure makes
WM_CREATE return -1. Valve's Wine source pinned by Proton 11 at
[e60892cc](https://github.com/ValveSoftware/wine/blob/e60892cc2398b0a83c332a2078c7b85e47bdb42b/dlls/dcomp/device.c)
returns E_NOTIMPL from DCompositionCreateDevice. That is a source-confirmed
incompatible startup path, but the reporter has not supplied their Proton
version, log or failing stage, so it is not yet the confirmed cause of their
particular launch failure. Wine Mono, helper process creation and the D3D12
game runtime remain later compatibility boundaries, not diagnosed failures.

The candidate in launcher/ui/native_ui.cpp tries composition first and, if
unavailable, uses CreateSwapChainForHwnd with an opaque, discard swap chain.
A capability check is used instead of a Wine-name override. Windows retains
composition when supported. frontend-presentation.log (and each tool's
presentation log) records the selected backend and composition HRESULT locally.
This log is not currently included in the sanitized support ZIP.

In launcher/native/frontend_win32.cpp, the HWND fallback temporarily hides the hosted
game viewport while a launcher menu or dialog captures input, then restores
the same viewport. It cannot place transparent UI above the game child the way
DirectComposition does. This interaction and actual Deck gameplay still need
live verification; no performance or visual-parity claim is made.

jfg_proton_presentation_ui_tests injects E_NOTIMPL only into the test target.
It uses the same UI integration checks as the normal composition test, verifies
the fallback owns the real launcher HWND, presents and resizes, and exercises
menu selection and verification feedback. The production executable has no
failure-injection switch. These Windows tests are not a Proton execution.

Private evidence: gh40-proton-review-20261021/candidate, including original
source hashes, build log and per-target test results. Local WSL Ubuntu and
Ubuntu-24.04 currently have no Wine/Proton installation on PATH; no compatibility
prefix or Steam Deck run was performed. No running preview or release package
was replaced, and no issue reply or closure was posted.

Next verification is a copied package/profile in a separate Proton prefix:
launcher startup, ROM import/verification, Play, game rendering/input/audio,
menu/dialog open-close and save/restart. Capture exact Proton/SteamOS version
and PROTON_LOG=1 output. Keep #40 open until that evidence is available.

Transferable lesson: optional compositor APIs must not be mandatory to start
a launcher when window rendering is sufficient; compatibility needs separate
checks for launcher, managed helper and game rather than one platform label.

### Candidate verification result

At 2026-10-21 21:32 UTC, the Release launcher build passed, the normal
DirectComposition UI suite passed 85 checks, and the injected-E_NOTIMPL HWND
suite passed 86 checks. These cover initialization, presentation, resize,
menu hover/selection and file-verification feedback. The injected target emits
a compile-time constant-condition warning; no build or test failed. Backend
logs confirm directcomposition/0x0 and window/0x80004001 respectively.

The compiled launcher is preserved privately with its embedded helper hash and
source-before hashes. It is not a complete distributable package and was not
installed over the user's preview. The game's rendering/input/audio, hosted
game-child hide/restore, Wine Mono helper execution, and actual Proton
compatibility remain untested. There is no released resolution or commit yet.

The owner has no Steam Deck. Hardware verification must involve the reporter;
a draft requesting Proton/SteamOS details and willingness to test is saved
privately for owner review. No GitHub comment, closure or upload is authorized.

## October 27 blank-menu follow-up

The reporter now reaches gameplay in v1.4.0, but opening launcher menus shows a blank grey/blue region until closed. Local source review identified that the non-composited HWND swap chain still receives a visible input-shield child over the client area. The root has WS_CLIPCHILDREN; that shield is useful only when DirectComposition can place UI above child windows. A backend-aware input surface is being qualified. This is a source-supported candidate, not yet reporter verification. An isolated GE-Proton 11-11 / umu 1.4.4 environment is being prepared on D:; this machine is not Steam Deck hardware.

### October 27 local qualification

The candidate now uses a shared backend-aware capture-window helper. The HWND backend hides its unpainted input shield and sends menu input to the root; DirectComposition retains its shield. Visibility is synchronized even if the settings state was changed before the synchronization call. Closing the menu restores the same hosted viewport and game focus.

Windows Release suites passed 100 normal-composition and 101 HWND-fallback checks, including real hosted game/shield children across repeated menu open/close. The launcher rebuilt successfully. Under actual GE-Proton11-11, umu 1.4.4 and steamrt4 4.0.20261021.265997 on WSL2 Ubuntu 24.04, a natural probe returned DComposition E_NOTIMPL and selected window presentation. The fallback integration suite then passed all 101 checks, including presentation, resize, menu selection and host-window visibility.

The first natural Proton test failed only its Windows-specific assertion requiring composition; initialization itself succeeded. That informative failure and the passing fallback run are retained in remaining-gh-issues-20261027/proton evidence. The isolated Linux prefix/runtime/cache resides in a D: backed ext4 image, runs as an unprivileged account, and does not replace the owner's launcher or profile.

This validates the concrete menu host defect in an actual Proton runtime, not Steam Deck hardware, the managed launch helper, full game compatibility, or every Proton release. Reporter verification remains pending. No GitHub action was taken.

Transferable lesson: a child used only to intercept input for composited content must not cover a non-composited swap chain; integration tests need the host's actual child hierarchy, not only the UI renderer.

### Host-style and pixel qualification

November 7 owner follow-up: after the updated USB handoff, the owner reports
everything looks good except unusually long cutscene skips. Record this as
positive Bazzite feedback, without inventing individual checklist results or
Steam Deck acceptance. The returned archive identifies the original launcher,
not the latest USB candidate, so the tested build remains unconfirmed. See the
[archive receipt and skip follow-up](cutscene-skip-completion-time.md#returned-archive-and-owner-feedback)
for hashes, capture limits and collection instructions. No public issue closure.

Subsequent manual transfer succeeds: the 10:07 UTC collector archive identifies
the latest `e35e7769...` launcher installation and contains a newer USA session
from 09:17 UTC, normal shutdown, and About/presentation logs. CRC and private-copy
hash checks pass. This supplies current-build evidence alongside the owner's
positive Bazzite UI feedback. Individual checklist items and Steam Deck reporter
verification are still not inferred; the cutscene skip report remains open.

The integration fixture now includes the launcher's WS_CLIPCHILDREN style, which the earlier simplified window omitted. It also reads back menu pixels and checks for rendered text, retaining the three-cycle child visibility/focus checks. Windows composition passes 104 checks; Windows HWND fallback and actual GE-Proton pass 105 each. Captured menu images are retained privately for review. These checks establish rendered menu content and the correct host hierarchy; they still do not substitute for a Steam Deck hardware pass.

November 8 owner follow-up: the owner manually tested the current mouse behavior
on Bazzite and reports it fully working. This complements the earlier positive
Bazzite UI feedback and accepted opening-skip improvement. It does not substitute
for the Steam Deck reporter check or individually verified checklist coverage.
See the [mouse acceptance record](proton-mouse-confinement.md#owner-acceptance-2026-11-08).

## November 9 comparison with #58

The current renderer API candidate re-runs Windows composition/fallback and
actual isolated GE-Proton menu checks. Game visibility, popup presentation and
menu pixels continue to pass. The earlier blackout was caused by hiding the
hosted viewport during fallback capture, corrected by the owned-popup path; it
does not establish a D3D12/Vulkan game-renderer failure. [#58's follow-up](github-black-screen-audio.md)
adds separate requested/selected API, setup and presentation-result evidence and
a standalone comparison. No new Bazzite or Steam Deck hardware approval is
inferred. Private evidence: `renderer-api-20261109/proton-results.json`.
