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

[Preview 0.4.0-preview.2](https://github.com/TK22-26/JetForceGemini-Recomp/releases/tag/v0.4.0-preview.2)
uses short build/dependency cache paths, enables Git long-path handling for
dependency downloads, and retries submodule initialization when a checkout
already exists. Its checked-command wrapper also preserves native stderr and
exit codes under PowerShell 5.1. These changes have automated coverage; the
reporter's complete Windows 10 installation sequence still needs a retest.

Firmware-virtualization detection, older WSL distribution handling, and
PowerShell prerequisite probes such as `Test-LinuxPackages` remain open.
Repeated restarts alone will not resolve every setup failure. The issue records
the reporter's workarounds; they are not a validated general automatic repair.
[Manual build setup](development/rom-bootstrap.md) is available for users
comfortable installing and checking prerequisites.

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

## Player shadow darkness

A maintainer reports that the shadow beneath the playable character looks
darker than on an N64 and emulator (2026-10-04). This is pending a matched
scene comparison and renderer investigation; no shadow correction has been
validated yet.

## Support reports

Preview 0.4.0-preview.2 supports session selection, filtered system/build details,
crash stacks and an on-demand freeze snapshot. Rebuild an older game to gain the
native capture features. Capture remains best effort: forced termination, early
startup failures, corrupted stacks or access restrictions can leave partial logs.
These are text stack snapshots, not full-memory dumps. See [playtesting](playtesting.md)
for the file inventory and attachment instructions. Nothing uploads automatically.

## Rotated chest approach

The tutorial Fish Food chest in room 122 is reachable on foot, but automatic
collection currently rejects its opening point. A captured live export identifies
the chest's own conservative world-aligned box as the blocker, including after
projecting staging points onto the floor. The opening region overlaps an empty
corner of that box. Precise chest collision geometry is needed before accepting
this approach; the nearby terrain wall must remain an obstacle. The old
"Proximity mines" label was separately corrected to Fish Food.
