# GH-049: [Playtest] With Modern Controls can't view objectives during Floyd Challanges

Status: fixed in develop; owner confirmed 2026-11-08; component and actual native handler verified; unreleased.

Source: [[Playtest] With Modern Controls can't view objectives during Floyd Challanges](https://github.com/TK22-26/JetForceGemini-Recomp/issues/49). Evidence snapshot retained privately in D:/JFG-private/remaining-gh-issues-20261027/github-issues.json.

## Current resolution and owner acceptance

On November 8 the owner explicitly confirmed **#49 is fixed**. Modern controls
now recognize Floyd's paused-objective screen and route the configured Fire
action to native Z there, allowing the objective pages to cycle. The corrected
sampling gate also honors remapped Fire bindings; ordinary menus retain their
existing suppression behavior.

This accepts the fix and removes #49 from the current manual-test queue. The
confirmation does not specify region, platform or individual bindings, so no
additional device/region coverage is inferred. Earlier component/native checks
and intermediate failures below retain their recorded scope. Release delivery
and any GitHub issue disposition are separate from this acceptance.

## Reported symptoms and reproduction

### Problem type

Controls

### Launcher and game build

1.4.0 Release build

### Windows version, GPU, and input device

Windows 10, GTX 1080, XBOX Controller

### What happened and how to reproduce it

When pausing during a Floyd Challenge, it is not possible to view the objectives (supposed to be the Z button) with Modern Controls.

### How often does it happen?

Every attempt

### Support ZIP and additional details

_No response_

## Scope and evidence

Local owner-authorized batch: trace native Z input in paused Floyd challenges. Preserve existing approved fixes, user profiles and ROMs. No GitHub posting or issue changes. A reported symptom is not yet a confirmed cause. Attempts, results, final remedy and verification limits will be recorded here.

## October 27 local candidate

Native robotPauseUpdate (module 22 +0x2A34) cycles objectives with a Z press at +0x2B14/+0x2B48. Its separate pause screen was not decoded; Modern menu input suppressed Fire. Candidate recognizes the loaded module and active objective page, routing configured Fire to native Z only there. Default RT / left click; ordinary menus keep Fire suppressed.

Status: implementation candidate; component and native verification pending.

Verification: 209 Modern control checks; navigation and menu checks; 48 actual robotPauseUpdate cases: old suppression reproduced, candidate cycles all three pages across physical ports and timing-span modes. Owner live batch review pending; unreleased.

## Remapped mouse-button review

The first candidate's native menu mapping accepted configured Fire, but its
keyboard sampling gate exempted only left click. That would block Fire remapped
to right click. The gate now checks the actual Fire binding and keeps other menu
clicks suppressed. Regression checks use the real keyboard sampler and native-Z
mapping for left click, right click and a keyboard binding. All 231 Modern-control checks pass, including the new remapped-input cases, on Windows and Linux. The final native executable rebuild and ordinary Play/close pass. Owner gameplay review remains pending.
