# Controller query initialization: bounded causal proof, 2026-09-24

The native `osContInit` interception reports one connected controller but does
not reproduce the guest's controller-library initialization state. The original
US initializer at `0x80097950` sets the byte at `0x80105341` to four at guest
PC `0x80097AB0`. The query builder at `0x8009336C` reads that byte and emits one
eight-byte status query per channel before an end marker. Native interception
in `src/boot/native_boot.cpp` bypasses these writes.

In the sealed focus capture for completed updates 566–569, native's byte is
zero and oracle's is four. Native's query buffer at `0x80105030` starts with an
end marker; the oracle's has channel responses. These device-state differences
are outside the semantic fields previously reported equal. Equal semantic
hashes did not imply identical controller-library state.

`scripts/phase9_controller_query_probe.c` links the existing private generated
query builder and runs it on copies of the update-567 snapshots. The source
snapshots are not modified. The executable was built with WSL clang at `-O0`.

Observed output, exit code zero:

```
native: captured_limit=0 generated_query_channels=0
oracle: captured_limit=4 generated_query_channels=4
native-counterfactual-limit-four: captured_limit=0 generated_query_channels=4
```

The counterfactual changes only the copied channel-limit byte. This proves
that omitted initialization changes the actual generated query structure.
It does not yet prove that repairing it resolves the update-568 mismatch,
SI timing, initial Pak equivalence, or whole-route parity.

## Reproduction

Run from the repository directory under WSL; all private paths are local:

```sh
root=tools/results/phase4/semantic-audit-current-v3/normalized-phase8-hash-v1
pair=tools/private/autonomy/attempts/input-focus-931b2ccd29eb545895fe62fa/0001/pair
clang -std=c11 -O0 -I "$root/include" -I "$root" \
  scripts/phase9_controller_query_probe.c \
  "$root/baseline/fn_000_1494_recomp.c" -lm \
  -o tools/private/controller-query-proof-20260924a/probe
tools/private/controller-query-proof-20260924a/probe \
  "$pair/native/focus-update-567.rdram" \
  "$pair/oracle/focus-update-567.rdram"
```

## Repair boundary

Do not apply just the channel-limit write as a complete fix. Native raw SI DMA
currently preserves CIC challenge responses while leaving ordinary controller
commands to the high-level input path. The query routine uses raw SI; enabling
its four channels also requires correct status responses and guest-visible
completion behavior. The existing oracle SI trace has three query write/read
pairs at poll 574 with returned channel status bytes. The repair must preserve
the original initialization side effects and provide those protocol semantics,
then pass a short replay comparing query buffers, channel status, delivered
input and completed updates. Freeze the existing baseline binary and original
captures for that experiment.

No production behavior was changed by this diagnostic. Persistent goal remains
paused; this is proven headway from the bounded investigation, not completion
of the autonomous system.

## Bounded repair attempt: stopped at timer dependency

An opt-in candidate (`JFG_PHASE9_CONTROLLER_GUEST_INIT=1`) executes the
original initializer and handles status/reset PIF query packets. The packet
tests passed with the observed four-channel request shape, disconnected
channels, and atomic rejection of unsupported/malformed requests. The Windows
native target built successfully. Default behavior is unchanged; the native
replay objective records whether this probe flag was enabled.

The first 1,800-retrace probe exited before any completed update:

```
category: hle
guest_target: 0x8009b0d0
operation: osSetTimer
disposition: fail-closed-trap
```

Artifacts are under `tools/private/controller-guest-init-replay-20260924a`.
The replay wrapper subsequently rejected the empty update stream; the earlier
native stdout trap identifies the actual blocker. No gameplay improvement or
comparison advance was established. The native process has exited.

Work stopped at this dependency per the user's explicit instruction. Executing
the original initialization requires validated timer/message delivery support
before this candidate can be evaluated. Do not bypass the timer or enable this
candidate by default. The persistent goal remains paused.

## Timer implementation and bounded verification (2026-09-24)

Following explicit authorization to implement the dependency, native now has
an independently authored Count-based timer service, `include/jfg/boot/timers.hpp`.
`osSetTimer` decodes the O32 64-bit arguments and initializes guest timer
storage; expiry posts through the existing nonblocking guest queue and wakes
receivers. `osStopTimer` cancels registration. Countdown, interval fallback,
periodic reload, replacement, queue-full notification loss, deadline ordering,
and 64-bit delays have ROM-free tests. Deadlines are serviced at dispatch
boundaries and between deterministic VI events, not by skipping the wait.

Validation:

- WSL clang strict-warning timer tests passed in both guest-memory layouts.
- GCC AddressSanitizer + UndefinedBehaviorSanitizer timer tests passed.
  WSL clang's sanitizer runtime libraries were missing; GCC supplied the
  sanitizer check without installing or changing the toolchain.
- Existing thread-scheduler tests passed.
- Windows Release native build and `jfg.timers` CTest passed.
- Two opt-in native probes each reached 1,800 retraces, 863 completed updates,
  and 866 controller polls, exiting zero in approximately three seconds.
- At completed updates 566, 567, 568, and 569, the controller-channel byte is
  now four and all 64 bytes at `0x80105030` equal the sealed oracle capture.
  The old native capture had zero channels and an empty query.
- Both new runs have identical completed-update and poll trace files.
- A probe-disabled smoke run also exited zero at 1,800 retraces (896 polls),
  saved under `tools/private/controller-timers-default-20260924a`. This is
  a smoke check, not a claim of byte-for-byte baseline equivalence.

Private artifacts: `tools/private/controller-guest-init-timers-20260924a`
and `tools/private/controller-guest-init-timers-20260924b`. Executable SHA-256:
`6629bcfe372594e5cba31e6f64ee43453d4bf6c9a4d801e3ee66b54532d1c49e`.
Completed-update trace SHA-256:
`a950e9bc52074a7cd911bfba2bf19d9b434bab4ee44963f84f8ff3a7db12e8b3`.
Poll trace SHA-256:
`9ef43d31316eb8811659277bad8349904ac250d18ee1342f8585344b37f2346a`.

**Acceptance boundary:** the existing completed-update comparator still finds
the first gameplay-state mismatch at update 568. Repairing controller init
does not remove that mismatch. The wrapper correctly reports `acceptance=false`:
this bounded probe does not finish the recorded route or qualify initial-save
equivalence. Keep the initializer opt-in. The persistent goal remains paused;
no whole-game parity or autonomous-harness completion is claimed.

The HLE owns private timer-list bookkeeping in runtime side state, not an
emulated libultra linked list. Exact OS-internal memory parity, periodic timer
oracle qualification, and snapshot serialization of pending timers remain
explicit limitations (see `src/boot/PROVENANCE.md`). This is not a claim of
cycle-accurate N64 timing. Next investigation is the remaining update-568
state transition, not another blind long route search.
