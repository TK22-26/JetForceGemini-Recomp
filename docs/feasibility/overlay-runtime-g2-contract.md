# Overlay lifecycle and runtime-trap G2 contract

- Status: historical pre-completion contract; its real G2 proof slots were
  subsequently closed by the signed Phase 4/G2 aggregate
- Contract: `config/overlay-runtime-g2-contract.json`
- Schema: `schemas/overlay-runtime-g2-contract.schema.json`
- Validator: `scripts/validate_overlay_runtime_g2_contract.py`
- Models: `scripts/overlay_runtime_g2_models.py`

This file preserves the requirements and gaps as they were defined before the
trusted bundle was assembled. `docs/dashboard.md` and the signed evidence are
authoritative for current gate status.

This contract closes gaps in the public test mechanics without relabeling
synthetic work as target evidence. It contains no ROM bytes, generated bodies,
source symbols, target coordinates, local paths, or private trace bodies. The
reviewed contract fixes all real-evidence counts at zero, keeps G2 at no-go,
and denies a Phase 4 completion claim.

## Overlay requirement audit

| Master-plan requirement | Public executable evidence | Genuine remaining proof |
|---|---|---|
| Correct overlay address mapping | The existing active registry rejects invalid, overflowing, overlapping, inactive, and stale executable ranges. The lifecycle harness separately bounds and overlap-checks the full text/data/BSS mapped extent, then uses the registry for every export and external lookup. | Run the most complex real overlay at its privately observed placement and compare the aggregate result with the oracle. |
| Correct relocations | Existing ROM-free tests exercise the four patch arithmetic classes. The new harness requires every class in a closed scenario and journals each class in lifecycle order. | Apply the complete private records for the selected real overlay and prove the relocated state/output. A journal event is not relocation arithmetic evidence. |
| Active function-pointer lookup | Every synthetic export and cross-overlay reference resolves through a generation-bound registry token. | Connect generated call-by-register code to the production registry and exercise it on a real overlay. |
| Load, unload, and reload lifetime | A caller-ordered scenario executes load, bounded text/data copy completion, BSS clearing, relocation bookkeeping, instruction-cache invalidation, publish, callback, lookup, unpublish, dependent invalidation, unload, same-base reload, dependent rebind, stale-pointer rejection, and semantic-state comparison. | Instrument and replay the corresponding real loader sequence. |
| No stale native state or pointer | A monotonic generation rejects the prior lifetime token. A prior module ID cannot bypass reload through the first-load API, and reload requires a token from the exact prior generation. Reload must reproduce the same public synthetic semantic digest before publication. Callback failure rolls back the published module and invalidates dependents. | Hash the approved overlay-specific real state regions and prove no native pointer survives a real unload. The synthetic digest describes a fixture, not target memory. |
| Deterministic capture and replay | Consecutive caller-supplied operation tokens and a canonical aggregate journal produce identical replay digests. No wall clock participates. | Bind the same event contract to a qualified private trace and, later, the Phase 5 scheduler. |
| Cross-overlay legality | A dependent reference resolves only while its target lifetime is active, becomes fail-closed on target unload, and rebinds to the new generation after reload. | Prove every required real dependency/load-order case, including the still-unclassified exceptional references. |
| Clear failures | Public exceptions are generic and omit IDs supplied by hostile callers, target coordinates, and source details. | Preserve detailed diagnostics only in ignored private evidence. |

The harness is intentionally not a ROM loader and does not copy or transform
target data. It validates lifecycle orchestration around the already-tested
relocation primitives. The contract therefore cannot satisfy G2 merely because
the synthetic event sequence passes.

## Scheduler and runtime boundary

Phase 4's minimal runtime is not Phase 5's deterministic kernel. The harness is
synchronous and caller ordered:

- every public operation requires the next consecutive operation token;
- callbacks complete before the operation returns;
- no thread scheduler, timer, virtual time, or wall-clock source is provided;
- a callback exception rolls the module back rather than leaving a half-loaded
  lifetime;
- callback re-entry into lifecycle mutation is rejected before it can consume
  another operation token; and
- the manifest fixes `phase5_scheduler_claimed` to false.

This is the narrow integration boundary a later scheduler can drive. It is not
evidence that scheduler replay, virtual time, queues, or boot work already
exists.

## Trap-classification requirement audit

The existing `TrapInventory` rejects unknown and duplicate IDs and permits only
abort, emulate, or an explicitly supplied reviewed handler. The new opaque
classification ledger adds the missing G2 planning mechanics:

- an exact category surface covering CPU break/syscall, switch bounds, boot
  self-check, dangling-jump workarounds, checksums, and anti-tamper paths;
- exact per-kind candidate denominators;
- reachable, unreachable, or still-unclassified state;
- an owner and bounded estimate class for every completed classification;
- a non-stub disposition for every reachable site;
- an evidence digest and explicit trace-source classes;
- oracle and native trace classes for reachable sites;
- reviewed private-static evidence for unreachable sites; and
- aggregate-only counts and a canonical private-record digest.

The model can verify that required trace classes were declared, but it cannot
authenticate private traces. Trusted G2 completion remains governed by the
signed private-evidence path in the Phase 4 acceptance contract. The public
contract always records that a synthetic test is not G2 proof.

## Tests

`tests/test_overlay_runtime_g2_contract.py` covers:

- the closed two-overlay lifecycle, all relocation classes, callbacks,
  BSS clearing, indirect/external lookup, invalidation, rebind, unload, same-base reload,
  stale-pointer rejection, and zero active modules at the end;
- byte-for-byte equivalent public journals across two runs;
- out-of-order scheduler tokens and callback rollback;
- full mapped-extent bounds/overlap checks and callback re-entry rejection;
- reload semantic mismatch before publication;
- exact trap-denominator closure, ownership, estimates, trace-class shape,
  duplicate IDs, unclassified candidates, and reachable non-stub disposition;
- strict schema, reviewed-lock, no-go, privacy, duplicate-key, noncanonical
  number, hostile-diagnostic, cyclic-value, and overclaim rejection.

Run:

```text
python scripts/validate_overlay_runtime_g2_contract.py
python -m unittest tests.test_overlay_runtime_g2_contract -v
```

## Remaining G2 blockers

The machine-readable contract keeps these five blockers exact:

1. execute the most complex real overlay through load, relocate, indirect
   lookup, unload, and reload;
2. integrate generated lookup with the native runtime registry;
3. obtain a private dynamic-code/runlink trace for assembly-only and
   non-equivalent loader paths;
4. classify every reachable trap with private oracle/native replay; and
5. assign owned, estimated, non-stub mitigations to those reachable paths.

Until all five have authenticated executable evidence, the overlay and
runtime-trap G2 requirements remain open and Phase 4 cannot be reported
complete.
