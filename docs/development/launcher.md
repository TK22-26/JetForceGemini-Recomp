# Windows launcher prototype

The launcher can build a native runtime locally from your supported North
American ROM and open the resulting game. It stores saves in your Windows user
profile. The download contains the launcher and documentation; obtain the
source checkout separately and install the build tools before the first build.

## First build

1. Clone `https://github.com/TK22-26/JetForceGemini-Recomp.git` and select the
   `launcher-preview` branch for this prototype.
2. Follow [ROM build setup](https://github.com/TK22-26/JetForceGemini-Recomp/blob/launcher-preview/docs/development/rom-bootstrap.md)
   to install Python 3.11+, Git, Visual Studio 2022 C++/CMake and WSL2 Ubuntu 24.04.
3. Open `JFG-Launcher.exe` on Windows x64 and select your US big-endian `.z64` ROM.
4. Click **Build from ROM**. If prompted, select the source checkout folder.
   Dependencies are downloaded and game code is generated locally. This takes
   several minutes; the launcher displays the current stage.
5. When the build finishes, click **Launch game**. Future launches reuse the
   selected build and remembered ROM path.

Alternatively, use `launcher/windows/Build-And-Play.ps1` from the source tree
to select a ROM and build/launch in PowerShell. The command-line recipe also
supports resuming native compilation after successful generation.

An existing `jfg-native-boot.exe` can be selected in the second field. Its
matching `SDL2.dll`, `dxcompiler.dll` and `dxil.dll` must be beside it. The default
`jfg.exe` host shell cannot play the game and is rejected.

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
source discovery, the build command and UI rendering.

The ZIP uses a fixed allowlist: launcher executable, this guide, build setup
guide, and project license. It excludes the generated game executable, game
assets, runtime DLLs, ROM, saves, private diagnostics and compiler debug symbols.
Keep locally generated game output outside release archives. The repository's
license remains unchanged.
