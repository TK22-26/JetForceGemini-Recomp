# Phase 8 / M4 interactive-build acceptance contract

Phase 8 is complete only when the recompiled game runs continuously through a
single user-facing process: a user supplies a supported ROM, reaches the real
title menu, starts a new game, controls the first gameplay scene with audible
output, saves, exits, relaunches, and resumes that save.

The machine-readable contract is
[`config/phase8-acceptance.json`](../../config/phase8-acceptance.json). The
contract is `complete`, and the tracked completion summary passes the pinned
validator. This is the interactive substrate for the Phase 9 vertical slice,
not evidence that the complete slice itself has passed.

## Required proof

1. The real generated CPU corpus advances beyond the Phase 6 three-retrace
   checkpoint without substituting captured state or scripted game logic.
2. Live graphics tasks from that execution are submitted to RT64 and presented
   continuously. Replaying the Phase 7 captures is not sufficient.
3. Timestamped controller input drives the game's `osCont*` callbacks at the
   recorded sampling boundaries. Disconnect and reconnect are exercised.
4. Recorded input navigates the real title menu and reaches a frame where the
   player character responds in the first gameplay scene.
5. Real audio tasks are decoded to PCM and the host audio device consumes at
   least 60 seconds without an underrun, overrun, or unsupported command.
6. The game's required save/accessory operations reach project-owned persistent
   storage. A fresh profile saves, the process exits, a new process reloads the
   save, and the resumed checkpoint matches the independent oracle.
7. ROM selection/validation and configuration persistence are part of the same
   user-facing executable.
8. Three independent deterministic replays reach all four required scenarios
   with identical approved event and state hashes and zero unsupported runtime
   boundaries.

## Evidence boundary

ROM data, RDRAM, input bodies, save bodies, PCM, screenshots, emulator states,
and detailed traces remain ignored local artifacts. A future
`evidence/phase8-completion.json` may contain only public-safe aggregate counts,
durations, hashes, gate booleans, producer provenance, and dependency pins.

The contract validator is run with:

```text
python scripts/validate_phase8_acceptance.py
```

## Current keyboard bindings

- `W`, `A`, `S`, `D`: analog movement
- `Space` (or `Z`): jump / N64 A
- `Shift`: sprint by applying full analog-stick magnitude while moving
- `X`: N64 B; `C`: N64 Z; `Enter`: Start
- `Q`, `E`: L/R; `I`, `J`, `K`, `L`: C buttons
- Arrow keys: D-pad; `Escape`: exit
