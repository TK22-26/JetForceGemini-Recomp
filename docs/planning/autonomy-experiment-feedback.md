# Experiment feedback and repeated-test prevention (2026-09-26)

## Implemented transition

The [state-word experiment](autonomy-state-word-experiment.md) now feeds its
measured result into a new read-only investigation. Previously, that lane
ended at an observation and needed a manually prepared next diagnostic.

`scripts/autonomy/experiment_feedback.py` derives one stable successor from
each sealed observation. Before enqueueing it, the consumer verifies the
ledger/packet/source lineage and recomputes the observation from the pinned
captures. A sealed prediction, value, or parity flag that contradicts those
measurements is rejected. Historical producer bytes need not equal current
scripts; historical evidence must still match its seals.

The diagnostic receives the complete measured experiment history, its
predictions and outcomes, prior diagnosis, source baseline and capture pins.
Both positive and falsified predictions are evidence, not implementation
authority. A positive stored-word prediction does not prove consumption,
capture alignment, or causation. Neither outcome authorizes a gameplay patch.

The ordinary scheduler prioritizes this feedback before another experiment
plan or frontier exploration. Only the affected job is dispatched by the
explicit command below; it does not drain unrelated work.

```powershell
python -m scripts.autonomy.experiment_feedback `
  --observation experiment-observe-410efa3bed9b16fc25fad989 `
  --agent (Get-Command codex.cmd).Source --execute
```

For continued planning/capture/measurement/follow-up within the same lineage:

```powershell
python -m scripts.autonomy.research_cycle `
  --observation experiment-observe-410efa3bed9b16fc25fad989 `
  --agent (Get-Command codex.cmd).Source --max-jobs 3 --execute
```

This driver dispatches only named successors, up to the supplied job budget.
It returns active, failed, paused or unsupported stages without relaunching
them. A missing experiment primitive is explicitly `needs-instrumentation`,
not a successful research outcome or a reason to call the full goal complete.

Update, 2026-09-27: an eligible timed-out investigation may now receive one
distinct [synthesis-only successor](autonomy-research-completion.md). It uses
retained evidence and cannot conduct new research. The original failed job is
not relaunched or promoted, and a failed synthesis receives no further retry.

## Enforced experiment history

A successor diagnostic retains the original candidate retest and frozen
baseline, and adds its measured predecessor as a prerequisite. The existing
planner can consume that diagnostic without a new hand-authored probe packet.
History is checked back to the original experiment; cross-baseline/window
lineages and cyclic or over-budget histories are rejected.

Version 2 of the experiment contract pins the previously measured byte ranges
and round number. Version 1 remains accepted for existing first-round seals;
the output schema itself is unchanged. A new state-word prediction must read
at least one previously unmeasured byte. Changing its label, selecting another
update in the same captured window, splitting a known word into smaller reads,
or adding an unrelated novel read does not make a repeated prediction new.

At most three state-word experiments are allowed in one baseline lineage.
The next planner must select `needs-instrumentation`, or select it earlier
when stored snapshots cannot distinguish the remaining explanations. This
limits one method, not the full project objective. It is not permission to
launch arbitrary model-authored commands or to call the entire goal blocked.
Additional qualified experiment methods and proof production remain required.

Repeated invocations do not enqueue another successor. A simulated
interruption between facts publication and enqueue resumes with identical
facts. A separate simulated interruption after observation publication but
before sealing preserves the old attempt and recomputes the local measurement
in the second attempt without launching another model or game. These tests
are not a new real-process hard-kill or multi-day endurance claim.

## Acceptance boundary

Tests cover positive/negative prediction intake, contradictory sealed claims,
changed source/lineage/evidence, read-only successor contents, duplicate
suppression, pause/budgets, scheduler priority, historical producer identity,
history inheritance, repeated-byte rejection and interrupted publication.
The final full autonomy suite passes **202 tests**, including the bounded
driver. `git diff --check` passes. The repository hygiene check still reports
the same five pre-existing warnings in the OS-clock qualification document,
PI-timing microtest/reader and task-helper reader; they are not waived.

## Live evidence

`experiment-feedback-98a8cad005ae6826f79be282` passed with a clean private
worktree and no game replay or code edits. It checked the measured history,
retained captures and source before distinguishing stored state from actual
argument delivery. Its output remains `insufficient_evidence` with unvalidated
alignment and no asserted first supported retrace.

The next proposed test observes function entry at `0x80043130`. It predicts
that the 3/4 elapsed-step difference reaches A1 in invocation 1909, but demands
qualification of call identity, hook phase, return address, complete calls and
unchanged full update traces/input prefix. Equal arguments would falsify that
delivery link; unequal arguments still would not prove the downstream fault.
The raw native and oracle entry labels have different defined meanings; the
proposal does not authorize shifting completed-update comparisons.

The bounded driver automatically queued and completed
`experiment-plan-f891c16de39b8fa3e6939cf9`. Its version-2 contract retained the
first measured address and round number. The planner chose
`needs-instrumentation`: completed-update snapshots cannot establish argument
delivery or corresponding call phases. No additional paired replay or word
observation was launched. The missing primitive needs a qualified entry-hook
executor; it is not a global blocker or a request for manual gameplay.

Follow-up: the [qualified entry executor](autonomy-entry-experiment.md) now
handles this method change. Its live plan/capture/measurement sequence passed
and automatically queued another diagnosis with mixed word/register history.
The command above now advances that lane instead of returning the earlier
unsupported-method outcome. Other unsupported experiment methods remain open.

Repeating the driver returned the same `needs-instrumentation` result with
zero dispatched jobs. The ledger audit verified 98 passed seals among 123
jobs with zero integrity issues. No jobs are active; twelve queued, two failed
and eleven blocked historical jobs remain. No code was promoted to the main
branch by this transition.

Pins:

- Follow-up diagnosis: `7a123681dd09da84a29ce7b8b47a61a8d6915da2efcf516480aab1212f046c07`.
- Successor plan result: `b206392d683a8050b9c6aae3fce23dc7bc32241146b1632aa181d16c7e0a7d6d`.

The selected-state gameplay frontier is still 1908. Remaining work includes
execution/device-event experiments with qualified capture boundaries, protected
red/green proof production, general repair selection and independent retest,
reviewed integration, broader gameplay coverage, and endurance acceptance.
This transition does not finish the entire automation loop.
