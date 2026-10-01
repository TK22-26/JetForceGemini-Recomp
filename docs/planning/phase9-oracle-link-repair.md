# Reference interpreter link-register repair

## Result (2026-09-27)

The isolated reference CPU repair passes twelve independently specified
link-register cases in both Mupen interpreters, agreeing with Ares. The pinned
old cached interpreter fails all twelve. Two bounded game replays preserve
all thirteen checked whole artifacts from the old reference. Therefore this
is a demonstrated reference defect, **not the cause of the current 1909
selected-state mismatch**. The selected-state prefix remains 1908; consumed
VI already differs at 1908. The [1291 target is passed](phase9-execution-frontier-1909.md).

Neither the default native runtime nor the original TAS emulator is replaced.
The repaired reference remains an isolated candidate, not a silently updated
baseline for historical captures or signed evidence.

## Defect and independent test

The old `DECLARE_JUMP` implementation writes the link after the delay slot
and only on a taken branch. A delay-slot read therefore sees the old link;
a delay-slot write is overwritten; untaken REGIMM link branches omit the
link. The VR4300 specifies the link before the delay instruction, including
untaken branch-and-link forms. Likely-branch annulment suppresses the slot,
not the link. See chapter 16 of the
[NEC VR4300 manual, U10504EJ7V0UM00](https://hack64.net/docs/VR43XX.pdf).

`phase9_cpu_links_micro.S` tests JAL reads and writes in the delay slot,
JALR using r31 and another destination, and taken/untaken BGEZAL, BLTZAL,
BGEZALL and BLTZALL. It reports full-width slot and final link values.
Interrupts are disabled; exception behavior and undefined JALR rs=rd are
not qualified by these cases. Ares is an independent implementation, not
physical-hardware evidence.

| Isolated capture under `tools/private/` | Cases matching the manual |
| --- | ---: |
| `cpu-links-mupen-20260927c` (old cached interpreter) | 0/12 |
| `cpu-links-ares-20260927c` | 12/12 |
| `cpu-links-repaired-cached-20260927b` | 12/12 |
| `cpu-links-repaired-pure-20260927b` | 12/12 |

The repair captures condition and target before changing the link, writes
the sign-extended PC+8 before the slot, and removes the post-slot overwrite.
Cached out-of-block and idle macro paths receive the corresponding change;
their edge cases are not separately covered by these twelve microtests.
Count arithmetic and device scheduling policy are unchanged.

`scripts/oracle_guest_links.patch` applies with `git apply --unidiff-zero`
to the already qualified CPU-boundary producer, **not bare upstream**. A
fresh patch application reproduced both tested source files. The isolated
build changes only `src/r4300/r4300.c` and `src/r4300/pure_interp.c`.

The existing 28-case branch timing capture is byte-identical to its old-core
counterpart. The current native generator also passes its separate ten-case
guest-link fixture with relocated code and dynamic returns. That fixture is
not the same twelve-case oracle ROM and is not presented as such.

## Reproducibility and retained failed attempts

`scripts.phase9_cpu_link_adjudication` rechecks raw traces, ROM identity,
228 exact assembled instruction words, archived launch configuration,
engine identity, source/build receipts and runtime digests. It requires the
old twelve failures and exact Ares/repaired raw-value agreement. It does
not accept a model's verdict as proof. Qualification does not imply a
hermetic build, common-clock alignment, hardware validation or promotion.

The first probe incorrectly used an O32 `sd` pseudo-op, which stored a
register pair rather than the intended 64-bit GPR. Its retained `20260927a`
payload/captures are invalid semantic evidence. The corrected payload uses
explicit DSRL32 and two SW instructions; assembled-word validation covers
those stores. It is `cpu-links-20260927b/cpu-links.n64`, SHA-256
`c459349239e314017ba3cd353c7973a586e0450454291419d08065bf9c29299f`.
The user's source ROM is unchanged and the private derivative is not published.

Initial qualification also exposed that EmuHawk rewrites `config.ini` on
exit. The micro runner now archives exact prelaunch bytes in
`input-config.json` and pins them in the manifest. All four qualified link
captures were rerun with that archive; no post-run file was relabeled as
the launch configuration. Earlier captures remain untouched.

The first adjudication report predates additional manifest/runtime checks.
The authoritative new report is
`oracle-guest-links-20260927a/adjudication-v2.json`, SHA-256
`caa9032694d27d124fca743415cd9fe2ff83ae007cf71b90423dc3451fcf16f6`.
Sixty focused Python tests pass across link parsing/adjudication, rounding,
clock/branch observations, oracle CPU/Count ledgers and native effect readers.
Tests reject missing/changed launch configuration, empty manifests, added
runtime libraries, wrong interpreters and disagreement with raw observations.

## Game retest and limits

`oracle-guest-links-replay-20260927a` and `...20260927b` both finish the
7200-frame request normally, producing 2574 completed updates. Their update,
retrace, consumed-VI, CPU-boundary, device, point and checkpoint artifacts,
four complete focused RDRAM snapshots, final RDRAM and final PNG are all
byte-identical to the old oracle's corresponding thirteen files.

The post-capture reporter initially failed on a misspelled runtime-key name.
The complete game captures were preserved. The corrected qualifier verified
them without rerunning or modifying their traces. Both comparisons against
`instruction-effects-control-20260927b` pass all 1908 selected-state updates,
first differ at 1909, and validate all 1984 shared input polls. This is a
bounded partial-route result, not a whole-game or all-RAM parity claim.

Additional SHA-256 pins:

- Patch: `f86a62e4e4cdb4a13b6d52ef8ce1b6ca374da518dd8ee79c6885cafe8331c99c`.
- `repair-build.json`: `9008d5a3fe1148a3882c94d558f46b9852571006b288317259c1544b39481d6c`.
- Repaired Mupen DLL: `0416c09a5258179a1dab5288bdf239e01dbbf7ea3323696104891432dd97849a`.
- Repaired runtime: `debb852eeb661e204fee918a1304586af746c115ff8eedb009cbaa6f17bf0c3f`.
- Replay A `repair-retest.json`: `f42de3873d6667d5ea50ab006ca44fc4a136d58baded07082752d1ef693a4711`.
- Replay B `repair-retest.json`: `44cdc956ccce6beb73474cd22f30bdc7c5d0d17cc1f32f9f92ec9d9e17db4c0d`.
- Native link proof: `2e28bb10db90d1f9f2002d341f0dd1ca97e6240716b9dc2e5287e7ce626b5c23`.
- Branch timing repeat: `bc7a7f5b6e8c6ce874ba9245162f23f1744c9d6cb7b29d2f0e64ca5b5aea46ed`.

Follow-up: the [oracle effect observer](phase9-oracle-instruction-effects.md)
now passes bounded game capture and local-witness checks. Keep instruction
boundaries, exceptions and raw code identity explicit. The
[native effect stream](phase9-instruction-effect-stream.md) is already
bounded and paired; the cross-engine all-thread causal comparison is not.
Do not change native architectural links to reproduce the old oracle bug,
and do not treat this unchanged game result as a fix for 1909.
