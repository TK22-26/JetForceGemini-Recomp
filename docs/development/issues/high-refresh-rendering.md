# RENDER-001: Experimental high-refresh presentation

- Severity: enhancement / significant rendering limitation.
- Status: prototype implemented; release build, five focused tests, 60/240 FPS
  gameplay replays and consecutive-image capture verified for one fixture.
  Broader visual qualification and owner playtesting remain pending.
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
states. These describe the default mode; candidate measurements are recorded below.

## Initial source evidence and hypotheses

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
| 2026-10-11 | Implement, build and replay the opt-in prototype | Local commit `8d8f097`; five focused tests pass; 60/240 FPS camera fixture and exact guest-state comparison verified; owner visual acceptance pending |

## Actual resolution

Implemented in local commit `8d8f09701cc50d3a5b03eafd90ff5a41d3aeb3e9`
on `research/high-refresh-20261011`. No release is associated with this candidate.

An opt-in transform interpolation path is implemented behind
`JFG_EXPERIMENTAL_RENDER_FPS=60` (or another integer up to 1000). It preserves
the authored workload matrices and keeps copied scene history outside guest RAM.
This is an unreleased candidate; full visual acceptance and performance
qualification remain open.

## Verification and remaining limits

The candidate has matched guest memory/execution and distinct presented-frame
evidence for the retained replay. Still needed: longer pacing/GPU measurements,
audio-device behavior, semantic actor/camera lifecycle, CPU overlays, animation,
particles, menus, pause, resize and multiplayer checks. A rate setting or an FPS
counter alone is not proof of 360 FPS performance.

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

At the research handoff, no renderer rate switch or new game build had been
installed. The implementation below follows that retained baseline; the research
measurements must not be presented as candidate verification.

## Implementation in progress, 2026-10-11

The owner requested executable implementation after the research handoff.
A guarded coding/build/replay session is adding an opt-in render-rate prototype.
It snapshots exact-geometry matches and previous matrices with each RT64 workload,
preserves scene interpolation state across offscreen tasks, and derives source
cadence from immutable guest VI timestamps. The default remains original mode.
The initial implementation began with build, frame evidence and gameplay comparison pending; the completed candidate results are recorded below. CPU overlays
under SkipBuffering, ambiguous repeated meshes, deforming meshes and camera
discontinuities remain acceptance limits. This continues the same investigation.

Build setup findings: CMake is supplied by Visual Studio rather than PATH. The shared generated cache failed the branch normalizer digest check, so a new private root was regenerated. Its first compile exposed the missing final original-timing header step; the normal generation finish helper now supplies that header from this branch. No freshness checks or compiler errors were disabled.

The first renderer compile caught a C++20/char8_t incompatibility in pinned RT64, explicit interop-matrix conversion requirements, and an over-broad counter patch site. The shared history interface now remains C++17 compatible; RT64 keeps its existing language standard, conversions are explicit and the counter replacement is scoped to the render loop. Runtime qualification follows below.

The full game compile reached native boot and caught an MSVC deprecated environment getter in the new FPS setting. It now uses the existing Windows-safe environment API; warnings remain errors. The replay launch gate correctly refused to execute before a successful build. The generated function objects are retained for the incremental rebuild.

The optional frame-sequence capture initially matched a second GPU wait in the resize path. Its completion hook is now anchored to the exact presentation command submission, preserving the resize path. Compilation caught this before any candidate replay was launched.

## Candidate replay qualification, 2026-10-11

Release runtime SHA-256: `3a739fbf3b1f4824341e75634305945ce36c1351e1b835c761847208e3a26ccb`. Three isolated 4,100-VI replays at original, 60 and 360 requested FPS all completed normally in about 70 seconds. Full 4 MiB guest RDRAM, 8 MiB renderer snapshot, recorded input, save and probe state hash are identical across modes. All runs report 1,906 controller samples, 2,896 graphics tasks, 2,047 decoded audio tasks, 3,680,667,236 instructions and zero unsupported accesses. The probe still marks acceptance=false and runtime_snapshot_complete=false; this is fixture-specific evidence, not full game acceptance.

- Requested 60: effective 60 FPS; moving-camera VI 4000-4098 measured 59.98 presentations/s with 100 scene renders. Median/p95/p99 presentation intervals: 16.672 / 16.738 / 16.755 ms.
- Requested 360: effective 240 FPS; moving-camera VI 4000-4098 measured 239.81 presentations/s with 400 scene renders. Median/p95/p99 presentation intervals: 4.170 / 4.303 / 4.411 ms.

Private evidence: prototype-replays-v1/result.json and prototype-pacing-v1.json. Hardware: RTX 5090 / Ryzen 7 5800X; display detected by RT64 at 240 Hz. The 360 request is display-capped, so 360 delivered FPS is not claimed. Frame sequence capture follows separately and is excluded from pacing measurements.

## Presented-frame verification and handoff

- Requested 60 FPS: captured 4 actual swapchain frames; present 2789: 2/2 unique images; present 2791: 2/2 unique images. Guest RAM remains byte-identical to original mode.
- Requested 360 FPS: captured 15 actual swapchain frames; present 2788: 8/8 unique images; present 2791: 7/7 unique images. Guest RAM remains byte-identical to original mode.

Images are retained privately in prototype-frame-sequence-v1; per-pair pixel
differences and distinct-image counts are summarized in prototype-frame-sequence-analysis-v1.json.
These capture runs are excluded from timing measurements. Sampled final images
show the HUD, character and reflection; owner motion/scene acceptance remains
pending. The [feature page](../../features/high-refresh-rendering.md) records the
preview invocation, exact coverage and remaining limits.

The first milestone is a usable experimental implementation, not a released or
fully qualified rendering replacement. Preserve this evidence, original timing
and default rendering. Recover the original production ledger before further
autonomous work; never reset counters or bypass a supervisor denial.

## Guarded continuation boundary

The implementation, builds, replays and image checks ran inside the existing
production-guarded implementation job. Its starting investigation counters were
six attempts including the active job and five completed supporting activities,
with a six-activity limit and a 43,200-second execution allowance. The guard was
verified enabled throughout; no counters, roots or limits were reset.

Completing this supporting job reaches the activity limit even though elapsed
execution is below twelve hours. Read the production ledger and the retained
implementation-progress.json before any continuation. A completed preview does
not authorize another job or reopen the investigation after shelving. Keep
RENDER-001 open for the remaining acceptance work.
