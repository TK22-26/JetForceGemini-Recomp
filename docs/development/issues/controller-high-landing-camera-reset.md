# CAMERA-008: Modern controller high-drop landing resets the view

- Status: candidate implemented; actual-scope regression passes; native build and three focused suites pass; owner confirms the landing fix locally; unreleased.
- Severity: gameplay usability; disorienting camera reset.
- Reported: owner, 2026-10-19 evening while reviewing SS Anubis ledges.
- Affected: v1.3 and the first #30 controller-ledge candidate using Modern controller controls. The mouse path was already corrected.

## Reproduction and cause

Look downward or turn the camera away from the character's facing, fall far
enough to trigger the native landing recovery, and land. The view resets.
This differs from #30's ledge attachment/climb and needs its own acceptance.

The retained landing-view predicate in src/boot/native_boot.cpp explicitly
required device -3 (mouse). During the humanoid high-landing action, normal
gameplay ownership is correctly denied while the landing timer/native input
lock is active. Controllers could not enter the camera-only fallback, so their
saved shoulder view was cleared and subsequently reacquired from native
orientation. The existing mouse fix already distinguished this recovery from
dialogue, damage and scripted control.

## Candidate remedy and checks

Remove the mouse-device restriction from modern_landing_view_current, retaining
Modern-enabled, actor/control identity and native landing predicates. The same
camera-only branch now supports XInput, SDL and mouse look. It does not unlock
movement or change native landing animation, velocity, facing or recovery timer.

A private harness compiles the actual predicates and ModernShoulderScope with
real navigation/look helpers. The previous source fails the controller
landing-retention assertion. The candidate passes 486 assertions covering
XInput/SDL/mouse, Juno/Vela landing clips, timer 30/2/1, published/unpublished
input lock, final stale-lock tick, post-landing view retention, both mapped
look directions, focus suspension, script/boss/door locks, non-landing actions,
Original mappings, legacy inputs, disconnection and control identity changes.
Full guest-memory comparison verifies that the camera-only path does not
write movement/action state.

The owner confirmed the landing fix on 2026-10-19. This is not a claim for Lupus-specific recovery.
Lupus is excluded by the original humanoid landing predicate. Preserve that
scope until an independently observed Lupus behavior warrants investigation.

Private evidence: D:/JFG-private/v131-rnd-20261019/controller-landing.
Related: [mouse recovery](mouse-camera-high-landing-reset.md),
[controller ledges](controller-ledge-camera-reset.md).
No public reply, commit or release was made.

Combined ledge regression passes 720 assertions, in addition to 486 landing
assertions. Native Release build and jfg.navigation_mod, jfg.pc_input and
jfg.modern_controls pass. Desktop JFG - Controller Camera Fix Preview is
prepared with the new runtime 0bec5b766804429a68a39ea1ed8f482cfa4b284f635b3743528efdff782c987b.
The launcher was opened muted; the owner performs the gameplay check.

Owner response: "Fixed". The same response reports a separate camera reset on window focus loss; see [CAMERA-009](focus-loss-camera-reset.md).
