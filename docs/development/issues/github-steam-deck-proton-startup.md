# GH-040: Windows release does not start through Steam Deck Proton

- Severity: high for the reported platform; launch is blocked.
- Status: source-confirmed startup incompatibility; HWND presentation candidate implemented. Windows build and both backend UI suites passed; actual Proton/Deck and reporter verification pending.
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

The [published package targets Windows x64](../../known-issues.md#platform-and-support).
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

In src/app/frontend_win32.cpp, the HWND fallback temporarily hides the hosted
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
