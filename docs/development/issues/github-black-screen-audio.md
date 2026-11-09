# GH-058: [Playtest] Game starts but only shows black screen

Status: Cause unverified; requested/selected game API and bounded presentation diagnostics implemented and locally tested, with persisted Auto/D3D12/Vulkan selection and a validated standalone comparison. Affected Windows 10 retest pending.

Source: [[Playtest] Game starts but only shows black screen](https://github.com/TK22-26/JetForceGemini-Recomp/issues/58). Evidence snapshot retained privately in D:/JFG-private/remaining-gh-issues-20261027/github-issues.json.

## Reported symptoms and reproduction

### Problem type

Graphics

### Launcher and game build

v1.40, NOT built locally.

### Windows version, GPU, and input device

Windows 10 Home Build 19045, NVIDIA RTX 4070 Ti Super, Controller (Nintendo Switch Controller, wired)

### What happened and how to reproduce it

Installed application, loaded ROM, got succes, can edit all the settings.
After pressing play, screen remains black but audio starts playing, can also hear the selector move and can confirm selection. So game seems to be running, but screen is black.
Tried all the video settings, but no success.

### How often does it happen?

Once so far

### Support ZIP and additional details

_No response_

## Scope and evidence

Local owner-authorized batch: investigate black video with working audio/input on Windows10. Preserve existing approved fixes, user profiles and ROMs. No GitHub posting or issue changes. A reported symptom is not yet a confirmed cause. Attempts, results, final remedy and verification limits will be recorded here.

## October 27 local investigation

The report supplies Windows 10 build 19045 and an RTX 4070 Ti Super, but no support ZIP or reproducible local state. Source review confirms that the game can run while its hosted presentation is hidden, so audio alone does not identify a renderer failure. No blanket Windows 10 fallback or speculative GPU workaround is applied.

A bounded diagnostic candidate now records the launcher's selected composition/window backend and HRESULT, plus hosted-game/viewport visibility, sizes, parent relationship, minimization and menu capture. It stores no paths, HWNDs, titles, screenshots or game data. The managed helper copies these allowlisted fields into the existing support ZIP during play and at exit. Backend fallback behavior is separately tested under GH-040. Validation of this new diagnostic is pending; the reporter's black-screen cause remains unverified.

## October 27 validation update

The new bounded support export passes 688 managed launcher checks, including archive preservation and rejection of private/malformed presentation fields, plus 28 setup checks. The native launcher shell also builds. The first test invocation used a private working directory rather than the source checkout required by the suite; rerunning the same executable with the correct working directory passed. This diagnostic is ready for batch review. No local reproduction establishes the reporter's cause, so this issue is not marked fixed.

## Assembled launcher check

The staged launcher completed an ordinary muted Play run and clean close with a separate copied profile. Its report includes the actual DirectComposition backend, successful HRESULT, valid hosted game/parent relationship, viewport sizes and hidden-window state. The intentionally hidden background host is correctly reported as invisible; no claim of an on-screen visual review is made. Exported fields contain no paths, titles or handles.

The first smoke test supplied a poll-ordered diagnostic input capture to the launcher's retrace-ordered replay option, and native boot rejected it with exit 3 before creating a renderer. That is an invalid test setup, not a reproduction of the reporter's running-but-black game. Rerunning ordinary Play passed. The staged executable's receipt was regenerated from its exact binary and matching symbols rather than copying an older build receipt.

## November 8 current-build review

The owner authorized fresh verification of #57 and review of #58. Live GitHub
body/comments were captured privately; #57 has one screenshot comment, while
#58 has no comments or attached failing-session support ZIP. Current validation
results and their limits will be added below. Private evidence: `issue57-58-review-20261108/`.

### Fresh investigation result and limits

Live GitHub review still finds no comments or failing-session ZIP. The report is
released v1.4.0 on Windows 10 Home 19045 with an RTX 4070 Ti Super. It is separate
from the owner's accepted Bazzite/Proton menu and mouse fixes under #40.

The current managed suite passes 778 checks, including bounded presentation
field sanitization and actual support-ZIP export, plus 28 mocked setup checks.
Fresh native UI checks pass 161 checks with DirectComposition and 210 with a
deliberately unavailable composition API, exercising the window fallback. The
viewport geometry checks also pass. These are launcher presentation backends,
not a D3D12-versus-Vulkan game-renderer comparison. Relevant source hashes and the
delivered launcher executable match its build receipt.

A byte-identical private portable copy of the current launcher and USA runtime
completed normal hosted Play, two window sizes, minimize/restore, fullscreen and
return to windowed mode, followed by normal close. Frame production continued;
the render child retained its intended parent and positive, visible dimensions
after restoration. The expected temporary 1x1 minimized state recovered. Its
support report records successful DirectComposition and each window transition.
This checks actual host state and frame progress, not desktop pixel capture or
the reporter's Windows 10/GPU combination. No local failure establishes #58's
cause. No speculative rendering or GPU workaround was added.

The first hosted harness expected inherited diagnostic variables to survive
RegionalSession's intentional environment sanitization. No requested progress
file appeared and the harness then failed on an uninitialized local variable;
the launcher/game themselves ran and closed normally. The corrected harness
uses the supported `--progress-output` argument and a private portable data root.
Both attempts are retained; the harness failure is not a game regression.

### Earlier review: renderer selection and diagnostic gap

The owner asked whether Rendering settings allow selecting D3D12 or Vulkan.
At that review they did not. `Rt64Shell` disabled RT64's external configuration file
and leaves its API preference at Automatic. The pinned RT64 resolves Automatic
to D3D12 on native Windows and Vulkan when Wine is detected, with device-creation
fallback and adapter compatibility rules. The owner explicitly deferred adding
the proposed selector; no selector implementation is part of this investigation.

Current support fields `frontend_backend` and `frontend_composition_hresult`
describe the launcher's compositor. They do not identify the actual game graphics
API or prove successful game presentation. The native `renderer-ready` milestone
also does not prove that visible pixels reached the screen. This remains an
observability limitation, not a confirmed black-screen cause or a completed fix.
Future diagnostic work should expose the requested/resolved game API and bounded
presentation failure status independently of the compositor fields, with support
export/privacy tests. A selector is not required for that diagnostic work.

Next evidence: retry the current build on the affected Windows 10 machine; if
black video recurs, export that session from Help > Support report, including
whether it was windowed/fullscreen and whether minimize/restore changes it.
The report can distinguish a missing/hidden/zero-sized host from a running
renderer whose output or composition still fails. A successful run on another
machine is not acceptance of the reporter's fix.

Private evidence: `issue57-58-review-20261108/github-58.json`,
`managed-tests.log`, `presentation-tests.json`, `viewport-tests.log`,
`delivered-launcher-pins.json`, and `hosted-session-v2/` (window states, progress,
result and private support report). Preserve the failed `hosted-session/` attempt.

## November 8 renderer diagnostics and API selection authorization

The owner now authorizes up to three hours to implement the game-renderer
diagnostic gap and a persisted Auto / Direct3D 12 / Vulkan selector. The earlier
deferral is superseded. Work is in progress, not yet a qualified fix or release.
Keep the launcher compositor fields distinct from requested/selected game API,
and record bounded renderer initialization/presentation failures in support ZIPs.

The owner also requests comparison with #40's Proton menu blackout. Its recorded
cause was fallback launcher capture hiding the hosted viewport; opening a menu
therefore removed the game image. Compare this visibility/compositing path with
#58 without claiming both reports share a cause. A standalone run of the same
runtime, ROM and settings is the requested isolation test: success standalone
with failure hosted implicates the hosting/composition interaction, but does not
alone assign fault to one process. Prepare a matching-settings direct command.

Private evidence: `renderer-api-20261109/`. Production guard remains enabled,
with the existing investigation root, counters and cumulative time preserved.
Automated sessions use muted private audio settings; owner profiles remain intact.

## November 9 renderer diagnostics and API selector candidate

The diagnostic gap is addressed in the current local candidate. This does not
establish or resolve the reporter's Windows 10 black-screen cause. No affected
machine support ZIP or hardware retest has been received, and no release or
GitHub closure is claimed.

**Video > Video settings > Rendering > Graphics API** now offers Auto,
Direct3D 12 and Vulkan. Auto preserves the pinned RT64 selection policy; existing
v1 video files default to Auto. Apply persists the choice in `video.ini` and
marks a running game for restart; Cancel discards it. Selection applies on the
next game start, independently of the launcher's compositor. An explicit choice
that upstream compatibility rules override is reported as a setup failure with
guidance to try Auto or the other API; those driver safety rules are retained.
The launcher/UI apply protocol advances to version 7 so stale layouts fail closed.
Compatibility is forward migration: the new parser reads old files, while an
older strict parser may reject the newly saved `graphics_api` key. The preview
therefore keeps its copied profile separate from the earlier test installation.

The native support log records `renderer_requested`, `renderer_selected` after
successful API setup, `renderer_host`, and a bounded `renderer_setup` outcome.
Real D3D12 Present/ResizeBuffers and Vulkan queue-present/acquire/swap-chain
creation return codes are recorded as `renderer_result`. Each API/operation
records its first result and changes, capped at 16 entries plus a limit marker;
unchanged frames do not flood the log. The hash-checked generated Plume units
leave pinned dependency sources and return behavior intact. Support ZIP tests
retain only fixed API/status tokens and eight-digit result codes, excluding
paths and malformed values. Initialization failures produce actionable launcher
guidance. A successful present call still does not prove visible desktop pixels;
resize/out-of-date statuses are evidence, not automatic diagnoses.

The direct-play review also found that `FrontendBridge` copied profile frontend
presentation logs even with owner handle zero. A standalone run could therefore
inherit compositor evidence from an earlier hosted session. Both periodic and
final collection now require a frontend owner; standalone game renderer events
remain available. A test seeds a stale frontend log and verifies it is absent
from the standalone session. This fixes misleading evidence, not game rendering.

The first managed test run failed because its exact exported-native-log assertion
still expected only the earlier audio fields. Updating that expectation for the
new allowlisted renderer fields retained the privacy checks; the rebuilt tests
pass. This was a test expectation failure, not a runtime recovery workaround.
The first video UI run also exposed a fixture error: its temporary reopened UI
changed the shared document back to Display without restoring/layout-settling
the original UI before the next pointer check. Restoring the original view fixes
the fixture while retaining the real pointer-hit assertions; failures now name
the target control. Dependent Proton/package scripts correctly stopped at their
failed prerequisite and were reissued against the successful qualification.
The original failure receipts are preserved.
Two additional private pointer-message probes did not activate Apply on an
inactive Windows desktop, including a retry with measured dimensions; their
failure cause was not established and no product change was made for them.
A targeted-keyboard probe then passed 17 checks through the real production
settings process, native IPC and saved file: Vulkan Apply/reopen, D3D12 and Auto
Apply, and Cancel retaining Auto. This establishes the actual settings boundary
without claiming physical-pointer qualification. Preserve both failed probes
and `production-video-keyboard/`; the existing UI fixture's pointer tests pass.

### Relation to the Proton menu blackout

The established #40 cause was `sync_ui_capture_windows` hiding the viewport during
fallback menu capture. The corrected fallback uses an owned popup for panel
content and keeps the game viewport visible; the composition route retains its
input shield. This is independent of D3D12/Vulkan game API selection. Both Windows
presentation routes and the actual isolated GE-Proton fallback regression pass
again, including game visibility and menu pixels. The similar black appearance
does not establish that #58 shares that cause.

### Qualification and limits

All nine muted normal-Play combinations (USA/PAL/JP times Auto/D3D12/Vulkan)
start, report the selected API, produce frames/presentation results and close
normally. Real hosted USA sessions with each API continue producing frames
through resize, minimize/restore, fullscreen and return to windowed mode. The
delivered standalone helper script starts the same verified USA runtime with
the same API settings and closes normally; its report identifies standalone
hosting and excludes a deliberately stale frontend presentation log.

A private process-local unavailable Vulkan driver test fails cleanly with a
bounded setup result, without modifying installed drivers or owner settings.
The UI checks cover selection, dirty/restart state, Cancel, persistence, failed
save and reopening. The same video UI and menu regression also pass in isolated
GE-Proton 11-11 under WSL2 with software Vulkan. These are not new Bazzite/RTX4070,
Steam Deck or affected Windows 10/RTX4070 Ti Super hardware approvals. Native
Vulkan diagnostic frame readback was deliberately not enabled; its separate
qualification is not implied by successful normal presentation.

Private evidence: `renderer-api-20261109/` contains source/build receipts,
`runtime-api-results.json`, `hosted-api-results.json`, `ui-results.json`,
`proton-results.json`, `standalone-script/result.json`, and
`unavailable-api-result.json`. The local preview contains all three verified
runtime bundles and a copied profile. Owner audio preferences and save namespace
markers are preserved; automated profiles alone are muted. Existing uncommitted
work is preserved. No commit, push or public distribution was performed.

### Reporter comparison

Use the current candidate with the same ROM, save, window mode and Graphics API
for both hosted and standalone launches. The native game executable is
`jfg-native-boot.exe` inside its regional runtime. The preview's
`Test-Standalone.ps1` invokes the existing managed `direct-play` service with
owner handle zero: it retains ROM/runtime/save validation and support logging,
but creates no launcher window and no embedded viewport. `JFG-Launcher.exe
--play` still hosts the game and is not this isolation test.

If standalone works while the hosted run fails, that narrows the defect to the
hosting/composition interaction or its effect on the game renderer. It does not
alone prove which process is faulty. Export both sessions and compare their
runtime hashes, requested/selected API, host state and presentation results.
Separately retry D3D12 and Vulkan from a stopped game, retaining the failing
session's report. Never relabel success on this development PC as reporter
acceptance. Transferable lesson: distinguish frontend composition, game API
selection, API return status and actual visible output in every graphics report.

Implementation references: [settings schema](../../../include/jfg/renderer/video_settings.hpp),
[runtime selection and setup outcomes](../../../src/renderer/rt64_shell.cpp),
[bounded result history](../../../include/jfg/renderer/renderer_diagnostics.hpp),
[pinned presentation instrumentation](../../../cmake/renderer/rt64_presentation_diagnostics.cmake),
[support allowlist](../../../launcher/windows/Support.cs), and
[frontend behavior](../../features/frontend.md). The standalone comparison uses
the existing [direct-play service](../../../launcher/windows/FrontendBridge.cs).

## Graphics API presentation refinement - November 9

The owner requests a combo box matching Window size instead of the initial
three-button selector. The candidate now uses the same RmlUi select control and
shared styling, with Auto / Direct3D 12 / Vulkan choices. Escape dismisses the
open list before closing settings, and selection retains the existing Apply,
Cancel, persistence and next-game-start behavior. This is a UI refinement;
renderer API selection and the unresolved #58 diagnosis are unchanged.
The rebuilt launcher passes 285 Video Settings checks on Windows and
285 under isolated GE-Proton, including the combo's real
pointer opening, keyboard selection, Escape, Apply/Cancel and persistence.
The existing Desktop Renderer API Test shortcut now opens the updated launcher.
Its runtime bundles and owner profile were not modified; manual appearance
approval remains pending. No commit, push or release is claimed.
Private evidence: `renderer-api-combobox-20261109/`.

### Graphics API help-text correction

The owner rejected the generic "Change this if the game has graphics problems"
advice and duplicate restart sentence. The hint now says only "Auto chooses a
compatible renderer." The existing conditional restart warning retains its
behavior. API selection is not presented as a general graphics-fix guarantee.
The rebuilt launcher passes the existing 285 Windows Video Settings
checks and is available through the same Desktop Renderer API Test shortcut.
The owner's open launcher was preserved; reopen the shortcut for the update.
No renderer behavior, owner profile or runtime bundle changed.
Private evidence: `renderer-api-copy-20261109/`.
