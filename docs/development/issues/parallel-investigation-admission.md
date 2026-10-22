# AUTO-002: Parallel admission reaches the shared attempt ceiling during live work

- Status: Original interruption confirmed; private admission headroom correction
  fixture-tested during owner-renewed solution work. General parallel supervisor
  support remains outside this correction.
- First observed: 2026-10-20 UTC, during the owner-authorized two-hour parallel
  [Tawfret rain-delay investigation](github-ally-x-rendering.md).
- Severity: investigation interruption and incomplete final checks; no game,
  save or profile corruption observed.
- Affected configuration: private parallel exception under
  `high-refresh-rendering-20261011`, alongside the cutscene-start job.

## Cause and reproduction

The owner explicitly authorized parallel work. The host recorded that approval,
retained the existing investigation/root/counters, added 7,200 seconds and one
attempt/activity allowance, and admitted one rain worker. It scoped the
serialization exception to the named cutscene peer; the guard remained enabled.

That admission left `attempts == max_attempts == 62` after both jobs had
started. When the cutscene job finished, ordinary
[progress grading](../../../scripts/autonomy/progress_guard.py) checked the
cumulative attempt ceiling and shelved the investigation. The rain supervisor's
next heartbeat rejected the shelved state and terminated its child tree.
The private admission had not accounted for peer completion triggering shelving
while the final admitted attempt was still active. The production guard's
normal contract serializes attempts; overriding admission serialization alone
does not establish compatible parallel completion semantics.

This was not exhaustion of the approved two-hour wall-clock window. The
cutscene peer ended at Unix time `1792463364.6380484`; rain work ended at
`1792463365.590463`, after about 318.3 seconds of its own leased execution.
The failed rain attempt was subsequently graded `no-progress`; that charge was
preserved rather than rewritten as success.

## Evidence and final state

Private receipt/evidence ID: `tawfret-rain-delay-20261019`, including
`owner-authorization.json`, `admission-receipt.json`, `supervise.py`,
`worker.guard.json`, immutable step results and `progress.json`.
The authoritative ledger remains the production ledger documented in
[the guard contract](../../planning/autonomy-progress-guard.md).

Read-only status at the first interrupted attempt:

- Guard enabled; investigation shelved.
- Attempts 62; activity 56; no-progress 6.
- Leased time charged: 352,124.460 seconds cumulatively.
- Limits: 62 attempts, 57 activity, 6 no-progress, 364,544 seconds.
- Existing roots, prior results and counters preserved.

Completed source/trace analysis is retained in RENDER-016. Rain steps `206`
(cross-trace overlay timing) and `307` (additional provenance/consolidation)
were queued but did not run. Their intended outputs must not be cited as
completed checks.

## Remedy and compatibility lesson

No supervisor repair, additional admission or retry was attempted before the
owner renewed authorization. A general parallel correction needs to cover admission, simultaneous
budget accounting, peer grading and termination together, with isolated fixture
coverage. It must retain cumulative accounting and stop decisions; a larger
counter chosen after denial is not a validated remedy.

An owner-approved parallel exception still needs a complete execution contract.
The successful termination demonstrates guard enforcement, not successful
completion of the interrupted investigation. Production counters must never
be reset to hide this failure.

## Owner-renewed private correction (2026-10-20 UTC)

The owner then explicitly approved looking for a solution. The trusted host
admitted the renewed rain worker under the same investigation and root, within
the original two-hour wall deadline and unchanged cumulative time ceiling.
The original failure, counters and charges were preserved. Admission reserved
headroom for both the new attempt and the named peer's completion grading;
it did not disable the guard or reset a counter. The serialization exception
remains limited to that exact peer, with cumulative concurrent runtime checked
on each heartbeat. This is a scoped private admission adjustment, not a change
to production `progress_guard.py` or general parallel semantics.

Four isolated-ledger fixtures cover either worker finishing first, with pass
and fail outcomes. In all four, grading the first worker preserves the other
live worker, its heartbeat, charged attempts, and enabled guard. Receipt:
`D:/JFG-private/tawfret-rain-delay-20261019/solution/parallel-admission-fixtures.json`.
The production renewal successfully executed the rain candidate's native
harnesses, strict runtime build and isolated preview packaging. This does not
claim all production peer-completion permutations were observed.

Previously deferred steps 206 and 307 completed under the renewed guarded
worker; their overlay/capture outputs can now be cited with that provenance.
The initial statement that they had not run describes the interrupted attempt.
Private authorization/admission receipts are
`tools/private/tawfret-rain-delay-20261019/owner-solution-authorization.json`
and `solution-admission-receipt.json`; the final guard state/charges remain in
the authoritative production ledger. The original hard stop is retained as
an informative failure, not reclassified as success.


The renewed rain solution worker then completed normally with the guard enabled;
its completion left the named cutscene peer guarded and the investigation active
(attempts 64, activity 57, no-progress 6). The owner subsequently reported the
preview startup failure. A bounded startup-repair continuation used the remaining
original window and attempt, with the same completion-headroom rule and no time
ceiling increase or counter reset. Its receipts are `owner-launch-authorization.json`
and `launch-admission-receipt.json` in the same private task directory.
