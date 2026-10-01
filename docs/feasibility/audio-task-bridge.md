# ROM-free audio task bridge

- Status: G2 audio mechanism proven and subsequently bound into the signed
  Phase 4/G2 aggregate
- Evidence class: public ROM-free tests plus a body-free aggregate from ignored private evidence
- Shipping status: project worker is tracked; the injected generated wrapper and private task remain ignored

Sections that describe bundle assembly as pending are retained as historical
implementation notes; the dashboard and signed evidence carry current status.

## Outcome

The project now has an independently authored boundary for a future
RSP-recompiled audio adapter. It accepts only bounded top-level inputs whose
lengths are exact instruction, command, and output-frame multiples. It requires
both reviewed program variants, exposes indirect input memory and output only
through a checked broker, and authorizes completion only after all of these
conditions hold:

- the backend exposes the complete two-variant, broker-only capability surface;
- parsing completes without an unsupported command;
- the backend reports the same selected variant that the caller requested;
- every indirect read, mutable work-region write, and output write stays within
  its declared bounds;
- the backend's access counts and byte counts exactly match the bridge ledger;
- every submitted referenced-memory region is observed;
- every byte in the fixed-size, frame-size-multiple output is written exactly once;
- an independently supplied output validator accepts the staged result; and
- no backend or validator exception occurs.

Output and mutable referenced memory are transactional. The backend writes into
bridge-owned staging memory, later reads observe staged work-buffer writes, and
the caller's spans are unchanged on every failure path. The backend view
does not contain the caller's raw referenced-memory or output spans. Duplicate,
overlapping, top-level-input, and input-output aliases are rejected before
execution. Parsed top-level command coverage must equal the submitted command
count exactly; neither under-reporting nor over-reporting is accepted.

The tracked C++ test executes both variants with small synthetic byte arrays and
compares their complete output with independent exact references. This proves
the host contract, the two synthetic dispatch paths, broker-visible memory
closure, transactional work-buffer mutation, and synthetic output validation.
An ignored private harness additionally executed one approved primary task
through the generated program, project adapter, checked broker, exact independent
output oracle, and scheduler gate. The tracked manifest records only the reviewed
count and pass/fail aggregates; no task body, address, symbol, buffer, or private
digest is tracked. The same replay now enters through the installed project
worker and successfully uninstalls afterward. A separate ignored fallback probe
enters the actual generated secondary permutation at a controlled resume point,
performs one bounded brokered work-memory write, rejects the deliberately
unsupported return target, emits no completion, and proves transactional
rollback. This does not claim a real secondary task or secondary audio output.

The project-owned integration surface now also includes a concrete
`AudioRspTaskAdapter`. It invokes one generated wrapper, matching N64Recomp's
internal overlay-permutation dispatcher, gives it only the brokered task view
and `AudioMemoryAccess`, and forwards the wrapper's observed variant and exit
reason without substituting the caller's expected variant or allowing the
program to authorize completion. `AudioRuntimeTaskWorker` owns the opaque
program interface transferred at install, issues a worker-scoped monotonic
generation token, rejects absent, stale, cross-worker, double, and busy
operations, and holds a strong in-flight lease without holding its lock across
callbacks. `AudioTaskSchedulerGate` prepares completion after validated data is
committed, then emits one final `noexcept` completion signal. Rejecting or
throwing preparation emits none. The primary private replay binds real generated
semantics through this installed worker.

## G2 requirement-to-evidence matrix

| Requirement | Public-safe executable evidence | Exact remaining gap |
|---|---|---|
| Proposed native audio path | `AudioRuntimeTaskWorker` owns one opaque generated wrapper whose internal dispatcher owns the two overlay permutations. Its stack-scoped adapter maps only the `broke` exit, forwards the observed variant, and exposes only brokered memory. Tests reject invalid lifecycle identities; an ignored primary binding routed every observed DMA through the installed worker; and the generated secondary fallback probe remained brokered and fail-closed. | Preserve the worker boundary during the later scheduler integration; generated bodies remain intentionally untracked. |
| Real primary task | One approved primary task completed through worker install, generated wrapper, adapter, bounded referenced-memory broker, transactional work-buffer path, exact oracle, prepared completion, one final signal, and worker uninstall. The public manifest records one task and boolean outcomes only. | Preserve the private evidence for audit; no additional primary task is required for this gate. |
| RSP variants classified | Both discovered internal permutations compile. Public synthetic tests cover successful primary/secondary observations; the real corpus proves the primary; and a generated-secondary probe proves bounded broker entry, explicit unsupported-return classification, zero completion, and rollback. The extended private search classified 2,984 additional normal tasks with no secondary swap. | A real secondary task remains useful future coverage, but G2 requires one real audio task rather than one per internal permutation. |
| Observable output proof | The bridge writes every output byte once into staging memory, validates the complete result independently, and commits transactionally. The approved real primary replay matched the complete private oracle exactly. | None for the G2 audio proof. |
| Scheduler ordering | `AudioTaskSchedulerGate` tests prove validated output is visible before preparation, validation failure emits no preparation, rejected or throwing preparation emits no signal, and final `noexcept` commit occurs exactly once. The installed real primary replay observed the same order; the secondary fallback emitted none. | Full Phase 6 scheduler wiring remains later work, outside this feasibility proof. |

## Verified upstream boundary

At the pinned revisions, the current generated/runtime surface does not supply
the evidence this gate needs:

- N64Recomp's generated overlay wrapper accepts a raw guest-memory pointer and
  dispatches generated permutations from overlay state in
  [`rsp_recomp.cpp`](https://github.com/N64Recomp/N64Recomp/blob/ffb39cdad1da5de07eaaa48bd1db4a89a7986771/RSPRecomp/src/rsp_recomp.cpp#L902-L1001).
- N64ModernRuntime defines the generated microcode function with that same raw
  memory surface in
  [`rsp.hpp`](https://github.com/N64Recomp/N64ModernRuntime/blob/589bbf018a3e6d3646ddf7de1e7919f1b7e99bb1/librecomp/include/librecomp/rsp.hpp#L12-L35).
- Its RSP runner treats the expected break exit as task success after loading
  task data and executing the function; it does not independently inspect an
  output buffer or memory-access ledger in
  [`rsp.cpp`](https://github.com/N64Recomp/N64ModernRuntime/blob/589bbf018a3e6d3646ddf7de1e7919f1b7e99bb1/librecomp/src/rsp.cpp#L36-L63).
- The task worker emits SP completion after that boolean success result in
  [`events.cpp`](https://github.com/N64Recomp/N64ModernRuntime/blob/589bbf018a3e6d3646ddf7de1e7919f1b7e99bb1/ultramodern/src/events.cpp#L270-L294).

The project worker replaces the relevant upstream success boundary for the
proposed path without copying or linking its implementation. The ignored primary
binding translated all observed generated DMA through the broker and closed
successfully. The secondary fallback separately proves generated entry and
fail-closed broker behavior without claiming a real secondary task. A normal
exit alone cannot clear G2.

## Adversarial findings for the Phase 4 PR review

| Severity | Finding | Project fix | Regression evidence | Remaining work |
|---|---|---|---|---|
| High | The pinned generated RSP entry receives the full guest-memory pointer, while runtime success is based on the expected exit reason. A normal exit therefore proves neither referenced-memory closure nor audio output. | Added a bounded broker-only boundary, single-wrapper adapter, and installed project worker that expose no indirect raw-memory or output span to the program. | Synthetic tests reject unknown regions, out-of-bounds reads, partial region observation, partial output, overlapping output, false reports, and validator rejection; the installed private primary replay reached only the broker and matched its oracle; the generated secondary fallback remained brokered and rejected. | Preserve this boundary in scheduler integration. |
| High | The first real brokered replay exposed an omitted access class: the audio program writes intermediate RDRAM work buffers outside its final output span. The original read-only-region plus `write_output` broker rejected an otherwise successful generated execution. | Added checked `write_region` access, bridge-owned mutable-region staging with read-after-write semantics, exact write ledgers, and transactional commit only after the complete report and output oracle pass. | Synthetic tests prove staged reads, successful commit, write-protected rejection, and rollback after oracle failure. The approved primary task completed broker-only and matched its oracle; the generated secondary fallback performed a brokered work write and rolled it back after rejection. | Preserve this contract in runtime integration. |
| High | The first adapter modeled the two generated overlay permutations as two externally selected program objects and copied the caller's expected variant into the backend report. The generated inventory actually has one wrapper that dispatches overlay permutations internally, so the draft could not independently prove which variant executed. | Replaced the two-entry adapter with a single-wrapper binding. `AudioRspProgramReport` now supplies the observed internal variant and the bridge compares it with the caller expectation fail-closed. | Synthetic tests run both observations through one wrapper and reject an observation mismatch. The corrected private primary replay remains exact, the 2,984-task search is truthfully classified as zero swaps, and a direct generated-secondary fallback proves actual secondary code entry without relabeling it real. | A real secondary observation is retained as non-gating future coverage. |
| High | A raw installed program pointer or generation-only token could dangle, alias another worker, be reused after reinstall, or be invalidated reentrantly while a task was executing. | `AudioRuntimeTaskWorker` takes unique ownership, issues an opaque worker-scoped generation identity, snapshots a strong in-flight lease, and rejects absent, stale, cross-worker, double-install, double-uninstall, and busy/reentrant operations without mutating the active installation. | ROM-free tests cover every lifecycle error, stale identity after reinstall, callback reentrancy, exception recovery, and destructor timing; the private primary installs, dispatches, and uninstalls successfully. | None for the primary worker prototype. |
| High | The original fallible `signal_sp_complete` callback could emit an external signal and then return false, making the reported state disagree with an irreversible side effect. | Split completion into rejectable/throwing preparation with no signal and one final `noexcept` commit. | Tests prove rejected or throwing preparation commits zero times, validation failure never prepares, committed output is visible before preparation, and successful commit occurs exactly once. The generated secondary fallback emits no completion. | Preserve this split in scheduler integration. |
| High | The first bridge draft passed the caller task view to the backend, accidentally exposing the raw referenced-region and output spans beside the broker. Even after splitting the view, a referenced region aliased to a raw top-level input, or output aliased to any top-level input, could bypass broker observation or transactional isolation. | Split caller and backend task views. The backend sees only bounded top-level read-only inputs, aggregate region/output shape, and the broker. The bridge rejects region aliases, referenced-to-top-level aliases, output-to-top-level aliases, and input-output aliases. | Compile-time assertions prove the backend view has no raw output or referenced-region member; executable tests reject duplicate regions and every referenced/output alias class. | Preserve the split view in the generated-RSP adapter and do not retain an unbrokered guest-memory pointer. |
| High | The private boot-window evidence and extended search did not contain a real task that entered the second internal overlay variant. Treating synthetic coverage as a second real task would overclaim. | Kept the real-secondary flags false and added a distinct generated-secondary fallback class: it enters the actual generated permutation at a controlled resume point, performs a brokered write, rejects an unsupported return, emits no completion, and rolls back. | The aggregate separately records one real primary task, zero real secondary tasks, 2,984 searched tasks with zero swaps, and one generated fallback probe. | Retain a real secondary task as desirable future corpus coverage, not as a G2 requirement. |
| High | The earlier audio probe established normal control-flow exits but did not prove that a complete output buffer was written or matched a reference. | Output is fixed-size, has a frame-size-multiple length, is written exactly once through staging memory, and is copied to the caller only after an independent validator accepts it. | Tests reject empty, oversized, non-multiple, partial, overlapping, mismatched, rejected, and exception-throwing output paths; the required real primary aggregate records an exact complete oracle match. These checks do not claim host-pointer alignment. | None for G2; later secondary output coverage remains useful. |
| High | A backend-owned boolean could self-assert referenced-memory closure without establishing which regions were accessed or whether its counts were truthful. | Closure is derived from a bridge-owned ledger. Every declared region must be observed, all access is bounded, total operations and byte traffic are capped, and report counts must match the ledger exactly. | Tests reject unobserved regions, invalid indexes, out-of-range reads, duplicate aliases, and falsified read or write counts; the real primary replay used a bounded brokered region and the secondary fallback also used only the broker. | Preserve the ledger in runtime integration. |
| Medium | A backend could report the wrong overlay variant, incomplete or inflated parsing, unsupported work, or internally inconsistent operation totals while still returning an ordinary result. The initial coverage check rejected only under-reporting and accepted inflated command counts. | The bridge cross-checks variant identity, requires parsed top-level commands to equal the submitted count exactly, and validates unsupported counts plus all broker counters before output validation. | Synthetic tests reject wrong variants, under-reported and over-reported parses, incomplete parsing, unsupported commands, and altered byte counts. | Bind the eventual report to private task execution rather than unrestricted diagnostic logs. |
| Medium | Exceptions from capability discovery, task execution, allocation, output validation, or completion preparation could bypass a closed result or strand the worker busy. | No-throw bridge and worker boundaries convert dependency exceptions into stable failures, release the busy lease, and keep final completion commit infallible. | Tests cover exceptions before execution, during execution, during validation, and during completion preparation, followed by worker reuse or successful uninstall. | Preserve these boundaries in runtime integration. |
| Medium | Synthetic or private evidence could be relabeled, altered, or accompanied by sensitive bodies in a public G2 claim. | The closed, privacy-scanned manifest records exactly one reviewed real primary task, keeps the real-secondary fields false, records the generated fallback separately, and forbids private bodies. Trusted overall G2 validation still requires the ignored executable bundle. | Adversarial Python tests reject pin drift, aggregate changes, private-path/body fields, fabricated fallback progress, hostile diagnostics, duplicate keys, noncanonical numbers, and lock changes. | Bind both audio executions into the final trusted G2 evidence bundle. |
| Medium | The public validator trusted any caller-supplied valid JSON Schema, silently collapsed duplicate dependency identifiers, and could raise on programmatic non-JSON values. | Bound the reviewed schema to its canonical digest, reject duplicate or malformed dependency records, and return a generic fail-closed diagnostic for non-JSON or cyclic inputs. | Twenty-one adversarial Python tests now include permissive schema substitution, duplicate and unhashable dependency identifiers, aggregate mutation, and a non-JSON manifest member without echoing hostile data. | Update the schema digest deliberately whenever the reviewed contract changes. |

## Reproducible tests

The implementation and test are standalone C++20 files with no renderer,
runtime, generated code, or game-data dependency. The public evidence validator
is likewise ROM-free.

Suggested integration steps:

1. Add `src/runtime/audio_task_bridge.cpp` to the project-owned runtime target.
2. Build `tests/audio_task_bridge_tests.cpp` as a test executable linked to that
   target.
3. Run `scripts/validate_audio_task_bridge.py` from the central validation entry
   point.
4. Transfer the opaque program interface into `AudioRuntimeTaskWorker`, retain
   its installation token for dispatch/uninstall, and never bypass the worker.

## Exact remaining audio work

The G2 audio requirement is satisfied by the real primary task through the
proposed native worker and by explicit classification/testing of both generated
permutations. A real secondary task remains valuable future corpus coverage,
but it is not a second real-task requirement in the binding G2 contract. The
remaining Phase 4 work is to bind these executions into the trusted G2 evidence
bundle; Phase 6 will later integrate the same worker with the scheduler.

No task body, generated microcode body, audio buffer, symbol, address, private
path, identity, or secret is permitted in tracked evidence or GitHub.
