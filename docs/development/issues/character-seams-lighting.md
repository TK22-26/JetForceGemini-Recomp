# RENDER-002: Character/terrain seams and incorrect character lighting

Status: **high-refresh tearing corrected in a tested local candidate; Original-mode
joint and lighting reports open; owner confirmation pending** (2026-10-11).
Severity: major visual fidelity problem; gameplay impact unconfirmed.

## Report and reproduction

Juno shows visible gaps at his joints at every tested FPS with VSync enabled.
The owner confirms this also occurs in Original after stopping/restarting the
game. A supplied bridge-scene screenshot also shows pale gaps along terrain and
the bridge entrance. The owner separately reports delayed, inconsistent lighting recovery when
walking back toward the starting area: Juno stays too dark after the bridge,
then eventually brightens. The detailed clarification and comparisons are below. Do not assume these share one cause
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
by this evidence. The owner subsequently clarified the return direction and eventual recovery;
see the controlled follow-up below. The remaining intermittent lighting and
Original-joint reports are not resolved by this first comparison.

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

## Owner clarification and local delivery

The owner clarified that Juno darkens when he steps onto the bridge and **stays
dark after he walks off it**. The shadow on the bridge alone is not the reported
failure. Extend the controlled route past the Magnus conversation and compare
the transition in the reference and native runtime before changing lighting.

The shared-transform correction is committed as `dbc4c91f487a5a1b064ed55a49d60fa40dc536e7` and packaged at
`C:/JFG-builds/high-refresh-coherent-preview-20261011`. The existing desktop
preview shortcut now resolves to that package with the same profile arguments.
All 14 package entries pass size/hash validation; the managed frontend resolves
the new runtime through an isolated muted profile. Launcher binary unchanged.
Old package/shortcut retained for rollback. Owner visual confirmation remains
pending; lighting and Original-mode joint reports are still open.

The owner further narrows the lighting report to walking **back toward the
starting area**. Juno eventually brightens again, but the recovery appears late
and inconsistent. Treat this as a delayed transition, not a permanently stuck
light value. The first extended native route shows lighting restored after the
Magnus dialogue, but is the opposite crossing direction; a dedicated on-bridge,
turn-back, off-bridge-and-idle replay is now queued in Original, Custom/VSync,
and the muted Ares64 reference. No lighting remedy is claimed from the outward
route or from the shared-transform seam correction.

## Completed lighting follow-up and handoff

The clarified return route walks forward during VI 4000-4180, reverses during
4240-4500, then stands still through VI 6000. Original/VSync and Custom 360/VSync
both complete muted and finish with identical guest RDRAM, renderer snapshot
and save. Native captures 3090/3120 show Juno dark on the bridge/at its lip;
3150/3180 show brighter lighting on the starting-side approach. Brighter lighting
persists through the following idle captures. The separate muted Ares64 run
shows the same spatial appearance pattern at frames 4320/4350 and 4380/4410.
These sequences are not frame-aligned pixel or precise timing parity: camera
positions, animation phase, resolution/coverage and interpolated presentation
differ. Do not claim the owner's inconsistent extra delay has been disproved.

The longer outward route also completes 10,000 VI in both native modes with
identical final guest/renderer/save data. Juno brightens during and after the
Magnus conversation; the emulator shows this too. That outward route is useful
supporting evidence, but does not substitute for the clarified return direction.
Close-up captures also show some model-joint gaps in the reference; they are not
a matched-pose diagnosis of the owner's Original-mode joint report.

No lighting behavior was changed: an additional intermittent recovery delay has
not been isolated in these routes. The remaining useful reproduction is the
specific path/position where Juno stays dark beyond the starting-side orange
approach, including whether he is moving or standing. A short owner recording
of that case can define the next replay. The Original-mode joint report likewise
needs the affected pose in the delivered build. Both remain **open**; the tested
shared-transform seam correction remains **awaiting owner visual confirmation**.

All temporary capture instrumentation was removed and the clean target rebuilt.
The delivered package remains the exact four-mode-qualified executable SHA-256
`59d828e38c409ce87c2b082d29786d63a72dc901c4b2f298abae9f5a3e07619f`, rather than either diagnostic executable.
Its fourteen manifest entries were revalidated after the follow-up. Muted tests
use disposable profile/save copies; the desktop shortcut preserves the existing
preview profile arguments. No release, main-checkout edit or dependency update
was made. Machine-local delivery only.

Private evidence: `lighting-exit/native-result.json`, `lighting-exit-emulator`,
`lighting-return/comparison.json`, `lighting-return-emulator`,
`lighting-return/restore-result.json` and `seams-package-qualification.json`.
Aggregate public results remain in the linked transform-coherence evidence.
Lesson: distinguish an authored spatial lighting boundary from delayed recovery,
and compare the reported crossing direction before changing brightness or timing.
