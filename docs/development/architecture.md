# Runtime architecture

How the native game is produced and how its main runtime components behave.
Each section names the source, tests and contracts to read before changing a
component. Fixes to specific defects are in the [runtime fix log](boot-gameplay-fix.md);
source attribution and implementation boundaries are in
[boot provenance](../../src/boot/PROVENANCE.md).

## Build pipeline

The [ROM build](rom-bootstrap.md) runs entirely on the user's PC:

1. The pinned JFG decompilation rebuilds a matching ELF from the user's ROM in WSL.
2. Overlay boundaries come from that build's linker metadata; JFG's custom
   relocation records are translated into recompiler metadata.
3. N64Recomp, with the maintained [patch series](../../patches/n64recomp/README.md),
   generates the CPU code; its RSP recompiler generates the audio microcode.
4. The generated code links against project-owned runtime, boot, device and
   host code and the pinned RT64 renderer, producing `jfg-native-boot.exe`.
5. The [unified frontend](../features/frontend.md) hosts that executable in a
   supervised process.

Generated code, ROM-derived data and private evidence never enter the
repository. Pins are in `dependencies.lock.json` ([summary](../upstream/pinned-version.md)).
The four [execution profile axes](../adr/0002-execution-profiles.md) (behavior,
execution backend, presentation, feature set) govern how optional behavior and
deterministic testing are separated.

## Native host ownership

[Native modularization](issues/native-runtime-modularization.md) maps the private implementation
files under `src/boot/native/`. `native_boot.cpp` coordinates startup and the run loop; memory,
window, audio, overlay loading, saves, task submission and diagnostics have separate owners.
Shared State preserves its member order and single timing/cache ownership. The candidate
regional pipeline now reconstructs and generates US, PAL and JP through one program model,
CPU/RSP pipeline and native source tree. Each executable links one immutable revision
descriptor and its own generated corpus. PAL/JP product admission remains closed.

Game references live under `include/jfg/game/`. `CodeRef`, `InstructionRef` and `DataRef`
separate callable entries, observation sites and bounded data. Binding ABI 3 carries each
instruction site's original word. Original body hashes, operand witnesses, data-content
checks and semantic callees qualify the generated bindings. Native consumer coverage is
checked before the expensive corpus build; a missing observer name still fails closed.

`MemoryContext` composes one descriptor and matching bindings. Game-facing `MemoryView`
requires that context; `GuestMemory` provides raw hardware memory access separately.
The navigation helper uses named regional globals and instruction guards. Native code
uses the linked revision, and synthetic tests explicitly supply fixture contexts.
`ResidentMemory` checks revision, resident owner, extent, alignment and available RAM.
An overlay reference cannot obtain resident access: named original module IDs resolve
through the descriptor, while the existing overlay owner controls live access.

`OverlayMemory` resolves a named original module through the selected descriptor,
then checks its loaded owner and DATA/BSS extent. Actor/player members derive
from qualified original instruction operands; no default US fixture is used by
production consumers. `RendererGameLayout` is supplied explicitly per session to
presentation, rain, camera, shadow and blur integration. Sound recovery and
native math have equivalent explicit layouts. Test fixtures supply their own
synthetic layouts so they cannot mask a missing production composition.

ROM asset coordinates have a separate `RomAssetDirectory` / `RomAssetView` owner.
The original PI initializer supplies qualified table/data operands; the view
checks revision, boundaries and every section offset before NPC parsing. Guest
RAM references cannot be substituted for these cartridge coordinates.

The private `native-operations.json` maps semantic operations to exact generated
entries and sources. Revision/descriptor/bindings identities, original body
hashes and generated source hashes are validated before native transformations.
This replaces US generated filenames in collision/cache/shadow/direct-device and
math-reference selection. The generated manifest requires the map.

The [three-region plan](../planning/regional-runtime-architecture.md) owns migration
and acceptance gates. The [regional issue](issues/regional-rom-support.md) records
current build results and the remaining binary-schema/feature matrix. v16 reaches
Goldwood after new-slot/reload on all three original-OS candidates; current v23
enhanced source has separate pending qualification. Generation and helper tests
do not establish campaign or released gameplay support.

## Generated CPU code and overlays

The regional pipeline qualifies ELF metadata before constructing the program
model. A reviewed shared-body recipe verifies every original member extent,
each member hash and the complete instruction span; it then represents one
complete body with interior entry aliases. Loaded section bytes remain unchanged.
This prevents a regional symbol label from truncating executable control flow.
See [ELF qualification](../../scripts/build/regional/elf_metadata.py) and its
[tests](../../tests/build/test_regional_elf_metadata.py).

The compiler-input inventory discovers direct-call, branch, constant-register
transfer and covered-alias entries. It preserves each complete original body
and closes branch destinations exposed by alternate-entry suffixes before
invoking the compiler. Section/body ambiguity rejects the input. The
[entry inventory](../../scripts/build/regional/code_inventory.py) and
[regression cases](../../tests/build/test_regional_code_inventory.py) cover the
PAL exception preamble and JP matrix/shared-trigonometry failure classes without
embedding regional addresses in the shared runtime.

Historical inventory for the previously supported US build (the new regional corpus has its own validated manifest):

- 3,729 executable function symbols (2,899 sized; 824 zero-sized aliases; six
  sizes recovered explicitly). 2,909 required bodies are generated with zero
  game-function stubs.
- 157 overlay slots: 155 populated, all placed dynamically by the loader.
- The ELF carries no standard relocations. JFG's custom tables hold 28,035
  records (520 main, 11,076 primary, 16,439 secondary); every HI16 is paired
  with a LO16. Three exceptional reference-table entries fail closed.

Each generated body is a `<symbol>_recomp` archive member with a separate
callable wrapper; patch archives link before the baseline, and strict patch
mode rejects unmatched or duplicate replacements. The
[Phase 4 contract](../planning/phase4-acceptance.md) defines the denominators
and the signed completion evidence.

`GeneratedOverlayRuntime` (tests: `tests/runtime/generated_overlay_runtime_tests.cpp`)
owns the generated overlay table and enforces the loader lifecycle:

1. Validate section metadata, the exact text-plus-data input, a word-aligned
   cached mapping and no overlap with static or active sections.
2. Stage text/data, clear BSS, and run the checked relocation callback against
   staging only; reported relocation counts must equal the denominator and no
   write may leave the section or touch BSS.
3. Resolve declared dependencies and prepare rebinds and instruction-cache
   invalidation, then commit memory, cache and bindings and publish a new
   generation with no-fail operations.

Any failure before commit leaves memory and registry state unchanged; a failed
rollback poisons the runtime. Lookup tokens bind runtime, module and
generation; `get_function(vram)` resolves only initialized static text or an
active overlay. Unloading a target invalidates its dependents; reload reuses
the original input and base under a new generation, so earlier tokens go
stale. Callbacks run under a busy guard that rejects re-entry.

## Boot, OS and timing

The native boot path starts at the original entry and reaches stable VI and
scheduler activity ([Phase 6 contract](../planning/phase6-acceptance.md) and
[record](../planning/phase6-native-boot-addendum.md)); the cartridge handoff is
described in the [fix log](boot-gameplay-fix.md#cic-6105-boot-state-health-and-ammunition).
Normal Play uses the native host-clock policy, including when the video FPS option is
Original. The separate diagnostic instruction/device-clock path retains original-OS contracts
but is not qualified as the default simulation clock; workload-dependent device time and
loading audio remain open. See [the current timing investigation](issues/original-mode-simulation-parity.md)
and [native audio policy](runtime/native-audio-playback.md). These reference notes describe the
original-OS model and its bounded qualification:

| Area | Reference |
|---|---|
| Absolute deadlines, retirement, interrupt delivery | [Execution clock](../planning/phase9-execution-clock-implementation.md) |
| Guest OS state and reference device timing | [OS timing](../planning/phase9-os-clock-qualification.md) |
| Serial-interface completion | [SI timing](../planning/phase9-si-completion-timing.md) |
| GPU results visible to the guest CPU | [Framebuffer writeback](../planning/phase9-renderer-cpu-writeback.md) |
| Before/after compiler hooks | [Instruction effects](../planning/phase9-instruction-effect-observation.md) |

The current regional boot verifier selects its backend explicitly. The default
original-OS mode validates the bundle/corpus/source identity, repeats a bounded
neutral-input run with fresh private storage, and compares the declared probe
observations. Its receipt is a boot smoke result, not emulator parity or a
complete runtime snapshot. The explicit cooperative Phase 6 mode retains the
historical oracle contract. The producer and parent supervisor share the same
bounded original-OS result parser, including exact retrace and poll-stop targets.
See [regional verification](../../scripts/verification/verify_regional_native_boot.py)
and [probe protocol](../../include/jfg/boot/original_os_probe.hpp).

The September 2026 original-OS comparison matched 1,908 consecutive selected
actor/camera update states against the corrected reference emulator; consumed
VI timing first differed at update 1,908 and selected state at 1,909
([boundary record](../planning/phase9-execution-frontier-1909.md)). That is
selected-state agreement, not full-RAM equality or hardware timing. Do not
shift comparisons, insert VIs, drop compared fields or install timing constants
to move that boundary; the [production guard](../planning/autonomy-progress-guard.md)
decides whether further investigation runs.

## Graphics

`GraphicsTaskBridge` authorizes task completion only when the backend accepted
the task, parsing completed with no unsupported command, every command-triggered
read stayed inside declared regions of a read-only broker and every declared
region was observed, the output kind matches the backend's capability, and an
independent oracle accepted the output. Completion is a rejectable,
non-signaling preparation followed by one `noexcept` commit. Upstream renderer
interfaces return no status, so this bridge is what prevents incomplete work
from being acknowledged.

RT64 is pinned to commit `5473732a822a4423b5696e7cb18fecc425a59875`; CMake
rejects a missing or different checkout, and RT64 stays outside the ROM-free
default build. The shell owns an 8 MiB RDRAM snapshot, converts it to RT64's
word-swapped layout and never hands RT64 the live simulation buffer.
`RendererCallbackRuntime` enforces one submit and one present per task, and
`Rt64RendererCallbacks` binds RT64 to the bridge, parser, oracle and completion
sink. The project-owned binding installs a fail-closed F3D base map plus JFG
handlers for DMA matrices, texture offset, the 10-byte vertex variant, triangle
batches with per-corner texture coordinates, counted RDP DMA lists, DMA
offsets, billboards and matrix selection; unknown commands end the submission.
Pinned-RT64 corrections are applied through hash-checked CMake patches that
leave the checkout unchanged.

GPU output the guest CPU reads is written back to guest RAM before task
completion, after validating owned bytes against the submitted snapshot; a
conflicting CPU write rejects the whole operation, and bytes outside tracked
framebuffer ranges are refreshed from the CPU snapshot. Original-timing builds
(the default generation) write back all completed color and depth output;
otherwise only completed 8-bit intensity buffers are written back
(selection in `src/boot/native_boot.cpp`; task submission/writeback in
`src/boot/native/live_tasks.cpp`).

Phase 7 accepted the renderer with real boot/title and gameplay tasks, three
byte-identical readbacks per scene and identical simulation hashes with
rendering disabled, semantic-only and fully presented
([contract](../planning/phase7-acceptance.md), [evidence](../../evidence/phase7-completion.json)).
To reproduce with private inputs, configure `JFG_ENABLE_RT64=ON`, the exact
`JFG_RT64_ROOT` and `JFG_BUILD_PHASE7_RT64_RUNNER=ON`, then run
`jfg-phase7-rt64-task` with the ignored capture directory and an independent
semantic-oracle file; it prints aggregate counts only.

## Audio

The RSP recompiler generates one audio wrapper whose internal dispatcher owns
two overlay permutations. `AudioRuntimeTaskWorker` owns that wrapper through
an install token, rejects stale, cross-worker, double and re-entrant use, and
passes only a brokered task view: bounded inputs plus checked access to
referenced memory (`write_region` for intermediate work buffers) and output.
Writes are staged; every output byte must be written exactly once; access
counts must match the bridge ledger; an independent validator must accept the
output before staged data commits. `AudioTaskSchedulerGate` then prepares and
commits completion exactly once. The host audio adapter in `src/bootstrap`,
the playback clock and the live volume path are project code; see the fix log
for pacing behavior.

## Saves and accessories

FlashRAM is the game's primary save device. The native candidate uses one shared
`FlashDevice` command owner over `FlashRamStore`: a 128 KiB surface, 128-byte
program buffer, 16 KiB sector erase and Count-based completion deadlines.
Programming clears bits; reset discards pending work. Device completion is
separate from host durability, and file replacement remains transactional.
The historical reference bus remains confined to its historical evidence path.
Synthetic device/storage tests and a bounded US cold boot pass; valid in-game
slot creation and reload still require regional acceptance. The
[FlashRAM issue](issues/flashram-device-contract.md) records commands, failures
and the upstream sector-erase evidence.

`ControllerAccessoryBus` models four ports with generation-bound Controller Pak
sessions, Rumble Pak switching and a project-owned logical note store. Native
rumble duration/cooldown uses the shared Count frequency, avoiding a fixed
60-retrace assumption. Physical regional controller behavior remains unverified.

## Other references

- [Feasibility record](../feasibility/README.md): Phase 3 spike results, the G2
  decision and the signed-evidence pipeline.
- `config/runtime-capability-matrix.json`: the original runtime gap analysis.
- [Upstream reference review](../upstream/reference-review-2026-10-01.md) and
  [catalog](../upstream/reference-catalog.json): source observations for overlay,
  save, controller, camera and audio work.

The regional composition and artifact boundary are recorded in
[ADR 0004](../adr/0004-regional-runtime-composition.md). Implementation status
and remaining gates stay in the linked regional issue and architecture plan.

The original-OS cache model receives its runlink pointer, original slot map,
record stride and memory extent from the linked regional descriptor/bindings.
The fast and slow instruction paths share that address translator. Source
identity captures every non-cache file in its declared source roots, including
inline implementation and shader inputs. Both corrections pass component checks;
the current native build/qualification status remains in the regional issue.

The four-hour continuation stopped with v23 host rebuilding incomplete after a
stale-object linker failure. See the [final checkpoint](issues/regional-rom-support.md#end-of-the-four-hour-continuation); no enhanced Play or product handoff is claimed.
