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

The US music-insertion candidate is withdrawn as a fidelity fix. It remains in current source/preview
pending a separate removal; this documentation and folder reorganization does not change gameplay.
Sekhmet and the Goldwood Vela route remain unverified individually.

[Music investigation](../development/issues/flight-transition-missing-music.md) retains the correction
and earlier attempts. [PAL/JP support](../development/issues/regional-rom-support.md) is separate future
work: the recomp currently accepts only its supported US ROM profile. The PAL comparison did not add
PAL runtime support. Private ROMs, copied saves and emulator state are not repository assets.
