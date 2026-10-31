# GH-052: [Playtest] With Modern Controls the character turns transparent during combat

Status: local candidate; configuration/UI and actual native fade verified; owner batch review pending.

Source: [[Playtest] With Modern Controls the character turns transparent during combat](https://github.com/TK22-26/JetForceGemini-Recomp/issues/52). Evidence snapshot retained privately in D:/JFG-private/remaining-gh-issues-20261027/github-issues.json.

## Reported symptoms and reproduction

### Problem type

Gameplay or progression

### Launcher and game build

1.4.0 Release build

### Windows version, GPU, and input device

Windows 10, GTX 1080, XBOX Controller

### What happened and how to reproduce it

With modern controls the character turns transparent in combat situations even though the camera is zoomed out.

I think an option to turn transparency during combat on or off would be good, in case someone wants to keep it as an enemy indicator.

Also i think an additional option for modern controls where the camera gets behind the character like with classic controls would be good.

### How often does it happen?

Every attempt

### Support ZIP and additional details

_No response_

## Scope and evidence

Local owner-authorized batch: separate native combat fade from proximity fade; add requested setting. Preserve existing approved fixes, user profiles and ROMs. No GitHub posting or issue changes. A reported symptom is not yet a confirmed cause. Attempts, results, final remedy and verification limits will be recorded here.

## October 27 candidate

Added Combat transparency under Modern Controls / Advanced settings. Default On preserves the existing native aim/fire opacity. Off bypasses only the player camera/aim fade API, retaining near-body camera fading and scene/death/other-actor opacity paths.

Implementation candidate; validation pending. No release or GitHub changes.

## October 27 local candidate and verification

Advanced Modern controls now offer Combat transparency, enabled by default. Disabling it replaces the native camera/aim opacity result only for the connected, owned Modern player in ordinary gameplay, while still computing the close-camera fade. Cinematics, Original controls and other actors are excluded. Existing profiles migrate with the previous behavior preserved.

A copied profile migrated through the real serializer to v8 and ran normal Play with the setting off. Of 1,701 calls to the actual native fade routine, 175 combat fades were removed and 1,344 close-camera fades were retained; the game exited cleanly. Configuration/UI checks also passed. Private evidence: remaining-gh-issues-20261027/opacity-028-analysis.json and opacity-026 capture. This is locally verified behavior, with owner batch review still pending.
