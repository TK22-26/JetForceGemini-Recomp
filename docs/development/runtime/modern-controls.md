# Modern controls engineering reference

Current player instructions: [PC controls](../../features/pc-controls.md).
The [issue index](../issues/README.md) owns current defects, attempts and acceptance.

## Original integration and camera model

This section preserves the original integration design. Later multiplayer, Floyd and camera
corrections are described in their [issue records](../issues/README.md) and the
[current controls guide](../../features/pc-controls.md); original single-player restrictions below
are historical, not a claim that v1.4.0 only supports P1.

`include/jfg/runtime/pc_input.hpp` provides mapping, profile parsing, independent
look channels, rate integration and camera math. `window_input_mailbox.hpp`
transfers keys and focus/motion as one snapshot between window and game threads.
Sampling remains at the existing controller/SI boundary. The game retains
weapon handling, collision and special-state movement.

- Manual aim hooks the qualified US routine at `0x8003AABC`, updates yaw/pitch
  within its limits, and restores original raw movement afterward.
- Ground aim states 10/11 receive normalized forward/side movement through the
  existing physics path. Special states retain original guest behavior.
- Modern ground view/facing is coordinated around the original player update
  and the three character physics routines. Normal movement receives normalized
  forward/strafe velocity before the original collision step. Jump/flight momentum,
  swimming, ledge, damage, scripted and other special states retain their native
  movement handlers.
- The normal camera path at `0x8002CF6C` still supplies its desired position
  before native scenery constraints. Modern shoulder view uses that resolved
  position immediately, removing follow-camera drift. Scenery changes that position
  without rotating away from the shared input heading. The ground-aim camera
  retains the same yaw/pitch convention, with pitch limited to the supported
  aiming range. Legacy replay and original-mapping camera behavior is retained.
- Wall contacts retain a small inward clearance. Three lower-body visibility
  rays, spanning the player's width, additionally catch edges missed by the
  head-height camera ray. Possible contacts use the game's own
  `trackNearestIntersection` (`0x80018808`) and re-enter its camera constraint
  helper. This resolves the captured steep tree-edge obstruction.
- In tight spaces, the modern camera smoothly fades the player to a faint
  silhouette instead of leaving an opaque body across the view. The qualified
  opacity routine at `0x80015E3C` runs the original game first, then reduces its
  returned opacity according to distance from the camera to the player's body.
  Stronger original aim/death fades are preserved. The hook is restricted to
  active single-player modern camera control; scenery collision and movement
  are unchanged. Disabling experimental controls disables this fade.
- `pc_camera_visibility.hpp` conservatively filters clear rays against current
  static triangles and registered moving-model bounds. Unknown or invalid
  geometry falls back to the guest query. It avoids unnecessary guest collision
  calls in unobstructed views; it does not replace the game's collision result.

## Historical research and qualification

The [pre-reorganization controls record](https://github.com/TK22-26/JetForceGemini-Recomp/blob/db9ea90b41b9bf14d806ab6aea1aefbddbb80efa/docs/features/pc-controls.md) retains the October research, intermediate builds and test counts. These dated results are not current acceptance. The [native controls comparison](issue18-native-controls-handoff-2026-10-17.md) preserves original-ROM experiments and Normal/Expert distinctions.
