# Build the game from your ROM

For downloads and the first-run path, start with [getting started](https://github.com/TK22-26/JetForceGemini-Recomp/blob/main/docs/getting-started.md).
See [known setup issues](https://github.com/TK22-26/JetForceGemini-Recomp/blob/main/docs/known-issues.md#windows-10-setup) before installation.

This Windows x64 prototype starts with the supported US big-endian ROM and
creates a local native executable. The launcher can install missing developer
tools and obtain its pinned source checkout automatically. Open the standalone
EXE, choose your ROM, then click **Set up and build**. Administrator prompts and
a Windows restart may be needed; reopen the launcher to continue afterward.
See [the launcher guide](https://github.com/TK22-26/JetForceGemini-Recomp/blob/main/docs/development/launcher.md) for downloads, storage, and requirements.

For manual setup or command-line use, install Git, Python 3.11 or newer, Visual Studio 2022 with Desktop development
with C++ and CMake, and WSL2 with Ubuntu 24.04. Inside Ubuntu, install the
upstream build prerequisites:

```sh
sudo apt update
sudo apt install build-essential gcc-multilib binutils-mips-linux-gnu python3-venv python3-pip pkg-config cmake ninja-build git wget
```

From PowerShell at the repository root:

```powershell
python scripts/build_from_rom.py --rom 'D:\Games\my-copy.z64' --play
```

Alternatively, run `launcher/windows/Build-And-Play.ps1` in PowerShell to choose
the ROM using a file picker. The existing C# launcher can open the resulting
`jfg-native-boot.exe` on subsequent runs. Compilation can take several minutes.
The script validates the ROM before downloading dependencies. Other regions,
modified ROMs, and byte-swapped dumps are rejected.

The recipe clones the pinned dependencies, creates a fresh matching ELF in a
private WSL temporary directory, derives overlay boundaries from that build's
linker metadata, applies the pinned recompiler patch series, generates CPU and
audio code, and builds the live Windows runtime. It consults the upstream
decompilation locally; no upstream game source is copied into this repository.
Its generated audio configuration comes from the ROM's DMA descriptors and
command table. The host audio adapter under `src/bootstrap` is project code.

ROM copies, generated code, logs, and binaries remain under `tools/private/local-builds`
and a private WSL temporary directory. Both are local artifacts; do not upload
them or add them to a release. The local `linux-workspace.txt` identifies the
WSL folder retained for diagnosis. A failed run preserves its files. A normal
invocation creates a fresh build directory. If ROM generation completed but
Windows compilation failed, use `--resume-native tools/private/local-builds/BUILD-ID`
with the same `--rom` argument to resume compilation. The script checks the
generation manifest and hashes before resuming.

`--dependency-root` accepts an existing pinned upstream source/tool cache. This
can reuse IDO tools and repository objects; it creates a fresh Python environment.
The recipe always extracts and builds the matching ELF again. It never takes a
maintainer-generated ELF, overlay layout, CPU root, or audio source as input.

`--generation-timeout` bounds the Linux process group (default one hour).
`--jobs` controls build parallelism, and `--distro` selects a different installed
WSL distribution. Existing dependency checkouts at another revision are rejected
without changing them. Save files live in `%LOCALAPPDATA%\JFGRecomp\profiles\default`.

## Prototype verification

On 2026-10-01, the default dependency-download path produced a fresh matching ELF,
CPU corpus and audio program, then compiled the Windows x64 live runtime.
Development failures were corrected and native compilation resumed from those
locally generated inputs. No maintainer-generated game code was used as input.

A fresh save profile reached the title sequence with 592 rendered frames and
599 decoded audio tasks over 1,200 retraces. A second process accepted menu input
and preserved the profile. The new-game test committed 13 FlashRAM writes;
its save file changed and remained available for the next launch. Relaunching
reached playable Goldwood gameplay with 3,283 presented frames and 3,299 audio
tasks over 6,600 retraces. Further input tests moved the player through Goldwood
and fired three shots. The launcher's production launch path opened a live game
window and exited successfully after closing it.
These runs reported zero unsupported device accesses. Frames, audio,
ROM-derived code and detailed diagnostics remain local.

The launcher and setup tests use ROM-free fixtures. Public CI exercises the
build recipe, native output paths, launcher compilation, and source policy.
Neither CI nor compilation certifies a completed campaign. A pristine Windows
installation with installer elevation and reboot remains an outstanding
playtest of the setup flow.

A successful build establishes compilation. Game parity and campaign completion
remain open. Keep generated game code and binaries local.
