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
update, mesh_ready, clearing_active, player, exits, markers, npcs, progression, actors, and mod counters.
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

## Progression map and interaction inspector

The live window includes an interaction list and details panel. Select an entry
to inspect its world X/Y/Z, action, reward, requirement and current state. It
refreshes with the map, highlights the selected marker with a white ring, and clears selection when the room generation changes.
Orange-red squares show shooting targets; violet squares show doors/switches.
Existing floor slices apply to these markers too. A saved snapshot is labeled
as saved; its ownership and interaction states describe the capture time.

- NPC offers come from the supported US ROM's dialogue control tables, covering
  all 45 dialogue groups and their 19 reachable choice tables. Both red-key
  encounters, trades, rocket-launcher rewards, NPC ship parts, health/ammo
  services and music choices use the same reader. No room/actor whitelist is
  needed to recognize rewards. Select an NPC to see each offer and its conditions.
- Offers distinguish **available**, **blocked**, **owned** and **unknown**. These
  describe dialogue/inventory eligibility, not physical reachability or successful
  interaction. Multiple paths to the same reward remain separate alternatives.
  Spoken-to state is independent from reward ownership. A spent/traded item is
  not permanently marked collected just because an NPC was spoken to.
- Trade requirements retain prerequisites from every nested choice, identify
  consumed items and token costs, and use the active character's inventory.
  Rewards distinguish current-character, any-character and shared ownership
  according to the original conditions. Quest items without verified names
  retain numeric identifiers instead of guessed labels.
- Scene/level transitions appear as separate offers. Their downstream scripted
  effects (including story unlocks/upgrades) are not claimed as direct item grants.
  A dialogue with no direct offer says so; an unavailable catalog stays unknown.
- Chests retain verified weapon contents and opened state. Unknown special
  chest rewards remain unknown. Inventory still shows red-key/machine-gun status;
  individual NPC offers expose the broader inventory and shared quest conditions.
- Repeated-shot targets expose their activation latch, raw strength, recovery
  timer and linked door group. The timer is not a hit count. A door identifier
  is not a required weapon: no machine-gun-only requirement is assumed.
- Doors with the verified red-key condition show key missing, key owned, or
  key lock cleared. These states do not establish that the door is physically
  open or reachable. Other conditions and switch variants remain unknown.

`progression` is an optional schema-1 object in `live.json`, containing
`inventory`, `npc_catalog` coverage and `nodes`. Inventory has `known`, nullable `character`, nullable
`red_key`, and nullable `weapons_mask` (weapon inventory bits 0–14).
Each node contains `address`, world `position`, `kind`, `label`, `action`,
`status`, `requirement`, `requirement_known`, `reward`, `reward_item`,
`reward_weapon`, `required_item`, `required_weapon`, `spoken`, `encounter`,
`dialogue`, `door_id`, `linked_actor`, `raw_state`, `raw_condition`,
`target_health`, `target_max_health`, `reset_ticks`, and `traversal`.
NPC nodes additionally expose `npc_catalog_known` and `offers`. Each offer has
an `id` identifying its dialogue-row/choice path, `kind`, `reward`, `status`,
`scope`, action/item/weapon/flag/destination identifiers, `cost`, `consumed_items`
and `conditions`. Conditions expose their domain (`dialogue_row`, `visibility`,
or `prerequisite`), numeric id, description and `met`/`missing`/`unknown` state.
All conditions in one path must hold; separate offer paths are alternatives.
`owned` means the relevant inventory bit or shared flag is set, not proof of
which encounter supplied it. Music choices deliberately leave audio-dependent
visibility unknown. Scene effects and unloaded NPC coordinates need further
tracing before building a complete campaign dependency graph.

Integer -1 means unknown/not applicable; linked_actor 0 means no confirmed
loaded link. A target can affect multiple doors sharing its door_id;
linked_actor identifies the first loaded match only. Switch links come from
their actual door pointer, not proximity.

Addresses identify actors only within the current loaded snapshot. Consumers
must key them by session, level and generation, discard absent actors, and
must not persist addresses across room loads. No cross-room navigation graph
or stable campaign object identifier is provided yet.

`requirement_known` describes the stated interaction only. Every node currently
exports `traversal: "unknown"`: inventory, target activation, and proximity
must never be promoted into a walkable connection. Automated routing still
needs collision/clearance, jumps, moving platforms, dive exits, and confirmation
of door opening. Export readers support old snapshots without progression.
The mod only reads these progression fields; it never grants keys or weapons.
