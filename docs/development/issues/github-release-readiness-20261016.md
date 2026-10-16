# Open GitHub issue review before a full update (2026-10-16)

**Not all open reports are resolved. A full update is not yet release-qualified.** The owner accepted the current local game and amber updater design. That acceptance does not close independent GitHub reports.

Used `gh issue list --state open` and `gh issue view` with comments for all four open issues. The supplied startup support ZIP was read privately. Source and existing evidence were compared; no issue was closed, comment posted or release published.

| GitHub issue | Finding on this candidate | Release disposition |
|---|---|---|
| [#15 Linux compilation](https://github.com/TK22-26/JetForceGemini-Recomp/issues/15) | MSVC-only probe declarations and an unconditional Windows volume-file header remain | [Open Linux blocker](github-linux-native-build.md) |
| [#14 mouse-look startup crash](https://github.com/TK22-26/JetForceGemini-Recomp/issues/14) | Support log confirms access violation after ROM-ready; no stack or verified current-build remedy | [Open Windows qualification blocker](github-mouse-look-startup.md) |
| [#13 controller vertical camera](https://github.com/TK22-26/JetForceGemini-Recomp/issues/13) | Modern-controls GUI inversion persists and reverses camera/aim input; 790 UI checks pass | [Implemented/test-verified, reporter retest pending](github-controller-vertical-inversion.md) |
| [#4 Windows 10 source setup](https://github.com/TK22-26/JetForceGemini-Recomp/issues/4) | Native stderr, short paths, submodule retry and external recovery roots addressed; firmware/old-WSL gaps remain | [Partial; legacy source setup](github-windows-source-setup.md) |

The updater passes 78 UI assertions, 28 checker cases and a live packaged-helper check. It retains the accepted game runtime. The fresh setup fixture passes 15 assertions; it does not emulate an old WSL or disabled BIOS virtualization. No Linux/native gameplay experiments were launched during this launcher review. Existing higher-refresh guard counters and shelved investigations are preserved.

Before a broad release: reproduce and qualify #14, validate #15 on the actual Linux target if Linux is included, and resolve or explicitly scope the remaining legacy source-setup limitations. Obtain the reporter's controller confirmation when practical. Preserve the separate all-route/Unlimited/exit-cutscene limits in existing records; owner-reported smooth play does not certify every environment.

[Machine-readable audit](../../../evidence/github-release-readiness-20261016.json) and [updater qualification](../../../evidence/launcher-update-button.json). These results concern the local candidate, not retroactive changes to v1.1.0.
