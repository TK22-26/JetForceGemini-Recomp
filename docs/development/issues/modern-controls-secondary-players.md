# Modern controls unavailable for Players 2-4

- Status: owner-reported and reproduced in controller setup; investigation open.
- Severity: blocks use of advertised Modern configuration on secondary players.
- Affected: corrected Give Floyd preview, based on accepted develop controls; Windows.
- Related: [Floyd Player 2 input failure](github-floyd-cannot-fire.md), GitHub #37.

Owner reports only P1 allows Modern controls and explicitly requests repair for
P2-P4 alongside Floyd ignoring all P2 input. Reproduce by selecting P2, P3 or P4
in controller setup and trying to choose/configure Modern controls. Exact UI and
runtime gates are being checked; the source/profile snapshot is preserved in
D:/JFG-private/floyd-p2-modern-20261021. Keyboard/mouse and controller paths need
separate validation, independent saved bindings, reload, and original-mode parity.

Do not treat removing a UI restriction as complete: per-port input sampling,
Modern action state, keyboard/mouse ownership and native secondary-player/Floyd
contexts must be qualified. No cause/remedy or gameplay success is yet established.

## Confirmed UI restriction and candidate

Modern mode, style-button enabled state and the click handler each explicitly
required player index0. Per-player filenames and configuration arrays already
exist. Candidate removes those three restrictions while retaining separate
profiles and Original bindings. Added actual UI style/reload/isolation checks
for P2-P4. Runtime changes and multiplayer/Floyd validation remain pending;
this UI change alone is not a completed fix.

## Runtime candidate and validation progress

Actual UI suite passed 896 checks, including secondary Modern selection,
save/reload, separate bindings and preserved Original mappings. Runtime candidate
removes P1/single-player style gates, resolves the native player list by input
port, and gives each player independent view/action/roll/crawl/scope state.
It preserves the guest controller remap and multiplayer inventory selection.
Navigation-mod single-player restrictions are unchanged. Native builds and
gameplay qualification remain in progress; this is not released or owner accepted.

## Owner preview opened

Modern Players and Floyd Preview launched at the owner's request. Runtime and
four focused component suites pass; real UI passed 896 checks. Original native
sidekick/input routines passed 487 checks across 72 routing cases, including
Start join/leave, controller remaps and mission input locks. The owner capture
confirms the old Modern mission predicate drops Fire. Native routing checks do
not establish live reticle feel, multiplayer camera behavior or mission completion.
Those remain pending owner testing. Source profile/save preserved. Evidence:
D:/JFG-private/floyd-p2-modern-20261021/delivery.json and launch.json.


## Final owner disposition for v1.4.0 (2026-10-21)

The owner states that #37 and the associated Floyd work are fully approved
locally and requests reporter verification after delivery. This supersedes the
earlier local acceptance gates above without inventing additional measured routes
or hardware coverage. The combined v1.4.0 package still needs the requested
SS Anubis final pass. No publication or public reply is implied.
