# Navigation mod validation — October 2, 2026

Local Windows testing used the supported US ROM and copies of the recorded
starting saves. ROM-derived data, memory snapshots, video frames, and executable
artifacts remain in ignored private directories.

## Observed results

- A Goldwood input replay with firing removed ended in room 47. With the mod off,
  three ordinary squad enemies were alive. With it on, all three had completed
  removal through the game's normal processing. The friendly guide remained
  alive in both runs.
- Health stayed at the character's full capacity of 8704 fixed-point units.
  Synthetic tests independently exercise restoration from reduced health and
  different upgrade capacities.
- The first automatic kill occurred in room 47. A visible replay recorded zero
  clears throughout the opening sequence and only enabled clearing in gameplay.
- The longer visible replay reached room 21, with
  16 automatic clears. Its current export contains
  3539 vertices, 2342 triangles, and
  5 exit triggers. OBJ and top-down SVG inspection succeeded.
- An independent SS Anubis export decoded 2686 vertices, 1667 triangles, and four
  exits. No memory-range rejections occurred in that short replay.
- The longer trace recorded 2 safely rejected mod read/export
  operations across loading and gameplay; these did not crash the game.

## Owner observations

The owner watched the visible run and confirmed enemies died immediately on
spawn. The recorded movement later diverged and ran the character into a wall.
That run validates mod behavior and export availability, not route following
or reproduction of the original path.

## Limits

This is an optional mod prototype. It does not steer the player or establish
walkable connectivity, door requirements, or the interpretation of every exit
code. Ordinary squad enemies are covered; bosses and special encounters need
individual validation. Tribal squad exclusions have synthetic coverage; the
real replay comparison specifically verified the friendly guide.

Early test-harness attempts failed while taking a screenshot at a poll boundary.
Repeating the same route without that capture completed normally. The visible
run used normal play mode and closed through the game's window event.
These failed attempts remain in the private evidence and guard accounting.

See [setup and schema](navigation-mod.md) for usage and the prerequisites a
future navigator must check.

### Live map and item markers

The launcher has a separate live X/Z geometry window with player trail, exits,
zoom/pan, and item labels. Reader/UI tests cover stale state, room generation
changes, invalid triangle indices, and painting a map. Native marker tests cover
closed/opened chests, invalid pointers, unknown reward codes, and conservative
key classification. Chest rewards follow the supported ROM's reward switch and
jump table; unverified special collectable names are explicitly unidentified.

The owner observed enemies dying on spawn in the visible Goldwood run. Later
input playback diverged and ran into a wall; this is not navigation validation.
Automatic pathfinding and movement remain unimplemented.

A native SS Anubis replay exported 2,686 vertices, 1,667 triangles, four exits,
and five item markers, including the closed shotgun chest. The run retained full
health with zero invalid memory reads. The real exported room was painted in the
separate Windows viewer. This validates that chest and export path; other weapon
rewards and key variants still need manual in-game checks.

### NPC markers, prop correction, and master volume

The updated native Goldwood replay exports its living dialogue guide while all
three ordinary hostiles are cleared. Reading the saved Goldwood room capture
also exports two living Tribals without changing the source memory. The separate
Windows map paints blue NPC and white Tribal diamonds and counts them apart
from pickups. Descriptive categories cover the dialogue-controller object
family; these do not prove exact character names or reward availability.

The scenery prop internally named ForestCrate is excluded from item markers.
A regression test distinguishes that block from confirmed pickups and chests.

Windows and sanitizer tests cover NPC classification, malformed pointers, dead
Tribals, hostile/cutscene/scenery exclusions, all supported Tribal types, and
preserving captured memory. Launcher checks validate NPC data and shared,
persistent audio settings. The SVG reader has NPC/item validation and label
escaping coverage.

Master-volume tests exercise the complete signed 16-bit sample range, exact
100% passthrough, half volume, silence, and live gain ramps. Native PCM captures
contain 10,419,552 bytes of exact silence with saved mute enabled. A second run
starts audible, becomes silent after a live mute change, and resumes audio
after unmuting to 25%. Changes act on final output without changing guest clocks
or audio queue lengths.

### Flat height layers

The Windows live map now fills upward-facing collision surfaces, with a fixed
room-wide height palette, a player-following slice, manual slices, and an
all-height overview. Synthetic geometry checks separate overlapping floors,
exclude downward ceilings and vertical walls, retain ramp cross-sections, and
hold the selected height during a jump until a nearby support surface is found.
The launcher passes 110 checks and the setup harness passes ten checks.

Saved Goldwood and SS Anubis exports render successfully in the Windows map
window, including a manual slice and the all-height overview. Ten offscreen
renders take about 130-170 milliseconds in these local captures. This measures
map drawing, not game frame rate. The native game binary is unchanged here.
Player-floor selection remains a geometry estimate; it has no collision contact
flag. Markers use their exported world positions, so a floating pickup or exit
volume center can be above the selected slice without belonging to another
story. No walkability graph, floor connectivity, or automatic steering is added.


## Progression export and map inspector (2026-10-02)

Native Windows tests and Linux ASan/UBSan tests pass for per-character inventory,
spoken-without-key, reward ownership, unknown/invalid inventory, exact Magnus
encounter matching, chest content/open state, target activation, target/door
group matching and red-key lock state. These readers leave memory unchanged.
Launcher tests cover optional progression, inventory text, unknown ownership
rejection, unsupported traversal rejection, saved-map status and map rendering.
Python tests cover the same export validation and enriched SVG labels.

An offline export from the owner's final room-35 memory capture decoded 15
interaction nodes and character-1 inventory with the red key and weapon mask 5
(pistol and machine gun). ASan/UBSan reported no errors. This used an isolated
memory copy: no running game, audio output or save writes. A rendered WinForms
preview was checked locally. The red-key reward action and dialogue branch were
also established by the prior isolated original-function harness (11 functions).

Target controller observations: +0x08 is a door group, +0x0A is an activation latch,
+0x00 is a recovery timer and +0x06 is the strength limit. Door controller observations:
+0x43 selects the required inventory item by subtracting 2; +0x3E bit 8 is the key
lock; +0x44 is the door group. These are supported-US-ROM facts, not portable
addresses for other game versions. Targets expose actor origin coordinates;
an aiming system must still validate the hitbox and line of sight.

No fresh interactive playthrough or automatic navigation was performed for this
map-only update. Inventory ownership, key-lock clearing and target activation
are not proof of a physically passable door. Unknown routes, dialogue rewards,
weapon restrictions and jump/dive requirements stay unknown.

## NPC reward catalog across the supported ROM (2026-10-02)

This supersedes the single Magnus encounter restriction above. The host reads
numeric dialogue/choice records from the user's validated US ROM at startup;
no dialogue text, ROM control tables or generated game code is checked in.
All 45 selector groups and 19 reachable choice tables parse, producing 29
offer paths (including alternative paths and scene/music choices). Seventeen
of the 19 dispatcher actions are referenced by those tables. Actions 1 and 13
have known effects but no source NPC is invented for them.

An isolated harness compared the host's predicates with unmodified generated
game functions on 192 inventory/quest states: 8,832 comparisons passed. It
covered all 20 nontrivial root predicates, 17 non-audio visibility cases, and all eight payment predicates. Four audio-dependent
music visibility cases stay unknown in the host. Another harness executed all
19 reward handlers for each of three characters (57 cases), checking grants,
consumed items, ownership scope, costs, health refill and character isolation.
Only player lookup, weapon definition/presentation, audio and save notification
dependencies were replaced with explicit offline harness stubs. No live game,
audio device or save file was used.

Synthetic public fixtures cover the second red-key dialogue, nested trades,
payments belonging to a different character, cross-character reward ownership,
multiple service offers, shared quest flags, missing inventory, unknown catalog,
malformed offsets, truncation and cyclic choices. Original-ROM records remain
private validation inputs. The original-function comparisons validate control
semantics, not a full campaign playthrough or every scripted scene effect.

Final checks pass on Windows native and Linux ASan/UBSan builds, 121 launcher
checks, ten setup checks and ten Python map-reader tests. The actual-ROM
startup parser passes and rejects a damaged asset offset. A fresh offline export
of the saved room-35 memory passes map validation and retains all 15 interaction
nodes alongside 45/19 catalog coverage. The WinForms NPC trade inspector was
rendered offscreen and inspected. No fresh interactive campaign run was made.


## Path and jump-assist prototype (2026-10-03)

Windows native and Linux ASan/UBSan tests exercise a two-leg route using an
independent simple movement simulation, route completion, same-command restart
prevention, manual takeover, replay exclusion, suspended gameplay, room changes,
expired heartbeats, malformed commands, a blocked route and one bounded/released
jump attempt. Launcher tests cover shared portals, disconnected stacked floors,
off-map destinations and the command/stop format. The launcher passes 128 checks
and its setup harness passes ten checks. The controls render in the map window.

These are planner/controller tests, not an N64 physics simulation or a successful
live exit/jump demonstration. Camera adaptation, clearance, jump height, airborne
steering and scripted/locked exits still require live validation. No production
guard limits were reset for this prototype; it uses the existing mod allowance.


The saved room-35 geometry initially produced no routes with exact shared-edge
matching. Accounting for collinear split edges and steps up to 24 units produces
two candidate exit approaches (19 and three waypoints); two other exits remain
disconnected and are rejected. Small-step and excessive-step fixtures cover the
added connections. This demonstrates geometry planning, not live traversal.


## Automatic exit exploration (2026-10-03)

The launcher passes 192 checks, including circular A/B/C routes, directed
backtracking to an unexplored frontier, arrival-door deferral, stable exit
identities after actor reallocation, blocked-route memory and progress retries.
Tests cover manual cancellation across loading boundaries, stale/rewound maps,
missing controller acknowledgements, same-room reloads, partially loaded rooms,
one-shot Area Cleared requests and off-by-default history restoration.
Real WinForms controls are exercised against serialized native acknowledgements
and command files, including explicit restart, Stop AI and window close.

Straightening fixtures cover open ground, height mismatches, a vertical wall
and a two-unit gap. The recorded room-35 map still has two candidate routes and
two disconnected exits. The routes reduce from 22/five waypoints (including
doorway crossing) to three/two. This validates geometric planning, not capsule
clearance or actual gate availability. Ten setup checks and ten Python map-reader
checks pass. Windows native and Linux ASan/UBSan tests pass, including prompt
gating, request scope/expiry/replay exclusion and manual-counter preservation.

Muted live trials use independent copies of the navigation-mod saves and verify
that the originals are unchanged. The initial trial moved to an Area Cleared
screen and exposed that generation invalidation precedes the actual room load;
that false same-room confirmation has been fixed and covered by a regression
test. A second trial walked through the room and stopped against rocky geometry,
then refused to repeat its failed routes. It did not validate a safe route
through the entire map. Height data alone does not prove clearance.

The final live trial observed rooms 27, with 0 confirmed
directed connections and 0 Area Cleared acknowledgements. Its last state was:
`Explorer stopped: no reachable unexplored exits remain. Check blocked routes or progress manually.`.
This remains experimental: the initial calibration can move away from the
destination, steering/camera behavior needs further refinement, and parkour,
scripted gates, NPC trades and full campaign progression are not validated.
The production guard remained enabled; the owner-approved 60-minute extension
preserved all prior accounting and investigation identity.


## Entity collision heatmap and routing (2026-10-03)

The native bounds reader passes Windows tests and Linux ASan/UBSan tests in
both guest-byte and native-word layouts. Fixtures cover the accessor signature,
empty/oversized registries, stale and aliased duplicate actors, invalid pointers,
nonfinite/reversed bounds, enabled/disabled participation and safe entity names.
The launcher passes 229 checks, plus ten setup checks and fourteen Python
map/collision tests. New checks cover body width, overhead clearance, stacked
floors, detours with every segment validated, disabled/player models, unknown
registries, malformed JSON data, inspector dimensions, height-band rendering,
thin floor gaps, static walls and low ceilings. An actual WinForms interaction
test plans/starts a route, enables a new blocking model, and verifies a stop
command is emitted. Native code is read-only with respect to collision state.

A fresh muted room-27 capture exports 58 actors and 19 registered model boxes,
including crates, doors, arrows, switches and hut models. The `Hut2` box at the
earlier stuck location spans approximately Y 0..81 and covers that player's
recorded body position. This identifies a plausible missing actor obstruction;
it is bounding-box overlap, not an instrumented exact polygon contact. The
same-room map now draws that footprint and exposes its dimensions on click.
Actual WinForms player-floor and all-height captures were visually inspected.

Recorded-room planning accepts exit 65437 in two waypoints and refuses exit
65516 when no verified clearance is found. The observed planning times were
roughly 35 ms and 850 ms respectively on the development machine. The fresh
muted live trial acknowledges Area Cleared, confirms room 27 -> room 157, and
begins another route. Copied mod saves were used; original saves were hashed
before/after and remained unchanged. The final observed stop and confirmation
counts are retained with the private validation evidence.

This advances the earlier automatic-exploration result: one actual room
transition is now observed. It does not validate every exit, full-stage travel,
an exact player capsule, traversal through hollow model boxes, camera steering,
or jumping/parkour. Original ROM snapshots, captures and the paired native
runtime remain private local artifacts.


## Scrolling and forward exploration regression (2026-10-03)

The updated launcher passes 251 checks plus ten setup checks.
WinForms regression coverage refreshes a 60-row list while its selection is
off-screen, preserves the viewport and selected exit, removes an earlier row,
and verifies that changing rooms resets the selection. Explorer tests cover
entrance exclusion when forward paths fail, preserving the arrival candidate
after manual walking and reopening the map, alternative selection after a
moving obstacle, and releasing input when an active pilot makes no progress.
Live route checks also reject a terrain wall introduced after planning. A map
window test dispatches an automatic route, introduces a blocking door, checks
the stop command and saved failure reason, then verifies a different route is
sent. These are fixture regressions, not a full native playthrough.

Planning against the user's captured room 236 rejects exit 65365 for insufficient
clearance and exit 65367 for disconnected floor geometry. Exit 65307 has a
four-waypoint approach but is the nearby entrance candidate, so the updated
explorer stops instead of using it as a fallback. This establishes the captured
case's selection behavior, not that the two forward exits are impossible in the
original game. The native executable is unchanged for this launcher-only fix.


## Loop routing and proximity-door handling (2026-10-03)

The launcher passes 264 checks plus ten setup checks. New fixtures require a
room-wide detour around a long blocker beyond the local repair radius, with
all emitted segments independently checked. Door tests cover approaching a
dropped collision model, waiting without movement, refusing a partially raised
door, replanning after standing clearance appears, and stopping at a door that
stays down. Raising the door never counts as a confirmed room transition.

The user's captured room 27 contains an enabled Ftechdoor at the forward exit.
The widened search reaches the far side of the room, but the trigger itself is
behind that door. The updated planner returns a 24-waypoint approach around
the loop to the near side of the door, in approximately 2.5 seconds on the
development machine. Every segment passes the original full-geometry clearance
checks; the rendered path was inspected against the user's marked route.
This validates planning and fixture door behavior, not a fresh native traversal
of that complete route. The steering pilot and native executable are unchanged.


## Clearance preference and live door traversal (2026-10-03)

The updated launcher passes 298 checks plus ten setup checks. New regressions
cover wider routes instead of short body-width squeezes, comparing a valid short
route against a safer detour, preserving inner terrain probes when adding margin,
same-exit recovery after stopping/coasting, bounded retries, fresh-state dispatch,
and manual cancellation during planning and scripted-camera waits.
Native Windows tests and Linux ASan/UBSan tests pass, including camera accessor
signatures, pointer bounds in both memory layouts, rotating-camera steering with
inertia, sharp corners and losing the camera. Live observations establish the
US control-camera yaw convention; the door shot binds a cutcamera actor through player control +0x5C0, separate
from the animated and static-camera globals. Input stays released during the shot.

A fresh muted native run followed the room-27 loop around the huts, reached
the forward door sequence, waited for its scripted camera and resumed from a
freshly checked route. It confirmed room 27 -> 236 through exit code 65516,
with a closest observed distance of 8.4 world units to the door actor.
The independently captured input observations stayed neutral during the scripted
camera. Original navigation saves were hashed before and after and remained
unchanged; the trial used private copies and exited cleanly.

Earlier trials exposed false route rejection from inconsistent floor/probe
selection, camera estimation distorted by turning inertia, and stale snapshots
after a longer clearance search. Their failed outcomes remain in the private
evidence. The final run used the corrected checks, camera heading and braking.
This validates the reported forward-door case. It does not establish full-stage
or campaign completion, all camera modes, NPC transactions, exact collision
capsules, narrow-gap traversal, jumping, diving or parkour. ROM-derived traces,
map geometry, captures and the paired native runtime remain private.

### Adaptive speed validation (2026-10-03)

The launcher passes 304 checks plus 10 setup checks. Windows native and Linux ASan/UBSan navigation tests pass. Added checks cover running on an open straight, slowing near endpoints, expired and withdrawn speed permission, unchanged-route heartbeats, legacy commands, narrow floor strips, nearby models and objects on another story. A rotating-camera simulation with inertia runs a three-segment route, slows before its corners and stays within 20 world units of the segments.

A fresh muted native trial observed 10 running samples above 70 stick units and 482 walking samples at or below 40. Maximum observed input was 79.85. Observed room sequence: [27, 4294967295, 236]. The game and map probe exited cleanly; original navigation saves were hash-checked unchanged. The trial used separate copies. The forward-door transition from room 27 into 236 was observed again. This validates adaptive speed in the captured case, not full-campaign routing or every obstacle. Private evidence is retained in adaptive-speed-evidence; ROM-derived traces and packaged runtimes remain private.

### Continuous-speed validation (2026-10-03)

305 launcher checks, 10 setup checks, Windows native tests and Linux ASan/UBSan tests pass. A 30-waypoint path with two right-angle turns and a rotating camera averages 76.9183 stick units including pauses, completes in 326 simulated updates and stays within 12.4881 world units of the path.

A fresh muted native run crossed room 27 into 236 again. Room-27 active navigation averaged 74.93 stick units, including neutral steering samples, versus 26.81 for the previous adaptive controller. Whole-room elapsed time, including door/camera waits, was 37.33 seconds versus 90.35. Input stayed neutral during the scripted cameras. Game and probe exited cleanly, and original navigation saves were hash-checked unchanged. The paired native runtime and traces remain private.

This establishes the requested normal-travel input average in the captured case, not a universal game-speed guarantee. Mandatory jumping, crawl collision dimensions, SS Anubis traversal and whole-campaign routing remain unvalidated; the measurement and implementation plan is recorded in navigation-traversal-plan.md.

The first longer continuous-speed trial reached room 54 after rooms 27 and 236, then exited with native code 4: unresolved-dma-00beb010-80385700-00000290 at guest target 0x8009a710. The speed comparison above stopped after the first door. The original failed result and traces remain preserved; the later crash was subsequently diagnosed and corrected below.

### Room 54 sound-queue crash (2026-10-03)

The native exit at 0x8009A710 was a missing indirect osSyncPrintf output callback.
The unresolved-dma suffix identified the last PI transfer, not a proven DMA
failure. Restoring the callback exposed a repeatable hang at VI 9561: the
200-entry sound pool had filled, dropping the periodic event at VI 9555, and
the sound player looped on NONE events with zero delay after its queue drained.
The recorded drop counter advances from 210 to 211 at the lost periodic post.

The host supports the missing output callback after checking its loaded
instruction identity and argument-home range. A separate recovery qualifies
the US sound player, an empty queue, the original NONE result, prior overflow
and a valid interval. It delivers one periodic event with that positive interval;
the original callback resumes scheduling on its next turn. Queue links, event
order, count, overflow count and high-water mark are unchanged. The unused
event payload is cleared. Other queues and malformed states remain untouched.
Private progress includes counters for the output callback and clock recoveries.
Temporary event-by-event diagnostic instrumentation was removed.

Windows Release regression tests pass in both guest-memory layouts. Coverage
includes callback ABI and stack bounds, periodic recovery after overflow,
unchanged queue bytes, preserving normal events, rejecting another queue/output,
invalid player/code/interval/free-list states and idempotent rejection.
The existing continuous-running navigation tests also pass.

The exact recorded failing input was replayed with copied saves, first without presentation and then with the native game window rendering normally. Both exited with code 0, reached room 54 and VI 13980, and required exactly one clock recovery. The rendered run presented 2205 more frames and decoded 2205 more audio tasks after recovery; no warning callback was needed. Both runs were muted and original navigation saves were hash-checked unchanged. Private evidence is retained under room54-hang-evidence. The initial rejected combination of interactive and probe CLI options is retained separately and is not counted as a successful trial.

This fixes the observed dispatch crash and subsequent empty-queue hang. It does not eliminate sound-pool overload or recover sound events already dropped by the guest. The source of the event burst and any audible effect remain unvalidated. Jumping, crawling, SS Anubis traversal and campaign completion remain separate work. ROM-derived replays and the paired local runtime remain private.


### SS Anubis box route and shotgun (2026-10-04)

The refreshed launcher passes 353 checks and 12 setup checks. Windows Release
native navigation tests pass, including stopping-point jump steering, movement
state identity, chest activation geometry in both memory layouts, precise
terminal movement, fixed A-button input, cancellation, stale commands and room
changes. UI checks cover waiting for gameplay without a JIT dialog and cancelling
before dispatch.

Two automatic native platform trials completed the five-jump staircase. The
shared launcher chest runner then completed a fresh NORMAL slot-2 trial: standing
jump calibration, five supported landings, collision-checked chest approach,
normal A interaction and shotgun inventory verification (weapon mask 5 to 13).
Audio was muted and original normal-profile saves were hash-checked unchanged.
A prior shared-runner attempt reached the chest but failed its facing check after
a reverse braking correction; neutral final braking corrected that case.
Evidence remains private under box-jump-evidence/precision-chest-shared-2.

This validates that specific Normal-controls shotgun route. It does not establish
universal chest access, Expert-controls execution, crawl height, arbitrary
multi-storey traversal or full-stage completion.

### Door access decoding and trigger lanes (2026-10-04)

Windows Release native navigation tests pass in both guest-memory layouts.
The launcher passes 421 checks and 12 setup checks. New coverage includes
character-scoped yellow-key ownership, enemy/target opener latches, actual
door-indicator links, character exclusions, alternate exit conditions,
unsupported instruction identity, read-only decoding, sloping doorway lanes,
small elevated triggers, solid obstruction rejection, and stable progress
history while a door animates.

The room-47 capture identifies the proximity curtain at Exit 1, the yellow-key
requirement at Exit 5, and the enemy-clear door shared by the overlapping
Exits 3 and 6. In that capture condition 6 is active, condition 7 is inactive,
and the door retains one registered pending enemy group. The counter is not
an individual enemy count, and the mod does not force the door latch open.
Exit destinations remain raw until an actual transition is observed.

Exit 4's old route could end before its plane or aim beside a sloping wall.
The revised route searches laterally for body clearance and a supported
endpoint inside the actual trigger volume, beyond its required plane.
The final doorway segment may use the body envelope where the extra comfort
margin does not fit; the preceding route retains normal margins. A recorded
enemy-door geometry test also finds a body-clear passage after its collision
is simulated open; this is not a live enemy-gate unlock test.

A muted native trial crossed the tutorial exit into room 47, then used the
production explorer to cross Exit 4 back into room 92. Game and observer exited
with code 0. The trials used separate save copies and preserved their inputs.
An earlier run entered room 122, opened the Fish Food chest, and returned to 47.
Its subsequent direct route trial stopped on a clearance check before reaching
Exit 4. Another longer run timed out at the chest; a curtain trial stopped
during tutorial dialogue before reaching the curtain. Those failures remain
recorded and are not counted as full-run passes. Autonomous campaign completion,
universal chest reliability, and live passage through every decoded gate remain
unverified.

The inventory preview retains recognized unowned items as dim tiles and omits
unnamed storage bits. Overlapping inactive exit labels no longer obscure the
active map label; all variants remain in the interaction list. ROM-derived
snapshots, captures, and paired executables remain private.

### Hut curtain return route (2026-10-04)

The King's hut (room 48) places its exit trigger in front of the curtain.
The old approach calculation assumed the trigger was beyond the door and
targeted the far side of its closed collision, leaving the explorer stopped.
Door approaches now choose the player's side of the doorway independently
of trigger placement. Clearance observation stays anchored to the original
doorway while its collision moves, so a trigger before a closed curtain
cannot falsely prove passage is clear.

The launcher passes 430 checks and 12 setup checks. Added synthetic coverage
checks both approach sides, opening-radius reach, body clearance, partial
lifts, sideways opening, crossing the real trigger volume and rejection of
a missing key. The recorded room-48 stop now yields a collision-checked
approach instead of the former route failure.

A muted native trial used separate save copies and the production explorer:
tutorial 92 -> Goldwood 47 -> King's hut 48 -> Goldwood 47. From the hut's
actual entry position, it approached the curtain, observed clearance,
continued through the exit and confirmed room 47. Game and observer both
exited with code 0; source save hashes were unchanged. This verifies the
reported hut return. It does not establish full-campaign completion or
resolve the separately documented chest/dialogue interruptions. Private
snapshots, copied saves and native trial evidence remain outside the repo.
