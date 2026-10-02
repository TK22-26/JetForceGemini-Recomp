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
