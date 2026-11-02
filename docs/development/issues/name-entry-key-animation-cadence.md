# Name-entry keyboard key animation cadence

- ID: MENU-KEY-CADENCE-20261102.
- Status: PAL recording/replay complete; incomplete keyboard-scene interpolation measured; per-key cause and remedy open.
- Severity: visible presentation limitation on the in-game New Game name-entry keyboard.
- Affected: local v30 launcher/v28 enhanced PAL runtime (`5bac0c8`), owner testing at requested 120 FPS with VSync. US/JP are suspected by the owner but not independently reproduced.

## Report and reproduction

The owner reports that the animated buttons/letters while entering a new save
name do not appear to receive the higher presentation frame rate. This is the
in-game three-dimensional keyboard, not launcher controls or save-slot panels.
Move between keys and select letters to observe their animation.

The owner supplied a still screenshot identifying this keyboard, with Z
selected. A still cannot establish animation cadence. The owner requested a
logged PAL launcher session, explicitly not a video, to record input and
renderer behavior. Preserve that distinction.

## Investigation and evidence

The current PAL profile requests custom 120 FPS and VSync. That configuration
is not measured key-animation frequency. Shared interpolation can present at
a higher rate while individual frontend transformations remain at native
updates; this is a hypothesis, not an established cause.

A fresh private PAL diagnostic profile copies controller/video preferences and
imports the existing verified PAL ROM. It does not overwrite the owner's
campaign profile. Standard launcher diagnostics record input, gameplay, polls,
interpolation, support metadata and final RDRAM; no video capture is requested.
Compiler and automated gameplay work stay stopped during the owner's capture.
Private evidence root: `regional-automation-20261101-owner4h/manual-pal-name-entry`.

## Remaining work and lesson

Identify the exact animated key transformations and their presentation/update
cadence from the recorded route before choosing a correction. Retain original
menu timing and input semantics. Validate PAL first, then US/JP separately.
A global FPS target and successful menu navigation do not establish that every
frontend element interpolates. No fix, new native build or release is claimed.

## First owner PAL capture

The owner completed a logged route through the correctly launched PAL session.
The launcher/game closed cleanly. Private capture:
`manual-pal-name-entry-relaunch/captures/20261102-022700-213299dca88e4a5289633b5fc1f616a2`.
Input, gameplay, polls, interpolation, session metadata and final RDRAM are
retained with hashes in `pal-name-entry-capture-analysis.json`. Trace integrity
and global presentation are analyzed separately from the selected key's
animation; this is not yet a per-key diagnosis or a remedy.

The first launch attempt supplied managed-worker arguments to the native
launcher and produced no diagnostic capture. The public `--play --profile
--diagnostics` path corrected that orchestration mistake. Both attempts remain
preserved. No original campaign profile was overwritten.

## Recorded screen coverage

The same owner input replay reaches the name-entry keyboard (frontend mode 24),
confirmed by its final image. In the owner's completed trace, VI 2000-2220
contains 111 source frames with 1,968 vertices: 798 are matched for interpolation
and 1,170 are held at native updates. Median output interval is 8.334 ms
(approximately 120 FPS); native source rate is 25 Hz. The still identifies the
screen only. These scene totals do not yet identify individual key ownership
or establish why a particular vertex is held.

Private receipts: `pal-keyboard-screen-qualification.json`,
`pal-name-entry-capture-analysis.json`, and `owner-pal-keyboard-replay`.
The replay is muted, uses a fresh isolated profile and leaves the original
recording and campaign profile unchanged. Next: attribute held geometry to
the animated keys and test stable history across key selection/press/release.
Do not interpolate unrelated menu elements merely to increase coverage.
