# Dependency inventory

Core repositories, revisions, recursive submodule pins, and tool records are
in [dependencies.lock.json](../../dependencies.lock.json). Launcher UI dependency
pins are in [its CMake file](../../launcher/ui/CMakeLists.txt); their notice
sources and hashes are in [notice provenance](../../launcher/ui/licenses/provenance.json).
Python validation
packages are pinned in [requirements-dev.lock.txt](../../requirements-dev.lock.txt).
The inspected license facts below apply to those pins; this is not a complete
transitive package bill of materials.

## Build and source dependencies

| Component | Role | Retained notice or record |
|---|---|---|
| N64Recomp | Local recompiler with maintained patches | [MIT notice](../../patches/n64recomp/LICENSE.upstream) |
| RT64 | Native renderer | [MIT notice](../../patches/rt64/LICENSE.upstream) |
| Plume | Graphics platform support | [MIT notice](../../patches/plume/LICENSE.upstream) |
| CIC-NUS-6105 algorithm | Challenge-response implementation | [X-Scale notice](../../patches/cic/LICENSE.upstream) and source attribution |
| N64ModernRuntime | Evaluated runtime reference; not the project's native bridge | GPL-3.0-only at the lock pin |
| JFG decompilation | Local build input and symbol-fact consultation | Attribution in [third-party notices](../../THIRD_PARTY_NOTICES.md) |

Other research-only entries remain recorded in the lockfile and
[reference catalog](../upstream/reference-catalog.json). They are not a list
of bundled runtime components. Preserve existing copyright, permission, and
disclaimer text in source and notice files.

## Launcher release dependencies

The standalone Windows launcher statically links RmlUi 6.3 at
`ba95ffe8bfb6370efb2cdcca927eaad4710c5413` and FreeType 2.14.1 at
`526ec5c47b9ebccc4754c85ac0c0cdf7c85a5e9b`. Its Win32/DX11 build uses RmlUi's
default robin_hood/itlib containers. The aggregate RmlUi target also links the
Debugger library; its font notice is retained even if unused assets are removed.

| Component | Scope and retained notice |
|---|---|
| RmlUi | [MIT](../../launcher/ui/licenses/RmlUi-MIT.txt) |
| robin_hood and itlib | RmlUi Core containers; [MIT notices](../../launcher/ui/licenses/RmlUi-Containers-MIT.txt) |
| Courier Prime Code and Italic | RmlUi Debugger assets; [OFL notice](../../launcher/ui/licenses/RmlUi-Debugger-OFL.txt) |
| FreeType | [FTL](../../launcher/ui/licenses/FreeType-FTL.txt), selected instead of the alternate GPL license |
| FreeType components | BDF/PCF, The Open Group, hashing, internal zlib and HarfBuzz-derived source; [exact notices](../../launcher/ui/licenses/FreeType-ThirdParty.txt) |
| Barlow and Chakra Petch | Embedded font files; [source/hash manifest](../../launcher/ui/fonts/manifest.json), [Barlow OFL](../../launcher/ui/fonts/Barlow-OFL.txt), [Chakra Petch OFL](../../launcher/ui/fonts/ChakraPetch-OFL.txt) |

External Zlib, BZip2, PNG, HarfBuzz and Brotli integrations are disabled in the
launcher's FreeType configuration. Disabling external Zlib does not remove
FreeType's internal gzip implementation. HarfBuzz-derived source notices are
retained although external HarfBuzz integration is disabled. Optional RmlUi
Lua, SVG, Lottie and other renderer backends are not enabled.

[THIRD-PARTY.txt](../../launcher/ui/THIRD-PARTY.txt) indexes the release's
`licenses/` directory. Packaging includes all retained notice texts, the font
manifest and notice provenance; it rejects absent referenced notice paths.
This describes the launcher package, not a redistribution of the locally built
game or every system/toolchain component. Existing toolchain review limitations
below still apply.

## Build and validation tools

These tools execute during ROM-free development or CI; they are not linked
into the host shell.

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

## Dependency changes

Review the exact source and recursive dependencies before changing pins.
Update the lock, required notices, and package inventory together. Packaging
needs its own complete dependency/SBOM review; a local build-tool inventory
does not describe everything in a release artifact.
