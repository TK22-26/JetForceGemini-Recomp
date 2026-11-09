# Launcher explorer worker outlives its window

- ID: LAUNCHER-EXPLORER-SHUTDOWN-20261101.
- Status: verified in managed tests; live-owner verification pending; not released.
- Severity: moderate command ownership/lifetime defect.
- Affected: Windows development launcher; existing map explorer during regional migration checks.

The actual-window test in `NavigationExplorerTests` started exploration, closed
the map, and found movement still present after its 150 ms observation. Fixture
cleanup then failed because the background worker still held `ai-command.txt.tmp`.
The same suite had passed immediately before the regional session changes. The
failed run was concurrent with native compilation; this suggests scheduling
pressure exposed the race, but that trigger is not independently proven.

The source cause is explicit: `FormClosing` only called `StopAi`, which set the
runner cancellation flag and returned while the worker still owned the final
stop command. The window had no join/completion boundary. Region import and
save routing do not touch this worker.

The candidate waits at most two seconds for worker completion after requesting
cancellation. If it has not stopped, closing is cancelled and the window retains
ownership with a status message. No second writer races the worker's final
command, and no thread is forcibly terminated. The existing actual-window
regression exercises the close path; fresh validation is recorded below.

Private evidence: regional-architecture-20261101 step 070 managed-test log,
including the initial controls assertion and the secondary cleanup exception.
Personal saves and game data were not involved. Transferable lesson: cancellation
is a request; releasing a UI/profile owner needs an observed worker termination.

The fresh managed suite and setup checks passed after the candidate, including
the actual-window close regression and new regional bundle checks. This is a
local test result, not an in-game owner retest or a published resolution.
