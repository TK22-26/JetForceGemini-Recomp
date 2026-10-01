# Phase 9 Goldwood HUD and renderer diagnostic

## Reported route

The recorded Phase 9 Goldwood run reached the first section, died and
respawned, then continued into the lower enemy-heavy area. After respawn the
health instrument was visibly corrupt and appeared to drain periodically. The
starting-pistol ammo count was also reported to disappear until more ammo was
collected. The process later stopped during combat.

Windows event records showed that the earlier Windows Terminal failure was an
independent `Windows.UI.Xaml.dll` crash. The hidden game watchdog and input
recording survived long enough to retain the complete controller route.

## Renderer failure

Exact replay reproduced a fail-closed RT64 rejection. A direct F3DDKR display-
list command at snapshot address `0x0021d090` contained `0x00c01b18`. JFG uses
4 MiB RDRAM, so the original RSP resolves that alias to `0x00001b18`. The
private RT64 snapshot is 8 MiB; retaining the wider alias selected
`0x00401b18`, crossed into the materialized overlay aperture at `0x00401c80`,
and interpreted overlay code as graphics commands.

The repair is intentionally route-specific: only the observed unchanged
`G_DL` edge is normalized. Configured segmented display-list commands retain
the prior materializer behavior, and materializer-owned upper-aperture
addresses are not wrapped a second time. A focused test binds both the rejected
alias and preservation of an intentional upper-aperture translation.

An early implementation rewrote every translated display-list command and
caused simulation/audio to advance without a presentable framebuffer. Startup
validation caught this because `presented_frames` remained zero. Restoring the
old configured-segment write rule produced live presentation again (369 frames
within the first 750 retraces of the replacement manual run).

## Health and ammo instruments

Generated section 6 owns the health meter and shared instrument/message state.
Its generated lifecycle inventory permits load, unload, and reload, but the
native synthetic-overlay publisher previously treated every already-active
publication as an `ensure_active` operation. That preserves mutable data and
BSS across a genuine death/respawn module reload.

The current implementation distinguishes an ordinary call from a genuine PI
module load. To avoid treating unrelated reads of the same ROM range as module
loads, mutable state is reset only for section 6, only after the observed death
counter advances, only when the PI destination resolves to the base of the
matching live runlink module, and at most once per death generation.

This is a code-supported cause for the corrupt health instrument and may also
cover the disappearing ammo display because both symptoms involve instrument
state. The ammo relationship remains a hypothesis until the paced manual route
confirms the starting count, pickup transition, and post-respawn state.

## 2026-09-01 correction

The route-specific repair above did not hold. Replaying the recorded route
with the committed binary reproduced the same rejection, and the failing
task's RT64 snapshot showed that `0x00C01B18` is a pointer into generated
overlay section 12's `.data` (section N is linked at N MiB), whose shadow
holds a complete display list, while `0x00001B18` is main-program code. The
address needs the ordinary overlay-shadow translation, which the
materializer computed but did not write for direct display-list edges with a
configured segment. The narrowed special case has been removed and the write
rule corrected; the full route now completes. Details and evidence are in
`phase9-hardening-audit.md`.

## Remaining acceptance

- Complete the paced Goldwood run with live input logging.
- Check starting-pistol ammo before the first ammo pickup and immediately after
  pickup.
- Die and retry, then check health and ammo instruments.
- Re-enter the enemy-heavy lower section and confirm that the prior renderer
  rejection does not recur.
- Replay the final recorded route with the narrowed display-list repair and
  retain the deterministic checkpoint result.
