# N64Recomp Phase 4 patch set

Patch 0019 fixes generated LUI signed-left-shift undefined behavior by shifting
an unsigned 32-bit bit pattern before sign extension. Fatal UBSan reruns of
the link, CPU-state, original-OS queue and interrupt fixtures pass. Earlier
recovering-UBSan exits must not be interpreted as clean sanitizer evidence.

The ordered patch files under `series/` apply to the N64Recomp revision
recorded in `dependencies.lock.json`. They contain only generic toolchain changes and
synthetic regression tests; they contain no ROM bytes, target-derived symbols,
addresses, or local filesystem paths.

`LICENSE.upstream` preserves the upstream MIT notice for the copied patch
context and toolchain changes. It does not make a licensing claim about game
code, game data, or any private generated output.

Apply it from the project root to a clean N64Recomp checkout. The applicator
verifies the exact locked commit, clean target state, contiguous manifest order,
every patch digest, and `git apply --check` before changing the checkout:

```sh
python scripts/apply_n64recomp_patchset.py --target path/to/N64Recomp
```

Then verify the upstream regression target:

```sh
cmake -S . -B build -DBUILD_TESTING=ON
cmake --build build --target N64RecompCLI N64RecompPhase4RegressionTest
ctest --test-dir build --output-on-failure -R N64Recomp.phase4_regressions
```

Always rebuild `N64RecompCLI` after applying or changing the patch set and
before generating private output. Record the exact executable's SHA-256 with
the private run evidence. The normalized-source preparation must also reject
stale output containing per-function `__func__` diagnostics; switch failures
use an opaque null name while retaining their address and table context.

Indirect-decision capture is absent by default. A private generation that
needs it must explicitly set `input.indirect_decision_sidecar_path` to a direct
child of `output_func_path`. The producer emits one canonical JSON sidecar with
the exact generated-callable member set and every dynamic-call, dynamic-tail,
bounded-switch, or native-return decision, plus every emitted direct call.
Dynamic decisions refer directly to that embedded set by kind; switch
decisions carry their exact finite target member set; native returns bind the
active native return continuation. Direct-call rows distinguish the
instruction class and transfer role (`linked-call` or `direct-tail`) for every
call emitted through N64Recomp's direct-address path, including JAL, REGIMM
branch-and-link, J tail calls, and conditional-branch tail calls. They also
record the actual lowering chosen by N64Recomp: generated callable, checked
runtime-address lookup, reference symbol, or event symbol. Checked lookups use
the explicit `checked-lookup-call` classification and
`fail-closed-lookup-miss` default. The producer applies fixed limits to
indirect-decision count, direct-call count, total switch members,
generated-callable count, function-name and instruction-class bytes, and total
sidecar bytes, and all defaults fail closed.

The configured output directory is a trusted, ignored private generation root,
not a shared attacker-writable directory. The CLI lexically confines the
sidecar to a direct child of that root and writes through a sibling temporary
file, while the project harness separately creates and validates the private
root. The generic patch does not claim hostile concurrent-writer resistance.
Private sidecars contain ROM-derived coordinates and target sets and must never
be committed or published.

The regression target covers bounded and unaligned big-endian word reads,
conservative stack-analysis invalidation, discarded MIPS `$zero` writes,
observable loads and CP0 reads to `$zero`, live-hook ABI widths, architectural
integer divide-by-zero/overflow behavior, signed multiply result bit patterns,
and fail-closed relocation extent, alignment, ordering, field-type, and index
validation. Generated stores and GPR assignments also carry explicit
architecture-width casts so warning-strict compilers preserve the intended bit
patterns without implementation-dependent implicit conversions, including
32-bit COP1 lanes/control state and signed memory-helper displacements. A
synthetic control-transfer regression proves observable delay-slot work is
emitted before the transfer and only unlabeled dead fallthrough remains
afterward. It also proves switch diagnostics do not embed per-function names.
The sidecar regression additionally proves default-off configuration, direct-
child path confinement, bounded capture, canonical deterministic rewrites,
exact generated-callable ordering, direct-call lowering capture, and
sorted/deduplicated switch targets, including a regression that distinguishes
JAL from BGEZAL and linked calls from direct tails.

Patch 0016 adds opt-in `input.emit_guest_link_registers` for the offline C
backend. It preserves architectural links before delay-slot work, including
untaken conditional links, relocated caller sections, and capture of indirect
targets before their source registers can be changed by delay-slot work.
The default remains off. Unsupported backends and source/link overlap fail
explicitly. ROM-free executable coverage lives in
`scripts/test_generated_guest_links.py` (fixed and relocated variants).
This patch revision is not covered by the previously signed producer pins;
full producer regeneration and acceptance are separate requirements.

Patch 0017 adds the explicit offline `emit_guest_cpu_state` profile: context-
owned HI/LO, the FP condition bit, and stored FCR31 control. It extends the
context ABI, so all consumers must rebuild against the same header. This
does not implement floating arithmetic exception generation. The thirty
ROM-free cases in `test_generated_guest_cpu_state.py` cover cross-function
register visibility, eight multiply/divide operations, finite FP comparisons,
and control/rounding preservation.

Patch 0018 adds `emit_guest_dynamic_returns`, requiring architectural links.
An indirect JR may return through the host continuation only when its captured
target equals this function's captured incoming guest link. Otherwise it still
uses the checked callable lookup. This enables register-saved return links
without assuming a particular register, function, or game route. Delay slots
execute before either action; their writes cannot alter the captured target.
The new profile emits sidecar schema 2 and an explicit guarded-union decision
range. Schema 1 cannot claim that range. The local normalizer validates it;
downstream signed evidence/producer acceptance still requires a full revision
refresh, not reuse of older signed metadata.

Patch 0019 emits LUI through an unsigned 32-bit shift before sign extension.
This removes signed-shift UB without changing the architectural result.
Fatal sanitizer execution, not a recovering-sanitizer exit code, is required
for the private CPU qualifications.

Patch 0020 adds default-off `emit_guest_idle_loops`: self-targeting B/J execute
their real delay slots and repeat, allowing a CPU-owned interrupt to resume
the guest. The old permanent host pause remains the default. Eight executable
ROM-free tests cover both forms at 1, 2, 7 and 1000 iterations, plus the old
configuration and invalid-boolean rejection. The private root-n producer has
20 patches; it is not covered by previously signed producer evidence.

Patch 0021 adds explicit `after_vram` instruction-effect hooks for the offline
C backend. Ordinary hooks run after the generated operation; transfer hooks
run after operand/condition/link evaluation and before the delay slot. A
before and after hook can coexist at one instruction, but duplicate hooks of
the same kind are rejected. `after_vram` must be nonzero, word-aligned, inside
the named function, and cannot share a hook entry with `before_vram`.
Exception returns, traps, unsupported CP2 operations and non-executable idle
loops fail closed. These are not hardware-retirement hooks: callbacks that
transfer execution or raise exceptions still need independent qualification.

`scripts/test_generated_instruction_effects.py` compiles a ROM-free fixture
and checks 12 execution paths under fatal ASan/UBSan, nine rejected cases,
unchanged disabled output, and exact configured-hook-only body changes.
See [the evidence and remaining limits](../../docs/planning/phase9-instruction-effect-observation.md).
The 21-patch series is not covered by earlier signed producer pins.

Patch 0022 places instruction `before_vram` hooks inside the emitted instruction
boundary, after its address comment and before its operation. The normalizer's
interior-entry dispatcher can then skip the unexecuted function-start hook
and enter the target's hook, rather than jumping past it. Function-entry hooks
are unchanged. `scripts/test_generated_instruction_continuation.py` compiles
actual generated and normalized code under fatal ASan/UBSan: the previous
compiler fails all three interior-entry checks; the correction passes those
and ordinary entry. The existing twelve effect-path and nine rejection tests
also pass, with disabled output unchanged. This repairs demonstrated hook
placement, not a proved cause of the gameplay timing divergence. The 22-patch
series requires new producer qualification; old signed pins are not reused.

Patch 0023 preserves real jump-table LW operations under `emit_guest_cpu_state`.
Bounded dispatch uses JR's loaded target captured before its delay slot, not
the precomputed table index. Duplicate members are deduplicated; runtime table
changes may choose another known member, but unknown/unaligned targets fail
closed. Relocatable sections use a captured runtime section base and retain
full-width target comparisons. Default-off code generation is unchanged.
`scripts/test_generated_guest_jump_tables.py` exercises 16 paths and two
rejections in both fixed and relocated variants under fatal ASan/UBSan.
This repairs guest register/branch semantics, not a demonstrated explanation
of the gameplay timing divergence. The 23-patch series needs fresh producer
qualification and does not inherit previously signed evidence.
