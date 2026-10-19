# Issue 18 native controls investigation handoff

Prepared 2026-10-17 UTC for continuation of the 1.3 controls work.

**Issue:** [#18 — Issue while holding R for targeting (mouse/kb)](https://github.com/TK22-26/JetForceGemini-Recomp/issues/18).
**Persistent record:** [GH-018](issues/github-held-aim-and-diagonal-movement.md).
**Measurement receipt:** [native controls evidence](../../evidence/github-issue18-native-controls.json).

The original North American game, running in EmuHawk with Juno and the Expert
control preset, supports a **17.41798% aimed diagonal speed advantage** over
aimed forward movement. Its forward and strafe components combine independently.
The published v1.2.0 modern aiming adapter normalizes those components and uses
a lower forward scale. This supports the owner's requested movement
compatibility work for 1.3. Matching the measured native behavior is a
compatibility correction; increasing speed beyond that baseline would be a
separate enhancement.

The second symptom, firing cancelling held aim in the port, remains undiagnosed.
The original game retained aim through pistol fire in both Expert and Normal,
including moving-fire cases. The reporter's actual game executable, profile and
physical bindings are still unknown. No port fix has been implemented or verified.

**Do not post on the issue.** The owner requested a response for review and later
explicitly said, "do not message on the issue page tho". Nothing was posted,
committed, pushed or released. The reply near the end is an unsent draft.

## Owner intent and completed scope

The owner asked for issue review and a draft, questioned whether the additional
speed was native, then required an EmuHawk comparison. They want this addressed
in 1.3 if the emulator supports the report. When the existing investigation was
exhausted, they explicitly approved a parallel test for two hours. The original
investigation was renewed with its guard enabled and all prior charges retained.

Five guarded supporting jobs completed the native comparison. The two-hour
approval was an execution ceiling, not a requirement to keep testing for two
hours. It covered isolated native movement and held-aim/fire measurements,
alongside a separate performance investigation. It did not authorize a runtime
fix, commit, push, release or issue message. Current documentation work records
the result; it does not extend that execution allowance.

## Report and version identities

The report was opened by `jd002065-del` on 2026-10-17 at 21:28:32 UTC. At initial
review it had no comments, support ZIP or attached reproduction video. The
reported environment was Windows 10, NVIDIA 5070 Ti and driver version written
as `6.17.42`; that driver string was not independently validated.

At the beginning of the game with the starting pistol, the reporter holds "R"
to target and fires. They say the first shot always removes the reticle and
exits targeting despite continued aim input. Other weapons were untested. They
also observe faster diagonal movement outside targeting but no comparable
advantage while targeting, and offered to test a keyboard/mouse playthrough.

| Identity | Finding and consequence |
|---|---|
| Reported launcher revision | `c994c75`, matching the `v1.1.0` tag. This does not establish the independently selected game executable. |
| Latest release at review | [v1.2.0](https://github.com/TK22-26/JetForceGemini-Recomp/releases/tag/v1.2.0), published 2026-10-16 at 23:31:30 UTC; source `f56cd94c4bd7583bceee201eb3f229f744216bc1`. |
| Checkout used for review | `63e49a7a71c3a914d2adc1d91fdcf00bef30d38e`, "Document modern dual-stick and mouse controls with screenshots". It predates the release. |
| Source comparison | Read the v1.2.0 tag directly with `git show`; local README and older preview notes are not evidence of the published release's state. |

Still needed for the reported aim failure: actual runtime identity, Modern
Controls versus original Controller Mapping, literal aim/fire bindings,
hold/toggle setting, and whether "R" means a physical key or the emulated N64
action. A current v1.2.0 reproduction and the launcher's **Create support report**
output would help; see the [playtesting guide](../playtesting.md). Requesting
those details from the reporter requires the owner's later permission to send.

## Native Expert movement results

These are original-game measurements, not measurements of a modified recomp
executable. All input names in this section denote emulated N64 buttons. They
do not identify the reporter's keyboard bindings.

| Held input | Forward magnitude | Side magnitude | Horizontal speed | Repeats | Qualified samples |
|---|---:|---:|---:|---:|---:|
| R + C-Up | 4.0625 | 0 | 4.0625 | 2 | 54 |
| R + C-Right | 0 | 2.5 | 2.5 | 2 | 54 |
| R + C-Left | 0 | 2.5 | 2.5 | 2 | 44 |
| R + C-Up + C-Right | 4.0625 | 2.5 | 4.770105475773046 | 2 | 54 |
| R + C-Up + C-Left | 4.0625 | 2.5 | 4.770105475773046 | 2 | 48 |

Velocities and speed are in world units per observed native tick. Sample counts
are the total across two repeats. Direction signs are omitted from the component
magnitudes so left and right can be compared directly.

The combined speed is `sqrt(4.0625^2 + 2.5^2)`. Relative to straight aimed
forward movement, the increase is `(4.770105475773046 / 4.0625 - 1) * 100`,
or **17.417980942105736%**. Native aim remained 1 and movement state remained 11
through the qualified forward and diagonal trials.

This answers the central native-versus-enhancement question for Juno/Expert
ground targeting. It does not establish a universal diagonal multiplier for
every character, movement state, original preset or modern input magnitude.

## Native Normal differs from Expert

The test switched the original game's Player 1 control mode through its own
pause/options menus. The observed mapping table changed from Expert
`0x800A18D8` to Normal `0x800A18B4`; the menu screenshot also recorded the
selection. No memory patch selected the preset.

| Normal inputs while holding R | Observed result |
|---|---|
| R alone; R+A; R+B; R+C-Up; R+C-Down; R+full analog up; R+full analog down | No forward or side velocity and no translation in the confirmation trials. |
| R+C-Right | Side velocity 2.5 units/native tick, no forward component. |
| R+C-Up+C-Right or R+C-Down+C-Right | Same side velocity 2.5, no additional forward component. |
| R+C-Right+Z | Actual lateral movement, eight pistol shots, aim retained. |

The first Normal matrix incorrectly labeled R+A as `aim_forward` and R+A+Z as
`aim_move_fire`. Those raw labels describe an incorrect expectation: the actor
did not move forward. Preserve the records, but count that firing case as
stationary. The final confirmation stage explicitly tested eleven combinations
and supplied the genuine Normal moving-fire case using R+C-Right+Z.

Do not claim the original Normal preset has the demonstrated Expert aimed
diagonal advantage. A modern action-based mapping can use the demonstrated
Expert baseline as its compatibility target while Original Controller Mapping
retains the selected native preset's behavior.

## Held aim through pistol fire

| Preset and motion | Input | Evidence |
|---|---|---|
| Expert, stationary | R+Z | Two repeats, eight shots per trial, aim 1 / movement state 11 throughout. |
| Expert, forward movement | R+C-Up+Z | Two repeats, eight shots per trial, forward speed 4.0625, aim 1 / state 11 throughout. |
| Normal, stationary | R+Z | Two repeats, eight shots per trial, aim 1 / state 11 throughout. |
| Normal, lateral movement | R+C-Right+Z | Confirmation trial, eight shots, side velocity 2.5, aim 1 / state 11 throughout. |

The Normal screenshot `normal/session/checkpoint-f1.png` also shows the reticle
and targeting camera after firing. The mislabeled Normal R+A+Z cases retained
aim too, but add no moving-fire coverage.

The original-game result supports the expectation that held targeting should
survive pistol fire in these cases. It does not identify which part of the
port's keyboard/mouse pipeline loses the reporter's input or aim state.

## Published source and earlier investigations

[v1.2.0 `pc_aim_movement`](https://github.com/TK22-26/JetForceGemini-Recomp/blob/v1.2.0/include/jfg/runtime/pc_input.hpp#L231)
clamps each axis to +/-80, divides by 80, normalizes the combined vector if its
length exceeds 1, then scales side velocity by 2.5 and forward by 3.0. The
[ground-aim adapter](https://github.com/TK22-26/JetForceGemini-Recomp/blob/v1.2.0/src/boot/native_boot.cpp#L7683)
calls it for modern modes 3/4/5 in movement states 10/11, subject to its existing
control gate. It writes side velocity at control+0x10 and forward at control+4
before ordinary native collision/physics.

Two differences are therefore established in source: forward scale 3.0 instead
of the measured native Expert 4.0625, and combined-axis normalization instead of
independent native forward/strafe components. This identifies the relevant
movement adapter; it is not a live reproduction of the reporter's exact build.
Do not infer a port-to-native percentage from the native 17.4% comparison without
accounting for the port's actual action and axis scaling.

Earlier evidence must remain scoped to what it demonstrated:

- [INPUT-003](../features/pc-controls.md#modern-shoulder-camera-and-mouse-audit-2026-10-10)
  fixed mouse capture reacquisition when a second mouse button was pressed,
  which had cleared the held first button. Historical RMB+LMB qualification is
  relevant background, but it does not establish this new R-input report's cause.
- [MOVE-002](../features/pc-controls.md#upward-camera-running-speed-and-scripted-input-follow-up-2026-10-10)
  corrected modern raw ground speed 5 to native `65/16 = 4.0625`, removing a
  23.08% overspeed. A radial cap on one analog input does not establish the
  maximum combined native forward-plus-digital-strafe speed. Do not undo that
  correction or dismiss this issue solely because normalization was deliberate.
- The [pinned upstream review](../upstream/reference-review-2026-10-01.md) and
  [reference catalog](../upstream/reference-catalog.json), especially JFG-UP-010,
  were consulted. They distinguish observed behavior from unvalidated work and
  do not grant execution budget or authorize runtime changes.
- [Jimmie1717's TAS submission](https://tasvideos.org/9865S), under Strafe Running
  and Strafe Flying, documented native combined running/strafing acceleration.
  It uses the Japanese release and originally supplied a reason to investigate,
  not proof of the North American aimed speed ratio. The direct EmuHawk
  measurement above supplies the latter for the tested Expert case.

The initial response draft treated deliberate normalization as an explanation
for dismissing the speed observation. That reasoning is superseded: an existing
implementation choice is not evidence of native parity.

## How the EmuHawk evidence was qualified

The emulator was BizHawk 2.11.1 with the Mupen64Plus cached interpreter
(`Core=1`) and a 4 MiB configuration (`DisableExpansionSlot=true`). The ROM was
the original USA image, 33,554,432 bytes. ROM, executable and worker identities
were pinned in each stage's scope receipt.

A fresh isolated save was created with ordinary controller input using
`scripts/phase95_startup.py`. The bridge reused
`scripts/phase95_bridge.py` and an observer derived from
`scripts/phase95_bizhawk_bridge.lua`. Private emulator copies used isolated
configuration/save paths, disabled audio/autosave/recent autoloads and cleared
physical host bindings. No desktop input was injected and no personal save was
imported. Emulator windows and process trees were owned by the guarded jobs.

The observer read the original `controlPlayer` entry at `0x80032A48`: A0 supplies
the actor and A1 the native update timestep. It recorded position at actor
+0xC/+0x10/+0x14, yaw at +0, and the private control pointer at actor+0x68.
Control fields observed were forward velocity +4, side velocity +0x10,
movement state +0x568 and aim +0x1F4. Input polls and per-frame observations were
retained. There were no gameplay-memory writes; the game performed movement,
collision and weapon updates itself.

The initial spawn near `[19, -101.99, 199]` faced a ramp. Early 90-frame routes
included slopes, turning, boundary contacts and falls. The game also used
varying native update timesteps, including 2 and 3. Raw maximum displacement,
fixed wall time or equal numbers of update calls would therefore give misleading
speed comparisons. Those exploratory traces were retained and excluded as final
speed baselines.

Native R+C-Down input for 90 frames followed by 90 neutral frames repositioned
Juno into the flat pool area, approximately `[19, -101.99, -112.3957]`, yaw
32768. `qualify/session/checkpoint-a0.png` records the baseline. No teleport or
position patch was used. A small residual coast remained, so analysis discarded
initial acceleration/settling intervals.

Each qualified trial restored the exact baseline RDRAM, acquired aim for 30
frames where applicable and applied its action for 90 frames. The Expert matrix
had 16 cases repeated twice. The initial Normal matrix had seven cases repeated
twice; confirmation tested eleven Normal combinations. Not every exploratory
case met the final measurement criteria.

Expert qualification used intervals at or after relative frame 35 with vertical
change below 0.01, yaw change at most 1 and aim movement state 11. Horizontal
displacement was divided by the observed native timestep. For the reported
speed cases, displacement/timestep agreed with native velocity magnitude within
0.00002 units/tick, and measured extrema agreed with the expected speeds within
0.00001. The final stage independently checked sealed input artifacts and these
numeric relationships.

Adding timestep and velocity reads changed the observer between the initial
probe and qualification. `qualify/observer-lineage.json` explicitly records the
old/new observer hashes and parent checkpoint identity. ROM/configuration/runtime
and state-file identities were checked, and restored RDRAM/frame/poll/player
identity was retained. Do not silently replace observer hashes or describe an
instrumentation migration as an identical original observation environment.

## Evidence locations and integrity

Private artifact ID: **`issue18-native-controls-20261017`**, stored under the
existing `D:/JFG-private` root. The repository contains only the sanitized
[public receipt](../../evidence/github-issue18-native-controls.json). Keep ROMs,
RAM dumps, savestates, emulator binaries and saves private; do not copy them into
public issue comments, commits or support material.

| Private file or directory | Purpose |
|---|---|
| `owner-approval.json` | Exact owner authorization, deadline, preserved prior counters and renewed limits. |
| `ledger-before-renewal.sqlite` | Consistent backup of the operational ledger before renewal; evidence only, not an alternate execution ledger. |
| `supervise.py` | Trusted host wrapper for these stages; production lease, heartbeat, owner deadline, process bounds, artifact sealing and grading. |
| `probe.py`, `probe/` | Fresh original-US startup and fifteen exploratory input trials. Initial checkpoint/session artifacts also live directly under the evidence root. |
| `analyze.py`, `analyze/` | Initial trace analysis identifying terrain/heading/timestep confounders. |
| `qualify.py`, `qualify/` | Observer lineage, native repositioning, 32 Expert trials and qualified movement/fire analysis. |
| `normal.py`, `normal/` | Native pause-menu preset switch and fourteen Normal trials, including the preserved incorrect R+A label. |
| `confirm.py`, `confirm/` | Eleven Normal input checks, genuine moving-fire trial, independent Expert checks and sanitized export. |
| Each stage's `scope.json`, `result.json`, `progress.json`, `process.json`, stdout/stderr | Pinned inputs, sealed output identities, guard accounting and process evidence. |
| Session `frames.tsv`, `input-polls.tsv`, checkpoint manifests and screenshots | Native observations, exact controls and checkpoint provenance; associated state/RAM/save data remain private. |

Important SHA-256 identities:

| Artifact | SHA-256 |
|---|---|
| Original USA ROM | `159dde164c475976a3e527fbb20978431d4765f2c63019b3530c3aa8772595aa` |
| EmuHawk executable | `f8cdb93551a544f680bf3876d9d8d72643859e7a44a23b04e1a25b92e48f80cd` |
| Public receipt / `confirm/public-evidence.json` | `8e376c9d9b2a10892fc420262990c25eb7467778e1ccd6ea1095a929f882fd34` |
| `qualify/analysis.json` | `1041759d7a71478c2d7c511ddd64ad7fa18898f025e97d0b3386a6d38d13588c` |
| `qualify/session/frames.tsv` | `dc628197a4102a4e5718b8c9e0affb368f73af327155b43676f5a99d5a9bbc1a` |
| `normal/analysis.json` | `c7a8834bafef9114e2b1f6acec0695552aac345e8020c1df999004d7cddf5196` |
| `normal/session/frames.tsv` | `9433a03b8d6dd062c36dc0826ac319df4c06dc4ec0dfba529e86746935016e34` |
| `confirm/session/frames.tsv` | `f7fded66fdaa0d5da82051db7f0d6230046a3c7c7bf80b259c1cf47c1ca16b94` |
| `confirm/session/input-polls.tsv` | `df6db2c5fb5edad653ebf0374bbe0e91f5bd1631a9cec0499834de03be8b85b7` |

The original emulator installation is retained under the private legacy archive
`legacy-preservation-20261015/legacy-checkout/tools/emulators/bizhawk-2.11.1/app`.
The stage manifests contain the local ROM/emulator paths; do not replace those
identities merely to make an old script run on a different installation.

## Production guard and continuation constraints

The persistent requirements in [AGENTS.md](../../AGENTS.md) and
[the guard guide](../planning/autonomy-progress-guard.md) remain in force across
compaction, restart and Goal resume. The production guard must remain enabled.
Before any autonomous investigation execution, read the authoritative ledger
and recover the existing state/budget. Experiments, builds, replays and coding
workers must run through the guarded supervisor. Foreground execution is not a
substitute for an admitted job.

The authoritative ledger is `D:/JFG-private/autonomy-production/jobs.sqlite`;
`tools/private/autonomy` is its workspace junction. Historical scripts may point
to a retired original location. Never run them unchanged against a newly
created or replacement ledger. Do not disable the guard, reset counters,
rename/re-root this investigation, bypass a denial with direct execution, or
restore the pre-renewal backup to obtain another allowance. Guard-disabled tests
may use isolated fixture ledgers only.

Read-only snapshot at **2026-10-17 22:42:37 UTC**:

| Field | Recorded value |
|---|---|
| Investigation | `pc-input-aiming-20261008` |
| Existing root | `pc-input-aiming-20261008-implement` |
| Guard / state | Enabled (`1`) / active after explicit owner renewal |
| Attempts | 58 / 59 |
| Supporting activity | 53 / 54 |
| No-progress counter | 5 / 7 |
| Cumulative leased execution | 145401.99980854988 / 221400 seconds |
| Review / alternative counts | 0 / 0; no recovery registered |
| Progress verifier | `none`; these results received supporting-activity classification |
| Live or ungraded investigation run | None |
| Owner approval time | 2026-10-17 22:22:45 UTC |
| Owner test deadline | **2026-10-18 00:22:45 UTC** (October 17, 8:22:45 p.m. America/New_York) |

Before renewal the investigation was shelved at 53/53 attempts, 48/48 supporting
activities, no-progress 5 and 144926.7658984661 seconds spent. Renewal increased
the attempt/activity caps by six, the no-progress cap from six to seven, and the
execution cap by 7200 seconds. It retained every charge and the same root.
The recorded scope allowed two additional no-progress outcomes from the then
current counter of five. Review/alternative limits remained 300/600 seconds;
they are not fresh automatically runnable jobs.

The five completed job IDs share prefix
`pc-input-aiming-20261008-issue18-20261017-` and suffixes `probe`, `analyze`,
`qualify`, `normal`, `confirm`. Each passed and was graded `activity` because
there is no registered progress verifier for this work. Approximately 475.234
leased seconds were added; no progress credit or counter reset was awarded.
The last completed predecessor is the `confirm` job.

At the snapshot, one attempt and one supporting activity remained. This is not
standing permission to use them for coding or a different experiment. The
owner's wall-clock deadline is additionally enforced by this test supervisor;
the ledger's cumulative-time allowance must not be mistaken for permission to
run after that deadline. Check current ledger state and approval scope before
continuing. On denial or exhaustion, report the blocker and stop that work.

The separate `high-refresh-rendering-20261011` performance investigation was
active at the initial review. Its current state must be read independently.
Do not interrupt, duplicate or charge this controls work to that investigation.
Parallel approval did not permit simultaneous jobs inside this controls
investigation. All five controls runs finished and were graded.

## Remaining work for 1.3

These are follow-up tasks, not already implemented fixes or new execution
authorization. Preserve the owner's conditional 1.3 intent and obtain applicable
guarded execution scope/budget before running implementation workers or replays.

1. Reconcile the implementation base with the published v1.2.0 source and any
   subsequent owner changes. Preserve the existing workspace; do not reset or
   check out over unrelated edits.
2. Qualify native Vela/Lupus and relevant directional cases before changing a
   shared helper. The current numeric baseline is Juno/Expert ground aim;
   backward/boundary routes and other states are not qualified equivalents.
3. Correct the scoped modern ground-aim mapping to preserve the measured native
   component behavior. Review the forward scale as well as normalization.
   Avoid a blanket speed multiplier and preserve native collision, animation,
   state transitions and original preset restrictions.
4. Run meaningful before/after comparisons on the actual modern action path,
   including keyboard/mouse and controller axis scaling. Unit tests that merely
   repeat the old normalized constants are insufficient; use native numeric
   baselines and qualified displacement/aim-state evidence.
5. Diagnose held-aim cancellation independently. Establish exact build/bindings,
   trace held/pressed/released aim and fire across host input, action mapping and
   native aim state, and distinguish physical keyboard aim from mouse chords.
   Revisit INPUT-003 only if evidence shows the same capture mechanism.
6. Verify stationary and moving held-aim fire, then relevant transitions and
   other weapons/characters. Preserve the existing airborne-aim/jump behavior
   where applicable; this ground measurement does not qualify those states.
7. Record candidate, test-verified, pending live verification and released
   statuses separately. Update the issue record, index, known issues and
   feature notes with actual cause, remedy, limits and real commit/release only
   when available. Send an issue response only after the owner authorizes it.

The requested persistent issue-documentation practice applies to future bugs,
regressions and significant limitations across compaction and handoff. Preserve
informative failures and link historical evidence. A successful build, replay
or partial improvement does not complete a fix or reopen a shelved investigation.

## Suggested response for owner review only

The following draft has **not** been sent:

> Thanks for the detailed report. I checked the original North American game
> in EmuHawk: with Expert controls, Juno can move about 17.4% faster diagonally
> while targeting than straight forward. The current modern aiming movement
> mapping doesn't preserve that behavior, so I'm targeting a compatibility
> correction for 1.3.
>
> The original game also kept targeting active while firing the starting pistol
> in both Normal and Expert controls. I haven't identified the cause of your
> aim cancellation yet. Could you retest with v1.2.0 and confirm the game build,
> whether you're using Modern Controls or Controller Mapping, and the exact
> aim/fire bindings? Please also clarify whether "R" means the keyboard key or
> the N64 R action. If it persists, a support report from the launcher and a
> short clip would help reproduce it. Thanks for offering further testing.

## Workspace handoff

This task added the handoff, [GH-018 record](issues/github-held-aim-and-diagonal-movement.md)
and [sanitized receipt](../../evidence/github-issue18-native-controls.json), and
updated the [issue index](issues/README.md), [known issues](../known-issues.md)
and [PC controls notes](../features/pc-controls.md). No runtime source or test
implementation was changed. The guarded native evidence is complete; the port
fix and the reporter-specific input reproduction remain open.

Pre-existing user changes in `docs/development/issues/diagnostic-storage-exhaustion.md`
and `docs/planning/autonomy-progress-guard.md` were preserved. Do not include or
overwrite them incidentally. No commit was requested. If a later owner-authorized
commit is made, AGENTS.md requires author and committer `TK22-26` with
`254768757+TK22-26@users.noreply.github.com` and UTC timestamps.
