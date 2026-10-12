# PERF-002: Missing visible frame timing and slowdown capture

Status: verified in muted replays; local preview delivery; owner F8/live slowdown capture pending (2026-10-12).
Severity: moderate observability limitation; slowdown severity/location unclassified.
Owner reports slowdowns while testing the high-refresh preview but has no visible
counter or convenient frame log. Slowdown cause and location remain unconfirmed.
The separate combat slowdown record is PERF-001; do not assume the same cause.

Candidate: F8 toggles a swapchain-only counter and asynchronous per-render CSV.
Count render intervals and screen-scene submissions separately, excluding small
offscreen shadow tasks. The observer never writes simulation memory. Disk writes
run on a separate thread; an 8192-entry bounded queue counts overflow rather than
blocking rendering. Four rotating 16 MiB files bound each session's storage.
Local preview defaults can be enabled through performance.ini next to video.ini.
Tests must start muted and use copied profiles/saves. No slowdown fix claimed.


Initial build caught a misspelled configuration field, corrected before replay.
The first enabled replay failed before gameplay with 0xc0000409 in NVIDIA's
nvwgf2umx.dll (Windows Application events 1000/1001, retained crash dump).
The large glyph rectangle batch is a candidate trigger. The next candidate
limits clear calls to sixteen rectangles and keeps non-Windows renderer builds
behind a no-op diagnostics adapter. Failed run remains preserved; no delivery.


The bounded rectangle batches pass subsequent Original and Custom 360/VSync
replays. The initial driver failure did not recur in these checks; the exact
driver-internal failure is not diagnosed. The counter is Windows-only; other
renderer builds receive a no-op adapter rather than Windows dependencies.

Validation: three muted 4,500-VI modern-route runs (Original diagnostics on,
Custom 360/VSync on, Custom 360/VSync off) preserve exactly the same guest RDRAM,
renderer snapshot and save as the prior clean fixture. CSV frame numbers and
timestamps are monotonic, queue drops are zero, and Custom records intermediate
output frames rather than merely counting game submissions. The disabled run
writes no frame log. A screenshot verifies counter text and placement. F8 uses
foreground game-window ownership and rising-edge detection; physical-key/live
fullscreen verification remains for owner testing. Automated tests never take
desktop focus. Rotation/error paths were reviewed, not disk-exhaustion tested.

FPS measures swapchain render-hook cadence, not physical monitor scanout. GAME
counts screen-scene submissions, not every guest simulation tick; 64x64 shadow
tasks are excluded. MS is the last half-second's mean render interval; MAX is
its worst interval. Logging records each raw interval and the latest scene/VI
counters. Pausing, minimizing, loading and diagnostics toggling can introduce
gaps; these must be distinguished from gameplay stalls. GPU utilization and a
precise slowdown cause are not inferred from these counters alone.

Delivery uses the same preview profile and saves in a new immutable package.
The preview defaults to diagnostics enabled through `performance.ini`, with
F8 toggling the counter and recording for the current game session. CSV files
are under `performance` beside `video.ini`; a desktop **JFG - Performance Logs**
shortcut opens that directory. Stop the game to finish the capture, then share
the CSV files with the same session prefix. Four rotating 16 MiB segments retain
bounded recent history per session; old sessions are retained until removed by
the owner. Files contain timing/counter data, not game memory, ROMs or saves.
The observation tool has some rendering cost; compare with F8 off when needed.

Private evidence: `fps-logging-qualification-v2/result.json` and per-mode CSV,
frame captures, stdout/stderr; initial failed run and build receipts retained.
This adds observability and does not claim to fix the newly reported slowdown.


Implementation commit: `930c57517f31f624d2a05527cdcc1b5264ff4c72`.
Machine-local package: `C:/JFG-builds/high-refresh-diagnostics-preview-20261012`.
The existing preview shortcut now targets this package with the same profile;
the new Performance Logs shortcut opens that profile's `performance` folder.
All fourteen manifest entries and isolated launcher package resolution passed.
Runtime SHA-256: `9fc3233e51b0436f2675362bf9c803a81ee0a94a5a43cd1d9ee68612e2caa0f4`.
Old package and shortcut backup remain available; no public release was made.

The Original run recorded 3,218 render rows and Custom recorded 16,132, with
2,056 scene submissions in each. Custom diagnostics-on/off took 76.829/76.812
seconds in this capped replay; this does not establish overhead at unlimited
FPS, different hardware or long sessions. [Aggregate evidence](../../../evidence/frame-diagnostics.json)
links the observations to the qualified runtime. Implementation:
[counter and bounded writer](../../../src/renderer/frame_diagnostics.hpp),
[scene counters](../../../include/jfg/renderer/frame_diagnostics_state.hpp).
