# Durable instruction-level observations

## Implemented (2026-09-27)

`scripts.autonomy.instruction_job` admits existing off/on instruction captures
as an ordinary, bounded supervisor job. It does not depend on a model, API
billing, another manual playthrough or a new emulator run. This closes the gap
between the [engineering comparison](phase9-guest-jump-table-repair.md) and the
durable job ledger. It is not completion of the entire autonomous repair loop.

The intake explicitly names a native source-bound build, a cached-interpreter
oracle build, four distinct capture directories, an existing qualified point
probe, a bounded completed-update window and one observed invocation. Its
identity includes the request, raw evidence pins, experimental runtime pins
and the measurement-tool revision. Repeating an unchanged intake returns the
same queued/running/terminal job; it does not retry a passed or failed job.
Different native revisions are not relabeled as an old baseline or promoted
to the product runtime. Existing research packets are untouched.

```powershell
python -m scripts.autonomy.instruction_job `
  --queue tools/private/instruction-observation-request-20260927a.json --execute
```

The private request is an explicit engineering intake, not arbitrary code or
an agent-authored command. `--execute` dispatches just this deterministic job,
not the unrelated backlog. A `PAUSED` marker prevents admission/execution.
The worker has a 1200-second wall limit, 4-GiB memory limit, CPU limit, process
guard, lease heartbeat and bounded restart budget. Failure evidence is written
separately, never over a completed child result. The child can publish only a
new result for its running attempt. Ordinary supervisor restart/lease expiry
can repeat this read-only measurement once; new live hard-kill endurance
qualification for this job type has not been claimed.

## What the independent measurement proves

`scripts.autonomy.instruction_observation` rechecks:

- Native source/build/runtime bindings and the oracle's exact build sources,
  guarded rebuild receipts, observer source, DLL and runtime image.
- Input/save/profile/window identity, delivered input-poll equality and raw
  device/point correspondence. Oracle Pak equivalence remains explicitly
  unverified where the underlying input contract says so.
- Whole-file off/on equality, including complete update/retrace traces,
  focused RAM, device/point/exception records and oracle final checkpoints.
- Strict native/oracle stream completion and exact independent device,
  ERET and idle witnesses. It does not trust a prior `passed` JSON field.
- Explicit invocation-return and copied-vector correspondence, followed by
  the first differing instruction effect. Unknown correspondence stops the
  comparison; it is not normalized away. Both readers still validate the tail.
- Input/build/evidence pins again after measurement, before sealing.

A load mismatch includes the effective address computed from the **entry**
registers, signed displacement, access width and destination register. This
works when the destination aliases the base. The job also reads the retained
canonical RAM snapshots at that location and distinguishes snapshots before
the observed invocation from later ones. Signed LW, unsigned LW and LD are
explicitly supported. Unqualified instructions, phases and addresses make no
load claim. These snapshots are not a live memory-read witness and do not
identify the earlier store. Equal snapshots do not justify blaming a store.

The parent checks the child result and pins before sealing. The exported
`checked_observation` consumer authenticates the ledger seal and independently
recomputes the complete measurement before supplying it to another stage.
Neither job `passed` nor a matching prefix proves common clocks, all CPU
state, hardware retirement, causal repair, full build closure or parity.

## Verification and live result

Nineteen tests cover immutable intake, pause, pending/running/failed/passed
idempotence, changed producer/evidence, guarded dispatch without an agent,
failure preservation, independent consumer recomputation, false parity claims,
private-path/control separation, load sign extension, negative displacements,
base/destination aliasing, equal-snapshot limits and producer dependencies.
These workflow tests mock the expensive producer/process adapters; the real
measurement below is separate evidence.

The initial live job `instruction-observe-82f224611ca6938f3bc14a18` passed and
its independent consumer reproduced the result. Re-intake returned `passed`
with one attempt and no new worker. That revision's sealed report SHA-256 is
`ad872c206b43a1fbb90a49faf8a7cfad1154ba40f14b459ec3031f8fdd9670b0`.
The equal-snapshot wording guard subsequently changed the producer identity;
the old packet/result are retained unchanged, not rebound to the new code.
The final revision `instruction-observe-e7233ce1a46284f38f920ecf` also passed
its first actual supervisor attempt. Its independent consumer recomputed the
complete finding and matched the sealed result; re-intake returned the same
passed job with one attempt. Sealed report SHA-256:
`9008c6dffc945f7c8c171029cf26c2a1d101debf91e25c90655854a518bd76e6`.
The complete automation Python suite passes **402 tests** (88.687 seconds).
There were no leased, running or verifying ledger jobs at handoff. This does
not waive the separately documented patch-publication failures in 0016/0019.

On the real repaired native/reference captures, the job reconstructs 3435
matching instruction rows and the next saved-context load difference. Its
four native snapshots contain 1 and the four reference snapshots contain 0;
the first pair predates invocation 1908. This makes an earlier producer/store
investigation the next supported action. It does not establish the cause of
the actor/camera mismatch at 1909 or move the measured game-state frontier
beyond 1908.

A separate fresh comparison of the retained observer-off native and reference
update traces passes both the 1292 and 1908 prefixes, then reproduces the first
selected-state difference at 1909. The requested "pass 1291" target is met;
this is not a new claim of full-memory, CPU, timing or campaign parity.

## Remaining handoff

Admission of a new capture/build recipe is still explicit. The next integration
must use these qualified findings to select bounded earlier capture or store
provenance, retain immutable runtime/source lineage, and connect subsequent
proof, candidate, independent review and regression results back into the
same loop. Do not attach this different experimental runtime to an older
baseline packet just because selected-state hashes agree. Existing queued
legacy research is not automatically replayed or rewritten by this job type.

General instrumentation/proof construction, repair integration, gameplay
coverage expansion, complete native snapshots and full recovery/endurance
acceptance remain part of the unchanged entire-loop goal.

## Guarded predecessor qualification (2026-09-27)

The real predecessor cycle now selects an earlier invocation from a qualified
observation and launches native/reference observer-off/on captures through the
supervisor. Its first live attempt exposed a Python API boundary defect: the
stored request uses canonical hexadecimal strings, whereas both replay APIs
require integer PCs/words. The adapter now converts fresh lists at that
boundary; neither the validators nor the immutable request are weakened.

The guarded repair worker reproduced four failing native/reference off/on
subcases before the change. The updated regression invokes the actual point
validator, uses populated hexadecimal PC/word lists, checks request/recipe
immutability, and rejects malformed, out-of-range and unaligned requests.
All 44 focused instruction tests and six point-probe tests passed in the
worker; the supervisor and fresh review worktrees independently passed the
44-test suite. These counts do not claim a new full-repository test run.

The first reviewer requested missing red-test evidence. Its verdict is
preserved; a supplemental guarded review verified the pinned, ordered worker
trace and approved the same two-file candidate. Automatic inclusion of red
test receipts in the generic review bundle remains unfinished.

The repaired real cycle completed both native runs to retrace 4800 and both
reference runs to frame 7200, all with exit code zero. Qualification then
stopped at `invocation return/slot/caller continuity differs` for invocation
1907. These captures are retained but **not qualified**. No independent
follow-up observation was queued and no new parity frontier was accepted.
This is a correspondence-gate rejection, not a game crash or proof of its
cause. Do not skip instructions or relax the boundary check to obtain a pass.

The production guard shelved `native-prefix-parity` after its second failed
attempt: six total attempts, four supporting activities, approximately 1400
seconds of leased execution. Guard remains enabled, with no active jobs or
budget reset. A shelved investigation must not be reopened under a new name or
continued through direct foreground execution. Recovery integration and
independent intermediate-progress grading remain open entire-loop work.
