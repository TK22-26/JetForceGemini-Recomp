# Development Setup

## Data boundary

The repository builds and tests without a ROM. Keep the lawful user-supplied
ROM in the ignored `roms/` directory or outside the checkout. Never commit it
or upload it to GitHub, CI, logs, caches, or artifacts.

External repositories and downloaded tools belong under ignored `tools/`.
Private ROM layout coordinates belong in an untracked file outside the checkout
or under ignored `private-data/`; do not place them in source, documentation,
commands committed to the repository, logs, or evidence output.

## Validate the repository

```sh
python -m venv tools/venv
```

Activate the environment and install the pinned development package:

```sh
python -m pip install --require-hashes -r requirements-dev.lock.txt
python scripts/validate_project.py
python -m unittest discover -s tests -p "test_*.py" -v
```

## Windows host shell

Use CMake 3.20+ and Visual Studio 2022:

```powershell
cmake --preset windows-msvc
cmake --build --preset windows-msvc
ctest --preset windows-msvc
cmake --build --preset windows-msvc-release
ctest --preset windows-msvc-release
```

The executable intentionally exits with clear instructions when no ROM is
provided. It validates ROM size and byte order before reaching the future
hashing boundary.

## Linux/WSL upstream generation

The pinned matching decompilation rejects native Windows. Phase 1 therefore
uses Ubuntu under WSL2 or a clean Linux environment.

After WSL2 and Ubuntu are initialized:

```sh
sudo apt-get update
sudo apt-get install -y build-essential cmake ninja-build pkg-config git \
  python3 wget python3-pip binutils-mips-linux-gnu python3-venv
python3 scripts/bootstrap_tools.py
python3 scripts/build_upstream.py \
  --environment-id ubuntu-24.04 \
  --rom roms/<lawful-us-rom> \
  --overlay-layout private-data/phase1-overlay-layout.json
```

The private layout JSON has exactly three fields: `schema_version` set to `1`,
and integer `overlay_table_start` and `overlay_data_start` coordinates obtained
from the maintainer's lawful local analysis. The script validates the layout's
bounds, alignment, and pinned slot count but never includes either coordinate
in public evidence. A layout inside the checkout is accepted only when Git
confirms that the file is ignored.

The build script verifies the input SHA-1 before copying it into the ignored
upstream worktree, performs two clean builds, validates the ELF, linker map,
progress report, and overlay layout, and stores logs and per-environment
evidence only under ignored `tools/results/`. Use a second clean Linux
environment and `scripts/compare_phase1_evidence.py` to satisfy the Phase 1
cross-environment gate.

## Diagnostics

```sh
python scripts/doctor.py
python scripts/doctor.py --phase1 \
  --overlay-layout private-data/phase1-overlay-layout.json
```
