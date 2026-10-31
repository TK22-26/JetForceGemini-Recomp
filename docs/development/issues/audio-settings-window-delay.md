# UI-AUDIO-SETTINGS: Audio Settings remains a modal and opens slowly

- Status: resolved locally, owner-verified on 2026-10-31; unreleased. The replacement window opens immediately. The original delay's cause remains unknown.
- Severity: moderate settings usability regression/unfinished migration.
- Reported: 2026-10-31 during manual review of the issue 45 candidate.
- Affected review: `D:/JFG-previews/issue45-flight-music-review-20261031-v2`.
- Reproduction: open Audio > Audio settings while the game is running.
- Symptoms: settings appear as a modal instead of a separate settings window;
  the owner reports approximately 20 seconds before they appear.

The owner expects a window consistent with Video Settings and Controller Mapping.
The live game and copied profile must be preserved while fixing this UI problem.
This is separate from [flight-transition music](flight-transition-missing-music.md).

## Initial evidence and hypotheses

The RmlUi Audio action calls `modal("audio")` directly; Video and Settings instead
request a separate native tool window. The native launcher also omits Audio from
its RmlUi tool routing list, so its fallback invokes the legacy WinForms helper.
The exact source of the owner's 20-second delay has not yet been timed. Do not
attribute the delay to helper startup before reproducing the actual path.

Candidate plan: give Audio a dedicated native settings window and keep volume,
mute, persistence, keyboard navigation and close behavior. Verify launch latency
and ensure no ROM scans, controller scans or helper startup are required to open
these two audio controls. Preserve existing user changes and issue 45 runtime.

## Execution and acceptance

The production guard is enabled and this work shares the existing
`high-refresh-rendering-20261011` investigation, with no reset, re-root or added
allowance. Coding/builds/tests ran under its supervised worker. Owner acceptance
was initially pending and is recorded below; no release is claimed.

## Candidate and early checks

A dedicated RmlUi Audio Settings window now reads and writes only the profile
audio preferences. Menu, native command and live-tool routing include Audio.
Initial inactive-desktop tests passed 64 Audio, 104 menu and 247 Video checks;
three real executable launches became visible and responsive in 287-352 ms.
The 20-second owner delay has not been reproduced or attributed to one cause.
Visual review found missing plus/minus glyphs, corrected with the same span
markup used by other flex buttons. Host review also found and corrected the
previously absent Audio action-to-command mapping. These changes require the
final build/route check; initial numbers do not qualify a later binary.

An initial configure failed because the new test block accidentally included a
duplicate existing Video test target. Only that duplicate was removed; the
original target and its successful tests are preserved.

## Cause, final remedy and verification

The primary menu action was never migrated from `Ui::modal("audio")` to the
separate settings-window route. Completing that migration required all three
links: the RmlUi action, the launcher action-to-command mapping, and the native
live-tool entry. Audio now has its own small document/model, normal caption and
resizable frame. It skips the main-page/controller/update initialization and
has no setup-helper dependency. The WinForms fallback remains for non-RmlUi
builds; the shipped native path uses the new window.

The cause of the original 20-second stall remains unknown. The replacement route is timed:
three final real executable launches appeared and responded in **268-316 ms**;
an actual launcher menu (Alt+A, Down, Enter) opened the separate owned window
in **557 ms**, including injected key pacing. The integration host differs only
in its test singleton, allowing it to coexist with the owner's running game.
All measurements ran on inactive desktops without moving the physical pointer
or taking over the owner's game.

Final Audio UI checks pass **64** assertions for loading without writes,
volume/mute updates accepted by the runtime parser, mute preserving volume,
keyboard navigation and boundaries, pointer hit targets, Done/Escape, reopening,
malformed-file preservation and visible write errors. Existing menu and Video
suites pass **104** and **247** checks. Visual inspection verified the slider,
plus/minus labels, mute switch and footer. The owner subsequently confirmed that
the replacement opens immediately and the bug is fixed, as recorded below.

[Machine-readable receipt](../../../evidence/audio-settings-window.json).
Private scripts, baseline snapshots, failing configuration receipt, screenshots,
source-only diffs and timing evidence are in
`D:/JFG-private/audio-settings-window-20261031`.

## Local delivery and compatibility

Review package: `D:/JFG-previews/audio-settings-window-review-20261031`.
`Audio Settings.lnk` opens the new settings window for the current issue 45
review profile. `Play review.lnk` uses the updated launcher and that same profile
after the current game is closed. Packaging did not overwrite the running
launcher, change settings, or copy an active save. The original v2 preview and
its recorded identities are preserved. The flight-music game executable is
byte-for-byte unchanged; only the launcher/UI is rebuilt. Its retained setup
helper is unchanged.

The current running launcher cannot acquire new menu code without restarting.
A separately opened new Audio window can control its shared review profile now;
future launches through the new shortcut use the corrected menu route.

Transferable lesson: a standalone UI test can pass while its host action mapping
is missing. Include the complete menu-to-host-to-tool transition and measure
first visible, responsive output. Keep settings-window startup independent of
ROM verification, helper startup, controller discovery and animated home content.
A measured fast candidate does not establish which component caused an earlier
unrecorded stall.

## Owner acceptance: resolved locally (2026-10-31)

The owner confirms: "the replacement path does open immediatly so it is fixed - cause unknown".

This accepts the replacement Audio Settings window and resolves the observed
opening delay in the reviewed build. The original delay's root cause remains
unknown; successful replacement is not proof of a particular bottleneck. The
fix is owner-verified locally and unreleased. This acceptance applies to Audio
Settings only; it does not verify or close the separate flight-music report.
