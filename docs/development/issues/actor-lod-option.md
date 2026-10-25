# Actor LOD option

Status: behavior owner-verified locally; graphics placement passes UI checks; unreleased.

The owner requested Game > Settings > Actor LOD: Original / High on 2026-10-24 after observing distant drones use reduced-detail models in Projectile Motion Fix Preview at 120 FPS.

## Implementation

Original is the default. High suppresses only the native model-detail offset during objPrintModelObject (US 0x8000CC64), preserving actor+0x3A, the authored model/state variant. The header distance threshold and global detail operand are temporarily overridden and restored before returning from the draw. Opcode pins and model allocation checks reject unsupported layouts. Collision, simulation and visibility culling remain unchanged.

The launcher saves game-settings.ini in the active profile and applies changes to a running game through the same authenticated window path used for live fog changes. Failed saves keep the last accepted selection. A missing or invalid runtime preference uses Original. High can cost more rendering time in crowded scenes; performance equivalence is not assumed.

## Validation

Native tests cover Original, High, variant preservation, nested restoration, complete byte restoration and rejected unsupported instructions/allocations. Configuration tests cover persistence, parsing and invalid values. All 26 Settings UI checks pass, including reopening, failed saves and changing LOD while the game locks storage migration. An initial fixture failure came from an uninitialized test profile path; it was corrected without changing product behavior.

Native instruction pins were compared with the retained exit snapshot (which stores big-endian words). The owner subsequently verified live detail and persistence; no broad performance claim is made.

Related: [camera-turn actor jumps](camera-turn-actor-jumps.md). The LOD option is distinct from the accepted camera continuity fix during model changes.

## Owner review and graphics placement

The owner confirms both live High detail and persistence work in Skybox and LOD
Preview. The owner requested moving this visual preference out of Game Settings.
The controls now belong to Video Settings > Rendering and use that window's
draft/Apply/Cancel flow. Apply sends the choice to the running game without a
restart; Cancel preserves the saved choice. Relocation passes 228 Video Settings UI checks, including draft/Apply/Cancel, persistence, invalid protocol rejection and no restart notice. The storage UI suite also passes.
The accepted rendering behavior is unreleased. No broad performance guarantee
is made for every scene or machine.
