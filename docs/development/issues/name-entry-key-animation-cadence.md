# Name-entry keyboard key animation cadence

- ID: MENU-KEY-CADENCE-20261102.
- Status: US/PAL/JP native replays verify complete key interpolation; owner appearance review pending.
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

## Native key ownership investigation, 2026-11-02

The owner recording replay identifies 39 repeated key meshes (24 and 6 vertices
per key) rejected as ambiguous shape matches. A first candidate registered the
main keyboard model (frontend object 51) outside the world object list. Its
component tests passed, but a subsequent comparison against the actual held
matrix addresses disproved the proposed ownership: none belonged to that
model's two matrix palettes. Its runtime build was stopped before delivery.
Evidence is preserved in `keyboard-final-palette-comparison.json`.

The keys are separate repeated draws of frontend object 52. The replacement
candidate qualifies the exact original keyboard loop call, shared object global
and frontend drawing function for US/PAL/JP. It scopes the native key index
(0–40) through matrix emission, captures unchanged native matrix operands, and
adds the index to actor/model/lifetime identity. Original animation/input timing
and exact geometry validation remain unchanged. Frontend mode is an eight-bit
value. Exiting the screen or retiring/replacing the object invalidates history.

Regressions cover identical geometry with different indices, reversed draw
order, transient matrix address changes, matrix overwrite, actor retirement,
stale samples and nested or unqualified calls. Rebuilt PAL replay and US/JP
runtime checks remain pending; component tests alone do not establish a fix.
Private evidence root: `regional-presentation-20261102-owner2h`.

The actual captured KeyboardKeys allocation also has 51 model variants, beyond
the existing gameplay-only limit of 16. Its screen-qualified registration now
accepts the native signed-byte count (up to 127), while retaining complete array,
model and geometry bounds checks. Ordinary world actors retain their limit.
The first assertion assuming one model failed informatively; the recorded
allocation identifies the alphabet and key/keyboard variants. This check caught
an additional rejection before the rebuilt candidate was delivered.

A compiled consumer of the retained PAL memory now registers all 51 actual key
model ranges and gives each a valid rigid history identity. This supplies a
matrix observation to isolate the identity consumer; it does not execute the
new guest hook. The focused semantic suite and 30 binding/identity contracts
pass after the model-count correction. Live hook/replay checks remain pending.
Evidence: `recorded-keyboard-consumer` and `keyboard-tests-v4.result.json`.

## PAL native replay qualification

The rebuilt PAL runtime replays the owner's captured input through normal Play
and exits cleanly. In the measured keyboard interval, all 1,968 vertices match
for interpolation, compared with 798 before the correction. None of the 1,170
previously held key vertices remain rejected. All 41 native key indices are
observed on every one of the 238 measured source frames (9,758 matrix events).
The final image confirms the intended name-entry screen. The run is muted and
uses an isolated profile. Visual animation acceptance still belongs to the
owner; a screenshot alone is not motion evidence.

Evidence: `candidate-v3-keyboard-pal`, `keyboard-live-qualification-v2.json`.
All regions share the same source fix; US/JP runtime replays remain separate
checks. No release or native-console timing-equivalence claim is made.

Implementation: [scoped native key index](../../../include/jfg/renderer/keyboard_presentation.hpp),
[shared presentation identities](../../../include/jfg/renderer/presentation_identity.hpp),
and [native draw observation](../../../src/boot/native/guest_execution.cpp).
Regression coverage is in [semantic presentation tests](../../../tests/renderer/semantic_presentation_tests.cpp).
Lesson: qualify the actual repeated draw and allocation shape; a nearby main
model and a passing synthetic ownership test cannot establish the live path.

## Three-region test handoff

All three enhanced native runtimes compile, link and pass bundle identity checks.
The same owner input reaches name entry and exits normally in US/PAL/JP.

| Region | Measured source frames | Median matched / total vertices | Key indices per draw |
| --- | ---: | ---: | ---: |
| US | 299 | 1968 / 1968 | 41 |
| PAL | 238 | 1968 / 1968 | 41 |
| JPN | 300 | 1968 / 1968 | 41 |

None of the previously held key batches remain. Original native animation and
input timing are retained. Local `owner-review-v31` contains one unchanged v30
launcher with the newly built regional runtimes and separate copies of owner
settings/saves. Actual managed import/setup selects each matching new runtime.
The original v30 profiles remain unchanged. This is a local test handoff,
not a release or owner visual acceptance.

The final packaged launcher also starts the correct new native executable and
closes normally for each revision in isolated, explicitly muted profiles.
The handoff saves remain unchanged. Receipt: `launcher-smoke-v31.result.json`.

Local implementation commit: `0e97d2e347b1bd33c714de9de3ef678aa0e48cec` on `develop`.
The local test package is not a published release.
