# Durable autonomous execution plan: Phase 9.5 through full parity

Operating strategy updated 2026-09-24: follow the
[strategy reset](autonomy-strategy-reset.md) for execution priority and plateau
limits. Native comparison/repair and demonstration-guided route acquisition
replace the recent emphasis on repeated local checkpoint searches. Historical
evidence below remains valid within its stated limits.

Status: proposed operating plan, 2026-09-23. This is not evidence that the
remaining scope gates have passed. The authoritative product requirements remain
the [master plan](JFG_RECOMP_MASTER_PLAN.md), [scope assessment](JFG_RECOMP_SCOPE_ASSESSMENT.md),
and [dashboard](../dashboard.md).

## Outcome and boundary

The objective is to keep making verified progress without repeated human
playthroughs or prompts until the release-scoped game has complete native
compatibility, the selected enhancements pass their own gates, and the legal and
release decisions are made. "Indefinitely" means a restartable supervisor that
continues scheduling bounded work while useful in-scope work remains. It does
not mean an immortal chat, an unbounded agent turn, automatic approval of risky
changes, or a claim that an AI can supply legal or release sign-off.

Two different autonomous loops are required:

1. The **gameplay explorer** uses BizHawk observations, ordinary controller
   input, checkpoints, a game-specific frontier graph, and bounded navigation,
   combat, interaction, and recovery policies. It exports complete replay and
   coverage artifacts. No LLM controls the reticle frame by frame.
2. The **engineering agent** consumes oracle/native divergences, traces, and
   coverage gaps; selects a bounded task; adds a failing test or instrumentation;
   patches code; reruns validation; and records a reviewable evidence bundle.

The first loop discovers and reproduces behavior. The second closes the gap.
Neither substitutes for the other.

## Harness decision

Use a **local, durable Windows supervisor** as the system of record. Here
"coding-agent harness" means the agent runtime that edits and tests this repo,
not the BizHawk gameplay harness. The supervisor initially invokes the already
installed Codex CLI (`codex exec`) for bounded engineering task packets, but
the worker protocol is agent-neutral. Let Windows
Task Scheduler restart the supervisor at boot and periodically check its
heartbeat. Run BizHawk and native test workers as separate resource-limited
processes. This keeps the private ROM and captures on the authorized machine
and survives a Codex chat, terminal, model, or emulator crash.

Implement a versioned coding-agent adapter: launch, attach/resume when safe,
stream events/stdout/stderr, stop/timeout, capture usage and exit status, and
report a sealed result manifest. Candidate runtimes are Codex CLI/SDK,
OpenCode CLI/SDK, Oh My Pi RPC, Claude Code headless/Agent SDK, Gemini CLI
headless, and later the OpenAI Agents API with a self-hosted executor. The
installed machine currently has Codex 0.156.1 and OpenCode 1.18.31; Oh My Pi
is not installed. This is a provisional starting choice, **not a permanent
Codex mandate**. Do not make the first implementation depend on unverified API
access, account entitlements, a new cloud credential, or a single vendor's
session format. A Codex Goal in this thread remains useful for interactive
continuity, but it is not the job queue.
An in-app scheduled task can provide a status heartbeat; it is not the only
runner because local-project scheduled tasks require the computer and app to
remain running. Official documentation describes [Goals](https://developers.openai.com/cookbook/examples/codex/using_goals_in_codex),
[scheduled tasks](https://learn.chatgpt.com/docs/automations), and the
[Agents API/runtime choices](https://developers.openai.com/api/docs/guides/agents).

Before committing to a long-term coding agent, run the same three pinned,
isolated repo tasks through every *available, authenticated* candidate:
(1) diagnose a known oracle/native poll mismatch without editing; (2) add a
failing synthetic test and fix it; (3) resume after a forced worker kill.
Score correct verified outcomes, independence of evidence, Windows tool/process
recovery, structured observability, permission controls, privacy boundary,
elapsed time, and actual spend. A failed or absent credential is recorded, not
worked around. Select the measured winner for implementation jobs and the
best independent reviewer; re-run the benchmark when runtimes materially
change. The [OpenCode SDK](https://opencode.ai/v2/docs/build/sdk) supports an
embedded host and event stream, [Oh My Pi](https://github.com/can1357/oh-my-pi/blob/main/docs/rpc.md)
has JSONL RPC, [Claude Code](https://docs.anthropic.com/en/docs/claude-code/cli-usage)
has headless structured output, and [Gemini CLI](https://github.com/google-gemini/gemini-cli/blob/main/docs/cli/headless.md)
has JSON/stream-JSON headless output. These are integration candidates, not
claims that their coding quality has been measured on this repo.

The harness is replaceable; job manifests, evidence schemas, acceptance gates,
and privacy rules are not. Replacing the Codex transport must not reset progress
or redefine parity.

## Community input and route intelligence

The [published TASVideos full-game movie](https://tasvideos.org/6745M) by
Jimmie1717 provides a downloadable BizHawk `.bk2` controller-input movie and
video. Its [submission metadata and route notes](https://tasvideos.org/9865S)
specify 638,477 frames, BizHawk 2.9.1, a power-on start, the Japanese
*Star Twins* v1.0 ROM (SHA-1
`15099233760b36e7afad7da36b9464da1512c4b1`), and controller 2 for Floyd.
Our oracle/native project targets the US ROM and a different BizHawk version.
Therefore the movie is **not an executable US parity fixture**; direct input
replay may desync because the Japanese build has behavioral differences,
including a cutscene-skip feature documented by its author. An ordinary
[100% speedrun video](https://www.speedrun.com/jfg/runs/zxwjdeqm) is useful
for route interpretation but is not controller input. No confirmed downloadable
US-version input movie was found in this search as of 2026-09-23.

Use the TAS first as a progression/branch atlas: record levels, gates,
collectibles, required character/weapon mechanics, and route alternatives in
the frontier graph. A separate import spike may download the `.bk2` input
movie into ignored private storage, record its URL/page attribution and digest,
parse its input log, and attempt replay **only** with a lawfully supplied
matching Japanese ROM and pinned emulator configuration. Never fetch or ship a
ROM. Do not copy a Japanese input segment into a US regression corpus until
the US oracle independently reproduces its initial state, input timing,
progression, and endpoint; otherwise use it only as route guidance. Preserve
source attribution and follow TASVideos' [movie-page linking and republication
conditions](https://tasvideos.org/6745M). Third-party movies are not committed
to this repository.

### Regional variant policy

Keep the US ROM as the current native parity and release target. Maintain JP
TAS observations in an independently pinned `tas-jp` lane: route topology,
mechanic hypotheses, actor names, and encounter ideas may seed US objectives,
but JP RAM offsets, level IDs, savestates, input timing, and endpoint hashes
cannot close a US gate. Promote a cross-region finding only after an explicit
US-oracle reproduction with its own ROM/config/checkpoint provenance. Japanese
native support would be a separately estimated version target with its own
binary, assets, timing, saves, regression corpus, and acceptance runs; importing
this TAS alone does not add that scope. This mirrors the version-specific build
approach in the [OoT decomp](https://github.com/zeldaret/oot/blob/main/README.md)
and the staged region support of [Ship of Harkinian](https://www.shipofharkinian.com/faq),
while [Zelda 64: Recompiled](https://github.com/Zelda64Recomp/Zelda64Recomp)
shows that a static-recomp port may intentionally accept one ROM version.

Implementation update, 2026-09-23: the user-supplied Japanese dump matches
the published movie's SHA-1, the user's visible opening replay synchronizes,
and the complete BK2 input stream has been indexed in ignored private storage.
The graph, isolated bounded capture runner, and raw-change reporter now exist
with synthetic tests. A full-ROM-state capture proved too slow at its first
frame and was stopped with partial evidence retained; smaller screenshot/raw-
probe capture has now passed through frame 6,000 and resumed through frame
6,100. The US-mode and level RAM addresses are demonstrably not validated for
the Japanese build. Neither the visible opening nor the input index proves
whole-movie sync, whole-game autonomous control, or US parity. The next TAS
gate is a complete pinned Japanese state timeline with independently validated
level/progression fields and checkpoint-resume equivalence. Only then can it
seed named graph edges for US-oracle re-synthesis and uncovered-branch search.

## Durable supervisor contract

Create `scripts/autonomy/` with a versioned SQLite state store under ignored
`tools/private/autonomy/` and a redacted, committed status projection. Each job
has a stable ID, pinned source commit/tool/ROM/emulator/native digests, declared
inputs and prerequisites, resource class, retry budget, lease/heartbeat,
completion predicates, and paths to sealed artifacts. State transitions are
`queued -> leased -> running -> verifying -> passed|failed|blocked`. A crashed
worker loses its lease; a restarted supervisor reconciles the artifact and
either resumes an idempotent step or creates a new attempt. It never treats a
half-written result as a pass.

The scheduler selects the earliest blocking gate or first validated divergence,
then the highest-value bounded task within it. It may run independent read-only
analysis or tests concurrently, but only one writer owns a given source branch,
checkpoint lineage, or golden baseline. Use separate Git worktrees for coding
jobs, never multiple agents editing the same checkout. Every coding job has the
master plan's machine-readable task packet, file/line budget, hypothesis,
required failing test, validation commands, and stop conditions. The worker
may commit a passing change on its isolated branch; merge and push remain
separate, risk-appropriate review steps.

The supervisor must enforce per-job wall-time, CPU/RAM/disk, emulator-count,
retry, and model-spend limits. It archives stdout/stderr, selected inputs, logs,
checkpoint lineage, hashes, and the original failure before reduction. It
reports progress and blockers at least daily. Repeated failures become a
research/instrumentation task instead of an endless repair loop. A user pause,
missing heartbeat, stale state, incompatible checkpoint, privacy violation, or
approval-required change stops the affected job safely while unrelated work
continues.

Bootstrap update, 2026-09-23: `scripts/autonomy/job_store.py` implements only
the versioned local SQLite ledger and its synthetic tests: stable pinned jobs,
prerequisite and single-resource leases, expiry/retry, attempt history, and
hash-checked result sealing with a redacted status view. No durable worker
adapter, autonomous scheduler, Task Scheduler registration, resource/spend
enforcement, or multi-day recovery proof exists yet. The live Japanese TAS
batch is a separate bounded worker, not evidence that the full supervisor is
accepted.

Worker update, 2026-09-23: the first bounded Codex CLI worker is now implemented
at `scripts/autonomy/supervisor.py`; see the
[bootstrap runbook](autonomy-supervisor-bootstrap.md). It queues private pinned
packets, checks input/tool hashes before launch, runs one agent in a private
worktree with a wall-time/log cap and lease heartbeat, executes declared
validation, and seals a candidate-only result. A `queue-divergence` intake
compares supplied traces and queues a read-only diagnosis with evidence pins;
`queue-comparison` runs the streaming retrace comparator as a bounded,
pin-checked deterministic ledger job. Neither command generates captures or
implementation jobs automatically. This does **not** close the
remaining scheduler, independent review, CPU/RAM/spend enforcement, startup,
or multi-day recovery gates above.

No-API-billing update, 2026-09-23: the worker explicitly requires the saved
ChatGPT Codex login, removes API-key environment variables, and forces the
`chatgpt` login method per invocation. New read-only diagnoses have a JSON
Schema output contract and a fail-closed alignment guard before they can be
treated as code-divergence candidates. ChatGPT plan rate limits still apply;
no assumption of unlimited model usage or separate API billing is made.
The 2026-09-24 local preflight reports `Logged in using ChatGPT` even after
the worker strips API-key environment variables. Synthetic tests also prove
an API-key-only login is rejected before an agent worktree is created. Thus
API billing is not a prerequisite for the current worker; subscription usage
limits may still pause coding-agent jobs. Deterministic replay, capture,
comparison, and ledger transitions remain local and can continue without a
model. This is a transport boundary, not a promise of indefinite model access.

Candidate-review update, 2026-09-24: a passed implementation now queues one
pinned, independent read-only review. The worker reconstructs the sealed patch
and untracked archive in a fresh private worktree, creates a detached local
candidate commit, reruns declared validation, and records a structured verdict
plus hashes. Neither the
review job's `passed` ledger state nor an `approve` verdict merges code or
proves parity. Automatic native/oracle differential retest and risk-gated
promotion remain open.
The first real CLI review smoke passed on a synthetic one-file candidate:
ChatGPT login preflight, reconstruction, declared validation retest, read-only
structured review, and ledger sealing all completed in one private run. This
proves that transport path works on this machine, not that the reviewer is a
deterministic oracle or that game-code promotion is safe.

Scheduler update, 2026-09-23: a bounded `advance` transition now links a
sealed mismatching comparison to exactly one pinned, read-only diagnosis;
`drive` can execute a finite number of such jobs under explicit `--execute`.
The real south-route transition passed, and a separate short oracle VI-hook
capture proved matching initial flash and yielded 90 VI hashes. Poll/VI
schedule alignment remains open, so the earliest *validated* native gameplay
divergence is still unknown. The scheduler now launches a pinned, non-AI
follow-up capture for supported early misalignment diagnoses. It does not yet
author implementation packets, review patches, or run unattended.
An explicit poll-to-VI diagnostic report now joins the first 27 captured
oracle polls to consumed-VI sequences and the native poll trace. Identical
input samples coexist with changing VI offsets and a transient poll-16
mode/RNG difference. That rules out a single fixed retrace-offset repair;
it still does not validate a gameplay-code divergence or initial Pak identity.
The first automatically queued alignment job reproduced the independent
120-frame report byte-for-byte. A real guarded BizHawk hard-kill/retry drill
then retained an expired first attempt and passed a second 600-frame attempt;
the latter analyzed 256 polls with no input-value mismatch. This is evidence
for that worker's crash containment and retry, not multi-day supervisor soak.
The next deterministic ledger transition now captures both sides at a
completed guest-update hook. On the selected south-route prefix, all 296
native updates match the first 296 of 411 BizHawk updates by semantic state
hash. This is a validated matching *prefix at that hook*, not a whole-route
or presentation parity claim; selected input timing, initial Pak equivalence,
later gameplay, rendering, and audio remain separate gates. The successor
runs without an AI model or API billing. Engineering-agent jobs still require
the existing ChatGPT Codex login and are bounded by its plan limits.
Automatic prefix doubling reached the first raw mismatch at update 568.
Poll-position instrumentation locates an exact state resynchronization at
controller poll 575, native update 572 versus BizHawk update 568, followed by
23 matching sampled states. This is a cadence diagnostic, not a validated
code-divergence or whole-route pass; finding the poll/update scheduling cause
is now the active Phase 9 boundary task.

Evidence-import update, 2026-09-23: `scripts/autonomy/import_evidence.py` can
audit the surviving ten-job Phase 9.5 batch and two-repeat waypoint frontier,
then seal eleven integrity-only ledger jobs. The old manifests omit their
original source commit, so the imported jobs pin the audit's source/tool and
explicitly mark original-run replay and parity unverified. This is historical
artifact preservation, not retroactive producer provenance.

## Parity and verification contract

Define a single controller-input poll schedule and explicit comparison
boundaries before calling any native/oracle difference a gameplay divergence.
For each generated route, compare approved per-retrace (or validated aligned
poll) state fields, full RDRAM at sealed checkpoints, actor/player/RNG/camera
subsystems, progression, save data, and relevant runtime side state. Preserve
the first mismatch and a bounded trace around it. Compare graphics/audio at
designated reference points. Record nondeterminism separately from consistent
native divergence. Never update a golden reference merely to make a test pass.

The earlier retrace-target native south replay consumed fewer controller
polls and reported zero kills versus the oracle's three. A newer poll-target
run consumes every selected poll but still reports zero kills; neither run
establishes a validated aligned first divergence. Closing that boundary is
the first engineering packet. Native checkpoint resume is an optimization
only after full side-state inventory and uninterrupted/restored equivalence.

No single "parity percentage" replaces the gates. Acceptance requires the
specific G0-G9 and Phase 9-15 evidence in the scope assessment, including
campaign completion, release-scoped optional/multiplayer/save coverage,
graphics/audio references, determinism, soak, enhancements, packaging, and
human legal/release approval.

## Execution order and gate ledger

| Order | Autonomous work | Proof required before advancing a gate |
|---|---|---|
| 0: preserve baseline | Reconcile historical G4/G5 counts and run current ROM-free/ROM-backed validation without changing goldens. | Scope-assessment G4 fifty boot repeats and G5 ten reference captures are explicitly proved or left open. |
| 1: finish 9.5 A/B | Audit the ten seeded Goldwood jobs, common-checkpoint destinations, natural retry, and frozen-route oracle repeats; align native input timing and find the first true native divergence. | All A/B predicates and a truthful native differential report; a native mismatch is not a parity pass. |
| 2: finish 9.5 C/D/E | Persist covered/unknown/blocked frontier graph, add varied path/weapon/order seeds, automatic failure reduction plus pinned ASan rerun, perturbation soak, and validated native snapshots. | Every declared slice branch has a generated route or explicit blocker; seeded fault and interrupted-batch recovery pass; snapshot equivalence passes where claimed. |
| 3: finish Phase 9/G6 | Extend through cutscene, pause, controller loss, save/relaunch, overlay reload, graphics/audio references, and complete selected slice. | One hundred consecutive deterministic complete-slice runs with identical approved checkpoints and no crash; no unhandled calls. |
| 4: Phase 10/G7 | Grow the same frontier/segment mechanism across required characters, bosses, gates, collectibles, final sequence and credits. | Every segment independently replayable; three clean new-game routes to credits; zero compatibility-route blockers. |
| 5: Phase 11/G8 | Cover all release-scoped optional content, multiplayer, menus, save/accessory states, controllers, overlay branches, fuzz and soak. | Scenario/overlay denominator covered; eight-hour soak and stress suites; zero release-blocking parity defects and required-test flakes. |
| 6: Phases 12-13/G9 | Add aspect-ratio and high-refresh presentation on a frozen compatibility baseline. | Visual matrices pass and compatibility-mode simulation hashes remain invariant. |
| 7: Phases 14-15/G9 | Add the reviewed mod ABI and evidence-backed readable replacements; perform packaging, license, SBOM, clean-machine, rollback and support checks. | Mod SDK/replacement differentials pass; release checklist and soak pass; human legal and release decisions recorded. |

The next executable packet is **native/oracle boundary alignment on the
generated south route**: pin the exact initial save and controller-poll
contract; obtain a validated common boundary; emit first mismatch with actor,
player, RNG, camera, and runtime side-state evidence; add a regression test;
then fix that divergence without disturbing earlier matches. In parallel, the
gameplay worker can extend the Phase 9.5 frontier graph from the verified
Goldwood branches and exercise bounded perturbations.

Boundary update, 2026-09-23: the native runner now has an opt-in exact
controller-poll stop and neutral input after replay EOF. The south input
completed 10,881/10,881 native polls, but reached zero kills versus the
oracle's three, at a different VI count and before the last read response was
consumed by guest code. Therefore the first aligned gameplay divergence and
initial save/Pak equivalence are still the next engineering packet; poll
completion alone does not close it.

## Authority, privacy, and failure policy

- The ROM, derived RDRAM, screenshots, captures, SaveRAM, private corpus, and
  credentials stay under ignored private storage. Public CI gets only redacted
  schemas, hashes, test code, and synthetic fixtures. Run the repository hygiene
  validator before every commit or publication.
- The master plan's human-only decisions remain human-only: legal/licensing,
  instruction-level patches, compatibility hash exclusions, threshold or
  golden changes, save format, scheduler/timing architecture, large
  cross-subsystem changes, security-sensitive changes, and release approval.
- The agent may create local topic-branch commits after its tests and an
  independent review. It may not merge its own change or silently push a
  release. A failed review returns a bounded repair task.
- A machine shutdown, terminal crash, or model interruption is a recoverable
  worker failure, not a lost campaign run. A missing external permission or a
  human-only decision is a reported blocker, not something the supervisor
  invents authority to bypass.

## Bootstrap acceptance for the autonomy system itself

1. Import the existing 9.5 result and ten-job batch as read-only sealed jobs;
   generate a status projection that matches their manifests exactly.
2. Start one bounded oracle/native comparison job from the queue and produce a
   pinned evidence bundle without a manual controller or prompt.
3. Kill and restart the supervisor, Codex worker, and one BizHawk worker at
   separate points; prove no lost/duplicated completion and preserved failure
   artifacts.
4. Prove single-writer leases, incompatible-build rejection, spend/resource
   limits, pause/resume, privacy scan, and a blocked-task report.
5. Run a multi-day unattended soak with an independent daily audit of queue
   state versus artifacts. Only then rely on the supervisor for routine work.

Bootstrap evidence, 2026-09-23: item 1 has eleven integrity-only historical
imports (ten seed results plus the two-repeat waypoint result), recorded in the
[redacted status projection](autonomy-historical-status.json). Re-import left
each at one attempt. The missing historical producer commit remains an explicit
provenance gap, so this is not retroactive replay verification. Item 2 has one
real queued comparison of the existing south-route native/oracle traces. The
worker sealed a raw retrace-1 mismatch in `actor_list`, `actor_count`, and
`actor_table_sha256`; `alignment_validated` and `parity_verified` are both
false. Items 3-5 are still open.

Crash-containment update, 2026-09-23: the bounded Windows worker uses a
kill-on-close Job Object with fixed memory and CPU caps. A synthetic hard
parent exit terminated its assigned child. This is only the process-tree
primitive for item 3; lease/artifact reconciliation and forced-kill drills for
Codex and BizHawk remain unproved. Per-job aggregate resource and model-usage
limits in item 4 also remain open.

Recovery update, 2026-09-23: the worker now journals child guard state and
confirms the prior owner has exited before an expired attempt can retry. It
can reseal an intact complete candidate/comparison bundle without a second
agent run. A synthetic supervisor hard-kill/restart test passed with one
expired and one completed attempt; ambiguous guard states still block. The
Phase 9.5 BizHawk `Worker` also uses the kill-on-close guard, and an isolated
one-frame US probe passed. At this checkpoint, a real Codex hard-kill drill,
a BizHawk worker hard-kill/resume drill, and a multi-day restart audit still
remained for item 3.

Live recovery update, 2026-09-24: an opt-in synthetic-candidate job ran the
real ChatGPT-authenticated Codex CLI as reviewer. A separate drill killed its
supervisor after the Codex child was guarded, confirmed the child stopped,
reclaimed the expired lease, and retried in a fresh worktree. The private
ledger sealed exactly `expired -> passed`; no interrupted result was promoted.
This closes the real Codex hard-kill drill subcase, not the full bootstrap item
3: BizHawk hard-kill/resume and multi-day restart reconciliation still need
independent proof.

Continuous-loop update, 2026-09-24: an opt-in `serve --execute` command now
holds one state owner, audits passed artifact hashes and resource locks at
startup and daily, records unresolved jobs, and caps ChatGPT-agent lease
attempts per UTC day. When that cap is reached, the ledger can still lease
deterministic jobs. The live state audit verified 42 passed seals in 43 jobs
with zero integrity issues; one failed diagnostic remains unresolved. This is
not an actual token-spend cap, startup registration, or multi-day soak proof.
An opt-in Windows task installer and private event-logging entry point are now
implemented with plan-only default and zero coding-agent attempts/day by
default. The task has **not** been registered; its logon/daily triggers and
restart settings have only been constructed locally. Installation, live
restart/soak proof, aggregate resource/spend limits, and authorization to
run coding jobs at sign-in remain open.
An isolated agent-cap-zero entry-point smoke completed one audit/idle cycle
with a private event log; it did not run the production queue.
One bounded real-state cycle with the agent cap set to zero subsequently
completed a native/BizHawk update-capture job. The new tool-pinned run retained
the 567-update matching prefix and raw update-568 mismatch, with matching
input values over 2,300 compared polls. The required candidate differential
retest still needs a separately pinned build recipe and executable provenance
for the reconstructed candidate; this diagnostic baseline alone cannot
certify an implementation patch or parity.
Implementation packets now accept an optional declarative candidate-build
recipe with bounded CMake argv, private build-output path, baseline update ID,
timeout, and SHA-256-pinned input manifests. An approved independent review
queues a local, non-AI job that builds its reconstructed commit, replays the
selected input for the baseline retrace target, and compares the candidate's
completed-update trace against the sealed BizHawk and native traces over the
baseline completed-update count. The resulting raw-first-mismatch movement
is candidate-only: input/clock alignment, full dependency-closure attestation,
actual game parity, and differential retesting of a real gameplay-code fix
remain open. No API billing is required for this deterministic retest, while the
review itself uses the user's bounded ChatGPT/Codex allowance.

Real-build smoke update, 2026-09-24: an opt-in, explicitly synthetic marker
candidate used the copied sealed US baseline, the production Visual Studio
CMake graph, the resulting native executable, and the selected-input replay.
The first two attempts exposed Windows `MAX_PATH` failures in the private Git
worktree and nested RT64 build tree; short hashed private roots fixed both.
The successful run sealed an unchanged raw first mismatch at completed update
568 and 2,300 matching controller input polls. Its separate four-job ledger
audit found no seal/lock issue. This closes the *plumbing* integration proof,
not independent review of a real fix, input-clock alignment, complete build
closure, or any parity gate. No model or API call was used in this smoke.

Partial-route determinism update, 2026-09-24: the supervisor now automatically
queues a pinned 100-run native repeat job for a current sealed update baseline
at or beyond 4,800 retraces. Four guarded replays run concurrently and each
preserves its VI and completed-update streams. A real 100-run job against the
current selected south-route prefix sealed `deterministic=true`: every VI
stream, completed-update stream, and final state hash matched the baseline.
The live ledger audit found 44 valid passed seals in 45 jobs and no integrity
issue; one old failed VI diagnostic remains. This is repeatability of a
partial native route, not a BizHawk parity or complete-slice acceptance run.

Oracle-fidelity gate, 2026-09-24: bounded guest-PC traces isolated a local
`cvt.w.s` disagreement at an exact 558.5 input with FCR31 rounding mode zero.
Native yields 558, BizHawk yields 559, while the NEC VR4300 manual specifies
ties-to-even for that mode. The loop must not propose or accept a native patch
that merely follows this oracle result. At this stage an independent CPU
reference was still needed; see the instruction-level evidence in
`autonomy-supervisor-bootstrap.md`. Global input/update alignment and parity
remain open.

Independent-core follow-up: a private, synthetic one-instruction ROM produced
559 in Mupen64Plus and 558 in Ares64 for the same exact tie and mode-zero
FCR31, confirming that the local conflict belongs to the Mupen oracle path.
The Ares64 game-route replay itself failed the initial-flash and early-clock
equivalence checks, so it cannot replace the pinned route oracle without
separate calibration. The microtest is reproducible without an AI model or
API billing; its checked adjudication is documented in the runbook.

Poll-boundary follow-up: opt-in semantic hashes at each selected controller
poll now expose three mismatch windows in a real 659-poll native/BizHawk
prefix, beginning at poll 16 and reconverging three times. A pinned,
restart-aware one-command diagnostic and a ledger-scheduled successor both
produce the pair without a model or API billing. A second bounded analysis
finds exact nearby oracle-state recurrences for most same-poll differences;
its four unmatched polls remain explicit. This improves the earliest-difference
signal but does not validate hook-phase alignment, initial oracle Pak
equivalence, or any gameplay-code repair basis. Automatic implementation
packets must wait for verified aligned evidence.

This plan intentionally separates **continuous activity** from **verified
progress**. The loop keeps working because the state and tests persist outside
the model; it stops claiming success only when the actual scope gates pass.

Frontier-worker integration, 2026-09-24: the durable supervisor can now opt in
to a private, digest-pinned Phase 9.5 frontier-cycle registration. Its scheduler
queues one bounded BizHawk exploration step at a time, records source and tool
pins, runs under the existing resource guard, seals covered or blocked results,
and resumes the cycle on the next supervisor pass. It can run with the coding
agent attempt cap set to zero, so this gameplay path needs no API billing. An
isolated live smoke sealed its first blocked frontier result with a healthy
ledger audit, then queued a distinct successor. A one-cycle unattended service
smoke executed and sealed that successor without a manual worker invocation.
The final audit verified two passed seals, zero issues, and zero coding-agent
attempts. Both searches were bounded and incomplete; neither demonstrates
native parity or reachability of the unresolved exits. No Windows startup task
was installed. Direct and supervisor cycle writers now share an OS-backed
per-cycle lock; a synthetic cross-process kill test proved overlap rejection
and automatic lock release, with 295 Phase 9.5 and 100 autonomy tests passing.
A live BizHawk kill drill then terminated only the verified guarded supervisor
owner during an active search. Its worker tree disappeared, the first ledger
attempt expired normally, and a second attempt sealed the same selected edge
without overwriting the interrupted output. A concurrent direct CLI resume
was rejected by the cycle lock. The isolated ledger ended with three valid
passed seals, zero audit issues, and zero coding-agent attempts; the recovered
search was still incomplete. A separate synthetic service-level test confirms
that an agent-cap-zero supervisor cycle itself reclaims an expired guarded
frontier lease and seals its second attempt. Live service-driven recovery,
multi-day restart/soak proof, broader campaign coverage, and verified native
alignment remain open.

Spatial-frontier follow-up, 2026-09-24: bounded-incomplete searches can now
yield new paired, replayable checkpoint sources instead of only increasing a
cold-search budget. The cycle checks identical state and selected-input
lineage from independent workers, requires measured horizontal improvement,
and adds a same-level progression edge plus a fresh exit-search edge. Two
preserved live pairs produced closer level-21 sources without marking their
exits covered. The exporter already follows checkpoint-import lineage, so
these sources retain their full controller route. The first real
service-dispatched search from the level-16 paired source then sealed an
incomplete bounded result after 112 saved states, with only about 1.6 units
of additional distance improvement. It exposed a likely local search stall,
not exit coverage. Fresh paired sources are now scheduled before larger
retries at a paired source. The second paired-source search likewise sealed
incomplete after 124 states and about 0.1 unit of added progress. The immediate
planner bottleneck is escaping local distance minima or following route
topology, not worker recurrence. A bounded outward-displacement priority is
now selected only for paired-source retries; the ordinary search policy and
coverage predicates are unchanged. Its live efficacy and native differential
remain open. The first real detour retry then reached a best saved state about
1,395 units closer to the declared exit than its source, at depth 23, while
still ending incomplete at the 256-node bound. This demonstrates useful
spatial escape, not coverage. Independent replay and promotion of its chosen
node, followed by native differential, remain open.

Selected-node verification follow-up: a fresh BizHawk worker replayed only
the 18 chosen actions from the source checkpoint to the detour's best node.
Every intermediate state/counter tuple matched the saved search, and both
workers reconstructed the same 11,433 controller polls. This is a paired
spatial proof in seconds rather than a second full 256-node search. At that
checkpoint, cycle integration and full native alignment remained open.

Durable selected-node promotion now closes the queue/promote portion: an
incomplete search with at least 60 units of measured progress persists a
pending verification, replays only its chosen path, and publishes a new
checkpoint and search edge after matching the paired state/input evidence.
The supervisor queues a maintenance step if interrupted and does not treat it
as exit coverage. A live zero-job migration registered two such checkpoints;
the best detour source is the next selected frontier. Export/native comparison
from this new source and full-game route coverage remain open.

The first full service cycle from that replayed source ran and sealed a
bounded miss after 92 nodes. Its less-than-one-unit gain did not meet the
promotion threshold, so no new checkpoint was claimed; the next selected
edge is a different replayed level-21 source. The isolated ledger verified
seven passed seals and zero coding-agent attempts. Route-topology guidance,
native differential, and continuous multi-day operation remain open.

A second agent-free service cycle from the other replayed level-21 source,
toward declared level 289, sealed another bounded miss: 114 saved states and
about 1.95 units of improvement from a 3,202.6-unit starting distance. The
ledger now verifies eight passed seals with no integrity issue. This does not
establish exit reachability. The frontier worker now refuses to queue below
50 GiB of free disk, and its guarded child stops if that reserve is crossed
or one fresh frontier-job output tree exceeds 4 GiB. Targeted guard tests
pass. These are per-job safety limits, not yet a multi-day soak, global disk
quota, model-spend cap, or proof that the startup task is installed.

The next live detour result was invalidated because the planner source changed
during execution; the supervisor retained the journals and rejected the
unstable result. A new cycle rule can preserve a sufficiently novel spatial
detour after independent exact-path replay even when straight-line exit
distance temporarily worsens. It labels this as exploration, never exit
coverage. A fixed-pin live search then selected and independently replayed
a level-21 checkpoint 676 horizontal units from its source, 481 units farther
from the exit; the supervisor sealed its bounded result. A continuation
returned nearly to an earlier verified position, exposing the need to avoid
duplicate spatial frontiers. Candidate selection now filters positions within
180 units of verified same-level checkpoints and can preserve one additional
novel node from such a duplicate-producing job. The live secondary replay and
global route-topology solution remain open.

The zero-job maintenance resume then independently replayed two additional
spatially novel selected paths from the preserved searches and registered two
new level-21 checkpoint continuations. No new search or exit coverage was
claimed by that migration. The next scheduled bounded search starts from the
second new checkpoint; whether it improves campaign coverage is still open.

The next bounded continuation and two isolated jump probes all stopped near
the same mid-level spatial boundary, well before the declared level-16 exit.
Adaptive jump trials and finer post-jump state retention were both exercised
live, but neither produced an exit or a farther campaign route. This is now a
route-topology/mechanic investigation, not evidence of unreachable content.

The first route-topology instrument is a sealed, read-only BizHawk screenshot
of any private checkpoint, with exact post-load RDRAM verification. Several
Goldwood vantage points reveal a lower ground route that a detour search saved
but never expanded. A bounded breadth-first `coverage` search mode now exists
and is selected after repeated exit-search misses. Its live efficacy and
subsequent native differential remain open.

A live breadth-first probe from the lower checkpoint crossed the prior local
Z frontier and exposed an open westward ground branch. Both diagnostic route
segments back to an existing graph checkpoint have now passed independent
selected-input/state replay. A bounded proof-chain importer is implemented so
those segments can enter the durable frontier as progression only; live import
and supervisor continuation are still pending.

The live import passed, and the supervisor followed its westward checkpoint.
The bounded job advanced from roughly 2,032 to 1,117 horizontal units from
the selected level-16 exit but did not reach it. Supervisor maintenance
independently verified and promoted that saved state into the durable graph.
Selection now uses verified checkpoint distance as a small ordering term for
paired exit-search sources; this puts the newly closer route ahead of an older
checkpoint whose static priority was lower. Full Goldwood exit coverage and
native differential evidence remain pending.

Two more live bounded continuations tested the closer route and an older
checkpoint. Neither reached the exit. The closer route stopped alongside a
visually confirmed wall; the older route produced only minor local progress.
The next scheduled run is now a detour retry from the closer checkpoint,
ahead of untried branches hundreds of units farther from the landmark.

That detour job remained bounded-incomplete but independently verified a
spatially novel checkpoint. The prior eight-hop promotion cap would prevent
any further checkpoint along that branch, so the per-chain cap is now 64;
bounded workers, disk guards, and spatial novelty continue to constrain each
step. No exit coverage or native parity was claimed by this change.

The next bounded job returned to previously searched wall-side space. A
promoted node was within one unit of a node from an earlier job, exposing a
cross-job novelty gap. Promotion now consults earlier stable search traces
for the same level and exit, rejecting near-duplicate states within one
60-unit search cell. That prevents repeat traversal from masquerading as
new autonomous coverage; existing immutable artifacts remain intact.
