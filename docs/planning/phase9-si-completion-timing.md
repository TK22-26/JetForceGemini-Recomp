# SI completion timing investigation — 2026-09-24

## Findings

The update-568 mismatch is not an isolated generated gameplay defect. With
the guest-controller-init candidate enabled, native reaches front mode 24 at
update 572 and BizHawk at update 568, both at controller poll 575. The next
84 offset-paired semantic states match, ending at the captured oracle stream
boundary. This is diagnostic resynchronization, not parity acceptance.

A bounded startup test now identifies an actual guest-visible queue-result
difference, not just a difference between update counters:

| Observation | Native | BizHawk |
|---|---|---|
| Six status-query blocking receives during update 14 | Resume on native VIs 77 through 82, one per VI | All six calls complete during emulator frame 105 / consumed VI 76 |
| Following nonblocking SI receive, after 14 completed updates | Returns -1 at native VI 82, poll count 17 | V0 is 0 at guest return PC 0x80043168, frame 105, poll count 19 |
| Startup nonblocking receives before first update | Two empty returns, poll count 3 | Success at poll counts 3 and 4 |

The native SI queue is `0x800fb090`. Its delivery code services at most one
pending completion in `service_vi_frame`, including raw SI transfers used by
the original status query. At update 14 the six waits demonstrably advance
six virtual VIs. The subsequent native nonblocking check happens before the
next scheduled delivery and returns empty. In the oracle, a register probe
at the actual return instruction independently observes success.

The generated guest instruction at `0x80043168` branches to `0x80043330`
when V0 is nonzero, bypassing the controller-data processing path. Therefore
this difference changes execution; shifting trace indices cannot repair it.
Native recompiled calls do not preserve an informative RA in this capture
(the diagnostic caller column is zero); native attribution uses the known
SI queue, receive mode, and execution order, not an invented caller PC.

There is a separate oracle interval from frames 74 to 105 inside update 14.
The status-query blocking receives occur at frame 105, after that interval.
Do not attribute the entire long interval to those six SI waits. Its cause
and the complete startup timing remain unqualified.

## Reproduction and evidence

All jobs use the existing selected-input export and legally supplied US ROM.
No manual gameplay was required. Private artifacts:

- `tools/private/si-cadence-native-20260924a`: native 160-retrace probe,
  update focus 1..16, event window 0..24. `progress.json.timing.tsv` adds
  `si-timing` records: frame, consumed VI, poll count, completed updates,
  event, queue, caller, result. Entry result is the blocking-mode argument;
  delivery/return/resume result is the queue result code.
- `tools/private/si-cadence-oracle-20260924a`: independent 160-frame oracle
  with raw SI transactions and SI queue calls.
- `tools/private/si-cadence-oracle-20260924b`: repeat with SI plus three game
  queue addresses; identical final RDRAM hash to the preceding oracle run.
- `tools/private/si-cadence-oracle-return-20260924a`: existing entry-GPR
  probe at `0x80043168`, focus 1..16. All 19 recorded receives return zero;
  final RDRAM hash again matches the other oracle probes.
- `tools/private/si-cadence-native-regression-20260924a`: instrumented native
  1,800-retrace run. Completed-update and poll trace files are byte-identical
  to `controller-guest-init-timers-20260924a`; final hash remains
  `f8e1913af973ca00623d042479757a04052337d91f947aa9c515bd697c660dcf`.

Windows Release build and `git diff --check` passed. The only runtime change
in this investigation is focused read-only SI logging; no queue result,
latency, scheduling order, or input data was changed.

## Proper repair boundary

Replace VI-gated SI delivery with independently scheduled device completion,
including transfer ordering, busy state, guest notification, and thread
wakeup. Validate command-write/read phases and pending-event ownership so
one transfer cannot generate duplicate or stale completion messages.

Do not immediately deliver all messages, force receive success, add a
game-specific update offset, or choose a delay solely to match this route.
The SDK describes controller read duration on a millisecond scale, not a
video-frame dependency; it does not supply a precise universal DMA deadline:
[Nintendo SI device programming manual](https://jrra.zone/n64/doc/pro-man/pro26/26-01.htm).
The present dispatch-count clock is not hardware cycle accounting. Qualifying
SI deadlines and their interaction with that clock is still required before
accepting a timing implementation. No full-parity claim is warranted and the
persistent autonomous goal remains paused.

## Count-clock qualification follow-up

`--si-clock-trace` now explicitly enables a sidecar `si-clock.tsv` alongside
`--si-trace`. It observes the core's `CP0 REG9` at raw DMA entry/return,
SI status acknowledgement writes, and the game receive return at `0x80043168`.
It does not alter registers or input. Native `si-timing` records now append
the virtual Count and include a `read-start` event. Source/runtime digests
remain pinned by the respective replay wrappers.

In the capture around the first post-query receive:

- Oracle DMA return: `0x047a114e`; SI acknowledgement: `0x047a1b56`;
  successful game receive: `0x047a4036`. The observed deltas are 2,568 and
  12,008 Count ticks from DMA return, respectively, all in frame 105.
- Native high-level read start: Count 69,314,148; empty receive:
  Count 69,316,900. Only 2,752 modeled ticks elapse; completion is deferred
  to the following virtual VI regardless of this elapsed Count.

These observations support independent SI deadlines but do not calibrate
one universal delay. Acknowledgement happens in guest interrupt handling,
not at the physical instant DMA completes. The native read-start and oracle
raw-DMA-return hooks are also different boundaries. Do not reinterpret the
ratio as a global CPU-clock correction or use 2,568 as a hardware constant.
Native currently adds 64 ticks per dispatch and whole VI intervals during
service; instruction work between calls is not cycle-accounted.

Artifacts: `si-clock-native-20260924a`, `si-clock-oracle-20260924c`, and the
explicit-option repeat `si-clock-oracle-20260924d`, all under `tools/private`.
The earlier `si-clock-oracle-20260924b` lacks receive observations because
the new hook initially used an unsupported register alias; it is not a
valid receive-clock test. The corrected hook uses the existing register
alias set and requires positive focused receive observations at shutdown.
The original acknowledgement-only `...a` remains limited to DMA/ack timing.

The next implementation must separate device-event scheduling from VI
service and establish an explicit timing contract for guest execution.
Acceptance must include the empty/success receive branch at startup and
after update 14, no lost/duplicate notifications, timer interactions,
repeatability, and the existing state-comparison corpus. Merely shortening
the current frame-based delay is not an accepted fix.

## Deadline-scheduling causal experiment

An explicitly opt-in candidate now uses a single-flight SI deadline instead
of the VI delivery counter. Enable both `JFG_PHASE9_CONTROLLER_GUEST_INIT=1`
and `JFG_PHASE9_SI_COUNT_PROBE=1`; the replay wrapper rejects the latter alone.
Its recorded profile is `observed-oracle-ack-2568-not-hardware`. No latency
sweep or adjustment to force a particular game state was performed.

The independently authored `SiDeadline` preserves the submitted queue and
message, rejects overlapping transfers, and consumes completion once. The
runtime services it at dispatch boundaries and between VI events alongside
timers, posting normally through the scheduler; it never forces a receive
result. Existing transfer-payload processing is unchanged. This is a bounded
scheduling experiment, not a completed hardware SI/PIF model. In particular,
the measured acknowledgement interval includes software interrupt overhead.

Results with executable SHA-256
`dacfc4dda0141a9af149434e4c811e4b3525efe640c6c38b37f96cb3bf2b0801`:

- `tools/private/si-deadline-candidate-20260924a` and `...b`: two independent
  1,800-retrace runs; 880 completed updates, 889 polls, exit zero. Their
  update and poll traces are byte-identical.
- The six status-query receives resume without advancing consumed VI 66.
  The subsequent receive after completed update 14 returns success, not
  empty. Ordinary queue semantics determine that result.
- All 870 states in the longer saved oracle capture match at the **same
  update indices**, including the previously failing update 568. The bounded
  `--updates 870` comparison passes; the unbounded comparison correctly
  reports the oracle stream ending at 871.
- A fresh 3,000-target native/oracle pair matches updates **1 through 1260**.
  The first difference is update **1261**, actor **11** at `0x801baf80`.
  No other semantic component is flagged in that first differing record.
  Artifacts: `tools/private/si-deadline-native-3000-20260924a` and
  `tools/private/si-deadline-oracle-3000-20260924a`; the former contains
  `oracle-comparison.json`. These are semantic-component comparisons, not
  claims that all RDRAM, device state, or timing matches.
- With the SI probe disabled, the 1,800-retrace update/poll files remain
  byte-identical to the previous controller-init candidate. Artifact:
  `tools/private/si-deadline-disabled-20260924a`.
- Windows Release build and deadline/timer tests pass. GCC ASan/UBSan tests
  pass. Native/oracle replay contract suites pass 25 tests. Tests include
  busy rejection, no early completion, exactly-once delivery, rearming,
  overflow rejection and required initialization flags.

This experiment supplies causal evidence that VI-gated SI scheduling caused
the old same-update divergence: the unchanged game functions now match much
farther without offset pairing. It does not prove the chosen latency is
correct on hardware or explain the next actor difference. Keep the profile
disabled by default. Next work is to diagnose actor 11 at update 1261 and
qualify the independent event/guest-clock model; do not blindly imitate an
oracle arithmetic difference (the project already has an unresolved CPU
rounding qualification case).
