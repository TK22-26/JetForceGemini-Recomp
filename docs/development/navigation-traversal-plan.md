# Measured walking, jumping and crawling navigation

Research and proposed validation plan, 2026-10-03. SS Anubis is the owner's
first planned test of mandatory box-to-box traversal. This document does not
claim that jumping, crawling, their dimensions, or SS Anubis are implemented
or validated.

## Recommended architecture

Use layered walkable surfaces plus directed action connections. Floors,
box tops and platforms retain separate identities and heights even where
their X/Z footprints overlap. A* can select a sequence of walking, jump-up,
jump-across, drop, crouch/crawl, stand-up and door actions. Execution needs
position, velocity, support surface and movement mode, not only XYZ position.

Recast/Detour is a concrete C++ option for surface generation and queries.
Its off-mesh connections represent explicit transitions between surfaces;
they do not establish that Juno can perform the transition. Unreal's navigation
link system demonstrates the same separation between path connectivity and
custom traversal behavior. Recast is zlib-licensed; dependency adoption would
require preserving its notice.

- [Recast overview](https://recastnav.com/)
- [Detour off-mesh connections](https://recastnav.com/structdtOffMeshConnection.html)
- [Unreal navigation links](https://dev.epicgames.com/documentation/en-us/unreal-engine/overview-of-how-to-modify-the-navigation-mesh-in-unreal-engine)

Plan jumps with motion primitives validated against the game's physics:
standing jump, running jump, controlled drop and any separately verified dive.
A primitive records its starting movement state, input sequence, predicted arc
and acceptable landing region/state. A search over those actions can account
for momentum and chain jumps. Kinodynamic planning explicitly models velocity
and acceleration constraints. Motion-primitive research provides an established
way to reuse dynamically feasible trajectories.

The CMU extreme-locomotion paper is useful for its composition of runs/jumps and
momentum-aware planning. Its reported implementation does not solve collision
avoidance or robustness, so it is a design reference, not a ready game controller.
A full robot joint/torque model is unnecessary for Juno's game-controlled motion.

- [LaValle: kinodynamic planning](https://lavalle.pl/planning/node719.html)
- [Dellin and Srinivasa: A Framework for Extreme Locomotion Planning](https://publications.ri.cmu.edu/storage/publications/pub_files/2012/5/icra2012-primitives.pdf)
- [Sakcak et al.: Sampling-based optimal kinodynamic planning with motion primitives](https://arxiv.org/abs/1809.02399)

## Measurements required before adding traversal edges

In this game, Y is vertical and X/Z span the ground plane. Report all heights
relative to the supporting floor/box top, accounting for the player-origin
offset. The current 20-unit radius, floor +4..80 standing body, 24-unit step
allowance and 45-degree slope cutoff are routing assumptions, not established
Juno collision dimensions.

| Profile | Measurements | Acceptance evidence |
| --- | --- | --- |
| Walking/running | standing collision height, lateral dimensions, origin-to-floor offset, maximum step up/down, slope limit, acceleration, braking and turn response | successful and blocked steps/slopes at measured heights; unchanged game physics |
| Jumping | takeoff vertical velocity, vertical acceleration, apex rise, horizontal range at several approach speeds, air-control response, body sweep and landing speed | actual supported landings on measured surfaces, including the box side, overhead and landing-edge collision checks |
| Crawling | actual collision height/width/length through the stance transition, minimum tunnel height/width, crawl speed and step limits, stand-up headroom | repeatable crawl-only passage and refusal to stand where the standing body does not fit |

A maximum jump apex is not a maximum reachable box height. A valid jump must
arrive over a sufficiently large supported region while descending, avoid the
box's side and overhead geometry, and land with controllable horizontal speed.
Check ascent, descent and collision for the full character envelope; do not
test only a point or only the arc's endpoints. Test both traversal directions:
a safe drop does not imply a feasible jump back up.

Crawl requires a separate movement profile; switching a label or shrinking the
drawn player marker is insufficient. Do not allow stand-up until the standing
envelope fits. If the native controller changes dimensions during transitions,
the planner/executor must account for those intermediate dimensions too.

Recast exposes distinct height, radius, step/climb and slope parameters.
Its small-region filter can remove box tops, so preserve useful landing islands.
Automatic generic jump/drop link generation is only a starting point: it still
requires movement-specific dimensions and executable traversal behavior.

- [Recast configuration and small-region filtering](https://recastnav.com/structrcConfig.html)
- [Unreal automatic link generation and trajectory sampling](https://dev.epicgames.com/documentation/en-us/unreal-engine/automatic-navigation-link-generation)

## Data and execution design

1. Export validated actor-local collision geometry transformed into world space,
   or query actual support/collision tests. An actor AABB is useful for broad
   rejection but its upper face is not proof of a solid, flat landing surface.
   Destructible or moving boxes invalidate their navigation edges when changed.
2. Identify and signature-check player movement mode, grounded/support state,
   velocity and actual collision dimensions. Cross-check code-derived fields
   against observed motion rather than assigning meanings from offsets alone.
3. Record per native movement update for calibration. The normal live map's
   every-six-updates sampling is too coarse for precise takeoff/landing timing.
   Record inputs, XYZ, velocity, support/stance and contact outcomes together.
4. Fit or reproduce the game's discrete jump model. A ballistic parabola may be
   an initial approximation; verify gravity changes, input hold effects, air
   steering and animation-driven transitions before trusting predictions.
5. Sample takeoff regions and landing patches; simulate candidate inputs with
   swept collision checks. Search the action graph using travel time and
   clearance/reliability costs. Retain stance, surface and relevant momentum
   in the state so paths on different stories or with different arrival speeds
   are not incorrectly merged.
6. Execute approach -> align/run-up -> jump -> airborne correction -> confirm
   landing. Confirm support on the intended patch, not merely similar height.
   Replan from the actual landing state; cap retries instead of repeatedly
   jumping into the same obstacle.

For SS Anubis, validate one measured floor-to-box jump first, then a two-box
chain and a box-to-exit route. Visualize takeoff region, arc, body clearance,
landing region and action mode in the existing map. Add a floor slice or side
view for overlapping stories. Validate crawl-only passages independently before
combining jump/crawl actions into level progression.

The owner permits copied-save tests and visible native runs. Preserve normal
and navigation saves, retain failed trials, keep audio muted, and run all
calibration/build/replay work through the existing production guard. Current
approval for finishing speed work does not establish that any proposed traversal
capability already works.

## Speed measurement

The owner's current target is an average stick magnitude around 70-75 out of
80 during normal travel, including steering pauses. Report a time-weighted
average together with distance progressed per second and route completion:
large inputs while oscillating or pushing a wall are not successful fast travel.
Report scripted door/cutscene waits separately and also retain whole-trip time.
Jump setup, crawl sections and landing stabilization need their own speed
profiles; do not force a sprint target onto those actions.
