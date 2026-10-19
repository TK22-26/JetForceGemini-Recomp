# CAMERA-006: mouse camera angle resets after a high landing

- Severity: gameplay/control usability regression.
- Status: FIXED in local v1.3 candidate; component checks and owner live confirmation cover both high-drop landing and ledge-climb camera retention. Unreleased.
- Reported and last updated (UTC): 2026-10-18.
- Affected: owner using mouse Modern Controls in the v1.3 private blur review.
  Runtime at report: 982e43fc44aa82bc4645e97780337735e02c33b675426aba9d5261a7021fc025.
  Other versions and controller modes are unconfirmed.

## Symptoms and reproduction

Fall from a high place while looking toward the landing ground, then land.
Owner reports an awkward camera-angle reset, described as resetting
"looking down/straight" rather than keeping the chosen downward view.
Precise direction, landing animation, damage state and reproducible location
remain unmeasured. Do not relabel this as a collision bob without evidence.

Expected: preserve mouse-selected orientation across ordinary landing and
landing recovery, while retaining native physics, damage, animation and
scripted-camera ownership.

## Evidence and hypotheses

Owner report received during the isolated Vela blur review. That diagnostic
captures rendering metadata, not complete player-state/mouse history; the
current run alone may not identify the landing transition. No agent gameplay
or visual verification is authorized in the owner-led review workflow.

Inspect ModernShoulderScope / modern_shoulder_physics in
[src/boot/native_boot.cpp](../../../src/boot/native_boot.cpp) and shoulder
ownership in [pc_input.hpp](../../../include/jfg/runtime/pc_input.hpp).
Ordinary airborne aim already has a landing pitch-retention path, but special
landing/recovery states may discard the persistent view and reacquire the
native reset pitch. This is a hypothesis, not a confirmed cause.
Related: [crouch inversion](crouch-mouse-inversion.md),
[camera collisions](camera-collision-bounce.md),
[state transitions](modern-controller-state-transitions.md).
Pinned upstream reference review/catalog consulted; no dependency update.

## Attempts and results

Initial source inspection only. No gameplay changes, test replay, save edits
or replacement of the running owner preview. Record state-specific evidence
before changing the scope of input/camera ownership.

## Resolution and acceptance

Open. Preserve chosen pitch without disabling landing physics or required
scenery collision. Cover ordinary/high landings, Aim held/released, mouse
inversion preferences, death/scripted locks and character/area changes.
Component checks can verify state policy; owner must verify live feel.

## Lessons

Persistent view direction and native locomotion/camera control are separate
lifetimes. A temporary landing animation need not mean a new user-selected
view, but retaining orientation must not seize scripted camera control.

### Capture preparation limitation

An optional memory-buffered gameplay trace was attempted alongside the next
owner cutscene comparison. The normal launcher strips inherited JFG_ selectors,
so the trace file was not created. Owner informed immediately; the running
normal-effect comparison remains untouched. It logs FPS only and cannot be
claimed as complete camera-transition evidence. A dedicated private capture
must apply diagnostics after that sanitization boundary. Do not weaken normal
launcher environment isolation globally to enable a private diagnostic.

## Source cause and candidate, 2026-10-18

The original Juno air handler (00F03740) starts landing animation 0x1A and a
30-tick control+0x56B timer after a high drop; Vela uses animation 0x19.
Our strict action predicate rejects that timer. Both input polling and
ModernShoulderScope then discard the saved mouse view, and raw mouse capture
stops. The later reacquisition seeds the native reset pitch instead of retaining
the owner's selected downward angle. This is a concrete source path; live
state capture and owner acceptance remain pending.

Candidate separates camera-only ownership for this validated landing recovery
from movement/action ownership. It retains the current mouse-view identity,
orientation and scenery collision, including the timer-expiry/global-lock
handoff. Native landing animation, timer, gravity, damage and action gates are
unchanged. Ordinary scripted/door/dialogue/death gates still release ownership.
Only Juno/Vela landing clips are recognized; Lupus has no matching timer-setting
landing path in the reviewed code. Controller ownership is unchanged.

Focused checks cover both clips, timer countdown/expiry, stale global lock,
action rejection, damage and script/menu rejection. Owner must check live mouse
feel; no agent gameplay or visual testing was performed.

Integrated candidate builds successfully; 371 PC-input checks and navigation/action-lock fixtures pass. Private JFG - Glass and Controls Review desktop launcher prepared, with copied pre-rescue save, normal blur effects, muted 120 FPS/VSync and buffered controls/FPS logging. Runtime SHA-256: 669acb5f0cf377a40bd4f57cf7fd907a32890ee9141c01e1f2b7727426c845b2. Live owner verification pending; no autonomous gameplay performed.

## Additional owner report: ledge climb, 2026-10-18

In runtime 669acb5f0cf377a40bd4f57cf7fd907a32890ee9141c01e1f2b7727426c845b2
(JFG - Glass and Controls Review), grabbing a ledge and then jumping/climbing
onto it resets the mouse camera. This is a related newly reported transition,
not confirmation of the high-fall candidate. Its state path is under inspection.
The owner is playing; the process and copied save must remain untouched.

### Ledge capture and second candidate

The completed owner trace shows eight entries into movement state 12 followed
by loss/reacquisition of the shoulder view. The original adapter only accepted
states 0-3/10/11. Native Juno/Vela group ledge attachment/climb states 6/7/8/12
around their attached-surface pointer; these handlers own body alignment.

The candidate retains mouse camera ownership through those states while
excluding them from modern locomotion, body-heading writes and airborne
momentum adaptation. Native grab/climb controls, physics, collision and action
locks remain active. Only camera consumers use the retained orientation.
Original/controller modes and scripted/death/door states are not broadened.
Owner live verification is still required; no agent gameplay was performed.

Combined private Motion Clarity Review prepared on 2026-10-18. Runtime SHA-256: 8c81e21948e0af3a269b875dc3147d7f80c46d2a9f1f9e6b98bc955ed3ab80b8. Build and focused navigation, semantic-presentation and 371 PC-input checks pass. Latest owner save/settings copied to an isolated profile, originals unchanged. Muted 120 FPS/VSync with buffered FPS, controls, blur-copy and glass-match evidence. This is not live verification or a release; the owner performs gameplay/visual review.

Owner confirms on 2026-10-18: "jumping from ledge grab is now fixed" in Motion Clarity Review runtime 8c81e21948e0af3a269b875dc3147d7f80c46d2a9f1f9e6b98bc955ed3ab80b8. Ledge-climb reset is live-verified locally; high-drop landing remains a separate acceptance item. No stable release yet.

## Owner high-drop acceptance (2026-10-19)

The owner explicitly confirms the high-drop mouse-camera reset is fixed. This supplements the earlier ledge-climb acceptance and closes the pending live check for the reported mouse/Modern Controls transitions. Component and source evidence above remain the recorded cause/remedy; other characters and unusual states retain their stated coverage limits. No new gameplay change or stable release is claimed.
