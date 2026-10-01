# Continuation entry must include its instruction's before hook

## Proven defect (2026-09-27)

The first native [paired instruction-effect capture](phase9-instruction-effect-stream.md)
rejected at invocation 1908. This is a concrete compiler/normalizer integration
defect, not a row budget exhaustion and not yet a causal explanation for the
native/oracle actor mismatch at update 1909.

In generated section 46, a return delay-slot pair at `0x02f00308` completes.
Resuming at `0x02f0030c` then emits an entry for the function start,
`0x02f002c4`, but an effect for the actual continuation target. The existing
normalizer installs continuation dispatch and labels at the compiler's
instruction-address comments. The old compiler printed a before hook ahead
of that comment. Consequently the dispatch was after the function-start hook
and the target label was after the target hook. The same layout exists in the
prior execution-observation root; the new paired observer detects it.

Patch `0022-instruction-boundary-hooks.patch` prints the instruction-address
comment before its instruction-specific before hook. Continuation dispatch
now skips the unexecuted function-start hook and includes the resumed target's
hook. Function-entry hooks, the normalizer, instruction operations and the
strict capture gate are unchanged. No PC alias, pair waiver, Count offset,
input change or comparison shift is introduced.

## Executable red/green proof

`scripts.test_generated_instruction_continuation` assembles a ROM-free fixture,
generates C with both compilers, runs the actual continuation normalizer, and
compiles/runs the results with fatal ASan/UBSan. Independent expected records
check every entry/effect PC, phase, v0 value, cleared continuation scratch
register and final result, across normal entry and three interior entries.

The baseline passes normal entry but fails all three interior-entry cases.
The corrected compiler passes all four. Both retain the expected final guest
results 7, 6, 4 and 0; the correction fixes the executed-instruction boundary,
not those fixture arithmetic results. Unexpected sanitizer exits cannot count
as the expected baseline failure.

Private proof: `tools/private/instruction-continuation-proof-20260927a/result.json`,
SHA-256 `1253eecc43b1be127b02ee114ea89a58b664c23d058ada4fd28021a644dce955`.

The existing twelve-path ordinary-effect proof and nine rejection cases also
pass with the corrected compiler. Disabled-hook output remains unchanged.
Proof: `tools/private/instruction-boundary-effects-proof-20260927a/result.json`,
SHA-256 `9da8d56b46d7836b8eae46c4f1fabbcac86925a59192f71769cf01df594dca85`.

Compiler SHA-256:
`44ff7ac30f2f68de49fb18e0e52f0da9b8d97681db6fe1e64e6e45912dfc03ae`.
Patch SHA-256:
`442304313b2024cf5d52729ea0bd52024807de540426562bc7b4aea9f297b25c`.
All 22 patches apply to the locked clean upstream checkout; patched compiler
source matches the tested prototype after line-ending normalization. Aggregate
patchset SHA-256:
`3cffdebe4df73cb59afce6c9bb67be6de28e7bac7ea2716eec70cc8dd51d956e`.
Earlier signed producer evidence does not cover this series. Pre-existing
publication whitespace failures in patches 0016/0019 are not waived.

## Game retest, separately from observer qualification

Corrected before-only and paired roots use the same pinned ROM, symbols,
original context and runtime manifest. Removing only the new paired hooks
reproduces all 2939 normalized bodies of the corrected before-only root.
The new detached native build uses source snapshot
`c6dd69966496df3faa6c741da4edef5fb518b787`; old roots and captures are retained.

The new source-bound build and all three native CTest targets pass. Its
observer-off replay reaches 4800 consumed VI, 1973 updates and 1984 polls.
A fresh comparison against the retained corrected-Mupen oracle passes every
selected-state update through 1908, then reproduces camera and 18 actor
differences at 1909. Whole native selected-update/retrace traces, input and
poll files are also unchanged against the older runtime.

Point/device/ERET traces and focused RDRAM are **not** byte-identical to the
older runtime. Full snapshot comparison finds 8, 6, 4 and 2 changed bytes at
1907, 1908, 1909 and 1910 respectively. For example, word `0x800a067c`
changes from `0x4dc8efbe` to `0x4dc8efc0`; this is retained raw data, not a
clock alignment or causal explanation. These changes are not ignored or
presented as observer non-perturbation. The candidate is not promoted to the
product runtime and old measurement lineage is not rebound to this build.

Retest: `tools/private/instruction-effects-control-20260927b/compiler-candidate-retest.json`,
SHA-256 `700ba61c29fc2a4c9a1af036fd5a05521ba5fab5020ffe72ef8b3aba716e494f`.

The corrected runtime's **own observer-off/on comparison passes** all eleven
whole artifacts, including its four full RAM snapshots. The strict stream
completes 1177321 pairs, including 60 ERET transfers, with exact independent
device/ERET witnesses. This resolves the observed continuation capture failure
without relaxing the gate; detailed pins are in the
[instruction-effect qualification](phase9-instruction-effect-stream.md).

Known selected-state matching remains through 1908, consumed-VI accounting
already differs there, and actor/camera state first differs at 1909. Passing
this compiler fixture does not advance that frontier or prove physical-N64,
full-memory, campaign or product parity. The entire autonomous-loop goal
remains open.
