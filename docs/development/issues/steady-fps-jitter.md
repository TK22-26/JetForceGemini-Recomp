# RENDER-003: Jitter with steady 120 OUTPUT / 30 SCENES

Status: semantic character/camera interpolation tested and delivered as a local preview; owner visual confirmation pending. Overall jitter remains open.
Severity: high; smooth high-refresh rendering remains incomplete.

## Report and reproduction

The owner reports visible jitter even in a quiet scene while the counter holds
120 OUTPUT / 30 SCENES with no visible dips. It occurs both without input and
during motion, but is most obvious while moving Juno and turning the camera
together. The reported profile requests Custom 120 with VSync on. The affected desktop
preview was `high-refresh-native-timing-preview-20261012`, implementation
`5c7df1bdee61778590fb3b7baa281958a9167870`, runtime SHA-256
`a14d9d77fc98ef6be1999a3ea9492d60467a4b107e376c66d431fbfd70231259`.
Confirm the running executable separately; the owner report is not an automated
reproduction. The owner explicitly requests interpolation around stable actor,
skeleton/joint and camera identities, beyond matching graphics batches.

## Existing evidence and hypotheses

- [PERF-002](frame-diagnostics.md) corrects the reproduced capped-play bridge's
  source-clock fallback. That does not establish visually continuous motion.
- OUTPUT counts successful present returns, including repetitions; SCENES counts
  new submissions. Neither establishes unique images, physical scanout or smooth
  camera/animation progression. A stable average can conceal uneven intervals.
- [Presentation history](../../../include/jfg/renderer/interpolation_history.hpp)
  matches exact geometry and blends combined transforms. Unmatched/ambiguous
  geometry falls back to endpoints; animated geometry need not retain its key.
- Incomplete animation coverage, camera/player phase mismatch, coefficient
  blending and presentation/display pacing are competing hypotheses, not a
  diagnosed cause. The 30-Hz source rate alone does not make jitter inevitable.
- Combined movement and camera rotation need the same presentation timestamp.
  Stable semantic identities must include lifetime/reset handling so reused
  actors, camera cuts, teleports and mode transitions do not blend unrelated data.

## Planned validation and acceptance

Compare stationary, movement-only, camera-only and simultaneous-motion fixtures
using copied profiles/saves and muted, owned hidden windows. Measure per-frame
spacing and actual intermediate camera/body motion, not counters alone. Keep
heavy GPU screenshot captures separate from pacing benchmarks. Preserve the
original-clock reference and guest update/movement rules. Test actor reuse and
animation boundaries before claiming complete coverage. Native monitor/focus
behavior and owner visual confirmation remain necessary where hidden tests cannot
establish them. Do not infer that this report shares the heavier combat cause.

## Modern-engine references

Fixed simulation with interpolated rendering is a standard design:
[Godot's interpolation overview](https://docs.godotengine.org/en/stable/tutorials/physics/interpolation/physics_interpolation_introduction.html).
Camera handling can combine an interpolated follow target with per-render mouse
rotation; camera and target sampling must agree:
[Godot camera guidance](https://docs.godotengine.org/en/stable/tutorials/physics/interpolation/advanced_physics_interpolation.html).
These are design references, not evidence of implementation parity in JFG.

## Resolution and compatibility

The changing-geometry history gap is established and addressed by semantic
vertex ownership. It is not established as the sole cause of all reported jitter.
The candidate preserves gameplay state and the terrain correction. See the
qualification below and its later delivery record for the tested artifact. The
same guarded investigation retains all charges; unrelated PC/audio work is
unchanged. Never feed interpolated visual positions back into simulation.

## Diagnostic interruption and storage recovery

The identity diagnostic was interrupted by a full C: drive before runtime source edits or a game run. The guard retained the failed charge and stopped at 18 attempts. The owner explicitly approved one additional guarded retry within the existing five-hour deadline, preserving all counters and the investigation root.

Large private captures were moved to `D:/JFG-private/high-refresh-20261011` with SHA-256 verification of every file before removing the original copies; directory junctions preserve existing evidence references. New large outputs use D:. The production ledger and source checkout remain in place. The private relocation receipt records 16 directories, 6612 files and 8036767841 bytes.

Informative setup failures: the inventory initially used Path.is_junction, unavailable in the installed Python; Windows reparse attributes replaced it. The first cleanup script encountered PowerShell array wrapping before deleting anything; direct JSON array assignment corrected it. An automatic command review had rejected the combined relocation command without a specific reason; copying/hash verification and path-checked cleanup were subsequently separated. These failures establish no rendering result.

## Semantic interpolation candidate

The bounded identity trace ties animated matrix DMA addresses to two alternating
palettes owned by a model instance, with a stable bone index. Exact-shape matching
had left changing body geometry without history. The candidate carries actor
lifetimes and camera ownership with each immutable graphics task, and matches
logical model vertices by actor lifetime, instance, model, camera and joint.
Free requests, missing actors, level/model/camera changes and discontinuities
invalidate history. UV clones retain their original logical vertex identity.

Character vertex endpoints interpolate in world space before applying the same
camera phase. This avoids separately blending deforming local positions and
joint transforms, which can pull shared edges apart. It is presentation-only:
guest simulation and input timing are unchanged. It is not a reconstructed local
skeletal hierarchy with quaternion blending or per-render mouse look. Unsupported
draw paths retain the previous conservative matcher.

Six focused identity/interpolation/clock tests pass. The first muted moving-route
run matched 517,189 of 524,527 tagged vertices (98.6%); that is coverage evidence,
not visual acceptance. The same run averaged 119.22 output FPS and 27.29 scenes/s
in VI 4000-4400, including a 33.104-ms output interval. Pacing therefore remains a
qualification concern, and the installed preview has not been replaced. Paired
runs of the accepted runtime and candidate, without interpolation trace output,
are retained in private artifact `semantic-interpolation-v1/pacing-comparison.json`.

Implementation setup failures: a patch selector initially matched both a real
task and a skipped-task placeholder; it was narrowed before building. The first
build used RT64 interop matrix member syntax on an hlslpp matrix; row indexing
and explicit construction corrected it. Subsequent review guarded live-only
identity state for non-live builds, removed a per-UV-clone context mutex lookup,
cached joint inverse validation per DMA and inverses per transform, and skipped
semantic vertex collection for offscreen masks. The refined binary passed the route qualification below. Final review bounded
byte-swapped reads for truncated RAM spans, rejected signed-negative bone counts,
and kept unknown-camera paths on the existing conservative matcher.


## Bounded qualification (2026-10-13 UTC)

Seven focused tests pass, including retirement/address reuse, missing actors,
level/camera changes, stale buffers, ambiguous UV duplicates, actor-wide fallback,
and coincident shared-edge vertices under different joint rotations and camera
motion at five interpolation weights. F3DDKR texture tests cover the modified UV
clone path. These checks preserve endpoints; they do not establish raster coverage
of every reported thigh pose.

Without detailed interpolation tracing, the initial paired route averaged
119.85 OUTPUT / 29.78 SCENES for the candidate versus 119.90 / 29.79 for the
installed build. Refined idle, movement-only and camera-only cases held roughly
120 output FPS and 29.6-29.8 scenes/s. Combined movement/camera input was verified
in guest position/yaw samples, not merely assumed from the replay file.

The combined route exposed the same 31-update three-VI recovery episode in both
old and new builds: about 119.5-119.6 output FPS / 27.5 scenes/s over VI 4000-4400.
This remains an open source-cadence limitation. Custom 360 averaged 350.1 output
FPS / 27.4 scenes/s and included a 41.5-ms output interval. Neither observation
supports a claim of completely stable 30-Hz scenes or steady 360-FPS output.
All six normal-play cases recorded zero audio underruns and dropped log rows,
and preserved the copied save. The hidden-window tests measure successful present
returns; they do not qualify physical VSync/monitor delivery.

The original-clock reference retained exact guest/RT64 memory and copied-save
hashes. Paired original-clock visual runs likewise retained identical final
guest and RT64 memory. The first selected screenshot window was after movement
had stopped and was inconclusive for animation. A second bounded window targets
active simultaneous movement. Swapchain readback captures deliberately stall
rendering and are excluded from performance claims. Capture counts and hashes,
tested runtime identities and route results are in
[qualification](../../../evidence/semantic-interpolation.json).

In the active window, the baseline repeated one complete image across six
subframes, while the candidate produced six different images and changed dark
blue character pixels in each adjacent pair. The capture start can land on a
different presented group, so this is sampled motion evidence, not an exact
paired per-frame trajectory or proof that every output image is unique. Visual
inspection shows the walking pose progressing; the automated body mask excludes
the surrounding bright water but is not a complete character segmentation.

The remedy is host presentation metadata and world-space vertex interpolation;
it does not increase simulation/input frequency, reconstruct a local skeleton
hierarchy, interpolate lighting attributes, or implement per-render mouse look.
Unsupported paths keep conservative transform matching. Teleports and large
projected discontinuities hold an endpoint; every small cinematic cut and model
variant is not yet covered. Reported Original-mode thigh gaps, delayed lighting,
combat slowdown, Unlimited saturation and long-session/audio behavior remain
separate open work. Owner live confirmation is required before resolving this
jitter report.

Transferable lesson: constant output counters do not establish unique, coherent
animation samples. Carry stable ownership with the immutable render task, make
all parts of an actor share the same fallback decision, and measure screenshot
motion separately from timing to avoid diagnosing readback overhead as normal
play stutter. Large evidence remains on D: with verified stable references.


## Local preview delivery (2026-10-13 UTC)

Implementation commit `01a35a13539a89e8842b8491eb37565d42b03de8` is packaged as
`high-refresh-semantic-20261013` on D:. The existing **JFG - High Refresh Preview**
desktop shortcut now selects that package. Close an older launcher and reopen
the shortcut to test walking while turning the camera. Your existing profile,
save and settings were preserved; all 14 package manifest entries and launcher
initialization passed. F8 and **JFG - Performance Logs** remain available.
No public release or push was made.

The exact delivered runtime SHA-256 is `71f59d66fc20e62f85cc3c2c280e72a85b02aee61e0de5a87adf45fe80f906b4`.
Final combined-motion qualification averaged 119.87 output FPS /
27.49 scenes/s at Custom 120 with requested VSync, and
345.38 / 27.44 at Custom 360 with VSync off.
Output p99/max intervals were 8.637/10.200 ms and
4.228/42.520 ms respectively.
Both normal-play runs recorded zero audio underruns/dropped log rows; the exact
original-clock memory/save reference still matches. The existing three-VI
recovery episode remains visible; these are not steady-30/steady-360 claims.
Detailed results are in the qualification JSON. Owner visual review, full-game
coverage, physical monitor pacing and the separate seams/lighting issues remain
open. The previous package is retained for comparison.
