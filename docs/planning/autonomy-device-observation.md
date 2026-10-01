# Device ordering enters the autonomous research lane

## Implemented handoff (2026-09-27)

The [bounded device observer](phase9-device-event-observation.md) originally
produced manually checked captures outside the job ledger. The research
driver could not consume them and stopped at `needs-instrumentation`.

`scripts/autonomy/device_observation.py` now independently qualifies the raw
capture pair. It checks declared replay completion, input/save/profile/target
identity, whole update-trace equality with the uninstrumented controls, all
focused 4-MiB RDRAM snapshots, executed point opcodes, event footer/counts and
exact instruction-to-point correspondence. Every GPR word, raw PC, invocation
and running-thread word must agree within each engine's two observers.
Evidence and delivered-input files are hashed again after measurement.

The bounded ordering measurement uses the previously qualified call anchor
and a selected hook occurrence between the prior return and next entry. It
requires matching raw caller/thread/stack/input prefixes, including upper
words of SP and RA. It preserves all-thread event order strictly after that
hook and before the next entry. Full registers remain in the pinned raw TSV;
the report retains boundary contexts, local event fields and phase/source
counts. No overlay address is translated and no events are shifted to align.

`scripts/autonomy/device_experiment.py` registers source-bound engineering
captures against a passed unsupported interval plan and its original
unprobed control. Registration verifies the native source-build receipt,
the oracle's retained source-file digests and guarded build, runtime images,
configured interpreter, captures and complete parent lineage. It freezes the
recomputed measurement digest. This is not a model-selected experiment or a
prediction: `prediction_observed` remains null.

Queueing authenticates the sealed envelopes and immutable registration, then
schedules a bounded read-only verification job. Queueing itself accepts no
measurement. The worker independently recomputes registration, evidence and
the complete ancestry, rechecks ancestry and backing bytes after measurement,
and seals a result only with unchanged producer identity. The worker has a
900-second bound, heartbeat, process guard, pause handling and no retries.
Consumption recomputes the sealed result again rather than trusting its pass
flag. Existing queued, running, passed or failed jobs are never relaunched.

The ordinary scheduler and bounded research driver route this new lane into
the existing investigation and typed-experiment chain. Measured device limits
are retained in feedback. Point-planner history gets bounded counts and
sequence boundaries, not an accidental dump of every raw event into its
prompt; complete evidence remains pinned.

## Live evidence and status

The registration for `interval-plan-v2-a0af5811753bad62263a186c` completed its
independent checks in 233.110 seconds. Its private record is
`tools/private/autonomy/device-runtimes/interval-plan-v2-a0af5811753bad62263a186c.json`,
SHA-256 `2bf04e2f25f814bdb90d14a8cbc1627141d3fa49d0fe55fe5df8f33a86f6b387`.
It binds the successful native-B and oracle-A captures documented with the
observer, not the rejected native-A capture or wrong-interpreter build.

The research driver automatically selected and executed
`device-observe-6a24c33d90175f4ac1483b30`. It **passed on its first attempt**,
including the full before/after lineage checks, and sealed result SHA-256
`0fe0edb58ad8e5ed816e5ce2fe7845fc2cc77a16019b3e7f0259b9fa9bd78c80`.
Qualification passes with no reasons; all 1984 shared delivered inputs match.
The result is at
`tools/private/autonomy/attempts/device-observe-6a24c33d90175f4ac1483b30/0001/result.json`.
The first driver's subsequent feedback publication failed after revalidation:
an evidence-file loop in `device_experiment.inputs` reused the registration
path variable for a string filename. The returned `plan_message` therefore
could not be pinned. The observation itself remained passed and unchanged;
no downstream model job had been queued.

Distinct registration/evidence variable names fix that handoff. A regression
test first reproduced the same `AttributeError` through the actual sealed
observation dispatcher and feedback packet construction, then passed after
the fix. It asserts that feedback pins the registration, not the last capture
file. Expensive build/ancestry adapters and final agent enqueue are mocked in
that test; the ledger, files, seals, recomputation and evidence pins are real.
Live feedback resumption subsequently **passed independent revalidation** of
the unchanged sealed result and published
`experiment-feedback-90d7236f3be51fa17e94b25a`. Its third evidence pin is the
registration path and SHA-256 above. The previously published immutable facts
were reused unchanged. No game replay or observation retry was needed.
The bounded read-only diagnosis subsequently **passed on its first attempt**,
with exit code 0, no changed paths and no stop reason. Its structured message
SHA-256 is `79b8b27a235e75fabd13b96044a273a6a65a74434c7f51387a401272235f69d2`.
It reports `insufficient_evidence`, not a validated code defect or repair.
This completes the live observation-to-feedback handoff, not the game fix.

The direct deterministic reader reports that, after the third selected
graphics-readiness hook and before pacing entry at invocation 1908, the
oracle records an additional VI dispatch/acceptance not present in native.
Both sides record an AI dispatch in this interval. This narrows the ordering
question, not the underlying cause. Native `accept:none` represents combined
pending CPU acceptance; oracle source labels identify dispatcher paths. Those
labels are not independently matched physical interrupts. Native
pre-instruction Count and oracle lazy Count are not a common clock.

A follow-up read of the pinned raw TSVs confirms that the native VI is not
absent from the entire invocation: native pacing entry is sequence 1627 and
the next VI dispatch is 1652; oracle VI dispatch is 1655 and pacing entry is
1689. Both dispatch rows contain deadline word `3637804000`. These are local
sequence-order facts, not matching instruction ordinals or aligned clocks.
They locate the VI on opposite sides of pacing entry without proving why.

The sealed diagnosis keeps two alternatives open: equivalent retired work
reaching different VI phase/interrupt eligibility, or different intervening
receive/AI-handler/return/caller-loop work causing the earlier deadline
crossing. Its recommended next test is a bounded all-thread retirement and
device trace across those same anchors, including Count-update/deferred-debt
reconciliation and code/overlay identity. That new instrumentation is **not
implemented or qualified by this handoff**. Existing instruction-entry and
successor events must not be relabeled as retirement; a model recommendation
does not authorize a timing adjustment or bypass a proof gate.

A subsequent [native instruction-effect hook prototype](phase9-instruction-effect-observation.md)
now passes 12 compiled sanitizer-checked paths. Its disabled game generation
is byte-identical across all 62 output files. This supplies an ordinary/store/
branch-effect building block only; exception-return/thread boundaries, oracle
Count-debt reconciliation and the complete game trace above remain unqualified.

The subsequent [native ERET transfer observer](phase9-eret-transfer-observation.md)
now records the validated handoff before the host yields. Its fresh compiled
control/observed game captures preserve all ten existing trace/input/focused
RDRAM files and add 308 bounded transfer observations. This qualifies that
native observation on the retained prefix, not the oracle boundary, Count-debt
accounting or the complete all-thread instruction trace requested by diagnosis.

## Preserved invocation failure

An attempt to run the already queued optional operand planner used the
direct executable instead of its pinned npm launcher. The tool identity
check refused before authentication, a worktree or model process started.
`interval-plan-v2-a0af5811753bad62263a186c-operands-v1` remains blocked with
its original packet and failure receipt; it was not repinned or retried.
The original npm launcher was subsequently verified to match the job's pins.

Named agent jobs now check tool/input identity before acquiring a lease,
while retaining the post-lease check for races. A wrong invocation therefore
leaves a queued job's state and attempt budget untouched. This does not waive
the historical failure. The new device observation descends from the passed
base interval plan and newly qualified evidence, not from the failed optional
planner or a fabricated successful result.

## Verification and remaining scope

The complete autonomy suite passes 362 tests (87.488 seconds). Twenty-one new tests cover exact
instruction binding, raw 64-bit context rejection, bounded local event order,
changed full traces/snapshots/opcodes/input pins, incomplete captures,
concurrent evidence changes, source/runtime build identity, immutable queueing,
producer changes, seal/packet tampering, recomputation on consumption, pause,
no relaunch, research routing, the pre-lease tool check and successful device
observation-to-feedback publication. Worker/ledger tests
use synthetic measurement subprocess results; the live job above supplies
the separate real-evidence acceptance check. `git diff --check` passes.
After live feedback passed, the ledger audit verified 130 passed seals
among 159 jobs with zero integrity issues. Seventeen historical failed/blocked
jobs remain preserved, including the incorrect-launcher attempt above.

No game timing, input, comparison boundary or golden changed. Selected-state
parity still ends at update 1908. Global clock alignment, instruction retirement,
completed queue operations, a causal repair and physical-N64 parity remain
unproved. General proof construction, reviewed repair integration, broader
gameplay coverage and restart/endurance acceptance are still required for
the entire automation-loop goal.

## Revalidation cost reduction (2026-09-27)

The pacing reader now parses each full update trace once per side and reuses
the parsed control records only when freshly computed full-file digests are
equal. It still reads both full snapshot sets and hashes every backing trace
again after measurement and input checks. There is no persistent cache or
ancestry waiver. Three added regressions check call-local reuse, independent
parsing for different controls, and rejection of traces changed during either
snapshot or input validation.

On the retained real point-runtime registration, three loads took
1.2150982/1.1744771/1.1688132 seconds before and
1.0626322/1.0529510/1.0473698 seconds after: roughly 10.35% lower median cost
for this component, not for the entire autonomous loop. The canonical
calibration digest stayed
`4a9fdd392fede97c8ca5c92f23a17f3864b12873f09005b51e2cb994236d7285`.
Full sealed device-observation revalidation passed in 456.694 seconds with
the original result digest above unchanged. It created no model job and
reran no game. The full autonomy suite passed 362 tests in 90.362 seconds;
the focused pacing/point/device group passed 34 tests separately.

## Additional engineering evidence

The separate [oracle Count/ERET observation](phase9-oracle-cpu-boundary-observation.md)
now passes compiled-body tests and live non-perturbation checks. Its new
131033-event capture preserves the existing device evidence and reproduces
the 1908/1909 selected-state boundary. This evidence has not yet been
registered as a new autonomous producer or consumed by the sealed diagnosis.
No prior accepted result or producer registration was overwritten.

The subsequent [oracle Count-ledger lane](autonomy-oracle-count-ledger.md)
implements a separately registered supplement rather than replacing this
accepted observation. It retains the original measured history and derives
its interval directly from these qualified device/point boundaries.
