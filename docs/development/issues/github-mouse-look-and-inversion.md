# GH-032: Intermittent mouse look and ineffective vertical inversion setting

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

No support ZIP, failing profile or input capture is attached. The evidence
currently consists of the issue and its edited follow-up. Private API snapshots
are retained as `issue-triage-20261020/123300`.

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

Initial triage performed no runtime change, reproduction, build, test or
public reply. Subsequent authorized work is recorded above. The cause and remedy
for ineffective Off and intermittent capture remain pending; no issue closure.

## Remaining reproduction work

Preserve the failing settings and compare a copied profile with a fresh one.
Measure mouse motion, capture/focus state and applied inversion independently
through launch, Escape open/close, focus return and settings/reset transitions.
Check both inversion polarities, normal camera and aimed pitch, and crouch
without silently migrating user preferences. Distinguish button activity from
motion activity. Retain an affected-session support capture when available.

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
