# Phase 9: execution-driven prefix passes 1291

Follow-up: [the extended and repeated comparison](phase9-execution-frontier-1909.md)
now matches selected state through update **1908**, with the next timing
discrepancy at 1908 and actor/camera mismatch at 1909. The original 1300
evidence below remains unchanged.

## Result (2026-09-26)

The opt-in original-OS execution path matches the pinned corrected-Mupen
oracle strictly, at the same completed-update indices, through **update 1300**.
Two independent cold-boot native runs reproduce the result. The cooperative
control still first diverges at update 1292.

This fulfills the bounded request to pass 1291. It is not full-game parity,
default-runtime promotion, complete runtime snapshot acceptance, a 100-run
determinism result, or a refresh of signed Phase 4/G2 evidence.

## Evidence

| Run | Completed native updates | Strict oracle comparison |
| --- | ---: | --- |
| `execution-device-control-native-20260926a` | 1417 | First difference 1292 |
| `execution-original-os-native-20260926t` | 1309 | All 1300 available oracle updates match |
| `execution-original-os-native-20260926u` | 1309 | All 1300 available oracle updates match |

Artifacts are under `tools/private/`. Each new run ends normally at 3000
consumed retraces with 1319 sampled controller polls, 1387 graphics tasks,
1498 decoded audio tasks and zero unsupported MMIO accesses. Elapsed wall
times were approximately 42 seconds each. The recorded input route has
10881 polls, so these are explicitly partial-route tests, not route completion.

Both new runs have byte-identical full update and retrace trace files,
including their native timing/input metadata. The legacy aggregate state
digest also agrees; it is explicitly **not** a complete CPU/device snapshot.

The correction appears at the original failure boundary without shifting
update indices, input polls or comparison fields:

| Update | Native consumed VI | Oracle consumed VI | Controller poll (both) |
| --- | ---: | ---: | ---: |
| 1290 | 2940 | 2940 | 1299 |
| 1291 | 2943 | 2943 | 1300 |
| 1292 | 2946 | 2946 | 1301 |

The available oracle artifact ends at 1300. An attempted 1309 comparison
reports missing oracle update 1301, **not** a newly observed state divergence.
Updates 1301–1309 therefore remain unqualified against the reference.

### Pins

- Executable SHA-256: `6edd2c402141dce44a2a0d4f81f4bdf66e9eedefcf0f10d36133c5b726106397`.
- Generated root: `execution-root-20260926o/root`, 379218 instruction hooks.
- Oracle: `execution-task-oracle-20260926b/update-hashes.jsonl`, SHA-256
  `2f2867837c3aa1ee5281135f49e8e0c48062fe285acc369a38d21ab1d8f592dc`.
- Native update trace (both): `71a4ac3c95266a79247f1595b2174daf4e7adaa45d28d5cd13951995b2691c2d`.
- Native retrace trace (both): `f62d8938b9fbc4b352fb59c28c8b024526eebff030d62651689caf13b2662c99`.
- Aggregate state digest (both): `bc762ccfaf5d2fac495412d86f02c51a3e52df6008ef64a0869b0991b9959c39`.
- Input: `phase95-south-regression-poll-smoke-20260923a/selected-input`, SHA-256
  `6d91c02cf5c2c0563ae6de0cf644fbdd176d2221df81f40f0aee9b84e6c16fb5`.
- Initial flash SHA-256: `b5a41c3758763bbec72769fab4a2533bf2db0b6312d93d25a695f9e4b9e02260`.
- US ROM SHA-256: `159dde164c475976a3e527fbb20978431d4765f2c63019b3530c3aa8772595aa`.

## Implementation and limits

The CPU executes original private-ROM OS initialization, queues, thread
switches, exception handlers and controller routines. Host transport preserves
continuations; it does not choose guest scheduling outcomes. CPU instruction
work drives Count and the independently authored device models. No fitted
route-specific OS call cost, inserted gameplay VI, copied oracle gameplay
state, forced pacing value or comparison bypass was used.

The owned device path covers tested VI, PI ROM/FlashRAM, SI/PIF/CIC, CP0
Compare, SP/DP completion ordering and AI FIFO timing. Device behaviors were
qualified using isolated micro-ROMs; Windows and fatal ASan/UBSan unit tests
compare timing windows and payloads. Detailed evidence, rejected intermediate
runs and profile limits are in [the qualification log](phase9-os-clock-qualification.md).
The profile is corrected-Mupen compatibility, not a physical N64 timing claim.

The new path still requires explicit `JFG_PHASE9_GUEST_OS_PROBE=1`,
`JFG_PHASE9_GUEST_LEAF_PROBE=1` and `JFG_PHASE9_RENDERER_WRITEBACK_PROBE=1`.
It has a separate `jfg-phase9-original-os-probe` report with `acceptance:false`
and `runtime_snapshot_complete:false`; it does not fabricate legacy HLE
thread snapshots to satisfy the old report format. Unqualified device modes
and event ties still stop explicitly. The default cooperative path is unchanged.

## Next boundary

Extend the pinned oracle beyond 1300, continue the same-index comparison,
and qualify any newly reached behavior. Promotion and checkpoint-resume
acceptance additionally require complete CPU/device/transport side-state
coverage and wider regression evidence. The 1300 prefix is real progress;
it is not evidence that those remaining requirements are finished.
