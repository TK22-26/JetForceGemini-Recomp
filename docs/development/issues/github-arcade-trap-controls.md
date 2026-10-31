# GH-050: [Playtest] With Modern Controls can't use trap items in Jeff's Arcade race

Status: local candidate; actual native racing trap execution verified; owner batch review pending.

Source: [[Playtest] With Modern Controls can't use trap items in Jeff's Arcade race](https://github.com/TK22-26/JetForceGemini-Recomp/issues/50). Evidence snapshot retained privately in D:/JFG-private/remaining-gh-issues-20261027/github-issues.json.

## Reported symptoms and reproduction

### Problem type

Controls

### Launcher and game build

1.4.0 Release build

### Windows version, GPU, and input device

Windows 10, GTX 1080, XBOX Controller

### What happened and how to reproduce it

With modern controls it is not possible to use trap items in the Jeff's Arcade Race from the nightclub, but it is possible to use the boost.

### How often does it happen?

Every attempt

### Support ZIP and additional details

_No response_

## Scope and evidence

Local owner-authorized batch: trace native item input in arcade racing. Preserve existing approved fixes, user profiles and ROMs. No GitHub posting or issue changes. A reported symptom is not yet a confirmed cause. Attempts, results, final remedy and verification limits will be recorded here.

## October 27 local candidate

Native racing uses its own A boost / Z trap inputs. Racing did not have a Modern action context and fell into menu mapping, admitting A but dropping Fire. Candidate routes validated racing sessions through native boost/trap controls and preserves the racing camera; it does not enable character locomotion or aim adapters. Stale multiplayer type outside multiplayer does not select racing.

Status: implementation candidate; component and native verification pending.

Verification: Modern controller/mouse mapping checks; both memory layouts and stale multiplayer/pause/port exclusion checks; Release native build passes. Owner live batch review pending; unreleased.

## October 27 validation update

A private fixture executes the actual native hovershipControl, race input helper and sprintPlayerFire routines with isolated physics/audio/world-spawn dependencies. Across 96 cases, all four player slots and both compiled timing-span modes, configured Fire creates the appropriate native trap (0x278/0x279) and consumes the held item. No input/no item do not spawn; the formerly suppressed menu mapping does not fire. This validates input through native item consumption, not the full physical race. The first fixture omitted the fixed module's 80000400 relocation base and failed before reaching the native Fire branch; correcting that fixture setup passed. Private evidence: native-race/result-042.json. Owner batch review remains pending.
