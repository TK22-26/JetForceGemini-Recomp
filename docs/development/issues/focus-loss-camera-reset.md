# CAMERA-009: Camera resets when the game loses window focus

- Status: preview14 room-entry/focus-return fix owner-confirmed with Modern controller and mouse/keyboard, 2026-10-20; unreleased.
- Reported: 2026-10-19; owner confirmed landing fix and then found this.
- Severity: gameplay usability; unexpected camera movement.
- Affected: reproduced on Modern controller; source cause also applies to Modern mouse. Original exclusion verified in tests; owner cross-mode review accepted.

Turn the camera, click outside the game window, and return. The owner reports
a reset. Determine whether the reset occurs on focus loss, paused-state entry,
or focus return. Review Modern controller, mouse/keyboard and Original paths.
Do not assume all three modes reproduce or freeze native scripted cameras.
Preserve physical-input neutralization, focus-return release gate and controller
connectivity. Initial lead: host pause/control lifetime handling can clear the
retained Modern view even though ordinary input suspension preserves it.

Private session: D:/JFG-private/v131-rnd-20261019.
Related: [controller landing](controller-high-landing-camera-reset.md).
Initial report preceded the candidate below. Owner validation is recorded below; no public response or release.


## Qualified cause and candidate

The owner clarified that this happens while standing normally. An early branch
of sample_live_controller correctly preserves the Modern mode marker while
neutralizing physical input. A later scope/aim cleanup branch set modern_flags
to zero, undoing that preservation. ModernShoulderScope requires the marker;
without it, the persistent view is cleared and reacquired from native orientation.

The candidate keeps only kModernActionsFlag during that final cleanup. Aim
toggle, queued zoom and sensitivity state are still cleared. Look, movement
and buttons remain neutral, all controller connectivity remains unchanged,
and the physical release gate still requires release before fresh input.
Original mappings retain zero Modern flags and never acquire a Modern camera.

This source path affects both Modern controller and Modern mouse/keyboard.
Original uses the native camera and has no corresponding marker loss; tests
check its exclusion and unchanged guest state, not a physical Original visual
pass. Host focus pause does not write camera state. Do not add a universal
camera freeze that would interfere with native/scripted behavior.

## Evidence and limits

A harness compiles the actual earlier suspension block, late cleanup block and
ModernShoulderScope against real input, navigation, view and gate helpers.
Previous source fails at the lost mode marker. Candidate passes 2,610 checks:
XInput, SDL and mouse; Modern and Original; standing, airborne and ledge states;
repeated focus suspension; all-port input neutralization; pending zoom and aim
cancellation; retained chosen view; physical release and fresh look afterward.
The Original cases verify no Modern camera acquisition or guest-memory writes.
Full landing/ledge checks remain separately recorded.

The first harness configure failed because its CMake include path contained
Windows backslashes. Corrected forward-slash fixture paths pass; that attempt
did not modify production source. Both failed baseline and setup evidence remain.
Private artifact group: v131-rnd-20261019/focus-camera/qualified.

Earlier CAMERA-004 used a diagnostic replay suspension branch. That bypasses
the live-only late cleanup, explaining why that check can pass while physical
focus loss fails. Future focus tests must include the entire live input pipeline
and not only the suspension flag or view holder in isolation.
See [earlier focus investigation](modern-controller-state-transitions.md).

Owner gameplay verification is now accepted as recorded below. No public
comments, commit or release made.

Preview: JFG - Focus Camera Fix Preview; muted, standard diagnostics, no screenshots. Runtime ab99b8a235f6f6692fced13504dde1c95e14bc0f503b2014a4f4b84a5bf6dc8b. Owner performs gameplay. Earlier ledge and landing fixes remain included.


## Owner acceptance

The owner answered "Fixed in all tested modes" to the focused review request
covering Modern controller, mouse/keyboard and Original focus loss/return.
This accepts the local preview. It does not establish every hardware backend,
every gameplay state or a released resolution. The new runtime retains the
separately accepted controller ledge and high-drop landing corrections.

## Preview12 focus-return regression

Owner reports clicking back into the game after desktop focus loss resets the camera. Game closed; investigate the full focus-return path, preserving the earlier accepted input-neutralization fix. Exact device/state will be inferred from capture where available; do not assume the old cause recurred. No new remedy verified yet.

The captured profile is Modern XInput. The earlier marker-preservation fix is present in the compiled checkout; no missing merge was found in that path. The next preview records pc-view-reset-cause only when an active view is actually cleared, including the branch (device release1, gameplay eligibility2, non-gameplay3, shoulder eligibility4), actor/control, angles, block state, input mode/flags, device/connectivity and movement state. This is diagnostic only until the clearing cause is reproduced; no new camera fix is claimed.

Owner explicitly confirmed the preview12 focus-return regression uses Modern controller. This agrees with the captured XInput profile. Modern mouse and Original are not confirmed affected by this new regression. Preview13 logging is diagnostic, not a verified camera remedy.

## Preview13 room-transition report

Owner reports the camera snapped after Vela rescue and a room transition in preview13, in addition to the earlier desktop focus-return report on Modern controller. Capture 20261020-135821-12ef9f4c072f4183a963b0f418e49df2 is closed. Determine whether the two symptoms share a cause; do not assume focus loss caused this transition snap. The flash and Tawfret skip were both accepted in this pass.

Owner clarified the exact route: rescue Vela, use the map while game lacks focus, warp, then click back after the room transition. Capture records mainChangeLevel at73.192s, no active-view clearing diagnostic, and a fresh shoulder acquisition in the new room exactly with focus-return at76.381s. Existing retained-view focus behavior stays stable in the later Tawfret focus interval. Source delays first view acquisition whenever input is blocked, even though the new room/player is valid; removing that focus-only acquisition veto is the next candidate. Physical input neutralization and native transition ownership remain required.

## Room-entry handoff candidate

The root cause of this new reproduction is delayed first acquisition: the
Modern view was cleared at the correct room lifetime boundary, but an input-focus
check prevented acquiring its replacement while the map had focus. Clicking back
enabled Modern ownership and abruptly replaced the new room's native view.

The candidate removes that focus-only veto. A valid new room/player acquires its
Modern view even while physical input remains suspended. Native entrance facing,
new actor/control identity, scripted-camera/pause exclusions and the input-release
gate are preserved. No outgoing room angle is carried into the new room.

The actual-source regression fails before the change at first unfocused room
acquisition and passes 2,979 checks after it. It covers Modern XInput, SDL and
keyboard/mouse, all three characters, repeated blocked updates, unchanged view
on focus return, fresh look afterward, retained-view focus behavior, and
Original/disconnected/invalid-state exclusions. Native build and owner visual
verification are tracked separately; this is still a candidate until owner review.
Private evidence: v131-rnd-20261019/focus-camera/room-entry.

Preview14 native build and eight focused component suites passed, followed by the combined source build including the separately accepted rain-delay fix and nine component suites. The owner is reviewing the new map-warp/focus-return candidate with Modern controller and keyboard/mouse. Visual confirmation is still pending at commit preparation.

## Owner acceptance of preview14

The owner answered "Fixed in both modes" after the requested test: use the map
to warp while it has focus, let the new room load, then click back into the game.
The Modern controller and mouse/keyboard view both remain stable and fresh look
still works. This accepts the local room-entry handoff correction. Original
exclusion is covered by the source regression; no new Original visual pass is
claimed. The earlier accepted focus correction and room-lifetime invalidation
remain intact. Release and broader gameplay coverage remain separate.
