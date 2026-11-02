# Windows packaged-Python child containment

- ID: AUTONOMY-CHILD-CONTAINMENT-20261102.
- Status: repair verified by Windows regressions and actual native compiler containment; regional checks continue under the same production job; unreleased.
- Severity: high automation resource/termination control limitation; not a native-game defect.
- Affected: the current Windows packaged Python 3.11 worker launching native child processes.

## Evidence and impact

The production ledger guard remains enabled on the existing investigation and
attempt. The worker and Python helper processes belong to its Windows job with
the expected four-hour CPU cap, 16 GiB memory cap and kill-on-close flag.
However, read-only IsProcessInJob queries found the actual CMake, MSBuild and
CL descendants outside every job. The parent job's process list and accounting
likewise omitted them. No denial was overridden and no limit or counter was
reset. This is a demonstrated containment gap, not an exhausted budget.

Private evidence: `regional-automation-20261101-owner4h/guard-resource-accounting-002.json`,
`descendant-job-membership.json` and `containment-stop.json`. All three unfinished
public builds and the queued replay helpers were stopped; partial build files
and previous receipts remain retained. Earlier gameplay observations still
record what happened, but supervisor launch alone must not be described as
verified descendant containment. Earlier native process membership was not
measured retrospectively. An unpackaged interpreter explicitly attached to that same job subsequently
retained its native PowerShell child in the exact production job. This isolates
the observed failure to the packaged-worker launch configuration; the internal
Windows package/broker mechanism has not been traced.

Microsoft documents that normal child creation inherits the parent's job chain
and that parent accounting includes nested jobs. Querying a null job handle
selects the calling process's immediate job. See [nested jobs](https://learn.microsoft.com/en-us/windows/win32/procthread/nested-jobs)
and [job queries](https://learn.microsoft.com/en-us/windows/win32/api/jobapi2/nf-jobapi2-queryinformationjobobject).

## Required correction and validation

Keep the operational ledger, active attempt, owner deadline and counters.
Use an unpackaged worker explicitly attached to the same existing production
job before its execution gate opens. Verify its native child's membership
against that exact job, including descendants and cleanup. Future admission
must reject worker configurations whose child containment is unproved; a
Python-process-only smoke check is insufficient. Tests use isolated jobs and
fixture ledgers, never a disabled operational guard.

Record the actual cause, final remedy and validation here before calling the
limitation resolved. Completed regional checks and remaining work stay in the
[regional support record](regional-rom-support.md).

## Cause and implemented remedy

The supervisor accepted assignment of the Python worker as sufficient proof
of descendant containment. That assumption failed for the installed Windows
Store Python: its native compiler descendants were outside every job. It also
started workers before assignment, leaving an avoidable early-spawn race. The
observed build escape was not attributed to that separate race.

[WorkerJob.launch](../../../scripts/autonomy/process_guard.py) now checks Windows
package identity for both supervisor and child, rejects packaged workers or an
indeterminate query, creates the process suspended, assigns it to its job, then
resumes its sole initial thread. Any setup failure terminates and waits for the
child before propagating the error. Breakaway flags are rejected. POSIX callers
retain their existing subprocess/session behavior. The supervisor, native/oracle
replay, emulator bridge and CPU microcase runner use this launch path. The
existing assign API remains an attachment primitive, not a safe launch API.

New guard receipts use schema 2. Expired-attempt recovery rejects historical
schema-1 receipts because they cannot prove this stronger launch contract;
old evidence is preserved without automatic promotion or rewriting. Use an
unpackaged Python installation for guarded Windows work. Resolving a Store
execution alias to its packaged executable does not repair inheritance.

The focused tests pass actual Store-Python rejection before a sentinel can run,
no worker execution before job assignment, failed-assignment cleanup, package
query failure, breakaway rejection, native child/grandchild membership in the
exact job, kill-on-close and abrupt owner-exit cleanup. An additional regression
rejects the old receipt format. See [the regression suite](../../../tests/autonomy/test_autonomy_process_guard.py).
The complete Windows automation suite passes 470 tests with no skips or
failures, and all 11 native-replay contract tests pass. Another 26 oracle replay, emulator
bridge and CPU microcase runner tests pass with no skips. Private receipts:
`guard-suite.result.json`, `guard-other-consumers.result.json` and their original
logs (507 tests in the final affected suites, without double-counting focused
runs).

An original synthetic CMake/MSBuild/CL build then compiles, links and runs a
bounded native program through the repaired API. Actual CMake, MSBuild, CL,
linker and executable PIDs belong to the nested guard and the unchanged outer
production job. Its job accounts 2.70 user CPU seconds and 260.5 MiB peak
memory. Receipt: `native-containment-proof/result.json`. This validates the
specific native-tool chain that exposed the gap, not a full generated-game
build. API contracts: [package identity](https://learn.microsoft.com/en-us/windows/win32/api/appmodel/nf-appmodel-getpackagefullname),
[suspended creation](https://learn.microsoft.com/en-us/windows/win32/procthread/process-creation-flags)
and [thread resume](https://learn.microsoft.com/en-us/windows/win32/api/processthreadsapi/nf-processthreadsapi-resumethread).

The active continuation was recovered without a new admission, production job, deadline
or budget: an unpackaged worker was attached to the existing production job
before opening a PID-bound execution gate. Its native preflight passed; new
regional replay receipts record membership of the actual native game processes.
Historical escaped-child CPU/memory accounting cannot be reconstructed as
valid job accounting. Ledger wall-time charges and prior counters remain.

Private bootstrap failures are retained: two native preflights proved membership
but failed a cmd input/exit check; a subsequent generated helper had a quoting
syntax error and did not run; the corrected PowerShell preflight passed. These
are harness failures, not successful gameplay runs.

## Transferable lesson and remaining limits

Verify the actual native workload and descendant lifetime, not just the Python
wrapper. Package identity and pre-execution assignment are part of this Windows
launch contract. This repair controls normal descendants; it does not sandbox
malicious code or prevent an external service from launching unrelated work.
It grants no permission to reset the production ledger or bypass a denial.
No native-game behavior or public release changed because of this repair.
