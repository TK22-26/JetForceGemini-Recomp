# Bounded state-word experiment (2026-09-26)

## Implemented transition

The [candidate feedback](autonomy-candidate-feedback.md) diagnostic can now
feed a structured experiment planner, a pinned native/oracle capture, and
deterministic measurement without a manually authored probe packet.

The initial adapter supports candidate-retest diagnoses with a frozen-source
`original-os-probe` baseline. It is not a general executor for arbitrary
research proposals. The planner selects up to twelve aligned canonical RDRAM
reads, with widths of one, two or four bytes, inside a fixed completed-update
window. Its proposal contains competing hypotheses and one equal/different
prediction. It cannot supply shell commands, executable paths, game writes,
comparison shifts, replacement inputs or different runtime pins.

Unsupported proposals return `needs-instrumentation` without launching a
speculative capture. The typed contract is checked before measurement.
Planning is read-only; no implementation or parity approval follows from a
successful observation.

The executor reuses a sealed capture only when its source, runtime, reference
configuration, input, replay bounds and focused snapshots match the baseline
requirements. Otherwise it queues one bounded capture pair. The native update
trace must reproduce the baseline byte for byte. Evidence and snapshot hashes
are checked before measurement, then checked again before sealing the result.
This is not a claim of complete hermetic producer dependency closure.

## Entry command

```powershell
python -m scripts.autonomy.state_word_experiment `
  --diagnosis candidate-feedback-126df228845178d443e38892-format-v2 `
  --agent (Get-Command codex.cmd).Source --drive
```

The command dispatches at most one planner, one paired capture and one
observation job. It does not drain unrelated jobs. Without `--drive`, it only
queues the next stage. Stable successor IDs prevent duplicate jobs, and the
existing pause marker prevents advancement. The normal scheduler also queues
these transitions before frontier exploration.

## Live acceptance

The command completed all three stages:

- Plan: `experiment-plan-41af9a5f14755ac7fed127bd`.
- Capture: `experiment-capture-410efa3bed9b16fc25fad989`.
- Observation: `experiment-observe-410efa3bed9b16fc25fad989`.

The planner selected the elapsed-step word `0x800a3374` from the saved diagnosis
and predicted a difference at completed update 1908. The measured sequence was:

| Completed update | Native word | Oracle word | Native / oracle consumed VI |
| --- | ---: | ---: | --- |
| 1907 | 3 | 3 | 4589 / 4589 |
| 1908 | 3 | 4 | 4592 / 4593 |
| 1909 | 3 | 3 | 4595 / 4596 |
| 1910 | 3 | 3 | 4598 / 4599 |

All 1984 compared input polls match. Selected game state still matches through
1908, with the first actor/camera mismatch at 1909. The native update trace is
byte-identical to the frozen-build baseline. The reference is the pinned
corrected-Mupen compatibility profile, not physical-N64 timing truth.

This reproduces the [older focused observation](phase9-execution-frontier-1909.md)
on the actual frozen-source rebuilt executable. It closes a manual automation
handoff and binds the observation to that build; it does **not** advance the
gameplay frontier or prove the cause of the timing difference. The result
explicitly retains `alignment_validated: false`, `causal_fix_proved: false`
and `parity_verified: false`.

Private results live under `tools/private/autonomy/attempts/<job-id>/0001/`.
Relevant SHA-256 pins:

- Native executable: `69a38f6de137f45bc58ddabbd2698d8dbc39249709acb20c117381fe156df1ba`.
- Native update trace: `45ee833c282ef24bd4e07f8377e0528a73aed58148b5f6d1059ea7edcac88f86`.
- Capture result: `ce0f191b23fb9988a0a8697396c4452362079857c59690cbb8c5534728ca53fa`.

Rerunning the completed command returned the same passed observation without
launching a worker or capture. The complete autonomy test suite passed 175
tests. The ledger audit verified 96 passed seals among 121 jobs, with zero
integrity issues; historical failed/blocked and queued jobs remain.

## Remaining boundary

The interval-feedback handoff exposed a prompt-size bug on 2026-09-27:
`prediction_observation` can contain full boundary/register/event records,
not just a small value row. New word-plan prompts use an explicit compact
projection of checked outcomes, including qualification failures and null
predictions. Full observation files remain hash-pinned; raw reports are not
truncated or changed. The existing 20,000-character pre-enqueue validation
remains in force, and existing plans keep their immutable identities/results.

The next gameplay investigation is upstream execution/device timing around
1908, not forcing the elapsed-step value to match. The general automation loop
still needs additional experiment primitives and reviewed proof production,
protected repair selection/integration, broader regression and exploration,
and unattended endurance acceptance. The
[measured-result feedback](autonomy-experiment-feedback.md) now carries that
observation into the next investigation and enforces experiment history.
It does not autonomously implement every proposed next fix.
