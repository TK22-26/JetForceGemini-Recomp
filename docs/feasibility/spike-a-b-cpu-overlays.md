# Phase 3 spikes A and B: CPU metadata and overlays

Status: historical Phase 3 spike. Its CPU/overlay findings fed the later signed
Phase 4/G2 completion, and the separate Phase 6 evidence now reaches native M2
boot. Statements below that call those later gates open describe this spike's
original checkpoint, not current project status.

This report covers the pinned US artifact, JFG decomp commit `b49aa4791e8fb1e7acd3bba10346876358d0a9a7`, and N64Recomp commit `ffb39cdad1da5de07eaaa48bd1db4a89a7986771`. Only aggregate facts and approved whole-inventory checksums are tracked. ROM bytes, generated C, per-entry relocation data, source symbol names, per-symbol identifiers, and local paths remain under ignored `tools/` storage.

The tracked document labels its evidence origins explicitly. CPU and overlay aggregates are regenerated from ignored pinned local probes; the ROM-free runtime contract is exercised in CI; and the initial-config parse plus AddressSanitizer observation are maintainer-attested local observations because their pinned binaries and protected input are unavailable to public CI. The validator locks the complete current-pin public aggregate so a self-consistent count or headline mutation cannot pass unnoticed. This lock is change control, not an independent cryptographic proof of the protected input.

## Spike A result

The ELF is usable as a starting point, but not as a complete N64Recomp input.

- The ELF header does not provide a usable entry. N64Recomp rejects the privately supplied candidate as a direct `entrypoint`, while a privately supplied manual-function record is accepted and emitted in the successful fallback run. Its address and extent remain local-only.
- There are 3,729 executable function symbols: 2,899 sized and 830 zero-sized. Of the zero-sized symbols, 824 are aliases covered by sized functions. Six uncovered symbols require explicit size overrides; every inferred size is word-aligned and reaches the next function boundary.
- No executable symbol address or size is unaligned.
- The data inventory contains 11,767 object/no-type candidates. Of these, 8,771 belong to valid sections and 2,996 are absolute or special. There are 5,950 zero-sized candidates and 155 out-of-section ranges; all 155 are zero-sized pseudo-symbol candidates associated with the overlay surface. No conflicting data-symbol name was found.
- The context dump after the six overrides contains 156 executable sections, 2,905 functions, 324 data sections, and 12,605 data symbols.
- The ELF contains zero standard relocation sections and zero standard relocation entries. Its section layout alone therefore does not convey JFG's runtime-linker records to N64Recomp.

The first normal recompilation attempt fails at the game's unresolved `jal` placeholders. A ROM/context scan found 7,414 such sites in 970 functions. A conservative decoder also found 205 register-indirect transfer candidates in 139 functions. Candidate counts can include words embedded in oversized function ranges; they are a review queue, not a proven execution count.

### Recompiler crash

After the placeholder functions and ten additional failures were isolated, the normal Release build crashed without a diagnostic. An AddressSanitizer build reproduced an out-of-bounds read in `N64Recomp::analyze_function`, pinned `src/analysis.cpp:325`.

The jump-table analysis computes a table ROM address from function-relative VRAM and scans until the next known table. When there is no next table, its logical end can remain `UINT32_MAX`; the loop indexes the ROM vector without first clamping the scan to the owning section or ROM image. A malformed or false-positive table candidate can therefore read beyond the loaded input.

This is an upstream-tool blocker, not evidence that the target requires an unbounded table. The required upstream fix is to bound every inferred table by both its owning section and the ROM buffer, then return an actionable analysis error for an unterminated table. The pinned source was not modified for the recorded result.

### Conservative fallback proof

The fallback pre-stubs every function containing a placeholder call or register-indirect candidate, excluding five N64Recomp built-ins whose names are transformed internally. It then isolates ordinary recompilation errors one function at a time.

- 57 additional functions fail because a direct call target is absent from the parsed function metadata.
- One additional pseudo-function candidate contains an out-of-range branch and is rejected.
- The final set contains 1,091 stubs.
- N64Recomp exits successfully and emits 55 C translation units.
- The privately described manual boot function is present in generated output.

This proves that the remaining partition can pass N64Recomp code generation. It does not prove that the generated output compiles, links, boots, or behaves correctly, and the stub set is not acceptable for a release.

At the Phase 3 checkpoint, the pinned executable successfully parsed the then-current initial `config/jfg.us.toml` and completed `--dump-context`. The config omitted the private boot entrypoint and manual-function extent, and project policy kept broad generation disabled while G2 was open. Phase 4 local work now advances that public-safe baseline to one-function-per-file, strict patch, and lookup-mediated call settings while continuing to supply every coordinate and detailed symbol record only through ignored local orchestration. The Phase 3 conservative run pre-stubbed candidates before normal recompilation, so its inventory of 156 executable sections remains historical no-go evidence rather than proof that every section was individually attempted or every candidate function was classified.

## Spike B result

The complete pinned overlay table and every custom relocation record were parsed from the local supported image. The ignored detailed manifest uses only `ovl-NNN` identifiers.

### Complete static inventory

- 157 overlay slots exist; 155 are populated and two are empty.
- All 155 populated headers start with a zero runtime base, so every populated module is dynamically placed by the loader.
- ROM spans are in bounds and non-overlapping when text, data, primary relocation bytes, and secondary relocation bytes are all included.
- Four modules declare an initialization callback and 12 declare a resume callback. Every callback offset is within executable text.
- The overlay reference table contains 2,372 words.
- The main module has 520 relocation records. Populated overlays have 11,076 primary and 16,439 secondary records, for 28,035 records overall.
- Every relocation target is word-aligned. All symbol indices, local offsets, and patch locations pass the modeled bounds checks. All 8,478 HI16 records are immediately followed by a LO16 record with the same reference identity and a distinct patch site; 71 additional standalone LO16 records use the linker's supported single-record path. No unknown source type or patch type occurs.

The observed source-type totals are 12,107 external, 14,835 local-offset, 1,090 local-jump, and three main-data records. Patch totals are 2,028 full-word, 8,980 jump-target, 8,478 HI16, and 8,549 LO16 mutations.

The dependency graph has 134 main-to-overlay edges, 156 distinct overlay-to-overlay edges, and 514 self-overlay references. These are static references, not load-order observations.

### Reference-table exceptions

Normal overlay targets never reference an empty slot or exceed the target module's text/data/BSS extent. One reference-table word encodes a module number outside the normal and recognized special ranges, and one main relocation refers to it. Another reference-table word uses the reserved special class and is referenced twice by overlay relocation records.

These three references must remain fail-closed until a private runtime trace establishes their intended behavior. They may be sentinels, protection behavior, or incomplete decompilation knowledge; treating them as ordinary overlays would permit an out-of-range table access.

### Loader and dynamic-code model

The inspected high-level loader model performs this lifecycle:

1. allocate text, data, BSS, and retained primary-relocation storage;
2. copy text/data from ROM and zero BSS;
3. load the secondary relocation table into temporary memory;
4. apply full-word, jump-target, HI16, and LO16 mutations;
5. invalidate the instruction cache;
6. revisit loaded modules whose external references may now resolve;
7. call optional initialization or resume callbacks indirectly;
8. on unload, clear the active base and repatch affected references to a trap or unresolved value.

No algorithmic creation of new instruction streams was observed. The observed behavior copies code and patches existing words. That conclusion is provisional because portions of the loader remain assembly-only or marked non-equivalent in the pinned decomp. A runtime trace must cover those paths before the project treats dynamic code generation as absent.

N64Recomp can model relocatable sections, but this ELF supplies none of JFG's custom dual-table records as standard ELF relocations. The project must either translate the custom records into N64Recomp metadata before generation or add a bounded JFG-specific ingestion path. Runtime patching of native host instructions is not the intended fallback.

## Required runtime contract

The runtime needs an explicit module registry keyed by opaque overlay ID. The executable synthetic model records the active guest base, text extent, and a monotonic per-ID generation token. Publish rejects duplicate IDs, invalid 32-bit ranges, and any overlap with an active range before mutating registry state. Unpublish requires the current generation. Reload increments the generation even when the same guest base is reused, so a pointer from an earlier lifetime cannot resolve.

Indirect lookup returns an `(overlay ID, generation, function offset)` token, and resolving that token requires the same active generation. The synthetic tests cover successful lookup, unload, same-base reload, stale-pointer and stale-unpublish rejection, out-of-range offsets, and overlap rejection at publish time. This is a contract proof only, not integration with generated code.

The public Phase 4 contract now also executes a closed, caller-ordered two-module
lifecycle with callback rollback, cross-overlay invalidation and rebind, all
four relocation-class journal entries, same-base semantic reload comparison,
and deterministic aggregate replay. Its schema and reviewed lock keep real
overlay counts at zero and G2 at no-go. See
`docs/feasibility/overlay-runtime-g2-contract.md`. This orchestration proof does
not apply target relocations or connect generated call-by-register code.

Phase 4 now tracks the project-authored normalization step in
`scripts/build_private_generated_root.py`. It consumes only ignored or external
local inputs, rejects an existing or tracked output root, and emits the separate
baseline bodies, callable wrappers, generated lookup/lifecycle/section/R32
tables, symbol inventory, and forced-link registry expected by the build. The
generated section initializer publishes only the permanently resident main
section; overlay bases remain zero until an explicit lifecycle load. Generated
lookup therefore cannot resolve an unloaded overlay. R32 application has a
bounded, transactional checked entry point that rejects an unloaded dependency
or an out-of-RDRAM site before changing memory, while the legacy ABI wrapper
fails closed if that validation fails. Section metadata is emitted only into
the ignored generated root so a project-owned runtime adapter can perform the
real copy, BSS-clear, relocation, cache-invalidation, and publication sequence
without placing target coordinates in the repository.

The normalizer itself is ROM-free and tested with a one-section synthetic
fixture. Two fresh output roots must be byte-identical. A real ignored run also
reproduced the complete current-pin body/wrapper/table denominators, and the
new table sources compile under the pinned local Clang toolchain. This closes
the tracked-orchestration gap; it does not substitute for executing the most
complex real overlay through the native runtime.

Required trace events include load begin, bounded copy, BSS clear, relocation,
instruction-cache invalidation, publication, callback entry/completion, lookup,
unpublish, dependent invalidation/rebind, unload completion, stale-pointer
rejection, and reload
verification. Each event should carry only an opaque overlay ID, generation,
relocation class, and aggregate status in publishable logs. Private traces may
retain addresses and per-site details.

## Decision and next gates

| Item | Result | Next gate |
|---|---|---|
| ELF function metadata | Partial | Land six explicit size overrides and classify the remaining direct targets without release stubs. |
| Boot entry | Fallback proven | Keep the private manual entry record local-only until the ELF exporter emits a valid sized entrypoint. |
| N64Recomp jump-table analysis | Blocked upstream | Add section/ROM bounds and a regression test, then rerun without conservative indirect stubs. |
| Custom overlay records | Fully mapped statically | Convert all 28,035 records into validated generation/runtime metadata. |
| Overlay reference exceptions | Blocked on behavior | Trace the three references privately and assign explicit fail-closed dispositions. |
| Function-pointer lookup | Synthetic proof only | Integrate the active-module registry with generated call-by-register code. |
| Load/unload/reload | Static inventory plus synthetic lifecycle contract | Instrument and replay every populated module, including both empty-slot rejection paths. |
| Dynamic code generation | Not observed, provisional | Trace all assembly-only/non-equivalent loader paths. |

Reproduction:

The `--layout` file is private JSON stored outside the checkout or under an
ignored path. It contains exactly seven keys: `schema_version` (integer `1`),
`main_relocation_start`, `overlay_reference_table_start`,
`overlay_table_start`, `overlay_data_start`, `main_text_size`, and
`main_data_size` (integer byte coordinates/extents). The four starts must be
distinct, increasing, word-aligned, and inside the supported image; the two
sizes must be positive. Populate the target values locally and never commit
the file. The private CPU entrypoint and manual-entry size accept decimal or
`0x` base-prefixed integers; both must be word-aligned, the size must be
positive, and their range must fit one executable section.

```text
python3 scripts/probe_n64recomp_cpu.py --n64recomp <pinned-binary> --n64recomp-source-root <pinned-source> --expected-n64recomp-sha256 <pinned-executable-sha256> --elf <pinned-phase1-elf> --rom <supported-local-rom> --entrypoint <private-entrypoint> --manual-entry-size <private-entry-size> --work-dir tools/results/phase3/cpu-verified --output tools/results/phase3/cpu-evidence-verified.json --tracked-evidence docs/feasibility/phase3-cpu-overlay-evidence.json
python3 scripts/analyze_phase3_overlays.py --rom <local-rom> --layout <ignored-private-layout.json> --output tools/results/phase3/overlay-evidence.json --details tools/results/phase3/overlay-details.json --tracked-evidence docs/feasibility/phase3-cpu-overlay-evidence.json
python3 -m unittest tests.test_phase3_cpu_overlays
```
