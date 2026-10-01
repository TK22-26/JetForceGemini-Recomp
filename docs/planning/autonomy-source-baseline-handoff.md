# Rebuildable source baseline for the repair lane (2026-09-26)

## Verified result

The update-1909 baseline now has a private source commit that an isolated
repair worktree can actually check out. A fresh native build from that commit
reproduced **all 1973 native completed-update records**, the complete retrace
trace, and the controller-poll trace byte for byte. A new native/BizHawk ledger
job reproduced the first selected-state mismatch at 1909 and matching delivered
inputs. This is repair-loop infrastructure progress, not a new game fix.

The main branch and its index were not changed. The user's separate scope
assessment edit was excluded. The snapshot includes 195 explicitly selected
public source changes, including the existing runtime work; it contains no
private generated code, ROM, or emulator binary. Its local-only ref is under
`refs/autonomy/source-snapshots/`, not a development/release branch. It is not
an independently reviewed or merged commit.

## Implementation

- `scripts.autonomy.source_snapshot` freezes explicitly supplied public source
  paths in an alternate index based on the existing HEAD. It captures working
  file contents, new files and tracked deletions without staging over the
  user's index. It rejects private paths, links, excessive inputs and concurrent
  source/HEAD/index changes. Git's normal clean/EOL rules apply; the manifest
  separately records raw source-file hashes and immutable Git blob identities.
- `scripts.autonomy.source_build` binds a completed guarded CMake build to that
  snapshot and its native EXE/DLL identity. It checks the clean detached source
  worktree, successful configure/build results, finished child guards and
  preserved logs. It rejects changed build evidence, executable or DLLs.
- `scripts.autonomy.update_job --source-build RECORD` registers the actual
  source commit from that record rather than the main branch's older HEAD.
  Successors inherit and revalidate the binding. Update and focused-boundary
  diagnosis packets now use their baseline's source commit as well.
- Native-repeat and candidate-retest tool identities include the new source
  validators. The candidate lane's existing requirement that implementation
  and baseline share a source commit can now use this real rebuilt baseline.

These are **recorded local build provenance**, not proof of a complete,
hermetic compiler/generated-input/dependency closure. `build_closure_verified`
stays false. The source snapshot includes the runtime changes at capture time;
later harness-only changes are pinned separately by the replay producer's tool
identity. Rebuilding the snapshot does not imply that it contains later
harness changes.

## Private evidence

Under `tools/private/autonomy/source-baseline-1909a/`:

- `source-snapshot.json`: snapshot and raw/Git file inventory;
- `build-result.json`: explicit CMake argv, successful bounded checks, about
  20 seconds configuring and 337 seconds compiling/linking;
- `build-0/1.stdout`, `.stderr`, `.guard.json`: preserved build evidence;
- `source-build.json`: the runtime/source binding;
- `rebuild-update-equivalence.json`: all 1973 rebuilt/native updates match.

The detached checkout is `tools/private/ab1909s`; its fresh build is
`tools/private/ab1909b`. The existing production/diagnostic executable was
not overwritten.

| Identity | Value |
| --- | --- |
| Private source commit | `189787f9ed446936faea9f2c554750e1a4246022` |
| Rebuilt native EXE SHA-256 | `69a38f6de137f45bc58ddabbd2698d8dbc39249709acb20c117381fe156df1ba` |
| Rebuilt native runtime SHA-256 | `db48dfbb32edc5da94bc4abd5921b1bb7ee90fc2d4e5c384998e433896b8ca4f` |
| Source-build record SHA-256 | `68ac6269f84825422aadec1e9e2d3d16fb2ce40b30100c33bc486501324aadf7` |
| Matching native update trace SHA-256 | `45ee833c282ef24bd4e07f8377e0528a73aed58148b5f6d1059ea7edcac88f86` |
| Ledger job | `execution-update-f6b6450b3b760d121bfbea0e` |
| Sealed result SHA-256 | `a450d67ac22f3b1748300d08fbcc853c53427afb126299f5ec2ff814e18b3563` |

Registration/replay command used:

```powershell
python -m scripts.autonomy.update_job `
  --from-job execution-update-f796defa05b25cdfb31cba6f `
  --native tools/private/ab1909b/Release/jfg-native-boot.exe `
  --emulator tools/private/oracle-rounding-build-20260924a/corrected-emulator/EmuHawk.exe `
  --execution-profile original-os-probe --target 4800 `
  --source-build tools/private/autonomy/source-baseline-1909a/source-build.json --execute
```

The job sealed a completed **diagnostic**, not a parity pass: selected state
matches through 1908, then differs at 1909. The earlier consumed-VI mismatch
remains unresolved. No AI/API service was invoked in this build/replay proof.

Tests cover index preservation, source mutation, new/deleted files, immutable
snapshots, bad build/guard results, changed runtime/evidence, and worker,
successor and diagnosis source-commit propagation. The final broad suite passed
all **117 tests**, and `git diff --check` passed. Repeating the registration
command returned the same passed job without launching another replay.
The ledger integrity audit found 87 valid passed seals and zero integrity
issues, with no active jobs. Historical failed/blocked jobs remain unresolved.

## Remaining repair-loop work

The [first proof-gated repair cycle](autonomy-proven-repair-cycle.md) has now
used this baseline for bounded implementation, independent review, a fresh
candidate build and previous-prefix regression. It repairs the qualified
REGIMM annulled-slot Count omission, but leaves the game frontier at 1909.
General automatic proof selection, bounded candidate selection/integration,
complete dependency closure and broader gameplay coverage remain unaccepted.
The new source binding does not authorize blind timing edits or relax any
comparison, review, legal, source-provenance or full-scope acceptance gate.
