# RENDER-002: Character/terrain seams and incorrect character lighting

Status: **high-refresh tearing corrected in a tested local candidate; Original-mode
joint and lighting reports open; owner confirmation pending** (2026-10-11).
Severity: major visual fidelity problem; gameplay impact unconfirmed.

## Report and reproduction

Juno shows visible gaps at his joints at every tested FPS with VSync enabled.
The owner confirms this also occurs in Original after stopping/restarting the
game. A supplied bridge-scene screenshot also shows pale gaps along terrain and
the bridge entrance. The owner separately reports incorrect lighting: Juno stays
too dark, as if he has remained in shadow. Do not assume these share one cause
or that higher presentation FPS alone causes them.

Affected local high-refresh preview runtime SHA-256:
`b34887ed7da310b11d52d33a1382f83b4c6e521985386d3061226fe6c43d408e`.
Most recent launcher implementation at report: 0f83a2a; runtime unchanged through
the intervening launcher/UI edits. Profile: isolated high-refresh preview.
Evidence: owner's bridge screenshot retained privately as
`high-refresh-20261011/seams-lighting-owner.png`, plus their Original/VSync/Juno
confirmation. Exact baseline comparison and controlled reproduction pending.

## Initial hypotheses and plan

- Compare the same scene/state in this runtime and the retained known-working
  build, beginning with Original mode. Preserve source saves and normal launcher.
- Examine shared geometry/matrix/lighting paths as well as presentation-only
  interpolation. Combined-matrix precision, vertex ownership, transform matching
  and lighting state are hypotheses, not established causes.
- Use a copied replay/profile and captures to distinguish baseline defects from
  branch regressions; verify a candidate at Original and Custom before delivery.
- Existing high-refresh checks establish bounded guest-state and presentation
  behavior, not joint continuity or lighting parity. See [RENDER-001](high-refresh-rendering.md).

## Guard and evidence

The owner explicitly approved reopening the same high-refresh investigation for
six additional guarded attempts and renewed its time window for three hours.
Original roots, twelve attempts/activities and 11470.6854326725 seconds retained;
new caps are eighteen attempts/activities. Guard stays enabled. Admission receipt:
`owner-seams-lighting-3hours.json`; no new investigation identity or counter reset.
The pinned upstream reference review/catalog were consulted; they do not establish
a rendering remedy. All experiments, builds and coding run under the supervisor.

## Validation and resolution

The reproduced high-refresh terrain tearing is corrected and tested in the local
candidate described below. The broader Original-mode joint and lighting reports
remain open. No release or complete visual-fidelity resolution is claimed.

## Controlled baseline comparison

At VI 4004 in the retained tutorial-room replay, Original/VSync-on runtime b34887ed matches reference 26852729 byte-for-byte in the final image, guest RDRAM, renderer snapshot, recorded input and save. Source save unchanged. This excludes a branch regression at that checkpoint only; it does not establish bridge-scene parity. Evidence: `seams-original-comparison/result.json`. A copied preview-save fixture is being checked separately.

Owner requested all tests start muted. Native fixtures use independent `volume=0, muted=1`; the Ares64 reference disables sound in its isolated configuration and runs on an inactive desktop. Personal audio settings are preserved.

A private screenshot-sequence diagnostic build initially failed under `/WX` because MSVC rejects `getenv`; changed its environment read to `_dupenv_s`. No candidate graphics correction or delivery was made by that failed build.

A private geometry diagnostic hit MSVC narrowing warnings from hlslpp vector indices. Corrected bounded component indices to int. The failed build and source are retained privately; no product correction claimed. Original-mode walk captures now reach the bridge without the large terrain cracks shown in the owner screenshot. High-refresh comparison follows; original-mode joint concerns remain open.

## Reproduced high-refresh tearing and first candidate

The muted Original and Custom 360/VSync-on walks use identical copied save and
input. Large cyan terrain/bridge cracks appear only in Custom in this fixture,
matching the supplied screenshot. Original remains intact here. This does not
invalidate the owner's separate Original-mode joint report.

Cause found in the prototype: exact-geometry matching decides motion per vertex
batch, although many batches share the same current transform. A culled/changed
batch can stay at the current endpoint while adjacent matched batches move.
The first candidate makes all batches sharing an exact current matrix use one
unambiguous history transform, or all stay at the endpoint on conflict/unsafe
geometry. Regression fails on the old implementation and passes after the change.
Runtime replay/visual verification pending; no completed fix claimed.

Private evidence: `seams-walk`, `seams-geometry`, `seams-custom` and
`seams-coherence/regression.json`. Diagnostic TSV analysis initially rejected a
raw uint8 light-count field; the parser correction retains the failed receipt.

## Verified candidate and remaining reports

The shared-transform correction removes the reproduced cyan cracks at bridge
approach/crossing captures 2880 and 2940. Five focused renderer tests pass. The
clean executable, with all temporary capture/geometry instrumentation removed,
completes four muted 4,500-VI replays: Original/VSync, Custom 60/VSync,
Custom 360/no VSync and Unlimited/no VSync. All preserve the same guest RDRAM,
renderer snapshot and save. Original's final image is byte-identical to the
pre-correction baseline. Custom and Unlimited still generate moving intermediate
frames. Detailed receipts and short-walk pacing are in
[the aggregate evidence](../../../evidence/high-refresh-transform-coherence.json).

Lighting is not declared fixed. An isolated Ares64 run using a copy of the same
FlashRAM and a scripted walk also darkens Juno on this bridge, then shows him
lit during the far-bank conversation. This is an appearance reference, not
frame-aligned pixel parity. The captured native geometry uses prelit colors
(zero RSP light counts); changing RT64 normal-lighting parameters is unsupported
by this evidence. The owner was asked whether the darkness persists after
leaving the bridge or looks wrong on the bridge itself. Further location/pose
evidence is needed to resolve the remaining lighting and Original-joint reports.

Compatibility lesson: a vertex-batch identity is not an independent animation
identity. Culling and topology changes must not split a single matrix's motion.
Conflicting old transforms and unsafe shared geometry hold the whole group at
the endpoint. This may reduce smoothing in ambiguous cases; it does not alter
guest timing, authored transforms, lighting values or feedback pixels. Changed
vertex positions, other characters and broad scene transitions remain outside
this bounded visual qualification.

Private receipts/captures: `seams-clean-qualification/result.json`,
`seams-coherent-candidate`, `seams-reviewed-2880.png`,
`seams-reviewed-2940.png`, and `seams-emulator`. Original failed diagnostic build
and parser receipts remain preserved. Reference source inspected:
[GLideN64 F3DDKR](https://github.com/gonetz/GLideN64/blob/master/src/uCodes/F3DDKR.cpp)
and [vertex pipeline](https://github.com/gonetz/GLideN64/blob/master/src/gSP.cpp),
snapshot hashes d80701e1c3a046b45540fc52757b13fb84646357126a2ec8dc74f38c6bb65f74
and 30327540e7e975e4c7eb856a1b8f29c5a5c75a0ff023129d3a28f64ed75af538.
No upstream implementation was copied or dependency upgraded.
