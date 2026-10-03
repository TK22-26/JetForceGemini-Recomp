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
- Experimental steering is available through the Live map controls below. Bosses and special scripted
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
or stable campaign object identifier is exported by the runtime. The launcher
can build a session graph from confirmed transitions as described below.

`requirement_known` describes the stated interaction only. Every node currently
exports `traversal: "unknown"`: inventory, target activation, and proximity
must never be promoted into a walkable connection. Automated routing still
uses conservative registered-model bounds as described below, but still needs
precise character clearance, jumps, moving platforms, dive exits, and door-opening logic. Export readers support old snapshots without progression.
The mod only reads these progression fields; it never grants keys or weapons.


## Experimental exit approach and jump assist

In **Live map**, select an exit in the interaction list, click **Plan exit route**,
inspect the dashed yellow candidate route, then click **Start AI**. **Stop AI**,
Esc, or any manual controller/keyboard input returns control immediately.
AI is off until explicitly started. It uses the existing isolated mod save.

The first version searches connected upward-facing triangles through shared
edges at least 40 world units wide, including collinear split edges and steps
no taller than 24 units. The prototype accepts at most 2,000 floor triangles.
Height is retained: stacked floors and gaps
are never connected by proximity alone. The exit is projected to a nearby floor;
exits without a matching floor or connected surface route require manual control.
Portal width is a conservative filter, not a full player collision/clearance test.
Dynamic doors, explosive barriers and NPC prerequisites are not solved by this
planner. The drawn route is a candidate, not proof that it is traversable.

The pilot starts with two short stick probes to learn movement direction, then
adjusts its stick basis from observed movement as the camera turns. It stops on
blocked calibration, sustained lack of progress, excessive deviation, inactive
gameplay, a room change, replay input, or its 1,800-update run limit. It approaches
the exit floor position; reaching that point does not prove an exit transition.
Map commands expire after 1.5 seconds without a heartbeat. A stopped command
cannot restart through repeated heartbeats; Start AI must issue a new command.

**Experimental jump assist** permits one short A-button pulse after movement
stalls on stable ground. It releases A, monitors movement and limits the attempt.
This is obstacle recovery, not a gap/parkour planner. Precise jumps, tree dives,
moving platforms and scripted campaign requirements remain manual. Expect to intervene
while testing. The latest collision-map validation observed one live room
transition; successful parkour and jumping over the earlier obstacle remain unproved.

`live.json.navigation_ai` reports state, command nonce, active flag, waypoint
index/count and jump attempts. `ai-command.txt` is a bounded, atomically replaced
per-session command containing room/generation, nonce, timestamp and waypoints.
Existing input recording captures the generated stick/buttons for later replay.


## Automatic exploration (experimental)

Start the game with **Navigation mod** enabled. In **Live map**, click
**Explore automatically**. No exit selection is required. **Stop AI**, Escape,
manual game input, or closing the map stops exploration. With the mod enabled,
Escape cancels automation; close the game window when you want to quit.
Jump assist remains optional and off by default.

The explorer prefers untried exits with candidate surface routes. It excludes
the nearby entrance candidate remembered on arrival. Other confirmed directed
connections can lead toward rooms with unexplored exits; returning through the
current entrance requires manual selection. It never assumes that a drop, dive or doorway works in reverse.
Known loops without an unexplored destination are not selected. Repeat-transition
limits stop stale or changing graphs from producing endless circuits.

Room IDs come from the live game. Exit identities combine their position,
normal and raw destination code; actor pointers and generation numbers are
not persistent room/exit identities. A raw destination code is not interpreted
as a room number. The interaction list shows untried, skipped entrance,
confirmed destination, unavailable and blocked states with reasons.

Only observed transitions establish connections. A command must have been
acknowledged and the player must have approached its exit. The destination
must have a different room ID and remain stable in active gameplay for at
least 600 ms. A generation change alone is insufficient: the game invalidates
the map before completing its level change. Same-room reloads remain
unconfirmed. Rewinds, unexpected loads and conflicting destinations stop
the explorer rather than adding speculative links.

The game's **Area Cleared** prompt can be acknowledged automatically once
per pending exit. This is a normal A-button pulse, permitted only while the
supported US ROM's transition-prompt flag (0x800A329C) and pause-mode byte
(0x800FD7BD) both equal one. Its transition update at 0x800468EC checks A/Start
in that state. The host does not edit those game flags or advance NPC dialogue.
The request is tied to room, generation, current manual-input counter, nonce
and a 1.5-second expiry. Manual input and replay exclude acknowledgement.
These state observations were checked against the pinned local decompilation's
`mainChangeLevel`, transition update and `mainGetPauseMode` assembly; the
host implementation is original code.

Blocked routes are not retried on every update. Newly observed red-key,
weapon, NPC ownership/prerequisite or gate-activation facts permit reconsideration;
changing character also changes the attempt context. Repeated ownership
toggles do not generate unlimited retries. This uses currently exported facts,
not a complete campaign dependency solver. Keys, trades, shooting targets,
explosives, precise jumps and dive exits can still require player intervention.

Walking candidates exclude faces steeper than 45 degrees; this is a conservative
prototype limit, not a measured character-specific capability. The planner keeps **Y height**; X/Z are the ground plane. Route straightening
removes triangle-midpoint detours only with continuous floor coverage at the
matching height, a 40-unit floor strip, and static obstruction probes between
4 and 80 units above the floor. Thin gaps, different stories and detected
walls prevent a shortcut. Segments are capped at 600 units and 80 units of
height change. These conservative prototype dimensions are not a verified
character capsule. Registered entity models now supply a separate dynamic
bounds layer, and every emitted segment is checked as described below.
The checks remain conservative approximations of actual character motion.
The pilot still performs its two short initial calibration movements; this
update does not establish straight-line tracking under all camera conditions.

`exploration-history.json` is saved atomically beside the map exports. It
remembers rooms, directed exits, attempts, failures and monotonic progress facts
within that game run. Closing/reopening the map preserves that history but
does not arm movement. Every new game launch uses a new export directory;
history is not shared across saves or game sessions. It stays local. After moving past an obstacle yourself or enabling jump assist,
use **Retry room exits**, then **Explore automatically** to request another attempt.
This explicit action clears local failure blocks while retaining discovered
connections and attempt counts; it never starts movement by itself.

Exploration is bounded to 15 minutes and 128 transitions per explicit start.
Individual routes retain the native pilot's limits. Missing acknowledgements,
stale exports, repeated transitions without progress and exhausted reachable
frontiers stop with a reason. Interrupted controls in the same room require
an explicit restart; a confirmed room load can continue automatically.


## Entity collision bounds and height map (2026-10-03)

Use the paired updated native executable and launcher, enable **Navigation mod**,
and open **Live map**. **Entity collision boxes** is enabled by default. The map
is a flat X/Z view; Y is vertical height. It reads the current entities and the
game's registered collision models, rather than inferring object sizes from
their origins or item labels.

- Filled footprints use the existing room height scale: the fill is the model's
  top height, and the narrow side stripe is its base height. The numeric range
  remains visible on sufficiently large boxes. Out-of-scale heights clamp to
  the legend endpoints; the inspector always shows their numeric heights.
- In **Player floor**, a box is filled when its vertical span intersects the
  prototype standing body range, from floor +4 through floor +80. The terrain
  keeps its independently selectable slice width. **Height slice** clips entity
  visibility using the selected height interval. **All heights** shows every
  model; this can obscure lower floors and is intended for inspection.
- **Other levels** shows out-of-band footprints as dashed outlines. Disabled
  polygon models are also unfilled/dashed and are identified in the inspector.
  A tall entity crossing the selected interval remains visible even if its
  origin is on another floor.
- Click a footprint for its current entity name, position, base/top Y, height,
  width/depth, and polygon-collision state. The selection is discarded on room
  changes; guest actor addresses are not persistent identities.
- **Unknown entity origins** optionally adds cross markers for actors without
  registered model bounds. Their size, solidity and collision coverage remain
  unknown. NPC/item interaction markers continue to display independently.

`live.json.actors` adds a sanitized runtime `name`; `player` includes `address`.
The optional `collision` object has `schema: 1`, `known`, `reason`, and `models`.
Each model contains `address`, `enabled`, and world-coordinate `lower`/`upper`
XYZ bounds. Readers reject duplicate or stale identities, invalid pointers,
nonfinite/reversed bounds and oversized registries. Missing or incomplete
collision data prevents AI routing; older snapshots can still be viewed.

The supported US reader shares the accessor pin and layout observations with
`scripts/phase95_collision.py`: registry count/table at 0x801047E0/0x801047E4,
actor collision-state pointer at +0x5C, lower/upper triples at +0x100/+0x10C,
and polygon participation bit 0 of properties +0x0A (properties pointer +0x4C).
The resident accessor is checked before reading. Local reference assembly for
`hitGetHitModels`, `hitMakePolylist`, `hitGetHeights` and the transformed-bounds
producer corroborates these fields. No reference assembly or game assets are
embedded in the implementation. Names and boxes come from the user's running ROM.

Routing expands active model boxes by a **20-unit horizontal body allowance**
and checks the entire swept segment against its **4-to-80-unit vertical body
range**. The player's own model and disabled models are excluded. The same test
applies to original waypoints, shortcuts and generated detours. An object above
or below that body range does not block the route just because its footprint
overlaps in the top-down view.

Blocked segments use a bounded visibility search around expanded box corners
and nearby floor candidates. Each emitted segment also needs continuous floor
coverage across a 40-unit strip, with up to 24 units of step tolerance, plus
static terrain/headroom probes. Routes remain limited to 256 waypoints, 600-unit
segments, 80 units of segment height change, and the existing 45-degree floor
limit. Clearance searching has a two-second time check and at most 256 local
candidates. No verified route means movement is refused. The launcher rechecks
remaining segments against fresh entity bounds before sending heartbeats; a
new obstruction releases movement and names the blocker. Manual routes require
replanning; automatic exploration first stops, waits for the player to settle, and
replans the same exit within a bounded retry allowance.

These are conservative bounding boxes, not exact polygon collision or decoded
character-specific capsules. A rotated or hollow object can have usable space
inside its box that this planner refuses. Unregistered collision types, player
steering/calibration, dynamic platforms, door-opening requirements and parkour
remain limitations. Body allowance dimensions are prototype values. The map
does not promise safe traversal of an entire stage or campaign.


## Exit selection and live movement checks (2026-10-03)

The interaction list preserves its selected actor and top visible row while
snapshots refresh, including when earlier rows disappear. Selection and scroll
reset when the room changes. Manual **Plan exit route** now uses the same
floor-checked doorway approach as automatic exploration.

**Explore automatically** excludes the entrance candidate observed when the
map first sees gameplay in a room. That candidate is the nearest doorway within
400 world units; it is a heuristic, not a decoded entry trigger. Walking elsewhere
before clicking Explore does not change it. The candidate survives reopening
the map in the same export session. A new session first opened midway through a
room may not know the actual entrance. Manual exit selection remains available.

Other exits are attempted in order, with unknown destinations preferred and a
route required before movement starts. When no forward route passes clearance,
exploration stops and explains why; it does not fall back through the entrance.
A live obstruction releases movement and starts a bounded local replan of the
same exit. Exhausting that allowance records the failure and considers another
forward candidate.
Each update checks the actual player-to-waypoint segment against static terrain
and floor coverage as well as remaining entity bounds. Automatic movement stops
when distance to the waypoint fails to improve for about 1.8 seconds (3.5 seconds
during jump assist), then stops and replans the same exit. These checks reduce wall pushing;
locked gates and parkour still need separate progression/traversal logic.


## Room-wide routes and lifting doors (2026-10-03)

If a locally repaired route fails, the planner searches floor samples across
the entire room. A* edges must pass the existing floor-strip, height, terrain,
headroom and entity-bound checks. Samples include triangle interiors and edges
plus expanded obstacle corners. Spatial buckets limit neighboring candidates;
the fallback has a 16,000-sample limit and a three-second search time check.
Stacked floors retain separate heights, and no unverified edge is emitted.

An exit trigger behind a registered door can now produce a **door approach**
instead of rejecting all navigation. This applies only to a nearby interaction
identified as `pass_door`, with a currently enabled registered collision model.
The approach stops outside the door's expanded bounds on the side opposite the
exit. It never deletes the actor, disables collision, supplies a key, or assumes
an opening requirement has been met.

Automatic exploration walks to that approach, releases movement, and watches
the current door bounds for up to eight seconds. A partially raised door still
blocks the standing body. Once its bounds clear the crossing (or its collision
is disabled/removed), the planner checks a new route through the exit and resumes.
A door that remains closed is recorded with a key/switch/other-requirement
message. Requirements stay unknown unless independently decoded. Manual routes
can also approach a door; continuing them after opening requires replanning.


## Clearance preference, steering and local recovery (2026-10-03)

Route selection now favors space around obstacles as well as distance. Planned
segments use the existing 20-unit body allowance plus 20 units of extra model
clearance. Floor/terrain checks add outer probes eight units beyond the original
body probes, retaining the original probes so a thin obstacle cannot disappear
between them. Planning and live validation use the same walkable-floor filter.

Paths near active, height-overlapping models receive additional travel cost
within 80 and 120 units. A valid short candidate is compared with a room-wide
alternative when it passes close to models. Smoothing may not increase that
cost by cutting back toward an obstacle. These dimensions are prototype world
units, not an exact player capsule or a promise that every narrow passage can
be traversed automatically. The runtime still checks the original smaller body
envelope, leaving room for ordinary tracking error inside the planned margin.
After planning, the launcher loads a fresh snapshot and checks room identity,
update order, manual input, gameplay control and actual-position clearance
before dispatch. A stale starting snapshot is not itself proof the game stopped.

The supported US build reads the control-camera yaw through a signature-checked
accessor and validated camera-array pointer. Native steering uses that heading
instead of learning camera turns from character inertia. It slows using measured
velocity and releases movement briefly at sharp corners. A valid camera heading
also removes the exploratory forward/right calibration walk. Losing a previously
validated camera stops the pilot; manual input never rearms a stopped command.
The camera source observation is tied to JFG-UP-025 in the pinned upstream review;
its axis convention was checked against live movement and camera position.

Automatic exploration retains its chosen exit for up to four local recoveries,
with a 120-second total elapsed allowance for that exit. A recovery sends a stop,
waits for native acknowledgement and fresh stable positions, then replans from
where the player actually stopped. It does not immediately blacklist the exit.
A player that fails to settle within seven seconds stops the attempt. Manual
input, stale data, Stop AI, and room-state changes retain their cancellation rules.

A decoded animated, static or player-bound cutcamera can release input and wait for up to 15 seconds.
When gameplay resumes, the same exit is replanned after settling. Unclassified
pauses still require an explicit restart; any manual input during a scripted
camera cancels continuation. The game continues to own doors, locks and opening
animations. No actor removal, collision disabling, key granting or teleport is
used to cross a door.

The local map export retains bounded route-stop events plus the most recent
stopped snapshot and route for diagnosis. Live snapshots include read-only camera
and steering observations. These local ROM-derived exports remain outside the
public release and the sanitized support ZIP.
