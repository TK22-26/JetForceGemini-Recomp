# MOD-001: Exit warp stops at the door instead of entering the next room

- Severity: navigation tool malfunction; blocks convenient travel for the boss reproduction.
- Status: native-contact correction released in v1.2.1; ten transitions verified; progression-independent explicit map warps requested for 1.3.
- Reported: 2026-10-18 UTC, during the official v1.2.0 Ichor capture.
- Affected profile: Windows official release v1.2.0, Live Map Warp to exits enabled.
- Related source: include/jfg/mod/navigation_mod.hpp (NavigationMod::warp_to_exit).

## Symptoms and reproduction

Double-click a live exit with the warp mod enabled. The player moves to the
physical door but does not enter the next room. The owner explicitly expects
the click to activate the exit and change rooms.

## Evidence and cause

The current implementation writes the exit actor's exact XYZ position to the
player, then returns. The supported game's exitControl (0x8002561C) requires
a strict negative signed plane distance for directional exits. exitInit
constructs its plane through the actor position: the current target is on the
boundary, not inside the activation half-space. Collision and update ordering
can also undo a bare position change before the exit is visited.

Source review establishes the center-on-boundary flaw; this is not yet a
verified fix for every exit. The game queues an eligible contact using the
player control's pending-exit pointer and contact timer, then controlPlayer
consumes it through the ordinary level transition path. The correction should
preserve condition checks, destination/spawn selection, area-clear prompts,
one-shot requests, and stale-room/scripted-scene rejection.

## Attempts and results

2026-10-18: inspected the released warp and pinned guest exit/control paths.
No build, autonomous game test, or change to the owner's active process was
made while the owner was navigating.

## Verification and remaining limits

The source candidate and focused eligibility/one-shot tests are written.
Their execution and a real room transition in a new build remain pending. The active official release is unchanged.

## Lessons

Object centers are not necessarily valid trigger points. A warp intended to
enter an exit must satisfy its contact semantics and use the game's own
transition handling, rather than assigning the displayed room identifier.


## Candidate implementation (not yet tested)

The hotfix source now queues the exact contact produced by exitControl, after
validating its instruction layout, active player/health, current exit, native
progression conditions, and absence of an existing transition. The original
controlPlayer remains responsible for the destination, spawn and region/clear
prompt. It does not overwrite global level IDs, unlock quest flags or grant
items. A diagnostic event records accepted requests for later capture review.

Focused tests cover contact state in both memory byte orders, disabled/stale/
replayed commands, existing pending transitions, pause/death, missing progression
and unknown guest layout. They have been written but not executed while the owner
plays. The active v1.2.0 capture still uses the old behavior.


## Owner regression clarification and history review

The owner confirms that exit warp previously entered the next room. Treat this
as a reported regression, not an intentional change in expected behavior.
The committed warp function has used exit-origin placement since ce6042e
and that function is unchanged in the released v1.2.0 source. This narrows
the search to exit geometry, collision/update ordering, and interaction with
other runtime changes; it does not invalidate the owner's earlier working use.
No specific introducing commit has been established.


## Native transition checks

The focused navigation tests pass. The copied-save route now crosses the actual exits from levels 43, 42, 44, 248, 146, 185, 153, 151 and 119 using the candidate contact request. The first fixture then chose an inactive overlapping exit at level 19, which was correctly refused. The revised fixture selects the open progression alternative. No quest state is overwritten. Physical launcher click and final visual acceptance remain pending.

The revised active-exit fixture also crosses level 19 into introduction 230 and then reaches the boss at 181. Both effective-input runs accept all ten native exit requests. Launcher click acceptance is still pending.


## Released scope and 1.3 progression bypass

The native-contact correction ships in v1.2.1 (main 40dad7f4). Its ten recorded
room transitions and separate Juno/Lupus fixture entries are retained evidence;
this is not manual coverage of every map exit.

The owner explicitly requests that 1.3 map exit warps enter the selected
destination even when normal progression requirements are unmet. This is a
change to the explicit warp mod only. Ordinary walking contacts must retain
their progression rules. Preserve valid current player/exit/session checks,
request freshness and nonce handling, and native destination/spawn semantics.
Do not grant inventory items or permanently unlock quest flags to implement it.
Locked/overlapping exits require focused and native transition verification.
This follow-up is open under GitHub #21; no 1.3 bypass is released yet.

## 1.3 explicit warp progression bypass candidate

The owner requests unrestricted explicit map exit warps. The 1.3 candidate
removes the host progression predicate from that command only, while retaining
loaded-exit identity, current room/generation, nonce/age, active player,
instruction-layout and pending-transition checks. It still queues the native
contact and does not grant items, alter quest flags or patch ordinary exit logic.
The launcher help now describes the bypass.

The new focused regression fails against the 1.2.1 eligibility restriction,
then passes with the candidate in both memory byte orders. It covers missing
and unknown progression, exact selection between overlapping exits, unchanged
progression queries/flags, duplicate/stale commands and invalid gameplay states.
The first build wrapper could not locate CMake on PATH; no test ran in that
attempt. Using the retained qualified tool path completed both comparisons.
Launcher command checks and an actual locked-exit native transition are pending.
Private evidence: goldwood-exit-1.3-20261017/ungated-warps.

The first locked native fixture accepts Lupus's condition-24 exit but enters
introduction 352 instead of its selected fight 210; the Ichor fixture similarly
enters introduction 230 instead of 181. These are failures, despite passing
focused tests and reaching a different room. The first candidate can lose its
selected contact to an overlapping native exit before controlPlayer consumes it.
A follow-up retains the exact selection and reasserts it once at the native
player-update boundary, revalidating room/generation, player, live exit descriptor,
age and health. No progression flags change. Focused interleaving/removal/expiry
tests and a diagnostic of the replaced contact are added; native verification
is pending. Preserve the failed fixture evidence.

The boundary diagnostic confirms the race: Lupus's ordinary contact changed to
0x801ba170; the explicit selection restores 0x801bbcf0 and the native transition
receives destination 210. Ichor likewise receives selected destination 181.
Both untouched first-visit states subsequently request their native introduction
(352 / 230). The fixture assertion expecting an already-active boss therefore
still failed; this later native introduction is separate from the corrected
contact race. It is not evidence of reaching active combat or bypassing all
scripts inside a destination. The explicit warp bypasses door/exit progression,
while native first-visit scene handling remains intact.

Focused handoff checks pass, including a replaced contact, a removed exit,
expiry and generation changes. Both memory byte orders are exercised. The
launcher command tests/build pass; the merged runtime also passes navigation,
modern/PC input and unique-VI presentation checks. Both native probes were
muted/hidden and retained their original source saves. This verifies native
locked-exit handoff, not manual coverage of every launcher exit.
Private proof: ungated-warps/native-contact-verification.json.
