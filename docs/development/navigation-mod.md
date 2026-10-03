# Navigation mod prototype

This optional single-player mod keeps health at the current character's full
capacity, clears ordinary squad enemies as they load or spawn, and exports the
loaded stage's geometry, exits, and player position. It uses the supported US
ROM and a locally built game executable. It is off for ordinary launches.

In the launcher, select **Navigation mod**, then **Launch game**.
The first mod launch copies your existing campaign into
%LOCALAPPDATA%\JFGRecomp\profiles\navigation-mod. Later mod launches continue
that copy. The normal profile is not written by mod runs. Controller settings
are shared through the launcher's Controllers button.

Click **Live map** to reopen the live window. Use **Open exports** inside that
window to open its files. Each launch gets its own export folder.
The mod exports data from your own ROM on your PC; these files are not included
in the repository or support ZIP.

## What is implemented

- Health is restored before and after player updates; the game's damage
  immunity timer is kept active. Capacity comes from that character's upgrades.
- Enemies belonging to ordinary enemy squads have health set to zero, leaving
  their normal death processing active. Later spawns are checked too.
- The game's Tribal classification is excluded, including friendly squad
  variants. Clearing starts only after a player has entered normal gameplay.
  It is suspended in other game modes, during animation/player cutscene cameras,
  and while the game disables player controls. Animated cutscene actors are excluded.
- Stage changes invalidate the prior map. Mesh generation and level identifiers
  must match live state before a consumer uses them.
- The prototype does not steer the player yet. Bosses and special scripted
  encounters still need individual testing; universal campaign completion and
  every squad gate are not established.

## Export format

Both files are schema 1 JSON, replaced atomically after writing a temporary file.
The mesh is written once per room load. Live state is refreshed every six game
updates. Coordinates are world coordinates, with Y up.

mesh.json contains level, generation, blocks, vertices, and triangles.
Each triangle has vertex indices v, the original batch flags, a block index,
and its collision-plane normal. Material flags are retained rather than treated
as proven walkability rules.

live.json contains level, generation, timestamp_ms (UTC Unix milliseconds),
update, mesh_ready, clearing_active, player, exits, markers, npcs, actors, and mod counters.
first_clear_level and first_clear_update record where automatic clearing began. Player state includes
position, yaw (raw game angle), and health (fixed point; divide by 256).
Exit state includes a position, plane normal and plane_d, raw radius,
destination_code, condition_code, and directional value.

Destination and condition codes are raw game fields. A destination code is not
always a direct level number. A visible exit is not proof that its gate is open.
Geometry and exits are the groundwork for navigation, not a validated navmesh:
doors, moving platforms, jumps, height clearance, and scripted requirements need
additional handling before automatic walking can be trusted.

Consumers should reject snapshots without a player, mesh_ready false, mismatched
level/generation, or a timestamp older than five seconds. A future navigator
must also wait for clearing_active before supplying movement. A process that closes
or hangs leaves a stale timestamp.

## Live map window

With Navigation mod checked, Launch also opens a separate top-down map window.
Use **Live map** to reopen the latest session, the mouse wheel to zoom, drag to
pan, and **Fit room** to reset the view. Cyan marks the player; the arrow shows
movement direction, not camera facing. Yellow dots mark exits. Squares mark
items: orange for weapons, purple for keys, green for other items, and gray for
opened chests. Labels identify verified chest rewards. Unknown special rewards
retain their numeric content code. Scenery named ForestCrate is excluded because
its name does not establish that it contains an item.

Blue diamonds mark dialogue NPCs; white diamonds mark living Tribals.
Labels describe verified character categories, rather than claiming an exact
proper name or an available reward. NPCs have a separate count from item markers.

The optional npcs array records address, position, kind, label, object_id,
behavior, and squad_type (-1 for dialogue NPCs). Dialogue behaviour 90 and the
original Tribal squad classification select these actors. Ordinary enemies,
scenery, cutscene actors, dead Tribals, and invalid object pointers are excluded.
Classification does not establish rescue status, interaction range, quest
completion, or whether an NPC still has a reward.

Markers refresh from currently loaded actors. Collected loose pickups disappear
when the game removes their actor. The prototype has not catalogued every item
or key variant, and does not predict spawns in unloaded rooms.

The map fills upward-facing collision surfaces and colors them using a fixed
room-wide height scale. Y is vertical in this game; X/Z form the flat map.
Walls and downward-facing ceilings are excluded from the filled surface view.
Surface colors do not imply walkability or connectivity.

- **Player floor** (default) follows the highest surface under the player's
  feet when the player is within eight world units of it. While airborne it
  holds the last height; this is a geometry-based estimate, not a game contact
  flag. When no support has been established, it starts at the player's height.
- **Height slice** lets you inspect a fixed Y elevation. Reduce **Slice width**
  to separate closely stacked floors. Ramps are clipped in 3D before projection,
  so the part passing through the selected height range remains visible.
- **All heights** shows the entire upward-surface set with its height colors.
  Upper surfaces can cover lower ones; use a slice to inspect beneath bridges.
- **Other levels** shows faint context and hollow markers outside the slice.
  Arrows and numbers give their direction and vertical distance from the slice
  center. These are exported marker positions: floating pickups and exit-volume
  centers may sit above their floor. Turn it off to hide that context. The player remains visible, with an
  above/below label when outside the slice; trail segments are height-clipped.

Nearby floors within one slice still overlap in X/Z. No edges are inferred
between them, and gaps at a slice boundary are not necessarily impassable walls.
Moving platforms, clearance, slope limits, jumps, and progression conditions
remain unvalidated. This is a geometry viewer, not a proven walkable map.

The window switches to a saved-map indicator after exports stop. An old room is
discarded during transitions until matching live state and geometry are ready.
For standalone viewing: `JFG-Launcher.exe --map-view "C:\path\to\maps\run"`.

## Inspect an export

Python's standard library is sufficient. Substitute a real run directory:

    python scripts/navigation_map.py "C:\path\to\maps\run"
    python scripts/navigation_map.py "C:\path\to\maps\run" --allow-stale --obj "C:\path\map.obj" --svg "C:\path\map.svg"

Use --allow-stale only to inspect a saved capture after play ends. The OBJ opens
in a 3D editor. The SVG is a top-down browser preview with player and exit markers;
overlapping floors remain visible and are not collapsed into a walkable route.

For direct native launches, set JFG_NAVIGATION_MOD=1 and JFG_MOD_OUTPUT to a new
local directory, and pass separate --save and --controller-pak paths.
The launcher manages these paths automatically.

## Validation

Synthetic tests cover disabled behavior, health capacity, friendly exclusions,
multiplayer exclusion, later enemy health initialization, transitions, native
word ordering, memory bounds, and malformed geometry. Launcher tests cover save
isolation, preserving mod progress, shared controller mappings, and unique export
sessions. Map-reader tests reject stale, mismatched, and malformed snapshots.

Real-ROM replay evidence is kept locally under ignored tools/private paths.
See [the validation notes](navigation-mod-validation.md) for the scenes and
limitations validated.
