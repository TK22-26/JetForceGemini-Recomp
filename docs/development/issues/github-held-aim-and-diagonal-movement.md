# GH-018: Held aim cancels on firing; diagonal movement differs while aiming

- Severity: core-control compatibility issue; owner now reports the original reporter acknowledged the held-aim interruption fixed in v1.2.
- Status: held-aim cancellation acknowledged fixed in v1.2, relayed by the owner on 2026-10-19. Standing-aim movement correction matches the measured native Expert components in tests and captured gameplay; included locally for v1.3, unreleased.
- Reported and last updated (UTC): 2026-10-17.
- Report: [GitHub #18](https://github.com/TK22-26/JetForceGemini-Recomp/issues/18).
- Reported environment: Windows 10, NVIDIA 5070 Ti, driver reported as 6.17.42, keyboard/mouse.
- Reported launcher revision: `c994c75`, matching the `v1.1.0` tag. Actual game executable/build, control profile and bindings have not been supplied.
- Owner intent (2026-10-17): target 1.3 if EmuHawk supports the report. The native Expert measurement now supports movement compatibility work for that target; implementation and release verification remain open.
- Current test status: five guarded supporting jobs completed under the owner's two-hour isolated test approval. The same investigation retained its enabled guard, charges and roots. No runtime change or GitHub message was made.
- Detailed continuation: [issue 18 handoff](../issue18-native-controls-handoff-2026-10-17.md), including measurements, private evidence identities, guard snapshot, remaining work and an unsent reply.
- Public measurement receipt: [native controls evidence](../../../evidence/github-issue18-native-controls.json).

## Symptoms and reproduction

At the beginning of the game with the starting pistol, hold the input described
as R to aim and fire once. The reporter says the reticle disappears and aiming
ends on every first shot despite continuing to hold the aim input. Other weapons
are untested. It is not yet clear whether R means a keyboard binding or the
emulated N64 action, or which input fires the weapon.

Separately, the reporter observes faster diagonal movement outside aiming but
no equivalent diagonal speed increase while aiming. No timed comparison, video
or original-game baseline was attached. The reporter offered further testing
during a keyboard/mouse playthrough.

## Evidence and hypotheses

- The issue had no comments or support attachment when reviewed. The launcher
  revision alone does not identify the independently selected game runtime.
- The current published [v1.2.0 release](https://github.com/TK22-26/JetForceGemini-Recomp/releases/tag/v1.2.0)
  is dated 2026-10-16 and identifies runtime/launcher source `f56cd94c4bd7583bceee201eb3f229f744216bc1`.
  Its controls overhaul makes a current-package retest useful; it does not prove
  this report fixed. This checkout predates that release, so release claims were
  checked against the tag and live release metadata instead of local README text.
- [INPUT-003 and the mouse audit](../../features/pc-controls.md#modern-shoulder-camera-and-mouse-audit-2026-10-10)
  record a previous held-aim failure caused by reacquiring mouse capture when a
  second mouse button was pressed. Its correction and historical qualification
  concern that demonstrated mouse-button chord. The new R-input report has not
  been shown to share its cause.
- [The movement correction](../../features/pc-controls.md#upward-camera-running-speed-and-scripted-input-follow-up-2026-10-10)
  documents deliberate diagonal normalization in modern ground movement.
  Existing `tests/pc_input_tests.cpp` also describes normalized aiming movement.
  These existing records are not a new test run or proof of the reporter's profile.
- [Pinned upstream review](../../upstream/reference-review-2026-10-01.md) and
  [catalog JFG-UP-010](../../upstream/reference-catalog.json) describe native stick
  clamping. They do not establish movement equivalence across normal/aiming
  states, or authorize adding a diagonal speed bonus from another game.
- Follow-up evidence: [Jimmie1717's N64 TAS submission](https://tasvideos.org/9865S),
  under Strafe Running and Strafe Flying, explicitly documents greater speed
  from combining ordinary running and strafing in the original game. This is
  a primary account by the run's author; the run uses the Japanese release.
  It establishes that native strafe-running is a real mechanic, but does not
  establish the exact North American aiming-state behavior or speed ratio.
  Our analog-stick clamp evidence does not account for every combined native
  movement input. Deliberate modern normalization therefore cannot by itself
  justify dismissing a possible movement-parity report.

### Qualified original-game findings

The North American original was run in BizHawk 2.11.1 / Mupen64Plus cached
interpreter with Juno and the starting pistol. Trials restored the same RDRAM
checkpoint, used native controller inputs, and observed position, movement state,
aim state, velocity and native update timestep without gameplay-memory writes.
The following Expert-preset results use settled, flat-ground, fixed-heading
intervals; each case was repeated twice. R and C-button names below refer to
emulated N64 controls, not physical keyboard bindings.

| Held Expert input | Horizontal units per native tick | Qualified samples across two repeats |
|---|---:|---:|
| R + C-Up | 4.0625 | 54 |
| R + C-Right | 2.5 | 54 |
| R + C-Left | 2.5 | 44 |
| R + C-Up + C-Right | 4.770105475773046 | 54 |
| R + C-Up + C-Left | 4.770105475773046 | 48 |

Expert combines the full forward and strafe components:
`sqrt(4.0625^2 + 2.5^2) = 4.770105475773046`, which is **17.41798% faster**
than aimed forward movement. Restoring this demonstrated behavior is a native
compatibility correction, not an invented aiming-speed enhancement.

Normal behaves differently. With R held, A, B, C-Up, C-Down and full up/down
analog inputs produced no forward movement in the tested setup. C-Right produced
2.5 units per tick of lateral movement; adding C-Up or C-Down did not add a
forward component. Do not generalize the Expert diagonal result to Original
Controller Mapping's Normal preset.

Held aim remained active through pistol firing in both presets. Expert had
stationary and forward-moving firing trials, each repeated twice with eight
shots. Normal had stationary trials and a confirmed sideways-moving
R + C-Right + Z trial with eight shots. Observed aim stayed 1 and movement state
stayed 11. This establishes the original-game expectation for these cases;
it does not reproduce or diagnose the reporter's physical-input failure.

### Published modern mapping mismatch

In [v1.2.0 `pc_aim_movement`](https://github.com/TK22-26/JetForceGemini-Recomp/blob/v1.2.0/include/jfg/runtime/pc_input.hpp#L231),
combined axes are normalized to length 1 before scaling side velocity by 2.5
and forward velocity by 3.0. The
[ground-aim adapter](https://github.com/TK22-26/JetForceGemini-Recomp/blob/v1.2.0/src/boot/native_boot.cpp#L7683)
uses this helper for modern modes 3/4/5 in movement states 10/11, writing the
velocities before native physics and collision. Both the forward scale and
combined-axis normalization differ from the measured native Expert behavior.
This is a source-level finding; no current released executable was run through
the reporter's keyboard/mouse path during this investigation.

## Attempts and results

| Date | Review or attempted remedy | Result | Decision and evidence |
|---|---|---|---|
| 2026-10-17 | Read issue, release metadata, version tags and existing control evidence | Older launcher identified; game revision/profile remain unknown; no gameplay reproduction | Draft a reply for owner review; request v1.2.0 retest, exact profile and aim/fire bindings, and support report if still affected |
| 2026-10-17 | Read production guard state without modification | Guard enabled; existing `pc-input-aiming-20261008` investigation shelved; 53/53 attempts and 48/48 supporting activities used | No experiment, build, replay or coding worker launched; no investigation reopened or allowance reset |
| 2026-10-17 | Owner asked whether the speed increase is native or an enhancement; checked the original-game TAS author's account and existing mapping source | Native running-plus-strafing speed increase documented; native held-aim equivalence remains unverified | Correct the draft's implication that normalization settles the question; recommend matching native behavior before considering an aiming-speed enhancement. No runtime change or test |
| 2026-10-17 | Owner requested EmuHawk measurement and a 1.3 fix if native behavior supports the report; rechecked production ledger | Guard still enabled; same investigation shelved with zero remaining attempts and supporting-job allowance | EmuHawk not launched. Need an explicit bounded renewal of the same investigation before guarded execution; retain every existing charge and root |
| 2026-10-17 | Owner explicitly approved a two-hour parallel test | Trusted host recorded a same-investigation renewal with prior counters preserved, at most six supporting attempts and two additional no-progress outcomes, and a two-hour deadline | Guarded original-US input measurement started in isolated EmuHawk state; private evidence `issue18-native-controls-20261017`. Separate performance work is untouched |
| 2026-10-17 | Initial original-US probe and trace analysis | Spawn-ramp traversal, turning, boundary contacts and varying native update timestep confounded raw displacement comparisons | Preserve exploratory traces; do not use their raw maxima or elapsed frame counts as speed baselines |
| 2026-10-17 | Qualified Expert trials after native-input repositioning onto flat terrain | Forward 4.0625, side 2.5 and diagonal 4.77010548 units/native tick; two repeats; held aim survived stationary and moving pistol fire | Native aimed diagonal advantage confirmed for Juno/Expert; retain timestep and movement-state evidence |
| 2026-10-17 | Switched to Normal through the game's pause menus and tested movement/fire | Lateral movement and held-aim firing worked; R+A did not move forward despite the initial raw trial label | Preserve the mislabeled raw trial and explicitly exclude it as forward or moving-fire evidence |
| 2026-10-17 | Confirmed eleven Normal input combinations and independently checked Expert measurements and sealed artifacts | Normal forward inputs tested remained stationary; R+C-Right+Z moved laterally and fired eight shots without dropping aim | Export sanitized public evidence; preset difference is material; no identical-diagonal claim for Normal |
| 2026-10-17 | Compared the native baseline with v1.2.0 source | Modern aimed forward scale 3.0 and radial normalization differ from native Expert | Track movement compatibility for 1.3; investigate aim cancellation separately; no code change or posted response |

## Actual resolution

No fix has been implemented. The movement mapping's normalization and forward
scale are the identified source-level differences from the native Expert
baseline. A candidate must preserve qualified native behavior across its actual
character/state scope before it can be considered a verified remedy.

The cause of the reporter's aim cancellation remains unknown. Neither the earlier
capture correction nor upgrading has been verified as its remedy. No code change,
commit, release or GitHub response was made. The response in the handoff remains
an owner-review draft; the owner explicitly prohibited messaging on the issue.

## Verification and remaining limits

First establish the actual launcher/game builds, Modern Controls versus original
Controller Mapping, literal aim/fire inputs and hold/toggle setting. If the issue
persists on v1.2.0, request a short pistol reproduction and the launcher's
**Create support report** ZIP for that session, following the
[playtesting guide](../../playtesting.md). A short movement comparison in the same
open area would help distinguish a speed-cap expectation from a control defect.
Additional weapon/character coverage is optional after the initial reproduction.

The native measurement covers Juno, the starting pistol and the tested Goldwood
area. Vela/Lupus, other weapons, airborne/swimming/damage/scripted states and the
released port's physical-input path remain unqualified here. Backward and turning
routes that encountered terrain are not equivalent speed baselines. Do not apply
a blanket character/state speed multiplier from these results.

Any autonomous experiment, build, replay or coding worker must use the guarded
supervisor with the same investigation identity and charges. The two-hour
approval was for native measurement only, not a runtime fix or publication.
At the 2026-10-17 22:42:37 UTC read-only snapshot, the guard was enabled and the
investigation active at 58/59 attempts and 53/54 supporting activities, with no
live or ungraded run. The approval expires at 2026-10-18 00:22:45 UTC. Re-read the
operational ledger before any continuation; this record grants no new allowance.

### Completed EmuHawk protocol and evidence limits

Fresh save creation and repositioning used ordinary controller inputs. The
qualified matrix restored the exact baseline RDRAM before each trial, acquired
aim for 30 frames, then applied the action for 90 frames. Analysis used
post-35-frame intervals with level ground, stable yaw and native aim state 11.
Horizontal displacement divided by the observed native control-update timestep
agreed with velocity magnitude within 0.00002 units/tick. The observer's addition
of timestep/velocity reads has an explicit lineage receipt and restored-RDRAM
equality check; it did not write gameplay memory.

The [handoff](../issue18-native-controls-handoff-2026-10-17.md) identifies the
private scripts, traces, screenshots, sealed results and hashes. Only the
sanitized measurement receipt is copied into public repository evidence; ROM,
RAM, states, emulator binaries and saves remain private.

## Lessons for future ports and changes

Track launcher and runtime identity separately. Similar symptoms with keyboard
and mouse aim bindings do not establish a shared input-capture cause. Keep
movement-speed expectations separate from aim-state cancellation, and qualify
each control profile before changing normalization or original mapping behavior.
An analog-stick radial cap does not prove the maximum speed of combined stick
and digital strafe actions. Preserve demonstrated native movement techniques;
treat any additional aiming-speed behavior beyond the native baseline as a
separate enhancement decision. The initial reply draft's description of deliberate
normalization is an implementation fact, not evidence of native parity.

## v1.3 standing-aim candidate, 2026-10-18

Owner explicitly requested implementing the EmuHawk-supported movement finding.
Standing aim (state 11) now uses independent components: forward 4.0625 and
sideways 2.5 units/native tick. Combined full input gives 4.77010548 as measured.
Backward keeps the native 3.0 cap; crouch/state10 retains its existing policy.
Original controller mappings and special-state physics are unchanged.
The Juno/Vela standing handlers cap forward at 65 times their native movement
scale; Lupus explicitly caps at 4.0625. The fixture checks the published Juno
measurement, analog partial input and saturation. Broader character feel remains
for the owner to verify; this does not resolve the separate reported fire/aim
cancellation. No issue comment or release has been made.

Guard: existing active pc-input-aiming-20261008 retains all counters and its
last available attempt. The first launch waited on the occupied shared worktree
(no progress-guard denial and no lease); after the rendering job finished
normally, the same queued request acquired that resource through the supervisor.
No budget, ancestry, resource name or immutable job was reset.

Integrated candidate builds successfully; 371 PC-input checks and navigation/action-lock fixtures pass. Private JFG - Glass and Controls Review desktop launcher prepared, with copied pre-rescue save, normal blur effects, muted 120 FPS/VSync and buffered controls/FPS logging. Runtime SHA-256: 669acb5f0cf377a40bd4f57cf7fd907a32890ee9141c01e1f2b7727426c845b2. Live owner verification pending; no autonomous gameplay performed.

## Owner movement feedback, 2026-10-18

Owner reports horizontal movement is definitely faster in the combined preview.
The code/component comparison matches recorded native standing-aim magnitudes
(forward 4.0625, side 2.5, diagonal 4.770105475773046 units/native tick).
Actual displacement in this preview has not yet been qualified; neither
subjective improvement nor component tests establish runtime parity.

### Completed owner capture: runtime movement observation

The buffered trace contains standing-aim velocities exactly 4.0625 forward and
2.5 side, independently, in both diagonal directions. Consecutive same-heading,
same-velocity, level intervals give actual displacement/native tick:
forward 4.061964-4.062429 (55 samples), diagonal 4.769486-4.770033
(319 samples), pure side 2.499776-2.499799 (37 samples).
All are within 0.00062 world units/tick of the measured native magnitudes.
Small heading-dependent differences remain; this is not bit-exact emulator
trajectory parity or new qualification of other movement states.
Private receipt: D:/JFG-private/v13-owner-controls-20261018/owner-movement-qualification.json.

## Reporter acknowledgement relayed by owner (2026-10-19)

The owner states that the reporter acknowledged held aim cancelling when firing is fixed in v1.2. Treat that symptom as reporter-confirmed resolved for the reported case, rather than an outstanding v1.3 diagnosis. This is owner-relayed acknowledgement; no new GitHub fetch, post or closure occurred in this continuation, and no additional cause/commit attribution is invented. The separate standing-aim movement correction remains included for v1.3 with the measured runtime evidence above.

Release-preparation readback verifies the reporter acknowledgement directly: [comment 6244055488](https://github.com/TK22-26/JetForceGemini-Recomp/issues/18#issuecomment-6244055488), 2026-10-18. They had accidentally launched the older game and confirm targeting cancellation is gone in v1.2.0. The subsequent maintainer comment separately confirms the movement remedy is targeted for v1.3. No new reply or closure was posted.
