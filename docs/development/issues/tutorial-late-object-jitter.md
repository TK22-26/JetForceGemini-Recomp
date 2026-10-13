# RENDER-006: Late tutorial objects jitter; live cadence drops

Status: **owner-reported visual defect; timing drops verified in the existing
manual capture; cause and remedy open** (2026-10-13 UTC).
Severity: high; the full tutorial does not meet smooth-play acceptance.

## Report and affected build

The owner played the tutorial with log-only diagnostics at Custom 120, VSync on.
Near the end, wooden crates, the exit light and a bridge visibly stuttered or
jittered, in the later cave and when leaving the bridge area. Exact room IDs,
input sequence and symptom timestamps were not recorded. This is broader than
the earlier gem/drone report; do not assume those prior causes explain it.

Package: `high-refresh-combat-spans-20261013`, implementation
`a93faa5ef61b86536327ffa83d48fc95835a21ff`, runtime SHA-256
`e7e3af29fd9aeec9e037da93a27d0e50272ba7bbb6b4ac77eb5f6536dd2d6fc5`.
The launcher support log confirms the runtime hash, and the native log confirms
native elapsed timing and instruction spans. Both exit codes are zero.

## Recorded evidence

Private capture `frames-20261013-145735-36772-0.csv` contains 85,946 presentation
rows, from elapsed 1.990 to 733.829 seconds. SHA-256:
`34dc7c0519297f267800720d3c86ec3b5c8f45eaae9fed95f35308f8c340fb36`.
Queue drops, render-counter discontinuities and timestamp/interval mismatches
are all zero. The overlay was off. Raw logs and reviewed support files remain
on D:; [aggregate evidence](../../../evidence/tutorial-owner-timing-review.json)
records formulas, windows, provenance and limits without personal save data.

Times below are minutes:seconds since logger initialization, not since gaining
control of Juno. Rates use counter deltas divided by the sampled wall duration.

| Window | Rendered output/s | New scene submissions/s | Worst present interval |
|---|---:|---:|---:|
| 0:30-3:30 (may include initial waiting) | 119.66 | 29.92 | 15.71 ms |
| 7:15-7:35 | 110.05 | 20.16 | 70.52 ms |
| 10:40-10:45 | 119.66 | 26.66 | 10.90 ms |
| 10:45-10:50 | 116.45 | 21.61 | 34.41 ms |
| 10:50-10:55 | 114.85 | 24.85 | 31.78 ms |
| 11:55-12:00 | 119.94 | 30.03 | 8.66 ms |

The final two minutes average 118.56 output/s and 28.34 scene submissions/s,
with 25 present intervals over 20 ms. Approximate reconstructed scene intervals
include 336 above 40 ms and 167 above 50 ms. The ordinary target is about
33.3 ms per scene; these are actual source-cadence irregularities, not merely a
rounded HUD reading. The last section is intermittent, not continuously slow.

There is a 594.43-ms present-return gap ending at 11:52.947 and a 1,564.36-ms
gap ending at 10:02.762. Pause, focus and room-transition markers are absent,
so these gaps cannot be labelled unprompted gameplay stalls from this log.
Earlier near-20-Hz windows above do not depend on those long gaps.

## Interpretation and remaining work

- Source-cadence drops are demonstrated. The earlier bounded combat replay
  passes remain valid for those fixtures, but do not establish full-tutorial
  acceptance. See [PERF-001](goldwood-combat-slowdown.md).
- The reported object-specific jitter could also involve interpolation identity,
  coverage, camera-relative transforms or visibility. Those are hypotheses;
  this CSV contains no object identities, transforms, interpolation phases or
  pictures. It cannot prove whether a crate or bridge interpolated correctly,
  or whether all visual jitter coincides with the measured cadence drops.
- SCENES measures screen-scene submissions, not every simulation tick. OUTPUT
  measures successful present returns, not unique poses or physical scanout.
  Reconstructed scene timestamps use independently sampled atomic fields and
  are approximate. No CPU/GPU cost profile or audio-underrun counter was captured.
- The prelaunch check found no other games; competing processes were not
  monitored throughout the owner run. External load attribution remains open.

This was an owner-requested review of existing files and persistent issue
documentation. No new game, replay, build or optimization worker was run; no
runtime remedy was attempted. The production guard remains enabled and the
same investigation remains shelved with 23 attempts and 22 supporting jobs.
No counters or allowances changed. Further autonomous work must use the same
guarded investigation and receive an authorized continuation.

Transferable lesson: qualify a complete live route and short-window source
cadence, alongside per-object visual continuity. A near-120 presentation average
and a successful short combat fixture cannot establish smooth full-level play.

## Approved two-hour continuation

Owner approved two hours on 2026-10-13 to investigate these findings. The same
production investigation and root retain all previous counters; guard enabled.
Admitted one additional attempt and supporting job, plus 7,200 seconds. Tests
will be muted and use copied saves. No current fix or reproduced object-specific
cause is claimed. Competing controls tests must finish before timing comparisons.
Large evidence is retained under the private tutorial-investigation-20261013 ID.

### Rigid-object candidate

The supported US camPushModelMtx consumes an ObjectTransform pointer and emits
a transient combined matrix. The existing semantic path recognizes skin palettes
and sprites, but not this rigid path. Candidate binds emitted matrices to live
actor/model/camera identities and retains exact geometry/motion checks. Matrix
bytes, actor lifetime, free/reuse, and task age validate bindings. A diagnostic
shadow history measures old versus new matching only when tracing is requested.
This is implemented candidate code; qualification and actual affected-room
coverage remain pending. No object-specific visual fix is claimed yet.

The first source-edit step stopped on a nonunique text anchor after writing the
tracker and boot observer. It was not built. The renderer-only continuation
uses a unique struct anchor; the failed step is retained in private evidence.

All four focused suites passed in the first rigid build. Its final diff check
then rejected one whitespace-only blank line in the new test, so the dependent
game step correctly did not launch. Whitespace is repaired; the qualified binary
is unchanged. State and scene coverage qualification follows.

Step07 preserved exact Original and recorded-native-clock state, then stopped on
an overbroad comparison of Original versus Custom raw RAM. Different rendered
framebuffers are expected across those modes; step09 checks all other bytes
explicitly and preserves the initial failure. No performance run was launched
by step08 because its dependency gate failed.

The first timing comparison overlapped a separate launcher compiler, was
explicitly excluded by process monitoring, and did not advance to the candidate.
The copied-save coverage probe is functional evidence, not performance.

### Candidate findings and rejected projection rule

The initial identity candidate preserves exact Original and recorded-native-clock
states, and all non-framebuffer bytes across Original/Custom. Two compiled
entry-metadata checks, 17 normalizer tests and four focused C++ suites pass.
The first Goldwood rigid trace has zero improved or regressed matches. This
establishes coverage, not a reproduced remedy for the owner's late cave.

Detailed camera-turn/walk geometry traces show screen-motion, depth and camera-
plane rejections on longwoodbridge, ForestCrate and exit markers. An offline
prototype ignoring corners outside both endpoint views produced no newly matched
visible samples and some visible regressions. It was rejected before editing
production logic; the paired-game step therefore did not run. These observations
do NOT prove that off-screen vertices caused the owner's visible jitter.
The temporary geometry dumper is removed. Its overhead/underruns are diagnostic
artifacts, not clean runtime performance measurements.

One clean 120/VSync comparison reduced median update wall time excluding explicit
clock wait from 25.245 to 22.914 ms after direct entry metadata plus rigid identity.
Both had zero audio underruns; source cadence still had occasional late updates.
The repeated baseline overlapped a launcher build and was excluded. An earlier
comparison also overlapped that task. A quiet preflight that counted idle MSBuild
pool nodes was cancelled; the corrected gate checks pooled-node CPU activity.
No full-tutorial or late-cave slowdown resolution is claimed.

Owner then explicitly requested merging current develop. This candidate and
evidence are checkpointed before that merge; the combined source must be rebuilt
and qualified before any preview replacement. See
[aggregate investigation](../../../evidence/tutorial-rigid-entry-investigation.json).

## Develop integration (2026-10-13, qualification pending)

Owner requested merging develop `63e49a7a71c3a914d2adc1d91fdcf00bef30d38e`
into high-refresh checkpoint `60cb549bceb023d416dc7721793e809d33ac0699`.
The merge preserves the high-refresh recovery policy, semantic/rigid identities,
video dialog and render diagnostics alongside develop camera, controls, native
audio sample source, profiling and render-viewport fixes. The newer diagnostic
clock-stall environment name accepts the previous high-refresh name as a fallback;
existing high-refresh trace event names remain stable. Both issue histories are
retained. Build and replay results must be recorded before delivery; a successful
merge alone does not establish late-cave or full-tutorial acceptance.

The second merged combat comparison overlapped a separate Scooby-Doo launcher
build. Its first window fell to 27.92 scenes/s and is explicitly excluded from
acceptance. The dependent camera step did not launch. After the live-window
regression, the remaining combat/360/pause cases use a fresh quiet preflight;
the first clean merged combat case remains valid. No foreign work was stopped.

## Develop merge qualification (2026-10-13)

Develop `63e49a7a71c3a914d2adc1d91fdcf00bef30d38e` is integrated with the
high-refresh candidate. Fresh generation has identical game files, and 25
Python checks, 13 focused C++ suites, viewport tests, 120 video RmlUi checks and
546 modern-controls UI checks pass. Original/Custom preserve every non-render-
buffer guest byte. A new native-clock recording with the native audio source
replays exactly. Older pre-merge raw hashes differ after the imported behavior
changes; no claim of cross-revision bitwise equivalence is made.

Review caught a real message-number collision missed by the initial non-live
dialog test. The new live test reproduces swallowed widescreen relayout before
the fix, then passes after the video-state query moves to its own message.
Apply, pause/resume and aspect changes are checked on an isolated desktop.

merged-combat-120-a: 119.7/29.81, 120.0/29.79, 119.8/29.84, 119.6/29.80 OUTPUT/SCENES; merged-combat-120-final-b: 119.7/29.85, 119.9/29.74, 119.9/29.84, 119.8/29.80 OUTPUT/SCENES; merged-combat-360: 352.0/29.79, 356.4/29.75, 357.3/29.83, 352.1/29.76 OUTPUT/SCENES. All three clean combat runs have zero audio underruns and
no foreign compiler/game overlap. Pause/resume also passes. The full-circle
trace has no backward presentation phases, and the reconstructed area-47 pond
retains full north-facing camera distance. These are bounded muted tests,
not a full tutorial or physical-display acceptance.

The owner-reported later-cave objects and full-route cadence drops remain open.
Rigid identity is qualified as a candidate; no visual remedy for that exact
unreproduced report is claimed. The rejected projection rule remains absent.
See [merge qualification](../../../evidence/high-refresh-develop-merge.json)
for rates, phase counts, provenance and limits. Preview packaging follows.

## Local merged-preview delivery (2026-10-13)

The qualified combined runtime/launcher is delivered as
`high-refresh-develop-merged-20261013`. The existing desktop **JFG - High Refresh
Preview** shortcut now selects it; close and reopen an older launcher to use
the new package. Existing save, video/audio/control settings and log-only
performance preferences are preserved byte-for-byte. Package validation and
isolated setup initialization pass. Source merge: `f70b513c896df107163f2d72abed344a87dc2517`.
Runtime SHA-256: `1381e018fa2ec2cc8cc0e9c64c785753485b4068a81a08b7f29f8ca0cee2e4f8`.

This is a local preview, not a public release. Full-tutorial performance and
the exact later-cave crates/exit-light/bridge jitter still require live coverage;
their issue records remain open. All runtime tests were muted. Large private
evidence and the new package stay on D:. The production guard remained enabled
under the same investigation and counters throughout.

## Expanded owner route capture (2026-10-13, preparation)

The owner clarified that the earlier recording includes a long wait at the
start because recording had begun without their realizing it. That waiting
period must be excluded from active-route reports and review playback. The
old timing-only capture has no exact input boundary, so no precise idle cutoff
is invented. Retain the original evidence and timestamps for reproducibility;
label old elapsed windows as session time, not active gameplay time.

The owner approved one guarded hour to prepare and collect a fresh route.
The explicit launcher diagnostics option now also enables the existing RT64
interpolation trace (display phase and actor/model matching), alongside inputs,
actor/camera events and timing. Ordinary Play still strips inherited diagnostic
variables. A fresh capture starts on Play; waiting in the launcher is excluded.
The status states that diagnostics are recording. Initial save/settings are
snapshotted for replay. Frame CSV logging is enabled without an overlay in the
dedicated muted copied profile, with all capture artifacts on D:.

This is observation plumbing, not a jitter fix. Expanded synchronous traces
can affect timing; observed stalls must later be compared to a normal run.
Initial in-game waiting must be trimmed only in derived analysis/viewing, with
raw VI/input ordering preserved. Setup validation passes; owner route collection
and visual acceptance remain pending.

Validation: 640 launcher checks (including explicit trace paths, inherited-variable
stripping and duplicate rejection), 15 setup checks, six graphics-policy checks
and viewport checks pass. A muted live smoke writes all eight requested streams,
a v8 modern-input recording, rendered/source frame CSV, final image and guest RAM.
It includes 10,485 display phases, 8,592 rigid-object samples and 2,638 semantic
samples. The smoke close harness initially selected the runtime wrapper PID,
not its render child; descendant lookup recovered and closed the owned game
normally. The attempt to isolate that helper did not propagate the desktop to
the render child (it used Default); do not treat this as isolated-desktop or
clean performance evidence. No timing or visual-fix claim relies on this smoke.
The delivered runtime is unchanged from the qualified develop merge.

## Owner repeat-route report (2026-10-13, review in progress)

The expanded capture closed normally. The owner reports a roughly one-second
laggy response when Juno is hit, and the exit light marker and bridge jittering
again near the end. "Jumping" means visual jitter, not actors actually jumping.
Juno's ground shadow also appears to update sluggishly; this last symptom is
subjective and not yet established as a separate regression. Preserve the
separation between whole-frame stalls, low source cadence, object history
rejections and shadow-mask updates. No cause or fix is confirmed yet.

Affected package: high-refresh-route-capture-20261013, launcher source
9407ccd726001bad4e2372af3bdfb94688394209, unchanged merged runtime
1381e018fa2ec2cc8cc0e9c64c785753485b4068a81a08b7f29f8ca0cee2e4f8.
Input v8, camera/actor trace, interpolation trace, frame CSV, initial profile and
final RAM/image are retained privately on D:. Initial launcher waiting was not
recorded. Exclude initial in-game waiting from derived active-route reports;
retain raw VI ordering. Expanded logging overhead is a possible confounder,
not a demonstrated explanation for the reported symptoms.

The first replay fixture rejected repeated controller polls sharing a VI because
it selected retrace-range input ordering; the raw recording is retained and
valid under recorded-poll ordering. A second, muted hidden replay using recorded
VI timing runs cleanly with no audio underruns, but never leaves area 21, while
the owner reaches areas 16, 26 and 157. It is NOT accepted as an exact route or
late-cave performance comparison. Native elapsed-clock state divergence and
replay-input correspondence must be checked before making a causal comparison.

### Completed framebuffer-write window candidate

The muted replay's extra trace identifies 297 completed-sequence events with a
CPU write to the active screen framebuffer (0x10ff00 or 0x135700); all replayed
an entire finite output window. The existing path already selects the latest
interpolated image, so those outputs repeat one endpoint rather than new motion.
Candidate presents that completed endpoint once per write event while retaining
operation execution, pause, capture and unlimited handling. This does not yet
correct the existing mismatch between CPU changes on the base target and the
selected interpolated target. Route visual acceptance and timing comparison are
pending. The focus fix passes input tests but did not restore owner-route
correspondence by VI 7000; later-room reproduction remains unresolved.

### Stationary rigid object camera candidate

A fresh bounded bridge orbit again reproduces history rejection when a bridge
vertex approaches/crosses the camera plane. Independent matrix reconstruction
shows a stationary bridge and small camera steps (an example is about 8.55
world units and axis cosine 0.9988), while the projected-vertex test rejects the
whole shared transform. The previously rejected generic offscreen-vertex rule
remains absent.

Candidate captures immutable world/view/projection operands at the already
validated US camPushModelMtx return, keeps actor/model/camera lifetime binding,
and checks that their product describes the actual emitted fixed matrix.
Unchanged world/projection plus a bounded rigid camera step may interpolate a
stationary object across the camera plane. Unknown objects, changing poses,
changed projection, cuts, conflicting bindings and invalid matrices retain the
existing conservative path. No guest state is changed. Synthetic near-plane,
teleport, model-change, projection-change, singular and invalid-value checks
are added. Build, exact endpoint-state and rendered-image checks are pending.

The first camera-candidate build exposed a compatibility constraint: RT64's
adapter translation units use C++17, so a shared header cannot default a C++20
comparison operator. Explicit array comparisons restore C++17 compatibility;
the blocked image test did not run against a stale binary. Evidence is retained.

The first immutable-pose candidate passes its unit tests, accepts all 3,732
observed matrix/operand products, and preserves every non-framebuffer guest
byte in the bounded orbit. It does not yet improve bridge matching (2,610 of
3,500 before and after). Therefore it is not qualified as a bridge fix. The
captured VI 4056 images face the pond and do not visibly show the rejected bridge;
a visible rejected sample and the failing pose-continuity condition are being
checked before further changes. Full poll-order native routes also diverge:
the baseline reaches area 47, while the candidate reaches areas 16 and 26.
Their whole-route FPS averages are not a controlled performance comparison.

The missing pose acceptance is explained by guest lookup-table trigonometry:
retained view axes have squared lengths near 0.99869, just outside the initial
0.001 orthonormal tolerance. The revised check bounds near-unit axes, divides
by their measured squared lengths when recovering the camera eye and normalizes
orientation comparisons. Tests retain rejection of actual scale/cuts. A
vertex-inside-screen test alone is insufficient for large bridge triangles;
homogeneous polygon clipping is used to choose visible rejection captures.

## Review qualification (2026-10-13)

The completed-window pacing defect is reproduced and corrected in tests.
A VI with CPU framebuffer writes was presenting the already completed endpoint
for another whole 4/6-output interval. It now presents that endpoint once.
Framebuffer operations, pause, final captures and the Unlimited path remain.
In the bounded recorded-time comparison, repeated presentation phases fall
from 995 to 35, with zero backwards phases. These runs do not establish exact
whole-route input correspondence. The existing base-versus-interpolated target
CPU-write limitation described above remains open.

The stationary-object camera extension now accepts all 3,732 captured operand
products and improves bridge matching from 2,610/3,500 to 3,500/3,500; the exit
arrow remains 230/232. It preserves every non-framebuffer guest byte. However,
homogeneous triangle clipping finds that all newly accepted bridge samples in
this orbit are offscreen. This is tested coverage, NOT proof that the owner's
visible bridge/light jitter is fixed. Camera cuts, lifetime changes, changing
world/projection, invalid matrices and geometry keep conservative rejection.
The header must remain compatible with RT64's C++17 translation units.

A further native-clock tail attempt spent its entire gameplay section in area
21 rather than reproducing the late bridge. Its 1,176 geometric frames produce
no newly matched visible objects. Preserve this informative failure; do not
repeat full-route FPS comparisons without clock/input correspondence. Available
owner inputs lack the exact simulation-clock history needed for faithful route
recreation, and poll-order baseline/candidate paths diverge.

Final clean runtime SHA-256:
`f6c420fdb4ef5c7b4c361e334ca86e91a7ca94126c866e5645ab5f2db5d7546c`.
Ten focused C++ suites and four presentation-analyzer tests pass. Temporary
geometry dumping is removed. Original/Custom 120 have identical save hashes
and zero differing guest bytes outside the known rendering buffers. These
readback-heavy state probes report 2/3 audio underruns; they are not clean
performance evidence. The separately measured native Play tests below have zero.

At 1164x873, isolated muted Goldwood combat with normal and expanded logging
holds 119.65-119.95 OUTPUT and 29.76-29.86 SCENES across the measured windows.
The expanded trace contains 18 damage events. All live runs have zero audio
underruns and zero dropped diagnostic rows. A 360-cap run delivers
349.89-354.92 OUTPUT / 29.73-29.82 SCENES, so it does not qualify sustained 360.
Pause/resume passes; its deliberate 1.25-second pause is excluded from a
slowdown claim. These are bounded checks, not the owner's full-route resolution.

Active owner-route reporting now starts at first non-neutral gameplay input,
VI 2010. The earlier VI 1978 position change was entry settling, not player
input. Raw recording order/timestamps remain intact. The active route averages
113.73 OUTPUT / 28.14 SCENES over 225.85 seconds, with 211 intervals over 20 ms
and 67 over 40 ms. Its 1,466 ms maximum includes room-transition coverage and
must not be attributed to a hit without correlation.

The exact visible crate/light/bridge report, full-route damage slowdown and
[shadow cadence](shadow-cadence.md) remain OPEN. Lessons: completed framebuffer
writes do not authorize a fresh animation interval; immutable transform
operands must be tied to emitted matrix bytes and object lifetimes; matching
counters and offscreen geometry cannot establish a visible fix. Aggregate
[evidence](../../../evidence/high-refresh-route-review.json) preserves the
qualification scope without ROM-derived meshes or save files. Raw evidence is
retained privately on D:. No public release or full-game acceptance is claimed.
