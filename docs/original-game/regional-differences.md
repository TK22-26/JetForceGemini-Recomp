# Regional differences

## Leaving Walkway: departure music

| ROM / platform | Observation | Evidence limit |
|---|---|---|
| NTSC / physical N64 | Music is absent when leaving Walkway | Owner rechecked this exact departure; other proposed routes were not individually rechecked |
| PAL / original ROM in EmuHawk | Music is present | Owner confirmed the PAL session after loading Juno in Walkway; not a PAL hardware test |
| Japanese version | Unknown | Not checked |

Recorded 2026-10-31. The owner corrected an earlier mistaken request to restore this music as US
fidelity. On 2026-11-08 the owner classified #45 as a native NTSC bug and deferred a different
correction to a separate general native-bug-fixes update. The hardware evidence remains scoped
to the reviewed Walkway departure; the underlying code/asset cause remains unknown.
See [N64-003](bugs.md#n64-003-missing-flight-transition-music-on-ntsc-45).

The US Walkway music override was removed from source on November 1. Scoped native normal/skip
replays restore original selection with no Walkway override events; fresh owner listening is not
claimed. Older preview packages still contain the insertion. Sekhmet and the Goldwood Vela route
remain unverified individually.

[Music investigation](../development/issues/flight-transition-missing-music.md) retains the correction
and earlier attempts. [Regional runtime support](../development/issues/regional-rom-support.md)
now covers USA, PAL and JP; supporting a region does not establish its untested music behavior.
Private ROMs, copied saves and emulator state are not repository assets.
