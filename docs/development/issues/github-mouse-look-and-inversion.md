# GH-032: Intermittent mouse look and ineffective vertical inversion setting

- Status: reported; triaged 2026-10-20 UTC; not reproduced or fixed locally.
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

No runtime change, reproduction, build or test was performed during triage.
Cause and remedy are pending. No public reply or closure was posted.

## Proposed verification when authorized

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
