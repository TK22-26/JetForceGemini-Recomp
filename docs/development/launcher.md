# Windows ROM-to-play launcher

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

Source and generated output stay in `%LOCALAPPDATA%\JFGRecomp\source`; setup
diagnostics stay in `%LOCALAPPDATA%\JFGRecomp\setup.log`. Failed build diagnostics
also remain in that source checkout's `tools/private/local-builds` directory.
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

This is a development prototype. Campaign completion and full original-console
parity remain open. See [the handoff](https://github.com/TK22-26/JetForceGemini-Recomp/blob/launcher-preview/docs/development/handoff.md)
for known limitations and useful playtest reports.

## Build the launcher

```powershell
powershell -NoProfile -File scripts/build_launcher.ps1 -Test
python scripts/package_launcher.py
```

The C# launcher uses the Windows .NET Framework compiler and has no NuGet or
game dependency. Outputs remain under ignored `build/launcher`. Tests cover ROM
rejection, executable validation, argument forwarding, save preservation,
source discovery, setup argument forwarding, embedded-script restoration,
missing-tool installation plans, retries, ROM rejection before downloads, and UI rendering.

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
Please report installer failures with the stage and error, without uploading
your ROM, generated code, or raw build logs.
