# GH-048: [Playtest] In high framerates flying enemies move faster

Status: deferred for the current planned version by owner instruction on
2026-11-08; unresolved, not accepted as fixed. No further #48 work or manual
sign-off is required for this version. Existing candidate code and evidence
are retained; this documentation decision does not implement or remove code.

Controlled runs isolate ordinary Play's host-clock update cadence
as the cause of faster legacy per-call flight motion, including Original FPS.
The local elapsed-VI candidate passes finite checks but does not reproduce the
original variable load cadence. Exact Original policy and hardware timing
remain unresolved; no final fix or release qualification is claimed. See the
[Original timing investigation](original-mode-simulation-parity.md).

The owner explicitly requested "48 - skip for this version". Remove #48 from
the current manual-test queue and revisit its remaining engineering/reference
qualification in future work, without selecting a future release date or
changing the recorded Original-timing requirement. No GitHub closure is implied.

Source: [[Playtest] In high framerates flying enemies move faster](https://github.com/TK22-26/JetForceGemini-Recomp/issues/48). Evidence snapshot retained privately in D:/JFG-private/remaining-gh-issues-20261027/github-issues.json.

## Reported symptoms and reproduction

### Problem type

Gameplay or progression

### Launcher and game build

1.4.0 Release build

### Windows version, GPU, and input device

Windows 10, GTX 1080, XBOX Controller

### What happened and how to reproduce it

In high framerates flying enemies move faster which makes them sometimes hard to hit depending on the type, they also crash faster when shot down.

### How often does it happen?

Every attempt

### Support ZIP and additional details

Best example in the second level of the Swamp world at the beginning with the tree platforms and lake.

## Scope and evidence

Local owner-authorized batch: compare simulation speed at Original and high output. Preserve existing approved fixes, user profiles and ROMs. No GitHub posting or issue changes. A reported symptom is not yet a confirmed cause. Attempts, results, final remedy and verification limits will be recorded here.

## October 27 investigation progress

Normal Play at Original and 120 FPS was compared with the same copied profile and input route through Swamp Landing Play (158) to Swamp bog (118). This first route contains ground ZombieAnt actors, not the reported flying encounter. Simulation rates are approximately 29.8 updates/second in both modes. One enemy's travelled path was 4,892.77 versus 4,892.57 world units over comparable 113–114 second intervals. This rules out a global fourfold simulation-rate increase in that control case; it does not resolve the flying-enemy report.

The names and native exit destinations are being used to locate the intended lake/tree-platform encounter. A dead-end trip to room115 (Swamp) also contained only ground enemies. No speculative speed multiplier is applied. Private evidence: tawfret-ground-control-047.json and route captures.

## Actual flying-enemy comparison

The native exit route reached Swamp track (125), with three live DragGalaxian actors. With the same copied profile and input, Original and 120 FPS both simulate approximately 30 updates per second. One flying actor travelled at 108.04 versus 107.92 world units per second over comparable 25-second windows. The other actors also showed no high-refresh speed multiplier; small sampled path differences include spawn-phase and AI timing differences.

A separate paired run used the existing Instant kill mod to set enemy health to zero and let the original death logic run. This is a controlled native death-path comparison, not a recorded weapon hit. All three falling trajectories matched exactly at every corresponding native update (43, 40 and 33 samples). Their observed durations were 1.4042/1.4048, 1.3039/1.3027 and 1.0703/1.0693 seconds, respectively. Output refresh does not alter those motion samples or duration in this case.

Private evidence: flying-speed-057.json, flying-death-063.json, flying-death-summary-063.json and the paired normal-Play route captures. All runs close cleanly. No gameplay speed adjustment is justified by these results, so none was added. The reported v1.4.0/GTX1080 symptom has not been reproduced on the current candidate and this host; exact reporter-route/hardware verification remains open. The evidence does not prove every flying enemy, all performance conditions, or the reporter's exact room.

## Original-ROM comparison in progress

The October 27 follow-up now includes actual EmuHawk/Angrylion with the pinned
US ROM, the same logical copied Flash checkpoint, and its recorded controller
poll path replayed by the candidate. Room 125 and all three DragGalaxian
identities and spawn positions match. This controls the prior route difference.

The original-ROM encounter produces roughly 19 actor updates per guest second,
versus roughly 30 for both recomp output modes. The first enemy crosses from
spawn height to Y > -200 after 60 original-ROM VI retraces versus 44 in recomp
Original (22 versus 21 observed updates). This is new evidence of a difference
from the original emulator baseline; the earlier Original/120 pair alone did
not establish N64 speed parity. Enemy paths, timings and native delta handling
are being separated before assigning a cause or applying a speed change.

No arbitrary enemy multiplier or global simulation change has been introduced.
Private evidence: emuhawk-sanitization-20261027/matched-flight-011.json and its
original-ROM/native captures. Emulator wall speed is not used as game speed.

## Original-ROM death/timestep qualification

The first controlled dead DragGalaxian matches the recomp at all 43 common
position samples, with zero XYZ difference. The same samples span 133 guest VI
retraces in EmuHawk and 84 in both recomp output modes (about 2.22 versus 1.40
guest seconds). This is a difference in simulation cadence, not an interpolation
speed multiplier. The separate original-ROM live encounter passes timestep
arguments of 2, 3 or 4 to controlPlayer, predominantly 3; the matched recomp
probe passes 2 throughout its bounded sample.

Source review agrees with the measured death curve: the native SquaddieControl
death branch at overlay offset 0x11E34 damps horizontal velocity and subtracts
a fixed 1.0 from vertical velocity once per update. That branch does not scale
this acceleration by elapsed retraces. Running this legacy update more often
therefore completes the fall sooner in real/guest time. The original game also
has timestep-scaled paths; a blanket speed factor would change unrelated AI and
movement and is not justified by one encounter. No speed adjustment was added.

This qualifies the first actor's controlled death, not all flight AI, all
performance conditions, physical N64 timing, or a natural weapon hit. The
reporter's broader concern remains open. Prior Original/120 agreement must not
be described as original-ROM timing parity.

Private evidence: flight-timing-conclusion-022.json, native-timestep-021,
emuhawk-death-014 and emuhawk-screenfx-0-018/timesteps.tsv under the follow-up
root. The first timestep probe misspelled its retrace-hash environment variable
and failed setup; the corrected probe completed cleanly. Probe dumps are used
for timestep arguments, not host-performance measurement.

## Owner-approved original-ROM timing rerun

On October 27 the owner approved three additional hours and clarified that
EmuHawk should be rerun. The same production investigation/root/counters are
preserved. New checks repeat neutral flight and controlled deaths, then remove
the execution breakpoint from a flight run to test whether instrumentation
changes guest cadence. Capture guest VI intervals, actual timestep arguments,
actor position and velocity; do not use emulator host wall time as game time.
No speed change is justified merely by a lower original frame rate. Results
pending; private evidence root: flying-timing-rerun-20261027.

## Completed repeatability and full flight comparison

The owner-approved rerun completed five actual original-ROM runs: two neutral
flight repetitions, a third flight run with the execution breakpoint removed
before the first enemy update, and two controlled death repetitions. All three
flight captures have exactly identical per-VI positions, velocities and health
for all three DragGalaxians. Both death captures also match exactly. Removing
the execution probe does not change any observed guest timing or motion.
EmuHawk host wall duration varies; it is not the timing denominator.

Three new native Play runs replay the same original controller-poll route and
logical copied Flash: Original output, 120 FPS, and a repeated Original run.
The warm Original and 120 FPS runs both advance the live enemies at exactly
30 position updates per guest second in the measured steady window. They match
all 2,446 common position/velocity samples. The first Original run includes
extra guest retraces between some updates; its motion sequence still matches.
That one-run delay is recorded, not treated as an output-rate speed multiplier.

Crucially, original-ROM and recomp also match **all 1,410 common live-flight
position and velocity samples** (477, 470 and 463 by actor), with zero numerical
difference. The original encounter spreads them over more guest retraces:

| Actor, spawn order | Common live samples | Original-ROM VI span | Recomp 120 FPS VI span |
| --- | ---: | ---: | ---: |
| First | 477 | 1,511 | 958 |
| Second | 470 | 1,493 | 942 |
| Third | 463 | 1,472 | 927 |

These are spans between corresponding observed samples, not full lifetimes.
Nominally 60 VI retraces equal one guest second. The original steady window is
about 18.6 position updates per guest second. Its controlPlayer timestep counts
over the full capture are 7 calls with 2, 384 with 3, and 86 with 4.
Every observed live position change in the compared windows equals the previous
position plus the current stored velocity, with exact single-precision rounding;
there is no additional elapsed-VI factor at that integration step.

Both new controlled death runs match the prior paired native death captures for
all three actors, with zero XYZ error over 43/38/31 common samples. Their original
VI spans are 133/125/104 versus 84/74/60 in both native output modes. Common
prefixes differ in length because removal/collision observation endpoints differ;
this does not assert identical despawn timing. Health is set to zero once at
spawn, while position, velocity, timers and AI code remain untouched. These are
controlled death-path tests, not newly recorded natural weapon hits.

### Cause, current disposition and compatibility lesson

The measured difference is real relative to this original-ROM emulator
baseline. Legacy flight integration and falling motion advance once per game
update; the recomp executes that unchanged motion sequence more frequently.
The SquaddieControl death acceleration remains a fixed 1.0 per update, and its
movement helper passes actor velocity directly to movement/collision handling.
There is no evidence here of an extra multiplier from selecting 120 FPS, a
different compiled flight curve, or an execution-probe artifact.

No gameplay timing patch was made. A constant 19/30 slowdown would encode this
particular encounter's measured performance into all flying enemies; it would
not establish a correct time-based reference for other rooms, enemy types or
loads. A remedy needs an explicitly justified simulation reference and checks
of collision, firing/AI, death timing and progression across those cases.
This report remains open; the owner's larger batch must not label it fixed.

Earlier Original/120 agreement only established output-mode parity. It did not
establish original-game timing parity. The new full-curve comparison supersedes
the earlier uncertainty about aligning live paths: corresponding motion states
now match exactly by update, while guest-time pacing demonstrably differs.
This remains an original US ROM/EmuHawk 2.11.1 Angrylion/cxd4 comparison, not
physical N64, the reporter's GTX1080 machine, or every flying-enemy class.

Private evidence: flying-timing-rerun-20261027/reference-reruns.json,
original-repeat-analysis.json, live-comparison.json, curve-comparison.json,
warm-native-comparison.json and verification.json. ROM/save/runtime hashes,
original checkpoints, Lua and input routes are retained privately. All eight
new game/emulator runs exit cleanly; original user saves and runtime are
unchanged. No GitHub comments, issue changes, commits, pushes or publication.

## Owner-approved implementation, October 27

The owner approved three hours to implement and validate a shared elapsed-game-
time correction. The same production investigation/root and all counters remain.
Before selecting a reference cadence, compare additional original-ROM encounters
and inspect the shared flight movement, steering, falling and timer consumers.
The initial plan required qualifying the reference before implementation. Preserve grounded enemies,
player controls, collision and existing smooth presentation. All candidate work
and copied-profile replays stay local; evidence root: flying-timing-fix-20261027.

### Implementation and qualification in progress

A second original-ROM encounter (Goldwood room 24, Galaxian5) runs at about
20.05 updates per guest second; the initial Tawfret case is about 19 under
heavier load. The local candidate uses a stable three-VI movement reference
(approximately 20 Hz), independently of output FPS. This is an explicit
compatibility choice, not a claim that every original room always runs at 20 Hz.

The shared movement-5/death-1 squad class receives elapsed-VI acceleration,
turning, flight drag, displacement, death gravity/spin and contact drag.
Velocity keeps its native units for steering and collision decisions.
Animation and existing elapsed-time AI clocks remain native. Ground, player,
special movement classes and instruction-timed oracle runs are excluded.
ROM-free math and actual-adapter checks pass. The full Windows suite passes
117 tests; the corrected GCC fixture also passes the complete available Linux
suite (the pre-existing G2 trap-runtime quarantine remains excluded).

Qualification is not complete: the v2 controlled Tawfret death run stopped at
an unresolved resident target (0x8009BE20), after the observed death curves.
Other initial flight/death runs exit cleanly. Preserve and investigate this
failure before approving a preview. The first full CTest invocation used the
partial native-runtime build tree and found unbuilt executables; the dedicated
portable Windows tree supplies the complete passing suite.
Private evidence: flying-timing-fix-20261027 (reference inventories, component
tests, native-v1/v2 results, and swamp-death-original-v2 trap/capture).

### Scope, reference and preliminary comparison

The implementation is a runtime adapter around the shared squad movement class,
not an output-FPS switch or a global game-clock change. A positive elapsed-VI
argument determines the fractional movement step. Canonical velocities retain
their original units for acceleration solvers, turning, targeting and collisions.
Death gravity and drag use fractional extensions of the original discrete
integrator; one reference tick reproduces the legacy step. Contact stop/bounce
decisions remain native, and their subsequent drag/gravity are time-scaled.

Reference surveys also included Goldwood ground-only rooms and a neighboring
Tawfret ground encounter. Their differing update rates are recorded; they are not
used to claim a universal N64 simulation rate. Movement-5/death-1 is the bounded
supported class. Special movement classes, players, grounded enemies and
instruction-timed oracle runs retain their original path.

The second original flying type is Galaxian5 in Goldwood room 24. In preliminary
v2 traces, its controlled death spans 233 VI ticks versus 231-235 in the original
reference, with about 152.08 versus 152.01 units peak rise. Tawfret peak rise is
about 231.06 versus 230.95. Live trajectories are close in elapsed guest time,
but not bit-identical: adaptive steering, fractional steps, collision sampling,
original load and spawn phase can differ. This deliberately does not recreate
variable hardware slowdown.

A ground-only paired replay records zero flight-time-step events. Actual ground
trajectories are not a bit-exact parity proof because the real-time replay's
player/input timing differs; adapter isolation tests provide the direct check.
No claim is made for all enemy types, physical hardware or the reporter's machine.

The stopped death captures exposed missing static SDK formatting metadata.
See [the separate record](sdk-printf-field-metadata.md). Preserve their failure
evidence; the new generation adds only function metadata and validates all
loaded bytes unchanged. Final gameplay reruns are pending.

Final replay preparation initially used an invalid video configuration: the
harness stored 30 in the remembered custom-FPS field, which the existing parser
requires to remain 60-1000 even in Original mode. Startup correctly rejected
that file before loading a scene. The harness now retains 120 in that field
while explicitly selecting mode=original, matching the prior valid fixtures
and ordinary launcher serializer. The rejected capture is retained; no game
parser rule or frame-rate behavior was changed to admit it.

### Final local qualification

The prepared final runtime builds successfully. Twelve copied-profile native
replays exit cleanly and reach their requested scenes: Tawfret flight and death
at Original/60/120, Goldwood flight at Original/120 and death at Original/60/120,
plus a ground-only control at 120. Every flying encounter exercises the actual
elapsed-time adapter and records finite positions/velocities. The ground-only
control records no flight adapter events. All runs render frames.

The ordinary hosted launcher also starts Play, renders and closes cleanly with
the exact staged executable. The original ROM and source save hashes remain
unchanged. Windows 117/117 and Linux 110/110 enabled CTests pass; the existing
Linux G2 trap-runtime quarantine remains excluded. Generation contract checks,
actual formatter execution, source validation and repository hygiene also pass.

The new preview is local, with copied save/bindings, 120 FPS and the FPS overlay
hidden. Owner visual gameplay review is still required; no release, GitHub
comment or issue closure is claimed. Controlled death tests set health to zero
at spawn; they do not replace a natural-combat review.

The final Goldwood Original/120 comparison shares 2,691 identical live
position/velocity states across three actors. Goldwood controlled falling spans
232-233 VI ticks versus 231-235 in the original-ROM reference; peak rise is
152.082-152.101 versus 152.009 units. Tawfret falling peak rise stays within
0.001 units across output settings, near 231.060 versus 230.949 in the reference.
Other live trajectories are not bit-identical when elapsed update spans and
AI/input phase differ. These captures validate selected output settings and
guest motion; physical-display smoothness still requires owner visual review.

Private evidence IDs: flying-timing-fix-20261027/native-v4-results.json,
final-motion-qualification.json, output-mode-motion-comparison.json,
review-ready.json and span-preparation-qualification.json. Earlier failed builds
and runs remain preserved. The exact stable-reference and enemy-class limits
above still apply; this is not bit-exact emulation of variable hardware slowdown.

## New Original-mode requirement

After the local candidate handoff, the owner required Original FPS to match
original timing 1:1, with timing improvements confined to higher output modes.
The stable three-VI reference does not establish that property. The pre-existing
native Play clock also differs from the measured Mupen64Plus reference, so merely bypassing the
flight adapter in Original is not a complete fix. See
[the Original-mode investigation](original-mode-simulation-parity.md).
Earlier finite candidate checks remain valid within their recorded scope.

October 27 follow-up: the fresh instruction-timed Original/120 comparison
matches all 4,939 tracked motion states and their relative VI timing. That
reference path remains approximately 5-8% slower in matched VI spans than
Mupen64Plus. Neither is established as exact physical N64 timing. The owner
has an N64/NA cartridge; hardware measurement and the exact Original-mode
requirement remain open. See the linked Original-mode record for corrected
interpretation, primary sources and finite evidence. No additional runtime
change, publication or issue closure followed this comparison.

The owner subsequently supplied a confirmed original N64 image capture.
A matched Goldwood room-236 local route activates 14 flying actors and shows
about 14.8 emulator game updates per 60 VIs under load. This further limits the
earlier constant-three-VI candidate: it cannot certify original variable timing.
The diagnostic reference-clock Original/120 pair matches 6,825 common states;
clock differences and transition audio underruns still prevent a default-policy
remedy. See the Original-mode record and its ordinary-Play evidence.

## October 28 workload-clock finding

The follow-up isolates a second limitation in the diagnostic Original clock:
short fixed SP/DP deadlines omit most original graphics/audio device work.
Original-ROM traces actually yield and resume graphics around audio. Controlled
device-only and matched-boot interventions demonstrate its effect on update
cadence. This does not promote the current stable flight adapter or certify
hardware parity. See the [research evidence](../../evidence/original-timing-research-20261028.json)
and [full Original issue](original-mode-simulation-parity.md).


## Regional architecture policy (2026-11-01)

The optional three-VI compatibility reference is now explicitly scoped to the
US revision used by the retained Goldwood/Tawfret comparisons. PAL and Japan
execute their original movement path. Shared code and equal retention constants
do not qualify a regional cadence. New regional reference encounters are required
before enabling this optional correction there; this does not block executing
the original regional game. See [regional support](regional-rom-support.md).
