# Automation delivery plan

Build reproducible gameplay exploration and a bounded engineering repair loop.
Both support the [campaign and compatibility roadmap](JFG_RECOMP_MASTER_PLAN.md).
They do not replace human playtesting or prove full-game parity by existing.

## Current foundation

The repository contains a durable supervisor, guarded attempts, source snapshots,
review/replay handoffs, typed observation lanes, and scenario generation tools.
Bounded scenarios and negative diagnostic results have been demonstrated.
The general repair loop, complete campaign exploration, and native snapshot
equivalence remain open. Historical runs are not current ledger status.

## Remaining outcomes

1. **State-aware gameplay:** complete the bounded objectives and acceptance gates
   in the [exploration plan](phase9-5-autonomous-exploration.md), including
   generated navigation, interaction, combat, natural death/retry, and recovery.
2. **Growing coverage:** represent reachable, covered, blocked, and unknown
   branches with valid prerequisites and character/inventory variants. Room
   visits alone do not establish progression coverage.
3. **Unattended regression:** preserve original inputs and failures, reproduce
   signatures, perform bounded reduction without assuming monotonic failure,
   rerun against a matching sanitizer build, and resume interrupted batches.
4. **Evidence-led repair:** choose a qualified divergence, generate and independently
   measure a bounded experiment, produce regression coverage and a candidate,
   independently review, rebuild, and replay before crediting progress.
5. **Native resume:** inventory all execution state, prove restored/uninterrupted
   equivalence, and reject incompatible builds. RDRAM-only restoration is insufficient.

## Verification contract

- Bind every observation to source, tool, input, initial state, and profile identities.
- Qualify observation-off/on runs before using diagnostic results to infer causes.
- Preserve negative results, stopped attempts, and evidence lineage across restarts.
- Require the same route/input for candidate comparisons; reject stale or mixed pins.
- Distinguish reference-generated routes, native replay, selected-state agreement,
  whole-state equality, and accepted gameplay coverage.
- Validate the native failure path with a controlled fault and test batch restart.
- Run the slice's 100 complete deterministic repetitions; startup counts and
  varied exploration counts remain separate results.
- Treat other-region route observations as hypotheses until reproduced against
  the supported US input/profile. They do not establish another supported ROM.

## Operating constraints

Follow the [automation guide](../development/automation.md), [AGENTS.md](../../AGENTS.md),
and [progress guard](autonomy-progress-guard.md). Recover production state and
allowance before each continuation. Stop at budget, integrity, or approval gates.
Keep source writers isolated, bound resources and retries, and retain failures.

Agent adapters may change without changing evidence semantics or resetting
accounting. Benchmark available adapters on pinned tasks before adopting one;
do not infer capability from a tool listing or require new credentials silently.
Production guard requirements survive conversation restarts and compaction.

Acceptance requires an independently verified improvement and a recoverable,
bounded end-to-end workflow. Finished jobs, prompt changes, additional logs,
or repeated lower frontiers do not close that gate.
