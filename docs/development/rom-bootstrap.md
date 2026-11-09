# Build the game from your ROM

For downloads and the first-run path, start with [getting started](https://github.com/TK22-26/JetForceGemini-Recomp/blob/main/docs/getting-started.md)
and check [known setup issues](https://github.com/TK22-26/JetForceGemini-Recomp/blob/main/docs/known-issues.md#windows-10-setup).
The [launcher](https://github.com/TK22-26/JetForceGemini-Recomp/blob/main/docs/development/launcher.md)
automates everything below; this page is for manual setup and command-line use.

## Prerequisites

Install Git, Python 3.11 or newer, Visual Studio 2022 with **Desktop development
with C++** and CMake, and WSL2 with Ubuntu 24.04. Inside Ubuntu, install the
upstream build prerequisites:

```sh
sudo apt update
sudo apt install build-essential gcc-multilib binutils-mips-linux-gnu python3-venv python3-pip pkg-config cmake ninja-build git wget
```

## Build and play

From PowerShell at the repository root:

```powershell
python scripts/build/build_from_rom.py --rom 'D:\Games\my-copy.z64' --play
```

Or run `launcher/windows/Build-And-Play.ps1` to pick the ROM with a file
dialog. On develop, the script identifies the exact US, PAL or Japanese ROM
before downloading anything and normalizes supported byte orders into a
private copy. Modified or unknown revisions are rejected. Build time depends
on the host and configuration. US saves retain `%LOCALAPPDATA%\JFGRecomp\profiles\default`;
PAL and JP use revision subfolders beneath the shared profile.

The recipe clones the pinned dependencies, builds a fresh matching ELF in a
private WSL temporary directory, derives overlay boundaries from that build's
linker metadata, applies the pinned N64Recomp patch series, generates CPU and
audio code (the audio configuration comes from the ROM's DMA descriptors and
command table), and builds the Windows runtime. The upstream decompilation is
consulted locally; no upstream game source is copied into this repository. It
never accepts a maintainer-generated ELF, overlay layout, CPU root or audio
source as input.

## Regional builds on develop

The development pipeline admits the exact US, PAL and Japanese revisions in the
[ROM catalog](../../config/roms/revisions.json). Each uses the same extraction, program model,
CPU/audio generation and native runtime pipeline, with an immutable revision descriptor and
matching bundle. ROM byte order is normalized into a private copy; the input is preserved.
Launcher imports, build caches and save namespaces retain the revision identity. Published
v1.4.0 packages still support only their pinned US ROM.

`scripts/build/prepare_regional_metadata.py` remains a metadata-only developer entry point: it
validates matching ELF/map data, all 155 overlays and exact ROM reconstruction, but does not by
itself build a playable executable. Use the complete build workflow above for native output.
[Regional qualification](issues/regional-rom-support.md) records exact identities, native and
launcher evidence, remaining gameplay checks and release status.

The public source-build command uses the default original-OS CMake profile.
The locally supplied enhanced review build additionally selects the documented
native timing, collision and renderer optimization configuration. Build and
replay evidence identifies the actual configuration; a successful default
source build does not qualify every enhanced feature or measured performance.

## Workspaces and options

ROM copies, generated code, logs and binaries stay in the short per-checkout
cache `%LOCALAPPDATA%\JFG\b\<checkout-id>\w\<run-id>` and a private WSL
temporary directory, whose path is recorded in `linux-workspace.txt`. The
command prints the exact workspace. Do not upload either directory or add it
to a release or issue. Each normal run creates a fresh workspace; a failed run
keeps its files.

| Option | Use |
|---|---|
| `--resume-native <workspace>` | Resume after generation succeeded but compilation failed; pass the same `--rom` (and `--build-root`). Manifests and hashes are checked first. |
| `--build-root D:/JFG-builds` | Use a different short, writable cache location. |
| `--dependency-root <dir>` | Reuse an existing pinned upstream source/tool cache (IDO tools, repository objects); the ELF is still rebuilt. Checkouts at another revision are rejected unchanged. |
| `--generation-timeout <s>` | Bound the Linux process group (default one hour). |
| `--jobs <n>` | Build parallelism. |
| `--distro <name>` | Use a different installed WSL distribution. |

Legacy workspaces under `tools/private/local-builds` remain intact and can be
resumed when their native output path fits MSBuild's limit.

## Verification scope

The historical US workflow was verified end to end from its supported ROM: a fresh
ELF, CPU corpus and audio program, a compiled Windows runtime that reaches the
title, accepts menu input, saves to FlashRAM, relaunches into Goldwood gameplay
and exits cleanly, with zero unsupported device accesses. The v1.0 runtime also
passes the combined opening and Quarry timing validation recorded in the
[runtime fix log](https://github.com/TK22-26/JetForceGemini-Recomp/blob/main/docs/development/boot-gameplay-fix.md#quarry-audio-delay-and-original-guest-timing).

The current three-region enhanced candidates have separate fresh generation,
native build, launcher and bounded gameplay receipts. Public `--resume-native`
checks reject damaged generation inputs for all three and configuration passes.
A later public-default US compile test fails under an 8 GiB job memory ceiling;
serial compilation also reaches that ceiling. Its original logs are retained,
no larger-memory result is assumed, and current public-default compile/link
qualification remains open. This resource-bounded experiment does not replace
or invalidate the separately qualified enhanced bundles. See the
[current regional evidence](issues/regional-rom-support.md#additional-automated-check-continuation).

Public CI exercises the build recipe, native output paths, launcher compilation
and source policy without a ROM. A successful build establishes compilation,
not original-console parity; a pristine Windows installation with installer
elevation and reboot still needs playtesting.
