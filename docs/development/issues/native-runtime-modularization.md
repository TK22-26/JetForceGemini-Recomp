# ARCH-NATIVE-20261101: Native runtime responsibilities share one translation unit

- Status: native module split compiles and links; 118 CTests and scoped copied-profile replays pass. All 15 native translation units pass GCC headless source checks after feature-guard corrections. Unreleased; no full owner playthrough or Linux live qualification.
- Severity: medium maintainability and compatibility risk, not a newly observed gameplay failure.
- Baseline: `0b691d0`, `src/boot/native_boot.cpp` (16,265 lines / approximately 853 KB).

## Problem and intended boundaries

The same translation unit owns guest memory mappings and MMIO faults, SDL audio device lifecycle,
Windows input/window ownership, generated overlay adaptation, simulation state, dispatch hooks,
diagnostics and the run loop. Regional support and routine changes must currently navigate all of
these responsibilities together. Large size alone is not proof of incorrect behavior.

Extract cohesive modules with explicit ownership and interfaces. Preserve generated ABI, guest
state, member order and initialization, exception/RAII behavior, original scheduling and thread
handoffs. Compile actual private native inputs as well as portable checks; preserve failed attempts
and compare bounded runs before declaring the refactor verified. Avoid textual include fragments
that merely move the same monolith without establishing module ownership.

## Current work and evidence

The production guard is enabled under the existing investigation; earlier counters are retained.
The clean baseline source is backed up in the private `reorganization-followups-20261101` receipt.
The owner's PAL and Japanese ROMs are available as private, hash-verified normalized copies.
Those inputs do not establish regional runtime compatibility.

The ownership table and validation below describe the completed split and its remaining limits.

## Implemented ownership

`native_boot.cpp` is now the 1,737-line child/startup coordinator. Private implementations live in
`src/boot/native/`; no new public generated ABI or launcher command-line contract was introduced.

| Files | Responsibility |
|---|---|
| `guest_memory.hpp/.cpp` | Guest mappings, MMIO fault handling, mapping cleanup and device observation |
| `host_audio_device.hpp/.cpp` | SDL device lifecycle, queue/latency recovery and PCM capture |
| `generated_overlay_table.hpp/.cpp` | Generated overlay metadata, relocation and lookup adapter |
| `live_window.hpp/.cpp` | Win32 window owner thread, input mailbox and mouse diagnostics |
| `runtime_constants.hpp`, `event_journal.hpp` | Hardware layout constants and existing event policy |
| `runtime_state.hpp` | One shared simulation state and generated dispatch identity |
| `runtime_services.hpp` | Internal cross-module interfaces and feature guards |
| `gameplay_scopes.hpp` | Inline RAII scopes around guest gameplay calls |
| `controller_input.cpp` | Device/config sampling, modern input and guest menu interpretation |
| `live_frontend.cpp` | Host audio/window services, captures and navigation requests |
| `runtime_reports.cpp` | Gameplay, timing, semantic-hash and progress reporting |
| `save_storage.cpp` | Private FlashRAM/controller-pak path setup and persistence |
| `overlay_loading.cpp` | Guest overlay allocation/publication and lifecycle checks |
| `live_tasks.cpp` | VI configuration, audio/graphics task submission and graphics completion |
| `runtime_diagnostics.cpp` | Failure reports, memory-watch diagnostics and bounded exit gates |
| `guest_execution.cpp` | Guest dispatch, original OS bridge, CPU operations and instruction probes |
| `rom_image.cpp` | Supported ROM validation, IPL state and static-section loading |
| `process_supervisor.hpp/.cpp` | Child capability validation, process isolation and canonical result handling |

The original instruction/cache timing storage remains single-owned in `guest_execution.cpp`.
The coordinator binds that same storage to State through an explicit helper; putting the original
cache-definition header in every translation unit would have created independent clocks/caches.
`LiveRt64Window` now receives the mailbox and required atomics/diagnostics directly, rather than
all simulation State. Publishing the resulting window/raw-input capability still happens after
the window thread signals readiness. Guest memory, audio and generated-table classes have actual
out-of-line implementations. Hot gameplay RAII scopes remain inline to preserve dispatch inlining.

State itself retains its existing member order and initialization. Guest dispatch still contains a
large, coupled OS/game-hook implementation (approximately 6,259 lines with its probes); this change
does not claim that all runtime state or every dispatch case is now independently designed. Its
address assumptions remain US-specific. The split establishes clear source ownership without
inventing a regional gameplay implementation.

## Validation and informative failures

All changed native translation units compile with the existing MSVC Release warnings-as-errors
policy and link against retained qualified generated CPU/audio/renderer objects. The old CMake
cache points to private generated sources removed during an earlier cleanup, so this is an
incremental host rebuild, not a fresh ROM-to-game generation or a new release qualification.
The checked CMake target lists the new implementation files.

Early extraction mistakes were caught before acceptance: numeric digit separators confused a
private lexical helper, initial member-array parsing produced invalid declarations, Windows header
ordering exposed the SDK `near` macro, and moved scopes/enum/helper declarations were not visible
across their new boundaries. The corrected code compiles without relaxing warnings. Feature-guard
consolidation preserves the exact active declarations and their order for Windows/non-Windows and
live/non-live configurations. An opaque-payload heuristic also identified a prototype containing
four unnamed `unsigned` parameters; naming those parameters removes ambiguity without exempting
source from hygiene checks.

Private receipt: `reorganization-followups-20261101`, with original source backup, extracted-method
and domain inventories, all failed/passing build logs, guard-equivalence checks and copied-profile
replays. The production ledger remains enabled under the same investigation and all prior charges.

## Cross-platform boundary check

A GCC source check caught three extracted Windows reservation methods whose definitions had lost
an enclosing Windows guard. Their original boundary is restored. The same check also exposed
existing platform limitations: an unguarded Windows timer type, diagnostic references outside their
live feature guards, and Windows CRT calls in the Linux live path. Baseline-versus-candidate compiler
checks confirm those latter failures exist in baseline `0b691d0`. Windows timer storage and optional
host/profile calls now have their proper platform/feature guards. All 15 headless translation units
pass GCC with warnings treated as errors. The Linux live path still has inherited Windows-only
window/audio and CRT assumptions; no Linux live build or gameplay acceptance is claimed.

## Runtime replay scope

The actual Windows build uses retained qualified generated CPU/audio/renderer objects and the newly
compiled host modules. Replays use private copied profiles; owner saves and ROM inputs are unchanged.
The cases cover normal and skipped outbound Walkway, the retained Goldwood/Vela candidate, Water
Ruin as a before/after control, and a native Walkway exit/prompt chain after diagnostic positioning.
The Walkway descriptor rollback is the intentional behavioral difference in this refactor's build;
[the audio record](flight-transition-missing-music.md) separates its hardware expectation from tests.

An attempted whole-section binary comparison after interface cleanup did not establish identical
machine code. It was not accepted as behavioral proof; the actual resulting executable receives
its own route replays. Private receipts preserve both binaries, section hashes and every run.
These finite checks do not establish full campaign equivalence, original-clock parity or universal
save/controller compatibility. The shared simulation State and large guest-dispatch implementation
remain candidates for later semantic decomposition.

Final source validation: **1,816 Python tests pass (49 skips)**, all **118 CTests pass**, all 15
headless translation units pass GCC and MSVC source checks, and the current Windows host links
with warnings treated as errors. Five fresh captures of the final runtime pass, supplementing
the retained before/after control and earlier six-route sets. Tested final runtime SHA-256:
`700f84955b3f7d85233111f9194c2af57bc36b97494a4783101670a47b8888d0`. The private runtime-current-route-results.json, python-suite-complete.result.json
and platform/build receipts retain the exact scope. Local Markdown paths and anchors were checked
across 222 documents; the cumulative audit covers every current source file and new module.

## Evidence identity and historical consumers

Current controller-return, event-pair and input-focus fingerprints now include every extracted
native source/header and its build registration through one explicit shared inventory. Current
Phase 6 producers and validators bind the same inputs. A regression test changes both an extracted
implementation and State header and requires all capture identities to change; missing inputs fail.
The final reference audit caught these consumers still hashing only the coordinator after the split.

Historical signed records and their original hashes remain unchanged and authenticated. They do
not become current-source acceptance. The frozen branch-count repair policy still targets the
source path in its immutable historical intake; this cleanup neither retargets that narrow policy
nor reopens its investigation. Local documentation links follow current owners; immutable commit
and release source links retain their historical locations.
