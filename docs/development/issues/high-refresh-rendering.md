# RENDER-001: High-refresh presentation is not implemented

- Severity: enhancement / significant rendering limitation.
- Status: source review complete and reference replay repeatable; implementation
  pending, with no high-refresh gameplay verification.
- Reported and last updated: 2026-10-11 UTC.
- Baseline: `d649cf586b13d2bff7ab7258db9991ad554ae017`, combining the owner's
  `66e14d6` workspace checkpoint with latest fetched main `acccc55`.
- Owner target: smooth 60 FPS and higher, ideally 360+ on capable hardware;
  preserve game simulation timing.
- Related: [PERF-001](goldwood-combat-slowdown.md) is a separate, ongoing
  simulation-cadence investigation. This work does not reopen or replace it.

## Symptoms and reproduction

The current renderer starts with RT64's original refresh mode. JFG's custom
F3DDKR bridge explicitly marks its transform groups as ignored for interpolation.
A high-refresh display alone therefore does not provide new interpolated scene
states. These are source observations, not measurements of a new runtime.

## Evidence and hypotheses

`src/renderer/rt64_shell.cpp` selects Console presentation to preserve CPU-written
overlays. `src/renderer/rt64_f3ddkr.cpp::select_matrix` selects `G_EX_ID_IGNORE`
and skips all transform components, with an already-combined matrix and identity
view/projection. RT64's pinned `5473732a` workload queue also clamps manual rates
to detected display refresh. Each boundary must be addressed explicitly.

The leading hypothesis is presentation-only RT64 interpolation with stable
render-object identities and qualified camera/model representation. DK64 uses
simple interpolation in its reviewed model path, so separate affine transforms
are not a prerequisite for a bounded initial experiment. Unqualified decomposition
remains inappropriate. Increasing VI, Count or simulation frequency is outside
the agreed first milestone.

## Attempts and results

| Date | Investigation | Result |
|---|---|---|
| 2026-10-11 | Checkpoint owner workspace and integrate fetched main | `66e14d6` and merge `d649cf5`; 10 release-prebuilt and 7 package-beta tests pass under production guard |
| 2026-10-11 | Inspect pinned RT64 and JFG bridge | Explicit interpolation opt-out, combined matrix representation, presentation ownership and display-rate clamp identified |
| 2026-10-11 | Retrieve primary sources from DK64, Zelda, Banjo, Starship and DKR ports | Revision-pinned comparison complete; stable identities, camera discontinuities and task ownership inform the proposed integration |

## Actual resolution

Pending. No high-refresh implementation or release is claimed.

## Verification and remaining limits

Need distinct rendered-frame evidence, frame pacing and GPU measurements;
unchanged simulation/input/audio/save behavior; camera cuts, CPU overlays,
animation, particles, menus, pause and multiplayer checks. A rate setting or an
FPS counter alone is not proof of smooth motion or 360 FPS performance.

## Lessons and retained evidence

The production guard stays enabled across restart, compaction and handoff.
Use investigation `high-refresh-rendering-20261011` in the original operational
ledger; the owner granted a 43,200-second budget. Preserve counters and stop on
denial. Private evidence: `high-refresh-20261011`; no ROM, generated game code or
save data is added to source. Update this record and the issue index as work proceeds.

## Working-build memory baseline, 2026-10-11

Four isolated replays used retained reference-clock runtime `26852729d4f` and
copies of one save/profile, stopping at VI 4000, 4002, 4004 and a repeated 4004.
All runs exited normally. Repeated VI 4004 guest RDRAM, renderer snapshot and
captured image were byte-identical. The original save remained unchanged.
This retained runtime is a reference build, not a new build of the research branch.
Private hashes and endpoint trace metadata are retained in `memory-baseline.json`
and `memory-comparison.json`. The runtime probe marks `acceptance=false` and
`runtime_snapshot_complete=false`; these dumps are not full resumable checkpoints.
This qualifies a reference fixture only; it does not validate interpolation.

## Findings and next implementation boundary

See the [source comparison](../../upstream/high-refresh-reference-review-2026-10-11.md)
and [implementation plan](../../planning/high-refresh-rendering.md).

All four replays retained the reference clock and exited at their requested VI.
The repeated VI 4004 state hash, recorded input, 4 MiB guest RDRAM, 8 MiB renderer
snapshot and captured image agree. This establishes repeatability for this fixture
and runtime only. It does not establish unchanged gameplay for a future candidate.

- `vi4000` to `vi4002`: 23,419 guest-memory bytes differ; 10,423/307,200 pixels differ.
- `vi4002` to `vi4004`: 248,057 guest-memory bytes differ; 298,273/307,200 pixels differ.
- `vi4004` to `vi4004-repeat`: 0 guest-memory bytes differ; 0/307,200 pixels differ.

The traces alternate scene color buffers `0x10ff00` and `0x135700` with
a separate offscreen pass at `0x328480`. At the endpoints, the last submitted
task is the small offscreen pass (`command_size=0x1b`), whereas presentation
selects a scene buffer. Do not use the last arbitrary graphics task as the
interpolation endpoint. The existing single final `.rt64` dump needs task/VI
lineage before it can serve as a multi-frame interpolation replay.

No renderer rate switch, transform-ID patch or new game build was installed.
The source investigation is complete enough to specify the first implementation
experiment; high-refresh rendering remains open and unverified.
