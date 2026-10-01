# Architectural jump-table load and target repair

## Finding (2026-09-27)

The qualified native and oracle instruction-effect captures now support a
bounded, explicit correspondence check. `phase9_instruction_correspondence.py`
checks the oracle's four-row return lead-in against its actual JR target and
unchanged full GPR state; it does not search for a convenient alignment.
It also qualifies the copied four-instruction exception vector using all eight
focused RAM snapshots, exact opcodes, expected GPR effects, EXL state, delay
slot, branch target and following handler entry. Both original PCs and row
numbers remain in the report. No general PC normalization or Count fitting is
performed. Twelve tests cover positive and negative boundaries, unknown
transitions and malformed trailing data. Both readers are exhausted even after
the first difference, so a bad stream footer cannot be ignored.

After 3137 matching rows and one qualified vector mapping, the first shared
state difference is a jump-table LW. The reference register contains the loaded
target; generated native code contains the entry's address instead. The emitted
source confirms that the compiler substitutes ADDIU for this LW. Dispatch
previously used a saved table index, masking the wrong architectural register.

Private comparison: `tools/private/instruction-correspondence-20260927a.json`,
SHA-256 `ef27fd344c178c5cf45d4e125adf32d9e27ea2ab696d30fbd6c52b5ab8dbad00`.
This is a demonstrated compiler defect, **not yet a causal explanation of the
camera/actor divergence at update 1909**. The previously qualified selected-state
prefix through 1908 already exceeds the requested 1291 milestone; consumed-VI
accounting differs at 1908. Those are not claims of complete CPU/game parity.

## Generic implementation and executable proof

Patch 0023 retains the real LW under the explicit offline `emit_guest_cpu_state`
profile. JR captures its actual target before its after-effect hook and delay
slot. Bounded dispatch compares that target against the deduplicated generated
member set. A runtime table modification can select another member; it cannot
silently use the old index. Unknown or unaligned targets report a switch error
and return rather than falling through. Relocated members use the captured
runtime section base and full-width architectural target comparisons. The
legacy default-off path remains unchanged. This does not add unrestricted
dynamic-code support or alter game instructions.

The original ROM-free fixture checks loaded GPR visibility, delay-slot reads,
delay-slot target clobbering, all four table entries, duplicate destinations,
and runtime changes within the member set. The old compiler fails all 16
architectural checks and does not reject invalid table targets. The repaired
compiler passes 16 checks and both rejection cases, in both fixed and relocated
variants, under fatal ASan/UBSan. Existing compiler regression, ten guest-link
checks, thirty stored-CPU-state checks, twelve instruction-effect paths and
nine rejected-hook configurations also pass.

The initial `guest-jump-tables-{control,fixed}-20260927a` attempts had an invalid
test-driver RAM base and crashed before generated code ran. They are retained
as failed fixture attempts, not counted as compiler proof. Corrected evidence:

| Private report | SHA-256 |
| --- | --- |
| `guest-jump-tables-control-20260927b/result.json` (failed control) | `021b417f7baad019f5c7576dedb35a5d3cad019e007fe8127dc1d0083769499b` |
| `guest-jump-tables-fixed-20260927b/result.json` | `5fe3b5d717519cffa2406ea37dab9a3ae44a4f5526b47056de8ea30fb136a114` |
| `guest-jump-tables-relocated-20260927a/result.json` | `4acccf6e8785bbcb2e8612c5cd6b27a98c9a56d337e95ebe3642ecafec609884` |

Compiler SHA-256:
`aae3d5e8d7df1dc5d8e05e1438c70285d0ff8e1f92e27c5a5d046cadb0cae1b3`.
Patch SHA-256:
`98cc3e2eb48c4a99fbfba646ad01e76e224f480c092fa528f0b56d877671f3b7`.
All 23 patches apply to the locked upstream checkout, reproducing the three
modified compiler source files after line-ending normalization. Aggregate
patchset SHA-256:
`1534ac9e20f83d7b2f20f9e981c53d6cde4185bb1b2729402ae7d7c502478ef2`.
Earlier signed producer pins do not cover this series.

The consolidated qualification also regenerates the fixture with this profile
disabled on both compilers and proves byte-identical C bodies. Its report is
`tools/private/guest-jump-qualification-20260927b/result.json`, SHA-256
`0a81fa5bf368a4be355de8cc9d7894811ca8c16d8a05f44a59a91e22ba10a991`.
The 39 focused reader/correspondence tests and 383 automation tests pass.
The initial qualification `a` is retained: the subsequent zero-context patch
format removes whitespace-only context lines without changing compiler source
or binary bytes. The 20-test patch-publication suite still reports its two
pre-existing failures in patches 0016/0019 and one skip; patch 0023 is clean.
Those older failures are not waived or presented as a fully passing suite.

## Fresh game candidate

Both before-only and paired roots were regenerated with unchanged ROM,
symbols, original context and runtime manifest. Removing only the paired
observer hooks reproduces all 2939 before-only generated bodies. Manifest:
`tools/private/guest-jump-effect-root-20260927a/manifest.json`, SHA-256
`b63c94cff49672649a5f5beb60388fb3dcf070eb575bcd3f512872f41f9d1669`.
The isolated native source snapshot is
`6e5209cafc89c74aae40202c3c90148765a74bfa`.

The native build succeeds and all three ERET/effect CTest targets pass. Its
source-bound build receipt is
`tools/private/autonomy/source-guest-jump-20260927a/source-build.json`, SHA-256
`3ed65306a20780d9f3543c9161694df3440a607036fac3eaec53349a96be1b4a`.
Executable SHA-256:
`4ed966cfaf2a65edb4194f3c5941a15bc313639a5a1757db3a6ae110d166482a`;
runtime SHA-256:
`7d2382e3ddd50dd4bd5160bc64c4f69d1e4e47ee5d33a52ab6b3508c2e4208b0`.
The snapshot retains the pre-formatting patch bytes; the fresh qualification
above independently proves the publication-format patch produces identical
compiler source. No old build or capture receipt has been rebound.

The observer-off replay completes 4800 VI. Selected game-state comparison
passes through update 1908 and still first differs in camera and 18 actors at
1909. Selected-update/retrace traces, inputs, polls, ERET transfers and all four
full focused RAM snapshots are byte-identical to the preceding native build.
Point/device traces differ; they are retained rather than treated as
observation-only changes. Retest:
`tools/private/guest-jump-effects-control-20260927a/compiler-candidate-retest.json`,
SHA-256 `01878b9b1a94898473ff02b89bff3087c73c88be22810f049b41808bcf7d1a81`.

Fresh observer-off/on qualification passes all eleven whole artifacts and
completes 2354642 rows, including 1177321 entries and 60 ERET transfers. All
256 independent device-instruction witnesses and 60 ERET witnesses bind.
Report: `tools/private/guest-jump-effects-observed-20260927a/nonperturbation.json`,
SHA-256 `850ade56555af481c1a92f366f76f1a08dc3089c3e14afa654caff4844de13d9`.
Stream SHA-256:
`1135734f31495b2f66277f887604da229e296c4878549eb60c337dcb1038b7e3`.

The fresh checked correspondence now passes the formerly wrong LW and reaches
3435 matching rows (previously 3137), retaining the same explicit vector
mapping. Its next difference is a 64-bit load of saved LO from a thread context
(the following MTLO confirms the field):
native restores 1 while the oracle restores 0. The surrounding inputs and GPRs
agree. All four focused snapshots independently contain those different values
at that location, so the next investigation is the provenance of saved CPU
state, not a claim that this is another load-lowering defect. The earlier
save/computation that produced the values has not yet been identified.
Report: `tools/private/guest-jump-correspondence-20260927a.json`, SHA-256
`ce74bb0f4d3d840cd753c068bf14a8ca17f1fa0c46b6526e858d180a760caf09`.
Both validating readers finish; raw clocks remain unaligned and unmodified.

This candidate is not promoted, not an accepted autonomous ledger job, and not
covered by old signed evidence. There is no hard blocker on further diagnosis.
Full-memory, timing, campaign and product parity and the entire autonomous
loop remain open. The requested 1291 selected-state milestone is exceeded;
this compiler repair advances the instruction comparison, not the 1908
selected-game-state frontier.

The [durable instruction-observation job](autonomy-instruction-observation.md)
now independently requalifies these experimental captures under the supervisor
and records the saved-state finding in the ledger. That admits diagnostic
evidence, not this repair as a reviewed/product-integrated candidate.
