# Phase 9.5 implementation evidence

Updated 2026-09-24. All gates in the [plan](phase9-5-autonomous-exploration.md)
remain open. The user has now requested implementation through completion.

## Japanese full-game TAS ingestion, 2026-09-23

The user's legally dumped Japanese ROM was byte-order normalized in ignored
private storage and matched the movie's pinned SHA-1. The user confirmed that
the opening of the movie synchronizes in a visible BizHawk 2.9.1 playback;
that observation is **not** a verification of all 638,477 frames. The visible
viewer is left under user control.

`phase95_tas_index.py` now validates the direct, two-controller BK2 archive and
streams its entire input log into compact 600-frame windows without importing
the ROM or movie into Git. The pinned private index reports exactly 638,477
frames, 1,065 windows, a power event at frame 1,362, 350,422 active P1 frames,
and 6,523 active P2 frames. It preserves source digests and controller/plugin
configuration as provenance; input activity alone does not establish a level,
pickup, boss, or branch. `phase95_frontier_graph.py` adds a persistent,
deterministic frontier with independent Japanese TAS, US oracle, and US native
coverage lanes. A Japanese movie edge cannot silently count as US parity.
Four coarse capture-priority clusters (70,800--81,000; 367,800--433,200;
464,400--479,400; 501,000--517,200) contain about 77% of P2-active frames.
These are input-density hints, not continuous gameplay or verified Floyd events.

The bounded `phase95_tas_capture.py`/Lua worker captures raw, explicitly
**unverified Japanese** RAM probes from a fresh emulator copy, and can resume
from a pinned previous segment's savestate. `phase95_tas_probe_report.py`
summarizes contiguous raw probe changes as candidate milestones, not semantic
claims. Its report is private. The initial 0--6,000-frame worker stalled on a
frame-zero full-RDRAM dump; only that owned worker was stopped, partial logs
were preserved, and the separate visible viewer remained running. A smaller
raw-probe/screenshot capture and short live restore then succeeded; full-movie
capture and semantic validation are still required for a useful state atlas.
This work starts Phase 9.5 C; it does
not close its branch-exploration gate or prove autonomous whole-game play.

The new synthetic tests and existing focused Phase 9.5 tests total 162 passing
tests at this checkpoint. Longer capture and full-movie continuation remain
pending.

Follow-up: a screenshot-plus-raw-probe capture of frames 0--100 completed
with a 1.47 MiB continuation state, 101 contiguous trace rows and exit code 0.
An independent worker resumed from that sealed state for frames 101--200,
remained in movie playback, recorded exactly 100 further rows, and exited 0.
The raw-change reporter accepted both contiguous segments. This proves a
short Japanese TAS restore/continuation, not full-movie sync or validated
Japanese state fields. A longer 0--6,000 opening capture then completed in an
isolated worker with 6,001 contiguous PLAY rows, seven screenshots, a 2.82 MiB
continuation state and exit code 0; a second continuation for frames
6,001--6,100 also passed. The frame-6,000 screenshot shows active third-person
gameplay with HUD and Floyd. At the same frame the raw bytes at the known US
front-mode and level addresses read zero, so those addresses **must not** be
treated as Japanese gameplay fields. An independently validated Japanese RAM
map, whole-movie capture and branch exploration remain open.

`phase95_tas_state_extract.py` can now reconstruct the full 8 MiB Japanese
RDRAM from a pinned BizHawk `.State` offline. The state archive's Zstandard
`Core.bin` has a checked `M64+SAVE` layout; conversion restores N64 byte order
and cross-checks four sampled RAM values at the same movie frame before
writing the private extract. The frame-6,000 extract passed these checks with
RDRAM SHA-256
`c54195418dab9b6d480c308d37dd6d9aad0197c7903617e78a08169468dcfc1b`.
This provides a cheap full-state source for Japanese layout discovery, not a
validated level/player map or US parity fixture.

Follow-up actor-layout validation: an 8 MiB Japanese decoder now reads the
actor table/count at physical offsets 0xF2BB4/0xF2BB8 and bounds parsing to
the declared count. It decoded 51 actors at frames 6,000 and 6,100, 23 at
19,999, and 19 cutscene actors at 39,999; all current entries had bounded
headers, printable names, and finite positions. A `playerBoy` table entry and
candidate player pointer at 0xF8824 agreed in the first three gameplay
snapshots; frame 39,999 has no current `playerBoy`, so no player is claimed.
Valid-looking stale actor entries beyond the declared count demonstrate why
string search alone would be unsafe. A later gameplay snapshot at frame 59,999
had 67 valid actors and an on-screen `playerBoy`, but the candidate pointer
field contained `8`; the observer retained the actors and marked player
identity unresolved instead of rejecting the state. The first three gameplay
snapshots therefore support the pointer only conditionally.

Independent resident Japanese getter/code signatures, checked in each state,
identify front-mode byte 0xA50C0, signed level word 0xFB024, and RNG seed
0xA32E4. The six sampled states at frames 6,000, 6,100, 19,999, 39,999,
40,099, and 59,999 decode levels 47, 47, 237, 379, 379, and 121.
This is a bounded source-ROM state atlas, not US equivalence. Health, ammo,
progression and controller behavior remain unavailable.

`phase95_tas_route_atlas.py` now turns the validated private state index into
an idempotent endpoint inventory of JP level/mode/RNG, actors, and player
resolution. At four completed batch endpoints (through frame 79,999), it
records level IDs 237, 379, 121, and 195 and three **endpoint-bracketed**
changes. It explicitly leaves exact transition frames, intermediate levels,
objective completion, graph-edge coverage and full-game acceptance unknown.
The batch and atlas remain incomplete while the remaining movie is running.
Once the endpoint batch is sealed, the atlas can also ingest the separate
5,000-frame sample grid as it progresses. It checks the grid plan, batch pin,
sample/capture/extraction lineage, and each RAM digest before merging samples;
the output records whether the grid is partial. Undecodable transitional RAM
remains in the inventory with its sealed provenance but no level claim, and
no transition is inferred across it. Finer sample spacing narrows possible
transition brackets but does not establish an exact transition, objective
completion, graph-edge coverage, US/native parity, or whole-game acceptance.

The private follow-through completed overnight: the batch reports all 32
segments through movie frame 638,476, the offline state index has 32 sealed
endpoints, and the separate 5,000-frame grid has all 96 planned samples. The
reconciled atlas has 128 sampled states and 115 endpoint-bracketed level-change
candidates across 108 observed level IDs. Its sealed follow-through status
explicitly says `full_game_acceptance: false`. The final frame screenshot is
not independent proof of movie synchronization or campaign completion; no JP
edge is promoted into the US oracle lane from this capture alone.

`phase95_tas_followthrough.py` is a bounded private post-capture worker. It
waits for the existing batch to seal, checks every indexed state, then advances
the 5,000-frame grid one sealed job at a time while refreshing the partial
atlas. It has wall-time, job-count, per-job timeout, and disk-headroom limits;
it does not drive the visible viewer or imply that the Japanese route covers
unvisited branches. Synthetic tests pass, but the full follow-through has not
yet completed.

`phase95_frontier_job.py` is a separate US-oracle branch-job integration: it
selects an uncovered graph *proximity* objective, requires exact checkpoint
and worker identity pins, and only records that objective covered after two
independent matching bounded navigation runs. It never counts proximity to an
exit as a crossed transition. The initial live preflight was blocked by a
Windows config-file newline mismatch; the follow-up below resolved that
identity calculation without weakening the checkpoint pin.

Live follow-up: the worker's Windows-normalized config hash was matched to an
existing sealed level-47 US checkpoint. One bounded waypoint probe failed its
three-step budget and was retained as blocked. A second, explicitly declared
waypoint-0055 proximity objective completed independently in two isolated
BizHawk workers using a selected 12-frame movement action. Both ended at frame
18,629 / poll 7,274 with identical player pointer and full-RDRAM SHA-256
`4556265c91c5c02e4cfeef037737758de6d5814c40482a0c2d6c34d3c03b5c76`.
The private `phase95-frontier-job-20260923a/run-002` graph marks only that
proximity edge covered. This proves a narrow live checkpoint-to-planner loop,
not an exit crossing, alternate destination, encounter, or milestone B pass.

The pinned full-movie batch was started in a separate hidden worker after the
0--6,000 smoke. It divides the 638,477-frame source into 32 bounded segments,
revalidates each source and predecessor-state hash, and preserves failed
attempts. A running batch is not a pass; its completion and restart behavior
must be checked against its private ledger before promoting any movie coverage.
The offline state-index pass is idempotent and reports incomplete while the
capture batch is active; its first two sealed segments yielded validated
full-memory extracts at frames 19,999 and 39,999.
`phase95_tas_sample.py` also passed a live bounded probe from the sealed
39,999 state to arbitrary target frame 40,099, extracting a full checked
RDRAM image without restarting the movie from power-on. This is the mechanism
for refining transition boundaries once the Japanese level field is validated.

## US native selected-input completion contract, 2026-09-23

Review of the south-route differential found that the native runner stops at
26,441 VI retraces because that number was copied from the oracle's frame
count. At that stop it had consumed only 8,883 of the route's 10,881 selected
controller polls. Thus the zero-kill endpoint is an observed early-stop state,
not a complete-input-route comparison, and no aligned first gameplay
divergence has been proved. The replay-by-poll implementation also held the
last recorded sample indefinitely after input EOF, whereas the oracle uses
neutral input. A focused neutral-EOF fix and explicit poll-completion report
now pass the public C++ replay test, focused Python tests, and private Release
native build. A new ROM-backed rerun reached the old 26,441-retrace stop in
30.2 seconds and explicitly reported `input_route_complete: false`, 8,883
observed polls, and 1,998 missing polls. Its state hash matched the previous
early-stop result, as expected because EOF was not reached. The next parity
gate remains a truly shared stop/observation
boundary plus validated initial save/Pak equivalence; merely adding retraces
cannot establish parity.

An opt-in native `--probe-polls` stop now passes a one-poll private smoke and
strict parent validation. It stops after the Nth controller-read HLE is
recorded, before the guest consumes that response. The south route's new
`--stop-by-polls` run consumed all 10,881 selected polls, exited 0 after
25,550 VI retraces / 127.3 seconds, and explicitly marked input complete.
Native weapon counters still showed 15 shots, zero hits and zero kills; the
oracle's completed route had three kills. This is a stronger bounded
diagnostic than the earlier truncated 8,883-poll run, but it is not an aligned
gameplay checkpoint: the exact last-response update, initial save/Pak
equivalence, and native/oracle execution boundaries remain unverified. The
poll-stop mode also has a different fast-render scheduling rule, so its VI
count must not be equated with the earlier retrace-stop run.
A completed 10,881-poll comparison artifact reports that all selected input
samples match. Its clocks differ from poll zero (oracle frame 40 versus native
VI 0), and the first observed mode/RNG difference is at poll 16 (oracle frame
72 versus native VI 35). This is an unaligned observation, not proof of an
aligned gameplay divergence or parity.

## Durable autonomy bootstrap, 2026-09-23

`scripts/autonomy/job_store.py` provides a versioned SQLite ledger for stable
pinned job IDs, prerequisite-gated leases, transactional per-resource writer
locks, heartbeat/expiry/retry, attempt history, and hash-checked result
sealing. Five synthetic tests pass. This does not yet run a coding agent,
schedule game objectives, restart at boot, enforce spend/resource limits, or
pass the supervisor acceptance plan; it is the recoverable state foundation.

## Observation inventory: first implementation

`scripts/phase95_observation.py` reads the US-retail big-endian 4 MiB RDRAM
layout without modifying game state. It decodes the actor table, names, positions,
yaw, front mode, and RNG. A player pointer supplied by the controlPlayer hook must
still belong to the current actor table. The decoder rejects unsupported pointer
segments, invalid bounds/alignment/counts, duplicate aliased actors, nonfinite
positions, and unknown profiles. A session freshness guard rejects reordered or
repeated observations. Health, ammo, camera, level identity, progression,
collision, and hostility are explicitly unavailable, not guessed.

Provenance: existing oracle actor observations use table/count globals at
0x800F2CA4/0x800F2CA8, controlPlayer at 0x80032A48, transform coordinates at
actor offsets 0x0C/0x10/0x14, and header pointer at 0x40. Local US symbol data
corroborates the table/count and control function. The local upstream structure
declarations are incomplete and include inconsistent inherited fields; they must
not be treated as verified navigation or player-health layouts.

Verification:

- `python -m unittest tests.test_phase95_observation`: 10 passing tests.
- `python -m scripts.phase95_observation tools/private/phase9-cold-boot-parity-20260905/oracle/checkpoint-018500.rdram --player 0x801BD150 --sequence 18500`:
  successfully decoded the preserved oracle gameplay checkpoint, with 24 actors
  and front mode 16. Player position/yaw agree with the existing checkpoint TSV.
  Named exit, bridge, hint, and health-pickup actors are available as navigation
  candidates. Their presence does not prove reachability, pickup, or interaction.

The raw observation output and RDRAM are private game-derived data. This is
offline evidence only: no new live autonomous run has passed yet. The profile
label selects a layout; it is not ROM identity verification. The future launcher
must pin and validate the actual ROM/core/build before allowing actions.

## Live bridge: first verified exchange

`scripts/phase95_bridge.py` and `scripts/phase95_bizhawk_bridge.lua` now provide
a supervised observation/action exchange. The host verifies the requested ROM
digest, creates a unique private emulator copy excluding saved-state/SaveRAM
directories, checks data paths for absolute/parent escapes, and records the ROM,
executable, configuration, and script digests. The adapter publishes a complete
RDRAM observation before atomically publishing its sequence/session metadata.
Commands are bounded to 120 emulator frames and checked for sequence/session
and controller ranges. Inputs are neutral between requests. The core pauses
while awaiting the host; input-poll samples are incrementally logged separately
from emulator frame numbers. Host timeouts and owned-process cleanup are present.

Two live probes completed in isolated private workers. The reproducible second
probe (`tools/private/phase95-live-probe-20260906b/probe.json`) observed frame 1,
requested 60 neutral frames, and observed frame 61 with 11 input polls. The
bridge result records `stopped`, and the owned emulator exited. Command and
observation journals survive. This validates basic transport and bounded stepping,
not autonomous gameplay, restore equivalence, watchdog fault tests, or parity.
Five protocol tests and the ten observation tests pass.

Reproduce using `python -m scripts.phase95_bridge OUTPUT --emulator EMUHAWK
--rom ROM --rom-sha256 EXPECTED_SHA256`. OUTPUT must not exist. The command is a
neutral transport probe, not a bot run. The host planner and live decoder are
not yet integrated; memory is currently transferred as a 4 MiB dump per action,
so transport cost needs measurement before short-step combat control.

Original US code for `levelGetNumber` reads a signed word at 0x800FB114;
`frontGetMode` confirms the byte at 0x800A51B0. These are next observation inputs
to verify against runtime state. Menu substate and name-entry cursor still need
decoding before replacing the fixed cold-boot recording with state-aware actions.

## Next concrete work

### Level-47 surface route and jump mapping, 2026-09-22

The surface follower can now preserve its proposed route across sealed checkpoint
chunks, identify the same MrHints2 actor, and reject a waypoint reached on the
wrong vertical layer. This matters because an earlier proximity-only trial
appeared to clear a waypoint while the player remained on a lower surface.
These route diagnostics do not imply that the NPC was reached or interacted with.

An isolated button sweep at the level-47 frontier established that the active
expert control mapping uses C-right (mask `0x0008`) to jump; A did not rise in
that test. The navigator now reads the active, validated control mapping instead
of hardcoding A. Its original long jump still overshot a nearby ledge, so a
short jump with neutral airborne release was added. The selected short-jump
continuation at waypoint 14 reproduced its trial's complete RDRAM hash and
landed at player Y 20.64 versus target Y 21.0. The resumed autonomous route
then passed waypoints 15 through 57, each with the layer guard and sealed
checkpoint. At waypoint 58, movement stopped near the roaming NPC. The
separate `phase95-south-hint-dialogue-20260922a` probe from waypoint 57
observed MrHints2 become the game's selected speaker and then return to idle.
The post-dialogue movement probe moved 137.55 units under ordinary forward
input and matched all six restored continuation steps. Resuming the route
then cleared waypoints 58 through 60. The original final-coordinate check
correctly rejected arrival because the live NPC was still 38.11 units away.

The navigator now tracks the actor's current position in each candidate trial,
not just its position when the route was proposed. A bounded pursuit from the
sealed final-coordinate checkpoint reached 28.42 units from the same live
MrHints2 actor in `phase95-south-live-actor-chase-20260922b`; selected actions
again reproduced their trial RDRAM. `surface-result.json` reports route
completion and proximity but explicitly leaves interaction unverified; the
dialogue proof is in the separate probe lineage. No enemy encounter or pickup
was verified. The route still lacks dynamic collision/door semantics and is
not a Phase 9.5 acceptance run.

The follower now handles a selected-speaker MrHints2 conversation when it
stalls on this approach and retries from the resulting state. The one-invocation
repeat `phase95-south-auto-dialogue-20260922b` started at sealed waypoint 57,
verified an active-to-idle conversation, completed waypoints 58--60, and reached
27.40 units from the live actor. Its final result links the nested dialogue
artifact and checkpoint, and reports both actor proximity and interaction
verified. The emulator stopped cleanly. This is a checkpoint-resumed local
route, not a fresh-boot, encounter, pickup, or ten-seed scenario pass.

`python -m unittest discover -s tests -p 'test_phase95_*.py' -q` passes all
118 focused tests at this point in the implementation history. The NPC route
is a reusable autonomous path, not a substitute for the scenario requirements.

### One-command south Goldwood slice, 2026-09-22

The original-US weapon statistics reader validates the resident instruction
sites and exposes pistol shots, hits, and kills. An isolated combat candidate
sweep restores a sealed checkpoint for every ordinary-controller trial, then
replays the selected trial and requires the weapon counters and observed actor
lifecycle to agree. Three sequential Galaxian4 kills were verified this way;
the final kill changed the observed Ftechdoor actor height from 0 to 78. The
combat objective did not credit proximity or mere firing as a kill.

The exit follower now distinguishes the level-199 setup/intermediate from the
playable level-21 arrival. A pre-clear crossing attempt failed within its
declared budget, which is retained as negative evidence. After the three kills
and door opening, the crossing passed: level 199 was observed, followed by
three stable playerBoy/mode-16 observations at level 21. A bounded terrain
route to a live HealthPowerup then verified the selected actor disappeared and
health increased by exactly 0x100, from 7654 to 7910 in raw units.

`python -m scripts.phase95_goldwood_scenario` composes the previously verified
MrHints2 dialogue/route, three-kill encounter, door, exit, transition, and
pickup in one supervised BizHawk worker from sealed waypoint 57. Private run
`tools/private/phase95-goldwood-south-scenario-20260922a` passed all seven
stages without human steering during the run, ended in level 21 at frame
26,441, took 909.375 wall seconds, and stopped its owned emulator cleanly.
The result bundle contains the objective, incremental stage ledger, per-stage
artifacts/checkpoints and final RDRAM SHA-256
`a50a11057b010d06a445cafc0cfa0fa5780ab5f206c6a8a1fe79d66de395b335`.
The focused Phase 9.5 suite now passes 130 tests.

This is a checkpoint-resumed **single south route**, not milestone B acceptance:
the alternate named destination and natural death/retry are not yet integrated
into the same scenario, and there are no ten seeded encounter jobs. At the time
of this one-command run there were also no frozen repeats or native report; the
follow-up evidence below addresses those separately. The one-command artifact
itself reports `acceptance: false` and `native_comparison: not_run` accordingly.
Milestones A, C, D and E also remain open under their respective gates.

### Selected-input regression and alternate branch diagnostics, 2026-09-22

`phase95_export_inputs.py` reconstructs the selected controller-poll lineage
through imported and local oracle checkpoints, discarding speculative trial
branches. It exported the completed south route as 10,881 input-v2 polls from
cold boot. Its manifest pins the input digest and makes the initial-save and
native-parity limitations explicit. The fresh `controller-poll` mode in the
BizHawk oracle independently replayed that exported input three times. The
frozen-repeat audit compares full 4 MiB RDRAM SHA-256 at the declared dialogue,
three-kill, level-21 arrival and final-pickup checkpoints; all three repeats
match all four checkpoints and the original final hash. The private audit is
`phase95-south-selected-input-20260922c/frozen-repeat-audit.json`.

The same input was generated for the native replay-by-poll runner and reached
its bounded 26,441-retrace target. The generated native differential report
`phase95-south-selected-input-20260922c/native-report-v2.json` records a
validated endpoint mismatch: native sampled 8,883 controller polls and zero
weapon kills, versus the oracle's 10,881 polls and three kills. It explicitly
does **not** claim a first validated gameplay-divergence retrace or native
parity. Oracle emulator frames and native VI receives are different observation
boundaries, and the initial-save equivalence is not yet verified. Native
acceptance remains blocked by this unresolved comparison and route mismatch.

The new `phase95_regression_bundle.py` combines selected-input export, independent
oracle repeats, full-RDRAM repeat audit, native replay and the differential
report under one supervised command. Its complete three-repeat run
`phase95-south-regression-full-20260922a` passed all frozen oracle checkpoints
and reproduced the native mismatch; `bundle-result.json` reports
`native_parity_verified: false`. The south scenario CLI also has an opt-in
`--regression-bundle` handoff after its worker stops; the handoff itself is not
yet separately exercised by a fresh end-to-end scenario invocation. This
closes artifact assembly, not the native code divergence.

The level-47 east branch to level 48 is being reconstructed from ordinary
input. An attempt from the shared level-47 checkpoint reached waypoint 44,
then the vertical guard correctly rejected a lower-surface waypoint while the
player remained on an overlapping upper deck. Terrain sampling at that point
showed both upper and lower triangles; the route search now rejects a walking
drop onto the lower one while an upper continuation remains. A checkpointed
continuation traversed the revised upper route through waypoint 19; an explicit
ground approach then reached exit radius, and a sealed follow-up crossed into
level 48 with three stable `playerBoy` observations. These are separate
diagnostics, not yet a one-command alternate-branch acceptance run.

Two bounded idle-damage probes from pre-combat and one-kill level-47 frontiers
did not produce a natural death: the first stayed at full health for 2,400
frames, and the second took only a small initial hit before health stopped
changing. They are retained as negative evidence, not death/retry coverage.

### Ten fresh autonomous Goldwood startups, 2026-09-22

`scripts/phase95_startup_batch.py` supervises independent fresh-save startup
jobs and checks the state-aware Goldwood gameplay endpoint, movement probe,
six-step exact checkpoint continuation, and clean stop. Its one-job smoke passed.
The ten-job `phase95-startup-batch-10-20260922a` completed in 968.094 seconds
with 10/10 passes and no human controller input. The separate
`batch-audit.json` re-read all job artifacts: ten distinct worker sessions,
one ROM/emulator/config/Lua/runtime pin set, one Goldwood-entry complete-RDRAM
hash (`45d9ba5a...3211`), and one post-restore hash (`849cffdb...8efb`).
Each job entered playerBoy gameplay at level 92, frame 13,601 / input poll
4,943, and reported six equal checkpoint continuation steps. This proves the
ten-repeat startup/restore evidence item of milestone A. It does not validate
watchdog fault handling, all control headings, the milestone-B ten seeded
encounter jobs, or Phase 9's 100 complete-slice deterministic runs.

### Isolated aiming calibration and closed-loop steering, 2026-09-22

`scripts/phase95_aim.py` reads the US-retail `controlGetManualAim` fields after
checking the resident instructions that write manual yaw and pitch. It restores
the *same sealed* level-92 oracle checkpoint before every bounded controller
trial and checks complete RDRAM and frame/poll/player equality. The first
attempt used a checkpoint with an incompatible controller config digest; the
import correctly rejected it before any game input. The compatible source was
`phase95-isolated-frontier-20260907a/checkpoint-b0000.json`.

The completed `phase95-aim-20260922e` trial bundle shows expert-mode R input
holds the player stationary while permitting aim yaw, and Z spends pistol ammo.
At 120 frames of R-held horizontal stick, magnitudes 5--40 caused no yaw
change, 50 moved about 2,999/65,536 of a turn, and 60 moved about 24,307/65,536.
This is a measured dead zone and nonlinear response at that checkpoint, not a
globally calibrated reticle. The `phase95-aim-20260922f` pulse bundle shows a
24-frame R-held magnitude-50 action moves yaw/pitch about 237 angle units and
magnitude-60 about 1,909 after the aim state has engaged. Twelve-frame pulses
in this test showed no angular response. Each trial preserved its controller
input, counters, state digest and before/after state.

`scripts/phase95_aim_turn.py` now selects short yaw or pitch inputs by
checkpoint lookahead and exactly replays the chosen action. A coarse 24/48-frame
version failed after inertial overshoot and retained its incomplete bundle
(`phase95-aim-turn-20260922a`). Adding intermediate durations produced a live
two-step yaw pass in `phase95-aim-turn-20260922b`: target 37,768, final 37,899,
error 131 (about 0.72 degrees). A separate two-step pitch pass in
`phase95-pitch-turn-20260922a` targeted -5,000 and ended -5,131, also error
131. Opposite-direction checks `phase95-aim-turn-20260922c` and
`phase95-pitch-turn-20260922b` both targeted + or -5,000 from their initial
axis value and ended with error 131 in two selected steps. The selected trials
reproduced exact complete-RDRAM hashes and frame,
poll and player counters. Both jobs exited cleanly and sealed their endpoints.
Those early endpoint predicates were too weak: the accepted yaw state still had
`manual_delta_x = -179.83`, and holding R neutrally for 60 frames moved yaw from
37,899 to 36,614. Chaining a pitch correction from that checkpoint exposed
the drift in `phase95-combined-aim-20260922a`; it did **not** meet combined
alignment. `phase95_aim_turn.py` now evaluates each candidate *after* a neutral
60-frame settling action and checks both motion fields at completion. The first
revised attempt rejected an exact-continuation comparison because it included
host observation sequence numbers; the comparison now uses game frame, input
poll, player, and complete-RDRAM hashes at every action boundary.

The corrected `phase95-aim-turn-settled-20260922b` reached yaw 37,550, error
218, with both motion fields zero. Pitch steering imported that sealed endpoint
and left yaw unchanged while reaching pitch -4,782, error 218. The integrated
single-command check `phase95-combined-aim-single-20260922a` reproduced both
corrections on one worker and sealed checkpoint c2. Its result confirms both
errors 218, below the 256-unit budget, with no residual aim motion. This is
also true in the opposite directions in `phase95-combined-aim-single-20260922b`
(yaw 27,986; pitch +4,782; both errors 218). This is
stable angular control in a safe room, not enemy identification, hit
confirmation, or combat. All 106 focused Phase 9.5 tests pass.

### NPC conversation and health upgrade evidence, 2026-09-22

The level-48 KingBear actor uses resident object control 90, which dispatches to
the loaded overlay-32 `mrhintsControl`. Its ordinary roaming repeatedly changes
private mode between 0 and 1. The earlier mode-only dialogue predicate can
therefore claim a false conversation. `phase95_dialogue.py` now verifies the
resident dispatch and relocated overlay, reads the game's selected-speaker
pointer, and requires that pointer to select the target before it can report a
conversation. The bounded `phase95-king-dialogue-20260909b` run approached the
actor and made 120 observations, but selected speaker remained zero throughout.
It did not verify dialogue or progression. The revised probe preserves an
explicit incomplete result on budget exhaustion. Its previous process was no
longer running when inspected on 2026-09-22; the old private bundle lacks a
completion result, so it remains incomplete evidence.

`phase95_inventory.py` now validates overlay-104 health pickup controller code
and resident dispatch before decoding `GeminiPowerup` kind 0xE9. Original
controller instructions gate health upgrades below 12, use the actor's flag
byte plus 0x2F, increment the game character's upgrade count, and refill health
to `(5 * upgrades + 4) * 256`. In the preserved level-48 arrival snapshot the
flag is clear and the character has 6 upgrades, so this is a mechanically
eligible health upgrade candidate. Its observed position is elevated; this
does not prove reachable collection. A collection verifier requires the flag to
flip, the same character's upgrade count to increase by exactly one, capacity
to rise by 0x500, and health to equal the new capacity. No live collection has
yet passed. Focused inventory tests cover positive and false evidence.

The same validated controller also handles `HealthPowerup` kind 0xA9. The
preserved level-92 entrance snapshot has four mode-0, non-respawning instances
near x=835--848, z=278--378. They restore one health unit but are initially
ineligible because the character is at 34/34 health. The reader now reports
them with health-deficit eligibility; a strict completion check requires the
same character and capacity, an exact one-unit health gain, and disappearance
of the selected actor. The static surface planner proposes a route from the
entrance toward the first pickup, but it has not been executed and does not
prove traversal. The level-48 upgrade lies on a surface around y=217 while
the restored player is near y=0; the current no-jump ground route search found
no connection. That does not prove it is unreachable. Neither pickup class has
been collected autonomously. All 101 focused Phase 9.5 tests pass.

### Verified second branch crossing and selected-step recovery

`scripts/phase95_recover_selected.py` imports a sealed checkpoint and replays the
last selected navigation record, checking its full-RDRAM hash and frame/poll/player
counters at every action boundary before sealing f1. Input/digest/counter shapes
are validated before acting, and the source journal path, digest and selected
record are retained. Mismatches cannot publish a recovery success checkpoint.
This recovers one journaled continuation, not a complete planner/batch restart.

`phase95-branch48-recovery-cross-20260909a` imported `0012b0007` from the failed
final waypoint and reproduced its selected 24-frame forward action exactly.
The recovered endpoint passed the unchanged crossing-proximity check. A separate
ordinary-input crossing then reached declared destination 48; three playerBoy /
mode-16 observations passed, ending at frame 19157 / poll 7434 and sealing e1.
The process exited zero with bridge `stopped`. This verifies both selected
level-47 destinations (122 and 48) as generated branches, while leaving the
earlier waypoint failure accurately recorded. It is not yet ten seeded complete
jobs, frozen-route oracle repetition, native comparison, or milestone B closure.

The level-48 arrival inventory reports 34 health units, slot-0 ammo 100, no
ammo-pickup actors, plus KingBear and GeminiPowerup among room actors. Their
presence does not establish enemy identity or pickup eligibility. Next work
needs to decode the NPC/progression interaction and powerup effect, or select
a validated combat encounter. All 94 focused tests pass, including exact/mismatched
selected recovery and rejection of invalid actions before execution.

### Second branch approach and precision control, 2026-09-09

`phase95-branch48-surface-20260908a` started from the level-47 arrival checkpoint
and targeted the exit whose setup declares destination 48. It completed 48
terrain-derived waypoints, then exhausted eight movement steps at waypoint 49.
Distances oscillated around 30--70 units rather than converging inside the
30-unit waypoint radius. The process stopped cleanly and checkpoint `0030c1`
preserves the last completed point. No level-48 arrival is claimed by that run.

Surface following now enables precision candidates: the original eight
24-frame directions plus six- and twelve-frame directions and a neutral action.
The radius and retry budget are unchanged. All constituent action observations
still require exact replay. Synthetic tests check the candidate set and a target
that short input reaches while long input overshoots. The bounded continuation
`phase95-branch48-precision-20260909a` imported `0030c1`, passed 17 additional
waypoints, then exhausted the final waypoint's eight steps. Its last selected
position was (730.8664, 14.7700, -280.3274), approximately 54.22 units from that
waypoint. The Curdoor collision inventory reports `polylist_enabled: false`;
do not attribute this failure to a locked door without further evidence.
The emulator stopped cleanly. `phase95-branch48-crossing-20260909a` imported the
last pre-action checkpoint `0012b0007`, but rejected the crossing before movement
because that earlier state did not satisfy the probe's 100-unit proximity
precondition. This is not a destination-48 pass. A useful next recovery is to
replay the final selected action with its exact-state check, seal that endpoint,
and then test the actual exit trigger, preserving the failed waypoint objective.

The inventory decoder now also reads signed player-health fixed-point data from
actor +0x4C properties +6. Overlay 104 `healthPickupControl` corroborates health
increments of 0x100/0x500 and full-health assignment. Its game-character +2
upgrade count gives capacity `(5 * upgrades + 4) * 256`, capped by the original
upgrade rule at 12 upgrades. The preserved second-branch state decodes health
8704/8704 (34/34 units) with six upgrades. These read-only observations are not
yet a validated death/retry controller or proof of combat behavior. All 92 focused
tests pass after the precision-control and health additions.

### Ammo inventory and pickup eligibility, 2026-09-08

`scripts/phase95_inventory.py` decodes the current single-player character's
weapon-owned mask, 16 ammo counts and 16 capacities. Resident
`mainGetGameCharacter` code establishes gameplay global 0x800FD7D4, character
stride 0x76 and base +0x15C, selected by player private byte +1 masked with 3.
Overlay 72 `ammoPickupControl` establishes ownership +0x0A, ammo +0x14 and
capacity +0x34 within that character. The decoder checks resident accessor
instructions and the loaded pickup overlay's call to `mainGetGameCharacter`.
`controlGetWeaponDef` supplies the pinned 0x30-stride definition table at
0x800A1490, with capacity increment +0x26 and limit +0x2E. Capacity collection
sets flag 0x80 plus the pickup's private +8 ID; the gameplay bitset is at +0x30.

The preserved level-122 arrival decodes character index 1, owned mask 1 and
slot-0 ammo/capacity 100/100. The two ammocapacity actors refer to weapon slots
6 and 9 (flags 199/200); fullammo refers to slot 10. None of those weapons is
owned, so all three are ineligible now. Original pickup code requires ownership
before applying its effect. No manual steering, weapon grants, or attempted
collection was performed to bypass that prerequisite.

Eligibility checks now reject unowned weapons, already-collected capacity flags,
capacity increases beyond the definition limit, and full-ammo targets without a
deficit. A capacity-collection predicate requires the exact capacity increment
AND a newly set persistent flag for the same character; proximity or actor
disappearance alone cannot pass. This predicate has synthetic coverage but no
live collection pass yet. Next, choose an eligible pickup elsewhere or establish
the normal weapon-acquisition prerequisite while implementing combat observations.

### Terrain-sampled route proposal and bounded follower

`scripts/phase95_surface_route.py` searches a sampled surface-height grid using
A*, allowing initial movement away from the objective. The default grid spacing
is 40 units with a 1,200-unit endpoint margin, bounded expansions, a maximum
sampled rise/run of 0.75, and a midpoint support check. Multiple surface heights
are retained. These are proposal heuristics, not engine collision rules: player
clearance, materials, doors, walls between samples and jump mechanics remain
unverified. The terminal distance includes height; it is not horizontal-only.

An offline proposal from the reported branch-stall position produced 37 points,
backing west before passing south of the direct obstruction and returning toward
the exit. This new proposal explicitly declares a 95-unit exit-neighborhood
radius, distinct from the prior 65-unit diagnostics, because the marker's Y=79
is well above nearby ground. It does not retroactively pass those diagnostics
or claim that an exit has activated.

`scripts/phase95_surface_follow.py` derives a proposal from the actual imported
state, then tests each point through the existing checkpoint-lookahead controller
with a predeclared 30-unit radius and eight-step budget. Per-waypoint journals and
checkpoint prefixes avoid collisions while sharing one owned emulator. Completed
points retain checkpoint lineage. Only ordinary controller input is used.
The live run `phase95-branch122-surface-20260908a` used the prior sealed branch
checkpoint. Its actual start generated 35 points including the starting point;
all 34 subsequent waypoints completed with matching selected-action trajectories.
The final player position was approximately (740.1954, 1.9120, 1562.9957), and
checkpoint `0022c1` was sealed at frame 17585 / poll 6723. The emulator stopped
cleanly. This is live terrain-informed detour evidence, not merely an offline
proposal. Each selected movement is replay-checked locally; a frozen full route
still needs the separate three-repeat oracle/native acceptance workflow.

`phase95-branch122-crossing-20260908a` then imported that endpoint, declared the
selected exit's destination 122, and verified three observations of playerBoy
in mode 16 at level 122. It sealed e1 at frame 18005 / poll 6879 and stopped
cleanly with process exit zero. Thus this branch's ordinary-input crossing is
verified, without retroactively accepting the failed direct/short-jump searches.
Its room inventory includes two ammocapacity actors, fullammo, robotToken actors,
FishPierBridge and ObjectChest. Presence does not prove collection, hostility,
or control after arrival; pickup-state decoding is the next useful capability.

Five new tests cover sampled detours, missing starting support, budget exhaustion,
vertical separation, and disjoint checkpoint namespaces. All 84 focused tests
pass after this implementation. This is not yet the composed encounter runner,
an automatically scheduled branching campaign, or a native differential pass.

### Static track geometry decoding, 2026-09-08

`scripts/phase95_terrain.py` now reads static track block/batch triangles from
RDRAM without altering the game. It verifies the four resident `trackGetTrack`
instructions at 0x8001B650 before following global 0x800A0D60. Original
`trackGetBlock`, `trackBlockDim`, and `trackGetHeights` establish the block count
at header +0x1A, block array +4 (stride 0x48), signed bounds array +8 (stride 12),
batch array at block +0x0C (stride 16, count +0x28), triangle array +4 (stride
16), and vertex array +0 (stride 10). Batch +6 is the vertex base; +8 and the
following batch's +8 bound the triangle range. Triangle bytes +1/+2/+3 index
vertices relative to that base. Pointer spans, counts/ranges and a total triangle
budget are checked. Batch flags are preserved, not interpreted as walkability.

The saved level-47 search observation decodes four blocks containing 595, 497,
862 and 887 triangle records (2,841 total). A geometric vertical-intersection
probe at X/Z (485,1701) finds height 30.8485, near the observed stalled player's
height. Probes at (540,1670) and (600,1630) find no nonvertical triangle surface;
the exit position (702,1574) has surfaces at approximately 1.5714 and 444.6320.
These are geometry-only observations, not an engine collision query or proof of
an impassable gap. They motivate seeking a surrounding surface-connected route
rather than assuming a direct jump can reach the exit.

Three unit tests cover triangle decoding/interpolation, outside/degenerate
surfaces, and invalid accessor/count/range/pointer data. Static collision masks,
material behavior, player clearance, dynamic objects and traversal rules still
need integration before any route derived from these surfaces is accepted.

### Checkpoint graph search for non-greedy detours

`scripts/phase95_explore.py` adds bounded best-first search over saved oracle
states. Unlike the local navigator, it retains alternative parents and can
expand positions farther from the exit. Each accepted node records its parent,
ordinary controller action, position/yaw, full-RDRAM digest, frame/poll/player
counters, and sealed checkpoint. Every restore is checked before a new trial.
Success requires replaying the entire selected parent chain from the imported
root with matching memory/counters at every step, then sealing the endpoint.

The first policy uses eight 60-frame stick directions, a distance-plus-depth
priority, and 60-unit spatial/eight-yaw-bin novelty pruning. Pruning ignores
other gameplay state and is explicitly heuristic; exhausted search does not
establish an unreachable exit. Default bounds are 128 saved nodes and 40
expansions. Node/trial journals survive failure, but automatic queue/planner
rehydration and unattended batch restart are not implemented yet.

Six synthetic tests pass: a detour that initially increases target distance,
bounded incomplete search, invalid coordinates, save-state mutation detection,
restore mismatch detection, and rejection of a selected route that fails replay.
The ROM-backed run `phase95-branch122-search-20260907a` started from the sealed
level-47 branch stall. It exhausted 40 expansions with 90 saved nodes; their
distances ranged from 255.4797 to 540.5694. No endpoint reached the declared
65-unit radius. `search-failure.json` explicitly reports incomplete search,
not an unreachable exit. The emulator recorded `stopped`, and checkpoints and
trial/node journals survive. All 72 focused tests passed after this search work.

Follow-up on 2026-09-08: `scripts/phase95_collision.py` decodes registered object
collision bounds, not static terrain. The resident `hitGetHitModels` instructions
at 0x8007E484 are checked against the US profile before using count/table globals
0x801047E0/0x801047E4. `hitMakePolylist` corroborates actor +0x5C collision data,
lower/upper bounds at +0x100/+0x10C, and actor +0x4C properties bit 0 at +0x0A.
Pointers, count, actor membership/duplicates, finite coordinates and ordered
bounds are checked. The saved search observation decodes eight registered
objects, including doors and switches; their bounds do not explain the stalled
position. Static terrain and polygon-level traversal remain to be decoded.
Four new synthetic tests cover valid/empty registries, invalid bounds, accessor
mismatch, count overflow, and stale actor references.

### Bounded jump lookahead at the stalled branch

Navigation now optionally evaluates eight release-A / jump-A / directional-travel
sequences in addition to the original eight movement actions. The A-button mapping
is documented in Phase 8 acceptance and used by the existing Phase 9 bridge-jump
probes. `--navigation-jump` opts into this diagnostic; it does not certify a
general-purpose jump controller or collision model. Each constituent action is
observed and checked for an unplanned mode/level change. Journals retain the full
ordered action list instead of flattening a compound action into one sample.

`phase95-branch122-jump-20260907a` resumed the prior stall's sealed b0009 checkpoint.
It evaluated 80 candidates across five selected steps, including 40 compound jump
trials, but made no material distance improvement and hit its configured stall
limit at approximately 255.85 units. The emulator stopped cleanly; it did not
crash. This rejects those tested short jump sequences as a solution from that
frontier, not the exit's reachability. All failed trials and checkpoints survive.

After this run, candidate journals were extended with intermediate position,
frame/poll/player metadata and full-RDRAM digests. Selected sequences must now
match every constituent action boundary, not just their final memory. Synthetic
tests verify jump-edge release, a jump-only obstacle, and rejection of an
intermediate divergence even when final memory converges. This extended trajectory
instrumentation has unit coverage but was added after the above live run.
Next traversal work requires geometry/route reasoning or measured exploration
that can temporarily move away from the objective; increasing retries at the
same local minimum is not evidence of progress. The branch gate remains open.

### Branch identity and first bounded alternate-exit attempt

`scripts/phase95_world.py` inventories instantiated exits without treating them
as proven reachable connections. Each identity combines source level, observed
position, and the complete 28-byte setup digest, excluding runtime heap pointers.
The selector requires exactly one current actor; identical/ambiguous matches are
rejected. Both navigation and crossing accept `--exit-id`. Navigation records the
selected setup identity and now preserves the initial world inventory as well.
This is an observation inventory, not yet a persistent coverage graph or scheduler.

The preserved level-47 arrival contains six exit actors with destinations 48,
122, 199, 92, 168, and 21. The exits to 199 and 21 share the same position but
have different setup data. Setup buffers can be byte-aligned: original code
reads their destination/control bytes individually, so the decoder validates
the full RDRAM span without incorrectly requiring word alignment for that buffer.
Actor pointers retain their alignment checks. Gates and traversal prerequisites
remain incompletely decoded; these destination numbers do not prove access.

`phase95-branch122-approach-20260907a` imported the level-47 arrival checkpoint
and selected the setup identity for destination 122. Ten selected movement
steps, each verified against its lookahead trial, approached from over 500 units
to approximately 255.54 units. Five consecutive insufficient improvements then
triggered the configured stall failure. The player ended near
(485.14, 34.76, 1701.73). The emulator recorded `stopped`; this was not a game
crash or a successful branch. Sealed checkpoints through b0009 and all trial/input
journals survive for bounded traversal investigation. This run predates automatic
world-inventory publication; its selected identity is in navigation-objective.json.

All 63 focused tests pass. New tests cover colocated exits, missing/ambiguous
selection, byte-aligned buffers, out-of-range pointers, heap relocation preserving
identity, and setup changes invalidating identity. Next work is traversal/map
reasoning beyond greedy distance reduction, plus the still-missing validated
aim/combat/health/ammo observations and composed scenario runner. No branch,
encounter, or Phase 9.5 milestone gate is closed by this diagnostic.

### Generated first exit crossing: level 92 to level 47

`phase95-exit-approach-20260907a` imported the sealed post-dialogue frontier
and used checkpoint-lookahead navigation to approach the unique `exit` actor.
Six selected actions (48 trials) reached distance 53.8886 from its fixed position
within the predeclared radius 65. Each selected continuation matched its trial's
full RDRAM hash. The landmark-only result sealed checkpoint c1; it did not claim
an area transition. Navigation still rejects unplanned transitions.

`scripts/phase95_exit.py` now provides a separate bounded crossing diagnostic.
Original `controlPlayer` at 0x80032BC8 reads the exit setup pointer at actor +0x3C;
setup bytes +0x0A/+0x0B encode the destination (high byte 0xFF means low byte only).
Setup +0x14 can redirect via world/character-selection logic, so this first probe
rejects those gated exits rather than assuming their destination. It requires a
nearby unique exit to another level and declares its destination before acting.

`phase95-exit-crossing-20260907a` imported c1, declared destination level 47,
and sent one 60-frame forward input followed by bounded neutral observations.
It observed level 92 initially, then a valid playerBoy in mode 16 at level 47
for three samples. The endpoint was frame 16097 / poll 6025, sealed as e1.
It stopped cleanly with process exit zero. This was generated ordinary-input
progression from the newly explored route, not replay of a human recording.

`phase95-level47-movement-20260907a` imported e1 in another worker and verified
movement there: 138.9858-unit forward response, yaw change -16324 on the turn
probe, and six restore-continuation steps matching full RDRAM and frame/poll/player
metadata exactly. It also exited zero with bridge result `stopped`. These are
oracle checkpoints; native resume and native parity are not established.

The new area contains multiple exits (including colocated actors), doors,
switches, range triggers, and another hint actor. A unique-name selector is
insufficient for branching here. Next work must identify objectives by validated
setup/destination identity and build the local route graph, while decoding
encounter/health/ammo state for combat. Actor presence alone is not hostility or
proof that a path is traversable. Dialogue, approach, and crossing diagnostics
still need composition into the supervised scenario runner.

All 59 focused Phase 9.5 tests pass, including destination decoding, rejection
of gated/same-level/invalid-pointer exits, stable expected-arrival requirements,
and bounded crossing success/failure without false checkpoint publication.

### Hint-dialogue frontier and post-dialogue control verification

The input-isolated run `phase95-isolated-frontier-20260907a` reached Goldwood
autonomously and passed its movement/restore probe, but direct navigation toward
the initial MrHints2 landmark exhausted its stall allowance. The NPC's private
control mode was 5 and the player's position stopped changing. The failed run
preserved a sealed `checkpoint-b0010.json`; it is not a navigation pass.

`scripts/phase95_dialogue.py` validates the unique MrHints2 actor and its private
state pointer, reads the control-mode byte, and uses bounded A+B press/release
edges. The source provenance is overlay 32's `mrhintsControl`: actor +0x68 is
the private-state pointer, and its first byte selects one of 19 control states.
Nonzero mode is not independently established as a universal dialogue predicate;
this remains a bounded probe of the observed Goldwood conversation.

`phase95-dialogue-20260907a` imported the failed navigation frontier in a separate
worker, observed active state returning to three consecutive idle samples, and
sealed `checkpoint-d1.json` at frame 15533 / poll 5813. Its result explicitly
sets `progression_verified` false. No human input or guest-memory writes were
used. This evidence alone does not establish restored player control.

The new checkpoint-based CLI for `scripts.phase95_movement` tested that claim.
`phase95-post-dialogue-movement-20260907a` observed a 137.6812-unit forward
response, but its restore verification was interrupted by a Windows
`PermissionError` reading the published `ready.txt`. This was a host transport
failure, not a game crash; the emulator subsequently stopped cleanly.
`Worker.observe` now retries transient missing/access-denied observation reads
under the original deadline, retaining the same process and action sequence.
It does not retry malformed headers, resend actions, or restart the emulator.
New tests cover transient header and memory failures, persistent denial/timeouts,
malformed observations, and process exit.

The corrected run `phase95-post-dialogue-movement-20260907b` imported the same
sealed dialogue checkpoint and passed all six exact restore-continuation checks:
all 4 MiB of RDRAM and frame/poll/player metadata matched. Forward response was
137.6812 units and the turn probe changed yaw by -16292. The process exited zero
and the bridge recorded `stopped`. Thus movement is available after this specific
conversation; exit/progression flags and an encounter remain unverified. All 54
focused Phase 9.5 tests pass. Next, compose interaction handling with navigation
and validate the first exit/encounter objective without weakening those predicates.

### Cross-process recovery implementation and input-isolation correction

Live result: `phase95-frontier-20260907c` rebuilt the bridge route and sealed its
completion checkpoint. A distinct worker, `phase95-resume-20260907a`, verified
and imported that checkpoint, matched its RDRAM/frame/poll/player observation,
then reached the declared MrHints2 landmark neighborhood in ten selected actions
(80 lookahead trials), ending at distance 59.40 within radius 65. Every selected
continuation reproduced exactly and the process stopped cleanly. This is oracle
cross-process route extension without replaying startup. It does not prove an
NPC interaction, a genuinely alternate branch, native resume, or combat.

The repeat `phase95-input-repeat-20260907a` showed guest X=4 during requested
neutral input and failed bounded keyboard recovery. Suppressing digital analog
bindings and setting axes before each frame were insufficient for physical input
isolation. Inspection found the copied N64 profile still bound to XInput axes.
Worker setup now removes N64 physical button, autofire, and axis bindings from
the private configuration copy only. Original user settings are unchanged. A
first fresh run with cleared bindings completed label entry at frame 1667;
the second fresh run also passed. Runs `phase95-isolated-input-20260907a` and
`phase95-isolated-input-20260907b` have 31 identical observation records, including
full RDRAM hashes, sequences, frames, polls, and player pointers. This is two
matching startup/name completions, not ten gameplay jobs or 100 slice runs.
Forty-six Phase 9.5 unit tests pass. Configuration pins changed, so checkpoints
from the earlier configuration must be regenerated for the isolated-input profile,
not silently imported with relaxed validation. Failure artifacts are retained.

New checkpoints are sealed by the host after the save acknowledgment: manifests
bind ROM, runtime EXE/DLL inventory, configuration, Lua script, state/side-file
digests, and expected RDRAM/counters. Imported checkpoints must match those pins
and reproduce the sealed observation in a new isolated worker. Import records
the original manifest and digest as lineage and changes only the transport
session token, not guest state. Old unsealed states are not silently promoted.
Landmark completion now saves a frontier checkpoint. Cross-process live proof
is pending; planner/frontier graph packaging and native resume remain separate.

`phase95-frontier-20260907a` exhausted its startup budget with an unchanged name
key despite logged stick commands. Its RDRAM hash differed from the earlier
successful run as early as frame 121. `phase95-frontier-20260907b` confirmed the
stall persisted after suppressing digital analog-direction bindings; it stopped
after the new bounded menu retry policy instead of repeating to the global limit.
Both failed runs and their logs are retained; neither counts as success.

Local BizHawk sources show `joypad.setanalog` uses frontend sticky holds and the
N64 core gives digital analog-direction bindings precedence. The bridge now
suppresses those bindings and installs stick values before each frame as well
as at input polls. This removes reliance on host refresh timing for the first
frame of a command. Startup logs now include the guest controller buffer rather
than only requested inputs. The first corrected run passed name entry; repeat
startup and sealed gameplay-frontier recovery are being verified. The early
cross-run hash mismatch is not declared resolved by a menu success.

### Gameplay continuation verified; local navigator under test

The private `phase95-gameplay-restore-20260906a` run completed and stopped.
After saving the settled Goldwood state, all six forward/turn/release continuation
steps reproduced byte-identical 4 MiB RDRAM and matching frame/poll/player
counters after restore. Each step's hashes and counters are recorded in
`gameplay-restore.jsonl`; `movement-result.json` records six matching steps.
This advances gameplay restore evidence, but does not prove death, save-file
relaunch, overlay reload, cross-process planner recovery, or native snapshots.

`phase95_navigation.py` adds local checkpoint lookahead: evaluate eight bounded
stick actions from one state, score 3D distance to a declared observed landmark,
restore, execute the selected action, and require exact RDRAM agreement with its
trial. The target/radius/budget are written before trials. Trial branches and
selected route actions are logged separately. Exhausted budgets, repeated lack
of progress, invalid player state, unexpected level transitions, and failed
continuation reproduction are failures, never completion. This is not a global
map/pathfinding or combat implementation. Synthetic tests cover final-budget-step
completion, exhausted budgets, vertical distance, and seeded selected-action
divergence. The first live bridge-landmark run passed in
`tools/private/phase95-navigation-20260907a`: the predeclared target was the
observed longwoodbridge actor, radius 65 in 3D, with a 40-step budget. Five
selected 24-frame actions (40 candidate trials) reached distance 11.0253 in
level 92. Every selected continuation matched its trial RDRAM exactly; the
gameplay restore check also passed in this run. The final worker sequence is
310 and the emulator stopped cleanly. This is a generated local navigation
route, not the recorded manual route. The objective/trials/selected actions and
result are private JSON artifacts. Landmark proximity does not establish an
encounter, pickup, interaction, alternate branch, or full slice completion.

### Movement and first checkpoint continuation

`scripts/phase95_movement.py` measures bounded stick responses after a neutral
settling period. `phase95_startup --calibrate-movement` first performs state-aware
startup, then records player positions, heading changes, frame/poll counts, and
the exact actions. It rejects unplanned front-mode/level transitions.

Private run `tools/private/phase95-movement-20260906a` reached level 92, settled
with four consecutive stationary 120-frame neutral intervals, then moved about
138.99 horizontal units under a 60-frame Y=60 input. The 30-frame X=60 probe
changed yaw by -16299 units and also translated the player. Release intervals
continued moving; this is not a pure turn-in-place or instantaneous stop model.
Do not infer a world-space navigation policy from one heading/camera setup.
The shortened keyboard wraparound path also completed in this live run.
All recorded probes completed and the emulator exited cleanly. This establishes
ordinary input response, not aiming accuracy, combat, or navigation acceptance.

The bridge now supports save/load commands for unique hexadecimal checkpoint
slots, with session/sequence validation, neutral input, persistent BizHawk state,
and companion player/poll state. Transport sequence numbers remain monotonic
after restoration; input polls return to the saved branch counter and explicit
checkpoint events are logged. These are same-session oracle checkpoints only:
full planner/frontier/disk-state packaging and cross-process recovery are pending.

`python -m scripts.phase95_bridge OUTPUT --checkpoint-probe --emulator EMUHAWK
--rom ROM --rom-sha256 EXPECTED_SHA256` passed in private run
`tools/private/phase95-checkpoint-20260906a`. It saved at frame 121, advanced 60
frames, restored, and repeated the action. All 4 MiB of RDRAM and frame/poll/player
counters matched at frame 181. The result digest is recorded in private probe.json.
This is startup-only continuation evidence; combat/loading/save/retry restore
equivalence and full Phase 9.5 checkpoint acceptance are still open.

Next: save a settled gameplay frontier, validate repeated movement continuations
from it, then build feedback-controlled navigation to an explicit reachable
Goldwood objective. Map geometry and aim/combat/health decoding remain required.

### State-aware name completion

`phase95_keyboard.py` resolves overlay-42 state from its loaded module address
and verified relocated instruction pairs, rather than fixing heap addresses.
It reads the menu submode, key index, label length, and animation tilt. The
initializer sets its active flag before its buffer cursor; that intermediate
state is explicitly unavailable, not a fatal invalid pointer or actionable menu.
Opcode, pointer, buffer, and key bounds are checked. Five decoder tests cover
those cases, including aliased non-RDRAM pointers.

The private live run `tools/private/phase95-label-20260906a` completed label
entry with ordinary inputs and no route recording: select a fresh slot, wait for
the keyboard, type one character, move right while observing each key selection,
confirm END at key 40, then observe mode 24 changing to mode 0 / level 322.
The endpoint is frame 2993, sequence 108, with 1375 input polls. State and action
journals show the label length changing to one, key selection reaching 40, and
submode changing from 1 to 9 before the transition. The emulator stopped cleanly.
This is new-game startup progress, not proof of gameplay or persistence recovery.

The `--gameplay` extension passed its first live startup diagnostic: it waits through
the opening sequence, confirms mode 5 with separated input edges, and requires
mode 16 plus a controlPlayer-hook pointer present in the actor table and named
playerBoy before reporting its diagnostic endpoint. Actual movement/control
calibration is still required; a player actor alone cannot prove controllability.
`tools/private/phase95-gameplay-20260906a/startup-result.json` records mode 16,
level number 92, and the validated player at frame 14927 / action sequence 273 /
input poll 5615. The run used a fresh isolated save and ordinary state-selected
inputs; it did not load a recording. The emulator exited cleanly. Mode 16 first
appeared at level 93 without a player, so the controller correctly waited rather
than calling that earlier transition gameplay. No movement/encounter gate is
claimed. A subsequent code optimization chooses the shorter horizontal path to
END; its wraparound branch is unit-tested but not yet verified in a live run.
Twenty-nine Phase 9.5 unit tests pass after this extension.

The first bounded state-aware startup diagnostic is implemented in
`scripts/phase95_startup.py`. It waits neutrally in observed modes 0/2, sends
separated A-button edges in mode 3, and stops on observed mode 24. It never
reads the recorded cold-boot route. The private run
`tools/private/phase95-startup-20260906a/startup-result.json` records that endpoint
at emulator frame 1327 after 16 actions and 574 input polls, with no human input.
The emulator exited cleanly. Five startup-policy tests cover loading, explicit
release edges, transition stop, stale/incomplete state, and unsupported modes.
This is entry into the save/name interface, not a new game or gameplay pass.

Menu investigation identifies overlay 42 (`frontKeyboard`) as the save/name
interface. The guest module table provides its actual loaded address; relocated
initializer instructions can resolve its state variables without assuming a
fixed heap address. Existing captured frame 3000 shows the game-label keyboard.
Do not confuse the overlay's save-slot bytes with keyboard navigation coordinates:
the former include six-slot selection and copy/delete state. Decode the actual
key selection and submode before driving name completion. The level-number word
is uninitialized at very early boot and must not be used as a valid level predicate
until the relevant initialization/loaded-state conditions are established.

Integrate the live adapter with observations and implement state-aware menu
control and movement calibration. Resolve level
and control-mode observations from original code and live state; establish the
bounded Goldwood scenario before selecting navigation objectives. Do not infer
hostility from actor presence or copy uncertain upstream struct offsets.

## Gate audit

### 2026-09-23: input-poll boundary and east/death diagnostics

The selected south route's fresh oracle poll trace and native trace now record
controller samples and mode/level/RNG state at each poll. `phase95_poll_compare.py`
validates that both consumed the declared input-v2 samples and reports the first
observed difference without claiming a common execution boundary. The native
run stopped at the declared 26,441 retraces after 8,883 polls; the oracle used
10,881 polls. All 8,883 shared-prefix input samples match. Their clocks already
differ at poll 0 (native retrace 0, oracle frame 40); the first observed
mode/RNG difference is poll 16 (native retrace 35, oracle frame 72). This is
not yet a validated gameplay divergence or native parity. The native run still
has zero weapon kills versus the oracle's three. The private comparison artifact
is `tools/private/phase95-south-poll-compare-20260923a.json`. The updated
one-repeat regression-bundle smoke test completed in 267 seconds and now
produces the poll comparison automatically; its oracle repeat matched and its
native endpoint mismatch remained explicit.

A natural-damage probe from the generated level-21 route depleted health to
zero at frame 35,255 and sealed that state. Thirty further neutral intervals
(3,600 frames) left mode 16, level 21, the same player pointer and position,
and zero health. Short A/Start/B probes immediately after depletion did not
restart; after the settling period, each caused the player to leave the actor
table, followed by a stable level-21 playerBoy respawn at position
`(40, -1.99, 841)` with health `0x2200`. Stick movement did not trigger it.
`phase95_death_retry_scenario.py` then reproduced the entire bounded
damage-to-retry sequence in one checkpoint-resumed command: 69 neutral damage
intervals, 30 neutral post-zero intervals, an A press, a missing-player loading
observation, and three stable positive-health respawn observations. Its private
result is `tools/private/phase95-level21-death-retry-scenario-20260923a`.
The exact damage source was not attributed to one actor, and this remains a
frontier diagnostic, not ten seeded end-to-end Goldwood jobs. No health or
progression memory was edited. Its 16,483 selected input polls were exported
through the multi-worker checkpoint lineage and a fresh BizHawk replay matched
the original final 4 MiB RDRAM SHA-256
`36f66e782ee15b8f9402cfbdd5e14f5fb0b8bc2cbeb01597882fdc855c251cb7`.
Native reached the same 39,347-retrace target without crashing, but consumed
only 13,185 polls and is not a gameplay-parity pass.

The first one-command east scenario reached the upper route but stalled at its
last automatically proposed waypoint. A west-shift to the reviewed upper-deck
route, followed by 18 ordinary-input waypoints and a pinned three-waypoint
ground approach, crossed to level 48 in a chained checkpoint diagnostic with
three stable player observations. The fresh six-stage one-command re-run from
the earlier level-47 checkpoint then completed the same destination without
intervention in 1,666 seconds, ending at frame 18,161 with full RDRAM digest
`caaf652b79bbee7fde212599f3e7942d2a78e71a875380531e590c023c6006b0`.
Its private artifact is `tools/private/phase95-goldwood-east-scenario-20260923b`.
The 6,949 selected controller polls were exported and a fresh oracle replay
matched the same final 4 MiB RDRAM digest. Native reached frame 18,161 without
crashing but consumed 6,123 polls, so the alternate branch is also not native
parity evidence.
The proposal grid's exact start position changes which side of a narrow
passage is selected, so the reviewed route and layer checks are explicit;
exit-coordinate proximity alone is not completion. This is a second named
destination, not combat/pickup/death coverage within that east job. The south
scenario starts from a later south-specific waypoint-57 checkpoint in the same
lineage. These two one-command scenarios do not yet select destinations from
one identical immediate checkpoint; that milestone-B condition remains open.

`phase95_seeded_jobs.py` now selects the three reviewed objectives by seed,
pins all route/checkpoint inputs in its batch objective, preserves failed or
interrupted attempt directories, and resumes without re-running completed
seeds. A one-seed death/retry smoke job completed in 84 seconds; an immediate
resume launched zero workers and left exactly one completion-journal entry.
The first ten-job-manifest attempt supplied the earlier east checkpoint to the
south-specific waypoint-57 route and failed at its frontier guard before
gameplay. The failed attempt was preserved; the runner now requires distinct
pinned south, east, and death checkpoints. No ten-job result is claimed.
The seed currently selects the objective only. It does not vary low-level
navigation or combine the level-21 death frontier into the south job, so this
is a restartable reliability/branch-batch foundation, not ten accepted seeded
exploration jobs.

### 2026-09-23: composing the common-frontier south branch

`phase95_goldwood_common_south.py` now composes fifteen reviewed, live-observation
waypoint segments from the earlier level-47 checkpoint used by the east branch.
It advances via the bounded navigation controller, not recorded controller
samples. Each segment's imported checkpoint hash must equal its predecessor's
sealed endpoint hash before gameplay starts; the live endpoint must then match
the same reviewed full-RDRAM hash. The two intentional lower-layer transitions
use explicit reviewed waypoints and exact endpoint hashes instead of weakening
the generic surface-layer guard. Three lineage unit tests cover valid, skipped,
and incomplete chains.

Run with `python -m scripts.phase95_goldwood_common_south OUTPUT --checkpoint
tools/private/phase95-exit-crossing-20260907a/checkpoint-e1.json --private-root
tools/private --emulator EMUHAWK --rom ROM --rom-sha256 PIN`. `OUTPUT` must not
already exist. `--start-segment` and `--stop-after` are bounded checkpoint
diagnostics, not a substitute for the uninterrupted command.

Checkpoint-resumed diagnostics reproduced every segment, including the complete
south prefix through waypoint 57. The final waypoint checkpoint in
`tools/private/phase95-common-south-short-bg-20260923a` matched the prior
combat-frontier full-RDRAM SHA-256
`18023c520ffb56594a7358d0d638d31f10c00e5ab0c2124f10d77271106d75cb`.
An initial composition tried to jump from waypoint 13 directly into the final
historical chunk; its entry guard correctly rejected the mismatched checkpoint.
The reviewed route is actually seven chunks from waypoint 13 to 57, and the
composer now includes every boundary. The uninterrupted one-command run
`tools/private/phase95-goldwood-common-south-20260923a` then imported the exact
same level-47 `checkpoint-e1.json` used by the east scenario and passed all
fifteen route segments plus all seven south-scenario stages in one worker. It
recovered the MrHints2 dialogue lock, selected three ordinary pistol kills,
crossed through level 199 to stable playable level 21, and collected the exact
one-unit health pickup without human input. It finished in 2,284 seconds at
full-RDRAM SHA-256
`a50a11057b010d06a445cafc0cfa0fa5780ab5f206c6a8a1fe79d66de395b335`.
Thus both named destinations now have one-command runs from the same immediate
checkpoint. This remains reviewed-route execution, not unknown-path discovery
or native parity. The corrected ten-job batch at
`tools/private/phase95-goldwood-seeded-ten-20260923b` has completed seeds 0-3:
south, east, death/retry, and a second south, on their separately pinned
frontiers. The remaining six jobs subsequently completed: the sealed
`batch-result.json` records `completed: true`, `jobs_completed: 10`, all three
objectives covered, and `native_parity_verified: false`. Seeds 0-9 each
completed on attempt one with no manual intervention. This is a 10/10
reliability/branch-objective batch, not a milestone-B pass: seeds select only
the objective, low-level paths do not vary, the three objectives begin at
separately reviewed frontiers, and native parity is not established.

### 2026-09-24: south-to-death continuation from a common branch lineage

`phase95_goldwood_south_retry.py` resumes the sealed health-pickup checkpoint
from the completed common-level-47 south run, verifies both parent completion
manifests and the imported full-RDRAM hash, then navigates toward an observed
level-21 BlueAnt and performs natural death/retry in the same BizHawk worker.
The first ROM-backed attempt reached all 25 waypoints and the exact prior
death-frontier RDRAM hash `0ab007d76e46f26ddd9af083926ded7fd075df47e5f1698ad1dbfa854c5ddb5a`,
but the originally selected ant had moved far away. A static proximity assertion
rejected the otherwise live frontier. The failed run remains under
`tools/private/phase95-goldwood-south-retry-20260924a`. The controller now
records target distance and requires live BlueAnt context without inferring the
source of subsequent damage.

The corrected run at `tools/private/phase95-goldwood-south-retry-20260924b`
completed all 25 waypoints, observed two live BlueAnt actors, zero health at
frame 35,255, A-triggered player departure, and three stable full-health
level-21 respawn observations through frame 39,347. It used no human input.
Its full selected lineage exported 16,483 controller polls with input SHA-256
`a990a04770d3a8f0f66025744d124b65f6b0bf7d5989f2d796ae6653da95776b`.
A fresh isolated BizHawk replay reached the declared frame and exactly matched
the composite final full-RDRAM SHA-256
`36f66e782ee15b8f9402cfbdd5e14f5fb0b8bc2cbeb01597882fdc855c251cb7`.
The native replay reached the same 39,347-retrace target without crashing, but
consumed 19,215 controller polls, including 2,732 post-EOF neutral polls.
That endpoint is an input-clock divergence, not parity; the first aligned
gameplay divergence and Pak equivalence remain unverified. This demonstrates
a reproducible combined south/death route from the common branch's descendant
checkpoint. It is still one reviewed route, not varied seeded exploration or
whole-campaign coverage.

To regenerate the continuation and selected-input export in one command, run
`python -m scripts.phase95_goldwood_south_retry OUTPUT --checkpoint
tools/private/phase95-goldwood-common-south-20260923a/checkpoint-6e1.json
--emulator EMUHAWK --rom US_ROM --rom-sha256 US_ROM_SHA256 --initial-flash
INITIAL_FLASH --initial-pak INITIAL_PAK`. `OUTPUT` must not exist. The command
does not itself certify native parity; oracle/native replays above are separate
verification artifacts.

### 2026-09-24: scenario-neutral route verification

`phase95_route_verifier.py` now takes any completed source-worker result and its
selected-input export, validates their shared lineage and final 4 MiB RDRAM
image, derives declared stage checkpoints, and runs or reuses pin-matched
oracle/native replays. It audits every requested oracle checkpoint and the full
input-poll path, records native endpoint/poll evidence, and invokes native
failure triage if a new native replay exits nonzero. It does not equate the
native state hash to BizHawk RDRAM or mark parity while input/update alignment
and Controller Pak equivalence remain open. Existing replay roots can be reused
only when their ROM, emulator, config/runtime, input, save and executable pins
match; the native isolated save copies are writable, so the verifier checks
their pre-run launcher hashes and reports post-run digests separately.

The first fresh end-to-end job, under
`tools/private/phase95-goldwood-east-generic-verification-20260924a`, recaptured
all six declared east-route stage images with the current emulator and native
binary. One independent oracle repeat matched all six. Native reached frame
18,161 but consumed 8,623 polls versus 6,949 declared, with 1,674 post-EOF
neutral polls; the same-index mode/level/RNG comparison first differs at poll
16, which is not yet an aligned gameplay divergence.

The south/death source exposed an important checkpoint identity rule: at frame
26,975, checkpoint-restored candidate trials yielded several different RDRAM
hashes without advancing the emulator frame. The verifier therefore rejects an
ambiguous frame-only request and accepts an explicitly observed frame-plus-hash
selection. A fresh replay under
`tools/private/phase95-goldwood-south-retry-generic-verification-20260924b`
matched eight selected images, including the exact ant frontier, health-zero,
player-absent, and stable respawn states. Native's 19,215 versus 16,483 polls
and 2,732 post-EOF polls remain a boundary failure. Future south/death
scenario results now emit these selected checkpoint identities directly; the
older completed run supplied the ant hash explicitly for this audit. These are
one-repeat smoke validations, not the three-repeat milestone-B gate.

For a new generated route, run `python -m scripts.phase95_route_verifier
SELECTED_INPUT SCENARIO_RESULT OUTPUT --emulator EMUHAWK --rom US_ROM
--rom-sha256 US_ROM_SHA256 --executable NATIVE_EXE --repeats 3`.
`--checkpoint-state FRAME:SHA256` selects a branch-specific state when the
worker journal contains multiple states at one frame. Existing pinned replay
roots can be supplied with `--oracle-existing` and `--native-existing`; the
verifier will reject stale pins rather than silently recapture or relabel them.

| Gate | Evidence status |
|---|---|
| A: autonomous control and restore equivalence | Ten independent fresh-save state-aware startups reached level-92 playerBoy gameplay; all six-step checkpoint continuations, entry hashes and final hashes matched. Expert-mode input calibration and settled yaw/pitch steering pass on a sealed level-92 checkpoint; combined angular targets pass in both directions. Alignment to an observed game target, multi-heading validation, watchdog fault tests, and full planner/recovery packaging remain missing, so the whole milestone remains open. |
| B: generated Goldwood gameplay | Generated landmark navigation and declared level 92-to-47, 47-to-122, and 47-to-48 crossings verified. A one-command south run from the earlier common level-47 checkpoint verifies fifteen exact-hash route segments, MrHints2 dialogue recovery, three ordinary pistol kills, door opening, level-199 intermediate to playable level-21 arrival, and exact health pickup collection. The one-command east run from that same immediate checkpoint verifies the alternate level-48 destination. The south route's frozen selected input matches four gameplay checkpoints and its final hash in three independent BizHawk repeats. A checkpoint-resumed continuation from the common south pickup now combines observed ant-route navigation and natural death/retry; its exported full lineage reproduced the final hash in a fresh BizHawk run. The 10/10 seeded objective batch completed without intervention, but uses separate reviewed frontiers and unvaried low-level paths. Native consumed 2,732 post-EOF neutral polls on the combined route; first aligned divergence is not yet established. Varied paths, KingBear dialogue, and level-48 health upgrade collection remain unverified. Gate open. |
| C: expanding slice frontier | Coverage graph, generated slice scenarios, and recovery coverage missing. |
| D: regression factory | A completed generated south route can produce selected input, fresh oracle repeats, native replay, endpoint differential, and poll-boundary comparison in one bounded bundle; one-repeat smoke and a prior three-repeat bundle completed. The scenario-neutral verifier has now passed one-repeat six-checkpoint east and eight-checkpoint south/death jobs, each with a current-binary native endpoint report and parity explicitly false. A three-objective seeded runner preserved and resumed one completed smoke job without duplication, then completed all ten separately pinned objective jobs without intervention. A native crash now triggers bounded signature-preserving prefix triage and original-artifact retention, with nonmonotonic uncertainty reported. ROM-backed fault seeding, automatic ASan rerun, restartable perturbation batches, and 100 complete slice runs remain missing. |
| E: native frontier resume | Full execution-state inventory, snapshot implementation, and equivalence evidence missing. |

Autonomy-supervisor diagnostic, 2026-09-23: a queued, pinned streaming
comparison of the existing south-route traces completed and reported a raw
retrace-1 difference in `actor_list`, `actor_count`, and
`actor_table_sha256`. A guarded read-only diagnosis then found that native
retrace 1 and BizHawk frame 41 have identical semantic digests; this was
independently checked with the trace comparator's digest function. The
existing poll report places poll 0 at native retrace 0 versus BizHawk frame
40. Thus the raw frame-1 difference is consistent with startup capture-point
misalignment, not yet a gameplay code defect. A constant offset and initial
save/Pak equivalence remain unproved. The next falsifiable test is a short
neutral-input boot with actor-list pointer/count, poll index, and hook
location captured at the first controller polls and just after actor-list
initialization in both systems; compare the same hook/poll boundary.

Event-order capture follow-up, 2026-09-24: the model-free
`scripts.phase9_event_pair` producer completed a fresh pinned 1,500-target
native/BizHawk run and immediately reused both completed sides on restart.
Across 659 shared controller polls, the sampled inputs matched; the first
same-poll semantic mismatch remains poll 16. The bounded controller/update/VI
trace identifies different cadence at poll intervals 15-16 (four native VI
messages and no native update versus two BizHawk VI messages and one update),
17-18 (two native VI messages and one update versus 31 BizHawk VI messages
and no update), and 573-574 (four native VI messages versus 56 BizHawk VI
messages). This makes a dropped controller sample less likely and gives a
specific scheduler/capture boundary to test. It does not validate initial
Controller Pak equivalence, within-call input consumption, aligned game
state, or native parity. Milestones A, D, and E remain open.

The durable supervisor has now queued and sealed that event capture from
fresh current-binary update, poll-pair, and lag predecessors. Its 659-poll
event report is independently pinned in the ledger. The read-only diagnosis
successor is wired to wait for this evidence and consume the event report
and both raw streams before making another hypothesis. This closes a manual
handoff in the evidence loop, not the parity or complete-game gates.

The completed-update analyzer now identifies a much tighter candidate
frontier in that sealed capture: 567 consecutive native/BizHawk update states
match, with first same-update difference at update 568. Controller-poll
clocks already differ at update 1, so poll 16 is a capture-phase mismatch,
not evidence for an early gameplay defect. The update-568 difference occurs
around the 56-VI oracle gap and still requires initial Pak and exact
within-call input validation. Future event-pair bundles include a digested
update-alignment report automatically. The read-only supervisor diagnosis
ran with the existing ChatGPT login and no API billing; no full-game gate is
closed by this result.

A second model-free paired replay now derives a four-update focused RDRAM
window from that frontier and compares the exact game-visible current and
previous controller buffers and pressed/released buttons. Its first local
run and no-recapture restart agreed across updates 566–569, including the
update-568 state difference. This reduces support for a dropped delivered
sample at that boundary; VI scheduling, all within-call reads, and initial
Pak equivalence remain open. The durable supervisor has a queued-successor
path for this focus capture, but the new ledger path and any later diagnosis
must still be exercised before calling that transition verified.

That ledger transition subsequently passed as
`input-focus-430010b43acf3d443d4f6876`, with an independently verified
seal and an idempotent scheduler rerun. The older read-only diagnosis is
preserved; a new report-digest-suffixed diagnosis successor is now wired to
consume the focused result. It has not yet run, so the causal explanation of
the update-568 transition remains open.

Bounded raw-SI follow-up, 2026-09-24: an opt-in US BizHawk trace captured 14
`__osSiRawStartDma` entry/return transactions in a focused update window.
At poll 574 there were four write/read pairs, including three repeated
exchanges from callers `0x80093254`/`0x80093270`; the trace reports the full
64-byte before/after PIF buffers privately and pins their digest. The
ordinary controller-read caller also appears. This establishes actual SI
traffic at the long VI interval, but not equivalent native accessory behavior
or a game-code defect. A separate 2,000-target native/BizHawk event pair
extended the poll-575 resynchronization from 84 to 303 matching offset-paired
updates. It ended only because the oracle update stream ended; two intervening
VI-queue delta differences retained matching semantic state. Alignment and
parity remain unverified. The restartable update scheduler now recognizes a
validated oracle-stream-ended diagnostic suffix and queues one larger capture
under its existing route bound, while still rejecting semantic mismatches and
inconsistent suffix indices. The SI parser is included in producer tool pins.

Longer ledger frontier, 2026-09-24: current-tool update job
`updates-rebase-4c46c5e9e2fd562e298985bf` sealed 4,800 native retraces
and 7,200 oracle frames from the selected south input. The first raw
same-numbered update mismatch remains 568, but the poll-575 anchor supports
693 matching offset-paired semantic updates before a new candidate mismatch
at native update 1265 / oracle update 1261. The compared controller input
prefix still matches. The focused before/after capture reports matching
controller values, two configured VI consumptions on each side in both the
lead-in and onset intervals, and a first sampled actor difference at the
first paired VI consumption of the onset. Actor index 11 has three differing
bytes at the completed-update boundary. The full RDRAM transition also has
unclassified non-actor changes; none is promoted to a gameplay global or a
validated code defect. Hook equivalence, initial accessory equivalence, and
whole-route parity remain open.

The VI-boundary diagnosis scheduler had a hard-coded statement from an older
capture that the lead-in contained an extra native VI; this is false for the
new sealed report. The successor packet is now versioned by report digests and
constructed from that capture's measured VI counts, first relative mismatch,
focused actor state, input comparison, and RDRAM transition summary. The
superseded queued diagnosis must not be run as evidence.
The stale packet `vi-boundary-f5d113483273b4bf8223fa76-diagnosis` was
explicitly marked blocked in the private ledger, retaining its attempt and
reason. Its digest-versioned replacement
`vi-boundary-f5d113483273b4bf8223fa76-diagnosis-v2-d1b21cb28539` is queued
read-only with twelve pinned evidence files, no allowed source edits, and no
extra-native-VI claim. It has not run: the ledger already records 17 coding-
agent attempts for this UTC day, above the continuous worker's cap of four.

Model-free actor-word localization now augments the RDRAM transition report
with a bounded list of raw before/after 32-bit words for newly differing
bytes in stable actor slots. It checks the four snapshot hashes again and
excludes slots whose index/address changed across the transition. A direct
re-analysis of the sealed update-1265/1261 snapshots found 18 stable slots,
zero unstable slots, and exactly two newly differing words in actor 11 at
offsets `0x0EC` and `0x0FC`, covering the three actor bytes above. The word
contents stay private; offsets are localization evidence, not an established
field type, instruction cause, or native parity verdict.
The refreshed ledger boundary job `vi-boundary-4208021de089d379547b71fb`
sealed that report with two raw word offsets and 18 stable actor slots; its
read-only diagnosis successor is queued with the offsets and equal VI counts
in its measured-facts prompt. The four-image snapshot digests were rechecked
before reporting. This still does not establish matching hook phases or an
instruction-level cause.

A scheduler audit found that a boundary-tool change queued seven old focused
captures alongside the current one. Those seven queued attempts were retained
as explicitly blocked superseded jobs, and the scheduler now selects only
current-tool, unchanged-binary, unsuperseded focus leaves. Re-running the
transition produced no duplicate queue entries. The private ledger seal/lock
audit remains healthy; its unresolved count includes these intentional
historical supersessions, not seven new gameplay defects.

Autonomous frontier discovery probe, 2026-09-24: the new
`scripts.phase95_frontier_discover` imports a sealed US checkpoint twice in
isolated BizHawk workers, compares RDRAM/counters/player position and exit
inventory, and emits only *unexplored* exit-proximity objectives. From the
reviewed level-21 Goldwood south checkpoint, private run
`phase95-frontier-discover-20260924c` agreed on the same five instantiated
exits in both workers. This is not a complete level or game inventory and
does not establish gate requirements or reachability. Candidate priority is
measured horizontal distance, not exit hash order.

The first generated objective selected the nearby level-21-to-47 exit.
`phase95-frontier-exit-search-20260924a` exhausted 40 expansions under the
old 3D-radius rule, getting within 76.34 units. Its trace placed the player
on the floor near the exit's X/Z coordinates while the exit actor was about
76 units above the player. The search now supports an explicit horizontal
radius plus vertical tolerance without claiming a level transition. In
`phase95-frontier-exit-search-20260924c`, two independent normal-input
searches completed the 25-horizontal/100-vertical proximity predicate in
four actions, with identical final RDRAM SHA-256
`c9b72d73cfc6f0412e7b03fe2c931eb3f8eb7b094cf1891b0da4d2c47f3a2fc9`.
Each retained a sealed nearby checkpoint and exact selected-route replay.
The frontier worker now checks checkpoint state/side digests and the final
observation before publishing a successful checkpoint pointer. It also
promotes a replay-equal successful search checkpoint into a reached graph
node, without treating exit proximity as a crossed transition. Applying that
promotion to the sealed run and then launching discovery from its generated
checkpoint produced private `phase95-frontier-discover-20260924d`: two
independent workers agreed on four remaining instantiated level-21 exits.
The graph therefore grows from a generated checkpoint, but an outer job
scheduler still has to resolve checkpoint pointers and drive this sequence
without hand-entered commands.

Crossing remains blocked. The selected exit actor was absent at the nearby
checkpoint, although the source level was still 21. The exit helper can now
resume an in-flight objective only from a replay-equal search result whose
final RDRAM digest matches the checkpoint. Private crossing run
`phase95-frontier-exit-cross-20260924b` applied the default entry action and
observed 100 bounded steps without level-47 arrival. Actor disappearance was
therefore **not** treated as transition proof. The runner now writes an
explicit `exit-failure.json` on exhausted arrivals; a fresh eight-step private
probe `phase95-frontier-exit-cross-20260924c` verified that artifact and still
observed level 21. Next: determine whether
this marker is a one-way/conditional exit, whether the crossing action is
wrong, or whether the actor unload reflects a different gameplay condition;
then make the crossing and next-checkpoint registration part of the frontier
scheduler. Phase 9.5 A/B/C gates and full-game autonomy remain open.

Restartable bounded cycle, 2026-09-24: checkpoint nodes now carry a private-
root-relative pointer as well as a manifest SHA-256. The new
`scripts.phase95_frontier_cycle` resolves and checks that pointer, runs one
frontier job, persists graph/state before launching follow-up discovery, and
can resume pending discovery without replaying the completed job. Its test
also preserves interrupted worker directories and rejects path escape or a
checkpoint-seal mismatch. Live private run
`phase95-frontier-cycle-20260924a` used one command from the reviewed level-21
checkpoint inventory: it covered the nearest exit-proximity edge twice with
identical final RDRAM, promoted the selected route checkpoint, and discovered
from that checkpoint in two more independent BizHawk workers. The resulting
graph has two reached checkpoint nodes, two covered declared edges (the
proximity objective and checkpoint link), and eight untested proximity edges
across the two checkpoints. These counts are only for declared graph edges;
the complete level/game denominator is unknown. The command is bounded by
`--max-jobs` and retains a private `state.json` for resume. It does not yet
schedule exit crossing, combat, pickup/progression validation, native replay,
or whole-campaign discovery.

Level-21 region prompt resolved, 2026-09-24: the previously blocked exit was
not an unreachable doorway. A single-frame replay of the fourth search action
from its sealed parent checkpoint reproduced the exact 60-frame final RDRAM
hash and found the exit actor disappearing at frame 26647, while the current
level remained 21. At that boundary, game globals requested level 47, set
the region-change flag, and entered pause mode 1. The original `func_80046070`
update path checks `joyGetPressed` for A (`0x8000`) or Start (`0x1000`) before
clearing that flag. Sending only neutral frames had therefore left the game
waiting at a valid prompt; actor disappearance alone was not proof of a hang.

The crossing helper now issues at most two bounded A press/release attempts
only when the region-change flag, pause mode, and requested destination agree
with the declared exit objective. A live replay from the sealed near-exit
checkpoint used one A press, observed loading, and then three stable gameplay
samples with `playerBoy` in level 47. The frontier worker now schedules that
as a *separate* transition objective after a successful proximity search.
Private cycle `phase95-frontier-cycle-cross-20260924a` crossed twice with the
same final frame 27245, poll 11211, and RDRAM SHA-256
`b9b5d51d39350e84925f40d34c3d793d747d37a305b1517c9f28c85dcf65469c`.
It promoted a sealed level-47 checkpoint and deterministically inventoried
six instantiated exits there. Its graph now has 14 declared edges, four
covered and ten untested; the four covered include two checkpoint links, not
four distinct level transitions. The destination is already known territory,
not new campaign coverage. Native replay/parity of this generated route and
campaign-scale branch policy remain open.

Selected-input export is now a durable stage of the frontier cycle, 2026-09-24.
After a covered job, the cycle records a pending export before starting it;
an interrupted export is retried in a new private directory on resume without
repeating the gameplay job. It checks the written manifest and input digest
before clearing the pending stage. Live
`phase95-frontier-cycle-cross-20260924b` repeated the level-21-to-47 crossing
and follow-up six-exit discovery, then automatically exported its full
checkpoint lineage as 11,211 controller polls with input SHA-256
`f019be5a86cc2fb57612b0f2a54d426109a8c2c4a0069ea3fa3f803f9447275b`.
This is a replayable oracle input artifact, not native equivalence: its export
does not yet carry a validated initial save/Pak pair, and the cycle has not
run native differential replay on it.

The frontier worker now also reconstructs each independent worker's full
selected controller-poll path, verifies its length against the final poll
counter, and requires equal input SHA-256 digests as well as equal final game
state. Synthetic tests confirm that identical final memory reached through
different inputs is blocked. An initial live rerun was blocked: the two
BizHawk source configurations first tried did not match the
sealed checkpoint's config pin, so preflight correctly refused to launch them.
An archived BizHawk source with the exact config, runtime and Lua pins was then
located. Live `phase95-frontier-cycle-cross-20260924c` passed the strengthened
guard: both workers produced 11,211 polls, the same selected-input SHA-256
`d59c2af897d032211ca54ff8c054d37feb33899b506aef23128a97805f46edf4`,
and the same final full-RDRAM SHA-256 as the earlier crossing. The cycle again
exported the 11,211-poll route with input-file SHA-256
`f019be5a86cc2fb57612b0f2a54d426109a8c2c4a0069ea3fa3f803f9447275b`.

The frontier cycle can now optionally pin a candidate initial flash/Pak pair
and native executable, then automatically run the scenario-neutral route
verifier after export and before follow-up discovery. The completed worker
writes a minimal source-scenario result sealed by its final frame, poll count,
input digest and RDRAM hash. Export, verification and discovery each have
durable pending state; a reported diagnostic failure is retained as an artifact
and does not stop unrelated frontier discovery. This is a diagnostic stage,
not a parity gate. A live one-repeat run at
`phase95-frontier-cycle-cross-verify-20260924a` matched the oracle's final
full-RDRAM hash at frame 27,245. The current native executable reached its
27,245-retrace stop without crashing but consumed 13,164 controller polls
versus 11,211 declared, including 1,953 post-EOF neutral polls. The first
same-index mode/RNG mismatch is at poll 16, but the oracle/native retrace
boundaries are not aligned, so this is not a validated first gameplay
divergence. Native parity and Controller Pak equivalence remain unverified.

To include the bounded diagnostic in a new frontier cycle, supply all of
`--initial-flash`, `--initial-pak`, and `--executable`; `--verify-repeats`
controls independent oracle replays (default one, maximum ten). Omit all
three to run oracle-only. `--resume` reuses the recorded pins and does not
accept new ones.

The poll comparator now also collapses repeated `(mode, level, RNG)` samples
and reports the first differing *transition-order* signature separately from
same-index poll mismatches. On the live level-21-to-47 route, the two traces
agree through 594 observed state transitions. The next signatures differ at
oracle poll 1,302/frame 2,978 and native poll 1,300/retrace 2,741, then briefly
match again at oracle poll 1,308/native poll 1,309. This is a localization hint,
not a validated common execution boundary or a proved root cause.

The resumed frontier cycle made a bounded attempt at the level-47 exit near
`[46, 64, -2090]`. It explored 110 saved nodes in 40 expansions, approaching
to horizontal distance 74.7 against a 25-unit objective radius. The worker
explicitly reported incomplete search, not an unreachable exit. Two distinct
exit identities at that *same* observed coordinate lead to levels 199 and 21;
the earlier scheduler repeated the same 40-expansion search for both. The
cycle now preserves bounded misses as blocked evidence, schedules a deferred
larger retry, and can migrate old misses without replaying them. Co-located
misses share one queued retry; a future successfully sealed proximity checkpoint
may cover each co-located proximity objective only after their identities are
confirmed in the final RDRAM, then creates separate crossing objectives for
their different destinations. The live migration retained the original failure
artifacts, retired the duplicate queued retry, and selected a different exit
location for the next job. This is branch scheduling, not proof that either
co-located crossing is controllable.

The next selected level-47 objective was a different exit, at
`[715, 81, -349]` toward level 48. Two independent workers agreed on a
12-step proximity route ending at oracle frame 27,965 with 11,571 polls and
full-RDRAM SHA-256
`8d89f8726cc04efefb38ae25b0142dc3fe94a6c3eb364c8ac14910fa71e9e335`.
Its exported input extends the earlier 11,211-poll route by exactly 360
samples; the shared input prefix, fresh oracle poll-state rows, and native
poll-state rows each matched exactly across the two runs. The new fresh
BizHawk replay matched its endpoint. Native reached retrace 27,965 but
consumed 13,524 polls against 11,571 declared, again 1,953 post-EOF neutral
polls. That repeated count is evidence of a stable input-clock discrepancy
across these related routes, not proof that the native game followed the
oracle branch. The level-48 crossing remains a separate objective.

That crossing then completed as a separate two-worker job in the same cycle.
Both workers reached stable playable `playerBoy` in level 48 at oracle frame
28,385, poll 11,727, with full-RDRAM SHA-256
`bc51e6229466ed97315562791bc2e6fb8189a021b67f02a5ff8af88e492c80c7`.
The fresh oracle replay matched. Native reached the retrace stop but consumed
13,734 polls, including 2,007 post-EOF neutral polls; this remains an
input-clock mismatch, not parity. Independent arrival inventories agreed on
one currently instantiated level-48 exit back to level 47. The graph at this
point has 25 *declared* edges (eight covered, fourteen unexplored, three
blocked); checkpoint links and repeated observations are included, so this is
not a game-coverage percentage. Frontier selection now defers exits back to
already reached levels while other reachable exits lead to as-yet-unreached
levels. A bounded retry from a closer checkpoint outranks a fresh search for
the same semantic exit from a much farther checkpoint. Return exits remain
eligible when more novel objectives are exhausted.

The first larger retry for the shared level-47 exit location used 256-node/
80-expansion bounds but again ended incomplete; the closest saved state still
remained outside the 25-unit radius. This is not evidence either destination
is unreachable. The next retry is bounded at 256 nodes/100 expansions. The
exploration controller now uses 30-frame ordinary-input moves when a node is
within `max(100, 4*radius)` of its target, while retaining 60-frame moves for
long traversal. A frame-aware synthetic case proves the finer moves can reach
a proximity missed by 60-frame overshoot; a ROM-backed success for this
specific shared exit remains to be tested. Frontier jobs and discovery now
record SHA-256 digests of an explicit set of Python planner/verification files and
refuse to promote coverage if those files change during the worker run. Older
run artifacts lacked that code pin and remain diagnostic evidence only.

The 100-expansion tier-two search has now ended explicitly incomplete: 193
saved nodes did not meet the 25-unit exit radius. Two earlier independent
workers did, however, save an identical near-exit state at frame 27,365,
controller poll 11,271, full-RDRAM SHA-256
`3e5a07a03e986bfe2ae1205ad128e6c5949158ad12c13d83dd7d2753d51fd58f`.
The new `phase95_frontier_salvage` tool checked both checkpoint seals and their
entire selected controller paths, then wrote a private paired-frontier bundle.
The player was still 74.7 horizontal units from the co-located exits; this is
not an exit-completion result. A direct ten-step crossing probe from that
checkpoint stayed in level 47, and a one-step jump/precision lookahead chose a
12-frame ordinary movement candidate at 77.1 units of three-dimensional
distance. Those negative bounded probes rule out the simplest direct crossing
from that state, not the branch itself. Subsequent search should target the
missing traversal route or a different approach rather than re-running this
same near-exit input path.

The frontier cycle then ran a jump-aware tier-three retry under a source pin.
It exhausted its declared 100 expansions with 211 saved states, including 87
reached through release/jump/settle input sequences. Its closest state was
still 74.35 horizontal units from the shared exit against the 25-unit
predicate. The worker correctly reported an incomplete search, not an
unreachable exit. The scheduler now discounts a fresh search of a semantic
exit already blocked elsewhere, leaving it available later but selecting an
unattempted exit first; on the preserved live graph this changes the next
selection from another approach to the level-199 exit to the unattempted
level-122 exit. This policy change is a coverage priority, not a claim that
level 122 is reachable.

The first level-122 search from the level-47 checkpoint near the already
covered level-48 exit exposed a stale-pointer ordering error. Its first
ordinary movement changed the observed level to 48 while the hook still
reported the departing player pointer, so decoding before checking level
raised `player pointer is not in current actor table`. The planner now checks
the raw level first and records an incidental transition as a rejected trial.
A clean rerun showed all eight bounded ordinary movement candidates from this
checkpoint transition to level 48; no navigable node was saved. A distinct
`source_auto_transition` failure now records the observed level and trial
count, suppresses larger retries from that source, and marks its four other
exit-search edges blocked with the specific alternate-source reason. The
same exit identities remain available from earlier checkpoints. On the
preserved graph, selection advances to a level-21 exit targeting level 288.
That destination is a declared actor setup, not a proven reachable level.

The next cycle tried the level-21 exit whose setup declares destination 288.
Ordinary checkpoint search reduced horizontal distance from 3,442 to 2,803
units, then exhausted its 128 saved-node bound without an exit proximity or
transition. Its failure is explicitly incomplete, and a larger retry remains
available. The scheduler now selects a different level-21 exit whose setup
declares destination 16 before repeating that distant search. This demonstrates
autonomous frontier continuation after an unsuitable checkpoint, but not
reachability of either declared destination.

The next bounded cycle steps searched the level-21 exit setups declaring
destinations 16 and 289, then the tier-one retries for setups declaring 288
and 16. All four were incomplete under their respective 40- or 80-expansion
budgets; none establishes that the destination is unreachable. The durable
supervisor can now queue these BizHawk steps from an explicit private cycle
registration without using a coding agent. An isolated service smoke sealed
two consecutive bounded steps with a healthy ledger audit. A third step was
interrupted by killing its guarded owner during live BizHawk work; Windows
removed the worker tree, the lease expired, and attempt two resumed the same
edge and sealed a bounded result. The final isolated ledger verified three
passed seals, zero audit issues, and zero coding-agent attempts. A direct
CLI resume while the supervisor owned the cycle was rejected by the new
per-cycle lock. This proves bounded recurrence and one manual-invoked recovery
drill, not full autonomous coverage, native parity, or an unattended multi-day
service.

Paired spatial continuation, 2026-09-24: the frontier cycle now scans two
bounded-incomplete searches from the same sealed source and exit, invokes the
paired-checkpoint verifier, and registers a new reachable checkpoint/search
edge only when the independent workers agree on the full state and selected
input path and the checkpoint is at least 60 horizontal units closer. The
source searches stay blocked, and the paired progression edge means only
ordinary-input spatial progress, not exit proximity or a level transition.
The live zero-job migration of the preserved cycle promoted two existing
pairs: the level-288 setup improved from 3,442.3 to 2,803.0 units, and the
level-16 setup from 3,674.7 to 3,069.2 units. Both paths reconstruct 11,045
controller polls with their sealed selected-input digests. The next selected
edge searches from the new level-16 checkpoint. This removes a cold-search
repeat bottleneck; that next search still has to prove any further progress.

The first service-dispatched search from the paired level-16 source did run
through BizHawk with the coding-agent cap at zero. It saved 112 states under
its 40-expansion budget but improved the 3,069.2-unit starting distance by
only about 1.6 units, then sealed an incomplete result; it did not cover the
exit. The isolated ledger now has four verified seals and no integrity issue.
The scheduler now gives the other fresh paired source (for the level-288
setup) a turn before escalating this nearly stalled source to an 80-expansion
retry. A fresh paired source remains a route hypothesis, not reachability
proof.

The next service-dispatched search from the other paired source (the exit
setup declaring level 288) also stopped within its 40-expansion budget. It
saved 124 nodes, improving the 2,803.0-unit starting distance by only about
0.1 unit. Across both paired-source runs, the explored states spread several
hundred units laterally but reached only depth six or seven; simple
distance-greedy search is not yet navigating around the apparent route
obstacle. This is evidence for a policy upgrade, not proof that either exit
is unreachable. The isolated agent-free ledger ended at five valid passed
seals with no integrity issue.

The paired-source retry now uses a distinct, bounded detour priority:
straight-line exit distance is offset by measured horizontal displacement
from the source, with the same visited-cell pruning, fixed node/expansion
limits, and exact selected-route replay requirement. Ordinary searches retain
the earlier distance priority. Synthetic wall-maze and job-dispatch tests
exercise this mode; a live detour result is still required to assess whether
it escapes the measured Goldwood local minima.

The first real paired-source detour retry did escape the first local minimum.
Its 256-node bounded search reached depth 23; the best sealed node was about
1,674.2 units from the declared level-16 exit, versus 3,069.2 at the source.
The search still did not satisfy the 25-unit exit predicate, so its outcome
remains blocked/incomplete. The agent-free ledger verified six passed seals
with no issue. The next required step is an independent replay of the chosen
node's selected input path and state before promoting that farther checkpoint;
repeating the whole search is not needed to establish the selected path.

The focused `phase95_frontier_verify_node` tool now proves that path without
another search. Its first live run imported the original source into a fresh
BizHawk worker, replayed the 18-action parent chain to saved node 190, and
matched every intermediate RDRAM hash and frame/poll/player counter. The
final paired checkpoint has identical full RDRAM SHA-256 and the same 11,433
selected controller polls in both workers. It remains a spatial checkpoint,
not an exit or native-parity result. Automatic cycle promotion of this proof
is the next integration gate.

The cycle now implements that integration as a durable pending-node stage.
It selects a bounded-incomplete search node only after at least 60 units of
measured improvement, replays its parent chain in a fresh isolated worker,
checks both checkpoint seals and selected input, and adds a same-level
progression plus a new search edge while leaving the old exit edge blocked.
An agent-free supervisor maintenance packet handles interrupted pending work
without advancing a different edge. A live zero-job migration independently
verified two preserved search paths, including the depth-18 detour state at
1,674.2 units, and the next selected edge now starts from that replayed
checkpoint. No exit transition or native parity was inferred from this.

The next agent-free service cycle did start from the newly replayed 1,674.2-
unit checkpoint. Its 40-expansion search saved 92 nodes but improved distance
by less than one unit. The cycle correctly skipped another node promotion,
preserved the bounded miss, and selected a different independently replayed
level-21 source next. The isolated ledger verified seven passed seals with
zero issues and zero coding-agent attempts. This is a useful negative control
for the automatic promotion threshold, not a campaign coverage result.

The following agent-free cycle searched from the other replayed level-21
source toward declared level 289. It saved 114 states, moving from about
3,202.6 to 3,200.6 units from the exit, and sealed an incomplete bounded
result. The ledger has eight valid seals and no issue. The selected next
frontier is the paired level-288 retry; no new exit was crossed. To keep
unattended retries from consuming the drive, the frontier worker now checks
a 50-GiB disk reserve and caps each fresh job output tree at 4 GiB.

The subsequent level-288 detour retry explored more than 200 saved states but
was rejected as evidence: a planner source changed while its worker was live,
so `planner_source_stable` was false and the supervisor did not seal it as a
valid bounded job. This is an operator-induced pin violation, not a game
failure. The result and attempt journals remain private for diagnosis.

The cycle now has a second, explicitly labeled checkpoint-promotion path for
such obstacle detours. If a bounded detour search makes no 60-unit exit-distance
gain, it can select a node at least 240 horizontal units from its source and
at least 180 units from already verified same-level positions. A fresh BizHawk
worker must replay the exact chosen path and checkpoint before promotion; the
new edge remains an unexplored exit objective, not exit coverage. Synthetic
selection/promotion tests pass. Live stable-pin proof is pending.

Fixed-pin live proof followed: the next level-16 detour search was a stable
bounded miss, but selected node 172 lay 676.46 horizontal units from its
source. A fresh BizHawk worker replayed the six-action parent path and matched
the saved state and 11,553 selected controller polls. The promoted level-21
checkpoint is about 481 units *farther* from the declared exit, deliberately
labeled `spatial-detour`; it is not exit coverage. The agent-free supervisor
sealed the bounded job with a healthy ledger and no coding-agent attempt.

One 40-expansion continuation from that checkpoint improved its local exit
distance from 2,155.37 to 1,673.95, but the best node landed within about a
unit of an earlier verified checkpoint. Its full state differs and remains a
valid route variant, yet it is a poor new waypoint. The cycle now filters
already verified same-level positions within 180 horizontal units when
choosing *either* exit-progress or detour nodes. If a job's first replayed
checkpoint overlaps another verified position, it may contribute one second,
spatially novel verified node; this is bounded to two per job. A secondary
continuation receives scheduling preference. Synthetic tests pass; live
secondary replay remains to be checked.

The first migration attempt found a naming collision: a second verification
from an already verified job tried to reuse its existing `node-verify-...-01`
directory. No checkpoint was overwritten. Pending work remains durable and
now starts the secondary verification at attempt `02`; the failed `01`
artifact remains unchanged.

After the fresh-slot fix, a `--max-jobs 0` maintenance resume completed two
independent secondary replays without launching another search. Job 8's
17-action selected path produced a checkpoint at approximately `(830,55,-1302)`
with 11,414 controller polls; job 13's five-action selected path produced one
at `(881,58,-1102)` with 11,653 polls. Each has a separate checkpoint seal,
selected-input digest, and continuation edge. The old near-duplicate state
variant remains in the graph, but the newly chosen edge starts from the
spatially distinct job-13 continuation. Exit crossing and native parity remain
unverified.

The first live continuation from the second secondary checkpoint again stopped
short of the level-16 exit. At a saved node near Z=-1,449, three ordinary
forward-leaning 60-frame actions moved only about 4 to 12 horizontal units,
while a retreat action moved over 100. The prior jump retry policy only
generated jump trials within roughly 160 units of the *final exit*, so it
could not test a jumpable obstacle at this midpoint. Jump-enabled searches
now add a release/jump/settle trial for each ordinary direction that stalls
below 20 horizontal units, even far from the exit. The search remains bounded
by its node and expansion caps. Synthetic distant-wall tests pass; whether
this particular Goldwood barrier is jumpable remains a live diagnostic question.

The first isolated jump-enabled search from the sealed checkpoint exhausted
40 expansions with 96 saved nodes and 36 jump trials; it did not cross the
barrier and explicitly reported `unreachable: false`. Its finest trial reached
Z=-1,459, about 11 units past the saved-state frontier at Z=-1,448, but the
60-unit cell/yaw pruning discarded that post-jump state. Jump outcomes moving
at least 10 horizontal units can now be saved in a separate 15-unit cell grid,
still under the same node/expansion caps. A synthetic short-jump test proves
such a state survives. A second sealed live probe is needed to determine
whether this changes the Goldwood result.

The second isolated probe completed under the same 40-expansion bound with
101 saved nodes, 51 jump trials, and 15 fine-cell jump continuations. It saved
and expanded the Z=-1,459 state that the first probe discarded, but still did
not cross toward the level-16 exit. Its result remains bounded-incomplete,
`unreachable: false`. The 15-unit retention fix is real, but this evidence
does not support continuing to tune jump pruning as the primary route solution.
The next planner work should identify the traversable route topology or the
mechanic/gate at this mid-level boundary, using the preserved states and actor
inventory rather than another straight-line retry from the same checkpoint.

Read-only visual inspection is now available through
`scripts.phase95_checkpoint_visual`. It checks the original checkpoint seal,
ROM/emulator/runtime/config pins, and exact RDRAM after a separate BizHawk
state load, then writes a private PNG and digest manifest. It never supplies
controller input and is diagnostic, not a gameplay route. Live captures at the
Z=-1,459 boundary and nearby saved states passed those checks. The images show
the close-to-exit states pressed against foliage/tree geometry, while a
lower-ground saved state around `(569,0,-1273)` faces an open path. This is a
visual route hypothesis, not a decoded collision map.

A bounded detour search imported that lower state and saved a westward ground
branch as node 1 at about `(357,0,-1238)`, but never expanded it in forty
expansions; it continued to favor the nearer tree branch and ended incomplete
after 106 nodes. The planner now has a `coverage` mode that expands saved nodes
in breadth-first order under the same caps, and level-exit retries switch to
that mode at tier two. Synthetic ordering and dispatch tests pass. A live
coverage run from the lower state is the next route-topology check.

The live breadth-first probe did expand the previously ignored ground branch.
In 40 expansions it saved 128 nodes and reached about `(160,18,-1613)`, past
the previous Z=-1,459 frontier, without claiming the exit. A fresh BizHawk
worker independently replayed the selected three-action path from the lower
checkpoint, matching its full RDRAM and selected controller input. The
preceding jump-probe path to that lower checkpoint was independently replayed
as well. `scripts.phase95_frontier_import_chain` now validates both proof
seals, exact checkpoint-to-checkpoint lineage, source graph reachability, and
exit identity before adding covered *progression* links plus one unexplored
exit continuation. Synthetic acceptance and discontinuity tests pass; the
live graph import is the next check.

The two replayed segments were imported into the live frontier as covered
progression, leaving the level-16 exit objective unexplored. The supervisor
then ran job 15 from the new west checkpoint `(160,18,-1613)`. Its bounded
search saved 128 states and independently replayed a node at approximately
`(890,57,-2222)`, reducing horizontal distance to the declared exit from
2,032 to 1,117 units. The search remained incomplete, so neither exit coverage
nor native parity was asserted. Supervisor maintenance automatically promoted
that verified node; an extra manual replay confirmed the same selected state
but was not imported twice. The frontier selector now accounts for verified
distance-to-exit when choosing between paired checkpoint continuations, so
the closer new route wins over an older, farther one despite its historical
priority. The next bounded continuation must test whether this route actually
reaches the exit or merely exposes another local obstacle.

Jobs 16 and 17 were bounded misses from two verified checkpoints. Job 16
started at the closer `(890,57,-2222)` state, saved 118 states, and found no
state closer to the selected exit. A sealed, read-only screenshot shows the
player alongside a wall at that checkpoint; the image supports an obstacle
hypothesis, not a collision-map proof. Job 17 tested an older checkpoint near
`(830,55,-1302)` and likewise made only minor local progress. The selector
now gives one tier-one *detour* retry at the much closer verified checkpoint
precedence over fresh branches at least 400 horizontal units farther away.
This keeps the next experiment on the promising route while explicitly
allowing a path that initially moves away from the landmark.

Job 18 exercised that tier-one detour for 80 expansions and saved 188 states.
It did not beat the starting 1,117-unit exit distance, but maintenance
independently replayed and promoted a spatially novel checkpoint around
`(646,57,-1707)`, about 569 units from its source. That continuation reached
the old fixed eight-hop `salvage_depth` ceiling. The ceiling is now 64 hops
per progression chain; every search remains separately bounded, and existing
novelty checks still gate promotion. This permits the route graph to follow
longer level paths without interpreting the detour as exit coverage.

Job 19 continued from that detour checkpoint and returned to the wall-side
area. Its best saved state was roughly 1,114 units from the exit, only about
three units better than the earlier 1,117-unit checkpoint. Maintenance then
promoted a different saved node at `(900,56,-2030)` as spatially novel.
Cross-checking the trace showed that job 18 had already saved a state just
0.73 horizontal units away. The promotion heuristic had compared only prior
*verified checkpoints*, not all prior bounded-search observations. It now
rejects candidate nodes within 60 horizontal units of any earlier stable,
same-level, same-exit search trace (while still allowing a second candidate
from the same job). A synthetic two-job regression test covers this exact
cross-job duplicate. Existing sealed evidence is retained; no prior graph
fact is silently rewritten.
