# ROM-free graphics task bridge

- Status: G2 graphics bounded native fallback proven and subsequently bound
  into the signed Phase 4/G2 aggregate
- Evidence class: public ROM-free tests plus one allowlisted private aggregate
- Shipping status: no visual renderer, RT64 adapter, runtime binding, or presentation path

Sections that describe bundle assembly as pending are historical. They do not
reopen G2; rendering and presentation remain later milestones.

## Outcome

The project now has an independently authored graphics-task boundary and a
bounded custom-family semantic fallback. The fallback translates the complete
reviewed seven-handler surface plus the one variant override into
renderer-owned semantic submissions, delegates only a fixed allowlist of
shared base-family commands, and rejects unknown commands or state. It accepts
only bounded spans,
requires the complete reviewed family capability surface, catches backend,
oracle, and completion-sink exceptions, and authorizes task completion only
after all of these predicates hold:

- the backend accepted the task;
- parsing completed;
- no command was unsupported;
- every adapter-declared command-triggered memory read stayed within a bounded,
  opaque region through the project-owned read-only broker;
- the broker observed every declared non-empty referenced-memory region;
- the output view has a bounded, internally consistent shape and a declared
  kind that matches the backend capability;
- an output oracle whose most-derived object is distinct from the renderer
  adapter accepted that view; and
- the renderer-completion sink prepared without signaling, followed by its
  no-fail commit after output validation.

Every failure returns `completion_authorized: false`. The bridge never prints,
hashes, persists, or copies a program, command, referenced-memory, or output
body. Its tracked executable test uses zero-filled synthetic arrays only.

The semantic renderer records exact command and payload bytes in a bounded,
canonical stream owned by the renderer. It does not hash payloads, and the
bridge distinguishes `semantic_submission` from `rendered_pixels`. A backend
cannot advertise one kind and return the other. This prevents semantic success
from being presented as pixel or visual proof.

Ignored local tooling executed one approved private task with a complete
bounded memory snapshot. The supplied immediate command prefix was verified
byte-for-byte through the broker, parsing continued through brokered memory to
the real terminator, an independently generated exact semantic oracle accepted
the output, and completion occurred afterward. Only that allowlisted aggregate
is tracked: no task body, identifier, address, path, digest, output body, or
other ROM-derived value is published.

This proves one real graphics task through the proposed project-owned native
path and a tested bounded fallback for the reviewed custom family. Those are
the binding G2 graphics requirements. The shared
base-family path currently emits semantic submissions and does not rasterize,
produce pixels, drive VI presentation, or bind the runtime scheduler. The
private run also does not establish complete real-task surface coverage. None
of those facts weakens the G2 fallback proof: scheduler/VI integration belongs
to Phase 6, while pixels, visual comparison, and first frame belong to Phase 7
and M3. Overall G2 completion still requires the trusted cross-requirement
evidence bundle.

## G2 requirement-to-evidence matrix

| Requirement | Public-safe executable evidence | Exact remaining gap |
|---|---|---|
| Proposed native graphics path | The project-owned `GraphicsTaskBridge` invokes the bounded custom backend, renderer-owned semantic sink, independent oracle, and completion sink without an upstream runtime dependency. One ignored private execution used this complete path. | Bind the execution into the trusted overall G2 evidence bundle. Full scheduler wiring is Phase 6. |
| One real graphics task | One approved private task completed only after brokered root traversal, declared-memory observation, exact independent semantic comparison, and completion preparation. The tracked manifest records one task and boolean/enum aggregates only. | Preserve the private evidence for audit; no additional graphics task is required by G2. |
| `F3DDKR_GBI` behavior or bounded fallback | The fallback implements the reviewed seven-handler custom translation surface and one variant override, maintains bounded family state, delegates a fixed shared-command allowlist, and rejects unknown, malformed, out-of-bounds, or over-stack work. The real task matched an independently generated exact semantic stream. | None for the G2 bounded-fallback clause. A broader corpus remains useful later coverage. |
| Completion behavior | The bridge requires closed broker state and independent oracle acceptance before rejectable preparation and one `noexcept` commit. Failure and exception tests emit no completion. | Preserve the boundary when Phase 6 connects the full scheduler. |
| Pixels and first frame | Output-kind enforcement proves the accepted result is semantic and explicitly not rendered pixels. | Not a G2 requirement. Visual rendering, pixel oracles, presentation, and first frame are Phase 7/M3. |

## Verified upstream boundary

The official RT64 and N64ModernRuntime `main` refs still matched the project
pins when checked on 2026-08-04. At those pins:

- N64ModernRuntime's renderer interface returns `void` from
  [`send_dl`](https://github.com/N64Recomp/N64ModernRuntime/blob/589bbf018a3e6d3646ddf7de1e7919f1b7e99bb1/ultramodern/include/ultramodern/renderer_context.hpp).
- Its graphics worker emits SP completion before calling the renderer and DP
  completion after the call, without a renderer success result to inspect, in
  [`events.cpp`](https://github.com/N64Recomp/N64ModernRuntime/blob/589bbf018a3e6d3646ddf7de1e7919f1b7e99bb1/ultramodern/src/events.cpp).
- RT64's interpreter logs and continues when a command has no handler, while an
  unrecognized family leaves the selected GBI null, in
  [`rt64_interpreter.cpp`](https://github.com/rt64/rt64/blob/5473732a822a4423b5696e7cb18fecc425a59875/src/hle/rt64_interpreter.cpp).

The bridge supplies the status contract the project needs, but it is not wired
into those upstream interfaces. A shipping integration must adapt the renderer
path so unsupported or incomplete work cannot be acknowledged as successful.
The human-only runtime/dependency architecture choice remains open.

## Adversarial findings for the Phase 4 PR review

| Severity | Finding | Project fix | Regression evidence | Remaining work |
|---|---|---|---|---|
| High | The pinned renderer call returns no status, SP completion is emitted before the call, and an unknown renderer command can be logged without producing a failure result. This can acknowledge incomplete graphics work. A first sink design also allowed an implementation to signal externally and then return failure or throw. | Added a fail-closed bridge whose completion sink first performs a rejectable, non-signaling preparation step after backend acceptance, complete parsing, zero unsupported commands, broker closure, and independent output-oracle acceptance. The final commit is a separate `noexcept` operation. | Synthetic tests prove backend, oracle, completion preparation, and no-fail commit ordering; every failure before the commit leaves completion unauthorized and uncommitted. | Integrate the contract with the selected runtime and RT64 adapter; the concrete SP/DP event mapping and no-fail commit implementation still require scheduler review and approved real-task evidence. |
| High | No project-owned boundary constrained pointer-bearing graphics inputs or later command-triggered memory reads. An empty declaration or unobserved extra region could also make a no-access transaction appear closed, and an implicitly copied broker could fork the ledger to bypass transaction-wide budgets. | Added a non-copyable, non-movable read-only opaque-region broker with fixed region, total-byte, access-count, and access-byte ceilings. The region set must be non-empty, and every declared region must be observed. Invalid identifiers, zero-length reads, out-of-bounds reads, duplicate or unobserved regions, and over-budget declarations fail closed. | Compile-time regressions reject broker copy/move; synthetic tests reject empty, malformed, and unobserved extra region sets plus broker violations before output validation or completion. The broker exposes only validated subspans and retains a permanent failure state after an invalid access. | Review the real adapter to prove it has no memory-read bypass, then execute approved private tasks with a complete region set. Byte-range coverage inside an observed region is not claimed. |
| High | A backend could appear viable while exposing only part of the bounded custom-family surface or while continuing after unknown commands. | The bridge requires exactly seven base custom handlers, one variant override, a shared base-family delegate, and fail-closed unknown-command behavior. The fallback translates that fixed custom surface into bounded semantic events. | Synthetic tests reject a missing handler, family mismatch, fail-open unknown-command policy, malformed custom state, and incomplete packets; one private task matches an independently generated exact semantic stream. | Implement and independently review the shared base-family visual execution path; semantic translation is not pixel proof. |
| Medium | An exception from capability discovery, task execution, output validation, or completion preparation could bypass an ordinary error result. | `submit` catches exceptions at each rejectable boundary and returns a stable stage-specific failure without authorizing completion; the final completion commit is non-throwing. | Separate synthetic tests cover exceptions before and during execution, in the output oracle, and in completion preparation. | The eventual adapter should also translate backend-native non-exception failures into the structured report. |
| Medium | A backend could claim closure/output with booleans, under-report the submitted stream, return counts outside the bridge's fixed bound, implement the nominally separate oracle interface itself, or label semantic records as pixels. Counts larger than the top-level stream are intentionally permitted for nested lists and therefore are not independent proof of executed work. | Removed backend-owned closure/output booleans. The bridge now owns the memory broker, validates a bounded output view, requires distinct most-derived backend/oracle objects, requires an explicit matching output kind, calls the oracle separately, and rejects zero/short, over-ceiling, arithmetically unsafe, or inconsistent reports. | Synthetic tests cover broker state, backend/oracle identity aliasing, unknown or mismatched output kinds, malformed output geometry, oracle rejection/exception, zero/short/over-ceiling command counts, and unsupported-count reports. | A visual backend must advertise and return rendered pixels, then pass an independent pixel oracle. Distinct object identity is necessary but does not alone prove organizational independence. |
| Medium | A bounded semantic fallback could be relabeled as visual or first-frame evidence, or its valid G2 graphics result could be weakened by imposing a later milestone. | Added a closed, privacy-scanned capability manifest and validator that lock the exact semantic comparison, one-task private aggregate ceiling, absent private bodies, G2 graphics pass, and the explicit absence of visual output and an RT64 adapter. | Python adversarial tests reject visual, corpus-size, evidence-strength, private-body/path, pin, and gate mutations. | Bind this result into the trusted overall G2 bundle. Treat pixels and first frame as Phase 7/M3 evidence, not as a retroactive G2 condition. |
| High | The bridge originally compared only task and backend family values, so a caller and backend that both selected `unknown` could pass the family check. | The task validator now requires the one reviewed bounded family before capability discovery or execution. | A synthetic regression submits matching `unknown` task/backend values with otherwise complete capabilities and proves the backend is never executed. | Add a new explicit family enum and reviewed capability record before any future family can be accepted. |
| High | Raw JSON Schema messages and public-safety locations could reflect hostile private-shaped keys or values into validation output. The initial JSON loader also accepted duplicate keys and nonstandard numeric constants. | Schema and privacy failures now use generic diagnostics; schema-construction exceptions fail closed; the loader rejects duplicate keys and nonstandard constants. | Adversarial tests cover hostile keys/values without echo, invalid schemas, duplicate keys, `NaN`, and malformed JSON. | Keep all future evidence validators on the same sanitized diagnostic boundary. |
| Medium | The evidence validator accepted a valid but substituted JSON Schema and silently collapsed duplicate dependency identifiers. Programmatic non-JSON values could also escape through the canonical-hash path. | Bound the reviewed schema to its canonical digest, reject duplicate or malformed dependency records, and convert non-JSON or cyclic inputs to a generic closed failure. | Adversarial tests cover permissive schema substitution, duplicate and unhashable dependency identifiers, and a non-JSON manifest member without reflecting hostile data. | Update the schema digest deliberately whenever the reviewed contract changes. |
| High | The immediate task command span is only a prefix; treating its end as the end of the top-level display list can report a false complete parse. | The fallback starts from a separately supplied bounded target address, fetches through the broker until the real terminator, and verifies every supplied prefix byte against that brokered stream. A missing terminator, mismatch, trailing supplied bytes, stack overflow, or invalid branch fails closed. | Synthetic prefix/missing-end/trailing-data tests pass, and the independent private semantic run reaches completion only after the full brokered traversal. | Preserve the separate entry-address contract when wiring the runtime; never infer completion from exhaustion of the immediate prefix. |
| High | Source inspection and a private probe of the pinned RT64 revision found no reviewed implementation of the required bounded custom family. An adapter could therefore parse through the wrong family or fail open on unknown commands. | Added an original project-owned bounded semantic fallback without patching RT64 or copying the local GPL research implementation. The RT64 adapter and visual path remain explicitly unimplemented, and the bridge rejects family/capability mismatches. | Public synthetic tests exercise the complete reviewed custom translation surface and fail closed on unknown commands; one private task independently matches the exact semantic stream. | Implement and review the shared base-family visual renderer or an RT64 binding, then validate pixels rather than semantic submissions. |

## Reproducible tests

The C++ test is a standalone executable so it can be integrated into the
project CMake graph without depending on RT64 or any ROM-derived artifact. It
has passed with strict warnings-as-errors under MSVC, Clang, and GCC after the
bounded fallback and output-kind changes, plus AddressSanitizer and
UndefinedBehaviorSanitizer. The public validator and adversarial Python tests
pass. The public manifest exposes only the reviewed one-task aggregate, passes
the graphics requirement of G2, and makes no visual-evidence claim.

Suggested CMake integration:

1. Add `src/runtime/graphics_task_bridge.cpp` and
   `src/runtime/bounded_custom_graphics.cpp` to a project-owned runtime target.
2. Build `tests/graphics_task_bridge_tests.cpp` and
   `tests/bounded_custom_graphics_tests.cpp` as test executables linked to that
   target.
3. Run `scripts/validate_graphics_task_bridge.py` from the central validation
   entry point.

## Next milestones after the G2 graphics proof

No graphics-specific G2 blocker remains. Phase 4 still must bind this ignored
execution into the trusted cross-requirement G2 evidence bundle. Later work is
sequenced by the master plan rather than hidden inside this gate:

1. Phase 6 binds graphics completion to scheduler and VI activity.
2. Phase 7/M3 implements and reviews a shared base-family visual renderer or
   RT64 adapter, presentation, and the first rendered frame.
3. Phase 7 compares renderer-owned pixels with an independent private visual
   oracle across the required frame corpus.

No private task body, program body, display list, framebuffer, symbol, address,
path, user identity, or secret is permitted in tracked evidence or GitHub.
