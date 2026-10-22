# GH-039: Give all weapons leaves the inventory unchanged

## Delivery and issue status — 2026-10-22 UTC

The expanded Give weapons behavior ships in v1.4.0. Paused-dialog grant acknowledgement and inventory access passed owner testing. #39 is closed with the approved request to double-check the new version and comment if it still fails; earlier duplicate-click/UI limits remain documented.

[Release v1.4.0](https://github.com/TK22-26/JetForceGemini-Recomp/releases/tag/v1.4.0); [verified issue action](https://github.com/TK22-26/JetForceGemini-Recomp/issues/39#issuecomment-6332078068).
Earlier entries below preserve their original investigation and verification scope.

- Severity: medium; optional mod functionality.
- Status: reproduced in official v1.3.0; source candidate passes paused-game
  integration and component checks; owner confirms the actual UI grant. Reporter retest and release pending.
- Reported and investigated: 2026-10-21 UTC.
- Source: [GitHub #39](https://github.com/TK22-26/JetForceGemini-Recomp/issues/39),
  reported by @marvin-SL on JFG-1.3.0-windows-x64 using keyboard/mouse.
- Related: [navigation mods](../../features/navigation-mod.md) and
  [launcher](../launcher.md#live-map-mods).

## Symptoms and reproduction

The reporter says Give all weapons adds nothing on every attempt. They also ask
why the action is under Live map settings. Placement is a separate design question;
this repair does not relocate it. No support ZIP, character, room or exact waiting
time was provided. We reproduced a concrete failure matching the symptom, without
claiming access to the reporter's exact session.

In active single-player gameplay with missing weapons, open Live map Settings /
Mods, choose Give all weapons, and leave the settings window open for more than
five seconds before returning to the game. The released runtime leaves the
inventory unchanged. A fresh request consumed promptly succeeds.

## Actual cause

The launcher pauses gameplay while its Mods dialog is open. The launcher writes
the request immediately, but v1.3.0 only consumes it from gameplay updates. The
request expires after five seconds of wall-clock time. Remaining in the dialog
therefore guarantees rejection on resume. The old launcher only reported that it
had requested the grant; it did not distinguish runtime acceptance from rejection.

Two captured native inventories have valid, positive capacities for all fifteen
weapons. Production grant code applied fresh requests to both copied memory
images and rejected expired requests unchanged. No capacity or inventory-layout
workaround is indicated by this evidence.

## Candidate remedy

The native game thread now services explicit inventory requests while paused,
without updating simulation, AI, movement, health, enemy kills or room transitions.
The ordinary grant path and its nonce, room generation, freshness, player,
single-player and inventory checks remain intact. Give Floyd shares that request
delivery path; this investigation's full paused runtime reproduction covers weapons.

The runtime exports the consumed weapon-request nonce and whether it applied.
The launcher matches that acknowledgement to its own request and reports success,
rejection or lack of confirmation. Submission alone is never presented as success.
A successful action still grants only the current character, once, with ammunition
up to that character's existing capacities. Normal in-game saving remains required.

Source: src/boot/native_boot.cpp, include/jfg/mod/navigation_mod.hpp,
launcher/windows/NativeLiveTools.cs, launcher/windows/NavigationMap.cs and
launcher/ui/live_tools.hpp. Native and launcher regression checks cover the change.

## Attempts and results

| Date | Check | Result |
|---|---|---|
| 2026-10-21 | Read report and trace launcher/modal/native command paths | Found simulation pause versus five-second request expiry |
| 2026-10-21 | Production grant on two copied captured inventories | Ages 0/4999 ms accepted; 5001/12000 ms rejected without mutation |
| 2026-10-21 | First hidden runtime probe in bounded retrace mode | Did not enter the Play-mode pause loop; pause timeout, retained as an invalid reproduction setup |
| 2026-10-21 | Official v1.3.0 hidden Play session with copied save | Eight-second paused request failed, remained failed on resume; fresh retry granted all fifteen weapons |
| 2026-10-21 | Initial candidate measurement | Grant applied, but assertion compared against an older async snapshot. Trace showed pause and grant on the same VI. Retained failure; replaced measurement with stable paused snapshots plus no-tick/no-submit trace checks |
| 2026-10-21 | Candidate hidden Play session with copied save | Grant completed during the eight-second pause; update counter stayed unchanged; resume did not duplicate it; a fresh retry refilled successfully |
| 2026-10-21 | Candidate inventory comparison | Other characters and current-character item flags unchanged; current weapon mask became 0x7fff |
| 2026-10-21 | Native navigation suite | Passed, including all three character inventories, both memory layouts, isolated writes and rejection cases |
| 2026-10-21 | Launcher build and checks | Passed: 685 launcher checks, 28 setup checks, graphics/viewport/storage checks |
| 2026-10-21 | Owner live button review | Confirmed Given acknowledgement and all weapons available after leaving Mods open for at least eight seconds |
| 2026-10-21 | Build preparation failures | Initial edit attempts hit CRLF and older isolated source; backups retained. Generated normalizer identity differed only by CRLF/LF. Restored the exact previously qualified bytes in the private build; manifest and validation unchanged; Release build passed |

## Evidence and limits

Private evidence directory: D:/JFG-private/gh39-give-weapons-20261021.
Baseline: official130-paused-grant-play/result.json.
Candidate: candidate-paused-grant-verified/result.json.
Additional evidence: request-age-reproduction.json, captured-inventory.json,
normalizer-identity.json, normalizer-resolution.json, navigation-mod-tests.log
and launcher-build.log. The copied-save source hash was unchanged.

The integration test uses actual runtime Play-mode pause and command protocols,
a hidden muted window and the copied save. It does not simulate a visual click on
the new launcher button. The owner subsequently verified that complete UI flow and weapon availability.
Reporter retest and release packaging remain pending. Actual in-game save/reload
was not part of this focused verification; normal save behavior is unchanged. No public comment,
issue closure, commit or release is claimed.

## Guard and historical status

The first issue review recorded an unreproduced report while the navigation
investigation was shelved. The owner subsequently approved one additional hour.
The trusted supervisor reopened the same investigation/root with all counters
preserved and the production guard enabled. Tests use copied saves only; no live
preview or user save was replaced.

## Transferable lesson

A frontend that pauses simulation must provide a safe game-thread path for explicit
commands meant to work in that paused UI. Increasing command lifetime would only
hide the delivery problem. Keep bounded request validation and acknowledge actual
application independently of request submission.

### Adjacent Mods presentation review (2026-10-21)

The owner-requested [Mods layout candidate](live-map-mods-layout.md) preserves actual runtime acknowledgement. Its pending button state starts when helper feedback arrives. Read-only review also identified existing limitations outside the layout change: rapid clicks before that feedback can enqueue multiple requests, and local command-file write errors or unprefixed bridge validation notices may only appear in the map status behind the dialog. These remain open; no reproduction or repair is claimed here. Preserve request identity and explicit failure feedback when extending the action protocol.
