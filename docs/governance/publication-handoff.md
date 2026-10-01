# Public source repository handoff

On 2026-10-01 the owner authorized a separate repository containing a scrubbed
source snapshot. The original development repository remains private and its
history, open review, operational ledger and private evidence are preserved.
This replaces the earlier proposal to change the original repository's visibility.

The public repository has fresh Git history using the generic maintainer
no-reply identity. It excludes five emulator patches with unresolved licensing,
all ignored local inputs, and old hosted content. Permissive upstream notices
are retained, including the CIC algorithm attribution added for this snapshot.
See [the source audit](../legal/publication-audit.md) for the exact boundary.

## What a collaborator can test

A normal clone builds the ROM-free host shell and synthetic tests. The `jfg`
shell does not execute the game. The `launcher-preview` branch adds a Windows
[ROM-to-build recipe](../development/rom-bootstrap.md) and graphical launcher.
Testers install its developer-tool prerequisites and supply their own supported
ROM; generation and compilation run locally. The launcher package contains no
game runtime or assets. Start with [the contributor handoff](../development/handoff.md).

## Validation

Snapshot checks are recorded below after guarded execution. The private
preparation baseline passed 64 CTests and 51 focused Python tests; its full
Python suite ran 1658 tests with 10 failures, 2 errors and 18 skips. Those
failures involved patch-whitespace checks, stale source/tool identities and a
drifted signed Phase 6 binding. They were not repaired by re-pinning evidence.
Omitted oracle patches additionally prevent their producer identity checks
from running. This snapshot is not a passing release candidate; the full
Python CI lane remains enabled so those failures remain visible.

## Repository controls

The publication workflow establishes protection of the public default branch
and private vulnerability reporting. Subsequent changes require pull requests,
review and the required policy, Windows and Linux checks. No old branches,
tags, pull requests, workflow logs, releases, caches or artifacts are imported.
The owner-authorized initial snapshot creates the new repository; it does not
merge the original private PR or erase that review's unresolved checks.

The existing production guard remains enabled. All snapshot builds and checks
use the original publication investigation's remaining budget. The three
previously shelved investigations remain shelved with their charges intact.
The local ledger is not distributed. A clone must not create a fresh allowance
to resume exhausted work; preserve existing accounting with the maintainer.

## Snapshot verification results

- export: passed.
- Current source hygiene: passed.
- Project and schema validation: passed.
- Focused Python tests (51 tests): passed.
- Windows x64 Release configure: passed.
- Windows x64 Release build: passed.
- CTest (64 tests): passed.

These checks cover this exported source. They do not replace the known
full Python suite failures or establish game or campaign acceptance. The
complete fresh Git history is also scanned before the first push.
