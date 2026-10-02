# Boot state correction for health and ammunition

The native cartridge-entry runner omitted retained CIC-6105 boot state. The
original game checks consequently removed health while idle and could clear
the equipped weapon's ammunition. The correction initializes the missing
boot state once, before generated game execution.

## Cause and implementation

The generated player update calls the original RAM check at guest address
`0x09C00000`. It reads uncached RDRAM `0xA00002E8`; when the boot residue is
missing, the player update at `0x80032B8C` periodically subtracts `0x40` from
health. A separate check at `0x80033440` expects `osCicId` at `0x80000310` to
identify CIC 6105. A mismatch permits clearing the equipped ammo counter.
Both locations were zero in the preserved live session.

`initialize_6105_handoff` initializes the CIC ID and copies three four-byte
IPL3 residues from the already validated local ROM. The two high-RDRAM words
are consumed by the original startup RAM checks. The existing generated
checks continue to execute. The public adapter contains offsets and device
metadata; the IPL3 bytes remain in the user's ROM. This is a minimal supported
cartridge handoff model, not execution of the complete hardware IPL.

## Verification

The same 3,674-poll recording, initial save and Pak were run against both
binaries, ending at the same stationary player position in the training area.
The route includes 1,500 appended neutral polls. The old build ended with
8,192 raw health and `0/100` pistol ammo; the corrected build retained full
8,704 raw health and `100/100`. Both high-RDRAM startup checks reported success
with the correction. All 66 native tests and a replay containing six additional
Start presses passed. Synthetic tests cover byte order, bounded initialization,
and preservation of unrelated memory without shipping ROM data.

The original live process was left running. Its recording, saves and four
non-atomic memory snapshots were preserved privately. The running process
does not acquire this correction until restarted. Previously saved ammo or
health values are not rewritten by the boot adapter.

## Initial visual investigation

The first Goldwood invasion stutter observation was inconclusive. A paced,
unskipped intro observation reached 9,800 VI retraces without a trap. Of 4,545
presentation gaps, 4,533 spanned two VI retraces; larger gaps also occurred.
The first observation used an actor sampler that only recognizes `animBlue` and captured no matching
actors on this route. The final scene still contained the ship's animated
characters. These observations do not isolate the reported invasion moment or
distinguish its animation cadence from rendering delays.

An earlier paced diagnostic completed in the child but was rejected by the
parent because the optional final actor dump added a console record. That
rejection is retained separately and is not a passing regression result.
The boot correction has not been established as a fix for the visual issue.

## Detailed local gameplay recording

Set `JFG_GAMEPLAY_TRACE` to a writable file path before starting the native
runner to enable the opt-in `jfg-gameplay-trace-v1` timeline. Logging is off by
default. Rows contain decimal elapsed microseconds, an event name, and hexadecimal
integer values. Float guest fields retain their raw IEEE-754 bit patterns.
The trace is buffered, flushed once per second and at controlled exits, and stops
at 256 MiB with a limit marker. A hard crash can lose the final buffered interval.

The events cover controller input, VI ticks, completed guest updates, graphics
preparation/submission/presentation timing, audio queue levels and underruns,
scene state, and changed actor state. Actor sampling covers every type when the actor table contains at most 256
entries, including the ship characters omitted by the first probe. Larger tables
produce an `actor-table-invalid` event and skip actor sampling for that update.
Actor rows include name words, the first 128 actor bytes and the first 32 bytes
of both properties and control data when readable. Unchanged actor snapshots
are omitted. These raw guest snapshots are private diagnostic data and are not
part of the launcher's filtered support ZIP.

The authoritative payload order is at each `gameplay_trace.event` call and in
`trace_gameplay_state` in `src/boot/native_boot.cpp`. Tick/update rows include
VI, input poll, diagnostic update count, frontend mode, level, actor count,
presentation/graphics counters, pending work, dispatch count, and audio status.
Actor rows begin with VI, update, slot, guest address and four name words,
followed by 32 actor words, eight properties words and eight control words.
An invalid guest read is encoded as `ffffffff`.

A paired 2,300-poll replay with tracing disabled/enabled produced identical
final 4 MiB RDRAM, full health and 100/100 ammo. The enabled trace contained
36 actor types and 15,831 changed actor snapshots in about 6.4 MB. Focused
tests passed, including trace size-limit behavior. This checks data coverage
and guest-state preservation; it does not establish zero timing overhead or
identify the reported visual stutter. The subsequent manual recording and
matched invasion replay are described below.

## Invasion presentation correction

The manual recording captured two in-scene presentation gaps of 2.61 and 2.41
seconds while guest updates and audio continued. During these gaps the game
submitted ten distinct color targets: two display buffers plus effects targets.
The native runner incorrectly used an eight-entry retained-snapshot cache as
proof that RT64 still owned a display target. Effects repeatedly evicted both
display-buffer entries, suppressing presentation even though RT64 retained the
rendered framebuffers.

Presentation now queries RT64's frontend framebuffer registry for a resident
color target. The unused retained snapshots and their eviction bookkeeping are
removed; consumed snapshots return to the existing reuse pool after submission
and any requested writeback. This does not replay historical graphics tasks or
raise the cache limit. Opt-in diagnostics record `present-skip` with VI, input
poll, update, selected display address and last submitted color address when the
selected target is unavailable.

Both binaries replayed the same 3,538-poll prefix and pre-recording
save/Pak, including the complete invasion. The old build had
287 presentations over 424
invasion updates; the corrected build had 422 over
424. Maximum in-scene presentation gaps were
2194.536 ms before and
57.500 ms after. The corrected replay had
0 gaps above 100 ms,
0 missing-target events, and no additional audio
underruns during the invasion. Final 4 MiB game memory matched byte for byte.

The renderer test, four focused native tests, and the stationary health/ammo
replay passed. These results cover this recorded scene and presentation
regression; they do not establish campaign-wide rendering correctness or
eliminate loading gaps between scenes. The corrected local runtime is prepared
for visual confirmation. Private logs, game memory, saves and binaries remain
outside the public repository.
