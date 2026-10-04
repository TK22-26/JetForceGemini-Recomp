# Known issues

Check this page before opening a report. It summarizes confirmed limitations
and links to current reports; [GitHub issues](https://github.com/TK22-26/JetForceGemini-Recomp/issues)
contain the ongoing discussion.

## Windows 10 setup

[Issue 4](https://github.com/TK22-26/JetForceGemini-Recomp/issues/4) reports four
setup failures with `v0.4.0-preview.1` and Windows PowerShell 5.1:

- Disabled firmware virtualization can lead to repeated restart instructions.
- Older WSL installations may reject the requested Ubuntu distribution.
- Missing Linux packages can cause the package check to stop setup.
- Long RT64 dependency paths can fail checkout; a retry can skip incomplete
  submodules left by the first attempt.

These installer fixes are pending. The issue records the reporter's workarounds;
they have not been validated as a general automatic repair. Repeated restarts
alone will not resolve every setup failure. [Manual build setup](development/rom-bootstrap.md)
is available for users comfortable installing and checking prerequisites.

## Release and source versions

Each released launcher builds its pinned source revision. `main` can contain
newer gameplay fixes, so include your launcher version and game/source build
when reporting. See [getting started](getting-started.md) for both paths and
[recent fixes](development/boot-gameplay-fix.md) for their validation scope.

## Controller coverage

The preview supports keyboard input and Xbox/XInput controllers. Other
controller types need an XInput-compatible driver or adapter. Native
DirectInput/HID mapping and rumble configuration are not implemented.

## Gameplay coverage

A maintainer playtest completed Goldwood and reached SS Anubis. Full campaign
completion and original-console accuracy remain unverified. Report a specific
failure with the location and reproduction steps using the
[playtesting guide](playtesting.md).

## Support reports

The current support ZIP contains filtered text logs. It exports the latest
session, so create it before starting another session after a failure.
Crash-dump and freeze-capture collection are not available in the released
reporting workflow.
