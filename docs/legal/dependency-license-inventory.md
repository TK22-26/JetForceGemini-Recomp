# Dependency and license inventory

- Status: Phase 0-4 reviewed inventory; no distribution approval implied
- Snapshot date: 2026-08-04
- Final approval authority: Human maintainers

This inventory records engineering facts observed in pinned source trees,
package metadata, and project lock files. A recorded license name is not a
legal conclusion about copyright ownership, license compatibility, generated
output, game data, or distribution obligations. A publicly readable
repository is not permission to copy, modify, or redistribute unlicensed
content.

This is not yet a complete transitive software bill of materials. Unless a
row expressly says otherwise, every component is proposed for local
evaluation only and is not approved for linking, bundling, packaging, or
distribution.

## Phase 0-4 dependency-selection record

The Phase 2 host shell contains only project-authored targets and uses the
host C++ standard library. Its CMake configuration does not fetch, vendor, or
link a third-party runtime, renderer, UI, audio, or input library.

No UI, audio, or input library is selected for Phases 0-2. In particular,
RecompFrontend remains excluded because no project-level license was observed
at the inspected commit. N64ModernRuntime and RT64 remain architecture
candidates, and N64Recomp remains a candidate local build tool; none is a
bundled dependency of the Phase 2 shell. The Phase 4 patch payload does contain
limited upstream N64Recomp context, covered by the exact notice in
`patches/n64recomp/LICENSE.upstream`.

Final bundled dependency selection is deferred until feasibility evidence and
human license review establish the runtime, renderer, frontend, audio, and
input architecture. Deferral does not approve any candidate. The repository's
current `LICENSE` remains all-rights-reserved and grants no distribution
permission.

## Candidate repositories and research inputs

| Component | Snapshot commit | Observed top-level license evidence | Intended relationship | Current policy |
|---|---|---|---|---|
| [Jet Force Gemini decomp](https://github.com/Ryan-Myers/Jet-Force-Gemini) | `b49aa4791e8fb1e7acd3bba10346876358d0a9a7` | No root license observed | Local research and ELF/metadata input | Do not copy source, headers, or symbol exports. **Maintainer-approved exception (Phase 6): facts-only consultation of the symbol map — libultra function name → ROM address — to identify libultra addresses in the generated set. No source copied; identification detail stays private; HLE authored independently. Attributed in THIRD_PARTY_NOTICES.md.** This is a research-boundary decision, not a distribution grant or license opinion. |
| [N64Recomp](https://github.com/N64Recomp/N64Recomp) | `ffb39cdad1da5de07eaaa48bd1db4a89a7986771` | Byte-exact upstream MIT notice tracked at `patches/n64recomp/LICENSE.upstream` | Local build-time recompiler plus tracked source-context patch payload | Notice-bound patch context only; no broader distribution approval is implied, and the external source tree and binary remain local-only pending transitive and human review |
| [N64ModernRuntime](https://github.com/N64Recomp/N64ModernRuntime) | `589bbf018a3e6d3646ddf7de1e7919f1b7e99bb1` | `COPYING` contains GNU GPL version 3 text | Candidate linked runtime | Not selected or linked; architecture and license consequences require human review |
| [RecompFrontend](https://github.com/N64Recomp/RecompFrontend) | `9ef9cdfdead7649247ab4957f43517f44c33931d` | No root license observed | Excluded UI/input candidate | Do not copy, modify, link, or distribute pending written permission or replacement |
| [RT64](https://github.com/rt64/rt64) | `5473732a822a4423b5696e7cb18fecc425a59875` | `LICENSE` contains MIT text | Candidate renderer | Not selected or linked; local research only pending transitive review and a notice plan |
| [Zelda64Recomp](https://github.com/Zelda64Recomp/Zelda64Recomp) | `1a9c26613c6e0906140dc8bcca7362cbe00bf1eb` | `COPYING` contains GNU GPL version 3 text | Architecture research reference only | Do not copy game-specific source, patches, assets, or symbols |
| [BizHawk](https://github.com/TASEmulators/BizHawk) | `bdddf4a58aa1a022afb11dc73294a81a5aa7bbd5` (tag 2.11.1) | Root `LICENSE` describes mixed and potentially incompatible licensing across bundled cores | Local emulator oracle only | Do not redistribute the package; retain exact package and plug-in hashes and perform human review before any broader use |
| [GLideN64 executed component](https://github.com/gonetz/GLideN64) | `4f1f88a415630481a9ce58f11279e6ec94bbe2d1` | Root `LICENSE` states GNU GPL version 2 | Component pinned by BizHawk 2.11.1 and exercised locally | Oracle execution only; not a shipping dependency |
| [GLideN64 inspected candidate](https://github.com/gonetz/GLideN64) | `020b6ab5de1f13d8e673c0a23529f1de1e507c9d` | Root `LICENSE` states GNU GPL version 2 | Newer source-inspection reference | Counts and behavior scope only; do not copy implementation text |

Commit IDs identify inspected local snapshots. They are not dependency or
distribution approvals, and moving branches must not be consumed without a
lock update.

## Direct Phase 2-4 build and validation inputs

These tools execute during ROM-free development or CI; they are not linked
into the current host shell.

| Input | Version record | Observed license evidence | Status |
|---|---|---|---|
| CMake | Minimum `3.20`; exact developer version not locked | Not recorded in this inventory | Host build tool only |
| C++ compiler and standard library | C++20; Visual Studio 2022 and Ubuntu CI toolchains; exact packages not locked | Toolchain-specific and not yet inventoried | Host build tools/runtime; package review deferred |
| Python | CI requests `3.11`; developer interpreter not locked | Interpreter/package terms not inventoried here | Validation tool only |
| `attrs` | `26.1.0` | `License-Expression: MIT`; bundled `LICENSE` | Pinned validation dependency |
| `jsonschema` | `4.26.0` | `License-Expression: MIT`; bundled `COPYING` | Pinned validation dependency |
| `jsonschema-specifications` | `2025.9.1` | `License-Expression: MIT`; bundled `COPYING` | Pinned validation dependency |
| `referencing` | `0.37.0` | `License-Expression: MIT`; bundled `COPYING` | Pinned validation dependency |
| `rpds-py` | `2026.6.3` | `License-Expression: MIT`; bundled `LICENSE` | Pinned validation dependency |
| `typing_extensions` | `4.16.0` | `License-Expression: PSF-2.0`; bundled `LICENSE` | Pinned validation dependency |
| `actions/checkout` | Commit `3d3c42e5aac5ba805825da76410c181273ba90b1` | Action and transitive Node bundle review pending | Pinned CI action; read-only token policy |
| `actions/setup-python` | Commit `ece7cb06caefa5fff74198d8649806c4678c61a1` | Action and transitive Node bundle review pending | Pinned CI action; credentials are not persisted |
| LLVM/Clang portable Windows toolchain | Release `llvmorg-22.1.8`; archive SHA-256 `d96c2cc1736f4eb7fa43cb9bbdf56d93551a9ae0a9aadb9c99c3c3b2b712a234` | LLVM distribution identifies `Apache-2.0 WITH LLVM-exception` | Ignored local Phase 4 compiler only; downloaded from the official LLVM GitHub release into `tools/` and not redistributed |
| [OpenSSH `ssh-keygen`](https://github.com/openssh/openssh-portable) | OS-provided developer/CI executable; exact package version not locked | OpenSSH publishes BSD-style and component-specific license notices in its upstream `LICENCE` file | Subprocess-only Phase 4 Ed25519 signing and verification; only the generic public key is tracked, the private key remains ignored and local, and no OpenSSH binary is redistributed |

The exact Python validation versions are recorded in
`requirements-dev.lock.txt`. GitHub Action commits are recorded in
`dependencies.lock.json`. Recording an immutable version does not substitute
for a license or bundled-content review.

## Pinned upstream-decomp build inputs

The following inputs are used only inside the ignored local JFG decomp
checkout. None is vendored into this repository, and no decomp build output is
approved for Git or GitHub.

### Host packages

The pinned decomp README requires `build-essential`, `pkg-config`, `git`,
`python3`, `wget`, `python3-pip`, `binutils-mips-linux-gnu`, and
`python3-venv`. The Makefiles additionally invoke GNU Make, GCC, a MIPS
assembler/linker/objcopy/strip toolchain, `tar`, and standard POSIX shell
utilities.

These are distribution-provided packages rather than project pins. Their
exact versions, package patches, copyright files, compiler-runtime terms, and
redistribution obligations are not recorded here. They are approved only as
local operating-environment tools for Phase 1. Any future build image,
installer, SDK, or toolchain redistribution requires a separate package-level
inventory.

### Direct Python requirements

The version requirement comes from the pinned decomp's `requirements.txt`.
"Observed resolution" records local installed package metadata and is not a
project lock when the requirement permits a range.

| Package | Upstream requirement | Observed resolution | Observed package license metadata | Status |
|---|---|---|---|---|
| `splat64[mips]` | `==0.50.0` | `0.50.0` | `License: MIT License` | Exact direct pin; transitive `mips` extra remains to be inventoried |
| `spimdisasm` | `==1.42.3` | `1.42.3` | `License: MIT License` | Exact direct pin; also selected transitively by `splat64[mips]` |
| `pycparser` | `>=2.22` | `3.0` | `License-Expression: BSD-3-Clause` | Range is not reproducibly locked |
| `colorama` | `>=0.4.6` | `0.4.6` | BSD license classifier and bundled license file | Range is not reproducibly locked |
| `watchdog` | `>=6.0.0` | `6.0.0` | `License: Apache-2.0` | Range is not reproducibly locked |
| `Levenshtein` | `>=0.26.1` | `0.27.3` | `License-Expression: GPL-2.0-or-later` | Local build tool package; compatibility/output implications not determined |
| `cxxfilt` | `>=0.3.0` | `0.3.0` | `License: BSD`; precise SPDX expression not stated | Range is not reproducibly locked |
| `mapfile-parser` | `>=2.13.0` | `2.13.0` | Bundled MIT license text; no SPDX field observed | Range and transitive packages are not locked |
| `PyYAML` | `>=6.0.2` | `6.0.3` | `License: MIT` | Range is not reproducibly locked |
| `colour` | `>=0.1.5` | `0.1.5` | `License: BSD 3-Clause License` | Range is not reproducibly locked |

The complete resolved Python dependency graph and artifact hashes are not
tracked. Direct license labels do not classify transitive packages or the
license status of tool output.

### Git submodules and downloaded executables

| Input | Pin/source | Observed license evidence | Status |
|---|---|---|---|
| `asm-processor` | `b29ff12bf1d7cd1f49bf9a47b03e3ff3972ed973` | Root `LICENSE` identifies the Unlicense | Pinned upstream helper; local only |
| `asm-differ` | `5074289a13ced3a4ca4359c94d3f337d760a93ca` | Root `LICENSE` and package metadata identify the Unlicense | Pinned upstream helper; local only |
| `m2c` | `2853e096eb2368f601cd0f05119e98d74c2edca6` | Root `LICENSE` contains GPLv3 text; package metadata says `GPL-3.0-only` | Pinned upstream helper; local only |
| `ido-static-recomp` | Release tag `v1.2` selected by the decomp tools Makefile | License and bundled-notice evidence not captured in the tracked inventory | Downloaded executable; tag is recorded but artifact digest is not |
| `objdiff` / `objdiff-cli` | Release tag `v3.4.5` selected by the decomp tools Makefile | License and bundled-notice evidence not captured in the tracked inventory | Downloaded executables; tag is recorded but artifact digests are not |
| `n64crc` | Built from the pinned JFG decomp checkout | Covered only by the decomp repository's unresolved root-license status | Local build helper; do not redistribute |

The decomp tools Makefile downloads executable release artifacts with `wget`
and does not verify a tracked digest. Until hashes, provenance, and licenses
are recorded, those artifacts are permitted only for the isolated local Phase
1 reproduction and must not be cached, mirrored, or redistributed by this
project.

## Current license posture

The root project is all-rights-reserved and distribution is not authorized.
Keeping project-authored interfaces capable of supporting a GPLv3 runtime is
an engineering option, not a license selection or compatibility conclusion.
No candidate dependency changes the repository's current license merely by
being cloned or inspected locally.

Before selecting or linking a runtime, renderer, frontend, audio, or input
library, a human maintainer must approve:

1. The final dependency architecture and root project license.
2. Whether the selected components form a combined work and the applicable
   source, notice, relinking, or offer obligations.
3. Whether every dependency carries additional file-level notices,
   exceptions, bundled assets, or generated-output terms.
4. Whether RecompFrontend receives usable written permission or is replaced.
5. How generated code, symbols, decomp metadata, and patches are classified.
6. The source-offer, installer-notice, interactive-notice, and SBOM plan.

## Unlicensed upstream rule

Until written permission is recorded, unlicensed upstream source, headers,
matching code, and exported symbol files remain local research inputs only.
They MUST NOT be copied into commits, issues, pull requests, evidence bundles,
packages, releases, caches, or CI artifacts. Clean-room independently authored
interfaces require provenance and human review.

## Transitive inventory requirements

Every selected dependency must be expanded recursively before approval,
including:

- Git submodules and nested source repositories.
- CMake `FetchContent`, package-manager, and system-library dependencies.
- Python packages and downloaded executable release artifacts.
- Bundled fonts, icons, shaders, UI assets, examples, and test data.
- Compiler runtimes and redistributable platform components.
- GitHub Actions and release/packaging tools.
- Build-time generators whose output embeds licensed material.

Each inventory record requires:

| Field | Requirement |
|---|---|
| Name and upstream URL | Canonical project identity |
| Exact version | Commit, immutable archive digest, or package version |
| Use | Build, link, runtime, test, package, or research only |
| License | SPDX expression plus copied license/notice evidence |
| Linking/distribution form | Static, dynamic, subprocess, source, or data |
| Required actions | Attribution, source, notices, modifications, offers |
| Owner and review date | Accountable human and currency |
| Approval status | Proposed, approved-local, approved-distribution, blocked |

`NOASSERTION`, a missing license, an unknown nested dependency, or an
unresolved conflict blocks copying, linking, packaging, and distribution.

## Dependency acquisition policy

- External source checkouts live under ignored `tools/` paths.
- Approved versions are locked by full commit ID and verified source digest.
- Build scripts MUST NOT follow a moving branch or download executable tools
  without integrity verification.
- Third-party code is never copied from a research checkout into project code
  merely for convenience.
- Updates require license-diff review, provenance update, focused tests, and an
  SBOM diff.
- GitHub Actions are pinned to full-length commit IDs.

## Release gate

Distribution remains blocked until:

1. The recursive inventory has no unresolved license fields.
2. Human maintainers approve the root project license.
3. All required license texts and notices are included.
4. Corresponding-source, relinking, and source-offer obligations are
   satisfied.
5. The release SBOM exactly matches the built artifacts.
6. Protected-data scanning finds no ROM, asset, private corpus, unlicensed
   upstream copy, or unapproved generated output.
