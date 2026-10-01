# Update 1261: isolated oracle rounding repair

## Diagnosis (2026-09-24)

With the SI deadline experiment enabled, native matches the original oracle
through update 1260. At update 1261, actor 11 at `0x801baf80` differs at
offsets `0xee`, `0xef`, `0xff`: native `22 25 a8`, oracle `21 cf 52`.
Before the update the actor bytes agree. The current native actor bytes are
identical to the older native instruction-probe capture at update 1265.
All four parent-function call argument sets and captured 256-byte A1/A2/A3
blocks likewise match the older native capture after excluding clock labels.
The new watched word is again `0xc2047dd6 -> 0xc20d2225` in dispatch
`0x8000bc28`. This ties the new frontier to the previously traced CPU case.

The older instruction probe localized that case to conversion of exact 558.5
under FCR31 nearest mode: native gives 558 and Mupen gives 559. Fresh runs of
the same pinned micro-ROM reproduce Mupen=559 and Ares=558. The
[NEC VR4300 manual, table 5-5](https://www.bitsavers.org/components/nec/mips/1995_NEC_VR4300_MIPS_RISC_Microprocessor_Users_Manual.pdf)
specifies ties to an even least-significant bit, supporting 558. Native
arithmetic must not be changed to reproduce this oracle defect.

Source inspection independently identifies the cause in the local reference:
nearest-mode `cvt_w_s` routes through `round_w_s`, which uses C `roundf`.
That function's halfway rule is away from zero, not ties to even.

## Isolated correction

No native game arithmetic or original emulator was edited. A private copy
of the existing Mupen source and already available dependency libraries was
built using its VS2022 x64 Release project. The copied source is upstream
oracle code, never linked into the independently authored game runtime.

`scripts/oracle_round_even.h` is an independently authored finite nearest-even
helper, independent of host rounding direction. `scripts/oracle_round_even.patch`
replaces the four shared float/double-to-word/long nearest-rounding helpers
in the private core. This corrects a general halfway rule, not one operand,
PC, actor, or frame. It does not qualify exception flags, NaNs, out-of-range
integer conversions, or all dynamic-recompiler paths.

Build root: `tools/private/oracle-rounding-build-20260924a`.
Source checkout: `bdddf4a58aa1a022afb11dc73294a81a5aa7bbd5`.
Original `fpu.h` SHA-256:
`ade51a5f0bab44d863c3a3b243be70f92d33281548674128c03f45cdf3ef0672`.
Baseline DLL SHA-256:
`95f5432448a9638b743b68caf8c44ea81ec2e823da53f618281b8856f5679415`.
Corrected DLL SHA-256:
`ec3ecb418f1a408f282ff292e8a532c4bb755be30f579f61ec90f5ea56ddcb08`.

To reconstruct, copy `tools/upstream/BizHawk/libmupen64plus/mupen64plus-core`
and `tools/upstream/rt64/src/contrib/mupen64plus-win32-deps` into a **new**
private build root as sibling directories. Build the unmodified baseline
first, using `projects/msvc/mupen64plus-core.vcxproj`, Release/x64, and
absolute private `OutDir`/`IntDir` overrides (use trailing forward slashes).
Then apply `scripts/oracle_round_even.patch` with `git apply --unidiff-zero
--directory=<copied-core-path>`, and copy `scripts/oracle_round_even.h` into
the copied `src/r4300` directory. Build to separate corrected output/object
directories. Never build over or replace a pinned emulator's DLL.

For each side, copy the original emulator into a new private directory and
replace only that copy's `dll/mupen64plus.dll`. Existing microtest and oracle
replay wrappers then create fresh workers and pin their new runtime digests.
The original TAS/reference emulator remains untouched.

## Validation

- 56 finite helper cases cover positive/negative ties, non-ties, zero, and
  a word-range boundary under all four host rounding directions. GCC test
  and Windows Release test builds succeed; the helper preserves host mode.
- Fresh original-reference microtests: `si-frontier-rounding-{mupen,ares}-20260924a`.
- Rebuilt baseline microtest returns 559; corrected microtest returns 558.
  Both complete with the same test ROM and mode zero. Artifacts:
  `oracle-rounding-{baseline,corrected}-micro-20260924a`.
- Rebuilt baseline's 3,000-frame game update trace is byte-identical to the
  pinned original oracle's trace, with matching final RDRAM hash
  `59d7074fdcaf1681388342ed492893a4d4ffd6b0fda8b84da78c40149267c87c`.
  Artifact: `oracle-rounding-baseline-route-20260924a`.
- Corrected-reference route replay removes the update-1261 discrepancy and
  matches the unchanged SI-candidate native through **update 1291**, using
  the same numbered completed-update comparison. The first new difference
  is update **1292**, in actor records. Artifact:
  `oracle-rounding-corrected-route-20260924a/native-comparison.json`.
  No offset matching or ignored arithmetic field was used. This qualifies
  the local finite-rounding repair on this prefix, not the entire reference.
- Windows CTest `jfg.oracle_round_even` passed. The tracked patch reverse
  check against the isolated corrected source passed.

All artifact names above are under `tools/private`. These are bounded
reference-qualification checks, not whole-game parity or authorization to
replace the TAS core. The SI timing candidate remains opt-in and the
persistent autonomous goal remains paused.

The next frontier is now traced to an elapsed-VI/pacing discrepancy before
the actor differences; see [VI pacing investigation](phase9-vi-pacing-frontier.md).
