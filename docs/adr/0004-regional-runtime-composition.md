# ADR 0004: One runtime architecture with revision-bound game programs

- Date: 2026-11-01.
- Status: selected for the owner-authorized implementation; integration and regional acceptance remain in progress.
- Scope: the exact US, PAL and Japanese revisions in the ROM catalog.
- Supersedes: no frozen execution-profile, dependency or evidence contract.

## Context

The original native product couples US addresses, generated filenames, SDK
names and save paths to shared host services. Exact PAL and Japanese image
reconstruction exposed differences in static sections, original relocation
domains, function metadata, VI clocks and game behavior. A region selector
alone cannot make those assumptions valid.

## Decision

Keep one shared runtime source tree and link one executable per exact game
revision. Each executable contains one generated CPU corpus, compatible RSP
output and immutable descriptor/bindings. The launcher ends the current
session before switching to another revision's verified runtime bundle.
Region is input identity and remains independent of the four
[execution-profile axes](0002-execution-profiles.md).

The versioned [ROM catalog](../../config/roms/revisions.json) owns exact input
identity. Normalization writes a private canonical copy and preserves the
original. Recognition, native-build admission, gameplay qualification and
release support are separate decisions.

One extraction/model/generation pipeline must serve every revision, including
US. Reviewed metadata recipes may describe real extraction differences; they
cannot supply a guessed address delta or replace missing game routines.
Code bodies, aliases, alternate entries, instruction sites and non-CPU
payloads have distinct inventory dispositions. Every metadata correction
preserves loaded original bytes and retains its evidence privately.

Game integration consumes typed, qualified references. Entry instructions are
distinct from generated callables; an instruction hook is not a callable
alternate entry. Data references declare their domain, extent and alignment.
Overlay references require the existing load/lifetime owner. Shared device
and host services do not select regional game addresses.

Build identity has two stages. Before linking, a compatibility key describes
the original input/model/bindings, generator, native source, audio outputs,
dependency pins and compiler/configuration. After linking, a bundle manifest
records executable and dependency-file hashes and the embedded key. Neither
hash includes itself. The launcher compares the actual executable's identity
with the manifest and selected ROM before opening writable profile data.
An executable filename or sidecar cannot relabel a different game program.

US retains its existing profile/save namespace; other revisions use explicitly
marked sibling namespaces. No implicit save conversion or sharing is allowed.
Switching a controller accessory remains a session/device concern, independent
of which game program is linked.

## Consequences and acceptance

The product can share hardware, renderer, audio, input and persistence
implementations while retaining original regional behavior. The confirmed
Walkway music difference belongs to the selected game program; see the
[regional issue evidence](../development/issues/regional-rom-support.md).
Optional enhancements require declared bindings and qualification of their
actual consumers. Unqualified capabilities cannot be advertised as supported.

Shared generation, typed record contracts and exact VI presentation intervals
now serve all three revisions. All three original-OS candidates create saves
and reload into Goldwood; later enhanced candidates also pass native builds
and bounded Play. Development build admission is enabled for all three exact
revisions. The regional issue owns final source/product qualification and the
remaining feature matrix. These checks do not close campaign acceptance or
publish a supported release.

The [architecture plan](../planning/regional-runtime-architecture.md) owns the
implementation sequence and exit gates. The [regional issue record](../development/issues/regional-rom-support.md)
owns actual results, failures and remaining limitations. Existing original
ROMs, generated code, detailed instruction evidence and personal saves remain
private under the established project policy.
