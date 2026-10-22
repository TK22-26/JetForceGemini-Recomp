# GH-032: Intermittent mouse look and ineffective vertical inversion setting


## Supplied evidence investigation (2026-10-21)

**Current status:** supplied ZIP and both videos inspected; intermittent motion
loss and ineffective Off remain unresolved. A focused support-diagnostics
candidate is implemented and tested in source. A complete instrumented runtime
package and failing/working live captures remain pending. It does not change
input delivery or claim a fix.
The accepted default/reset-Off change remains separately approved and unreleased.

The support ZIP is 2,522 bytes, SHA-256
`38226f33e103f6e8964e5a996ee6e76bf5c83ca3d3fdc2332ff017dcaba58fd8`.
It identifies the official v1.3.0 runtime
`1bfc6a04ced93f0eec76a9a4f72817b6d93a5de2f26f4de6af9114cdf13b786f`,
clean runtime source `665596482a7395593e85dbe73f1bd4b016d183d9`, and a
launch at 18:20:56 UTC. The selected controller device is -3 (mouse/keyboard).
This report belongs to this project. The nine ZIP entries contain build identity,
legacy controller settings and progress breadcrumbs, but no Modern profile,
raw-motion counters, capture/focus history or effective mouse inversion value.
`controller_invert_y=0` describes the legacy mapping; it does **not** establish
Modern mouse inversion Off. Empty crash/hang files do not diagnose lost motion.

The failing clip is 22.78 seconds and the working clip 17.03 seconds, both
2560x1440/60fps. Decoded two-second frame samples show movement, firing/aim
activation and menu cycles in the failing clip; the later working clip also shows
substantial free camera pitch/orbit. This supports the reporter's distinction,
but the videos do not expose physical mouse deltas or Windows input ownership.
No new Off/On comparison is present. Original downloads, hashes, decode logs and
contact sheets are retained privately under evidence ID `mouse-evidence-20261021`.

### Source findings and rejected hypotheses

- Both the reported v1.3.0 source and current source register a raw mouse once
  with flags 0 and use registration success as the capture prerequisite. Buttons
  arrive separately through legacy window messages. Captured cursor/buttons can
  therefore coexist with absent raw packets or rejected absolute packets.
- The hosted game window belongs to the runtime process; its launcher root belongs
  to another process. The game capture gate checks the launcher root foreground
  state, while Windows default raw delivery depends on application focus.
  Launch and menu-return code call SetFocus without observing the resulting
  focus state. This is a **routing hypothesis**, not a proved race: cross-thread
  parenting can attach input queues, and the videos/ZIP do not record actual focus.
- Microsoft documents [default focus-dependent raw delivery and INPUTSINK](https://learn.microsoft.com/en-us/windows/win32/api/winuser/ns-winuser-rawinputdevice),
  [SetFocus queue requirements](https://learn.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-setfocus),
  and [process-wide registration ownership](https://learn.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-registerrawinputdevices).
  These contracts motivate observing the actual recipient; they do not establish
  the reporter's cause or justify changing registration flags by themselves.
- A hidden registration-only test with the shipped SDL2 DLL preserved the mouse
  HWND and flags through AUDIO/GAMECONTROLLER initialization and shutdown. SDL
  added a separate gamepad registration. No foreground change, input injection,
  game launch or personal profile access occurred. Controller initialization
  stealing mouse registration was not reproduced by this test.
- The mailbox locks and three consumer sites retain accepted motion; no permanent
  drain/clear defect was identified in this review. Absolute packets are rejected
  intentionally, but the reporter's actual packet type remains unknown.

The next useful evidence is numeric raw/accepted/dropped motion counts, actual
focus/capture/gating state and the effective Modern mouse settings from a failing
session, compared with a working launch. Do not request the same uninstrumented
ZIP again or present a speculative INPUTSINK/fallback change as a verified fix.
The diagnostic candidate retains no coordinates, key contents, window handles,
device paths, ROM data or saves. Public posting remains held.

The work uses the enabled production supervisor, original investigation/root,
unchanged counters/limits and the owner's existing parallel window ending
22:59:58 UTC. No new time allowance, public reply, commit, push or release.
Transferable lesson: registration success is not delivery proof, and legacy
controller inversion fields cannot diagnose a separate Modern mouse preference.

## Diagnostic candidate and verification (2026-10-21)

The runtime now counts raw-message delivery, read errors, relative/absolute
packets, uncaptured rejection, accepted nonzero motion, mailbox consumption and
sampled nonzero mouse look. Once per second, the existing support cadence records
registration target/flags, launcher foreground state, actual child focus (with an
explicit unknown state), capture/settings/input gates and effective per-player
Modern mouse inversion and sensitivity. Input registration, acceptance decisions,
button handling and camera behavior are unchanged.

A runtime-owned ring retains the last 60 snapshots in mouse.log, ordered oldest
first. This preserves preceding gameplay state when opening the support menu
changes focus. Maximum output is 53,040 bytes, below the existing 64 KiB support
file limit; every line is below 256 bytes. Window-message handling updates atomic
counters only. Counters are cumulative, context is sampled, and values across
threads are not an atomic packet transaction. Elapsed time starts at the first
support snapshot. The history is diagnostic evidence, not an input replay.

The launcher exports this file using an explicit numeric schema allowlist.
Mouse counts have eight fields and flow counts six; their order is defined by
MouseCount in [the diagnostics header](../../../include/jfg/runtime/mouse_input_diagnostics.hpp).
The state row contains elapsed time plus fourteen status/error fields;
each player row contains thirteen effective setting/context fields.
The header documents each position. Older runtimes produce an empty optional
mouse entry; previous report files and privacy exclusions remain supported.

Validation:

- The new exporter regression failed against the old source as expected.
  The corrected C# helper suite passed **680 checks**, including actual ZIP
  roundtrip, privacy canaries and malformed/oversized schema rejection.
- The focused native test passed with MSVC /W4 /WX and Release/NDEBUG, covering
  no delivery versus read/rejection/acceptance, explicit unknown focus, formatting,
  70-sample wrap/order, 75 maximum-width samples and production Windows file output.
  Persistent CTest registration: jfg.mouse_input_diagnostics.
- The actual production writer's **53,040-byte** history survived the actual
  helper sanitizer and ZIP exporter byte-for-byte.
- The complete current native_boot.cpp translation unit compiled successfully
  with the existing Release options into a private object/PDB; source hashes were
  stable during the final 59.9-second compile. Whitespace checks passed.

Two private PowerShell reflection harness attempts failed because its arguments
were wrapped as PSObject rather than String. Explicit constructor selection and
typed arguments corrected the harness; the failed logs remain preserved. These
were test harness failures, not product defects or lost reporter evidence.

No full runtime executable was linked, preview installed, physical mouse session
run or public reply posted. Performance, real focus delivery and the reporter's
Off behavior are not qualified by these tests. Build/distribute a complete
instrumented package before requesting a failing-session ZIP and matching working
launch from it. Export promptly after the symptom so the preceding minute remains.
Keep #32 open; the failure's final cause and remedy remain unknown.

Evidence: mouse-evidence-20261021/helper-baseline.log, helper-candidate.log,
runtime-diagnostics/history-final-receipt.json, history-roundtrip/result.json
and native-history-compile/result.json. Implementation:
[diagnostics header](../../../include/jfg/runtime/mouse_input_diagnostics.hpp),
[runtime integration](../../../src/boot/native_boot.cpp),
[export allowlist](../../../launcher/windows/Support.cs),
[report file inventory](../../../launcher/windows/Diagnostics.cs) and
[focused regression](../../../tests/mouse_input_diagnostics_tests.cpp).
Lesson: preserve pre-menu context, distinguish missing motion from discarded
motion, and verify that the exact diagnostic bytes survive the export sanitizer.


Guard closeout (2026-10-21 21:38 UTC): the diagnostic job completed and sealed successfully as supporting activity. The production guard remains enabled; grading reached the unchanged cumulative attempt ceiling (85/85), so the investigation is now shelved. No further experiment, build, replay or coding-worker execution was started. Full instrumented packaging/live capture remains pending; the earlier22:59:58UTC outer deadline does not override this stop.

## Reporter evidence received (2026-10-21 18:28 UTC; reviewed 20:47 UTC)

The [new reporter comment](https://github.com/TK22-26/JetForceGemini-Recomp/issues/32#issuecomment-6323481257)
supplies the requested
[support ZIP](https://github.com/user-attachments/files/33782134/JFG-support-3b837e77089645d2b2805b94a84844bd.zip)
and videos of the [failing session](https://github.com/user-attachments/assets/25ba2e60-4074-4457-a405-c19203fce79c)
and a [later working launch](https://github.com/user-attachments/assets/435731bd-3538-41f4-a435-ab4644a7d493).
The reporter says the window grabs the mouse and right-click enters aim, yet
motion does nothing. Two subsequent launches produced failure then success.
This is their observation; cursor hiding/buttons alone do not verify raw motion
delivery or capture ownership. No new inversion-Off result is reported.

**Current status:** evidence received, analysis pending; intermittent mouse look
and ineffective Off remain open. Earlier requests below for the first failing ZIP
are historical and fulfilled. Inspect this supplied ZIP and the paired videos
before asking for duplicate evidence. The attachments were linked, not downloaded,
played or analyzed by this audit. Private API snapshot:
`github-follow-up-review-20261021T204709Z/github-issues.json`.

The accepted default/reset-Off correction is on develop in
[`abcfc32`](https://github.com/TK22-26/JetForceGemini-Recomp/commit/abcfc322d260e220278d844be33ab0ad749220b6),
but remains unreleased. This comment is not a retest of that correction. Preserve
the reporter's profile, identify the attached runtime/settings, then compare
mouse motion, capture/focus state, selected player/input and inversion application
in an eligible guarded investigation. No new cause, patch or public reply is
claimed. Reporter retest after delivery remains required.

## Owner mouse-default preview (2026-10-20)

At the owner's request, **JFG - Mouse Inversion Preview** is packaged for an
in-game check. The rebuilt launcher uses the tested default/reset-Off source.
Its runtime is the unchanged, owner-accepted Modern Roll Direction runtime,
which already supports explicit saved Off. This preview does not contain a new
native pitch/capture correction. The shared defaults header will also be included
when the next complete runtime release is built.

Settings, bindings and save were copied to an isolated preview profile; the
original preview/profile were hash-verified unchanged. The copied mouse inversion
value is 0. Actual packaged helper init/setup and runtime protocol
checks pass. Launcher SHA-256: `4078a35da2c8c8437f2e5569a074ea26dc091fdcda7e5f9df92236df42b9db61`.
Runtime SHA-256: `a26006f13c507dd4601461308ce43153d98d6eb90ca104685fce2ac130dee154`.
Evidence ID: `mouse-default-preview-20261020`.

The owner tested the preview in game and reports "looks good"; local acceptance
is recorded. The exact coverage of each suggested camera/aim/reset case was not
individually reported. **Reporter retest TODO:** ask the #32 reporter to retest
mouse look and inversion with the updated build when available, including Off/On
and restart behavior. If symptoms persist, obtain the affected-session support
ZIP and cursor-capture observations. The reporter's ineffective-Off/capture
symptoms remain open. The default/reset correction is unreleased; no new public
reply, commit, push or release was performed.

## Ineffective Off review and approved reporter reply (2026-10-20)

The owner explicitly authorized posting the approved concise reply and reviewing
why mouse inversion may remain active when Off. The exact reply was posted and
verified at [GitHub](https://github.com/TK22-26/JetForceGemini-Recomp/issues/32#issuecomment-6298722151). It requests cursor behavior and a failing-session
support ZIP. This authorization applies only to that reply; no additional public
messages, issue closure or release is authorized. The bounded source/fixture
review is complete; no general failure to apply Off was reproduced. The
reporter symptom remains open, pending a failing-session support ZIP/profile
and live reproduction. The default/reset correction remains a separate,
unreleased change. Evidence ID: `mouse-inversion-review-20261020`.

### Findings and limits

- The UI stores mouse and controller inversion separately for each player.
  The selected input determines which setting the visible control changes.
  A successful save writes the complete profile using an atomic replacement.
- Actual runtime reload/selection functions and the real asynchronous file
  reader were exercised with private schema-5 and schema-6 profiles. Saved
  On changed to Off during a running reader, changed back to On, and stayed
  Off after a reader/runtime-state restart. Controller, other-player and
  legacy preferences did not overwrite the Modern mouse preference.
- The focused fixture passed 1,807 checks, including 576 motion/aim cases
  across both polarities and sensitivity ranges. Raw mouse samples apply
  the current setting when consumed. Camera/native aim helper conversions
  agree, and the earlier crouch-aim pitch conversion remains in the native
  consumer. This is not a full native-camera or physical-mouse replay.
- The initial fixture did not compile because the Win32 `near` macro
  collided with a navigation-header identifier under its independent
  include order. Undefining that macro in the private fixture resolved the
  harness failure. The failed log is retained; no product change was made.
- Unrelated latches, scope state and profiling were explicit no-op fixture
  boundaries. No game, emulator, physical input, installed preview or
  personal settings were touched. Prior 839 offscreen UI checks establish
  default/reset/save behavior; these runtime tests add disk reload and
  input-direction coverage, not end-to-end reporter reproduction.

The confirmed way to re-enable inversion was the old default/reset value.
That does not establish why explicit Off remains ineffective for the
reporter. An unexpected active profile/player/input type or a native path
not represented by these fixtures remains a hypothesis, not a diagnosis
or evidence of user error. No further inversion or capture patch is
justified by this review alone. Next, inspect the requested failing-session
support ZIP for saved settings and selected input/profile, then reproduce
the affected camera/aim state before changing runtime behavior.

All review work used the existing guarded queue and unchanged deadline,
root, counters and enabled production guard. The shared cutscene review
session remains intact. No commit, push or release was performed.

## Modern mouse default/reset correction (2026-10-20)

The owner requests noninverted Modern mouse look by default. Both v1.3.0 and the
prior develop source explicitly initialized `look.mouse_invert_y=1`, while
controller `look.aim_invert_y` defaulted to 0. Both full mouse defaults and the
sensitivity/behavior reset restored that On value. Resetting settings was therefore
a concrete way to re-enable mouse inversion during troubleshooting; it does not
prove why the reporter still sees inversion after explicitly selecting Off.

`ModernControlsConfig` now inherits mouse inversion Off from `PcInputConfig`.
The existing reset path consequently restores Off. Controller defaults and
explicit saved mouse On/Off preferences remain intact. No profile migration,
schema bump, capture change or runtime pitch-sign change is included.

Verification: the updated default regression failed against the old source,
then the corrected core suite passed (169 modern controls checks passed).
The actual offscreen Modern UI suite passed 839 checks, including
On selection, reset cancellation, reset-to-Off persistence and preservation of
controller choices. These tests establish default/reset/persistence behavior,
not a reproduction or resolution of intermittent capture or ineffective Off.

Source and regression changes are local and unreleased. No existing preview or
personal profile was replaced, and no gameplay was launched. Evidence ID:
`modern-mouse-default-20261020`, including baseline/candidate logs and UI results.
At that point the draft reply was unposted; the subsequent authorized reply
is linked above. The work ran serially in the existing guarded
queue under the owner's narrow request, retaining its deadline, root and counters.

Lesson: distinguish controller and mouse defaults, explicit saved preferences,
and reset behavior. Cursor hiding is a useful observation, not proof that mouse
motion reached the game.

- Status: mouse default/reset corrected to Off and verified in source tests; unreleased. Intermittent capture and ineffective Off remain unreproduced and unresolved.
- Severity: high usability impact when mouse camera/aim input is unavailable.
- Affected report: v1.3.0, Windows 11, RTX 5070 Ti, keyboard/mouse, multiple monitors.
- Source: [GitHub #32](https://github.com/TK22-26/JetForceGemini-Recomp/issues/32),
  created 2026-10-20 06:10 UTC; [reporter follow-up](https://github.com/TK22-26/JetForceGemini-Recomp/issues/32#issuecomment-6284874862)
  last edited 06:42 UTC.

## Symptoms and reproduction

Keyboard movement, mouse buttons and menu interaction work, but mouse motion
often fails to move the camera, including while aiming. The initial report
described a constant failure; the follow-up corrects this to intermittent,
with some launches working.

Track vertical inversion separately: the reporter says upward mouse movement
still aims downward with inversion disabled, including after a restart.
Their objection to an inverted default is a separate product-default request.
Neither proves why their saved Off setting appears ineffective.

The reporter first attributed capture loss to leaving the game on a
multi-monitor desktop, then withdrew that explanation when focus return worked.
Launching, Escape-menu cycles, changing/resetting settings and focus transitions
remain possible triggers without a reliable minimal reproduction. A hidden
cursor does not establish that relative mouse input was captured.

## Evidence and hypotheses

At the initial 2026-10-20 review, no support ZIP, failing profile or input capture
was attached; the evidence was the issue and its edited follow-up. That private
API snapshot remains `issue-triage-20261020/123300`. The new support ZIP and videos
received on 2026-10-21 are linked above; their contents await analysis.

Capture lifetime, selected profile/settings application and native pitch-sign
handling are prospective investigation areas, not confirmed causes. The accepted
[focus-loss camera reset](focus-loss-camera-reset.md) preserves the chosen view;
that result does not establish mouse motion capture works in this case.
Earlier [crouch inversion](crouch-mouse-inversion.md) and
[retained-profile/default](modern-capture-profile-defaults.md) findings are
context, not proof of a recurrence. The resolved
[mouse-enabled startup crash](github-mouse-look-startup.md) is a different symptom.

## Attempts and results

| Date | Action | Result |
|---|---|---|
| 2026-10-20 | Read the issue, its current edited follow-up and existing issue records | Corrected frequency to intermittent; retained the withdrawal of the focus-only explanation; separated capture, ineffective inversion and default preference |
| 2026-10-20 | Correct mouse default/reset to Off at owner request | Before/after regression and 839 UI checks pass; saved preferences preserved; local and unreleased |
| 2026-10-20 | Post owner-approved reply and trace UI/runtime setting application | Exact reply verified; requested cursor observation and failing support ZIP |
| 2026-10-20 | Compile isolated runtime review fixture | First attempt failed on Win32 macro/include-order conflict; fixture-only correction, original failure retained |
| 2026-10-20 | Exercise actual profile reader/reload/selection and motion helpers | 1,807 checks and 576 motion/aim cases pass; explicit Off survives live reload/restart; reporter symptom remains unreproduced |
| 2026-10-21 | Review new reporter comment and attachment links | Requested support ZIP and failing/working videos received; capture described as active while motion fails; attachment analysis and reproduction pending |

Initial triage performed no runtime change, reproduction, build, test or
public reply. Subsequent authorized work is recorded above. The cause and remedy
for ineffective Off and intermittent capture remain pending; no issue closure.

## Remaining reproduction work

Preserve the failing settings and compare a copied profile with a fresh one.
Measure mouse motion, capture/focus state and applied inversion independently
through launch, Escape open/close, focus return and settings/reset transitions.
Check both inversion polarities, normal camera and aimed pitch, and crouch
without silently migrating user preferences. Distinguish button activity from
motion activity. Start with the supplied affected-session ZIP and paired videos;
request additional capture only if those leave a specific evidence gap.

This is prospective work subject to owner selection and the production guard.
Initial review can be coordinated with #33, but shared input/settings/native
dispatch edits require an integration owner and preserved active previews.

## Compatibility lesson

Honor the latest correction to a report rather than freezing an early causal
claim. Test stored settings, applied settings and input consumption separately;
similar focus or inversion symptoms do not establish a common defect.


## Owner disposition (2026-10-21 UTC)

Owner explicitly reconfirms #32 approval and requests a note to ask the reporter
to test the updated build. The accepted default/reset-Off correction needs no
additional owner approval. Reporter follow-up remains required for mouse capture,
inversion Off/On and restart behavior; if it still fails, request the affected
support ZIP and cursor-capture details. This audit sends no new public reply.

## Relation to the new Floyd regression (2026-10-21)

Owner asks whether the new Floyd inversion with Off explains this report. Its saved P2 mouse preference was correctly Off. The newly introduced Floyd adapter omitted a native coordinate conversion; the corrected adapter passes the original native reticle consumer. That adapter did not exist in the reported v1.3.0 build and cannot be this report's exact cause. A similar conversion error in an untested older path remains possible, not established. Reporter retest/support capture are still required; this does not close #32.
