# Trusted investigation continuations

An exhausted job retry budget does not necessarily exhaust its investigation.
A trusted host can explicitly attach a fresh queued job to a completed failed
or blocked normal-work attempt while that same investigation remains active:

```python
from scripts.autonomy import progress_guard

receipt = progress_guard.admit_continuation(
    store, "synthetic-problem",
    predecessor_job_id="failed-job", job_id="fresh-job",
    reason="Test the distinct explanation recorded in the failed attempt",
)
```

After separately enqueueing the fresh job, the equivalent host CLI is:

```text
python -m scripts.autonomy.progress_guard --state tools/private/fixture-state --admit-continuation synthetic-problem --predecessor-job failed-job --job fresh-job --reason "Test the recorded explanation"
```

The API returns (and the CLI prints) the durable admission receipt. Reasons must
be 1–500 printable characters, without surrounding whitespace. This is a trusted
maintenance interface, like investigation registration and independent grading.
Workers must have neither ledger write access nor access to a host service that
exposes admission. There is no automatic proposal generation or progress classifier.

Accounting ancestry is separate from execution prerequisites. The child can omit
the failed predecessor from its prerequisite list. Every dependency it does list
must still pass through the ordinary job-store success checks, and every listed
dependency's ancestry must belong to the same registered investigation. Descendants
inherit the child's investigation through ordinary prerequisites.

Admission requires the guard to be enabled, an existing active investigation with
time, attempts, no-progress and activity allowance remaining, and no live or
ungraded investigation attempt. The predecessor's latest attempt must be completed
and independently graded as normal work. The child must be queued and unattempted,
without conflicting membership. Unknown IDs, mixed/unregistered ancestry, recovery
roles, reused children and forks from the same predecessor attempt fail closed.

Schema version 3 adds `problem_continuations`, recording the problem, predecessor
job, exact completed attempt token, child, reason and admission time. Unique
constraints enforce one continuation per predecessor attempt and per child.
Versions 1 and 2 migrate transactionally without rewriting old job specifications,
seals, attempt receipts, definitions, roots, guard-enabled state or counters.
Version 1 has no guard setting to preserve and remains disabled until explicitly
enabled, as before; version 2 retains its existing setting.

Admission and membership assignment share one `BEGIN IMMEDIATE` transaction with
validation, serialized against leases, grades and other admissions. Exact repeats
return the original receipt and timestamp while the investigation is still active
and eligible; conflicting reasons or ancestry cannot rewrite it. Shelved,
exhausted and recovery-state investigations reject even repeated admissions after
restart. Admission awards no progress and changes no investigation counter. It
does not change failure to success, retry counts, original specs, roots or budgets.
The child's lease charges the same investigation attempt count and sets its guard
deadline to lease start plus remaining cumulative execution time. Existing grading,
stall stops, heartbeat, pause, resource and success-dependency gates still apply.

Tests use isolated synthetic ledgers and original fake-worker inputs only. This
interface grants no authorization to resume any shelved operational investigation.
