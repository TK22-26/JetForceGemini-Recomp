# INPUT-012: Removed controller immediately moves to another player

## Owner follow-up: remove all, reopen, then change input type (2026-10-20)

Owner confirmed the input-type replacement follow-up fixed on 2026-10-20;
unreleased. Prior automated evidence and earlier pending status are retained below. Starting
inputs: keyboard/mouse plus one controller. Remove both, save, close, reopen,
re-add the pad, then switch that player to keyboard/mouse: the released pad moved
to a later Automatic player. No save-loss report. Earlier explicit-Remove
approval does not close this new sequence.

Cause: `assignDevice` excluded the pad for explicit Remove, but changing input
type released it without retaining that exclusion. The shared UI now records the
released identity for every explicit replacement. Explicit Add re-enables only
the selected pad; Automatic retains normal discovery. The core resolver and
custom bindings remain unchanged, with transactional policy/mapping rollback.

The exact regression fails before and passes after. Real Controller Mapping UI:
282 checks; Modern UI: 790 checks. Coverage includes remove-all/save/reload/type
change, another reload/reconnect, replacing an Automatic pad, explicit Add and
Automatic, unchanged downstream players, and policy/mapping write-failure
rollback. Discovery is injected in an isolated offscreen UI; physical acceptance
is pending. Persistent regression:
`launcher/ui/tests/controller_mapping_ui_tests.cpp`; implementation:
`launcher/ui/native_ui.cpp`.

Desktop: **JFG - Modern Input Fix Preview**.
Package: `C:\JFG-previews\modern-input-followup-20261020`.
Launcher SHA-256: `25710daa68b3d66b53b4e8d5e0a824f53735b24a139a901a0b8689040bb24697`.
Actual resource101 helper extracted from the deployed launcher matches the
accepted preview and passes init/setup. Runtime protocol passes. Source and
copied settings/controller files/save are hash-verified unchanged. Ctrl remains
crouch. No gameplay was launched. The previous preview remains available.

Evidence: `D:/JFG-private/modern-crawl-reversal-20261020`, especially
`controller/assignment/final-handoff.json`, baseline/candidate receipts, frozen
build-input manifest, helper identity and root `delivery.json`. The launcher
build is private; shared build output is untouched. Same enabled production
investigation/root/counters, deadline 18:09:13 UTC; no public action or release.

Lesson: input-type replacement is also a device release. Preserve release policy
across every UI/persistence path, while distinguishing explicit selection or
Automatic from unplugging a sticky assigned controller.

## Status and severity
The original explicit-Remove fix was implemented and owner-approved locally on
2026-10-19; unreleased. That approval does not cover the input-type replacement
follow-up above, which awaits owner verification.
Affects v1.3.0 launcher automatic controller assignment and the rain/reticle preview
using that launcher. Moderate: assigning a controller to the intended player becomes
confusing and requires removing it from each subsequent port.

## Report and reproduction
The owner removed an Xbox controller from Player 2. It immediately appeared on
Player 3, then Player 4 after another removal, and became free only after removing
it from Player 4. Downstream ports retain their default Automatic setting.

## Evidence and cause
The Remove action in launcher/ui/native_ui.cpp calls assignDevice(-2), saving only
the current port as disconnected. ControllerPorts::devices then gives the freed
physical controller to the next automatic port. This is the ordinary resolver
working without any memory of the user's explicit removal intent.
The existing UI tests disconnected all four ports before testing Remove; the core
availability test also disconnected downstream ports. Neither represented defaults.

## Planned correction and acceptance
Persist explicit removal intent by device identity and share the policy between
the launcher and runtime. Removed devices must stay selectable for explicit Add
but must not immediately be reclaimed by automatic ports, including after restart.
Keep unrelated assignments, hotplug behavior and stable SDL identities intact.
Regression coverage must start with automatic downstream ports, exercise Remove
through the real UI, reload settings and explicitly reassign the controller.

## Related startup observation
During the same review, changing to 60 FPS and restarting left a blank blue game
area with PAUSED in the launcher. Read-only inspection found the Live Map window
still marked JfgLiveModal and the frontend pause property set. Closing Live Map
and dismissing the launcher menu let the game load, as confirmed by the owner.
This was a retained modal pause, not evidence of a 60 FPS rendering failure.
The blank startup pause is confusing UI feedback; no correction is claimed.

## Validation and release
The source correction is implemented, but has not been released. Private investigation steps 067-075 preserve
the source inspection and owner-session state. No gameplay was driven automatically.

## Compatibility lesson
Automatic assignment and explicit removal are distinct intents. Test with untouched
default ports and with both physical-device identity and persisted profile state.


### Completed automated verification

Persistent device-identity exclusions are shared by launcher/runtime; explicit Add
clears the exclusion. Removing a device no longer permits later Automatic ports
to reclaim it. The previous implementation fails the real UI regression:
Remove must not move Xbox to another automatic player. Five core suites, 233
mapping UI checks and 790 Modern UI checks pass, including persistence,
hotplug, explicit Add and save failure. The owner-facing combined preview includes
this candidate. No physical controller acceptance is inferred from the harness.

Evidence: D:/JFG-private/v131-rnd-20261019/controller-removal-validation.json.

## Owner decision, 2026-10-19

Owner approved this candidate for the upcoming update. Automated results and
historical limits remain as recorded; this is local acceptance, not release.
