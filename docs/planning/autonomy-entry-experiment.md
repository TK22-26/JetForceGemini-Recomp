# Qualified consumer-entry experiments (2026-09-26)

## Implemented path

The [measured-result research cycle](autonomy-experiment-feedback.md) can now
follow an unsupported state-word proposal with a typed `entry-gpr` plan.
The new planner translates the saved diagnosis; it cannot supply executable
commands, change input or runtime pins, or authorize a game-code fix.

The executor supports direct JAL calls with a NOP delay slot. It checks the
call target and instruction bytes against pinned canonical RDRAM, then uses
the existing native function-entry and BizHawk memory-execute hooks to retain
all 32 64-bit GPRs. Registers and argument traces must describe the same calls.
The capture is limited to the existing focused window, 1024 hits per side,
300 seconds per replay and the pinned baseline's replay targets.

Qualification requires one corresponding call per side in each focused
invocation, the expected return address and matching delivered-poll positions.
Both full completed-update traces must equal the previous capture without
entry instrumentation. All raw registers, call order and clock labels remain
in the private result. Missing or ambiguous calls, wrong callers, changed
poll positions, or changed traces make the prediction inconclusive; malformed
or changed evidence fails closed. This does not establish global alignment,
physical-N64 timing truth, downstream causation or parity.

The native hook labels the invocation as `completed_updates + 1`; the oracle
hook records `completed_updates`. The analyzer explicitly uses those declared
meanings to identify an invocation and retains both raw labels. It does not
shift, skip or weaken any completed-update state comparison.

## Durable workflow

`entry_plan.py` validates the new typed schema. `entry_experiment.py` verifies
the unsupported predecessor, source/build/reference lineage and capture
evidence. `entry_observation.py` performs deterministic qualification and
measurement. The existing update worker retains its process guard, leases,
pause handling and artifact recovery; entry argument/GPR files are now sealed
and checked during recovery too.

The scheduler and bounded research driver can execute this path without a
manually authored probe packet:

```powershell
python -m scripts.autonomy.research_cycle `
  --observation experiment-observe-410efa3bed9b16fc25fad989 `
  --agent (Get-Command codex.cmd).Source --max-jobs 3 --execute
```

Three named jobs cover planning, capture and observation when a suitable
reference capture already exists. No unrelated backlog is consumed. The next
diagnostic inherits both word and register experiment history. Per-method
budgets and repeated-probe checks prevent resetting experiment history by
switching methods. Unsupported methods still require engineering; this is not
an arbitrary-command executor or a finished self-improvement loop.

## Live evidence

The bounded driver completed:

- `entry-plan-0bb3b646799e3df43751b9c4`: the model selected entry
  `0x80043130`, direct call `0x80045248`, and A1 at invocation 1909 from the
  saved diagnosis. No probe address was supplied manually to this run.
- `entry-capture-93a0f8fdbaac57f9f3f1cd71`: native reached 4800 consumed VI;
  oracle reached frame 7200. Both argument and full-GPR traces completed.
- `entry-observe-93a0f8fdbaac57f9f3f1cd71`: qualification passed and the
  predicted argument difference was observed.

| Invocation | Shared controller poll | Native A1 | Oracle A1 | Differing GPRs |
| --- | ---: | ---: | ---: | --- |
| 1907 | 1916 | 3 | 3 | none |
| 1908 | 1917 | 3 | 3 | none |
| 1909 | 1918 | 3 | 4 | A1 only |
| 1910 | 1919 | 3 | 3 | none |

The expected return address is `0x80045250`. Both complete update traces are
byte-identical to the retained capture without entry tracing, and the input
prefix remains matched. Thus the previously observed stored-step difference
is actually delivered to this consumer; the equal-argument alternative is
falsified at the qualified call. This is stronger evidence than the prior
completed-state observation. It still does not identify the upstream CPU or
device timing fault, or prove downstream causation of every differing byte.

The observation result SHA-256 is
`b3929eaaf96ed31db9e25434c1af7a57f699cdcd8a6c4971a1a01048f3aae04a`.
It explicitly retains false global-alignment, causal-fix and parity flags.
The driver automatically queued the measured follow-up
`experiment-feedback-54f2252939dcf2ad22ada3fc` with both experiment histories,
then stopped at its three-job dispatch budget. No game-code change or
candidate promotion occurred. The selected-state frontier remains 1908.

## Verification and remaining work

The full autonomy suite passes **214 tests**. Entry-specific tests cover
typed plans, method budgets, repeated full-register probes, malformed traces,
wrong callers, ambiguous calls, input-position mismatch, observation changed
by tracing, direct-JAL/NOP qualification, schema selection/read-only planning,
and fixed native/oracle CLI bounds. Historical word tests and replay-worker
tests remain green. `git diff --check` passes. The repository hygiene scan
still reports the same five pre-existing warnings; none are waived here.

Independent re-reading of the sealed observation recomputed the same qualified
result after the final producer edits. The ledger audit verifies 101 passed
seals among 127 jobs, with zero integrity issues. The current entry capture
has live normal-completion evidence; the new entry recovery checks are not a
claim of another live hard-kill drill or multi-day endurance acceptance.

Next is the measured follow-up investigation of the upstream pacing/CPU/device
cause. Additional experiment primitives, general protected proof production,
repair selection and reviewed integration, broader gameplay coverage and
endurance acceptance remain unfinished. Argument delivery is now measured;
the entire automation loop is not complete.
