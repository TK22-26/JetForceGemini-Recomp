# Third-Party Dependency Status

The root MIT license covers original project contributions. Existing third-party
copyright and license notices retain their separate scope. It does not relicense
game content, generated ROM-derived output, or third-party code. Distribution of
a combined work must also satisfy every applicable dependency license, including
GPL requirements where GPL-covered components are used.

No third-party source tree or binary is vendored in this repository. External
repositories are cloned locally under the ignored `tools/` directory at commits
recorded in `dependencies.lock.json`.

The tracked N64Recomp patch series necessarily contains limited context from
the MIT-licensed upstream source. Its required copyright and permission notice
is preserved byte-for-byte from the locked upstream revision in
`patches/n64recomp/LICENSE.upstream`. That notice applies to the upstream
material represented in the patch payload; it does not change the license of
project-authored material.

The RT64/Plume compatibility edits embedded in `CMakeLists.txt` retain
the exact pinned MIT notices in `patches/rt64/LICENSE.upstream` and
`patches/plume/LICENSE.upstream`.

The CIC-NUS-6105 challenge-response algorithm in
`src/runtime/cic_nus_6105.cpp` is conservatively attributed to X-Scale (2011).
The complete upstream copyright, redistribution conditions, disclaimer and
views paragraph are retained both in that source and in
`patches/cic/LICENSE.upstream`. The source was inspected at BizHawk commit
`bdddf4a58aa1a022afb11dc73294a81a5aa7bbd5`, path
`libmupen64plus/mupen64plus-core/src/memory/n64_cic_nus_6105.c`.
The project integration uses C++ types and packed PIF RAM. This notice applies
to the upstream algorithm; the project license does not override upstream rights.

Five GPL-covered `scripts/oracle_*.patch` diagnostic patches are intentionally
absent from this public snapshot because the licensing of the modifications
has not been settled. Their associated license inventory is also omitted.
Historical documents may name these maintainer-local inputs. Workflows that
require them cannot run from this snapshot. See the
[publication audit](docs/legal/publication-audit.md).

The current candidates are:

| Component | Status |
|---|---|
| N64Recomp | MIT; local build tool candidate; tracked patch context carries `patches/n64recomp/LICENSE.upstream` |
| LLVM/Clang | Apache-2.0 WITH LLVM-exception; ignored local compiler toolchain |
| OpenSSH `ssh-keygen` | BSD-style/component-specific notices; OS-provided signature tool only |
| N64ModernRuntime | GPL-3.0; runtime candidate |
| RT64 | MIT; renderer candidate |
| Plume | MIT; embedded compatibility patch context carries `patches/plume/LICENSE.upstream` |
| CIC-NUS-6105 algorithm | X-Scale (2011), permissive two-condition notice retained in source and `patches/cic/LICENSE.upstream` |
| Mupen64Plus within BizHawk | External local oracle only; diagnostic patches excluded from this snapshot |
| Jet Force Gemini decompilation | No root license found; consulted facts-only for libultra identification (see attribution below) |
| RecompFrontend | No project-level license found; excluded pending permission |

## Attribution: Jet Force Gemini decompilation (facts-only consultation)

The Jet Force Gemini decompilation project
(https://github.com/Ryan-Myers/Jet-Force-Gemini) was **consulted** during
Phase 6 for the sole purpose of identifying which addresses in our own
generated set correspond to libultra (N64 SDK) functions. Only factual
symbol data — libultra function names (public SDK API) mapped to ROM
addresses — was used, to guide independently authored HLE implementations.
**No decomp source, headers, or implementation was copied.** The libultra
HLE code in this project is original work authored to the public SDK
contract (see `src/boot/PROVENANCE.md`).

The decomp carries no observed license, so this is a maintainer-approved
research consultation of factual metadata, not a grant of copy rights; it
does not affect the underlying game copyright.

This is an engineering inventory, not a final license opinion. The detailed
review and source links are in
`docs/legal/dependency-license-inventory.md`.
