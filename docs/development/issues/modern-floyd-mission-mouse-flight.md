# Modern mouse/keyboard Floyd mission flight controls

- Status: owner approved delivered preview7 controls, including mouse flight with A/D strafing and the separate controller flight option. Automated checks pass; actual firing and full mission completion have no separate owner result. Unreleased.
- Severity: mission control usability; prevents useful qualification of #37 shooting/completion.
- Build/profile: Modern Players and Floyd preview4, SS Anubis Floyd mission, Modern M/K. Controller not tested by owner.
- Reproduction: enter Floyd mission after collecting a Mizar token; W pitches down and S pitches up. Mouse changes the reticle but does not turn Floyd's flight direction, leaving flight steering on WASD.

## Cause and approved behavior

Before preview5, `map_modern_floyd_actions` forwarded ordinary movement axes unchanged. The native mission branch in sidekickControl reads absolute stick X/Y at 0x8002F9E4 and0x8002FACC, applies a deadzone and native aircraft pitch/yaw, then updates flight heading at control+0x60/+0x62. W produces forward-stick input, which is nose-down in the original flight controls. This explains the reported W/S inversion; it does not establish a saved Invert vertical toggle or a regression of the already accepted co-op reticle sign fix.

The earlier Modern mouse hook ran later at 0x80031090, overriding the absolute reticle target after the flight update has already consumed keyboard axes. Thus mouse aim does not steer the mission. Treating mouse deltas as a persistent virtual stick would continue turning after the mouse stops and is not the approved direct-look behavior.

Owner approved the recommended Modern M/K layout: mouse turns Floyd's flight direction, W provides forward thrust, S brakes, left-click shoots and E interacts with the pad. Keep the reticle aligned with flight for this mode. The mission-only adapter must apply relative mouse motion before native flight orientation/position are consumed, honor the saved inversion/sensitivity exactly once, avoid repeated consumption at higher update rates, preserve pitch bounds and reset safely across focus/pause/retry/exit. Native speed/collision and mission transitions need regression checks. Co-op remains a separate reticle mode; controller has not been owner tested and is outside this mouse remapping request.

The implementation and qualification below supersede the initial pending state. This is not a complete mission replay. Private evidence: D:/JFG-private/floyd-mission-mouse-flight-20261021. Related [#37](github-floyd-cannot-fire.md), [co-op inversion](modern-floyd-vertical-inversion.md), [pad entry](give-floyd-mission-pad-access.md).

Transferable lesson: co-op reticle input and mission flight steering share an input source but consume it at different times; a later reticle override cannot control the earlier flight update. Validate both modes independently through the native consumer.


2026-10-21 candidate checkpoint: source and isolated runtime are implemented.
Four focused suites and the serial Release build pass. Original native flight
plus exact-source adapter tests pass 302 cases / 3,790 checks. Evidence is in
`D:/JFG-private/floyd-mission-mouse-flight-20261021/qualification.json` and
`native-flight-2/run-3.log`; full-game flight feel, actual shooting and mission
completion remain unverified. Preview replacement stopped before copying any
runtime because the owner launcher was open (PID 5832); the owner was asked to
close it. This safe stop is not a runtime build failure. The existing preview4
package remains intact until delivery resumes. The dependent documentation
step likewise stopped on the unmet delivery prerequisite.

## Preview5 implementation and qualification

Modern M/K missions consume relative mouse motion at the two original
`sidekickControl` input-read return sites, before native flight updates. The
adapter updates current native yaw/pitch, clears residual angular velocity and
neutralizes the old steering axes. Mouse motion is consumed once per input
sample; pitch retains the original +/-16384 limits. Existing mouse aim
sensitivity, vertical sensitivity and inversion are applied once during input
sampling. No new cached flight heading survives retries.

Forward/back movement actions become native thrust/brake (default W/S). Fire
continues to reach native Z, and the mission reticle is centered on flight.
Interact remains available for pad/menu entry. The controller mission mapping
and independent co-op reticle are preserved. Mode identity includes the mission
bit so switching modes does not reuse the previous reticle accumulator. Existing
focus/pause/input-lock capture clearing remains in force. Native speed, collision,
flight camera and mission progression routines are unchanged.

Validation:

- All four focused suites pass: PC input, Modern controls, Modern roll and
  navigation mods. Serial Release runtime build passes.
- Private fixture executes 17 original generated functions through native input,
  steering, throttle/brake ramps and vector rotation. The sine entry alias uses
  the original cosine implementation with an inverse quarter-turn argument;
  original lookup-table data comes from the owner's closed capture.
- 288 flight cases cover both generated execution paths, all four physical
  slots, owner/joined-P2 routing, 1/2/3 ticks, inversion Off/On and aim sensitivity
  50/100/200. Mouse-up moves thrust upward with inversion Off. Repeated updates
  do not reuse motion; stopping the mouse holds heading. W/S reach the native
  throttle/brake ramps while Fire remains held. Two unchanged-input cases
  reproduce the original W/S aircraft pitch direction.
- Twelve exact-source adapter/gating/transition cases cover blocked focus,
  controller/Classic exclusion, pause, locked mission transition, co-op,
  unrelated callers, disconnect, old recording, centered mission reticle,
  preserved co-op direction and retry/clamp reversal. The reticle adapter uses
  an observation callback; this does not requalify the whole native reticle body.
- Total: 302 cases, 3,790 checks. These are bounded native/adapter tests using
  private scratch RAM, not a full-game replay or an EmuHawk mission completion.

Informative failed attempts retained privately: the first unit assertion used
unsigned 65336 instead of the helper's signed -200 angle; corrected expectation.
The first native fixture lacked the shared sine entry alias, then stopped on a
generated function's unused-parameter warning; added the original entry adapter
and scoped warning suppression. Review also replaced a nonexistent mod-memory
32-bit writer with the existing 16-bit writes before the successful runtime
build. None of these failed attempts counts as passing validation.

Preview5 replaces the runtime in the existing Modern Players and Floyd preview.
Package inventory, runtime protocol and helper setup pass. Profile, settings,
ROM and save hashes are unchanged; preview4 runtime is backed up privately.
The accepted preview4 camera correction remains included. No automatic gameplay
launch, commit, push or release. Runtime SHA-256: `8a8b19d1ff65f350196f8f0e5de43e30c8bbf7f1393ec3befe4faa8f97a2ba40`.
Evidence: `D:/JFG-private/floyd-mission-mouse-flight-20261021/qualification.json`,
`native-flight-2/run-3.log`, `delivery.json` and component/build logs.

Owner check: enter SS Anubis after collecting a Mizar token, steer up/down and
left/right with the mouse, hold W to fly, use S to brake, fire with left-click,
then pause/resume and retry. Live control feel, actual shots and mission
completion remain open. This mission mapping cause does not establish a shared
cause with the earlier #32 mouse inversion report.

Owner closed the launcher; preview5 was delivered with all package/profile checks passing and reopened for the requested live test. No automatic Play. A delivery retry first stopped on a relocated test-receipt path; corrected orchestration before copying files, with failed logs retained. Live flight/fire/completion results remain pending.

## Owner preview5 feedback and strafe follow-up

Owner says mouse flight feels pretty good and requests A/D strafing alongside it. This is positive flight-feel feedback, not explicit acceptance of shooting or mission completion. Preview5 intentionally discarded A/D; original A/D was aircraft yaw, not sideways flight. Owner-requested sideways movement is now a candidate: keep X as semantic strafe intent, add heading-relative lateral thrust before the original flight velocity/collision pipeline, cap combined thrust at native full magnitude, and leave mouse heading/W/S behavior intact. Verification and preview6 delivery pending. Same enabled production guard/investigation/counters; existing deadline22:37:40UTC.


## Preview6: A/D lateral flight added

Move Left/Right (default A/D) now remain in the Modern M/K mission X channel.
The existing flight input hook still neutralizes native yaw steering, so A/D
does not turn Floyd. A second narrowly gated hook at the original forward-vector
call adds lateral thrust relative to current native yaw. It updates the saved
nonzero-acceleration gate so A/D also works without W. Combined forward/lateral
thrust is capped at native full thrust; native smoothing, speed normalization,
speed cap, position integration and subsequent scenery collision remain in use.
Release uses original coasting. No persistent host velocity or heading is added.

The side vector stays horizontal even when looking up/down. Mouse flight,
W thrust, S brake, Fire and centered mission aim retain preview5 behavior.
Move Left/Right rebinding works through the existing action mapping. Shift does
not increase side thrust above the native full-thrust magnitude. Controller,
co-op and Classic bypass this new mission mouse hook.

All four focused component suites and the serial Release runtime pass. A private
18-function native fixture now executes through original velocity and position
integration. Its 3,456 movement cases cover both execution paths, four physical
ports, joined/owner routing, four headings, three pitch angles, 1/2/3 ticks,
both strafe directions and forward/neutral/brake combinations. Side movement
does not change heading; A/D alone moves horizontally; combined impulses stay
bounded; native speed never exceeds 8. Long holds reach that cap, release coasts,
and opposite input reverses lateral velocity. Expanded caller/state checks and
the earlier mouse/reticle cases also pass: 3,771 cases / 437,600 checks total.
The initial fixture build rejected a shadowed local variable; renamed it before
the passing run. Failed logs remain private.

This fixture stops after native position integration, before scenery collision.
It is not a full mission replay or proof of live wall contact/shooting/completion.
New X input means strafe in Modern M/K mission recordings; older mission captures
whose X meant aircraft yaw are not unchanged-behavior replay evidence.

Preview6 is installed in the existing Modern Players and Floyd preview. Runtime
protocol, launcher helper setup and package inventory pass; profile/settings/save
hashes are unchanged. Prior preview5 runtime is preserved privately. Runtime
SHA-256: `7768c6f590a90d65004a38193672fafc472e35350752456ede6686392121bf3a`. Evidence:
`D:/JFG-private/floyd-mission-mouse-flight-20261021/strafe/qualification.json`,
`native-integration/run-2.log`, build logs and `delivery.json`.

Owner check: strafe each way at rest and while holding W, steer the mouse while
strafing, release/reverse A/D, and check nearby wall contact and S braking.
Live feel, actual shots and mission completion remain pending. No automatic
launch/Play, commit, push or release.


Preview7 retains mouse steering and A/D strafing and adds a [controller-only flight inversion preference](modern-floyd-controller-flight-inversion.md). Mouse flight is unaffected. Owner A/D feel, actual shots and mission completion remain pending.

Owner acceptance update (2026-10-21): owner replied “approved” to the delivered preview7 controls. Record preview approval; prior pending statements above describe earlier checkpoints. No individual wall-contact, firing or mission-completion result was supplied. See [controller flight acceptance](modern-floyd-controller-flight-inversion.md).


## Final owner disposition for v1.4.0 (2026-10-21)

The owner states that #37 and the associated Floyd work are fully approved
locally and requests reporter verification after delivery. This supersedes the
earlier local acceptance gates above without inventing additional measured routes
or hardware coverage. The combined v1.4.0 package still needs the requested
SS Anubis final pass. No publication or public reply is implied.
