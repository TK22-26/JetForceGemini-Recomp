# Drone buried beside a broken hut

Status: open, cause unconfirmed; reported 2026-10-24.

## Symptom and context

In the Skybox and LOD Preview at 120 FPS, the owner found a blue drone with much
of its body below the ground beside broken hut geometry in Goldwood. The owner
suspects it clipped the hut and was pushed underground. This could be an original
game collision issue; no native-hardware comparison establishes that yet.

Severity: potential gameplay/collision defect, with visual-only pose displacement
still an alternative. Actor LOD High was selected in this copied profile, but no
evidence establishes that the LOD change caused this. The LOD override is scoped
to rendering and restores the native model-selection values before returning.

## Evidence and reproduction limits

The owner supplied codex-clipboard-mPEpUV.png, retained privately with the latest
three saved map exports under D:/JFG-private/shot-effects-fix-20261024/buried-drone.
The normal preview had recording disabled, so this is not a full input/RAM capture.
The owner had already left or closed the scene before the request to keep the
drone in view. The latest map export is room 21; inspecting its actors may establish
whether the affected actor survived, but it cannot reconstruct the collision.

Reproduction is not yet deterministic. Record the room, hut destruction and
drone movement if it recurs. Compare the native actor position with its rendered
pose and local collision geometry, then compare Original/High LOD and the original
game if needed. Do not change global collision behavior based on the screenshot.

No remedy has been attempted. The persistent lesson is to distinguish a native
actor pushed below the floor from a presentation transform error before patching.
This issue is separate from the accepted camera-turn actor interpolation fix.

The retained room-21 export contains four live BlueAnt actors. Their world Y values are -20.089, 45.2156, -1.59108 and -1.96. The snapshot alone does not identify which actor is pictured or prove a bad floor placement. A terrain-height comparison is retained privately; render matrices and the collision history were not recorded in that normal preview.

The saved floor mesh puts the first BlueAnt at Y=-20.089 over terrain
Y=-0.341693, about 19.75 units below the surface. Two other floor-standing blue
drones are about 0.96 below their local surface; the player is about 0.012 above.
This supports a native state/collision displacement rather than only a drawn
pose error, but does not establish that this is the pictured actor, the entry
path, persistence over time, or a difference from the original game. No collision
correction is justified without that additional evidence.
