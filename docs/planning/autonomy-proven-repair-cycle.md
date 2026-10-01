# First proof-gated runtime repair cycle (2026-09-26)

## Scope and current state

The [rebuildable source baseline](autonomy-source-baseline-handoff.md) enabled a
real, narrowly qualified native runtime repair candidate. The independent
branch microtest already measured annulled `BLTZL`/`BGEZL` slots, while the
native corrected-Mupen Count profile omitted their cost.

The protected checker compiles the actual native accounting statements,
unchanged, into an independently specified instruction-stream fixture. On the
frozen baseline it reports exactly four failures: untaken kinds 4 and 5 at
16/128 iterations yield 130/1026 ticks rather than 162/1282. The other 24
qualified cases match. The candidate now passes all 28 cases. This is
extracted-block coverage, not execution of the complete game hook under all
exceptions, and not physical-N64 timing qualification.

The diagnostic and implementation workers completed, and an independent
read-only reviewer approved the reconstructed candidate after checking the
protected validation receipts. The fresh-build/gameplay retest has completed:
all 1973 completed-update records are byte-identical to the baseline, with
1984 matching consumed controller polls. Selected state still matches through
1908 and first differs at 1909. Thus this candidate fixes a demonstrated
microtest defect, but does **not** explain or advance the gameplay frontier.
It remains a private candidate, not a main-worktree change or parity approval.

## Operational chain

1. A read-only structured diagnosis is sealed against the frozen baseline.
2. `scripts.autonomy.branch_count_repair` validates its lineage, native build,
   execution profile and the independent oracle's runtime/config/trace pins.
   A model's classification or confidence is **not** the proof gate.
3. The protected `scripts/phase9_branch_count_check.py` reruns against immutable
   baseline source. Only the exact four qualified failures authorize this
   policy's implementation packet. Different/additional failures stop intake.
4. The bounded implementation worker may modify only `src/boot/native_boot.cpp`.
   It cannot edit the checker, reference, generated source or comparison gates.
5. The supervisor runs the protected check itself. Independent review
   reconstructs the patch in another worktree and reruns the same check before
   the reviewer starts. Approval is advisory, not merge/parity authorization.
6. An approved candidate is built afresh and replayed independently against
   the sealed oracle and the previous passing prefix. The sealed diagnostic
   distinguishes input mismatch, earlier regression, unchanged frontier and
   later frontier; retaining a candidate is not promotion to product parity.

`--drive` resumes only this finite case, with at most three job dispatches per
invocation. It does not consume unrelated backlog, relaunch an active job,
rerun a completed candidate or bypass the paused marker. Source/evidence
changes remain errors. The ordinary scheduler also recognizes registered
proof-gated intakes before open-ended exploration work.

The current intake policy is specifically `regimm-annulled-count-v1`. It is
not yet a general automatic proof generator for every possible divergence.
BC1 likely, REGIMM branch-and-link and other unqualified families are excluded.

## Live case

Private ledger IDs:

- diagnosis: `br-count-diag-a`;
- implementation: `bc-95d695027dda`;
- initial review: `bc-95d695027dda-review` (`needs_evidence`);
- evidence-aware re-review: `re-44ed500a0c32` (`approve`);
- build/replay: `re-44ed500a0c32-native-retest`.

The final disposition is `retained-no-frontier-gain`. The replay reached its
4800-VI bound without crashing; this is only a prefix of the recorded route.
The private candidate commit is `3052c1e704e7623ea9d6bdce8b5fd58724067d9c`,
its freshly built executable SHA-256 is
`c0ec0942f3a9877ef38e571c46020939c0d985358877ca4fbed11dc427e17052`, and
its completed-update trace SHA-256 is
`45ee833c282ef24bd4e07f8377e0528a73aed58148b5f6d1059ea7edcac88f86`.
The sealed result and underlying build/replay/guard records are under
`tools/private/autonomy/attempts/re-44ed500a0c32-native-retest/0001/`.

Repeating the bounded resume command after completion returns the same sealed
result without launching another worker or replay. The ledger audit verifies
92 passed seals among 116 jobs, with zero integrity issues and no active jobs.
Twelve queued and twelve historical failed/blocked jobs remain; a healthy
ledger does not mean those outstanding tasks passed.

Registration and bounded resume:

```powershell
python -m scripts.autonomy.branch_count_repair `
  --diagnosis br-count-diag-a `
  --baseline execution-update-f6b6450b3b760d121bfbea0e `
  --oracle-report tools/private/branch-clock-mupen-20260926b/result.json `
  --oracle-trace tools/private/branch-clock-mupen-20260926b/cpu-branch.tsv `
  --agent (Get-Command codex.cmd).Source --drive
```

## Defects exposed in the automation itself

The initial reviewer could not launch Windows Store Python from its sandbox.
The supervisor had successfully run the protected test, but its receipts
were absent from the review prompt. The reviewer correctly withheld approval.
New review prompts supply the supervisor's per-command outcome and exact
stdout/stderr paths/hashes. Those log receipts are revalidated before sealing,
during crash recovery and before a candidate retest. They do not substitute
for tests that have never run. One bounded evidence refresh is available for
an older `needs_evidence` review with successful checks but no receipts; it
does not retry rejections or indefinitely repeat a new review.

A crash-recovery test also exposed a Windows guard-record publication race:
a briefly open reader can deny atomic replacement with WinError 5. A controlled
real-file test reproduces the failure and checks a bounded atomic replacement
that preserves the old complete record and still propagates persistent denial.
After the pinned live retest finished, the supervisor's JSON publisher was
connected to that helper. Only Windows access/sharing/lock errors are retried,
for at most half a second by default; there is no delete/truncate fallback.
Producer tool inventories now include the helper. The real hard-kill recovery
test passes with an expired first attempt and exactly one successful retry,
as do the temporary-reader and persistent-denial tests.

Worker setup retained ChatGPT-authenticated `codex exec`, structured final
outputs and read-only review. No API-billing dependency or sandbox relaxation
was introduced. This follows the checked [official non-interactive guidance](https://learn.chatgpt.com/docs/non-interactive-mode)
and [authentication guidance](https://learn.chatgpt.com/docs/auth).

The initial model diagnosis also incorrectly contrasted a source-file hash
with a runtime-bundle hash as if equality were required. Those identify
different objects. Independent build/source evidence, not that model claim,
supplied the repair's lineage.

## Verification after integration

All 147 `test_autonomy*.py` tests pass, including actual Windows subprocess
termination and the supervisor retry test. A separate set of 13 branch-check,
branch-trace, execution-profile and failed-trace tests also passes (160 total).
These tests are distinct from the protected candidate's 28-case oracle check.
The completed-case resume is idempotent both before and after the guard-publisher
change. `git diff --check` passes; main HEAD and its empty index are unchanged.
The user's separate master-scope edit was not modified.

## Not yet accepted

General diagnosis-to-proof generation, bounded multi-candidate improvement,
complete build dependency closure, automatic integration under the project
gates, full regression corpus coverage and the remaining autonomous exploration
and scope gates remain open. This case must not be reported as completion of
the entire automation loop.

For the next gameplay investigation, retain update 1909 as the selected-state
boundary and 1908 as the earlier consumed-VI timing boundary. The branch-count
candidate's identical full update trace is negative evidence for this specific
omission causing that divergence. Do not tune VI constants, shift comparisons
or repeat this candidate in pursuit of a frontier gain it did not produce.

The [candidate feedback successor](autonomy-candidate-feedback.md) now uses
this negative result to queue the next bounded read-only investigation without
manual diagnostic-packet preparation.
