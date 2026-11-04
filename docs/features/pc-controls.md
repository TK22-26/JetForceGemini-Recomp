# PC controls

The launcher offers original N64 mapping and optional Modern Controls. v1.4.0 supports Modern
controls for P1-P4 with independent devices, bindings and camera preferences. Original mapping
remains available for every port. Broader physical-controller and multiplayer qualification continues;
see [known issues](../known-issues.md).

## Assign a device and choose a style

Open **Controllers**, choose P1-P4, and use **Add device** or **Change device**. Connected devices
already assigned elsewhere are excluded. An unplugged device retains its bindings; **Remove**
disconnects the player without erasing them. Switching styles preserves both layouts.

- **Controller Mapping** binds physical inputs to N64 controls. Match its Normal/Expert preset
  to the game's own Control Mode; changing the launcher preset does not change the game's save.
- **Modern Controls** binds gameplay actions. Selecting it enables the style immediately.
  Original mapping is the default when no Modern profile exists.

## Default Modern bindings

| Action | Keyboard and mouse | Xbox / DualSense |
|---|---|---|
| Move / strafe | WASD | Left stick |
| Look | Mouse | Right stick |
| Aim / fire | Right / left mouse | LT / RT; L2 / R2 |
| Jump | Space | A / Cross |
| Crouch | Ctrl | B / Circle |
| Interact | E | X / Square |
| Previous / next weapon | Wheel down / up | LB / RB; L1 / R1 |
| Sniper magnification | Middle mouse while scoped | Right-stick click while scoped |
| Pause | Tab | Menu / Options |
| Menu select / back | E / Q; right-click also goes back | A / B; Cross / Circle |

Use the input diagram or **Keys & buttons** to rebind. Five mouse buttons, wheel directions,
keys, pad buttons, triggers and stick directions are supported. Release held inputs before capture;
Escape, focus loss or device loss cancels it. Escape and F11 retain launcher shortcuts.

Modern ground movement normally strafes relative to the camera. Aim can be held or toggled;
jumping while aiming retains the reticle and scope through takeoff and landing. Release Aim to
leave the aim camera; leave aim before crouching. Native jump motion and collision remain active.

## Sensitivity, rolling and Floyd

Camera, aiming and scope sensitivity are independent, with X/Y inversion and vertical scaling.
Controllers add movement/look deadzones and response curves. Saved choices survive reconnection.
Capture releases for focus loss, settings, guest pause and cinematics; reconnection requires neutral input.

Juno and Vela can roll sideways from crouch/crawl. **Roll Left/Right** are optional unbound actions.
**Automatic movement rolling** defaults On; turn it Off to keep only explicit roll buttons.
Manual rolls retain native posture gates, opposing directions cancel, and Lupus cannot roll.
See the [roll investigation](../development/issues/github-modern-controls-side-roll.md).

In Floyd missions, mouse movement steers; W supplies thrust, S brakes, A/D strafe and left-click
fires with default bindings. Controller **Invert Floyd flight steering** is independent of normal
look inversion and defaults to the original aircraft direction. Co-op Floyd joins through the
assigned player's Start/Pause action. Native mission entry requirements, including tokens, still apply.

## Native menu navigation

P1 Modern mouse input supports title choices, save-slot selection and starting a selected save,
main pause icons, pause Options icons and character-selection arrows. Targets follow the game
viewport and exclude black bars. The first click after returning from another application activates
the window without also issuing gameplay input.

Movement keys navigate menus, E selects and Q/right-click goes back. E on the map retains travel
confirmation. Nested settings, copy/erase, naming and dialogue are not a complete mouse interface;
use directional input for unsupported pages. Explicit remaps remain supported.

## Current develop additions: unreleased

**Advanced > Free movement by default** lets movement turn the character while the mouse/right
stick controls the camera independently; aim temporarily restores Modern aiming. **Toggle movement**
is assignable and starts unbound. **Combat transparency** can disable ordinary aim/combat fade while
retaining camera-proximity fading. These per-player preferences are shared across Modern device types;
profile schema 8 migrates schemas 1-7 without discarding bindings.

The local batch also maps configured Fire to Floyd objective pages while paused and adds arcade
boost/trap/brake actions. These changes have automated coverage and retain their individual owner-review
status: [free movement](../development/issues/github-modern-free-movement.md),
[transparency](../development/issues/github-combat-player-transparency.md),
[Floyd objectives](../development/issues/github-floyd-objectives-controls.md), and
[arcade traps](../development/issues/github-arcade-trap-controls.md). They are not v1.4.0 release claims.

## Compatibility and evidence

Original `controller.ini` / `pc-input.ini` mappings remain independent of `modern-controls.ini`.
Keep profile backups when moving between builds with different schema support. XInput rumble is
available; native SDL/DualSense rumble, gyro and adaptive triggers remain future work.

[Implementation and historical qualification](../development/runtime/modern-controls.md) separates
code design and original-ROM comparison from these instructions. [Issue records](../development/issues/README.md)
retain failed experiments, source identities, reported regressions and actual verification limits.

## Current local camera corrections

The v33 replacement starts the Modern Aim return gently, separates authored
position changes from obstacle recovery, and clears old recovery when native Aim
owns the camera. The owner confirms natural scope-in and smooth scope-out on
PAL/controller. All three versions pass the targeted native checks; USA/JP still
await manual verification. The local v33 build is unreleased. See the
[Aim-release record](../development/issues/modern-aim-release-camera-snap.md).
The owner accepts the separate [backward body-tilt correction](../development/issues/pal-modern-backward-body-tilt.md)
on PAL with a controller. These local results are not v1.4.0 release claims.
