# ADR 0003: Conservative Phase 4 dependency architecture

- Status: Accepted by `TK22-26`
- Date: 2026-08-04
- Decision owner: `TK22-26`
- Supersedes: None

## Context

The G2 predecessor gate needs a concrete runtime and renderer architecture
before Phase 4 can be reported complete. The decision must not silently turn a
local feasibility experiment into permission to copy, link, bundle, publish,
or distribute third-party material.

The pinned candidates do not share one license posture. N64Recomp carries an
MIT license; RT64 carries an MIT license; N64ModernRuntime carries GPL-3.0-only
terms; no usable root license was observed for the pinned RecompFrontend or JFG
decompilation snapshots. Emulator and graphics-plugin oracles also contain
mixed or copyleft components. License labels alone do not settle combined-work,
generated-output, notice, or distribution questions.

This ADR is an engineering boundary, not legal advice. It intentionally makes
the narrowest selection that permits local G2 execution while preserving every
release and redistribution gate.

## Decision

### Selected Phase 4 components

1. **N64Recomp is selected only as a pinned local build-time tool.** Its source
   checkout and executable remain beneath ignored `tools/`. The tracked patch
   context carries the exact upstream MIT notice. No generated game body is
   distributed.
2. **The Phase 4 minimal runtime, lifecycle brokers, and device bridges are
   project-authored.** They may expose independently authored ABI-compatible
   interfaces, but may not copy source or headers from unlicensed inputs.
3. **The project-owned bounded semantic graphics backend is selected for G2.**
   It executes the reviewed F3DDKR/F3DJFG command subset and compares its
   semantic submission stream exactly with a distinct ignored oracle. This is
   command-family feasibility evidence only; it is not pixels, visual
   correctness, a first frame, or an RT64 execution claim. RT64 remains a
   pinned ignored research target for the later visual-renderer work because
   the inspected revision has no F3DDKR/F3DJFG handler surface.
4. **The project-authored audio bridge is the Phase 4 audio route.** Any RSP
   recompiler or reference implementation used to verify it remains a pinned
   ignored tool or oracle unless separately approved.
5. **The project-authored host shell remains the frontend.** RecompFrontend is
   excluded from copying, linking, modification, and distribution unless usable
   written permission is recorded later.

### Explicitly unselected components

- N64ModernRuntime is research-only for Phase 4. It is not copied, linked,
  bundled, or used as the shipping runtime. This avoids making a project-license
  or GPL combined-work decision inside the G2 experiment.
- The JFG decompilation is a local metadata/research input only. No source,
  headers, matching code, or exported symbol files may be copied.
- BizHawk and its executed graphics plug-in are private local oracles only.
  They are not shipping dependencies and may not be redistributed by this
  project.
- Newer graphics plug-in source is inspection-only. No implementation text may
  be copied into the project-authored adapter.
- RT64 is not the G2 execution route and is not selected for linking or
  distribution. Its source checkout and authenticated fail-closed discovery
  probe remain ignored research evidence. Pixel output, visual correctness,
  RT64 integration, and the first rendered frame remain Phase 7 blockers.

### Distribution posture

This decision authorizes no distribution. The repository remains private and
all-rights-reserved. There is no release, installer, binary package, public
artifact, source offer, or claim that a shipping dependency graph is approved.
Any future shipping selection requires a new human-approved ADR that includes:

- a recursive source, submodule, package, shader, asset, and notice inventory;
- exact immutable versions and artifact digests;
- linking and distribution forms;
- applicable source, relinking, attribution, notice, and offer obligations;
- a root-project license decision;
- installer, interactive-notice, SBOM, and source-correspondence plans; and
- a clean protected-data review of every release input and output.

### Clean-room and evidence rules

- Project-authored runtime and adapter code must be derived from public
  interface facts, independently observed behavior, and synthetic or private
  black-box tests—not copied implementation text.
- Local G2 outputs publish only fixed-schema aggregate counts, booleans, pins,
  and cryptographic digests. ROM bodies, generated code, symbols, coordinates,
  captures, images, audio, save bodies, and unrestricted logs remain ignored.
- A passing scanner is necessary but does not classify copyright or license
  status.
- The canonical UTF-8 bytes of this accepted ADR are bound into the G2 evidence
  as `architecture_decision_sha256`.

## Evidence reviewed

- N64Recomp pinned-source `LICENSE` and repository metadata identify MIT terms.
- RT64 pinned-source `LICENSE` identifies MIT terms and its build instructions
  require recursive submodules.
- N64ModernRuntime pinned-source `COPYING` and repository metadata identify
  GPL-3.0 terms.
- The pinned RecompFrontend and JFG decomp snapshots did not present an
  approved root license for project reuse.
- `docs/legal/dependency-license-inventory.md` records the pinned local
  snapshots, intended relationships, and current exclusions.

These facts support the conservative boundary above; they are not a legal
opinion about a hypothetical distributed combined work.

## Consequences

- Phase 4 can execute a real bounded semantic graphics experiment without
  selecting a visual renderer, shipping runtime, or frontend.
- More host/runtime code remains project-owned work.
- A public release stays blocked until the much larger transitive and legal
  review is complete.
- RecompFrontend and decomp-derived implementation text remain unavailable.
- N64ModernRuntime behavior may inform black-box requirements, but its code is
  not a Phase 4 implementation input.
- RT64 integration and all pixel/visual claims remain later work; a G2 semantic
  pass cannot be relabeled as rendered output or first-frame evidence.

## Human approval

`TK22-26` explicitly approved this exact revised selection on 2026-08-05:
the project-owned bounded semantic backend is the G2 graphics fallback, and
RT64 pixel/visual integration is deferred to Phase 7. This approval does not
authorize distribution or imply that the remaining executable-evidence gates
have passed.
