# Development setup

Use this guide to build the host shell and run source tests without a ROM.
For the playable game, use [ROM build setup](rom-bootstrap.md).
For playtesting, start with [getting started](../getting-started.md).

## Requirements

- Git and Python 3.11 or newer.
- CMake 3.20 or newer and a C++20 compiler.
- Visual Studio 2022 with C++ tools on Windows, or Ninja with GCC/Clang on Linux.

Keep dependencies under ignored `tools/` and game inputs outside Git.
Automated agents must run checks through the supervisor required by
[AGENTS.md](../../AGENTS.md); the commands below describe the human workflow.

## Python environment and validation

```sh
python -m venv tools/venv
```

Activate it with `tools\venv\Scripts\Activate.ps1` in PowerShell or
`source tools/venv/bin/activate` in a Linux shell. Then run:

```sh
python -m pip install --require-hashes -r requirements-dev.lock.txt
python scripts/validate_project.py
python -m unittest discover -s tests -p "test_*.py" -v
```

## Windows builds

The build command locates CMake and Visual Studio automatically. It uses a
short, separate output directory for each checkout, including deep source paths:

```powershell
python scripts/build_windows.py --config Debug --test
python scripts/build_windows.py --config Release --test
```

Output lives in `%LOCALAPPDATA%\JFG\b\<checkout-id>\c`; the command prints
the exact path. Use `--build-root D:/JFG-builds` to choose another short, writable
local cache location. Existing source, builds and dependency caches are preserved.

## Linux builds

```sh
cmake --preset linux
cmake --build --preset linux
ctest --preset linux
```

These default targets build the host shell (`jfg`) and tests. The shell does
not run the game. The [ROM build recipe](rom-bootstrap.md) produces
`jfg-native-boot` for Windows playtesting.

## Choosing checks for a change

Run relevant focused tests while working and the applicable build/test suites
before submitting behavior changes. For documentation, inspect local links,
commands, and `git diff --check`. Run the repository hygiene check before pushing:

```sh
python scripts/check_repository_hygiene.py --history
```

[CI](https://github.com/TK22-26/JetForceGemini-Recomp/actions/workflows/ci.yml)
records the exact checks used for public pull requests. See
[test quarantine](../tests/quarantine.md) for the documented Linux test exclusion.

## RT64 shader header changes

The pinned RT64 build originally tracked shader entry files but omitted their
shared include files. Following [Luke Deardoff's report in issue #4](https://github.com/TK22-26/JetForceGemini-Recomp/issues/4#issuecomment-5985126218),
the host build now adds the shared .h and shader .hlsli dependency set
to the existing shader-generation commands. It leaves the upstream checkout
and shader contents unchanged. A header edit conservatively rebuilds shader
outputs; unchanged builds remain incremental. Added headers are discovered
at build time.

The jfg.rt64_shader_dependencies test uses synthetic files to check shared,
nested and newly added headers, downstream generated files, and unchanged
builds. It exercises DXIL, SPIR-V, Metal's shared SPIR-V input, and preprocessed
shader-source rules without requiring a ROM or shader compiler. Keep its
Visual Studio fixture outside Windows Temp and AppData: MSBuild excludes
both from dependency tracking. If the build cache lives there, the test uses
the source checkout's ignored build/shader-tests directory instead. Source
checkouts also inside those directories require an explicit --work-root
outside them when running the fixture directly.
