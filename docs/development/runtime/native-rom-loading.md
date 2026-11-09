# Native ROM loading

Ordinary native Play now has two qualified immutable-ROM paths. The checked SDK
adapter completes eligible `osPiStartDma` reads directly from the resident ROM;
unsupported or busy requests retain original SDK/PI execution, where the existing
next-Count-tick bus policy can still apply. Save devices retain their own path.

The SDK adapter checks the original region-bound PI manager and queue layouts,
requires an idle manager/access/event/completion state with no waiting completion
consumer, validates all addresses/ranges and rejects aliasing before mutation.
It writes the original descriptor fields, preserves status, copies the same
native-word-layout payload as the PI model, and enqueues the actual descriptor
pointer. The real game `romCopy` and `osRecvMesg` continue normally. Unsupported
states fall back without partial writes. This preserves the qualified SDK
contract; internal queue positions and PI registers need not match emulated
transfer execution in native elapsed-time mode.

`JFG_DIAGNOSTIC_NATIVE_ROM_API=0` disables the SDK adapter for comparisons.
An explicit `1` requires native elapsed timing and remains suppressed whenever
the inherited ROM policy excludes recorded clocks or instruction observers.
Ordinary support logs report enabled policy and first actual admission. Optional
`native-rom-api-total` rows contain VI/poll, cumulative reads and bytes;
`native-rom-api` rows contain per-update reads/bytes. Neither is a CPU duration.

See [GH-041](../issues/cutscene-skip-completion-time.md) for causal evidence,
regional validation, current identities and pending owner acceptance. The change
removes thousands of emulated transfer/interrupt/thread round trips during the
opening skip, while retaining scene initialization and script effects. Normal
Play's Original FPS setting still uses its existing timing policy; the separate
instruction-timed reference path is what the compatibility comparisons protect.

## Earlier next-tick PI policy and its historical qualification

An explosion in Goldwood creates shockwaves and explosion sprites, including eleven newly loaded texture frames. Full profiling identifies roughly 11 ms inside sprite loading; ROM section reads account for most of that interval. These nested durations overlap. The host already copies ROM bytes synchronously, but native play also waited for the simulated cartridge-bus duration before delivering the normal PI completion interrupt.

Native play now schedules successful immutable-ROM reads for the next Count tick after the copy. All destination/source bounds, byte layout, busy status, interrupt delivery and acknowledgement remain. FlashRAM retains its separate timing and transfer path. This changes loading latency; game simulation still follows elapsed time. Original instruction timing, recorded-clock comparisons and instruction observers retain the original bus model. The decompressor, textures and gameplay behavior code are unchanged.

JFG_DIAGNOSTIC_NATIVE_ROM_COMPLETION=0 selects the original bus delay for private comparisons. An explicit value of 1 requires native elapsed-time mode. Ordinary Play enables the policy; input replay and optional function profiling can observe it. This is a runtime policy, not a new user-facing video setting.

When gameplay logging is enabled, rom-dma records contain VI, input poll, completed setup call count, copied bytes, reference bus Count ticks, scheduled Count ticks, and native call count for the update interval. Transfers outside measured updates are not attributed to those updates. Counters do not represent extra CPU work or imply that every tick was spent blocked.

Boundary tests cover byte-identical ROM reads with both policies, asynchronous completion/acknowledgement, invalid length and Count overflow, reference timing and unchanged FlashRAM timing. Runtime qualification and remaining limitations are tracked in [PERF-001](../issues/goldwood-combat-slowdown.md). The integrated executable passes the retained 17,000-retrace Original reference and the recorded-clock RAM/save/instruction/interpolation comparison, including explicit opt-in suppression during replay. Both final native combat windows remain at two VIs per update. The six-minute default 120 replay and the 360 replay have zero audio under/overruns, rejected buffers or payload mismatches. [Qualification](../../../evidence/high-refresh-native-rom.json) retains all observations and limits; local delivery and owner live acceptance are separate steps.

The observed explosion performs 27 ROM reads totaling 4,576 bytes. The reference bus model schedules 44,915 Count ticks (about 0.96 ms total); native completion schedules 27 ticks. The wall-time benefit includes avoiding the associated waiting/waking path and, when close to a retrace boundary, avoiding the extra update interval. Do not claim that all of the roughly 11 ms profiled loading time was cartridge-bus duration. Alternating ordinary explosion roots measured 48.161/36.815 ms in controls and 33.198/33.974 ms with native completion. One control retained two-VI cadence, so this is loading headroom rather than a universal no-dip guarantee.

The longer default run retains a 631.54 ms death/reload interval, a 67.115 ms interval containing 40.72 ms graphics submission (39.60 ms full synchronization), and a 49.96 ms cold-overlay load. The renderer stall has no ROM reads. Its internal cause remains open. The replay stays in Goldwood after the death restart, so it does not qualify the owner's exact late-cave route.

Local delivery is complete. Both desktop shortcuts select the qualified native-ROM package and preserve their profiles/arguments. [Package and delivery receipt](../../../evidence/high-refresh-native-rom.json). Owner live acceptance remains pending.
