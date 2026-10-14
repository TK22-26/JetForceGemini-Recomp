# NATIVE-001: Native Play access violation during extended replay

Status: intermittent failures reproduced in private native candidates; a corrupted
guest pointer byte is confirmed, but its writer/cause remains unqualified.
Not delivered. Severity: critical stability qualification blocker.

A muted hidden 120-FPS/VSync native Play replay from the preserved tutorial
profile stopped after approximately 200 seconds, before its 17,000-retrace
target. Runtime ad17e4c3 reports Windows access violation 0xc0000005 at module
RVA 0x15a9961f; the last dispatched guest target is 0x80075030 (__osException).
That last-dispatch target does not by itself identify the faulting function.
The support crash record includes a complete host stack. The input save hash is
unchanged; normal diagnostic footers and final RAM captures are absent because
the native exception exits the process.

Earlier 17,000-retrace Original-mode reference and shorter native 120/360 checks
passed. They do not cover this longer native path. The equality of those reference
states is retained as evidence, not a reason to dismiss this crash. Whether the
failure predates the CPU/matrix/equal-slot changes is still unknown.

Evidence: combat-focus-20261014/shared-extended-120 (crash/support/breadcrumb/
partial gameplay logs), shared-extended-host-load.json, extended-crash-review.json
and extended-crash-symbols.txt. Matching runtime/PDB are preserved privately.
Keep the desktop preview unchanged while locating the fault and testing the
predecessor. Do not publish generated source, ROM, or personal save data.

Transferable lesson: successful bounded state and presentation checks do not
establish long-run native stability; preserve the exact binary/PDB and separate
the exception site from the last recorded guest dispatch.

## Extended predecessor check and opt-in crash evidence

The pre-equal-slot runtime 7dd907ff also fails during the extended native route,
at approximately 208 seconds / VI 12049, with the minimal runtime's switch-error
trap (process 0xc0000409). This differs from the candidate's access violation;
it establishes an older long-route stability problem, not a shared cause.
Neither run qualifies the full native route. No foreign game/compiler was
observed by the two-second process monitors.

An explicit private RDRAM-capture session now also records the native fault's
access kind/address, host registers, last guest instruction, exception PC and
running-thread word, then writes logical RAM before the existing fail-closed
exit. Ordinary Play does not log host addresses or capture RAM. The capture is
a diagnostic, not a remedy; a render-thread fault could observe in-progress
guest state. Matching diagnostic binary/PDB and all raw runs remain private.
Evidence: predecessor-extended-120, predecessor-extended-host-load.json,
native-crash-diagnostic-baseline and extended-native-comparison.json.

The explicit-capture repeat reproduces a second access violation, at guest PC
0x80020098 reading through guest pointer 0x9f265a10 (outside RDRAM). The current
running-thread word is valid at 0x800f92a0. This does not establish the first
crash's cause. One identical-configuration run first completed 17,006 retraces
with no audio underruns; the repeat failed at 10,743. Treat the instability as
intermittent and retain both outcomes. Evidence: diagnostic-extended-120-0/1
and diagnostic-crash-symbols.txt, with the captured logical RAM kept private.

Private fault details are moved to stderr so the parent's canonical stdout trap
protocol remains intact; the first diagnostic's extra stdout text caused parent
rejection (exit 3) while correctly preserving the child's access violation/exit
4 in stderr and support logs. No crash text was lost. The diagnostic now also
records the last fully observed CPU context to locate the source of invalid
registers. Its pointer is observed only in explicit RAM-capture sessions.

The first switch-trap diagnostic build failed the generated bridge object audit:
using printf introduced CRT inline-wrapper COMDAT exports. Replacing that call
with bounded eight-digit formatting and existing stream primitives preserves the
audited bridge inventory. No audit bypass or inventory relaxation is used, and
no game was launched from the failed build. Failed logs are retained.

The captured level-model word at 0x800f5b0c is 0x1f265a10, versus 0x80265a10
in the clean candidate and delivered-preview runs. The failing host address is
the generated mapping of that invalid guest pointer; 0x9f265a10 was the host
mapping offset, not the stored guest value. The leading guest byte changed.
The pinned decomp identifies the failing function as shadow geometry work
(src/shadows.c, func_8001FD20), correcting the initial animation attribution.

A temporary opt-in model-word observer samples at existing full CPU boundaries,
retains 64 recent PCs and fails closed with RAM capture at the first valid-to-
invalid transition. It is diagnostic-only, requires explicit private RAM capture,
and never repairs the pointer or changes ordinary guest execution. Its timing
runs are causal diagnostics, not FPS qualification.

The observer's initial build stopped on shadowed-local and deprecated getenv
warnings; using the existing Windows environment-reading convention with unique
locals resolves them. No game ran from that failed build.

The first model observer run actually completes 17,012 retraces without a
pointer change or audio underrun, but its initial informational line breaks
the parent's strict canonical-child-output parser. Both child stdout and stderr
share that private protocol handle, so moving text to stderr alone was not
sufficient. This is a diagnostic protocol failure, not another game crash.
Fault details now go to an explicit .fault.txt companion beside the requested
private RAM file; ordinary successful observation emits no protocol text.
The prior run and rejection are preserved and are not counted as clean wrapper
qualification. The game itself reported a normal window-close exit.

A private hardware-watch fixture passes on twelve owned threads: three watched
writes (including a single-byte corrupting write) are observed, reads/unrelated
writes do not trigger, and restoring the debug context disarms the watch.
An optional "hardware" mode now arms one unused write-watch slot in each guest
execution thread at the existing observer boundary. A corrupting write records
the exact host instruction/stack, CPU context and RAM, then fails closed.
The software observer remains to detect writes by other threads. No external
process is attached, no occupied debugger slot is overwritten, and ordinary Play
does not install an exception observer. This diagnostic is not a gameplay fix.
Evidence: hardware-word-watch-fixture/result.json and its compiled fixture.

The first in-game hardware diagnostic stops at its own debug-register admission
check near VI 2000, before observing a corrupting write. It is not another game
crash. The asynchronous handler's armed flag is made volatile and a bounded
per-thread setup receipt records the supplied debug-register context to explain
any repeated refusal. Occupied debug registers still fail closed.

The setup receipt identifies the hardware-diagnostic rejection: RaiseException
provides ContextFlags 0x10004f, which excludes valid debug-register contents.
A second thread's apparent Dr7 is uninitialized text-shaped data, not evidence
that a real debugger occupied the slot. Volatile alone does not address that.

A second isolated fixture passes twelve arm/write/disarm sequences using the
documented suspended-thread API. An owned helper now briefly suspends only its
requesting guest thread, gets valid debug registers, configures an unused slot,
and resumes before any allocation/logging. The requester joins the helper and
continues; errors fail closed and existing debug slots remain protected.
The exception observer only handles actual owned data-watch traps. This replaces
the unqualified RaiseException setup, not the game's scheduling or memory rules.
Reference: https://learn.microsoft.com/en-us/windows/win32/api/processthreadsapi/nf-processthreadsapi-setthreadcontext .

## Corrected diagnostic qualification

Private run suspended-model-120-0 ends with code 0; normal performance footer: True. No invalid watched pointer is observed in this run. Setup receipts verify the owned thread watch configuration.

Private run suspended-model-120-1 ends with code 3; normal performance footer: False. No invalid watched pointer is observed in this run. Setup receipts verify the owned thread watch configuration.

The second run stops at the original OS exception-handler jump table (guest PC 0x80075290, table 0x800aef50). It does not trigger the model-pointer watch first. Its truncated CSV also exposes a fixture parser TypeError before the normal result receipt; recovered-result.json retains the raw failure without claiming clean performance qualification. A switch-trap snapshot is still needed to distinguish malformed target/table from scheduler context corruption.

The installed 1b0bdd0f preview also completes one 17,000-retrace native comparison. This is one clean baseline run, not proof that intermittent failures are absent. No desktop shortcut/profile or released package is changed. Evidence: suspended-model-review.json and delivered-extended-120.

The watched repeat identifies a second concrete failure at __osException's
interrupt dispatch (PC 0x80075290, __osIntTable 0x800aef50), before any observed
model-pointer change. An explicit private diagnostic now handles SIGABRT to
save the existing fault context/RAM before terminating; ordinary Play keeps
its original abort disposition. Diagnostic exception code 0xe04a4647 identifies
this deliberate snapshot. No invalid target is repaired or allowed through.
The Windows CRT documents this abort-handler logging/termination path:
https://learn.microsoft.com/en-us/cpp/c-runtime-library/reference/abort .

The first abort-capture build rejects a redundant unreachable termination after the existing non-returning fault handler. Removing that unreachable statement preserves warning-as-error checks; no replay used the failed build.

The repaired diagnostic builds successfully, but its private receipt script omitted a hashlib import at final reporting. The dependent replay correctly did not run. A separate validation request rechecks the build and produces its hash; prior failed receipts remain intact.

Two abort-capable watched Play runs and the subsequent recorded-combat-prefix
diagnostic are retained separately from performance qualification. The first
two finish without memory faults but have 100/89 audio underruns amid high host
load. A foreground status sample identifies unrelated .NET CPU/disk activity;
that sample does not explain every hitch. The next controlled-prefix capture
records per-process CPU, memory and I/O totals, not merely selected executable
names. The private directory review initially included sibling host-load JSON
files in its glob; the corrected review filters directories, preserving the
failed request and preventing its dependent replay from launching.

The hardware observer is expanded only after a twelve-thread four-slot fixture
passes. It watches the level-model pointer plus the immutable redispatch, RCP
and timer interrupt-table targets. A changed table word captures the actual
writer even if its damaged value remains inside RDRAM. Occupied debug slots
still refuse setup, and ordinary Play remains unaffected. This is diagnostic
coverage, not a proven corruption remedy.

## Bounded clock recording for reproducibility

Repeated live runs can take different paths before an intermittent failure.
An explicit finite-diagnostic Count transcript allowance may now be chosen
before recording/replay starts, up to 64,000,000 samples (2,048,000,016 bytes).
The default remains 16,000,000. Active/exhausted/finished transcripts cannot
raise their allowance or reset sample counters. Exhaustion is reported as a
sample limit, and a failed exhausted tape cannot finish successfully. Private
failure exits flush the Count stream before saving RAM so buffered final
interrupt observations are retained. Unit checks exercise record/replay bounds,
invalid limits and unchanged charges. This is separate from the production
investigation ledger: its guard, ancestry and all prior charges remain intact.
Large captures stay on the owner's evidence drive; this does not select a new
clock policy or change ordinary Play.

The first configurable-transcript build catches a missed member insertion in the private edit script. The missing limit field is added, and build/tests must pass before recording; the dependent capture correctly did not launch.

The first large Count capture reaches exactly 64,000,000 samples and stops
at the explicit sample limit (guest PC 0x80098a20), near VI 16309. No memory
fault is observed. Its replay reaches the same deliberate stop. The private
postprocessor then rejects a partially written terminal gameplay-trace row;
this is a reader failure, not a game crash. Recovered metadata uses the saved
native exit code and raw RAM; it does not invent native elapsed time or a
successful original wrapper receipt. The private reader now ignores only an
unterminated final trace row, retaining all complete records and raw evidence.
The Count file is 2,048,000,016 bytes, SHA-256
2e54d0504cc82f2cea8dd30a3a6a32a7148b21dd083a9e2cd59d78897c1eb195.
Neither the transcript bound nor this replay resolves the intermittent fault.

The 64-million-observation replay matches every guest RAM byte and save at the
same explicit sample-limit PC. All 7,836 common complete update records agree;
one extra complete record remains only in the recording because the replay's
terminal trace write was interrupted. This qualifies reproducibility of this
long non-failing route, not resolution of the intermittent corruption.

GuestBacking maps cached and uncached RDRAM through different host addresses.
A hardware watch on one linear address does not cover the other alias. A
separate private page-write mode now observes writes through both views of the
two relevant pages, single-steps the original instruction, restores protection,
and compares the model word plus all nine interrupt-table targets. It captures
the pre-write host PC if a watched word becomes invalid/changes. A twelve-thread,
two-alias fixture verifies byte corruption, same-value and unrelated writes,
reads and disarming. The mode installs only with explicit private capture;
normal Play does not protect these pages. It is a diagnostic, not a memory
repair. Writes by an unexpected concurrent host thread can still observe a
non-atomic guest snapshot; writer-PC attribution remains separate from that
snapshot limit. Native recorded-route qualification is pending.

The alias-aware observer passes the complete available 64-million-sample route:
all 4 MiB of RAM, the save and all 7,837 complete update records match the
recording at the same explicit sample-limit stop. The watched replay completes
in about 177 seconds, versus 280 seconds for recording, without changing the
recorded game state. No memory fault is observed; this validates the diagnostic
on this route and does not qualify the reported corruption as fixed.
Evidence: alias-page-replay-review.json, long-clock-replay-review.json,
alias-page-write-fixture/result.json and recorded-native-clock-receipt.json.

The alias-aware 360-FPS native recording also reaches its explicit 64-million-
sample limit without a watched memory change, near VI 14231. It retains a
second complete Count tape on D: (SHA-256
3f703e333ac72ef00c978ac224f7da7b7a32f2bd5bca056fdbe6098bc9a756af).
The diagnostic records 26 audio underruns and combat source windows around
24-26 updates/s despite roughly 350 presentations/s. This is neither clean
performance qualification nor a corruption remedy; page trapping and recording
add diagnostic cost. Continue targeted matching analysis from recorded input
rather than treating repeated non-failing live runs as proof of resolution.

## External observation of the unchanged failing executable

A private Windows debugger helper can observe the exact previously failing
052e18d5 executable without recompiling it. Admission verifies the owned child
PID/image and reads its RAM pointer using the matching PDB/PE section map. It
watches both cached/uncached views of the model-pointer and interrupt-table
pages, including all eight interrupt-offset words and nine handler targets.
While single-stepping a protected write, other debuggee threads remain suspended;
a change saves the pre-write host context and private RAM before diagnostic
termination. It never repairs a value or attaches to an unrelated process.

The twelve-thread, two-alias controlled fixture passes all 72 writes and 36
invalid transitions, including byte writes and interrupt-target restoration.
This qualifies the helper in that fixture, not the game fault. Native observation
and memory dumps remain on D: under external-memory-observer and
external-watch-native-120-0. Debugger/protection overhead and concurrent host
load exclude these runs from performance acceptance. No corruption remedy is
claimed; the delivered preview is unchanged.

The unchanged 052e18d5 executable completes both bounded 17,000-VI external
observations without reproducing corruption. The write observer handles 58,519
protected writes with zero invalid transitions. The exception-only helper passes
its controlled terminal-exception/minidump-precursor fixture and captures the
4 MiB fixture RAM, then the game run exits normally. These are negative diagnostic
observations, not crash fixes or complete owner-route verification.

The exception-only game run records 661 audio underruns and reaches only
3698 input polls by VI 17005. Thus an equal VI target under a
slow observer does not imply an equal traversal of the input route. Windows
notifies an attached debugger before application vectored handlers, so even
without protected write pages it intercepts the runtime's normal MMIO exceptions.
The helper also requests thread context on those first-chance events. This is a
concrete intrusive-observer limitation; do not use these rates as game performance
or absence of faults as stability proof. Further observation should preserve
native execution timing more closely, with transient-corruption limitations made
explicit. The observer's fixed 'pages=4' banner enumerates candidate pages;
exception-only mode protects none, as its zero watched-write count confirms.
Reference: https://learn.microsoft.com/en-us/windows/win32/debug/vectored-exception-handling .


## Read-only polling and teardown qualification

The unchanged failing executable completed one 17,005-VI run under 5-ms external
read-only polling, reaching 8,159 controller polls with zero audio underruns.
No protected pages or debugger attachment were used. The helper then failed its
final memory read during orderly child teardown; the child itself exited normally.
This is not a new game crash or a complete observer receipt. Preserve both logs.
The revised helper allows up to two seconds for process exit after a failed read,
records that terminal read error, and still fails if the process remains alive.
Both a held-corruption snapshot and a controlled unmap-before-exit fixture pass.
Polling can miss transient corruption and cannot identify the writer. A snapshot
is an observation-time dump, not a faulting-instruction capture. NATIVE-001 remains
open; the helper change is diagnostic only. Evidence: external-poll-native-120-0
and external-poll-observer-v2, including its normal-exit fixture.


The revised read-only helper completes 45,625 samples over 250.687 seconds in
external-poll-native-120-1. The unchanged old runtime exits normally at
17005 VI / 8189 controller polls, with
0 audio underruns. No watched corruption is detected. The terminal
unmap/read race is recorded and process exit confirmed. This remains one further
non-reproduction, not proof of native stability or exact writer attribution.


## External debug-register experiment

A private helper sets unused write-watch registers on owned threads of the exact
previously failing executable, without debugger attachment or page protection.
It watches the model word and the first eight interrupt-table bytes through both
cached and uncached views. All other interrupt-table bytes remain uncovered.
It briefly suspends each newly observed thread to set registers; a new thread
may execute before the next scan. Occupied watch slots are rejected. The helper
restores its own registers on bounded completion. A data-watch exception goes to
the existing executable's fault capture, so the saved RIP is after the write.
Any model write can trigger, including legitimate initialization; a capture is
not automatically memory corruption. Controlled fixtures must pass before use
on the game. Evidence: external-register-observer, kept private on D:.

Controlled cached/uncached model-byte and table-word writes reach the existing
unhandled-exception path. Read/unrelated-write and disarm fixtures also pass,
with twelve worker threads armed in each case. Game cause remains unlocated.


The first unchanged-executable register watch captures an expected model-pointer
store in shadow initialization at VI 6353 / poll 2975 (guest 0x8001d804), writing
a valid 0x80265a10. This is a deliberate diagnostic stop, not another corruption.
It verifies that the old executable's fault path saves RAM and post-write host
registers without debugger attachment. The next bounded watch starts after this
observed initialization, at VI 7000; legitimate later initialization can still
trigger and must be distinguished from corruption.

The private fixture's `hidden` summary used the final owned-window list, which
is cleared when a child exits before the loop observes its process termination.
That incorrectly reports false for this deliberate stop. The fixture did assert
the window was hidden when it attached, and its saved environment requests the
hidden diagnostic window. A revised receipt retains the actual earlier check;
raw historical receipts are preserved. This is diagnostic metadata, not a game
visibility or mute-setting change. Evidence: external-register-native-120-0.


Reviewing the original bad RAM beyond the model word shows repeating
03 00 1f 1f 1f bytes at 12-byte strides across neighboring globals, with later
writes surviving between them. The model byte is part of broader structured
corruption, not evidence of a lone random bit flip. A source-pattern search
records candidate byte-store loops and the actual run extents. Pattern similarity
alone does not identify the executed writer; the filtered watch remains the
causal check. Evidence: corruption-byte-pattern.json and the preserved original
RAM capture. This observation does not yet justify changing game lighting or
shadow routines.


The after-initialization watch reaches VI 12833 / poll 6245, then stops on the
same legitimate shadowInit store (guest 0x8001d804, post-write host RVA 0x20c9d9f6)
with model value 0x80265a10 and canonical interrupt handlers. It does not capture
the corrupting write. Moving admission later cannot cover this repeated valid
initialization reliably. A private observer therefore adds a narrowly filtered
vectored handler to the unchanged failing executable: only the exact verified
post-store instruction, expected pointer value and owned model-watch slot may
continue. Other instructions, values, watched tables and exception types retain
the existing fault path. This changes the diagnostic process/module layout and
can still affect reproducibility; it is not a runtime repair or stability proof.
Controlled fixtures must qualify filtering before any game run. Evidence:
external-register-native-120-after-init and filtered-register-observer.


## Shadow polygon scratch-buffer lead

The preserved failed RAM has polygon count 472 at `0x800f45e8` and vertex
count 32. The pinned decomp allocates `0x300` bytes at `0x800f45f0`, or 64
12-byte polygon records. Both receiver collection routines (actual ROM entries
`0x8001e8b8` and `0x8001ee1c`) append records without a polygon-capacity check.
Their vertex cache clamps to index 31, matching the repeated `03 00 1f 1f 1f`
pattern. Record 450 begins at `0x800f5b08`; its third vertex index lands exactly
at model word `0x800f5b0c`, explaining the captured `0x1f265a10` value.
The per-caster caller resets both counters before collection at `0x8001e684`
and `0x8001e698`. This is strong evidence of a shadow scratch overflow, but
neither the precise executed writer nor why so many polygons were accepted has
yet been captured. Do not repair the model pointer or claim that all native
failures share this cause. A private pre-overflow capture will retain CPU/RAM
before the first out-of-bounds append. Evidence: shadow-overflow-source-evidence.

The filtered register observer passed all nine controlled fixtures, including
allowed initialization, wrong-value, wrong-instruction and uncached writes.


The first filtered-watch route completes with 72 threads armed, no watched
writes, no captured corruption and no audio underruns. It is a non-reproduction,
not a stability fix. The first private shadow-limit build fails the generated
object-shape audit because placing the capture helper in a generated translation
unit adds functions. Its original sources are restored and rebuilt. The revised
probe places capture code in the host runtime and leaves the generated function
inventory intact; the audit is retained. Evidence: filtered-register-native-120,
shadow-limit-probe and shadow-limit-probe-v2. Probe results are diagnostic only.
