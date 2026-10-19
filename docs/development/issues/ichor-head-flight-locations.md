# NATIVE-003: Verify Ichor's detached-head flight locations

- Status: **bounded EmuHawk/recomp comparison completed; no out-of-bounds flight observed; broader parity remains unconfirmed**.
- Target: **1.3**.
- Severity: compatibility concern under investigation; no confirmed gameplay defect.
- Reported: 2026-10-18 by the owner following the Vela/Ichor boss tests.
- Affected build/profile: owner observed the 1.2.1 boss-test session; exact runtime, input profile, difficulty and head-phase timestamps have not yet been isolated. No 1.3 reproduction or native comparison is claimed.

## Report and reproduction

After Vela destroys Ichor's body, observe the detached head's flying positions
through several complete attack/flight cycles. The owner suspects those positions
may be off, explicitly describing this as a hunch rather than a confirmed bug.
They request comparison with EmuHawk or an equivalent original-game reference.

The owner recalls an earlier Mizar fix involving flight outside the arena and
asks that this be considered as a possible related case. That historical fix
and any shared code must be located and checked before asserting a connection.
The first limited source/commit-message search did not establish one.

## Evidence and current limits

The owner accepted Vela, Juno and Lupus controls in the 1.2.1 preview. That
acceptance does not validate boss AI, path targets or detached-head flight bounds.
The existing 1.3 Ichor movement/rendering fixtures reach the intact boss and
exercise player movement/aim/fire; they have not yet established the body-destroyed
phase. Their clean timing and audio results are not native flight-position proof.

The original North American game and a retained BizHawk 2.11.1/EmuHawk installation
are available privately. Prior native observation methodology and artifact
identities are recorded in the [issue #18 handoff](../issue18-native-controls-handoff-2026-10-17.md).
Reuse the qualified ROM identity and isolated saves/configuration, while keeping
this boss comparison separate from that handoff's input conclusions.

## Hypotheses, not findings

- Native authored head paths could legitimately appear unusual.
- Actor/world coordinates or flight-target selection could differ in the port.
- Camera placement, projection, interpolation or native blur could make correct
  world positions appear displaced.
- A shared path/coordinate remedy from the recalled Mizar fix might be relevant;
  no shared cause has been demonstrated.

## Required comparison

1. Locate the historical Mizar out-of-bounds remedy and identify its actual scope.
2. Reach the same body-destroyed Ichor phase in isolated original-ROM and recomp
   runs. Preserve the transition into that phase; do not infer it from intact-boss
   controls fixtures. Record ROM/runtime, save/checkpoint, difficulty and inputs.
3. Observe head world position, flight destination/state, player position and arena
   bounds over multiple cycles, including both idle and moving-player cases.
   Align by boss state and native game ticks; wall time/output FPS are insufficient.
4. Compare original world trajectories and destinations before interpreting
   screen-space differences. Review camera/interpolation separately at Original
   and high-refresh settings if world coordinates agree.
5. Only make a gameplay change after a reproducible divergence is established.
   Preserve native difficulty, attack timing, hitboxes and legitimate flight bounds.

## Attempt log

| Date | Action | Result / next step |
|---|---|---|
| 2026-10-18 | Owner report recorded and added to the 1.3 backlog | Unconfirmed compatibility check; no fix, release claim or native position comparison yet |
| 2026-10-18 | Limited source/docs and Mizar commit-message search | No matching historical flight-bound fix identified; broaden the retained-history review |

## Resolution and lessons

Cause and remedy: **not established**. Original-game parity, live confirmation and
release verification remain open. A visually unusual boss path is not enough to
justify changing native behavior. Keep simulation coordinates separate from
presentation/camera artifacts, and do not generalize a different boss's fix.

Related: [1.3 session backlog](1.2.1-session-1.3-followup.md),
[Vela rendering/blur](vela-rescue-cutscene-stutter-resolution.md),
[1.2.1 boss-controls fix](github-ichor-boss-controls.md).
No ROM, generated game code, emulator savestate or personal save is committed.

## 2026-10-18 original-game comparison

The isolated US-ROM EmuHawk 2.11.1 reference and the recomp now both reach the
actual detached-head phase (4) as Vela (playerGirl). A controlled fixture supplies
body-part damage and protects player health to reach that phase; the game performs
the destruction transitions. It does not write head damage, flight coordinates,
destinations, AI phase, random state or timing. This is not an unassisted fight.

The original SlugBossMover routine's common random destination branch chooses
X in [-764, 626], Y in [79, 375] and Z in [-239, 1150]. Its separate player-dependent
attack branch must be considered before treating these as universal arena limits.

The original reference records 6,927 head-phase frame observations and 84 distinct
destinations. Its head actor origin spans approximately X [-730, 622],
Y [83, 370], Z [-236, 1145]. The neutral-player recomp records 789 head-phase
samples and 60 distinct destinations, with origin approximately X [-746, 583],
Y [89, 374], Z [-236, 1096]. All sampled destinations remain within the native
common-branch bounds. Native screenshots also show the head behind arena pillars;
that appearance alone is not evidence of a port defect.

A second recomp run with moving/turning Vela records 782 head-phase samples and 61 distinct destinations. All its sampled targets remain in those native bounds. Observed player position ranges: {'min': [-269.995, 176, 1958], 'max': [269.995, 176, 1958]}. These are measured samples, not an assertion that every random trajectory was covered.

Private evidence: ichor-head-flight/head-flight-comparison-v3.json,
head-flight-comparison-moving.json, original-head-phase-v2/session/head-flight.tsv,
and the corresponding runtime/ROM/save hashes. The original save import was
verified byte-for-byte after the required Mupen word layout conversion.

Informative setup failures are retained: an initial original save-layout attempt
used the wrong FlashRAM offset; a first damage fixture did not reach the head;
a port observer initially selected the parent instead of the owned game child.
The next observer incorrectly rejected the port's relocated overlay state
0x09502250 as outside RDRAM. Reading the verified overlay mapping fixed capture.
These failures do not establish gameplay defects.

No gameplay remedy was made. Different random streams, timing/input sequences
and observation rates prevent exact trajectory parity claims. Actor origins do
not establish the entire visible head mesh's collision bounds. Screen-space
presentation at Original/high refresh and a full unaided fight remain useful
follow-ups if the owner sees a specific discrepancy. The recalled historical
Mizar flight fix has not been located in retained history; no shared cause is
established. Keep this item checked within the measured scope, not labelled
fixed or released.
