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
