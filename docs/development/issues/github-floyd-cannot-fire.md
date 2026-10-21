# GH-037: Floyd cannot fire

- Status: reported on v1.3.0; not yet reproduced or investigated.
- Severity: potentially blocks completion of Floyd missions.
- Report: [GitHub #37](https://github.com/TK22-26/JetForceGemini-Recomp/issues/37), 2026-10-20; audited 2026-10-21 UTC.
- Setup: Windows 10; input device, control preset, bindings and exact mission unspecified.

The reporter says Floyd cannot shoot on every attempt, preventing some missions
from being completed. No support ZIP, recording or further comments were attached
at this audit. The reproduction currently consists only of entering a Floyd
mission and trying to fire; the affected mission and control setup need confirmation.

No cause is established. Input routing, bindings and native mission behavior are
possible investigation areas, not findings. No remedy or runtime test was attempted
as part of issue reconciliation. Compare the same mission with Original and Modern
controls, keyboard/mouse and controller, after obtaining the reporter's setup.

Keep this separate from the accepted character boss-aim and sideways-roll fixes.
Ordinary character shooting tests do not establish Floyd mission compatibility.
Record a same-state reproduction and actual mission completion before claiming a
fix. No commit, build or owner acceptance for another issue resolves this report.
