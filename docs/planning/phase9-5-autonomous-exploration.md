# Phase 9.5: Autonomous gameplay exploration

Status: acceptance requirements remain open. Bounded capabilities are implemented;
see the [runtime summary](../development/runtime-research.md) for their limits.

## Purpose and sequencing

Remove the maintainer as the routine gameplay driver. Build a game-specific bot
that navigates, fights, explores alternate branches, recovers from failure, and
generates reproducible native/oracle tests. Repeating a fixed recording is not
completion of this phase. No LLM inference is required during gameplay.

This workstream supports the campaign slice while Phase 9 remains open.
The decimal label is an enabling addition, not a dependency on Phase 9 completion.
It supports Phase 9 acceptance and subsequent Phase 10/11 expansion without
weakening their gates. The maintainer need not demonstrate every level or path;
missing map/mechanic knowledge is an engineering task, not a routine request for
another manual playthrough.

## Foundation and remaining acceptance

The source includes controller-input recording/playback, native replay,
determinism comparison, state observation, checkpoint tools, generated navigation,
and bounded failure triage. Earlier scenario results demonstrate parts of the
loop, not completion of every milestone below.

Still establish general varied-path exploration, combined recovery coverage,
frontier scheduling, a fully qualified failure-reduction/sanitizer workflow,
and native snapshot equivalence. Use the [runtime summary](../development/runtime-research.md)
and [automation plan](autonomous-full-scope-execution.md) for current boundaries.

## Architecture

| Component | Responsibility |
|---|---|
| Oracle adapter | Read BizHawk state, apply controller input at defined input polls, advance bounded execution, save/restore reference checkpoints. |
| World model | Decode player position/facing, camera/control mode, health/ammo, actor identity/lifecycle, enemies, pickups, exits, and progression. Validate each field and reject stale observations. |
| Navigation model | Extract collision/room data and connections where feasible; build a graph with hazards, jumps, one-way links, doors, and prerequisites. Use measured exploration or engineering-authored waypoints when decoding is incomplete. |
| Action controller | Closed-loop move-to, aim, fire, jump, interact, collect, pause, and retry behaviors. Calibrate camera-relative movement and reticle response. Use graph search and explicit state machines/behavior trees. |
| Exploration manager | Choose uncovered reachable objectives, preserve checkpoints and route histories, explore alternate branches, detect stuck/dead states, bound retries. |
| Verification worker | Replay generated routes on native, compare defined reference checkpoints, classify failures, and retain regression artifacts. |

Initial implementation choice: a small Lua emulator adapter and testable Python
planner. Define a versioned bounded protocol with sequence numbers, acknowledgments,
timeouts, and neutral input on planner failure. Benchmark the transport before
choosing files, pipes, or sockets; no external service dependency is required.

Level knowledge is not already available to the bot. Inventory and decode game
data first. Track unknown connections explicitly. Special traversal, bosses, and
progression gates may need dedicated behaviors. Do not promise discovery of every
hidden path without an independently established coverage denominator.

## Correctness and replay contract

- Observe memory, but progress through ordinary controller input. Acceptance
  routes must not teleport, grant health/ammo, or write progression/physics.
  Separate fault-injection experiments must be labeled and excluded.
- Pin ROM, emulator/core/settings, native binary/source, initial saves/accessories,
  planner/map version, and exploration seed. Preserve concrete input-poll samples
  as well as semantic actions and objective outcomes.
- Finish the pending input/update-boundary validation before claiming parity.
  Independent bot development need not wait for every existing gameplay defect.
- Strict native/reference replay uses the same declared input schedule. If load
  cadence makes a recording nonportable, report scheduling divergence. Running
  an independently adapting bot on native is a separate robustness test, not
  identical-input differential evidence.
- Compare validated canonical fields at defined completed-update boundaries.
  Do not skip mismatches, arbitrarily offset traces, or mask RNG differences.
  Partial-update snapshots remain diagnostic evidence.
- Classify reference bot failure, harness failure, input timing mismatch, native
  crash, native state divergence, and incomplete evidence separately. A timeout
  or successful process exit alone never proves objective completion.

## Checkpoints, supervision, and artifacts

Reference checkpoints include emulator state, planner state, graph/frontier
version, random generator state, held inputs, counters, and pending actions.
Prove restore-and-replay equivalence before using them. Isolate SaveRAM/accessory
disk state and output paths per worker.

Preserve each segment's parent and exact boot-prefix lineage. BizHawk snapshots
cannot load into native. Initially native verification replays from the pinned
initial state, accelerated where supported. Report prefix cost honestly.
Native snapshots require guest execution, scheduler/queues, timers, runtime and
device side state; RDRAM alone is insufficient.

Each run bundle contains a manifest, explicit objective/completion predicate,
initial-state digests, concrete inputs, actions/observations, checkpoint lineage,
state traces, coverage, logs, exit classification, and first-failure details.
Persist incrementally so a terminal/planner/emulator crash retains evidence.
Keep ROM-derived memory/save bodies private under repository policy; publish
summaries and digests only.

A supervisor owns only its launched processes and supplies heartbeat/watchdog,
stop, time/disk/retry limits, and isolated workers. User pause stops new work and
shuts down owned jobs safely. Never terminate unrelated sessions.

## Milestones and acceptance

### A: Reliable autonomous control

1. Define observation/action schemas and field provenance. Test stale/invalid
   state, protocol failures, action timing, neutral-on-stop, and save isolation.
2. Launch a fresh reference game, navigate menus, and reach an explicit Goldwood
   gameplay predicate through state-aware actions rather than fixed wait lengths.
3. Calibrate movement/aim and prove reference checkpoint restore equivalence.

Gate: ten repeat runs reach the declared gameplay state without human controller
input. Identical continuations from restored checkpoints reproduce approved state.

### B: Goldwood proof of capability (first useful deliverable)

1. Map a bounded area containing an encounter and two reachable branches or
   distinct destinations. Name them and their completion predicates before tests.
2. Navigate, fight using normal health/ammo, verify encounter completion, collect
   a reachable pickup, and reach the destination.
3. Select the alternate destination from a checkpoint. Exercise natural death
   and retry without operator assistance. Preserve failed attempts too.

Gate: ten seeded exploration jobs complete their declared objectives within
predeclared retry budgets, with zero human intervention during runs. Cover both
destinations and death/retry. Freeze one generated successful route and reproduce
it three times in BizHawk with matching approved checkpoints. Automatically
generate a native replay and differential report. A native divergence remains a
native acceptance blocker, not a concealed pass or a reference-bot failure.

This must create new gameplay, not wrap the existing manual recording. Report
elapsed time, retries, intervention count, coverage, and native prefix cost.

### C: Growing frontier and branching coverage

Extend through the selected Phase 9 slice: transitions, cutscenes, save/relaunch,
death/retry, pause, controller disconnect, and active overlay reloads. Maintain
known reachable/covered/blocked/unknown branches with evidence and prerequisites.
Account for character/inventory variants; room visitation is not progression
coverage. Generate varied paths, engagement orders, and weapon choices.

Gate: every declared slice objective/branch has a generated reproducible route
or an explicit blocker; slice acceptance still requires all blockers resolved.
Expand this mechanism with Phase 10 campaign segments and Phase 11 optional
content, authoring special mechanics as necessary.

### D: Unattended regression factory

Archive failures automatically, locate the earliest reproducible failing prefix,
and perform bounded reduction preserving the same failure signature and valid
lineage. Do not assume failures are monotonic for binary search. Preserve the
original inputs regardless of minimization. Rerun compatible native failures
under a pinned ASan build; an ASan symptom alone is not proof of root cause.

Add checkpoint perturbations (stick noise, combat choices, pause/disconnect,
death/retry), preserving seeds and resulting inputs. Run resource-limited batches
with restart support and coverage/failure reports. Measure safe concurrency;
BizHawk and native headless workers need not have equal performance.

Implementation checkpoint, 2026-09-24: the native selected-input regression
bundle now invokes `scripts.phase95_native_failure_triage` when its native replay
exits nonzero. Triage checks input/save, executable, and ROM pins; retains the
original route, logs, and retrace stream; and records bounded retrace-prefix
probes with exact exit-code/ASan-class signatures. The last flushed retrace is
only a search hint. A matching earlier probe is not called the globally earliest
failure unless all preceding targets were tested. This is a model-free,
no-API-billing diagnostic, not the D gate: a ROM-backed seeded fault, restartable
batch reduction, automatic pinned ASan rerun, and perturbation coverage remain
unverified. Direct poll-stop and live-manual-launch failures are not yet wired
into this triage path.

Gate: a seeded test fault produces a recoverable artifact and reproducible report;
an interrupted batch resumes without losing completed results. Run Phase 9's
100 consecutive deterministic complete slice runs with identical approved
checkpoints and no crashes. Report varied exploration separately: neither count
substitutes for the other, and startup repeats do not close this gate.

### E: Native frontier resume optimization

Inventory all native execution state before designing snapshots. Require
uninterrupted-versus-restored equivalence across combat, loading, saving, and
retry, plus incompatible-build rejection. Until verified, oracle checkpoint
exploration and native boot-prefix replay remain supported. This optimization
does not block milestone B; its absence remains visible in performance reports.

## Next implementation order

### Immediate priority: finish the bounded Goldwood proof

Existing startup, local navigation, and oracle checkpoint diagnostics are a
foundation, not an autonomous-player acceptance pass. Continue in this order:

1. Finish milestone A: validate control/aim observations, input isolation and
   watchdog behavior, then demonstrate ten fresh autonomous gameplay startups.
2. Define the first Goldwood scenario before running it: one encounter, one
   pickup, two named reachable destinations, and explicit completion predicates.
   Decode missing health/ammo, hostility, dialogue/progression, and map fields;
   do not equate proximity to an NPC with a completed interaction.
3. Implement closed-loop navigation, aiming/combat, interaction, and natural
   death/retry. Preserve a checkpoint and route lineage at each verified frontier.
4. Run milestone B's ten seeded jobs and three frozen-route oracle repeats,
   then automatically replay the generated inputs on native and report the first
   validated divergence, or explicitly report unresolved comparison boundaries.

The first useful handoff is a command that independently starts or resumes the
scenario, chooses a declared destination, plays it, and leaves a reproducible
result bundle without human steering. Reaching a landmark or replaying the old
manual route is not that handoff. Do not expand to whole-game exploration before
this bounded loop works; keep unknown paths and unsupported mechanics visible.

### Remaining workstream order

1. Inventory observation fields and Goldwood map data; define A/B scenario
   manifests, progress predicates, and retry/resource budgets.
2. Implement supervised adapter and movement/aim primitives with synthetic-state
   tests, then bounded ROM-backed calibration.
3. Implement reference checkpoints and Goldwood planner; demonstrate milestone B.
4. Integrate generated routes with native verification; finish boundary validation
   before approving parity.
5. Expand frontier and regression factory, then optimize native resume.

Stop a job on stale state, incompatible checkpoint, exhausted budget, missing
heartbeat, or user pause. Preserve evidence and identify the specific blocker.
Missing game knowledge calls for engineering, not routine human play requests.
This planning document alone does not start implementation or unattended batches.

## Deliverables

- Versioned adapter, schemas, unit/integration tests, and supervised runner.
- Goldwood map/objective manifest and closed-loop navigation/combat controller.
- Persistent checkpoint/frontier store and branch coverage scheduler.
- Generated replay bundles, native comparison integration, and failure triage.
- Coverage dashboard with milestone evidence, limitations, and explicit unknowns.

Full-game acceptance remains governed by the [project roadmap](JFG_RECOMP_MASTER_PLAN.md).
