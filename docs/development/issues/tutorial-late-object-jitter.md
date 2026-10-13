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
| 0:30-3:30 | 119.66 | 29.92 | 15.71 ms |
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
