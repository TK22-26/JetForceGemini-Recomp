# GH-037: Floyd cannot fire

- Status: fully approved locally by owner for v1.4.0. Reporter re-verification after delivery remains pending; no extra local acceptance gate.
- Severity: potentially blocks completion of Floyd missions.
- Report: [GitHub #37](https://github.com/TK22-26/JetForceGemini-Recomp/issues/37), 2026-10-20; audited 2026-10-21 UTC.
- Setup: Windows 10; input device, control preset, bindings and exact mission unspecified.

The reporter says Floyd cannot shoot on every attempt, preventing some missions
from being completed. No support ZIP, recording or further comments were attached
at this audit. The reproduction currently consists only of entering a Floyd
mission and trying to fire; the affected mission and control setup need confirmation.

No cause is established. Input routing, bindings and native mission behavior are
possible investigation areas, not findings. No remedy or runtime test was attempted
as part of issue reconciliation. Compare the same mission with Original and Modern
controls, keyboard/mouse and controller, after obtaining the reporter's setup.

Keep this separate from the accepted character boss-aim and sideways-roll fixes.
Ordinary character shooting tests do not establish Floyd mission compatibility.
Record a same-state reproduction and actual mission completion before claiming a
fix. No commit, build or owner acceptance for another issue resolves this report.


## Owner test tooling request (2026-10-21 UTC)
Owner recalls Floyd firing previously working and will test manually. The initial
save/diagnostic-launch request was replaced with an explicit Give Floyd action
in Tools > Map > Settings > Mods. Implementation and native unlock verification
are in progress. This test aid does not establish or fix the #37 firing report.
No normal save is modified by preparing the tool.

Implementation note: the first scripted edit stopped on a nonunique match for the
navigation command count. Both the action reader and AI reader share that count;
the corrective step updates both together for the new fifth command file. No game
was run with the partial edit. This is test-tool plumbing, not a Floyd fire fix.

The first test build caught a shadowed fixture variable under warnings-as-errors.
The runtime compiled; the fixture variable was renamed before test rerun.

The offscreen UI check initially returned usage error 2 because its output
directory argument was omitted; rerunning with that required argument passed.
No game was launched by this check.

## Candidate delivery

Give Floyd now exists in Tools > Map > Settings > Mods. It sets current-game
flag 3 only; the original room loader spawns Floyd after entering another room.
Saving retains the unlock. Native flag inspection, both memory-layout tests,
launcher bridge tests, builds and packaged init/setup checks passed. These are
tool checks, not a gameplay or firing verification. Owner will test shooting.
Private evidence: D:/JFG-private/give-floyd-mod-20261021; preview: Give Floyd
Preview desktop shortcut. See [feature notes](../../features/navigation-mod.md).

## Corrected preview packaging

Owner screenshot showed the first preview omitted Give Floyd. The private
CMake copy retained forward-slash paths to the older launcher snapshot because
the path replacement used Windows backslashes. The new helper/runtime passed
but that did not validate the compiled UI source. Corrected every source/include
root, rebuilt, and added an offscreen real Mods-panel visibility/label/capability
check with a rendered image. This supersedes the first UI/package completion
claim. Source dependencies and the delivered executable must both be checked
when reusing private build recipes. Shooting remains owner-tested separately.

## Owner confirmation: Player 2 ignores all input (2026-10-21 UTC)

Owner first reports Floyd does not work with Player 2 controls, then clarifies:
"it seems to ignore all input - im using keyboard and mouse modern controls but
it also ignores the controller modern controls". This broadens the local symptom
beyond the reporter's inability to shoot. Reproduction: use corrected Give Floyd
preview, unlock Floyd, enter another room, assign the second player to Modern
keyboard/mouse or Modern controller, and try controlling him. Owner confirms
both paths ignore input. Exact room and sidekick-versus-mission context remain
to be established; Original controls have not been compared in this report.

Affected private runtime SHA-256: eece486e47ead7aff39c674c4791e9be50e908d9704c420cf13d9f8c3f1be4ba.
Private evidence: D:/JFG-private/give-floyd-mod-20261021/p2-report; latest session
20261021-011038-9031d5ba06d44554bbeb6c8642f91380. Source/profile snapshots retained; no personal save is published.
Shared Modern Player 2 routing/context gating is a hypothesis, not a proven
cause. No firing/control remedy has been attempted. The Give Floyd unlock
aid must not be confused with a fix for this input regression.

## Corrected owner scope and four-hour approval

The owner corrects the earlier two-preset P2 comparison: Modern controls are
only selectable for P1. They explicitly confirm two bugs: Modern controls for
P2-P4 are broken, and Floyd does not respond to any Player 2 input. Investigate
both; the absence of Modern configuration is not yet proven to cause the native
Floyd input failure. The previous claimed Modern P2 test is superseded.

Owner approved four hours on 2026-10-21 UTC, bounded through05:14:28 UTC,
with the enabled production guard and existing investigation/root/counters
preserved. Evidence: D:/JFG-private/floyd-p2-modern-20261021. The failed step919
corrective note was denied by its expired prior-window assertion; this approval
authorizes the correction and new scoped work. No direct fallback was run.

See [secondary-player Modern controls](modern-controls-secondary-players.md)
for the separate configuration/runtime qualification. No remedy yet tested.

## Native co-op join gate identified

Native Floyd sidekick handler0x8002F728 reads P2 Start edges (0x1000 through
0x80043510 with port1) and toggles0x800A4FC8 / sidekick control+0x94 bit7.
The owner confirms they had NOT tried P2 Start/Pause. Consequently the inactive
co-op report is not yet proof of a runtime input bug; guided join/aim/fire retest
is pending. The original report mentions Floyd missions, which are a different
context and still need testing. The P2-P4 Modern restriction is independently
confirmed: UI modernMode/style handler and runtime modern_controls_selected
explicitly reject nonzero ports. Do not conflate the join prerequisite, per-port
Modern restriction, and P1 Floyd mission fire mapping.

## Current findings and candidate (2026-10-21 UTC)

Owner explicitly confirmed Start/Pause had not been tried on P2. Native
sidekickControl reads the P2 Start edge before enabling co-op. The private
owner dump has co-op disabled and sidekick join bit clear; it does not establish
a failure after joining. Earlier "all input failure" wording is superseded by
this qualification. A first dump decode incorrectly assumed live word-swapped
layout; invalid pointers rejected it. Correct canonical-big-endian decoding is
preserved beside the failed attempt.

Modern sampling previously rejected owner control +0x10D, including active
Floyd mission mode 1, then used menu mappings which omit Fire. The candidate
qualifies the native Floyd route separately, retains locked mission mode 3,
maps Fire to native Z, and adapts separate look to Floyd's absolute reticle.
The original join/leave, flight physics and pressed-shot handling stay native.
Jump/Interact accelerate and Crouch brakes in missions. This is source evidence
and a candidate remedy; mission completion and owner acceptance remain pending.

Player input must use the guest's logical-to-controller-port table. Competitive
multiplayer inventory and camera selection still use the logical player. These
are different identities; simply indexing all state by control[0] is insufficient.

The prior guarded job expired during the first runtime build. Its partial build
is not validation. The already-authorized four-hour continuation retained the
same production ledger, investigation root and counters, with the guard enabled.
The pending unexecuted remap step and rebuild continue through that supervisor.

Validation attempts: runtime compiled, but the first new PC-input test build failed warnings-as-errors because local aim/held names shadowed earlier fixtures. Renamed those locals. A scoped source-edit step also stopped on two camera-consumer matches instead of one; both sites are now handled, preserving the partial-edit evidence. No failed attempt counted as a passing test.

Native fixture follow-up: the first routing run stopped at the original deadzone getter, absent from the fixture dispatcher. Included that original routine and retained the failure. Native sidekick routing gives an already-joined P2 priority over the mission owner; candidate context now mirrors that precedence.

## Owner preview opened

Modern Players and Floyd Preview launched at the owner's request. Runtime and
four focused component suites pass; real UI passed 896 checks. Original native
sidekick/input routines passed 487 checks across 72 routing cases, including
Start join/leave, controller remaps and mission input locks. The owner capture
confirms the old Modern mission predicate drops Fire. Native routing checks do
not establish live reticle feel, multiplayer camera behavior or mission completion.
Those remain pending owner testing. Source profile/save preserved. Evidence:
D:/JFG-private/floyd-p2-modern-20261021/delivery.json and launch.json.

Owner preview result: Floyd input works after joining. Modern mouse vertical direction is inverted despite P2 setting Off (also confirmed in saved profile). Follow-up cause/remedy/testing: [Floyd vertical inversion](modern-floyd-vertical-inversion.md). Owner closed preview; prepare corrected runtime for retest. Mission completion and broader multiplayer qualification remain open.

Owner reproduced [vertical inversion with Off](modern-floyd-vertical-inversion.md) in preview 1. The new adapter missed the native Y conversion; preview 2 corrects both devices and preserves P2 settings. Original native consumer tests pass 96 Off/On motion cases. Launcher reopened for owner retest; no mission-completion or released-resolution claim.

Owner accepts the preview2 direction fix. [EmuHawk bounds comparison](floyd-widescreen-aim-bounds.md) confirms the limited co-op aiming area is original behavior; mouse matches and controller cardinal endpoints match. Controller diagonals remain a separate open response issue. No full mission-completion or release claim.

Approved follow-up corrects the Modern controller diagonal reach in preview3, with64 original-consumer cases and4 component suites passing. Source and preview are ready; owner physical-controller test and actual Floyd mission completion remain pending. Original widescreen limits preserved.

Owner cannot activate the SS Anubis mission pad after Give Floyd and changing rooms in preview4. Mission testing is blocked pending [pad access investigation](give-floyd-mission-pad-access.md). Co-op input acceptance is not minigame acceptance.

Owner reached the SS Anubis Floyd mission and reports W/S pitch reversed relative to Modern expectations and no mouse flight steering. Approved [Modern M/K mission remapping](modern-floyd-mission-mouse-flight.md): mouse steering, W thrust/S brake. This does not accept shooting or mission completion; both remain unverified.

Preview5 implements the approved [Modern M/K mission controls](modern-floyd-mission-mouse-flight.md): mouse steers flight/aim, W thrust and S brake, left-click Fire, E pad interaction. Runtime/four suites and 302 native/adapter cases pass, including original throttle/brake and Fire packet delivery. Actual shots and mission completion still require owner verification; #37 remains open. The SS Anubis pad entry blocker was explained by the original Mizar-token requirement and owner subsequently entered the mission.

Owner reports preview5 mission mouse flight feels pretty good and requests A/D strafing. Preview6 implements lateral flight; native velocity/position tests pass. This feedback does not establish actual firing or mission completion; #37 remains pending those checks. See the mission control issue for coverage and preview identity.


Preview7 adds the owner-requested [separate Modern controller flight inversion setting](modern-floyd-controller-flight-inversion.md), default On. Native flight and launcher checks pass; actual firing and mission completion still await owner verification. This does not close #37.

Owner approved the preview7 controls on 2026-10-21. Controller flight preference and the delivered controls preview are accepted locally. The reply does not separately confirm actual firing or mission completion; retain those outstanding #37 checks. No GitHub closure, commit, push or release performed.


## Full owner acceptance for v1.4.0 (2026-10-21)

The owner explicitly states Floyd is fully approved locally and requests reporter
re-verification after delivery. This supersedes older pending local firing,
mission-completion and controller-acceptance statuses in this historical record.
Do not invent a particular mission or route beyond that owner acceptance. The
release is now v1.4.0; no public reply or issue closure is authorized by this note.
