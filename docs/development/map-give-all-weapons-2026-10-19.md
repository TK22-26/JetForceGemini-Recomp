# Map action: Give all weapons

Owner requested on 2026-10-19 while investigating GitHub #25 reticles.
Candidate implemented; native component checks and 664 launcher checks pass.
Owner gameplay review remains pending.

Map -> Settings -> Mods contains a one-click Give all weapons action. It grants
the current single-player character all 15 ordinary weapons, fills their ammo
to existing capacities and updates the native owned-weapon count. It retains
capacity/power upgrades, equipped weapon, other characters, health, quest flags
and progression. It does not continuously replenish ammo. Saving the game keeps
the changed inventory; the UI says so beside the action.

The native pickup and selection routines establish saved-player ownership at
+0x0a, ammo at +0x14 (16 halfword slots), capacity at +0x34, weapon count +0x6f
and selected weapon +0x70. Native initialization already supplies capacities
and power defaults for unowned weapons. All 15 capacities are checked before
any write; malformed or uninitialized inventories are rejected atomically.

A separate JFGWEAPONS1 request binds each click to room, generation, nonce and
a five-second freshness window. The gameplay thread validates the current
player exists in the actor list and rejects menus, death and scripted scenes.
Consumed/rejected nonces cannot fire later. Old runtimes do not advertise this
action, so the RmlUi button stays disabled. Existing JFGMODS1 preferences remain
compatible and unrelated toggles are unchanged.

Validation checks cover both guest byte layouts and all three characters, untouched bytes outside the grant,
ammo consumption after a click, fresh refill clicks, repeat rejection, stale
generation/time, missing player, menus, invalid character and partial-write
prevention. Launcher tests exercise request binding and native bridge dispatch.
No generated code, ROM or personal save is included.

This is an unreleased v1.3 candidate, not a reticle fix.

An initial byte-exclusion test incorrectly assumed swapped guest bytes in both
fixtures. Corrected it to respect each fixture layout; the full native navigation
suite then passed. Runtime and launcher Release builds passed. Unreleased.

The runtime, launcher and helper are staged with verified hashes for the owner's diagnostic preview. Installation is pending the owner closing the running game/launcher; the active profile/save has not been replaced. Gameplay verification remains pending.

Installed into JFG - Tawfret Rain Capture after the owner closed the previous preview. Replaced runtime/launcher/helper hashes and the runtime package manifest were verified, prior binaries retained privately, and all existing top-level save/config hashes preserved. Launcher reopened muted without starting gameplay. Owner gameplay review remains pending; the earlier screenshot correctly showed the unupdated launcher.
