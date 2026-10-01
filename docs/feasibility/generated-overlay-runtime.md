# Generated-overlay runtime integration

Status: project-owned native integration implemented and exercised with a
ROM-free synthetic generated table. This is not evidence that a real target
overlay has executed, and it does not close G2.

## Boundary

`GeneratedOverlayRuntime` owns one `GeneratedOverlayTable` adapter. A private
translation unit can bind the locally generated C table without including its
private header in tracked code. The tracked adapter surface contains only:

| Generated capability | Tracked projection |
| --- | --- |
| Global section count | A bounded, stable `section_count()` |
| Section-table initialization | `initialize_sections()` bound to runtime-owned stable address storage |
| Per-section metadata | Text, data, and BSS extents plus the overlay classification |
| Load/unload lifecycle | A checked section index, operation, and runtime-supplied base |
| Relocation denominator | A bounded per-source-section count |
| Checked relocation application | A full staged guest-memory view, section index, and expected count |
| Generated function lookup | Immediate token-relative and `get_function(vram)` entrypoint lookup after active-range validation |

The private adapter must discard ROM positions, linked coordinates, source
names, and generated bodies when projecting metadata. The runtime accepts the
exact private text-and-data bytes only as an owned runtime input. It does not
log, hash, serialize, or expose those bytes. Tracked tests use synthetic bytes,
opaque numeric identities, and synthetic cached-memory placements only.

The adapter's initializer binds the supplied address span for the adapter's
lifetime. Its destructor must release any generated global pointer to that
span. The runtime explicitly destroys the owned adapter before the stable
address storage is released, including rejected-install and runtime-destruction
paths.

## Transaction and publication order

Initial load and same-base reload use the same activation path:

1. Validate a stable generated section count and metadata projection.
2. Require an overlay section, exact text-plus-data input size, a word-aligned
   cached guest mapping, and no overlap with a static section or active overlay.
3. Snapshot live guest memory, copy text and data into staging, and clear BSS in
   staging.
4. Bound the generated relocation denominator by both a project limit and the
   initialized word count.
5. Temporarily load the generated section address while the runtime is busy,
   then run the generated checked relocation callback against staging only.
6. Require the reported and re-read relocation counts to equal the reviewed
   denominator. Reject any staging write outside the section and any write that
   makes BSS nonzero.
7. Resolve every declared dependency and prepare all dependent rebindings in
   allocation-complete temporary containers.
8. Prepare instruction-cache invalidation as the final fallible operation.
9. Copy relocated bytes and zeroed BSS to live guest memory, commit cache
   invalidation, swap prepared bindings, and publish the new generation using
   only no-fail operations.

Any failure before step 9 leaves live guest memory and registry state
unchanged. If the generated section address was temporarily loaded, it is
unloaded during rollback. Failure to restore that generated-table state poisons
the runtime, which rejects all later work.

Unload checks the exact runtime identity, opaque module identity, and active
generation before removing the generated section address. A rejected or
throwing unload is restored to its prior address before returning. A successful
unload then clears the complete mapped extent, removes the module's bindings,
and invalidates every active dependent without allocation.

Reload accepts only the exact token from the prior inactive lifetime. It owns
and reuses the original input and placement, so the caller cannot substitute a
different body or base. Publication receives a new monotonic generation, and
the prior token becomes stale.

## Lookup and dependencies

Function offsets are word-aligned and bounded to generated text before the
generated lookup table is called. Tokens are bound to one runtime, one opaque
module, and one generation. Empty, stale, cross-runtime, inactive, and
out-of-band-mutated states fail closed.

The absolute-address bridge used by the generated `get_function(vram)` ABI
accepts only initialized static text or the text range of an active overlay. It
performs the same metadata, generated-address, and dependency checks before
calling the generated lookup table. An unloaded overlay address therefore
cannot resolve merely because its prior placement is known.

Dependencies use only opaque reference/module IDs and section-relative function
offsets. Loading requires every declared target to be active. Target unload
removes its dependent bindings; while any binding is absent, the runtime blocks
all native lookup for the dependent module. A successful same-base target reload
prepares and swaps every rebind atomically. A failed rebind leaves the target
inactive and dependents invalidated.

The private image builder must declare the complete cross-overlay dependency
set derived from its ignored relocation inventory. The tracked synthetic model
cannot prove that completeness. The native entrypoint returned by lookup is an
immediate-call ABI result; callers must perform token-checked lookup for each
dispatch and must not cache a raw entrypoint across a lifecycle operation.

## Callback and concurrency policy

Every generated-table and cache callback runs while the runtime's busy guard is
set. Recursive entry on the same thread receives `busy`; other threads serialize
on the recursive mutex. Exceptions are contained and mapped to sanitized error
categories. Cache preparation may fail or throw but cannot make invalidation
visible. Cache commit is `noexcept` and runs only after relocated bytes are
visible.

Normal ownership must explicitly unload active modules. Forced runtime
destruction clears their guest extents and destroys the owned adapter without
calling lifecycle callbacks: callback captures may already have been destroyed
by their owner. Adapter destruction releases the generated global table binding
before its address storage disappears.

The guest-memory owner must outlive the runtime and must not bypass this
lifecycle boundary. Direct calls to the generated lifecycle or lookup table
would violate the ownership contract.

## ROM-free test evidence

`tests/generated_overlay_runtime_tests.cpp` covers:

- table ownership, stable section initialization, metadata validation, and
  adapter destruction ordering;
- staged text/data copy, BSS clearing, checked relocation, cache ordering, and
  bounded publication;
- initial load, token-relative and generated-ABI absolute lookup, unload,
  same-base reload, and stale generation rejection;
- cross-runtime tokens, inactive modules, duplicate sections, invalid images,
  static/active overlap, and metadata/address drift;
- unresolved, invalidated, rebound, and failed-rebind dependency paths;
- cache, lifecycle, relocation, lookup, and unload rejection/exception paths;
- out-of-section relocation writes, BSS writes, denominator mismatch, rollback
  failure, and runtime poisoning; and
- callback re-entry during cache, generated lookup, load, and unload operations.

Focused validation commands are:

```text
cmake --build --preset windows-msvc --target jfg_generated_overlay_runtime_tests
ctest --test-dir build/windows-msvc -C Debug -R jfg.generated_overlay_runtime --output-on-failure
```

The source and test also compile as standalone strict-warning translation units
with MSVC, GCC, and Clang. AddressSanitizer plus UndefinedBehaviorSanitizer and
the Clang static analyzer cover the synthetic path.

## G2 work that remains

This tracked implementation intentionally leaves the overlay G2 decision at
no-go until private executable evidence proves all of the following:

1. An ignored adapter binds every reviewed generated callback, including
   section count/init/metadata/lifecycle, relocation count/apply, and lookup.
2. The approved difficult real overlay is loaded from private input and its
   full relocation/dependency denominator is reconciled with the adapter input.
3. Real text/data copy, BSS clearing, every required relocation class,
   instruction-cache invalidation, active lookup, unload, and same-base reload
   reach their expected independent-oracle outcomes.
4. A stale generation and every invalidated dependent dispatch fail through the
   installed native runtime, not only the synthetic table.
5. The pinned private runner emits structured bounded transcripts in the
   required independent environments without publishing bodies, coordinates,
   symbols, paths, or detailed traces.
