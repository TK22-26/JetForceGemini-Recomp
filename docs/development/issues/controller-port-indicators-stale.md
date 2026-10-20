# INPUT-013: Player port indicators stay stale after controller changes

## Owner acceptance (2026-10-20)

The owner approved all changes in the Modern Roll Direction Preview and requested
commit and push to `develop`: "approved on all - commit and push to develop".
This accepts the roll bindings and automatic-roll preference, prone-roll direction,
and live P1-P4 indicators. Earlier backward-crawl and controller reassignment fixes
remain owner-confirmed. The preview runtime is
`a26006f13c507dd4601461308ce43153d98d6eb90ca104685fce2ac130dee154`;
launcher is `4bff11b4c8145925f948f563dec573f46d382c1d622da36a0e0b0e488ba956f3`.
Acceptance supersedes earlier pending-preview statuses below. This is an accepted
development change, not a release or a claim of exhaustive hardware/collision
coverage. Automated evidence and its limits remain unchanged.

The owner separately approved one bounded ten-minute guard continuation solely
for acceptance records, commit and push. The production guard, investigation root,
cumulative seconds cap and existing counters are retained; no new gameplay
investigation is authorized.


## Tested preview candidate (2026-10-20)

Desktop shortcut: **JFG - Modern Roll Direction Preview**.
Package: `C:\JFG-previews\modern-roll-direction-20261020`. Runtime SHA-256 `a26006f13c507dd4601461308ce43153d98d6eb90ca104685fce2ac130dee154`;
launcher SHA-256 `4bff11b4c8145925f948f563dec573f46d382c1d622da36a0e0b0e488ba956f3`. Startup protocol and the actual
packaged launcher's extracted helper init/setup passed. No gameplay was launched.
The accepted previous preview, settings and saves remain intact; copied profile
hashes were verified. Ctrl, inversion and existing bindings remain unchanged.
New work awaits owner live verification and is unreleased. Earlier backward-crawl
and controller-assignment fixes remain owner-confirmed.

## Cause, remedy and verification

The toolbar polled connected hardware but cached mapping/exclusion snapshots
until game start. Separate controller-window saves therefore left indicators
stale. `refreshControllerAssignments()` in `launcher/ui/native_ui.cpp` uses
existing AsyncConfigFiles background snapshots for five bounded 8 KB assignment/
policy files at roughly 250 ms intervals. Valid changes preserve sticky identity
reservations. The active controller editor and Modern editing state are excluded;
no per-frame/game-thread disk reads were added.

The exact idle-add regression fails on both original and coherent peer baselines.
The candidate passes 305 mapping, 839 Modern UI and 55 menu-input checks. Tests
cover add/remove/reconnect, persistence, player isolation and invalid saves.
Coherent peer UI-008 runtime changes were preserved. Stale hash attempts 204-206
stopped without source edits. Fake discovery and offscreen pointer tests do not
replace a real-controller desktop acceptance check. Recheck P1-P4 after saving
add/remove/type changes while the game remains stopped. Source/cache invalidation
must be tested separately from hardware discovery in future assignment changes.

Evidence: `D:/JFG-private/modern-prone-roll-20261020/controller` and `delivery.json`.

- Status: Preview correction owner-accepted; unreleased.
- Severity: stale launcher status; no save-loss or gameplay-input failure reported.
- Affected preview: assumed Modern Input Fix Preview, launcher SHA-256
  `25710daa68b3d66b53b4e8d5e0a824f53735b24a139a901a0b8689040bb24697`.

## Reproduction and evidence

The top P1/P2/P3/P4 indicators do not change after adding or removing controllers.
They refresh only when the game is loaded. The owner explicitly distinguishes
stale assignment indicators from a player-selector click failure. Screenshot:
`modern-prone-roll-20261020/owner-port-indicators.png` (retained private evidence).
The owner confirmed the separate controller-assignment follow-up fixed; preserve
its released-pad exclusion and saved profile behavior.

## Investigation

Cause and remedy unconfirmed. Compare device discovery, saved assignment changes
and toolbar refresh while idle, without requiring gameplay startup. Preserve
player selection, physical identity, custom bindings and accepted assignment fix.
Private evidence: `D:/JFG-private/modern-prone-roll-20261020/controller`.
The existing enabled production guard/root/counters remain in force under the
owner-approved single additional attempt ending 18:09:13 UTC; no time added.
No runtime or live verification claimed for this new report yet.
