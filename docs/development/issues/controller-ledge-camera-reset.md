# CAMERA-007: modern dual-stick ledge climb recenters the camera

## Delivery and issue status — 2026-10-22 UTC

Ledge and swimming-transition corrections are released in v1.4.0 after local owner approval. The approved reply closes #30 and asks for a retest, with reopening if camera snapping persists.

[Release v1.4.0](https://github.com/TK22-26/JetForceGemini-Recomp/releases/tag/v1.4.0); [verified issue action](https://github.com/TK22-26/JetForceGemini-Recomp/issues/30#issuecomment-6332071353).
Earlier entries below preserve their original investigation and verification scope.

- Status: ledge/water camera and water-origin airborne facing owner-approved locally. Latest water-air preview accepted after single-instance relaunch; unreleased; #30 remains open for delivery and reporter retest.
- Severity: gameplay usability; abrupt disorienting view change.
- Report: [GitHub #30](https://github.com/TK22-26/JetForceGemini-Recomp/issues/30), 2026-10-19.
- Setup: Windows 10, RTX 5060 Ti, Xbox One controller, Modern dual-stick controls.
- Owner requests inclusion in a quick v1.3.1 together with #31.

## Reproduction and source distinction

Grab a ledge with the camera offset, then climb/jump onto it. The reporter says
the camera immediately snaps behind the character every time.
Character and exact ledge are not specified.

The v1.3 [mouse landing/ledge correction](mouse-camera-high-landing-reset.md)
deliberately retained mouse ownership only. The modern_ledge_view_current
gate in [native_boot.cpp](../../../src/boot/native_boot.cpp) requires the mouse
device selector. This identifies a coverage gap, not a complete measured cause
for the controller report. The earlier mouse acceptance is not controller proof.

## Intended remedy and checks

Retain player-selected dual-stick camera orientation during ordinary ledge
attachment/climb while leaving native body alignment, locomotion, collision,
action restrictions and scripted cameras intact. Verify both look sources,
inversion, approach angles, climb completion, death, dialogue and room changes.
Owner performs live visual verification; no autonomous gameplay authorized.

No source change, new component test, build or delivery exists yet. Public
comments remain on hold until owner review. Keep the mouse issue's historical
acceptance separate. Lesson: ownership fixes must explicitly cover each input
device path rather than assuming Modern Controls is one common path.


## Source cause and candidate (2026-10-19)

The retained-view predicate required device -3 (mouse). During humanoid ledge
states 6/7/8/12, ModernShoulderScope rejects ordinary locomotion ownership and
only preserves its saved view when that predicate permits camera-only ownership.
For XInput/SDL controllers it therefore clears the active PcShoulder. On climb
completion, reacquisition seeds the native body heading, producing the abrupt
recenter described by the reporter.

The candidate removes the mouse-only restriction from modern_ledge_view_current.
It retains the existing Modern-enabled, actor/control identity, native ledge and
script/action gates. Ledge movement remains excluded from modern locomotion,
body alignment and velocity writes. The controller look accumulator already
supports this retained-view path. Landing recovery's separate mouse restriction
is unchanged; this correction targets #30.

## Verification and remaining limits

A private harness extracts the actual ownership predicates and ModernShoulderScope
from native_boot.cpp and compiles them against real memory/look helpers. It uses
a small host State fixture, not a game replay. The old code fails preservation
for a connected controller. The candidate passes 720 assertions covering XInput,
SDL and mouse paths, both humanoid characters, all four ledge states, both look
directions, focus suspension, climb completion, control identity changes,
disconnects, original mappings and native/script locks. It checks that retaining
or moving the ledge camera does not write guest RAM.

The first harness version had incorrect look-sign and new-control expectations.
Those fixture mistakes were corrected before the baseline failure/candidate pass;
both attempts are preserved. This is not gameplay acceptance or proof of every
physical controller/inversion configuration.

The native Release build succeeds. jfg.navigation_mod, jfg.pc_input and
jfg.modern_controls pass. A new muted desktop shortcut, JFG - Controller Ledge Fix
Preview, uses an isolated copy of the latest lighting preview and its save/settings.
It includes the rain/reticle, controller-removal and fog candidates. The original
preview/profile remains unchanged. Owner should verify a ledge with the camera
offset, turn the right stick while attached, and climb without recentering.

Private evidence: D:/JFG-private/v131-rnd-20261019/controller-ledge.
No public reply, closure, commit or release was made.

Preview runtime SHA-256: 8dff015f855bde2d782ae53a7225a3d2e82fb618d5baa3ee7af3440b96945b93

## Owner validation, 2026-10-19 evening

The owner answered "Fixed" to the Modern controller ledge-climb test. Support
logs confirm the new ledge runtime (8dff015f...) was run, followed by the older
Tawfret Lighting Preview (cfac17af...). Mark #30 owner-confirmed locally,
unreleased; reporter hardware retest still pending. The separate lighting-run
lag is tracked in [PERF-005](tawfret-lighting-preview-stutter.md).

## Additional water-transition trigger (2026-10-20)

The original reporter added: "This also happens when you dive in and out of
the water". [Comment, 2026-10-20 19:20:26 UTC](https://github.com/TK22-26/JetForceGemini-Recomp/issues/30#issuecomment-6299273626).
This expands #30 beyond ledge attachment/climbing to an abrupt camera recenter
associated with entering/leaving water. The parent report names v1.3.0, Windows
10, RTX 5060 Ti, Xbox One controller and Modern dual-stick controls; the comment
does not specify a new build, character, location or exact transition.

Reproduction to establish: offset the camera from character heading, dive and
surface, then separately test shoreline entry/exit, recording which transition
snaps the view. Compare the current candidate with Original controls and Modern
mouse; do not assume all those paths are affected. Severity remains gameplay
usability/disorientation. No support ZIP or water-specific recording accompanies
this comment. The owner requested reopening the latest launcher to verify it.

Current result: **reported, not independently reproduced; no water-specific fix
is implemented or verified by this intake**. The accepted ledge and high-landing
fixes retain their established scope. Loss/reacquisition of camera ownership at
a swimming-state transition is a hypothesis, not a confirmed cause. No new
remedy or gameplay experiment was attempted. The actual cause remains open.

Historical swimming/dive/surface/shoreline replay coverage in
[PC controls](../../features/pc-controls.md) proves those recorded routes and
inputs, not preservation of an arbitrarily offset camera across every water
transition. Future checks must measure view continuity as well as movement
and control availability. Preserve native swimming physics, scripted cameras
and the accepted ledge/landing behavior when investigating this case.

Keep #30 open for the added trigger. No public reply or closure was performed.


## Owner reproduction and authorized fix (2026-10-20)

The owner reproduced the water camera reset in the latest capture and requested
a fix for both Modern controller and mouse/keyboard, approving two hours.
Capture ID: `issue30-water-followup-20261020/owner-sessions/20261020-210930-c8573c1f0bd94fec8ab4176de795b9c9`.
Runtime: `ab2ebd46007a8b28d5fee5302319ac502c6a82143eb7d37e9c00d494cb6726d5`.
The owner reproduction supersedes the intake's unconfirmed status. Cause analysis
and correction are in progress; no fix or completed validation is claimed yet.
The existing production guard/root/counters remain enabled and unchanged.


## Water camera cause and manual preview (2026-10-20)

The owner capture confirms twelve `pc-view-reset-cause` events with reason 4
while the actor is in native swimming state 4, connected Modern controller mode
5, and otherwise valid gameplay. This occurs as Juno in Goldwood room 26.
On returning to a supported land/air state, `pc-shoulder-acquire` seeds the
native body heading again instead of preserving the player's chosen camera.
Both Modern paths share the rejected swimming-state gate.

The candidate adds camera-only swimming ownership in
[native_boot.cpp](../../../src/boot/native_boot.cpp). It retains yaw/pitch and
integrates look input while native swimming continues to own heading and
movement. A session that starts in water can acquire its native initial view.
The ordinary shoulder locomotion predicate still excludes swimming. Updates
that begin swimming also skip ground-derived velocity/body/air-aim conversions
if native code changes to an airborne or shoreline state inside that update.
Original controls, gameplay/scripted-camera restrictions and actor/control
identity checks remain in place. This extends the ledge/landing retention
approach without adding swimming to the ground locomotion states.

Validation: 369 focused checks execute the actual source scopes/predicates for
mouse, XInput and SDL paths. Pre-fix cases fail on lost swimming view, initial
water acquisition and premature swim-to-air aim takeover; corrected cases pass.
The fixture checks guest RAM preservation while swimming and identity/lock
restrictions. Six native component suites pass (PC input, Modern controls/roll,
navigation, cutscene skip and audio), and the final runtime builds successfully.
These checks are not completed in-game water acceptance.

Informative failures: the first fixture incorrectly expected a replacement
control identity to stay inactive instead of acquiring a fresh native view;
the assertion was corrected before applying source changes. Two baseline
replays of the complete owner route, using poll-only and recorded native timing,
ended in room 47 without reaching water. Both cleanly ran with no unsupported
accesses but failed the required water-coverage assertions. They provide no
water-fix verification. Their evidence is retained rather than relabeled as
passes. The owner then requested manual validation and launcher handoff, so no
additional gameplay route experiments were attempted.

Private evidence: `D:/JFG-private/issue30-water-followup-20261020/`, including
the owner capture, scope regression baseline failures and final result,
`candidate-build-final.json`, `candidate-ctest-final.log`, both unsuccessful
route summaries, and `delivery.json`. The preview includes the accepted boss
aim fix and uses the accepted control-settings launcher. Settings and the
latest water-test save are copied into a separate profile; source saves remain
unchanged. No ROM, generated code or personal save data is published.

Manual checks still pending: offset-camera entry/exit, jump/surface/shoreline
transitions, look input, swimming movement and aim handoff with both Modern
presets. Vela diving and other characters need live coverage too. Keep #30 open
until this candidate is accepted and the reporter can retest a released build.
No commit, push, release or public reply accompanies this handoff.

Transferable lesson: separate camera retention from locomotion ownership for
native special states; check transitions within one guest update as well as
the state at its beginning. A route replay that never reaches the reported
state cannot establish compatibility or acceptance for that state.

Preview runtime SHA-256: `154e5806a5a747a30f8f669d07c82443ac8cbba28d8fc50bc52af4f86238b77d`.


## Water preview regression reported by owner (2026-10-20)

The owner reports that the camera gets stuck on Juno, cannot look out of the
water from above, and makes navigation difficult. This rejects the water
candidate; passing source checks did not establish usable swimming framing.
Capture: `water-preview-sessions/20261020-214943-2483bea230344998b614a88577554649`
under the private issue30 evidence directory; runtime SHA-256
`154e5806a5a747a30f8f669d07c82443ac8cbba28d8fc50bc52af4f86238b77d`.
Severity: gameplay usability regression. Reproduce as Juno entering/swimming
and attempting an overhead view with the candidate. Cause under analysis;
retained direction versus swimming camera framing/collision must be separated.
No replacement or validation is claimed at this intake.


## Trapped swimming camera: confirmed cause and correction (2026-10-20)

The new capture contains 708 swimming updates and no water view resets. Look
angles continue changing, but the ground camera boom contracts from 200 units
to as little as 7.9206 units. In 667 frames the native scenery query already
returns the requested clear endpoint. The added ground-distance recovery then
discards many of those points: its intermediate recovery distance intersects
the water-surface height-clearance band, repeatedly contracting near Juno even
when the requested overhead endpoint is clear. This is a regression introduced
by assigning the ground boom solver to retained swimming camera ownership.

The correction separates retained direction from ground-distance recovery.
`pc_camera_resolve` in [pc_input.hpp](../../../include/jfg/runtime/pc_input.hpp)
keeps the native collision-resolved swimming endpoint, applies the established
near-plane clearance, and clears the ground boom history. Ground states use the
existing solver unchanged. The call in
[native_boot.cpp](../../../src/boot/native_boot.cpp) selects this branch only
for qualified Modern swimming, without the ground-only height-plane override.
Direction retention, mouse/controller look integration, native water movement
and the water-to-air/shore safeguards remain. The trace distinguishes
`pc-swimming-camera` from `pc-camera-boom`.

Validation:
- 106 added collision checks in [pc_input_tests.cpp](../../../tests/pc_input_tests.cpp)
  reproduce the surface-band trap, retain the valid overhead endpoint at
  30/60/120 updates, preserve native ceiling/wall corrections, clear distance
  history before landing, and compare ground results with the previous solver.
  The pre-correction branch fails the overhead endpoint assertion.
- The initial synthetic fixture omitted the post-contact recovery hold and
  stepped past the narrow band; its setup assertion failed. The fixture now
  includes that solver state. This informative failure is preserved separately.
- The actual 708 recorded swimming collision endpoints pass through the compiled
  corrected host resolver. All 667 native-clear endpoints remain clear; this
  restores 364 previously collapsed clear-camera frames and 139 overhead frames
  without extra collision queries. This checks recorded collision results,
  not a full gameplay replay or new visual acceptance.
- All 369 retained-view scope checks still pass. Six native component suites
  pass; the PC input executable reports 1724 checks. The corrected runtime
  builds, package hashes/support symbols match, and launcher Init/Setup pass.

Private evidence remains in `D:/JFG-private/issue30-water-followup-20261020/`:
`regression-camera-summary.json`, `water-collision-regression.json`,
`recorded-water-camera-point-check.json`, `corrected-water-build.json`,
`corrected-water-ctest.log`, and `delivery-corrected.json`. The rejected build
and its capture remain intact. Preview 2 copies the latest water-test settings
and save into a separate profile. Owner manual overhead-view/navigation,
entry/exit and both Modern input checks remain pending; Vela diving is also
not yet live-verified. No commit, push, public reply or release.

Lesson: a native-clear endpoint above water does not imply that every point
along a ground camera recovery path is acceptable. Camera-direction retention
needs collision/framing coverage as well as state-transition tests.

Corrected runtime SHA-256: `c187d82471838a3c43bde260669f56b86638f982b0b24fba8b9564cd9886d6c1`.

## Water camera accepted; water-to-air body-facing snap (2026-10-21 UTC)

The owner confirms "camera fix works" and approves the ability to face away
from the camera while swimming. This is local acceptance of preview 2's water
camera correction, not verification of every character/device combination.
The owner separately reports Juno snapping toward the Modern camera heading
when a jump or brief surface departure enters the airborne state, then snapping
back to his swimming heading on re-entry. Severity: visible gameplay/control
transition regression. Reproduction: swim with Juno facing away from the view,
then jump or briefly leave the surface and fall back into water.

Existing capture reviewed read-only:
`water-preview-v2-sessions/20261021-000609-e0e6e32836e64985888bb1eb1bb30e52`
in the private issue30 evidence directory, runtime `c187d824...`. The owner game
was still running during review and was left intact. At VI `0x16a2` Juno is
swimming with body/control heading `0x3e11` while retained view yaw is `0x7edb`.
At `0x16a4` he is airborne with body/control `0x3b28`. At `0x16a6` and `0x16a8`
the body becomes `0x7edb` while native control heading continues `0x3604` and
`0x31ad`. At `0x16aa`, swimming resumes with body/control `0x2fc3`; retained
view yaw stays `0x7edb` throughout. These rows directly show the facing switch
without a camera reset.

Source explanation: `movement_before_state == 4` protects only an update that
starts swimming. The following airborne update records state 3, so
`ModernAirPhysicsScope` resumes writing the retained view yaw to the visible
actor after native physics. Native swimming then restores movement-facing on
re-entry. No direction-independent camera change is needed for this symptom.

Proposed remedy, NOT implemented: retain native movement-facing for the entire
airborne excursion that originated in swimming, including repeated water/air
transitions. Release it on confirmed solid-ground contact or an intentional
valid aiming takeover. Consider a short visual turn when restoring ordinary
ground-facing, while leaving camera direction, trajectory and collision native.
Do not use a fixed grace timer that expires during a longer jump, or freeze
the exact takeoff heading and prevent normal native steering. Reset ownership
on actor/control/area changes and test both Modern paths, aim, shore landings,
repeated surface hops, and Original controls. This proposal has not been built
or tested. No gameplay edits or new experiments were run for this review; the
previous water work window ended at 2026-10-20 23:12:51 UTC. A separate active
Quarry investigation does not extend the water authorization.

Lesson: remembering only the previous update's movement state cannot preserve
ownership over a multi-update excursion. Track the origin and actual end of
the movement episode separately from per-update physics state.


## Water-air facing implementation authorized (2026-10-21 UTC)

Owner approved one hour to fix the diagnosed body-facing snap. The accepted
water camera remains the baseline. Candidate implementation and tests are in
progress for both Modern input paths; no new live acceptance is claimed.
Private evidence: `D:/JFG-private/water-air-facing-20261021/`. Same production
guard, root and counters are retained; no parallel agents, commit or release.


## Water-origin airborne facing candidate and checks (2026-10-21 UTC)

The candidate adds `water_origin` to the existing actor/control-owned
`PcShoulder` state in [pc_input.hpp](../../../include/jfg/runtime/pc_input.hpp).
Qualified swimming sets it; airborne updates retain it. Native ground or another
special locomotion state clears it, and the existing view lifetime reset clears
it on actor/control, room, mode or gameplay-ownership changes.

`ModernShoulderScope` records that origin after acquiring the current identity.
`ModernAirPhysicsScope` in
[native_boot.cpp](../../../src/boot/native_boot.cpp) leaves the native body
heading untouched during the complete water-origin airborne excursion, except
when the existing qualified air-aim path deliberately takes ownership. Aiming
does not erase water origin, so releasing aim during that same jump returns to
native movement-facing. The first-update water physics/aim safeguards remain.
The native steering heading is followed rather than freezing a takeoff angle.
No camera, movement, collision, land-jump facing or ground velocity algorithm
is changed. Normal ground-facing resumes on native landing; no additional
visual blending is introduced without evidence that it is needed.

Validation and scope:
- The actual extracted shoulder/air-physics scopes reproduce the old failure
  on the second airborne update. The candidate passes 4437 checks over mouse,
  XInput and SDL paths and all three character physics dispatches. Coverage
  includes 120 consecutive air updates, changing native headings, repeated
  surface hops, re-entry, solid-ground landing, later land-origin jumps,
  deliberate air aim/release, focus suspension/return, accepted view retention,
  native velocity preservation and existing gameplay-ownership restrictions.
- All 39 water-origin airborne excursions in the owner's capture were checked
  with the actual source scopes using recorded native/view headings and aim
  input on all three Modern input paths. Camera and native steering remain
  unchanged; the visible body follows native facing except qualified aim.
  This is a source-scope check of recorded transitions, not a full game replay.
- Six native component suites pass. The PC input executable reports 1927
  checks, including long water-origin lifetime and identity/ground reset cases,
  and the accepted swimming collision regression coverage. The native runtime
  builds; package hashes, symbols/support identity and launcher Init/Setup pass.

Private evidence: `D:/JFG-private/water-air-facing-20261021/`, especially
`capture-water-air-excursions.json`, baseline/candidate scope logs,
`scope-result.json`, `recorded-transition-result.json`, `candidate-build.json`,
`candidate-ctest.log` and `delivery.json`. Preview:
`C:/JFG-previews/water-air-facing-20261021`. It copies the latest accepted Water
Camera Preview 2 profile and keeps the prior save/profile intact.

Owner live verification remains pending: repeat Juno's small surface departures
while facing away from the camera, a full jump back into water, shore landing,
and deliberate aiming/release with both Modern presets. Broader Vela/Lupus live
coverage is not inferred from the source fixture. The accepted water camera
remains accepted; this new body-facing candidate is not yet owner-confirmed.
No commit, push, release or public reply.

Candidate runtime SHA-256: `7fc37d2d185da7bc746afcfdc0c15cfe63af14e81c4f4035ad574f9a2e453700`.

Recorded transition result: `RECORDED excursions=39 samples=1482 changed_body_frames=1365 aim_samples=0
PASS 8883 water-view actual-scope checks`.


## Camera jump report and isolated relaunch (2026-10-21 UTC)

Owner reported the camera jumping behind Juno, then clarified that two agents
had opened JFG concurrently and requested a relaunch. The water-air candidate
owner-sessions directory was empty before this request; the affected runtime
is not yet established. Concurrent launch is a test ambiguity, not a proven
root cause. No camera code was changed in response to this ambiguous run.
The exact packaged water-air candidate was reopened after confirming no JFG
launcher/game was active; a single visible launcher was verified. Single-instance
owner retest is pending, with diagnostics directed to the candidate evidence
folder. Preserve the reported regression until that retest resolves attribution.
Private receipt: `D:/JFG-private/water-air-facing-20261021/preview-reopen-20261021.json`.


## Owner acceptance after isolated relaunch (2026-10-21 UTC)

Owner tested the reopened water-air preview and explicitly accepted it:
"approved - this works well". This supersedes the pending owner acceptance
above for the combined water-camera and water-origin airborne-facing behavior.
No further owner acceptance gate remains for this preview.

The captured session is
`D:/JFG-private/water-air-facing-20261021/owner-sessions/20261021-002900-9412dbe681ae4f118b60b62c010550cb`.
Its session identity matches accepted runtime SHA-256
`7fc37d2d185da7bc746afcfdc0c15cfe63af14e81c4f4035ad574f9a2e453700`
and `C:/JFG-previews/water-air-facing-20261021`. The private acceptance receipt
is `D:/JFG-private/water-air-facing-20261021/owner-acceptance.json`.
The earlier camera-jump report and concurrent-launch ambiguity remain historical
evidence; neither the affected runtime nor concurrent-launch causality was
established. The owner's subsequent isolated retest accepts the packaged fix.
No additional camera code change was made between these two reports.

The final body-facing cause was that the per-update swimming safeguard expired
on the second airborne update, letting Modern air physics overwrite native
body heading with camera heading before swimming restored native heading.
Retaining water origin throughout the airborne excursion preserves native
steering/facing, while normal ground contact and qualified air aim retain their
intended ownership. The previously accepted native swimming camera collision
resolution is preserved. Both Modern input paths have source/component coverage;
this acceptance does not invent an unreported live device/character matrix or
turn the recorded-transition fixture into a full game replay.

The prior source, recorded-transition and component checks remain the validation
basis alongside this owner live acceptance. No gameplay changes or additional
experiments were needed to record acceptance. Remaining work is release/delivery
and asking the #30 reporter to retest. No commit, push, public comment or issue
closure was performed. Keep #30 open until delivery/retest is handled.
