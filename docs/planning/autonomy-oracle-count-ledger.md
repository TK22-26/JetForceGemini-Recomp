# Oracle Count evidence enters the research loop

## Implemented (2026-09-27)

The [oracle CPU boundary observer](phase9-oracle-cpu-boundary-observation.md)
produced a non-perturbing capture, but its data were not consumable by the
autonomous research driver. A new local Count ledger and registered
observation lane close that particular handoff. They do not authorize a
repair, construct missing instrumentation themselves or complete the entire
autonomous improvement loop.

`scripts/phase9_oracle_count_ledger.py` joins every device event in the
selected invocation with the independently recorded CPU mutations. The join
uses the producer's exact event sequence, never a search for matching Count
values. CPU `device_sequence=d` means after device event d and before d+1.
Every witnessed raw Count must agree. Mutations after the final device
witness remain explicitly separate.

The selected interval uses fixed instruction-entry events. All Count
mutations from the start through immediately before the end must account
for the two boundary values exactly. Writes/resets are distinguished from
additions, unsigned wrap is retained, and an ERET does not pay its nested
lazy update twice. The report keeps raw boundaries, mutation counts by
reason/PC and ERET contexts. It does not equate lazy Count with retired work
or qualify anchor changes between mutations.

## Automated path

`scripts/autonomy/count_ledger_experiment.py` adds an immutable registration
against an already passed device-observation job. Registration independently
rechecks that parent's complete ancestry, source-bound oracle build, new
observer-off/on captures, and whole control artifacts. Its interval comes
from the parent's qualified point boundaries, not manually supplied sequence
numbers or a model-selected alignment. New C/header bytes must match the
retained built observer. Both new captures must use the same pinned cached
interpreter runtime; the off-control must have no CPU-boundary artifact.

The scheduler and bounded research driver queue a separate read-only job.
It recomputes the measurement and parent lineage, rechecks backing files and
producer evidence after measurement, and only then seals an observation.
It has a 1200-second bound, heartbeat, process guard and no automatic retry.
Existing queued/running/failed/passed jobs are returned unchanged. A changed
producer cannot run under an old job's pins. Pause checks remain active.

Measured feedback independently recomputes the sealed result and retains
the preceding device observation in history. The registration is a pinned
evidence file, not a raw TSV filename accidentally reused as that path.
Word and point planners receive bounded projections with the new measured
values and explicit qualification limits; complete per-PC and ERET contexts
remain in pinned evidence. They must not request the same Count capture
again just because a subsequent prompt discarded its contents.

## Current evidence

The direct reader reconciles **all 677 device events** in invocation 1908.
Between the parent's oracle device sequences 1644 and 1689 it accounts for
33712 lazy Count updates and four ERET boundaries. The raw modular Count
change is 618732. There is no Count write, reset or idle fast-forward in
this interval. These mechanisms are excluded locally; that does not explain
the native/oracle difference or exclude an earlier timing effect.

Seven CPU rows follow the invocation's final device witness. They are
accounted within the CPU log, but are not reported as device-witnessed.

Direct measurement:
`tools/private/oracle-cpu-boundaries-observed-20260927a/count-ledger.json`,
SHA-256 `58058d4ee4823f42372353fd1fcdec5b2f8de466794fa23a1563273fa8f57683`.
This engineering artifact is not itself a ledger acceptance.

Seventeen new workflow/qualification tests cover immutable/no-relaunch
queueing, pause, guarded sealing, producer changes, packet tampering,
fresh consumption, changed ancestry/backing data, actual feedback dispatch,
history retention, exact parent boundaries and whole-control equality.
Thirteen Count-ledger tests use the real readers and cover off-by-one joins,
contradictions, ERET double counting, Count writes/wrap, incomplete captures,
changed bytes, empty traces and compact planner history. Expensive ancestry,
build and process adapters are mocked in workflow tests; they do not substitute
for live job acceptance.
The full autonomy suite passes 379 tests (88.204 seconds); the latest focused
Count-ledger/workflow group passes 30 tests. `git diff --check` passes.

## Remaining acceptance

Live registration, independent worker sealing and feedback publication must
be recorded separately below when they complete. Existing signed results,
runtime images and control captures are not rewritten.

Live registration passed in **452.860 seconds**, against
`device-observe-6a24c33d90175f4ac1483b30`. Its immutable record is
`tools/private/autonomy/count-ledger-runtimes/device-observe-6a24c33d90175f4ac1483b30.json`,
SHA-256 `cc4521c1974b2be40d714da9a47f3b65d8ef63593325df63f29f3d9529b9ad25`.
The ordinary one-job research driver selected
`count-ledger-observe-d8ef1d4765f6260efefa848b`. Its independent measurement
**passed on the first attempt**, with qualification true and no reasons.
The sealed result is
`tools/private/autonomy/attempts/count-ledger-observe-d8ef1d4765f6260efefa848b/0001/result.json`,
SHA-256 `7920b5afbc48c9d5df6f6afd628a5cf993d2c401f047da27815493be22942c5a`.
It independently reproduces all 677 reconciled device events and the fixed
interval described above. No game replay or model worker was required for
this measurement. The same driver independently revalidated the result and
published `experiment-feedback-cb1956550a34e77eef2fd6ba`. The explicit read-only
worker ran once, but exhausted its 480-second budget without a final diagnosis.
Its failed attempt and completed command receipts are preserved; this is not
accepted diagnostic output and the original job is not retried.

The existing one-shot synthesis recovery exposed a projection gap: its older
field filter dropped Count-ledger measurements and included unbounded raw
device events. Recovery now retains the compact exact Count interval, totals,
raw boundaries and limits, and explicitly identifies omitted detail. Device
history preserves phase/source counts and selected raw boundary fields without
inlining all events. Historical word/entry/point projections and old packets
are unchanged. Fresh revalidation produced the durable checkpoint, but its
complete verified summary left too little room for the newest pre-clipped
command receipt, so prompt publication failed before launching a model.
The checkpoint and all 31 completed receipts were preserved. Prompt packing
now keeps the entire verified summary and receipt identity/exit/size metadata,
while explicitly shortening that receipt's inline output only when the older
packing path cannot fit any receipt. Original checkpoint bytes are unchanged;
oversized evidence still rejects rather than dropping verified history.

Seventeen recovery tests pass, including publication with Count values and
the large-summary fallback. The actual checkpoint produces an 18282-character
prompt retaining the 618732 Count interval and an explicitly truncated receipt;
this sizing check is not substituted for fresh qualification. The full autonomy
suite now passes 382 tests in 111.224 seconds, including the prompt-packing test.
The bounded recovery driver independently revalidated the observation and
published `research-completion-1dc69fdfb7edc3b4f0b1831b`. Its one-shot model
worker completed with exit code 0, no changed paths, no tools, and a sealed
structured diagnosis. The result is
`tools/private/autonomy/attempts/research-completion-1dc69fdfb7edc3b4f0b1831b/0001/result.json`,
SHA-256 `c16736a420c764c12e5f8ef1b156716758a58e93a38a1b5b91ee94236d3fc54b`.
The preserved checkpoint SHA-256 is
`858385f91ada9f0b8887dedba3233646dbec51354725f284116b5ac95162db8b`.

The diagnosis explicitly reports insufficient evidence, unvalidated alignment
and no supported first retrace. It retains the Count measurements and proposes
bounded pacing-queue history to distinguish delivery, consumption and observer
explanations; it does not claim the cause or authorize a repair. This accepts
completion of the synthesis workflow, not the hypothesis as independent proof.
The same one-job driver is now revalidating the completed handoff before
selecting the next plan; it cannot execute another model job in this run.

The bounded resume command is:

```powershell
python -m scripts.autonomy.research_cycle `
  --observation count-ledger-observe-d8ef1d4765f6260efefa848b `
  --agent (Get-Command codex.cmd).Source --max-jobs 1 --execute
```

Do not relaunch this command while its current driver is live. Existing job
state is durable, and a running measurement is not a request for another
emulator capture or another worker.

Selected-state matching remains through update 1908, with consumed-VI
accounting already differing there and the first actor/camera difference at
1909. The entire loop still needs general independent proof/instrumentation
construction, reviewed repair integration, broader gameplay and recovery/
endurance acceptance. Local Count agreement is not global clock alignment,
all-instruction completion, causal proof or physical-N64/product parity.
