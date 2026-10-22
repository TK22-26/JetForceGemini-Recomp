# Give Floyd: SS Anubis mission pad cannot be activated

- Status: missing native entry requirement confirmed: current character has zero Mizar tokens; owner retry after collecting a token pending. No pad/input fix indicated by this evidence.
- Severity: blocks owner qualification of Floyd missions and #37 firing remedy.
- Build/profile: Modern Players and Floyd preview4; runtime ede714b70ed68f2bd3051969f68b2259652f8d9c660c1f98c49ffad57865de5b.
- Reproduction: use Give Floyd, change rooms (owner confirmed), reach SS Anubis mission pad; owner cannot interact.
- Initial evidence: live map has level131 and a SidekickPad actor; player stands near its position. Give Floyd currently grants current-game flag3 only. Pad eligibility, grant acceptance, required input and native state remain hypotheses; no diagnosis/fix accepted.

Private evidence: D:/JFG-private/floyd-pad-access-20261021. Active capture20261021-211753-c9aa58c3da44407ebee957c896bc3269 is still running; do not treat its unflushed files as completed recording or manipulate the owner's game. Related [Floyd report](github-floyd-cannot-fire.md), [Give Floyd](../../features/navigation-mod.md#give-floyd-local-candidate-2026-10-21). No mission-completion claim.

## Confirmed activation blocker

A read-only snapshot of the owner runtime shows level131, character1, a valid attached Floyd pointer, clear secondary eligibility byte, full player health and a position within the pad's32-unit radius and25..57 height interval. The pad remains idle and its nearby indicator is set. Give Floyd succeeded: the sidekick is present and current-game flag3 is set.

The active character has zero Mizar tokens at current-game character inventory+0x12. Original sidekickpadControl0x01600404..0x01600420 requires a positive token count for this kind1 pad (kind5 is the separate exception);0x01600794..0x016007A0 consumes one token when the mission starts. The live map also identifies collectible Mizar tokens nearby. This is a missing original entry requirement, not evidence that the Give Floyd flag failed. The grant deliberately changes only the Floyd unlock, not currency.

Next action: collect a nearby Mizar token and use Interact (current Modern M/K binding E) while standing on the pad. Mission firing/completion remains unverified until the owner enters and tests it. No runtime/save changes made for this diagnosis. Evidence: live-gates.json, token-gate.json and private native instruction extracts under D:/JFG-private/floyd-pad-access-20261021. The source search initially used generated section022, which is guest overlay23; retained rejected extract was corrected to section021/guest overlay22 and matched the actual0x016002A4 entry. The memory read was not atomic, but pad/character/room values were consistent with the live map.

Transferable lesson: a character unlock does not satisfy all native minigame costs or eligibility conditions; verify the active character's inventory and the original interaction handler before changing bindings or progression.

Owner subsequently entered the Floyd minigame and reported flight-control behavior. The entry blocker is cleared for this test; the separate mission-control issue remains open.


## Final owner disposition for v1.4.0 (2026-10-21)

The owner states that #37 and the associated Floyd work are fully approved
locally and requests reporter verification after delivery. This supersedes the
earlier local acceptance gates above without inventing additional measured routes
or hardware coverage. The combined v1.4.0 package still needs the requested
SS Anubis final pass. No publication or public reply is implied.
