# Bounded completion of interrupted research

## Problem and accepted live transition (2026-09-27)

The [instruction-point experiment](autonomy-point-experiment.md) produced a
qualified measurement, but its next investigation used its entire 480-second
budget without writing a structured diagnosis. Restarting that same research
would repeat work; treating its raw transcript as a successful diagnosis would
invent an accepted result.

The driver now has a single synthesis-only successor. It checks the failed
attempt, preserves its full transcript and failure, independently rechecks the
measured observation, and freezes a bounded research checkpoint. A read-only
worker receives selected measurement fields and explicitly clipped command
output excerpts as data. It may propose the next falsifiable experiment, but
may not conduct another investigation. Results involving new tool calls are
rejected, as are claims of validated alignment, a first supported retrace or a
proved code divergence. This is hypothesis continuation, not proof production.

The actual failed investigation was recovered this way:

- Original: `experiment-feedback-569bb45c7b8220f004d58ee6`, still blocked;
  elapsed attempt time 481.53 seconds, no final diagnosis.
- Successor: `research-completion-ea1b284f199374f438429da8`, passed in 86.38
  seconds with a clean private worktree and no tool calls.
- The full transcript contains 24 completed command receipts. The immutable
  checkpoint retains their output hashes and bounded excerpts; the 16,109-
  character prompt fits four recent excerpts alongside the measured history.
  Omitted material is explicitly identified, not represented as inspected.
- Accepted diagnosis SHA-256:
  `7adb62641d0fa3b68e619b358ec92610e77038680b790cec76ac2cb25f95911d`.
- Accepted synthesis event stream SHA-256:
  `2a53edea77528fb8fe7dc5ca22f77269054e5b10a9627d1398247225227d3503`.
- The driver consumed this result and automatically queued
  `experiment-plan-289f095f018156768129c0b2`. That planner passed with an
  explicit `needs-instrumentation` result: completed-update word reads cannot
  determine transient queue/receive ordering.
- The entry and point planners also completed with `needs-instrumentation`
  (`entry-plan-74bef6aeeed1c7736091b78e` and
  `point-plan-fc11205d03db6b5e0e95748a`). The three-job continuation stopped
  there without another game capture. In particular, the instruction
  inventory derived from this diagnosis contained no new direct JAL/NOP
  anchor candidate; that is not evidence that no useful anchor exists in the
  game or in earlier observations.

The resulting hypothesis distinguishes earlier message availability from
receive/control-flow differences or incompatible capture windows. It is not a
new gameplay finding: root-driven calibration already established a 2/3 queue
count on pacing entry, and the machine point experiment already measured 4/5
receive calls. Selected-state comparison still passes through 1908 and first
differs at 1909. No game code, input, timing or comparison criteria changed.

## Contract and failure behavior

`scripts/autonomy/research_completion.py` accepts only the canonical failed
feedback job for a sealed word/entry/point observation. Eligibility requires:

- Exactly one terminal attempt, no retries and no existing final message.
- A timeout-related failure and an elapsed attempt at least as long as its
  declared budget; a completed transcript cannot use this path.
- Contained prior children, an exited guard owner, and an unchanged private
  source worktree at the expected commit.
- Matching original packet/ledger/source/measurement lineage.
- A freshly recomputed observation before checkpoint publication.

The historical snapshot-error wording is accepted only with these additional
timeout/containment checks. Other failures, active jobs, dirty worktrees,
completed diagnoses and repeat completion attempts do not receive extra work.

Checkpoint evidence is hashed before and after extraction. Re-enqueue after
interrupted publication must reproduce the same checkpoint bytes. The original
failed job is referenced as retained failure evidence, never converted into a
passed prerequisite. The new job retains the original passed replay/baseline/
observation prerequisites and has a fixed 180-second budget, no retries, no
validation commands and no allowed edits. If synthesis fails, that lane stops;
there is no synthesis-of-synthesis fallback.

The normal worker seals the synthesis transcript hash. Initial acceptance,
completed-result recovery and later diagnosis consumption all check that hash
and reject tool-use events or unsupported certainty. The existing authenticated
worker is used; no API billing dependency was added. Daily agent-attempt limits
count this job like other model jobs.

The first live compact summary omitted some qualified caller/input and
registered calibration context. Future checkpoints now retain probe addresses,
qualification scope, input-prefix results and the already independently
recomputed runtime-calibration measurements, with the calibration file pinned
before and after reading. This prevents loss of known evidence merely because
it arose during instrumentation qualification. The live checkpoint and its
accepted diagnosis were not rewritten or rerun; the richer summary path is
unit-tested but has not yet produced a second live diagnosis.

The bounded research driver and ordinary scheduler both select this successor
automatically. It is also covered by pause and immutable-evidence checks. This
does not turn an unsupported experiment into an arbitrary command, bypass a
failed capture qualification, merge a repair or certify parity.

## Verification and remaining scope

Tests cover real ledger publication, a real fake-worker process, no-tool output
sealing, recovery with tampered transcripts, output certainty restrictions,
changed retained evidence, dirty/uncontained/ineligible attempts, truncated
log tails, duplicate receipts, prompt bounds, interrupted publication, one-time
dispatch and terminal failure behavior. These are not a new live hard-kill or
multi-day endurance proof.

The complete autonomy suite passes 251 tests. The final ledger audit verifies
112 passed seals among 138 jobs with zero integrity issues; 14 historical
failures/blocks remain, including the intentionally preserved original timeout.
Repository hygiene reports the same five pre-existing findings in the OS-clock
document, PI microtest/trace and task-recovery helper; none is waived.
`git diff --check` passes. No main commit/push or candidate promotion occurred.

The next engineering step is to expose prior qualified caller anchors to
experiment selection and qualify observations across the earlier queue/event
boundaries. New typed experiments must distinguish remaining explanations;
another pacing-count measurement would duplicate existing evidence.

That history handoff is now implemented and live-checked in the
[history/interval continuation](autonomy-interval-observation.md). It restores
two caller candidates without altering old results. The refreshed planner
identifies a genuine cross-thread/pre-entry observation limitation; an
engineering interval analyzer now qualifies the additional reference send-call
entry. Typed autonomous interval selection and operation-completion evidence
remain open.

The full objective still requires generalized independent proof construction,
reviewed repair integration and continuation, broader gameplay coverage, and
restart/endurance acceptance. The present change closes the timeout-to-next-
experiment handoff; it does not redefine those remaining requirements.
