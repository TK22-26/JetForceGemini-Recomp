# Floyd widescreen aiming bounds

- Status: original outer limits confirmed in EmuHawk at 4:3 and widescreen; Modern mouse matches. No widescreen bounds defect found; no bounds change.
- Severity: original gameplay restriction. The separate Modern controller diagonal correction is in preview3, pending owner verification.
- Build: Modern Players and Floyd preview 2, runtime c16099ba8960efa8da60d9831788dbc9dcd9e36444552dbd6cb96104b550b37e.
- Reproduction: join Floyd as P2, use Modern look toward screen edges in widescreen. Owner says Floyd cannot cover the whole screen after confirming vertical direction works.

Original 0x80031090 clamps stick input to +/-65 and smooths reticle offsets toward +/-80. This source observation suggests deliberate limits but does not itself prove displayed widescreen parity. Compare original EmuHawk 4:3/widescreen, reticle offsets and screenshots, then the same native consumer and current Modern adapter. Preserve source settings/save; private copied fixtures only. No implementation approved for bounds.

Evidence: D:/JFG-private/floyd-bounds-20261021. Production guard retained; owner approved one hour of comparison, reporting before any bounds change.

First native comparison passed axis endpoints but failed its assumption that a full Modern controller diagonal must reach both square corners. Inspection shows radial stick normalization produces a smaller diagonal target. The second fixture separately verifies cardinal limits and records diagonal reach instead of concealing the discrepancy; original failed log retained. This is a distinct shape/response question, not evidence that widescreen changes the original outer limits. No product change.


## Original-game result

EmuHawk 2.11.1, original supported USA ROM, Mupen64Plus cached interpreter,
4 MiB and isolated P2 controller configuration reproduce the restriction in
joined co-op Floyd. A private copy of the owner's saved checkpoint, level43,
was given only the Floyd unlock flag; the 4:3 copy clears the native saved
widescreen bit and updates the original checksum. Personal profile/save are
hash-verified unchanged. No original gameplay-memory patches or ROM changes.

Each direction restores the same joined state. Eight trials per mode cover
left/right/up/down, +/-127 horizontal extremes and diagonals. Held +/-80 and
+/-127 both settle at the same +/-80 reticle offset; stronger input cannot
extend the range. Original native screen coordinates are:

| Mode | Horizontal reticle centre | Vertical reticle centre | Native coordinates |
|---|---|---|---|
| 4:3 | x=80..240 (middle 50%) | y=40..200 (middle two-thirds) | 320x240 |
| Widescreen | x=80..240 (middle 50%) | y=40..200 (middle two-thirds) | 320x240 before widescreen presentation |

Both modes deliberately clamp the input axes to +/-65 and scale the settled
reticle offsets to +/-80. This is direct code behavior and original-game
reproduction, not a claim about an undocumented designer rationale. The game
retains a 320x240 source coordinate system in widescreen; displayed stretching
or VI cropping must not be mistaken for a larger aiming envelope. Screenshot
reticle centres agree with the measured endpoints; sprite edges extend beyond
the centre and are not the aiming limit.

## Preview comparison

The owner's accepted preview2 capture uses the same widescreen mode and source
dimensions. Its 1,131 Modern Floyd input records reach both -65 and +65 on each
axis. The current production mouse/controller adapter was then run through the
unaltered original generated reticle and dimension routines, using the two
EmuHawk snapshots. All64 cases execute both generated paths; 7,826 checks pass.
Mouse reaches the same square limits and both devices reach the same cardinal
limits. No installed native game was driven or relaunched during the owner's
separate Juno review. This adds native-consumer comparison and recorded mouse
targets, not a new physical-controller or full GPU preview replay.

The first native comparison exposed a separate controller diagonal difference:
at default sensitivity the normalized right stick produces target +/-46 on a
full diagonal, giving offsets +/-56.615, while mouse can reach +/-80 corners.
EmuHawk confirms raw diagonal65 reaches +/-80; raw56 reaches +/-68.923 and
raw46 reaches +/-56.615. See the [separate controller record](modern-floyd-controller-diagonal-range.md).
The initially failing test is preserved; no universal input-parity claim.

Recommendation: preserve the original outer bounds. Extending mouse aim to the
screen edges would change the original gameplay. Review controller diagonal
mapping separately before implementing a change. No gameplay code, preview
binary, personal settings, commit, release or public issue changed here.
Full Floyd mission completion and physical controller gate behavior remain
outside this co-op bounds result.

Private evidence: `floyd-bounds-20261021/summary.json`, original-first and
original-standard bounds.json/checkpoint PNGs, owner-trace-bounds.json,
native-bounds-v2/bounds.csv and original-diagonals/results.json. Source original
consumer 0x80031090, input clamps0x80031138..0x80031180, offset scaling
0x80031198..0x80031228, dimension getter0x80054EA0. Production adapter:
[pc_input.hpp](../../../include/jfg/runtime/pc_input.hpp), `PcFloydLook`.

Lesson: distinguish the original aiming envelope, the shape produced by a
controller mapping, and final display aspect. Equal cardinal endpoints alone
do not establish equal corner reach. Keep owner-accepted direction separate
from range and mission qualification.

After reporting the original bounds, the owner approved the separate controller correction. Preview3 now maps circular stick travel onto the original square reticle before per-axis gains/inversion, passing cardinal/corner tests without extending the native outer limits. See the linked controller record; live controller acceptance remains pending.

Latest preview3 owner capture has3,858 Modern Floyd target events and reaches +/-65 on both axes, including corners. Owner confirms mouse can reach corners; unchanged mouse feel is expected because preview3 only changes controller diagonal shaping. [HUD layering](floyd-reticle-ammo-hud-layering.md) separately reproduces original behavior with the software renderer; no wider mouse envelope is indicated.
