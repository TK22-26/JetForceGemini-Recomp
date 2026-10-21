# DIAG-003: Cutscene selector rejects a running game

- Reported: 2026-10-20.
- Severity: blocks the private direct-entry cutscene review workflow.
- Affected: Cutscene Review selector, including its refreshed audio/menu package.
- Status: process-family correction passes focused checks; owner confirms the selector now loads a scene. All-scene/character coverage and skip completion remain unverified. Private diagnostic tool only.

## Symptoms and reproduction

Start the review launcher, press Play, load the copied save and press Load scene.
The game keeps running without entering the selected scene. The selector reports
that a game must be started even though one is already open.

The captured process list contains one launcher, native parent PID4556 and its
normal phase-six child PID34408. Both native processes have the same executable.
The selector required exactly one matching process, so it returned before writing
the request. The request file remained empty. This identifies a selector-side
failure before any runtime scene transition.

## Cause and remedy

The original guard counted processes as game sessions. The runtime's normal
parent/child architecture makes that assumption false. It was not a settings,
focus or native scene-load rejection.

The private selector now counts roots of matching native process families using
ProcessId/ParentProcessId. A native child of a matching native parent belongs to
that same game. No game still prompts the owner to start one; multiple independent
families produce a separate, accurate message to close the extra game.

The existing package path restriction, front-end/transition checks in the runtime,
request freshness/nonce checks and scene validation remain in force. No request
was sent and no gameplay was exercised automatically during this correction.

## Validation and remaining limits

The original live process list demonstrates two matching native processes and an
empty request file. The corrected selector smoke covers no process, launcher only,
one native process, parent/child, child-first enumeration and two independent
parent/child families. Existing 168-entry UI/search checks also pass.

The owner closed both launcher and game before the corrected selector handoff.
The owner then confirmed "ok its now working" after the refreshed selector was
opened. This verifies the corrected Load scene handoff for the tested entry;
it does not approve every variant, character or skip completion. Other scene-entry
dependencies and cutscene completion remain separate tests.

Private evidence: v131-rnd-20261019/steps/620-inspect-selector-no-load,
cutscene-skip/selector-no-load-20261020 and
cutscene-skip/selector-refresh-20261020. The corrected private UI source is
retained as cutscene-review-source/Review-Cutscenes.ps1. No ROM or save is published.

## Transferable lesson

Count sessions according to the runtime process topology. A UI construction smoke
test cannot validate an assumption about how many processes a live game creates.
Include the ordinary parent/child shape in diagnostic-tool guard checks.

See [the inventory and owner workflow](../cutscene-skip-review.md) and
[cutscene skip implementation](optional-cutscene-skipping.md).

## Character mapping and live-review findings (2026-10-20)

Owner reports Juno selects Vela and Vela selects Juno. Confirmed source error:
the selector sent its UI SelectedIndex (Juno-first) directly as the native ID.
The existing inventory implementation and tests establish Vela=0, Juno=1, Lupus=2.
The selector now maps names explicitly; focused mapping and save/reopen checks
pass. Owner visual check of corrected mapping is pending. Existing notes retain
the names the owner selected; reports made before the corrected selector restart
must be interpreted with the Juno/Vela swap. No user annotations are rewritten.

The live manifest also reports room15/group0 and group1 cannot skip with all
three selections, and room45/group0 crashes. Closed captures show two faults
following a room45 request, with the same unchanged runtime hash. These are
open investigation items; a direct-entry crash is not yet a confirmed campaign
crash. A second startup consumed the same still-fresh request, a separate
session-boundary concern to address. User requested side-by-side testing:
read-only live note monitoring, immutable running preview, fixes staged separately
and applied at an agreed stopping point. No scene requests are sent by monitoring.


## Restart replay regression (2026-10-20)

Owner reproduced restarting Play into the previous requested scene after temporary
request-file cleanup. Each native process reset its consumed nonce to zero, while
the file remained valid for sixty seconds. The next process could consume it during
startup, including attract scenes. Clearing the file only at launcher startup did
not cover Play restarts in an existing launcher and was not a complete fix.

Candidate: the diagnostic runtime records a new session start time before starting
its asynchronous request reader, and accepts only requests created after that
boundary. Existing nonce, expiry, original room/group validation and transition
guards remain. This needs no live deletion of the request file. Tests cover an
already-consumed request, an unconsumed request carried into a new session, the
exact boundary, a fresh request, duplicates, future times and expiry. Build/test
and owner restart verification are pending. This addresses stale replay; the
separate room45 direct-entry crash and room15 skip qualification remain open.

The scoped runtime and request tests build successfully; five component suites
pass (cutscene review, skip, audio, PC input, Modern controls). The closed owner
package has been updated with this candidate while preserving launcher, copied
profile, baseline save, selector and notes. Owner restart confirmation remains
pending. No gameplay was driven by this packaging check.


## Hidden selector handoff

The replacement handoff launched the WinForms selector through PowerShell with
Start-Process WindowStyle Hidden, which left its form hidden as well as the
console. Owner reported no selector. Enumerating windows found the existing
JFG - Cutscene Review form; ShowWindow/foreground restored it without touching
the running game or notes. Future handoff must hide the PowerShell console via
its own argument and explicitly verify the review form is visible.

### Credits state retained after leaving Disco Credits (2026-10-20)

Owner reports that credits remain drawn over another room after leaving the
Disco Credits test. The note is stored under361/Secret Pad but explicitly
belongs to exiting360/Disco Credits. Current immutable session-fix preview.
The selector explicitly requests mode23 for360 and otherwise preserves the
current native mode; carrying credits mode into later review rooms is a
hypothesis requiring native-source confirmation. Distinguish this diagnostic
scene-entry/exit limitation from ordinary campaign skip completion.
Open; no verified remedy yet. Preserve the owner note in its original location.


### 2026-10-20: Credits frontend leaks into subsequently selected room

The owner confirmed Disco Credits text remains over another scene loaded by
the selector. The selector selected native frontend mode23 for room360, then
copied frontGetMode unchanged for every other destination. Thus the next native
transition initialized Credits again. The candidate retains the actual mode
used before entering Credits and supplies it to mainChangeLevel when leaving.
Repeated Credits selections retain the original mode. Native transition
800468EC already calls frontFreeMode at80046E6C and frontSetMode at800474AC;
no credits draw suppression or raw overlay-state reset is introduced. An
unrecognized Credits entry without a retained prior mode fails closed.

Component tests cover entry, repeated Credits, leaving, independent native
mode changes and missing context. Build/owner verification pending. The owner
moved the note from361 to360 in their checklist; no checklist edits were made
by the implementation.


### 2026-10-20: preview blocked by stale package manifest

Installing the tested Quarry checklist runtime replaced the executable but
left the preview package manifest pointing at the previous executable hash
and size. The launcher correctly rejected Play with "Game files are missing or
changed." Corrected the private preview manifest and verified every packaged
file against its listed size and SHA-256. Also corrected inherited runtime
support identity and omitted stale symbol metadata. No game settings, copied
save, baseline or owner notes were changed. This was a local candidate packaging
regression; it is not a released game fault. Future candidate replacement must
refresh and validate its package metadata before launching.


### BigShip no longer crashes, but selector appears to do nothing (2026-10-21 UTC)

During the broader review on accepted Quarry-fog runtime
ca94e6b4c3437fa86086c7bc8e0009767144313c2eef0654ce020d8265ccd50d,
the owner reports BigShip no longer crashes the program but does nothing.

The current cutscene_review_entry_valid explicitly rejects room45 before actor
creation. This is the previously added diagnostic crash-prevention behavior:
standalone loading lacks the parent model required by native severed-limb
setup. It is not a completed safe-entry implementation, and does not establish
that the scene is unused or that normal campaign playback/skip is broken.
The owner observation is consistent with that rejection; no live request-log
correlation is claimed in this intake.

Status: crash prevention observed by owner; direct review entry unresolved.
The selector needs a clear unavailable/context-required reason instead of an
apparently successful Load scene action. Reproduction: select045/variant0 and
request loading from gameplay; the scene does not start. Character was not
specified. Preserve existing per-character notes and marks; do not mark this
entry passed. Safe native setup and/or proper campaign context remains a
follow-up. No runtime or selector mutation was made during the active review.


### 2026-10-21: Juno-only retest, frontend recovery and input handoff

The owner confirms checked Juno entries pass; historical failure notes do not reopen them. Only unchecked Juno entries are active. In the recorded207/0 run, the completion handler returned to native character selection (room127, mode5); the process continued rendering. The review request handler then refused room127, preventing selection of another test scene. The candidate remembers the loaded review game mode and permits recovery from character selection/title only with that known context. Script-driven Credits entry uses the same retained review mode; native transition cleanup remains responsible for freeing the previous frontend. Normal campaign completion is unchanged.

The335/0 trace remained qualified while physical/mapped A was present, but effective game buttons were neutral: UI capture/input blocking were set and Settings capture was clear. The recorded game window was not foreground. The private selector now requests foreground activation of its own launcher after writing Load scene and reports whether the handoff succeeded. It never weakens the runtime focus guard or targets another preview. Isolated fresh-save/reopen tests pass and the real owner progress file is unchanged. Live focus handoff and207 recovery remain pending owner review.

Candidate runtime SHA-256:
bad068704a5fa6f308dc8d42dbe1d77d56cb104a6f0cdc0f458db16a39a95bae.

Candidate selector SHA-256:
456456381144975d5ca017d45215878027b858902cf53a285262adcb1c54df11. Evidence: private cutscene-skip/juno-final-retest-20261021. Cross-reference [current retest status](cutscene-owner-retest-20261020.md). No release or owner acceptance is inferred from component checks.


The private selector now explains the existing BigShip standalone-entry rejection before sending a request, and shows per-variant context guidance for the other ten unchecked entries without established native exits. All rows, owner notes and checkboxes remain present and untouched. This fixes misleading Load scene feedback; it does not make those variants safe/skippable or mark them passed. Original308 entry at016009B8 and322 entry at02A022E8 both request group0, not the unresolved group1. The275 literal at09800608 is a sound call, not an entry path. No global unreachable/unused claim follows from these limited callers.

An isolated check exposed a selector row-event ordering defect: SelectionChanged can run before CurrentCell updates, so reading CurrentRow there could retain the previous notes target. Changed the handler to CurrentCellChanged, which saves the previous dirty note before displaying the new row. A new direct-row-navigation check proves the old note saves under its original key and the selected row displays its own notes. The initial failed fixture and source are preserved; the corrected smoke and fresh-process reopen pass. The fixture invokes the actual Load handler directly because PerformClick on an invisible test form does not dispatch a click. No owner progress mutation occurred. Initial selection now matches the unchecked376/0 candidate. Live user review remains pending.


2026-10-21 relaunch: the selector-presence query matched the orchestration PowerShell process itself because its -Command text contained the literal -File/Review-Cutscenes.ps1 search pattern. It therefore incorrectly concluded a selector existed. Excluding PowerShell -Command/-EncodedCommand hosts from the -File process search resolves the identification error; explicit window enumeration verifies the real review form is visible. No running game, owner note or checklist was modified. The failed presence/window checks are retained in the guarded queue and private candidate evidence.


##207 direct-entry prerequisite failure, October21

Owner confirmed207/0 skips then black-screens. Two fresh owner sessions show only character unlock1/Juno set and completion91 set, with unlock0/2 and completion90/92 clear. Native main thread is runnable inside08701754, looping through all three character actors without a selectable one. Original ROM tables08702A78/08702A84 pair unlocks1/0/2 with completions91/90/92; original207 asset211/group0 sets91 before conditional completion. This is an invalid direct-entry story context; merely allowing selector mode recovery cannot recover a thread stuck inside the native menu control.

Candidate prepares unlock prerequisites0/1/2 through the native flag setter only for diagnostic207/0 selection, in the already-isolated copied review game. It preserves all completion flags, uses the original conditional ending, and does not change production campaign entry or skip behavior. The selector profile may save this prepared state; the owner?s normal save remains untouched. No invented destination or menu-loop timeout. Pending native checks/build/live acceptance.

Private original-native regression confirms both selection directions loop with the captured207 state, and both reach an eligible character after native unlock preparation. All other game-flag bytes remain unchanged. The first fixture accidentally carried its bounded instruction counter from the expected looping case into preparation, causing an uncaught test-limit exception; resetting that isolated fixture counter per case passes eight checks. Failed fixture logs are retained. This is not a production-guard counter reset or a game crash. Native build and both cutscene suites pass; live review remains pending.


Owner acceptance2026-10-21 20:46UTC:376/0 and207/0 work on batch2 (96a6b257);405/2 already passed. Saved Juno boxes agree.335/0 and11 context-dependent entries remain unchecked. This is local owner verification, not a published resolution. See [current retest](cutscene-owner-retest-20261020.md).


Owner acceptance20:55UTC:335/0 passed and207/0 re-confirmed. All four targeted Juno retests now pass. Only11 unchecked context-dependent entries and the separate native type145 qualification audit remain; current preview and owner notes unchanged.


The remaining11 entries are classified as likely development/setup variants after the original631-exit scan and script audit. Normal exit data selects the already-passed378/2,409/1 and410/1. No actual source or owner notes were changed, and universal unreachability is not claimed. See [the detailed classification](cutscene-owner-retest-20261020.md).


Final Juno audit: the type 145 follow-up is complete. It is the native FireWork particle/light control, distinct from type 147 texture animation. Only the incorrect source explanation changed; runtime code and accepted preview remain identical. All four targeted owner retests pass. The remaining 11 rows retain their likely development/setup classification and original notes. See [the final audit](cutscene-owner-retest-20261020.md).
