# Oracle Count mutations and ERET completion

## Result (2026-09-27)

The cached-interpreter oracle now has a separately tested Count-mutation and
exception-return observer. Its observation-off/on game runs both complete
7200 emulator frames and 2574 guest updates. Twelve complete artifacts are
byte-identical across both runs and the retained earlier oracle capture.

A fresh comparison against the qualified native ERET capture again matches
all **1908 consecutive selected completed-update states**, then differs at
1909. The requested 1291 boundary is passed. This observation does not extend
the matching prefix or fix the outstanding divergence. Consumed VI already
differs at 1908; selected-state equality is not full-memory or timing parity.

## Implementation and contract

`scripts/oracle_cpu_boundaries.{c,h,patch}` instruments a private copy of the
existing corrected-Mupen/device-observer producer. The prior pinned producer
is unchanged. The patch applies on top of that producer with
`git apply --unidiff-zero`; copy the new C/header into its `src/r4300` first.
The standalone patch does not add those files or build a producer itself.

`scripts.phase95_oracle_replay --cpu-boundary-update 1908` requests one
invocation within an explicitly configured device-observation window, using
cached interpreter core 1. Missing device capture, an out-of-window update,
another core or malformed input rejects. The wrapper removes inherited
`JFG_PHASE9_CPU_BOUNDARY_UPDATE` before applying the explicit choice.

The versioned `cpu-boundaries.tsv` preserves two event types in one local
sequence:

- Count mutations: raw PC, old/new lazy anchors, before/after Count, reason,
  operand, Status/Cause, running-thread word and latest device-event sequence.
  Sites cover lazy updates, cached idle fast-forward, CP0 Count writes,
  Compare's temporary +2/-2, NMI reset and hard reset. Arithmetic is checked
  as unsigned 32-bit, including wraps.
- ERET: state before the original `update_count()` and after the original
  jump, EXL/LLbit transition, interrupt-eligibility check and anchor reset,
  but **before interrupt dispatch**. Records preserve EPC, Status, Count,
  anchors, LLbit, thread words and all 32 full-width GPRs. The previous ERET
  thread word is a raw selector observation, not an independently qualified
  host-stack owner or CPU switch.

The observer checks Count continuity at every actual instruction entry in
the requested invocation and around every instrumented mutation. A missing
change, invalid boundary, unsupported ERL return, I/O failure or row-budget
exhaustion fails capture. Completion requires observing an instruction in
the next invocation; shutdown alone cannot produce a successful footer.
The limit is 524288 rows, with a separate 128-MiB reader limit.

`scripts/phase9_oracle_cpu_boundaries.py` independently checks the arithmetic,
continuity, field widths, sequence/window, footer and ERET state transition.
Each ERET must have its associated immediately preceding lazy-Count row.
Those two rows overlap: their Count deltas must not be summed twice. Replay
records the completion, summary and digest, rejecting incomplete output.

These observations do not modify guest state, timing policy or event queues.
They do not qualify pure-interpreter/dynarec paths, bulk savestate restores,
physical-N64 behavior, ordinary instruction completion or deferred-work
accounting. Anchor changes between Count mutations are not yet all logged.
Raw Count values remain **unaligned across engines**.

## Executable verification

`scripts.test_oracle_cpu_boundaries` extracts and compiles the actual private
producer's `update_count` and ERET bodies against controlled CPU/interrupt
surroundings. The prior producer, new producer with observation disabled,
and new observed producer give identical final outputs under fatal ASan/UBSan.

Twelve cases cover lazy arithmetic/wraps, ERET with and without a due
interrupt, and the six other Count-writer reasons. The latter are controlled
mutations, not full CP0/reset semantic proofs. Four negative cases reject
unaccounted Count, row-budget exhaustion, unsupported core and ERL return.
The interrupt stub verifies ERET publication precedes dispatcher mutation.
The actual C output roundtrips through the Python reader with all seven
Count reasons and full-width GPRs preserved.

Retained sanitizer proof:
`tools/private/oracle-cpu-boundary-proof-20260927b/result.json`, SHA-256
`c84ba9b70142e05d357881a97bf71a5492d7907bf53dbd558fa5787f3701afbf`.
Eight new Python tests plus the replay-contract/device-reader tests pass:
29 total. The complete autonomy suite passes 362 tests in 86.664 seconds.
The new patch passes application checking against its retained base;
`git diff --check` passes.

## Live qualification and evidence

The guarded MSVC producer build completed with unchanged before/after source
inventory. It is retained under `tools/private/oracle-cpu-boundaries-20260927a`:

- Build receipt SHA-256:
  `ae31d6b8c1f3d98f3ce4d9ecaf69b6d3519f64fc8f86ff080af2ae033cb50806`.
- DLL SHA-256:
  `39df72c1631535718c5ae1920607435c4c27ea45079006b21bcccb2259548701`.
- EXE/DLL runtime digest:
  `14f05b4e6d4675a21e63f17b9fd3e29caee95c2442cfee5fa3a53e7a05a1932f`.

Under `tools/private/`, captures are
`oracle-cpu-boundaries-control-20260927a` and
`oracle-cpu-boundaries-observed-20260927a`; earlier control is
`device-events-oracle-20260927a`. The off-control inherited the setting in
the launcher environment, but replay removed it and created no CPU file.

All three captures have byte-identical whole update, retrace, consumed-VI,
point, device and checkpoint logs; four full focused RDRAM images at
1907-1910; and the final RDRAM image and screenshot. Independent qualification
rechecks point/device correspondence, full update parsing, actor bytes against
snapshots, capture completion/provenance, source inventory and runtime pins.
Backing evidence is hashed again after measurement. All 1984 shared delivered
input polls match the native capture and selected input. Initial flash matches;
oracle controller-Pak equivalence remains unverified.

The selected invocation contains **131033 events**: 130968 lazy Count updates,
2 idle fast-forwards and 63 ERET boundaries. Every ERET opcode matches all
four focused RDRAM images. Trace SHA-256:
`e077bad98fa9563278cc76d8b319a6cb5c97c122cceab1e2bfcb6884352ac5a1`.

The engineering qualification is observed `nonperturbation.json`, SHA-256
`bc22c59ffc8a91ec2461834c39eac523bfac7cf373ddd69f225a54c7cc5ded44`.
Its retained `qualify.py` records the checks. This is not an accepted autonomous
ledger job, a hermetic build attestation or promotion of the opt-in runtime.

## Next acceptance

The [Count-ledger research adapter](autonomy-oracle-count-ledger.md) now
reconciles every device Count in the invocation and implements registration,
guarded observation and feedback routing. Its live acceptance is recorded
separately; the engineering capture above is not retroactively a ledger job.

Combine these boundaries with the [native ERET observer](phase9-eret-transfer-observation.md),
the now-captured [oracle instruction effects](phase9-oracle-instruction-effects.md),
anchor/deferred-work accounting and raw code/
overlay identity. Qualify the bounded all-thread interval before using it to
choose between device-phase and different-executed-work explanations. Native
and oracle ERET counts alone do not establish a causal defect.

No count offsets, VI insertion, input changes, comparison shifts or ignored
fields were introduced. Global clock alignment, causal repair, product/campaign
parity and the entire autonomous improvement loop remain unproved.
