# Jet Force Gemini Native Recompilation

This repository contains host runtime code, build and validation tools,
tests, and planning for a native Jet Force Gemini recompilation project.
Project-authored code and permissively licensed upstream material are identified
in [the third-party notices](THIRD_PARTY_NOTICES.md).

This public snapshot starts with fresh Git history. Private development history,
ROM-derived outputs, and five emulator diagnostic patches with unresolved
licensing are excluded. See [the publication audit](docs/legal/publication-audit.md).

**This is a development repository, not a downloadable game.** A normal clone
builds the ROM-free host shell and tests. The experimental playable runtime
also needs locally generated inputs that are not included in Git.

New collaborators and testers should start with the
[repository handoff](docs/development/handoff.md). It explains what can be
built from a clone, the current gameplay limits, and the remaining tester setup.

The project does not provide the game ROM or extracted game content. A lawful
user-supplied North American retail ROM is required for local development. ROM
bytes, generated recompilation output, extracted assets, memory snapshots, save
states, and other ROM-derived expressive material must remain outside Git.

## Current state

The recorded local milestones through Phase 8 are complete:

- Phase 1 reproducibly validates the pinned upstream matching-decompilation
  build in two WSL environments.
- Phase 2 provides the ROM-free C++20 host shell, schemas, tests, and
  Windows/Linux CI lanes.
- Phase 3 closes the feasibility/G2 gate with regenerable private evidence
  and a public `go` decision later bound into the signed Phase 4 aggregate.
- Phase 4 compiles the complete generated CPU corpus and records the result in
  the signed `evidence/phase4-completion.json` manifest.
- Phase 5 provides the deterministic test kernel, replay/state-hash formats,
  and signed boundary-capture evidence.
- Phase 6 reaches stable scheduler/VI activity from the supported original
  entry path in three bit-identical native runs, with emulator parity, guarded
  MMIO accounting, AddressSanitizer coverage, and signed local-M2 evidence.
- Phase 7 records first-frame and representative gameplay rendering through RT64.
- Phase 8 records interactive graphics, input, audio, and save/relaunch scenarios.

Phase 9 remains open. Local Goldwood runs exercise combat, death/retry, and
transitions, but a complete campaign slice and finishable campaign are not
accepted. The latest documented original-OS comparison matches selected state
through update 1908 and diverges at update 1909; this is not complete runtime
parity. See the [comparison result](docs/planning/phase9-execution-frontier-1909.md).

See `docs/dashboard.md` for the detailed status and evidence links. Generated
code, ROM-backed inputs, and private evidence bodies remain local and ignored.
Binary and generated-output distribution remain subject to the recorded
legal/license decision. Source publication preparation is tracked separately in
[the publication handoff](docs/governance/publication-handoff.md).

## Windows ROM-to-play prototype

A [launcher prototype](docs/development/launcher.md) can generate and compile a
local game build from your ROM, then launch it with saves in your user profile.
The launcher downloads a pinned source checkout and installs missing Git,
Python, Visual Studio C++ and WSL/Ubuntu build tools on first setup. Windows may
require administrator approval and a restart; reopen the launcher to continue.
See [ROM build setup](docs/development/rom-bootstrap.md). No game executable,
ROM, extracted assets or generated game code is included in the launcher.

After installing the prerequisites, the command-line equivalent is:

```powershell
python scripts/build_from_rom.py --rom 'D:\Games\my-copy.z64' --play
```

## ROM-free build

Requirements:

- CMake 3.20 or newer
- Ninja on Linux (the `linux` preset uses the Ninja generator)
- A C++20 compiler
- Python 3.11 or newer for repository validation

On Windows with Visual Studio 2022:

```powershell
cmake --preset windows-msvc
cmake --build --preset windows-msvc
ctest --preset windows-msvc
python scripts/validate_project.py
```

On Linux:

```sh
cmake --preset linux
cmake --build --preset linux
ctest --preset linux
python3 scripts/validate_project.py
```

`jfg` is the Phase 2 host shell: it validates ROM metadata and does not execute
the game, even when given a ROM. The experimental target is `jfg-native-boot`,
which requires additional private build inputs. See
[development setup](docs/development/setup.md) and the
[handoff](docs/development/handoff.md) before attempting a playable build.

## Policies

Read `docs/legal/rom-and-assets-policy.md`, `SECURITY.md`, and
`CONTRIBUTING.md` before contributing.

## License

Original project code and documentation are available under the [MIT License](LICENSE).
Third-party components retain their own terms; see [the notices](THIRD_PARTY_NOTICES.md).
The license does not grant rights to Jet Force Gemini game code, assets, or trademarks.
