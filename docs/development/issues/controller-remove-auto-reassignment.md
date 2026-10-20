# INPUT-012: Removed controller immediately moves to another player

## Status and severity
Unreleased candidate implemented on 2026-10-19; core and real UI regression checks pass. Owner approved locally; unreleased.
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
