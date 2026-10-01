# Spike D: native runtime gaps

> Historical Phase 3 spike. Its original G2 runtime blockers were subsequently
> closed by the signed Phase 4 aggregate, and the independently authored Phase
> 6 runtime now reaches local M2. The capability observations below are retained
> as the original checkpoint, not as current project status; see
> `docs/dashboard.md`.

- Status: bounded, not cleared for broad implementation
- Evidence date: 2026-08-04
- Tracked data class: public-safe aggregate only
- Machine-readable record: `config/runtime-capability-matrix.json`

This spike compares the pinned target build, recompiler, and modern runtime at
the capability level. It does not copy upstream code, target bytes, source or
symbol names, disassembly, save bodies, or machine paths. Detailed inspection
notes remain in ignored local Phase 3 results.

## Result

The runtime stack has a viable baseline for message queues, timers, standard
PI transfers, FlashRAM, EEPROM, SRAM, and rumble. It does not yet establish a
viable target path for direct hardware-register accesses, all address aliases,
TLB behavior, code-cache coherency, raw or exceptional PI transfers, the
game-specific decompressor, Controller Pak files, or every trap and self-check
path.

Every currently fundamental blocker has a ROM-free synthetic contract and a
passing contract test. These tests bind a proposed implementation boundary;
they are not an integrated fallback path and do not prove target
compatibility. The matrix therefore carries an explicit `G2` current-pin
decision of `no-go-current-pin`, denies broad Phase 4 authorization, and names
all eight required blockers. Its validator independently enforces the pinned
commits, capability verdicts, fallback-to-implementation bindings, and blocker
set so editing the evidence or dependency lock cannot turn the baseline into
an all-clear result. A canonical current-pin matrix lock additionally rejects
self-consistent edits to counts, evidence classifications, and summaries. The
lock records maintainer review; it is not independent proof of private target
observations.

| Capability | Pinned runtime | Fundamental | ROM-free contract test |
|---|---|---:|---|
| Direct hardware registers | Unsupported as a general facility | Yes | Fail-closed allowlisted broker |
| Direct-mapped address aliases | Partial | Yes | Central checked translator |
| TLB mappings | Unsupported | Yes | Explicit bounded mapping table |
| Cache operations | No-op bridges; insufficient for code mutation | Yes | Host coherency gate |
| PI DMA | Standard paths present; raw/alignment/device gaps | Yes | Bounds-checked copy and completion broker |
| Decompression | Target path unverified | Yes | Bounded project callback |
| Timers | Partial | No | Targeted semantic probes are the next gate |
| Message queues | Supported surface observed | No | Targeted deterministic probes are the next gate |
| Controller Pak files | Unsupported; reports no device | Yes | Bus-bound native accessory layer and logical note store |
| Trap and self-check paths | Abort-only or missing behavior remains | Yes | Strict opaque trap inventory |

## Evidence boundaries

The target-source lexical pass covered 429 source text units at the pinned
commit. Counts in the matrix are occurrences, not unique call sites and not
proof of reachability. The private ELF pass decoded executable sections and
reported only aggregate candidate counts. In particular, trap-like instruction
counts can include unreachable code, padding, or decoder false positives.

The pinned runtime inspection established these engineering facts:

- Queue creation, send, jam, receive, blocking, and external completion paths
  are implemented.
- Timer creation, cancellation, and time queries exist, with incomplete count
  setting and one cancellation return-value detail.
- Standard and handle-based PI transfer paths exist, while raw transfer paths
  terminate and alignment or device-range limitations remain.
- Cache-maintenance bridges are no-ops and the all-entry TLB-unmap bridge is an
  empty stub.
- FlashRAM, EEPROM, SRAM, and rumble facilities exist.
- Controller Pak file operations return a no-device result.
- CPU break and switch-bound hooks terminate; the base syscall hook expected by
  generated code is not implemented.

## Save-device decision

FlashRAM is the primary observed cartridge-save surface.
Controller Pak file management is definitely required by the inspected target
surface and is absent from the pinned runtime. The independently authored
native accessory layer now models four isolated ports, opaque bus- and
generation-bound sessions, Controller Pak/Rumble Pak switching, and rumble
state. Its logical store implements bounded allocation, deterministic
enumeration, read, write, deletion, capacity accounting, and process-style
reload. Its project-owned canonical snapshot is written through a flushed,
same-directory temporary file and atomic replacement. The format intentionally
models no proprietary on-device filesystem image.

The project-owned FlashRAM model implements exact staged pages, program and
erase completion, interrupt and busy behavior, raw fixed-size 128 KiB images,
atomic replacement, failed-write retry, and transactional malformed-image
rejection. Full-page programming follows both pinned host reference
implementations rather than imposing unverified physical bit-transition rules.
Device completion is kept separate from host-file durability so an I/O failure
can be retried without retaining an ambiguous pending command.

Native tests cover accessory detection, cross-bus session rejection,
disconnect/reconnect invalidation, multi-port isolation, deterministic logical
Controller Pak serialization, missing/full-device and note-limit failures,
FlashRAM page and device boundaries, interrupt behavior, raw-image reload, and
failed persistence. The complete save-device test matrix and remaining ABI
boundary are documented in `docs/feasibility/save-device-runtime.md`.

A private supported-image boot exercised the real Mempak path. A separate
isolated oracle now proves durable reload and restoration for both FlashRAM and
Controller Pak domains without using or altering personal save data. The
tracked record contains only aggregate results; raw device bodies and hashes
remain ignored. This oracle plus the native ROM-free execution closes the
device-level round-trip evidence, but it does **not** route the generated
game's calls through the native implementation. G2 remains fail-closed until
the final private bundle binds these executions and the game-facing `osFlash*`
and `osPfs*` bridge ownership is integrated or explicitly bounded.

Rumble switching is covered by the native accessory tests. EEPROM was not
observed in the lexical target pass. SRAM use
remains unverified because generic transfer paths can cover multiple devices.

## Trap decision

Tracked trap evidence contains only opaque classes and aggregate candidate
counts. Unknown or duplicate trap IDs fail closed. A proven site must receive
one explicit disposition: abort, emulate, or defer to an explicitly supplied
reviewed handler. A deferred synthetic dispatch without that handler is
rejected. Blind stubbing is prohibited.

The synthetic model and matrix use the same `boot-self-check` class. Its
fallback is the strict trap-manifest contract, not the unrelated register
broker. The pinned runtime disposition remains `unhandled`; the synthetic
inventory test demonstrates classification mechanics only and does not claim
that a compatible self-check behavior exists.

The Phase 4 public contract adds an opaque candidate-denominator ledger that
requires reachability, an owner, a bounded estimate, a non-stub reachable
disposition, and the required private trace classes before a classification can
be structurally complete. The tracked no-go manifest fixes the real trace count
at zero and rejects G2 or completion overclaims. It validates evidence shape,
not private trace authenticity; see
`docs/feasibility/overlay-runtime-g2-contract.md`.

The private next step is reachability classification. Each reachable break,
syscall, switch-bound condition, boot self-check, dangling-jump workaround,
checksum, and anti-tamper path must be assigned an opaque tracked ID,
reproduced through the private oracle, and given a non-accidental behavior.
Until that work is complete, the control-integrity surface remains a
fundamental blocker even though its inventory boundary is tested.

## Reproduction

The tracked checks are ROM-free:

```sh
python scripts/validate_runtime_capabilities.py
python -m unittest tests.test_runtime_capabilities -v
python scripts/check_repository_hygiene.py --history
```

The unit suite also mutates every current-pin status to an all-clear result,
flips both matrix and dependency-lock pins, substitutes the boot self-check
fallback, and overlaps an explicit mapping with direct KSEG windows. Each
mutation must be rejected.

Private target detail is regenerated locally and remains under the ignored
`tools/results/phase3/spike-d/` boundary.
