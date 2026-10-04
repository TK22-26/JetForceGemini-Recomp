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
