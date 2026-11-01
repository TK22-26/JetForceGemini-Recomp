# Regional differences

## Leaving Walkway: departure music

| ROM / platform | Observation | Evidence limit |
|---|---|---|
| NTSC / physical N64 | Music is absent when leaving Walkway | Owner rechecked this exact departure; other proposed routes were not individually rechecked |
| PAL / original ROM in EmuHawk | Music is present | Owner confirmed the PAL session after loading Juno in Walkway; not a PAL hardware test |
| Japanese version | Unknown | Not checked |

Recorded 2026-10-31. The owner corrected an earlier mistaken request to restore this music in the
US build. The evidence confirms a regional behavior difference for the reviewed departure; the
underlying code/asset cause remains unknown. Do not list the NTSC absence as a confirmed native bug.

The US Walkway music override was removed from source on November 1. Scoped native normal/skip
replays restore original selection with no Walkway override events; fresh owner listening is not
claimed. Older preview packages still contain the insertion. Sekhmet and the Goldwood Vela route
remain unverified individually.

[Music investigation](../development/issues/flight-transition-missing-music.md) retains the correction
and earlier attempts. [PAL/JP metadata preparation](../development/issues/regional-rom-support.md)
now reconstructs both ROMs and their overlays exactly. Playable regional support remains open;
the recomp currently accepts only its supported US ROM profile. Private ROMs, copied saves and emulator state are not repository assets.
