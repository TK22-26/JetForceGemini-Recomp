# AUDIO-002: Frequent audible interruptions in optimized high-refresh preview

Status: **cause reproduced; native playback remedy verified in bounded tests; local preview and owner listening check pending** (2026-10-16 UTC).
Severity: high; interruptions occur during ordinary walking as well as combat.

The owner reports substantially more stable gameplay and no noticeable FPS drops
in high-refresh-native-collision-20261016, but frequent audible interruptions
described as underruns. The saved session confirms runtime SHA-256
34ce90c9a11bba75a9ae47f3ae3d8a40d635b20357bf8c52391f4bd015a6bff1,
implementation 8f94f148ec367e4a221679a40255f12e6353af07.
Do not equate the audible symptom with a particular buffer counter without
checking the new capture, or treat muted replay counters as listening verification.

Private evidence: route-capture-20261013/owner-sessions/20261016-062617-3fd7bf54efdd4eab861c018a60fcc3c5;
analysis under route-audio-bridge-20261016. Preserve original timestamps and
profile; heavy evidence stays on the private evidence drive.
Related: [prior source-audio crackle](intermittent-music-crackle.md),
[combat cadence](goldwood-combat-slowdown.md), and
[bridge rendering report](tutorial-late-object-jitter.md).

Plan: inspect recorded queue/task timing and capture provenance; compare source
PCM and playback continuity using the same recorded inputs, with optional
collision acceleration disabled as a control. Audit native clock refresh and
audio scheduling before choosing a remedy. These are hypotheses, not findings.
Consult the pinned upstream audio review JFG-UP-024. Keep tests muted and record
audio to private files if required. No fix or audible validation is claimed.

Transferable lesson: smooth game/presentation counters and zero recorded queue
underflows do not establish continuous, correct audio.

Initial log review confirms 217 audio queue underrun episodes, 42 pause-empty / resume recovery pairs, and zero recorded overruns. The synchronous ROM sample provider was enabled. These facts establish host queue starvation; they do not yet identify why production missed playback demand. The owner run is about six minutes and reaches the later bridge room (26), unlike the earlier short combat fixture.

A muted normal-Play replay using the new input file reproduces 91 queue-empty episodes and two full empty-queue recovery pauses. It diverges from the owner path (rooms 21/47 rather than the late room 26), so it is audio-reproduction evidence only. Initial scheduler observations are retained privately; skipped/coalesced VI notifications may reduce synthesis cadence. No remedy is yet verified.

## Informative candidate failure (2026-10-16 UTC)

The first debt-repayment prototype performed zero repayments: the original
countdown is a signed byte, while the probe initially compared the whole
big-endian word with 2. Source assembly confirms lb/sb at 0x80050764 and
0x80050770. The first stress pair (35/67 empty-buffer events, 5/2 recovery
pauses) therefore does not test the proposed remedy and must not be cited as
improvement. The corrected opt-in prototype selects the high byte and
preserves all adjacent bytes. Observation now reports the actual byte value.
Its controlled repeat is pending. A separate first bridge build rejected
MSVC deprecated getenv under warnings-as-errors; it was corrected to the
existing _dupenv_s convention before tests.

## Controlled missed-retrace experiment (2026-10-16 UTC)

A default-off fixture inserted 23 artificial 35 ms scheduler stalls over the
same bounded input replay. The default-off native candidate retains missed
audio countdown pulses and repays them on subsequent retraces; it does not
advance gameplay or change AI/SDL sample clocks. These injected-stall runs
test causality, not ordinary-play performance or audible acceptance.

- audio-stall-v2-off: 21 queue-empty episodes, 5 actual pause/refill recoveries, 0 debt repayments.
- audio-stall-v2-on: 27 queue-empty episodes, 5 actual pause/refill recoveries, 31 debt repayments.

Private evidence: route-audio-bridge-20261016/audio-controlled-v2-analysis.json. The candidate remains experimental, unshipped and requires an unmodified heavier route test plus clock/state review. Muted tests do not establish listening quality.

## Scheduler task-gate investigation (2026-10-16 UTC)

The corrected countdown-only stress pair still had five pause/refill recoveries
in both variants (21 versus 27 empty-queue events). A longer, heavier logged run
had zero underruns, which alone does not establish improvement. Notification
traces show queued audio notifications accumulating. Original __scSchedule only
runs a ready audio task when sc->doAudio is set, normally at the next audio
notification retrace. A second default-off native candidate sets that existing
gate when a verified ready audio task and a free RSP are present, leaving the
original task scheduler, synthesis and sample clocks in control. Four same-binary
injected-stall combinations compare countdown recovery and this task gate;
results remain private in audio-factor-comparison.json. The 35 ms artificial
stall fixture must be removed before any delivery. No audible acceptance claimed.

The same-binary four-way short stress test did not identify a fix: countdown/task-gate combinations off/off, on/off, off/on and on/on had 3/11/7/4 empty-queue events and 3/2/2/3 pause/refill recoveries. The combined candidate decoded more tasks but delivered only 3000 buffers, so extra synthesis alone is insufficient. A submission-return probe initially failed to build because osAiSetNextBuffer is not in the mapped OS table; the corrected observation wraps its ordinary generated dispatch instead. No delivered build was changed by that failed build.

## Buffer rejection and native demand investigation (2026-10-16 UTC)

The corrected submission probe found 9 rejected osAiSetNextBuffer calls in the
two-slot/countdown/ready-task stress run, versus none in its control. The original
manager ignores that return and synthesizes the next buffer, losing rejected
PCM. Hashes at AI submission and later host copy match: no payload overwrite in
these runs. Host delivery occurs roughly 14-16 ms after the AI write.

A bounded four-slot native AI experiment preserves more catch-up PCM, but still
does not fix starvation: queue-only had 14 empty episodes / 2 refill pauses;
queue plus countdown/ready-task had 9 / 2 and one startup rejection. The latter
also synthesized more 552-sample short blocks. Lost retraces are not a sufficient
measure of actual sample demand. Tests retain exactly two slots by default and
verify opt-in four-slot ordering, sample durations, bounds and interrupt behavior.
The next default-off hypothesis replenishes an 85 ms host queue watermark using
the original audio synthesis and frequency, with bounded notifications and a
ready-task gate. No audio candidate is delivered or audibly verified.

Review of the expanded native queue found a boundary condition: admission must check the final queued deadline, not only the active buffer. The correction rejects aggregate Count overflow while retaining all queued buffers. The physical two-slot path remains unchanged; a near-64-bit-limit regression test covers the four-slot case. This was found before delivery.


## Qualified native playback remedy (2026-10-16 UTC)

The demonstrated chain is lost production time from retrace scheduling,
delayed ready audio tasks, catch-up PCM discarded by FIFO rejection, and late
host delivery. Lost notification counts alone and queue expansion alone failed
the controlled test. The combined remedy uses actual queued playback demand,
ready-task execution, bounded four-slot native retention and immediate PCM
delivery. It retains the original synthesizer, sample frequency, game clock and
separate reference timing path. The native queue policy and exact scope are
documented in [implementation and compatibility](../native-audio-playback.md).

The combined private candidate completes 12 forced 35 ms stalls with zero
underruns, rejected submissions or payload mismatches. Its queue range is about
74-133 ms. The clean six-minute/22,000-retrace run also has zero underruns,
overruns, refill pauses, rejected buffers and payload mismatches. The final
360 FPS capture and 17,000-retrace Original reference comparison pass. Exact
binary hashes, the final overflow-boundary correction, regression checks and
remaining game-update gaps are recorded in
[qualification](../../../evidence/high-refresh-audio-bridge.json).

Transferable lesson: count actual audio samples and host playback demand.
A completed synthesis task is not proof that its PCM was accepted or delivered.
Preserve submission outcomes and payload identity when changing scheduling.
Owner listening verification remains pending; these tests were muted.
