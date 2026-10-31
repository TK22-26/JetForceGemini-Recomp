# ROM-REGIONS: PAL and Japanese ROM support

- Status: owner-requested separate future work; no implementation begun.
- Severity: compatibility limitation, not a newly reproduced US build regression.
- Reported/updated: 2026-10-31 UTC.
- Affected: current US-ROM recompilation/bootstrap support contract, including the current develop review builds.

## Request and evidence

The owner requests support for PAL and Japanese releases separately from the
folder reorganization. Existing supported US ROM recognition, generated code
and assets do not establish compatibility with other regional revisions.

The owner loaded the original Europe ROM in EmuHawk, confirmed Juno at
Walkway from an isolated copied save, and heard music when leaving Walkway.
The owner separately reconfirmed that NTSC hardware omits that music. See
[the scoped audio record](flight-transition-missing-music.md#regional-comparison-and-separate-future-rom-support-october-31).
PAL evidence is an emulator listening report; Japanese behavior and PAL
hardware remain unverified. Cross-region acceptance of this copied save is
one observed case, not general save-format equivalence.

## Proposed separate work and validation requirements

Identify exact supported regional ROM hashes/revisions; separate regional
bootstrap/generated-code and asset profiles; preserve region-specific timing,
audio and cutscene behavior; qualify controller/save compatibility and normal
versus skipped transitions per region. Do not apply PAL behavior globally to
the US/NTSC runtime or assume Japanese behavior matches either version.

No regional generator, runtime, distribution or configuration change was made.
No estimate, release target or implementation acceptance is implied. The
existing unsupported US Walkway music override still requires its own removal
and validation. This record does not reopen a shelved investigation or expand
the production guard budget.

## Transferable lesson

Expected behavior needs a named ROM region and revision. A regional difference
can explain contradictory reports without establishing an emulator or recomp
bug. Keep native-hardware observations, emulator observations, assumptions and
future support requests separate.
