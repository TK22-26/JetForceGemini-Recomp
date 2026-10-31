# GH-058: [Playtest] Game starts but only shows black screen

Status: cause unverified; bounded presentation diagnostics locally tested; reporter evidence needed.

Source: [[Playtest] Game starts but only shows black screen](https://github.com/TK22-26/JetForceGemini-Recomp/issues/58). Evidence snapshot retained privately in D:/JFG-private/remaining-gh-issues-20261027/github-issues.json.

## Reported symptoms and reproduction

### Problem type

Graphics

### Launcher and game build

v1.40, NOT built locally.

### Windows version, GPU, and input device

Windows 10 Home Build 19045, NVIDIA RTX 4070 Ti Super, Controller (Nintendo Switch Controller, wired)

### What happened and how to reproduce it

Installed application, loaded ROM, got succes, can edit all the settings.
After pressing play, screen remains black but audio starts playing, can also hear the selector move and can confirm selection. So game seems to be running, but screen is black.
Tried all the video settings, but no success.

### How often does it happen?

Once so far

### Support ZIP and additional details

_No response_

## Scope and evidence

Local owner-authorized batch: investigate black video with working audio/input on Windows10. Preserve existing approved fixes, user profiles and ROMs. No GitHub posting or issue changes. A reported symptom is not yet a confirmed cause. Attempts, results, final remedy and verification limits will be recorded here.

## October 27 local investigation

The report supplies Windows 10 build 19045 and an RTX 4070 Ti Super, but no support ZIP or reproducible local state. Source review confirms that the game can run while its hosted presentation is hidden, so audio alone does not identify a renderer failure. No blanket Windows 10 fallback or speculative GPU workaround is applied.

A bounded diagnostic candidate now records the launcher's selected composition/window backend and HRESULT, plus hosted-game/viewport visibility, sizes, parent relationship, minimization and menu capture. It stores no paths, HWNDs, titles, screenshots or game data. The managed helper copies these allowlisted fields into the existing support ZIP during play and at exit. Backend fallback behavior is separately tested under GH-040. Validation of this new diagnostic is pending; the reporter's black-screen cause remains unverified.

## October 27 validation update

The new bounded support export passes 688 managed launcher checks, including archive preservation and rejection of private/malformed presentation fields, plus 28 setup checks. The native launcher shell also builds. The first test invocation used a private working directory rather than the source checkout required by the suite; rerunning the same executable with the correct working directory passed. This diagnostic is ready for batch review. No local reproduction establishes the reporter's cause, so this issue is not marked fixed.

## Assembled launcher check

The staged launcher completed an ordinary muted Play run and clean close with a separate copied profile. Its report includes the actual DirectComposition backend, successful HRESULT, valid hosted game/parent relationship, viewport sizes and hidden-window state. The intentionally hidden background host is correctly reported as invisible; no claim of an on-screen visual review is made. Exported fields contain no paths, titles or handles.

The first smoke test supplied a poll-ordered diagnostic input capture to the launcher's retrace-ordered replay option, and native boot rejected it with exit 3 before creating a renderer. That is an invalid test setup, not a reproduction of the reporter's running-but-black game. Rerunning ordinary Play passed. The staged executable's receipt was regenerated from its exact binary and matching symbols rather than copying an older build receipt.
