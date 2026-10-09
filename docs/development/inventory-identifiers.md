# Inventory identifier sources

Labels use the factual bit positions documented by
[Jimmie1717's jfg-z common data](https://github.com/Jimmie1717/jfg-z/blob/64b9f17f1f9194d868a87970897688626de304e6/JetForceGemini/data/common.lua).
The US [offset definitions](https://github.com/Jimmie1717/jfg-z/blob/64b9f17f1f9194d868a87970897688626de304e6/JetForceGemini/data/NJFE0.lua)
corroborate the character-record offsets already read by our runtime.
The project is MIT licensed. No Lua implementation, graphics or ROM assets are
included here. Ship-part ordering also agrees with the pinned JFG decomp enum.

Weapon IDs are ordinary low-to-high bits of the 16-bit ownership mask. In
particular, 4 is Shocker, 7 is Sniper rifle and 10 is Fish Food. Earlier host
labels incorrectly named those and shifted several intervening weapons.
The fifteenth regular weapon is Cluster bombs; the unused Splitter bit is
not presented as a regular collectible.

Character item IDs count high-to-low within each byte starting at record +0x66.
The 16-bit key mask covers IDs 0-15; objects at +0x68 cover IDs 16-31.
Gold-bar numbering consequently runs 3, 2, 1 at IDs 23, 24, 25.
ID 26 is Ear plugs and ID 27 is Arcade chip. Other unlabelled bits remain
unmapped rather than being assigned invented items. New exports include ID 27;
older 27-entry exports remain readable without claiming its ownership.

Shared ship-part flags run 32-43. These are a different namespace from character
item IDs. Names improve inventory and NPC/map descriptions; no ownership or
progression flags are changed.

## Local artwork

The launcher derives weapon HUD sprites and static pickup-model thumbnails from
the user's verified supported ROM. It distributes decoder code and identifier
metadata only. See [the frontend implementation notes](../planning/rmlui-frontend.md#local-image-pipeline-and-provenance)
for the table relationships, cache boundary and current 45-image coverage. The
internal tri-rocket flag has no physical-item tile. Every displayed item has a
verified ROM artwork mapping; extraction failures can still fall back to names.

## Internal flag versus collectible

The pinned jfg-z definition calls the key-mask bit `0x0020` at character-record
`+0x66` `keys.trirocket`. This becomes exported item ID 10. Its name documents a
memory flag; it does not establish a separate physical key pickup. The actual
Tri-Rocket Launcher uses its own weapon-ownership bit (`0x0020` at `+0x0A`).

[The independently authored item guide](https://www.raregamer.co.uk/games/jet-force-gemini-quick-reference-item-guide/)
lists the launcher as a weapon and identifies the five colored keys, with no
separate Tri-Rocket key collectible. Online review on 2026-10-08 therefore supports
excluding ID 10 from the physical inventory grid and its completion count.
The precise trigger/use of that internal bit remains unverified; no new gameplay
meaning is inferred. Its raw export and game/save state are unchanged.

The display now has 15 weapons, 15 keys/quest items, and 12 shared ship parts.
