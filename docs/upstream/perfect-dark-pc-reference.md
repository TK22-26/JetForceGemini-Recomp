# Perfect Dark references for PC enhancements

Perfect Dark supports mouse and keyboard controls, separate analog inputs,
rebinding, sensitivity, inversion, and controller discovery. Its host input
design informed the original JFG implementation below; no Perfect Dark game
code or host implementation was copied into JFG.

The owner resumed implementation on 2026-10-08. All new input paths now require
an explicit **Experimental PC controls** opt-in in the Controllers modal.
It is disabled by default and enforced in the runtime as well as the UI.
JFG now has per-player keyboard and mouse-button/wheel bindings, Normal/Expert
presets, direct relative mouse aiming, separate analog stick aiming, ground
movement while aiming, and mouse / stick orbit for the normal third-person
camera. Modern stick aiming uses a rate scaled by guest update time; mouse
motion is displacement. These remain experimental: complete gameplay feel
and all-character, all-camera qualification are still pending.

See [launcher controls](../development/launcher.md#keyboard-mouse-and-separate-stick-aim)
for configuration and limitations.

## Pinned source and local archive

- Repository: [perfect-dark-pc-port/perfect_dark][pd-repo], branch `port`.
- Reviewed commit: `32a1cb9f268dd3ac73016801025c6bbbfa20130f`.
- Commit date: 2026-08-13 UTC; reference retained: 2026-10-08.
- Local archive:
  `tools/upstream/perfect-dark-reference/32a1cb9f268dd3ac73016801025c6bbbfa20130f/`.
- Retained files: `port/src/{input,config,video,fs}.c`, their corresponding
  `port/include/` headers, and the complete upstream `LICENSE`.
- `manifest.json` in that archive records source URLs, upstream Git blob IDs,
  SHA-256 digests, and byte counts. Downloaded files matched the pinned blobs.

The archive is ignored by Git under the existing `tools/` policy. The pinned
links below remain the reference for other checkouts. These files depend on
Perfect Dark and its platform interfaces; the selection is not a standalone
library or a new JFG build dependency. Game assets and decompiled game source
are not included in this archive.

The [upstream MIT notice][pd-license] is retained with the files. Any later
source adaptation must preserve the applicable copyright and permission
notice and add its attribution to [third-party notices](../../THIRD_PARTY_NOTICES.md).

## Modern controls target and remaining work

The intended modern preset has two independent input paths:

| Device | Movement | Aim and camera | Other requirements |
| --- | --- | --- | --- |
| Keyboard and mouse | WASD movement and strafing | Relative mouse movement | Rebind keys, mouse buttons and wheel; separate look and aim sensitivity; inversion |
| Controller | Left-stick forward/back movement and strafing | Right-stick aiming and camera control | Independent stick sensitivity, deadzones and inversion; preserve analog magnitude |

For ordinary third-person play, movement should be relative to the active
gameplay camera. The right stick should aim while in aiming mode and control
the camera where that gameplay mode permits. Resolve JFG's turning, aim-mode
transitions, and camera constraints in the game integration; mapping right-stick
directions to digital C buttons does not meet this requirement.

Proposed keyboard defaults are left-click fire, right-click aim, Space jump,
and wheel weapon selection. Use JFG actions when presenting bindings and
account for Normal and Expert control schemes. Keep the original control
profile available alongside the modern preset.

Perfect Dark's [input backend][pd-input] provides relative mouse movement,
bindable mouse buttons and wheel, per-axis stick settings, separate analog
inputs, controller discovery, and rumble. Its [input interface][pd-input-h]
is useful for understanding the separation between input collection and game
behavior. Its [movement integration][pd-movement] shows mouse deltas entering
aiming logic and separate moving-crosshair and centered-crosshair behavior.
The movement source is a linked reference only; its game-specific calculations
are not a JFG camera implementation.

JFG's [PC input mapper](../../include/jfg/runtime/pc_input.hpp) provides
configurable keyboard/mouse bindings and an independent look channel.
Version-2 PC profiles select modern behavior; legacy profiles retain their
previous behavior. In modern mode the guest manual-aim routine still handles
weapon state and output values, followed by direct angle updates within its
pitch limits. Ground aim states consume normalized movement velocities through
the existing physics path. The normal camera receives a desired orbit point
before its original scenery solver; final camera positions are not overwritten.

Input collection retains the existing controller/SI sample boundary. Mouse
motion is consumed once, while held stick input remains a rate. Experimental
v3 recordings capture movement and look together, including the look mode;
v1/v2 recordings remain stock. The runtime experimental switch gates both live
input and replay extensions. Consult the
[JFG reference review](reference-review-2026-10-01.md) and
[catalog](reference-catalog.json), especially the controller and camera entries.

Acceptance should cover simultaneous movement, strafing and aiming; all three
characters; Normal and Expert schemes; diagonal movement and stick drift;
aim transitions; menus, cutscenes, pause and focus loss; controller reconnects;
and independent player assignments. Return from settings must not leave firing,
movement or camera input held. Verify feel in actual gameplay as well as input
mapping, with sensitivity checked across supported frame rates.

## Other adaptation candidates

| Candidate | Perfect Dark reference | JFG adaptation boundary |
| --- | --- | --- |
| Wider controller support and adjustable rumble | [Input backend][pd-input] | JFG currently uses XInput on Windows. Preserve port assignments and reconnect behavior when adding another backend. |
| Persistent input and enhancement settings | [Configuration source][pd-config] | Reuse the separation of settings and behavior; integrate with existing JFG profiles and frontend persistence. |
| Screen-shake strength and crosshair size/color | [Configuration documentation][pd-settings] | Add explicit JFG options after identifying the relevant camera and reticle behavior. |
| Field of view and HUD placement | [Configuration documentation][pd-settings] | Adapt per gameplay camera and viewport; preserve scripted cameras and split-screen layout. |
| Texture filtering, antialiasing, VSync and frame cap | [Video source][pd-video] | Use corresponding RT64 capabilities and JFG timing constraints; Perfect Dark's renderer code is not interchangeable with RT64. |
| Intro skipping and mouse interaction in game menus | [Configuration documentation][pd-settings] | Requires JFG guest-menu and startup integration. Mouse support in the launcher does not supply this. |
| Optional asset overrides | [File lookup source][pd-fs] and [modding documentation][pd-modding] | Establish JFG resource identities and formats first. Perfect Dark's documented texture replacement limits do not establish unrestricted HD texture support. |

The current JFG checkout already provides frontend fullscreen, live volume and
mute, pause when inactive, player assignments, controller remapping, and
deadzones. Extend these [existing frontend features](../development/launcher.md)
when implementing the candidates above.

Perfect Dark's experimental high frame rates require game-specific timing
fixes, and its network play belongs to a separate branch. Neither is a small
portable addition to JFG. See its [feature and branch descriptions][pd-readme].

## Local validation (2026-10-08)

The Release runtime and native RmlUi launcher compiled. The 67 PC input checks
passed, as did existing controller mapping and controller-port/SI checks.
A private Direct3D11 frontend harness checked menu routing, Normal/Expert
presets, independent player persistence, mouse-side-button rebinding,
sensitivity persistence, scrolling and restoring keyboard/aim defaults.
Additional tests cover disabled defaults, saved opt-in/out, locked settings,
retained per-player settings, and direct modal access while disabled. Mouse
checks cover fractional displacement at low sensitivity and clearing motion.
The actual rendered settings page was reviewed and its slider styling fixed.
The final paired preview rebuild also passed 539 managed launcher and 12
setup checks. The level-orbit replay rotates the camera using mouse and stick
input while leaving Juno in place, then holds steady when input stops.

The paired local preview is in `build/pc-input-launcher/`. No gameplay feel,
all-character behavior or complete camera/weapon compatibility is claimed by
these tests alone.

## Supported-US integration and qualification boundary

The retained generated-code observations identify manual aim at 0x8003AABC,
raw look globals 0x800F6DB4 / 0x800F6DB8, aim yaw at control +0x11C,
and aim pitch at +0x1E2. Original raw movement inputs are restored after
manual aim; modern ground aim states 10/11 use local forward/side velocities.
Other movement states, including special actions, retain original movement.

Normal third-person orbit is scoped to 0x8002CF6C. The call to 0x800446E4
at 0x8002E158 occurs after its desired camera point is computed and before
the scenery constraint path, including 0x8002CC70. Runtime checks qualify the
routine signature, owning stack and saved actor before supplying that point.
Cutscenes and other camera routines remain on their original paths.

Private native replay evidence records direct mouse angles without stick
acceleration, simultaneous movement and independent look, and both mouse and
stick orbit. The disabled experiment executes neither extension hook and
matches the stock player and camera state in the same scene. These are narrow
gameplay checks on the retained save, not complete campaign acceptance.
The original save is hashed before and after every replay and remains unchanged.
Generated game code, RAM captures and save fixtures remain private.

The retained qualification scene uses Juno (character 1), not Vela. A native
pause/resume replay verifies that the look hook stays inactive in the pause
menu and resumes without queued deltas. Four shots reach the guest weapon
path while the modern stick controls aim. Replaying the captured v3 input
reproduces the actor, aim and orbit event timelines exactly.

The normal camera now retains a small inward clearance when the existing
scenery solver shortens its line of sight against a wall; floor and ceiling
corrections are preserved. A steep-angle tree test exposed scenery occlusion,
so this remains a known camera qualification gap, not a collision-parity claim.
The retained steep-angle replay did not produce a scenery contact requiring
retreat; the new contact-clearance arithmetic is covered by unit checks, while
its wall-contact gameplay behavior remains unqualified.

## Execution requirements

Before further execution, recover the production ledger,
verify that its guard is enabled, and recover the existing investigation state
and remaining budget before any coding-worker, experiment, build, or replay
job. Follow [AGENTS.md](../../AGENTS.md) and the
[production guard contract](../planning/autonomy-progress-guard.md).
Do not create a replacement ledger, reset counters, rename an investigation
for fresh allowance, or execute directly after a denial.

The operational ledger was subsequently located in the sibling
`../Jet Force Gemini Recomp/tools/private/autonomy/jobs.sqlite`. Its production
guard was enabled. The bounded `pc-input-aiming-20261008` investigation used
that ledger and the guarded supervisor, preserving existing investigations
and counters. The owner's explicit "approved 60 more min" extended that same
active investigation by 3600 seconds, retaining all prior charges and an audit
receipt. The guard stayed enabled; this memo grants no further allowance.

[pd-repo]: https://github.com/perfect-dark-pc-port/perfect_dark
[pd-readme]: https://github.com/perfect-dark-pc-port/perfect_dark/blob/32a1cb9f268dd3ac73016801025c6bbbfa20130f/README.md
[pd-license]: https://github.com/perfect-dark-pc-port/perfect_dark/blob/32a1cb9f268dd3ac73016801025c6bbbfa20130f/LICENSE
[pd-input]: https://github.com/perfect-dark-pc-port/perfect_dark/blob/32a1cb9f268dd3ac73016801025c6bbbfa20130f/port/src/input.c
[pd-input-h]: https://github.com/perfect-dark-pc-port/perfect_dark/blob/32a1cb9f268dd3ac73016801025c6bbbfa20130f/port/include/input.h
[pd-movement]: https://github.com/perfect-dark-pc-port/perfect_dark/blob/32a1cb9f268dd3ac73016801025c6bbbfa20130f/src/game/bondmove.c#L806
[pd-config]: https://github.com/perfect-dark-pc-port/perfect_dark/blob/32a1cb9f268dd3ac73016801025c6bbbfa20130f/port/src/config.c
[pd-video]: https://github.com/perfect-dark-pc-port/perfect_dark/blob/32a1cb9f268dd3ac73016801025c6bbbfa20130f/port/src/video.c
[pd-fs]: https://github.com/perfect-dark-pc-port/perfect_dark/blob/32a1cb9f268dd3ac73016801025c6bbbfa20130f/port/src/fs.c
[pd-settings]: https://github.com/perfect-dark-pc-port/perfect_dark/wiki/Config-variables
[pd-modding]: https://github.com/perfect-dark-pc-port/perfect_dark/wiki/Modding

The final stationary full-orbit replay traversed all eight 45-degree sectors,
then held steady at neutral input. Juno stayed in place. The scenery solver
ran throughout; this fixture produced no inward-clearance updates.
