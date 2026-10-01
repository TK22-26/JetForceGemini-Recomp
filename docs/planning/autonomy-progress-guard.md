# Investigation-level anti-stall enforcement

Implemented 2026-09-27. This is a bounded-waste control in the existing
supervisor, not completion of the autonomous repair loop or game parity.

## What changed

The original guard rollout introduced schema 2: immutable investigation contracts, job-to-
problem membership, charged attempts, independent outcome decisions, semantic
progress credits, and durable denial reasons. Version-1 jobs, attempts and
seals are preserved by the additive migration. Old results are not rewritten.
The reviewed continuation update below adds schema 3 without changing those
contracts or resetting their accounting.

The guard is enforced at lease acquisition, below individual job dispatchers.
When enabled, unregistered roots cannot launch. Descendants inherit the same
investigation across new job IDs, source revisions and worker sessions.
Mixed/unregistered ancestry is denied rather than silently creating a fresh
allowance. A trusted host registers roots; a coding worker cannot grant itself
another budget through its output. Worker isolation remains essential: this
is not protection against someone with arbitrary write access to the ledger.

Each investigation is serialized through independent grading. Supporting work
can finish successfully without earning progress credit. Failed/expired work
counts against the stall allowance. Claimed progress, file counts, test counts
and changed report wording do not reset counters.

Default forward-looking limits:

- 12 normal attempts and 1800 seconds of leased execution across the problem.
- Two no-progress outcomes, or six completed supporting jobs without a
  registered progress proof, trigger recovery or shelving.
- At most one fresh read-only review (300 seconds) and one pre-admitted
  alternative (600 seconds). These are bounded extra allowances, not resets.
- A verified progress credit resets only the local stall/activity counters.
  It does not erase elapsed execution or the cumulative attempt count.

The current production progress adapter independently checks the existing
candidate/review/replay lineage and input correspondence before crediting a
later selected-update frontier. A semantic fingerprint and numeric high-water
mark reject repeated or lower frontiers even under renamed baselines. This is
selected-state progress, not complete CPU, timing, campaign or product parity.
Other successful job types count as bounded supporting activity until their
own substantive-progress verifier is implemented.

The process runner checks the remaining investigation allowance before launch
and during one-second heartbeats. Budget exhaustion terminates its guarded
child tree. A live attempt or pending independent grade is not treated as a
new opportunity to launch duplicate work. Expiry, failure and restart retain
charges; decisions cannot be rewritten into successes.

Recovery currently uses trusted, pre-admitted jobs. The fresh reviewer is
read-only, and its answer earns no progress credit. One alternative may then
run; the problem is shelved afterward, preserving the result. Independent
admitted work remains runnable. With no runnable work and a denied queue, the
service returns `progress-stopped` and writes `investigation-progress.json`
instead of continuously replanning or reporting idle. This is not a completed
goal, an application Goal pause, or an automatic budget extension.

## Reproducible acceptance

```powershell
python -m unittest discover -s tests -p 'test_autonomy_progress_guard.py'
python -m scripts.autonomy.progress_guard_smoke tools/private/progress-guard-smoke-NEW
```

The output directory must be new. The smoke creates a small original fixture
repository and fake CLI workers, not a game or real model. It uses actual
supervisor dispatch, detached worktrees, guarded subprocesses, sealed results,
SQLite restart and independent problem selection. It retains the complete
evidence and producer digests. No account quota or API billing is required.

The trap asserts that two failed attempts run, a third never launches, exactly
one review and alternative run, independent work finishes, a hung worker is
terminated by the problem budget, self-reported progress earns no credit, a
restart cannot reopen the alternative, and the exhausted service path stops.
The initial `20260927a` smoke had invalid fixture validation commands and is
retained as a failed fixture attempt, not acceptance evidence. Corrected
captures `b`/`c` pass; `d` additionally proves live budget termination. Latest
producer-pinned acceptance is recorded in the private handoff.

Twenty-two focused tests cover migration, lineage, resource-independent work,
pause-preserving dispatch, time/attempt accounting, unchanged and regressing
frontiers, fresh-review limits, actual worker processes, named denials and
continuous-service stopping. Production evidence-adapter unit tests use mocks;
they do not establish a new native repair or game-frontier improvement.

The final full automation suite passes **441 tests** in 93.736 seconds.
Producer-pinned smoke `tools/private/progress-guard-smoke-20260927e/result.json`
passes all eleven checks in 4.687 seconds; SHA-256:
`796690b6bb292e1f4b25cd127912f178516aa565d170fb7bc39eeca42b366fbe`.
Its stalled 90-second fixture was terminated after about 1.2 seconds of leased
execution by the one-second investigation allowance. No real model was used.

## Rollout and remaining work

The main ledger was backed up to
`tools/private/autonomy/jobs.pre-progress-guard-20260927.sqlite`, migrated and
enabled while it had zero active jobs. The existing `PAUSED` marker remains.
`native-prefix-parity` is anchored to the previously completed observation
`instruction-observe-e0fadbd8b74d8f92c69a99b3`; future descendants share its
budget. This is an accounting anchor, not a claim that changed measurement
tools can consume the old observation without fresh requalification. Historical
execution predates this rollout and is not retroactively charged or credited.

No production recovery job is registered yet. Without one, the guard shelves
an exhausted investigation instead of inventing permission or retrying. The
next integration must admit evidence-grounded recovery experiments and add
independent verifiers for hypothesis elimination and repaired microcases.
General alternative generation/selection, real-model recovery effectiveness,
and the entire autonomous repair/integration loop remain unproved.

## Reviewed continuation update (2026-09-27)

The [trusted continuation API](autonomy-guard-continuation.md) now separates
explicit investigation accounting ancestry from successful job prerequisites.
A failed zero-retry job can have a fresh, explicitly admitted continuation
only while its existing investigation is active and has allowance remaining.
Admission records the exact predecessor attempt, preserves all prior charges,
and rejects exhausted, shelved, live, ungraded, or conflicting cases. It does
not reopen shelved investigations or make continuation automatic.

The first maintenance candidate passed its 21 focused tests but failed broader
validation because its isolated source snapshot omitted a required header and
six frontier fixtures assumed an existing private directory. Those failures
remain recorded. The user explicitly approved one bootstrap admission using
the tested private API, with the same original maintenance budget and charges.
The corrected source snapshot includes public source dependencies, and the
frontier fixture now creates its own expected worktree-local parent directory.

The repair passed all **463 automation tests** in 97.895 seconds. An independent
reconstruction passed the same 463 tests in 96.907 seconds, followed by a
high-confidence review approval with no blocking findings. Exactly the six
reviewed files were integrated and compared against private candidate commit
`a74a2699260727b1b8e32bc9719ca3f3773a4078`. The main branch/index were not moved.

The operational ledger is schema 3 and protection remains enabled. The original
failed job, immutable investigation definition, and all charges were retained;
neither unrelated investigation changed. The bootstrap exception has been used
once and is not a standing authorization to use unreviewed code. This closes
the failed-job admission gap, not the complete autonomous loop or game parity.

These controls cover supervisor-launched work, not arbitrary shell commands or
the foreground coding chat. Autonomous project work must enter this queue to
be governed. The design separates Codex Goal continuation from project-specific
enforcement; Goals themselves are evidence-based continuation contracts, not
this project's investigation controller. See the
[official Goals documentation](https://developers.openai.com/cookbook/examples/codex/using_goals_in_codex).
