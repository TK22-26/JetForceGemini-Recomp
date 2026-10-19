# PERF-006: Controller settings reads can block a game update

- Status: cause captured; background-reader remedy implemented and verified in focused tests and normal Play routes; unreleased 1.3.
- Observed build: private 1.3 source-seeded blur candidate, base 34853fd, runtime 0916946dc1758b5094227a35e9e1fe0034052bec34ae2a791cae2d5f42f5ecaf.
- Severity: intermittent performance hitch; storage latency can delay input/game updates.

## Cause and evidence

The game thread synchronously reopened up to twelve controller, modern-control and
keyboard/mouse configuration files every 250 ms. A captured update at VI 14612 took
66.220 ms; its nested configuration stage took 40.682 ms and input stage 40.714 ms.
Those nested spans overlap and must not be added. The storage-read stage accounts
for the dominant measured delay in that update.

That initial route used the diagnostic probe with elapsed-clock timing, not normal
Play's full optimization/audio defaults. Its eight audio underruns therefore do
not establish a shipped-game regression. This correction supersedes that inference;
the original evidence remains retained.

Private artifacts: goldwood-exit-1.3-20261017/vela-composite,
long-route-hitch-timeline.json, play-route-review.json and play-live-settings.
No personal settings, saves or generated game code are included here.

## Remedy

AsyncConfigFiles reads a bounded initial snapshot before the first input sample,
then refreshes it on one background thread. The game thread acquires immutable
snapshots and runs the existing parsers and input-reset rules without filesystem I/O.
A slow read does not hold the snapshot lock. A confirmed missing modern-controls
file disables modern controls as before; an unreadable/invalid/empty file preserves
the active configuration. Windows sharing permits the launcher's atomic replace.

Startup still reads synchronously because settings are needed before input starts.
Shutdown joins the reader. Two independent 250 ms polls mean a live change may
take approximately 500 ms plus the worker's read time to appear. This removes
the measured gameplay I/O path; it does not promise zero host scheduling delays.

## Verification and limits

- Focused tests: bounded/empty files, immutable snapshots, live edits, deletion,
  Windows sharing errors and a deliberately blocked worker read. Accessing the
  previous snapshot remains responsive during the blocked read.
- Normal Play live test: enabled/disabled/restored profiles, invalid contents and
  deletion/restoration. Six observed windows matched the expected input state;
  zero audio underruns and overruns.
- Two normal Play 15,600-VI routes reached ten native exits, the Ichor introduction
  and active moving/aiming/firing boss input. Both had zero audio underruns.
  The synchronous control had 2,215 boss intervals, all two VI; the candidate had
  2,209, all two VI. Boss wall-time maxima were 35.675 and 35.210 ms respectively.
  This clean control did not reproduce the earlier 40 ms file stall, so it is not
  a statistical claim of a general FPS speedup.
- Two approximately 43 ms intervals in room 119 persist in both routes. Their
  VI deltas remain two; separate transition/effect attribution remains open.
- Candidate runtime e48650e7f8229409e933b8287a9d1ef87ee75fcc7c87398561c7fe7e12c4ee68
  also contained a private rendering candidate. These runs establish the stated
  settings and timing scope, not full renderer or campaign acceptance.

## Compatibility lesson

File polling belongs off the timing-critical input path even when configuration
files are small. Preserve live-update semantics and failure distinctions instead
of treating a temporary sharing violation as deletion. Probe timing/audio results
must not be represented as normal Play qualification unless their defaults match.

Related: [1.3 backlog](1.2.1-session-1.3-followup.md),
[Vela rendering investigation](vela-rescue-cutscene-stutter-resolution.md).

## v1.3.0 source availability

The documented change is included in tag v1.3.0 (launcher/source
02be6fa9a4c50f4056f778c5148ca8ac70b0e92b; clean runtime
665596482a7395593e85dbe73f1bd4b016d183d9). See the
[combined release qualification](../releases-1.3.0-qualification.md) for owner
acceptance, source CI, package and publication evidence. Earlier failed attempts
and the scene/device/seed limits above remain part of this record; inclusion
does not turn an unverified broader report into a confirmed resolution.
