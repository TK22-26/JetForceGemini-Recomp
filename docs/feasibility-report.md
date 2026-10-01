# Phase 3 feasibility report

- Report date: 2026-08-04
- Decision: **no-go for broad Phase 4 implementation**
- Evidence policy: public-safe aggregates only; private ROM-backed bodies remain ignored

> **Historical record:** this report captures the 2026-08-04 Phase 3 decision.
> The listed G2 blockers were subsequently closed by the signed Phase 4/G2
> aggregate, and Phase 6 later reached local M2. See `docs/dashboard.md` for
> current gate status; statements below that G2 “remains open” are not current.

> **2026-08-04 scope update:** the maintainer subsequently authorized local
> Phase 4 engineering under the unchanged no-copy boundary. That authorization
> permits risk-retirement work and private generation; it does not change this
> G2 no-go finding or permit Phase 4 to be reported complete before G2 passes.

Phase 3 has bounded several architecture risks and produced working probes,
validators, synthetic contracts, and representative private executions. It has
also found blockers that make a complete CPU link or correct rendered frame
premature. The project should continue focused feasibility work and must not
represent the Phase 3 or G2 gate as complete.

## Evidence classes

Results in this report deliberately separate three evidence classes:

1. **Publicly reproducible:** schemas, validators, synthetic fixtures, and
   independently authored models that CI can run without a ROM.
2. **Maintainer-attested private:** aggregate results from the supported image,
   ELF, generated output, emulator tasks, save state, and local harnesses. The
   underlying bodies cannot be committed under the repository data policy.
3. **Pinned-source inspection:** capability and license facts checked at the
   commits recorded in `dependencies.lock.json`.

Schema validation proves the shape and internal policy of a tracked record; it
does not independently reproduce a private ROM-backed experiment.
Target ROM offsets, target VRAM addresses, and manual boot extents are excluded
from tracked evidence and must be supplied only to an ignored local probe.

## Exit-gate answers

| Question | Answer | Evidence and remaining gate |
|---|---|---|
| Can all CPU code sections be represented? | **Not yet.** | The context inventory contains 156 executable sections, but the conservative run pre-stubbed candidate functions; it did not individually attempt every section or classify every candidate function. That partition generated 55 C units with 1,091 stubs. An upstream unbounded jump-table scan also caused an AddressSanitizer-confirmed out-of-bounds read. G2 remains explicitly open. |
| Can all overlays be mapped? | **Statically yes; operationally no.** | All 157 slots and 28,035 custom relocation records are represented by aggregate evidence. The active-module registry passes synthetic publish/unpublish, same-base reload, stale-generation, and publish-time overlap tests. A difficult real overlay has not yet completed the full load, relocate, indirect-call, unload, and reload route through generated code. |
| Is there a viable graphics/RSP path? | **Yes for G2 through a bounded native fallback; visual output is a later milestone.** | The tracked ROM-free bridge includes the complete reviewed custom-family translation surface, bounded brokered traversal, exact semantic submissions, output-kind separation, and fail-closed completion. An allowlisted aggregate records one private exact semantic match with referenced-memory closure, satisfying the real-task and bounded-fallback clauses of G2. It does not claim the Phase 6 scheduler/VI binding or Phase 7/M3 pixels and first frame. |
| Is there a viable audio path? | **Yes for G2 through the bounded native worker; overall bundle binding remains.** | One approved real primary task passed through the installed generated-program adapter, checked broker, transactional output, exact independent oracle, and completion gate. Both internal permutations have synthetic coverage, and the generated secondary fallback proves bounded entry and rollback without claiming a real secondary task. Full scheduler integration belongs to Phase 6. |
| Are save devices supportable? | **Yes, with project work.** | The candidate runtime supports cartridge save devices but not Controller Pak files. A project-authored ROM-free native note store now covers bounded operations, deterministic enumeration, atomic checksummed persistence, fresh-process-style reload, and malformed/full/missing failure cases. A private emulator Mempak checker persistence/reload result remains oracle evidence only: it did not enter this implementation and does not clear G2. Discovery, native-to-oracle operation parity, and repair behavior remain. |
| Are anti-tamper and trap paths understood enough to proceed broadly? | **No.** | A strict aggregate inventory and fail-closed disposition model exist, but private reachability and intent classification are incomplete. Break, syscall, cache, TLB, and self-check behavior cannot be silently stubbed. |
| What upstream work is required? | **At least three bounded workstreams.** | N64Recomp needs bounded jump-table analysis and a JFG custom-overlay metadata path; the runtime needs explicit overlay, Controller Pak, register/TLB/cache, trap, scheduler, and presentation integration; graphics needs a reviewed shared base-family visual renderer or RT64 binding. No upstream contact or contribution is authorized by this report. |

## Spike results

- [CPU and overlay report](feasibility/spike-a-b-cpu-overlays.md)
- [RSP, graphics, and audio report](feasibility/spike-c-rsp-graphics-audio.md)
- [Runtime and save report](feasibility/spike-d-runtime-gaps.md)
- [Prioritized blocker backlog](feasibility/blocker-backlog.md)
- [Revised planning range](feasibility/revised-planning-range.md)

Machine-readable deliverables:

- `docs/feasibility/phase3-cpu-overlay-evidence.json`
- `config/rsp-task-manifest.json`
- `config/runtime-capability-matrix.json`
- `config/graphics-task-bridge.json`
- `config/audio-task-bridge.json`

## Test status

| Required proof | Current result |
|---|---|
| Static overlay validator | Passes all tracked aggregate bounds and type checks |
| Synthetic relocation | Passes supported relocation classes and rejects malformed inputs |
| Indirect-call lookup | Synthetic registry passes publish, unpublish, same-base reload, stale-pointer/generation, and publish-time overlap rejection; generated-code integration remains open |
| RSP manifest validator | Passes privacy, pin, inventory, capture, and decision checks |
| Graphics task bridge | G2 graphics passes through the bounded ROM-free native fallback: one private aggregate establishes real task execution, brokered memory closure, and an independent exact semantic match. Trusted bundle binding remains; scheduler/VI is Phase 6 and visual rendering/pixel validation is Phase 7/M3 |
| Audio task bridge | G2 audio passes through one real primary task on the installed bounded worker with exact output validation; both permutations have synthetic coverage and the generated secondary fallback fails closed. Trusted bundle binding remains; a real secondary task is useful non-gating coverage |
| Runtime capability matrix | Passes required-surface, fallback-registry, oracle-gate, fixed current-pin no-go, pin, and safe-text checks; all-clear and pin-flip mutations are rejected |
| Unknown register report | Static aggregate exists; fail-closed broker contract passes |
| Save-device probes | Synthetic enumeration and logical snapshot reload pass; private checker persistence/reload is oracle-only and G2 remains blocked |
| Trap inventory | Required classes and fail-closed dispositions validate; reachability remains open |

## Decision

The master-plan deliverables record a defensible feasibility decision, but the
stricter G2 executable gate is not satisfied. Under the later maintainer scope
decision, local Phase 4 work may proceed when it directly retires a blocker,
improves the private evidence harness, or hardens the no-copy boundary. Neither
that work nor a successful compiler run changes the no-go verdict by itself.
