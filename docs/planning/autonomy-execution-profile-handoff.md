# Pinned execution-profile handoff (2026-09-26)

## Verified result

Follow-up: the [source-baseline handoff](autonomy-source-baseline-handoff.md)
now provides a private source commit, an isolated fresh build and a replay
reproducing the current native baseline byte for byte. The earlier live jobs
below retain their original base-HEAD provenance; they were not rewritten.

The original-OS execution profile now runs through durable update, focused
capture, boundary-analysis and native-repeat jobs. This is a working
model-free diagnostic chain, not acceptance of the complete self-improvement
loop. The [game-state frontier remains 1908/1909](phase9-execution-frontier-1909.md).

Live ledger jobs in `tools/private/autonomy/`:

| Job | Verified result |
| --- | --- |
| `execution-update-f796defa05b25cdfb31cba6f` | 4800 native VI, 1973 completed updates, 1984 matching delivered input polls; first selected-state difference 1909 |
| `execution-update-f796defa05b25cdfb31cba6f-focus` | Automatically selected updates 1907-1910; reproduces the 1908/1909 onset and preserves all four RDRAM captures per side |
| `vi-boundary-72ab11da19b56759dbcda716` | Automatically queued, replay-free analysis: preceding interval consumes 3 native versus 4 oracle VI; onset interval consumes 3 on both sides |
| `native-det-20b168137074c3fbdad71b57` | Two concurrent native repeats have identical complete update/retrace trace bytes and aggregate state hashes to the baseline |

Both successor selectors queued exactly one job, then returned no duplicate.
Reinvoking the same completed registration command with unchanged source/tools
returned the existing passed job without launching another replay. The repeat
job used two runs, **not** the separate 100-run acceptance gate. The old timing
value was not forced and comparison indices were not shifted.

Result-manifest SHA-256 values, in table order:

```text
23d6d1e667e71d2208ceb0e988c4976260de3fd6b03caebfceec276864a23455
6a6cc3dcf7e6ca008e52ac607df362d99ea51ea30c10e7124967d834bf493e7e
f569d6ee9ac519cac23b1bd68572d72f3f77b41a1b7e23b2015fed46f0dbdc4c
997c7cafbe6ed422cd4512b1fae1edef45ed0171f9c2057f31518cc7d4bf3b5c
```

The final ledger integrity audit verified 86 passed seals, zero integrity
issues and no active jobs. It also retained 12 queued and 12 historical
failed/blocked jobs; those were not rerun or relabeled. Integrity is not parity.

## Execution contract

New opted-in packets carry an `execution` object with five exact fields:

- `profile`: `original-os-probe` or `cooperative`;
- `native_runtime_sha256`: native EXE/DLL closure;
- `oracle_runtime_sha256`: emulator EXE/DLL closure;
- `oracle_source_config_sha256`: installed source configuration bytes;
- `oracle_config_sha256`: expected isolated configuration after removing host
  controller bindings, including platform newline bytes.

Queueing pins these values. Workers validate them before execution and before
sealing, and check that native/oracle result manifests report the selected
profile and corresponding runtime/configuration. Changed dependencies cause
a baseline rebase, not continuation under the old identity. A rebase retains
its execution profile; extension cannot silently switch profiles.

Determinism identities include the contract, which is copied from the verified
baseline. Reviewed candidate retests also inherit the profile; they separately
measure and verify the newly built candidate's own EXE/DLL closure. Recovery
checks the same result identity before reusing a completed artifact.

Historical packets remain readable. Native workers explicitly select the
cooperative profile for legacy packets instead of inheriting diagnostic shell
flags. A legacy packet cannot accept an original-OS result lacking a contract.
Named-profile comparisons use same-index focus and boundary analysis; they
cannot extend a mismatching prefix by finding a shifted matching suffix or
silently fall back to the legacy HLE-poll diagnostic lane.

## Model-free entry command

Use an existing sealed alignment/update job to supply its selected input and
ROM provenance. This command queues one pinned replay and executes only that
job. It does not start an AI agent or an unbounded service:

```powershell
python -m scripts.autonomy.update_job `
  --from-job phase9-south-alignment-hardkill-long-20260923 `
  --native build-phase9-private/Release/jfg-native-boot.exe `
  --emulator tools/private/oracle-rounding-build-20260924a/corrected-emulator/EmuHawk.exe `
  --execution-profile original-os-probe --target 4800 --execute
```

Omit `--execute` to queue only. Job identity includes the profile/runtime,
target, predecessor and producer-tool identity. The predecessor's historical
alignment result is lineage, not an assertion of alignment or parity. A
passed update job means a completed, sealed comparison, which may contain a
mismatch; consumers must inspect `prefix_match` and `first_divergence`.

## Tests and limits

100 Python tests passed across execution contracts, update/supervisor jobs,
runtime handoff and native/oracle replay contracts. A focused 21-test rerun
also passed after the final scheduler guard. Coverage includes DLL/config
mutation, incorrect result profile, successor inheritance and duplicate
suppression, candidate runtime separation, two parallel repeats and simulated
supervisor interruption after capture with no-replay recovery. The latter is
a synthetic interruption test, not a new live hard-kill drill. `git diff
--check` passes. No AI/model/API service was invoked by the live jobs.

Still open: the proper runtime correction at the new timing boundary; a live
real-defect diagnosis -> coding candidate -> independent review/build/retest
cycle under this profile; qualification of candidate build/source closure;
wider corpus and failure/restart coverage; complete native snapshots; and the
remaining exploration/full-scope gates. The tested native executable is pinned
by bytes but contains worktree changes beyond its recorded base Git commit;
it must not be treated as proof that rebuilding that commit reproduces it.
The newer source-baseline job closes that specific gap with a separate private
commit and fresh executable; full build dependency closure remains open.
`acceptance`, alignment/parity claims and complete-snapshot claims remain false.
