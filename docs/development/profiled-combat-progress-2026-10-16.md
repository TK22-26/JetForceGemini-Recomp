# Profile-directed combat optimization, 2026-10-16

The no-20-FPS goal remains open. The installed profiled-math preview already contains the earlier compact timing and bounded resident-math improvements. This continuation adds qualified diagnostics and tests further candidates; it does not declare all remaining drops fixed.

## What the measurements establish

Game updates and synchronous graphics submission execute on different host threads. A later native capture shows both thread-cycle totals increasing in slow updates. Renderer fence/texture/queue waits explain only part of submission time. Wall durations include scheduling and blocking; nested costs are never added twice. Windows OS CPU-time deltas are coarse here, so use aggregate observations and preserve cycle units.

The permanent profiler now emits snapshot/decode/writeback timings, six renderer wait totals/counts, and actual submission-owner cycle/CPU-time observations. Its analyzer pairs repeated scene keys in order and reports incomplete or invalid joins. Ordinary F8 FPS logging leaves this expensive detail disabled. [Controls and interpretation](function-profiling.md); [qualification](../../evidence/high-refresh-submission-profile.json).

## Candidate decisions

| Candidate | Correctness evidence | Decision |
|---|---|---|
| Direct snapshot memcpy | Four exact recorded state comparisons | Unselected: about 0.1 ms per-update component saving, no repeatable overall improvement |
| Direct point-in-region predicate | 53,272 shadow answers; 76,699 ABI calls; 200,000 synthetic cases | Unselected: modest native saving, slow updates remain |
| Direct line-intersection predicate | 971,701 supported synthetic cases; 179,256 recorded ABI calls | Unselected: native overall improvement inconsistent |
| Closed collision BSP/arithmetic operation | 50,000 isolated cases match full CPU context, stack/globals and floating environment; periodic full RAM comparison | Feasibility only: runtime bounds, ownership, safepoints and actual-call comparison still required |
| Windows thread-dispatch profiling | Owned-thread fixture succeeds without hardware counters or driver changes | Private diagnostic; runtime validation tracked separately |

Real-time comparisons share a verified initial state where stated, but their later paths and host scheduling can diverge. Exact recorded comparisons verify preserved behavior and same-workload costs; replaying an old timing transcript is not native FPS acceptance.

Private artifacts, generated code and captures remain on D:. Failed and inconclusive attempts are preserved. The production guard remains enabled with the same investigation identity and counters. The eight-hour extension changes only admitted allowance.

Further details and historical evidence: [combat slowdown](issues/goldwood-combat-slowdown.md), [frame diagnostics](issues/frame-diagnostics.md).
