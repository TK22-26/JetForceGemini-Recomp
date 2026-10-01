# Local autonomy supervisor bootstrap

Latest handoff correction (2026-09-27):
[lossless point-prompt recovery](autonomy-point-prompt-recovery.md) reduces the
20,709-character failed prompt to 18,152 characters without dropping evidence.
Only its verified pre-launch failure can receive one immutable successor;
that successor has now sealed a live result in one attempt, with no evidence
dropped and no repeat of the completed word/entry workers. It requires
all-thread/device-event instrumentation. The first driver exited; a fresh
one-job driver is revalidating the completed point result with the corrected
interval successor selector. This is
not a gameplay repair or full-loop acceptance.

Latest validation optimization (2026-09-27): the
[fresh-context handoff](autonomy-context-handoff.md) removes a duplicate
review/baseline walk inside each diagnostic-context call without caching
results across calls or removing before/after measurement checks. A live
before/after check returned the identical context digest with one review
validation instead of two. All 325 autonomy tests pass; this is not a
whole-loop performance or completion claim.

Latest source-backed planning (2026-09-27): the
[bounded operand-context successor](autonomy-interval-experiment.md#source-backed-operand-context-successor-2026-09-27)
derives conditional register effects from matching retained instructions and
offers one new evidence-backed plan after an unsupported interval result.
The live model selected a receive-branch readiness test, and the driver ran
and sealed its paired capture without a manually authored probe packet.
At that checkpoint the autonomy suite passed 321 tests. Independent ledger measurement now
passes qualification and falsifies the proposed readiness-operand difference;
diagnostic feedback completed successfully, as did the next unsupported word
and entry plans. The subsequent instruction-point job was blocked by the
20,000-character prompt limit, and the bounded driver has exited; it is not
still running. See the [research handoff](autonomy-research-resume.md) for the
exact job and independently rechecked 1908 selected-state frontier.
This is not a causal game fix or full-loop completion.

Latest execution-loop improvement (2026-09-27): the
[research tail resume](autonomy-research-resume.md) selects the deepest durable
planner instead of repeatedly walking every earlier lane before dispatch.
Full executor/measurement validation remains in place. Profiling showed 1,875
subprocess calls in one prior context check; internal recursive validation is
still a scaling concern. This improves continuation, not repair acceptance.

Latest autonomous observation (2026-09-27): the
[typed cross-thread interval lane](autonomy-interval-experiment.md) completed
a model-selected measurement using retained, independently rechecked captures.
The second pacing send-entry queue word is 1 on both sides, falsifying the
predicted earlier difference. Its follow-up diagnostic completed successfully
but still reports insufficient causal evidence. The next planner's handoff
exposed an oversized raw-history prompt; the state-word adapter now projects
checked values and qualification while retaining complete pinned reports.
Selected-state parity remains through update 1908; the next mismatch is 1909.

Latest failure recovery (2026-09-27):
[bounded research completion](autonomy-research-completion.md) turned the
timed-out investigation's retained evidence into a structured, tool-free next
test in 86 seconds, without changing the original failed job. The driver
consumed it and continued to typed experiment selection. This is a one-time
synthesis step, not an unbounded retry or a causal gameplay repair.

Earlier autonomous observation (2026-09-26): the
[typed instruction-point lane](autonomy-point-experiment.md) completed a live
model-selected plan, paired capture, qualified measurement and automatic
follow-up handoff. It confirms four native receive calls versus five reference
calls in pacing invocation 1908, with unchanged full update traces and focused
RDRAM. This closes another manual handoff, not the upstream timing defect,
gameplay frontier or entire automation objective.
The queued follow-up then exhausted its research budget without an accepted
diagnosis. Logs survive; failure reporting was corrected to preserve the
original stop instead of masking it with a post-deadline snapshot error.

Latest upstream observation (2026-09-26): a new bounded
[instruction-point capture](phase9-pacing-receive-observation.md) finds the
1908 pacing queue already contains two native messages versus three reference
messages on producer entry. Both sides count the observed receives correctly;
policy settings match. Full update traces and focused RDRAM are unchanged by
tracing. The primitive is implemented and locally qualified; the typed
autonomous integration is documented above.

Latest qualified execution experiment (2026-09-26): the
[consumer-entry lane](autonomy-entry-experiment.md) automatically planned,
captured and qualified the next test. A1 is the only differing GPR at the
paired invocation 1909 (native 3, oracle 4), with both full update traces
unchanged by instrumentation. The measured follow-up completed; the upstream
timing fault and the full automation objective remain open.

Latest measured-result handoff (2026-09-26):
[experiment feedback](autonomy-experiment-feedback.md) now recomputes sealed
observations before handing them to a follow-up investigation. Successor plans
retain measured history and reject repeated-byte predictions; a bounded series
of state-word experiments must change method instead of endlessly recapturing.

Latest experiment transition (2026-09-26): the
[bounded state-word lane](autonomy-state-word-experiment.md) completed a live
diagnosis -> typed plan -> pinned paired capture -> measured observation.
It reproduced the 1908 elapsed-step difference on the frozen-source build,
without a manually authored probe packet. Selected-state parity still ends
at 1908; this closes a handoff, not the general self-improvement loop.

Latest feedback transition (2026-09-26): completed candidate replays now
automatically queue one [evidence-backed investigation](autonomy-candidate-feedback.md)
for unchanged, regressed, input-mismatched or later-frontier outcomes. This
replaces manual diagnostic-packet preparation after a repair attempt. It does
not yet turn arbitrary research proposals into independently validated fixes.

Latest repair-loop evidence (2026-09-26): one
[proof-gated real-defect cycle](autonomy-proven-repair-cycle.md) completed
diagnosis, bounded implementation, independent review, fresh build and replay.
Its 28-case Count microtest passes, but the first gameplay mismatch remains
1909. The candidate is retained privately, not merged or accepted as parity.
Review validation receipts and Windows guard-publication recovery are now
handled explicitly; the general self-improvement loop remains unfinished.

Latest source integration (2026-09-26): the
[rebuildable baseline](autonomy-source-baseline-handoff.md) captures the current
runtime in a private detached commit without changing the user's branch/index.
A fresh build reproduced the native traces byte for byte. Replay registration
can now bind that build's actual source commit through `--source-build`; repair
workers need not start from the older main-branch code.

Latest integration evidence (2026-09-26): the
[pinned execution-profile handoff](autonomy-execution-profile-handoff.md)
connects the original-OS replay to durable comparison, automatic focused
capture, replay-free boundary analysis and native-repeat jobs. All four live
jobs sealed successfully. This does not close the engineering repair loop or
full-scope parity gates; earlier entries below remain historical evidence.

The first supervisor worker lives in `scripts/autonomy/supervisor.py`, not the
tracked `tools/` tree: repository hygiene intentionally excludes **all** of
`tools/` from commits. Its mutable state, packets, logs, and isolated Git
worktrees live under ignored `tools/private/autonomy/`.

This version uses the installed `codex exec` and its existing ChatGPT login;
it does not call the OpenAI API or require API billing. ChatGPT/Codex plan
limits still apply. Before launch it verifies ChatGPT sign-in and strips common
API-key environment variables from agent and validation children. Each Codex
invocation also forces the `chatgpt` login method, so loss of that login fails
the job instead of switching to API billing. No job runs
merely because the supervisor is installed or
a packet is queued. Running an agent requires the explicit `--execute` flag.

## Packet and commands

Create a JSON packet **outside tracked files** with the exact schema below.
The ROM, emulator, and native paths must name existing local files; the
supervisor hashes them and never copies them into the repository. The commit
must be a full local Git commit ID. Validation commands are argv arrays, not
shell strings, and are run from the isolated worktree. Packet authors must
trust and review these commands before queueing.

```json
{
  "schema": 1,
  "job_id": "phase9-example-001",
  "kind": "implement",
  "source_commit": "<full Git commit ID>",
  "pin_files": {
    "rom": "C:\\absolute\\path\\to\\lawful-dump.n64",
    "emulator": "C:\\absolute\\path\\to\\EmuHawk.exe",
    "native": "C:\\absolute\\path\\to\\game.exe"
  },
  "prompt": "Hypothesis, evidence, file budget, required failing test, and stop rules go here.",
  "timeout_seconds": 1800,
  "validation": [["python", "-m", "unittest", "tests.test_some_focus"]],
  "prerequisites": [],
  "retry_budget": 1,
  "allowed_paths": ["src/runtime/", "tests/test_some_focus.py"],
  "max_changed_files": 4,
  "evidence_files": []
}
```

An implementation packet may additionally include a `candidate_build` object
for a local native differential retest. It must name a sealed baseline update
job, bounded CMake configure/build argv using `{source}` and `{build}`
placeholders, an executable path relative to the private build directory, a
60-3600 second timeout, and one or more SHA-256-pinned build-input manifests.
The packet validator rejects a changed manifest or an executable path escape.
After a passed independent review with an `approve` verdict, the scheduler
queues one deterministic retest. It reconstructs the reviewed commit in a
private worktree, runs the bounded CMake recipe, replays the selected input
through the resulting native executable, and compares its completed-update
trace to the sealed BizHawk trace and original native baseline. The baseline
retrace target is used for replay; the separately recorded completed-update
count bounds comparison. The retest makes **no** Codex or API call. A passed
retest seals only raw first-mismatch movement and an input-poll diagnostic;
it does not prove alignment, game parity, or a complete build-dependency
closure. Input-manifest pins alone are not a build-closure attestation.

`kind` is `diagnose`, `implement`, or `review`. Only implementation packets
may write, and they require at least one validation command. Diagnose and
review jobs use Codex's read-only sandbox. The scheduler now creates a review
packet after a sealed implementation: it checks the result/patch/archive
hashes, reconstructs the candidate in a fresh private worktree, makes a
detached local-only commit, reruns the declared validation, and launches a
separate structured review only if that retest passes. It does
not merge, push, or treat an approving verdict as a parity pass. Manually
authored review packets need a passed implementation prerequisite with the
same pinned source and three sealed evidence files.

From the repository root:

```powershell
python -m scripts.autonomy.supervisor queue C:\path\to\private-packet.json
python -m scripts.autonomy.supervisor status
python -m scripts.autonomy.supervisor audit
python -m scripts.autonomy.supervisor run-once --execute
python -m scripts.autonomy.supervisor run-once --execute --job-id phase9-example-001
python -m scripts.autonomy.supervisor pause
python -m scripts.autonomy.supervisor resume
```

To turn a native/BizHawk retrace pair into a pinned **read-only diagnosis**
job, use `queue-divergence JOB_ID NATIVE_TRACE ORACLE_TRACE --rom ROM --emulator
EMULATOR --native EXE [--oracle-offset N]`. It runs the existing first-
divergence comparator, stores the report privately, pins all three evidence
files, and asks the agent to verify input/retrace alignment before proposing a
fix. Matching traces do not queue a job. This does not yet run the emulator or
generate new input autonomously.

New diagnosis jobs request a JSON response conforming to
`scripts/autonomy/diagnosis.schema.json`; the worker validates its fields and
seals the final-message digest. A `code_divergence` classification is rejected
unless the diagnosis claims validated alignment and supplies a specific
retrace and evidence. This makes the result machine-readable for a future
scheduler, but is not independent validation of the model's factual claims.

For deterministic comparison as a durable queue job, use the same arguments
with `queue-comparison`, then `run-once --execute`. The comparison worker is
non-AI: it pins the two traces and ROM/emulator/native/tool identities, runs
the streaming comparator under a wall-time/log cap, and seals a private
result even when the raw retraces mismatch. Its `alignment_validated` and
`parity_verified` fields remain false. A successful comparison job proves
the comparison executed reproducibly, **not** that the two clocks or initial
states are aligned. The comparator now streams records instead of retaining
whole-route traces in memory.

`advance --max-new-jobs 1` inspects sealed comparison jobs oldest-first and
queues one idempotent, pinned, read-only diagnosis for each raw mismatch. It
uses the existing report; it does not rerun the comparator or launch a model.
`drive --execute --max-jobs 1` performs that transition and executes at most
the declared number of eligible jobs. Both commands honor `PAUSED`. A raw
match remains unverified until input, initial state, and capture alignment
are proved; the scheduler does not promote it to parity. Once a sealed
structured diagnosis classifies an early raw mismatch as capture
misalignment, `advance` queues one pinned, non-AI alignment job. That job
runs a guarded short BizHawk VI capture and the poll/VI analyzer. The
scheduler does not yet generate an implementation packet.

For a short alignment probe, `python -m scripts.phase95_oracle_replay OUTPUT
--emulator EXE --rom ROM --rom-sha256 SHA --source SELECTED_INPUT
--target-frame 120 --vi-trace --timeout 300` runs the selected-poll export
through a fresh, guarded BizHawk copy. It records VI-consumption semantic
hashes and initial flash identity. The chosen prefix must not exceed the
exported route target. This probe is diagnostic, not an accepted parity run.

The historical Phase 9.5 evidence can be imported with
`python -m scripts.autonomy.import_evidence --batch
tools/private/phase95-goldwood-seeded-ten-20260923b --frontier
tools/private/phase95-frontier-job-20260923a/run-002`. The importer verifies
the ten ordered seed journals and their completed result files, every batch
asset pin, the two-repeat frontier endpoint, the emulator/ROM identities, and
the frontier graph reference before sealing eleven **integrity-audit** jobs.
It is idempotent for the same source/tool pins. The original producer source
commit was not recorded in those historical manifests: the ledger's commit
and tool pins identify the *audit*, not the historical producer. This import
does not replay the jobs or close any gameplay/parity gate.

`run-once` consumes at most one eligible packet and exits. `--job-id` leases
exactly the named queued job, subject to its prerequisites, instead of
working through older queued packets. It is useful for a newly generated
current-binary diagnostic; it does not bypass the daily agent-attempt cap in
the continuous worker. A failed job can be
retried within its packet's retry budget using `retry JOB_ID`. A changed pin
or packet blocks the job instead of silently running against different inputs.
The redacted `status` view contains no prompt, paths, hashes, or private logs.
Attempts and candidate results remain in `tools/private/autonomy/attempts/`;
the tracked patch and untracked files are copied and hashed there. The worker
rejects changes outside `allowed_paths`, changes to protected private/golden
trees, and candidates over the declared file budget. Worktrees are retained
for inspection. A sealed `passed` job means only that
the bounded agent task and its declared checks completed. It does **not** mean
game parity or approval to merge/push.

For a sealed implementation job, `advance` queues one idempotent review job
before other follow-ups. The reviewer sees the reconstructed candidate commit,
not just a patch filename. Its JSON verdict is `approve`, `reject`, or
`needs_evidence`; the sealed review result records the candidate commit,
review digest, and reconstructed-candidate retest. A `passed` review job means
the independent read-only review
*ran*, even if its verdict rejects the change. Only an approved review with a
candidate-build recipe queues the local differential retest. There is no
automatic merge or promotion based on that diagnostic.

A live integration smoke can be run explicitly with
`python -m scripts.autonomy.live_review_smoke --execute`. It creates only
synthetic fixture files under ignored `tools/private/autonomy/`, uses a local
fixture implementer, and runs the real ChatGPT-authenticated Codex CLI as the
read-only reviewer. The job has a 240-second wall-time cap. The 2026-09-24
run sealed two passed jobs, a successful reconstructed-candidate retest, a
structured review, and zero post-review worktree changes. It did not exercise
game code, a native/oracle differential, or candidate promotion.
The separate `--hard-kill-review-once` mode killed a real guarded Codex review
and confirmed its child stopped. The ledger then retried in a new private
worktree and recorded exactly `expired -> passed`, preserving both attempt
directories. This proves that one Windows Codex crash/retry path, not a
multi-day unattended recovery guarantee.

The separate `python -m scripts.autonomy.live_native_retest_smoke --execute`
command exercises a **real** Windows CMake build and native replay against a
copied sealed US baseline. Its implementation marker and approval are local
fixtures, not a real gameplay fix or independent model review. The first two
attempts exposed Windows path-length failures in Git checkout and nested
MSBuild/RT64 output; the retest worker now uses short private worktree and
build roots. The successful 2026-09-24 smoke is retained under ignored
`tools/private/nrs-20260924T090810919669Z/`: the candidate executable built,
the replay reached its pinned 4,800-retrace target, 2,300 compared input polls
matched, and both baseline and candidate first differed from BizHawk at raw
completed update 568. The four-job smoke ledger audit found four valid passed
seals and no integrity issue. This proves build/replay plumbing on this
machine without API billing; it does **not** validate input-clock alignment,
build closure, a code fix, or whole-game parity.

The scheduler now queues one 100-run native determinism job when it sees a
current, sealed selected-input update baseline of at least 4,800 retraces.
`scripts/autonomy/determinism_job.py` runs four bounded native replays at a
time, pins the executable, ROM, selected input, initial flash/Pak, baseline
traces, and tool code, and seals each run's VI/update trace digests and final
state hash. A difference seals a first-run diagnostic rather than being called
a process failure. The real 2026-09-24 partial-route job
`native-det-f59f9e4872d6ad20e65176b1` completed all 100 repeats: all VI
streams, completed-update streams, and final state hashes were identical to
the sealed baseline. The live ledger audit then verified 44 passed seals in
45 jobs with zero integrity issues; one earlier failed VI diagnostic remains.
This proves native repeatability only through the 4,800-retrace prefix. It
does not prove BizHawk/native alignment, a complete route, or parity.

An opt-in continuous loop is available with
`python -m scripts.autonomy.supervisor serve --execute
--max-agent-attempts-per-day 4`. It holds a single-owner state lock, checks
ledger seals/resource locks at startup and daily, reports each cycle, and
limits ChatGPT-agent **attempts** by UTC day while continuing eligible local
jobs. Use `--max-agent-attempts-per-day 0` for deterministic-only operation;
`--max-cycles 1` is a bounded smoke. `audit` writes a private report including
failed/blocked job IDs; it does not turn them into passes. This is an attempt
cap, not a measured token quota or an installed startup service. A 2026-09-24
audit of the live ledger verified 42 passed seals among 43 jobs with zero
integrity issues; one prior failed diagnostic remains unresolved.
An explicit real-state `serve --execute --max-cycles 1
--max-agent-attempts-per-day 0` then ran one non-AI update-capture job. Its
native and oracle captures sealed a 567-update matching prefix and the known
raw mismatch at update 568; 2,300 compared controller polls had matching
input values. The same-poll resynchronization diagnosis remains unvalidated
as a gameplay-code divergence. A follow-up ledger audit verified 43 passed
seals among 44 jobs with no integrity issue. The new capture was justified by
a changed update-capture tool digest; ROM, emulator, and native executable
digests stayed pinned. It was not a documentation-commit rebase loop.

## Acceptance still missing

This is a restart-aware worker slice, not the complete self-improvement loop.
The first comparison still requires supplied traces; the scheduler can now
select the earliest raw mismatch, obtain a structured diagnosis, and run a
bounded capture-alignment follow-up. It cannot yet choose a general backlog
task or synthesize an implementation packet from validated divergence. It cannot
resume an interrupted Codex conversation, establish aligned whole-route
parity from the new raw candidate retest, enforce aggregate disk and
token-usage caps, validate and enable the Windows startup task,
or merge an approved change. Expired attempts now carry per-child guard
records: once the owner is confirmed dead, an intact completed bundle can be
sealed without rerunning, or an incomplete attempt can safely retry in a new
worktree. A missing/uncertain guard record or live owner blocks for manual
recovery. Those remain explicit gates in the
[full-scope plan](autonomous-full-scope-execution.md). Do not run it unattended
for multi-day work until the remaining controls and soak proof pass.

Startup-task preparation, 2026-09-24: `scripts/autonomy/service_entry.py`
adds a private, fsynced event log around the existing single-owner loop.
`scripts/autonomy/install_windows_task.ps1` defaults to a **plan-only** preview;
`-Action Install` explicitly registers a current-user logon task plus a daily
watchdog, with Task Scheduler restart and duplicate-instance limits. Its
default ChatGPT-agent attempt cap is zero. The plan preview, PowerShell parse,
task-object construction, and service-entry synthetic tests pass. No startup
task has been installed, no multi-day soak has run, and the plan's remaining
resource/spend and review gates still prohibit claiming safe unattended
operation. `-Action Status` inspects, and `-Action Remove` refuses an
unrecognized task.
An isolated live `service_entry --max-cycles 1` smoke with agent cap zero
completed its startup audit and idle cycle and flushed start/cycle/stop events
under ignored private storage. This checks the service entry point, not Task
Scheduler registration or the production queue's restart behavior.

Worker children on Windows are now placed in a non-inheritable Job Object with
kill-on-close, an 8 GiB committed-memory cap, and a 3,600-second CPU-time cap,
in addition to the existing wall-time/log caps. A synthetic hard-parent-exit
test verifies that its assigned child stops. A supervisor hard-kill/restart
test verifies one expired attempt and one final completion, with both attempt
records preserved. The Phase 9.5 BizHawk worker now uses the same guard, and
an isolated one-frame US oracle probe passed. A real BizHawk hard-kill/resume,
multi-day restart behavior, and the equivalent non-Windows containment proof
remain open. Limits are still fixed per child, not an aggregate job/model
spend budget.

On 2026-09-23, one bounded **synthetic** read-only transport smoke ran through
the installed ChatGPT-authenticated Codex CLI. It exited successfully, changed
no files, and sealed a private candidate record. Its fixture pins are not game
parity evidence. The unit/integration suite also exercises pin drift, pause,
timeout, expired-worktree blocking, path scope, and trace-intake behavior.
An additional live CLI smoke on the same date accepted the diagnosis JSON
Schema with forced ChatGPT login and produced a validated
`insufficient_evidence` result. It did not inspect or compare game traces.
The first real `advance`/`drive` cycle also sealed a structured diagnosis of
the south-route raw mismatch. A 120-frame isolated US oracle follow-up then
captured 90 VI-consumption hashes; initial flash matched the exported save.
The native/VI-oracle raw comparison first differs at label 1 only in the
actor-list pointer, and labels 20-33 are fully equal. These nominal labels
are **not** a validated common clock: native poll 16 is near VI 35 whereas
oracle poll 16 is near VI 43. The next gate is an explicit poll/VI alignment
interpretation with Pak equivalence, followed by a validated first-divergence
test at a common guest execution boundary.

`python -m scripts.phase9_poll_vi_alignment SELECTED_INPUT ORACLE_PREFIX
NATIVE_REPLAY --max-polls 256 --output PRIVATE_REPORT` now produces that
diagnostic map. It verifies the export, replay and initial-flash identities;
joins each oracle input callback to the last consumed VI; checks selected
controller values; and records VI offset windows and prior-VI hash matches.
The first real 120-frame report analyzed 27 shared polls: input values matched,
the first observed mode/RNG difference was poll 16, and the VI offset changed
from 10 (polls 5-15) to 8 (polls 16-17) to 34 (polls 20-26). Therefore a
single constant retrace offset is falsified. The report deliberately leaves
`alignment_validated` false and Pak equivalence unknown. It is not yet a
parity test. The same report is now produced by a durable ledger job: the
real automated 120-frame job's report digest exactly matched the independent
manual probe. A separate 600-frame hard-kill drill confirmed the guard stops
the owned BizHawk tree, retains attempt 1 as `expired`, and seals attempt 2
as `passed` after retry, with 256 polls analyzed. Neither result claims
alignment or parity.

The next deterministic successor is a completed-guest-update job. After a
passed alignment diagnostic, `python -m scripts.autonomy.supervisor advance`
queues a pinned prefix capture; `run-once --execute` performs native and
BizHawk selected-input replays with `--update-hashes`, compares the native
completed-update count against an equal-length BizHawk prefix, and seals the
two traces plus comparison. This path makes **no model call**. The bounded
prefix is capped at 600 native retraces and 1.5 times that many oracle frames
(or the export endpoint), with a 900-second job budget. A shorter oracle update
stream blocks rather than being reported as a gameplay mismatch. A matching
prefix does not establish whole-route parity, controller/Pak equivalence, or
visual/audio parity.

The first real ledger-driven south-route job passed on 2026-09-23: native
captured 296 completed guest updates in 600 retraces; the 900-frame BizHawk
probe captured 411 updates; all first 296 semantic hashes matched. The result
is in ignored private storage under
`tools/private/autonomy/attempts/phase9-south-raw-20260923-diagnosis-alignment-updates/0001/`.
This narrows the earlier raw retrace/poll mismatch to capture timing or later
behavior for this prefix; it does not close the remaining parity gates.
Matching jobs with sealed native and oracle update traces now queue a bounded
successor at twice the native retrace target, capped by the exported route.
The successor depends on the prior sealed job, pins it as evidence, and stops
expanding on the first semantic mismatch. This grows coverage without manual
probe selection or AI/API calls; a mismatch still needs a separate diagnostic
and fix workflow.

The first expanded 1,200-native-retrace / 1,800-oracle-frame job stopped at a
raw update-568 mismatch. A rebuilt native probe and instrumented oracle now
annotate completed-update hashes with their controller-poll positions (and
side-specific frame/retrace counters); these counters are *not* part of the
semantic state digest. At the mismatch, native had consumed 570 polls while
BizHawk had consumed 575. Both reached the same transition after poll 575:
BizHawk at update 568, native at update 572. Twenty-three following semantic
states matched under that four-update offset in the bounded capture. The
new poll-alignment analyzer reports a same-poll resynchronization candidate,
not validated alignment or parity. Future ledger mismatches automatically
seal this report when both streams carry the metadata; old captures explicitly
say that clock metadata was unavailable. The remaining question is why the
native poll/update cadence lags the oracle at this transition.
Rebuilding the native executable exposed a ledger edge case: a changed binary
at a mutable build path used to invalidate a *past* sealed job and halt
`advance`. The scheduler now verifies the historical seal against its stored
hashes, considers only frontier leaves, and queues a new same-prefix rebase
when the native binary, emulator, or comparison tooling changes. It never
silently extends a mismatch under new code, and a changed ROM still blocks.
For an unchanged-build, sealed update mismatch, `advance` now queues one
read-only Codex diagnosis with the raw comparison, poll-anchor report, both
traces, and replay manifests pinned as evidence. It asks for a falsifiable
cadence/code hypothesis and cannot edit timing code or claim parity. This is
the first model-assisted successor in the update lane; it uses the existing
ChatGPT login, not API billing, and stops if that login is unavailable.
The local read-only diagnosis classified the 568/572 shift as unvalidated
capture misalignment and requested a same-input/same-save poll-prefix test.
That test passed for the first 576 controller values: no input mismatch,
candidate FlashRAM matched both sides, and the native Pak matched the
candidate file. BizHawk Pak equivalence remains unverified. Five brief
same-index mode/RNG disagreements at polls 16-17 and 494-496 persist before
the poll-575 state anchor; different poll/frame clocks mean these are not yet
validated game-code divergences. New update jobs now capture the native poll
trace and seal this prefix comparison automatically; a missing or mismatching
input prefix prevents blind frontier expansion.
The poll-alignment report now scans the entire captured suffix after its
same-poll anchor, recording the first *later* mismatch or confirming that the
native prefix ended with matching semantic states. When input values match,
the anchor is supported, and that entire captured suffix matches, `advance`
may double the **diagnostic** capture target even though the raw update labels
diverged. It preserves the original mismatch and keeps `parity_verified`
false; any later mismatch or missing poll evidence stops expansion for
diagnosis.
The 4,800-retrace diagnostic extension matched 1,733 controller inputs and
681 semantic updates after the poll-575 anchor. It then found a distinct
later mismatch at native update 1253 / BizHawk update 1249 (native poll 1256,
BizHawk poll 1258). This is a new investigation point, not a validated code
fault: the compared updates still occur after different poll counts. The
scheduler now directs read-only diagnoses to the active update leaf rather
than repeatedly diagnosing older superseded captures.

Focused guest-update RDRAM capture is the next deterministic successor when
the active update alignment report contains a bounded first-later semantic
mismatch. `advance` queues a pinned child using the same route and build,
with a window spanning the immediately preceding matched update pair and
the first mismatching pair (at most 16 updates). Both replay wrappers accept
`--focus-updates FIRST LAST` and require every requested canonical 4 MiB
snapshot; the worker compares actor bytes against each side's hashed update
trace, seals the snapshots and focused report, and keeps alignment/parity
unvalidated. This capture and comparison require no AI model or API billing.
The focused child is terminal capture evidence, not a recursive extension;
a read-only diagnosis can inspect its actor-byte report.

The independent 2026-09-24 capture around the later mismatch used native
updates 1248-1260 and oracle updates 1248-1260. At the last matching semantic
pair (native 1252 / oracle 1248), all 18 actor regions matched byte-for-byte.
At the next pair (native 1253 / oracle 1249), 17 of 18 actor regions differed.
Actor 1 at `0x801b9e40` first differed in four bytes at offsets `0x0c1`,
`0x0c3`, `0x191`, and `0x193`. This sharply localizes the onset but does **not**
establish a game-code bug: the compared updates were recorded after 1256 versus
1258 controller polls, respectively. Full RDRAM differs even at the actor-
matching pair; controller-Pak equivalence on BizHawk remains unverified.
The ledger-driven rebase and focused child reproduced the same onset and
sealed their evidence as `updates-rebase-786cf61f3049b07457d95cab` and
`updates-rebase-786cf61f3049b07457d95cab-focus`. A ChatGPT-authenticated,
read-only diagnosis suggested checking whether the two different poll indices
consumed different controller values. An independent join to the pinned
`controller.input` shows each side consumed exactly one neutral sample between
the matched and mismatched update: native poll 1255 and oracle poll 1257 both
had buttons `0000`, connected player 1, and stick `(0,0)`. This weakens a
different-*value* input explanation, though poll callback timing or an
untraced state field could still matter. The focused comparator now reports
these exact intervening input values, and future diagnoses receive the
selected-input file as pinned evidence.

A bounded 3,100-frame oracle rerun with the configured VI-consumption hook
reproduced the exact focused RDRAM hash at update 1248. Its configured VI
counter advanced by two between oracle updates 1248 and 1249; native's
configured VI counter advanced by three between paired updates 1252 and 1253.
The paired update clocks had also differed at earlier points while semantic
states still matched, so this is a timing lead-in, **not** causal proof. The
oracle update trace now records that configured VI counter when requested,
the focused ledger child enables it, and the alignment/focus reports compare
the per-update deltas separately from emulator frame numbers. Hook identity
and full runtime equivalence remain open. A changed tool or binary can rebase
a terminal focused child without recursively focusing the same mismatch.
The focused captures also retain native and oracle semantic hashes at their
respective configured-VI consumption hooks. A replay-free `vi-boundary` ledger
successor pins those existing traces and snapshots, then compares the two
bounded consumption intervals bracketing the matched and mismatched update
pair. On the current capture, the lead-in had three native versus two oracle
consumptions, but the first two relative consumption states matched. In the
next interval, actors already differed at the **first** paired consumption
(native 2653 / oracle 2857); native's third consumption in that interval came
later. This rules out that *later third consumption alone* as the first point
of observed actor divergence. The earlier extra consumption or an untraced
state difference may still contribute. These hook samples are diagnostic:
their execution-boundary equivalence and save/Pak equivalence are unverified.
The same replay-free job now seals a canonical RDRAM transition summary.
For this pair, 226,017 bytes already differed at the actor-matching update;
10,287 previously equal bytes became different at the next update, including
161 bytes inside the validated actor regions and 10,126 elsewhere. The latter
are grouped by physical 4 KiB page, not labeled as gameplay globals: several
dense pages may be transient graphics data. This report localizes new evidence
without pretending that pre-existing memory differences were irrelevant.

The next bounded diagnostic adds `--watch-word 0x801bc3e0` to the existing
focused replay wrappers. BizHawk's memory-write callback captured nine writes
in this window, all at guest PC `0x8000e2ec`. The native trace records
generated-function dispatches whose entry/exit values changed; its 54 rows
include nested callers of the same nine updates and must **not** be counted
as 54 memory writes. In the first divergent transition, both sides had the
same pre-write word `0xc408cb89`. BizHawk's next value was `0xc40a673d`,
while native's was `0xc40b2e24`. The native innermost changing dispatch was
`0x8000e278`, containing the oracle's write PC. Thus the earlier actor-word
sequence agrees through the last matched value, and the differing value is
produced during the same guest function. This still does not prove a bad
instruction translation: an untraced operand, timing state, or pre-existing
nonactor state could feed that function. The exact guest operands at the
write are the next useful capture. Both runs are diagnostic, not parity
acceptance; this feature requires no API billing.

The actor write was downstream of a timing input. A replay-free focused-word
probe over native 1252→1253 and oracle 1248→1249 shows five identical prior
words becoming different: player angle `0x801ba350`, its copied source
`0x800fa4d0`, rotation input `0x800fa638`, matrix coefficient
`0x800faf80`, then actor output `0x801bc3e0`. Targeted memory watches show
the player angle is written inside the player-update overlay (oracle PCs
`0x803912a0`–`0x803912a8`; native generated function `0x02f0084c`), while
the subsequent functions copy the angle and derive the matrix and actor
coordinate. This is a dependency trail, not proof that all other state was
equal at the function boundary.

A bounded entry-argument probe now accepts a pinned oracle `--entry-pc` and
native `--entry-target`, logs A0–A3, and seals a replay-free comparison. The
real capture found nine calls on each side in the first divergent update, in
the same actor-pointer order. Native passed A1 bits `0x3d4cccce` (about 0.05
seconds) and A2/A3 `3`; BizHawk passed `0x3d088889` (about 0.0333 seconds)
and A2/A3 `2`. The generated caller multiplies its frame count by a fixed
seconds-per-frame factor before entering the overlay, and the guest main
update loads that count from `0x800a3374`. Thus the downstream angle/matrix/
actor difference is explained by **different elapsed-VI inputs**, not by an
observed mismatch in the overlay's arithmetic. At that diagnostic stage, why
native had three VIs while BizHawk had two was still open; the queue probe
below resolves this local fault. Hook alignment and full runtime state still
require validation before any broad parity claim. The word and entry
comparisons run without an AI model or API billing.
The native focused timing trace now also records successful VI-queue receives.
In the observed lead-in it records a third configured VI consumption at native
VI 2652 before update 1252 returns; the paired oracle update returns after
two configured consumptions. The trace preserves message identity and delivery
count so the next test can distinguish guest queue timing from a synthetic
frame-scheduler decision. No frame-cadence change had been made at that stage.

A further focused native replay recorded the scheduler state at each VI
service. The extra native VI is a **quiescent guest wait**, not a synthetic
busy-poll timeslice: the interrupt-timeslice count stays at 132. At VI 2650,
the game thread waits on queue `0x800fe8a8` while one graphics task remains
pending; the ordinary two-VI update immediately before it instead reaches
queue `0x800feb80` after the task completes. Event registrations show that
`0x800fe8a8` is not the direct SP/DP, VI, or SI event queue, so its producer
was traced separately. Thread 4 sends to the first completion queue
`0x800fe4b8` at VI 2650, then sends to `0x800fe8a8` at VI 2651; thread 2
blocks on the latter between those two sends. The diagnostic trace now
includes pending task counts, blocked thread queues, sorted event-to-queue
mappings, and focused game-queue calls. The equivalent BizHawk queue ordering
was then still needed to distinguish task completion from an earlier
guest-state difference.

The paired queue-call probe resolved this local timing fault. At oracle
completed update 1247, the coordinator sent both `0x800fe4b8` and
`0x800fe8a8` during consumed VI 2857; native sent those messages on VIs
2650 and 2651. Replaying native with full rendering around the window did
**not** remove the extra VI, ruling out fast-replay skipping as the sole
cause. The second native task had command size `0x1f` and rendered to private
off-screen target `0x34c2c0`, while the runtime's immediate completion rule
covered only the `0x1b` variant. Native now preserves and completes both
observed tiny variants immediately, including under accelerated replay, with
the existing fail-closed displayed-framebuffer check.

The bounded 3,200-VI native regression now reaches the target twice with the
same final state and byte-identical per-update hash streams. At the previously
divergent paired transition, native updates 1252 -> 1253 and oracle updates
1248 -> 1249 consume two configured VIs each and have identical canonical
actor bytes before and after; all nine player-overlay A0-A3 entry tuples
also match. This is a **local divergence fix**, not full parity: global
runtime alignment and initial Pak equivalence remain unverified, and the
broader route still has unpaired update indices.

The ledger rebase against the corrected native binary (`0b064f5`) completed
without an API call. After the same-poll resynchronization anchor, 693 paired
semantic updates matched and the next mismatch moved to native update 1265 /
oracle update 1261. The old raw update-568 index mismatch remains, so this is
still a poll-anchored diagnostic suffix, not validated global alignment. The
supervisor now recognizes a mismatch that moves beyond a rebased focus window
and queues a new bounded focus child instead of stopping at the old one. It
also refuses to launch VI-boundary analysis for a stale focus pair. One such
stale analysis was queued before this guard and failed closed; its ledger
record remains visible.

The new sealed focus has matching actor bytes at native 1264 / oracle 1260,
then exactly three differing bytes in actor 11 at `0x801baf80` (offsets
`0xee`, `0xef`, `0xff`) at native 1265 / oracle 1261. Both sides consumed two
configured VIs and one neutral controller sample between those pairs. The
replay-free VI-boundary child localized the actor onset to the first of those
two consumptions; its paired RNG seed remained equal. This is the next
diagnostic frontier, not a validated code fault or parity pass.

A bounded watch at actor word `0x801bb06c` sharpened that frontier. Both
focused snapshots start at `0xc2047dd6`; native stores `0xc20d2225` while
BizHawk stores `0xc20d21cf`, then the sampled word reconverges on the next
update. The native innermost changing generated dispatch is `0x8000bc28`,
and the oracle write PC is `0x8000bd1c` inside that same guest function. Its
guest instructions copy a 15-word source block into the actor matrix; the
observed store does not perform floating-point arithmetic. A bounded entry
probe found the same three calls and identical A0-A3 arguments on both sides
at this update, including the actor-11 call. The source block's runtime
contents or address derivation are therefore the next comparison; neither
the equal arguments nor the transient reconvergence prove the entire guest
state or generated code is equivalent.

The source-buffer watch moved the dependency one step earlier. The oracle's
per-instruction load hook identified source word `0x8036022c` for the copied
actor word. Both sides repeatedly overwrite that scratch buffer after the
matrix copy, so completed-update snapshots cannot establish its value during
the call. During the divergent update, native's focused source watch sees
`0xc09a0ce0 -> 0xc20d2225` in generated dispatch `0x80074acc`;
BizHawk's write callbacks land at `0x80074d84` and `0x80074d94`, with the
eventual source word `0xc20d21cf`. That guest function performs
floating-point matrix arithmetic before the store, unlike
the downstream copy. The next gate is a bounded operand trace at that source
writer: prove whether its input matrix/scalar words and FPU control state
match at equivalent execution points before changing arithmetic or timing.

The first bounded FPU-entry probe is now available without API billing. Its
optional `--entry-fpu` mode records the raw low/high words of all 32 CP1
registers alongside each focused `--entry-target`/`--entry-pc` call. An
oracle-only register catalog confirmed that BizHawk exposes those words as
`CP1 FGR REGn_lo` and `CP1 FGR REGn_hi`; the native side reads the generated
`recomp_context` FPR block. The 3,200-VI native and 3,100-frame oracle jobs
both completed with pinned selected input and initial flash. For the source
writer's matching actor-11 call (`A0=0x80360138`), native update 1265 versus
oracle completed-update 1260 has seven differing low FPR words: F0, F3, F4,
F10, F19, F23, and F26. The corresponding writer calls on the immediately
preceding and following paired updates have all 64 raw FPR words equal.
The sealed local run directories are `tools/private/autonomy/native-fpu-entry-20260924a`
and `tools/private/autonomy/oracle-fpu-entry-20260924a`; the machine comparison
is `tools/private/autonomy/entry-fpu-compare-20260924a.json`.
This localizes a transient difference to the writer's entry state, before
its matrix arithmetic and the downstream actor copy; it does not yet prove
whether the upstream fault is a gameplay-value calculation, timing, or a
different pre-entry execution path. The next gate is tracing the first
producer of the differing F0/F3/F4 words and validating the source memory
operands at that call. The partial route, initial Pak, and global alignment
are still not accepted as parity.

Correction after the parent-function probe: most of the seven FPR differences
at `0x80074acc` are **not live operands** there. The continuation reloads F0,
F3, and F4 from A1, while the earlier `0x800743d0` function overwrites F23
from compressed data. At the parent entry, all four A0-A3 argument tuples
match. The fourth actor-11 call has a one-count T9 difference at entry, but
the function recalculates T9 at `0x80074440`; it is not an established cause.
The wider, 256-byte entry-memory trace has identical A3 bytes on both sides,
including the start of the compressed data reached via A2's `0x34` pointer.
Its four mismatching words are three A1 words at offsets 84, 140, and 212,
plus one A2 word at offset 176. Static inspection finds no direct A1/A2 load
in the `0x800743d0`–`0x80074acc` block, but indirect or later use is not
excluded. The GPR trace at the continuation still has a transient T2
difference and the FPU trace still has F23 different. These observations
move the next diagnostic gate *inside* the compressed-data decode, not to a
production patch: compare instruction-level values around `0x80074440`,
`0x800744c8`, and `0x800744d4`, including indirect load words and FPU control
state. The sealed probes and comparisons are under
`tools/private/autonomy/{native,oracle}-entry-{memory,gpr}-20260924a`,
`tools/private/autonomy/{native,oracle}-entry-memory256-20260924a`, and
`tools/private/autonomy/{native,oracle}-continuation-gpr-20260924a`.

Instruction-level diagnostic update, 2026-09-24: the opt-in private-root
instrumenter `scripts/phase9_instruction_probe_root.py` adds bounded native
callbacks at guest PCs `0x80074434`, `0x80074440`, `0x800744c8`, and
`0x800744d4`. The original normalized generated root is unchanged. Native
replay refuses to call the trace complete unless all four sites are observed;
`scripts/compare_phase9_instruction_probe.py` requires an explicit
native/oracle update pair, actor A0, and occurrence number. It never infers
global input-clock alignment. Oracle `--entry-fcr` captures FCR31 per call.
All of these artifacts are diagnostic-only.

The private four-PC native build and replay completed at 3,200 retraces with
64 bounded instruction hits. Four BizHawk jobs completed at frame 3,100,
one per PC, with identical selected input and initial flash. At the first
actor-11 call (`A0=0x80360138`, native update candidate 1265 versus oracle
completed-update counter 1260), the raw F4 operand before `cvt.w.s` is equal:
`0x440ba000`, exactly 558.5. At the next site native F4 contains integer
`0x22e` (558), while BizHawk contains `0x22f` (559). Oracle FCR31 at that
exact call is `0x01000800`, whose low two rounding-mode bits are zero; the
native host reports nearest rounding. The second actor-11 call at the same
paired update reconverges by `0x800744d4`. The per-call comparisons are
`tools/private/autonomy/iprobe-4pc-occ{1,2}-verified-20260924a.json`;
these also verify ROM, selected input, initial flash, and BizHawk identity
across the per-PC jobs. Provenance is
in `tools/private/ipr2/instruction-probe-manifest.json` and
`tools/private/autonomy/native-iprobe-4pc-20260924a/native-result.json`.

This is **not** an authorized native gameplay fix. The NEC VR4300 manual's
rounding-mode table specifies nearest with ties to an even least-significant
bit for mode zero, which agrees with native's 558 for an exact 558.5 tie.
BizHawk's observed 559 conflicts with that documented CPU rule. Treat this
as a local oracle-semantics conflict requiring an independent CPU/hardware
check, not as proof that native arithmetic should be changed to 559. The
global partial-route input/update alignment remains unvalidated, and no
parity or full-route gate is closed by this result. Manual source:
https://www.bitsavers.org/components/nec/mips/1995_NEC_VR4300_MIPS_RISC_Microprocessor_Users_Manual.pdf

Independent CPU check, 2026-09-24: the pinned Mupen64Plus cached mode (`Core=1`)
and an isolated pure-interpreter mode (`Core=0`) produced byte-identical
FPU traces and final RDRAM for this game prefix; both yielded 559 at the
same tie. A direct Goldwood replay under Ares64 was rejected because its
fresh FlashRAM hash and early frame timing differ, so it was **not** used as
an aligned game-route oracle. Instead, `scripts/phase9_cpu_rounding_build.sh`
assembled a tiny private test ROM with the user's local CIC-6105 bootcode;
the generated ROM remains ignored under `tools/private` and contains no game
payload. The private derivative is
`tools/private/cpu-rounding-20260924a/cpu-rounding.n64` with SHA-256
`ac4541020db8febcb2554b525c0fed6a17bac81ccddbe7866b823ac710aca8f1`;
the assembled payload SHA-256 is
`8abcd8ef58771f399fa23bd86b6a005ddb2fe58b6a3e0ddadc63bc4d631d5fe3`.
Its only program converts raw float `0x440ba000` under FCR31 mode
zero and stores the result in RDRAM. The bounded `phase9_cpu_rounding_run.py`
ran that exact ROM separately in BizHawk's Mupen64Plus and Ares64 cores.
Mupen returned 559 with FCR31 `0x00000000`; Ares64 returned 558 with FCR31
`0x00001004` (also mode zero). Both runs completed and verified the operand,
marker, ROM digest, and isolated core config. The checked machine artifact is
`tools/private/autonomy/cpu-rounding-adjudication-20260924a.json`, with
disposition `mupen_oracle_semantics_conflict`; the two source results are
under `cpu-rounding-{mupen,ares}-20260924a` in the same private directory.
This resolves the *local instruction-semantics* question in favor of the
VR4300 manual and native's ties-to-even result. It does not validate global
gameplay parity or make Ares64 a drop-in route oracle. Future repair packets
must exclude this specific Mupen-only tie discrepancy as evidence for a
native gameplay patch; unrelated mismatches still require ordinary aligned
diagnosis.
The ChatGPT-authenticated supervisor now explicitly instructs implementers
and reviewers to stop rather than change native CPU semantics solely to
follow an emulator result contradicted by a pinned independent CPU test and
processor specification. This is a prompt-level guard, not a substitute for
a future mechanical adjudication gate.
An implementation packet that pins the checked
`mupen_oracle_semantics_conflict` adjudication as evidence is now rejected by
the packet validator; read-only diagnosis may still use it. This is a narrow
mechanical safeguard. It does not validate other oracle discrepancies or
prevent a packet author from omitting relevant evidence, so automatic repair
generation must still require a separately verified, aligned repair basis.

Poll-boundary diagnostic, 2026-09-24: native and BizHawk can now emit opt-in
semantic hashes at numbered controller-input polls, in addition to completed
guest-update hashes. The native hook is after latching the HLE controller
sample and before returning it to the guest; BizHawk samples in `oninputpoll`
before the core reads the injected controller state. The trace records exact
selected buttons/stick, mode, level, RNG, player, actor table/actors, camera,
globals, and the optional completed-update counter. The streaming
`scripts/compare_phase9_poll_hashes.py` checks one selected sample per poll,
producer/initial-state pins, contiguous indices, and full semantic mismatch
windows without treating different emulator frames and native VI retraces as
the same clock. `scripts/phase9_poll_semantic_pair.py` runs both bounded
captures and comparison with one command under ignored `tools/private`;
repeating a completed command reuses its pinned artifacts, while an
interrupted side is preserved and rejected for explicit recovery. It makes no
model or API call.

```powershell
python -m scripts.phase9_poll_semantic_pair tools/private/autonomy/poll-pair-new --source SELECTED_EXPORT --executable NATIVE_EXE --emulator EMUHAWK_EXE --rom US_ROM --rom-sha256 ROM_SHA256 --target 1500 --timeout 300
```

The real 1,500-target pair at
`tools/private/autonomy/poll-pair-1500-20260924b` completed and reproduced
identical input values across all 659 shared polls. The first semantic
difference is poll 16 (native 13 completed updates, BizHawk 12). The 189
mismatching polls form windows 16–71, 494–573, and 575–627; sampled state
reconverges at polls 72, 574, and 628. An immediate rerun reused the sealed
pair in under a second. This localizes cadence-sensitive windows much earlier
than the raw update-568 comparison, but `alignment_validated` and
`parity_verified` remain false: hook-phase equivalence and oracle Pak identity
are not yet proved, and a same-poll difference is not automatically a native
gameplay-code defect. The paired capture is now also a ledger-scheduled,
model-free successor to the newest sealed update mismatch whose native
executable and BizHawk pins still match the installed files. `advance` queues
one 1,500-retrace poll pair with a private evidence packet; `run-once` executes
it with a guarded child process, heartbeats, input/tool hashes, restart
containment, and a sealed result. A stale baseline is skipped rather than
silently comparing a newly built binary against an old seal. The existing
standalone pair above predates this ledger job and remains standalone. The
first live successor, `poll-pair-7a1d7a9656b31f5a4ab33a55`, followed a fresh
current-binary update rebase and sealed 659 shared input polls under
`--max-agent-attempts-per-day 0`. It reproduced the same three mismatch
windows (16-71, 494-573, 575-627), with the first mismatch at poll 16 and
native/oracle completed-update counts 13/12. The ledger audit then verified
51 passed seals with zero integrity issues. The job still marks both `alignment_validated`
and `parity_verified` false. Neither the scheduler nor the paired producers
use an AI model or API billing.
At this 1,500 target, opt-in tracing left both endpoints unchanged against
fresh no-trace runs: native's final state hash and BizHawk's final 4 MiB RDRAM
hash matched their respective traced runs. This is an instrumentation-neutrality
check for one prefix, not a whole-route guarantee.
Separately, the source-pinned `native-det-046f08dc706c313539cfc7c3` job
sealed 100 identical native VI/update streams and final hashes for the same
4,800-retrace partial prefix; it says nothing about the full campaign.

Poll-lag successor, 2026-09-24: the model-free
`poll-lag-718bebb320d4f7633691078c` job independently rechecked the sealed
comparison, input, producer manifests, and traces. Among 189 same-poll state
mismatches, 179 native states have a unique exact match at an oracle poll
within eight polls (+1: 52, +3: 52, +4: 75); six have ambiguous nearby
matches, and four (polls 570-573) have no nearby exact match. Only 161 of the
179 unique shifted matches also have identical controller values at those
*shifted* polls. These are state-recurrence observations, not a safe input
remapping, validated hook alignment, or a repair basis. The ledger audit
verified 52 passed seals with zero integrity issues. One earlier queued lag
packet was correctly blocked when its conservative tool pin changed during
implementation; it is retained rather than rewritten. A passed lag report now
queues one read-only cadence-diagnosis packet with twelve pinned evidence
files. Under `serve --max-agent-attempts-per-day 0`, that agent packet stays
queued while local diagnostics continue; no API billing is needed for the
lag analysis. The scheduler now also recognizes a passed poll pair whose five
actual producer/comparator script digests, selected input/save pins, native
binary, ROM, BizHawk executable/runtime, and target still match. It reuses
that sealed evidence after unrelated supervisor changes instead of scheduling
another cold capture; a changed producer or input still requires a new pair.

Controller-call phase check, 2026-09-24: the native poll row now includes its
`osContStartReadData` and `osContGetReadData` call counts. The US BizHawk Lua
oracle counts entry executions of the same two guest functions before each
`oninputpoll` snapshot. A fresh 1,500-target pair at
`tools/private/autonomy/poll-call-phase-20260924b` completed with a clean
BizHawk exit and 659 shared polls. `scripts/phase9_poll_call_phase.py` found
exactly equal start/get counts at all 659; its report still sets
`alignment_validated=false` and `parity_verified=false`. This falsifies a
simple different-*call* explanation for those polls, but does not establish
within-call ordering or identical initial controller Pak state. The same
semantic mismatch windows and first mismatch at poll 16 persist. The first
attempt reached the endpoint but crashed during BizHawk breakpoint teardown
because the new hooks were not explicitly unregistered. The Lua cleanup was
corrected, and the first attempt remains in ignored private storage rather
than being counted as a passed pair. The analysis and capture require no AI
model or API billing.

```powershell
python -m scripts.phase9_poll_call_phase NATIVE_POLL_HASHES ORACLE_POLL_HASHES --prefix-polls 659
```

Accessory-state boundary, 2026-09-24: the oracle replay's
`--domain-inventory` option now records a bounded BizHawk memory-domain inventory and
the hashes of each region in its isolated Mupen64Plus SaveRAM image. It fails
if either inventory or the expected raw-image layout is missing. The pinned US
core exposes FlashRAM but **no Controller Pak memory domain** to Lua. The raw
SaveRAM image hash was identical (`8d44deb710b0cf74bd5af7aa5e65929dc440aa7a0e8e87d1064ea5fffe9bb0a2`)
at independently isolated frame-3 and frame-120 probes and the clean
frame-1,500 poll pair. The logical FlashRAM bytes still match the native
candidate at each endpoint. This supports no *persistent save write* over
that prefix; it does not rule out reads or prove that BizHawk's four raw
32 KiB Mempaks are game-visible equivalents of the native 32-byte logical
empty-note snapshot. The machine result keeps
`native_pak_equivalence_validated=false`. The next parity gate is a
game-visible accessory-operation trace or a separately justified logical
operation comparison, not a comparison of incompatible file formats.

Automatic successor update, 2026-09-24: new poll-pair jobs request the
Mupen64Plus domain/SaveRAM inventory as part of the oracle run, verify the
raw SaveRAM image against its reported digest on reuse, and keep Pak
equivalence false. The model-free poll-lag successor now attaches the
controller-call-phase report whenever *both* producers emitted complete
counter fields. Old pairs without either counter field still run the lag
analysis; mixed or partially instrumented traces fail closed. The bounded
read-only diagnosis packet includes the sealed call-phase report in place
of the less useful pair plan when one exists. None of these additions calls
a model or establishes semantic alignment, Pak equivalence, or game parity.

Live successor proof, 2026-09-24: after the native binary changed, the
scheduler rejected the stale completed-update baseline and queued
`updates-rebase-80a572072bbc3cb20a586d21`. Its bounded native/oracle
capture sealed successfully. The current-binary poll pair
`poll-pair-d2313b5db3b877277522458d` then sealed 659 shared polls with
the oracle domain/SaveRAM inventory. Its model-free successor
`poll-lag-59daabc6b58e058772dfb900` automatically sealed both lag and
call-phase reports; start/get call counts matched at all 659 polls, while
the 189 semantic mismatch polls and three prior windows persisted. The
read-only diagnosis packet was queued with the call-phase report among its
12 pinned evidence files, but no coding agent was run. The ledger audit
verified 56 passed seals with zero integrity issues and two pre-existing
unresolved jobs. This is a verified automatic evidence chain, not an aligned
parity result or a self-fixing implementation loop.

Read-only diagnosis follow-up, 2026-09-24: the current-binary packet
`poll-lag-59daabc6b58e058772dfb900-diagnosis` was run by explicit job ID
through the ChatGPT-authenticated CLI, without API billing. Its sealed
classification is `capture_misalignment`, with `alignment: unvalidated` and no
supported first divergent retrace. At poll 16 native has 13 completed game
updates against BizHawk's 12; native's state is seen again at oracle polls
18-19, but this does not license shifting the input. At polls 570-573 there
is no nearby semantic state match within eight polls. Controller start/get
call counts match through 659 shared polls, so the next bounded experiment
must resolve event order *within* the calls and update/VI cadence, using the
same initial save state. BizHawk Pak equivalence remains unproved. No game
code fix should be promoted from this diagnosis alone.

Bounded event-order producer, 2026-09-24: `python -m
scripts.phase9_event_pair OUTPUT --source SELECTED_INPUT --executable EXE
--emulator EMUHAWK --rom ROM --rom-sha256 SHA --target 1500 --window 13:21
--window 566:577` runs both sides locally, without a model or API billing. It
pins inputs and tool digests, retains finished sides for restart, checks the
659-poll shared prefix, and writes `event-report.json` plus a hashed
`pair-result.json`. Opt-in runtime hooks record controller-start/get entry,
the exact sampled input, game-update begin/end, and consumed VI messages in
each short window; native also records the HLE exits. The trace parser rejects
missing polls, malformed or decreasing counters, unsupported events, and
unbounded output. Hook entry is not proof of within-call guest consumption.

The first live paired capture found the same controller samples across all
659 shared polls and the known first semantic mismatch at poll 16. Event
counts differ between polls 15 and 16: native consumes four VI messages and
completes no update; BizHawk consumes two and completes one. Between polls
17 and 18, BizHawk consumes 31 VI messages with no update while native
consumes two with one update. A second gap at polls 573-574 is 56 BizHawk VI
messages versus four native VI messages. This is direct scheduler/capture
cadence evidence, not evidence of a dropped input or a verified code defect.
The independently equivalent initial Pak state and a common aligned game
boundary remain unproved, so the producer always reports `parity_verified:
false`.

The supervisor now has a model-free `event-pair-packet` successor for a sealed
poll-lag mismatch. It derives at most two windows from the report's first
semantic-mismatch and first unmatched-poll locations, checks that the pinned
native executable contains the compiled opt-in event hook, and skips stale
binary pins. The guarded worker runs the one-command producer, seals the
bundle digests, and can recover a complete prior attempt after an expired
lease. Event capture is queued ahead of another read-only model diagnosis;
neither stage can classify a shifted poll state as game-code divergence.
The diagnosis successor waits while that event job is active and, after a
passed seal, substitutes the event report and two raw event streams into its
12-file evidence budget. A verified event capture is reused after a
tool-only change instead of being silently recaptured.

Live ledger proof, 2026-09-24: a current-native update rebase, poll pair, and
poll-lag job sealed in sequence. The ordinary `advance` command then queued
`event-pair-4496fc99584e2c8a26ac50b1` without a model call; its guarded
worker sealed the same 659 shared polls and the interval-15-to-16 VI/update
difference seen in the standalone capture. The ledger audit counted 61
verified seals with zero integrity issues and two historical unresolved
jobs. This proves the automatic capture transition, not full loop closure.

Windows CLI identity correction, 2026-09-24: queueing with the shell's
`codex.CMD` spelling and running with the resolved `codex.cmd` spelling
previously produced different tool pins for the *same bytes*. The supervisor
now normalizes the filename case in that identity hash without relaxing its
binary-content pin. If an older read-only poll-lag diagnosis was blocked by
this tool-pin drift, the scheduler creates one tool-digest-suffixed successor
with the same sealed evidence; it does not rewrite the blocked job.

The replacement diagnosis
`poll-lag-8623a0b565a0a609c88cde30-diagnosis-tool-3c08b5dd9513`
ran successfully via the signed-in ChatGPT CLI, with API keys removed from
the child environment. It remains `capture_misalignment`, not a gameplay-fix
authorization. The ledger audit counted 62 verified seals, zero integrity
issues, and three unresolved historical/blocked jobs.

Completed-update frontier, 2026-09-24: the model-free
`scripts.phase9_update_alignment` analyzer compared the already-sealed event
pair's full completed-update streams. The first **567** same-numbered game
update states match, even though controller-poll counts differ starting at
update 1 and same-poll state first differs at poll 16. The first actual
same-numbered update-state difference is update **568**: native is still in
front mode 3 with 11 actors after poll 570/VI 1145; BizHawk is in front mode
24 with one actor after poll 575/consumed VI 1303. This coincides with the
large oracle-only VI gap, but does not by itself prove the cause. Future
bounded event-pair bundles automatically write and digest
`update-alignment.json`; the diagnosis evidence budget uses that report when
present. Equal update states are not a proof of equal input timing or initial
Controller Pak state, so both alignment and parity flags remain false.
The fresh local smoke bundle at
`tools/private/phase9-update-alignment-smoke-20260924a` reproduced the
567/568 result, then passed a no-recapture restart. This producer did not
launch an AI agent.

Game-visible input successor, 2026-09-24: `python -m
scripts.phase9_update_focus_pair OUTPUT --event-pair EVENT_PAIR` derives a
four-update window around the first same-update state difference, replays
both sides with existing focused RDRAM hooks, and compares the exact current
and previous four-controller pads plus pressed/released button fields at
each completed-update boundary. It accepts older sealed event captures by
recomputing and pinning their update-alignment report, and verifies newer
bundles against their stored digest. It retains complete sides on restart.
The supervisor now queues this model-free capture after a sealed event pair,
records its producer and input pins, and verifies a sealed report before
giving it to a later read-only diagnosis. No model call or API billing is
required for this capture.

The local older-bundle smoke at
`tools/private/phase9-update-focus-legacy-smoke-20260924a` found **no**
game-visible input-buffer difference across completed updates 566–569,
including update 568. A matching controller buffer at this boundary makes a
simple dropped delivered input less likely, but does not prove identical
within-call reads, initial Pak state, or the reason for the 56-VI oracle gap.

Live ledger proof: `input-focus-430010b43acf3d443d4f6876` was queued from
the older sealed event capture and its native/oracle worker sealed the same
four-update result. Read-only seal verification and a repeat scheduler pass
succeeded; the ledger audit has 63 verified seals and zero integrity issues.
The diagnosis scheduler now waits for this model-free successor and, when it
passes, queues a report-digest-suffixed *new* read-only diagnosis with the
focused input comparison among its pinned evidence. Previously passed or
blocked diagnoses remain immutable.

Countdown-clock probe, 2026-09-24: `python -m
scripts.phase9_update_word_pair OUTPUT --source SOURCE --executable EXE
--emulator EMULATOR --rom ROM --rom-sha256 SHA --address 0x800a3294
--target 1500` now captures one selected guest word after every completed
update in both builds. The opt-in hook is enabled only for this diagnostic;
the pinned older executable is not overwritten. The producer validates both
traces, source and binary pins, retains completed sides on restart, and writes
`word-report.json`, `update-alignment.json`, and `pair-result.json`. The
standalone bundle `tools/private/phase9-countdown-word-pair-20260924a`
completed and passed a no-recapture restart. Its first same-numbered-update
word difference is update **553**: native `0x00000000`, oracle
`0x1c000000` at `D_800A3294`. This is a diagnostic frontier, not a root
cause or a validated cross-runtime alignment.

The focused onset capture at
`tools/private/phase9-countdown-onset-watch-20260924a` explains why. The
oracle first decrements the transition countdown in update 553 at controller
poll **559**; native first decrements it in update 557 at the *same poll 559*.
Both post-update words are `0x1c000000`, and the next several words also
match when keyed by poll. The game-visible A-button press likewise appears
at oracle update 553 and native update 557, not the same update number. The
four-update offset already exists before this transition and follows earlier
oracle-only VI gaps. Therefore the later front-mode difference at update 568
must not be handed to an implementer as proof of a bad generated gameplay
function. The actionable frontier is poll/VI/update cadence and exact
within-call input timing. Initial Controller Pak equivalence and a common
aligned game boundary are still unproved; `alignment_validated` and
`parity_verified` remain false. All captures and comparisons above run
locally without API billing.

Model-free clock-evidence successor, 2026-09-24: the scheduler now derives
`update-poll-...json` from the *sealed* event pair's complete update streams
before queuing another read-only diagnosis. It pins both stream digests, the
pair plan/result, and the analyzer version, and refuses a changed existing
artifact. The diagnosis receives this file within its fixed 12-file budget
and gets a report-digest-suffixed new identity; prior diagnoses remain
immutable. The old guidance describing update 568 as a candidate gameplay
frontier was removed. The live derived report finds a same-poll anchor at
poll **575** (native update 572, oracle update 568) followed by **84**
matching offset-paired update states. `advance_poll_lag_diagnoses` queued
`poll-lag-8623a0b565a0a609c88cde30-diagnosis-focus-f183b42f74ea-clock-874bcef9844c`
without launching a model. This is evidence for scheduler/capture cadence,
not proof of end-to-end parity or permission to alter gameplay code.

Early Controller Pak activity check, 2026-09-24: bounded, independent entry
probes of the original US libultra PCs observed `osPfsIsPlug` twice on each
side. The first call has the same queue/output arguments at controller poll
2; the second occurs at native poll 16 versus oracle poll 18. `packInit`
enters once in the oracle before completed update 1. Neither side entered
`osPfsInit` in the first 16 completed updates; the probe wrappers correctly
failed their positive-hit contract, while their raw entry traces recorded
zero hits. The game's `packInit` assembly only calls `osPfsInit` for a
detected plugged accessory, so an initial Controller Pak data read through
that startup path is not supported by this trace. This does **not** prove
full native/BizHawk Pak equivalence or rule out later accessory activity.
The native `initial.pak` is a 32-byte empty-note snapshot, whereas BizHawk
stores four 32 KiB Mempak regions inside SaveRAM; comparing their file hashes
would be meaningless. The next alignment test should trace actual guest SI/
controller consumption and the VI/update queue phase, not equate these
different persistence formats.

Bounded SI follow-up, 2026-09-24: the focused oracle raw-DMA hook captured
14 completed transactions, including four write/read pairs at poll 574. Three
pairs share callers `0x80093254`/`0x80093270`; the fourth is adjacent to the
ordinary controller-read caller. PIF buffers remain in ignored private
storage. This shows device traffic in the long VI interval without proving
initial Pak equivalence or identifying a native defect. A 2,000-target paired
capture then found 303 matching offset-paired updates from the poll-575 anchor,
ending at the oracle stream boundary rather than a later semantic mismatch.
The scheduler's diagnostic extension guard now handles that exact
oracle-stream-ended case, with suffix-index and route-bound checks; it never
promotes resynchronization to parity.

Returned-controller-byte probe, 2026-09-24: the opt-in native HLE hook and
BizHawk caller-return hook now capture the exact 24-byte four-pad buffer
after `osContGetReadData` completes, within one or two bounded poll windows.
The US caller return PC `0x800431bc` was independently observed in all 18
`osContGetReadData` entry-register captures around the transition; the
oracle hook fails closed if the selected caller or destination changes.
`scripts.phase9_controller_return_pair` runs both captures from one command,
validates the returned-byte rows and input/ROM/runtime pins, retains complete
sides on restart, and compares by controller poll rather than raw update
number. The frozen runtime is
`tools/private/phase9-native-controller-return-20260924a` (executable plus
three DLLs, all included in its runtime digest). The authoritative local
bundle `tools/private/phase9-controller-return-pair-20260924c` finds **25 of
25** same-poll 24-byte returns identical over polls 552-576, with no
native-only or oracle-only return poll. Both complete sides were reused on
restart. This rejects a dropped or altered `osContGetReadData` return in
that window; it does not validate SI timing, the Pak state, or parity.

Provenance correction: rebuilding `build-phase9-update-word/Release` for the
new hook changed the executable bytes pinned by the older countdown bundle
`phase9-countdown-word-pair-20260924a`. Its immutable trace remains useful
historical data, but that old plan is not restart-verifiable against the
current build path. The countdown was recaptured against the frozen runtime
as `tools/private/phase9-countdown-word-pair-20260924c`, reproducing first
same-update word difference 553 and the 567-update semantic prefix, and
passing a no-recapture restart. Future paired producers pin the executable
and neighboring executable/DLL runtime digest so dependency changes fail
closed instead of silently invalidating their evidence.

Controller-return ledger lane, 2026-09-24: `scripts.autonomy.controller_return_job`
queues the same model-free paired producer with a durable packet, exact source
input/save hashes, ROM/emulator/native hashes, executable/DLL runtime hashes,
bounded poll window and caller PC, guarded process lifetime, lease heartbeat,
attempt recovery, and a sealed result. Its read-only verifier recomputes the
byte comparison from the sealed traces without recapturing. The live job
`controller-return-c755061c2ff3a3cda42ff5ee` sealed 25 shared returns,
25 matching return-byte sets, and no same-poll difference. The ledger audit
then reported 66 verified seals and zero integrity issues. This closes the
single-job supervisor plumbing proof, **not** automatic caller discovery,
automatic successor selection from arbitrary routes, the hard-kill/resume
drill for this worker, or the Phase 9.5/full-scope gates. No model or API
service was invoked by the capture worker.

Controller caller discovery, 2026-09-24: bounded BizHawk event captures now
write `controller-callers.tsv` at each `osContGetReadData` entry, recording the
observed return PC and 24-byte destination alongside poll/update/frame/VI
clocks. The local parser bounds rows, validates address and clock invariants,
and emits a pinned per-window caller report. The supervisor accepts only a
single observed caller across nonempty windows before scheduling the
controller-return byte comparison; ambiguous or missing callers do not guess
a PC. Historical event jobs without this trace remain readable but cause a
new event capture when the predecessor and native runtime remain valid.
The live restartable pair
`tools/private/phase9-event-caller-pair-20260924a` observed 34 calls: 9 in
polls 13–21 and 25 in polls 552–576, all returning to `0x800431bc`. A new
ledger event job `event-pair-36cdfeddd8e5e5f4db412365` sealed 21 calls in
its derived windows. Its native executable is event-capable but lacks the
newer controller-return hook, so the successor selector correctly declined
to chain from that pin. Controller-return job
`controller-return-8a5ab18e4c97c199eaa00c08` was then seeded using the
sealed oracle caller evidence and the explicitly frozen hook-capable runtime.
It sealed 21/21 matching shared-poll return buffers, no missing polls and no
same-poll byte difference. Automatically selecting an upgraded runtime and
rebuilding the upstream baseline remains open. Audit after the return job:
69 verified passes, zero
integrity issues. These captures need no API billing or AI model. This is
bounded caller discovery, **not** a validated game-state alignment or
full-route parity proof.

Verified runtime handoff, 2026-09-24: when a sealed event pair's native
binary lacks the controller-return hook, the scheduler now searches passed,
re-verified controller-return jobs for a hook-capable runtime with the same
ROM and emulator pins. It proceeds only if exactly one distinct native
runtime digest is available; a missing or ambiguous upgrade is not guessed.
The successor packet pins the caller-event job ID and report digest, makes
that event a ledger prerequisite, and re-verifies the sealed caller report
before capture and on later reads. The live automatic successor
`controller-return-efa1c86c017b87cc5362131c` selected the frozen runtime
and sealed 21/21 matching return buffers with no missing polls. A second
scheduler pass queued nothing. Audit: 70 verified passes, zero integrity
issues. This handoff is local and uses no API billing. At this checkpoint it
did not yet rebuild the poll/update baseline under the upgraded runtime;
no cross-runtime alignment or gameplay parity was inferred.

Upgraded baseline refresh, 2026-09-24: `poll_pair_job` now accepts a sealed
caller-evidence-linked controller-return job as an alternate predecessor.
Its packet pins that predecessor, its selected input/save files, and the
upgraded ROM/emulator/native runtime; the original baseline remains
immutable. The scheduler queues this alternate only when the return job
actually changed the native executable relative to its caller-event job,
preventing a capture feedback cycle. Live jobs
`poll-pair-fc14073630243377298e2aae`,
`poll-lag-beab4dfcd409fe563c89ca93`, and
`event-pair-631d1be08aae27f04df7aff5` sealed in sequence under the frozen
hook-capable runtime. The refreshed pair compared 659 polls; the first
semantic mismatch is still poll 16, and the refreshed event report still
finds the first interval difference between polls 15 and 16. Re-running the
return/refresh selectors queued nothing. Audit: 73 verified passes, zero
integrity issues. This is a refreshed local diagnostic baseline, not proof
of controller-clock equivalence or gameplay parity. No model or paid API
was used for these jobs.

The upgraded branch also reached input-focus capture. Its first attempt
`input-focus-e14c265fc11ca201bedf6987` stopped because the focus producer
assumed LF bytes for a JSON alignment report written with CRLF on Windows.
The producer and sealed verifier now compare the parsed report to a fresh
recomputation while still enforcing the predecessor's exact on-disk SHA-256.
The replacement `input-focus-e425e5ae2437dc146d49007e` sealed and verified;
its selected game-visible controller buffers show no first differing update.
This does not make the early state/cadence difference benign. Audit after the
replacement: 74 verified passes, zero integrity issues, four historical
unresolved jobs (including the failed first focus attempt).

The upgraded branch's read-only Codex diagnosis
`poll-lag-beab4dfcd409fe563c89ca93-diagnosis-focus-f183b42f74ea-clock-e4abf2cd4e29`
sealed without a patch. It classified the evidence as unvalidated capture
alignment, with medium confidence: 567 matching completed-update states,
poll/VI cadence differences, equal controller start/get hook counts, and
matching captured game-visible controller buffers at updates 566–569 do not
prove identical within-call consumption or initial Pak state. Its next test
is a bounded dual-side device/Pak and within-call timing trace through poll
577, anchored at the end of update 567. This is a hypothesis and test
request, not an accepted gameplay-code fix. The worker used ChatGPT login,
not API billing. Audit: 75 verified passes, zero integrity issues, four
historical unresolved jobs.

A final focus recapture under the corrected verifier source,
`input-focus-931b2ccd29eb545895fe62fa`, sealed with the same report as
the replacement above and a tool pin matching the current source tree.
Audit: 76 verified passes, zero integrity issues, four historical
unresolved jobs.
