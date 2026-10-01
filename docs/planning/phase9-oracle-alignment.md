# Phase 9 oracle sampling investigation

Status: unresolved; 2026-09-05. This is not an approved parity exception.

The existing schema-1 producers use different clocks. Native boot calls
`write_retrace_semantic_hash` immediately after successful receipt on the queue
registered by `osViSetEvent`, incrementing `state.vi_retraces`. The BizHawk Lua
script calls `write_retrace_hash(emu.framecount())` between emulator frames.
Consequently their equal numeric retraces do not establish equal execution
points. The comparator remains useful for native/native regression testing.

Reinspection of the preserved native and BizHawk semantic-hash smoke streams
under `manual-health-ammo-restart8-20260901-0020` gives:

| Observation | Native consumed VI number | Emulator frame |
|---|---|---|
| Front mode changes to 2 | 34 | 101 |
| Front mode changes to 3 | 992 | 1122 |
| First sample's actor list | Initialized, count 0 | Uninitialized, count 3,398,324,335 |
| Initialized actor-list address | `0x801d6940` | `0x801d86b0` (frame 41) |

The transition offsets differ (67 versus 130), so one constant offset does not
even align these two milestones. Raw actor pointers differ after initialization
as well. Neither finding alone identifies a simulation bug; input/save origins,
sampling points, allocation and scheduling must be compared explicitly.

`JFG_PHASE9_ORACLE_VI_TRACE=1` now enables read-only Lua hooks at the supported
US `osViSetEvent` and `osRecvMesg` entries. They record the configured queue,
interval, and matching receive callers in `checkpoints.tsv`. Entry is explicitly
not consumption: a receive may block or fail. Do not bless the old frame-indexed
stream or adjust offsets to conceal mismatches.

## Verified consumption probe

The diagnostic ran in an isolated copy of BizHawk 2.11.1, including its existing
save/configuration, to avoid changing the ordinary oracle installation. The
300-frame capture identified `0x8004f9e0` as the scheduler receive return site.
Disassembly of the supported US ELF establishes that s4 contains the queue and
s5 the message-output pointer there. VI, RSP and RDP share this queue; counting
every receive would therefore be incorrect.

The opt-in diagnostic now writes `consumed-vi-hashes.jsonl` at that return site,
requiring successful return, the configured queue, and the configured VI message
value. A second 300-frame run exited normally and produced 270 validated records
under ignored `tools/private/phase9-vi-alignment-20260905/consumption-capture`.
The original emulator-frame hash stream is retained separately.

At consumed VI 1 the oracle actor list is zero with count zero, not the earlier
uninitialized garbage. It initializes at consumed VI 12. Front mode becomes 2
at consumed VI 70, versus native VI 34. Thus the corrected observation point
does not remove the startup scheduling/allocation differences. The native VI
counter also needs auditing: its current increment checks successful receive
on the queue and an outstanding delivery, rather than checking message identity.

This probe retained frame-indexed input and copied oracle save state; it does
not claim matching native/oracle initial persistence or input schedules. Next:
bind initial persistence and input indexing, then investigate startup allocation
and scheduling before approving canonical parity.

## Native queue-message defect confirmed

The read-only native `vi-queue-receive` timing diagnostic records the actual
message, configured VI message, delivered count, and whether the receive is
selected as a hash checkpoint (detail columns a through d). It is enabled by
the existing actor-trace option. Before the fix, the 1,794-retrace full-render
`vi-message-audit-20260905` startup replay selected 901 real VI messages (666)
and 893 RSP-completion messages (667). The first wrong selection occurred with
five consumed retraces and six delivered messages: reported checkpoint 6.
Another 892 real VI receives were then not selected. This is a misplaced
sampling/input boundary, not evidence of twice as many VI interrupts.

The runtime now additionally requires that the successfully received message
equals the configured VI message in both immediate and blocking receive paths.
Old state/journal baselines are not automatically approved for this change;
the startup and complete route must be revalidated. No oracle parity claim is
made merely because this counter defect is corrected.

The rebuilt fixed runtime passed `vi-message-fix-20260905`: 1,794 actual VI
checkpoints, zero selected non-VI messages, zero unsupported accesses, and normal
target exit. The 40,452-retrace `vi-message-fix-fullroute-20260905` gameplay
regression completed with zero unsupported accesses. The trace audit found
40,452 selected VI messages and zero selected non-VI messages. Combat counters,
death/retry, player position, two persistence writes and the journal hash match
the previous full-render run. The final semantic record has no actor, player,
RNG, globals or camera differences. Full RDRAM and full-state hashes differ;
the byte comparison includes scheduler queue and stack state at the corrected
stop point, so the old full-state hash is not a golden for the new boundary.

## Input clock and initial flash

`JFG_PHASE9_ORACLE_INPUT_CLOCK=consumed-vi` selects input at the core's input-poll
callback using the consumed-VI counter. The default remains emulator-frame for
older probes. Local Mupen64Plus `N64Input.GetControllerInput` source confirms
that the callback precedes reading axes and buttons. All button values are
explicitly set, including releases; the selected values are recorded per poll.

`prepare_phase9_oracle_flash.py` inserts the native logical flash image into a
SaveRAM template at offset `0x20800`, reversing each four-byte word. Layout and
endianness come from the pinned Mupen64Plus source. The converter rejects wrong
sizes and existing output files and preserves other devices from the template.
It does not claim equivalence of Controller Pak images.

The matched-input oracle completed 1,900 emulator frames / 1,870 consumed VIs.
Front-mode transitions remain at oracle consumed VI 70 and 1,091, versus native
34 and 992. A subsequent 300-frame probe using the normalized input verified
the emulator-visible initial FlashRAM hash as
`0b330cc2d3067ac4d58920f4c1b761997063f14a5d81804e06997dc44c646252`,
identical to the source native flash file. This isolates the remaining startup
scheduling/allocation mismatch from a wrong flash byte order or wrong clock
label. These neutral-input probes do not prove non-neutral gameplay parity.

## First allocation difference

The bounded `mm-alloc` trace (native actor timing; oracle
`JFG_PHASE9_ORACLE_ALLOC_TRACE=1`) records requested size and returned address
through consumed VI 100. In the startup allocation probe, the first ten
`mmAlloc` results match exactly. Allocation 11 differs: oracle requests 3,232
bytes from return site `0x80052dc4`, while native next requests 48 bytes.
Disassembly identifies that site as `runlinkDownloadCode` allocating the
module text/data/BSS block. Oracle also allocates 280 temporary relocation bytes,
then a 2,680-byte module and 88 temporary bytes before the matching 48-byte
allocation. These explain 5,920 bytes of the subsequent heap displacement;
the actor-list offset needs the remaining allocation history accounted for.

This is consistent with native synthetic overlay publication bypassing some
original module allocations, not a differing initial heap base. It is not yet
a complete parity explanation. Cross-runtime raw pointer hashes cannot simply
be approved as equivalent; module lifetime, heap pressure and pointer-bearing
state still need explicit correspondence and tests.

The first oracle allocation capture reached frame 300 but then faulted inside
Mupen64Plus breakpoint removal during Lua-console shutdown. Its trace is useful
diagnostic data, not a successful process result. The script now unregisters
its named callbacks before requesting core exit. The separate
`allocation-clean-exit-capture` reached frame 300, wrote its terminal result,
and its process exited without the earlier exception in stderr. The native
Release rebuild and 25 focused Python tests passed as well.

### Full actor-list offset accounted for

Aligning allocation sizes through actor-list creation gives exact matches
except for three oracle-only persistent module allocations and their temporary
relocation buffers. The persistent sizes, rounded to 16-byte heap alignment,
are 3,232 + 2,688 + 1,616 = 7,536 (`0x1d70`). This exactly equals
`0x801d86b0 - 0x801d6940`. The temporary buffers (280, 88, 8 bytes) are reused
before subsequent allocations. The actor list is allocation 50 natively and
56 in the oracle trace, including these temporary calls.

An experiment clearing an exact synthetic marker at `runlinkDownloadCode` entry
completed startup safely but did not change the early allocation sequence. It
was removed: the normalized direct overlay transfer bypasses that original
loader entry entirely. Preserving guest module heap pressure requires work at
the first direct-publication boundary, with reentrancy and guest-context handling
for the real loader, not merely changing the module table on loader entry.
The VI-counting fix remains in place. Full overlay lifetime parity is still
unproven; this is not an approved pointer-hash exclusion.

### Guest loading restored at direct activation

`ensure_guest_overlay_allocation` now resolves the target's exact ROM/text/data/
BSS identity in the guest module table before executing a normalized overlay
call. Real loaded bases are retained. A missing/synthetic base invokes the
original generated `runlinkDownloadCode` with the matching slot and a separate
CPU context, preserving the pending function arguments. The actual loader
performs persistent and temporary allocations, relocation, PI work and lifetime
updates. Recursive incomplete loads fail closed. Synthetic code publication
then remains responsible for the normalized executable/data address space.

`guest-overlay-load-20260905` completed 1,794 retraces with zero unsupported
accesses. All 183 recorded startup allocations match the oracle exactly in
requested size, order and returned address; the actor-list address is now
`0x801d86b0`. This is materially stronger than masking pointer bytes.

The complete semantic record also matches at both observed front-mode entry
events, selected by the transition itself, not by searching for equal hashes:

| Transition | Native consumed VI | Oracle consumed VI | Shared semantic SHA-256 |
|---|---:|---:|---|
| 0 to 2 | 34 | 70 | `f581a61b4b283d38127bafbd56a9dbc628b6d1fa0b1539397ec875ef1abcb3d0` |
| 2 to 3 | 992 | 1091 | `569f1150e1d074b795a6599f36f0f2968a65be24237abb8645ae8da7407ce4f3` |

These are startup diagnostic checkpoints only. Equal transition state does not
prove equal intervening timing or non-neutral gameplay/recovery parity. The
40,452-retrace `guest-overlay-load-fullroute-20260905` replay completed with zero
unsupported accesses and two persistence writes, but changed the gameplay
outcome (5 enemy kills versus 25, different final player position, 20 versus
21 level-change calls). It is not accepted as a passing route regression.
Correcting guest heap/lifetime behavior changes execution; the full oracle
replay must distinguish corrected behavior from an introduced defect. The
isolated `fullroute-capture` oracle run has been launched to 41,000 emulator
frames with the same normalized input and verified matching initial flash,
using consumed-VI input and state recording. Gameplay parity remains open.
The four existing overlay relocation/runtime/address/module-table CTests pass;
they do not substitute for the ROM-backed lifecycle and gameplay regression.

### Recorded route is not portable through startup loading

The full-route oracle diagnostic was deliberately stopped after a verified menu
divergence, not left to produce misleading gameplay evidence. The recorded A
presses begin at consumed VI 1,029, then repeat at 1,051 and 1,081. Native has
entered front mode 3 by VI 992. Oracle enters it at VI 1,091 and does not poll
input between VI 1,029 and 1,098 while loading. Native consequently enters mode
24 at VI 1,114, whereas oracle never takes that branch on this input sequence.
This is not proof of dropped controller samples in the replay parser.

The existing paced `cold_boot_to_gameplay_probe_route` is now packaged by
`python -m scripts.prepare_phase9_cold_boot_probe` with blank all-FF flash,
copied Pak state and explicit neutral gaps. Explicit gaps prevent the manual
capture launcher's hold-until-next-sample normalization from extending scripted
button pulses. Artifacts live under ignored
`tools/private/phase9-cold-boot-parity-20260905` and are marked non-acceptance.
Native completed 18,000 retraces, reached mode 16, exercised 675 player-control
calls and reported zero unsupported accesses. The paired oracle completed
18,500 emulator frames, reached mode 16 and exited without an exception.
Both take the same startup transition sequence so far; the complete semantic
record matches at the opening-cutscene entry (native VI 4,836 / oracle 4,899).
The mode-24 entry differs only in the recorded actor state and remains under
investigation.

`replay_phase9_capture.ps1 -UntilRetrace` now permits an exact diagnostic stop
within the source recording. A tested stop at 2,086 produced a 4 MiB RDRAM dump
with normal target exit. Oracle `JFG_PHASE9_ORACLE_TRANSITION_DUMPS=1` adds RDRAM
dumps at consumed-VI front-mode transitions for the matching byte-level probe;
this new dump option still needs emulator verification. The comparator now
rejects gaps/reordering and missing actor address/hash fields, even in identical
streams. Thirty focused Python tests pass.

### Paced cold-boot comparison frontier

Both runtimes follow front modes 0, 2, 3, 24, 0, 5, 16 on the paced route.
However, mode-5 and mode-16 entry state does not yet match: RNG, actors and
camera differ. Reaching gameplay is therefore coverage evidence, not parity.

A diagnostic comparison starting at the matching cutscene-entry state removes
consecutive identical records from each stream (without approving that as an
acceptance rule). The first 423 distinct states match exactly. The next records
are native VI 5,682 and oracle VI 5,743. Native has 18 actors and RNG
`0x19ba5fbb`; oracle has 22 actors and RNG `0x86ce3d36`. This is an actor-list
change/rebuild boundary, not necessarily an actor-construction fault: the
counts decrease from the preceding cutscene's 23 actors. Investigate the guest
update/transition boundary and whether the oracle VI samples a partially
completed update before assigning causality or changing simulation behavior.
