# Phase 9 hardening audit

Date: 2026-09-01. Branch: `develop`.

This records a code audit of the runtime, renderer, and build/test layers
performed while the Goldwood vertical slice was being stabilized, the
findings that were acted on, the evidence for each change, and the findings
that were deliberately left open. Every change below was validated against
the preserved 40,452-retrace Goldwood route capture
(`manual-stick-range-20260831-220319`) by exact full-render replay unless the
entry says otherwise.

## Correction to the Goldwood HUD renderer diagnostic

`phase9-goldwood-hud-renderer-diagnostic.md` describes a route-specific
repair for the display-list alias `0x00C01B18` at snapshot offset
`0x0021D090`: normalize it to `0x00001B18` on the theory that JFG's 4 MiB
RDRAM wraps segment-zero addresses at 22 bits. Replaying the recorded route
with the current binary reproduced the original rejection at retrace 40,44x,
so that repair was never effective. Inspecting the failing task's RT64
snapshot (`audit-baseline-20260901/final.rdram.rt64`) settled the cause:

| Address | Content | Interpretation |
|---|---|---|
| `0x0021D090` | `06000000 00C01B18` | The G_DL edge under investigation |
| `0x00001B18` | `468084A0 ...` | Main-program MIPS code (the documented wrap target) |
| `0x00401B18` | zeros | Overlay section 1's BSS (RT64's 23-bit mask result) |
| `0x00439488` | `E7000000 00000000 BA001001 ... B8000000` | A complete display list |

Generated overlays are linked at synthetic addresses of N MiB for section N.
Section 12 is linked at `0x00C00000` with a `.text` of `0x1920` and a `.data`
of `0x2C0`, so `0x00C01B18` is a pointer into section 12's `.data`, produced
by overlay code for its own display list. Its RT64 shadow at `0x00439488`
holds a well-formed list (pipe sync, other-mode words, geometry mode, EndDL).
The pointer therefore needs the ordinary overlay-shadow translation, not a
wrap. The translation was being computed but never written because the
materializer skipped `words[1]` for direct display-list edges whenever the
command's segment was configured, and the special case only applied when the
translation had left the word unchanged, which it never does for this
address.

Changes:

- `src/boot/native_boot.cpp` (`materialize_live_graphics_overlays`): a
  direct `0x06`/`0x07` edge whose address was translated into an overlay
  shadow now takes the translated absolute address whenever the configured
  segment base carries no physical offset. RT64 adds the KSEG0 base and its
  physical mask strips it again, so the traversal and the interpreter agree.
- `include/jfg/renderer/rt64_f3ddkr_address.hpp`: removed
  `materialize_f3ddkr_snapshot_address` and its tests. The literal-address
  gate is gone.
- The "Remaining acceptance" bullet in the HUD diagnostic that asked for a
  replay with the narrowed repair is superseded by the replay recorded below.

## Renderer bounding (`src/renderer/rt64_f3ddkr.cpp`)

RT64's stock interpreter has no iteration cap, an unbounded return-address
stack, and no bounds check on `fromRDRAM`. F3DDKR's handlers relied on masks
that alias out-of-range addresses onto valid-looking snapshot bytes. Each of
the following now fails closed with a distinct `rejection_reason` (codes are
declared in `src/renderer/rt64_f3ddkr.hpp`):

| Code | Condition | Why |
|---|---|---|
| 5 | more than 65,536 G_DL edges in one task | a self-referential list hung the game thread or grew the return stack without bound |
| 6 | return stack deeper than 64 on a call-form G_DL | same failure, call form |
| 7 | G_CULLDL with an empty return stack | RT64 reported this as a clean EndDL and silently ended the task |
| 9 | texture shift larger than the current texture address | the subtraction wrapped to a ~4 GiB address that `loadBlock` dereferenced |
| 10 | F3D G_MOVEMEM payload outside the 8 MiB snapshot | stock handler dereferences a 16 MiB-masked address unchecked |

Address resolution now reports a sentinel (`kF3ddkrInvalidAddress`) instead
of masking when the resolved address is outside the 24-bit RSP range or when
the task DMA offset pushes a guest address past the 8 MiB snapshot. Because
RT64 stores G_MW_SEGMENT bases unmasked, resolved addresses are MIPS virtual
addresses; the direct, KSEG0, and KSEG1 windows are accepted and every other
segment is rejected. The first attempt at this rule rejected KSEG0 outright
and stopped the route at its first frame, which is recorded here so the
mistake is not repeated.

Stock F3D `G_SPRITE2D_BASE` (0x09) is mapped to `unsupported`; F3DDKR has no
sprite microcode and the stock handler dereferences the pointer unchecked.
`G_MOVEMEM` (0x03) is kept because JFG emits it, but wrapped with a range
check.

Diagnostics: the rejection fields are no longer overwritten by every
successful G_DL edge. The most recent edge is kept in
`last_display_list_address` / `last_display_list_target` and copied into the
rejection fields only when no handler recorded a more specific cause.
`Rt64GraphicsDiagnostics` is filled by named assignment instead of positional
aggregate initialization. Data words inside counted 0x07 blocks are counted
(`nested_data_words`) rather than rejected; the materializer's own comment
records that low opcodes in those blocks are data, and rejecting them was
wrong.

## Boot fail-closed gaps (`src/boot/native_boot.cpp`)

- **Guest address span.** The 0x8A000000-byte reservation was released
  before the RDRAM, ROM, MMIO, and overlay views were placed, leaving every
  gap free for host allocations. A wild guest pointer into such a gap read
  host memory instead of faulting. `GuestBacking::create` now re-reserves
  every free gap in the span as no-access memory after the views are placed
  and treats a gap that is no longer free as a failed attempt. Sub-64 KiB
  tails are left alone because no allocation can be placed there either.
- **MMIO single-step handler.** The vectored handler acted on any
  `EXCEPTION_SINGLE_STEP` while a guard page was armed, including ones from
  other threads, clearing their trap flag and re-arming early. The arming
  thread id is recorded and the single-step branch is taken only on that
  thread.
- **Relocation bounds.** `site_offset > shadow.extent - 4U` underflowed for
  extents of 1 to 3 bytes. The extent is now checked first.
- **Host audio.** A missing or mismatched SDL audio device was a fail-closed
  dispatch, which prevented headless replay on hosts without a usable device
  and blocks parallel soak. Setting `JFG_PHASE9_NULL_AUDIO=1` opts into a
  null sink whose consumption follows the emulated AI DMA clock. Without the
  variable the behavior is unchanged, so a manual run cannot lose audio
  silently.

## Runtime (`src/runtime`)

- `recomp_support/minimal_runtime.cpp`: every CPU trap bridge aborted with
  no output. `fail_closed` now takes a `TrapSite` and names the bridge on
  stderr before aborting. The Phase 4 object-shape audit pins this object to
  exactly one external data symbol (`section_addresses`) and counts external
  COMDAT string literals as data, so a first version using literals failed
  the audit with `runtime-data: inventory-mismatch actual-count=5`. The
  message text now lives in function-local `static constexpr char` arrays
  and the site names in one static two-dimensional array; the audit passes
  unchanged.
- `generated_overlay_runtime.cpp`: one published-address mismatch returned
  `runtime_poisoned` without setting `poisoned_`, so later operations
  proceeded on the inconsistent table. It now poisons like the other sites.
  The flag is `mutable` because the discovering path is `const`.

## Phase 4 closure pins

`minimal_runtime.cpp`, `generated_overlay_runtime.cpp`, its header,
`CMakeLists.txt`, and `tests/CMakeLists.txt` are part of the frozen Phase 4
source closure whose SHA-256 digests are pinned in
`scripts/phase4_evidence_harness.py`, with the harness itself pinned in
`scripts/validate_phase4_private_evidence.py`. Both CMake files had already
drifted from their pins at commit 570a9cb, so a refresh was owed before this
audit. The pin tables and the harness self-pin were refreshed together, as
the Phase 4 run-book requires. What remains is the run-book's next step: rerun
the eleven pinned production audits and re-sign `evidence/phase4-completion.json`
with the project key. That step needs the signing key and the WSL producer
builds and is not performed here.

## Validation

Replays of `manual-stick-range-20260831-220319`, full render, target
retrace 40,452:

| Replay | Binary | Result |
|---|---|---|
| `audit-baseline-20260901` | HEAD 570a9cb | renderer trap at `0x0021D090`, the documented alias |
| `audit-renderer-bounds-20260901` | + renderer bounding, first range rule | trap at first frame: KSEG0 segment base rejected (rule corrected) |
| `audit-renderer-bounds2-20260901` | + corrected range rule | same trap as baseline, no earlier divergence |
| `audit-alias-fix-20260901` | + materializer fix and boot changes | reached retrace 40,452; `unsupported_accesses` 0; 20,156 presented frames |
| `audit-final-20260901` | + trap messages and poison flag (final tree) | reached retrace 40,452; identical `state_hash` and `journal_hash` to the previous row |

Final route hashes: `state_hash`
`4d294ef6b615b5dd05218c76c4a405ba963b763e39728f4fc3e47f76e5c2a9f0`,
`journal_hash`
`cfd8c4e252d077261e009fd96a093ec750bf44f56ef607054b9a7a234907b392`.
The route now loads overlays 100, 110, 106, 118, 10, and 95 after the
previously rejected task, which the 2026-08-31 replay never reached.

Other checks on the final tree:

- `jfg_rt64_shell_tests` passes after each renderer change.
- CTest in `build-phase8-private` (Release, 32 tests excluding the ROM-gated
  Phase 6 and Phase 9 probes): 32 passed.
- `jfg_generated_object_shape_audit` passes.
- `tests.test_phase4_production_harness`: 62 of 66 pass. The four failures
  are `fixed build tool differs from its repository pin` for `cmd.exe` and
  `wsl.exe` (the installed Windows binaries no longer match the pinned
  digests after a Windows update) and the two GCC sanitizer cases that run
  through the same `wsl.exe` pin. They fail identically without this
  change set and are environmental.

## Second pass (same day)

- **Canonical probe record.** The four host wall-clock totals
  (`audio_task_us`, `graphics_prepare_us`, `graphics_submit_us`,
  `graphics_present_us`) are removed from the `retrace-target` record and
  its parent-side format check, and written as a `totals` row in the
  `.timing.tsv` side channel instead. The canonical line is now
  byte-identical across deterministic runs. The interactive `jfg-phase8-play`
  summary keeps them; it is not a determinism artifact.
- **Exception unwinding through guest frames.** Generated C targets are
  compiled with `-fexceptions` on GCC/Clang (`cmake/GeneratedCode.cmake`),
  and `jfg_boot` propagates `/EHc-` on MSVC so callers no longer assume
  `extern "C"` callees cannot throw. `ExecutorShutdown` can now unwind
  through a parked guest body on every supported toolchain.
- **Iteration order.** `generated_overlay_runtime` uses `std::map` and
  `std::set` in place of the unordered containers, so callback order and
  the first reported error no longer depend on the standard library's hash
  layout.
- **CI.** The sanitizer lane configures with `JFG_ENABLE_ADDRESS_SANITIZER=ON`
  (the same branch the identified Phase 6 sanitizer build uses) plus UBSan
  flags, builds every target, and runs the whole CTest set. The Windows
  lanes no longer exclude `jfg.g2_trap_probe_runtime`, since the quarantine
  is Linux-runner-specific; `docs/tests/quarantine.md` records the scope.
  These workflow edits are untested until the next push.
- **Test hygiene.** The generated-root and trap-probe Python tests now use
  `build/test-tmp` as their scratch root instead of `tools/`. The assembly
  and trap-derivation tests keep `tools/` because the scripts under test
  reject local paths outside that prefix by design. The Phase 6 CMake
  behaviour test removes its scratch build directory through `addCleanup`.
  The nine leaked `tools/g2-*` directories and two stray test executables
  were deleted.
- **Launcher.** The worker now removes the `LocalDumps` registry key and
  unregisters its scheduled task when the game exits.
- Pins for `CMakeLists.txt`, `cmake/GeneratedCode.cmake`, and the overlay
  runtime sources were refreshed again, with the harness self-pin.

Validation of the second pass: `audit-final2-20260901` (full render,
same route) reached retrace 40,452 with the same `state_hash` and
`journal_hash` as the first-pass replays, the canonical record contains no
`*_us` fields, and the `totals` row appears in the timing side channel.
CTest 32 of 32, `jfg_rt64_shell_tests`, the object-shape audit, and the
Python modules whose scratch roots or cleanup changed all pass. The full
Python sweep (598 tests) leaves five failures: the four stale Windows
tool-pin cases in the Phase 4 harness suite, and the Phase 6 manifest
drift test described below. `scripts/validate_project.py` passes after its
Windows lane commands were updated to match the workflow.

## Phase 6 completion manifest

`evidence/phase6-completion.json` binds `ci.yml`, both CMake lists,
`cmake/GeneratedCode.cmake`, `native_boot.cpp`, `jfg_native_boot_main.cpp`,
`minimal_runtime.cpp`, and `tests/test_phase6_cmake_behavior.py` by digest,
and `tests.test_phase6_policy` reports every drifted file. `CMakeLists.txt`
and `native_boot.cpp` already differed from their bound digests at commit
570a9cb, so that manifest, like the Phase 4 one, was already due for a
refresh. The refresh is `scripts/build_phase6_completion_manifest.py` with
the project signing key, following `docs/planning/phase6-acceptance.md`; it
is not performed here. Until it runs, that one policy test and the Phase 4
harness tests report drift by design.

## Third pass (2026-09-02)

- **Overlay activation cost.** `reapply_generated_r32_relocations` made two
  further full copies of guest RDRAM (`original` and `pre_relocation`) and
  ran `std::any_of` over every descriptor for every initialized byte. Both
  callers stage a copy of live memory and rewrite only the module window
  before calling, so live memory is now the reference for bytes outside the
  window, the pre-relocation snapshot covers only the initialized window, and
  a per-byte site mask replaces the quadratic scan. Every check the function
  made before is still made. Validated by the route replay below producing
  the same state and journal hashes.
- **`dispatch` duplication.** The three copies of the overlay-32 hint and
  King Bear callback bookkeeping are one helper. The larger split of the
  function (the VI service loop inside the `osStartThread` handler, the
  repeated fail-closed overlay publication blocks) is still deferred until
  the determinism loop exists to validate it.
- **Renderer in CI.** A `renderer` job on `windows-2022` checks out only the
  pinned RT64 revision (`scripts/bootstrap_tools.py --only rt64`, a new
  option), configures with `JFG_ENABLE_RT64=ON`, builds
  `jfg_rt64_shell_tests`, and runs `jfg.rt64_shell`. RT64 vendors SDL2 and
  dxc for Windows, so no extra SDK is required. Untested until pushed.
- **Tooling out of `tools/`.** The eight hand-written Phase 4 helpers now
  live under `scripts/research/phase4/` with a README stating that they are
  provenance only and depend on untracked private result trees.

Validation of the third pass: `audit-final3-20260902` (full render, same
route) reached retrace 40,452 with the same `state_hash` and `journal_hash`
as every earlier passing replay; CTest 32 of 32; hygiene and project
validation pass with the moved tooling; the workflow policy test accepts
the new `renderer` job.

## Fourth pass (2026-09-02): dispatch split under per-retrace hashes

The per-retrace semantic hash trace (`JFG_PHASE9_RETRACE_HASH`, written by
`write_retrace_semantic_hash`) is now the validation instrument for
refactors of `dispatch`: a baseline trace is recorded once, each refactor is
replayed with the trace enabled, and `scripts/compare_phase9_retrace_hashes.py`
must report a full match. This is stricter than the final `state_hash`,
which would accept a divergence that later converged.

Extractions in this pass, all validated that way against the baseline
`hash-baseline-8550d01`:

- `service_vi_frame`: the 137-line body of the VI service loop that lived
  inside the `osStartThread` handler (frame budget, journal, window and
  audio service, presentation, pending task completion, VI field, SI and VI
  delivery). The handler now reads as a scheduler loop.
- `fail_closed_overlay_publication`: the four identical fail-closed blocks
  after `publish_synthetic_overlay`.
- `note_hints_control_call` from the previous pass.

`dispatch` is now about 1,550 lines. The remaining bulk is the HLE name
switch, which is a table in the shape of an if-chain and is the next
natural extraction (one handler per function, dispatched by name).

## CI and evidence refresh (2026-09-02)

Draft PR #10 (`develop` into `main`) exercised the workflow, since the
workflow runs only on pull requests and pushes to `main`:

| Lane | Result |
|---|---|
| Build (ubuntu-24.04), Build (windows-2022) | pass |
| Sanitizers (Linux), full CTest under ASan+UBSan | pass |
| RT64 renderer shell (Windows), new lane | pass in 6m10s |
| Policy and schema validation | fail |

The policy failure is `check_repository_hygiene.py --history`: every commit
must use the generic maintainer identity and a UTC timestamp, and 29
reachable commits on `develop` do not (26 predate this audit). Fixing that is
a history rewrite of `develop` and is a maintainer decision, not a code
change.

Evidence refresh work started: the `jfg.phase6_native_m2` test passes
against the Phase 6 private tree; the Phase 4 matrix run stopped
immediately on the stale `cmd.exe` pin, so the `cmd.exe` and `wsl.exe`
digests in `WINDOWS_BUILD_TOOL_SHA256` were refreshed (the seven other
pinned tools still match) along with the harness self-pin. The Phase 6
private tree also exposed a build break: `resolve_bzero_host_offset` is
defined under `JFG_PHASE8_LIVE_RUNTIME` but called unconditionally, so a
Phase 6 configuration without the live runtime does not compile.

### Phase 6 refresh: done

The Phase 6 manifest was rebuilt and re-signed. The CTest wrapper for
`jfg.phase6_native_m2` does not pass the sanitized executable, so a summary
produced that way fails the acceptance gate (`sanitized_build_identity`
null). The refresh therefore ran `scripts/verify_phase6_native_boot.py`
directly against the rebuilt Release and MSVC ASan native-boot executables
with `--require-clean`, installed the resulting public summary and stub
ledger under `evidence/`, then ran `build_phase6_completion_manifest.py`
with the project key referenced by path. `--verify` reports `valid` and
`tests.test_phase6_policy` passes. The three-retrace probe's `state_hash`
changed from the previous evidence, which was produced at f85e726 before
the bzero, hint-dialogue, and Goldwood runtime commits; the BizHawk oracle
comparison inside the same evidence still passes.

### Phase 4 refresh: blocked on a product decision

The matrix run fails at the clang replay configure step with
`normalizer-revision: digest-mismatch`. The Phase 4 manifest binds the
`normalized-canonical-v3` root (generated inventory `bf5eb4fe...`), but that
root records the normalizer digest of an older
`scripts/build_private_generated_root.py`. The current normalizer matches
the `normalized-phase8-hash-v*` roots (inventory `684125ec...`), which are
what every Phase 8 and Phase 9 binary is built from. The preparation step
rejects a private root produced by a different normalizer by design, so the
refresh cannot proceed against `canonical-v3` as it stands. Two ways
forward, either of which changes what the Phase 4 manifest claims:

1. Regenerate a canonical root with the current normalizer and rerun the
   eleven audits against it, accepting a new generated inventory digest.
2. Declare `normalized-phase8-hash-v4` the Phase 4 product and run the
   matrix against it.

Which root is the Phase 4 product is a maintainer decision. With the tool
pins refreshed, all 66 `tests.test_phase4_production_harness` cases pass
again; `evidence/phase4-completion.json` remains the f782e09 signature over
a closure that has since changed until the matrix is rerun.

### Phase 4 refresh: matrix done, G2 re-derivation is the remaining step

Against `normalized-phase8-hash-v4` the matrix passed all eleven audits at
commit dd15dad and produced `phase4-private.json` and the G3 product
projection (`tools/results/phase4/g3-final-dd15dade-hashv4-v1/prepared`).
The private body validates: every pinned-harness transcript re-executes
cleanly. Compared with the signed f782e09 core, only `config_sha256` (the
hash-v4 N64Recomp configuration) and `minimal_runtime_source_sha256` differ;
generator, patch set, and input ELF pins are identical, and the four pins
finalize cross-checks against G2 all match. The G2 CPU case for the new
projection was derived (`g2-cpu-case.bin`).

Finalize is blocked by the G2 bundle, not the Phase 4 body. The G2
producers' tracked dependency closure (`PRODUCER_TRACKED_DEPENDENCY_PATHS`)
changed in six files since the reviewed commit: `CMakeLists.txt`,
`cmake/GeneratedCode.cmake`, `bounded_custom_graphics.cpp` (earlier
commits) and `generated_overlay_runtime.{cpp,hpp}`,
`minimal_runtime.cpp` (this audit). By design that invalidates the eleven
producer binary pins, the build attestations, and every executed slot. The
new tracked closure digest at 235a088 is
`080dfef5e6f4725c7199afa52b05afb640de1e8e7e4606226ceab2ff217cfe5d`, and the
producers were rebuilt A/B under WSL GCC 13.3 against hash-v4 with the
attested define set.

Re-authoring the G2 pins needs one input this session cannot derive: each
build attestation's `private_generated_closure_sha256`, which the validator
only requires to be a well-formed digest shared by native/oracle pairs and
whose original derivation is not recorded in any script. Inventing it would
be fabricated evidence, so the G2 re-derivation stops here pending the
maintainer's derivation rule. Everything else (new binary digests, closure
digest, reviewed commit and tree, harness re-execution of the fourteen
slots, assembly under WSL, finalize) is mechanical once that rule is known.
`evidence/phase4-completion.json` therefore remains the f782e09 signature.

### Commit identity rewrite (2026-09-02)

The 30 commits between the `main` merge base fda10b2 and the head of
`develop` were rewritten with `git filter-branch` to the generic maintainer
identity and UTC timestamps; no tree changed. `develop` was force-pushed
with a lease against its previous head, and the old refs were dropped
locally. None of the affected commits were on `main` or on any `agent/*`
branch. A local stash from 2026-08-18 (one file, an earlier
`evidence/phase6-completion.json` edit) still points at the old history, so
the local `--history` check reports three commits reachable only through
that stash; the remote has no stash and CI is unaffected. The Phase 6
evidence was regenerated once more so its recorded `producer_revision`
names a commit that exists after the rewrite.

## Findings left open

- ROM-free unit tests for `native_boot.cpp`: the environment-variable and
  option parsing should be moved into a struct that a test can drive
  without a ROM. Not started.

## Fifth pass (2026-09-04): Phase 4/G2 refresh closed

The hash-v4 Phase 4 matrix body and G3 projection were retained as the current
product. All fourteen newly assembled G2 slots in
`g2-final-cde8a9c-v1` passed the tracked private validator, including fresh
dispatcher execution of each pinned producer. An earlier validation attempt
overlapped another validator process and returned a transient harness
rejection; a serial instrumented run and a clean uninstrumented run both
passed all slots.

The completion builder then authenticated the hash-v4 Phase 4 private body,
the G2 public/private pair, their cross-gate pins, and the anonymous signing
key. Its post-signature trusted validation passed before the refreshed
`evidence/phase4-completion.json` was installed. Phase 6 had already been
refreshed and signed in the prior pass. The former Phase 4/Phase 6 evidence
refresh finding is therefore closed.

## Partial-route determinism runner (2026-09-05)

`scripts/run_phase9_determinism.ps1` starts the Phase 9 exit-gate loop before
slice completion. It launches a bounded number of independent accelerated,
headless, null-audio replays, records the per-retrace semantic hash stream for
each run, and compares every stream with the first run. A process failure,
missing trace, length mismatch, or first differing retrace fails the batch and
retains the individual run directory and comparison report. The default is
the scope-required 100 runs with four concurrent workers; smaller counts are
available for smoke testing the runner itself.

The first unattended batch used the surviving 1,794-retrace partial route
from `manual-health-ammo-restart8-20260901-0020`. One hundred independent
runs completed with four workers, zero unsupported accesses, and all 99
per-retrace comparisons matched the baseline. This is early determinism
coverage only: it does not satisfy the Phase 9 exit gate until the recorded
route is the complete selected slice.
