# Windows ROM-to-play launcher

Start with [getting started](https://github.com/TK22-26/JetForceGemini-Recomp/blob/main/docs/getting-started.md)
for downloads, requirements, and known setup issues.

Download `JFG-Launcher.exe` from the public release on Windows x64 and select
your supported North American ROM. The launcher sets up the tools, builds the
game locally, and remembers the resulting executable for later play.

## First setup

1. Open the launcher and choose your US big-endian `.z64` ROM.
2. Click **Set up and build**. Setup explains the downloads before starting.
   Allow the official Windows installers when prompted.
3. If setup requests a Windows restart, restart, reopen the launcher and click
   **Set up and build** again. Your selections and saves are preserved.
4. When compilation finishes, click **Launch game**. Future launches reuse the
   game build and do not require setup or recompilation.

The first setup needs internet access and can download several GB. Allow ample
disk space for Visual Studio, Ubuntu, source dependencies, and generated build
files. Windows 10/11 x64 must support WSL2 with virtualization enabled. Microsoft
App Installer (`winget`) must be installed; setup gives instructions if it is
missing. Administrators can also install the tools manually using
[ROM build setup](https://github.com/TK22-26/JetForceGemini-Recomp/blob/main/docs/development/rom-bootstrap.md).

Setup detects and reuses existing tools. Missing components are Git for Windows,
Python 3.12, Visual Studio 2022 C++ Build Tools with CMake, WSL/Ubuntu 24.04, and
the Ubuntu compiler/build packages. It downloads this launcher's exact source
commit and the revisions in `dependencies.lock.json`. A modified source cache
is rejected while its files are preserved. Package installers retain their own
licenses. See Microsoft's [WinGet installation reference](https://learn.microsoft.com/en-us/windows/package-manager/winget/install)
and [WSL installation guide](https://learn.microsoft.com/en-us/windows/wsl/install).

Source stays in `%LOCALAPPDATA%\JFGRecomp\source`; setup diagnostics stay in
`%LOCALAPPDATA%\JFGRecomp\setup.log`. The source candidate stores generated
inputs, dependencies, game builds and build logs under the short per-checkout
cache `%LOCALAPPDATA%\JFG\b\<checkout-id>`. Earlier previews retain their
original `tools/private/local-builds` directories; no existing files are moved.
The selected ROM stays at its original path and is required when playing.
If you move it, select its new location in the launcher. An existing playable
build can be selected directly as `jfg-native-boot.exe` with its runtime DLLs.

The launcher checks the ROM size, byte order and full SHA-1 locally. It supports
the 32 MiB US revision with SHA-1 `493ced9008dbe932d6e91179b68e8630cf23a023`.
It does not download a ROM or upload diagnostics. The setup-guide button opens
the public instructions in your browser.

## Saves and controls

Saves and remembered file selections live under
`%LOCALAPPDATA%\JFGRecomp\profiles\default`. **Open saves** opens that folder.
Existing saves are preserved. Close the game before closing the launcher.
Only one launcher instance runs in a Windows session.

| Keys | Action |
| --- | --- |
| W, A, S, D | Analog movement |
| Shift | Full stick magnitude |
| Space or Z | A / jump |
| X / C | B / Z |
| Enter | Start |
| Q / E | L / R |
| I, J, K, L | C buttons |
| Arrow keys | D-pad |
| Escape | Exit |

**Controllers** detects Xbox/XInput devices, lets you choose the active controller,
remap all N64 buttons (including Start/pause), select the movement stick, invert
its axes, and adjust dead zones and trigger/stick thresholds. Click **Learn**,
release the controls, then press a button or move a stick. Save the mapping to
apply it on the next launch. **Restore defaults** restores the standard layout.
Mappings are stored as `controller.ini` alongside your default save profile.
If a controller disconnects, keyboard fallback remains available; automatic
selection uses the first connected XInput device. Other controller types need
an XInput-compatible driver or adapter. Native DirectInput/HID mapping and
rumble configuration are not implemented in this preview. Hardware coverage
still needs tester feedback; automated tests use synthetic controller samples.

Existing game builds must be rebuilt with this launcher version to consume the
mapping and write native support diagnostics. An older selected executable can
still produce an exit-code report but does not gain new runtime features.

## Reporting a problem

Launch through `JFG-Launcher.exe` to keep a local support session. If the game
crashes, click **Create support report**, inspect the ZIP if desired, and attach
it to a [playtest issue](https://github.com/TK22-26/JetForceGemini-Recomp/issues/new?template=playtest.yml).
Include the level/menu, what you pressed, what you expected and whether the
problem repeats. If Windows or the launcher closes unexpectedly, reopen the
launcher and create the report before starting another session.

The source candidate **0.4.0-preview.2** expands reports with session selection,
recognized setup/compiler errors, system/configuration details, game build and
symbol identity, automatic crash stacks and an on-demand **Capture freeze** action.
The released **0.4.0-preview.1** retains its original two-log exporter.

See [playtesting and reporting](../playtesting.md) for the file inventory, retention,
older-build behavior and GitHub attachment instructions, and
[support diagnostics](support-diagnostics.md) for maintainer validation.

## Build the launcher

```powershell
powershell -NoProfile -File scripts/build_launcher.ps1 -Test
python scripts/package_launcher.py
```

The C# launcher uses the Windows .NET Framework compiler and has no NuGet or
game dependency. Outputs remain under ignored `build/launcher`. Tests cover ROM
rejection, executable validation, argument forwarding, save preservation,
source discovery, setup argument forwarding, embedded-script restoration,
missing-tool installation plans, retries, ROM rejection before downloads, controller profile validation,
button capture, crash-process reporting, log bounds/redaction, archive contents, and UI rendering.

The ZIP uses a fixed allowlist: launcher executable, this guide, build setup
guide, and project license. It excludes the generated game executable, game
assets, runtime DLLs, ROM, saves, private diagnostics and compiler debug symbols.
Keep locally generated game output outside release archives. Original project
contributions use MIT; third-party notices retain their separate scope.
Packaging requires a clean committed source tree. The build receipt binds the
launcher to its source revision and installer.

A pristine Windows installation with UAC/reboot has not yet been tested end to
end. The local ROM-to-game build and launch were demonstrated separately; the
new setup flow has automated tests and a real pinned-source download check.
Please report installer failures with the stage, reproduction steps, and the
exported support ZIP.
