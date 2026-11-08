# PROTON-MOUSE-20261107: Hidden pointer escapes windowed gameplay

- Original severity: high; mouse controls were unusable during the reported failure.
- Status: owner manually verified fully working on Bazzite on 2026-11-08; accepted locally, unreleased; precise cause unconfirmed.
- Reported: 2026-11-07 UTC; owner acceptance recorded 2026-11-08 UTC.
- Affected session: USA, Modern keyboard/mouse, windowed, Bazzite x64 PC,
  RTX 4070, Wayland, GE-Proton11-11. The returned executable matches the
  preceding all-region native-ROM test bundle.
- Evidence: owner recomp test; no original-N64 comparison applies.

## Symptoms and reproduction

During mouse gameplay, the pointer disappears but continues across the desktop.
Clicks can activate background windows; rapid movement briefly reveals the
cursor. Relative gameplay motion should remain confined while active and release
deliberately for menus, settings, focus loss and exit.

The owner separately accepts the opening-skip improvement. The earlier 18:47 UTC
USA log measures 1.828 seconds from confirmation to character selection across all nine
scenes. That acceptance does not cover this mouse defect or other regions.

## Evidence and cause boundary

The direct 18:47 UTC report matches executable SHA-256
`fd8cfcb976a468d9184cfbea9338c138ca9f9632036611c99208950ba3abcda3`.
Its 60-sample mouse history records ten additional focus losses, 13,470 accepted
nonzero raw packets and 854 nonzero camera outputs. Raw motion reaches gameplay;
this is different from the zero-delivery symptom in [GH-032](github-mouse-look-and-inversion.md).
The accompanying 18:38 archive predates this run; it is not the current evidence.
Original reports, hashes and scripts are retained privately as
`proton-mouse-capture-20261107`.

The old [controller poll](../../../src/boot/native/controller_input.cpp) performed
whole-client `ClipCursor` and cursor hiding on the gameplay worker, ignored API
results and reported the requested capture as active. The HWND belongs to a
separate thread, and its launcher parent belongs to another process. This is a
demonstrated unchecked capture contract; the exact reason confinement escaped
on the owner's compositor is **not established**.

Both the original rendered game and a two-process window fixture confined the
pointer successfully under isolated X11/GE-Proton11-11. Moving the call between
worker, child-window and parent-window threads did not reproduce the failure.
Do not describe that experiment as proof of a Wine thread-ownership cause.
Pinned [Wine input source](https://github.com/ValveSoftware/wine/blob/c53678ab22a85f0fad3588dd34f0452a463bd015/dlls/win32u/input.c)
and its X11/Wayland drivers were reviewed at
`c53678ab22a85f0fad3588dd34f0452a463bd015`; server/API acceptance alone is not
independent evidence that the desktop compositor confined the physical pointer.

## Candidate submitted before the failed owner retest

The following describes the previously delivered candidate. The November 7
20:07 owner retest below rejects it as a fix for Bazzite/Wayland.

[Win32RelativeMouse](../../../include/jfg/runtime/win32_relative_mouse.hpp), owned
by the [render-window thread](../../../src/boot/native/live_window.cpp), now:

- Separates gameplay's capture request from checked activation.
- Keeps the desktop pointer in a one-pixel region at the client center while
  consuming the existing raw relative-motion stream.
- Checks geometry, clip API result, returned clip rectangle and cursor position
  before acknowledging capture; a failed check leaves it inactive.
- Balances cursor hiding and restores it on release. Focus, settings, move/resize,
  explicit release and shutdown retain their release paths. It avoids clearing
  a different application's newly acquired clip.
- Emits bounded numeric `mouse_capture` diagnostics, without pointer coordinates,
  handles, window titles or key history. The support ZIP retains the new record.

Camera calculations, controller mappings and mouse-button capture routing remain
the existing implementations. The code is shared by USA, PAL and JP.

## Attempts, verification and limits

The enabled production guard admitted one owner-approved continuation of at most
two hours using the existing investigation, counters and limits.

Early fixture attempts failed on an ANSI/Unicode cursor-resource mismatch,
console-window activation, a timer-based fixture phase transition and private
display cleanup. The corrected GUI fixture uses independently timed phases;
these earlier failures were test-harness failures, not evidence of a game defect.
No result was credited merely because its wrapper exited successfully.

[Windows capture tests](../../../tests/runtime/win32_relative_mouse_tests.cpp)
exercise denied clipping, center confinement, resize, menu release, focus,
wrong-thread rejection and reacquisition. They run explicitly because they need
an interactive window. The same test passed on Windows and GE-Proton/X11.
The actual candidate game also received relative motion under Proton while the
X server independently reported the pointer at the center; camera counters
continued increasing. The original build's pointer was confined to the client
edge in the corresponding baseline.

Native diagnostic serialization and maximum-size history tests pass: 986 bytes
per maximal sample and 59,160 bytes for sixty samples, below the 64 KiB cap.
Launcher tests accept the eight unsigned fields and reject extra, negative,
oversized and nonnumeric fields. All three rebuilt runtimes verify their source
and embedded identities; muted private save-load replays reach gameplay and close
normally. These replays cover regional loading, not physical controller feel.

The compact [validation record](../../../evidence/proton-mouse-confinement-20261107.json)
pins the tested binaries and observations. Private saves, ROMs, raw captures and
Wine source remain outside the public repository.

**Original acceptance requirements:** owner windowed Bazzite/Wayland testing,
including rapid sweeps,
clicks, simultaneous aim/fire, pause/menu release and Alt-Tab recovery. Local X11
success cannot establish the behavior of that desktop or prove the original
trigger. The later owner retest failed, so the defect remains open. There is no commit,
GitHub closure or released-resolution claim.

## Transferable lessons

Requested capture, cursor visibility, raw input delivery and physical confinement
are distinct observations. Check activation, retain deliberate release paths,
and independently inspect pointer behavior in the affected display environment.
Keep source-build and portable-package inventories distinct: the portable bundle
also needs its existing C++ runtime DLLs and an updated outer manifest hash.

Related: [PC controls](../../features/pc-controls.md),
[support diagnostics](../support-diagnostics.md),
[cutscene skip](cutscene-skip-completion-time.md).

The actual rebuilt launcher and USA runtime also pass the isolated Proton/X11 run with ordinary key/mouse input: confinement before a top-menu open, physical release while the menu is active, center confinement and camera motion after dismissal, and normal exit. Simultaneous aim/fire buttons were exercised; their gameplay feel and the owner Wayland/Steam environment still require manual testing. No replay, detailed trace, screenshot readback or owner save was used in that run.

Initial USB delivery, before the failed retest: the existing issue40 test bundle contained the candidate for all three regions, the matching launcher/helper, complete portable DLL inventories and outer index, updated handoff and collector. 125 package checksums and the managed resolver verify. Previous files are backed up; owner saves/settings/ROMs and returned capture folders were not modified. Owner Wayland acceptance was pending at delivery and was subsequently rejected.

## Owner retest: candidate still fails

On November 7 the owner reports the delivered candidate still only hides the
pointer. Clicking outside the game steals focus, and continued mouse movement
stops when the desktop pointer reaches a monitor edge. These are failures of
confinement and unbounded relative input, not manual acceptance. A new returned
folder contains 20:05 and 20:07 UTC sessions. The earlier isolated X11 passes do
not establish Bazzite/Wayland correctness. Original returned evidence is retained
privately as `proton-mouse-retest-20261107`. The owner approved two further hours;
one attempt/activity was added to the same guarded investigation with all prior
counters, spent time and roots preserved. No further fix is claimed.


### Renewed compositor investigation

The new 20:07 owner run used `winex11.drv` under GE-Proton11-11, confirmed
by the preserved full Proton log. All six requested/active/geometry/API/rectangle/
pointer checks can report one despite the reported desktop escape. Wine's server
clamps its reported cursor position to the requested rectangle, so this is not
independent compositor proof. The prefix input policy and actual driver grab are
not recorded by the original default Proton trace.

A private nested Weston/Xwayland fixture acknowledged actual pointer-lock
requests; the small two-process window and real launcher both reached that path.
A nested KWin 5.27 fixture did too. These are older software-rendered compositor
fixtures, not the owner's Bazzite/NVIDIA/Steam session. The first rapid alternating
input batches cancelled their camera deltas; the first KWin outer-display input
run also lacked meaningful camera movement. Neither is counted as a passing
unbounded-camera regression. A direct compositor-seat input fixture subsequently eliminated that test
limitation, as described below. Initial fixture failures were missing
outer window-manager/fullscreen handling, WSL X socket namespace collision, and
KWin's required permission declaration for the isolated input test client. No
production desktop permissions or owner profiles were changed.

The qualified KWin fixture must enter and click the fully mapped game surface
before evaluating capture. Earlier setup-only clicks preceded surface readiness,
and large jumps subsequently skipped the window; those trials were invalid
motion checks. With entry corrected, the current binary delivers unbounded
2,500-pixel relative movements to the camera and resumes after menu close plus
physical re-entry. No owner failure has been reproduced by that passing check.

A separate native-Wayland-window focus test exposes another diagnostic limitation:
Wine/Xwayland still reports the game captured while a native Wayland terminal
is active. Camera delivery stops in that interval and returns after focus/re-entry.
This does not establish the cause of the owner's repeated mouse escape. The test
is retained as a failed focus-state assertion, not counted as a capture pass.
The exact GE build's optional native Wine Wayland driver loaded, but the
hosted-game test did not reach active capture before its timeout. This is an
unqualified comparison, not a verified workaround or a changed default.

### Focused owner capture prepared before acceptance

The default 598 MB Proton log lacks the cursor and focus driver channels needed
to distinguish a skipped/rejected grab from a compositor failure. The pinned
Wine implementation forwards clip processing to the foreground thread; moving
our call again would not, by itself, establish a fix. Its `GrabPointer` policy
can suppress a driver grab, but the owner's prefix policy is not yet available.
No policy change or further runtime correction is justified by the supplied log.

The [filtered capture utility](../../../scripts/diagnostics/proton_mouse_capture.py)
and [runnable shell entry](../../../scripts/diagnostics/capture-proton-mouse.sh)
wrap the existing Steam launch command. They retain only allowed pointer/focus
functions, read the applicable input-policy keys, sample X11 pointer/focus without
injecting input, and include the new session's bounded game logs. Other Wine
messages are discarded in memory. Pointer coordinates and numeric window IDs
remain private diagnostic data; no ROM, save or window/key text is collected.
Five minutes and 16 MiB bound the driver trace; gameplay continues normally after
the capture limit. Normal close seals an archive and verifies its USB copy.
The installer changes only its own tool files and prints a Steam launch option;
it does not edit the prefix, Steam settings, game, saves or manual audio settings.

The actual launcher with this wrapper passes the qualified KWin seat-input and
menu re-entry check. It records both `NtUserClipCursor` and driver grab functions,
X server pointer samples, and a byte-verified copied archive. Nine focused tests
pass on Linux; Windows passes eight with the symlink-privilege test skipped.
These checks qualify collection, not resolution of the owner's mouse defect.

The E: handoff now identifies the prior candidate as failed and provides a short
owner capture procedure. Runtime binaries remain the previously tested versions.
Still needed: a fresh-launch windowed capture reproducing the monitor-edge stop
and outside-click focus loss, followed by a menu/re-entry check if practical.
At that point the cause and owner acceptance remained open. Preserve the earlier passing fixture
records alongside the failed owner retest; neither replaces the other.

## Owner acceptance, 2026-11-08

The owner explicitly reports: "I manually tested on bazzite and its now fully
working." This accepts the current local mouse behavior on the reported Bazzite
machine and supersedes the preceding failed retest and pending capture request.
The earlier failure evidence remains retained; the new statement is manual
acceptance, not a newly analyzed driver trace.

The delivered window-thread capture implementation and focused diagnostic tools
remain the current code. No runtime change was made during the final diagnostic
continuation. The exact environmental trigger and reason for the change from
failure to success have not been established, so focus ownership and a skipped
Wine grab remain hypotheses rather than a proven root cause. Further mouse
investigation is unnecessary unless the problem recurs.

The owner approved publication to `develop`. This is local-build acceptance,
not a tagged release or independent Steam Deck/other-region verification. The
capture tool remains available for a recurrence; no additional capture is
required to record this acceptance. Compatibility lesson: preserve API results,
physical behavior and owner retest chronology separately, including an accepted
outcome whose exact cause remains unknown.
