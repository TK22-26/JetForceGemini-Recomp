# NATIVE-001: Native Play access violation during extended replay

Status: reproduced once in a private candidate; cause and predecessor coverage
under investigation. Not delivered. Severity: critical stability qualification
blocker for this candidate.

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
