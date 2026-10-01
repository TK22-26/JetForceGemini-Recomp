# Phase 6 native-boot acceptance contract

- Status: binding acceptance criteria for local Phase 6 work
- Scope: native boot from the original entry point to stable VI/scheduler
  activity (the M2 milestone)
- Data boundary: ROM image, generated bodies, and any boot trace derived
  from them remain ignored and local

This contract fixes the runtime architecture decision (P3-LIC-001) for
implementation purposes, the authorship rules that decision requires, and the
determinism gate the boot must meet. It builds on the Phase 5 deterministic
test kernel and follows the fail-closed evidence discipline of
`docs/planning/phase4-acceptance.md` and `docs/planning/phase5-acceptance.md`.

## Runtime architecture decision (P3-LIC-001)

The project adopts **an independently authored runtime** (Option C):

- The shipping runtime — the libultra/N64 SDK surface the game calls, the
  thread/queue/scheduler model, PI/SI/VI, timers, and the RSP task interface —
  is authored by this project.
- The renderer is RT64 (MIT), integrated in Phase 7.
- Third-party HLE runtimes, specifically N64ModernRuntime/librecomp
  (GPL-3.0), and the emulator oracles (BizHawk, GLideN64) are **research-only
  behavioral oracles**. They are never linked into a distributable artifact.

**Rationale.** Two owner reasons, both binding on how the runtime is built:

1. **Principled independence from the recomp lineage.** The runtime is our
   own work, validated against — not derived from — prior projects.
2. **Copyleft avoidance / license freedom.** Keeping the runtime independent
   preserves the project's freedom to choose its own terms. Linking GPL-3.0
   librecomp into a distributable would force the whole distributable to
   GPL-3.0; that outcome is explicitly declined.

This is an engineering architecture decision. The formal legal decision to
*distribute* under specific terms remains a human/maintainer checkpoint (see
"License posture") and is not claimed by this document.

## Independent-authorship rules (binding)

Independence is only real if the authorship is real. The following are hard
rules, not guidance:

1. **No copy-and-relabel.** Source from any third-party runtime — GPL,
   permissive, or otherwise — must not be copied, transcribed,
   machine-translated, or minimally adapted and then presented as this
   project's own. That an implementation is open source is permission to use
   it under its license, never permission to reproduce it under ours. This
   rule applies with particular force to librecomp because it implements the
   same surface we are authoring.
2. **Oracles are black boxes.** librecomp and the emulator oracles are
   consulted only for *behavior* — inputs, outputs, memory/register state,
   event ordering. We diff observable behavior; we do not reproduce internal
   structure. Behavioral equivalence is the goal; expressive copying is
   forbidden even when it would be faster.
3. **Interface vs. implementation.** The libultra/N64 SDK contract (function
   signatures, documented semantics, ABI) is the platform's specification and
   is the authoritative thing we implement. Implementing that contract is
   independent authorship; copying any project's *implementation* of it is
   not.
4. **Reference handling.** If third-party source is read to understand a
   behavior, it is treated exactly like the Jet Force Gemini decomp under the
   existing no-copy boundary: reference for understanding only, never the
   authoring path, and never transcribed. When a specification and an oracle
   suffice, prefer them over reading source at all.
5. **Per-module authorship provenance.** Every runtime bridge module carries a
   tracked provenance record attesting independent authorship: owner role, the
   spec or documented contract it implements, the oracle(s) used to validate
   it, and an explicit statement that no third-party runtime source was
   copied. A module without this record does not count as complete.

A violation of any rule is a completion blocker, not a style nit.

## Runtime-bridge boundary

Boot is expressed against this project's own runtime-bridge interface, not
against any external runtime's API directly. The backend behind that interface
is swappable. This keeps three things true at once: the boot logic is
independent of any one runtime, the license decision stays cleanly separable,
and Option A (adopt librecomp) remains a cheap fallback behind the identical
interface if the owner ever reverses the decision.

## Anti-scope

Implement only the libultra/runtime surface the boot actually reaches.
Everything else fails closed with an explicit trap and a ledger entry — never
a silent stub. The reachable surface is expected to include thread creation
and scheduling, message queues and events, PI DMA, SI/controller status, VI
mode and retrace, timers, and RSP task submission; it is not the full SDK.
Scope is driven by what the boot reaches plus the stub ledger, never by a goal
of reimplementing libultra.

## License posture and separability

Phase 6 boot runs as **local research**. No ROM-derived bytes and no
third-party GPL runtime are distributed. GPL obligations attach only at
distribution, so local oracle use during development carries none.

The deferral has a hard edge: **the human/legal distribution decision must be
recorded before any Phase 6 deliverable is published as a distributable M2
build.** Producing the local M2 milestone build and its trace does not require
it; distributing that build does. This document does not itself authorize
distribution.

## Determinism gate

Boot must be deterministic in the Phase 5 sense: bit-identical across repeated
original-entry processes on the same host, build, and inputs, measured through
the native runner's full-RDRAM/state hash, ordered side-effect journal hash,
canonical output, and first-divergence report. The pinned
`config/divergence-tolerance-v1.json` policy applies unchanged — zero tolerated
divergence in deterministic mode. Host thread timing need not be bit-identical;
the deterministic boot profile must be.

## RSP task handoff to Phase 7

When boot reaches RSP task submission, graphics and audio task submissions are
captured into the side-effect journal with the renderer/audio fakes disabled,
so that disabling them changes no simulation state and Phase 7 inherits real
captured title/boot tasks to drive RT64. Phase 6 does not render and does not
resolve the F3DDKR microcode; it only records the tasks.

## Completion rule and test mapping

Phase 6 is complete only when the boot reaches stable, repeatable VI/scheduler
activity with no nondeterministic divergence, every direct call resolves or
has an explicit fail-closed disposition, and every stub or unsupported access
is instrumented and ledgered. The master-plan Phase 6 tests map as follows:

- original reset-to-entrypoint execution, thread/queue ordering, DMA/overlay
  publication, bounded scheduling, and unresolved-boundary rejection →
  private `jfg.phase6_native_m2`
- repeated canonical output plus state/journal hash consistency and a
  first-divergence report → private `jfg.phase6_native_m2`
- emulator queue-ring advancement and consumed-message comparison → private
  `jfg.phase6_native_m2`
- original-entry boot under AddressSanitizer → private evidence consumed by
  the Phase 6 completion manifest; the public CI sanitizer lane separately
  protects the ROM-free bridge modules
- intentionally invalid ROM fails safely → private `jfg.phase6_native_m2`

The `jfg.boot*` representative fixture remains useful ROM-free regression
coverage, but it is not acceptance evidence for the original-entry M2 claim.

## Deliverables

- boot trace (local, ignored; sanitized public summary by digest)
- emulator/native checkpoint comparison
- remaining-stub ledger with an explicit disposition per entry
- runtime-authorship provenance records for every bridge module
- M2 milestone build (local; distribution gated as above)

## Human review checkpoints

- scheduler and thread/queue semantics
- the distribution/license decision, before any distributable M2 build
- any stub disposition that changes observable boot behavior
- confirmation that the independent-authorship rules were followed
